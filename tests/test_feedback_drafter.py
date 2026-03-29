"""
feedback_drafter.py — unit tests for pure (non-LLM) functions.

Tests data-sufficiency checks, prompt fragment builders, and the
no-backend fast path in FeedbackDrafter.draft_feedback.

No MLX, no LLM calls.

Run with: python -m pytest tests/test_feedback_drafter.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.feedback_drafter import (
    FeedbackDrafter,
    _build_length_fragment,
    _build_preprocessing_fragment,
    _build_style_fragment,
    _build_wellbeing_context,
    _coding_has_enough_data,
    _format_list,
    _format_quotes,
    _safe_confidence,
)


# ---------------------------------------------------------------------------
# _safe_confidence
# ---------------------------------------------------------------------------

class TestSafeConfidence:
    def test_valid_float(self):
        assert _safe_confidence(0.8) == pytest.approx(0.8)

    def test_clips_above_1(self):
        assert _safe_confidence(1.5) == 1.0

    def test_clips_below_0(self):
        assert _safe_confidence(-0.3) == 0.0

    def test_string_float(self):
        assert _safe_confidence("0.75") == pytest.approx(0.75)

    def test_none_returns_fallback(self):
        assert _safe_confidence(None) == pytest.approx(0.7)

    def test_garbage_string_returns_fallback(self):
        assert _safe_confidence("not a number") == pytest.approx(0.7)

    def test_zero_valid(self):
        assert _safe_confidence(0) == 0.0

    def test_one_valid(self):
        assert _safe_confidence(1) == 1.0


# ---------------------------------------------------------------------------
# _coding_has_enough_data
# ---------------------------------------------------------------------------

class TestCodingHasEnoughData:
    def test_empty_record_insufficient(self):
        assert _coding_has_enough_data({}) is False

    def test_theme_tags_only_insufficient(self):
        assert _coding_has_enough_data({"theme_tags": ["power"]}) is False

    def test_two_fields_sufficient(self):
        assert _coding_has_enough_data({
            "theme_tags": ["power"],
            "notable_quotes": [{"text": "quote", "significance": "sig"}],
        }) is True

    def test_disengaged_register_does_not_count(self):
        """emotional_register='disengaged' should NOT count toward the threshold."""
        result = _coding_has_enough_data({
            "theme_tags": ["minimal"],
            "emotional_register": "disengaged",
        })
        assert result is False

    def test_non_disengaged_register_counts(self):
        """Any register except 'disengaged' counts as a populated field."""
        assert _coding_has_enough_data({
            "theme_tags": ["power"],
            "emotional_register": "passionate",
        }) is True

    def test_all_fields_populated(self):
        record = {
            "theme_tags": ["power"],
            "notable_quotes": [{"text": "q", "significance": "s"}],
            "concepts_applied": ["intersectionality"],
            "personal_connections": ["grandmother's story"],
            "readings_referenced": ["Crenshaw 1989"],
            "emotional_register": "analytical",
        }
        assert _coding_has_enough_data(record) is True

    def test_empty_lists_do_not_count(self):
        """Empty lists are falsy and should not increment the counter."""
        assert _coding_has_enough_data({
            "theme_tags": [],
            "notable_quotes": [],
            "concepts_applied": ["intersectionality"],
            "personal_connections": ["family history"],
        }) is True  # concepts + personal_connections = 2


# ---------------------------------------------------------------------------
# _format_list
# ---------------------------------------------------------------------------

class TestFormatList:
    def test_empty_returns_none(self):
        assert _format_list([]) == "none"

    def test_single_item(self):
        assert _format_list(["power"]) == "power"

    def test_multiple_items_comma_separated(self):
        result = _format_list(["power", "identity", "resistance"])
        assert "power" in result
        assert "identity" in result

    def test_truncated_to_5(self):
        items = [f"item{i}" for i in range(8)]
        result = _format_list(items)
        assert "item6" not in result
        assert "item4" in result


# ---------------------------------------------------------------------------
# _format_quotes
# ---------------------------------------------------------------------------

class TestFormatQuotes:
    def test_empty_returns_none(self):
        assert _format_quotes([]) == "none"

    def test_dict_quote_formatted(self):
        quotes = [{"text": "The law sees race or gender, not the combination."}]
        result = _format_quotes(quotes)
        assert "The law sees race or gender" in result

    def test_string_quote_formatted(self):
        result = _format_quotes(["Just a plain string quote."])
        assert "Just a plain string quote." in result

    def test_dict_without_text_skipped(self):
        quotes = [{"significance": "only sig, no text"}]
        result = _format_quotes(quotes)
        assert result == "none"

    def test_max_3_quotes(self):
        quotes = [{"text": f"Quote {i}"} for i in range(5)]
        result = _format_quotes(quotes)
        # Only first 3 should appear
        assert "Quote 3" not in result
        assert "Quote 2" in result


# ---------------------------------------------------------------------------
# _build_preprocessing_fragment
# ---------------------------------------------------------------------------

class TestBuildPreprocessingFragment:
    def test_none_returns_empty(self):
        assert _build_preprocessing_fragment(None) == ""

    def test_no_flags_returns_empty(self):
        assert _build_preprocessing_fragment({"was_translated": False}) == ""

    def test_translated_includes_language(self):
        meta = {"was_translated": True, "original_language_name": "Spanish"}
        result = _build_preprocessing_fragment(meta)
        assert "Spanish" in result
        assert "multilingual" in result.lower() or "strength" in result.lower()

    def test_translated_unknown_language(self):
        meta = {"was_translated": True}
        result = _build_preprocessing_fragment(meta)
        assert "another language" in result

    def test_transcribed_acknowledged_positively(self):
        meta = {"was_transcribed": True}
        result = _build_preprocessing_fragment(meta)
        assert "audio" in result.lower() or "oral" in result.lower()
        assert "strength" in result.lower() or "nuance" in result.lower()

    def test_both_flags_both_included(self):
        meta = {"was_translated": True, "original_language_name": "Tagalog",
                "was_transcribed": True}
        result = _build_preprocessing_fragment(meta)
        assert "Tagalog" in result
        assert "audio" in result.lower() or "oral" in result.lower()


# ---------------------------------------------------------------------------
# _build_wellbeing_context
# ---------------------------------------------------------------------------

class TestBuildWellbeingContext:
    def test_none_axis_no_wellbeing_section(self):
        record = {"wellbeing_axis": "NONE"}
        result = _build_wellbeing_context(record)
        assert "WELLBEING-AWARE" not in result

    def test_crisis_axis_adds_warmth_instruction(self):
        record = {"wellbeing_axis": "CRISIS"}
        result = _build_wellbeing_context(record)
        assert "WELLBEING-AWARE" in result
        assert "crisis" in result.lower()

    def test_burnout_axis_adds_warmth_instruction(self):
        record = {"wellbeing_axis": "BURNOUT"}
        result = _build_wellbeing_context(record)
        assert "WELLBEING-AWARE" in result
        assert "burnout" in result.lower()

    def test_crisis_does_not_leak_to_student(self):
        """The wellbeing note must instruct NOT to reference the signal."""
        record = {"wellbeing_axis": "CRISIS"}
        result = _build_wellbeing_context(record)
        assert "NOT reference" in result or "not reference" in result.lower()

    def test_observation_included_in_context(self):
        record = {
            "wellbeing_axis": "NONE",
            "observation": "Student demonstrates nuanced analysis of power structures.",
        }
        result = _build_wellbeing_context(record)
        assert "Student demonstrates" in result

    def test_observation_marked_not_for_student(self):
        """Observation context is for teacher awareness only."""
        record = {
            "wellbeing_axis": "NONE",
            "observation": "Observation text here.",
        }
        result = _build_wellbeing_context(record)
        assert "NOT for the student" in result or "not for the student" in result.lower() \
               or "awareness" in result.lower()

    def test_reaching_for_included(self):
        record = {
            "wellbeing_axis": "NONE",
            "what_student_is_reaching_for": "A more structural analysis of power.",
        }
        result = _build_wellbeing_context(record)
        assert "structural analysis" in result

    def test_checkin_flag_adds_context(self):
        record = {
            "wellbeing_axis": "ENGAGED",
            "checkin_flag": True,
            "checkin_reasoning": "Mentions 'I can't sleep' in passing.",
        }
        result = _build_wellbeing_context(record)
        assert "CHECK-IN" in result
        assert "can't sleep" in result

    def test_checkin_flag_student_never_sees(self):
        """Check-in note must explicitly say the student shouldn't see it."""
        record = {
            "wellbeing_axis": "ENGAGED",
            "checkin_flag": True,
            "checkin_reasoning": "Subtle signal.",
        }
        result = _build_wellbeing_context(record)
        assert "NOT reference" in result or "not reference" in result.lower()

    def test_disengaged_register_adds_tone_guidance(self):
        record = {
            "wellbeing_axis": "NONE",
            "emotional_register": "disengaged",
        }
        result = _build_wellbeing_context(record)
        assert "TONE GUIDANCE" in result or "disengagement" in result.lower()

    def test_disengaged_register_with_burnout_no_double_note(self):
        """If axis is BURNOUT, the disengaged tone guidance should NOT fire."""
        record = {
            "wellbeing_axis": "BURNOUT",
            "emotional_register": "disengaged",
        }
        result = _build_wellbeing_context(record)
        # BURNOUT should fire, but "TONE GUIDANCE" disengaged branch should not
        assert "WELLBEING-AWARE" in result
        assert "TONE GUIDANCE" not in result

    def test_empty_record_returns_empty(self):
        assert _build_wellbeing_context({}) == ""


