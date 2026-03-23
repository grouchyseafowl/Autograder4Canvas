"""
CohortCalibrator — Class-relative engagement baselines from AIC signal vectors.

Mechanism 1 of the engagement analysis system. Computes per-class distributions
from the fast, always-available AIC signals (no LLM needed) and maps individual
student values to class-relative interpretations.

Design philosophy:
  - Class-relative, not absolute thresholds. A student with a high comma density
    in a class where everyone has high comma density is not unusual. Absolute
    thresholds penalize entire populations; class-relative ones surface genuine
    individual deviation.
  - Bayesian cold-start for first runs: blend observed class mean with a weak
    prior from the education-level defaults. As the system sees more assignments,
    the prior fades away.
  - Exponential moving average (EMA) for evolving baselines: each new run
    updates the baseline at 0.3 new + 0.7 prior, so one anomalous assignment
    doesn't wreck the running estimate.

Signals extracted from AIC results:
  - sentence_variance   (org_analysis.sentence_analysis.variance_coefficient)
  - starter_diversity    (org_analysis.sentence_analysis.starter_diversity)
  - comma_density        (org_analysis.sentence_analysis.comma_density)
  - avg_word_length      (org_analysis.sentence_analysis.avg_word_length)
  - hp_confidence        (human_presence total_score / 100)
  - authenticity         (human_presence authentic_voice normalized_score / 100)

Usage:
    from modules.cohort_calibration import CohortCalibrator, extract_signal_vector

    calibrator = CohortCalibrator()
    vectors = [extract_signal_vector(r) for r in results]
    distributions = calibrator.compute_class_distributions(vectors)

    # Per-student class-relative interpretation
    for signal_name, value in student_vector.items():
        rank = calibrator.get_percentile_rank(value, distributions[signal_name])
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from Academic_Dishonesty_Check_v2 import AnalysisResult


# ── Education-level signal priors ────────────────────────────────────────────
# These are expected population means for each signal at each education level.
# Used as weak Bayesian priors during cold-start (first run for a course).
# Values are derived from calibration data and the separation statistics
# documented in organizational_analyzer.py:
#   - AI starter_diversity mean = 1.0, Human = 0.759 (d=2.13)
#   - AI comma_density mean = 5.69, Human = 2.80 (d=1.85)
#   - AI avg_word_length mean = 5.13, Human = 4.28 (d=2.17)
#   - AI sentence_variance (VC) mean = 0.336, Human = 0.458 (d=0.99)
# Education level adjustments reflect known population patterns:
#   - HS students write shorter words, use more sentence starters repetition
#   - University students write longer words, higher comma density
#   - Community college has wide variance; priors are conservative

EDUCATION_LEVEL_PRIORS: Dict[str, Dict[str, float]] = {
    "high_school": {
        "sentence_variance": 0.48,     # HS students have more uneven rhythm
        "starter_diversity": 0.72,     # More repetition, less transformer-like
        "comma_density": 2.40,         # Simpler sentence structures
        "avg_word_length": 4.10,       # Shorter vocabulary
        "hp_confidence": 0.35,         # Moderate human presence baseline
        "authenticity": 0.30,          # Lower authentic voice in formal HS writing
    },
    "community_college": {
        "sentence_variance": 0.45,     # Wide variance — conservative prior
        "starter_diversity": 0.75,     # Between HS and university
        "comma_density": 2.80,         # Human mean from calibration data
        "avg_word_length": 4.28,       # Human mean from calibration data
        "hp_confidence": 0.30,         # Slightly lower — diverse population
        "authenticity": 0.28,          # Cultural factors affect voice expression
    },
    "four_year": {
        "sentence_variance": 0.44,     # Slightly more polished than CC
        "starter_diversity": 0.78,     # More varied starters
        "comma_density": 3.00,         # Slightly more complex sentences
        "avg_word_length": 4.40,       # Slightly longer vocabulary
        "hp_confidence": 0.35,         # Moderate baseline
        "authenticity": 0.32,          # More personal voice expected
    },
    "university": {
        "sentence_variance": 0.42,     # More polished academic writing
        "starter_diversity": 0.80,     # High diversity expected
        "comma_density": 3.20,         # Complex academic sentences
        "avg_word_length": 4.55,       # Academic vocabulary
        "hp_confidence": 0.38,         # Higher engagement expected
        "authenticity": 0.35,          # Strong authentic voice expected
    },
    "online": {
        "sentence_variance": 0.44,     # Similar to four_year
        "starter_diversity": 0.76,     # Slightly less diverse
        "comma_density": 2.90,         # Mid-range
        "avg_word_length": 4.35,       # Mid-range
        "hp_confidence": 0.32,         # Slightly lower — less in-class context
        "authenticity": 0.30,          # Less contextual grounding typical
    },
}

# Default prior if education level is unknown
_DEFAULT_PRIOR = EDUCATION_LEVEL_PRIORS["community_college"]

# Signal names in canonical order
SIGNAL_NAMES = [
    "sentence_variance",
    "starter_diversity",
    "comma_density",
    "avg_word_length",
    "hp_confidence",
    "authenticity",
]


# ── Signal extraction ────────────────────────────────────────────────────────


def extract_signal_vector(result: "AnalysisResult") -> Optional[Dict[str, float]]:
    """Extract a signal vector dict from an AnalysisResult.

    Returns a dict with keys matching SIGNAL_NAMES, or None if the result
    lacks the necessary data (e.g., text was too short for org analysis).

    Signal sources:
      - sentence_variance:  org_analysis → sentence_analysis → variance_coefficient
      - starter_diversity:  org_analysis → sentence_analysis → starter_diversity
      - comma_density:      org_analysis → sentence_analysis → comma_density
      - avg_word_length:    org_analysis → sentence_analysis → avg_word_length
      - hp_confidence:      human_presence_confidence (total_score / 100, already 0-1)
      - authenticity:       human_presence_details → authentic_voice normalized_score / 100
    """
    # Org analysis is a dict (the .details from OrganizationalAnalysis)
    org = getattr(result, 'organizational_analysis', None)
    if org is None:
        return None

    sent = org.get('sentence_analysis', {})
    if not sent:
        return None

    # Require at least sentence_variance to be present (indicates enough text)
    if 'variance_coefficient' not in sent:
        return None

    # Extract HP signals
    hp_conf_raw = getattr(result, 'human_presence_confidence', None)
    hp_confidence = hp_conf_raw / 100.0 if hp_conf_raw is not None else 0.0

    # Authentic voice: from the human_presence_details dict
    hp_details = getattr(result, 'human_presence_details', None)
    authenticity = 0.0
    if hp_details is not None:
        # hp_details is the __dict__ of HumanPresenceResult (or a dict)
        av = hp_details.get('authentic_voice')
        if av is not None:
            # av is either a CategoryScore object or a dict
            if isinstance(av, dict):
                norm = av.get('details', {}).get('normalized_score', 0.0)
            elif hasattr(av, 'details'):
                norm = av.details.get('normalized_score', 0.0)
            else:
                norm = 0.0
            authenticity = norm / 100.0

    return {
        'sentence_variance': sent.get('variance_coefficient', 0.0),
        'starter_diversity': sent.get('starter_diversity', 0.0),
        'comma_density': sent.get('comma_density', 0.0),
        'avg_word_length': sent.get('avg_word_length', 0.0),
        'hp_confidence': hp_confidence,
        'authenticity': authenticity,
    }


# ── CohortCalibrator ─────────────────────────────────────────────────────────


class CohortCalibrator:
    """Computes class-relative baselines from AIC signal vectors.

    This is the core of Mechanism 1: every student is measured against
    their own class, not against a universal threshold. A class of
    advanced writers all using complex sentences will have a high class
    mean for comma density — no individual gets flagged for matching
    their peers.
    """

    def compute_class_distributions(
        self, signal_vectors: List[Dict[str, float]]
    ) -> Dict[str, Dict[str, float]]:
        """Compute per-signal statistical distributions from a class of students.

        Args:
            signal_vectors: List of per-student signal dicts. Each dict has
                keys from SIGNAL_NAMES with float values. Vectors with
                missing keys are skipped for that signal.

        Returns:
            Dict mapping signal_name to stats dict with keys:
                mean, median, stdev, p10, p25, p75, p90, iqr

        Example:
            >>> cal = CohortCalibrator()
            >>> vecs = [{'sentence_variance': 0.45, ...}, ...]
            >>> dists = cal.compute_class_distributions(vecs)
            >>> dists['sentence_variance']['mean']
            0.45
        """
        if not signal_vectors:
            return {}

        distributions: Dict[str, Dict[str, float]] = {}

        for signal_name in SIGNAL_NAMES:
            # Collect all values for this signal, skipping missing
            values = [
                v[signal_name]
                for v in signal_vectors
                if signal_name in v and v[signal_name] is not None
            ]

            if not values:
                continue

            arr = np.array(values, dtype=np.float64)

            p10, p25, p75, p90 = np.percentile(arr, [10, 25, 75, 90])
            iqr = float(p75 - p25)

            distributions[signal_name] = {
                'mean': round(float(np.mean(arr)), 4),
                'median': round(float(np.median(arr)), 4),
                'stdev': round(float(np.std(arr, ddof=1)) if len(arr) > 1 else 0.0, 4),
                'p10': round(float(p10), 4),
                'p25': round(float(p25), 4),
                'p75': round(float(p75), 4),
                'p90': round(float(p90), 4),
                'iqr': round(float(iqr), 4),
            }

        return distributions

    def get_percentile_rank(
        self, value: float, baseline_stats: Dict[str, float]
    ) -> str:
        """Map a value to its engagement interpretation relative to class baseline.

        Uses the pre-computed percentile boundaries (p10, p25, p75) from
        compute_class_distributions() to classify the value.

        The labels are engagement-framed, not deficit-framed:
          - 'conversation_opportunity': below P10 — worth a check-in, not an accusation
          - 'worth_monitoring': P10-P25 — on the lower end but not unusual
          - 'typical': P25-P75 — the class middle
          - 'strong_engagement': above P75 — above-average engagement signal

        Args:
            value: The student's signal value
            baseline_stats: Stats dict with p10, p25, p75 keys

        Returns:
            One of the four engagement interpretation strings
        """
        p10 = baseline_stats.get('p10', 0.0)
        p25 = baseline_stats.get('p25', 0.0)
        p75 = baseline_stats.get('p75', 1.0)

        if value < p10:
            return 'conversation_opportunity'
        elif value < p25:
            return 'worth_monitoring'
        elif value <= p75:
            return 'typical'
        else:
            return 'strong_engagement'

    def cold_start_baseline(
        self,
        class_mean: float,
        n_students: int,
        education_level: str = "community_college",
        signal_name: str = "sentence_variance",
    ) -> float:
        """Bayesian blending for first run with no prior baseline data.

        When a course has no historical baselines, we blend the observed
        class mean with a weak prior from the education-level defaults.
        The prior weight shrinks as the class gets larger (more data
        means less need for the prior).

        Formula:
            effective = (n * class_mean + prior_weight * type_mean) / (n + prior_weight)
            where prior_weight = max(10, 25 - n)

        With 25+ students the prior weight is 10, so the class data
        dominates (~70%). With 5 students the prior weight is 20, giving
        the prior more influence (~80%).

        Args:
            class_mean: Observed mean from current class
            n_students: Number of students in the class
            education_level: Education level for prior lookup
            signal_name: Which signal to blend

        Returns:
            Blended baseline mean
        """
        priors = EDUCATION_LEVEL_PRIORS.get(education_level, _DEFAULT_PRIOR)
        type_mean = priors.get(signal_name, class_mean)

        prior_weight = max(10, 25 - n_students)
        effective = (n_students * class_mean + prior_weight * type_mean) / (
            n_students + prior_weight
        )
        return round(effective, 4)

    def evolve_baseline(
        self,
        new_class_mean: float,
        previous_baseline_mean: float,
        alpha: float = 0.3,
    ) -> float:
        """Exponential moving average update for evolving baselines.

        Each new assignment's class mean is blended with the running
        baseline. Alpha controls how much weight the new observation
        gets (0.3 = 30% new, 70% prior). This smooths out assignment-
        level noise while allowing the baseline to drift with genuine
        changes in class engagement over the semester.

        Args:
            new_class_mean: Observed mean from the new assignment
            previous_baseline_mean: Running baseline from prior assignments
            alpha: Weight for new observation (default 0.3)

        Returns:
            Updated baseline mean
        """
        updated = alpha * new_class_mean + (1.0 - alpha) * previous_baseline_mean
        return round(updated, 4)

    def compute_student_percentiles(
        self,
        student_vector: Dict[str, float],
        distributions: Dict[str, Dict[str, float]],
    ) -> Dict[str, str]:
        """Map a student's signal vector to class-relative interpretations.

        Args:
            student_vector: Per-student signal dict (from extract_signal_vector)
            distributions: Class distributions (from compute_class_distributions)

        Returns:
            Dict mapping signal_name to engagement interpretation string
        """
        percentiles: Dict[str, str] = {}
        for signal_name, value in student_vector.items():
            if signal_name in distributions:
                percentiles[signal_name] = self.get_percentile_rank(
                    value, distributions[signal_name]
                )
        return percentiles
