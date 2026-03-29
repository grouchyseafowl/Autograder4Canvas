"""
Trajectory Context — unit test suite.

Tests the per-student and class-wide longitudinal trajectory builders.
Pure unit tests: no LLM, no database, no MLX. All store interactions are faked.

Run with: python -m pytest tests/test_trajectory_context.py -v

Test areas (12 sections, ~70 tests):
  - Equity language compliance: label vocabulary, deficit-word blacklist,
    register neutrality (#CRIP_TIME, #ETHNIC_STUDIES, #DISABILITY_STUDIES)
  - 10-signal pattern break: all single signals tested in isolation (must NOT
    trigger), 2+ combination (must trigger), zero-signal baseline
  - Signal 6 suppression: #COMMUNITY_CULTURAL_WEALTH (UWR + linguistic assets)
  - Signals 8-10: personal connections vanished, readings disappeared,
    formulaic shift (fires on new, silent on pre-existing)
  - Smart word count description: inflection detection (was-increasing-then-
    collapsed, oscillating burnout), steady, too-few-data, empty
  - Submission time analysis: always-late-night NOT flagged, variable schedule
    NOT flagged, daytime→2AM IS flagged, insufficient data
  - Prior count cases: 0 (empty), 1 (comparison caveat), 2+ (pattern section),
    >3 (summary), attachment submissions, translated #LANGUAGE_JUSTICE
  - Class-wide trajectory: engagement/exhaustion/themes/arc formatters,
    structural framing note, no-individual-names guarantee
  - Integration: output shape, pattern break rendering, store failure graceful
  - Equity regressions: ESL student, neurodivergent output, working student
"""