# ---------------------------------------------------------------------------
# _build_style_fragment
# ---------------------------------------------------------------------------

class TestBuildStyleFragment:
    def test_warm_style(self):
        result = _build_style_fragment("warm")
        assert "warm" in result.lower()

    def test_direct_style(self):
        result = _build_style_fragment("direct")
        assert "clear" in result.lower() or "direct" in result.lower() or "specific" in result.lower()

    def test_socratic_style(self):
        result = _build_style_fragment("socratic")
        assert "question" in result.lower()

    def test_unknown_style_falls_back_to_warm(self):
        result = _build_style_fragment("nonexistent")
        assert "warm" in result.lower()

    def test_lens_focused_with_lens(self):
        lens = {"power": "Who has power?"}
        result = _build_style_fragment("lens_focused", lens)
        assert "power" in result


# ---------------------------------------------------------------------------
# _build_length_fragment
# ---------------------------------------------------------------------------

class TestBuildLengthFragment:
    def test_brief(self):
        result = _build_length_fragment("brief")
        assert "2" in result or "3" in result or "sentence" in result.lower()

    def test_moderate(self):
        result = _build_length_fragment("moderate")
        assert "4" in result or "6" in result or "sentence" in result.lower()

    def test_detailed(self):
        result = _build_length_fragment("detailed")
        assert "paragraph" in result.lower() or "6" in result or "8" in result

    def test_unknown_falls_back_to_moderate(self):
        result = _build_length_fragment("nonexistent")
        assert "sentence" in result.lower() or "4" in result


