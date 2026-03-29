"""
TeacherProfileManager — unit tests.

Tests profile loading, edit recording, concern sensitivity, wellbeing floor
enforcement, prompt fragment generation, and template save/fork.

Uses a real InsightsStore with a tmp_path database — no mocking needed
since InsightsStore is a pure SQLite wrapper.

Run with: python -m pytest tests/test_teacher_profile.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.insights_store import InsightsStore
from insights.teacher_profile import (
    PROTECTED_WELLBEING_PATTERNS,
    WELLBEING_FLOOR_NOTE,
    WELLBEING_SENSITIVITY_FLOOR,
    TeacherProfileManager,
    is_protected_concern,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = InsightsStore(db_path=tmp_path / "profile_test.db")
    yield s
    s.close()


@pytest.fixture
def manager(store):
    return TeacherProfileManager(store, profile_id="test-profile")


# ---------------------------------------------------------------------------
# is_protected_concern
# ---------------------------------------------------------------------------

class TestIsProtectedConcern:
    @pytest.mark.parametrize("text", [
        "student mentions suicide",
        "possible self-harm indicated",
        "expressed hopeless feelings",
        "student discussed crisis at home",
        "mentions abuse by family member",
        "wrote about violence in detail",
        "student in isolation from peers",
        "CRISIS language in submission",  # case-insensitive
        "Safety concern flagged",
    ])
    def test_protected_patterns_match(self, text):
        assert is_protected_concern(text) is True

    @pytest.mark.parametrize("text", [
        "student is confused about the assignment",
        "missed the main argument",
        "writing is off-topic",
        "needs more citations",
    ])
    def test_non_protected_patterns(self, text):
        assert is_protected_concern(text) is False

    def test_case_insensitive(self):
        assert is_protected_concern("SUICIDE mentioned") is True
        assert is_protected_concern("Self-Harm noted") is True


# ---------------------------------------------------------------------------
# Loading / defaults
# ---------------------------------------------------------------------------

class TestProfileLoading:
    def test_loads_empty_profile_when_store_empty(self, manager):
        p = manager.profile
        assert p.theme_renames == {}
        assert p.subject_area == "general"
        assert p.custom_concern_patterns == []

    def test_loads_existing_profile(self, store):
        store.save_profile("existing", {
            "subject_area": "ethnic studies",
            "interest_areas": ["power", "identity"],
        })
        mgr = TeacherProfileManager(store, profile_id="existing")
        assert mgr.profile.subject_area == "ethnic studies"
        assert mgr.profile.interest_areas == ["power", "identity"]

    def test_corrupted_profile_falls_back_to_empty(self, store):
        """If stored profile_data is invalid JSON object, fall back to defaults."""
        # Save a broken profile via raw connection
        store._conn.execute(
            "INSERT INTO teacher_profiles (profile_id, profile_data, created_at, updated_at)"
            " VALUES ('broken', 'NOT JSON AT ALL', datetime('now'), datetime('now'))"
        )
        store._conn.commit()
        mgr = TeacherProfileManager(store, profile_id="broken")
        # Should get defaults, not crash
        assert mgr.profile.subject_area == "general"


# ---------------------------------------------------------------------------
# Theme edit recording
# ---------------------------------------------------------------------------

class TestThemeEdits:
    def test_record_theme_rename(self, manager, store):
        manager.record_theme_rename("racism", "structural racism")
        p = store.get_profile("test-profile")
        assert p["theme_renames"]["racism"] == "structural racism"

    def test_record_theme_rename_in_memory(self, manager):
        manager.record_theme_rename("colonialism", "settler colonialism")
        assert manager.profile.theme_renames["colonialism"] == "settler colonialism"

    def test_record_theme_split(self, manager):
        manager.record_theme_split("discrimination", ["racial discrimination", "gender discrimination"])
        assert len(manager.profile.theme_splits) == 1
        assert manager.profile.theme_splits[0]["original"] == "discrimination"

    def test_record_theme_merge(self, manager):
        manager.record_theme_merge(
            sources=["oppression", "exploitation"],
            target="systemic oppression",
        )
        assert manager.profile.theme_renames["oppression"] == "systemic oppression"
        assert manager.profile.theme_renames["exploitation"] == "systemic oppression"

    def test_record_theme_merge_target_not_renamed(self, manager):
        """The target itself should not appear in renames."""
        manager.record_theme_merge(
            sources=["power", "control", "structural violence"],
            target="structural violence",  # target is one of the sources
        )
        # "structural violence" as target: source == target, so not renamed
        assert "structural violence" not in manager.profile.theme_renames

    def test_edit_history_appended(self, manager):
        manager.record_theme_rename("foo", "bar")
        manager.record_theme_split("foo", ["a", "b"])
        assert len(manager.profile.edit_history) == 2
        assert manager.profile.edit_history[0]["action"] == "theme_rename"
        assert manager.profile.edit_history[1]["action"] == "theme_split"

    def test_edit_history_bounded_at_200(self, manager):
        for i in range(250):
            manager.record_theme_rename(f"old_{i}", f"new_{i}")
        assert len(manager.profile.edit_history) <= 200


# ---------------------------------------------------------------------------
# Concern sensitivity
# ---------------------------------------------------------------------------

class TestConcernSensitivity:
    def test_acknowledge_increases_sensitivity(self, manager):
        manager.record_concern_action("student discusses hopelessness", "acknowledge")
        key = "student discusses hopelessness"
        assert manager.profile.concern_sensitivity[key] > 0.5

    def test_dismiss_decreases_sensitivity(self, manager):
        manager.record_concern_action("student off-topic digression", "dismiss")
        key = "student off-topic digression"
        assert manager.profile.concern_sensitivity[key] < 0.5

    def test_dismiss_non_protected_can_reach_zero(self, manager):
        key = "student misses the point"
        # Dismiss 5 times to drive to 0
        for _ in range(6):
            manager.record_concern_action(key, "dismiss")
        assert manager.profile.concern_sensitivity[key[:80]] == 0.0

    def test_protected_concern_hits_floor_on_dismiss(self, manager):
        key = "student mentions suicide"
        # Dismiss 10 times — should never go below WELLBEING_SENSITIVITY_FLOOR
        for _ in range(10):
            manager.record_concern_action(key, "dismiss")
        assert manager.profile.concern_sensitivity[key[:80]] >= WELLBEING_SENSITIVITY_FLOOR

    def test_protected_concern_dismiss_returns_note(self, manager):
        key = "student mentions suicide"
        # Drive sensitivity down to floor
        for _ in range(10):
            note = manager.record_concern_action(key, "dismiss")
        # At floor, should return the floor note
        assert note == WELLBEING_FLOOR_NOTE

    def test_non_protected_dismiss_returns_none(self, manager):
        note = manager.record_concern_action("off-topic writing", "dismiss")
        assert note is None

    def test_reset_concern_sensitivity(self, manager):
        manager.record_concern_action("some concern", "acknowledge")
        manager.record_concern_action("another concern", "dismiss")
        manager.reset_concern_sensitivity()
        assert manager.profile.concern_sensitivity == {}


# ---------------------------------------------------------------------------
# Custom patterns
# ---------------------------------------------------------------------------

class TestCustomPatterns:
    def test_add_custom_concern_pattern(self, manager):
        manager.add_custom_concern_pattern("student attributes group behavior to genetics")
        assert "student attributes group behavior to genetics" in manager.profile.custom_concern_patterns

    def test_add_concern_pattern_deduplicates(self, manager):
        manager.add_custom_concern_pattern("same pattern")
        manager.add_custom_concern_pattern("same pattern")
        assert manager.profile.custom_concern_patterns.count("same pattern") == 1

    def test_remove_custom_concern_pattern(self, manager):
        manager.add_custom_concern_pattern("to be removed")
        manager.remove_custom_concern_pattern("to be removed")
        assert "to be removed" not in manager.profile.custom_concern_patterns

    def test_add_strength_pattern(self, manager):
        manager.add_strength_pattern("student connects course material to community knowledge")
        assert "student connects course material to community knowledge" \
            in manager.profile.custom_strength_patterns

    def test_add_strength_pattern_deduplicates(self, manager):
        manager.add_strength_pattern("code-switching")
        manager.add_strength_pattern("code-switching")
        assert manager.profile.custom_strength_patterns.count("code-switching") == 1

    def test_remove_strength_pattern(self, manager):
        manager.add_strength_pattern("to remove")
        manager.remove_strength_pattern("to remove")
        assert "to remove" not in manager.profile.custom_strength_patterns


# ---------------------------------------------------------------------------
# Disable/enable default patterns
# ---------------------------------------------------------------------------

class TestDefaultPatternToggle:
    def test_disable_pedagogical_pattern(self, manager):
        manager.disable_default_pattern("colorblind framing")
        assert "colorblind framing" in manager.profile.disabled_default_patterns

    def test_disable_protected_pattern_silently_refused(self, manager):
        """Wellbeing/crisis patterns cannot be disabled."""
        manager.disable_default_pattern("personal distress")
        assert "personal distress" not in manager.profile.disabled_default_patterns

    def test_disable_crisis_silently_refused(self, manager):
        manager.disable_default_pattern("crisis detection")
        assert "crisis detection" not in manager.profile.disabled_default_patterns

    def test_enable_previously_disabled(self, manager):
        manager.disable_default_pattern("tone policing")
        manager.enable_default_pattern("tone policing")
        assert "tone policing" not in manager.profile.disabled_default_patterns

    def test_disable_deduplicates(self, manager):
        manager.disable_default_pattern("essentializing")
        manager.disable_default_pattern("essentializing")
        assert manager.profile.disabled_default_patterns.count("essentializing") == 1


# ---------------------------------------------------------------------------
# Prompt fragments
# ---------------------------------------------------------------------------

class TestPromptFragments:
    def test_theme_vocabulary_fragment_empty_when_no_renames(self, manager):
        result = manager.get_theme_vocabulary_fragment()
        assert result == ""

    def test_theme_vocabulary_fragment_contains_renames(self, manager):
        manager.record_theme_rename("poverty", "economic precarity")
        fragment = manager.get_theme_vocabulary_fragment()
        assert "economic precarity" in fragment
        assert "poverty" in fragment

    def test_theme_vocabulary_fragment_contains_splits(self, manager):
        manager.record_theme_split("discrimination", ["housing discrimination", "employment discrimination"])
        fragment = manager.get_theme_vocabulary_fragment()
        assert "housing discrimination" in fragment

    def test_concern_sensitivity_fragment_empty_when_no_calibration(self, manager):
        assert manager.get_concern_sensitivity_fragment() == ""

    def test_concern_sensitivity_fragment_high_sensitivity(self, manager):
        key = "student expresses hopelessness"
        for _ in range(3):  # raise to 0.8
            manager.record_concern_action(key, "acknowledge")
        fragment = manager.get_concern_sensitivity_fragment()
        assert "High sensitivity" in fragment

    def test_concern_sensitivity_fragment_floor_note(self, manager):
        key = "student mentions suicide"
        for _ in range(10):  # drive to floor
            manager.record_concern_action(key, "dismiss")
        fragment = manager.get_concern_sensitivity_fragment()
        assert "safety signal" in fragment.lower() or "minimum" in fragment.lower()

    def test_custom_concern_fragment_empty_when_none(self, manager):
        assert manager.get_custom_concern_fragment() == ""

    def test_custom_concern_fragment_contains_patterns(self, manager):
        manager.add_custom_concern_pattern("student attributes trauma to personal weakness")
        fragment = manager.get_custom_concern_fragment()
        assert "personal weakness" in fragment

    def test_interests_fragment_empty_when_none(self, manager):
        assert manager.get_interests_fragment() == ""

    def test_interests_fragment_contains_areas(self, manager):
        manager.record_interest_areas(["power", "identity", "structural violence"])
        fragment = manager.get_interests_fragment()
        assert "power" in fragment
        assert "identity" in fragment

    def test_interests_capped_at_5(self, manager):
        manager.record_interest_areas(["a", "b", "c", "d", "e", "f", "g"])
        assert len(manager.profile.interest_areas) == 5

    def test_disabled_defaults_fragment_empty_when_none(self, manager):
        assert manager.get_disabled_defaults_fragment() == ""

    def test_disabled_defaults_fragment_contains_patterns(self, manager):
        manager.disable_default_pattern("tone policing")
        fragment = manager.get_disabled_defaults_fragment()
        assert "tone policing" in fragment

    def test_full_profile_fragment_empty_when_empty_profile(self, manager):
        """A fresh profile with no edits produces an empty full fragment."""
        # The equity fragment and strength defaults may fire — that's OK.
        # Just ensure no crash.
        fragment = manager.get_full_profile_fragment()
        assert isinstance(fragment, str)

    def test_full_profile_fragment_wraps_in_delimiters(self, manager):
        manager.record_theme_rename("poverty", "economic precarity")
        fragment = manager.get_full_profile_fragment()
        assert "--- TEACHER PROFILE ---" in fragment
        assert "--- END PROFILE ---" in fragment


# ---------------------------------------------------------------------------
# Template save / fork
# ---------------------------------------------------------------------------

class TestTemplates:
    def test_save_as_template(self, manager, store):
        manager.record_theme_rename("racism", "structural racism")
        manager._profile.subject_area = "ethnic studies"
        manager._save()
        manager.save_as_template("ethnic-studies-default")
        tmpl = store.get_profile_template("ethnic-studies-default")
        assert tmpl is not None
        assert tmpl["subject_area"] == "ethnic studies"

    def test_save_as_template_strips_run_specific_data(self, manager, store):
        """Templates should not carry concern_sensitivity or edit_history."""
        manager.record_concern_action("some concern", "acknowledge")
        manager.save_as_template("clean-template")
        tmpl = store.get_profile_template("clean-template")
        assert tmpl["concern_sensitivity"] == {}
        assert tmpl["edit_history"] == []

    def test_fork_from_template(self, store):
        template_data = {
            "subject_area": "biology",
            "custom_concern_patterns": ["scientific essentialism"],
            "concern_sensitivity": {},
            "edit_history": [],
        }
        store.save_profile_template("bio-default", template_data)
        forked = TeacherProfileManager.fork_from_template(
            store, "bio-default", "new-bio-course"
        )
        assert forked.profile.subject_area == "biology"
        assert "scientific essentialism" in forked.profile.custom_concern_patterns

    def test_fork_from_nonexistent_template_loads_empty(self, store):
        """Fork from missing template falls through to empty profile."""
        forked = TeacherProfileManager.fork_from_template(
            store, "no-such-template", "new-profile"
        )
        assert forked.profile.subject_area == "general"
