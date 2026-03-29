"""
InsightsStore — unit tests.

Tests SQLite persistence: run lifecycle, stage tracking, codings,
profile save/load, template save/load, and resume logic.

All tests use a fresh in-memory (tmp_path) database — no shared state.

Run with: python -m pytest tests/test_insights_store.py -v
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.insights_store import InsightsStore


# ---------------------------------------------------------------------------
# Fixture: fresh store per test
# ---------------------------------------------------------------------------

@pytest.fixture
def store(tmp_path):
    s = InsightsStore(db_path=tmp_path / "test_insights.db")
    yield s
    s.close()


# ---------------------------------------------------------------------------
# Run lifecycle
# ---------------------------------------------------------------------------

class TestRunLifecycle:
    def test_create_and_get_run(self, store):
        store.create_run(
            run_id="run-001",
            course_id="course-42",
            course_name="Ethnic Studies",
            assignment_id="asgn-7",
            assignment_name="Week 3 Response",
        )
        r = store.get_run("run-001")
        assert r is not None
        assert r["run_id"] == "run-001"
        assert r["course_id"] == "course-42"
        assert r["assignment_id"] == "asgn-7"
        assert r["completed_at"] is None

    def test_get_run_missing_returns_none(self, store):
        assert store.get_run("nonexistent-id") is None

    def test_complete_run(self, store):
        store.create_run(
            run_id="run-002",
            course_id="course-42",
            course_name="Ethnic Studies",
            assignment_id="asgn-7",
            assignment_name="Week 3 Response",
        )
        store.complete_run("run-002", confidence={"overall": 0.8})
        r = store.get_run("run-002")
        assert r["completed_at"] is not None

    def test_stages_completed_empty_initially(self, store):
        store.create_run(
            run_id="run-003",
            course_id="c1",
            course_name="Biology",
            assignment_id="a1",
            assignment_name="Osmosis Lab",
        )
        r = store.get_run("run-003")
        assert r["stages_completed"] == []

    def test_complete_stage_adds_stage(self, store):
        store.create_run(
            run_id="run-004",
            course_id="c1",
            course_name="Bio",
            assignment_id="a1",
            assignment_name="Lab",
        )
        store.complete_stage("run-004", "quick_analysis")
        r = store.get_run("run-004")
        assert "quick_analysis" in r["stages_completed"]

    def test_complete_stage_idempotent(self, store):
        store.create_run(
            run_id="run-005",
            course_id="c1",
            course_name="Bio",
            assignment_id="a1",
            assignment_name="Lab",
        )
        store.complete_stage("run-005", "coding")
        store.complete_stage("run-005", "coding")  # second call same stage
        r = store.get_run("run-005")
        assert r["stages_completed"].count("coding") == 1

    def test_complete_multiple_stages(self, store):
        store.create_run(
            run_id="run-006",
            course_id="c1",
            course_name="Bio",
            assignment_id="a1",
            assignment_name="Lab",
        )
        for stage in ["quick_analysis", "class_reading", "coding", "synthesis"]:
            store.complete_stage("run-006", stage)
        r = store.get_run("run-006")
        assert len(r["stages_completed"]) == 4

    def test_get_runs_filtered_by_course(self, store):
        for i in range(3):
            store.create_run(
                run_id=f"run-c1-{i}",
                course_id="course-A",
                course_name="History",
                assignment_id=f"a{i}",
                assignment_name=f"Week {i}",
            )
        store.create_run(
            run_id="run-c2-0",
            course_id="course-B",
            course_name="Biology",
            assignment_id="bio-a1",
            assignment_name="Lab 1",
        )
        runs_a = store.get_runs(course_id="course-A")
        assert len(runs_a) == 3
        assert all(r["course_id"] == "course-A" for r in runs_a)

    def test_get_completed_runs_excludes_incomplete(self, store):
        store.create_run(
            run_id="run-done",
            course_id="c1",
            course_name="X",
            assignment_id="a1",
            assignment_name="Y",
        )
        store.create_run(
            run_id="run-in-progress",
            course_id="c1",
            course_name="X",
            assignment_id="a2",
            assignment_name="Z",
        )
        store.complete_run("run-done")
        completed = store.get_completed_runs()
        ids = [r["run_id"] for r in completed]
        assert "run-done" in ids
        assert "run-in-progress" not in ids

    def test_save_and_get_quick_analysis(self, store):
        store.create_run(
            run_id="run-qa",
            course_id="c1",
            course_name="X",
            assignment_id="a1",
            assignment_name="Y",
        )
        qa_data = json.dumps({"assignment_id": "a1", "stats": {"total_submissions": 8}})
        store.save_quick_analysis("run-qa", qa_data)
        r = store.get_run("run-qa")
        # quick_analysis is stored as raw JSON string in the run row
        assert r["quick_analysis"] is not None

    def test_save_and_get_class_reading(self, store):
        store.create_run(
            run_id="run-cr",
            course_id="c1",
            course_name="X",
            assignment_id="a1",
            assignment_name="Y",
        )
        store.save_class_reading("run-cr", "Students showed strong engagement with Crenshaw.")
        text = store.get_class_reading("run-cr")
        assert "Crenshaw" in text

    def test_get_class_reading_missing_run(self, store):
        result = store.get_class_reading("nonexistent")
        assert result == ""


# ---------------------------------------------------------------------------
# Codings
# ---------------------------------------------------------------------------

class TestCodings:
    def _make_run(self, store, run_id="run-cod-001"):
        store.create_run(
            run_id=run_id,
            course_id="c1",
            course_name="Ethnic Studies",
            assignment_id="a1",
            assignment_name="Week 1",
        )

    def test_save_and_get_coding(self, store):
        self._make_run(store)
        coding = json.dumps({"student_id": "s001", "theme_tags": ["power"]})
        store.save_coding("run-cod-001", "s001", "Aaliyah Johnson", coding)
        codings = store.get_codings("run-cod-001")
        assert len(codings) == 1
        assert codings[0]["student_id"] == "s001"

    def test_coding_record_decoded(self, store):
        self._make_run(store)
        coding = json.dumps({"student_id": "s002", "theme_tags": ["resistance", "community"]})
        store.save_coding("run-cod-001", "s002", "Marcus Okonkwo", coding)
        record = store.get_coding_record("run-cod-001", "s002")
        assert record is not None
        assert isinstance(record["coding_record"], dict)
        assert record["coding_record"]["theme_tags"] == ["resistance", "community"]

    def test_get_coding_record_missing(self, store):
        self._make_run(store)
        result = store.get_coding_record("run-cod-001", "nonexistent")
        assert result is None

    def test_save_multiple_codings(self, store):
        self._make_run(store)
        students = [
            ("s001", "Aaliyah Johnson"),
            ("s002", "Marcus Okonkwo"),
            ("s003", "Priya Nair"),
        ]
        for sid, name in students:
            coding = json.dumps({"student_id": sid, "word_count": 250})
            store.save_coding("run-cod-001", sid, name, coding)
        codings = store.get_codings("run-cod-001")
        assert len(codings) == 3

    def test_save_coding_upsert(self, store):
        """Second save to same (run_id, student_id) should update."""
        self._make_run(store)
        v1 = json.dumps({"student_id": "s001", "theme_tags": ["power"]})
        v2 = json.dumps({"student_id": "s001", "theme_tags": ["power", "resistance"]})
        store.save_coding("run-cod-001", "s001", "Aaliyah", v1)
        store.save_coding("run-cod-001", "s001", "Aaliyah Johnson", v2)
        record = store.get_coding_record("run-cod-001", "s001")
        assert "resistance" in record["coding_record"]["theme_tags"]

    def test_save_coding_with_submission_text(self, store):
        self._make_run(store)
        coding = json.dumps({"student_id": "s001", "word_count": 120})
        store.save_coding(
            "run-cod-001", "s001", "Destiny Cruz", coding,
            submission_text="This is my response about intersectionality.",
        )
        record = store.get_coding_record("run-cod-001", "s001")
        assert record["submission_text"] == "This is my response about intersectionality."

    def test_codings_isolated_by_run(self, store):
        """Codings for run A should not appear in run B."""
        store.create_run(run_id="run-A", course_id="c1", course_name="X",
                         assignment_id="a1", assignment_name="Y")
        store.create_run(run_id="run-B", course_id="c1", course_name="X",
                         assignment_id="a2", assignment_name="Z")
        store.save_coding("run-A", "s001", "A Student",
                          json.dumps({"student_id": "s001"}))
        assert store.get_codings("run-B") == []


# ---------------------------------------------------------------------------
# Profile persistence
# ---------------------------------------------------------------------------

class TestProfilePersistence:
    def test_save_and_get_profile(self, store):
        data = {"subject_area": "ethnic studies", "interest_areas": ["power", "identity"]}
        store.save_profile("default", data)
        retrieved = store.get_profile("default")
        assert retrieved is not None
        assert retrieved["subject_area"] == "ethnic studies"
        assert retrieved["interest_areas"] == ["power", "identity"]

    def test_get_profile_missing_returns_none(self, store):
        assert store.get_profile("no-such-profile") is None

    def test_save_profile_upsert(self, store):
        store.save_profile("default", {"subject_area": "general"})
        store.save_profile("default", {"subject_area": "biology"})
        retrieved = store.get_profile("default")
        assert retrieved["subject_area"] == "biology"

    def test_list_profiles(self, store):
        store.save_profile("course-1", {"subject_area": "history"})
        store.save_profile("course-2", {"subject_area": "biology"})
        profiles = store.list_profiles()
        assert "course-1" in profiles
        assert "course-2" in profiles

    def test_list_profiles_empty(self, store):
        assert store.list_profiles() == []


# ---------------------------------------------------------------------------
# Profile templates
# ---------------------------------------------------------------------------

class TestProfileTemplates:
    def test_save_and_get_template(self, store):
        data = {"subject_area": "history", "custom_concern_patterns": ["anachronism"]}
        store.save_profile_template("history-default", data)
        retrieved = store.get_profile_template("history-default")
        assert retrieved is not None
        assert retrieved["subject_area"] == "history"

    def test_get_template_missing_returns_none(self, store):
        assert store.get_profile_template("no-such-template") is None

    def test_save_template_upsert(self, store):
        store.save_profile_template("stem-default", {"subject_area": "biology"})
        store.save_profile_template("stem-default", {"subject_area": "chemistry"})
        retrieved = store.get_profile_template("stem-default")
        assert retrieved["subject_area"] == "chemistry"

    def test_list_profile_templates(self, store):
        store.save_profile_template("template-A", {"subject_area": "art"})
        store.save_profile_template("template-B", {"subject_area": "music"})
        templates = store.list_profile_templates()
        assert "template-A" in templates
        assert "template-B" in templates

    def test_delete_template(self, store):
        store.save_profile_template("to-delete", {"subject_area": "x"})
        store.delete_profile_template("to-delete")
        assert store.get_profile_template("to-delete") is None


# ---------------------------------------------------------------------------
# Resume: stage completion tracking enables resume on crash
# ---------------------------------------------------------------------------

class TestResumeLogic:
    """Tests that completed_stage tracking enables safe resume after crash."""

    def test_stages_persist_across_reopen(self, tmp_path):
        """Stage completions survive closing and reopening the store."""
        db_path = tmp_path / "resume_test.db"

        store1 = InsightsStore(db_path=db_path)
        store1.create_run(
            run_id="run-resume",
            course_id="c1",
            course_name="X",
            assignment_id="a1",
            assignment_name="Y",
        )
        store1.complete_stage("run-resume", "quick_analysis")
        store1.complete_stage("run-resume", "class_reading")
        store1.close()

        store2 = InsightsStore(db_path=db_path)
        r = store2.get_run("run-resume")
        assert "quick_analysis" in r["stages_completed"]
        assert "class_reading" in r["stages_completed"]
        store2.close()

    def test_codings_survive_reopen(self, tmp_path):
        """Saved codings survive closing and reopening."""
        db_path = tmp_path / "coding_persist.db"

        store1 = InsightsStore(db_path=db_path)
        store1.create_run(run_id="run-X", course_id="c1", course_name="X",
                          assignment_id="a1", assignment_name="Y")
        store1.save_coding("run-X", "s001", "A Student",
                           json.dumps({"student_id": "s001", "word_count": 200}))
        store1.close()

        store2 = InsightsStore(db_path=db_path)
        codings = store2.get_codings("run-X")
        assert len(codings) == 1
        assert codings[0]["student_id"] == "s001"
        store2.close()
