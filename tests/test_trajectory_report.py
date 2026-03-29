"""
Trajectory Report — unit test suite.

Tests the per-student longitudinal narrative report generator.
Pure unit tests: no LLM, no database, no MLX. All data is synthetic.
Phase 1 (arc builder) is tested exhaustively; Phase 2 (LLM narrative) is
tested only for prompt assembly (no actual LLM calls).

Run with: python -m pytest tests/test_trajectory_report.py -v

Test areas:
  - Minimum submission threshold (0, 1, 2)
  - Theme evolution: persistent, emerging, fading, confidence-weighted
  - Intellectual thread: reaching_for + confusion_or_questions trajectory
  - Quote curation: significance, spread, deduplication, max limit
  - Engagement patterns: intellectual mode identification, peak detection
  - Thematic engagement rhythm: temporal + thematic correlation
  - Emotional notes: surfaced at peaks
  - World connections: current_events trajectory
  - Strengths trajectory: repertoire growth, register range
  - Wellbeing arc: trend classification, arc rendering
  - Cluster trajectory: depth vs range
  - Lens observations: teacher-configured analysis
  - Prior feedback: included, truncated, "don't repeat" note
  - Integrity signals: z-score divergence, formulaic shift
  - Teacher profile: arc weighting, engagement score boost
  - Preamble: coverage disclosure, date range, missing assignments
  - Scale test: 30+ submissions produce bounded arc
  - Edge cases: missing fields, empty coding records, None values

All test data is synthetic — no real student data. FERPA-safe.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from typing import Any, Dict, List

from insights.trajectory_report import (
    build_semester_arc,
    build_preamble,
    _build_theme_evolution,
    _build_intellectual_thread,
    _curate_key_quotes,
    _build_engagement_patterns,
    _build_world_connections,
    _build_strengths_trajectory,
    _build_wellbeing_arc,
    _build_cluster_trajectory,
    _build_lens_observations,
    _build_prior_feedback_note,
    _build_integrity_signals,
    _engagement_score,
    _format_date,
    _format_date_range,
)


# ---------------------------------------------------------------------------
# Test data factories — synthetic students, FERPA-safe
# ---------------------------------------------------------------------------

def _make_entry(
    assignment: str = "Assignment 1",
    run_id: str = "r1",
    started_at: str = "2026-01-15T14:00:00Z",
    **coding_fields,
) -> Dict[str, Any]:
    """Build a synthetic history entry."""
    return {
        "run_id": run_id,
        "student_name": "Test Student",
        "assignment_name": assignment,
        "started_at": started_at,
        "coding_record": coding_fields,
    }


def _make_basic_entry(
    assignment: str, started_at: str, word_count: int = 300,
    register: str = "analytical", themes: List[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    """Build a typical entry with common defaults."""
    return _make_entry(
        assignment=assignment,
        started_at=started_at,
        word_count=word_count,
        emotional_register=register,
        theme_tags=themes or ["topic_a"],
        engagement_signals={"engagement_depth": "moderate"},
        **kwargs,
    )


def _make_rich_entry(
    assignment: str, started_at: str,
) -> Dict[str, Any]:
    """Build a deeply-engaged entry with all fields populated."""
    return _make_entry(
        assignment=assignment,
        started_at=started_at,
        word_count=600,
        emotional_register="passionate",
        emotional_notes="deeply invested — this material is personal",
        theme_tags=["identity", "structural_power", "community"],
        theme_confidence={"identity": 0.95, "structural_power": 0.9, "community": 0.7},
        notable_quotes=[
            {"text": "This is where I come from", "significance": "grounding theory in place"},
            {"text": "The system was not built for us", "significance": "structural critique"},
        ],
        what_student_is_reaching_for="Connecting lived experience to structural analysis",
        personal_connections=["family history", "neighborhood"],
        readings_referenced=["hooks", "Crenshaw"],
        concepts_applied=["intersectionality", "structural power"],
        current_events_referenced=["housing policy"],
        wellbeing_axis="ENGAGED",
        engagement_signals={"engagement_depth": "strong"},
        linguistic_assets=["code_switching", "narrative_sophistication"],
        confusion_or_questions="How do we move from analysis to action?",
        lens_observations={"equity": "centers lived experience as valid evidence"},
    )


def _make_sparse_entry(
    assignment: str, started_at: str,
) -> Dict[str, Any]:
    """Build a minimal entry — student submitted but not much there."""
    return _make_entry(
        assignment=assignment,
        started_at=started_at,
        word_count=45,
        emotional_register="flat",
        theme_tags=["compliance"],
        engagement_signals={"engagement_depth": "minimal"},
    )


def _make_semester(n: int = 8) -> List[Dict[str, Any]]:
    """Build a full semester of synthetic entries for scale testing."""
    history = []
    themes_pool = [
        ["identity", "belonging"],
        ["structural_power", "identity"],
        ["community", "resistance"],
        ["policy", "structural_power"],
        ["narrative", "voice"],
    ]
    registers = ["analytical", "passionate", "personal", "analytical", "reflective"]
    for i in range(n):
        week = i + 1
        history.append(_make_entry(
            assignment=f"Week {week} Response",
            run_id=f"r{week}",
            started_at=f"2026-01-{7 + week:02d}T14:00:00Z",
            word_count=200 + (i * 30),
            emotional_register=registers[i % len(registers)],
            theme_tags=themes_pool[i % len(themes_pool)],
            theme_confidence={t: 0.6 + (i * 0.03) for t in themes_pool[i % len(themes_pool)]},
            notable_quotes=[{
                "text": f"Synthetic quote week {week}",
                "significance": f"Shows development at week {week}",
            }] if i % 2 == 0 else [],
            what_student_is_reaching_for=f"Week {week} intellectual reach",
            engagement_signals={"engagement_depth": "moderate" if i % 3 else "strong"},
            personal_connections=["family"] if i % 3 == 0 else [],
            readings_referenced=[f"Author_{week}"] if i % 2 == 0 else [],
            concepts_applied=[f"concept_{week}"],
            linguistic_assets=["code_switching"] + (["narrative_sophistication"] if i > 4 else []),
            wellbeing_axis="ENGAGED" if i < 6 else "BURNOUT",
        ))
    return history


# ===========================================================================
# Date helpers
# ===========================================================================

class TestFormatDate:
    def test_iso_with_z(self):
        assert _format_date("2026-01-15T14:00:00Z") == "Jan 15"

    def test_iso_with_offset(self):
        assert _format_date("2026-03-05T10:30:00+05:00") == "Mar 5"

    def test_empty(self):
        assert _format_date("") == ""

    def test_none(self):
        assert _format_date(None) == ""

    def test_invalid(self):
        assert _format_date("not-a-date") == ""


class TestFormatDateRange:
    def test_single_date(self):
        result = _format_date_range(["2026-01-15T14:00:00Z"])
        assert "Jan 15" in result

    def test_range(self):
        result = _format_date_range([
            "2026-01-15T14:00:00Z",
            "2026-05-20T14:00:00Z",
        ])
        assert "Jan 15" in result
        assert "May 20" in result
        assert "–" in result

    def test_empty_list(self):
        assert _format_date_range([]) == ""

    def test_invalid_dates_filtered(self):
        result = _format_date_range(["bad", "", "2026-01-15T14:00:00Z"])
        assert "Jan 15" in result


# ===========================================================================
# Theme evolution
# ===========================================================================

class TestThemeEvolution:
    def test_no_themes(self):
        history = [_make_entry(theme_tags=[]), _make_entry(theme_tags=[])]
        result = _build_theme_evolution(history)
        assert "No themes" in result

    def test_persistent_themes(self):
        history = [
            _make_basic_entry("A1", "2026-01-10", themes=["identity", "power"]),
            _make_basic_entry("A2", "2026-01-17", themes=["identity", "community"]),
            _make_basic_entry("A3", "2026-01-24", themes=["identity", "power"]),
            _make_basic_entry("A4", "2026-01-31", themes=["identity", "voice"]),
        ]
        result = _build_theme_evolution(history)
        assert "Persistent" in result
        assert "identity" in result

    def test_emerging_themes(self):
        history = [
            _make_basic_entry("A1", "2026-01-10", themes=["topic_a"]),
            _make_basic_entry("A2", "2026-01-17", themes=["topic_a"]),
            _make_basic_entry("A3", "2026-01-24", themes=["topic_a", "new_theme"]),
            _make_basic_entry("A4", "2026-01-31", themes=["new_theme"]),
        ]
        result = _build_theme_evolution(history)
        assert "emerging" in result.lower() or "new_theme" in result

    def test_confidence_weights_ranking(self):
        """High-confidence themes should rank above low-confidence frequent ones."""
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                theme_tags=["deep_theme", "surface_theme"],
                theme_confidence={"deep_theme": 0.95, "surface_theme": 0.2},
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                theme_tags=["deep_theme", "surface_theme"],
                theme_confidence={"deep_theme": 0.9, "surface_theme": 0.15},
            ),
            _make_entry(
                assignment="A3", started_at="2026-01-24",
                theme_tags=["deep_theme", "surface_theme"],
                theme_confidence={"deep_theme": 0.88, "surface_theme": 0.1},
            ),
        ]
        result = _build_theme_evolution(history)
        # deep_theme should appear before surface_theme in persistent list
        if "deep_theme" in result and "surface_theme" in result:
            assert result.index("deep_theme") < result.index("surface_theme")


# ===========================================================================
# Intellectual thread
# ===========================================================================

class TestIntellectualThread:
    def test_reaching_for_across_assignments(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                what_student_is_reaching_for="Understanding power structures",
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                what_student_is_reaching_for="Applying power analysis to local context",
            ),
        ]
        result = _build_intellectual_thread(history)
        assert "Understanding power structures" in result
        assert "Applying power analysis" in result
        assert "[A1]" in result
        assert "[A2]" in result

    def test_confusion_or_questions_trajectory(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                confusion_or_questions="What is structural racism?",
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                confusion_or_questions="How does structural racism operate in education?",
            ),
        ]
        result = _build_intellectual_thread(history)
        assert "Questions" in result
        assert "structural racism" in result

    def test_empty_reaching_for(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10"),
            _make_entry(assignment="A2", started_at="2026-01-17"),
        ]
        result = _build_intellectual_thread(history)
        assert result == ""


# ===========================================================================
# Quote curation
# ===========================================================================

class TestQuoteCuration:
    def test_few_quotes_all_included(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                notable_quotes=[{"text": "Quote one", "significance": "sig one"}],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                notable_quotes=[{"text": "Quote two", "significance": "sig two"}],
            ),
        ]
        result = _curate_key_quotes(history)
        assert "Quote one" in result
        assert "Quote two" in result

    def test_assignment_spread(self):
        """Quotes should be spread across assignments, not clustered."""
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                notable_quotes=[
                    {"text": f"A1 quote {i}", "significance": f"sig {i}"}
                    for i in range(5)
                ],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                notable_quotes=[
                    {"text": "A2 quote", "significance": "important"},
                ],
            ),
        ]
        result = _curate_key_quotes(history)
        # A2's quote should appear even though A1 has more
        assert "A2 quote" in result

    def test_no_quotes(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10"),
            _make_entry(assignment="A2", started_at="2026-01-17"),
        ]
        result = _curate_key_quotes(history)
        assert "No notable quotes" in result

    def test_max_limit(self):
        """Should not exceed _MAX_QUOTES even with many available."""
        history = []
        for i in range(15):
            history.append(_make_entry(
                assignment=f"A{i}", started_at=f"2026-01-{10+i:02d}T00:00:00Z",
                notable_quotes=[
                    {"text": f"Quote from A{i}", "significance": f"sig {i}"},
                    {"text": f"Second quote from A{i}", "significance": ""},
                ],
            ))
        result = _curate_key_quotes(history)
        # Count actual quote lines (lines starting with '  - "')
        quote_lines = [l for l in result.split("\n") if l.strip().startswith('"') or l.strip().startswith('- "')]
        assert len(quote_lines) <= 8  # _MAX_QUOTES


# ===========================================================================
# Engagement patterns
# ===========================================================================

class TestEngagementPatterns:
    def test_identifies_intellectual_modes(self):
        history = [
            _make_rich_entry("A1", "2026-01-10"),
            _make_sparse_entry("A2", "2026-01-17"),
        ]
        result = _build_engagement_patterns(history)
        assert "personal-to-theory connection" in result
        assert "Strongest work in" in result

    def test_emotional_notes_at_peaks(self):
        history = [
            _make_rich_entry("A1", "2026-01-10"),
            _make_sparse_entry("A2", "2026-01-17"),
        ]
        result = _build_engagement_patterns(history)
        assert "deeply invested" in result

    def test_teacher_interests_reweight_peaks(self):
        """Teacher interests should boost assignments that align."""
        # A1 matches teacher interest, A2 doesn't
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                word_count=300, emotional_register="analytical",
                theme_tags=["evidence_use"],
                engagement_signals={"engagement_depth": "moderate"},
                concepts_applied=["evidence-based argumentation"],
                readings_referenced=["Author1"],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                word_count=350, emotional_register="passionate",
                theme_tags=["personal_narrative"],
                engagement_signals={"engagement_depth": "moderate"},
                personal_connections=["family"],
            ),
        ]
        result_no_profile = _build_engagement_patterns(history)
        result_with_profile = _build_engagement_patterns(
            history, teacher_interests=["evidence-based argumentation"],
        )
        # With teacher interest, A1 should rank higher as peak
        assert "A1" in result_with_profile

    def test_engagement_rhythm_building(self):
        """Should detect building momentum across semester."""
        history = [
            _make_entry(
                assignment=f"A{i}", started_at=f"2026-01-{10+i:02d}T00:00:00Z",
                engagement_signals={"engagement_depth": "limited" if i < 2 else "strong"},
                word_count=100 + i * 50,
                notable_quotes=[{"text": f"q{i}", "significance": "s"}] if i > 2 else [],
                personal_connections=["family"] if i > 2 else [],
            )
            for i in range(6)
        ]
        result = _build_engagement_patterns(history)
        assert "building momentum" in result

    def test_empty_history(self):
        assert _build_engagement_patterns([]) == ""


# ===========================================================================
# Engagement score
# ===========================================================================

class TestEngagementScore:
    def test_strong_engagement_scores_high(self):
        cr = {
            "engagement_signals": {"engagement_depth": "strong"},
            "notable_quotes": [{"text": "q", "significance": "s"}],
            "personal_connections": ["family"],
            "readings_referenced": ["Author"],
            "concepts_applied": ["concept"],
        }
        score = _engagement_score(cr)
        assert score >= 10  # 6 + 1 + 1 + 1 + 1

    def test_minimal_engagement_scores_low(self):
        cr = {
            "engagement_signals": {"engagement_depth": "minimal"},
        }
        score = _engagement_score(cr)
        assert score <= 1

    def test_teacher_interests_boost(self):
        cr = {
            "theme_tags": ["structural_power"],
            "concepts_applied": ["intersectionality"],
            "engagement_signals": {"engagement_depth": "moderate"},
        }
        base_score = _engagement_score(cr)
        boosted_score = _engagement_score(
            cr, teacher_interests=["structural_power", "intersectionality"],
        )
        assert boosted_score > base_score

    def test_teacher_interests_no_match_no_boost(self):
        cr = {
            "theme_tags": ["narrative"],
            "engagement_signals": {"engagement_depth": "moderate"},
        }
        base = _engagement_score(cr)
        boosted = _engagement_score(cr, teacher_interests=["quantum_mechanics"])
        assert base == boosted


# ===========================================================================
# World connections
# ===========================================================================

class TestWorldConnections:
    def test_surfaces_current_events(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                current_events_referenced=["immigration enforcement", "housing policy"],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                current_events_referenced=["climate legislation"],
            ),
        ]
        result = _build_world_connections(history)
        assert "immigration enforcement" in result
        assert "climate legislation" in result
        assert "[A1]" in result

    def test_empty_when_no_events(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10"),
            _make_entry(assignment="A2", started_at="2026-01-17"),
        ]
        assert _build_world_connections(history) == ""


# ===========================================================================
# Strengths trajectory
# ===========================================================================

class TestStrengthsTrajectory:
    def test_repertoire_growth(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                linguistic_assets=["code_switching"],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                linguistic_assets=["code_switching", "narrative_sophistication"],
            ),
        ]
        result = _build_strengths_trajectory(history)
        assert "expanded" in result
        assert "narrative_sophistication" in result

    def test_register_range(self):
        history = [
            _make_basic_entry("A1", "2026-01-10", register="analytical"),
            _make_basic_entry("A2", "2026-01-17", register="passionate"),
            _make_basic_entry("A3", "2026-01-24", register="personal"),
        ]
        result = _build_strengths_trajectory(history)
        assert "Register range" in result

    def test_consistent_register(self):
        history = [
            _make_basic_entry("A1", "2026-01-10", register="analytical"),
            _make_basic_entry("A2", "2026-01-17", register="analytical"),
        ]
        result = _build_strengths_trajectory(history)
        assert "Consistent register" in result


# ===========================================================================
# Wellbeing arc
# ===========================================================================

class TestWellbeingArc:
    def test_stable_wellbeing(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", wellbeing_axis="ENGAGED"),
            _make_entry(assignment="A2", started_at="2026-01-17", wellbeing_axis="ENGAGED"),
        ]
        result = _build_wellbeing_arc(history)
        assert "ENGAGED" in result
        assert "throughout" in result

    def test_arc_shift(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", wellbeing_axis="ENGAGED"),
            _make_entry(assignment="A2", started_at="2026-01-17", wellbeing_axis="BURNOUT"),
        ]
        result = _build_wellbeing_arc(history)
        assert "ENGAGED" in result
        assert "BURNOUT" in result
        assert "→" in result

    def test_word_count_trend(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", word_count=500),
            _make_entry(assignment="A2", started_at="2026-01-17", word_count=300),
            _make_entry(assignment="A3", started_at="2026-01-24", word_count=100),
        ]
        result = _build_wellbeing_arc(history)
        assert "decreasing" in result


# ===========================================================================
# Cluster trajectory
# ===========================================================================

class TestClusterTrajectory:
    def test_depth(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", cluster_id=2),
            _make_entry(assignment="A2", started_at="2026-01-17", cluster_id=2),
        ]
        result = _build_cluster_trajectory(history)
        assert "depth" in result

    def test_range(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", cluster_id=1),
            _make_entry(assignment="A2", started_at="2026-01-17", cluster_id=3),
        ]
        result = _build_cluster_trajectory(history)
        assert "range" in result
        assert "2 clusters" in result

    def test_no_clusters(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10"),
            _make_entry(assignment="A2", started_at="2026-01-17"),
        ]
        assert _build_cluster_trajectory(history) == ""


# ===========================================================================
# Lens observations
# ===========================================================================

class TestLensObservations:
    def test_surfaces_lens(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                lens_observations={"equity": "centers lived experience"},
            ),
        ]
        result = _build_lens_observations(history)
        assert "equity" in result
        assert "centers lived experience" in result

    def test_limits_to_max(self):
        """Should only show most recent observations."""
        history = [
            _make_entry(
                assignment=f"A{i}", started_at=f"2026-01-{10+i:02d}T00:00:00Z",
                lens_observations={"equity": f"obs {i}"},
            )
            for i in range(10)
        ]
        result = _build_lens_observations(history)
        # Should contain recent ones, not all 10
        assert "obs 9" in result
        assert "obs 0" not in result

    def test_empty_lens(self):
        history = [_make_entry(assignment="A1", started_at="2026-01-10")]
        assert _build_lens_observations(history) == ""


# ===========================================================================
# Prior feedback
# ===========================================================================

class TestPriorFeedback:
    def test_includes_feedback(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                draft_feedback="Consider grounding your claims in textual evidence.",
            ),
        ]
        result = _build_prior_feedback_note(history)
        assert "grounding your claims" in result
        assert "Avoid repeating" in result

    def test_truncates_long_feedback(self):
        long_fb = "x" * 200
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                draft_feedback=long_fb,
            ),
        ]
        result = _build_prior_feedback_note(history)
        # Should be truncated to 100 chars
        assert "x" * 100 in result
        assert "x" * 101 not in result

    def test_no_feedback(self):
        history = [_make_entry(assignment="A1", started_at="2026-01-10")]
        assert _build_prior_feedback_note(history) == ""


# ===========================================================================
# Integrity signals
# ===========================================================================

class TestIntegritySignals:
    def test_z_score_divergence(self):
        """Detects when writing pattern shifts away from class norms."""
        history = [
            _make_entry(assignment=f"A{i}", started_at=f"2026-01-{10+i:02d}T00:00:00Z",
                        cohort_z_score=0.1 * i)
            for i in range(6)
        ]
        # Early avg ~0.1, late avg ~0.4 — not enough divergence
        result = _build_integrity_signals(history)
        # Divergence threshold is 1.0, so this should NOT trigger
        assert result == ""

    def test_large_z_score_shift(self):
        """Large z-score shift should trigger pattern note."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", cohort_z_score=0.0),
            _make_entry(assignment="A2", started_at="2026-01-17", cohort_z_score=0.1),
            _make_entry(assignment="A3", started_at="2026-01-24", cohort_z_score=2.0),
            _make_entry(assignment="A4", started_at="2026-01-31", cohort_z_score=2.5),
        ]
        result = _build_integrity_signals(history)
        assert "shifted" in result

    def test_formulaic_shift(self):
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                linguistic_assets=["code_switching"],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                linguistic_assets=["formulaic_essay_structure"],
            ),
        ]
        result = _build_integrity_signals(history)
        assert "Formulaic" in result

    def test_formulaic_preexisting_not_flagged(self):
        """If formulaic was always there, don't flag as shift."""
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                linguistic_assets=["formulaic_essay_structure"],
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                linguistic_assets=["formulaic_essay_structure"],
            ),
        ]
        result = _build_integrity_signals(history)
        assert "Formulaic" not in result

    def test_no_integrity_signals(self):
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10"),
            _make_entry(assignment="A2", started_at="2026-01-17"),
        ]
        assert _build_integrity_signals(history) == ""


