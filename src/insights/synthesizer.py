"""
Synthesis report generation for the Insights Engine.

Tier-differentiated:
  Lightweight: structured records only, template-constrained, formulaic but functional
  Medium: all records + teacher context, more interpretive, connects themes
  Deep: full context + pedagogical philosophy, genuine analytical depth

Report sections: What Students Said, Emergent Themes, Tensions & Contradictions,
Surprises, Focus Areas, Concerns, Divergent Approaches, Looking Ahead,
Students to Check In With.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    ConcernRecord,
    GuidedSynthesisResult,
    OutlierReport,
    QuickAnalysisResult,
    SubmissionCodingRecord,
    SynthesisReport,
    ThemeSet,
)
from insights.prompts import (
    INTEREST_AREAS_FRAGMENT,
    SYNTHESIS_CONCERN_PROMPT,
    SYNTHESIS_HIGHLIGHT_PROMPT,
    SYNTHESIS_TEMPERATURE_PROMPT,
    SYNTHESIS_TENSION_PROMPT,
    SYNTHESIS_PROMPT_DEEP,
    SYNTHESIS_PROMPT_LIGHTWEIGHT,
    SYNTHESIS_PROMPT_MEDIUM,
    SYSTEM_PROMPT,
    _SYNTH_PASS_1,
    _SYNTH_PASS_2,
    _SYNTH_PASS_3,
)

log = logging.getLogger(__name__)


def _summarize_themes(theme_set: ThemeSet) -> str:
    """Build a concise theme summary for Lightweight tier."""
    lines = []
    for t in theme_set.themes:
        quotes_str = ""
        if t.supporting_quotes:
            quotes_str = f' — e.g., "{t.supporting_quotes[0].text[:80]}..."'
        lines.append(f"- {t.name} ({t.frequency} students, conf={t.confidence:.1f}){quotes_str}")
    if theme_set.contradictions:
        lines.append("\nCONTRADICTIONS:")
        for c in theme_set.contradictions:
            lines.append(f"- {c.description}")
            lines.append(f"  Side A ({len(c.side_a_students)} students): {c.side_a}")
            lines.append(f"  Side B ({len(c.side_b_students)} students): {c.side_b}")
    return "\n".join(lines)


def _summarize_outliers(outlier_report: OutlierReport) -> str:
    lines = []
    for o in outlier_report.outliers:
        quote_str = ""
        if o.notable_quote:
            quote_str = f' — "{o.notable_quote.text[:80]}..."'
        lines.append(f"- {o.student_name}: {o.why_notable[:100]}{quote_str}")
    return "\n".join(lines) if lines else "No outliers identified."


def _summarize_concerns(coding_records: List[SubmissionCodingRecord]) -> str:
    lines = []
    for r in coding_records:
        for c in r.concerns:
            lines.append(
                f"- {r.student_name}: \"{c.flagged_passage[:80]}...\" "
                f"(confidence: {c.confidence:.1f}) — {c.why_flagged[:80]}"
            )
    return "\n".join(lines) if lines else "No concerns flagged."


def _summarize_quick_analysis(qa: Optional[QuickAnalysisResult]) -> str:
    if not qa:
        return "Quick analysis not available."
    lines = [
        f"Submissions: {qa.stats.total_submissions}",
        f"Word count: avg {qa.stats.word_count_mean:.0f}, median {qa.stats.word_count_median:.0f}",
    ]
    if qa.sentiment_distribution:
        dist = ", ".join(f"{k}: {v}" for k, v in
                         sorted(qa.sentiment_distribution.items(), key=lambda x: -x[1]))
        lines.append(f"Sentiment distribution: {dist}")
    if qa.clusters:
        lines.append(f"Natural clusters: {len(qa.clusters)}")
    if qa.concern_signals:
        concern_types = {}
        for sig in qa.concern_signals:
            concern_types[sig.signal_type] = concern_types.get(sig.signal_type, 0) + 1
        concern_str = ", ".join(f"{k}: {v}" for k, v in concern_types.items())
        lines.append(f"Non-LLM concern signals: {concern_str}")
    # Surface assignment connection observation when present — the synthesizer
    # needs to know if submissions diverged from the assignment topic so it
    # doesn't frame narrative sections around the assignment name when students
    # wrote about something else entirely.
    if qa.assignment_connection_observation:
        lines.append(
            f"ASSIGNMENT CONNECTION NOTE: {qa.assignment_connection_observation}"
        )
    return "\n".join(lines)


def _records_to_summary(records: List[SubmissionCodingRecord]) -> str:
    """Summarize coding records (for Medium tier — not full JSON)."""
    lines = []
    for r in records:
        tags = ", ".join(r.theme_tags[:3])
        quote = f'"{r.notable_quotes[0].text[:60]}..."' if r.notable_quotes else ""
        lines.append(f"- {r.student_name}: [{tags}] {r.emotional_register} {quote}")
    return "\n".join(lines)


def _summarize_linguistic_diversity(
    coding_records: List[SubmissionCodingRecord],
) -> str:
    """Aggregate linguistic_assets across all records into a class-level block.

    Counts how many students exhibit each unique asset label and produces a
    teacher-facing summary.  Returns empty string when no assets are detected.
    """
    asset_counts: Dict[str, int] = {}
    for r in coding_records:
        # Dedupe per student — count each label at most once per student
        seen: set = set()
        for label in r.linguistic_assets:
            if label and label not in seen:
                seen.add(label)
                asset_counts[label] = asset_counts.get(label, 0) + 1

    if not asset_counts:
        return ""

    # Sort by count descending, then alphabetically for stability
    sorted_assets = sorted(asset_counts.items(), key=lambda x: (-x[1], x[0]))
    lines = ["LINGUISTIC DIVERSITY IN THIS CLASS:"]
    for label, count in sorted_assets:
        lines.append(f"  - {count} student{'s' if count != 1 else ''}: {label}")
    lines.append("This communicative diversity is a classroom resource.")
    return "\n".join(lines)


def _build_interests(teacher_interests: list) -> str:
    if not teacher_interests:
        return ""
    summary = ", ".join(f"({i+1}) {interest}" for i, interest in enumerate(teacher_interests[:3]))
    return INTEREST_AREAS_FRAGMENT.format(interests_summary=summary)


def _build_teacher_context(teacher_context: str, next_week: str = "") -> str:
    lines = []
    if teacher_context:
        lines.append(f"TEACHER CONTEXT: {teacher_context}")
    if next_week:
        lines.append(f"NEXT WEEK'S TOPIC: {next_week}")
    return "\n".join(lines)


def synthesize(
    theme_set: ThemeSet,
    outlier_report: OutlierReport,
    quick_analysis: Optional[QuickAnalysisResult],
    coding_records: List[SubmissionCodingRecord],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
    course_name: str = "",
    teacher_context: str = "",
    teacher_interests: Optional[list] = None,
    analysis_lens: Optional[Dict] = None,
    profile_fragment: str = "",
) -> SynthesisReport:
    """Generate the synthesis report.

    The prompt and context vary by tier — see spec Section IV, Pass 4.
    """
    total = len(coding_records)
    interests_text = _build_interests(teacher_interests or [])
    context_text = _build_teacher_context(teacher_context)
    diversity_text = _summarize_linguistic_diversity(coding_records)

    if tier == "lightweight":
        return _synthesize_lightweight(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment, diversity_text,
        )
    elif tier == "medium":
        return _synthesize_medium(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment, diversity_text,
        )
    else:
        return _synthesize_deep(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment, diversity_text,
        )


def _synthesize_lightweight(
    theme_set, outlier_report, quick_analysis, coding_records,
    assignment_name, course_name, total, context_text, interests_text,
    backend, profile_fragment="", linguistic_diversity="",
) -> SynthesisReport:
    """3-pass synthesis for lightweight tier.

    Small local models (8B) can't reliably produce 9 JSON sections in one
    pass — they lose track of the structure and emit 3-4 sections.  Instead,
    we make three passes of 3 sections each, then merge.  Each pass gets
    the same context, so per-section quality is comparable to a single-pass
    approach on a larger model.
    """
    # Build the shared context prefix (everything except section instructions)
    context = SYNTHESIS_PROMPT_LIGHTWEIGHT.format(
        assignment_name=assignment_name,
        course_name=course_name,
        total_submissions=total,
        teacher_context=context_text,
        themes_summary=_summarize_themes(theme_set),
        outliers_summary=_summarize_outliers(outlier_report),
        concerns_summary=_summarize_concerns(coding_records),
        quick_analysis_summary=_summarize_quick_analysis(quick_analysis),
        teacher_interests=interests_text,
        profile_fragment=profile_fragment,
        linguistic_diversity=linguistic_diversity,
        _SYNTHESIS_SECTIONS="{pass_sections}",
    )

    merged_sections: dict = {}
    confidences: list = []

    for i, pass_sections in enumerate((_SYNTH_PASS_1, _SYNTH_PASS_2, _SYNTH_PASS_3), 1):
        prompt = context.format(pass_sections=pass_sections)
        log.info("Synthesis pass %d/3...", i)
        result = _run_synthesis(prompt, backend)
        merged_sections.update(result.sections)
        confidences.append(result.confidence)

    avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5
    return SynthesisReport(sections=merged_sections, confidence=avg_confidence)


def _synthesize_medium(
    theme_set, outlier_report, quick_analysis, coding_records,
    assignment_name, course_name, total, context_text, interests_text,
    backend, profile_fragment="", linguistic_diversity="",
) -> SynthesisReport:
    prompt = SYNTHESIS_PROMPT_MEDIUM.format(
        assignment_name=assignment_name,
        course_name=course_name,
        total_submissions=total,
        teacher_context=context_text,
        records_summary=_records_to_summary(coding_records),
        themes_json=json.dumps(theme_set.model_dump(), default=str)[:4000],
        outliers_json=json.dumps(outlier_report.model_dump(), default=str)[:2000],
        concerns_summary=_summarize_concerns(coding_records),
        quick_analysis_summary=_summarize_quick_analysis(quick_analysis),
        teacher_interests=interests_text,
        profile_fragment=profile_fragment,
        linguistic_diversity=linguistic_diversity,
        _SYNTHESIS_SECTIONS="",
    )
    return _run_synthesis(prompt, backend)


def _synthesize_deep(
    theme_set, outlier_report, quick_analysis, coding_records,
    assignment_name, course_name, total, context_text, interests_text,
    backend, profile_fragment="",
) -> SynthesisReport:
    # Full records for deep tier
    records_data = [r.model_dump() for r in coding_records]
    prompt = SYNTHESIS_PROMPT_DEEP.format(
        assignment_name=assignment_name,
        course_name=course_name,
        total_submissions=total,
        teacher_context=context_text,
        records_json=json.dumps(records_data, default=str)[:8000],
        themes_json=json.dumps(theme_set.model_dump(), default=str)[:6000],
        outliers_json=json.dumps(outlier_report.model_dump(), default=str)[:3000],
        concerns_json=json.dumps(
            [{"student": r.student_name, "concerns": [c.model_dump() for c in r.concerns]}
             for r in coding_records if r.concerns],
            default=str,
        )[:3000],
        quick_analysis_json=json.dumps(
            quick_analysis.model_dump() if quick_analysis else {}, default=str
        )[:3000],
        teacher_interests=interests_text,
        profile_fragment=profile_fragment,
        _SYNTHESIS_SECTIONS="",
    )
    return _run_synthesis(prompt, backend)


def _run_synthesis(prompt: str, backend: BackendConfig) -> SynthesisReport:
    """Execute synthesis prompt and parse the result."""
    raw = send_text(backend, prompt, SYSTEM_PROMPT)
    parsed = parse_json_response(raw)

    if "_parse_error" in parsed:
        log.warning("Synthesis JSON parse failed, retrying")
        from insights.prompts import JSON_REPAIR_PROMPT
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:2000],
            expected_format='{"sections": {"what_students_said": "...", ...}, "confidence": 0.8}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT)
        parsed = parse_json_response(raw)

    sections = parsed.get("sections", {})
    if not isinstance(sections, dict):
        sections = {}

    confidence = float(parsed.get("confidence", 0.5))

    return SynthesisReport(sections=sections, confidence=confidence)


# ---------------------------------------------------------------------------
# A6 — Guided Synthesis Chain
# ---------------------------------------------------------------------------

def _validate_no_student_data(payload: str, coding_records: List[SubmissionCodingRecord]) -> bool:
    """FERPA enforcement: verify no student-identifiable data in cloud payload.

    Call this BEFORE sending any payload to a cloud API. If validation fails,
    skip cloud enhancement — do not crash.

    Returns True if payload is safe to send, False if FERPA violation detected.
    """
    payload_lower = payload.lower()
    for record in coding_records:
        if record.student_name and record.student_name.lower() in payload_lower:
            log.error(
                "FERPA VIOLATION BLOCKED: student name '%s' found in cloud payload",
                record.student_name,
            )
            return False
        if record.student_id and record.student_id in payload:
            log.error(
                "FERPA VIOLATION BLOCKED: student ID '%s' found in cloud payload",
                record.student_id,
            )
            return False
    return True


def _build_flagged_students_block(flagged: List[SubmissionCodingRecord]) -> str:
    """Format flagged student data for Call 1 prompt."""
    lines = []
    for r in flagged:
        concern_summaries = []
        for c in r.concerns:
            concern_summaries.append(
                f'  - Flagged passage: "{c.flagged_passage[:120]}"\n'
                f'    Why flagged: {c.why_flagged}\n'
                f'    Confidence: {c.confidence:.2f}'
            )
        tags = ", ".join(r.theme_tags[:4]) if r.theme_tags else "none"
        register = r.emotional_register or "unspecified"
        lines.append(
            f"STUDENT: {r.student_name}\n"
            f"  Theme tags: {tags}\n"
            f"  Emotional register: {register}\n"
            f"  Concerns:\n" + "\n".join(concern_summaries)
        )
    return "\n\n".join(lines)


def _build_strong_students_block(strong: List[SubmissionCodingRecord]) -> str:
    """Format strong engager data for Call 2 prompt."""
    lines = []
    for r in strong:
        tags = ", ".join(r.theme_tags[:4]) if r.theme_tags else "none"
        first_quote = (
            f'"{r.notable_quotes[0].text[:120]}"'
            if r.notable_quotes
            else "(no notable quote)"
        )
        personal = (
            "; ".join(r.personal_connections[:2])
            if r.personal_connections
            else "none noted"
        )
        lines.append(
            f"STUDENT: {r.student_name}\n"
            f"  Theme tags: {tags}\n"
            f"  Notable quote: {first_quote}\n"
            f"  Personal connections: {personal}"
        )
    return "\n\n".join(lines)


def _summarize_connection(qa_result: Optional[QuickAnalysisResult]) -> str:
    """Extract assignment connection summary from QuickAnalysisResult."""
    if not qa_result:
        return "not available"
    obs = getattr(qa_result, "assignment_connection_observation", "")
    if obs:
        return obs[:200]
    return "not available"


def _summarize_similarity(qa_result: Optional[QuickAnalysisResult]) -> str:
    """Extract pairwise similarity observation from QuickAnalysisResult."""
    if not qa_result:
        return "not available"
    ps = getattr(qa_result, "pairwise_similarity", None)
    if ps and getattr(ps, "observation", ""):
        return ps.observation[:200]
    return "not available"


def guided_synthesis(
    coding_records: List[SubmissionCodingRecord],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
    qa_result: Optional[QuickAnalysisResult] = None,
    profile_fragment: str = "",
    settings: Optional[Dict[str, Any]] = None,
) -> GuidedSynthesisResult:
    """Guided Synthesis Chain (A6).

    Replaces the broken open-ended 3-pass synthesis with 4 scoped, guided
    calls that surface patterns and tensions without prescribing pedagogy.
    The teacher is the synthesis layer — this provides the diagnosis.

    Each call has its own try/except. If Call 3 fails, Calls 1, 2, and 4
    still complete and produce usable output. (#CRIP_TIME)

    FERPA: Student names appear in LOCAL calls only. Cloud enhancement
    uses ONLY anonymized pattern descriptions — validated before sending.
    """
    result = GuidedSynthesisResult()
    settings = settings or {}

    # Pre-processing (non-LLM): group students by engagement pattern
    flagged = [r for r in coding_records if r.concerns]
    strong = [
        r for r in coding_records
        if r.engagement_signals
        and r.engagement_signals.get("engagement_depth") == "strong"
    ]
    limited = [
        r for r in coding_records
        if r.engagement_signals
        and r.engagement_signals.get("engagement_depth") in ("limited", "minimal")
    ]
    # Middle: everyone not in flagged, strong, or limited
    flagged_ids = {r.student_id for r in flagged}
    strong_ids = {r.student_id for r in strong}
    limited_ids = {r.student_id for r in limited}
    middle = [
        r for r in coding_records
        if r.student_id not in flagged_ids
        and r.student_id not in strong_ids
        and r.student_id not in limited_ids
    ]

    total = len(coding_records)
    log.info(
        "Guided synthesis: total=%d flagged=%d strong=%d limited=%d middle=%d",
        total, len(flagged), len(strong), len(limited), len(middle),
    )

    # ------------------------------------------------------------------
    # Call 1 — Concern Pattern Analysis (only if flagged students exist)
    # ------------------------------------------------------------------
    call1_output: Dict[str, Any] = {}
    if flagged:
        result.calls_attempted += 1
        try:
            flagged_block = _build_flagged_students_block(flagged)
            prompt = SYNTHESIS_CONCERN_PROMPT.format(
                flagged_students_block=flagged_block,
            )
            log.info("Guided synthesis Call 1 (concerns): %d flagged students", len(flagged))
            raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
            parsed = parse_json_response(raw)
            if "_parse_error" not in parsed:
                patterns = parsed.get("patterns", [])
                diffs = parsed.get("key_differences", [])
                if isinstance(patterns, list):
                    result.concern_patterns = patterns
                    call1_output["patterns"] = patterns
                if isinstance(diffs, list):
                    result.concern_differences = diffs
                    call1_output["key_differences"] = diffs
                result.calls_completed += 1
                log.info("Call 1 complete: %d patterns, %d differences", len(patterns), len(diffs))
            else:
                log.warning("Call 1 JSON parse failed: %s", parsed.get("_parse_error"))
        except Exception as e:
            log.warning("Guided synthesis Call 1 failed (concern patterns): %s", e)

    # ------------------------------------------------------------------
    # Call 2 — Engagement Highlights (only if strong engagers exist)
    # ------------------------------------------------------------------
    call2_output: Dict[str, Any] = {}
    if strong:
        result.calls_attempted += 1
        try:
            strong_block = _build_strong_students_block(strong)
            prompt = SYNTHESIS_HIGHLIGHT_PROMPT.format(
                strong_students_block=strong_block,
            )
            log.info("Guided synthesis Call 2 (highlights): %d strong students", len(strong))
            raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
            parsed = parse_json_response(raw)
            if "_parse_error" not in parsed:
                highlights = parsed.get("highlights", [])
                if isinstance(highlights, list):
                    result.engagement_highlights = highlights
                    call2_output["highlights"] = highlights
                result.calls_completed += 1
                log.info("Call 2 complete: %d highlights", len(highlights))
            else:
                log.warning("Call 2 JSON parse failed: %s", parsed.get("_parse_error"))
        except Exception as e:
            log.warning("Guided synthesis Call 2 failed (highlights): %s", e)

    # ------------------------------------------------------------------
    # Call 3 — Tension Surfacing (only if BOTH flagged AND strong exist)
    # ------------------------------------------------------------------
    if flagged and strong and call1_output and call2_output:
        result.calls_attempted += 1
        try:
            # Build concern patterns block from Call 1 output
            concern_block_lines = []
            for p in call1_output.get("patterns", []):
                desc = p.get("description", "")
                names = ", ".join(p.get("student_names", []))
                concern_block_lines.append(f"- {desc} (students: {names})")
            for d in call1_output.get("key_differences", []):
                concern_block_lines.append(f"  Distinction: {d}")
            concern_patterns_block = "\n".join(concern_block_lines) or "(none)"

            # Build highlights block from Call 2 output
            highlight_block_lines = []
            for h in call2_output.get("highlights", []):
                desc = h.get("description", "")
                names = ", ".join(h.get("student_names", []))
                highlight_block_lines.append(f"- {desc} (students: {names})")
            highlight_patterns_block = "\n".join(highlight_block_lines) or "(none)"

            prompt = SYNTHESIS_TENSION_PROMPT.format(
                concern_patterns_block=concern_patterns_block,
                highlight_patterns_block=highlight_patterns_block,
            )
            log.info("Guided synthesis Call 3 (tensions)")
            raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
            parsed = parse_json_response(raw)
            if "_parse_error" not in parsed:
                tensions = parsed.get("tensions", [])
                if isinstance(tensions, list):
                    result.tensions = tensions
                result.calls_completed += 1
                log.info("Call 3 complete: %d tensions", len(tensions))
            else:
                log.warning("Call 3 JSON parse failed: %s", parsed.get("_parse_error"))
        except Exception as e:
            log.warning("Guided synthesis Call 3 failed (tensions): %s", e)
    elif flagged and strong:
        log.info(
            "Skipping Call 3 (tension surfacing): Call 1 or Call 2 produced no output to work from"
        )

    # ------------------------------------------------------------------
    # Call 4 — Class Temperature (ALWAYS runs)
    # ------------------------------------------------------------------
    result.calls_attempted += 1
    try:
        # Summarize concern types from flagged students
        concern_type_counts: Dict[str, int] = {}
        for r in flagged:
            for c in r.concerns:
                # Use first 6 words of why_flagged as the concern type label
                label = " ".join(c.why_flagged.split()[:6]) if c.why_flagged else "unspecified"
                concern_type_counts[label] = concern_type_counts.get(label, 0) + 1
        if concern_type_counts:
            concern_types_str = "; ".join(
                f"{k} ({v})" for k, v in list(concern_type_counts.items())[:5]
            )
        else:
            concern_types_str = "none"

        connection_summary = _summarize_connection(qa_result)
        similarity_summary = _summarize_similarity(qa_result)

        # Edge case: ALL students flagged — note this for Call 4
        all_flagged_note = ""
        if len(flagged) == total and total > 0:
            all_flagged_note = (
                " Note: ALL students in this class were flagged for concerns — "
                "this may indicate the assignment prompt or reading needs reframing."
            )

        prompt = SYNTHESIS_TEMPERATURE_PROMPT.format(
            total_students=total,
            flagged_count=len(flagged),
            concern_types=concern_types_str + all_flagged_note,
            strong_count=len(strong),
            limited_count=len(limited),
            middle_count=len(middle),
            connection_summary=connection_summary,
            similarity_summary=similarity_summary,
        )
        log.info("Guided synthesis Call 4 (class temperature): %d total students", total)
        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=800)
        parsed = parse_json_response(raw)
        if "_parse_error" not in parsed:
            temp = parsed.get("class_temperature", "")
            areas = parsed.get("attention_areas", [])
            if isinstance(temp, str):
                result.class_temperature = temp
            if isinstance(areas, list):
                result.attention_areas = areas
            result.calls_completed += 1
            log.info("Call 4 complete: class_temperature=%d chars", len(result.class_temperature))
        else:
            log.warning("Call 4 JSON parse failed: %s", parsed.get("_parse_error"))
    except Exception as e:
        log.warning("Guided synthesis Call 4 failed (class temperature): %s", e)

    log.info(
        "Guided synthesis complete: %d/%d calls succeeded",
        result.calls_completed, result.calls_attempted,
    )

    # ------------------------------------------------------------------
    # Optional cloud enhancement (FERPA-safe: anonymized patterns only)
    # ------------------------------------------------------------------
    cloud_url = settings.get("insights_cloud_url", "")
    cloud_key = settings.get("insights_cloud_key", "")

    if cloud_url and cloud_key:
        try:
            _run_cloud_enhancement(result, coding_records, assignment_name, cloud_url, cloud_key, settings)
        except Exception as e:
            log.warning("Cloud enhancement failed (non-fatal): %s", e)

    return result


def _run_cloud_enhancement(
    result: GuidedSynthesisResult,
    coding_records: List[SubmissionCodingRecord],
    assignment_name: str,
    cloud_url: str,
    cloud_key: str,
    settings: Dict[str, Any],
) -> None:
    """Run optional cloud synthesis using ANONYMIZED pattern data only.

    FERPA enforcement: ONLY pattern descriptions and aggregate stats are sent.
    NO student names, NO student IDs, NO student text, NO quotes.
    """
    total = len(coding_records)

    # Build anonymized payload from guided synthesis output
    payload_parts = [
        f"An engagement analysis found these patterns in a class of {total} students "
        f"responding to an assignment about {assignment_name or 'this topic'}:",
        "",
    ]

    if result.concern_patterns:
        payload_parts.append("CONCERN PATTERNS:")
        for p in result.concern_patterns:
            desc = p.get("description", "")
            # Count student_names but DO NOT include the names
            count = len(p.get("student_names", []))
            payload_parts.append(f"- {desc} ({count} student(s))")
        if result.concern_differences:
            payload_parts.append("Key distinctions:")
            for d in result.concern_differences:
                payload_parts.append(f"  - {d}")
        payload_parts.append("")

    if result.engagement_highlights:
        payload_parts.append("ENGAGEMENT HIGHLIGHTS:")
        for h in result.engagement_highlights:
            desc = h.get("description", "")
            count = len(h.get("student_names", []))
            payload_parts.append(f"- {desc} ({count} student(s))")
        payload_parts.append("")

    if result.tensions:
        payload_parts.append("TENSIONS BETWEEN GROUPS:")
        for t in result.tensions:
            desc = t.get("description", "")
            between = t.get("between", [])
            payload_parts.append(f"- {desc}")
            for b in between:
                payload_parts.append(f"  Between: {b}")
        payload_parts.append("")

    if result.class_temperature:
        payload_parts.append(f"CLASS TEMPERATURE: {result.class_temperature}")
        if result.attention_areas:
            payload_parts.append("Attention areas:")
            for a in result.attention_areas:
                payload_parts.append(f"  - {a}")
        payload_parts.append("")

    payload_parts.append(
        "Provide a richer pedagogical analysis: What do these patterns suggest "
        "about where the class is in their understanding? What tensions are "
        "most productive for learning? What should the teacher pay attention to? "
        "Do NOT suggest specific exercises or lesson designs — the teacher decides."
    )

    cloud_prompt = "\n".join(payload_parts)

    # FERPA validation — MUST pass before any cloud call
    if not _validate_no_student_data(cloud_prompt, coding_records):
        log.error("Cloud enhancement aborted: FERPA validation failed")
        return

    # Also validate the cloud_prompt doesn't contain student IDs as standalone tokens
    log.info("FERPA validation passed — sending anonymized patterns to cloud")

    # Use cloud backend via existing llm_backend infrastructure
    from insights.llm_backend import BackendConfig, send_text as _send_text, parse_json_response as _parse_json

    cloud_model = settings.get("insights_cloud_model", "gpt-4o-mini")
    cloud_format = settings.get("insights_cloud_api_format", "openai")
    cloud_backend = BackendConfig(
        name="cloud",
        model=cloud_model,
        base_url=cloud_url,
        api_key=cloud_key,
        api_format=cloud_format,
    )

    cloud_system = (
        "You are helping a teacher understand class-level engagement patterns. "
        "All data is anonymized — you will not see student names or text. "
        "Do NOT suggest singling out students. Do NOT suggest specific exercises. "
        "Analyze patterns and surface pedagogical significance."
    )

    raw = _send_text(cloud_backend, cloud_prompt, cloud_system, max_tokens=1200)
    # Cloud response may be free text or JSON — store as-is
    result.cloud_narrative = raw.strip()
    log.info("Cloud enhancement complete: %d chars", len(result.cloud_narrative))
