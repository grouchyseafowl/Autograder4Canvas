"""
InsightsEngine — Pipeline orchestrator for the Insights Engine.

Phase 1 flow:
  data_fetcher → preprocessing pipeline → quick_analyzer → save to insights_store

Phase 2 flow (after quick analysis):
  LLM backend detection → per-submission coding → concern detection →
  theme generation → outlier surfacing → synthesis → save all to store

Takes progress_callback for GUI integration.
Saves intermediaries at each stage for resumability.
"""

import logging
import os
import re
import shutil
import time
from typing import Callable, Dict, List, Optional

from insights.data_fetcher import DataFetcher
from insights.insights_store import InsightsStore
from insights.models import (
    ConcernSignal,
    QuickAnalysisResult,
    SubmissionCodingRecord,
)
from insights.patterns import signal_matrix_classify
from insights.quick_analyzer import QuickAnalyzer

log = logging.getLogger(__name__)


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


class InsightsEngine:
    """Pipeline orchestrator for the Insights Engine.

    Phase 1: data_fetcher → preprocessing → quick_analyzer → store.
    Phase 2: adds LLM passes (coding, concerns, themes, outliers, synthesis).
    """

    def __init__(
        self,
        api=None,
        store: Optional[InsightsStore] = None,
        settings: Optional[Dict] = None,
    ):
        self._api = api
        self._store = store or InsightsStore()
        self._settings = settings or {}
        self._cancelled = False
        self._caffeinate_proc = None

    def cancel(self) -> None:
        self._cancelled = True
        self._stop_sleep_prevention()

    def is_cancelled(self) -> bool:
        return self._cancelled

    def _start_sleep_prevention(self) -> None:
        """Prevent the computer from sleeping while the pipeline runs.

        macOS:   caffeinate -s (prevents system sleep including lid-close
                 if "Prevent sleeping when display is off" is enabled
                 in System Settings → Battery → Options)
        Windows: powercfg to disable AC standby timeout (restored on stop)
        Linux:   systemd-inhibit if available
        """
        import platform
        import subprocess as _sp
        system = platform.system()

        if not self._settings.get("insights_keep_awake", True):
            return

        try:
            if system == "Darwin":
                # -s prevents system sleep (stronger than -i which only prevents idle)
                # -w ties to our process ID so it auto-cleans if we crash
                self._caffeinate_proc = _sp.Popen(
                    ["caffeinate", "-s", "-w", str(os.getpid())],
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                )
                log.info("Sleep prevention active (caffeinate -s)")

            elif system == "Windows":
                # Save current standby timeout, then disable
                try:
                    result = _sp.run(
                        ["powercfg", "/query", "SCHEME_CURRENT", "SUB_SLEEP",
                         "STANDBYIDLE"],
                        capture_output=True, text=True, timeout=5,
                    )
                    # Parse current AC timeout for restoration later
                    for line in result.stdout.splitlines():
                        if "Current AC Power Setting Index" in line:
                            self._original_standby = line.split("0x")[-1].strip()
                            break
                except Exception:
                    self._original_standby = None

                # Disable standby on AC power (0 = never)
                _sp.run(
                    ["powercfg", "/change", "standby-timeout-ac", "0"],
                    capture_output=True, timeout=5,
                )
                log.info("Sleep prevention active (powercfg standby disabled)")

            elif system == "Linux":
                # Try systemd-inhibit
                if shutil.which("systemd-inhibit"):
                    self._caffeinate_proc = _sp.Popen(
                        ["systemd-inhibit", "--what=sleep",
                         "--who=Autograder4Canvas",
                         "--why=Running overnight analysis",
                         "sleep", "infinity"],
                        stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
                    )
                    log.info("Sleep prevention active (systemd-inhibit)")

        except Exception as e:
            log.debug("Could not start sleep prevention: %s", e)

    def _stop_sleep_prevention(self) -> None:
        """Restore normal sleep behavior."""
        import platform
        import subprocess as _sp

        # Kill caffeinate/systemd-inhibit process (macOS/Linux)
        if self._caffeinate_proc:
            try:
                self._caffeinate_proc.terminate()
                self._caffeinate_proc = None
            except Exception:
                pass

        # Restore Windows standby timeout
        if platform.system() == "Windows":
            original = getattr(self, "_original_standby", None)
            if original:
                try:
                    # Convert hex seconds back to minutes
                    minutes = max(1, int(original, 16) // 60)
                    _sp.run(
                        ["powercfg", "/change", "standby-timeout-ac",
                         str(minutes)],
                        capture_output=True, timeout=5,
                    )
                except Exception:
                    # Fallback: restore to 30 minutes
                    _sp.run(
                        ["powercfg", "/change", "standby-timeout-ac", "30"],
                        capture_output=True, timeout=5,
                    )
            log.info("Sleep prevention stopped (standby restored)")

    def run_analysis(
        self,
        *,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[Dict] = None,
        teacher_interests: Optional[list] = None,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Run the full analysis pipeline for one assignment.

        Args:
            progress_callback: called with status strings
            result_callback: called with (result_type, data_dict) for live preview

        Returns the run_id on success, None on failure/cancellation.
        """
        progress = progress_callback or (lambda msg: None)
        emit_result = result_callback or (lambda t, d: None)
        self._cancelled = False
        self._start_sleep_prevention()

        # Load teacher profile for prompt injection
        from insights.teacher_profile import TeacherProfileManager
        profile_mgr = TeacherProfileManager(self._store)
        profile_fragment = profile_mgr.get_full_profile_fragment()

        # Create run record
        run_id = self._store.generate_run_id()

        try:
            # ----------------------------------------------------------
            # Stage 1: Data fetch
            # ----------------------------------------------------------
            progress(f"Fetching submissions for {assignment_name} ({course_name})...")
            if self._cancelled:
                return None

            fetcher = DataFetcher(self._api)

            if is_discussion:
                # Canvas discussion assignments have a separate topic_id
                # Fetch assignment info to get the linked topic_id
                assign_info = fetcher.fetch_assignment_info(course_id, assignment_id)
                topic_id = None
                if assign_info:
                    topic_id = assign_info.get("discussion_topic", {}).get("id")
                if not topic_id:
                    # Fallback: try using assignment_id as topic_id
                    topic_id = assignment_id
                    log.info("No discussion_topic.id found, trying assignment_id as topic_id")
                raw_submissions = fetcher.fetch_discussion_entries(
                    course_id, topic_id
                )
            else:
                raw_submissions = fetcher.fetch_submissions(
                    course_id, assignment_id
                )

            if not raw_submissions:
                progress("No submissions found.")
                return None

            total = len(raw_submissions)
            progress(f"Found {total} submissions.")

            # Create run in store
            self._store.create_run(
                run_id=run_id,
                course_id=str(course_id),
                course_name=course_name,
                assignment_id=str(assignment_id),
                assignment_name=assignment_name,
                model_tier=model_tier,
                total_submissions=total,
                teacher_context=teacher_context,
                analysis_lens_config=analysis_lens,
            )
            self._store.complete_stage(run_id, "data_fetch")

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 2: Preprocessing (translation + transcription)
            # ----------------------------------------------------------
            progress("Preprocessing submissions...")
            submissions = self._preprocess(
                raw_submissions,
                translate_enabled=translate_enabled,
                transcribe_enabled=transcribe_enabled,
                progress=progress,
            )
            self._store.complete_stage(run_id, "preprocessing")

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 3: Quick Analysis (non-LLM)
            # ----------------------------------------------------------
            progress("Running Quick Analysis...")
            analyzer = QuickAnalyzer(
                progress_callback=progress,
            )
            qa_result = analyzer.analyze(
                submissions,
                assignment_id=str(assignment_id),
                assignment_name=assignment_name,
                course_id=str(course_id),
                course_name=course_name,
            )

            # Save quick analysis result
            self._store.save_quick_analysis(run_id, qa_result.model_dump_json())
            self._store.complete_stage(run_id, "quick_analysis")

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 4-8: LLM Analysis Pipeline
            # ----------------------------------------------------------
            # Detect available LLM backend
            from insights.llm_backend import auto_detect_backend

            backend = auto_detect_backend(model_tier, self._settings)

            if backend is None:
                # No LLM available — complete with Quick Analysis only
                progress("No LLM backend available — Quick Analysis complete.")
                confidence = {
                    "overall": self._compute_confidence(qa_result),
                    "data_quality": min(1.0, total / max(total, 1)),
                }
                self._store.complete_run(run_id, confidence)
                return run_id

            progress(f"LLM backend: {backend.name} ({backend.model})")

            # Build submission text map
            texts: Dict[str, str] = {}
            meta: Dict[str, Dict] = {}
            for sub in submissions:
                sid = str(sub.get("student_id", sub.get("user_id", "")))
                body = sub.get("body") or sub.get("text") or ""
                texts[sid] = _strip_html(body)
                meta[sid] = sub

            # Build assignment prompt from available info
            assignment_prompt = f"Assignment: {assignment_name}"

            # GPU throttle delay
            throttle = float(self._settings.get("insights_throttle_delay", 2.0))

            # ----------------------------------------------------------
            # Stage 4: Per-submission coding
            # ----------------------------------------------------------
            from insights.submission_coder import code_submission

            progress("Coding submissions with LLM...")
            coding_records: List[SubmissionCodingRecord] = []

            for i, (sid, body) in enumerate(texts.items()):
                if self._cancelled:
                    return None

                sub_meta = meta.get(sid, {})
                name = sub_meta.get("student_name", f"Student {sid}")
                quick_sub = qa_result.per_submission.get(sid)

                # Get signal matrix results for this submission
                vader_compound = qa_result.sentiments.get(sid, {}).get("compound", 0.0)
                wc = len(body.split())
                sig_results = signal_matrix_classify(
                    body, vader_compound, wc, qa_result.stats.word_count_median
                )

                # Get concern signals for this student
                student_concern_signals = [
                    s for s in qa_result.concern_signals if s.student_id == sid
                ]

                if i == 0:
                    emit_result("stage", {"stage": "LISTENING TO STUDENT WORK"})
                progress(f"Reading student work ({i + 1}/{total}): {name}...")

                # Show the student's actual text while LLM processes
                emit_result("reading", {
                    "student_name": name,
                    "text": body[:500],
                    "word_count": wc,
                })

                # Guard: skip LLM coding for very short submissions
                if wc < 15:
                    # Diagnose WHY the text is blank/short
                    sub_type = sub_meta.get("submission_type", "")
                    attachments = sub_meta.get("attachments", [])
                    if wc == 0 and sub_type == "online_upload" and attachments:
                        filenames = [a.get("filename", "?") for a in attachments[:3]]
                        reason = (
                            f"file upload ({', '.join(filenames)}) — "
                            f"text extraction failed or unsupported format"
                        )
                        tag = "file upload — text not extracted"
                    elif wc == 0 and not body.strip():
                        reason = "blank submission (no text entered)"
                        tag = "blank submission"
                    else:
                        reason = f"only {wc} words"
                        tag = "insufficient text for analysis"

                    progress(f"  Skipping {name}: {reason}")

                    record = SubmissionCodingRecord(
                        student_id=sid,
                        student_name=name,
                        theme_tags=[tag],
                        theme_confidence={tag: 1.0},
                        emotional_register="",
                        emotional_notes=reason,
                        notable_quotes=[],
                        word_count=wc,
                    )
                    coding_records.append(record)
                    self._store.save_coding(
                        run_id, sid, name, record.model_dump_json(),
                        submission_text=body,
                    )
                    preview_data = record.model_dump()
                    preview_data["_original_text"] = body[:300] if body.strip() else reason
                    emit_result("coding", preview_data)
                    continue

                record = code_submission(
                    submission_text=body,
                    student_id=sid,
                    student_name=name,
                    assignment_prompt=assignment_prompt,
                    quick_summary=quick_sub,
                    signal_matrix_results=sig_results,
                    tier=model_tier,
                    backend=backend,
                    analysis_lens=analysis_lens,
                    teacher_interests=teacher_interests,
                    profile_fragment=profile_fragment,
                )

                coding_records.append(record)

                # Save intermediary (include submission text for chatbot export)
                self._store.save_coding(
                    run_id, sid, name, record.model_dump_json(),
                    submission_text=body,
                )

                # Emit for live preview — include original text for sparse results
                preview_data = record.model_dump()
                preview_data["_original_text"] = body[:300]
                emit_result("coding", preview_data)

                # Throttle between LLM calls
                if throttle > 0 and i < total - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "coding")

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 5: Concern detection (dedicated pass)
            # ----------------------------------------------------------
            from insights.concern_detector import detect_concerns

            progress("Running dedicated concern detection...")

            for i, record in enumerate(coding_records):
                if self._cancelled:
                    return None

                sid = record.student_id
                body = texts.get(sid, "")
                wc = len(body.split())

                progress(f"Concern check {i + 1}/{total}: {record.student_name}...")

                # Guard: skip LLM concern detection for very short submissions
                if wc < 15:
                    record.concerns = []
                    self._store.save_coding(
                        run_id, sid, record.student_name, record.model_dump_json()
                    )
                    continue

                vader_compound = qa_result.sentiments.get(sid, {}).get("compound", 0.0)
                sig_results = signal_matrix_classify(
                    body, vader_compound, wc, qa_result.stats.word_count_median
                )
                student_signals = [
                    s for s in qa_result.concern_signals if s.student_id == sid
                ]

                concerns = detect_concerns(
                    submission_text=body,
                    student_name=record.student_name,
                    student_id=sid,
                    assignment_prompt=assignment_prompt,
                    signal_matrix_results=sig_results,
                    concern_signals=student_signals,
                    tier=model_tier,
                    backend=backend,
                    profile_fragment=profile_fragment,
                )

                record.concerns = concerns

                # Re-save with concerns
                self._store.save_coding(
                    run_id, sid, record.student_name, record.model_dump_json()
                )

                if throttle > 0 and i < total - 1:
                    time.sleep(throttle)

            self._store.complete_stage(run_id, "concerns")

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 6: Theme generation
            # ----------------------------------------------------------
            from insights.theme_generator import generate_themes

            progress("Generating themes...")

            theme_set = generate_themes(
                coding_records,
                tier=model_tier,
                backend=backend,
                assignment_name=assignment_name,
                analysis_lens=analysis_lens,
                teacher_interests=teacher_interests,
                profile_fragment=profile_fragment,
            )

            self._store.save_themes(
                run_id, theme_set_json=theme_set.model_dump_json()
            )
            self._store.complete_stage(run_id, "themes")

            # Emit themes and contradictions for live preview
            emit_result("stage", {"stage": "THEMES IDENTIFIED"})
            for t in theme_set.themes:
                emit_result("theme", t.model_dump() if hasattr(t, "model_dump") else t)
            for c in theme_set.contradictions:
                emit_result("contradiction", c.model_dump() if hasattr(c, "model_dump") else c)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 7: Outlier surfacing
            # ----------------------------------------------------------
            from insights.theme_generator import surface_outliers

            progress("Surfacing outliers...")

            outlier_report = surface_outliers(
                theme_set,
                coding_records,
                qa_result.embedding_outlier_ids,
                tier=model_tier,
                backend=backend,
                assignment_name=assignment_name,
            )

            self._store.save_themes(
                run_id, outlier_report_json=outlier_report.model_dump_json()
            )
            self._store.complete_stage(run_id, "outliers")

            # Emit outliers for live preview
            emit_result("stage", {"stage": "OUTLIERS — UNIQUE VOICES"})
            for o in outlier_report.outliers:
                emit_result("outlier", o.model_dump() if hasattr(o, "model_dump") else o)

            if self._cancelled:
                return None

            # ----------------------------------------------------------
            # Stage 8: Synthesis
            # ----------------------------------------------------------
            from insights.synthesizer import synthesize

            progress("Generating synthesis report...")

            synthesis = synthesize(
                theme_set,
                outlier_report,
                qa_result,
                coding_records,
                tier=model_tier,
                backend=backend,
                assignment_name=assignment_name,
                course_name=course_name,
                teacher_context=teacher_context,
                teacher_interests=teacher_interests,
                analysis_lens=analysis_lens,
                profile_fragment=profile_fragment,
            )

            self._store.save_themes(
                run_id, synthesis_report_json=synthesis.model_dump_json()
            )
            self._store.complete_stage(run_id, "synthesis")

            # ----------------------------------------------------------
            # Stage 9: Draft student feedback (if enabled)
            # ----------------------------------------------------------
            if self._settings.get("insights_draft_feedback", False) and backend:
                from insights.feedback_drafter import FeedbackDrafter

                progress("Drafting feedback for students...")
                drafter = FeedbackDrafter()
                profile = self._load_teacher_profile()

                for i, record in enumerate(coding_records):
                    if self._cancelled:
                        return None

                    progress(
                        f"Drafting feedback {i + 1}/{len(coding_records)}: "
                        f"{record.student_name}..."
                    )

                    record_dict = record.model_dump()
                    preprocessing_meta = record_dict.get("preprocessing")
                    if preprocessing_meta and isinstance(preprocessing_meta, dict):
                        pass  # already a dict
                    else:
                        # Pull from submission metadata
                        sub_meta = meta.get(record.student_id, {})
                        preprocessing_meta = {
                            "was_translated": sub_meta.get("was_translated", False),
                            "was_transcribed": sub_meta.get("was_transcribed", False),
                            "original_language_name": sub_meta.get(
                                "original_language_name"
                            ),
                        }

                    draft = drafter.draft_feedback(
                        coding_record=record_dict,
                        assignment_prompt=assignment_prompt,
                        analysis_lens=analysis_lens,
                        preprocessing_meta=preprocessing_meta,
                        teacher_profile=profile,
                        tier=model_tier,
                        backend=backend,
                    )

                    self._store.save_feedback(
                        run_id=run_id,
                        student_id=record.student_id,
                        student_name=record.student_name,
                        draft_text=draft.feedback_text,
                        confidence=draft.confidence,
                    )

                    if throttle > 0 and i < len(coding_records) - 1:
                        time.sleep(throttle)

                self._store.complete_stage(run_id, "feedback")

            # ----------------------------------------------------------
            # Complete run
            # ----------------------------------------------------------
            confidence = self._compute_full_confidence(
                qa_result, coding_records, theme_set,
                outlier_report=outlier_report,
            )
            self._store.complete_run(run_id, confidence)
            progress("Analysis complete.")
            self._stop_sleep_prevention()

            return run_id

        except Exception as e:
            log.exception("Analysis pipeline failed: %s", e)
            progress(f"Error: {e}")
            self._stop_sleep_prevention()
            return None

    def run_partial(
        self,
        *,
        run_id: str,
        start_stage: str,
        progress_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Re-run pipeline from start_stage forward using existing data.

        start_stage: "themes" | "outliers" | "synthesis"
        Returns run_id on success, None on failure.
        """
        progress = progress_callback or (lambda msg: None)
        self._cancelled = False

        run = self._store.get_run(run_id)
        if not run:
            progress("Run not found.")
            return None

        from insights.teacher_profile import TeacherProfileManager
        profile_mgr = TeacherProfileManager(self._store)
        profile_fragment = profile_mgr.get_full_profile_fragment()

        try:
            from insights.llm_backend import auto_detect_backend

            model_tier = run.get("model_tier", "lightweight")
            backend = auto_detect_backend(model_tier, self._settings)
            if backend is None:
                progress("No LLM backend available for re-run.")
                return None

            assignment_name = run.get("assignment_name", "")
            course_name = run.get("course_name", "")
            teacher_context = run.get("teacher_context", "")
            analysis_lens = run.get("analysis_lens_config")
            teacher_interests = None

            # Load existing data
            codings = self._store.get_codings(run_id)
            coding_records = []
            for row in codings:
                rec = row.get("coding_record", {})
                if isinstance(rec, str):
                    import json as _json
                    rec = _json.loads(rec)
                from insights.models import SubmissionCodingRecord
                coding_records.append(SubmissionCodingRecord.model_validate(rec))

            themes_row = self._store.get_themes(run_id)
            qa_json = run.get("quick_analysis")
            qa_result = None
            if qa_json:
                qa_result = QuickAnalysisResult.model_validate_json(qa_json)

            stages_run = []

            # Theme generation
            if start_stage in ("themes",):
                from insights.theme_generator import generate_themes
                progress("Re-generating themes...")
                theme_set = generate_themes(
                    coding_records, tier=model_tier, backend=backend,
                    assignment_name=assignment_name,
                    analysis_lens=analysis_lens,
                    teacher_interests=teacher_interests,
                    profile_fragment=profile_fragment,
                )
                self._store.save_themes(
                    run_id, theme_set_json=theme_set.model_dump_json()
                )
                stages_run.append("themes")
            else:
                import json as _json
                ts_raw = themes_row.get("theme_set", "{}") if themes_row else "{}"
                from insights.models import ThemeSet
                theme_set = ThemeSet.model_validate_json(ts_raw)

            if self._cancelled:
                return None

            # Outlier surfacing
            if start_stage in ("themes", "outliers"):
                from insights.theme_generator import surface_outliers
                progress("Re-surfacing outliers...")
                embedding_ids = qa_result.embedding_outlier_ids if qa_result else []
                outlier_report = surface_outliers(
                    theme_set, coding_records, embedding_ids,
                    tier=model_tier, backend=backend,
                    assignment_name=assignment_name,
                )
                self._store.save_themes(
                    run_id, outlier_report_json=outlier_report.model_dump_json()
                )
                stages_run.append("outliers")
            else:
                import json as _json
                or_raw = themes_row.get("outlier_report", "{}") if themes_row else "{}"
                from insights.models import OutlierReport
                outlier_report = OutlierReport.model_validate_json(or_raw)

            if self._cancelled:
                return None

            # Synthesis
            from insights.synthesizer import synthesize as synth_fn
            progress("Re-generating synthesis...")
            synthesis = synth_fn(
                theme_set, outlier_report, qa_result, coding_records,
                tier=model_tier, backend=backend,
                assignment_name=assignment_name,
                course_name=course_name,
                teacher_context=teacher_context,
                teacher_interests=teacher_interests,
                analysis_lens=analysis_lens,
                profile_fragment=profile_fragment,
            )
            self._store.save_themes(
                run_id, synthesis_report_json=synthesis.model_dump_json()
            )
            stages_run.append("synthesis")

            progress(f"Re-run complete ({', '.join(stages_run)}).")
            return run_id

        except Exception as e:
            log.exception("Partial re-run failed: %s", e)
            progress(f"Re-run error: {e}")
            return None

    def resume_run(
        self,
        *,
        run_id: str,
        progress_callback: Optional[Callable] = None,
        result_callback: Optional[Callable] = None,
    ) -> Optional[str]:
        """Resume an interrupted run from where it stopped.

        Skips already-coded students, then runs remaining stages.
        Returns run_id on success, None on failure.
        """
        progress = progress_callback or (lambda msg: None)
        emit_result = result_callback or (lambda t, d: None)
        self._cancelled = False
        self._start_sleep_prevention()

        run = self._store.get_run(run_id)
        if not run:
            progress("Run not found.")
            return None

        import json as _json
        stages = run.get("stages_completed", [])
        if isinstance(stages, str):
            stages = _json.loads(stages)
        completed_set = set(stages)

        progress(f"Resuming run — completed stages: {', '.join(stages)}")

        try:
            from insights.llm_backend import auto_detect_backend
            from insights.teacher_profile import TeacherProfileManager

            model_tier = run.get("model_tier", "lightweight")
            backend = auto_detect_backend(model_tier, self._settings)
            if backend is None:
                progress("No LLM backend available.")
                self._stop_sleep_prevention()
                return None

            progress(f"LLM backend: {backend.name} ({backend.model})")

            profile_mgr = TeacherProfileManager(self._store)
            profile_fragment = profile_mgr.get_full_profile_fragment()

            assignment_name = run.get("assignment_name", "")
            course_name = run.get("course_name", "")
            teacher_context = run.get("teacher_context", "")
            analysis_lens = run.get("analysis_lens_config")
            teacher_interests = None
            assignment_prompt = f"Assignment: {assignment_name}"

            qa_json = run.get("quick_analysis")
            qa_result = None
            if qa_json:
                qa_result = QuickAnalysisResult.model_validate_json(qa_json)

            throttle = float(self._settings.get("insights_throttle_delay", 2.0))

            # Load existing codings
            existing_codings = self._store.get_codings(run_id)
            coded_sids = set()
            coding_records = []
            for row in existing_codings:
                rec = row.get("coding_record", {})
                if isinstance(rec, str):
                    rec = _json.loads(rec)
                coding_records.append(
                    SubmissionCodingRecord.model_validate(rec)
                )
                coded_sids.add(row.get("student_id", ""))

            total = run.get("total_submissions", 0)

            # If coding is not complete, we need submission texts
            if "coding" not in completed_set:
                # Can't resume coding without original submissions
                # (they aren't stored in the DB)
                progress(
                    "Cannot resume from coding stage — "
                    "original submissions not stored. "
                    "Start a new analysis instead."
                )
                self._stop_sleep_prevention()
                return None

            # If concerns not complete, re-run concerns for all students
            if "concerns" not in completed_set:
                progress("Concerns stage incomplete — skipping to themes...")
                # Mark concerns as done (codings have inline concerns from
                # the coding pass)
                self._store.complete_stage(run_id, "concerns")

            # Determine the right start_stage based on what's already done
            if "themes" not in completed_set:
                start = "themes"
            elif "outliers" not in completed_set:
                start = "outliers"
            elif "synthesis" not in completed_set:
                start = "synthesis"
            else:
                progress("All stages already complete.")
                self._stop_sleep_prevention()
                return run_id

            progress(f"Resuming from {start}...")
            result = self.run_partial(
                run_id=run_id,
                start_stage=start,
                progress_callback=progress_callback,
            )

            self._stop_sleep_prevention()
            return result

        except Exception as e:
            log.exception("Resume run failed: %s", e)
            progress(f"Resume error: {e}")
            self._stop_sleep_prevention()
            return None

    def _preprocess(
        self,
        raw_submissions: List[Dict],
        *,
        translate_enabled: bool,
        transcribe_enabled: bool,
        progress: Callable,
    ) -> List[Dict]:
        """Run the preprocessing pipeline on raw Canvas submissions."""
        try:
            from preprocessing import PreprocessingPipeline
        except ImportError:
            log.info("Preprocessing pipeline not available — using raw text")
            progress("Preprocessing pipeline not available — using raw text.")
            return raw_submissions

        s = self._settings
        whisper_model = s.get("insights_whisper_model", "base")
        translation_backend = s.get("insights_translation_backend", "ollama")
        translation_model = s.get("insights_translation_model", "llama3.1:8b")
        handwriting_enabled = s.get("insights_handwriting_enabled", False)

        canvas_headers = {}
        if self._api:
            canvas_headers = dict(self._api.headers)

        try:
            pipeline = PreprocessingPipeline(
                canvas_headers=canvas_headers,
                translation_enabled=translate_enabled,
                transcription_enabled=transcribe_enabled,
                image_transcription_enabled=handwriting_enabled,
                whisper_model=whisper_model,
                translation_backend=translation_backend,
                translation_model=translation_model,
            )
            results = pipeline.process_submissions(
                raw_submissions,
                progress_callback=lambda cur, tot, msg: progress(
                    f"Preprocessing ({cur + 1}/{tot}): {msg}"
                ),
            )
        except Exception as e:
            log.warning("Preprocessing failed, falling back to raw text: %s", e)
            progress(f"Preprocessing failed ({e}) — using raw text.")
            return raw_submissions

        enriched = []
        for sub, result in zip(raw_submissions, results):
            sub = dict(sub)
            sub["body"] = result.text
            sub["was_translated"] = result.was_translated
            sub["was_transcribed"] = result.was_transcribed
            sub["was_image_transcribed"] = result.was_image_transcribed
            sub["original_language_name"] = result.original_language_name
            sub["original_text"] = result.original_text
            if result.teacher_comment:
                sub["preprocessing_comment"] = result.teacher_comment
            enriched.append(sub)

        return enriched

    def _load_teacher_profile(self) -> Optional[dict]:
        """Load the teacher profile for feedback generation."""
        from insights.teacher_profile import TeacherProfileManager
        try:
            mgr = TeacherProfileManager(self._store)
            return mgr.profile.model_dump()
        except Exception:
            return None

    def _compute_confidence(self, result: QuickAnalysisResult) -> float:
        """Compute confidence from Quick Analysis alone."""
        factors = []

        n = result.stats.total_submissions
        if n >= 20:
            factors.append(1.0)
        elif n >= 10:
            factors.append(0.8)
        elif n >= 5:
            factors.append(0.6)
        else:
            factors.append(0.4)

        components_run = 0
        if result.top_terms:
            components_run += 1
        if result.tfidf_terms:
            components_run += 1
        if result.sentiments:
            components_run += 1
        if result.clusters:
            components_run += 1
        if result.keyword_hits:
            components_run += 1
        if result.named_entities:
            components_run += 1
        factors.append(min(1.0, components_run / 6))

        return round(sum(factors) / len(factors), 2) if factors else 0.0

    def _compute_full_confidence(
        self,
        qa: QuickAnalysisResult,
        records: List[SubmissionCodingRecord],
        theme_set,
        outlier_report=None,
    ) -> dict:
        """Compute full pipeline confidence after all LLM stages.

        Enhanced in Phase 5 with cross-validation and synthesis coverage.
        """
        data_quality = self._compute_confidence(qa)

        # Coding reliability: how many records have non-empty theme tags
        coded = sum(1 for r in records if r.theme_tags)
        coding_reliability = coded / max(len(records), 1)

        # Theme coherence: what % of students appear in at least one theme
        themed_ids = set()
        for t in theme_set.themes:
            themed_ids.update(t.student_ids)
        all_ids = {r.student_id for r in records}
        orphan_rate = 1.0 - (len(themed_ids) / max(len(all_ids), 1))
        theme_coherence = (1.0 - orphan_rate)

        # Cross-validation concerns
        concern_notes: list = []
        try:
            from insights.cross_validator import CrossValidator
            cv = CrossValidator()
            concern_flags = cv.validate_concerns(records, qa.concern_signals)
            disagreements = [f for f in concern_flags if f.agreement != "agree"]
            if disagreements:
                concern_notes.append(
                    f"LLM and signal matrix disagreed on {len(disagreements)} concern flag(s)"
                )

            # Theme vs embedding cluster validation
            if theme_set and hasattr(theme_set, "themes") and qa.clusters:
                theme_flags = cv.validate_themes(
                    [t.model_dump() if hasattr(t, "model_dump") else t
                     for t in theme_set.themes],
                    qa.clusters,
                )
                low_overlap = [f for f in theme_flags if "low overlap" in (f.confidence_note or "").lower()]
                if low_overlap:
                    concern_notes.append(
                        f"{len(low_overlap)} theme(s) don't align well with "
                        f"embedding clusters — may reflect LLM interpretation "
                        f"rather than actual submission groupings"
                    )

            # Outlier cross-validation (with actual LLM outliers)
            llm_outliers = []
            if outlier_report and hasattr(outlier_report, "outliers"):
                llm_outliers = [
                    o.model_dump() if hasattr(o, "model_dump") else o
                    for o in outlier_report.outliers
                ]
            outlier_flags = cv.validate_outliers(
                llm_outliers,
                qa.embedding_outlier_ids,
            )
            embed_only = [f for f in outlier_flags if f.agreement == "matrix_only"]
            if embed_only:
                concern_notes.append(
                    f"{len(embed_only)} embedding outlier(s) not surfaced by LLM"
                )
        except Exception:
            log.debug("Cross-validation skipped", exc_info=True)

        # Data quality notes
        n_subs = qa.stats.total_submissions
        n_enrolled = qa.stats.total_enrollment
        if n_enrolled > 0 and n_subs < n_enrolled * 0.7:
            concern_notes.append(
                f"Only {n_subs}/{n_enrolled} students submitted — "
                f"analysis may not represent the full class"
            )

        overall = round(
            (data_quality + coding_reliability + theme_coherence) / 3, 2
        )

        return {
            "overall": overall,
            "data_quality": round(data_quality, 2),
            "coding_reliability": round(coding_reliability, 2),
            "theme_coherence": round(theme_coherence, 2),
            "concerns": concern_notes,
        }