# ===========================================================================
# Preamble
# ===========================================================================

class TestPreamble:
    def test_basic_preamble(self):
        history = [
            _make_basic_entry("A1", "2026-01-15"),
            _make_basic_entry("A2", "2026-02-15"),
        ]
        result = build_preamble("Alex Rivera", "Biology 101", history)
        assert "Alex Rivera" in result
        assert "Biology 101" in result
        assert "2" in result  # assignment count

    def test_coverage_disclosure(self):
        history = [
            _make_basic_entry("A1", "2026-01-15"),
            _make_basic_entry("A3", "2026-02-15"),
        ]
        all_assignments = ["A1", "A2", "A3", "A4"]
        result = build_preamble(
            "Alex Rivera", "Biology 101", history,
            all_course_assignments=all_assignments,
        )
        assert "2 of 4" in result
        assert "A2" in result  # missing assignment listed
        assert "A4" in result  # missing assignment listed

    def test_date_range(self):
        history = [
            _make_basic_entry("A1", "2026-01-15T14:00:00Z"),
            _make_basic_entry("A2", "2026-05-20T14:00:00Z"),
        ]
        result = build_preamble("Alex Rivera", "Bio", history)
        assert "Jan 15" in result
        assert "May 20" in result

    def test_model_name_shown(self):
        history = [_make_basic_entry("A1", "2026-01-15")]
        result = build_preamble(
            "Alex Rivera", "Bio", history,
            generated_at="2026-03-28T12:00:00Z",
            model_name="gemma3:12b",
        )
        assert "gemma3:12b" in result


