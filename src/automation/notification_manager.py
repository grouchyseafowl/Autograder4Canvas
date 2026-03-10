"""
Canvas Autograder - Notification Manager
Sends daily digest email of students marked incomplete.
"""

import os
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
    canvas_base_url: str = ""

    @property
    def submission_url(self) -> str:
        base = self.canvas_base_url or os.getenv("CANVAS_BASE_URL", "https://institution.instructure.com")
        return (
            f"{base}/courses/{self.course_id}"
            f"/assignments/{self.assignment_id}/submissions/{self.student_id}"
        )


@dataclass
class NewAssignmentGroupEvent:
    """A new assignment group detected in Canvas that needs configuration."""

    course_name: str
    course_id: int
    group_name: str
    group_id: int
    canvas_base_url: str = ""

    @property
    def assignments_url(self) -> str:
        """Link to view assignments in this course."""
        base = self.canvas_base_url or os.getenv("CANVAS_BASE_URL", "https://institution.instructure.com")
        return f"{base}/courses/{self.course_id}/assignments"


class NotificationManager:
    """Collects incomplete events and sends digest via n8n webhook."""

    def __init__(self, webhook_url: str, recipient_email: str):
        self.webhook_url = webhook_url
        self.recipient_email = recipient_email
        self.events: List[IncompleteEvent] = []
        self.new_group_events: List[NewAssignmentGroupEvent] = []
        self.logger = logging.getLogger('autograder_automation')

    def add_event(self, event: IncompleteEvent):
        self.events.append(event)

    def add_new_group_event(self, event: NewAssignmentGroupEvent):
        """Add a new assignment group detection event."""
        self.new_group_events.append(event)

    def has_events(self) -> bool:
        return len(self.events) > 0 or len(self.new_group_events) > 0

    def send_digest(self):
        """Send digest email via n8n webhook if there are any events."""
        if not self.events and not self.new_group_events:
            self.logger.info("  📧 No events — skipping notification email")
            return

        # Create subject based on what we're reporting
        parts = []
        if self.events:
            parts.append(f"{len(self.events)} Incomplete")
        if self.new_group_events:
            parts.append(f"{len(self.new_group_events)} New Groups")

        subject = f"Autograder Report: {' + '.join(parts)} — {datetime.now().strftime('%b %d, %Y')}"
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
                timeout=(5, 10)  # (connect timeout, read timeout)
            )
            response.raise_for_status()

            # Build notification summary
            summary_parts = []
            if self.events:
                summary_parts.append(f"{len(self.events)} incomplete event(s)")
            if self.new_group_events:
                summary_parts.append(f"{len(self.new_group_events)} new group(s)")

            self.logger.info(
                f"  📧 Notification sent: {', '.join(summary_parts)} "
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
            "<h3>Autograder — Status Report</h3>"
            f"<p>Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>"
            "<hr>"
        )

        # NEW ASSIGNMENT GROUPS SECTION - Show first for visibility
        if self.new_group_events:
            sections.append("<h4>⚠️ New Assignment Groups Detected</h4>")
            sections.append(
                "<p>These assignment groups were found in Canvas but are not configured "
                "for auto-grading. Assignments in these groups will not be graded until you "
                "add them to your configuration.</p>"
            )
            sections.append(_html_new_groups_table(self.new_group_events))
            sections.append(
                "<p><strong>To configure:</strong> Run "
                "<code>python3 src/run_automation.py --update-config</code></p>"
            )
            sections.append("<hr>")

        # Existing incomplete events sections
        if ci_events:
            sections.append("<h4>Incomplete Submissions</h4>")
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
            f"Autograder — Status Report",
            f"Run: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        # New assignment groups section
        if self.new_group_events:
            lines.append("⚠️  NEW ASSIGNMENT GROUPS DETECTED ⚠️")
            lines.append("")
            lines.append("The following assignment groups need to be configured:")
            lines.append("")
            lines.extend(_text_new_groups_table(self.new_group_events))
            lines.append("")
            lines.append("To configure: python3 src/run_automation.py --update-config")
            lines.append("")
            lines.append("=" * 60)
            lines.append("")

        # Existing incomplete events sections
        if ci_events:
            lines.append("── Incomplete Submissions ──")
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


def _html_new_groups_table(events: List[NewAssignmentGroupEvent]) -> str:
    """Render new assignment groups as an HTML table."""
    rows = []
    for e in events:
        rows.append(
            f'<tr>'
            f'<td>{e.course_name}</td>'
            f'<td><strong>{e.group_name}</strong></td>'
            f'<td><a href="{e.assignments_url}">View Assignments</a></td>'
            f'</tr>'
        )

    return (
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;background:#fff3cd">'
        '<tr style="background:#ffc107;color:#000">'
        '<th>Course</th><th>Assignment Group</th><th>Link</th>'
        '</tr>'
        + "".join(rows)
        + '</table>'
    )


def _text_new_groups_table(events: List[NewAssignmentGroupEvent]) -> List[str]:
    """Render new assignment groups as plain-text lines."""
    lines = []
    for e in events:
        lines.append(f"  • {e.group_name} ({e.course_name})")
        lines.append(f"    {e.assignments_url}")
        lines.append("")
    return lines
