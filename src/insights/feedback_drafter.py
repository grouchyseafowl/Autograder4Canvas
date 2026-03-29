"""
Draft student feedback generator for the Insights Engine (Phase 4).

Generates per-student feedback from coding records. Each draft requires
individual teacher review before posting — no batch auto-approve.

Design principles:
  - Confidence threshold: skip drafting for thin data (< 0.6)
  - Preprocessing acknowledgment: multilingual / audio submissions
    get positive recognition, never treated as lesser
  - Concern sensitivity: concerns are for the teacher, not the student.
    Feedback tone adjusts (warmer) but never reveals concern flags.
  - Equity attention: emotional labor gets acknowledged.
"""

import json
import logging
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import DraftFeedback
from insights.prompts import (
    FEEDBACK_DRAFT_PROMPT,
    FEEDBACK_LENGTH_VARIANTS,
    FEEDBACK_STYLE_VARIANTS,
    FEEDBACK_SYSTEM_PROMPT,
    JSON_REPAIR_PROMPT,
)

log = logging.getLogger(__name__)

# Minimum populated fields to attempt drafting
_MIN_FIELDS_FOR_DRAFT = 2


def _safe_confidence(value) -> float:
    """Safely convert an LLM-returned confidence value to float."""
    try:
        return max(0.0, min(1.0, float(value)))
    except (ValueError, TypeError):
        return 0.7


def _coding_has_enough_data(record: dict) -> bool:
    """Check if a coding record has enough data to draft meaningful feedback.

    Returns True if at least _MIN_FIELDS_FOR_DRAFT content fields are populated.
    """
    populated = 0
    if record.get("theme_tags"):
        populated += 1
    if record.get("notable_quotes"):
        populated += 1
    if record.get("concepts_applied"):
        populated += 1
    if record.get("personal_connections"):
        populated += 1
    if record.get("readings_referenced"):
        populated += 1
    if record.get("emotional_register") and record["emotional_register"] != "disengaged":
        populated += 1
    return populated >= _MIN_FIELDS_FOR_DRAFT


def _format_list(items: list) -> str:
    """Format a list as a comma-separated string or 'none'."""
    if not items:
        return "none"
    return ", ".join(str(i) for i in items[:5])


def _format_quotes(quotes: list) -> str:
    """Format notable quotes for the prompt."""
    if not quotes:
        return "none"
    parts = []
    for q in quotes[:3]:
        if isinstance(q, dict):
            text = q.get("text", "")
            if text:
                parts.append(f'"{text}"')
        elif isinstance(q, str):
            parts.append(f'"{q}"')
    return "; ".join(parts) if parts else "none"


def _build_preprocessing_fragment(meta: Optional[dict]) -> str:
    """Build a preprocessing acknowledgment fragment."""
    if not meta:
        return ""
    parts = []
    if meta.get("was_translated"):
        lang = meta.get("original_language_name", "another language")
        parts.append(
            f"This student wrote in {lang} (translated for analysis). "
            f"Acknowledge their multilingualism positively — writing in "
            f"one's home language is a strength, not a limitation."
        )
    if meta.get("was_transcribed"):
        parts.append(
            "This student submitted audio/video (transcribed for analysis). "
            "Acknowledge the oral format positively — spoken reflection can "
            "capture nuance that writing sometimes misses."
        )
    if not parts:
        return ""
    return "PREPROCESSING CONTEXT:\n" + "\n".join(parts)