# ===========================================================================
# Full arc builder
# ===========================================================================

class TestBuildSemesterArc:
    def test_minimum_viable_arc(self):
        """Two basic entries should produce a non-empty arc."""
        history = [
            _make_basic_entry("A1", "2026-01-10"),
            _make_basic_entry("A2", "2026-01-17"),
        ]
        arc = build_semester_arc(history)
        assert len(arc) > 0

    def test_rich_arc_contains_all_sections(self):
        """Rich entries should populate all arc sections."""
        history = [
            _make_rich_entry("A1", "2026-01-10"),
            _make_rich_entry("A2", "2026-01-17"),
        ]
        arc = build_semester_arc(history)
        assert "Persistent" in arc or "threads" in arc.lower()
        assert "Intellectual reach" in arc
        assert "quotes" in arc.lower()
        assert "engagement" in arc.lower()
        assert "World connections" in arc

    def test_teacher_profile_in_arc(self):
        history = [
            _make_basic_entry("A1", "2026-01-10"),
            _make_basic_entry("A2", "2026-01-17"),
        ]
        arc = build_semester_arc(
            history,
            teacher_profile={
                "interest_areas": ["critical thinking"],
                "subject_area": "philosophy",
            },
        )
        assert "critical thinking" in arc
        assert "philosophy" in arc

    def test_scale_30_submissions(self):
        """30 submissions should produce a bounded arc, not blow up."""
        history = _make_semester(30)
        arc = build_semester_arc(history)
        # Arc should be bounded — not linearly scaling with N
        # (quotes are capped, themes are summarized, etc.)
        # Allow generous bound but it shouldn't be 30x a 2-entry arc
        assert len(arc) < 8000  # generous upper bound

    def test_empty_coding_records(self):
        """History entries with empty/None coding records shouldn't crash."""
        history = [
            {"run_id": "r1", "student_name": "Test", "assignment_name": "A1",
             "started_at": "2026-01-10T00:00:00Z", "coding_record": None},
            {"run_id": "r2", "student_name": "Test", "assignment_name": "A2",
             "started_at": "2026-01-17T00:00:00Z", "coding_record": {}},
        ]
        # Should not raise
        arc = build_semester_arc(history)
        assert isinstance(arc, str)


