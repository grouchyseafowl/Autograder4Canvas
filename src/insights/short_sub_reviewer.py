"""
Short Submission Reviewer — LLM-based engagement assessment.

Uses the lightweight tier (8B local model) for a binary classification:
does this below-threshold submission demonstrate engagement?

Follows the same LLM backend pattern as the insights pipeline:
auto_detect_backend -> send_text -> parse JSON -> validate with Pydantic.

Anti-bias post-processing mirrors concern_detector.py: checks LLM output
for deficit framing and register-correlated confidence gaps.
"""

import logging
import re
from typing import Optional

from insights.llm_backend import BackendConfig, auto_detect_backend, parse_json_response, send_text
from insights.prompts import (
    SHORT_SUB_DISCUSSION_PROMPT,
    SHORT_SUB_REVIEW_PROMPT,
    SHORT_SUB_SYSTEM_PROMPT,
)
from insights.short_sub_models import ShortSubReview

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Anti-bias post-processing
# ---------------------------------------------------------------------------

# Deficit framing in LLM rationale that may signal register bias
_DEFICIT_MARKERS = re.compile(
    r"\b(limited vocabulary|lacks detail|lacks depth|basic response|"
    r"minimal effort|low quality|poorly written|"
    r"insufficient|inadequate|superficial|"
    r"doesn't try|didn't bother|no real engagement|"
    r"not serious|not genuine|too short to assess)\b",
    re.IGNORECASE,
)

# Informal register markers in submission text
_INFORMAL_REGISTER = re.compile(
    r"\b(ain't|gonna|gotta|finna|lowkey|deadass|"
    r"for real|hit different|no cap|bruh|nah|yo\b|ion\b|imo\b|"
    r"like for real|that's facts|on god)\b",
    re.IGNORECASE,
)


def check_engagement_bias(
    review: ShortSubReview, submission_text: str
) -> ShortSubReview:
    """Anti-bias post-processing on LLM short sub verdict.

    1. Catches deficit framing in rationale when submission has engagement evidence
    2. Flags potential register bias (informal text + low confidence + TEACHER_REVIEW)
    3. Prevents placeholder/partial_attempt classification when engagement evidence exists
    """
    # Check 1: deficit language in rationale despite engagement evidence
    if _DEFICIT_MARKERS.search(review.rationale) and review.engagement_evidence:
        review.bias_warning = (
            "\u26a0 Note: The model used deficit framing in its assessment "
            "despite finding engagement evidence. This may reflect bias "
            "toward academic register rather than actual engagement level."
        )
        # Nudge confidence up if model found evidence but rated it low
        if review.confidence < 0.5:
            review.confidence = min(0.6, review.confidence + 0.2)

    # Check 2: informal register + low confidence may be register bias
    if (
        _INFORMAL_REGISTER.search(submission_text)
        and review.confidence < 0.5
        and review.verdict == "TEACHER_REVIEW"
        and not review.bias_warning
    ):
        review.bias_warning = (
            "\u26a0 Note: This submission uses informal register (AAVE, "
            "colloquial). Low confidence may reflect model bias toward "
            "academic writing style rather than actual engagement level."
        )

    # Check 3: prevent placeholder/partial_attempt when evidence exists
    if review.brevity_category in ("placeholder", "partial_attempt") and review.engagement_evidence:
        review.brevity_category = "unclear"
        review.verdict = "TEACHER_REVIEW"
        review.bias_warning = (
            (review.bias_warning + " | " if review.bias_warning else "")
            + "\u26a0 Reclassified from placeholder/partial_attempt: "
            "engagement evidence was found."
        )

    return review


# ---------------------------------------------------------------------------
# Thread context formatting
# ---------------------------------------------------------------------------

def _format_thread_context(ctx: dict) -> str:
    """Format thread context dict into a readable string for the prompt."""
    parts = []
    if ctx.get("parent_post"):
        parts.append(f"ORIGINAL POST:\n{ctx['parent_post'][:500]}")
    reviewed_idx = ctx.get("reviewed_reply_index", -1)
    for i, reply in enumerate(ctx.get("sibling_replies", [])):
        label = ">> THIS REPLY (being reviewed)" if i == reviewed_idx else f"Reply {i + 1}"
        parts.append(f"{label}:\n{reply[:300]}")
    return "\n\n".join(parts) if parts else "(no thread context available)"


# ---------------------------------------------------------------------------
# Main review function
# ---------------------------------------------------------------------------

def review_short_submission(
    student_name: str,
    submission_text: str,
    word_count: int,
    min_word_count: int,
    assignment_prompt: str = "",
    review_guidance: str = "",
    equity_fragment: str = "",
    thread_context: Optional[dict] = None,
    backend: Optional[BackendConfig] = None,
) -> Optional[ShortSubReview]:
    """Send one short submission to the LLM for engagement assessment.

    Returns ShortSubReview on success, None on failure (graceful degradation).
    The backend should be detected ONCE before the student loop and passed in;
    this avoids repeated Ollama availability checks.
    """
    if backend is None:
        backend = auto_detect_backend(tier="lightweight")
    if backend is None:
        log.warning("Short Sub Review: no LLM backend available")
        return None

    # Safety truncation — 8B models have limited context
    text = submission_text[:8000]

    review_guidance_block = (
        f"GENRE GUIDANCE:\n{review_guidance}" if review_guidance else ""
    )
    equity_block = equity_fragment or ""

    if thread_context:
        prompt = SHORT_SUB_DISCUSSION_PROMPT.format(
            student_name=student_name,
            word_count=word_count,
            min_word_count=min_word_count,
            assignment_prompt=assignment_prompt or "(not provided)",
            thread_context=_format_thread_context(thread_context),
            submission_text=text,
            review_guidance=review_guidance_block,
            equity_fragment=equity_block,
        )
    else:
        prompt = SHORT_SUB_REVIEW_PROMPT.format(
            student_name=student_name,
            word_count=word_count,
            min_word_count=min_word_count,
            assignment_prompt=assignment_prompt or "(not provided)",
            submission_text=text,
            review_guidance=review_guidance_block,
            equity_fragment=equity_block,
        )

    # send_text raises RuntimeError on failure — catch per-student
    try:
        raw = send_text(backend, prompt, SHORT_SUB_SYSTEM_PROMPT)
    except RuntimeError as exc:
        log.warning("Short Sub Review LLM call failed for %s: %s", student_name, exc)
        return None

    # Parse JSON — use parse_json_response to handle markdown fences
    try:
        data = parse_json_response(raw)
        review = ShortSubReview(**data)
    except Exception as exc:
        log.warning("Short Sub Review parse failed for %s: %s | raw: %.200s", student_name, exc, raw)
        return None

    # Floor rule: very low confidence -> always TEACHER_REVIEW
    if review.confidence < 0.3:
        review.verdict = "TEACHER_REVIEW"

    # Attach thread context to result for storage
    if thread_context:
        review.thread_context = thread_context

    # Anti-bias post-processing
    review = check_engagement_bias(review, submission_text)

    return review
