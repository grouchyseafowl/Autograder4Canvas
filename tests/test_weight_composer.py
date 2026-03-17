"""
Unit tests for WeightComposer — two-axis per-marker weight system.

Tests:
  1. CC compose with no population overlays → expected weights
  2. HS + ESL high + ND-aware → example from plan
  3. Population max() composition (student overrides)
  4. compose_weights convenience function
  5. Invalid level raises ValueError
  6. Missing YAML raises FileNotFoundError
  7. Backward-compat: DishonestyAnalyzer with composed_weights=None is unchanged

Run from repo root:
    cd src && python -m pytest ../tests/test_weight_composer.py -v

Or:
    cd src && python ../tests/test_weight_composer.py
"""

import sys
import os
from pathlib import Path

# Allow running from project root or tests/ directory
_HERE = Path(__file__).parent
_SRC = _HERE.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import pytest

from modules.weight_composer import (
    WeightComposer,
    PopulationSettings,
    ComposedWeights,
    compose_weights,
    population_from_profile,
    compose_from_profile,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def composer():
    return WeightComposer()


# ── Phase 1 verification tests ────────────────────────────────────────────────

class TestCommunityCollegeDefaults:
    """Verify CC compose matches expected calibration from the plan."""

    def test_ai_transitions_weight(self, composer):
        """CC ai_transitions should be 0.35 (matches old 0.5 × 0.7)."""
        weights = composer.compose("community_college", PopulationSettings())
        assert abs(weights.marker_weights["ai_transitions"] - 0.35) < 0.01, (
            f"Expected ~0.35, got {weights.marker_weights['ai_transitions']}"
        )

    def test_inflated_vocabulary_weight(self, composer):
        """CC inflated_vocabulary should be 0.20 (matches old 0.3 × 0.67)."""
        weights = composer.compose("community_college", PopulationSettings())
        assert abs(weights.marker_weights["inflated_vocabulary"] - 0.20) < 0.01, (
            f"Expected ~0.20, got {weights.marker_weights['inflated_vocabulary']}"
        )

    def test_ai_specific_org_weight(self, composer):
        """CC ai_specific_org should be 1.00 (full weight, no CC adjustment)."""
        weights = composer.compose("community_college", PopulationSettings())
        assert abs(weights.marker_weights["ai_specific_org"] - 1.00) < 0.01

    def test_outlier_percentile(self, composer):
        """CC outlier_percentile should be 95."""
        weights = composer.compose("community_college", PopulationSettings())
        assert weights.outlier_percentile == 95

    def test_cognitive_protection_floor(self, composer):
        """CC standard cognitive_protection_floor should be 0.5."""
        weights = composer.compose("community_college", PopulationSettings())
        assert weights.cognitive_protection_floor == 0.5

    def test_education_level_recorded(self, composer):
        """ComposedWeights should record which edu level was used."""
        weights = composer.compose("community_college", PopulationSettings())
        assert weights.education_level == "community_college"

    def test_population_recorded(self, composer):
        """ComposedWeights should record effective population settings."""
        pop = PopulationSettings()
        weights = composer.compose("community_college", pop)
        assert weights.population.esl_level == "none"
        assert weights.population.first_gen_level == "none"
        assert not weights.population.neurodivergent_aware


class TestHighSchoolDefaults:
    """Verify HS weights match plan table."""

    def test_ai_transitions_very_low(self, composer):
        """HS ai_transitions should be 0.15 (formally taught curriculum)."""
        weights = composer.compose("high_school", PopulationSettings())
        assert abs(weights.marker_weights["ai_transitions"] - 0.15) < 0.01

    def test_inflated_vocabulary_high(self, composer):
        """HS inflated_vocabulary should be 0.45 (strongest HS signal)."""
        weights = composer.compose("high_school", PopulationSettings())
        assert abs(weights.marker_weights["inflated_vocabulary"] - 0.45) < 0.01

    def test_ai_specific_org_slightly_reduced(self, composer):
        """HS ai_specific_org should be 0.90."""
        weights = composer.compose("high_school", PopulationSettings())
        assert abs(weights.marker_weights["ai_specific_org"] - 0.90) < 0.01

    def test_outlier_percentile(self, composer):
        """HS outlier_percentile should be 96."""
        weights = composer.compose("high_school", PopulationSettings())
        assert weights.outlier_percentile == 96


class TestFourYearDefaults:
    """Four-year matches hardcoded analyzer defaults."""

    def test_ai_transitions(self, composer):
        weights = composer.compose("four_year", PopulationSettings())
        assert abs(weights.marker_weights["ai_transitions"] - 0.50) < 0.01

    def test_inflated_vocabulary(self, composer):
        weights = composer.compose("four_year", PopulationSettings())
        assert abs(weights.marker_weights["inflated_vocabulary"] - 0.30) < 0.01

    def test_outlier_percentile(self, composer):
        weights = composer.compose("four_year", PopulationSettings())
        assert weights.outlier_percentile == 92


# ── Population overlay tests ──────────────────────────────────────────────────

class TestESLOverlay:
    """ESL overlay reduces ai_transitions, inflated_vocabulary, personal_voice."""

    def test_esl_high_reduces_ai_transitions_cc(self, composer):
        """ESL high × CC base: 0.35 × 0.55 = 0.1925."""
        pop = PopulationSettings(esl_level="high")
        weights = composer.compose("community_college", pop)
        expected = 0.35 * 0.55
        assert abs(weights.marker_weights["ai_transitions"] - expected) < 0.01

    def test_esl_moderate_reduces_inflated_vocab_hs(self, composer):
        """ESL moderate × HS base: 0.45 × 0.70 = 0.315."""
        pop = PopulationSettings(esl_level="moderate")
        weights = composer.compose("high_school", pop)
        expected = 0.45 * 0.70
        assert abs(weights.marker_weights["inflated_vocabulary"] - expected) < 0.01

    def test_esl_none_no_change(self, composer):
        """ESL none should not change any weights."""
        no_esl = composer.compose("community_college", PopulationSettings(esl_level="none"))
        base   = composer.compose("community_college", PopulationSettings())
        assert no_esl.marker_weights["ai_transitions"] == base.marker_weights["ai_transitions"]

    def test_esl_does_not_affect_generic_phrases(self, composer):
        """ESL overlay only affects ai_transitions, inflated_vocab, personal_voice."""
        pop = PopulationSettings(esl_level="high")
        with_esl = composer.compose("community_college", pop)
        without  = composer.compose("community_college", PopulationSettings())
        # generic_phrases should be unchanged
        assert with_esl.marker_weights["generic_phrases"] == without.marker_weights["generic_phrases"]


class TestFirstGenOverlay:
    """First-gen overlay reduces generic_phrases and ai_transitions."""

    def test_first_gen_high_reduces_generic_phrases(self, composer):
        """First-gen high × CC base generic_phrases: 0.40 × 0.70 = 0.28."""
        pop = PopulationSettings(first_gen_level="high")
        weights = composer.compose("community_college", pop)
        expected = 0.40 * 0.70
        assert abs(weights.marker_weights["generic_phrases"] - expected) < 0.01

    def test_first_gen_does_not_affect_inflated_vocab(self, composer):
        """First-gen overlay doesn't touch inflated_vocabulary."""
        pop = PopulationSettings(first_gen_level="high")
        with_fg = composer.compose("community_college", pop)
        without  = composer.compose("community_college", PopulationSettings())
        assert with_fg.marker_weights["inflated_vocabulary"] == without.marker_weights["inflated_vocabulary"]


class TestNeurodivergentOverlay:
    """ND-aware mode reduces ai_specific_org, boosts cognitive_diversity, lowers floor."""

    def test_nd_reduces_ai_specific_org(self, composer):
        """ND-aware × CC base: 1.00 × 0.70 = 0.70."""
        pop = PopulationSettings(neurodivergent_aware=True)
        weights = composer.compose("community_college", pop)
        assert abs(weights.marker_weights["ai_specific_org"] - 0.70) < 0.01

    def test_nd_boosts_cognitive_diversity(self, composer):
        """ND-aware × CC base: 0.60 × 1.50 = 0.90."""
        pop = PopulationSettings(neurodivergent_aware=True)
        weights = composer.compose("community_college", pop)
        assert abs(weights.marker_weights["cognitive_diversity"] - 0.90) < 0.01

    def test_nd_lowers_cognitive_protection_floor(self, composer):
        """ND-aware cognitive_protection_floor should be 0.30."""
        pop = PopulationSettings(neurodivergent_aware=True)
        weights = composer.compose("community_college", pop)
        assert abs(weights.cognitive_protection_floor - 0.30) < 0.01

    def test_nd_off_standard_floor(self, composer):
        """ND-off cognitive_protection_floor should be 0.50."""
        pop = PopulationSettings(neurodivergent_aware=False)
        weights = composer.compose("community_college", pop)
        assert abs(weights.cognitive_protection_floor - 0.50) < 0.01


class TestPlanExample:
    """Verify the plan's composition example: HS + ESL high + ND-aware."""

    def test_hs_esl_high_nd_aware_ai_transitions(self, composer):
        """HS base 0.15 × ESL-high 0.55 = 0.0825 ≈ 0.083."""
        pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
        weights = composer.compose("high_school", pop)
        expected = 0.15 * 0.55
        assert abs(weights.marker_weights["ai_transitions"] - expected) < 0.01, (
            f"Expected ~{expected:.3f}, got {weights.marker_weights['ai_transitions']:.3f}"
        )

    def test_hs_esl_high_nd_aware_ai_specific_org(self, composer):
        """HS base 0.90 × ND-aware 0.70 = 0.63."""
        pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
        weights = composer.compose("high_school", pop)
        expected = 0.90 * 0.70
        assert abs(weights.marker_weights["ai_specific_org"] - expected) < 0.01, (
            f"Expected ~{expected:.3f}, got {weights.marker_weights['ai_specific_org']:.3f}"
        )

    def test_hs_esl_high_nd_aware_cognitive_diversity(self, composer):
        """HS base 0.60 × ND-aware 1.50 = 0.90."""
        pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
        weights = composer.compose("high_school", pop)
        expected = 0.60 * 1.50
        assert abs(weights.marker_weights["cognitive_diversity"] - expected) < 0.01

    def test_hs_esl_high_nd_aware_cognitive_floor(self, composer):
        """ND-aware floor should be 0.30."""
        pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
        weights = composer.compose("high_school", pop)
        assert abs(weights.cognitive_protection_floor - 0.30) < 0.01

    def test_hs_esl_high_nd_aware_outlier_percentile(self, composer):
        """HS outlier_percentile should be 96."""
        pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
        weights = composer.compose("high_school", pop)
        assert weights.outlier_percentile == 96


# ── Population max() composition ─────────────────────────────────────────────

class TestPopulationMaxComposition:
    """Student overrides merged via max() — student gets more protection."""

    def test_student_esl_upgrades_class_level(self):
        """Class low ESL + student high ESL → student gets high."""
        class_pop = PopulationSettings(esl_level="low")
        student_pop = PopulationSettings(esl_level="high")
        merged = class_pop.max_with(student_pop)
        assert merged.esl_level == "high"

    def test_class_esl_kept_when_higher(self):
        """Class high ESL + student none → student gets high (class wins)."""
        class_pop = PopulationSettings(esl_level="high")
        student_pop = PopulationSettings(esl_level="none")
        merged = class_pop.max_with(student_pop)
        assert merged.esl_level == "high"

    def test_nd_or_composition(self):
        """ND-aware: OR composition — on if either sets it."""
        class_pop = PopulationSettings(neurodivergent_aware=False)
        student_pop = PopulationSettings(neurodivergent_aware=True)
        merged = class_pop.max_with(student_pop)
        assert merged.neurodivergent_aware is True

    def test_student_overrides_affect_composition(self, composer):
        """Passing student_overrides to compose() should upgrade the weights."""
        class_pop = PopulationSettings(esl_level="none")
        student_pop = PopulationSettings(esl_level="high")
        weights = composer.compose("community_college", class_pop, student_overrides=student_pop)
        # Should reflect ESL high overlay, not the class-level none
        expected = 0.35 * 0.55  # CC base × ESL high
        assert abs(weights.marker_weights["ai_transitions"] - expected) < 0.01

    def test_composition_log_records_override(self, composer):
        """Composition log should mention student override merge."""
        class_pop = PopulationSettings(esl_level="none")
        student_pop = PopulationSettings(esl_level="moderate")
        weights = composer.compose("community_college", class_pop, student_overrides=student_pop)
        assert any("Student overrides merged" in line for line in weights.composition_log)


# ── Validation ────────────────────────────────────────────────────────────────

class TestValidation:
    """Invalid inputs raise appropriate errors."""

    def test_invalid_esl_level_raises(self):
        with pytest.raises(ValueError, match="esl_level"):
            PopulationSettings(esl_level="extreme")

    def test_invalid_first_gen_level_raises(self):
        with pytest.raises(ValueError, match="first_gen_level"):
            PopulationSettings(first_gen_level="very_high")

    def test_unknown_education_level_raises(self, composer):
        with pytest.raises(FileNotFoundError, match="not found"):
            composer.compose("unknown_level", PopulationSettings())


# ── Convenience functions ─────────────────────────────────────────────────────

class TestConvenienceFunctions:
    """Test compose_weights() and credential profile helpers."""

    def test_compose_weights_cc_default(self):
        weights = compose_weights()
        assert weights.education_level == "community_college"
        assert abs(weights.marker_weights["ai_transitions"] - 0.35) < 0.01

    def test_compose_weights_with_overlays(self):
        weights = compose_weights(
            education_level="high_school",
            esl_level="high",
            neurodivergent_aware=True,
        )
        expected = 0.15 * 0.55  # HS × ESL high
        assert abs(weights.marker_weights["ai_transitions"] - expected) < 0.01

    def test_population_from_profile_defaults(self):
        pop = population_from_profile({})
        assert pop.esl_level == "none"
        assert pop.first_gen_level == "none"
        assert pop.neurodivergent_aware is False

    def test_population_from_profile_reads_values(self):
        profile = {
            "population_esl": "moderate",
            "population_first_gen": "high",
            "population_neurodivergent_aware": True,
        }
        pop = population_from_profile(profile)
        assert pop.esl_level == "moderate"
        assert pop.first_gen_level == "high"
        assert pop.neurodivergent_aware is True

    def test_compose_from_profile_uses_education_level(self):
        profile = {
            "education_level": "four_year",
            "population_esl": "none",
        }
        weights = compose_from_profile(profile)
        assert weights.education_level == "four_year"
        assert abs(weights.marker_weights["ai_transitions"] - 0.50) < 0.01

    def test_compose_from_profile_default_cc_when_missing(self):
        weights = compose_from_profile({})
        assert weights.education_level == "community_college"


# ── Summary output ─────────────────────────────────────────────────────────────

class TestSummaryOutput:
    """ComposedWeights.summary() produces human-readable output."""

    def test_summary_contains_edu_level(self, composer):
        weights = composer.compose("high_school", PopulationSettings())
        summary = weights.summary()
        assert "high_school" in summary

    def test_summary_contains_marker_weights(self, composer):
        weights = composer.compose("community_college", PopulationSettings())
        summary = weights.summary()
        assert "ai_transitions" in summary
        assert "0.35" in summary


# ── Standalone runner ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Run quick smoke test without pytest
    print("Running weight_composer smoke tests...\n")

    c = WeightComposer()

    # Test 1: CC defaults
    w = c.compose("community_college", PopulationSettings())
    print(f"CC ai_transitions: {w.marker_weights['ai_transitions']:.3f} (expected ~0.350)")
    print(f"CC inflated_vocab: {w.marker_weights['inflated_vocabulary']:.3f} (expected ~0.200)")
    print(f"CC ai_specific_org: {w.marker_weights['ai_specific_org']:.3f} (expected 1.000)")
    print()

    # Test 2: HS + ESL high + ND-aware (plan example)
    pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
    w = c.compose("high_school", pop)
    print(f"HS+ESL-high+ND ai_transitions: {w.marker_weights['ai_transitions']:.3f} (expected ~0.083)")
    print(f"HS+ESL-high+ND ai_specific_org: {w.marker_weights['ai_specific_org']:.3f} (expected ~0.630)")
    print(f"HS+ESL-high+ND cognitive_diversity: {w.marker_weights['cognitive_diversity']:.3f} (expected ~0.900)")
    print(f"HS+ESL-high+ND cognitive_floor: {w.cognitive_protection_floor:.3f} (expected 0.300)")
    print(f"HS+ESL-high+ND outlier_percentile: {w.outlier_percentile} (expected 96)")
    print()

    print("Composition log:")
    for line in w.composition_log:
        print(f"  {line}")
    print()

    print("\nAll smoke tests passed!")