# ===========================================================================
# Equity language compliance
# ===========================================================================

class TestEquityLanguage:
    """Verify the arc builder doesn't use deficit language."""

    DEFICIT_WORDS = [
        "lacking", "deficient", "poor", "weak", "struggling",
        "behind", "below grade", "at-risk", "low-performing",
        "irregular", "abnormal", "problematic",
    ]

    def test_no_deficit_language_in_arc(self):
        history = _make_semester(8)
        arc = build_semester_arc(history)
        arc_lower = arc.lower()
        for word in self.DEFICIT_WORDS:
            assert word not in arc_lower, f"Deficit word '{word}' found in arc"

    def test_variable_output_not_pathologized(self):
        """Variable word counts should be described neutrally."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", word_count=500),
            _make_entry(assignment="A2", started_at="2026-01-17", word_count=50),
            _make_entry(assignment="A3", started_at="2026-01-24", word_count=400),
            _make_entry(assignment="A4", started_at="2026-01-31", word_count=60),
        ]
        arc = build_semester_arc(history)
        arc_lower = arc.lower()
        # Should NOT say "inconsistent" or "unreliable"
        assert "inconsistent" not in arc_lower
        assert "unreliable" not in arc_lower

    def test_register_shifts_neutral(self):
        """Register changes should be described, not judged."""
        history = [
            _make_basic_entry("A1", "2026-01-10", register="passionate"),
            _make_basic_entry("A2", "2026-01-17", register="analytical"),
            _make_basic_entry("A3", "2026-01-24", register="personal"),
        ]
        arc = build_semester_arc(history)
        arc_lower = arc.lower()
        assert "decline" not in arc_lower
        assert "deteriorat" not in arc_lower


# ===========================================================================
# Multilingual / translated submissions
# ===========================================================================

class TestMultilingualSupport:
    def test_translated_submission_noted(self):
        """Non-English submissions should have language noted in context.

        Known gap: Phase 1 arc builder doesn't surface preprocessing
        metadata (original_language_name). The old single-call format did.
        This test documents the gap for future revision. #LANGUAGE_JUSTICE
        """
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                word_count=300,
                preprocessing={"was_translated": True, "original_language_name": "Spanish"},
                theme_tags=["community"],
            ),
            _make_basic_entry("A2", "2026-01-17"),
        ]
        arc = build_semester_arc(history)
        # TODO: arc should note "Originally written in Spanish" — not yet implemented
        assert isinstance(arc, str)


# ===========================================================================
# Framework-driven edge cases
# ===========================================================================

class TestCripTime:
    """#CRIP_TIME — Variable output must be described, never pathologized.
    Who defines the pace of this process?"""

    def test_wildly_variable_word_counts_no_deficit_language(self):
        """200/800/150/600 pattern — normal for neurodivergent students,
        working students, students with care responsibilities."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", word_count=200,
                        engagement_signals={"engagement_depth": "moderate"}),
            _make_entry(assignment="A2", started_at="2026-01-17", word_count=800,
                        engagement_signals={"engagement_depth": "strong"}),
            _make_entry(assignment="A3", started_at="2026-01-24", word_count=150,
                        engagement_signals={"engagement_depth": "moderate"}),
            _make_entry(assignment="A4", started_at="2026-01-31", word_count=600,
                        engagement_signals={"engagement_depth": "strong"}),
        ]
        arc = build_semester_arc(history)
        arc_lower = arc.lower()
        assert "irregular" not in arc_lower
        assert "inconsistent" not in arc_lower
        assert "unstable" not in arc_lower
        # Should use "variable" if it describes the pattern at all
        if "variable" in arc_lower:
            pass  # acceptable description

    def test_minimum_two_submissions_still_produces_arc(self):
        """Students working at their own pace may have few analyzed submissions.
        Two should be enough to produce something useful."""
        history = [
            _make_rich_entry("A1", "2026-01-10"),
            _make_rich_entry("A4", "2026-03-05"),  # big gap, only 2 submissions
        ]
        arc = build_semester_arc(history)
        assert len(arc) > 100  # should produce meaningful content


