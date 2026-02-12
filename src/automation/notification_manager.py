"""
Canvas Autograder - Notification Manager
Sends daily digest email of students marked incomplete.
"""

import logging
import requests
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class IncompleteEvent:
    """A single student marked incomplete on an assignment."""

    course_name: str
    assignment_name: str
    student_name: str
    student_id: int
    course_id: int
    assignment_id: int
    word_count: int
    required_words: int
    category: str = "ci"  # "ci", "discussion_post", "discussion_reply"

    @property
    def submission_url(self) -> str:
        return (
            f"https://cabrillo.instructure.com/courses/{self.course_id}"
            f"/assignments/{self.assignment_id}/submissions/{self.student_id}"
        )


class NotificationManager:
    """Collects incomplete events and sends digest via n8n webhook."""

    def __init__(self, webhook_url: str, recipient_email: str):
        self.webhook_url = webhook_url
        self.recipient_email = recipient_email
        self.events: List[IncompleteEvent] = []
        self.logger = logging.getLogger('autograder_automation')

    def add_event(self, event: IncompleteEvent):
        self.events.append(event)

    def has_events(self) -> bool:
        return len(self.events) > 0

    def send_digest(self):
        """Send digest email via n8n webhook if there are any incomplete events."""
        if not self.events:
            self.logger.info("  📧 No incomplete events — skipping notification email")
            return

        subject = f"Autograder Incomplete Report — {datetime.now().strftime('%b %d, %Y')}"
        html_body = self._build_html_body()
        text_body = self._build_text_body()

        payload = {
            "to": self.recipient_email,
            "subject": subject,
            "html": html_body,
            "text": text_body
        }

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            self.logger.info(
                f"  📧 Notification sent: {len(self.events)} incomplete event(s) "
                f"→ {self.recipient_email}"
            )
        except requests.exceptions.RequestException as e:
            self.logger.error(f"  📧 Failed to send notification email: {e}")

    def _build_html_body(self) -> str:
        """Build HTML email body with tables grouped by category."""
        # Split events into categories, maintaining insertion order
        ci_events = [e for e in self.events if e.category == "ci"]
        post_events = [e for e in self.events if e.category == "discussion_post"]
        reply_events = [e for e in self.events if e.category == "discussion_reply"]

        sections = []
        sections.append(
            "<html><body>"
            "<h3>Autograder — Incomplete Submissions</h3>"
            f"<p>Run: {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
            f"{len(self.events)} total event(s)</p>"
            "<hr>"
        )

        if ci_events:
            sections.append("<h4>Complete/Incomplete Assignments</h4>")
            sections.append(_html_table(ci_events))

        if post_events:
            sections.append("<h4>Discussion Forum — Posts</h4>")
            sections.append(_html_table(post_events))

        if reply_events:
            sections.append("<h4>Discussion Forum — Replies</h4>")
            sections.append(_html_table(reply_events))

        sections.append("</body></html>")
        return "".join(sections)

    def _build_text_body(self) -> str:
        """Build plain-text fallback."""
        ci_events = [e for e in self.events if e.category == "ci"]
        post_events = [e for e in self.events if e.category == "discussion_post"]
        reply_events = [e for e in self.events if e.category == "discussion_reply"]

        lines = [
            f"Autograder — Incomplete Submissions",
            f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(self.events)} event(s)",
            "",
        ]

        if ci_events:
            lines.append("── Complete/Incomplete Assignments ──")
            lines.extend(_text_table(ci_events))
            lines.append("")

        if post_events:
            lines.append("── Discussion Forum — Posts ──")
            lines.extend(_text_table(post_events))
            lines.append("")

        if reply_events:
            lines.append("── Discussion Forum — Replies ──")
            lines.extend(_text_table(reply_events))

        return "\n".join(lines)


def _html_table(events: List[IncompleteEvent]) -> str:
    """Render a list of events as an HTML table."""
    rows = []
    for e in events:
        rows.append(
            f'<tr>'
            f'<td>{e.course_name}</td>'
            f'<td>{e.assignment_name}</td>'
            f'<td>{e.student_name}</td>'
            f'<td>{e.word_count} / {e.required_words}</td>'
            f'<td><a href="{e.submission_url}">View</a></td>'
            f'</tr>'
        )

    return (
        '<table border="1" cellpadding="4" cellspacing="0" style="border-collapse:collapse;width:100%">'
        '<tr style="background:#f0f0f0">'
        '<th>Course</th><th>Assignment</th><th>Student</th><th>Words (got/need)</th><th>Link</th>'
        '</tr>'
        + "".join(rows)
        + '</table>'
    )


def _text_table(events: List[IncompleteEvent]) -> List[str]:
    """Render a list of events as plain-text lines."""
    lines = []
    for e in events:
        lines.append(
            f"  {e.student_name} — {e.assignment_name} ({e.course_name})\n"
            f"    Words: {e.word_count} / {e.required_words} needed\n"
            f"    {e.submission_url}"
        )
    return lines
