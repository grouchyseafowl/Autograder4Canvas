"""
Bulk Shift Deadlines dialog: shift due/lock/unlock dates for multiple
assignments by N days.
"""
from typing import Dict, List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTextEdit, QSpinBox, QProgressBar, QFrame,
)
from PySide6.QtCore import Qt

from gui.styles import SPACING_SM, SPACING_MD, make_run_button, make_monospace_textedit


class BulkShiftDialog(QDialog):
    """Modal dialog to shift deadlines for selected assignments by N days."""

    def __init__(self, api, editor, course_id: int, assignment_ids: List[int],
                 assignment_names: Dict[int, str], parent=None):
        super().__init__(parent)
        self._api = api
        self._editor = editor
        self._course_id = course_id
        self._assignment_ids = assignment_ids
        self._assignment_names = assignment_names
        self._worker = None
        self._any_ok = False

        self.setWindowTitle("Bulk Shift Deadlines")
        self.setMinimumWidth(520)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        count = len(self._assignment_ids)
        info_label = QLabel(
            f"<b>Selected:</b> {count} assignment{'s' if count != 1 else ''}"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Shift input
        form = QFormLayout()
        form.setSpacing(SPACING_SM)

        self._delta_spin = QSpinBox()
        self._delta_spin.setRange(-365, 365)
        self._delta_spin.setValue(0)
        self._delta_spin.setSuffix(" days")
        form.addRow("Shift by:", self._delta_spin)

        layout.addLayout(form)

        # Buttons
        btn_row = QHBoxLayout()
        self._run_btn = QPushButton("Shift Deadlines")
        self._run_btn.clicked.connect(self._on_run)
        make_run_button(self._run_btn)
        btn_row.addWidget(self._run_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Progress bar (hidden until run)
        self._progress = QProgressBar()
        self._progress.setRange(0, len(self._assignment_ids))
        self._progress.setValue(0)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # Results area (hidden until run)
        self._results = QTextEdit()
        self._results.setReadOnly(True)
        make_monospace_textedit(self._results)
        self._results.setVisible(False)
        self._results.setMinimumHeight(200)
        layout.addWidget(self._results)

        # Close button (hidden until done)
        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setVisible(False)
        layout.addWidget(self._close_btn)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        delta_days = self._delta_spin.value()

        # Disable controls
        self._run_btn.setEnabled(False)
        self._delta_spin.setEnabled(False)
        self._cancel_btn.setEnabled(False)

        # Show progress and results
        self._progress.setVisible(True)
        self._results.setVisible(True)
        self._results.clear()

        from gui.workers import BulkShiftDeadlinesWorker

        self._worker = BulkShiftDeadlinesWorker(
            self._api, self._editor, self._course_id,
            self._assignment_ids, delta_days,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.item_done.connect(self._on_item_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_item_done(self, assignment_id: int, result) -> None:
        name = self._assignment_names.get(assignment_id, str(assignment_id))
        status = "OK" if result.ok else "FAIL"
        self._results.append(f"[{status}] {name}: {result.message}")

        if result.ok:
            self._any_ok = True

        # Auto-scroll
        sb = self._results.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_all_done(self, results: list) -> None:
        ok_count = sum(1 for _, r in results if r.ok)
        fail_count = len(results) - ok_count
        self._results.append(
            f"\nDone. {ok_count} succeeded, {fail_count} failed."
        )

        sb = self._results.verticalScrollBar()
        sb.setValue(sb.maximum())

        self._close_btn.setVisible(True)

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    @property
    def was_modified(self) -> bool:
        """Return True if any deadline edits succeeded."""
        return self._any_ok
