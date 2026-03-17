"""
QThread-based workers for all async Canvas API operations.
"""
import json
import logging
import tempfile

log = logging.getLogger(__name__)
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import QThread, Signal


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

class CancellableWorker(QThread):
    """Base for all background workers. Provides cancel flag and error signal."""

    error = Signal(str)

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self._api = api
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled


# ---------------------------------------------------------------------------
# Load courses / terms
# ---------------------------------------------------------------------------

class LoadCoursesWorker(CancellableWorker):
    """Fetches all terms then courses for every term (empty terms are filtered in the UI)."""

    terms_loaded = Signal(list)         # [(term_id, term_name, is_current), ...]
    courses_loaded = Signal(int, list)  # (term_id, [course_dicts])

    def run(self) -> None:
        try:
            all_terms = self._api.get_all_terms()
            if self.is_cancelled():
                return

            # Fetch ALL courses before emitting anything.
            # This means terms_loaded and every courses_loaded fire in the same
            # Qt event-queue batch — no visible intermediate state.
            courses_by_term = self._api.get_all_teacher_courses()
            if self.is_cancelled():
                return

            term_list = [(t["id"], t["name"], t["is_current"]) for t in all_terms]
            self.terms_loaded.emit(term_list)
            for term in all_terms:
                self.courses_loaded.emit(term["id"], courses_by_term.get(term["id"], []))

        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Load assignments for one course
# ---------------------------------------------------------------------------

class LoadAssignmentsWorker(CancellableWorker):
    """Fetches assignment groups with nested assignments for one course."""

    assignments_loaded = Signal(list)  # [group_dicts with 'assignments' key]

    def __init__(self, api, course_id: int, parent=None):
        super().__init__(api, parent)
        self.course_id = course_id

    def run(self) -> None:
        try:
            groups = self._api.get_assignment_groups(self.course_id)
            if not self.is_cancelled():
                self.assignments_loaded.emit(groups)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Bulk assignment prefetch (all courses upfront)
# ---------------------------------------------------------------------------

class LoadAllAssignmentsWorker(CancellableWorker):
    """
    Background prefetch: fetches assignment groups for every course in the
    given list, emitting one signal per course as each finishes.
    """

    course_assignments_loaded = Signal(int, list)  # (course_id, groups)

    def __init__(self, api, course_ids: List[int], parent=None):
        super().__init__(api, parent)
        self.course_ids = list(course_ids)

    def run(self) -> None:
        for cid in self.course_ids:
            if self.is_cancelled():
                return
            try:
                groups = self._api.get_assignment_groups(cid)
                self.course_assignments_loaded.emit(cid, groups)
            except Exception:
                self.course_assignments_loaded.emit(cid, [])


# ---------------------------------------------------------------------------
# Lazy submission count loader
# ---------------------------------------------------------------------------

class LoadSubmissionCountsWorker(CancellableWorker):
    """Fetches submission counts one assignment at a time."""

    count_ready = Signal(int, int)   # (assignment_id, count)
    progress = Signal(int, int)      # (done, total)

    def __init__(self, api, course_id: int, assignment_ids: List[int], parent=None):
        super().__init__(api, parent)
        self.course_id = course_id
        self.assignment_ids = assignment_ids

    def run(self) -> None:
        total = len(self.assignment_ids)
        for done, aid in enumerate(self.assignment_ids, 1):
            if self.is_cancelled():
                return
            try:
                count = self._api.get_submission_count(self.course_id, aid)
                self.count_ready.emit(aid, count)
            except Exception:
                self.count_ready.emit(aid, -1)
            self.progress.emit(done, total)


# ---------------------------------------------------------------------------
# Test connection
# ---------------------------------------------------------------------------

