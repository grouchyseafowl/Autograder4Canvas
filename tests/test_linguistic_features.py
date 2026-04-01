"""
linguistic_features.py — unit tests.

Tests AAVE detection, multilingual tier suppression, ESL feature detection,
`_derive_tier` logic, `detect_features` output contract, and short-submission
tier thresholds.

All pure functions — no LLM, no DB, no MLX.

Equity-critical regression cases:
  - AAVE writing must NOT suppress just because it sounds "negative"
  - Translated submissions must caveat sentiment, never suppress just for translation
  - Righteous anger / political urgency must not trigger false suppression
  - AAVE lexical features produce asset labels, not deficit labels

Run with: python -m pytest tests/test_linguistic_features.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from modules.linguistic_features import (
    LinguisticFeature,
    LinguisticFeatureResult,
    FeatureBaseline,
    _derive_tier,
    _dedupe_assets,
    _merge_aic,
    _build_caveat,
    detect_features,
)


# ---------------------------------------------------------------------------
# Synthetic corpus — no real student data
# ---------------------------------------------------------------------------

# AAVE-inflected academic writing — strong AAVE lexical + syntax
AAVE_TEXT = """\
Let me be real about what Crenshaw is saying because I think a lot of people
miss it. She ain't just saying discrimination exists. She saying the law itself
was built for a particular kind of person.

My aunt she tired of explaining this to people who don't get it. They was
asking her to prove both race AND gender hurt her, like those things separate.
That's what the reading calls intersectional invisibility — you can't prove
it because the system wasn't built to see it.

Deadass, the General Motors case shows how the law working exactly like it
was designed to. No cap."""

# Standard academic writing — no special features. Must be > 80 words to avoid
# short_submission suppression (the structural detector fires below 80 words).
STANDARD_TEXT = """\
Crenshaw's concept of intersectionality challenges legal frameworks that
treat discrimination categories as mutually exclusive. The General Motors
case illustrates how this creates structural invisibility for plaintiffs
who face multiple intersecting forms of discrimination.

The argument is compelling because it exposes how single-axis analysis
fails to capture the compound disadvantage experienced by individuals at
the intersection of multiple marginalized identities.

The court's decision in the GM case reveals a deeper problem: legal
categories were constructed without considering overlapping forms of
discrimination. When plaintiffs can only argue along a single axis,
the law becomes a tool that replicates the very harm it claims to address.
This structural limitation is the central insight of Crenshaw's framework."""

# ESL writing with L1 transfer features
ESL_TEXT = """\
The intersectionality concept is very important for understanding
discrimination. In my country, we also have same problem where people
who is woman AND also minority, they cannot get help from law because
law only see one discrimination at time.

I think the reading make good argument. The peoples in marginalized groups
they suffer double discrimination. This is very unfair situation."""

# Translated submission (was_translated=True). Must be > 80 words to avoid
# short_submission suppression so we can test translation-specific behavior.
TRANSLATED_TEXT = """\
The concept of intersectionality allows us to understand how different
forms of discrimination interact and compound each other. The law should
recognize combined forms of discrimination rather than treating each axis
separately, because the experience of facing multiple forms of discrimination
at once is qualitatively different from facing only one.

Students in our class made similar observations during the discussion.
The reading by Crenshaw demonstrates how the General Motors case exposed
the limitations of single-axis legal reasoning. When the court refused to
consider race and gender as a combined category, it made a political choice
about whose suffering was legally legible and whose was not."""

# Short text — below meaningful analysis threshold
SHORT_TEXT = "This was interesting."

# Righteous political anger — must NOT suppress (course material engagement)
RIGHTEOUS_ANGER_TEXT = """\
This reading made me furious and that's okay. The law was designed to
exclude Black women — that's not an accident, that's architecture. When
the judge dismissed the case he was doing exactly what the system trained
him to do.

I'm supposed to analyze this academically but I'm also supposed to be
honest: the data Crenshaw presents about General Motors is damning.
They hired Black people for factory jobs and white women for office jobs
and then said "we're not discriminating" because they could show both
groups somewhere. That's the most cynical legal argument I have ever read."""

# Multilingual code-meshing
MULTILINGUAL_TEXT = """\
La lectura de Crenshaw me hizo pensar mucho. Intersectionality — I don't
know the English word for what I want to say here, the way things stack on
top of each other — it's like what we call in Spanish "estar entre dos aguas,"
to be between two waters.

My grandmother came here and was Latina AND poor AND a woman AND an immigrant.
The law never had a box for all of that at once."""