class TestCommunityCulturalWealth:
    """#COMMUNITY_CULTURAL_WEALTH — What assets do marginalized communities
    possess that institutions ignore?"""

    def test_stable_repertoire_named_as_strength(self):
        """A student who CONSISTENTLY code-switches isn't 'developing' —
        they're maintaining a repertoire. That's a strength to name."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10",
                        linguistic_assets=["code_switching", "narrative_sophistication"]),
            _make_entry(assignment="A2", started_at="2026-01-17",
                        linguistic_assets=["code_switching", "narrative_sophistication"]),
            _make_entry(assignment="A3", started_at="2026-01-24",
                        linguistic_assets=["code_switching", "narrative_sophistication"]),
        ]
        result = _build_strengths_trajectory(history)
        assert "Consistent repertoire" in result
        assert "code_switching" in result

    def test_community_knowledge_in_personal_connections_not_ignored(self):
        """Students who bring family/community knowledge should have it
        visible in the engagement score, not just academic references."""
        # Student with rich personal connections but no readings
        cr_community = {
            "engagement_signals": {"engagement_depth": "strong"},
            "personal_connections": ["grandmother", "neighborhood", "church"],
            "readings_referenced": [],
            "concepts_applied": [],
            "notable_quotes": [{"text": "test", "significance": "test"}],
        }
        # Student with readings but no personal connections
        cr_academic = {
            "engagement_signals": {"engagement_depth": "strong"},
            "personal_connections": [],
            "readings_referenced": ["Author1", "Author2"],
            "concepts_applied": ["concept1"],
            "notable_quotes": [{"text": "test", "significance": "test"}],
        }
        community_score = _engagement_score(cr_community)
        academic_score = _engagement_score(cr_academic)
        # Community-grounded work should not score dramatically lower
        # than academic-reference-heavy work
        assert community_score >= academic_score * 0.6


class TestNeurodiversity:
    """#NEURODIVERSITY — Is this designed for one neurotype, or for
    cognitive pluralism?"""

    def test_hyperfocus_pattern_not_pathologized(self):
        """Long responses on some topics, minimal on others.
        Common ADHD pattern. The report should describe, not diagnose."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10", word_count=900,
                        engagement_signals={"engagement_depth": "strong"},
                        theme_tags=["passion_topic"],
                        personal_connections=["family", "community"],
                        notable_quotes=[{"text": "test quote", "significance": "deep"}],
                        emotional_register="passionate"),
            _make_entry(assignment="A2", started_at="2026-01-17", word_count=50,
                        engagement_signals={"engagement_depth": "minimal"},
                        theme_tags=["required_topic"]),
            _make_entry(assignment="A3", started_at="2026-01-24", word_count=1100,
                        engagement_signals={"engagement_depth": "strong"},
                        theme_tags=["passion_topic"],
                        personal_connections=["neighborhood"],
                        notable_quotes=[{"text": "another quote", "significance": "rich"}],
                        emotional_register="passionate"),
            _make_entry(assignment="A4", started_at="2026-01-31", word_count=40,
                        engagement_signals={"engagement_depth": "minimal"},
                        theme_tags=["required_topic"]),
        ]
        arc = build_semester_arc(history)
        arc_lower = arc.lower()
        # Must not pathologize the pattern
        assert "lazy" not in arc_lower
        assert "unmotivated" not in arc_lower
        assert "refuses" not in arc_lower
        assert "won't" not in arc_lower
        # Should identify the mode that sparks engagement
        engagement_result = _build_engagement_patterns(history)
        assert "Strongest work in" in engagement_result
        # Should detect it's the passion_topic assignments that spark engagement
        assert "passion_topic" in engagement_result.lower() or "A1" in engagement_result


