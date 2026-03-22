"""
Per-submission LLM coding for the Insights Engine.

Tier logic:
  Lightweight: 2 calls (comprehension -> interpretation) per submission
  Medium: 1 combined call per submission
  Deep: 1 full call per submission

Concern detection is ALWAYS separate (see concern_detector.py).
"""

import json
import logging
from typing import Dict, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    PerSubmissionSummary,
    QuoteRecord,
    SubmissionCodingRecord,
)
from insights.patterns import classify_vader_polarity
from insights.prompts import (
    ANALYSIS_LENS_PROMPT_FRAGMENT,
    CODING_FULL_PROMPT,
    COMPREHENSION_PROMPT,
    INTEREST_AREAS_FRAGMENT,
    INTERPRETATION_PROMPT,
    JSON_REPAIR_PROMPT,
    SYSTEM_PROMPT,
)

log = logging.getLogger(__name__)


def _format_signal_matrix(signals: list) -> str:
    """Format signal matrix results for prompt injection."""
    if not signals:
        return "No signal matrix flags for this submission."
    lines = []
    for sig in signals:
        if hasattr(sig, "signal_type"):
            lines.append(f"- {sig.signal_type}: {sig.interpretation} (category: {sig.keyword_category})")
        elif isinstance(sig, tuple) and len(sig) >= 4:
            lines.append(f"- {sig[0]}: {sig[3]} (category: {sig[1]})")
    return "\n".join(lines) if lines else "No signal matrix flags."


def _format_keyword_hits(hits: Dict[str, int]) -> str:
    if not hits:
        return "none"
    return ", ".join(f"{k}: {v}" for k, v in sorted(hits.items(), key=lambda x: -x[1])[:8])


def _build_lens_fragment(analysis_lens: Optional[Dict]) -> str:
    if not analysis_lens:
        return ""
    criteria = []
    for name, desc in analysis_lens.items():
        criteria.append(f"- {name}: {desc}")
    if not criteria:
        return ""
    return ANALYSIS_LENS_PROMPT_FRAGMENT.format(lens_criteria="\n".join(criteria))


def _build_interests_fragment(teacher_interests: list) -> str:
    if not teacher_interests:
        return ""
    summary = ", ".join(f"({i+1}) {interest}" for i, interest in enumerate(teacher_interests[:3]))
    return INTEREST_AREAS_FRAGMENT.format(interests_summary=summary)


def _parse_response(raw: str, student_name: str, student_id: str) -> dict:
    """Parse LLM JSON response with retry-on-failure logic."""
    parsed = parse_json_response(raw)
    if "_parse_error" in parsed:
        log.warning("JSON parse failed for %s: %s", student_name, parsed["_parse_error"])
        return parsed
    return parsed


def _safe_quotes(quotes_data: list) -> list:
    """Safely convert quote dicts to QuoteRecord instances."""
    result = []
    for q in (quotes_data or [])[:3]:
        if isinstance(q, dict) and q.get("text"):
            result.append(QuoteRecord(
                text=q["text"],
                significance=q.get("significance", ""),
            ))
    return result


def _validate_concepts(concepts: list, submission_text: str) -> list:
    """Post-validate concepts_applied against actual submission text.

    Removes concepts the student never mentioned.  An 8B model sometimes
    attributes course concepts to a submission based on the assignment
    prompt rather than the actual text.  Misrepresenting a student's
    engagement is a form of harm — it could lead a teacher to assume
    understanding that isn't there.

    Uses simple token overlap (not embedding similarity) to keep it
    fast and deterministic.
    """
    import re as _re

    if not concepts:
        return []

    sub_lower = submission_text.lower()
    sub_tokens = set(_re.findall(r"[a-z]{3,}", sub_lower))

    validated = []
    for concept in concepts:
        concept_lower = concept.lower()
        concept_tokens = set(_re.findall(r"[a-z]{3,}", concept_lower))

        if not concept_tokens:
            validated.append(concept)
            continue

        # Check 1: Direct substring match (handles multi-word concepts)
        if concept_lower in sub_lower:
            validated.append(concept)
            continue

        # Check 2: Token overlap — at least half the concept's content
        # words appear in the submission
        overlap = len(concept_tokens & sub_tokens)
        if overlap / len(concept_tokens) >= 0.5:
            validated.append(concept)
            continue

        # Check 3: Stem overlap — catches partial references like
        # "intersectional" for the concept "intersectionality"
        stems = {t[:6] for t in concept_tokens if len(t) > 3}
        sub_stems = {t[:6] for t in sub_tokens if len(t) > 3}
        if stems & sub_stems:
            validated.append(concept)
            continue

        log.debug(
            "Hallucination guard removed concept '%s' — "
            "no vocabulary support in submission text",
            concept,
        )

    return validated


