"""
Bulk Run dialog: select multiple courses, configure scope and options,
then run Preview Run or Run & Post Grades across all selected courses.
"""
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QWidget, QCheckBox, QTextEdit,
    QProgressBar, QSizePolicy, QGroupBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette, QFont

from gui.styles import (
    SPACING_SM, SPACING_MD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    AMBER_BTN,
    make_run_button, make_secondary_button, make_monospace_textedit,
)

# ---------------------------------------------------------------------------
# Modality display
# ---------------------------------------------------------------------------

_FORMAT_TAGS = {
    "on_campus": ("IP",  "#7DAB72"),
    "online":    ("OL",  "#5BA8C9"),
    "blended":   ("HY",  "#C97AB8"),
    "hybrid":    ("HY",  "#C97AB8"),
}

# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_PANE_QSS = f"""
    QFrame#bulkPane {{
        background: qradialgradient(cx:0.5,cy:0.5,radius:0.9,
            stop:0.00 #201A08, stop:0.70 #130E04, stop:1.00 #090702);
        border: 1px solid {BORDER_DARK};
        border-top-color: {BORDER_AMBER};
        border-radius: 8px;
    }}
"""

_SCROLL_QSS = f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}
"""

_SECTION_QSS = f"""
    color: {PHOSPHOR_DIM};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
    background: transparent;
    border: none;
    padding: 6px 0 2px 0;
"""

_CB_QSS = f"""
    QCheckBox {{
        color: {PHOSPHOR_MID};
        font-size: 12px;
        background: transparent;
        spacing: 6px;
    }}
    QCheckBox:hover {{ color: {PHOSPHOR_HOT}; }}
    QCheckBox::indicator {{
        width: 13px; height: 13px;
        border: 1px solid {BORDER_AMBER};
        border-radius: 3px;
        background: {BG_INSET};
    }}
    QCheckBox::indicator:checked {{
        background: {AMBER_BTN};
        border-color: {PHOSPHOR_HOT};
    }}
"""

_SCOPE_CB_QSS = f"""
    QCheckBox {{
        color: {PHOSPHOR_MID};
        font-size: 12px;
        background: transparent;
        spacing: 8px;
    }}
    QCheckBox:hover {{ color: {PHOSPHOR_HOT}; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid {BORDER_AMBER};
        border-radius: 3px;
        background: {BG_INSET};
    }}
    QCheckBox::indicator:checked {{
        background: {AMBER_BTN};
        border-color: {PHOSPHOR_HOT};
    }}
"""


_PILL_QSS = f"""
    QPushButton {{
        background: rgba(58,40,8,0.30);
        color: {PHOSPHOR_MID};
        border: 1px solid {BORDER_AMBER};
        border-radius: 9px;
        padding: 1px 9px;
        font-size: 11px;
        min-height: 20px;
    }}
    QPushButton:hover {{
        background: rgba(80,55,12,0.45);
        color: {PHOSPHOR_HOT};
        border-color: {PHOSPHOR_MID};
    }}
    QPushButton:pressed {{
        background: rgba(240,168,48,0.18);
        border-color: {PHOSPHOR_HOT};
        color: {PHOSPHOR_HOT};
    }}
"""


# ---------------------------------------------------------------------------
# _CourseRow — one selectable course item in the list
# ---------------------------------------------------------------------------