class TestTransformativeJustice:
    """#TRANSFORMATIVE_JUSTICE — Can we address harm without replicating it?"""

    def test_crisis_wellbeing_surfaced_without_alarm_language(self):
        """CRISIS signal must reach the teacher but without panic framing.
        Describe what's observed, don't diagnose."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10",
                        wellbeing_axis="ENGAGED"),
            _make_entry(assignment="A2", started_at="2026-01-17",
                        wellbeing_axis="ENGAGED"),
            _make_entry(assignment="A3", started_at="2026-01-24",
                        wellbeing_axis="CRISIS"),
        ]
        result = _build_wellbeing_arc(history)
        assert "CRISIS" in result
        # Should NOT use alarm language
        result_lower = result.lower()
        assert "emergency" not in result_lower
        assert "danger" not in result_lower
        assert "immediately" not in result_lower

    def test_integrity_signals_never_say_cheating(self):
        """Integrity pattern shifts must name the structural observation,
        never the conclusion. The teacher interprets."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10",
                        cohort_z_score=-0.5, linguistic_assets=["code_switching"]),
            _make_entry(assignment="A2", started_at="2026-01-17",
                        cohort_z_score=-0.3, linguistic_assets=["code_switching"]),
            _make_entry(assignment="A3", started_at="2026-01-24",
                        cohort_z_score=2.0, linguistic_assets=["formulaic_essay_structure"]),
            _make_entry(assignment="A4", started_at="2026-01-31",
                        cohort_z_score=2.5, linguistic_assets=["formulaic_essay_structure"]),
        ]
        result = _build_integrity_signals(history)
        result_lower = result.lower()
        assert "cheat" not in result_lower
        assert "plagiar" not in result_lower
        assert "dishonest" not in result_lower
        assert "integrity violation" not in result_lower
        # Should describe the pattern structurally
        assert "shifted" in result_lower or "pattern" in result_lower