def code_submission(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    quick_summary: Optional[PerSubmissionSummary],
    signal_matrix_results: list,
    tier: str,
    backend: BackendConfig,
    analysis_lens: Optional[Dict] = None,
    teacher_interests: Optional[list] = None,
    profile_fragment: str = "",
) -> SubmissionCodingRecord:
    """Code one student submission using the LLM.

    Returns a SubmissionCodingRecord populated with LLM analysis.
    Concern detection is NOT included — that's a separate call.
    """
    # Build context from quick analysis
    vader_compound = quick_summary.vader_compound if quick_summary else 0.0
    vader_polarity = classify_vader_polarity(vader_compound)
    keyword_hits = _format_keyword_hits(quick_summary.keyword_hits if quick_summary else {})
    cluster_id = str(quick_summary.cluster_id) if quick_summary and quick_summary.cluster_id is not None else "none"
    signal_ctx = _format_signal_matrix(signal_matrix_results)
    lens_fragment = _build_lens_fragment(analysis_lens)
    interests_text = _build_interests_fragment(teacher_interests)

    if tier == "lightweight":
        record = _code_lightweight(
            submission_text=submission_text,
            student_id=student_id,
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            vader_compound=vader_compound,
            vader_polarity=vader_polarity,
            keyword_hits=keyword_hits,
            cluster_id=cluster_id,
            signal_ctx=signal_ctx,
            lens_fragment=lens_fragment,
            interests_text=interests_text,
            backend=backend,
            profile_fragment=profile_fragment,
        )
    else:
        record = _code_full(
            submission_text=submission_text,
            student_id=student_id,
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            vader_compound=vader_compound,
            vader_polarity=vader_polarity,
            keyword_hits=keyword_hits,
            cluster_id=cluster_id,
            signal_ctx=signal_ctx,
            lens_fragment=lens_fragment,
            interests_text=interests_text,
            backend=backend,
            analysis_lens=analysis_lens,
            profile_fragment=profile_fragment,
        )

    # Carry forward non-LLM metadata
    record.student_id = student_id
    record.student_name = student_name
    record.word_count = len(submission_text.split())
    record.vader_sentiment = vader_compound
    if quick_summary:
        record.cluster_id = quick_summary.cluster_id
        record.keyword_hits = quick_summary.keyword_hits

    return record


