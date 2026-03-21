"""
Dedicated concern detection for the Insights Engine.

ALWAYS a separate LLM call regardless of tier.
At Lightweight: mainly confirms/rejects non-LLM signal matrix flags.
At Medium: can classify concern types with moderate confidence.
At Deep: full cultural analysis capability.

Anti-bias post-processing: checks LLM output for bias markers
("aggressive", "emotional", "too angry") — if found, adds warning.
"""

import logging
import re
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import ConcernRecord, ConcernSignal
from insights.patterns import CRITICAL_KEYWORDS, has_critical_keywords
from insights.prompts import CONCERN_PROMPT, JSON_REPAIR_PROMPT, SYSTEM_PROMPT

log = logging.getLogger(__name__)

# Bias markers in LLM output that suggest tone policing
_BIAS_MARKERS = re.compile(
    r"\b(aggressive|too emotional|overly emotional|hostile tone|"
    r"angry rhetoric|threatening|confrontational|too angry|"
    r"irrational|hysterical)\b",
    re.IGNORECASE,
)


def _format_signal_matrix_for_prompt(signals: List[ConcernSignal]) -> str:
    """Format signal matrix results for the concern prompt."""
    if not signals:
        return "No non-LLM concern signals for this submission."
    lines = []
    for sig in signals:
        lines.append(
            f"- {sig.signal_type}: {sig.interpretation} "
            f"(category: {sig.keyword_category}, VADER: {sig.vader_polarity})"
        )
        if sig.matched_text:
            lines.append(f'  Matched text: "{sig.matched_text}"')
    return "\n".join(lines)


def _format_signal_matrix_tuples(signals: list) -> str:
    """Format raw signal matrix tuples for the concern prompt."""
    if not signals:
        return "No non-LLM concern signals for this submission."
    lines = []
    for sig in signals:
        if isinstance(sig, tuple) and len(sig) >= 4:
            lines.append(f"- {sig[0]}: {sig[3]} (category: {sig[1]}, VADER: {sig[2]})")
        elif hasattr(sig, "signal_type"):
            lines.append(f"- {sig.signal_type}: {sig.interpretation}")
    return "\n".join(lines) if lines else "No non-LLM concern signals."


# Phrases that indicate the LLM is flagging course content, not student wellbeing
_CONTENT_FLAG_MARKERS = re.compile(
    r"\b(triggering|disturbing content|graphic|violent content|"
    r"may be triggering|this passage may|difficult material|"
    r"sensitive (content|material|topic)|mature content|"
    r"content warning|distressing (content|material)|"
    r"indication of distress)\b",
    re.IGNORECASE,
)

# Phrases in why_flagged that suggest the model is concerned about subject
# matter rather than the student's personal state
_SUBJECT_MATTER_EXPLANATIONS = re.compile(
    r"\b(discusses? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"mentions? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"references? (to )?(rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"describes? (rape|violence|murder|assault|genocide|trauma|abuse)|"
    r"course (content|material) .{0,30}(difficult|heavy|disturbing|graphic))\b",
    re.IGNORECASE,
)


def _check_bias_in_output(concerns: List[ConcernRecord], submission_text: str) -> List[ConcernRecord]:
    """Anti-bias post-processing: check LLM concern output for bias markers.

    If the LLM's 'why_flagged' uses tone-policing language AND the flagged
    passage contains structural critique keywords, add a warning.

    Also checks for the model confusing course content with student distress:
    if the model flags a passage because the SUBJECT MATTER is disturbing
    (not because the STUDENT is in distress), demote the flag.
    """
    checked = []
    for concern in concerns:
        # Check if the LLM used biased language in its explanation
        if _BIAS_MARKERS.search(concern.why_flagged):
            # Check if the flagged passage contains structural critique
            if has_critical_keywords(concern.flagged_passage) or has_critical_keywords(submission_text):
                concern.why_flagged = (
                    f"\u26a0 POSSIBLE MODEL BIAS: The model characterized this "
                    f"student's tone negatively. The passage appears to contain "
                    f"structural critique, which is appropriate academic "
                    f"engagement, not a concern. Original model assessment: "
                    f"{concern.why_flagged}"
                )
                concern.confidence = max(0.1, concern.confidence - 0.3)

        # Check if the model is flagging course CONTENT rather than student
        # WELLBEING — e.g., "this passage discusses rape" or "may be triggering"
        why = concern.why_flagged
        if (_CONTENT_FLAG_MARKERS.search(why)
                or _SUBJECT_MATTER_EXPLANATIONS.search(why)):
            # The model appears to be concerned about the subject matter,
            # not the student's personal state. Demote significantly.
            concern.why_flagged = (
                f"\u26a0 LIKELY COURSE CONTENT (not student distress): The model "
                f"flagged this because the subject matter is disturbing, not "
                f"because the student appears to be in personal crisis. "
                f"Original model assessment: {why}"
            )
            concern.confidence = max(0.1, concern.confidence - 0.4)

        checked.append(concern)
    return checked