# ---------------------------------------------------------------------------
# _derive_tier
# ---------------------------------------------------------------------------

class TestDeriveTier:
    def test_no_features_returns_high(self):
        assert _derive_tier([]) == "high"

    def test_suppress_feature_returns_suppressed(self):
        f = LinguisticFeature(
            name="aave_lexical", category="syntactic_variation",
            sentiment_effect="suppress",
        )
        assert _derive_tier([f]) == "suppressed"

    def test_caveat_feature_returns_low(self):
        f = LinguisticFeature(
            name="oral_transcription", category="register_affect",
            sentiment_effect="caveat",
        )
        assert _derive_tier([f]) == "low"

    def test_suppress_beats_caveat(self):
        """suppress takes priority over caveat."""
        suppress_f = LinguisticFeature(
            name="aave_lexical", category="syntactic_variation",
            sentiment_effect="suppress",
        )
        caveat_f = LinguisticFeature(
            name="oral_transcription", category="register_affect",
            sentiment_effect="caveat",
        )
        assert _derive_tier([caveat_f, suppress_f]) == "suppressed"

    def test_none_effect_returns_high(self):
        f = LinguisticFeature(
            name="citation_count", category="academic_convention",
            sentiment_effect="none",
        )
        assert _derive_tier([f]) == "high"


# ---------------------------------------------------------------------------
# _dedupe_assets
# ---------------------------------------------------------------------------

class TestDedupeAssets:
    def test_empty_returns_empty(self):
        assert _dedupe_assets([]) == []

    def test_single_asset(self):
        f = LinguisticFeature(
            name="aave_lexical", category="syntactic_variation",
            asset_label="AAVE linguistic features — authentic voice",
        )
        result = _dedupe_assets([f])
        assert len(result) == 1
        assert "AAVE" in result[0]

    def test_deduplicates(self):
        label = "AAVE linguistic features — authentic voice"
        f1 = LinguisticFeature(name="f1", category="x", asset_label=label)
        f2 = LinguisticFeature(name="f2", category="x", asset_label=label)
        result = _dedupe_assets([f1, f2])
        assert len(result) == 1

    def test_preserves_order(self):
        f1 = LinguisticFeature(name="f1", category="x", asset_label="First label")
        f2 = LinguisticFeature(name="f2", category="y", asset_label="Second label")
        result = _dedupe_assets([f1, f2])
        assert result[0] == "First label"
        assert result[1] == "Second label"

    def test_empty_asset_label_not_included(self):
        f = LinguisticFeature(name="f1", category="x", asset_label="")
        assert _dedupe_assets([f]) == []


# ---------------------------------------------------------------------------
# _merge_aic
# ---------------------------------------------------------------------------

class TestMergeAic:
    def test_empty_returns_empty(self):
        assert _merge_aic([]) == {}

    def test_single_adjustment(self):
        f = LinguisticFeature(
            name="aave", category="x",
            aic_weight_adjustments={"grammatical_perfection": 0.5},
        )
        result = _merge_aic([f])
        assert result["grammatical_perfection"] == pytest.approx(0.5)

    def test_most_protective_wins(self):
        """When two features adjust the same marker, lowest (most protective) wins."""
        f1 = LinguisticFeature(
            name="f1", category="x",
            aic_weight_adjustments={"grammatical_perfection": 0.5},
        )
        f2 = LinguisticFeature(
            name="f2", category="y",
            aic_weight_adjustments={"grammatical_perfection": 0.3},
        )
        result = _merge_aic([f1, f2])
        assert result["grammatical_perfection"] == pytest.approx(0.3)

    def test_different_markers_merged(self):
        f1 = LinguisticFeature(
            name="f1", category="x",
            aic_weight_adjustments={"marker_a": 0.6},
        )
        f2 = LinguisticFeature(
            name="f2", category="y",
            aic_weight_adjustments={"marker_b": 0.4},
        )
        result = _merge_aic([f1, f2])
        assert "marker_a" in result
        assert "marker_b" in result


# ---------------------------------------------------------------------------
# _build_caveat
# ---------------------------------------------------------------------------

