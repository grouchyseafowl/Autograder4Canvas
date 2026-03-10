"""
Canvas Autograder - Grade Preservation Logic
Ensures existing grades are not overwritten by automation.
"""

import os
import requests
from typing import Dict, Any, List


class GradeChecker:
    """Ensures existing grades are not overwritten."""

    def __init__(self, base_url: str = None, api_token: str = None):
        """
        Initialize grade checker.

        Args:
            base_url: Canvas base URL
            api_token: Canvas API token
        """
        self.base_url = base_url or os.getenv("CANVAS_BASE_URL")
        self.api_token = api_token or os.getenv("CANVAS_API_TOKEN")

        if not self.api_token:
            raise ValueError("CANVAS_API_TOKEN not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def filter_gradeable(self, submissions: Dict[int, Dict[str, Any]],
                        preserve_existing: bool = True) -> Dict[int, Dict[str, Any]]:
        """
        Filter submissions to only those safe to grade.

        Args:
            submissions: Dict of {user_id: submission_data}
            preserve_existing: If True, exclude already-graded submissions

        Returns:
            Filtered dict of gradeable submissions
        """
        if not preserve_existing:
            return submissions

        gradeable = {}

        for user_id, submission in submissions.items():
            if self._is_safe_to_grade(submission):
                gradeable[user_id] = submission

        return gradeable

    def _is_safe_to_grade(self, submission: Dict[str, Any]) -> bool:
        """
        Check if a submission is safe to grade without overwriting manual grades.

        Only skips submissions that are explicitly marked as 'graded' by Canvas.
        Does NOT use the score field because Canvas automatically sets score=0
        for all submitted work, even when ungraded. Using score would incorrectly
        skip submitted work that needs grading.

        Args:
            submission: Submission data dictionary

        Returns:
            True if safe to grade (submitted but not yet graded)
        """
        # Check workflow_state
        workflow_state = submission.get('workflow_state', '')

        # Skip if already graded by a teacher
        # Only workflow_state='graded' reliably indicates an existing grade
        if workflow_state == 'graded':
            return False

        # Skip if not submitted (nothing to grade)
        if workflow_state in ['unsubmitted', 'not_submitted']:
            return False

        # If workflow_state is 'submitted' or 'pending_review', safe to grade
        # Note: These submissions may have score=0, which is a Canvas placeholder
        # for submitted work, NOT an indication of being graded
        return True

    def has_manual_grades(self, course_id: int, assignment_id: int) -> bool:
        """
        Check if assignment has any manually-entered grades.

        Used for additional safety - can be used to skip entire assignment
        if manual grading detected.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            True if manual grades detected
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {'per_page': 100}

        try:
            # Get first page of submissions
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            submissions = response.json()

            # Get assignment details to know points_possible
            assignment_url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}"
            assignment_response = requests.get(assignment_url, headers=self.headers, timeout=30)
            assignment_response.raise_for_status()
            assignment = assignment_response.json()
            points_possible = assignment.get('points_possible', 0)

            # Check for unusual scores (likely manual)
            for sub in submissions:
                if sub.get('workflow_state') == 'graded':
                    score = sub.get('score', 0)

                    # If score is not 0 or full points, likely manual
                    # (Complete/Incomplete should only be 0 or full points)
                    if score not in [0, points_possible, None]:
                        return True

            return False

        except requests.exceptions.RequestException:
            # On error, assume safe and return False
            return False

    def get_graded_count(self, submissions: Dict[int, Dict[str, Any]]) -> int:
        """
        Count submissions that are already graded.

        Args:
            submissions: Dict of {user_id: submission_data}

        Returns:
            Number of already-graded submissions
        """
        return sum(
            1 for sub in submissions.values()
            if not self._is_safe_to_grade(sub)
        )

    def get_gradeable_count(self, submissions: Dict[int, Dict[str, Any]]) -> int:
        """
        Count submissions that are safe to grade.

        Args:
            submissions: Dict of {user_id: submission_data}

        Returns:
            Number of gradeable submissions
        """
        return sum(
            1 for sub in submissions.values()
            if self._is_safe_to_grade(sub)
        )

    def get_graded_user_ids(self, submissions: Dict[int, Dict[str, Any]]) -> set:
        """
        Get set of user IDs that already have grades.

        Args:
            submissions: Dict of {user_id: submission_data}

        Returns:
            Set of user_ids that are already graded
        """
        return {
            uid for uid, sub in submissions.items()
            if not self._is_safe_to_grade(sub)
        }

    def partition_submissions(self, submissions: Dict[int, Dict[str, Any]]) -> tuple:
        """
        Partition submissions into gradeable and already-graded.

        Args:
            submissions: Dict of {user_id: submission_data}

        Returns:
            Tuple of (gradeable_dict, graded_dict)
        """
        gradeable = {}
        graded = {}

        for user_id, submission in submissions.items():
            if self._is_safe_to_grade(submission):
                gradeable[user_id] = submission
            else:
                graded[user_id] = submission

        return gradeable, graded
