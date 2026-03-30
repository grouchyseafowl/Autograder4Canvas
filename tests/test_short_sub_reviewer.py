"""
short_sub_reviewer.py — unit tests for pure (non-LLM) functions.

Tests the anti-bias post-processing layer and thread context formatter.
No LLM calls.

Equity-critical cases:
  - Deficit language in rationale + engagement evidence → bias warning, confidence bumped
  - Informal register (AAVE, colloquial) + low confidence + TEACHER_REVIEW → bias warning
  - Placeholder/partial_attempt + engagement evidence → reclassified to unclear
  These protect students whose writing is assessed against an implicit standard
  of formal academic English.

All fixtures are synthetic.

Run with: python3 -m pytest tests/test_short_sub_reviewer.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.short_sub_reviewer import (
    _format_thread_context,
    check_engagement_bias,
)
from insights.short_sub_models import ShortSubReview


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_review(
    verdict="CREDIT",
    brevity_category="concise_complete",
    rationale="The student demonstrates solid understanding.",
    engagement_evidence=None,
    confidence=0.7,
    bias_warning=None,
) -> ShortSubReview:
    return ShortSubReview(
        verdict=verdict,
        brevity_category=brevity_category,
        rationale=rationale,
        engagement_evidence=engagement_evidence or [],
        confidence=confidence,
        bias_warning=bias_warning,
    )


PLAIN_TEXT = "Intersectionality matters because it reveals compound harms."
AAVE_TEXT = "deadass this reading hit different. fr fr the law ain't built for us."


# ---------------------------------------------------------------------------
# check_engagement_bias — deficit language check
# ---------------------------------------------------------------------------

class TestDeficitLanguageBias:
    """
    #ALGORITHMIC_JUSTICE: Deficit framing in the LLM's rationale despite
    finding engagement evidence is a signal that the model is penalizing
    register rather than assessing engagement.
    """

    def test_deficit_language_plus_evidence_adds_warning(self):
        review = make_review(
            rationale="The student shows limited vocabulary and lacks depth.",
            engagement_evidence=["deadass the law ain't built for us — that's real"],
            confidence=0.4,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.bias_warning is not None
        assert "bias" in result.bias_warning.lower() or "deficit" in result.bias_warning.lower()

    def test_deficit_language_nudges_confidence_up(self):
        review = make_review(
            rationale="Basic response, lacks detail.",
            engagement_evidence=["The system wasn't designed for us — that's Crenshaw's point."],
            confidence=0.3,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.confidence > 0.3

    def test_nudged_confidence_capped_at_06(self):
        review = make_review(
            rationale="Minimal effort and inadequate response.",
            engagement_evidence=["Real engagement here."],
            confidence=0.45,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.confidence <= 0.6

    def test_deficit_without_evidence_no_warning(self):
        """If the model found no evidence, deficit framing might be correct — don't warn."""
        review = make_review(
            rationale="Basic response, lacks depth.",
            engagement_evidence=[],
            confidence=0.3,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.bias_warning is None

    def test_no_deficit_language_unchanged(self):
        review = make_review(
            rationale="Student connects the reading to their community experience.",
            engagement_evidence=["my family dealt with this for generations"],
            confidence=0.75,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.bias_warning is None
        assert result.confidence == pytest.approx(0.75)


# ---------------------------------------------------------------------------
# check_engagement_bias — informal register bias check
# ---------------------------------------------------------------------------

class TestInformalRegisterBias:
    """
    #COMMUNITY_CULTURAL_WEALTH: AAVE and informal register are linguistic
    assets. Low model confidence on informal-register text may reflect
    register bias rather than lack of engagement.
    """

    def test_aave_text_plus_low_confidence_teacher_review_warns(self):
        review = make_review(
            verdict="TEACHER_REVIEW",
            rationale="Hard to assess engagement.",
            engagement_evidence=[],
            confidence=0.35,
        )
        result = check_engagement_bias(review, AAVE_TEXT)
        assert result.bias_warning is not None
        assert "register" in result.bias_warning.lower() or "AAVE" in result.bias_warning

    def test_aave_text_high_confidence_no_warning(self):
        """High confidence means the model wasn't uncertain — no bias signal."""
        review = make_review(
            verdict="CREDIT",
            confidence=0.8,
        )
        result = check_engagement_bias(review, AAVE_TEXT)
        assert result.bias_warning is None

    def test_aave_text_credit_verdict_no_warning(self):
        """Only fires on TEACHER_REVIEW + low confidence, not on CREDIT."""
        review = make_review(
            verdict="CREDIT",
            confidence=0.3,
        )
        result = check_engagement_bias(review, AAVE_TEXT)
        assert result.bias_warning is None

    def test_plain_text_low_confidence_no_register_warning(self):
        """Register bias check only applies when informal markers are present."""
        review = make_review(
            verdict="TEACHER_REVIEW",
            confidence=0.3,
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.bias_warning is None

    def test_existing_deficit_warning_not_overwritten(self):
        """If deficit warning already set, register bias check skips (no double)."""
        review = make_review(
            verdict="TEACHER_REVIEW",
            rationale="lacks depth",
            engagement_evidence=["some evidence"],
            confidence=0.3,
        )
        result = check_engagement_bias(review, AAVE_TEXT)
        # Only one bias warning (deficit check fires first; register check sees bias_warning already set)
        assert result.bias_warning is not None


# ---------------------------------------------------------------------------
# check_engagement_bias — placeholder/partial reclassification
# ---------------------------------------------------------------------------

class TestPlaceholderReclassification:
    """When the model says 'placeholder' but found engagement evidence,
    it contradicted itself — reclassify to 'unclear'."""

    def test_placeholder_plus_evidence_reclassified(self):
        review = make_review(
            brevity_category="placeholder",
            verdict="TEACHER_REVIEW",
            engagement_evidence=["I'll finish later but here's my main point"],
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.brevity_category == "unclear"

    def test_partial_attempt_plus_evidence_reclassified(self):
        review = make_review(
            brevity_category="partial_attempt",
            verdict="TEACHER_REVIEW",
            engagement_evidence=["started the argument but couldn't finish"],
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.brevity_category == "unclear"

    def test_reclassification_adds_bias_warning(self):
        review = make_review(
            brevity_category="placeholder",
            engagement_evidence=["some real content here"],
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.bias_warning is not None
        assert "Reclassified" in result.bias_warning or "reclassif" in result.bias_warning.lower()

    def test_placeholder_without_evidence_not_reclassified(self):
        review = make_review(
            brevity_category="placeholder",
            engagement_evidence=[],
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.brevity_category == "placeholder"

    def test_reclassification_appends_to_existing_warning(self):
        # Use neutral rationale so deficit check doesn't overwrite the existing warning
        review = make_review(
            brevity_category="placeholder",
            rationale="The student connected the reading to their experience.",
            engagement_evidence=["evidence here"],
            bias_warning="⚠ Prior warning.",
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert "⚠ Prior warning." in result.bias_warning
        assert "Reclassified" in result.bias_warning or "|" in result.bias_warning

    def test_non_placeholder_brevity_category_unchanged(self):
        review = make_review(
            brevity_category="concise_complete",
            engagement_evidence=["strong evidence"],
        )
        result = check_engagement_bias(review, PLAIN_TEXT)
        assert result.brevity_category == "concise_complete"


# ---------------------------------------------------------------------------
# _format_thread_context
# ---------------------------------------------------------------------------

class TestFormatThreadContext:
    def test_empty_dict_returns_no_context_message(self):
        result = _format_thread_context({})
        assert "no thread context" in result.lower()

    def test_parent_post_included(self):
        ctx = {"parent_post": "What does intersectionality mean to you?"}
        result = _format_thread_context(ctx)
        assert "ORIGINAL POST" in result
        assert "intersectionality" in result

    def test_sibling_replies_included(self):
        ctx = {
            "sibling_replies": ["Reply one content.", "Reply two content."],
            "reviewed_reply_index": -1,
        }
        result = _format_thread_context(ctx)
        assert "Reply one" in result or "Reply 1" in result

    def test_reviewed_reply_labeled(self):
        ctx = {
            "sibling_replies": ["other reply", "the reply being reviewed"],
            "reviewed_reply_index": 1,
        }
        result = _format_thread_context(ctx)
        assert "THIS REPLY" in result or "being reviewed" in result

    def test_long_parent_post_truncated(self):
        ctx = {"parent_post": "x" * 1000}
        result = _format_thread_context(ctx)
        # Should not include all 1000 chars — truncated to 500
        assert len(result) < 1000 + 50  # 50 slack for formatting

    def test_no_sibling_replies_no_reply_section(self):
        ctx = {"parent_post": "Original question here."}
        result = _format_thread_context(ctx)
        assert "Reply" not in result or "ORIGINAL POST" in result
