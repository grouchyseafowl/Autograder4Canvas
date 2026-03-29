"""
Prompts module — unit tests.

Tests that all prompt constants:
  - Exist and are non-empty strings
  - Contain required format placeholders (no missing variables)
  - Don't accidentally contain bare Python template syntax that would fail str.format()

These are regression tests against accidental truncation or placeholder typos
that would cause silent failures in the pipeline (empty prompts, KeyError on format).

Run with: python -m pytest tests/test_prompts.py -v
"""

import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

import insights.prompts as prompts


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def placeholders_in(template: str) -> set[str]:
    """Extract all {placeholder_name} tokens from a format string.
    Skips doubled braces {{ }} (escaped braces).
    """
    # Replace {{ and }} with placeholder tokens to avoid matching them
    cleaned = template.replace("{{", "\x00").replace("}}", "\x01")
    return set(re.findall(r"\{(\w+)\}", cleaned))


# ---------------------------------------------------------------------------
# Module-level constants existence
# ---------------------------------------------------------------------------

class TestConstantsExist:
    @pytest.mark.parametrize("name", [
        "SYSTEM_PROMPT",
        "CLASS_READING_SYSTEM_ADDENDUM",
        "CLASS_READING_PROMPT",
        "CLASS_READING_SMALL_PROMPT",
        "CLASS_READING_MERGE_PROMPT",
        "COMPREHENSION_PROMPT",
        "INTERPRETATION_PROMPT",
    ])
    def test_constant_exists(self, name):
        assert hasattr(prompts, name), f"prompts.{name} not found"

    @pytest.mark.parametrize("name", [
        "SYSTEM_PROMPT",
        "CLASS_READING_SYSTEM_ADDENDUM",
        "CLASS_READING_PROMPT",
        "CLASS_READING_SMALL_PROMPT",
        "CLASS_READING_MERGE_PROMPT",
        "COMPREHENSION_PROMPT",
        "INTERPRETATION_PROMPT",
    ])
    def test_constant_is_nonempty_string(self, name):
        value = getattr(prompts, name)
        assert isinstance(value, str), f"prompts.{name} is not a str"
        assert len(value.strip()) > 0, f"prompts.{name} is empty"


# ---------------------------------------------------------------------------
# SYSTEM_PROMPT content
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_instructs_json_output(self):
        assert "JSON" in prompts.SYSTEM_PROMPT

    def test_instructs_use_student_names(self):
        assert "student names" in prompts.SYSTEM_PROMPT.lower() or \
               "student name" in prompts.SYSTEM_PROMPT.lower()

    def test_course_content_not_wellbeing_guidance_present(self):
        """Critical equity guard: distinguish disturbing subject matter from distress."""
        assert "course material" in prompts.SYSTEM_PROMPT.lower()

    def test_mentions_verbatim_quotes(self):
        assert "verbatim" in prompts.SYSTEM_PROMPT.lower() or \
               "quote" in prompts.SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# CLASS_READING_PROMPT placeholders
# ---------------------------------------------------------------------------

class TestClassReadingPrompt:
    REQUIRED = {"assignment_prompt", "course_name", "teacher_context", "submissions_block"}

    def test_required_placeholders_present(self):
        found = placeholders_in(prompts.CLASS_READING_PROMPT)
        missing = self.REQUIRED - found
        assert not missing, f"CLASS_READING_PROMPT missing placeholders: {missing}"

    def test_format_with_all_placeholders(self):
        """Should not raise KeyError when all placeholders are supplied."""
        result = prompts.CLASS_READING_PROMPT.format(
            assignment_prompt="Write about intersectionality.",
            course_name="Ethnic Studies 10",
            teacher_context="",
            submissions_block="[Student submissions here]",
        )
        assert len(result) > 0

    def test_mentions_three_orientations(self):
        """Asset/Threshold/Connection orientations must be present."""
        text = prompts.CLASS_READING_PROMPT.upper()
        assert "ASSET" in text
        assert "THRESHOLD" in text
        assert "CONNECTION" in text


# ---------------------------------------------------------------------------
# CLASS_READING_SMALL_PROMPT placeholders
# ---------------------------------------------------------------------------

