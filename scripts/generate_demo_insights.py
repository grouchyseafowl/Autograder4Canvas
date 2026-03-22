#!/usr/bin/env python3
"""
Generate Demo Insights — Steps 4+7 of the DAIGT Testing Brief.

Runs the full InsightsEngine pipeline (stage-by-stage, bypassing DataFetcher)
on the assembled demo corpus. Captures wall-clock timing at each stage.
Outputs baked JSON files to src/demo_assets/.

Usage:
    python scripts/generate_demo_insights.py [--course ethnic_studies|biology|both]
                                              [--small-batch N]
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Add src/ to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_DIR = ROOT / "data" / "demo_corpus"
ASSETS_DIR = ROOT / "src" / "demo_assets"
TIMING_PATH = ROOT / "data" / "demo_source" / "pipeline_timing.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate_demo_insights")


# ──────────────────────────────────────────────────────────────
# Configuration per course
# ──────────────────────────────────────────────────────────────

COURSES = {
    "ethnic_studies": {
        "course_id": "90003",
        "course_name": "Ethnic Studies (11), Period 3",
        "assignment_id": "113002",
        "assignment_name": "Week 6 Discussion: Intersectionality in Practice",
        "teacher_context": (
            "This is a weekly discussion board. Students respond to a reading about "
            "intersectionality theory applied to everyday life. Complete/incomplete grading — "
            "150 word minimum. I'm looking for genuine engagement with the concepts, not "
            "polished academic writing."
        ),
        "corpus_file": "ethnic_studies.json",
        "output_file": "insights_ethnic_studies.json",
        "run_id": "demo-insights-run-eth-studies-000000000001",
    },
    "biology": {
        "course_id": "90005",
        "course_name": "Biology, Period 6",
        "assignment_id": "115001",
        "assignment_name": "Lab Reflection: Cell Respiration",
        "teacher_context": (
            "Lab reflection for the cell respiration experiment. Students measured "
            "CO2 output under different conditions and are asked to reflect on what "
            "the data showed them. Complete/incomplete, 100 word minimum."
        ),
        "corpus_file": "biology.json",
        "output_file": "insights_biology.json",
        "run_id": "demo-insights-run-bio-lab-0000000000001",
    },
}


# ──────────────────────────────────────────────────────────────
# Pipeline runner
# ──────────────────────────────────────────────────────────────

def run_pipeline(course_key: str, small_batch: int = 0,
                 backend_override=None, output_suffix: str = "") -> dict:
    """Run the full Insights pipeline for one course, capturing timing.

    Args:
        backend_override: Optional BackendConfig to use instead of default Ollama.
        output_suffix: If set, appended to output filename (e.g., "_sonnet").
    """
    cfg = COURSES[course_key]
    timing = {}

    # Load corpus
    corpus_path = CORPUS_DIR / cfg["corpus_file"]
    corpus = json.loads(corpus_path.read_text())
    if small_batch > 0:
        corpus = corpus[:small_batch]
    total = len(corpus)
    print(f"\n{'═'*60}")
    print(f"  Pipeline: {cfg['course_name']}")
    print(f"  Students: {total}")
    print(f"{'═'*60}")

    # ── Build submission dicts (as QuickAnalyzer expects) ──
    submissions = []
    for s in corpus:
        submissions.append({
            "student_id": s["student_id"],
            "student_name": s["student_name"],
            "body": s["text"],
            "submission_type": "online_text_entry",
            "word_count": s.get("word_count", len(s["text"].split())),
            "submitted_at": "2026-03-08T22:00:00Z",
            "due_at": "2026-03-08T23:59:00Z",
        })

    # ── Stage 1: Quick Analysis (non-LLM) ──
    from insights.quick_analyzer import QuickAnalyzer
    from insights.models import QuickAnalysisResult

    print("\n[Stage 1] Quick Analysis...")
    t0 = time.time()
    qa = QuickAnalyzer()
    qa_result = qa.analyze(
        submissions,
        assignment_id=cfg["assignment_id"],
        assignment_name=cfg["assignment_name"],
        course_id=cfg["course_id"],
        course_name=cfg["course_name"],
    )
    timing["quick_analysis"] = round(time.time() - t0, 2)
    print(f"  Done: {timing['quick_analysis']}s — "
          f"{qa_result.stats.total_submissions} submissions, "
          f"{len(qa_result.clusters)} clusters, "
          f"{len(qa_result.concern_signals)} concern signals")

    # ── Detect LLM backend ──
    from insights.llm_backend import BackendConfig, auto_detect_backend
    from settings import load_settings

    if backend_override:
        backend = backend_override
    else:
        # Use the user's configured backend (from GUI settings)
        user_settings = load_settings()
        backend = auto_detect_backend("lightweight", user_settings)
        if backend is None:
            # Fallback to hardcoded Ollama if nothing detected
            log.warning("No backend detected from settings, falling back to Ollama")
            backend = BackendConfig(
                name="ollama",
                model="llama3.1:8b",
                base_url="http://localhost:11434",
            )

    # Determine tier from backend
    tier = "lightweight"
    if backend.name == "cloud" and "sonnet" in backend.model:
        tier = "medium"
    elif backend.name == "cloud" and "opus" in backend.model:
        tier = "deep_thinking"

    print(f"\n[LLM Backend] {backend.name} / {backend.model} (tier={tier})")

    # ── Stage 2: Per-submission coding ──
    from insights.submission_coder import code_submission
    from insights.models import SubmissionCodingRecord, PerSubmissionSummary
    from insights.patterns import signal_matrix_classify
    import re

    def _strip_html(text):
        return re.sub(r"<[^>]+>", " ", text)

    # Build text/meta maps
    texts: Dict[str, str] = {}
    meta: Dict[str, dict] = {}
    for sub in submissions:
        sid = str(sub["student_id"])
        texts[sid] = _strip_html(sub.get("body", ""))
        meta[sid] = sub

    assignment_prompt = f"Assignment: {cfg['assignment_name']}"

    print(f"\n[Stage 2] Coding {total} submissions...")
    t0 = time.time()
    coding_records: List[SubmissionCodingRecord] = []
    per_student_times = []

    for i, (sid, body) in enumerate(texts.items()):
        sub_meta = meta[sid]
        name = sub_meta.get("student_name", f"Student {sid}")
        wc = len(body.split())

        # Get signal matrix results
        vader_compound = qa_result.sentiments.get(sid, {}).get("compound", 0.0)
        sig_results = signal_matrix_classify(
            body, vader_compound, wc, qa_result.stats.word_count_median
        )

        # Get concern signals for this student
        student_signals = [
            s for s in qa_result.concern_signals if s.student_id == sid
        ]

        quick_sub = qa_result.per_submission.get(sid)

        # Guard: skip LLM coding for very short submissions
        if wc < 15:
            record = SubmissionCodingRecord(
                student_id=sid, student_name=name,
                theme_tags=["insufficient text for analysis"],
                theme_confidence={"insufficient text for analysis": 1.0},
                emotional_register="", emotional_notes=f"only {wc} words",
                notable_quotes=[], word_count=wc,
            )
            coding_records.append(record)
            continue

        # Guard: skip LLM coding for gibberish submissions
        if quick_sub and quick_sub.is_gibberish:
            print(f"  [{i+1}/{total}] {name} — skipped (gibberish: {quick_sub.gibberish_reason})")
            record = SubmissionCodingRecord(
                student_id=sid, student_name=name,
                theme_tags=["non-analyzable text"],
                theme_confidence={"non-analyzable text": 1.0},
                emotional_register="",
                emotional_notes=f"Gibberish gate: {quick_sub.gibberish_detail}",
                notable_quotes=[], word_count=wc,
            )
            coding_records.append(record)
            continue

        st = time.time()
        record = code_submission(
            submission_text=body,
            student_id=sid,
            student_name=name,
            assignment_prompt=assignment_prompt,
            quick_summary=quick_sub,
            signal_matrix_results=sig_results,
            tier=tier,
            backend=backend,
        )
        per_student_times.append(time.time() - st)
        coding_records.append(record)

        if (i + 1) % 5 == 0 or i == total - 1:
            avg = sum(per_student_times) / len(per_student_times)
            print(f"  Coded {i+1}/{total} — last: {per_student_times[-1]:.1f}s, avg: {avg:.1f}s")

        # Throttle (reduced for batch generation)
        if i < total - 1:
            time.sleep(0.5)

    timing["coding_total"] = round(time.time() - t0, 2)
    if per_student_times:
        timing["coding_per_student_avg"] = round(
            sum(per_student_times) / len(per_student_times), 2
        )
    print(f"  Coding complete: {timing['coding_total']}s "
          f"(avg {timing.get('coding_per_student_avg', 0)}s/student)")

    # ── Stage 3: Concern detection ──
    from insights.concern_detector import detect_concerns

    print(f"\n[Stage 3] Concern detection...")
    t0 = time.time()
    for i, record in enumerate(coding_records):
        sid = record.student_id
        body = texts.get(sid, "")
        wc = len(body.split())
        if wc < 15:
            record.concerns = []
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
            tier=tier,
            backend=backend,
        )
        record.concerns = concerns

        if (i + 1) % 10 == 0 or i == total - 1:
            print(f"  Checked {i+1}/{total}")

    timing["concerns"] = round(time.time() - t0, 2)
    concern_count = sum(len(r.concerns) for r in coding_records)
    print(f"  Concerns complete: {timing['concerns']}s — {concern_count} total flags")

    # ── Stage 4: Theme generation ──
    from insights.theme_generator import generate_themes

    print(f"\n[Stage 4] Theme generation...")
    t0 = time.time()
    theme_set = generate_themes(
        coding_records,
        tier=tier,
        backend=backend,
        assignment_name=cfg["assignment_name"],
    )
    timing["themes"] = round(time.time() - t0, 2)
    print(f"  Themes complete: {timing['themes']}s — "
          f"{len(theme_set.themes)} themes, "
          f"{len(theme_set.contradictions)} contradictions")

    # ── Stage 5: Outlier surfacing ──
    from insights.theme_generator import surface_outliers

    print(f"\n[Stage 5] Outlier surfacing...")
    t0 = time.time()
    outlier_report = surface_outliers(
        theme_set,
        coding_records,
        qa_result.embedding_outlier_ids,
        tier=tier,
        backend=backend,
        assignment_name=cfg["assignment_name"],
    )
    timing["outliers"] = round(time.time() - t0, 2)
    print(f"  Outliers complete: {timing['outliers']}s — "
          f"{len(outlier_report.outliers)} outliers")

    # ── Stage 6: Synthesis ──
    from insights.synthesizer import synthesize

    print(f"\n[Stage 6] Synthesis report...")
    t0 = time.time()
    synthesis = synthesize(
        theme_set,
        outlier_report,
        qa_result,
        coding_records,
        tier=tier,
        backend=backend,
        assignment_name=cfg["assignment_name"],
        course_name=cfg["course_name"],
        teacher_context=cfg["teacher_context"],
    )
    timing["synthesis"] = round(time.time() - t0, 2)
    print(f"  Synthesis complete: {timing['synthesis']}s")

    # ── Stage 7: Draft feedback ──
    from insights.feedback_drafter import FeedbackDrafter

    print(f"\n[Stage 7] Drafting feedback...")
    t0 = time.time()
    drafter = FeedbackDrafter()
    feedback_rows = []

    for i, record in enumerate(coding_records):
        draft = drafter.draft_feedback(
            coding_record=record.model_dump(),
            assignment_prompt=assignment_prompt,
            tier=tier,
            backend=backend,
        )

        feedback_rows.append({
            "run_id": cfg["run_id"],
            "student_id": record.student_id,
            "student_name": record.student_name,
            "draft_text": draft.feedback_text,
            "approved_text": None,
            "status": "pending",
            "confidence": round(draft.confidence, 2),
            "posted_at": None,
        })

        if (i + 1) % 10 == 0 or i == total - 1:
            print(f"  Drafted {i+1}/{total}")

    timing["feedback"] = round(time.time() - t0, 2)
    print(f"  Feedback complete: {timing['feedback']}s")

    # ── Total timing ──
    timing["total"] = round(sum(v for v in timing.values() if isinstance(v, (int, float))), 2)
    timing["students"] = total
    timing["per_student_total"] = round(timing["total"] / total, 2)

    print(f"\n{'─'*40}")
    print(f"  TOTAL: {timing['total']}s ({timing['per_student_total']}s/student)")
    for stage, t in timing.items():
        if stage not in ("total", "students", "per_student_total", "coding_per_student_avg"):
            print(f"    {stage}: {t}s")
    print(f"{'─'*40}")

    # ── Normalize synthesis sections (8B model sometimes omits keys) ──
    REQUIRED_SECTIONS = [
        "what_students_said", "emergent_themes",
        "tensions_and_contradictions", "surprises", "focus_areas",
        "concerns", "divergent_approaches", "looking_ahead",
        "students_to_check_in_with",
    ]
    synth_dict = json.loads(synthesis.model_dump_json())
    sections = synth_dict.get("sections", {})
    for key in REQUIRED_SECTIONS:
        if key not in sections:
            sections[key] = "(Insufficient data for this section.)"
    synth_dict["sections"] = sections
    # Re-serialize with normalized sections
    from insights.models import SynthesisReport
    synthesis = SynthesisReport.model_validate(synth_dict)

    # ── Assemble baked JSON ──
    stages_completed = [
        "data_fetch", "preprocessing", "quick_analysis",
        "coding", "concerns", "themes", "outliers", "synthesis",
    ]

    run_record = {
        "run_id": cfg["run_id"],
        "course_id": cfg["course_id"],
        "course_name": cfg["course_name"],
        "assignment_id": cfg["assignment_id"],
        "assignment_name": cfg["assignment_name"],
        "started_at": "2026-03-08T16:45:00+00:00",
        "completed_at": "2026-03-08T17:12:00+00:00",
        "model_tier": tier,
        "model_name": backend.model,
        "total_submissions": total,
        "stages_completed": stages_completed,
        "pipeline_confidence": {"overall": 0.82},
        "teacher_context": cfg["teacher_context"],
        "analysis_lens_config": {"lens": "equity_attention"},
        "quick_analysis": qa_result.model_dump_json(),
    }

    codings_list = []
    for record in coding_records:
        sid = record.student_id
        codings_list.append({
            "run_id": cfg["run_id"],
            "student_id": sid,
            "student_name": record.student_name,
            "coding_record": record.model_dump(),
            "submission_text": texts.get(sid, ""),
            "teacher_edited": 0,
            "teacher_edits": None,
            "teacher_notes": None,
        })

    themes_record = {
        "theme_set": theme_set.model_dump_json(),
        "outlier_report": outlier_report.model_dump_json(),
        "synthesis_report": synthesis.model_dump_json(),
    }

    demo_json = {
        "run": run_record,
        "codings": codings_list,
        "themes": themes_record,
        "feedback": feedback_rows,
    }

    # Save
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out_name = cfg["output_file"]
    if output_suffix:
        out_name = out_name.replace(".json", f"{output_suffix}.json")
    out_path = ASSETS_DIR / out_name
    out_path.write_text(json.dumps(demo_json, indent=2, default=str))
    print(f"\n  Saved baked JSON: {out_path}")
    print(f"  File size: {out_path.stat().st_size / 1024:.0f} KB")

    return timing


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", default="both",
                        choices=["ethnic_studies", "biology", "both"])
    parser.add_argument("--small-batch", type=int, default=0,
                        help="Limit to N students (for quick testing)")
    parser.add_argument("--backend", default="ollama",
                        choices=["ollama", "sonnet", "opus"],
                        help="LLM backend: ollama (local 8B), sonnet, or opus")
    parser.add_argument("--output-suffix", default="",
                        help="Suffix for output files (e.g., '_sonnet')")
    args = parser.parse_args()

    # Build backend config
    from insights.llm_backend import BackendConfig
    backend_override = None
    output_suffix = args.output_suffix

    if args.backend == "sonnet":
        backend_override = BackendConfig(
            name="cloud",
            model="claude-sonnet-4-20250514",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            api_format="anthropic",
        )
        output_suffix = output_suffix or "_sonnet"
    elif args.backend == "opus":
        backend_override = BackendConfig(
            name="cloud",
            model="claude-opus-4-20250514",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            api_format="anthropic",
        )
        output_suffix = output_suffix or "_opus"

    all_timing = {}

    courses = (["ethnic_studies", "biology"] if args.course == "both"
               else [args.course])

    for course_key in courses:
        try:
            timing = run_pipeline(
                course_key,
                small_batch=args.small_batch,
                backend_override=backend_override,
                output_suffix=output_suffix,
            )
            all_timing[course_key] = timing
        except Exception as e:
            log.exception(f"Pipeline failed for {course_key}: {e}")
            all_timing[course_key] = {"error": str(e)}

    # Save timing report
    timing_path = TIMING_PATH
    if output_suffix:
        timing_path = TIMING_PATH.with_name(
            TIMING_PATH.stem + output_suffix + TIMING_PATH.suffix
        )
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_path.write_text(json.dumps(all_timing, indent=2))
    print(f"\n{'═'*60}")
    print(f"  Timing saved to {timing_path}")
    print(f"{'═'*60}")

    # Summary
    for course, t in all_timing.items():
        if "error" in t:
            print(f"  {course}: FAILED — {t['error']}")
        else:
            print(f"  {course}: {t['total']}s total, "
                  f"{t['per_student_total']}s/student, "
                  f"{t['students']} students")


if __name__ == "__main__":
    main()