def _code_lightweight(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    vader_compound: float,
    vader_polarity: str,
    keyword_hits: str,
    cluster_id: str,
    signal_ctx: str,
    lens_fragment: str,
    interests_text: str,
    backend: BackendConfig,
    profile_fragment: str = "",
) -> SubmissionCodingRecord:
    """Lightweight tier: 2 decomposed calls (comprehension + interpretation)."""

    # Call 1: Comprehension
    comp_prompt = COMPREHENSION_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        vader_compound=vader_compound,
        vader_polarity=vader_polarity,
        keyword_hits=keyword_hits,
        cluster_id=cluster_id,
        signal_matrix_context=signal_ctx,
        submission_text=submission_text,
        profile_fragment=profile_fragment,
    )

    raw_comp = send_text(backend, comp_prompt, SYSTEM_PROMPT)
    comp = _parse_response(raw_comp, student_name, student_id)

    # Retry once on parse failure
    if "_parse_error" in comp:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw_comp[:1500],
            expected_format='{"student_name": "...", "readings_referenced": [...], ...}',
        )
        raw_comp = send_text(backend, repair, SYSTEM_PROMPT)
        comp = _parse_response(raw_comp, student_name, student_id)

    # Call 2: Interpretation
    interp_prompt = INTERPRETATION_PROMPT.format(
        student_name=student_name,
        comprehension_json=json.dumps(comp, indent=2)[:2000],
        assignment_prompt=assignment_prompt,
        teacher_interests=interests_text,
        submission_text=submission_text,
        lens_fragment=lens_fragment,
        profile_fragment=profile_fragment,
    )

    raw_interp = send_text(backend, interp_prompt, SYSTEM_PROMPT)
    interp = _parse_response(raw_interp, student_name, student_id)

    if "_parse_error" in interp:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw_interp[:1500],
            expected_format='{"theme_tags": [...], "theme_confidence": {...}, ...}',
        )
        raw_interp = send_text(backend, repair, SYSTEM_PROMPT)
        interp = _parse_response(raw_interp, student_name, student_id)

    # Validate concepts against submission text (hallucination guard)
    validated_concepts = _validate_concepts(
        comp.get("concepts_applied", []), submission_text,
    )

    # Merge comprehension + interpretation into a single record
    return SubmissionCodingRecord(
        student_id=student_id,
        student_name=student_name,
        # From comprehension
        notable_quotes=_safe_quotes(comp.get("notable_quotes", [])),
        readings_referenced=comp.get("readings_referenced", []),
        concepts_applied=validated_concepts,
        personal_connections=comp.get("personal_connections", []),
        current_events_referenced=comp.get("current_events_referenced", []),
        # From interpretation
        theme_tags=interp.get("theme_tags", []),
        theme_confidence=interp.get("theme_confidence", {}),
        emotional_register=interp.get("emotional_register", ""),
        emotional_notes=interp.get("emotional_notes", ""),
    )


def _code_full(
    *,
    submission_text: str,
    student_id: str,
    student_name: str,
    assignment_prompt: str,
    vader_compound: float,
    vader_polarity: str,
    keyword_hits: str,
    cluster_id: str,
    signal_ctx: str,
    lens_fragment: str,
    interests_text: str,
    backend: BackendConfig,
    analysis_lens: Optional[Dict] = None,
    profile_fragment: str = "",
) -> SubmissionCodingRecord:
    """Medium/Deep tier: single combined coding call."""

    prompt = CODING_FULL_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        teacher_interests=interests_text,
        vader_compound=vader_compound,
        vader_polarity=vader_polarity,
        keyword_hits=keyword_hits,
        cluster_id=cluster_id,
        signal_matrix_context=signal_ctx,
        submission_text=submission_text,
        lens_fragment=lens_fragment,
        profile_fragment=profile_fragment,
    )

    raw = send_text(backend, prompt, SYSTEM_PROMPT)
    parsed = _parse_response(raw, student_name, student_id)

    if "_parse_error" in parsed:
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:1500],
            expected_format='{"student_name": "...", "theme_tags": [...], ...}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT)
        parsed = _parse_response(raw, student_name, student_id)

    # Build lens observations if analysis lens provided
    lens_obs = None
    if analysis_lens and parsed.get("lens_observations"):
        lens_obs = parsed["lens_observations"]

    # Validate concepts against submission text (hallucination guard)
    validated_concepts = _validate_concepts(
        parsed.get("concepts_applied", []), submission_text,
    )

    return SubmissionCodingRecord(
        student_id=student_id,
        student_name=student_name,
        theme_tags=parsed.get("theme_tags", []),
        theme_confidence=parsed.get("theme_confidence", {}),
        notable_quotes=_safe_quotes(parsed.get("notable_quotes", [])),
        emotional_register=parsed.get("emotional_register", ""),
        emotional_notes=parsed.get("emotional_notes", ""),
        readings_referenced=parsed.get("readings_referenced", []),
        concepts_applied=validated_concepts,
        personal_connections=parsed.get("personal_connections", []),
        current_events_referenced=parsed.get("current_events_referenced", []),
        lens_observations=lens_obs,
    )