class TestClassReadingSmallPrompt:
    REQUIRED = {"assignment_prompt", "course_name", "teacher_context", "submissions_block"}

    def test_required_placeholders_present(self):
        found = placeholders_in(prompts.CLASS_READING_SMALL_PROMPT)
        missing = self.REQUIRED - found
        assert not missing, f"CLASS_READING_SMALL_PROMPT missing: {missing}"

    def test_format_does_not_raise(self):
        prompts.CLASS_READING_SMALL_PROMPT.format(
            assignment_prompt="Reflect on the reading.",
            course_name="Bio 1",
            teacher_context="",
            submissions_block="[submissions]",
        )


# ---------------------------------------------------------------------------
# CLASS_READING_MERGE_PROMPT placeholders
# ---------------------------------------------------------------------------

class TestClassReadingMergePrompt:
    def test_group_readings_placeholder_present(self):
        found = placeholders_in(prompts.CLASS_READING_MERGE_PROMPT)
        assert "group_readings" in found

    def test_format_does_not_raise(self):
        prompts.CLASS_READING_MERGE_PROMPT.format(group_readings="[Group 1 reading]")


# ---------------------------------------------------------------------------
# COMPREHENSION_PROMPT placeholders
# ---------------------------------------------------------------------------

class TestComprehensionPrompt:
    REQUIRED = {
        "student_name",
        "assignment_prompt",
        "class_context",
        "linguistic_context",
        "vader_compound",
        "vader_polarity",
        "top_emotions",
        "keyword_hits",
        "cluster_id",
        "signal_matrix_context",
        "submission_text",
        "profile_fragment",
    }

    def test_required_placeholders_present(self):
        found = placeholders_in(prompts.COMPREHENSION_PROMPT)
        missing = self.REQUIRED - found
        assert not missing, f"COMPREHENSION_PROMPT missing placeholders: {missing}"

    def test_format_does_not_raise(self):
        prompts.COMPREHENSION_PROMPT.format(
            student_name="Aaliyah Johnson",
            assignment_prompt="Reflect on this week's reading.",
            class_context="",
            linguistic_context="",
            vader_compound="0.2",
            vader_polarity="positive",
            top_emotions="",
            keyword_hits="none",
            cluster_id="1",
            signal_matrix_context="",
            submission_text="This week I thought about intersectionality.",
            profile_fragment="",
        )


# ---------------------------------------------------------------------------
# INTERPRETATION_PROMPT placeholders
# ---------------------------------------------------------------------------

class TestInterpretationPrompt:
    REQUIRED = {
        "student_name",
        "comprehension_json",
        "assignment_prompt",
        "teacher_interests",
        "submission_text",
        "profile_fragment",
        "lens_fragment",
    }

    def test_required_placeholders_present(self):
        found = placeholders_in(prompts.INTERPRETATION_PROMPT)
        missing = self.REQUIRED - found
        assert not missing, f"INTERPRETATION_PROMPT missing placeholders: {missing}"

    def test_format_does_not_raise(self):
        prompts.INTERPRETATION_PROMPT.format(
            student_name="Marcus Okonkwo",
            comprehension_json='{"readings_referenced": []}',
            assignment_prompt="Reflect on the reading.",
            teacher_interests="",
            submission_text="I think about power a lot.",
            profile_fragment="",
            lens_fragment="",
        )

    def test_mentions_emotional_register_options(self):
        """Prompt must enumerate the valid emotional_register values."""
        assert "analytical" in prompts.INTERPRETATION_PROMPT
        assert "passionate" in prompts.INTERPRETATION_PROMPT
        assert "disengaged" in prompts.INTERPRETATION_PROMPT


# ---------------------------------------------------------------------------
# CLASS_READING_SYSTEM_ADDENDUM
# ---------------------------------------------------------------------------

class TestClassReadingSystemAddendum:
    def test_mentions_aave(self):
        assert "AAVE" in prompts.CLASS_READING_SYSTEM_ADDENDUM

    def test_affirms_non_standard_english(self):
        text = prompts.CLASS_READING_SYSTEM_ADDENDUM.lower()
        assert "asset" in text or "valid" in text