# ---------------------------------------------------------------------------
# FeedbackDrafter.draft_feedback (no-backend path)
# ---------------------------------------------------------------------------

class TestFeedbackDrafterNoBackend:
    """Tests the no-backend fast path (backend=None returns confidence=0.0)."""

    RICH_RECORD = {
        "student_id": "s001",
        "student_name": "Aaliyah Johnson",
        "theme_tags": ["power and resistance", "personal narrative"],
        "notable_quotes": [{"text": "The law excludes intersectional identity.", "significance": "Core argument."}],
        "concepts_applied": ["intersectionality"],
        "emotional_register": "passionate",
        "word_count": 310,
    }

    THIN_RECORD = {
        "student_id": "s002",
        "student_name": "Marcus Okonkwo",
        "word_count": 15,
    }

    def test_no_backend_returns_draft_feedback(self):
        drafter = FeedbackDrafter()
        result = drafter.draft_feedback(
            self.RICH_RECORD,
            assignment_prompt="Reflect on this week's reading.",
            backend=None,
        )
        assert result.student_id == "s001"
        assert result.confidence == 0.0
        assert "Manual review" in result.feedback_text

    def test_thin_record_returns_low_confidence(self):
        drafter = FeedbackDrafter()
        result = drafter.draft_feedback(
            self.THIN_RECORD,
            assignment_prompt="Reflect on this week's reading.",
            backend=None,
        )
        assert result.confidence == 0.0
        assert result.student_id == "s002"

    def test_returns_draft_feedback_model(self):
        from insights.models import DraftFeedback
        drafter = FeedbackDrafter()
        result = drafter.draft_feedback(
            self.THIN_RECORD,
            assignment_prompt="Reflect.",
            backend=None,
        )
        assert isinstance(result, DraftFeedback)

    def test_insufficient_data_returns_zero_confidence(self):
        drafter = FeedbackDrafter()
        result = drafter.draft_feedback(
            {"student_id": "s003", "student_name": "Jordan Reyes"},
            assignment_prompt="Reflect.",
            backend=None,
        )
        assert result.confidence == 0.0

    def test_student_name_preserved(self):
        drafter = FeedbackDrafter()
        result = drafter.draft_feedback(
            self.RICH_RECORD,
            assignment_prompt="Reflect.",
            backend=None,
        )
        assert result.student_name == "Aaliyah Johnson"