import os
import sys

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from insights.trajectory_context import (
    _classify_word_count_trend,
    _analyze_submission_time,
    _detect_pattern_break,
    _describe_word_count_pattern,
    _parse_hour,
    build_trajectory_context,
)
from insights.class_trajectory_context import (
    _ARC_LABEL_MAP,
    _classify_word_count_trend as class_classify_trend,
    _format_engagement_line,
    _format_exhaustion_line,
    _format_themes_line,
    _format_arc_line,
    _oxford_join,
    build_class_trajectory_context,
)
from insights.models import (
    StudentArc,
    ThemeEvolution,
    WeekMetric,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts(hour: int, minute: int = 0, day: int = 15) -> str:
    """Build an ISO 8601 timestamp at a given hour on 2026-03-{day}."""
    dt = datetime(2026, 3, day, hour, minute, tzinfo=timezone.utc)
    return dt.isoformat()


def _make_prior_record(
    word_count: int = 300,
    emotional_register: str = "reflective",
    wellbeing_axis: str = "NONE",
    unknown_word_rate: float = 1.0,
    linguistic_assets: Optional[List[str]] = None,
    theme_tags: Optional[List[str]] = None,
    submitted_at: str = "",
    concerns: Optional[list] = None,
    engagement_depth: Optional[str] = None,
    personal_connections: Optional[List[str]] = None,
    readings_referenced: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a fake coding_record dict matching what InsightsStore returns."""
    rec: Dict[str, Any] = {
        "word_count": word_count,
        "emotional_register": emotional_register,
        "wellbeing_axis": wellbeing_axis,
        "unknown_word_rate": unknown_word_rate,
        "linguistic_assets": linguistic_assets or [],
        "theme_tags": theme_tags or ["identity", "power"],
        "submitted_at": submitted_at,
        "concerns": concerns or [],
    }
    if engagement_depth is not None:
        rec["engagement_signals"] = {"engagement_depth": engagement_depth}
    if personal_connections is not None:
        rec["personal_connections"] = personal_connections
    if readings_referenced is not None:
        rec["readings_referenced"] = readings_referenced
    return rec


class FakeStore:
    """Mimics InsightsStore.get_student_history() for testing."""

    def __init__(self, history: List[Dict[str, Any]]):
        self._history = history

    def get_student_history(
        self, student_id: str, course_id: str, *, exclude_run_id: str = ""
    ) -> List[Dict]:
        return self._history


def _wrap_history_entry(
    coding_record: Dict[str, Any],
    assignment_name: str = "Essay 3",
    started_at: str = "2026-03-10T08:00:00+00:00",
) -> Dict[str, Any]:
    """Wrap a coding_record into the dict shape get_student_history returns."""
    return {
        "run_id": "run_test",
        "student_name": "Test Student",
        "coding_record": coding_record,
        "assignment_name": assignment_name,
        "started_at": started_at,
    }


# ===================================================================
# SECTION 1: Equity Language Compliance
# ===================================================================

class TestEquityLanguage:
    """No output should contain deficit-framing language."""

    # --- Per-student trajectory labels ---

    def test_word_count_trend_never_says_declining(self):
        """_classify_word_count_trend must return 'decreasing', never 'declining'."""
        result = _classify_word_count_trend([500, 400, 300, 200, 100])
        assert result == "decreasing"
        assert result != "declining"

    def test_word_count_trend_never_says_improving(self):
        result = _classify_word_count_trend([100, 200, 300, 400, 500])
        assert result == "increasing"
        assert result != "improving"

    def test_word_count_trend_never_says_irregular(self):
        """Variable output is described, never pathologised (#CRIP_TIME)."""
        result = _classify_word_count_trend([100, 500, 100, 500, 100])
        assert result == "variable"
        assert result != "irregular"

    # --- Class-wide trajectory arc label mapping ---

    def test_arc_label_map_values(self):
        """_ARC_LABEL_MAP must map internal labels to equity-framed labels."""
        assert _ARC_LABEL_MAP["declining"] == "decreasing"
        assert _ARC_LABEL_MAP["improving"] == "increasing"
        assert _ARC_LABEL_MAP["irregular"] == "variable"
        assert _ARC_LABEL_MAP["steady"] == "steady"

    def test_class_classify_trend_labels(self):
        """class_trajectory_context._classify_word_count_trend labels."""
        assert class_classify_trend([500, 400, 300, 200]) == "decreasing"
        assert class_classify_trend([200, 300, 400, 500]) == "increasing"
        # 5-point symmetric oscillation has zero slope → falls to CV check
        assert class_classify_trend([100, 500, 100, 500, 100]) == "variable"
        assert class_classify_trend([400, 410, 395, 405]) == "steady"

    def test_format_arc_line_uses_equity_labels(self):
        """_format_arc_line must never emit 'declining', 'improving', 'irregular'."""
        arcs = [
            StudentArc(student_id="1", student_name="A", trend="declining"),
            StudentArc(student_id="2", student_name="B", trend="improving"),
            StudentArc(student_id="3", student_name="C", trend="irregular"),
            StudentArc(student_id="4", student_name="D", trend="steady"),
        ]
        result = _format_arc_line(arcs)
        assert result is not None
        assert "declining" not in result
        assert "improving" not in result
        assert "irregular" not in result
        assert "decreasing" in result
        assert "increasing" in result
        assert "variable" in result
        assert "steady" in result

    def test_full_output_never_contains_deficit_language(self):
        """Full trajectory output must never contain deficit-framing vocabulary."""
        store = FakeStore([
            _wrap_history_entry(_make_prior_record(word_count=500), started_at="2026-03-01T10:00:00Z"),
            _wrap_history_entry(_make_prior_record(word_count=400), started_at="2026-03-08T10:00:00Z"),
            _wrap_history_entry(_make_prior_record(word_count=100), started_at="2026-03-15T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_current",
            current_word_count=50,
            current_submitted_at=_ts(10),
        )
        lower = result.lower()
        for banned in ["at risk", "concerning", "struggling", "failing",
                       "problematic", "deficient", "red flag", "alarming"]:
            assert banned not in lower, f"Deficit language '{banned}' found in output"

    def test_register_shift_described_neutrally(self):
        """Register shifts must be described, not evaluated (#ETHNIC_STUDIES).
        No register is 'better' or 'worse' — passionate→analytical reflects material."""
        priors = [
            _wrap_history_entry(
                _make_prior_record(word_count=400, emotional_register="passionate",
                                   submitted_at=_ts(10, day=1)),
                started_at="2026-03-01T10:00:00Z",
            ),
            _wrap_history_entry(
                _make_prior_record(word_count=400, emotional_register="passionate",
                                   submitted_at=_ts(10, day=8)),
                started_at="2026-03-08T10:00:00Z",
            ),
            _wrap_history_entry(
                _make_prior_record(word_count=400, emotional_register="analytical",
                                   submitted_at=_ts(10, day=15)),
                started_at="2026-03-15T10:00:00Z",
            ),
        ]
        store = FakeStore(priors)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=400,
            current_submitted_at=_ts(10, day=22),
            current_register="analytical",
        )
        lower = result.lower()
        for banned in ["declined from", "worse", "better", "degraded",
                       "deteriorated", "dropped to"]:
            assert banned not in lower, f"Value judgment '{banned}' in register description"


# ===================================================================
# SECTION 2: Pattern Break Detection — Core 2+ Signal Rule
# ===================================================================

class TestPatternBreakMultiSignal:
    """Pattern break requires 2+ simultaneous signals. Single signal = no break."""

    def _base_priors(self, n: int = 3, **overrides) -> List[Dict[str, Any]]:
        """Build N stable prior records with optional per-field overrides."""
        defaults = dict(
            word_count=400, emotional_register="reflective",
            wellbeing_axis="NONE", unknown_word_rate=1.0,
            linguistic_assets=[], theme_tags=["identity", "power"],
            submitted_at=_ts(14), personal_connections=["mom's story"],
            readings_referenced=["hooks ch3"], engagement_depth="strong",
        )
        defaults.update(overrides)
        return [_make_prior_record(**defaults) for _ in range(n)]

    # --- Single signal: NEVER triggers ---

    def test_single_signal_word_count_decrease_no_break(self):
        """Word count drop alone does not trigger a pattern break."""
        priors = self._base_priors()
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=50,  # massive drop
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count == 1, f"Expected exactly 1 signal (word count), got {count}"
        assert not is_break

    def test_single_signal_time_shift_no_break(self):
        """Time shift alone does not trigger a pattern break."""
        priors = self._base_priors(submitted_at=_ts(10))  # 10 AM typical
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(2),  # 2 AM — shifted
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        # Time shift might be 1 signal; ensure no break
        assert not is_break

    def test_single_signal_theme_drop_no_break(self):
        """Theme continuity drop alone does not trigger a pattern break."""
        priors = self._base_priors(theme_tags=["identity", "power"])
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["cooking", "gardening"],  # totally different
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count == 1
        assert not is_break

    # --- Two signals: DOES trigger ---

    def test_two_signals_word_count_plus_theme_drop(self):
        """Word count decrease + theme continuity drop = pattern break."""
        priors = self._base_priors(theme_tags=["identity", "power"])
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=50,  # signal 1: word count decrease
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["cooking"],  # signal 7: theme continuity drop
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count >= 2
        assert is_break

    def test_two_signals_word_count_plus_connections_vanished(self):
        """Word count decrease + personal connections vanished = break."""
        priors = self._base_priors(personal_connections=["grandma's story", "neighborhood"])
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=50,  # signal 1
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=[],  # signal 8
            current_readings_referenced=["hooks ch3"],
        )
        assert count >= 2
        assert is_break

    # --- Remaining single-signal isolation tests ---

    def test_single_signal_sustained_disengaged_register_no_break(self):
        """Signal 2: sustained disengaged register alone does not trigger break."""
        priors = self._base_priors(emotional_register="disengaged")
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="disengaged",  # signal 2: sustained disengaged
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert not is_break, "Sustained disengaged register alone must not trigger break"

    def test_single_signal_wellness_shifting_no_break(self):
        """Signal 4: ENGAGED→BURNOUT transition alone does not trigger break."""
        priors = [
            _make_prior_record(
                wellbeing_axis="ENGAGED", word_count=400, submitted_at=_ts(14),
                theme_tags=["identity", "power"], personal_connections=["mom's story"],
                readings_referenced=["hooks ch3"], engagement_depth="strong",
            ),
            _make_prior_record(
                wellbeing_axis="ENGAGED", word_count=400, submitted_at=_ts(14),
                theme_tags=["identity", "power"], personal_connections=["mom's story"],
                readings_referenced=["hooks ch3"], engagement_depth="strong",
            ),
            _make_prior_record(
                wellbeing_axis="BURNOUT", word_count=400, submitted_at=_ts(14),
                theme_tags=["identity", "power"], personal_connections=["mom's story"],
                readings_referenced=["hooks ch3"], engagement_depth="strong",
            ),
        ]
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert not is_break, "Wellness shift alone must not trigger break"

    def test_single_signal_engagement_depth_declining_no_break(self):
        """Signal 5: engagement depth drop alone does not trigger break."""
        priors = self._base_priors(engagement_depth="strong")
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="minimal",  # strong→minimal
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert not is_break, "Engagement depth drop alone must not trigger break"

    def test_zero_signals_no_break(self):
        """Stable student = 0 signals, no break."""
        priors = self._base_priors()
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count == 0
        assert not is_break


# ===================================================================
# SECTION 3: Signal 6 — Unknown Word Rate Suppression
# ===================================================================

class TestSignal6Suppression:
    """unknown_word_rate spike suppressed when linguistic_assets increasing."""

    def _priors_for_uwr(self, asset_counts: List[int], uwr: float = 1.0):
        """Build priors with varying linguistic asset counts."""
        records = []
        for i, ac in enumerate(asset_counts):
            assets = [f"asset_{j}" for j in range(ac)]
            records.append(_make_prior_record(
                unknown_word_rate=uwr,
                linguistic_assets=assets,
                theme_tags=["identity", "power"],
                submitted_at=_ts(14, day=10 + i),
                personal_connections=["mom's story"],
                readings_referenced=["hooks ch3"],
            ))
        return records

    def test_uwr_spike_fires_when_assets_not_increasing(self):
        """UWR spike should fire when linguistic assets are flat."""
        priors = self._priors_for_uwr([2, 2, 2], uwr=1.0)
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=5.0,  # 5x the prior avg of 1.0
            current_linguistic_assets=["asset_0", "asset_1"],  # same count
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        # Signal 6 should be True (UWR spiking, assets not increasing)
        # Everything else is stable, so exactly 1 signal
        assert count == 1, f"Expected exactly 1 signal (UWR spike), got {count}"

    def test_uwr_spike_suppressed_when_assets_growing(self):
        """UWR spike suppressed when linguistic assets are increasing (#COMMUNITY_CULTURAL_WEALTH)."""
        # Assets growing: 1 → 2 → 3 over prior records
        priors = self._priors_for_uwr([1, 2, 3], uwr=1.0)
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400,
            current_submitted_at=_ts(14),
            current_engagement_depth="strong",
            current_unknown_word_rate=5.0,  # high UWR
            current_linguistic_assets=["a", "b", "c", "d"],  # 4 > prior's 3
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["mom's story"],
            current_readings_referenced=["hooks ch3"],
        )
        # Signal 6 should be suppressed — so this signal should NOT count
        # The only way to verify: confirm total count doesn't include it
        # With everything else stable, count should be 0
        assert count == 0
        assert not is_break


# ===================================================================
# SECTION 4: Signals 8, 9, 10
# ===================================================================

class TestSignals8Through10:
    """Tests for personal connections vanished, readings disappeared, formulaic shift."""

    def _stable_priors(self, n: int = 3, **kw) -> List[Dict[str, Any]]:
        defaults = dict(
            word_count=400, emotional_register="reflective",
            wellbeing_axis="NONE", unknown_word_rate=1.0,
            theme_tags=["identity", "power"], submitted_at=_ts(14),
            personal_connections=["family story", "lived experience"],
            readings_referenced=["hooks ch3", "crenshaw"],
            engagement_depth="strong",
        )
        defaults.update(kw)
        return [_make_prior_record(**defaults) for _ in range(n)]

    # --- Signal 8: personal connections vanished ---

    def test_signal8_fires_when_connections_vanish(self):
        """Student who consistently brought personal connections now has zero."""
        priors = self._stable_priors(personal_connections=["family story", "church"])
        _, count_with = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=[], current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=[],  # vanished
            current_readings_referenced=["hooks ch3", "crenshaw"],
        )
        # Now compare to same but with connections present
        _, count_without = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=[], current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],  # still present
            current_readings_referenced=["hooks ch3", "crenshaw"],
        )
        assert count_with > count_without, "Signal 8 should fire when connections vanish"

    def test_signal8_requires_2_priors_with_connections(self):
        """Signal 8 requires connections in 2+ prior submissions."""
        # Only 1 prior had connections
        priors = [
            _make_prior_record(personal_connections=["family"], theme_tags=["id"], submitted_at=_ts(14)),
            _make_prior_record(personal_connections=[], theme_tags=["id"], submitted_at=_ts(14)),
            _make_prior_record(personal_connections=[], theme_tags=["id"], submitted_at=_ts(14)),
        ]
        _, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=[], current_theme_tags=["id"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=[],
            current_readings_referenced=[],
        )
        # Signal 8 should NOT fire (only 1 prior had connections, avg < 1)
        # With stable word count, register, etc. this should be 0 signals
        # (reading also needs 2+ to fire, and they had 0)
        assert count == 0

    # --- Signal 9: readings disappeared ---

    def test_signal9_fires_when_readings_vanish(self):
        """Student who consistently referenced readings now references zero."""
        priors = self._stable_priors(readings_referenced=["hooks ch3", "crenshaw"])
        _, count_with = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=[], current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=[],  # disappeared
        )
        _, count_without = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=[], current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=["hooks ch3"],  # still present
        )
        assert count_with > count_without, "Signal 9 should fire when readings disappear"

    # --- Signal 10: formulaic shift ---

    def test_signal10_fires_on_new_formulaic(self):
        """Student gains formulaic_essay_structure when they never had it."""
        priors = self._stable_priors(linguistic_assets=["code_switching", "narrative_voice"])
        _, count_with_formulaic = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=["formulaic_essay_structure"],  # NEW
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=["hooks ch3"],
        )
        _, count_no_formulaic = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=["code_switching"],  # no formulaic
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count_with_formulaic > count_no_formulaic, "Signal 10 should fire on new formulaic"

    def test_signal10_does_not_fire_if_already_formulaic(self):
        """If student always had formulaic_essay_structure, signal 10 does not fire."""
        priors = self._stable_priors(linguistic_assets=["formulaic_essay_structure"])
        _, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(14),
            current_engagement_depth="strong", current_unknown_word_rate=1.0,
            current_linguistic_assets=["formulaic_essay_structure"],
            current_theme_tags=["identity", "power"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=["hooks ch3"],
        )
        assert count == 0  # nothing changed