def _build_wellbeing_context(record: dict) -> str:
    """Build context for wellbeing-aware and observation-aware feedback drafting.

    Replaces _build_concern_context(). Reads wellbeing classifier output
    + observation prose instead of binary concern flags.

    The observation text is passed as context so the LLM can read it for
    structural power moves (tone policing, colorblind erasure, etc.) —
    no fragile string matching. The student never sees this context.
    """
    axis = record.get("wellbeing_axis", "NONE")
    observation = record.get("observation", "")
    reaching_for = record.get("what_student_is_reaching_for", "")
    register = record.get("emotional_register", "")

    parts = []

    # Wellbeing-aware tone
    if axis in ("CRISIS", "BURNOUT"):
        parts.append(
            "WELLBEING-AWARE DRAFTING: This student shows signs of "
            f"{axis.lower()}. Write with extra warmth. Do NOT add "
            "performance pressure. Do NOT reference the wellbeing "
            "signal — the student should see only a supportive comment."
        )

    # Pass observation for structural move awareness
    # The LLM reads the observation to know if tone policing, colorblind
    # erasure, or other structural moves were identified — and avoids
    # validating them in the feedback.
    if observation:
        parts.append(
            f"OBSERVATION CONTEXT (for your awareness, NOT for the student):\n"
            f"{observation}\n\n"
            "If this observation identifies a structural power move (tone "
            "policing, colorblind erasure, etc.), do NOT validate or praise "
            "that framing in your feedback. Redirect gently toward deeper "
            "engagement with the structural analysis."
        )

    # Growth direction from reading-first coding
    if reaching_for:
        parts.append(f"GROWTH DIRECTION: {reaching_for}")

    # CHECK-IN signal (Pass 2 — subtle self-disclosure in ENGAGED students)
    checkin_flag = record.get("checkin_flag")
    checkin_reasoning = record.get("checkin_reasoning", "")
    if checkin_flag and checkin_reasoning:
        parts.append(
            "CHECK-IN SIGNAL: This student is engaged but showed a subtle "
            "signal that may warrant teacher awareness. The feedback itself "
            "should NOT reference this signal — the student should see only "
            "a normal, substantive comment. The check-in is for the teacher's "
            "private awareness, not the student's feedback.\n"
            f"Signal detail: {checkin_reasoning}"
        )

    # Disengaged register (from coding) — may overlap with BURNOUT axis
    if register == "disengaged" and axis not in ("CRISIS", "BURNOUT"):
        parts.append(
            "TONE GUIDANCE: This student's submission shows signs of "
            "disengagement (shorter than usual, minimal content). Write "
            "with care, not performance pressure. Check in, not push."
        )

    return "\n\n".join(parts) if parts else ""


def _build_style_fragment(style: str, lens: Optional[dict] = None) -> str:
    """Build the style guidance fragment."""
    text = FEEDBACK_STYLE_VARIANTS.get(style, FEEDBACK_STYLE_VARIANTS["warm"])
    if style == "lens_focused" and lens:
        criteria = ", ".join(f"{k}: {v}" for k, v in lens.items())
        text = text.format(lens_criteria=criteria)
    return f"STYLE: {text}"


def _build_length_fragment(length: str) -> str:
    """Build the length guidance fragment."""
    text = FEEDBACK_LENGTH_VARIANTS.get(length, FEEDBACK_LENGTH_VARIANTS["moderate"])
    return f"LENGTH: {text}"


def _build_lens_fragment(lens: Optional[dict]) -> str:
    """Build analysis lens fragment for feedback."""
    if not lens:
        return ""
    criteria = "\n".join(f"- {k}: {v}" for k, v in lens.items())
    return f"ANALYSIS LENS:\n{criteria}"