class _CourseRow(QWidget):
    toggled = Signal(int, bool)   # (course_id, checked)

    def __init__(self, course: dict, parent=None):
        super().__init__(parent)
        self._course = course
        cid = course.get("id", 0)
        code = course.get("code") or course.get("name", "")
        title = course.get("nickname") or course.get("title") or ""
        fmt = (course.get("format") or "").lower()

        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 3, 8, 3)
        lo.setSpacing(7)

        self._cb = QCheckBox()
        self._cb.setStyleSheet(_CB_QSS)
        self._cb.toggled.connect(lambda v: self.toggled.emit(cid, v))
        lo.addWidget(self._cb)

        # Modality pill
        tag_info = _FORMAT_TAGS.get(fmt)
        if tag_info:
            tag_label, tag_color = tag_info
            pill = QLabel(tag_label)
            pill.setFixedSize(26, 16)
            pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
            pill.setStyleSheet(
                f"color: {tag_color}; font-size: 9px; font-weight: bold;"
                f" border: 1px solid {tag_color}; border-radius: 3px;"
                f" background: transparent;"
            )
            lo.addWidget(pill)

        # Course code + title
        code_lbl = QLabel(code)
        code_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 12px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        code_lbl.setMinimumWidth(0)
        lo.addWidget(code_lbl)

        if title:
            title_lbl = QLabel(title)
            title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 11px;"
                f" background: transparent; border: none;"
            )
            title_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            lo.addWidget(title_lbl, 1)
        else:
            lo.addStretch()

        self.setStyleSheet("background: transparent;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def course_id(self) -> int:
        return self._course.get("id", 0)

    def fmt(self) -> str:
        return (self._course.get("format") or "").lower()

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def set_checked(self, v: bool) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(v)
        self._cb.blockSignals(False)
        self.toggled.emit(self.course_id(), v)

    def mousePressEvent(self, event):
        self._cb.setChecked(not self._cb.isChecked())


# ---------------------------------------------------------------------------
# BulkRunDialog
# ---------------------------------------------------------------------------

class BulkRunDialog(QDialog):
    """Configure and launch a grading run across multiple courses."""

    def __init__(self, api, courses_by_term: list, parent=None):
        """
        courses_by_term: [(term_id, term_name, is_current, [course_dicts]), ...]
        """
        super().__init__(parent)
        self._api = api
        self._courses_by_term = courses_by_term
        self._worker = None
        self._course_rows: List[_CourseRow] = []

        self.setWindowTitle("Bulk Run")
        self.setMinimumSize(780, 520)
        self.resize(860, 600)
        self._setup_ui()
        self._update_run_buttons()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 16, 16, 16)
        outer.setSpacing(SPACING_MD)

        # Title
        title = QLabel("BULK RUN")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 16px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        sub = QLabel(
            "Select courses and configure the grading run. "
            "Applies to all autogradeable assignments matching the chosen scope."
        )
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(sub)

        sep = self._hsep()
        outer.addWidget(sep)

        # Main two-pane row
        pane_row = QHBoxLayout()
        pane_row.setSpacing(10)
        pane_row.addWidget(self._build_course_pane(), 0)
        pane_row.addWidget(self._build_config_pane(), 1)
        outer.addLayout(pane_row, 1)

        sep2 = self._hsep()
        outer.addWidget(sep2)

        # Footer: status label + buttons
        footer = QHBoxLayout()
        self._status_lbl = QLabel("0 courses selected")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px; background: transparent;"
        )
        footer.addWidget(self._status_lbl)
        footer.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self._cancel_btn)

        self._preview_btn = QPushButton("⊙  Preview Run")
        self._preview_btn.setToolTip(
            "Run grading logic and integrity check across selected courses,\n"
            "but do NOT post any grades to Canvas. Review the output first."
        )
        self._preview_btn.clicked.connect(lambda: self._on_run(dry_run=True))
        make_secondary_button(self._preview_btn)
        footer.addWidget(self._preview_btn)

        self._run_btn = QPushButton("▶  Run & Post Grades")
        self._run_btn.clicked.connect(lambda: self._on_run(dry_run=False))
        make_run_button(self._run_btn)
        footer.addWidget(self._run_btn)

        outer.addLayout(footer)

        # Progress + log (hidden until run starts)
        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; color: {PHOSPHOR_MID}; text-align: center; }}"
            f"QProgressBar::chunk {{ background: {AMBER_BTN}; border-radius: 3px; }}"
        )
        self._progress_bar.hide()
        outer.addWidget(self._progress_bar)

        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        make_monospace_textedit(self._log_output)
        self._log_output.setMinimumHeight(160)
        self._log_output.hide()
        outer.addWidget(self._log_output)

        self._post_row_widget = QWidget()
        post_row = QHBoxLayout(self._post_row_widget)
        post_row.setContentsMargins(0, 0, 0, 0)
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        post_row.addWidget(self._stop_btn)
        self._open_btn = QPushButton("Open Output")
        self._open_btn.clicked.connect(self._on_open_output)
        post_row.addWidget(self._open_btn)
        post_row.addStretch()
        self._post_row_widget.hide()
        outer.addWidget(self._post_row_widget)

    def _build_course_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("bulkPane")
        pane.setStyleSheet(_PANE_QSS)
        pane.setFixedWidth(290)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(SPACING_SM)

        hdr = QLabel("SELECT COURSES")
        hdr.setStyleSheet(_SECTION_QSS)
        lo.addWidget(hdr)

        # Quick-select — two rows so labels have room
        def _qs_btn(label, fmt):
            btn = QPushButton(label)
            btn.setStyleSheet(_PILL_QSS)
            btn.setFixedHeight(22)
            btn.clicked.connect(lambda _, f=fmt: self._quick_select(f))
            return btn

        qs_row1 = QHBoxLayout()
        qs_row1.setSpacing(4)
        qs_row1.addWidget(_qs_btn("All", None))
        qs_row1.addStretch()
        lo.addLayout(qs_row1)

        qs_row2 = QHBoxLayout()
        qs_row2.setSpacing(4)
        for label, fmt in [("In Person", "on_campus"), ("Online", "online"), ("Hybrid", "blended")]:
            qs_row2.addWidget(_qs_btn(label, fmt))
        qs_row2.addStretch()
        lo.addLayout(qs_row2)

        lo.addWidget(self._hsep())

        # Scrollable course list
        scroll = QScrollArea()
        scroll.setObjectName("bulkCourseScroll")
        scroll.setStyleSheet(_SCROLL_QSS)
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        content.setStyleSheet(f"background: {BG_INSET};")
        content_lo = QVBoxLayout(content)
        content_lo.setContentsMargins(0, 4, 0, 4)
        content_lo.setSpacing(0)

        for term_id, term_name, is_current, courses in self._courses_by_term:
            term_lbl = QLabel(term_name.upper() + ("  ●" if is_current else ""))
            term_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT if is_current else PHOSPHOR_DIM};"
                f" font-size: 10px; font-weight: bold; letter-spacing: 1px;"
                f" background: transparent; border: none;"
                f" padding: 8px 8px 2px 8px;"
            )
            content_lo.addWidget(term_lbl)

            for course in courses:
                row = _CourseRow(course)
                row.toggled.connect(self._on_course_toggled)
                self._course_rows.append(row)
                content_lo.addWidget(row)

        content_lo.addStretch()
        scroll.setWidget(content)
        lo.addWidget(scroll, 1)

        return pane

    def _build_config_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("bulkPane")
        pane.setStyleSheet(_PANE_QSS)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(16, 14, 16, 14)
        lo.setSpacing(SPACING_MD)

        # ── Scope section ────────────────────────────────────────────────
        scope_hdr = QLabel("SCOPE")
        scope_hdr.setStyleSheet(_SECTION_QSS)
        lo.addWidget(scope_hdr)

        self._scope_past_due = QCheckBox("All past-due assignments")
        self._scope_past_due.setStyleSheet(_SCOPE_CB_QSS)
        self._scope_past_due.setChecked(True)
        self._scope_past_due.setToolTip("Include assignments whose deadline has already passed.")
        self._scope_past_due.toggled.connect(self._on_scope_changed)
        lo.addWidget(self._scope_past_due)

        self._scope_last_week = QCheckBox("Due last week only")
        self._scope_last_week.setStyleSheet(_SCOPE_CB_QSS)
        self._scope_last_week.setToolTip(
            "Restrict past-due scope to assignments whose deadline\n"
            "fell within the last 7 days."
        )
        self._scope_last_week.setChecked(True)   # default on when past-due is on
        lo.addWidget(self._scope_last_week)

        self._scope_submitted = QCheckBox("All submitted assignments (ungraded)")
        self._scope_submitted.setStyleSheet(_SCOPE_CB_QSS)
        self._scope_submitted.setToolTip(
            "Include assignments that have ungraded student submissions,\n"
            "regardless of deadline."
        )
        self._scope_submitted.toggled.connect(self._on_scope_changed)
        lo.addWidget(self._scope_submitted)

        lo.addWidget(self._hsep())

        # ── Options section ──────────────────────────────────────────────
        opt_hdr = QLabel("OPTIONS")
        opt_hdr.setStyleSheet(_SECTION_QSS)
        lo.addWidget(opt_hdr)

        self._opt_mark_incomplete = QCheckBox(
            "Mark unsubmitted past-due assignments as Incomplete"
        )
        self._opt_mark_incomplete.setStyleSheet(_SCOPE_CB_QSS)
        self._opt_mark_incomplete.setToolTip(
            "For past-due assignments with no submission, assign an Incomplete grade."
        )
        lo.addWidget(self._opt_mark_incomplete)

        self._opt_run_aic = QCheckBox("Run academic integrity check")
        self._opt_run_aic.setStyleSheet(_SCOPE_CB_QSS)
        self._opt_run_aic.setToolTip(
            "Run the academic integrity checker alongside grading.\n"
            "Flags are reported but do not affect grades."
        )
        lo.addWidget(self._opt_run_aic)

        self._opt_preserve = QCheckBox("Preserve existing grades")
        self._opt_preserve.setStyleSheet(_SCOPE_CB_QSS)
        self._opt_preserve.setChecked(True)
        self._opt_preserve.setToolTip(
            "Do not overwrite grades that have already been posted."
        )
        lo.addWidget(self._opt_preserve)

        # Restore persisted defaults
        try:
            from settings import load_settings
            s = load_settings()
            self._opt_run_aic.setChecked(bool(s.get("run_aic_default", False)))
            self._opt_mark_incomplete.setChecked(
                bool(s.get("grade_missing_as_incomplete", False))
            )
        except Exception:
            pass

        lo.addStretch()
        return pane

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _hsep() -> QFrame:
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        return sep

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _quick_select(self, fmt) -> None:
        # Normalise: "blended" and "hybrid" are equivalent
        _aliases = {"blended": {"blended", "hybrid"}, "hybrid": {"blended", "hybrid"}}

        if fmt == "__clear__":
            for row in self._course_rows:
                row.set_checked(False)
            return

        # Determine which rows are in scope
        if fmt is None:  # "All"
            target_rows = self._course_rows
        else:
            match_fmts = _aliases.get(fmt, {fmt})
            target_rows = [r for r in self._course_rows if r.fmt() in match_fmts]

        # Toggle: if all targets are already checked, uncheck; otherwise check all
        all_checked = target_rows and all(r.is_checked() for r in target_rows)
        for row in target_rows:
            row.set_checked(not all_checked)

    def _on_course_toggled(self, course_id: int, checked: bool) -> None:
        self._update_run_buttons()

    def _on_scope_changed(self) -> None:
        past_due_on = self._scope_past_due.isChecked()
        self._scope_last_week.setEnabled(past_due_on)
        if past_due_on:
            self._scope_last_week.setChecked(True)   # auto-enable as default
        else:
            self._scope_last_week.setChecked(False)
        self._update_run_buttons()

    def _update_run_buttons(self) -> None:
        n_courses = sum(1 for r in self._course_rows if r.is_checked())
        scope_ok = (self._scope_past_due.isChecked()
                    or self._scope_submitted.isChecked())
        enabled = n_courses > 0 and scope_ok
        self._run_btn.setEnabled(enabled)
        self._preview_btn.setEnabled(enabled)

        if n_courses == 0:
            self._status_lbl.setText("No courses selected")
        elif not scope_ok:
            self._status_lbl.setText(f"{n_courses} course(s) selected — choose at least one scope")
        else:
            self._status_lbl.setText(f"{n_courses} course(s) selected")

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self, dry_run: bool) -> None:
        selected_courses = [
            (r.course_id(),
             r._course.get("name", ""),
             r._course.get("term_id", 0))
            for r in self._course_rows if r.is_checked()
        ]
        if not selected_courses:
            return

        scope = {
            "past_due":      self._scope_past_due.isChecked(),
            "submitted":     self._scope_submitted.isChecked(),
            "last_week_only": self._scope_last_week.isChecked(),
        }
        options = {
            "run_aic":        self._opt_run_aic.isChecked(),
            "preserve_grades": self._opt_preserve.isChecked(),
            "min_word_count": 200,
            "post_min_words": 200,
            "reply_min_words": 50,
        }

        mode_label = "PREVIEW RUN" if dry_run else "LIVE RUN — grades WILL be posted"
        self._log_output.clear()
        self._log_output.show()
        self._progress_bar.show()
        self._progress_bar.setRange(0, len(selected_courses))
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat(f"{mode_label}  %v / %m courses")
        self._post_row_widget.show()
        self._run_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self.setMinimumHeight(680)
        self.resize(self.width(), max(self.height(), 720))

        from gui.workers import BulkRunWorker
        self._worker = BulkRunWorker(
            api=self._api,
            course_entries=selected_courses,
            scope=scope,
            options=options,
            dry_run=dry_run,
        )
        self._worker.log_line.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _append_log(self, line: str) -> None:
        self._log_output.append(line)
        sb = self._log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setValue(done)

    def _on_finished(self, success: bool, message: str) -> None:
        self._run_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        icon = "Done" if success else "Error"
        self._append_log(f"\n[{icon}] {message}")
        self._progress_bar.setValue(self._progress_bar.maximum())

        try:
            from settings import load_settings
            from autograder_utils import open_folder, get_output_base_dir
            s = load_settings()
            if s.get("auto_open_folder"):
                open_folder(get_output_base_dir())
        except Exception:
            pass

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("\n[Stopped] Cancellation requested.")

    def _on_open_output(self) -> None:
        try:
            from autograder_utils import open_folder, get_output_base_dir
            open_folder(get_output_base_dir())
        except Exception:
            pass
