"""
Data model unit tests.

Pure unit tests — no LLM, no DB, no MLX.
Tests pydantic validators, field defaults, and backward-compat migrations.

Run with: python -m pytest tests/test_models.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from pydantic import ValidationError

from insights.models import (
    ConcernRecord,
    GuidedSynthesisResult,
    PreprocessingMetadata,
    QuoteRecord,
    SubmissionCodingRecord,
    SynthesisReport,
    TeacherAnalysisProfile,
    Theme,
)


# ---------------------------------------------------------------------------
# QuoteRecord
# ---------------------------------------------------------------------------

class TestQuoteRecord:
    def test_basic_construction(self):
        q = QuoteRecord(text="This is a quote.", significance="Shows engagement.")
        assert q.text == "This is a quote."
        assert q.significance == "Shows engagement."

    def test_requires_text(self):
        with pytest.raises(ValidationError):
            QuoteRecord(significance="oops")

    def test_requires_significance(self):
        with pytest.raises(ValidationError):
            QuoteRecord(text="some text")


# ---------------------------------------------------------------------------
# ConcernRecord
# ---------------------------------------------------------------------------

class TestConcernRecord:
    def test_default_confidence(self):
        c = ConcernRecord(
            flagged_passage="I don't want to be here.",
            surrounding_context="Student wrote two paragraphs then this.",
            why_flagged="Possible disengagement or distress.",
        )
        assert c.confidence == 0.5

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            ConcernRecord(
                flagged_passage="x",
                surrounding_context="y",
                why_flagged="z",
                confidence=1.5,
            )

    def test_confidence_at_zero(self):
        c = ConcernRecord(
            flagged_passage="x",
            surrounding_context="y",
            why_flagged="z",
            confidence=0.0,
        )
        assert c.confidence == 0.0

    def test_confidence_at_one(self):
        c = ConcernRecord(
            flagged_passage="x",
            surrounding_context="y",
            why_flagged="z",
            confidence=1.0,
        )
        assert c.confidence == 1.0


# ---------------------------------------------------------------------------
# SubmissionCodingRecord
# ---------------------------------------------------------------------------

class TestSubmissionCodingRecord:
    def test_minimal_construction(self):
        r = SubmissionCodingRecord(student_id="s001", student_name="Aaliyah Johnson")
        assert r.student_id == "s001"
        assert r.student_name == "Aaliyah Johnson"

    def test_defaults(self):
        r = SubmissionCodingRecord(student_id="s001", student_name="Aaliyah Johnson")
        assert r.theme_tags == []
        assert r.theme_confidence == {}
        assert r.notable_quotes == []
        assert r.emotional_register == ""
        assert r.readings_referenced == []
        assert r.concerns == []
        assert r.word_count == 0
        assert r.wellbeing_axis is None
        assert r.wellbeing_confidence == 0.0
        assert r.checkin_flag is None
        assert r.observation is None

    def test_vader_sentiment_migration(self):
        """Backward compat: vader_sentiment key should migrate to emotional_register_score."""
        r = SubmissionCodingRecord(
            student_id="s002",
            student_name="Marcus Okonkwo",
            vader_sentiment=0.75,
        )
        assert r.emotional_register_score == 0.75

    def test_vader_migration_does_not_override_explicit(self):
        """If both vader_sentiment and emotional_register_score present, keep set value."""
        r = SubmissionCodingRecord(
            student_id="s003",
            student_name="Priya Nair",
            vader_sentiment=0.5,
            emotional_register_score=0.8,
        )
        # model_validator uses setdefault, so explicit value wins
        assert r.emotional_register_score == 0.8

    def test_full_population(self):
        r = SubmissionCodingRecord(
            student_id="s004",
            student_name="Destiny Cruz",
            theme_tags=["power and resistance", "personal narrative"],
            theme_confidence={"power and resistance": 0.9, "personal narrative": 0.7},
            emotional_register="passionate",
            emotional_notes="Student writes with urgency about injustice.",
            readings_referenced=["Crenshaw (1989)"],
            concepts_applied=["intersectionality"],
            personal_connections=["grandmother's experience"],
            word_count=320,
            wellbeing_axis="ENGAGED",
            wellbeing_confidence=0.8,
        )
        assert r.theme_tags == ["power and resistance", "personal narrative"]
        assert r.emotional_register == "passionate"
        assert r.wellbeing_axis == "ENGAGED"
        assert r.word_count == 320

    def test_linguistic_assets_default_empty(self):
        r = SubmissionCodingRecord(student_id="s005", student_name="Jordan Reyes")
        assert r.linguistic_assets == []

    def test_is_possibly_truncated_default_false(self):
        r = SubmissionCodingRecord(student_id="s006", student_name="Kenji Watanabe")
        assert r.is_possibly_truncated is False
        assert r.truncation_note == ""


# ---------------------------------------------------------------------------
# SynthesisReport
# ---------------------------------------------------------------------------

class TestSynthesisReport:
    def test_basic_construction(self):
        r = SynthesisReport(sections={"themes": "Students engaged with intersectionality."})
        assert "themes" in r.sections

    def test_numeric_sections_filtered(self):
        """8B models sometimes write numeric values inside sections dict — filter them."""
        r = SynthesisReport(
            sections={
                "themes": "Good engagement.",
                "confidence": 0.87,   # numeric — should be stripped
                "concerns": "None noted.",
            }
        )
        assert "confidence" not in r.sections
        assert "themes" in r.sections
        assert "concerns" in r.sections

    def test_int_section_also_filtered(self):
        r = SynthesisReport(sections={"count": 5, "summary": "Short class."})
        assert "count" not in r.sections
        assert "summary" in r.sections

    def test_non_string_coerced(self):
        """Non-string, non-numeric values are coerced to str."""
        r = SynthesisReport(sections={"meta": ["list", "value"]})
        assert isinstance(r.sections["meta"], str)

    def test_empty_sections(self):
        r = SynthesisReport(sections={})
        assert r.sections == {}
        assert r.confidence == 0.0


# ---------------------------------------------------------------------------
# Theme
# ---------------------------------------------------------------------------

class TestTheme:
    def test_basic_construction(self):
        t = Theme(name="Power and resistance", frequency=5)
        assert t.name == "Power and resistance"
        assert t.frequency == 5

    def test_sub_themes_none(self):
        t = Theme(name="Power and resistance")
        assert t.sub_themes is None

    def test_sub_themes_string_list_passthrough(self):
        t = Theme(name="Resistance", sub_themes=["active resistance", "passive resistance"])
        assert t.sub_themes == ["active resistance", "passive resistance"]

    def test_sub_themes_dict_list_coercion(self):
        """Larger models return sub_themes as [{name:..., description:...}] — coerce to name strings."""
        t = Theme(
            name="Power",
            sub_themes=[
                {"name": "Institutional power", "description": "..."},
                {"name": "Interpersonal power"},
                {"theme": "Structural violence"},
            ],
        )
        assert t.sub_themes == ["Institutional power", "Interpersonal power", "Structural violence"]

    def test_sub_themes_empty_list_returns_none(self):
        """Empty list should be coerced to None (falsy branch)."""
        t = Theme(name="Empty", sub_themes=[])
        assert t.sub_themes is None

    def test_sub_themes_mixed_coercion(self):
        """Mix of dicts and strings — all coerced to str."""
        t = Theme(
            name="Mixed",
            sub_themes=[{"name": "Structural"}, "individual agency"],
        )
        assert t.sub_themes == ["Structural", "individual agency"]


# ---------------------------------------------------------------------------
# TeacherAnalysisProfile
# ---------------------------------------------------------------------------

class TestTeacherAnalysisProfile:
    def test_defaults(self):
        p = TeacherAnalysisProfile()
        assert p.theme_renames == {}
        assert p.theme_splits == []
        assert p.concern_sensitivity == {}
        assert p.interest_areas == []
        assert p.subject_area == "general"
        assert p.feedback_style == "warm"
        assert p.feedback_length == "moderate"
        assert p.custom_patterns == {}
        assert p.custom_concern_patterns == []
        assert p.disabled_default_patterns == []
        assert p.custom_strength_patterns == []
        assert p.edit_history == []

    def test_round_trip(self):
        p = TeacherAnalysisProfile(
            subject_area="ethnic studies",
            interest_areas=["power", "identity"],
            theme_renames={"racism": "structural racism"},
        )
        data = p.model_dump()
        restored = TeacherAnalysisProfile.model_validate(data)
        assert restored.subject_area == "ethnic studies"
        assert restored.theme_renames == {"racism": "structural racism"}
        assert restored.interest_areas == ["power", "identity"]


# ---------------------------------------------------------------------------
# PreprocessingMetadata
# ---------------------------------------------------------------------------

class TestPreprocessingMetadata:
    def test_defaults(self):
        m = PreprocessingMetadata()
        assert m.was_translated is False
        assert m.was_transcribed is False
        assert m.original_language_name is None
        assert m.needs_teacher_comment is False

    def test_translated(self):
        m = PreprocessingMetadata(was_translated=True, original_language_name="Spanish")
        assert m.was_translated is True
        assert m.original_language_name == "Spanish"


# ---------------------------------------------------------------------------
# GuidedSynthesisResult
# ---------------------------------------------------------------------------

class TestGuidedSynthesisResult:
    def test_defaults(self):
        g = GuidedSynthesisResult()
        assert g.concern_patterns == []
        assert g.engagement_highlights == []
        assert g.tensions == []
        assert g.class_temperature == ""
        assert g.calls_completed == 0
        assert g.calls_attempted == 0
        assert g.cloud_narrative == ""

    def test_partial_results_valid(self):
        """Partial results (some calls completed) are still valid models."""
        g = GuidedSynthesisResult(
            concern_patterns=[{"student": "s001", "pattern": "burnout"}],
            calls_completed=1,
            calls_attempted=4,
        )
        assert len(g.concern_patterns) == 1
        assert g.calls_completed == 1
