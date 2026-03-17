"""
Small dialog for changing an assignment's due date via context menu.

Uses an inline QCalendarWidget (never a popup) to avoid the macOS/PySide6
bug where setCalendarPopup(True) opens a calendar that immediately loses
focus and closes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Tuple

from dateutil.parser import isoparse
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QCalendarWidget,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTimeEdit,
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

        # Inline calendar — always visible, no popup (fixes macOS focus-loss bug)
        self._cal = QCalendarWidget()
        self._cal.setGridVisible(False)
        self._cal.setVerticalHeaderFormat(
            QCalendarWidget.VerticalHeaderFormat.NoVerticalHeader
        )
        layout.addWidget(self._cal)

        # Time row
        time_row = QHBoxLayout()
        time_row.setSpacing(SPACING_SM)
        time_lbl = QLabel("Time:")
        time_lbl.setFixedWidth(40)
        time_row.addWidget(time_lbl)
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("hh:mm AP")
        self._time_edit.setFixedWidth(100)
        time_row.addWidget(self._time_edit)
        time_row.addStretch()
        layout.addLayout(time_row)

        # Populate initial date / time
        if current_due_at is not None:
            try:
                dt = isoparse(current_due_at).astimezone()
                self._cal.setSelectedDate(QDate(dt.year, dt.month, dt.day))
                self._time_edit.setTime(QTime(dt.hour, dt.minute, dt.second))
            except (ValueError, TypeError):
                self._time_edit.setTime(QTime(23, 59, 0))
        else:
            self._time_edit.setTime(QTime(23, 59, 0))

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

        qdate = self._cal.selectedDate()
        qtime = self._time_edit.time()
        py_dt = datetime(
            qdate.year(),
            qdate.month(),
            qdate.day(),
            qtime.hour(),
            qtime.minute(),
            qtime.second(),
            tzinfo=datetime.now().astimezone().tzinfo,
        )
        utc_dt = py_dt.astimezone(timezone.utc)
        return True, utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