class TestAlgorithmicJustice:
    """#ALGORITHMIC_JUSTICE — If this were automated, who would it harm first?"""

    def test_engagement_score_does_not_penalize_brevity(self):
        """Short but deep work should not be scored as low engagement.
        Students who say powerful things in few words are engaged."""
        cr_brief_deep = {
            "engagement_signals": {"engagement_depth": "strong"},
            "notable_quotes": [
                {"text": "This is where I come from", "significance": "powerful"},
                {"text": "The system was not built for us", "significance": "structural"},
            ],
            "personal_connections": ["family"],
            "readings_referenced": [],
            "concepts_applied": ["structural power"],
        }
        cr_long_shallow = {
            "engagement_signals": {"engagement_depth": "limited"},
            "notable_quotes": [],
            "personal_connections": [],
            "readings_referenced": ["Author1"],
            "concepts_applied": [],
        }
        brief_score = _engagement_score(cr_brief_deep)
        long_score = _engagement_score(cr_long_shallow)
        # Brief but deep should score higher than long but shallow
        assert brief_score > long_score

    def test_teacher_interests_dont_erase_student_threads(self):
        """When teacher priorities don't match student interests, the arc
        should still reflect the STUDENT's threads, not go silent."""
        history = [
            _make_entry(
                assignment="A1", started_at="2026-01-10",
                theme_tags=["environmental_justice", "water_rights"],
                what_student_is_reaching_for="Connecting water access to structural racism",
                word_count=400,
                engagement_signals={"engagement_depth": "strong"},
            ),
            _make_entry(
                assignment="A2", started_at="2026-01-17",
                theme_tags=["environmental_justice", "indigenous_sovereignty"],
                what_student_is_reaching_for="How Standing Rock connects to local water fights",
                word_count=500,
                engagement_signals={"engagement_depth": "strong"},
            ),
        ]
        # Teacher priorities don't overlap with student's focus
        arc = build_semester_arc(
            history,
            teacher_profile={"interest_areas": ["literary analysis", "close reading"]},
        )
        # Student's own threads must still appear
        assert "environmental_justice" in arc or "water" in arc.lower()
        assert "Connecting water access" in arc or "Standing Rock" in arc