# ===================================================================
# SECTION 5: Smart Word Count Description
# ===================================================================

class TestSmartWordCountDescription:
    """_describe_word_count_pattern should catch inflection points."""

    def test_steady(self):
        result = _describe_word_count_pattern([400, 410, 395, 405], 403)
        assert "steady" in result.lower()

    def test_increasing(self):
        # Gentle increase: recent not >1.6x earlier, so falls through to overall trend
        result = _describe_word_count_pattern([300, 330, 360, 390, 420], 360)
        assert "increasing" in result.lower()

    def test_decreasing(self):
        result = _describe_word_count_pattern([500, 400, 300, 200], 350)
        assert "decreasing" in result.lower() or "was around" in result.lower()

    def test_increasing_then_collapse(self):
        """Inflection: was increasing, then collapsed."""
        counts = [200, 300, 400, 500, 80]
        result = _describe_word_count_pattern(counts, round(sum(counts) / len(counts)))
        # Should detect that recent diverges from earlier — mentions the low value
        assert "80" in result or "was around" in result.lower()

    def test_oscillating_burnout(self):
        """Variable pattern — the inflection detector catches the recent drop."""
        counts = [500, 100, 500, 100]
        result = _describe_word_count_pattern(counts, 300)
        # The function detects that recent (last 2) diverges from earlier
        # and reports the low value — this IS the smart inflection detection
        assert "100" in result or "was around" in result.lower()

    def test_too_few_for_pattern(self):
        """1-2 data points: just average, no trend claim."""
        result = _describe_word_count_pattern([400], 400)
        assert "around" in result.lower()  # reports avg, no trend

        result = _describe_word_count_pattern([400, 350], 375)
        assert "around" in result.lower()

    def test_empty_input(self):
        assert _describe_word_count_pattern([], 0) == ""