class TestConnectionWorker(CancellableWorker):
    """Tests Canvas API connection and returns user display name."""

    result_ready = Signal(bool, str)  # (ok, message)

    def run(self) -> None:
        try:
            ok = self._api.test_connection()
            if not ok:
                self.result_ready.emit(False, "Invalid token or unreachable Canvas URL")
                return
            # Fetch display name
            import requests
            url = self._api.base_url.rstrip("/") + "/api/v1/users/self"
            headers = {"Authorization": f"Bearer {self._api.api_token}"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.ok:
                name = r.json().get("name", "")
                self.result_ready.emit(True, name)
            else:
                self.result_ready.emit(True, "")
        except Exception as exc:
            self.result_ready.emit(False, str(exc))


# ---------------------------------------------------------------------------
# RunStore workers  (no API needed — all local SQLite reads)
# ---------------------------------------------------------------------------

class _StoreWorker(QThread):
    """Lightweight base for RunStore workers (no CanvasAPI dependency)."""
    error = Signal(str)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store


class LoadRunsWorker(_StoreWorker):
    """Load the run-browser sidebar list from RunStore."""
    runs_loaded = Signal(list)  # List[Dict]

    def run(self) -> None:
        try:
            self.runs_loaded.emit(self._store.get_runs())
        except Exception as exc:
            self.error.emit(str(exc))


class LoadCohortWorker(_StoreWorker):
    """Load scatter-plot data for one run (or latest-per-student for a course)."""
    cohort_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, course_id: str, assignment_id: Optional[str] = None, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            self.cohort_loaded.emit(
                self._store.get_cohort(self._course_id, self._assignment_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class LoadTrajectoryWorker(_StoreWorker):
    """Load sparkline data for one student across a course."""
    trajectory_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, student_id: str, course_id: str, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._course_id = course_id

    def run(self) -> None:
        try:
            self.trajectory_loaded.emit(
                self._store.get_trajectory(self._student_id, self._course_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class LoadDetailWorker(_StoreWorker):
    """Load full detail row for one student + assignment."""
    detail_loaded = Signal(dict)  # Dict or {} on not-found

    def __init__(self, store, student_id: str, assignment_id: str, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            row = self._store.get_student_detail(self._student_id, self._assignment_id)
            self.detail_loaded.emit(row or {})
        except Exception as exc:
            self.error.emit(str(exc))


class SaveNoteWorker(_StoreWorker):
    """Persist a teacher note asynchronously."""
    note_saved = Signal(int)  # new note id

    def __init__(self, store, student_id: str, course_id: str, note_text: str,
                 assignment_id: Optional[str] = None, parent=None):
        super().__init__(store, parent)
        self._student_id = student_id
        self._course_id = course_id
        self._note_text = note_text
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            nid = self._store.save_note(
                self._student_id, self._course_id,
                self._note_text, self._assignment_id,
            )
            self.note_saved.emit(nid)
        except Exception as exc:
            self.error.emit(str(exc))


class LoadGradingAssignmentsWorker(_StoreWorker):
    """Load course -> assignment tree for grading review sidebar."""
    assignments_loaded = Signal(list)  # List[Dict]

    def run(self) -> None:
        try:
            self.assignments_loaded.emit(self._store.get_grading_assignments())
        except Exception as exc:
            self.error.emit(str(exc))


class LoadGradingCohortWorker(_StoreWorker):
    """Load all students for one assignment with AIC JOIN."""
    cohort_loaded = Signal(list)  # List[Dict]

    def __init__(self, store, course_id, assignment_id, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id

    def run(self) -> None:
        try:
            self.cohort_loaded.emit(
                self._store.get_grading_with_aic(self._course_id, self._assignment_id)
            )
        except Exception as exc:
            self.error.emit(str(exc))


class SaveTeacherOverrideWorker(_StoreWorker):
    """Persist override to SQLite + post grade to Canvas."""
    override_saved = Signal(bool, str)  # (success, message)

    def __init__(self, store, api, course_id, assignment_id, student_id, grade, reason, parent=None):
        super().__init__(store, parent)
        self._api = api
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._student_id = student_id
        self._grade = grade
        self._reason = reason

    def run(self) -> None:
        try:
            self._store.set_teacher_override(
                self._student_id, self._assignment_id, self._grade, self._reason
            )
            # Post to Canvas
            import requests
            base = self._api.base_url.rstrip("/")
            url = (
                f"{base}/api/v1/courses/{self._course_id}"
                f"/assignments/{self._assignment_id}"
                f"/submissions/{self._student_id}"
            )
            r = requests.put(
                url, headers=self._api.headers,
                json={"submission": {"posted_grade": self._grade}}, timeout=30,
            )
            r.raise_for_status()
            self.override_saved.emit(True, "Grade posted to Canvas")
        except Exception as exc:
            self.override_saved.emit(False, str(exc))


class ExportXLSXWorker(_StoreWorker):
    """Generate XLSX in background thread."""
    export_done = Signal(bool, str)  # (success, path_or_error)

    def __init__(self, store, course_id, assignment_id, output_path, parent=None):
        super().__init__(store, parent)
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._output_path = output_path

    def run(self) -> None:
        try:
            path = self._store.export_grading_xlsx(
                self._course_id, self._assignment_id, self._output_path
            )
            self.export_done.emit(True, path)
        except Exception as exc:
            self.export_done.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Logging handler that emits log records as Qt signals
# ---------------------------------------------------------------------------

class QTextEditHandler(logging.Handler):
    """Thread-safe logging handler that emits records via a Qt Signal."""

    def __init__(self, signal: Signal):
        super().__init__()
        self._signal = signal

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            self._signal.emit(msg)
        except Exception:
            self.handleError(record)


# ---------------------------------------------------------------------------
# Run grading engine
# ---------------------------------------------------------------------------

class RunWorker(CancellableWorker):
    """
    Runs the appropriate grading script directly on the user-selected assignments.

    Calls Programs/Autograder_Complete-Incomplete_v1-3.py,
    Programs/Autograder_Discussion_Forum_v1-3.py, or
    Academic_Dishonesty_Check_v2.py directly — bypassing AutomationEngine
    so that per-assignment manual runs are not subject to automation scheduling
    rules (skip_future_assignments, existing config filters, etc.).
    """

    log_line = Signal(str)
    progress = Signal(int, int)   # (completed, total)
    finished = Signal(bool, str)  # (success, summary_message)

    def __init__(
        self,
        api,
        course_id: int,
        course_name: str,
        selected_assignments: list,    # full assignment dicts from Canvas API
        assignment_type: str,          # "complete_incomplete" | "discussion_forum" | "aic"
        min_word_count: int = 200,
        post_min_words: int = 200,
        reply_min_words: int = 50,
        discussion_mode: str = "separate",
        grading_type: str = "complete_incomplete",
        post_points: float = 1.0,
        reply_points: float = 0.5,
        min_posts: int = 1,
        min_replies: int = 2,
        run_adc: bool = False,
        preserve_grades: bool = True,
        mark_incomplete: bool = True,
        dry_run: bool = False,
        mode_settings: dict = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self.mode_settings = mode_settings or {}
        self.course_id = course_id
        self.course_name = course_name
        self.selected_assignments = selected_assignments
        self.assignment_type = assignment_type
        self.min_word_count = min_word_count
        self.post_min_words = post_min_words
        self.reply_min_words = reply_min_words
        self.discussion_mode = discussion_mode
        self.grading_type = grading_type
        self.post_points = post_points
        self.reply_points = reply_points
        self.min_posts = min_posts
        self.min_replies = min_replies
        self.run_adc = run_adc
        self.preserve_grades = preserve_grades
        self.mark_incomplete = mark_incomplete
        self.dry_run = dry_run

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        import sys
        import os

        src_dir = str(Path(__file__).parent.parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        if self._api and self._api.base_url:
            os.environ["CANVAS_BASE_URL"] = self._api.base_url
        if self._api and self._api.api_token:
            os.environ["CANVAS_API_TOKEN"] = self._api.api_token

        # Redirect stdout so print() output from the scripts appears in the log pane
        _emit = self.log_line.emit

        class _Capture:
            def __init__(self):
                self._buf = ""
            def write(self, text):
                self._buf += text
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    _emit(line)
                return len(text)
            def flush(self):
                if self._buf:
                    _emit(self._buf)
                    self._buf = ""

        old_stdout = sys.stdout
        sys.stdout = _Capture()

        self._progress_total = len(self.selected_assignments)
        self._progress_done  = 0

        try:
            if self.dry_run:
                self.log_line.emit("🔍 DRY RUN MODE — No grades will be submitted")

            if self.assignment_type == "aic":
                self._run_aic()
            elif self.assignment_type == "mixed":
                _orig = self.selected_assignments
                _ci   = [a for a in _orig
                         if "discussion_topic" not in (a.get("submission_types") or [])]
                _df   = [a for a in _orig
                         if "discussion_topic" in (a.get("submission_types") or [])]
                if _ci:
                    self.selected_assignments = _ci
                    self._run_ci()
                if _df:
                    self.selected_assignments = _df
                    self._run_df()
                self.selected_assignments = _orig
                if self.run_adc:
                    self._run_aic()
            elif self.assignment_type == "discussion_forum":
                self._run_df()
                if self.run_adc:
                    self._run_aic()
            else:
                self._run_ci()
                if self.run_adc:
                    self._run_aic()

            self.finished.emit(True, "Grading complete")
        except Exception as exc:
            self.finished.emit(False, str(exc))
        finally:
            sys.stdout.flush()
            sys.stdout = old_stdout

    # ------------------------------------------------------------------
    # Script runners
    # ------------------------------------------------------------------

    def _emit_progress(self) -> None:
        self._progress_done += 1
        self.progress.emit(self._progress_done, self._progress_total)

    def _load_module(self, filename: str):
        """Dynamically load a Programs script as a module."""
        import importlib.util
        module_path = Path(__file__).parent.parent / "Programs" / filename
        spec = importlib.util.spec_from_file_location(filename.replace("-", "_").replace(".", "_"), module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _load_aic_module(self):
        """Load the AIC script (lives in src/, not Programs/)."""
        import importlib.util
        module_path = Path(__file__).parent.parent / "Academic_Dishonesty_Check_v2.py"
        spec = importlib.util.spec_from_file_location("aic", module_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _submit_individual(self, assignment_id: int, grade_data: dict) -> None:
        """
        Submit grades via individual PUT requests.

        The Canvas bulk update_grades endpoint returns 200/queued but grades
        do not reliably apply on this instance. Individual PUTs are consistent.
        grade_data: {user_id (int): posted_grade (str)}
        """
        import requests as _req
        base = self._api.base_url.rstrip("/")
        url = f"{base}/api/v1/courses/{self.course_id}/assignments/{assignment_id}/submissions"
        headers = self._api.headers

        failed = []
        for user_id, grade in grade_data.items():
            try:
                r = _req.put(
                    f"{url}/{user_id}",
                    headers=headers,
                    json={"submission": {"posted_grade": grade}},
                    timeout=30,
                )
                r.raise_for_status()
            except Exception as exc:
                print(f"   ❌ Failed for student {user_id}: {exc}")
                failed.append(user_id)

        if failed:
            raise RuntimeError(f"Grade submission failed for {len(failed)} student(s)")
        print(f"✅ {len(grade_data)} grade(s) submitted")

    def _run_ci(self) -> None:
        """Grade selected assignments using the Complete/Incomplete script."""
        ci = self._load_module("Autograder_Complete-Incomplete_v1-3.py")

        print(f"📚 {self.course_name}")
        students = ci.get_active_students(self.course_id)
        if not students:
            print("❌ No active students found.")
            return
        print(f"✅ {len(students)} active students")

        # Switch to per-student progress tracking for smooth progress bar
        self._progress_total = len(students) * len(self.selected_assignments)
        self._progress_done = 0
        self.progress.emit(0, max(1, self._progress_total))

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")
            if not aid:
                continue

            print(f"\n{'=' * 60}")
            print(f"📝 {aname}")
            print(f"{'=' * 60}")

            submissions = ci.get_submissions(self.course_id, aid)
            all_subs = list(submissions.values())

            grade_data = {}
            # Cache evaluation results: {user_id: (grade, flags)}
            eval_cache = {}
            # Track skipped students for RunStore persistence
            skipped_users = []
            complete = incomplete = skipped = 0
            for enrollment in students:
                user_id = enrollment.get("user_id")
                if not user_id:
                    continue
                self._progress_done += 1
                self.progress.emit(self._progress_done, self._progress_total)
                sub = submissions.get(user_id)
                if sub and sub.get("workflow_state") not in ("unsubmitted", "not_submitted"):
                    if self.preserve_grades and sub.get("grade") == "complete":
                        skipped += 1
                        skipped_users.append(user_id)
                        eval_cache[user_id] = ("complete", [])
                        continue
                    is_ok, flags = ci.evaluate_submission(sub, all_subs, self.min_word_count)
                    grade = "complete" if is_ok else "incomplete"
                    # Mode: criteria_strict — flagged submissions → incomplete
                    if self.mode_settings.get("criteria_strict") and flags and is_ok:
                        grade = "incomplete"
                    # Mode: manual_review — flag borderline students without changing grade
                    if self.mode_settings.get("manual_review") and flags:
                        flags = flags  # keep flags for review
                    eval_cache[user_id] = (grade, flags)
                    if grade == "complete":
                        complete += 1
                    else:
                        incomplete += 1
                else:
                    if not self.mark_incomplete:
                        continue
                    grade = "incomplete"
                    eval_cache[user_id] = (grade, ["No submission"])
                    incomplete += 1
                grade_data[user_id] = grade

            if not grade_data:
                msg = f"⚠️  No students to grade"
                if skipped:
                    msg += f" ({skipped} already complete)"
                print(msg)
                # Still persist skipped students to RunStore
                self._persist_ci_results(
                    ci, aid, aname, submissions, all_subs, students,
                    grade_data, eval_cache, skipped_users,
                    complete, incomplete, skipped,
                )
                continue

            print(
                f"   {complete} complete, {incomplete} incomplete"
                + (f", {skipped} skipped (already complete)" if skipped else "")
            )
            if self.dry_run:
                print("🔍 DRY RUN — no grades submitted")
            else:
                self._submit_individual(aid, grade_data)

            # Persist grading results to RunStore
            self._persist_ci_results(
                ci, aid, aname, submissions, all_subs, students,
                grade_data, eval_cache, skipped_users,
                complete, incomplete, skipped,
            )

    def _persist_ci_results(
        self, ci, aid, aname, submissions, all_subs, students,
        grade_data, eval_cache, skipped_users,
        complete, incomplete, skipped,
    ) -> None:
        """Best-effort save of CI grading results to RunStore."""
        try:
            from automation.run_store import RunStore
            store = RunStore()

            # Save per-student results (graded + skipped)
            all_user_ids = list(grade_data.keys()) + skipped_users
            for user_id in all_user_ids:
                sub = submissions.get(user_id, {})
                user_info = sub.get("user", {})
                student_name = user_info.get("name", f"User {user_id}")
                body = sub.get("body", "")
                word_count = len(body.split()) if body else 0
                submission_type = sub.get("submission_type", "")
                submitted_at = sub.get("submitted_at")

                # Build attachment metadata
                attachments = sub.get("attachments", [])
                attach_meta = [
                    {"filename": a.get("filename", ""),
                     "size": a.get("size", 0),
                     "content_type": a.get("content-type", ""),
                     "url": a.get("url", "")}
                    for a in attachments
                ]

                grade, flags = eval_cache.get(user_id, ("incomplete", []))
                was_skipped = 1 if user_id in skipped_users else 0

                if flags:
                    reason = "; ".join(flags)
                elif grade == "complete":
                    reason = "Meets requirements"
                else:
                    reason = "Incomplete submission"

                store.save_grading_result({
                    "student_id": str(user_id),
                    "assignment_id": str(aid),
                    "student_name": student_name,
                    "course_id": str(self.course_id),
                    "course_name": self.course_name,
                    "assignment_name": aname,
                    "submitted_at": submitted_at,
                    "grade": grade,
                    "reason": reason,
                    "word_count": word_count,
                    "submission_type": submission_type,
                    "submission_body": body,
                    "attachment_meta": attach_meta,
                    "flags": flags,
                    "is_flagged": 1 if [f for f in flags if f != "No submission"] else 0,
                    "grading_tool": "ci",
                    "min_word_count": self.min_word_count,
                    "was_skipped": was_skipped,
                })

            # Save run-level metadata
            flagged_count = sum(
                1 for uid in all_user_ids
                if eval_cache.get(uid, (None, []))[1]
            )
            store.save_grading_run({
                "course_id": str(self.course_id),
                "assignment_id": str(aid),
                "course_name": self.course_name,
                "assignment_name": aname,
                "grading_tool": "ci",
                "total_students": complete + incomplete + skipped,
                "complete_count": complete,
                "incomplete_count": incomplete,
                "skipped_count": skipped,
                "flagged_count": flagged_count,
                "min_word_count": self.min_word_count,
                "was_dry_run": 1 if self.dry_run else 0,
                "mode_settings": json.dumps(self.mode_settings),
            })
            store.close()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"RunStore save failed (CI): {exc}")

    def _run_df(self) -> None:
        """Grade selected discussion assignments using the Discussion Forum script."""
        df = self._load_module("Autograder_Discussion_Forum_v1-3.py")

        print(f"📚 {self.course_name}")
        students = df.get_active_students(self.course_id)
        if not students:
            print("❌ No active students found.")
            return

        # Switch to per-student progress tracking for smooth progress bar
        self._progress_total = len(students) * len(self.selected_assignments)
        self._progress_done = 0
        self.progress.emit(0, max(1, self._progress_total))

        grading_type_str = "pass_fail" if self.grading_type == "complete_incomplete" else "points"
        grading_criteria = {"complete": {"total_words": self.post_min_words, "min_replies": 0}}

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            topic = assignment.get("discussion_topic") or {}
            topic_id = topic.get("id")
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")

            if not topic_id or not aid:
                print(f"⚠️  '{aname}': no linked discussion topic — skipping")
                self._emit_progress()
                continue

            print(f"\n{'=' * 60}")
            print(f"💬 {aname}")
            print(f"{'=' * 60}")

            entries = df.fetch_discussion_entries(self.course_id, topic_id)
            if not entries:
                print("   ⚠️  No discussion entries found.")
                continue

            all_entries = df.flatten_entries(entries)
            student_posts: dict = {}
            for entry in all_entries:
                uid = entry.get("user_id")
                msg = entry.get("message", "")
                if uid:
                    student_posts.setdefault(uid, []).append(msg)

            # Fetch current grades if preserving existing work
            current_grades: dict = {}
            if self.preserve_grades:
                import requests as _req
                base = self._api.base_url.rstrip("/")
                r = _req.get(
                    f"{base}/api/v1/courses/{self.course_id}/assignments/{aid}/submissions",
                    headers=self._api.headers,
                    params={"per_page": 100},
                    timeout=30,
                )
                if r.ok:
                    for s in r.json():
                        uid = s.get("user_id")
                        if uid:
                            current_grades[uid] = s.get("grade")

            grade_data = {}
            # Cache evaluation results: {user_id: (grade, flags, word_count, post_count, avg_words)}
            eval_cache = {}
            # Track skipped students for RunStore persistence
            skipped_users = []
            complete = incomplete = skipped = 0
            student_ids = {s.get("user_id") for s in students}
            for s in students:
                user_id = s.get("user_id")
                if not user_id or user_id not in student_ids:
                    continue
                self._progress_done += 1
                self.progress.emit(self._progress_done, self._progress_total)
                posts = student_posts.get(user_id)
                if not posts:
                    continue  # no posts — leave ungraded
                if self.preserve_grades and current_grades.get(user_id) in ("complete",) or (
                    grading_type_str != "pass_fail"
                    and current_grades.get(user_id) not in (None, "", "0", "incomplete")
                ):
                    skipped += 1
                    skipped_users.append(user_id)
                    existing_grade = current_grades.get(user_id, "complete")
                    eval_cache[user_id] = (existing_grade, [], 0, len(posts), 0.0)
                    continue
                status, flags, _wc, _pc, _avg = df.evaluate_discussion_post(
                    posts, grading_criteria, grading_type_str
                )
                if grading_type_str == "pass_fail":
                    grade = "complete" if status == "complete" else "incomplete"
                else:
                    max_pts = assignment.get("points_possible") or 10
                    grade = str(max_pts) if status not in ("incomplete", "F") else "0"
                eval_cache[user_id] = (grade, flags, _wc, _pc, _avg)
                if grade in ("complete",) or (grading_type_str != "pass_fail" and grade != "0"):
                    complete += 1
                else:
                    incomplete += 1
                grade_data[user_id] = grade

            if not grade_data:
                msg = "   ⚠️  No students to grade"
                if skipped:
                    msg += f" ({skipped} already graded)"
                print(msg)
                # Still persist skipped students to RunStore
                self._persist_df_results(
                    aid, aname, student_posts, students,
                    grade_data, eval_cache, skipped_users,
                    complete, incomplete, skipped,
                )
                continue

            print(
                f"   {complete} complete, {incomplete} incomplete"
                + (f", {skipped} skipped (already graded)" if skipped else "")
            )
            if self.dry_run:
                print("   🔍 DRY RUN — no grades submitted")
            else:
                self._submit_individual(aid, grade_data)

            # Persist grading results to RunStore
            self._persist_df_results(
                aid, aname, student_posts, students,
                grade_data, eval_cache, skipped_users,
                complete, incomplete, skipped,
            )

    def _persist_df_results(
        self, aid, aname, student_posts, students,
        grade_data, eval_cache, skipped_users,
        complete, incomplete, skipped,
    ) -> None:
        """Best-effort save of DF grading results to RunStore."""
        try:
            from automation.run_store import RunStore
            store = RunStore()

            # Save per-student results (graded + skipped)
            all_user_ids = list(grade_data.keys()) + skipped_users
            for user_id in all_user_ids:
                # Find student name from enrollment list
                student_name = f"User {user_id}"
                for s in students:
                    if s.get("user_id") == user_id:
                        user_info = s.get("user", {})
                        student_name = user_info.get("name", student_name)
                        break

                posts = student_posts.get(user_id, [])
                combined_text = " ".join(posts)
                word_count = len(combined_text.split()) if combined_text.strip() else 0
                post_count = len(posts)

                grade, flags, _wc, _pc, avg_words = eval_cache.get(
                    user_id, ("incomplete", [], 0, 0, 0.0)
                )
                # Use cached word count if available (more accurate from evaluator)
                if _wc:
                    word_count = _wc
                was_skipped = 1 if user_id in skipped_users else 0

                if flags:
                    reason = "; ".join(flags)
                elif grade in ("complete",) or (grade not in ("0", "incomplete")):
                    reason = "Meets requirements"
                else:
                    reason = "Incomplete submission"

                store.save_grading_result({
                    "student_id": str(user_id),
                    "assignment_id": str(aid),
                    "student_name": student_name,
                    "course_id": str(self.course_id),
                    "course_name": self.course_name,
                    "assignment_name": aname,
                    "submitted_at": None,  # discussions don't have submitted_at
                    "grade": grade,
                    "reason": reason,
                    "word_count": word_count,
                    "submission_type": "discussion_topic",
                    "submission_body": combined_text,
                    "attachment_meta": [],
                    "flags": flags,
                    "is_flagged": 1 if [f for f in flags if f not in ("No submission", "No posts")] else 0,
                    "grading_tool": "df",
                    "min_word_count": self.post_min_words,
                    "was_skipped": was_skipped,
                    "post_count": post_count,
                    "reply_count": max(0, post_count - 1) if post_count > 0 else 0,
                    "avg_words_per_post": avg_words,
                })

            # Save run-level metadata
            flagged_count = sum(
                1 for uid in all_user_ids
                if eval_cache.get(uid, (None, [], 0, 0, 0.0))[1]
            )
            store.save_grading_run({
                "course_id": str(self.course_id),
                "assignment_id": str(aid),
                "course_name": self.course_name,
                "assignment_name": aname,
                "grading_tool": "df",
                "total_students": complete + incomplete + skipped,
                "complete_count": complete,
                "incomplete_count": incomplete,
                "skipped_count": skipped,
                "flagged_count": flagged_count,
                "min_word_count": self.post_min_words,
                "was_dry_run": 1 if self.dry_run else 0,
                "mode_settings": json.dumps(self.mode_settings),
            })
            store.close()
        except Exception as exc:
            logging.getLogger(__name__).warning(f"RunStore save failed (DF): {exc}")

    def _run_aic(self) -> None:
        """Run the Academic Integrity Checker on selected assignments."""
        aic = self._load_aic_module()

        settings   = self.mode_settings or {}
        aic_config = settings.get("aic_config")
        aic_mode   = (aic_config or {}).get("aic_mode") or settings.get("aic_mode", "auto")

        print(f"\n{'=' * 60}")
        print("🔍 Academic Integrity Check")
        print(f"{'=' * 60}")
        if aic_mode and aic_mode != "auto":
            print(f"   Assignment mode: {aic_mode}")

        for assignment in self.selected_assignments:
            if self.is_cancelled():
                break
            aid = assignment.get("id")
            aname = assignment.get("name", f"Assignment {aid}")
            if not aid:
                continue

            print(f"\n📋 {aname}")

            # AIC works on text-entry, file uploads (.txt/.docx/.pdf), and discussions.
            # Skip only non-text types (URL-only, on_paper, etc.).
            sub_types = assignment.get("submission_types") or []
            _analyzable = {"online_text_entry", "online_upload", "discussion_topic"}
            if not any(t in _analyzable for t in sub_types):
                type_str = ", ".join(sub_types) if sub_types else "none"
                print(f"⚠️  AIC skipped — no analyzable text content (type: {type_str})")
                continue

            if self.dry_run:
                print(f"🔍 DRY RUN: Would run AIC on assignment {aid}")
            else:
                # Phase 9: pass full aic_config when available; fall back to bare mode name
                if aic_config:
                    results, _ = aic.analyze_assignment(
                        self.course_id, aid, aic_config=aic_config,
                        generate_report=False,
                    )
                elif aic_mode and aic_mode != "auto":
                    results, _ = aic.analyze_assignment(
                        self.course_id, aid, assignment_type=aic_mode,
                        generate_report=False,
                    )
                else:
                    results, _ = aic.analyze_assignment(
                        self.course_id, aid, generate_report=False,
                    )


# ---------------------------------------------------------------------------
# Canvas edit workers (mutations via CanvasEditor)
# ---------------------------------------------------------------------------

class EditAssignmentWorker(CancellableWorker):
    """
    Runs any single CanvasEditor mutation in a background thread.

    Pass a zero-argument callable that returns an EditResult.

    Example:
        worker = EditAssignmentWorker(
            api=self._api,
            editor=self._editor,
            fn=lambda: self._editor.rename_assignment(course_id, aid, "New Name"),
        )
        worker.result_ready.connect(self._on_edit_done)
        worker.start()
    """

    result_ready = Signal(object)   # EditResult (as object so Qt doesn't need to know the type)

    def __init__(self, api, editor, fn, parent=None):
        super().__init__(api, parent)
        self._editor = editor
        self._fn = fn

    def run(self) -> None:
        try:
            result = self._fn()
        except Exception as exc:
            from canvas_editor import EditResult
            result = EditResult(ok=False, error_code="unknown", message=str(exc))
        if not self.is_cancelled():
            self.result_ready.emit(result)


class BulkShiftDeadlinesWorker(CancellableWorker):
    """
    Shifts due dates for a list of assignments by delta_days with per-item progress.

    Signals:
        progress(done, total)         — emitted after each assignment attempt
        item_done(assignment_id, result) — the EditResult for each assignment
        all_done(results)             — List[Tuple[int, EditResult]] when finished
    """

    progress   = Signal(int, int)    # (done, total)
    item_done  = Signal(int, object) # (assignment_id, EditResult)
    all_done   = Signal(list)        # List[Tuple[int, EditResult]]

    def __init__(self, api, editor, course_id: int,
                 assignment_ids: List[int], delta_days: int, parent=None):
        super().__init__(api, parent)
        self._editor = editor
        self._course_id = course_id
        self._assignment_ids = assignment_ids
        self._delta_days = delta_days

    def run(self) -> None:
        def _on_progress(done: int, total: int) -> None:
            if self.is_cancelled():
                return
            self.progress.emit(done, total)

        try:
            results = self._editor.bulk_shift_deadlines(
                self._course_id,
                self._assignment_ids,
                self._delta_days,
                progress_callback=_on_progress,
            )
        except Exception as exc:
            self.error.emit(str(exc))
            return

        if not self.is_cancelled():
            for aid, result in results:
                self.item_done.emit(aid, result)
            self.all_done.emit(results)


# ---------------------------------------------------------------------------
# Load assignment groups for a list of courses (for mapping panel)
# ---------------------------------------------------------------------------

class LoadGroupsForCoursesWorker(CancellableWorker):
    """
    Fetches assignment groups for multiple courses, emitting per-course as they arrive.

    Signals:
        groups_loaded(course_id, course_name, groups)  — one course done
        all_done()                                     — all courses processed
    """

    groups_loaded = Signal(int, str, list)   # (course_id, course_name, groups)
    all_done      = Signal()

    def __init__(self, api, course_entries: list, parent=None):
        """course_entries: [(course_id, course_name), ...]"""
        super().__init__(api, parent)
        self._entries = course_entries

    def run(self) -> None:
        for course_id, course_name in self._entries:
            if self.is_cancelled():
                break
            try:
                groups = self._api.get_assignment_groups(course_id)
            except Exception:
                groups = []
            if not self.is_cancelled():
                self.groups_loaded.emit(course_id, course_name, groups)
        if not self.is_cancelled():
            self.all_done.emit()


# ---------------------------------------------------------------------------
# Bulk run across multiple courses
# ---------------------------------------------------------------------------

class BulkRunWorker(CancellableWorker):
    """
    Runs the autograder across multiple courses sequentially.

    For each course: loads assignment groups, filters by scope, builds an
    AutomationConfig, and runs the engine.

    Scope dict keys (all bool):
        past_due       — include assignments whose deadline has passed
        submitted      — include assignments with ungraded submissions
        last_week_only — restrict past_due to assignments due in the last 7 days

    Options dict keys:
        run_aic          (bool)  — run academic integrity check alongside
        preserve_grades  (bool)  — preserve existing grades
        min_word_count   (int)   — CI min word count (global fallback)
        post_min_words   (int)   — discussion post min words (global fallback)
        reply_min_words  (int)   — discussion reply min words (global fallback)

    group_overrides: optional {group_id: {min_word_count, post_min_words,
        reply_min_words, run_aic, assignment_type}} — per-group template settings
        that override the global options when present.
    """

    log_line       = Signal(str)
    course_started = Signal(str)          # course_name
    progress       = Signal(int, int)     # (done, total)
    finished       = Signal(bool, str)    # (success, summary)

    def __init__(self, api, course_entries: list, scope: dict,
                 options: dict, dry_run: bool = False,
                 group_overrides: dict = None, parent=None):
        """
        course_entries: [(course_id, course_name, term_id), ...]
        group_overrides: {group_id: template_settings_dict}
        """
        super().__init__(api, parent)
        self._course_entries = course_entries
        self._scope = scope
        self._options = options
        self._dry_run = dry_run
        self._group_overrides = group_overrides or {}

    def run(self) -> None:
        import sys
        import os
        import tempfile
        from datetime import datetime, timedelta, timezone
        from pathlib import Path

        src_dir = str(Path(__file__).parent.parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        if self._api and self._api.base_url:
            os.environ["CANVAS_BASE_URL"] = self._api.base_url
        if self._api and self._api.api_token:
            os.environ["CANVAS_API_TOKEN"] = self._api.api_token

        now = datetime.now(timezone.utc)
        seven_days_ago = now - timedelta(days=7)

        scope_past_due   = self._scope.get("past_due", True)
        scope_submitted  = self._scope.get("submitted", False)
        scope_last_week  = self._scope.get("last_week_only", False)

        run_aic             = self._options.get("run_aic", False)
        preserve            = self._options.get("preserve_grades", True)
        mark_incomplete     = self._options.get("mark_incomplete", False)
        min_words           = self._options.get("min_word_count", 200)
        post_words          = self._options.get("post_min_words", 200)
        reply_words         = self._options.get("reply_min_words", 50)

        total = len(self._course_entries)
        total_graded = 0
        total_errors = 0

        try:
            from automation.course_config import (
                AssignmentRule, CourseConfig, GlobalSettings, AutomationConfig,
            )
            from automation.automation_engine import AutomationEngine
            from autograder_utils import get_output_base_dir
        except Exception as exc:
            self.finished.emit(False, f"Import error: {exc}")
            return

        base_dir = get_output_base_dir()
        base_dir.mkdir(parents=True, exist_ok=True)

        handler = None
        try:
            import logging
            handler = QTextEditHandler(self.log_line)
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger = logging.getLogger("autograder_automation")

            for done, (course_id, course_name, term_id) in enumerate(self._course_entries):
                if self.is_cancelled():
                    break

                self.course_started.emit(course_name)
                self.log_line.emit(f"\n{'='*55}")
                self.log_line.emit(f"COURSE {done+1}/{total}: {course_name}")
                self.log_line.emit(f"{'='*55}")

                try:
                    groups = self._api.get_assignment_groups(course_id)
                except Exception as exc:
                    self.log_line.emit(f"  ERROR loading assignments: {exc}")
                    total_errors += 1
                    self.progress.emit(done + 1, total)
                    continue

                # Filter groups to those containing qualifying assignments
                qualifying_groups = []
                for group in groups:
                    assignments = group.get("assignments", [])
                    qualifies = False
                    for a in assignments:
                        if not _bulk_is_autogradeable(a):
                            continue
                        due_raw = a.get("due_at")
                        due_dt = _bulk_parse_due(due_raw)
                        needs_grading = (a.get("needs_grading_count") or 0) > 0

                        if scope_submitted and needs_grading:
                            qualifies = True
                            break
                        if scope_past_due and due_dt and due_dt < now:
                            if scope_last_week and due_dt < seven_days_ago:
                                continue  # too old when last_week_only is set
                            qualifies = True
                            break

                    if qualifies:
                        qualifying_groups.append(group)

                if not qualifying_groups:
                    self.log_line.emit("  No qualifying assignments found — skipping.")
                    self.progress.emit(done + 1, total)
                    continue

                self.log_line.emit(
                    f"  {len(qualifying_groups)} group(s) with qualifying assignments"
                )

                # Build config
                config = AutomationConfig()
                config.global_settings = GlobalSettings(
                    current_semester_term_ids=[term_id],
                    log_file_path=str(base_dir / "bulk_run.log"),
                    flag_excel_path=str(base_dir / "bulk_flags.xlsx"),
                    skip_future_assignments=True,
                    skip_no_submissions=not scope_submitted and scope_past_due,
                )
                course_cfg = CourseConfig(
                    course_id=course_id,
                    course_name=course_name,
                    semester_term_id=term_id,
                )
                seen_group_ids: set = set()
                for group in qualifying_groups:
                    gid = group.get("id", 0)
                    if gid in seen_group_ids:
                        continue
                    seen_group_ids.add(gid)
                    gname = group.get("name", f"Group {gid}")

                    # Per-group template overrides take precedence over globals
                    ov = self._group_overrides.get(gid, {})
                    rule_min   = ov.get("min_word_count",  min_words)
                    rule_post  = ov.get("post_min_words",  post_words)
                    rule_reply = ov.get("reply_min_words", reply_words)
                    rule_aic   = ov.get("run_aic",         run_aic)
                    rule_atype = ov.get("assignment_type", "mixed")

                    try:
                        course_cfg.add_rule(AssignmentRule(
                            rule_id=f"bulk_{gid}",
                            assignment_group_name=gname,
                            assignment_group_id=gid,
                            assignment_type=rule_atype,
                            min_word_count=rule_min,
                            post_min_words=rule_post,
                            reply_min_words=rule_reply,
                            run_adc=rule_aic,
                            preserve_existing_grades=preserve,
                            mark_missing_as_incomplete=mark_incomplete,
                        ))
                    except ValueError:
                        pass  # duplicate group — skip

                config.courses[course_id] = course_cfg

                fd, tmp_path = tempfile.mkstemp(suffix=".json")
                os.close(fd)
                tmp = Path(tmp_path)
                try:
                    config.save(tmp)
                    engine = AutomationEngine(
                        config_path=str(tmp),
                        dry_run=self._dry_run,
                        course_filter=course_id,
                    )
                    # AutomationEngine._setup_logging() clears handlers — re-add ours
                    logger.addHandler(handler)
                    engine.run()
                    total_graded += 1
                except Exception as exc:
                    self.log_line.emit(f"  ERROR running engine: {exc}")
                    total_errors += 1
                finally:
                    tmp.unlink(missing_ok=True)

                self.progress.emit(done + 1, total)

        finally:
            if handler:
                import logging
                logging.getLogger("autograder_automation").removeHandler(handler)

        if self.is_cancelled():
            self.finished.emit(False, "Cancelled.")
        elif total_errors > 0:
            self.finished.emit(
                total_graded > 0,
                f"Done. {total_graded} course(s) completed, {total_errors} error(s).",
            )
        else:
            mode = "preview" if self._dry_run else "graded"
            self.finished.emit(True, f"Done. {total_graded} course(s) {mode}.")


def _bulk_parse_due(raw):
    """Parse a due_at string; return aware datetime or None."""
    if not raw:
        return None
    try:
        from dateutil import parser as _dp
        from datetime import timezone
        dt = _dp.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _bulk_is_autogradeable(assignment: dict) -> bool:
    """Return True if the autograder can handle this assignment type."""
    grading_type = assignment.get("grading_type", "")
    submission_types = assignment.get("submission_types", [])
    return grading_type == "pass_fail" or "discussion_topic" in submission_types


# ---------------------------------------------------------------------------
# Demo run worker
# ---------------------------------------------------------------------------

class DemoRunWorker(QThread):
    """
    Simulates a grading run using demo_data.simulate_grading_run.
    Signals match RunWorker so RunDialog's handlers work unchanged.
    """

    log_line = Signal(str)
    progress = Signal(int, int)   # (completed, total)
    finished = Signal(bool, str)  # (success, summary_message)

    def __init__(self, selected_items: list, parent=None):
        super().__init__(parent)
        self._selected  = selected_items
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            from demo_data import simulate_grading_run

            results = simulate_grading_run(
                selected     = self._selected,
                callback     = lambda line, done, total: (
                    self.log_line.emit(line),
                    self.progress.emit(done, total),
                ),
                cancel_check = lambda: self._cancelled,
            )

            n = results["graded"]
            c = results["complete"]
            i = results["incomplete"]
            f = results["flagged"]
            msg = (
                f"Graded {n} submissions — "
                f"{c} Complete, {i} Incomplete"
                + (f", {f} flagged for review" if f else "")
            )
            self.finished.emit(True, msg)
        except Exception as exc:
            self.finished.emit(False, str(exc))


# ---------------------------------------------------------------------------
# Insights Engine worker
# ---------------------------------------------------------------------------

class InsightsWorker(CancellableWorker):
    """Runs the Insights Engine analysis pipeline in a background thread.

    Signals:
        progress_update(str): status messages from the pipeline
        analysis_complete(str): run_id on success
        error(str): error message on failure (inherited)
    """

    progress_update = Signal(str)
    result_ready = Signal(str, dict)  # (result_type, data) for live preview
    analysis_complete = Signal(str)

    def __init__(
        self,
        api,
        *,
        store=None,
        course_id: int,
        course_name: str,
        assignment_id: int,
        assignment_name: str,
        is_discussion: bool = False,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[dict] = None,
        teacher_interests: Optional[list] = None,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._store = store
        self._course_id = course_id
        self._course_name = course_name
        self._assignment_id = assignment_id
        self._assignment_name = assignment_name
        self._is_discussion = is_discussion
        self._translate_enabled = translate_enabled
        self._transcribe_enabled = transcribe_enabled
        self._model_tier = model_tier
        self._teacher_context = teacher_context
        self._analysis_lens = analysis_lens
        self._teacher_interests = teacher_interests
        self._settings = settings or {}

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            def _result(result_type: str, data: dict) -> None:
                self.result_ready.emit(result_type, data)

            run_id = engine.run_analysis(
                course_id=self._course_id,
                course_name=self._course_name,
                assignment_id=self._assignment_id,
                assignment_name=self._assignment_name,
                is_discussion=self._is_discussion,
                translate_enabled=self._translate_enabled,
                transcribe_enabled=self._transcribe_enabled,
                model_tier=self._model_tier,
                teacher_context=self._teacher_context,
                analysis_lens=self._analysis_lens,
                teacher_interests=self._teacher_interests,
                progress_callback=_progress,
                result_callback=_result,
            )

            if run_id:
                self.analysis_complete.emit(run_id)
            elif not self.is_cancelled():
                self.error.emit("Analysis returned no results.")
        except Exception as exc:
            log.exception("InsightsWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Partial re-run worker (Phase 3)
# ---------------------------------------------------------------------------

class PartialRerunWorker(CancellableWorker):
    """Re-runs downstream pipeline stages after teacher edits.

    Trigger mapping:
      Change student tags   -> start_stage="themes"   -> themes + outliers + synthesis
      Split/merge/rename    -> start_stage="outliers"  -> outliers + synthesis
      Dismiss/add outlier   -> start_stage="synthesis"  -> synthesis only
    """

    progress_update = Signal(str)
    rerun_complete = Signal(str, list)  # (run_id, stages_re_run)

    def __init__(
        self,
        api,
        *,
        run_id: str,
        start_stage: str,
        store=None,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._run_id = run_id
        self._start_stage = start_stage
        self._store = store
        self._settings = settings or {}

    def run(self) -> None:
        try:
            from insights.engine import InsightsEngine

            engine = InsightsEngine(
                api=self._api,
                store=self._store,
                settings=self._settings,
            )

            def _progress(msg: str) -> None:
                self.progress_update.emit(msg)
                if self.is_cancelled():
                    engine.cancel()

            result = engine.run_partial(
                run_id=self._run_id,
                start_stage=self._start_stage,
                progress_callback=_progress,
            )

            if result:
                stages = {
                    "themes": ["themes", "outliers", "synthesis"],
                    "outliers": ["outliers", "synthesis"],
                    "synthesis": ["synthesis"],
                }
                self.rerun_complete.emit(
                    self._run_id, stages.get(self._start_stage, [])
                )
            elif not self.is_cancelled():
                self.error.emit("Partial re-run returned no results.")
        except Exception as exc:
            log.exception("PartialRerunWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Feedback post worker (Phase 4)
# ---------------------------------------------------------------------------

class FeedbackPostWorker(QThread):
    """Post approved feedback to Canvas as assignment comments.

    Signals:
        post_progress(str): "Posting feedback for Maria Garcia..."
        post_complete(int, int): (success_count, fail_count)
        error(str): error message
    """

    post_progress = Signal(str)
    post_complete = Signal(int, int)
    error = Signal(str)

    def __init__(
        self,
        api,
        *,
        store,
        run_id: str,
        course_id: str,
        assignment_id: str,
        parent=None,
    ):
        super().__init__(parent)
        self._api = api
        self._store = store
        self._run_id = run_id
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            import requests

            approved = self._store.get_approved_feedback(self._run_id)
            if not approved:
                self.post_complete.emit(0, 0)
                return

            success = 0
            fail = 0
            headers = dict(self._api.headers) if self._api else {}
            base_url = self._api.base_url.rstrip("/") if self._api else ""

            for fb in approved:
                if self._cancelled:
                    break

                student_name = fb.get("student_name", fb.get("student_id", ""))
                self.post_progress.emit(
                    f"Posting feedback for {student_name}..."
                )

                text = fb.get("approved_text") or fb.get("draft_text", "")
                if not text:
                    fail += 1
                    continue

                try:
                    url = (
                        f"{base_url}/api/v1/courses/{self._course_id}"
                        f"/assignments/{self._assignment_id}"
                        f"/submissions/{fb['student_id']}"
                    )
                    r = requests.put(
                        url,
                        headers=headers,
                        json={"comment": {"text_comment": text}},
                        timeout=30,
                    )
                    r.raise_for_status()
                    self._store.update_feedback_status(
                        self._run_id, fb["student_id"], "posted",
                        approved_text=text,
                    )
                    success += 1
                except Exception as e:
                    log.warning(
                        "Failed to post feedback for %s: %s", student_name, e
                    )
                    fail += 1

            self.post_complete.emit(success, fail)

        except Exception as exc:
            log.exception("FeedbackPostWorker failed: %s", exc)
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Batch insights worker (Phase 3)
# ---------------------------------------------------------------------------

class BatchInsightsWorker(CancellableWorker):
    """Runs insights analysis across multiple assignments sequentially.

    Signals:
        progress_update(str): per-run progress messages
        run_complete(str, int, int): (run_id, run_index, total_runs)
        batch_complete(list): list of completed run_ids
    """

    progress_update = Signal(str)
    result_ready = Signal(str, dict)  # (result_type, data) for live preview
    run_complete = Signal(str, int, int)
    batch_complete = Signal(list)

    def __init__(
        self,
        api,
        *,
        assignments: list,  # [(course_dict, assignment_dict), ...]
        store=None,
        translate_enabled: bool = True,
        transcribe_enabled: bool = True,
        model_tier: str = "lightweight",
        teacher_context: str = "",
        analysis_lens: Optional[dict] = None,
        teacher_interests: Optional[list] = None,
        settings: Optional[dict] = None,
        parent=None,
    ):
        super().__init__(api, parent)
        self._assignments = assignments
        self._store = store
        self._translate_enabled = translate_enabled
        self._transcribe_enabled = transcribe_enabled
        self._model_tier = model_tier
        self._teacher_context = teacher_context
        self._analysis_lens = analysis_lens
        self._teacher_interests = teacher_interests
        self._settings = settings or {}

    def run(self) -> None:
        completed_ids = []
        total = len(self._assignments)

        try:
            from insights.engine import InsightsEngine

            for idx, (course, assignment) in enumerate(self._assignments):
                if self.is_cancelled():
                    break

                assign_name = assignment.get("name", "Unknown")
                course_name = course.get("name", "")
                code = course.get("course_code", "")
                display = f"{code} — {assign_name}" if code else assign_name
                self.progress_update.emit(
                    f"Run {idx + 1}/{total}: {assign_name}..."
                )
                # Stage divider in live results
                self.result_ready.emit("stage", {
                    "stage": f"RUN {idx + 1}/{total}: {display}",
                })

                is_discussion = (
                    assignment.get("submission_types", []) == ["discussion_topic"]
                )

                engine = InsightsEngine(
                    api=self._api,
                    store=self._store,
                    settings=self._settings,
                )

                def _progress(msg: str, _idx=idx, _total=total,
                              _cname=course_name, _aname=assign_name) -> None:
                    # For batch runs, show which assignment we're on
                    # without doubling up the counter brackets
                    prefix = (
                        f"Run {_idx + 1}/{_total} · {_aname}"
                        if _total > 1 else ""
                    )
                    if prefix:
                        self.progress_update.emit(f"{prefix} — {msg}")
                    else:
                        self.progress_update.emit(msg)
                    if self.is_cancelled():
                        engine.cancel()

                def _result(result_type: str, data: dict) -> None:
                    self.result_ready.emit(result_type, data)

                run_id = engine.run_analysis(
                    course_id=course["id"],
                    course_name=course_name,
                    assignment_id=assignment["id"],
                    assignment_name=assign_name,
                    is_discussion=is_discussion,
                    translate_enabled=self._translate_enabled,
                    transcribe_enabled=self._transcribe_enabled,
                    model_tier=self._model_tier,
                    teacher_context=self._teacher_context,
                    analysis_lens=self._analysis_lens,
                    teacher_interests=self._teacher_interests,
                    progress_callback=_progress,
                    result_callback=_result,
                )

                if run_id:
                    completed_ids.append(run_id)
                    self.run_complete.emit(run_id, idx + 1, total)

            self.batch_complete.emit(completed_ids)
        except Exception as exc:
            log.exception("BatchInsightsWorker failed: %s", exc)
            self.error.emit(str(exc))
