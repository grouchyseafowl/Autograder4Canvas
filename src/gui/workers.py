"""
QThread-based workers for all async Canvas API operations.
"""
import logging
import tempfile
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
    """Runs AutomationEngine in a background thread."""

    log_line = Signal(str)
    finished = Signal(bool, str)  # (success, summary_message)

    def __init__(
        self,
        api,
        course_id: int,
        course_name: str,
        term_id: int,
        group_name: str,
        group_id: int,
        assignment_type: str,          # "complete_incomplete" | "discussion_forum" | "mixed"
        min_word_count: int = 200,
        post_min_words: int = 200,
        reply_min_words: int = 50,
        discussion_mode: str = "separate",
        grading_type: str = "complete_incomplete",
        post_points: float = 1.0,
        reply_points: float = 0.5,
        min_posts: int = 1,
        min_replies: int = 2,
        run_adc: bool = True,
        preserve_grades: bool = True,
        dry_run: bool = False,
        parent=None,
    ):
        super().__init__(api, parent)
        self.course_id = course_id
        self.course_name = course_name
        self.term_id = term_id
        self.group_name = group_name
        self.group_id = group_id
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
        self.dry_run = dry_run

    def run(self) -> None:
        import sys
        import os

        # Make sure src/ is importable
        src_dir = str(Path(__file__).parent.parent)
        if src_dir not in sys.path:
            sys.path.insert(0, src_dir)

        # AutomationEngine reads credentials from env vars — ensure they're set
        if self._api and self._api.base_url:
            os.environ["CANVAS_BASE_URL"] = self._api.base_url
        if self._api and self._api.api_token:
            os.environ["CANVAS_API_TOKEN"] = self._api.api_token

        try:
            from automation.course_config import (
                AssignmentRule, CourseConfig, GlobalSettings, AutomationConfig,
            )
            from automation.automation_engine import AutomationEngine
            from autograder_utils import get_output_base_dir

            base_dir = get_output_base_dir()
            log_dir = base_dir
            flag_dir = base_dir
            log_dir.mkdir(parents=True, exist_ok=True)

            rule = AssignmentRule(
                rule_id="gui_run",
                assignment_group_name=self.group_name,
                assignment_group_id=self.group_id,
                assignment_type=self.assignment_type,
                min_word_count=self.min_word_count,
                post_min_words=self.post_min_words,
                reply_min_words=self.reply_min_words,
                discussion_grading_mode=self.discussion_mode,
                grading_type=self.grading_type,
                post_points=self.post_points,
                reply_points=self.reply_points,
                min_posts=self.min_posts,
                min_replies=self.min_replies,
                run_adc=self.run_adc,
                preserve_existing_grades=self.preserve_grades,
            )

            course_cfg = CourseConfig(
                course_id=self.course_id,
                course_name=self.course_name,
                semester_term_id=self.term_id,
            )
            course_cfg.add_rule(rule)

            config = AutomationConfig()
            config.global_settings = GlobalSettings(
                current_semester_term_ids=[self.term_id],
                log_file_path=str(log_dir / "gui_run.log"),
                flag_excel_path=str(flag_dir / "gui_flags.xlsx"),
            )
            config.courses[self.course_id] = course_cfg

            # Write temp config
            fd, tmp_path = tempfile.mkstemp(suffix=".json")
            os.close(fd)
            tmp = Path(tmp_path)
            config.save(tmp)

            # Attach log handler
            handler = QTextEditHandler(self.log_line)
            handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
            logger = logging.getLogger("autograder_automation")
            logger.addHandler(handler)

            try:
                engine = AutomationEngine(
                    config_path=str(tmp),
                    dry_run=self.dry_run,
                    course_filter=self.course_id,
                )
                engine.run()
                self.finished.emit(True, "Grading complete")
            except Exception as exc:
                self.finished.emit(False, str(exc))
            finally:
                logger.removeHandler(handler)
                tmp.unlink(missing_ok=True)

        except Exception as exc:
            self.finished.emit(False, f"Setup error: {exc}")


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
        min_word_count   (int)   — CI min word count
        post_min_words   (int)   — discussion post min words
        reply_min_words  (int)   — discussion reply min words
    """

    log_line       = Signal(str)
    course_started = Signal(str)          # course_name
    progress       = Signal(int, int)     # (done, total)
    finished       = Signal(bool, str)    # (success, summary)

    def __init__(self, api, course_entries: list, scope: dict,
                 options: dict, dry_run: bool = False, parent=None):
        """
        course_entries: [(course_id, course_name, term_id), ...]
        """
        super().__init__(api, parent)
        self._course_entries = course_entries
        self._scope = scope
        self._options = options
        self._dry_run = dry_run

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

        run_aic         = self._options.get("run_aic", False)
        preserve        = self._options.get("preserve_grades", True)
        min_words       = self._options.get("min_word_count", 200)
        post_words      = self._options.get("post_min_words", 200)
        reply_words     = self._options.get("reply_min_words", 50)

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
            logger.addHandler(handler)

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
                    try:
                        course_cfg.add_rule(AssignmentRule(
                            rule_id=f"bulk_{gid}",
                            assignment_group_name=gname,
                            assignment_group_id=gid,
                            assignment_type="mixed",
                            min_word_count=min_words,
                            post_min_words=post_words,
                            reply_min_words=reply_words,
                            run_adc=run_aic,
                            preserve_existing_grades=preserve,
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