# ===================================================================
# SECTION 6: Submission Time Analysis
# ===================================================================

class TestSubmissionTimeAnalysis:
    """Submission time pattern detection, including always-late-night student."""

    def test_always_late_night_not_flagged(self):
        """Student who always submits late-night is NOT flagged as shifted."""
        # All prior submissions are 11 PM – 2 AM
        prior_timestamps = [_ts(23), _ts(0), _ts(1), _ts(23, 30)]
        current = _ts(0, 30)  # another late-night — their normal

        description, is_shifted = _analyze_submission_time(prior_timestamps, current)
        assert not is_shifted, "Always-late-night student should NOT be flagged"
        assert "late" in description.lower() or "evening" in description.lower()

    def test_daytime_student_shifting_to_late_night(self):
        """Student who typically submits mid-afternoon, now submitting at 2 AM."""
        prior_timestamps = [_ts(14), _ts(15), _ts(14, 30)]
        current = _ts(2)  # 2 AM — outside window

        description, is_shifted = _analyze_submission_time(prior_timestamps, current)
        assert is_shifted, "Daytime student submitting at 2 AM should be flagged"

    def test_variable_schedule_not_flagged(self):
        """Student with high-variance schedule should not be flagged."""
        # Times span from 8 AM to 11 PM — wide spread
        prior_timestamps = [_ts(8), _ts(16), _ts(23), _ts(11)]
        current = _ts(2)

        description, is_shifted = _analyze_submission_time(prior_timestamps, current)
        assert not is_shifted, "Variable-schedule student should not be flagged"
        assert "variable" in description.lower()

    def test_insufficient_data_no_flag(self):
        """Fewer than 2 prior timestamps: no pattern can be established."""
        description, is_shifted = _analyze_submission_time([_ts(14)], _ts(2))
        assert not is_shifted
        assert description == ""

    def test_no_prior_timestamps(self):
        description, is_shifted = _analyze_submission_time([], _ts(14))
        assert not is_shifted
        assert description == ""


