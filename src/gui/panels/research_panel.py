"""
Research comparison panel — 3-way classification side-by-side display.

Launched from scripts/launch_research.py only (not the main GUI).
Left sidebar: course/assignment selector + controls.
Right pane: summary table + per-student 3-column comparison cards.
"""

from __future__ import annotations

import csv
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QRadialGradient
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gui.styles import (
    BORDER_AMBER,
    BORDER_DARK,
    BG_CARD,
    BG_INSET,
    BG_PANEL,
    BG_VOID,
    BURN_RED,
    PHOSPHOR_DIM,
    PHOSPHOR_GLOW,
    PHOSPHOR_HOT,
    PHOSPHOR_MID,
    PANE_BG_GRADIENT,
    ROSE_ACCENT,
    ROSE_DIM,
    TERM_GREEN,
    make_content_pane,
    make_h_rule,
    make_run_button,
    make_secondary_button,
    make_section_label,
    px,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Pill colors by axis value
# ---------------------------------------------------------------------------
_PILL_COLOR = {
    "FLAG":     BURN_RED,
    "CRISIS":   BURN_RED,
    "BURNOUT":  "#D87020",
    "ENGAGED":  TERM_GREEN,
    "NONE":     PHOSPHOR_DIM,
    "CLEAR":    PHOSPHOR_DIM,
    "CHECK-IN": ROSE_ACCENT,
}


def _axis_pill(text: str) -> QLabel:
    color = _PILL_COLOR.get(text.upper(), PHOSPHOR_DIM)
    lbl = QLabel(text.upper())
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"color: {color}; font-size: {px(10)}px; font-weight: bold;"
        f" border: 1px solid {color}; border-radius: 3px;"
        f" background: transparent; padding: 1px 6px;"
    )
    lbl.setMaximumWidth(120)
    return lbl


def _dim_label(text: str, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(size)}px;"
        f" background: transparent; border: none;"
    )
    return lbl


def _mid_label(text: str, italic: bool = False, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    style = (
        f"color: {PHOSPHOR_MID}; font-size: {px(size)}px;"
        f" background: transparent; border: none;"
    )
    if italic:
        style += " font-style: italic;"
    lbl.setStyleSheet(style)
    return lbl


def _glow_label(text: str, size: int = 10) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_GLOW}; font-size: {px(size)}px;"
        f" background: transparent; border: none; font-style: italic;"
    )
    return lbl


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w:
            w.deleteLater()
        sub = item.layout()
        if sub:
            _clear_layout(sub)


# ---------------------------------------------------------------------------
# _ResearchAssignRow — single-select radio style
# ---------------------------------------------------------------------------

class _ResearchAssignRow(QWidget):
    selected = Signal(int, str)   # (assignment_id, assignment_name)

    def __init__(self, assignment: dict, parent=None):
        super().__init__(parent)
        self._assign = assignment
        self._selected = False
        self._hovered = False

        name = assignment.get("name", "Untitled")
        due  = assignment.get("due_at", "")
        if due:
            try:
                dt  = datetime.fromisoformat(due.replace("Z", "+00:00"))
                due = dt.strftime("%m/%d")
            except (ValueError, TypeError):
                due = ""

        outer = QHBoxLayout(self)
        outer.setContentsMargins(10, 5, 8, 5)
        outer.setSpacing(6)
        outer.addSpacing(14)   # space for radio dot drawn in paintEvent

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(1)

        self._name_lbl = QLabel(name)
        self._name_lbl.setWordWrap(False)
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        text.addWidget(self._name_lbl)

        if due:
            due_lbl = QLabel(f"due {due}")
            due_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            text.addWidget(due_lbl)

        outer.addLayout(text, 1)
        self.setStyleSheet("background: transparent;")
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def assignment_id(self) -> int:
        return self._assign.get("id", 0)

    def assignment_name(self) -> str:
        return self._assign.get("name", "")

    def set_selected(self, v: bool) -> None:
        self._selected = v
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT if v else PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; border: none;"
        )
        self.update()

    def mousePressEvent(self, event):
        if not self._selected:
            self.selected.emit(self.assignment_id(), self.assignment_name())

    def enterEvent(self, event):
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        is_sel = self._selected
        is_hov = self._hovered
        if is_sel or is_hov:
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.fillRect(self.rect(), QColor("#0A0800"))
            glow_cx = self.width() * 0.18
            glow_cy = self.height() * 0.50
            center_col = QColor(204, 82, 130, 60) if is_sel else QColor(240, 168, 48, 38)
            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            grad = QRadialGradient(glow_cx, glow_cy, self.width() * 0.80)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.7, QColor(center_col.red(), center_col.green(),
                                        center_col.blue(), 8))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())
            p.restore()
            dot_x, dot_y = 8.0, self.height() / 2.0
            p.setPen(Qt.PenStyle.NoPen)
            dot_color = QColor(ROSE_ACCENT) if is_sel else QColor(PHOSPHOR_DIM)
            p.setBrush(dot_color)
            p.drawEllipse(int(dot_x - 3), int(dot_y - 3), 6, 6)
            p.end()
        else:
            super().paintEvent(event)


# ---------------------------------------------------------------------------
# ResearchPanel
# ---------------------------------------------------------------------------

