"""
cohort_calibration.py — unit tests.

Tests class-relative engagement baseline computation: distributions,
percentile ranking, cold-start Bayesian blending, EMA evolution,
and student percentile mapping.

Design principle validated here:
  All engagement interpretations are class-relative, not absolute.
  A student with high comma density in a class of everyone with high
  comma density is TYPICAL, not suspicious. Absolute thresholds penalize
  entire populations; class-relative ones surface genuine deviation.

Run with: python3 -m pytest tests/test_cohort_calibration.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from modules.cohort_calibration import (
    EDUCATION_LEVEL_PRIORS,
    SIGNAL_NAMES,
    CohortCalibrator,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_vector(**kwargs) -> dict:
    """Create a signal vector with defaults for all signals."""
    defaults = {
        "sentence_variance": 0.45,
        "starter_diversity": 0.72,
        "comma_density": 2.80,
        "avg_word_length": 4.28,
        "hp_confidence": 0.35,
        "authenticity": 0.30,
    }
    defaults.update(kwargs)
    return defaults


SMALL_CLASS = [
    make_vector(sentence_variance=0.30, comma_density=1.5),
    make_vector(sentence_variance=0.45, comma_density=2.8),
    make_vector(sentence_variance=0.60, comma_density=4.0),
    make_vector(sentence_variance=0.75, comma_density=5.5),
]

LARGER_CLASS = [make_vector(comma_density=float(i) * 0.5) for i in range(1, 21)]


# ---------------------------------------------------------------------------
# compute_class_distributions
# ---------------------------------------------------------------------------

class TestComputeClassDistributions:
    @pytest.fixture
    def calibrator(self):
        return CohortCalibrator()

    def test_empty_input_returns_empty_dict(self, calibrator):
        assert calibrator.compute_class_distributions([]) == {}

    def test_all_signal_names_computed(self, calibrator):
        vectors = [make_vector() for _ in range(5)]
        dists = calibrator.compute_class_distributions(vectors)
        for name in SIGNAL_NAMES:
            assert name in dists

    def test_stats_keys_present(self, calibrator):
        dists = calibrator.compute_class_distributions(SMALL_CLASS)
        for stats in dists.values():
            for key in ("mean", "median", "stdev", "p10", "p25", "p75", "p90", "iqr"):
                assert key in stats

    def test_mean_correct(self, calibrator):
        vectors = [make_vector(comma_density=2.0), make_vector(comma_density=4.0)]
        dists = calibrator.compute_class_distributions(vectors)
        assert dists["comma_density"]["mean"] == pytest.approx(3.0)

    def test_single_student_stdev_zero(self, calibrator):
        dists = calibrator.compute_class_distributions([make_vector()])
        assert dists["sentence_variance"]["stdev"] == pytest.approx(0.0)

    def test_missing_signal_skipped(self, calibrator):
        """Vectors with missing signals contribute to other signals but not the missing one."""
        v1 = {"sentence_variance": 0.45, "comma_density": 2.8,
              "starter_diversity": 0.7, "avg_word_length": 4.2,
              "hp_confidence": 0.3, "authenticity": 0.3}
        v2 = {"sentence_variance": 0.60, "comma_density": 3.5,
              "starter_diversity": 0.8, "avg_word_length": 4.5,
              "hp_confidence": 0.4, "authenticity": 0.4}
        # hp_confidence missing from v1 — only v2 contributes
        del v1["hp_confidence"]
        dists = calibrator.compute_class_distributions([v1, v2])
        assert dists["hp_confidence"]["mean"] == pytest.approx(0.4)
        assert dists["sentence_variance"]["mean"] == pytest.approx(0.525)

    def test_iqr_is_p75_minus_p25(self, calibrator):
        dists = calibrator.compute_class_distributions(SMALL_CLASS)
        sv = dists["sentence_variance"]
        assert sv["iqr"] == pytest.approx(sv["p75"] - sv["p25"], abs=0.001)


# ---------------------------------------------------------------------------
# get_percentile_rank
# ---------------------------------------------------------------------------

class TestGetPercentileRank:
    """
    #CRITICAL_PEDAGOGY: Engagement interpretations use asset-framing, not
    deficit-framing. 'Conversation opportunity' not 'low engagement'.
    """

    @pytest.fixture
    def calibrator(self):
        return CohortCalibrator()

    def baseline(self, p10=0.2, p25=0.4, p75=0.7):
        return {"p10": p10, "p25": p25, "p75": p75}

    def test_below_p10_is_conversation_opportunity(self, calibrator):
        result = calibrator.get_percentile_rank(0.1, self.baseline())
        assert result == "conversation_opportunity"

    def test_between_p10_and_p25_is_worth_monitoring(self, calibrator):
        result = calibrator.get_percentile_rank(0.3, self.baseline())
        assert result == "worth_monitoring"

    def test_between_p25_and_p75_is_typical(self, calibrator):
        result = calibrator.get_percentile_rank(0.55, self.baseline())
        assert result == "typical"

    def test_above_p75_is_strong_engagement(self, calibrator):
        result = calibrator.get_percentile_rank(0.85, self.baseline())
        assert result == "strong_engagement"

    def test_exactly_p25_is_typical(self, calibrator):
        result = calibrator.get_percentile_rank(0.4, self.baseline())
        assert result == "typical"

    def test_exactly_p75_is_typical(self, calibrator):
        result = calibrator.get_percentile_rank(0.7, self.baseline())
        assert result == "typical"

    def test_labels_are_engagement_framed_not_deficit(self, calibrator):
        """Labels must not use deficit framing."""
        labels = {
            calibrator.get_percentile_rank(v, self.baseline())
            for v in [0.05, 0.3, 0.55, 0.9]
        }
        for label in labels:
            assert "low" not in label
            assert "below" not in label
            assert "bad" not in label
            assert "poor" not in label


# ---------------------------------------------------------------------------
# cold_start_baseline
# ---------------------------------------------------------------------------

class TestColdStartBaseline:
    """Bayesian blending for first run: blend class mean with weak prior."""

    @pytest.fixture
    def calibrator(self):
        return CohortCalibrator()

    def test_large_class_prior_weight_is_10(self, calibrator):
        # With 25+ students, prior_weight = max(10, 25-25) = 10
        # effective = (25 * class_mean + 10 * prior) / 35
        class_mean = 0.5
        result = calibrator.cold_start_baseline(class_mean, n_students=25,
                                                 education_level="high_school",
                                                 signal_name="sentence_variance")
        prior = EDUCATION_LEVEL_PRIORS["high_school"]["sentence_variance"]
        expected = (25 * class_mean + 10 * prior) / 35
        assert result == pytest.approx(expected, abs=0.001)

    def test_small_class_prior_has_more_influence(self, calibrator):
        """With 5 students, prior weight=20, class data is 20% of effective."""
        result_5 = calibrator.cold_start_baseline(
            1.0, n_students=5, education_level="high_school",
            signal_name="sentence_variance"
        )
        result_25 = calibrator.cold_start_baseline(
            1.0, n_students=25, education_level="high_school",
            signal_name="sentence_variance"
        )
        # Smaller class → prior pulls result further from 1.0
        prior = EDUCATION_LEVEL_PRIORS["high_school"]["sentence_variance"]
        # result_5 should be closer to the prior than result_25
        assert abs(result_5 - prior) < abs(result_25 - prior)

    def test_unknown_education_level_uses_default(self, calibrator):
        # Unknown level → falls back to community_college
        result = calibrator.cold_start_baseline(
            0.5, n_students=10,
            education_level="nonexistent_level",
            signal_name="sentence_variance",
        )
        # Should return a valid float, not crash
        assert 0.0 <= result <= 1.5

    def test_returns_float(self, calibrator):
        result = calibrator.cold_start_baseline(0.5, n_students=15)
        assert isinstance(result, float)


# ---------------------------------------------------------------------------
# evolve_baseline
# ---------------------------------------------------------------------------

class TestEvolveBaseline:
    """EMA update: 30% new + 70% prior."""

    @pytest.fixture
    def calibrator(self):
        return CohortCalibrator()

    def test_standard_ema(self, calibrator):
        result = calibrator.evolve_baseline(new_class_mean=1.0, previous_baseline_mean=0.0)
        assert result == pytest.approx(0.3)

    def test_identical_values_unchanged(self, calibrator):
        result = calibrator.evolve_baseline(0.5, 0.5)
        assert result == pytest.approx(0.5)

    def test_custom_alpha(self, calibrator):
        result = calibrator.evolve_baseline(1.0, 0.0, alpha=0.5)
        assert result == pytest.approx(0.5)

    def test_new_observation_dominates_at_alpha_1(self, calibrator):
        result = calibrator.evolve_baseline(1.0, 0.0, alpha=1.0)
        assert result == pytest.approx(1.0)

    def test_result_is_between_old_and_new(self, calibrator):
        new, old = 0.8, 0.2
        result = calibrator.evolve_baseline(new, old)
        assert old <= result <= new


# ---------------------------------------------------------------------------
# compute_student_percentiles
# ---------------------------------------------------------------------------

class TestComputeStudentPercentiles:
    @pytest.fixture
    def calibrator(self):
        return CohortCalibrator()

    def test_returns_dict_of_interpretations(self, calibrator):
        distributions = calibrator.compute_class_distributions(SMALL_CLASS)
        student = make_vector(sentence_variance=0.45, comma_density=2.8)
        percentiles = calibrator.compute_student_percentiles(student, distributions)
        assert isinstance(percentiles, dict)

    def test_each_value_is_valid_interpretation(self, calibrator):
        valid = {"conversation_opportunity", "worth_monitoring", "typical", "strong_engagement"}
        distributions = calibrator.compute_class_distributions(LARGER_CLASS)
        student = make_vector()
        percentiles = calibrator.compute_student_percentiles(student, distributions)
        for val in percentiles.values():
            assert val in valid

    def test_signals_not_in_distributions_excluded(self, calibrator):
        """Only signals with distributions get a percentile."""
        # Empty distributions → no percentiles
        percentiles = calibrator.compute_student_percentiles(make_vector(), {})
        assert percentiles == {}

    def test_highest_comma_density_is_strong_engagement(self, calibrator):
        distributions = calibrator.compute_class_distributions(SMALL_CLASS)
        # comma_density=5.5 is the max in SMALL_CLASS → strong_engagement
        top_student = make_vector(comma_density=5.5)
        percentiles = calibrator.compute_student_percentiles(top_student, distributions)
        assert percentiles.get("comma_density") == "strong_engagement"