# ===================================================================
# SECTION 7: Prior Submission Count Cases (0 / 1 / 2+)
# ===================================================================

class TestPriorCounts:
    """build_trajectory_context handles 0, 1, and 2+ prior submissions correctly."""

    def test_zero_priors_returns_empty(self):
        """No prior history → empty string."""
        store = FakeStore([])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=300,
        )
        assert result == ""

    def test_one_prior_includes_comparison_caveat(self):
        """Single prior submission → 'comparison point, not a trend' caveat."""
        record = _make_prior_record(word_count=350)
        store = FakeStore([
            _wrap_history_entry(record, started_at="2026-03-01T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=300,
            current_submitted_at=_ts(14),
        )
        assert "comparison point, not a trend" in result
        assert "TRAJECTORY CONTEXT" in result

    def test_one_prior_no_pattern_break_section(self):
        """Single prior: no pattern break section, even if numbers differ wildly."""
        record = _make_prior_record(word_count=500)
        store = FakeStore([
            _wrap_history_entry(record, started_at="2026-03-01T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=50,  # massive drop
            current_submitted_at=_ts(14),
        )
        assert "What changed" not in result
        assert "Pattern:" not in result

    def test_two_priors_includes_pattern_section(self):
        """Two prior submissions → pattern section appears."""
        records = [
            _wrap_history_entry(
                _make_prior_record(word_count=400, submitted_at=_ts(10, day=1)),
                started_at="2026-03-01T10:00:00Z"
            ),
            _wrap_history_entry(
                _make_prior_record(word_count=380, submitted_at=_ts(10, day=8)),
                started_at="2026-03-08T10:00:00Z"
            ),
        ]
        store = FakeStore(records)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=370,
            current_submitted_at=_ts(10, day=15),
        )
        assert "Pattern:" in result

    def test_many_priors_summarizes_earlier(self):
        """More than 3 priors: most recent 3 get detail, earlier get summary."""
        records = [
            _wrap_history_entry(
                _make_prior_record(word_count=300 + i * 10, submitted_at=_ts(10, day=i + 1)),
                assignment_name=f"Essay {i+1}",
                started_at=f"2026-03-{i+1:02d}T10:00:00Z",
            )
            for i in range(5)
        ]
        store = FakeStore(records)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=360,
            current_submitted_at=_ts(10, day=20),
        )
        assert "Prior submissions (5):" in result
        assert "Plus 2 earlier" in result

    def test_zero_word_count_with_preprocessing_not_filtered(self):
        """Attachment submissions (wc=0 but preprocessing present) are included."""
        record = _make_prior_record(word_count=0)
        record["preprocessing"] = {"was_transcribed": True}
        store = FakeStore([
            _wrap_history_entry(record, started_at="2026-03-01T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=300,
        )
        assert result != ""
        assert "attachment submission" in result

    def test_translated_submission_shows_language_note(self):
        """#LANGUAGE_JUSTICE: Prior translated submission shows [in Spanish] notation."""
        record = _make_prior_record(word_count=350)
        record["preprocessing"] = {"original_language_name": "Spanish"}
        store = FakeStore([
            _wrap_history_entry(record, started_at="2026-03-01T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=300,
            current_submitted_at=_ts(14),
        )
        assert "[in Spanish]" in result, "Translated submission must note original language"

    def test_zero_word_count_no_preprocessing_filtered(self):
        """True zero submissions (wc=0, no preprocessing) are excluded."""
        record = _make_prior_record(word_count=0)
        # No preprocessing — this is a true empty submission
        store = FakeStore([
            _wrap_history_entry(record, started_at="2026-03-01T10:00:00Z"),
        ])
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=300,
        )
        assert result == ""  # filtered out, so no history


# ===================================================================
# SECTION 8: Class-Wide Trajectory Context
# ===================================================================

class TestClassTrajectoryContext:
    """Tests for class_trajectory_context.py builders."""

    def test_engagement_line_steady(self):
        metrics = [
            WeekMetric(week=1, avg_words=400),
            WeekMetric(week=2, avg_words=410),
            WeekMetric(week=3, avg_words=405),
        ]
        result = _format_engagement_line(metrics)
        assert result is not None
        assert "steady" in result
        assert "400" in result or "410" in result

    def test_engagement_line_insufficient_data(self):
        result = _format_engagement_line([WeekMetric(week=1, avg_words=400)])
        assert result is None

    def test_exhaustion_line_structural_framing(self):
        """Rising late/missing submissions include structural framing note."""
        metrics = [
            WeekMetric(week=1, late_count=2, silence_count=0),
            WeekMetric(week=2, late_count=5, silence_count=2),
        ]
        result = _format_exhaustion_line(metrics)
        assert result is not None
        assert "course design signal" in result
        assert "not individual" in result

    def test_exhaustion_line_no_framing_when_stable(self):
        """No structural framing when exhaustion is NOT rising."""
        metrics = [
            WeekMetric(week=1, late_count=3, silence_count=1),
            WeekMetric(week=2, late_count=2, silence_count=1),
        ]
        result = _format_exhaustion_line(metrics)
        assert result is not None
        assert "course design" not in result

    def test_themes_line_recurring_and_new(self):
        themes = [
            ThemeEvolution(theme_name="identity", status="recurring", weeks_present=[1, 2, 3]),
            ThemeEvolution(theme_name="power", status="recurring", weeks_present=[1, 2, 3]),
            ThemeEvolution(theme_name="climate", status="new", weeks_present=[3]),
        ]
        result = _format_themes_line(themes, run_count=4)
        assert result is not None
        assert '"identity"' in result
        assert '"climate"' in result
        assert "new this week" in result
        assert "persisted" in result

    def test_themes_line_empty(self):
        assert _format_themes_line([], run_count=3) is None

    def test_arc_line_no_individual_names(self):
        """Arc line must never name individual students."""
        arcs = [
            StudentArc(student_id="1", student_name="Maria Garcia", trend="steady"),
            StudentArc(student_id="2", student_name="DeShawn Williams", trend="declining"),
        ]
        result = _format_arc_line(arcs)
        assert result is not None
        assert "Maria" not in result
        assert "DeShawn" not in result
        assert "1 steady" in result
        assert "1 decreasing" in result  # mapped from "declining"

    def test_oxford_join(self):
        assert _oxford_join([]) == ""
        assert _oxford_join(["a"]) == "a"
        assert _oxford_join(["a", "b"]) == "a and b"
        assert _oxford_join(["a", "b", "c"]) == "a, b, and c"

    def test_class_trajectory_structural_note_always_present(self):
        """#DISABILITY_STUDIES: the structural framing note must be hardcoded
        into build_class_trajectory_context, not conditional on any data."""
        import inspect
        source = inspect.getsource(build_class_trajectory_context)
        assert "course design or material difficulty" in source
        assert "rather than individual disengagement" in source

    def test_build_class_trajectory_fewer_than_2_runs(self):
        """Fewer than 2 runs → empty string."""

        class FakeAnalyzerStore:
            pass

        # We can't easily mock TrajectoryAnalyzer, so test the public function
        # with a store that will produce no trajectory. The function catches
        # exceptions gracefully.
        store = FakeAnalyzerStore()
        result = build_class_trajectory_context(store, "course_1", "run_1")
        # Should return "" (TrajectoryAnalyzer will fail or return None)
        assert result == ""


# ===================================================================
# SECTION 9: _parse_hour edge cases
# ===================================================================

class TestParseHour:
    def test_standard_utc(self):
        assert _parse_hour("2026-03-15T14:30:00Z") == pytest.approx(14.5)

    def test_with_offset(self):
        assert _parse_hour("2026-03-15T14:30:00+00:00") == pytest.approx(14.5)

    def test_empty_string(self):
        assert _parse_hour("") is None

    def test_garbage(self):
        assert _parse_hour("not a timestamp") is None


# ===================================================================
# SECTION 10: Word Count Trend Classifier Edge Cases
# ===================================================================

class TestWordCountTrendEdgeCases:
    def test_single_value_returns_variable(self):
        """Fewer than 2 valid values → 'variable' (not enough data)."""
        assert _classify_word_count_trend([300]) == "variable"

    def test_none_values_skipped(self):
        """None values in the list should be skipped, not crash."""
        result = _classify_word_count_trend([None, 300, None, 310, None, 305])
        assert result in ("steady", "increasing", "decreasing", "variable")

    def test_zero_values_skipped(self):
        """Zero word counts are excluded from trend calculation."""
        result = _classify_word_count_trend([0, 300, 0, 310, 0, 305])
        assert result in ("steady", "increasing", "decreasing", "variable")

    def test_all_same_is_steady(self):
        assert _classify_word_count_trend([300, 300, 300, 300]) == "steady"


# ===================================================================
# SECTION 11: Integration — Full build_trajectory_context output shape
# ===================================================================

class TestBuildTrajectoryContextIntegration:
    """Full output shape validation for build_trajectory_context."""

    def _make_store_with_history(self, n_priors: int = 3) -> FakeStore:
        records = []
        for i in range(n_priors):
            rec = _make_prior_record(
                word_count=350 + i * 20,
                submitted_at=_ts(10, day=1 + i * 7),
                theme_tags=["identity", "power"],
                personal_connections=["family story"],
                readings_referenced=["hooks ch3"],
            )
            records.append(_wrap_history_entry(
                rec,
                assignment_name=f"Essay {i+1}",
                started_at=f"2026-{3:02d}-{1 + i * 7:02d}T10:00:00Z",
            ))
        return FakeStore(records)

    def test_output_has_header_and_footer(self):
        store = self._make_store_with_history(3)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=400, current_submitted_at=_ts(10, day=22),
        )
        assert result.startswith("TRAJECTORY CONTEXT")
        assert result.endswith("---")

    def test_output_includes_current_submission(self):
        store = self._make_store_with_history(3)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=400, current_submitted_at=_ts(10, day=22),
            current_register="reflective",
        )
        assert "Current submission:" in result
        assert "400 words" in result

    def test_pattern_break_shows_what_changed(self):
        """When 2+ signals fire, 'What changed:' appears in output."""
        # Build priors with strong engagement, then current has collapse
        priors = []
        for i in range(3):
            rec = _make_prior_record(
                word_count=500,
                theme_tags=["identity", "power"],
                submitted_at=_ts(10, day=1 + i * 7),
                personal_connections=["family story"],
                readings_referenced=["hooks ch3"],
            )
            priors.append(_wrap_history_entry(rec, started_at=f"2026-03-{1 + i * 7:02d}T10:00:00Z"))

        store = FakeStore(priors)
        result = build_trajectory_context(
            store, "stu_1", "course_1", "run_1",
            current_word_count=50,  # signal 1: word count collapse
            current_submitted_at=_ts(10, day=22),
            current_theme_tags=["cooking"],  # signal 7: theme continuity dropped
            current_personal_connections=[],  # signal 8: connections vanished
            current_readings_referenced=[],  # signal 9: readings disappeared
        )
        assert "What changed:" in result
        assert "Multiple signals" in result

    def test_store_failure_returns_empty(self):
        """If store.get_student_history() raises, return empty string gracefully."""

        class FailingStore:
            def get_student_history(self, *args, **kwargs):
                raise RuntimeError("DB connection lost")

        result = build_trajectory_context(
            FailingStore(), "stu_1", "course_1", "run_1",
            current_word_count=300,
        )
        assert result == ""


# ===================================================================
# SECTION 12: Regression — Specific Equity Scenarios
# ===================================================================

class TestEquityRegressions:
    """Scenario-based tests for equity edge cases."""

    def test_esl_student_uwr_spike_with_growing_voice(self):
        """ESL student's unknown word rate rises as they bring more authentic voice.
        Signal 6 should be suppressed (#COMMUNITY_CULTURAL_WEALTH)."""
        priors = [
            _make_prior_record(
                unknown_word_rate=2.0,
                linguistic_assets=["simple_vocabulary"],
                theme_tags=["identity"], submitted_at=_ts(10, day=1),
                personal_connections=["family story"],
                readings_referenced=["hooks ch3"],
            ),
            _make_prior_record(
                unknown_word_rate=3.0,
                linguistic_assets=["simple_vocabulary", "code_switching"],
                theme_tags=["identity"], submitted_at=_ts(10, day=8),
                personal_connections=["family story"],
                readings_referenced=["hooks ch3"],
            ),
            _make_prior_record(
                unknown_word_rate=3.5,
                linguistic_assets=["simple_vocabulary", "code_switching", "narrative_voice"],
                theme_tags=["identity"], submitted_at=_ts(10, day=15),
                personal_connections=["family story"],
                readings_referenced=["hooks ch3"],
            ),
        ]
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=400, current_submitted_at=_ts(10, day=22),
            current_engagement_depth="strong", current_unknown_word_rate=8.0,
            current_linguistic_assets=["simple_vocabulary", "code_switching", "narrative_voice", "community_knowledge"],
            current_theme_tags=["identity"], current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family story"],
            current_readings_referenced=["hooks ch3"],
        )
        # Signal 6 suppressed → should not contribute
        assert count == 0
        assert not is_break

    def test_neurodivergent_variable_output_not_pathologised(self):
        """Student with variable word counts: even when LSQ sees a downward slope,
        a single signal (word count decreasing) NEVER triggers a pattern break."""
        priors = [
            _make_prior_record(word_count=600, theme_tags=["id"], submitted_at=_ts(10, day=1),
                               personal_connections=["family"], readings_referenced=["ch1"]),
            _make_prior_record(word_count=100, theme_tags=["id"], submitted_at=_ts(10, day=8),
                               personal_connections=["family"], readings_referenced=["ch2"]),
            _make_prior_record(word_count=500, theme_tags=["id"], submitted_at=_ts(10, day=15),
                               personal_connections=["family"], readings_referenced=["ch3"]),
        ]
        is_break, count = _detect_pattern_break(
            prior_records=priors,
            current_word_count=80,
            current_submitted_at=_ts(10, day=22),
            current_engagement_depth="strong",
            current_unknown_word_rate=1.0,
            current_linguistic_assets=[],
            current_theme_tags=["id"],
            current_register="reflective",
            prior_timestamps=[r["submitted_at"] for r in priors],
            current_personal_connections=["family"],
            current_readings_referenced=["ch4"],
        )
        # LSQ may classify [600,100,500,80] as "decreasing" (overall slope negative)
        # but crucially, word count is at MOST 1 signal — never triggers a break alone
        assert not is_break, "Single signal (word count) must never trigger a break"
        # Verify the symmetric oscillation pattern IS classified as variable
        symmetric = _classify_word_count_trend([600, 100, 500, 100, 600])
        assert symmetric == "variable"

    def test_working_student_variable_submission_times(self):
        """Student with care/work responsibilities has variable schedule — not flagged."""
        prior_timestamps = [_ts(8), _ts(22), _ts(14), _ts(3)]  # all over the place
        description, is_shifted = _analyze_submission_time(prior_timestamps, _ts(1))
        assert not is_shifted
        assert "variable" in description.lower()


# ===================================================================
# Run directly
# ===================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