class TestBuildCaveat:
    def test_high_tier_returns_empty(self):
        assert _build_caveat([], "high") == ""

    def test_suppressed_contains_withheld(self):
        f = LinguisticFeature(
            name="aave_lexical", category="x", sentiment_effect="suppress",
        )
        result = _build_caveat([f], "suppressed")
        assert "withheld" in result.lower()

    def test_low_tier_contains_unreliable(self):
        f = LinguisticFeature(
            name="tense_mixing", category="x", sentiment_effect="caveat",
        )
        result = _build_caveat([f], "low")
        assert "unreliable" in result.lower() or "weak signal" in result.lower()

    def test_trigger_names_included(self):
        f = LinguisticFeature(
            name="zero_copula", category="x", sentiment_effect="suppress",
        )
        result = _build_caveat([f], "suppressed")
        assert "zero_copula" in result


# ---------------------------------------------------------------------------
# detect_features — output contract
# ---------------------------------------------------------------------------

class TestDetectFeaturesContract:
    """Output shape and type contracts regardless of feature detection results."""

    def test_returns_feature_result(self):
        result = detect_features(STANDARD_TEXT, word_count=80)
        assert isinstance(result, LinguisticFeatureResult)

    def test_sentiment_tier_valid_values(self):
        for text in [STANDARD_TEXT, AAVE_TEXT, TRANSLATED_TEXT]:
            wc = len(text.split())
            r = detect_features(text, word_count=wc)
            assert r.sentiment_tier in ("high", "low", "suppressed")

    def test_asset_labels_are_strings(self):
        result = detect_features(AAVE_TEXT, word_count=len(AAVE_TEXT.split()))
        assert all(isinstance(label, str) for label in result.asset_labels)

    def test_sentiment_triggers_are_strings(self):
        result = detect_features(AAVE_TEXT, word_count=len(AAVE_TEXT.split()))
        assert all(isinstance(t, str) for t in result.sentiment_triggers)

    def test_aic_adjustments_are_floats(self):
        result = detect_features(AAVE_TEXT, word_count=len(AAVE_TEXT.split()))
        assert all(isinstance(v, float) for v in result.aic_adjustments.values())

    def test_empty_text_returns_suppressed(self):
        """Empty text (0 words) is below hard suppress floor (15) → suppressed."""
        result = detect_features("", word_count=0)
        assert result.sentiment_tier == "suppressed"


# ---------------------------------------------------------------------------
# detect_features — AAVE equity regressions
# ---------------------------------------------------------------------------

class TestAaveEquityRegressions:
    """AAVE writing must not be penalized — it gets asset labels, not suppression
    for single features. Suppression requires 2+ distinct AAVE markers.
    """

    def test_aave_text_produces_aave_asset_labels(self):
        """AAVE writing must surface AAVE-specific asset labels."""
        wc = len(AAVE_TEXT.split())
        result = detect_features(AAVE_TEXT, word_count=wc)
        assert any("AAVE" in label or "aave" in label.lower() for label in result.asset_labels), (
            f"AAVE text must produce AAVE-specific asset labels. Got: {result.asset_labels}"
        )

    def test_aave_text_suppresses_sentiment(self):
        """AAVE writing with 4+ distinct markers → tier must be 'suppressed'."""
        wc = len(AAVE_TEXT.split())
        result = detect_features(AAVE_TEXT, word_count=wc)
        assert result.sentiment_tier == "suppressed", (
            f"AAVE text with multiple markers must suppress sentiment — "
            f"VADER/GoEmotions are biased against AAVE register. Got: {result.sentiment_tier}"
        )

    def test_aave_asset_label_not_deficit_framing(self):
        """Asset labels must not contain deficit words."""
        wc = len(AAVE_TEXT.split())
        result = detect_features(AAVE_TEXT, word_count=wc)
        deficit_words = ["error", "incorrect", "wrong", "deficient", "nonstandard", "mistake"]
        for label in result.asset_labels:
            label_lower = label.lower()
            assert not any(w in label_lower for w in deficit_words), (
                f"Asset label '{label}' contains deficit framing"
            )

    def test_standard_text_high_tier(self):
        """Standard academic writing should not trigger tier suppression."""
        wc = len(STANDARD_TEXT.split())
        result = detect_features(STANDARD_TEXT, word_count=wc)
        assert result.sentiment_tier == "high"

    def test_righteous_anger_not_suppressed(self):
        """
        #COMMUNITY_CULTURAL_WEALTH: Political urgency and righteous anger
        are engagement, not distress. VADER reads fury about injustice as
        'negative', but this text is 98 words of sophisticated critique.
        Must not be suppressed.
        """
        wc = len(RIGHTEOUS_ANGER_TEXT.split())
        result = detect_features(RIGHTEOUS_ANGER_TEXT, word_count=wc)
        assert result.sentiment_tier == "high", (
            f"Righteous anger about injustice must not suppress sentiment. "
            f"Got: {result.sentiment_tier}, triggers: {result.sentiment_triggers}"
        )


