"""
patterns.py — unit tests.

Tests the VADER+keyword signal matrix, sentiment reliability assessment,
and pattern matching functions.

Equity-critical cases:
  - "negative VADER + structural critique keywords" → APPROPRIATE, not a concern.
    Passionate analysis of injustice looks 'negative' to VADER but is the
    exact opposite of a concern — it's sophisticated academic engagement.
  - AAVE ≥ 2 distinct markers → sentiment suppressed (tool bias, not writer deficit).
  - Translated text with nontrivial score → suppressed (ESL proxy).
  - Two-tier word-count: hard suppress <15, soft caveat 15–59.

All tests are pure computation — no LLM, no MLX.

Run with: python3 -m pytest tests/test_patterns.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.patterns import (
    CRITICAL_KEYWORDS,
    assess_sentiment_reliability,
    classify_vader_polarity,
    has_critical_keywords,
    match_all_patterns,
    match_keyword_category,
    signal_matrix_classify,
)


# ---------------------------------------------------------------------------
# Synthetic text fixtures
# ---------------------------------------------------------------------------

STRUCTURAL_CRITIQUE = (
    "I want to critique and challenge the assumption that these legal frameworks "
    "are neutral. The reading argues that systemic racism embedded in these "
    "institutions operates through structural mechanisms. According to the author, "
    "decolonizing our approach to liberation means naming oppression explicitly."
)

ESSENTIALIZING_TEXT = (
    "All those people are just like that. That culture doesn't value education. "
    "They always act the same way no matter what."
)

DISTRESS_TEXT = (
    "I'm scared to go to school. I feel unsafe and I can't cope anymore. "
    "I don't see the point of continuing. Nobody would care if I disappeared."
)

TEACHER_TEST_TEXT = (
    "If you're actually reading this, thanks for checking. I've been struggling "
    "and wasn't sure anyone would notice."
)

AAVE_TWO_MARKERS = (
    "Y'all be acting like the law treats everyone the same but deadass it don't. "
    "Crenshaw done explained it perfectly and I finally got the language for it. "
    "The system ain't broken it was built this way for real."
)

AAVE_ONE_MARKER = (
    "I think Crenshaw's argument about intersectionality is really important. "
    "Y'all know how the courts have treated these cases. The framework itself "
    "needs to change, not just how it's applied in individual cases. "
    "Her analysis is compelling and I found myself agreeing with most of it."
)

PLAIN_TEXT = (
    "Crenshaw argues that intersectionality reveals how the law fails Black women. "
    "The General Motors case illustrates this structural erasure clearly. "
    "Her framework challenges courts to recognize compound harm. "
    "The analysis is thorough and well-supported by legal precedent throughout."
)


# ---------------------------------------------------------------------------
# classify_vader_polarity
# ---------------------------------------------------------------------------

class TestClassifyVaderPolarity:
    def test_positive_above_threshold(self):
        assert classify_vader_polarity(0.05) == "positive"
        assert classify_vader_polarity(0.5) == "positive"
        assert classify_vader_polarity(1.0) == "positive"

    def test_negative_below_threshold(self):
        assert classify_vader_polarity(-0.05) == "negative"
        assert classify_vader_polarity(-0.5) == "negative"
        assert classify_vader_polarity(-1.0) == "negative"

    def test_neutral_in_middle(self):
        assert classify_vader_polarity(0.0) == "neutral"
        assert classify_vader_polarity(0.04) == "neutral"
        assert classify_vader_polarity(-0.04) == "neutral"

    def test_boundary_exactly_005(self):
        # Exactly ±0.05 triggers the non-neutral branch
        assert classify_vader_polarity(0.05) == "positive"
        assert classify_vader_polarity(-0.05) == "negative"


# ---------------------------------------------------------------------------
# match_keyword_category
# ---------------------------------------------------------------------------

class TestMatchKeywordCategory:
    def test_critical_analysis_detected(self):
        cats = match_keyword_category(STRUCTURAL_CRITIQUE)
        assert "critical" in cats

    def test_essentializing_detected(self):
        cats = match_keyword_category(ESSENTIALIZING_TEXT)
        assert "essentializing" in cats

    def test_distress_detected(self):
        cats = match_keyword_category(DISTRESS_TEXT)
        assert "distress" in cats

    def test_teacher_test_detected(self):
        cats = match_keyword_category(TEACHER_TEST_TEXT)
        assert "direct_address" in cats

    def test_empty_text_no_categories(self):
        cats = match_keyword_category("")
        assert cats == []

    def test_plain_text_no_concern_categories(self):
        cats = match_keyword_category(PLAIN_TEXT)
        # Should not match essentializing, distress, or direct_address
        assert "essentializing" not in cats
        assert "distress" not in cats
        assert "direct_address" not in cats

    def test_disengagement_not_returned_by_match_category(self):
        # disengagement is detected by word count in signal_matrix_classify,
        # not by keyword matching
        cats = match_keyword_category("ok")
        assert "disengagement" not in cats


# ---------------------------------------------------------------------------
# signal_matrix_classify — equity-critical tests
# ---------------------------------------------------------------------------

class TestSignalMatrixClassify:
    """
    #ALGORITHMIC_JUSTICE: The matrix must NOT flag passionate critique as a
    concern. VADER reads structural critique as 'negative' — if we treated
    that as a warning, we'd systematically flag students doing the most
    sophisticated political analysis.
    """

    def test_negative_critical_is_appropriate(self):
        """Structural critique with negative VADER → APPROPRIATE, not a concern."""
        results = signal_matrix_classify(STRUCTURAL_CRITIQUE, vader_compound=-0.4)
        signal_types = [r[0] for r in results]
        assert "APPROPRIATE" in signal_types, (
            "Passionate critique of injustice must be APPROPRIATE, not flagged"
        )

    def test_positive_critical_is_appropriate(self):
        results = signal_matrix_classify(
            "I critique the institutional racism in this system.", vader_compound=0.2
        )
        signal_types = [r[0] for r in results]
        assert "APPROPRIATE" in signal_types

    def test_negative_essentializing_is_concern(self):
        results = signal_matrix_classify(ESSENTIALIZING_TEXT, vader_compound=-0.3)
        signal_types = [r[0] for r in results]
        assert "CONCERN" in signal_types

    def test_neutral_essentializing_is_concern(self):
        results = signal_matrix_classify(ESSENTIALIZING_TEXT, vader_compound=0.0)
        signal_types = [r[0] for r in results]
        assert "CONCERN" in signal_types

    def test_positive_essentializing_is_possible_concern(self):
        results = signal_matrix_classify(ESSENTIALIZING_TEXT, vader_compound=0.5)
        signal_types = [r[0] for r in results]
        assert "POSSIBLE CONCERN" in signal_types

    def test_negative_distress_is_check_in(self):
        results = signal_matrix_classify(DISTRESS_TEXT, vader_compound=-0.7)
        signal_types = [r[0] for r in results]
        assert "CHECK IN" in signal_types

    def test_neutral_distress_is_check_in(self):
        results = signal_matrix_classify(DISTRESS_TEXT, vader_compound=0.0)
        signal_types = [r[0] for r in results]
        assert "CHECK IN" in signal_types

    def test_teacher_test_produces_teacher_note(self):
        results = signal_matrix_classify(TEACHER_TEST_TEXT, vader_compound=0.0)
        signal_types = [r[0] for r in results]
        assert "TEACHER NOTE" in signal_types

    def test_results_are_4_tuples(self):
        results = signal_matrix_classify(DISTRESS_TEXT, vader_compound=-0.5)
        for r in results:
            assert len(r) == 4, "Each result should be (signal_type, category, polarity, interpretation)"

    def test_disengagement_detected_below_median(self):
        short_text = "ok I read it"
        results = signal_matrix_classify(
            short_text, vader_compound=0.0, word_count=4, median_word_count=150
        )
        signal_types = [r[0] for r in results]
        # word_count=4 is well below 40% of 150 → disengagement
        assert any(t in signal_types for t in ("PERFUNCTORY", "LOW ENGAGEMENT", "SURFACE COMPLIANCE"))

    def test_disengagement_not_detected_above_median(self):
        results = signal_matrix_classify(
            PLAIN_TEXT, vader_compound=0.0,
            word_count=len(PLAIN_TEXT.split()),
            median_word_count=50,
        )
        signal_types = [r[0] for r in results]
        assert "PERFUNCTORY" not in signal_types
        assert "LOW ENGAGEMENT" not in signal_types

    def test_positive_distress_is_verify(self):
        """Positive VADER + distress keywords → VERIFY (masked distress).
        A student writing 'I'm scared but trying to stay positive' could
        score positive while expressing real fear."""
        results = signal_matrix_classify(DISTRESS_TEXT, vader_compound=0.3)
        signal_types = [r[0] for r in results]
        assert "VERIFY" in signal_types

    def test_empty_text_no_signals(self):
        results = signal_matrix_classify("", vader_compound=0.0)
        assert results == []


# ---------------------------------------------------------------------------
# has_critical_keywords
# ---------------------------------------------------------------------------

class TestHasCriticalKeywords:
    def test_structural_racism_detected(self):
        assert has_critical_keywords("This is about structural racism in institutions.")

    def test_colonialism_detected(self):
        assert has_critical_keywords("Colonialism continues to shape these outcomes.")

    def test_liberation_detected(self):
        assert has_critical_keywords("We need liberation frameworks, not just reform.")

    def test_marginalized_detected(self):
        assert has_critical_keywords("Marginalized communities bear the cost of these policies.")

    def test_decolonize_variant_detected(self):
        assert has_critical_keywords("We need to decolonize our approach to education.")

    def test_empty_text_false(self):
        assert has_critical_keywords("") is False

    def test_neutral_text_false(self):
        assert has_critical_keywords("The reading was interesting and I enjoyed it.") is False


# ---------------------------------------------------------------------------
# match_all_patterns
# ---------------------------------------------------------------------------

class TestMatchAllPatterns:
    def test_personal_reflection_pattern(self):
        text = "In my experience, this reading really resonated with my family's story."
        hits = match_all_patterns(text)
        assert "personal_reflection" in hits

    def test_critical_analysis_pattern(self):
        text = "I want to challenge the assumption that these outcomes are neutral."
        hits = match_all_patterns(text)
        assert "critical_analysis" in hits

    def test_distress_markers_pattern(self):
        text = "I feel scared and unsafe right now and can't cope with things."
        hits = match_all_patterns(text)
        assert "distress_markers" in hits

    def test_empty_text_returns_empty_dict(self):
        assert match_all_patterns("") == {}

    def test_count_reflects_matches(self):
        text = "I connect this to my experience and how it connects to my life."
        hits = match_all_patterns(text)
        # "connect" appears twice → count should be ≥ 2
        assert hits.get("conceptual_connection", 0) >= 2

    def test_no_false_positives_on_plain_text(self):
        hits = match_all_patterns("The reading covered the main ideas from the author.")
        # No distress, no essentializing, no teacher_test
        assert "distress_markers" not in hits
        assert "essentializing" not in hits
        assert "teacher_test" not in hits


# ---------------------------------------------------------------------------
# assess_sentiment_reliability — two-tier threshold
# ---------------------------------------------------------------------------

class TestAssessSentimentReliability:
    """
    #FEMINIST_TECHNOSCIENCE: The 'objective' sentiment score is unreliable
    for entire classes of text. These tests lock down that the system
    acknowledges this rather than passing biased scores silently.

    #LANGUAGE_JUSTICE: Translated and transcribed text gets appropriate
    caution rather than being run through tools trained on standard English.
    """

    # --- Hard suppression ---

    def test_short_submission_suppressed(self):
        result = assess_sentiment_reliability("short text here", word_count=3)
        assert result.tier == "suppressed"
        assert "short_submission" in result.triggers[0]

    def test_boundary_14_words_suppressed(self):
        result = assess_sentiment_reliability("word " * 14, word_count=14)
        assert result.tier == "suppressed"

    def test_aave_two_markers_suppressed(self):
        """≥2 distinct AAVE markers → suppressed (tool bias, not writer deficit)."""
        result = assess_sentiment_reliability(AAVE_TWO_MARKERS, word_count=80)
        assert result.tier == "suppressed", (
            "AAVE text must be suppressed — VADER/GoEmotions are biased against "
            "AAVE grammar (Blodgett et al., EMNLP 2017)"
        )
        assert any("aave_markers" in t for t in result.triggers)

    def test_aave_suppression_reason_is_tool_not_writer(self):
        """Suppression reason must frame this as tool bias, not writer identity."""
        result = assess_sentiment_reliability(AAVE_TWO_MARKERS, word_count=80)
        assert "Bias risk" in result.caveat or "unreliable" in result.caveat

    def test_translated_with_nontrivial_score_suppressed(self):
        result = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80,
            was_translated=True, compound_score=0.5,
        )
        assert result.tier == "suppressed"
        assert any("esl_translated" in t for t in result.triggers)

    def test_translated_neutral_score_not_suppressed(self):
        """Translated text with a neutral score (0.0) should not trigger ESL suppression."""
        result = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80,
            was_translated=True, compound_score=0.0,
        )
        # compound_score=0.0 → abs() = 0.0 ≤ 0.1 → no ESL trigger
        # No other triggers on PLAIN_TEXT with sufficient word count
        assert result.tier == "high"

    def test_esl_suppression_boundary_at_01(self):
        """abs(compound_score) must be > 0.1 (not >=) to trigger ESL suppression."""
        # 0.1 exactly → NOT suppressed (boundary is strictly >)
        result_at = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80,
            was_translated=True, compound_score=0.1,
        )
        assert result_at.tier == "high"
        # 0.11 → suppressed
        result_above = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80,
            was_translated=True, compound_score=0.11,
        )
        assert result_above.tier == "suppressed"

    # --- Soft caution (low) ---

    def test_short_but_above_floor_is_low(self):
        """15–59 words → soft caveat, not suppressed."""
        result = assess_sentiment_reliability(PLAIN_TEXT[:200], word_count=30)
        assert result.tier == "low"
        assert any("short_submission" in t for t in result.triggers)

    def test_boundary_15_words_is_low(self):
        result = assess_sentiment_reliability("word " * 15, word_count=15)
        assert result.tier == "low"

    def test_aave_one_marker_is_low(self):
        result = assess_sentiment_reliability(AAVE_ONE_MARKER, word_count=80)
        assert result.tier == "low"
        assert any("aave_marker" in t for t in result.triggers)

    def test_transcribed_is_low(self):
        result = assess_sentiment_reliability(PLAIN_TEXT, word_count=80, was_transcribed=True)
        assert result.tier == "low"
        assert "oral_transcription" in result.triggers

    def test_low_assignment_connection_is_low(self):
        result = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80, assignment_connection_overlap=0.05
        )
        assert result.tier == "low"
        assert any("low_assignment_connection" in t for t in result.triggers)

    def test_assignment_connection_above_threshold_not_triggered(self):
        result = assess_sentiment_reliability(
            PLAIN_TEXT, word_count=80, assignment_connection_overlap=0.15
        )
        # overlap=0.15 ≥ 0.10 threshold → not triggered
        assert "low_assignment_connection" not in " ".join(result.triggers)

    # --- High (no triggers) ---

    def test_sufficient_plain_text_is_high(self):
        result = assess_sentiment_reliability(PLAIN_TEXT, word_count=80)
        assert result.tier == "high"
        assert result.caveat == ""
        assert result.triggers == []

    def test_high_tier_has_empty_caveat(self):
        result = assess_sentiment_reliability(PLAIN_TEXT, word_count=100)
        assert result.caveat == ""

    def test_boundary_60_words_is_high(self):
        result = assess_sentiment_reliability("word " * 60, word_count=60)
        assert result.tier == "high"

    # --- Suppression message content ---

    def test_suppressed_caveat_instructs_read_from_text(self):
        result = assess_sentiment_reliability("word " * 5, word_count=5)
        assert "directly from" in result.caveat or "from the student" in result.caveat

    def test_low_caveat_says_weak_signal(self):
        result = assess_sentiment_reliability("word " * 30, word_count=30)
        assert "weak signal" in result.caveat or "CAUTION" in result.caveat
