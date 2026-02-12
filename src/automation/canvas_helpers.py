"""
Canvas Autograder - Canvas API Helpers
Specialized API wrappers for automation system.
"""

import os
import requests
from typing import List, Dict, Any, Set, Optional
from datetime import datetime
from dateutil import parser
import pytz


class CanvasAutomationAPI:
    """Canvas API helpers for automation system."""

    def __init__(self, base_url: str = None, api_token: str = None):
        """
        Initialize Canvas API helper.

        Args:
            base_url: Canvas base URL (defaults to env CANVAS_BASE_URL or Cabrillo)
            api_token: Canvas API token (defaults to env CANVAS_API_TOKEN)
        """
        self.base_url = base_url or os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com")
        self.api_token = api_token or os.getenv("CANVAS_API_TOKEN")

        if not self.api_token:
            raise ValueError("CANVAS_API_TOKEN not set")

        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _get_paginated(self, url: str, params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """
        Fetch all pages from a paginated Canvas API endpoint.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            List of all items from all pages
        """
        items = []
        params = params or {}

        while url:
            try:
                response = requests.get(url, headers=self.headers, params=params, timeout=30)
                response.raise_for_status()
                items.extend(response.json())

                # Get next page URL from Link header
                url = response.links.get('next', {}).get('url')
                params = {}  # Params are in the next URL

            except requests.exceptions.RequestException as e:
                print(f"⚠️  API request failed: {e}")
                # Try once more
                try:
                    response = requests.get(url, headers=self.headers, params=params, timeout=30)
                    response.raise_for_status()
                    items.extend(response.json())
                    url = response.links.get('next', {}).get('url')
                    params = {}
                except:
                    # Give up on this page
                    break

        return items

    def get_current_term_ids(self) -> List[Dict[str, Any]]:
        """
        Get enrollment terms for current semester.

        Returns:
            List of current term dictionaries with id, name, start_at, end_at
        """
        url = f"{self.base_url}/api/v1/accounts/1/terms"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            terms = response.json()['enrollment_terms']
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to fetch terms: {e}")
            return []

        now = datetime.now(pytz.UTC)
        current_terms = []

        for term in terms:
            start_str = term.get('start_at')
            end_str = term.get('end_at')

            if not start_str or not end_str:
                continue

            try:
                start = parser.isoparse(start_str)
                end = parser.isoparse(end_str)

                # Include if currently active (within date range)
                if start <= now <= end:
                    current_terms.append({
                        'id': term['id'],
                        'name': term['name'],
                        'start_at': start_str,
                        'end_at': end_str
                    })
            except (ValueError, TypeError):
                continue

        return current_terms

    def get_courses_in_term(self, term_id: int) -> List[Dict[str, Any]]:
        """
        Get courses in term where user is teacher.

        Args:
            term_id: Canvas enrollment term ID

        Returns:
            List of course dictionaries
        """
        url = f"{self.base_url}/api/v1/courses"
        params = {
            'enrollment_term_id': term_id,
            'enrollment_type': 'teacher',
            'state': ['available'],
            'per_page': 100
        }

        courses = self._get_paginated(url, params)
        return courses

    def get_assignment_groups(self, course_id: int) -> List[Dict[str, Any]]:
        """
        Get assignment groups with assignments.

        Args:
            course_id: Canvas course ID

        Returns:
            List of assignment group dictionaries
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignment_groups"
        params = {'include[]': ['assignments', 'discussion_topic']}

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Failed to fetch assignment groups for course {course_id}: {e}")
            return []

    def get_assignments_in_group(self, course_id: int, group_id: int) -> List[Dict[str, Any]]:
        """
        Get assignments in a specific assignment group.

        Args:
            course_id: Canvas course ID
            group_id: Assignment group ID

        Returns:
            List of assignment dictionaries
        """
        # Get all assignment groups with assignments
        groups = self.get_assignment_groups(course_id)

        for group in groups:
            if group['id'] == group_id:
                return group.get('assignments', [])

        return []

    def check_for_new_assignments(self, course_id: int,
                                  known_group_ids: Set[int]) -> List[Dict[str, Any]]:
        """
        Check if new assignment groups created since last config.

        Args:
            course_id: Canvas course ID
            known_group_ids: Set of known assignment group IDs

        Returns:
            List of new assignment group dictionaries
        """
        current_groups = self.get_assignment_groups(course_id)

        new_groups = [
            g for g in current_groups
            if g['id'] not in known_group_ids
        ]

        return new_groups

    def get_submission_count(self, course_id: int, assignment_id: int) -> int:
        """
        Get count of submissions for an assignment.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Number of submissions
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {'per_page': 1}  # We only need the count

        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()

            # Check for pagination info to get total count
            # Canvas doesn't always provide total count, so we need to check actual submissions
            url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
            params = {'per_page': 100}

            submissions = self._get_paginated(url, params)

            # Count submissions that are actually submitted
            submitted_count = sum(
                1 for sub in submissions
                if sub.get('workflow_state') not in ['unsubmitted', 'not_submitted']
            )

            return submitted_count

        except requests.exceptions.RequestException as e:
            print(f"⚠️  Failed to get submission count: {e}")
            return 0

    def get_assignment_details(self, course_id: int, assignment_id: int) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about an assignment.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Assignment dictionary or None if not found
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Failed to get assignment details: {e}")
            return None

    def is_future_assignment(self, assignment: Dict[str, Any]) -> bool:
        """
        Check if assignment has a future deadline.

        Args:
            assignment: Assignment dictionary

        Returns:
            True if due date is in the future
        """
        due_at = assignment.get('due_at')
        if not due_at:
            return False

        try:
            due_date = parser.isoparse(due_at)
            now = datetime.now(pytz.UTC)
            return due_date > now
        except (ValueError, TypeError):
            return False

    def get_course_name(self, course_id: int) -> str:
        """
        Get course name.

        Args:
            course_id: Canvas course ID

        Returns:
            Course name or empty string if not found
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}"

        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            return response.json().get('name', '')
        except requests.exceptions.RequestException:
            return ''

    def test_connection(self) -> bool:
        """
        Test Canvas API connection.

        Returns:
            True if connection successful
        """
        url = f"{self.base_url}/api/v1/users/self"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException:
            return False