# ---------------------------------------------------------------------------
# detect_features — multilingual / ESL
# ---------------------------------------------------------------------------

class TestMultilingualFeatures:
    def test_translated_text_with_nonneutral_score_suppresses(self):
        """Translated text + non-neutral compound score → suppressed tier.

        Translation suppression fires only when compound_score is non-neutral
        (abs > 0.1) — a non-neutral score from translated text is suspicious
        because translation flattens affect markers.
        """
        wc = len(TRANSLATED_TEXT.split())
        result = detect_features(
            TRANSLATED_TEXT, word_count=wc,
            was_translated=True, compound_score=0.5,  # non-neutral
        )
        assert result.sentiment_tier == "suppressed"

    def test_translated_text_neutral_score_high_tier(self):
        """Translated text + neutral compound score → 'high' tier (no bias signal)."""
        wc = len(TRANSLATED_TEXT.split())
        result = detect_features(
            TRANSLATED_TEXT, word_count=wc,
            was_translated=True, compound_score=0.0,  # neutral
        )
        assert result.sentiment_tier == "high"

    def test_translated_text_has_multilingual_asset(self):
        """Translated text should surface a multilingual asset label."""
        wc = len(TRANSLATED_TEXT.split())
        result = detect_features(TRANSLATED_TEXT, word_count=wc, was_translated=True)
        assert any("multilingual" in label.lower() or "language" in label.lower()
                   for label in result.asset_labels), (
            f"Translated text should surface multilingual asset. Got: {result.asset_labels}"
        )

    def test_transcribed_text_caveats(self):
        """Oral transcriptions should caveat sentiment."""
        wc = len(TRANSLATED_TEXT.split())
        result = detect_features(TRANSLATED_TEXT, word_count=wc, was_transcribed=True)
        assert result.sentiment_tier in ("low", "suppressed")

    def test_multilingual_text_produces_asset_labels(self):
        """Code-meshing / multilingual writing should surface as an asset."""
        wc = len(MULTILINGUAL_TEXT.split())
        result = detect_features(MULTILINGUAL_TEXT, word_count=wc)
        assert len(result.asset_labels) > 0


# ---------------------------------------------------------------------------
# detect_features — baseline adjustments
# ---------------------------------------------------------------------------

