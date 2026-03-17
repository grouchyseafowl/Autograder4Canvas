"""
Canvas mutation backend for the GUI autograder.

Pure Python — no Qt imports. All mutation methods return EditResult and all
preflight checks return PreflightResult. Neither type ever raises to callers.
Rate-limit (HTTP 429) and timeout retry are handled internally.

Usage pattern (from a QThread worker):
    editor = CanvasEditor(base_url, api_token)

    # 1. Preflight (optional but recommended for risky changes)
    pre = editor.preflight_grading_type_change(course_id, aid, "pass_fail", "points")
    if not pre.can_proceed:
        # show blocking error in UI
        ...
    elif pre.advisory_warnings:
        # show confirmation dialog
        ...

    # 2. Execute
    result = editor.set_grading_type(course_id, aid, "pass_fail")
    if result.ok:
        # refresh UI with result.data (updated assignment dict)
        ...
    else:
        # show result.message, act on result.error_code
        ...
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Literal, Optional, Tuple

import requests
from dateutil import parser as dateutil_parser

logger = logging.getLogger("canvas_editor")

# Sentinel for "caller did not pass this argument" — distinct from None (which means "clear it")
_UNSET = object()


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------

@dataclass
class PreflightWarning:
    """One individual warning within a preflight result."""

    code: str
    # "block" = operation must not proceed (Canvas would reject or data would be lost)
    # "warn"  = advisory; user should confirm but can proceed
    severity: Literal["block", "warn"]
    message: str


@dataclass
class PreflightResult:
    """
    Result of a preflight check.

    safe             — True only when there are zero warnings of any kind
    can_proceed      — True when no blocking warnings (warn-only = user can override)
    advisory_warnings — warnings the user should acknowledge before proceeding
    blocking_warnings — warnings that mean the operation must be prevented
    """

    safe: bool
    warnings: List[PreflightWarning] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        return not any(w.severity == "block" for w in self.warnings)

    @property
    def blocking_warnings(self) -> List[PreflightWarning]:
        return [w for w in self.warnings if w.severity == "block"]

    @property
    def advisory_warnings(self) -> List[PreflightWarning]:
        return [w for w in self.warnings if w.severity == "warn"]

    @classmethod
    def safe_result(cls) -> "PreflightResult":
        return cls(safe=True)

    @classmethod
    def blocking(cls, code: str, message: str) -> "PreflightResult":
        return cls(
            safe=False,
            warnings=[PreflightWarning(code=code, severity="block", message=message)],
        )


@dataclass
class EditResult:
    """
    Result of a Canvas mutation.

    ok         — True if Canvas accepted the change
    data       — the updated Canvas object dict on success
    error_code — machine-readable: "rate_limit" | "timeout" | "not_found" |
                 "conflict" | "permission_denied" | "validation_error" | "unknown"
    message    — human-readable string for display in the GUI
    """

    ok: bool
    data: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    message: str = ""

    @classmethod
    def failure(cls, code: str, message: str) -> "EditResult":
        return cls(ok=False, error_code=code, message=message)


# ---------------------------------------------------------------------------
# Human-readable labels
# ---------------------------------------------------------------------------

GRADING_TYPE_LABELS: Dict[str, str] = {
    "pass_fail":    "Complete / Incomplete",
    "points":       "Points",
    "percent":      "Percentage",
    "letter_grade": "Letter Grade",
    "not_graded":   "Not Graded",
}

# Transitions where existing grade values become semantically wrong or invisible
_LOSSY_PAIRS = {
    ("points",       "pass_fail"),
    ("points",       "not_graded"),
    ("percent",      "pass_fail"),
    ("percent",      "not_graded"),
    ("letter_grade", "pass_fail"),
    ("letter_grade", "not_graded"),
    ("pass_fail",    "points"),
    ("pass_fail",    "percent"),
    ("pass_fail",    "letter_grade"),
}


# ---------------------------------------------------------------------------
# CanvasEditor
# ---------------------------------------------------------------------------

class CanvasEditor:
    """
    Thin mutation wrapper around the Canvas REST API.

    Does not inherit from CanvasAutomationAPI — composition is preferred so that
    read helpers on the existing api object can be called by workers without
    creating circular dependencies.
    """

    _MAX_ATTEMPTS = 3
    _BASE_TIMEOUT = 30   # seconds per request

    def __init__(self, base_url: str, api_token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    # -----------------------------------------------------------------------
    # Internal HTTP helpers
    # -----------------------------------------------------------------------

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> requests.Response:
        """Simple GET — for preflight reads. Not paginated."""
        url = f"{self.base_url}/api/v1{path}"
        return requests.get(url, headers=self._headers, params=params or {}, timeout=self._BASE_TIMEOUT)

    def _request(
        self,
        method: str,
        path: str,
        json_body: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
        """
        Execute a mutating HTTP request with 429 backoff and timeout retry.

        Returns (data, error_code, message).
        Never raises.

        Rate-limit (429) retries are tracked separately from timeout/connection
        retries so that hitting a rate limit doesn't burn the retry budget.
        """
        url = f"{self.base_url}/api/v1{path}"
        rate_limit_hits = 0
        error_attempts = 0

        while error_attempts < self._MAX_ATTEMPTS:
            try:
                resp = requests.request(
                    method,
                    url,
                    headers=self._headers,
                    json=json_body,
                    timeout=self._BASE_TIMEOUT,
                )

                if resp.status_code == 429:
                    rate_limit_hits += 1
                    if rate_limit_hits >= 3:
                        return None, "rate_limit", "Canvas rate-limited this request three times. Wait a moment and try again."
                    retry_after = min(int(resp.headers.get("Retry-After", 10)), 120)
                    logger.warning("Rate limited by Canvas; waiting %ds", retry_after)
                    time.sleep(retry_after)
                    continue  # does NOT increment error_attempts

                return self._parse_response(resp)

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
                error_attempts += 1
                if error_attempts < self._MAX_ATTEMPTS:
                    time.sleep(2 ** (error_attempts - 1))  # 1s, 2s

            except Exception as exc:
                return None, "unknown", f"Unexpected error: {exc}"

        return None, "timeout", "Canvas did not respond in time. Check your connection and retry."

    def _parse_response(
        self, resp: requests.Response
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], str]:
        """Map an HTTP response to (data, error_code, message)."""
        if resp.ok:
            try:
                return resp.json(), None, "OK"
            except ValueError:
                return None, "unknown", "Unexpected response format from Canvas."

        code: str
        if resp.status_code == 404:
            code = "not_found"
            msg = "The assignment or group no longer exists on Canvas."
        elif resp.status_code in (401, 403):
            code = "permission_denied"
            msg = "Your token doesn't have permission for this action. Check the Settings tab."
        elif resp.status_code == 422:
            code = "validation_error"
            try:
                body = resp.json()
                # Canvas wraps errors in {"errors": {"field": [{"message": "..."}]}} or similar
                errors = body.get("errors", {})
                if isinstance(errors, list):
                    msg = errors[0].get("message", resp.text[:200])
                elif isinstance(errors, dict):
                    first = next(iter(errors.values()), [{}])
                    msg = first[0].get("message", resp.text[:200]) if first else resp.text[:200]
                else:
                    msg = resp.text[:200]
            except Exception:
                msg = resp.text[:200]
        else:
            code = "unknown"
            msg = f"Canvas returned {resp.status_code}: {resp.text[:200]}"

        return None, code, msg

    def _put_assignment(self, course_id: int, assignment_id: int, fields: Dict[str, Any]) -> EditResult:
        """Low-level: PUT assignment with partial field update."""
        data, err_code, msg = self._request(
            "PUT",
            f"/courses/{course_id}/assignments/{assignment_id}",
            {"assignment": fields},
        )
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    def _put_group(self, course_id: int, group_id: int, fields: Dict[str, Any]) -> EditResult:
        """Low-level: PUT assignment group."""
        data, err_code, msg = self._request(
            "PUT",
            f"/courses/{course_id}/assignment_groups/{group_id}",
            fields,
        )
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    # -----------------------------------------------------------------------
    # Preflight helpers (lightweight reads)
    # -----------------------------------------------------------------------

    def _has_graded_submissions(self, course_id: int, assignment_id: int) -> Optional[bool]:
        """
        Returns True if at least one submission is graded, False if none, None on error.
        Uses per_page=1 to minimise load.
        """
        try:
            r = self._get(
                f"/courses/{course_id}/assignments/{assignment_id}/submissions",
                params={"workflow_state": "graded", "per_page": 1},
            )
            if not r.ok:
                return None
            return bool(r.json())
        except Exception:
            return None

    def _has_any_submissions(self, course_id: int, assignment_id: int) -> Optional[bool]:
        """
        Returns True if any actually-submitted work exists (graded or ungraded).
        Filters at the API level to avoid the per_page=1 false-negative bug where
        Canvas returns an "unsubmitted" placeholder as the first result.
        """
        try:
            # Check for submitted (ungraded) work
            r = self._get(
                f"/courses/{course_id}/assignments/{assignment_id}/submissions",
                params={"per_page": 1, "workflow_state": "submitted"},
            )
            if not r.ok:
                return None
            if r.json():
                return True
            # Also check graded (already-evaluated submissions still count as "has work")
            r2 = self._get(
                f"/courses/{course_id}/assignments/{assignment_id}/submissions",
                params={"per_page": 1, "workflow_state": "graded"},
            )
            if not r2.ok:
                return None
            return bool(r2.json())
        except Exception:
            return None

    def _get_group_info(self, course_id: int, group_id: int) -> Optional[Dict[str, Any]]:
        try:
            r = self._get(f"/courses/{course_id}/assignment_groups/{group_id}")
            return r.json() if r.ok else None
        except Exception:
            return None

    # -----------------------------------------------------------------------
    # PREFLIGHT CHECKS
    # -----------------------------------------------------------------------

    def preflight_grading_type_change(
        self,
        course_id: int,
        assignment_id: int,
        new_grading_type: str,
        current_grading_type: str,
    ) -> PreflightResult:
        """
        Warn if graded submissions exist (converting types won't re-grade them) or
        if the specific transition is inherently lossy (e.g. points → pass_fail).
        """
        if current_grading_type == new_grading_type:
            return PreflightResult.safe_result()

        warnings: List[PreflightWarning] = []

        if new_grading_type == "not_graded":
            warnings.append(PreflightWarning(
                code="not_graded_hides_grades",
                severity="warn",
                message=(
                    'Setting grading type to "Not Graded" means this assignment will not '
                    "count toward student course grades and existing grades will be hidden."
                ),
            ))

        has_graded = self._has_graded_submissions(course_id, assignment_id)
        if has_graded:
            old_label = GRADING_TYPE_LABELS.get(current_grading_type, current_grading_type)
            new_label = GRADING_TYPE_LABELS.get(new_grading_type, new_grading_type)
            lossy = (current_grading_type, new_grading_type) in _LOSSY_PAIRS
            message = (
                f"Existing grades won't be re-scored — they'll be reinterpreted under "
                f"{new_label} scale."
            )
            if lossy:
                message += " Some values may be truncated; review SpeedGrader afterward."
            warnings.append(PreflightWarning(
                code="has_graded_submissions",
                severity="warn",
                message=message,
            ))

        return PreflightResult(safe=(len(warnings) == 0), warnings=warnings)

    def preflight_group_move(
        self,
        course_id: int,
        assignment_id: int,
        source_group_id: int,
        target_group_id: int,
    ) -> PreflightResult:
        """
        Warn if source and target groups have meaningfully different weights,
        which would change how this assignment is counted in the overall grade.
        """
        if source_group_id == target_group_id:
            return PreflightResult.safe_result()

        src = self._get_group_info(course_id, source_group_id)
        tgt = self._get_group_info(course_id, target_group_id)

        if src is None or tgt is None:
            # Can't determine; allow with no warning
            return PreflightResult.safe_result()

        src_weight = float(src.get("group_weight") or 0)
        tgt_weight = float(tgt.get("group_weight") or 0)

        if abs(src_weight - tgt_weight) < 1.0:
            return PreflightResult.safe_result()

        src_name = src.get("name", "current group")
        tgt_name = tgt.get("name", "target group")
        return PreflightResult(
            safe=False,
            warnings=[PreflightWarning(
                code="weight_mismatch",
                severity="warn",
                message=(
                    f'Moving this assignment from "{src_name}" ({src_weight:.0f}% weight) '
                    f'to "{tgt_name}" ({tgt_weight:.0f}% weight) will change how much it '
                    f"contributes to the overall course grade."
                ),
            )],
        )

    def preflight_deadline_change(
        self,
        course_id: int,
        assignment_id: int,
        new_due_at: Optional[str],
        current_due_at: Optional[str],
    ) -> PreflightResult:
        """
        Warn if the new deadline is earlier than the current one (shortening may
        strand students who planned to submit before the old deadline).
        Also warn when removing a deadline entirely.
        """
        warnings: List[PreflightWarning] = []
        now = datetime.now(timezone.utc)

        if not new_due_at and current_due_at:
            warnings.append(PreflightWarning(
                code="deadline_removed",
                severity="warn",
                message=(
                    "Removing the deadline means students will not see a due date in their "
                    "Canvas calendar or To-Do list."
                ),
            ))
        elif new_due_at and current_due_at:
            try:
                cur = dateutil_parser.isoparse(current_due_at)
                new = dateutil_parser.isoparse(new_due_at)
                if new < cur:
                    if new < now:
                        warnings.append(PreflightWarning(
                            code="deadline_in_past",
                            severity="warn",
                            message=(
                                "The new deadline is already in the past. Students will see "
                                "the assignment as overdue and may not be able to submit "
                                "unless you also update the 'Available Until' date."
                            ),
                        ))
                    else:
                        warnings.append(PreflightWarning(
                            code="deadline_shortened",
                            severity="warn",
                            message=(
                                "You are moving the deadline earlier. Students who planned to "
                                "submit before the original deadline will have less time. "
                                "Canvas does not automatically notify students of deadline changes."
                            ),
                        ))
            except (ValueError, TypeError):
                pass

        return PreflightResult(safe=(len(warnings) == 0), warnings=warnings)

    def preflight_points_change(
        self,
        course_id: int,
        assignment_id: int,
        new_points: float,
        current_points: float,
    ) -> PreflightResult:
        """
        Warn if changing points_possible when grades already exist (affects percentages).
        Block if new_points is negative.
        """
        warnings: List[PreflightWarning] = []

        if new_points < 0:
            return PreflightResult.blocking(
                "negative_points", "Points possible cannot be negative."
            )

        if new_points == current_points:
            return PreflightResult.safe_result()

        if new_points == 0:
            warnings.append(PreflightWarning(
                code="zero_points",
                severity="warn",
                message=(
                    "Setting points possible to 0 on a graded assignment causes Canvas to "
                    "display unusual grade percentages. Consider using 'Not Graded' instead."
                ),
            ))

        has_graded = self._has_graded_submissions(course_id, assignment_id)
        if has_graded:
            warnings.append(PreflightWarning(
                code="has_graded_submissions",
                severity="warn",
                message=(
                    f"Students already have grades for this assignment. Changing points from "
                    f"{current_points:.4g} to {new_points:.4g} will change their displayed "
                    f"percentage — raw scores are kept but the denominator changes. "
                    f"SpeedGrader may need to be refreshed."
                ),
            ))

        return PreflightResult(safe=(len(warnings) == 0), warnings=warnings)

    def preflight_unpublish(
        self,
        course_id: int,
        assignment_id: int,
    ) -> PreflightResult:
        """
        Block if graded submissions exist — Canvas will reject the unpublish.
        Warn if any ungraded submissions exist (students lose access).
        """
        has_graded = self._has_graded_submissions(course_id, assignment_id)
        if has_graded:
            return PreflightResult.blocking(
                "has_graded_submissions",
                "Canvas will not allow unpublishing an assignment that already has graded "
                "submissions. Delete the grades first if you need to unpublish.",
            )

        has_any = self._has_any_submissions(course_id, assignment_id)
        if has_any:
            return PreflightResult(
                safe=False,
                warnings=[PreflightWarning(
                    code="has_ungraded_submissions",
                    severity="warn",
                    message=(
                        "Students have already submitted this assignment. Unpublishing will "
                        "hide it from them and they may lose access to their submitted work."
                    ),
                )],
            )

        return PreflightResult.safe_result()

    # -----------------------------------------------------------------------
    # ASSIGNMENT MUTATIONS
    # -----------------------------------------------------------------------

    def rename_assignment(
        self, course_id: int, assignment_id: int, new_name: str
    ) -> EditResult:
        """Rename an assignment. No preflight needed."""
        if not new_name or not new_name.strip():
            return EditResult.failure("validation_error", "Assignment name cannot be empty.")
        return self._put_assignment(course_id, assignment_id, {"name": new_name.strip()})

    def move_assignment_group(
        self, course_id: int, assignment_id: int, target_group_id: int
    ) -> EditResult:
        """Move assignment to a different assignment group."""
        return self._put_assignment(
            course_id, assignment_id, {"assignment_group_id": target_group_id}
        )

    def set_grading_type(
        self,
        course_id: int,
        assignment_id: int,
        grading_type: str,
        points_possible: Optional[float] = None,
    ) -> EditResult:
        """
        Change grading type. Optionally update points_possible at the same time
        (useful when switching to 'points' and setting a value simultaneously).
        """
        valid = {"pass_fail", "points", "percent", "letter_grade", "not_graded"}
        if grading_type not in valid:
            return EditResult.failure("validation_error", f"Invalid grading type: {grading_type!r}")
        fields: Dict[str, Any] = {"grading_type": grading_type}
        if points_possible is not None:
            fields["points_possible"] = points_possible
        return self._put_assignment(course_id, assignment_id, fields)

    def set_deadlines(
        self,
        course_id: int,
        assignment_id: int,
        due_at: Optional[str],
        unlock_at: Optional[str] = _UNSET,
        lock_at: Optional[str] = _UNSET,
    ) -> EditResult:
        """
        Set due date and optionally the unlock/available-from and lock/available-until dates.

        due_at is always sent (pass None to clear it).
        unlock_at / lock_at are only sent when explicitly provided; omit them to leave unchanged.
        All date strings must be ISO 8601 (e.g. "2026-04-01T23:59:00Z").
        """
        fields: Dict[str, Any] = {"due_at": due_at}
        if unlock_at is not _UNSET:
            fields["unlock_at"] = unlock_at
        if lock_at is not _UNSET:
            fields["lock_at"] = lock_at
        return self._put_assignment(course_id, assignment_id, fields)

    def set_points_possible(
        self, course_id: int, assignment_id: int, points: float
    ) -> EditResult:
        """Change points_possible. Run preflight_points_change first for risky changes."""
        if points < 0:
            return EditResult.failure("validation_error", "Points possible cannot be negative.")
        return self._put_assignment(course_id, assignment_id, {"points_possible": points})

    def set_published(
        self, course_id: int, assignment_id: int, published: bool
    ) -> EditResult:
        """Publish or unpublish. Run preflight_unpublish before unpublishing."""
        return self._put_assignment(course_id, assignment_id, {"published": published})

    def edit_assignment(
        self, course_id: int, assignment_id: int, fields: Dict[str, Any]
    ) -> EditResult:
        """
        Batch update: apply any subset of Canvas assignment fields in a single PUT.
        Caller is responsible for running preflights before calling this.

        Accepted keys (Canvas API field names):
          name, assignment_group_id, grading_type, due_at, unlock_at, lock_at,
          points_possible, published, submission_types, description
        """
        if not fields:
            return EditResult.failure("validation_error", "No fields provided for update.")
        return self._put_assignment(course_id, assignment_id, fields)

    # -----------------------------------------------------------------------
    # COURSE MUTATIONS
    # -----------------------------------------------------------------------

    def preflight_unpublish_course(self, course_id: int) -> PreflightResult:
        """
        Warn if students are actively enrolled — unpublishing immediately hides
        the course from all enrolled students.
        """
        try:
            r = self._get(
                f"/courses/{course_id}/enrollments",
                params={"type[]": "StudentEnrollment", "state[]": "active", "per_page": 1},
            )
            has_students = bool(r.ok and r.json())
        except Exception:
            has_students = False

        if has_students:
            return PreflightResult(
                safe=False,
                warnings=[PreflightWarning(
                    code="has_enrolled_students",
                    severity="warn",
                    message=(
                        "This course has enrolled students. Unpublishing will immediately "
                        "hide the course from all students — they will lose access to course "
                        "materials, grades, and announcements until the course is re-published."
                    ),
                )],
            )
        return PreflightResult.safe_result()

    def set_course_published(self, course_id: int, publish: bool) -> EditResult:
        """
        Publish (offer) or unpublish (claim) a course on Canvas.

        Canvas uses the 'event' field on the course object:
          "offer"  — publish the course (visible to students)
          "claim"  — unpublish (hidden from students)

        Run preflight_unpublish_course before unpublishing.
        """
        event = "offer" if publish else "claim"
        data, err_code, msg = self._request(
            "PUT",
            f"/courses/{course_id}",
            {"course": {"event": event}},
        )
        if err_code == "permission_denied":
            msg = (
                "Your institution has not granted teachers permission to publish or "
                "unpublish courses. This action may require admin permissions."
            )
        elif err_code == "not_found":
            msg = "Course not found on Canvas — it may have been deleted."
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    def rename_course(self, course_id: int, new_name: str) -> EditResult:
        """
        Rename a course on Canvas (PUT /api/v1/courses/:id).

        Requires the teacher to have "Manage course settings" permission.
        Many institutions grant this by default; some restrict it to admins.

        Returns a permission-specific message on 401/403 so the UI can give
        the user actionable guidance rather than a raw HTTP error.
        """
        if not new_name or not new_name.strip():
            return EditResult.failure("validation_error", "Course name cannot be empty.")

        data, err_code, msg = self._request(
            "PUT",
            f"/courses/{course_id}",
            {"course": {"name": new_name.strip()}},
        )

        if err_code == "permission_denied":
            msg = (
                "Your institution has not granted teachers permission to rename courses. "
                "To change the course name in Canvas you (or an admin) would need to update "
                "it in Canvas Course Settings directly. Your nickname is still saved locally."
            )
        elif err_code == "not_found":
            msg = "Course not found on Canvas — it may have been deleted or moved."

        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    # -----------------------------------------------------------------------
    # ASSIGNMENT GROUP MUTATIONS
    # -----------------------------------------------------------------------

    def rename_assignment_group(
        self, course_id: int, group_id: int, new_name: str
    ) -> EditResult:
        if not new_name or not new_name.strip():
            return EditResult.failure("validation_error", "Group name cannot be empty.")
        return self._put_group(course_id, group_id, {"name": new_name.strip()})

    def set_group_weight(
        self, course_id: int, group_id: int, weight: float
    ) -> EditResult:
        """
        Set the assignment group weight (percentage). Only meaningful when the
        course uses weighted assignment groups. Canvas accepts 0–100.
        """
        if weight < 0:
            return EditResult.failure("validation_error", "Group weight cannot be negative.")
        return self._put_group(course_id, group_id, {"group_weight": weight})

    def set_group_position(
        self, course_id: int, group_id: int, position: int
    ) -> EditResult:
        """Set the display position (1-based) of an assignment group."""
        return self._put_group(course_id, group_id, {"position": position})

    def set_assignment_position(
        self, course_id: int, assignment_id: int, position: int
    ) -> EditResult:
        """Set the display position (1-based) of an assignment within its group."""
        return self._put_assignment(course_id, assignment_id, {"position": position})

    def create_assignment_group(
        self,
        course_id: int,
        name: str,
        weight: float = 0.0,
        position: Optional[int] = None,
    ) -> EditResult:
        """Create a new assignment group. Returns the new group dict on success."""
        if not name or not name.strip():
            return EditResult.failure("validation_error", "Group name cannot be empty.")
        body: Dict[str, Any] = {"name": name.strip(), "group_weight": weight}
        if position is not None:
            body["position"] = position
        data, err_code, msg = self._request(
            "POST", f"/courses/{course_id}/assignment_groups", body
        )
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    def delete_assignment_group(
        self,
        course_id: int,
        group_id: int,
        move_assignments_to: Optional[int] = None,
    ) -> EditResult:
        """
        Delete an assignment group. Canvas requires move_assignments_to if the group
        has assignments — call preflight before this to surface that requirement.
        """
        path = f"/courses/{course_id}/assignment_groups/{group_id}"
        if move_assignments_to is not None:
            path += f"?move_assignments_to={move_assignments_to}"
        data, err_code, msg = self._request("DELETE", path)
        if err_code == "validation_error":
            err_code = "conflict"
            msg = (
                "Cannot delete a group that still has assignments. "
                "Move or delete the assignments first, or specify a destination group."
            )
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    # -----------------------------------------------------------------------
    # BULK OPERATIONS
    # -----------------------------------------------------------------------

    def bulk_shift_deadlines(
        self,
        course_id: int,
        assignment_ids: List[int],
        delta_days: int,
        progress_callback: Optional[Any] = None,
    ) -> List[Tuple[int, EditResult]]:
        """
        Shift due_at, unlock_at, and lock_at for each assignment by delta_days.
        All three dates are shifted together so the availability window moves as a unit.
        Assignments with no due date are skipped with ok=True and a note in message.
        Returns a list of (assignment_id, EditResult) in input order.

        progress_callback(done: int, total: int) is called after each assignment.
        """
        results: List[Tuple[int, EditResult]] = []
        total = len(assignment_ids)
        delta = timedelta(days=delta_days)

        for i, aid in enumerate(assignment_ids):
            try:
                r = self._get(f"/courses/{course_id}/assignments/{aid}")
                if not r.ok:
                    results.append((aid, EditResult.failure("not_found", f"Assignment {aid} not found.")))
                    if progress_callback:
                        progress_callback(i + 1, total)
                    continue

                assignment = r.json()
                due_str = assignment.get("due_at")

                if not due_str:
                    results.append((
                        aid,
                        EditResult(ok=True, data=assignment, message="No deadline — skipped."),
                    ))
                    if progress_callback:
                        progress_callback(i + 1, total)
                    continue

                due_dt = dateutil_parser.isoparse(due_str)
                fields: Dict[str, Any] = {
                    "due_at": (due_dt + delta).strftime("%Y-%m-%dT%H:%M:%SZ"),
                }

                # Shift unlock_at and lock_at together so the availability window moves as a unit
                for date_key in ("unlock_at", "lock_at"):
                    date_str = assignment.get(date_key)
                    if date_str:
                        try:
                            dt = dateutil_parser.isoparse(date_str)
                            fields[date_key] = (dt + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
                        except (ValueError, TypeError):
                            pass

                result = self._put_assignment(course_id, aid, fields)
                results.append((aid, result))

            except Exception as exc:
                results.append((aid, EditResult.failure("unknown", str(exc))))

            if progress_callback:
                progress_callback(i + 1, total)

        return results

    # -----------------------------------------------------------------------
    # STUDENT OVERRIDES
    # -----------------------------------------------------------------------

    def add_student_override(
        self,
        course_id: int,
        assignment_id: int,
        student_ids: List[int],
        due_at: Optional[str] = None,
        unlock_at: Optional[str] = None,
        lock_at: Optional[str] = None,
        title: str = "Student Extension",
    ) -> EditResult:
        """
        Create a per-student deadline override (extension) for an assignment.
        Multiple students can share one override by passing multiple IDs.

        Canvas accepts one override per POST. If a student already has an override,
        Canvas creates a second one — the later due_at takes precedence.
        Canvas returns 422 if any student_id is not enrolled in the course.
        """
        if not student_ids:
            return EditResult.failure("validation_error", "At least one student ID is required.")

        body: Dict[str, Any] = {
            "assignment_override": {
                "student_ids": student_ids,
                "title": title,
            }
        }
        if due_at is not None:
            body["assignment_override"]["due_at"] = due_at
        if unlock_at is not None:
            body["assignment_override"]["unlock_at"] = unlock_at
        if lock_at is not None:
            body["assignment_override"]["lock_at"] = lock_at

        data, err_code, msg = self._request(
            "POST",
            f"/courses/{course_id}/assignments/{assignment_id}/overrides",
            body,
        )
        if err_code == "validation_error":
            msg = (
                "One or more students are not enrolled in this course, "
                "or the override could not be applied. " + msg
            )
        return EditResult(ok=(data is not None), data=data, error_code=err_code, message=msg)

    def list_student_overrides(
        self,
        course_id: int,
        assignment_id: int,
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """
        Return (overrides_list, error_message). error_message is None on success.
        Useful for displaying existing overrides before adding a new one.
        """
        try:
            r = self._get(f"/courses/{course_id}/assignments/{assignment_id}/overrides")
            if r.ok:
                return r.json(), None
            _, _, msg = self._parse_response(r)
            return [], msg
        except Exception as exc:
            return [], str(exc)