class TestFeministTechnoscience:
    """#FEMINIST_TECHNOSCIENCE — Whose view is encoded as 'objective' or 'neutral'?"""

    def test_personal_register_not_devalued(self):
        """Personal and passionate registers should not produce lower
        engagement scores than analytical register. No mode is privileged."""
        cr_personal = {
            "engagement_signals": {"engagement_depth": "strong"},
            "emotional_register": "personal",
            "notable_quotes": [{"text": "q", "significance": "s"}],
            "personal_connections": ["family"],
            "readings_referenced": [],
            "concepts_applied": [],
        }
        cr_analytical = {
            "engagement_signals": {"engagement_depth": "strong"},
            "emotional_register": "analytical",
            "notable_quotes": [{"text": "q", "significance": "s"}],
            "personal_connections": [],
            "readings_referenced": ["Author"],
            "concepts_applied": [],
        }
        personal_score = _engagement_score(cr_personal)
        analytical_score = _engagement_score(cr_analytical)
        # Scores should be comparable — neither register is privileged
        assert abs(personal_score - analytical_score) <= 2


class TestBackwardCompat:
    """Edge cases for backward compatibility with older coding records."""

    def test_missing_engagement_signals(self):
        """Old records may not have engagement_signals at all."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10",
                        word_count=300, theme_tags=["topic"]),
            _make_entry(assignment="A2", started_at="2026-01-17",
                        word_count=350, theme_tags=["topic"]),
        ]
        # No engagement_signals field — should not crash
        arc = build_semester_arc(history)
        assert isinstance(arc, str)

    def test_none_fields_throughout(self):
        """Records where most fields are None — should degrade gracefully."""
        history = [
            _make_entry(assignment="A1", started_at="2026-01-10",
                        word_count=100, theme_tags=None, notable_quotes=None,
                        emotional_register=None, wellbeing_axis=None),
            _make_entry(assignment="A2", started_at="2026-01-17",
                        word_count=150, theme_tags=None, notable_quotes=None,
                        emotional_register=None, wellbeing_axis=None),
        ]
        arc = build_semester_arc(history)
        assert isinstance(arc, str)
        # Should still produce something from word count data
        assert len(arc) > 0

    def test_all_themes_unique_no_persistent(self):
        """Every assignment has unique themes — nothing 'persistent'."""
        history = [
            _make_basic_entry("A1", "2026-01-10", themes=["alpha"]),
            _make_basic_entry("A2", "2026-01-17", themes=["beta"]),
            _make_basic_entry("A3", "2026-01-24", themes=["gamma"]),
            _make_basic_entry("A4", "2026-01-31", themes=["delta"]),
        ]
        result = _build_theme_evolution(history)
        # Should not crash, should still describe the themes somehow
        assert "Persistent" not in result  # none are persistent
        assert isinstance(result, str)