class TestShortSubmissionTiers:
    """Two-tier threshold: hard suppress < 15 words; caveat between 15 and type threshold.

    Different assignment types have different expected lengths — a 25-word
    discussion reply is substantive; a 25-word essay is genuinely thin.
    #CRIP_TIME  #NEURODIVERSITY  #COMMUNITY_CULTURAL_WEALTH
    """

    def test_hard_suppress_below_floor(self):
        """< 15 words is always suppressed regardless of assignment type."""
        text = "Very short."
        result = detect_features(text, word_count=10)
        assert result.sentiment_tier == "suppressed"

    def test_caveat_in_default_zone(self):
        """15–60 words with default type → caveat (tier='low'), not suppress."""
        text = "x " * 30  # 30 words
        result = detect_features(text, word_count=30)
        assert result.sentiment_tier == "low", (
            "30-word default submission should be caveat, not suppress — "
            "a 30-word response is often substantive"
        )

    def test_discussion_post_30_words_is_high(self):
        """A 30-word discussion post is above the discussion threshold (25) — high tier."""
        text = "x " * 30  # 30 words — above discussion_post threshold of 25
        result = detect_features(text, word_count=30, assignment_type="discussion_post")
        assert result.sentiment_tier == "high", (
            "30-word discussion post is above the 25-word discussion threshold"
        )

    def test_discussion_post_18_words_is_caveat(self):
        """18 words with discussion_post type: above hard floor (15), below caveat (25) → low."""
        text = "x " * 18
        result = detect_features(text, word_count=18, assignment_type="discussion_post")
        assert result.sentiment_tier == "low"

    def test_essay_40_words_is_caveat(self):
        """40 words is above the hard floor but below essay caveat threshold (60) → low."""
        text = "x " * 40
        result = detect_features(text, word_count=40, assignment_type="essay")
        assert result.sentiment_tier == "low"

    def test_essay_70_words_is_high(self):
        """70 words with essay type is above caveat threshold (60) → high."""
        text = "x " * 70
        result = detect_features(text, word_count=70, assignment_type="essay")
        assert result.sentiment_tier == "high"

    def test_teacher_override_threshold(self):
        """short_word_threshold overrides type-based threshold."""
        text = "x " * 20
        # Teacher says anything over 10 words is fine
        result = detect_features(text, word_count=20, short_word_threshold=10)
        assert result.sentiment_tier == "high"

    def test_teacher_override_higher_than_default(self):
        """Teacher can set a higher threshold if their class writes longer."""
        text = "x " * 50
        result = detect_features(text, word_count=50, short_word_threshold=100)
        assert result.sentiment_tier == "low"

    def test_exit_ticket_at_floor(self):
        """Exit tickets are set at the hard floor — 15 words is caveat for exit_ticket."""
        # The exit_ticket caveat threshold is 15, same as hard floor.
        # 15 words: at the caveat threshold exactly → NOT in caveat zone (must be < threshold)
        # 14 words: below hard floor → suppress
        text = "x " * 14
        result = detect_features(text, word_count=14, assignment_type="exit_ticket")
        assert result.sentiment_tier == "suppressed"

    def test_exit_ticket_15_words_is_high(self):
        """Exit ticket caveat threshold = hard floor (15). At 15 words → high tier."""
        text = "x " * 15
        result = detect_features(text, word_count=15, assignment_type="exit_ticket")
        assert result.sentiment_tier == "high"

    def test_no_structural_feature_above_threshold(self):
        """No short_submission feature fires above the caveat threshold."""
        text = "x " * 70
        result = detect_features(text, word_count=70)
        struct_features = [f for f in result.features if f.name == "short_submission"]
        assert struct_features == []


class TestBaselineAdjustments:
    def test_baseline_does_not_crash(self):
        """Passing a FeatureBaseline should not raise."""
        baseline = FeatureBaseline(
            hedge_rate_median=2.0,
            hedge_rate_iqr=1.5,
            n_students=12,
        )
        wc = len(STANDARD_TEXT.split())
        result = detect_features(STANDARD_TEXT, word_count=wc, baseline=baseline)
        assert isinstance(result, LinguisticFeatureResult)

    def test_without_baseline_does_not_crash(self):
        wc = len(AAVE_TEXT.split())
        result = detect_features(AAVE_TEXT, word_count=wc, baseline=None)
        assert isinstance(result, LinguisticFeatureResult)


# ---------------------------------------------------------------------------
# detect_features — edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_very_short_text_suppressed(self):
        """4 words < 15-word hard suppress floor → suppressed."""
        result = detect_features(SHORT_TEXT, word_count=4)
        assert isinstance(result, LinguisticFeatureResult)
        assert result.sentiment_tier == "suppressed"

    def test_empty_text(self):
        """Empty text (0 words) is below hard suppress floor → suppressed."""
        result = detect_features("", word_count=0)
        assert result.sentiment_tier == "suppressed"

    def test_very_long_text_does_not_hang(self):
        long_text = STANDARD_TEXT * 20  # ~1600 words
        wc = len(long_text.split())
        result = detect_features(long_text, word_count=wc)
        assert isinstance(result, LinguisticFeatureResult)

    def test_llm_context_note_is_string(self):
        wc = len(AAVE_TEXT.split())
        result = detect_features(AAVE_TEXT, word_count=wc)
        assert isinstance(result.llm_context_note, str)

    def test_no_asset_labels_for_standard_text(self):
        """Plain academic text should produce no equity-related asset labels
        (it doesn't need them — the system surfaces assets when there's
        something to name, not as a default)."""
        wc = len(STANDARD_TEXT.split())
        result = detect_features(STANDARD_TEXT, word_count=wc)
        # Standard text may have academic_convention features but not AAVE/ESL assets
        aave_esl_labels = [
            l for l in result.asset_labels
            if "AAVE" in l or "multilingual" in l.lower() or "ESL" in l
        ]
        assert aave_esl_labels == []
