"""
Canvas submission retrieval for the Insights Engine.

Uses CanvasAutomationAPI for pagination and auth. Fetches raw Canvas
submission dicts and discussion entries, does NOT do preprocessing —
just gets raw data.
"""

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class DataFetcher:
    """Fetch submissions and discussion entries from Canvas API."""

    def __init__(self, api):
        """
        Parameters
        ----------
        api : CanvasAutomationAPI instance (from canvas_helpers.py)
        """
        self._api = api

    def fetch_submissions(
        self,
        course_id: int,
        assignment_id: int,
    ) -> List[Dict[str, Any]]:
        """Fetch all submissions for an assignment.

        Returns list of Canvas submission dicts, each containing:
        - user_id, user (with name), submitted_at, submission_type,
          body, attachments, etc.
        """
        url = (
            f"{self._api.base_url}/api/v1/courses/{course_id}"
            f"/assignments/{assignment_id}/submissions"
        )
        params = {
            "per_page": 100,
            "include[]": "user",
        }
        try:
            submissions = self._api._get_paginated(url, params)
        except Exception as e:
            log.error("Failed to fetch submissions for assignment %s: %s",
                      assignment_id, e)
            return []

        # Filter out submissions with no actual submission
        result = []
        for sub in submissions:
            if sub.get("workflow_state") == "unsubmitted" and not sub.get("body"):
                continue
            # Normalize user name
            user = sub.get("user", {})
            if user:
                sub["student_name"] = user.get("name", f"Student {sub.get('user_id')}")
            else:
                sub["student_name"] = f"Student {sub.get('user_id')}"
            sub["student_id"] = str(sub.get("user_id", ""))
            result.append(sub)

        return result

    def fetch_discussion_entries(
        self,
        course_id: int,
        topic_id: int,
    ) -> List[Dict[str, Any]]:
        """Fetch all discussion entries for a topic, grouped by student.

        Discussion posts need special handling: fetch via /view endpoint,
        flatten nested replies, group by student. Each student's
        contributions become a single "submission" for analysis.

        Returns list of dicts, each with:
        - student_id, student_name, body (all posts concatenated),
          post_count, reply_count
        """
        url = (
            f"{self._api.base_url}/api/v1/courses/{course_id}"
            f"/discussion_topics/{topic_id}/view"
        )
        try:
            import requests
            resp = requests.get(url, headers=self._api.headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.error("Failed to fetch discussion topic %s: %s", topic_id, e)
            return []

        participants = {
            str(p["id"]): p.get("display_name", f"Student {p['id']}")
            for p in data.get("participants", [])
        }

        # Flatten all entries and replies
        student_posts: Dict[str, List[Dict]] = {}

        def _collect(entries: List[Dict], is_reply: bool = False) -> None:
            for entry in entries:
                uid = str(entry.get("user_id", ""))
                if not uid or entry.get("deleted"):
                    continue
                if uid not in student_posts:
                    student_posts[uid] = []
                student_posts[uid].append({
                    "text": entry.get("message", ""),
                    "is_reply": is_reply,
                    "created_at": entry.get("created_at"),
                })
                # Recurse into replies
                for reply in entry.get("replies", []):
                    _collect([reply], is_reply=True)

        _collect(data.get("view", []), is_reply=False)

        # Build submission-like dicts grouped by student
        result = []
        for uid, posts in student_posts.items():
            post_texts = []
            post_count = 0
            reply_count = 0
            for p in sorted(posts, key=lambda x: x.get("created_at") or ""):
                text = p["text"] or ""
                if text.strip():
                    prefix = "[Reply]" if p["is_reply"] else "[Post]"
                    post_texts.append(f"{prefix} {text}")
                if p["is_reply"]:
                    reply_count += 1
                else:
                    post_count += 1

            if not post_texts:
                continue

            combined_body = "\n\n".join(post_texts)
            result.append({
                "student_id": uid,
                "student_name": participants.get(uid, f"Student {uid}"),
                "user_id": int(uid) if uid.isdigit() else uid,
                "body": combined_body,
                "submission_type": "discussion_topic",
                "post_count": post_count,
                "reply_count": reply_count,
                "submitted_at": posts[-1].get("created_at") if posts else None,
            })

        return result

    def fetch_assignment_info(
        self,
        course_id: int,
        assignment_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Fetch assignment metadata (name, due_at, description, etc.)."""
        url = (
            f"{self._api.base_url}/api/v1/courses/{course_id}"
            f"/assignments/{assignment_id}"
        )
        try:
            import requests
            resp = requests.get(url, headers=self._api.headers, timeout=30)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            log.error("Failed to fetch assignment info %s: %s", assignment_id, e)
            return None