class FeedbackDrafter:
    """Generate draft feedback for each student based on their coding record."""

    def draft_feedback(
        self,
        coding_record: dict,
        assignment_prompt: str,
        analysis_lens: Optional[dict] = None,
        preprocessing_meta: Optional[dict] = None,
        teacher_profile: Optional[dict] = None,
        tier: str = "lightweight",
        backend: Optional[BackendConfig] = None,
    ) -> DraftFeedback:
        """Generate one feedback draft for one student.

        Returns DraftFeedback with confidence=0.0 if data is insufficient.
        """
        student_id = coding_record.get("student_id", "")
        student_name = coding_record.get("student_name", "Unknown")

        # Confidence threshold: skip if too little data
        if not _coding_has_enough_data(coding_record):
            word_count = coding_record.get("word_count", 0)
            reason = (
                f"Submission had insufficient data for confident feedback "
                f"({word_count} words, minimal theme/quote content)."
            )
            return DraftFeedback(
                student_id=student_id,
                student_name=student_name,
                feedback_text=f"Manual review needed: {reason}",
                confidence=0.0,
            )

        if backend is None:
            return DraftFeedback(
                student_id=student_id,
                student_name=student_name,
                feedback_text="Manual review needed: no LLM backend available.",
                confidence=0.0,
            )

        # Build prompt components
        profile = teacher_profile or {}
        feedback_style = profile.get("feedback_style", "warm")
        feedback_length = profile.get("feedback_length", "moderate")

        system_prompt = FEEDBACK_SYSTEM_PROMPT.format(
            feedback_style=feedback_style,
            feedback_length=feedback_length,
        )

        # Build the user prompt
        prompt = FEEDBACK_DRAFT_PROMPT.format(
            student_name=student_name,
            assignment_prompt=assignment_prompt,
            lens_fragment=_build_lens_fragment(analysis_lens),
            preprocessing_fragment=_build_preprocessing_fragment(preprocessing_meta),
            theme_tags=_format_list(coding_record.get("theme_tags", [])),
            emotional_register=coding_record.get("emotional_register", "not assessed"),
            notable_quotes=_format_quotes(coding_record.get("notable_quotes", [])),
            concepts_applied=_format_list(coding_record.get("concepts_applied", [])),
            personal_connections=_format_list(coding_record.get("personal_connections", [])),
            readings_referenced=_format_list(coding_record.get("readings_referenced", [])),
            concern_context=_build_wellbeing_context(coding_record),
            profile_fragment="",
            style_fragment=_build_style_fragment(feedback_style, analysis_lens),
            length_fragment=_build_length_fragment(feedback_length),
        )

        # Call LLM
        try:
            raw = send_text(backend, prompt, system_prompt)
        except Exception as e:
            log.warning("Feedback LLM call failed for %s: %s", student_name, e)
            return DraftFeedback(
                student_id=student_id,
                student_name=student_name,
                feedback_text="Manual review needed: LLM call failed.",
                confidence=0.0,
            )

        parsed = parse_json_response(raw)

        if "_parse_error" in parsed:
            # Retry once
            repair = JSON_REPAIR_PROMPT.format(
                raw_response=raw[:1500],
                expected_format=(
                    '{"feedback_text": "...", "strengths_noted": [...], '
                    '"areas_for_growth": [...], "question_for_student": "...", '
                    '"confidence": 0.8}'
                ),
            )
            try:
                raw = send_text(backend, repair, system_prompt)
                parsed = parse_json_response(raw)
            except Exception:
                pass

        if "_parse_error" in parsed:
            log.warning("Feedback JSON parse failed for %s", student_name)
            return DraftFeedback(
                student_id=student_id,
                student_name=student_name,
                feedback_text="Manual review needed: could not parse LLM response.",
                confidence=0.0,
            )

        return DraftFeedback(
            student_id=student_id,
            student_name=student_name,
            feedback_text=parsed.get("feedback_text", ""),
            strengths_noted=parsed.get("strengths_noted", []),
            areas_for_growth=parsed.get("areas_for_growth", []),
            question_for_student=parsed.get("question_for_student", ""),
            confidence=_safe_confidence(parsed.get("confidence", 0.7)),
        )

    def draft_batch(
        self,
        coding_records: List[dict],
        assignment_prompt: str,
        analysis_lens: Optional[dict] = None,
        teacher_profile: Optional[dict] = None,
        tier: str = "lightweight",
        backend: Optional[BackendConfig] = None,
        throttle_delay: float = 2.0,
    ) -> List[DraftFeedback]:
        """Draft feedback for all students. Respects throttle delay."""
        import time

        results = []
        for i, record in enumerate(coding_records):
            # Extract preprocessing metadata
            preprocessing_meta = None
            prep = record.get("preprocessing")
            if prep:
                preprocessing_meta = prep if isinstance(prep, dict) else {}

            draft = self.draft_feedback(
                coding_record=record,
                assignment_prompt=assignment_prompt,
                analysis_lens=analysis_lens,
                preprocessing_meta=preprocessing_meta,
                teacher_profile=teacher_profile,
                tier=tier,
                backend=backend,
            )
            results.append(draft)

            # Throttle between LLM calls
            if throttle_delay > 0 and i < len(coding_records) - 1:
                time.sleep(throttle_delay)

        return results