class ResearchPanel(QFrame):
    """3-way classification comparison panel for research data collection."""

    def __init__(self, api=None, store=None, parent=None):
        super().__init__(parent)
        self._api   = api
        self._store = store

        self._worker        = None
        self._assign_worker = None
        self._current_result: Optional[dict] = None
        self._course_id:    Optional[int] = None
        self._course_name:  str = ""
        self._assignment_id:   Optional[int] = None
        self._assignment_name: str = ""
        self._prior_run_id:  Optional[str] = None
        self._prior_run_date: str = ""
        self._assign_rows:   List[_ResearchAssignRow] = []
        self._term_sections: list = []
        self._course_rows:   list = []  # all _CourseRow refs for single-select
        # student_id -> {"card": QFrame, "track_a": QFrame, ...}
        self._student_cards: Dict[str, dict] = {}

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from gui.styles import GripSplitter

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Banner
        banner = QFrame()
        banner.setObjectName("resBanner")
        banner.setFixedHeight(36)
        banner.setStyleSheet(
            "QFrame#resBanner {"
            f"  background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"    stop:0 #1A0A1C, stop:0.5 #200A10, stop:1 #0A0800);"
            f"  border-bottom: 1px solid {ROSE_DIM};"
            "}"
        )
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(16, 0, 16, 0)
        bl.setSpacing(0)
        banner_lbl = QLabel("RESEARCH COMPARISON  ·  3-TRACK CLASSIFICATION")
        banner_lbl.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: {px(11)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        bl.addWidget(banner_lbl)
        bl.addStretch()
        note = QLabel("not for production use")
        note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
            " border: none; font-style: italic;"
        )
        bl.addWidget(note)
        lo.addWidget(banner)

        # Splitter: sidebar | results
        splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(6)
        lo.addWidget(splitter, 1)

        sidebar = self._build_sidebar()
        sidebar.setMinimumWidth(240)
        sidebar.setMaximumWidth(380)
        splitter.addWidget(sidebar)

        self._results_outer = self._build_results_pane()
        splitter.addWidget(self._results_outer)
        splitter.setSizes([300, 1100])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)

        self.setStyleSheet(f"ResearchPanel {{ background: {BG_VOID}; }}")

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("resSidebar")
        sidebar.setStyleSheet(
            "QFrame#resSidebar {"
            f"  background: {BG_PANEL};"
            f"  border-right: 1px solid {BORDER_DARK};"
            "}"
        )
        lo = QVBoxLayout(sidebar)
        lo.setContentsMargins(0, 8, 0, 8)
        lo.setSpacing(0)

        # ── Courses ──
        lo.addWidget(make_section_label("  Courses"))
        lo.addSpacing(2)

        self._course_scroll = QScrollArea()
        self._course_scroll.setWidgetResizable(True)
        self._course_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._course_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_INSET}; }}"
            + _scrollbar_qss()
        )
        self._course_scroll.setMinimumHeight(150)
        self._course_scroll.setMaximumHeight(260)

        self._course_content = QWidget()
        self._course_content.setStyleSheet(f"background: {BG_INSET};")
        self._course_lo = QVBoxLayout(self._course_content)
        self._course_lo.setContentsMargins(0, 0, 0, 0)
        self._course_lo.setSpacing(1)
        self._course_lo.addStretch()
        self._course_scroll.setWidget(self._course_content)
        lo.addWidget(self._course_scroll)

        lo.addSpacing(4)
        lo.addWidget(make_h_rule())
        lo.addSpacing(4)

        # ── Assignments ──
        lo.addWidget(make_section_label("  Assignments"))
        lo.addSpacing(2)

        self._assign_scroll = QScrollArea()
        self._assign_scroll.setWidgetResizable(True)
        self._assign_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._assign_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_INSET}; }}"
            + _scrollbar_qss()
        )
        self._assign_scroll.setMinimumHeight(100)
        self._assign_scroll.setMaximumHeight(200)

        self._assign_content = QWidget()
        self._assign_content.setStyleSheet(f"background: {BG_INSET};")
        self._assign_lo = QVBoxLayout(self._assign_content)
        self._assign_lo.setContentsMargins(0, 0, 0, 0)
        self._assign_lo.setSpacing(1)
        self._assign_placeholder_lbl = QLabel("  select a course")
        self._assign_placeholder_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 8px;"
        )
        self._assign_lo.addWidget(self._assign_placeholder_lbl)
        self._assign_lo.addStretch()
        self._assign_scroll.setWidget(self._assign_content)
        lo.addWidget(self._assign_scroll)

        lo.addSpacing(4)
        lo.addWidget(make_h_rule())
        lo.addSpacing(8)

        # ── Prior run indicator ──
        self._prior_frame = QFrame()
        self._prior_frame.setObjectName("priorFrame")
        self._prior_frame.setStyleSheet(
            "QFrame#priorFrame {"
            f"  background: {BG_CARD}; border: 1px solid {BORDER_DARK};"
            f"  border-radius: 4px; margin: 0 8px;"
            "}"
        )
        plo = QVBoxLayout(self._prior_frame)
        plo.setContentsMargins(8, 6, 8, 6)
        plo.setSpacing(3)

        self._prior_lbl = QLabel("no prior run")
        self._prior_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        plo.addWidget(self._prior_lbl)

        self._prior_track_lbl = QLabel("")
        self._prior_track_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        plo.addWidget(self._prior_track_lbl)
        lo.addWidget(self._prior_frame)
        lo.addSpacing(10)

        # ── Run buttons ──
        btn_wrap = QFrame()
        btn_wrap.setStyleSheet("background: transparent; border: none;")
        blo = QVBoxLayout(btn_wrap)
        blo.setContentsMargins(8, 0, 8, 0)
        blo.setSpacing(6)

        self._btn_run_missing = QPushButton("Run Missing: Track A")
        make_secondary_button(self._btn_run_missing)
        self._btn_run_missing.setMinimumHeight(30)
        self._btn_run_missing.setVisible(False)
        self._btn_run_missing.clicked.connect(self._on_run_missing)
        blo.addWidget(self._btn_run_missing)

        self._btn_run_all = QPushButton("Run Full Comparison")
        make_run_button(self._btn_run_all)
        self._btn_run_all.setMinimumHeight(32)
        self._btn_run_all.setEnabled(False)
        self._btn_run_all.clicked.connect(self._on_run_all)
        blo.addWidget(self._btn_run_all)

        lo.addWidget(btn_wrap)
        lo.addSpacing(6)

        # ── Progress ──
        self._progress_lbl = QLabel("")
        self._progress_lbl.setWordWrap(True)
        self._progress_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )
        lo.addWidget(self._progress_lbl)

        lo.addStretch()
        lo.addWidget(make_h_rule())
        lo.addSpacing(6)

        # ── Export buttons ──
        exp_wrap = QFrame()
        exp_wrap.setStyleSheet("background: transparent; border: none;")
        elo = QHBoxLayout(exp_wrap)
        elo.setContentsMargins(8, 0, 8, 0)
        elo.setSpacing(6)

        self._btn_export_json = QPushButton("Export JSON")
        make_secondary_button(self._btn_export_json)
        self._btn_export_json.setMinimumHeight(28)
        self._btn_export_json.setEnabled(False)
        self._btn_export_json.clicked.connect(self._on_export_json)
        elo.addWidget(self._btn_export_json)

        self._btn_export_csv = QPushButton("Export CSV")
        make_secondary_button(self._btn_export_csv)
        self._btn_export_csv.setMinimumHeight(28)
        self._btn_export_csv.setEnabled(False)
        self._btn_export_csv.clicked.connect(self._on_export_csv)
        elo.addWidget(self._btn_export_csv)

        lo.addWidget(exp_wrap)
        return sidebar

    def _build_results_pane(self) -> QFrame:
        pane = QFrame()
        pane.setObjectName("resResults")
        pane.setStyleSheet(
            "QFrame#resResults { background: " + BG_VOID + "; border: none; }"
        )
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(8)

        # Summary (hidden until results arrive)
        self._summary_frame = QFrame()
        self._summary_frame.setObjectName("resSummary")
        self._summary_frame.setVisible(False)
        self._summary_frame.setStyleSheet(
            "QFrame#resSummary {"
            f"  background: {PANE_BG_GRADIENT};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-top-color: {BORDER_AMBER};"
            f"  border-radius: 6px;"
            "}"
        )
        self._summary_lo = QVBoxLayout(self._summary_frame)
        self._summary_lo.setContentsMargins(14, 10, 14, 10)
        self._summary_lo.setSpacing(4)
        lo.addWidget(self._summary_frame)

        # Column headers
        lo.addWidget(self._build_col_headers())

        # Scroll area for student cards
        self._cards_scroll = QScrollArea()
        self._cards_scroll.setWidgetResizable(True)
        self._cards_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._cards_scroll.setStyleSheet(
            f"QScrollArea {{ border: none; background: {BG_VOID}; }}"
            + _scrollbar_qss(width=8)
        )

        self._cards_widget = QWidget()
        self._cards_widget.setStyleSheet(f"background: {BG_VOID};")
        self._cards_lo = QVBoxLayout(self._cards_widget)
        self._cards_lo.setContentsMargins(0, 0, 0, 0)
        self._cards_lo.setSpacing(8)

        self._empty_lbl = QLabel("Select an assignment to begin.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(13)}px;"
            f" background: transparent; border: none; padding: 40px;"
        )
        self._cards_lo.addWidget(self._empty_lbl)
        self._cards_lo.addStretch()
        self._cards_scroll.setWidget(self._cards_widget)
        lo.addWidget(self._cards_scroll, 1)

        return pane

    def _build_col_headers(self) -> QFrame:
        hdr = QFrame()
        hdr.setStyleSheet(
            f"QFrame {{ background: transparent; border: none;"
            f" border-bottom: 1px solid {BORDER_DARK}; }}"
        )
        hlo = QHBoxLayout(hdr)
        hlo.setContentsMargins(4, 0, 4, 6)
        hlo.setSpacing(8)

        name_hdr = QLabel("STUDENT")
        name_hdr.setFixedWidth(130)
        name_hdr.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        hlo.addWidget(name_hdr)

        for label, color in [
            ("TRACK A  ·  BINARY CONCERN", BURN_RED),
            ("TRACK B  ·  4-AXIS + CHECK-IN", "#D87020"),
            ("TRACK C  ·  OBSERVATION", TERM_GREEN),
        ]:
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color: {color}; font-size: {px(10)}px; font-weight: bold;"
                f" letter-spacing: 1px; background: transparent; border: none;"
            )
            hlo.addWidget(lbl, 1)

        return hdr

    # ── Course/assignment loading ─────────────────────────────────────────────

    def on_terms_loaded(self, terms: list) -> None:
        from gui.dialogs.bulk_run_dialog import _TermSection
        # Clear existing (keep trailing stretch)
        while self._course_lo.count() > 1:
            item = self._course_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._term_sections = []
        self._course_rows.clear()
        for tid, name, is_current in terms:
            section = _TermSection(name, is_current)
            self._course_lo.insertWidget(self._course_lo.count() - 1, section)
            self._term_sections.append((tid, section))

    def on_courses_loaded(self, term_id: int, courses: list) -> None:
        from gui.dialogs.bulk_run_dialog import _CourseRow
        for tid, section in self._term_sections:
            if tid == term_id:
                for course in courses:
                    row = _CourseRow(course)
                    cid   = course.get("id", 0)
                    cname = course.get("name", "")
                    row.toggled.connect(
                        lambda _cid, checked, _cname=cname, _id=cid: (
                            self._on_course_clicked(_id, _cname) if checked else None
                        )
                    )
                    section.add_course_row(row)
                    self._course_rows.append(row)
                break

    def on_courses_done(self) -> None:
        self._course_content.adjustSize()

    def _on_course_clicked(self, course_id: int, course_name: str) -> None:
        if self._course_id == course_id:
            return
        # Single-select: uncheck all other course rows
        for row in self._course_rows:
            if row.course_id() != course_id and row.is_checked():
                row.set_checked(False)
        self._course_id   = course_id
        self._course_name = course_name
        self._assignment_id   = None
        self._assignment_name = ""
        self._prior_run_id    = None
        self._prior_run_date  = ""
        self._btn_run_all.setEnabled(False)
        self._btn_run_missing.setVisible(False)
        self._update_prior_indicator()
        self._load_assignments(course_id)

    def _load_assignments(self, course_id: int) -> None:
        if self._assign_worker:
            self._assign_worker.cancel()
            self._assign_worker = None
        self._assign_rows.clear()
        _clear_layout(self._assign_lo)

        loading = QLabel("  loading...")
        loading.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
            f" background: transparent; border: none; padding: 8px;"
        )
        self._assign_lo.addWidget(loading)
        self._assign_lo.addStretch()

        if not self._api:
            return

        from gui.workers import LoadAssignmentsWorker
        self._assign_worker = LoadAssignmentsWorker(self._api, course_id)
        self._assign_worker.assignments_loaded.connect(self._on_assignments_loaded)
        self._assign_worker.start()

    def _on_assignments_loaded(self, groups: list) -> None:
        _clear_layout(self._assign_lo)
        self._assign_rows.clear()

        if not groups or not any(g.get("assignments") for g in groups):
            empty = QLabel("  no assignments")
            empty.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
                f" background: transparent; border: none; padding: 8px;"
            )
            self._assign_lo.addWidget(empty)
            self._assign_lo.addStretch()
            return

        for group in groups:
            for assign in group.get("assignments", []):
                row = _ResearchAssignRow(assign)
                row.selected.connect(self._on_assignment_clicked)
                self._assign_lo.addWidget(row)
                self._assign_rows.append(row)
        self._assign_lo.addStretch()

    def _on_assignment_clicked(self, assignment_id: int, assignment_name: str) -> None:
        self._assignment_id   = assignment_id
        self._assignment_name = assignment_name
        for row in self._assign_rows:
            row.set_selected(row.assignment_id() == assignment_id)
        self._check_prior_run()
        self._btn_run_all.setEnabled(True)

    # ── Prior run detection ───────────────────────────────────────────────────

    def _check_prior_run(self) -> None:
        if not self._store or not self._course_id or not self._assignment_id:
            self._prior_run_id = None
            self._update_prior_indicator()
            return

        try:
            runs = self._store.get_runs(str(self._course_id))
        except Exception:
            runs = []

        best = None
        for run in runs:
            if str(run.get("assignment_id")) == str(self._assignment_id):
                if run.get("completed_at"):
                    if best is None or run["completed_at"] > best["completed_at"]:
                        best = run

        if best:
            self._prior_run_id   = best["run_id"]
            self._prior_run_date = best.get("completed_at", "")[:10]
            self._update_prior_indicator(found=True)
            self._btn_run_missing.setVisible(True)
            self._load_prior_run(self._prior_run_id)
        else:
            self._prior_run_id   = None
            self._prior_run_date = ""
            self._update_prior_indicator(found=False)
            self._btn_run_missing.setVisible(False)
            self._reset_cards()

    def _update_prior_indicator(self, found: bool = False) -> None:
        if found:
            self._prior_lbl.setText(f"prior run: {self._prior_run_date}")
            self._prior_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            self._prior_track_lbl.setText("Tracks B + C available  |  Track A missing")
            self._prior_track_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
        else:
            self._prior_lbl.setText("no prior run")
            self._prior_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
            self._prior_track_lbl.setText("")

    def _load_prior_run(self, run_id: str) -> None:
        """Populate Tracks B + C from stored data; leave Track A as [not run]."""
        if not self._store:
            return
        try:
            codings = self._store.get_codings(run_id)
        except Exception as exc:
            log.warning("Could not load prior codings: %s", exc)
            return

        self._reset_cards()

        for record in codings:
            student_id   = record.get("student_id", "")
            student_name = record.get("student_name", student_id)
            raw = record.get("coding_record") or {}
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except Exception:
                    raw = {}

            track_b = {
                "axis":              raw.get("wellbeing_axis", ""),
                "signal":            raw.get("wellbeing_signal", ""),
                "confidence":        raw.get("wellbeing_confidence"),
                "prescan_signals":   raw.get("prescan_signals") or [],
                "checkin_flag":      raw.get("checkin_flag"),
                "checkin_reasoning": raw.get("checkin_reasoning", ""),
            }
            track_c = {"observation": raw.get("observation", "")}

            self._ensure_card(student_id, student_name)
            self._populate_track(student_id, "track_b", track_b)
            self._populate_track(student_id, "track_c", track_c)

        self._empty_lbl.setVisible(False)

    # ── Run controls ──────────────────────────────────────────────────────────

    def _on_run_all(self) -> None:
        if self._worker and self._worker.isRunning():
            self._on_cancel()
            return
        if not self._assignment_id:
            return

        self._reset_cards()
        self._student_cards.clear()
        self._btn_run_all.setText("Cancel")
        self._btn_run_missing.setEnabled(False)
        self._btn_export_json.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._progress_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )
        self._progress_lbl.setText("initializing...")
        self._current_result = None

        from gui.workers import ResearchComparisonWorker
        self._worker = ResearchComparisonWorker(
            self._api,
            store=self._store,
            course_id=self._course_id,
            course_name=self._course_name,
            assignment_id=self._assignment_id,
            assignment_name=self._assignment_name,
            is_discussion=False,
            model_tier="medium",
            settings={},
            run_mode="full",
        )
        self._connect_worker(self._worker)
        self._worker.start()

    def _on_run_missing(self) -> None:
        if self._worker and self._worker.isRunning():
            self._on_cancel()
            return
        if not self._prior_run_id:
            return

        self._btn_run_missing.setText("Cancel")
        self._btn_run_all.setEnabled(False)
        self._btn_export_json.setEnabled(False)
        self._btn_export_csv.setEnabled(False)
        self._progress_lbl.setText("running Track A on stored submissions...")
        self._current_result = None

        from gui.workers import ResearchComparisonWorker
        self._worker = ResearchComparisonWorker(
            self._api,
            store=self._store,
            course_id=self._course_id,
            course_name=self._course_name,
            assignment_id=self._assignment_id,
            assignment_name=self._assignment_name,
            is_discussion=False,
            model_tier="medium",
            settings={},
            run_mode="track_a_only",
            prior_run_id=self._prior_run_id,
        )
        self._connect_worker(self._worker)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.cancel()
        self._progress_lbl.setText("cancelling...")

    def _connect_worker(self, worker) -> None:
        worker.progress_update.connect(self._on_progress)
        worker.track_result.connect(self._on_track_result)
        worker.comparison_complete.connect(self._on_complete)
        worker.error.connect(self._on_error)
        worker.finished.connect(self._on_worker_finished)

    def _on_worker_finished(self) -> None:
        self._btn_run_all.setText("Run Full Comparison")
        self._btn_run_all.setEnabled(bool(self._assignment_id))
        self._btn_run_missing.setText("Run Missing: Track A")
        self._btn_run_missing.setEnabled(True)
        if self._prior_run_id:
            self._btn_run_missing.setVisible(True)

    # ── Worker callbacks ──────────────────────────────────────────────────────

    def _on_progress(self, message: str) -> None:
        self._progress_lbl.setText(message)

    def _on_track_result(self, track: str, student_id: str, data: dict) -> None:
        name = data.get("student_name", student_id)
        self._ensure_card(student_id, name)
        self._populate_track(student_id, track, data)
        self._empty_lbl.setVisible(False)

    def _on_complete(self, result: dict) -> None:
        self._current_result = result
        n = result.get("total_students", 0)
        self._progress_lbl.setText(f"complete — {n} students")
        self._btn_export_json.setEnabled(True)
        self._btn_export_csv.setEnabled(True)
        self._rebuild_summary(result)

    def _on_error(self, msg: str) -> None:
        self._progress_lbl.setText(f"error: {msg[:120]}")
        self._progress_lbl.setStyleSheet(
            f"color: {BURN_RED}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding: 0 10px;"
        )

    # ── Card management ───────────────────────────────────────────────────────

    def _reset_cards(self) -> None:
        """Remove all student cards and reset to empty state."""
        _clear_layout(self._cards_lo)
        self._student_cards = {}

        self._empty_lbl = QLabel("Select an assignment to begin.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(13)}px;"
            f" background: transparent; border: none; padding: 40px;"
        )
        self._cards_lo.addWidget(self._empty_lbl)
        self._cards_lo.addStretch()
        self._summary_frame.setVisible(False)
        _clear_layout(self._summary_lo)

    def _ensure_card(self, student_id: str, student_name: str) -> None:
        if student_id in self._student_cards:
            return

        # Insert before trailing stretch
        stretch_idx = self._cards_lo.count() - 1
        card = self._build_card_skeleton(student_id, student_name)
        self._cards_lo.insertWidget(stretch_idx, card)

    def _build_card_skeleton(self, student_id: str, student_name: str) -> QFrame:
        card = make_content_pane(f"card_{abs(hash(student_id)) % 100000:05d}")
        card_lo = QHBoxLayout(card)
        card_lo.setContentsMargins(10, 8, 10, 8)
        card_lo.setSpacing(0)

        # Student name column
        name_col = QFrame()
        name_col.setFixedWidth(130)
        name_col.setStyleSheet("background: transparent; border: none;")
        nclo = QVBoxLayout(name_col)
        nclo.setContentsMargins(0, 2, 8, 2)
        nclo.setSpacing(2)
        nlbl = QLabel(student_name)
        nlbl.setWordWrap(True)
        nlbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        nclo.addWidget(nlbl)
        nclo.addStretch()
        card_lo.addWidget(name_col)

        # 3 track columns with vertical rules between them
        track_cols = {}
        for i, key in enumerate(("track_a", "track_b", "track_c")):
            vline = QFrame()
            vline.setFrameShape(QFrame.Shape.VLine)
            vline.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
            vline.setFixedWidth(1)
            card_lo.addWidget(vline)

            col = QFrame()
            col.setObjectName(f"{student_id}_{key}")
            col.setStyleSheet("background: transparent; border: none;")
            col_lo = QVBoxLayout(col)
            col_lo.setContentsMargins(8, 4, 8, 4)
            col_lo.setSpacing(4)
            empty_lbl = _glow_label("[not run]")
            col_lo.addWidget(empty_lbl)
            col_lo.addStretch()
            card_lo.addWidget(col, 1)
            track_cols[key] = col

        self._student_cards[student_id] = {
            "card": card,
            "track_a": track_cols["track_a"],
            "track_b": track_cols["track_b"],
            "track_c": track_cols["track_c"],
        }
        return card

    def _populate_track(self, student_id: str, track: str, data: dict) -> None:
        info = self._student_cards.get(student_id)
        if not info:
            return
        col: QFrame = info.get(track)
        if not col:
            return
        lo = col.layout()
        _clear_layout(lo)

        if track == "track_a":
            self._fill_track_a(lo, data)
        elif track == "track_b":
            self._fill_track_b(lo, data)
        else:
            self._fill_track_c(lo, data)

    def _fill_track_a(self, lo: QVBoxLayout, data: dict) -> None:
        flagged    = data.get("flagged", False)
        concerns   = data.get("concerns") or []
        bias_warns = data.get("bias_warnings") or []

        lo.addWidget(_axis_pill("FLAG" if flagged else "CLEAR"))
        lo.addSpacing(2)

        if not flagged:
            lo.addWidget(_glow_label("no concerns detected"))
        else:
            for concern in concerns[:3]:
                passage = (concern.get("flagged_passage") or "").strip()
                why     = concern.get("why_flagged", "")
                conf    = concern.get("confidence")
                if passage:
                    display = f'"{passage[:120]}…"' if len(passage) > 120 else f'"{passage}"'
                    lo.addWidget(_mid_label(display, italic=True))
                if why:
                    is_bias = "⚠" in why
                    w_lbl = QLabel(why[:200])
                    w_lbl.setWordWrap(True)
                    w_lbl.setStyleSheet(
                        f"color: {'#D87020' if is_bias else PHOSPHOR_DIM};"
                        f" font-size: {px(10)}px; background: transparent; border: none;"
                    )
                    lo.addWidget(w_lbl)
                if conf is not None:
                    lo.addWidget(_dim_label(f"conf: {float(conf):.2f}", size=9))
                lo.addSpacing(2)

        if bias_warns:
            bw = QLabel(f"⚠ {len(bias_warns)} bias flag(s)")
            bw.setStyleSheet(
                f"color: #D87020; font-size: {px(10)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(bw)

        lo.addStretch()

    def _fill_track_b(self, lo: QVBoxLayout, data: dict) -> None:
        axis     = (data.get("axis") or "").strip()
        signal   = data.get("signal", "")
        conf     = data.get("confidence")
        prescan  = data.get("prescan_signals") or []
        checkin  = data.get("checkin_flag")
        checkin_r = data.get("checkin_reasoning", "")

        lo.addWidget(_axis_pill(axis if axis else "—"))
        lo.addSpacing(2)

        if signal:
            lo.addWidget(_mid_label(signal[:220]))
        if conf is not None:
            lo.addWidget(_dim_label(f"conf: {float(conf):.2f}", size=9))

        if prescan:
            lo.addSpacing(2)
            ps_hdr = QLabel("prescan:")
            ps_hdr.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: {px(9)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(ps_hdr)
            for s in prescan[:2]:
                lo.addWidget(_dim_label(f'"{s[:100]}"', size=9))

        lo.addSpacing(4)
        lo.addWidget(make_h_rule())
        lo.addSpacing(2)

        if checkin is None:
            lo.addWidget(_glow_label("CHECK-IN: n/a"))
        elif checkin:
            lo.addWidget(_axis_pill("CHECK-IN"))
            if checkin_r:
                lo.addWidget(_dim_label(checkin_r[:300]))
        else:
            lo.addWidget(_glow_label("CHECK-IN: no flag"))

        lo.addStretch()

    def _fill_track_c(self, lo: QVBoxLayout, data: dict) -> None:
        obs = data.get("observation", "")
        if obs:
            lbl = QLabel(obs)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            lo.addWidget(lbl)
        else:
            lo.addWidget(_glow_label("[no observation]"))
        lo.addStretch()

    # ── Summary ───────────────────────────────────────────────────────────────

    def _rebuild_summary(self, result: dict) -> None:
        _clear_layout(self._summary_lo)

        comparisons = result.get("comparisons", {})
        n    = len(comparisons)
        meta = result.get("metadata", {})
        be   = meta.get("backend", {})

        # Top row
        top = QHBoxLayout()
        top.setSpacing(16)
        top.addWidget(_mid_label(
            f"students: {n}   ·   model: {be.get('model_name', 'unknown')}",
            size=11
        ))
        top.addStretch()
        prior_tracks = meta.get("tracks_from_prior", [])
        if prior_tracks:
            letters = ", ".join(t[-1].upper() for t in sorted(prior_tracks))
            top.addWidget(_dim_label(
                f"[prior run: {self._prior_run_date}  ·  Track {letters} loaded]",
                size=10
            ))
        self._summary_lo.addLayout(top)
        self._summary_lo.addWidget(make_h_rule())

        # Counts
        (a_flag, a_clear, b_crisis, b_burn, b_eng, b_none,
         b_ci, c_obs,
         d_ae, d_an, d_acb, d_bca) = self._count_results(comparisons)

        counts_lo = QHBoxLayout()
        counts_lo.setSpacing(20)

        if a_flag + a_clear:
            pct = 100 * a_flag / (a_flag + a_clear)
            al = QLabel(f"A flagged: {a_flag}/{a_flag+a_clear} ({pct:.0f}%)")
            al.setStyleSheet(
                f"color: {BURN_RED}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(al)

        if b_crisis + b_burn + b_eng + b_none:
            bl = QLabel(
                f"B  CRISIS:{b_crisis}  BURNOUT:{b_burn}"
                f"  ENGAGED:{b_eng}  NONE:{b_none}  CI:{b_ci}"
            )
            bl.setStyleSheet(
                f"color: #D87020; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(bl)

        if c_obs:
            cl = QLabel(f"C observations: {c_obs}/{n}")
            cl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            counts_lo.addWidget(cl)

        counts_lo.addStretch()
        self._summary_lo.addLayout(counts_lo)

        # Disagreements
        total_dis = d_ae + d_an + d_acb + d_bca
        if total_dis:
            self._summary_lo.addWidget(make_h_rule())
            self._summary_lo.addWidget(make_section_label("Disagreements"))
            for text, color in [
                (f"A flagged + B ENGAGED: {d_ae}",            BURN_RED),
                (f"A flagged + B NONE: {d_an}",               BURN_RED),
                (f"A clear + B CRISIS/BURNOUT: {d_acb}",      "#D87020"),
                (f"B CHECK-IN + A clear: {d_bca}",            ROSE_ACCENT),
            ]:
                row_lo = QHBoxLayout()
                row_lo.setContentsMargins(0, 0, 0, 0)
                lbl = QLabel(text)
                lbl.setStyleSheet(
                    f"color: {color}; font-size: {px(10)}px;"
                    f" background: transparent; border: none;"
                )
                row_lo.addWidget(lbl)
                row_lo.addStretch()
                self._summary_lo.addLayout(row_lo)

        self._summary_frame.setVisible(True)

    def _count_results(self, comparisons: dict):
        a_flag = a_clear = b_crisis = b_burn = b_eng = b_none = b_ci = c_obs = 0
        d_ae = d_an = d_acb = d_bca = 0
        for sc in comparisons.values():
            ta = sc.get("track_a") or {}
            tb = sc.get("track_b") or {}
            tc = sc.get("track_c") or {}
            if ta:
                if ta.get("flagged"):
                    a_flag += 1
                else:
                    a_clear += 1
            if tb:
                ax = (tb.get("axis") or "").upper()
                if ax == "CRISIS":   b_crisis += 1
                elif ax == "BURNOUT": b_burn += 1
                elif ax == "ENGAGED": b_eng += 1
                elif ax == "NONE":    b_none += 1
                if tb.get("checkin_flag"):
                    b_ci += 1
            if tc and tc.get("observation"):
                c_obs += 1
            if ta and tb:
                ax = (tb.get("axis") or "").upper()
                if ta.get("flagged") and ax == "ENGAGED":
                    d_ae += 1
                if ta.get("flagged") and ax == "NONE":
                    d_an += 1
                if not ta.get("flagged") and ax in ("CRISIS", "BURNOUT"):
                    d_acb += 1
                if tb.get("checkin_flag") and not ta.get("flagged"):
                    d_bca += 1
        return a_flag, a_clear, b_crisis, b_burn, b_eng, b_none, b_ci, c_obs, d_ae, d_an, d_acb, d_bca

    # ── Export ────────────────────────────────────────────────────────────────

    def _on_export_json(self) -> None:
        if not self._current_result:
            return
        safe_name = self._assignment_name[:30].replace(" ", "_").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Research JSON",
            f"research_{safe_name}.json",
            "JSON files (*.json)",
        )
        if not path:
            return
        try:
            payload = self._build_export_dict()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            self._progress_lbl.setText(f"exported: {os.path.basename(path)}")
        except Exception as exc:
            self._progress_lbl.setText(f"export error: {exc}")

    def _on_export_csv(self) -> None:
        if not self._current_result:
            return
        safe_name = self._assignment_name[:30].replace(" ", "_").replace("/", "-")
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Research CSV",
            f"research_{safe_name}.csv",
            "CSV files (*.csv)",
        )
        if not path:
            return
        try:
            payload = self._build_export_dict()
            rows = []
            for anon_id, sc in payload.get("students", {}).items():
                ta = sc.get("track_a") or {}
                tb = sc.get("track_b") or {}
                tc = sc.get("track_c") or {}
                bias_warn = any(
                    c.get("has_bias_warning", False) for c in ta.get("concerns", [])
                )
                rows.append({
                    "anon_id":             anon_id,
                    "word_count":          sc.get("word_count", ""),
                    "a_flagged":           ta.get("flagged", ""),
                    "a_concern_count":     ta.get("concern_count", ""),
                    "a_max_confidence":    max(
                        (c.get("confidence") or 0 for c in ta.get("concerns", [])),
                        default="",
                    ),
                    "a_bias_warning":      bias_warn,
                    "b_axis":              tb.get("axis", ""),
                    "b_signal":            tb.get("signal", ""),
                    "b_confidence":        tb.get("confidence", ""),
                    "b_checkin":           tb.get("checkin_flag", ""),
                    "b_checkin_reasoning": tb.get("checkin_reasoning", ""),
                    "c_observation":       tc.get("observation", ""),
                })
            if not rows:
                return
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
                writer.writeheader()
                writer.writerows(rows)
            self._progress_lbl.setText(f"exported: {os.path.basename(path)}")
        except Exception as exc:
            self._progress_lbl.setText(f"export error: {exc}")

    def _build_export_dict(self) -> dict:
        """Build anonymized export payload from current result."""
        result      = self._current_result
        comparisons = result.get("comparisons", {})
        sorted_ids  = sorted(comparisons.keys())
        id_map      = {sid: f"anon_{i+1:03d}" for i, sid in enumerate(sorted_ids)}

        students = {}
        for sid in sorted_ids:
            sc  = comparisons[sid]
            aid = id_map[sid]
            ta  = sc.get("track_a")
            tb  = sc.get("track_b")
            tc  = sc.get("track_c")

            anon_a = None
            if ta:
                c_list = []
                for c in (ta.get("concerns") or []):
                    c_list.append({
                        "flagged_passage":  c.get("flagged_passage", ""),
                        "why_flagged":      c.get("why_flagged", ""),
                        "confidence":       c.get("confidence"),
                        "has_bias_warning": "⚠" in (c.get("why_flagged") or ""),
                    })
                anon_a = {
                    "flagged":       ta.get("flagged"),
                    "concern_count": len(c_list),
                    "concerns":      c_list,
                }

            anon_b = None
            if tb:
                anon_b = {
                    "axis":              tb.get("axis"),
                    "signal":            tb.get("signal"),
                    "confidence":        tb.get("confidence"),
                    "prescan_signals":   tb.get("prescan_signals") or [],
                    "checkin_flag":      tb.get("checkin_flag"),
                    "checkin_reasoning": tb.get("checkin_reasoning", ""),
                }

            anon_c = None
            if tc:
                anon_c = {"observation": tc.get("observation", "")}

            students[aid] = {
                "word_count": sc.get("word_count", 0),
                "track_a":    anon_a,
                "track_b":    anon_b,
                "track_c":    anon_c,
            }

        meta = result.get("metadata", {})
        (a_flag, a_clear, b_crisis, b_burn, b_eng, b_none,
         b_ci, c_obs, d_ae, d_an, d_acb, d_bca) = self._count_results(comparisons)
        n = a_flag + a_clear

        return {
            "metadata": {
                "run_id":               meta.get("run_id"),
                "export_date":          datetime.now().isoformat(),
                "course_name":          "[redacted]",
                "assignment_name":      "[redacted]",
                "total_students":       len(sorted_ids),
                "backend":              meta.get("backend", {}),
                "track_timings":        meta.get("track_timings", {}),
                "tracks_freshly_run":   meta.get("tracks_freshly_run", []),
                "tracks_from_prior_run": meta.get("tracks_from_prior", []),
                "prior_run_id":         meta.get("prior_run_id"),
                "git_hash":             meta.get("git_hash", ""),
                "software_version":     meta.get("software_version", ""),
            },
            "summary": {
                "track_a": {
                    "flagged":     a_flag,
                    "clear":       a_clear,
                    "flagged_pct": round(100 * a_flag / n, 1) if n else 0.0,
                },
                "track_b": {
                    "crisis":   b_crisis, "burnout": b_burn,
                    "engaged":  b_eng,    "none":    b_none,
                    "checkin_count": b_ci,
                    "checkin_of_engaged_pct": round(
                        100 * b_ci / b_eng, 1
                    ) if b_eng else 0.0,
                },
                "track_c": {"observations_generated": c_obs},
                "disagreements": {
                    "a_flag_b_engaged":            d_ae,
                    "a_flag_b_none":               d_an,
                    "a_clear_b_crisis_or_burnout":  d_acb,
                    "b_checkin_a_clear":            d_bca,
                },
            },
            "students": students,
        }

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def cleanup(self) -> None:
        for w in (self._worker, self._assign_worker):
            if w and w.isRunning():
                w.cancel()
                w.wait(3000)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _scrollbar_qss(width: int = 6) -> str:
    return (
        f"QScrollBar:vertical {{ background: {BG_VOID}; width: {width}px; border: none; }}"
        f"QScrollBar::handle:vertical {{ background: {BORDER_AMBER}; border-radius: {width//2}px;"
        f"  min-height: 20px; }}"
        f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}"
    )