def detect_concerns(
    *,
    submission_text: str,
    student_name: str,
    student_id: str,
    assignment_prompt: str,
    signal_matrix_results: list,
    concern_signals: Optional[List[ConcernSignal]] = None,
    tier: str,
    backend: Optional[BackendConfig],
    profile_fragment: str = "",
) -> List[ConcernRecord]:
    """Run dedicated concern detection on one submission.

    If no LLM backend is available, returns signal matrix results as
    low-confidence concern flags (non-LLM fallback).
    """
    # Format signal matrix context
    if concern_signals:
        signal_text = _format_signal_matrix_for_prompt(concern_signals)
    else:
        signal_text = _format_signal_matrix_tuples(signal_matrix_results)

    # Non-LLM fallback: return signal matrix results as low-confidence flags
    if backend is None:
        return _signal_matrix_fallback(
            concern_signals or [],
            signal_matrix_results,
            student_id,
            student_name,
            submission_text,
        )

    # LLM concern detection
    prompt = CONCERN_PROMPT.format(
        student_name=student_name,
        assignment_prompt=assignment_prompt,
        signal_matrix_result=signal_text,
        submission_text=submission_text,
        profile_fragment=profile_fragment,
    )

    raw = send_text(backend, prompt, SYSTEM_PROMPT)
    parsed = parse_json_response(raw)

    if "_parse_error" in parsed:
        # Retry once
        repair = JSON_REPAIR_PROMPT.format(
            raw_response=raw[:1500],
            expected_format='{"concerns": [{"flagged_passage": "...", ...}]}',
        )
        raw = send_text(backend, repair, SYSTEM_PROMPT)
        parsed = parse_json_response(raw)

    # Build ConcernRecords from LLM response
    concerns = []
    for item in parsed.get("concerns", []):
        if not isinstance(item, dict):
            continue
        passage = item.get("flagged_passage", "")
        if not passage:
            continue
        concerns.append(ConcernRecord(
            flagged_passage=passage,
            surrounding_context=item.get("surrounding_context", ""),
            why_flagged=item.get("why_flagged", ""),
            confidence=float(item.get("confidence", 0.5)),
        ))

    # Anti-bias post-processing
    concerns = _check_bias_in_output(concerns, submission_text)

    # Drop low-confidence flags to reduce noise in teacher's view
    concerns = [c for c in concerns if c.confidence >= 0.7]

    return concerns


def _signal_matrix_fallback(
    concern_signals: List[ConcernSignal],
    signal_matrix_results: list,
    student_id: str,
    student_name: str,
    submission_text: str,
) -> List[ConcernRecord]:
    """Convert non-LLM signal matrix results to low-confidence ConcernRecords.

    Used when no LLM backend is available.
    """
    concerns = []

    # From ConcernSignal objects
    for sig in concern_signals:
        if sig.student_id != student_id:
            continue
        if sig.signal_type in ("APPROPRIATE",):
            continue  # Not a concern
        concerns.append(ConcernRecord(
            flagged_passage=sig.matched_text or "",
            surrounding_context="",
            why_flagged=f"Non-LLM signal: {sig.interpretation}",
            confidence=0.3,  # Low confidence — no LLM verification
        ))

    # From raw signal matrix tuples
    for sig in signal_matrix_results:
        if isinstance(sig, tuple) and len(sig) >= 4:
            signal_type, category, polarity, interpretation = sig
            if signal_type in ("APPROPRIATE",):
                continue
            concerns.append(ConcernRecord(
                flagged_passage="",
                surrounding_context="",
                why_flagged=f"Non-LLM signal ({category}): {interpretation}",
                confidence=0.3,
            ))

    return concerns
