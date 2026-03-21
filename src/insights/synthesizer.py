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
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    ConcernRecord,
    OutlierReport,
    QuickAnalysisResult,
    SubmissionCodingRecord,
    SynthesisReport,
    ThemeSet,
)
from insights.prompts import (
    INTEREST_AREAS_FRAGMENT,
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
    return "\n".join(lines)


def _records_to_summary(records: List[SubmissionCodingRecord]) -> str:
    """Summarize coding records (for Medium tier — not full JSON)."""
    lines = []
    for r in records:
        tags = ", ".join(r.theme_tags[:3])
        quote = f'"{r.notable_quotes[0].text[:60]}..."' if r.notable_quotes else ""
        lines.append(f"- {r.student_name}: [{tags}] {r.emotional_register} {quote}")
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

    if tier == "lightweight":
        return _synthesize_lightweight(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment,
        )
    elif tier == "medium":
        return _synthesize_medium(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment,
        )
    else:
        return _synthesize_deep(
            theme_set, outlier_report, quick_analysis, coding_records,
            assignment_name, course_name, total, context_text, interests_text,
            backend, profile_fragment,
        )


def _synthesize_lightweight(
    theme_set, outlier_report, quick_analysis, coding_records,
    assignment_name, course_name, total, context_text, interests_text,
    backend, profile_fragment="",
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
    backend, profile_fragment="",
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
