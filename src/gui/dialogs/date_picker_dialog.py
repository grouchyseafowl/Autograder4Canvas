"""
Small dialog for changing an assignment's due date via context menu.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from dateutil.parser import isoparse
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QDateTimeEdit,
    QPushButton,
    QVBoxLayout,
)

from gui.styles import SPACING_SM, SPACING_MD


class DatePickerDialog(QDialog):
    """Modal dialog that lets the user pick a new due date or clear it."""

    def __init__(
        self, current_due_at: Optional[str] = None, parent=None
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Change Due Date")
        self._cleared = False
        self._accepted = False

        self._setup_ui(current_due_at)

    # ── UI ────────────────────────────────────────────────────────────

    def _setup_ui(self, current_due_at: Optional[str]) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        # Date/time editor
        self._dt_edit = QDateTimeEdit()
        self._dt_edit.setDisplayFormat("MMM dd, yyyy hh:mm AP")
        self._dt_edit.setCalendarPopup(True)

        if current_due_at is not None:
            try:
                dt = isoparse(current_due_at)
                # Convert to local time for display
                dt_local = dt.astimezone()
                qdt = QDateTime(
                    dt_local.year,
                    dt_local.month,
                    dt_local.day,
                    dt_local.hour,
                    dt_local.minute,
                    dt_local.second,
                )
                self._dt_edit.setDateTime(qdt)
            except (ValueError, TypeError):
                self._dt_edit.setDateTime(QDateTime.currentDateTime())
        else:
            self._dt_edit.setDateTime(QDateTime.currentDateTime())

        layout.addWidget(self._dt_edit)

        # Button row: Clear on the left, OK/Cancel on the right
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING_SM)

        clear_btn = QPushButton("Clear")
        clear_btn.setToolTip("Remove the deadline entirely")
        clear_btn.clicked.connect(self._on_clear)
        btn_row.addWidget(clear_btn)

        btn_row.addStretch()

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self._on_ok)
        btn_box.rejected.connect(self.reject)
        btn_row.addWidget(btn_box)

        layout.addLayout(btn_row)

    # ── Slots ─────────────────────────────────────────────────────────

    def _on_ok(self) -> None:
        self._accepted = True
        self._cleared = False
        self.accept()

    def _on_clear(self) -> None:
        self._accepted = True
        self._cleared = True
        self.accept()

    # ── Public API ────────────────────────────────────────────────────

    def get_result(self) -> Tuple[bool, Optional[str]]:
        """Return *(accepted, iso_string_or_none)*.

        - OK pressed:    ``(True, "2026-04-01T23:59:00Z")``
        - Clear pressed: ``(True, None)``
        - Cancelled:     ``(False, None)``
        """
        if not self._accepted:
            return False, None

        if self._cleared:
            return True, None

        qdt = self._dt_edit.dateTime()
        py_dt = datetime(
            qdt.date().year(),
            qdt.date().month(),
            qdt.date().day(),
            qdt.time().hour(),
            qdt.time().minute(),
            qdt.time().second(),
            tzinfo=datetime.now().astimezone().tzinfo,
        )
        utc_dt = py_dt.astimezone(timezone.utc)
        return True, utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
