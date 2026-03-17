"""
DemoRunStore — in-memory RunStore replacement for demo mode.

Implements the same method signatures as RunStore so it works transparently
with LoadRunsWorker, LoadCohortWorker, LoadDetailWorker, and LoadTrajectoryWorker.
Notes and overrides are stored in-memory and survive the session but don't persist.
"""
import uuid
from typing import Dict, List, Optional


class DemoRunStore:
    """In-memory store backed by demo_data. No SQLite, no files."""

    def __init__(self, profile: str = "cc"):
        self._demo_profile      = profile
        self._notes:            Dict[str, Dict] = {}  # note_id → note dict
        self._overrides:        Dict[str, Dict] = {}  # student_id → composable overrides
        self._profile_overrides: Dict[str, str] = {}  # student_id → profile name

    # ── Run browser ───────────────────────────────────────────────────────────

    def get_runs(self) -> List[Dict]:
        from demo_data import get_demo_aic_runs
        return get_demo_aic_runs(profile=self._demo_profile)

    # ── Cohort scatter ────────────────────────────────────────────────────────

    def get_cohort(self, course_id: str, assignment_id: Optional[str] = None) -> List[Dict]:
        from demo_data import get_demo_cohort
        return get_demo_cohort(str(course_id), str(assignment_id or ""))

    # ── Student detail ────────────────────────────────────────────────────────

    def get_student_detail(self, student_id: str, assignment_id: str) -> Dict:
        from demo_data import get_demo_student_detail
        return get_demo_student_detail(student_id, assignment_id,
                                       profile=self._demo_profile)

    # ── Trajectory sparklines ─────────────────────────────────────────────────

    def get_trajectory(self, student_id: str, course_id: str) -> List[Dict]:
        from demo_data import get_demo_trajectory
        return get_demo_trajectory(student_id, course_id, profile=self._demo_profile)

    # ── Teacher notes (in-memory, survives the session) ───────────────────────

    def get_notes(self, student_id: str, course_id: str) -> List[Dict]:
        return [
            n for n in self._notes.values()
            if n.get("student_id") == student_id and n.get("course_id") == course_id
        ]

    def save_note(self, student_id: str, course_id: str, note_text: str,
                  assignment_id: Optional[str] = None) -> str:
        note_id = str(uuid.uuid4())
        self._notes[note_id] = {
            "id":          note_id,
            "student_id":  student_id,
            "course_id":   course_id,
            "assignment_id": assignment_id,
            "note_text":   note_text,
            "created_at":  "2026-03-15T12:00:00",
        }
        return note_id

    def update_note(self, note_id, text: str) -> None:
        if note_id in self._notes:
            self._notes[note_id]["note_text"] = text

    def delete_note(self, note_id) -> None:
        self._notes.pop(str(note_id), None)

    # ── Profile overrides (in-memory) ─────────────────────────────────────────

    def get_composable_overrides(self, student_id: str) -> Dict:
        return self._overrides.get(student_id, {
            "esl_level":           0.0,
            "first_gen_level":     0.0,
            "neurodivergent_aware": False,
        })

    def set_composable_overrides(self, student_id: str, **kwargs) -> None:
        if student_id not in self._overrides:
            self._overrides[student_id] = {}
        self._overrides[student_id].update(kwargs)

    def get_profile_override(self, student_id: str) -> str:
        return self._profile_overrides.get(student_id, "standard")

    def set_profile_override(self, student_id: str, profile: str) -> None:
        self._profile_overrides[student_id] = profile

    # ── Stubs for methods called elsewhere in PriorRunsPanel ─────────────────

    def should_reanalyze(self, *args, **kwargs) -> bool:
        return False

    def save_result(self, *args, **kwargs) -> None:
        pass
