"""
Right pane: assignment timeline panel.

Displays assignments as a timeline — deadline-passed items above a visual
"TODAY" divider, upcoming items below it.  Custom widget rows (not a tree)
give full visual control over the amber terminal aesthetic.

Supports two view modes:
  - "deadline" (default) — grouped by timeline sections
  - "group" — grouped by Canvas assignment groups

Public API (same names as before so MainWindow doesn't need changes):
    set_course(course_id, course_name)
    show_loading()
    show_empty()
    clear_assignments()
    populate_tree(groups)          ← name kept for back-compat
    set_editor(editor)             ← wire in CanvasEditor for mutations

Signals:
    run_requested(selected_items, course_name, course_id, mark_incomplete_no_sub)
    has_selection(bool)
    edit_completed()               ← emitted after a successful Canvas mutation
"""

import json
import re
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dateutil import parser as dateutil_parser

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QCheckBox, QScrollArea, QSizePolicy,
    QMenu, QInputDialog, QMessageBox, QDateTimeEdit,
)
from PySide6.QtCore import (
    Signal, Qt, QSize, QTimer, QMimeData, QDateTime,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QFont, QColor, QBrush, QPainter, QPainterPath, QPen,
    QDrag, QPixmap, QAction, QDesktopServices, QCursor,
)

from gui.styles import (
    SPACING_SM, SPACING_MD, FONT_LARGE, make_run_button,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    BG_CARD, BG_VOID, BG_INSET,
)

# ---------------------------------------------------------------------------
# Colour constants — no green anywhere
# ---------------------------------------------------------------------------

_PAST_COLOR   = "#F0A830"   # amber hot    — deadline passed (urgent)
_WEEK_COLOR   = "#C87C10"   # deep gold    — due this week
_FUTURE_COLOR = "#6B4F2A"   # warm brown   — upcoming (calm)
_NONE_COLOR   = "#3A2808"   # barely-there — no deadline

_PAST_BG    = QColor(240, 168, 48,  20)
_WEEK_BG    = QColor(200, 124, 16,  12)

_DIM_NAME   = "#5A3C08"    # name text for non-autogradeable items
_SEVEN_DAYS = 7 * 24 * 3600

# Each timeline section: key, display label, accent color, optional row bg
_SECTIONS = [
    {"key": "PAST",   "label": "DEADLINE PASSED", "color": _PAST_COLOR,   "bg": _PAST_BG},
    {"key": "WEEK",   "label": "DUE THIS WEEK",   "color": _WEEK_COLOR,   "bg": _WEEK_BG},
    {"key": "FUTURE", "label": "UPCOMING",         "color": _FUTURE_COLOR, "bg": None},
    {"key": "NONE",   "label": "NO DEADLINE",      "color": _NONE_COLOR,   "bg": None},
]

_GRADING_LABELS = {
    "pass_fail":    "Complete/Inc",
    "points":       "Points",
    "letter_grade": "Letter Grade",
    "percent":      "Percentage",
    "not_graded":   "Not Graded",
}

# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_PANEL_QSS = f"""
    QFrame#assignmentPanel {{
        background: qradialgradient(cx:0.52,cy:0.44,radius:0.90,fx:0.48,fy:0.40,
            stop:0.00 #2C2212, stop:0.60 #171208, stop:1.00 #100C03);
        border: 1px solid {BORDER_DARK};
        border-top-color:  {BORDER_AMBER};
        border-left-color: {BORDER_AMBER};
        border-radius: 10px;
    }}
    QFrame#assignmentPanel > QLabel {{
        background: transparent;
        border: none;
    }}
"""

_SCROLL_QSS = f"""
    QScrollArea#timelineScroll {{
        background: transparent;
        border: none;
    }}
    QScrollArea#timelineScroll > QWidget > QWidget {{
        background: {BG_INSET};
    }}
"""

_PILL_QSS = f"""
    QPushButton {{
        background: rgba(58,40,8,0.30);
        color: {PHOSPHOR_MID};
        border: 1px solid {BORDER_AMBER};
        border-radius: 10px;
        padding: 2px 11px;
        font-size: 11px;
        min-height: 22px;
    }}
    QPushButton:hover:!checked {{
        background: rgba(80,55,12,0.45);
        color: {PHOSPHOR_HOT};
        border-color: {PHOSPHOR_MID};
    }}
    QPushButton:checked {{
        background: rgba(240,168,48,0.18);
        color: {PHOSPHOR_HOT};
        border: 1px solid {PHOSPHOR_HOT};
    }}
    QPushButton:checked:hover {{
        background: rgba(240,168,48,0.26);
    }}
"""

_CLEAR_QSS = f"""
    QPushButton {{
        background: transparent;
        color: {PHOSPHOR_DIM};
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 2px 9px;
        font-size: 11px;
        min-height: 22px;
    }}
    QPushButton:hover {{
        color: {ROSE_ACCENT};
        border-color: rgba(200,80,80,0.30);
    }}
    QPushButton:pressed {{
        color: #FF6060;
    }}
"""



# ---------------------------------------------------------------------------
# UI state persistence (group order + collapsed state)
# ---------------------------------------------------------------------------

_UI_STATE_FILE = Path.home() / ".canvas_autograder_ui_state.json"


def _load_group_ui_state(course_id: int) -> Tuple[List[int], Set[int]]:
    """Return (group_order, collapsed_group_ids) for this course, or empty defaults."""
    try:
        data = json.loads(_UI_STATE_FILE.read_text())
        key = str(course_id)
        order = data.get("group_order", {}).get(key, [])
        collapsed = set(data.get("collapsed_groups", {}).get(key, []))
        return order, collapsed
    except Exception:
        return [], set()


def _save_group_ui_state(
    course_id: int, group_order: List[int], collapsed_groups: Set[int]
) -> None:
    """Persist group order and collapsed state for this course to disk."""
    try:
        data: Dict = {}
        if _UI_STATE_FILE.exists():
            try:
                data = json.loads(_UI_STATE_FILE.read_text())
            except Exception:
                data = {}
        key = str(course_id)
        data.setdefault("group_order", {})[key] = group_order
        data.setdefault("collapsed_groups", {})[key] = list(collapsed_groups)
        _UI_STATE_FILE.write_text(json.dumps(data))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_due(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        dt = dateutil_parser.parse(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _fmt_due(dt: Optional[datetime]) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%b %d")


def _is_autogradeable(grading_type: str, submission_types: List[str]) -> bool:
    if grading_type == "pass_fail":
        return True
    if "discussion_topic" in (submission_types or []):
        return True
    return False


def _type_label(grading_type: str, submission_types: List[str]) -> str:
    if "discussion_topic" in (submission_types or []):
        return "Discussion"
    return _GRADING_LABELS.get(grading_type, "Points")


# ---------------------------------------------------------------------------
# _SwitchToggle  — sliding pill switch widget
# ---------------------------------------------------------------------------

class _SwitchTrack(QWidget):
    """Painted sliding-pill track — 36 × 20 px."""

    _W, _H = 36, 20

    def __init__(self, parent=None):
        super().__init__(parent)
        self._on = False
        self.setFixedSize(self._W, self._H)

    def set_on(self, v: bool) -> None:
        self._on = v
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self._W, self._H
        r = h / 2

        track = QPainterPath()
        track.addRoundedRect(0.5, 0.5, w - 1, h - 1, r, r)

        # Track fill
        if self._on:
            p.fillPath(track, QColor(240, 168, 48, 55))
            p.setPen(QColor(240, 168, 48))
        else:
            p.fillPath(track, QColor(58, 40, 8, 160))
            p.setPen(QColor(106, 74, 18))
        p.drawPath(track)

        # Knob
        knob_d = h - 6
        knob_x = w - knob_d - 4 if self._on else 4
        knob_color = QColor(240, 168, 48) if self._on else QColor(90, 62, 14)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(knob_color)
        p.drawEllipse(int(knob_x), 3, knob_d, knob_d)
        p.end()


class _SwitchToggle(QWidget):
    """A labelled toggle switch — drop-in for QCheckBox in the toolbar."""

    toggled = Signal(bool)

    def __init__(self, label: str, parent=None):
        super().__init__(parent)
        self._checked = False

        lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(7)

        self._track = _SwitchTrack()
        lo.addWidget(self._track)

        self._lbl = QLabel(label)
        self._lbl.setMinimumWidth(0)   # don't let label text expand the toolbar
        self._lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._lbl)

        self.setMinimumWidth(0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh()

    def mousePressEvent(self, _event) -> None:
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:
        self._checked = v
        self._track.set_on(v)
        self._refresh()

    def _refresh(self) -> None:
        color = PHOSPHOR_HOT if self._checked else PHOSPHOR_MID
        self._lbl.setStyleSheet(
            f"color: {color}; font-size: 11px;"
            f" background: transparent; border: none;"
        )


# ---------------------------------------------------------------------------
# _ElidingLabel — clips long text with '…' instead of expanding the layout
# ---------------------------------------------------------------------------

class _ElidingLabel(QLabel):
    """QLabel that elides to '…' on the right when narrower than its text.
    Overrides minimumSizeHint so the layout never uses text width as a floor."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self._full_text = text
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self) -> QSize:
        return QSize(0, super().minimumSizeHint().height())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        elided = self.fontMetrics().elidedText(
            self._full_text, Qt.TextElideMode.ElideRight, max(0, self.width())
        )
        super().setText(elided)   # bypass our setText to avoid recursion


# ---------------------------------------------------------------------------
# _AssignmentRow
# ---------------------------------------------------------------------------

class _AssignmentRow(QFrame):
    """One checkbox row representing a single assignment."""

    toggled = Signal(int, bool)   # (assignment_id, is_checked)
    deadline_edit_requested = Signal(int, object)  # (assignment_id, new_due_at_str_or_None)

    # name-column foreground by situation
    _NAME_PAST_UNGRADED = "#F0A830"   # bright amber — urgent
    _NAME_PAST_CLEAN    = "#8A5E18"   # dim amber — passed, already done
    _NAME_WEEK          = "#C87C10"   # deep gold — closing soon
    _NAME_FUTURE        = "#7A5A30"   # warm muted — upcoming
    _NAME_NONE          = "#5A3C18"   # barely-there
    _NAME_MANUAL        = "#4A3820"   # manual-only dim

    def __init__(self, assignment: dict, section_key: str,
                 drag_enabled: bool = False, parent=None):
        super().__init__(parent)

        self._aid  = assignment["id"]
        self._data = assignment
        self._section_key = section_key
        self._inline_editing = False
        self._drag_enabled = drag_enabled

        ngr  = assignment["needs_grading_count"]
        auto = assignment["autogradeable"]

        # Row background tint
        tint = {"PAST": _PAST_BG, "WEEK": _WEEK_BG}.get(section_key)
        if tint is not None:
            r, g, b, a = tint.red(), tint.green(), tint.blue(), tint.alpha()
            bg_css = f"rgba({r},{g},{b},{a})"
        else:
            bg_css = "transparent"

        self.setFixedHeight(32)
        self.setStyleSheet(f"""
            QFrame {{
                background: {bg_css};
                border: none;
                border-bottom: 1px solid rgba(58,40,8,0.25);
            }}
            QFrame QLabel {{
                background: transparent;
                border: none;
            }}
            QFrame QCheckBox {{
                background: transparent;
            }}
        """)

        self._drag_start = None

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 8, 0)
        row.setSpacing(6)
        self._row_layout = row

        # ── Checkbox ────────────────────────────────────────────────────
        self._cb = QCheckBox()
        self._cb.setFixedSize(16, 16)
        self._cb.toggled.connect(lambda v: self.toggled.emit(self._aid, v))
        row.addWidget(self._cb)

        # ── Name ────────────────────────────────────────────────────────
        if not auto:
            name_color = self._NAME_MANUAL
        elif section_key == "PAST":
            name_color = self._NAME_PAST_UNGRADED if ngr > 0 else self._NAME_PAST_CLEAN
        elif section_key == "WEEK":
            name_color = self._NAME_WEEK
        elif section_key == "FUTURE":
            name_color = self._NAME_FUTURE
        else:
            name_color = self._NAME_NONE

        name_lbl = _ElidingLabel(assignment["name"])
        name_lbl.setToolTip(assignment["name"])
        name_lbl.setStyleSheet(f"color: {name_color}; font-size: 12px;")
        row.addWidget(name_lbl, 1)

        # ── Due date ────────────────────────────────────────────────────
        self._due_lbl = QLabel(_fmt_due(assignment["due_dt"]))
        self._due_lbl.setFixedWidth(70)
        self._due_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._due_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        row.addWidget(self._due_lbl)

        # ── Published status badge ───────────────────────────────────────
        published = assignment.get("published", True)
        if published:
            pub_text  = "✓"
            pub_color = PHOSPHOR_MID
        else:
            pub_text  = "✗"
            pub_color = PHOSPHOR_GLOW
        pub_lbl = QLabel(pub_text)
        pub_lbl.setFixedWidth(80)
        pub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pub_lbl.setStyleSheet(f"color: {pub_color}; font-size: 10px;")
        row.addWidget(pub_lbl)

        # ── Type badge ──────────────────────────────────────────────────
        tag = _type_label(assignment["grading_type"], assignment["submission_types"])
        badge_col = PHOSPHOR_DIM if not auto else PHOSPHOR_MID
        tag_lbl = QLabel(tag)
        tag_lbl.setFixedWidth(95)
        tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tag_lbl.setStyleSheet(f"""
            color: {badge_col};
            background: rgba(58,40,8,0.45);
            border: 1px solid rgba(90,60,8,0.30);
            border-radius: 3px;
            font-size: 10px;
            padding: 1px 4px;
        """)
        row.addWidget(tag_lbl)

        # ── To-grade count ──────────────────────────────────────────────
        if ngr > 0:
            ngr_css = f"color: {PHOSPHOR_HOT}; font-weight: bold; font-size: 11px;"
            ngr_txt = str(ngr)
        else:
            ngr_css = f"color: {PHOSPHOR_GLOW}; font-size: 11px;"
            ngr_txt = "—"

        ngr_lbl = QLabel(ngr_txt)
        ngr_lbl.setFixedWidth(48)
        ngr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ngr_lbl.setStyleSheet(ngr_css)
        row.addWidget(ngr_lbl)

        # Drag support (group view only).
        # WA_TransparentForMouseEvents on every QLabel makes mouse events fall
        # through directly to this frame, so mousePressEvent / mouseMoveEvent
        # fire without any event-propagation or event-filter complexity.
        # QCheckBox is intentionally left interactive.
        if drag_enabled:
            self.setAcceptDrops(True)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.setToolTip(assignment["name"])
            for lbl in self.findChildren(QLabel):
                lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # public helpers
    def set_checked(self, v: bool) -> None:
        self._cb.blockSignals(True)
        self._cb.setChecked(v)
        self._cb.blockSignals(False)

    def is_checked(self) -> bool:
        return self._cb.isChecked()

    def assignment_id(self) -> int:
        return self._aid

    def data(self) -> dict:
        return self._data

    # -- Double-click to edit deadline inline --

    def mouseDoubleClickEvent(self, event):
        if self._inline_editing:
            return
        self._start_inline_date_edit()

    def _start_inline_date_edit(self) -> None:
        """Replace the due-date label with an inline QDateTimeEdit."""
        self._inline_editing = True
        due_dt = self._data.get("due_dt")

        self._date_edit = QDateTimeEdit()
        self._date_edit.setFixedWidth(140)
        self._date_edit.setDisplayFormat("MMM dd, yyyy hh:mm AP")
        self._date_edit.setCalendarPopup(True)
        self._date_edit.setStyleSheet(f"""
            QDateTimeEdit {{
                background: {BG_INSET};
                color: {PHOSPHOR_HOT};
                border: 1px solid {PHOSPHOR_HOT};
                border-radius: 3px;
                font-size: 10px;
                padding: 1px 4px;
            }}
        """)

        if due_dt:
            qdt = QDateTime(
                due_dt.year, due_dt.month, due_dt.day,
                due_dt.hour, due_dt.minute, due_dt.second,
            )
            self._date_edit.setDateTime(qdt)
        else:
            self._date_edit.setDateTime(QDateTime.currentDateTime())

        # Swap the label for the editor
        idx = self._row_layout.indexOf(self._due_lbl)
        self._due_lbl.hide()
        self._row_layout.insertWidget(idx + 1, self._date_edit)
        self._date_edit.setFocus()

        self._date_edit.editingFinished.connect(self._finish_inline_date_edit)
        self._date_edit.installEventFilter(self)

    def eventFilter(self, obj, event):
        """Catch Escape key to cancel inline date editing."""
        if obj is getattr(self, '_date_edit', None):
            from PySide6.QtCore import QEvent
            if event.type() == QEvent.Type.KeyPress:
                if event.key() == Qt.Key.Key_Escape:
                    self._cancel_inline_date_edit()
                    return True
        return super().eventFilter(obj, event)

    def _finish_inline_date_edit(self) -> None:
        if not self._inline_editing:
            return
        self._inline_editing = False

        qdt = self._date_edit.dateTime()
        py_dt = datetime(
            qdt.date().year(), qdt.date().month(), qdt.date().day(),
            qdt.time().hour(), qdt.time().minute(), qdt.time().second(),
            tzinfo=timezone.utc,
        )
        new_due_str = py_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Check if actually changed
        old_due = self._data.get("due_at")
        changed = True
        if old_due:
            try:
                old_dt = dateutil_parser.isoparse(old_due)
                if abs((py_dt - old_dt).total_seconds()) < 60:
                    changed = False
            except (ValueError, TypeError):
                pass

        self._date_edit.hide()
        self._date_edit.deleteLater()
        del self._date_edit
        self._due_lbl.show()

        if changed:
            self.deadline_edit_requested.emit(self._aid, new_due_str)

    def _cancel_inline_date_edit(self) -> None:
        if not self._inline_editing:
            return
        self._inline_editing = False
        self._date_edit.hide()
        self._date_edit.deleteLater()
        del self._date_edit
        self._due_lbl.show()

    # -- Drag support (group view) --

    def _start_drag(self) -> None:
        """Initiate a QDrag for this assignment row."""
        drag = QDrag(self)
        md = QMimeData()
        md.setData("application/x-assignment-id", str(self._aid).encode())
        drag.setMimeData(md)
        pix = QPixmap(self.size())
        pix.fill(QColor(0, 0, 0, 0))
        self.render(pix)
        painter = QPainter(pix)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_DestinationIn)
        painter.fillRect(pix.rect(), QColor(0, 0, 0, 140))
        painter.end()
        drag.setPixmap(pix)
        drag.exec(Qt.DropAction.MoveAction)

    def mouseMoveEvent(self, event):
        if not self._drag_enabled or self._drag_start is None:
            return
        if (event.pos() - self._drag_start).manhattanLength() >= 10:
            self._drag_start = None
            self._start_drag()

    def mousePressEvent(self, event):
        if self._drag_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = event.pos()
            event.accept()
        else:
            super().mousePressEvent(event)

    # Drag-and-drop target (for inserting above this row in group view)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        md = event.mimeData()
        if md.hasFormat("application/x-assignment-id"):
            source_aid = int(md.data("application/x-assignment-id").data().decode())
            event.acceptProposedAction()
            target_group_id = self._data.get("group_id")
            panel = self.parent()
            while panel and not isinstance(panel, AssignmentPanel):
                panel = panel.parent()
            if panel and target_group_id is not None:
                panel._handle_assignment_drop(source_aid, self._aid, target_group_id)


# ---------------------------------------------------------------------------
# _SectionBand
# ---------------------------------------------------------------------------

class _SectionBand(QFrame):
    """Coloured header band for one timeline section."""

    select_all_clicked = Signal()

    def __init__(self, label: str, color: str, item_count: int, ungraded: int, parent=None):
        super().__init__(parent)
        self.setFixedHeight(24)
        # Left coloured accent bar via border-left
        self.setStyleSheet(f"""
            QFrame {{
                background: transparent;
                border: none;
                border-left: 3px solid {color};
            }}
            QFrame QLabel {{ background: transparent; border: none; }}
            QFrame QPushButton {{
                background: transparent;
                border: none;
                color: {PHOSPHOR_GLOW};
                font-size: 10px;
                padding: 0 4px;
            }}
            QFrame QPushButton:hover {{ color: {color}; }}
        """)

        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 6, 0)
        row.setSpacing(6)

        def _band_lbl(text: str, style: str) -> QLabel:
            lbl = QLabel(text)
            lbl.setStyleSheet(style)
            lbl.setMinimumWidth(0)
            return lbl

        # Section name
        row.addWidget(_band_lbl(
            label,
            f"color: {color}; font-size: 10px; font-weight: bold; letter-spacing: 1px;"
        ))

        # Item count
        if item_count:
            row.addWidget(_band_lbl(
                f"{item_count} assignment{'s' if item_count != 1 else ''}",
                f"color: {PHOSPHOR_GLOW}; font-size: 10px;"
            ))

        # Ungraded count — only if > 0
        if ungraded:
            row.addWidget(_band_lbl("·", f"color: {PHOSPHOR_GLOW}; font-size: 10px;"))
            row.addWidget(_band_lbl(
                f"{ungraded} ungraded",
                f"color: {PHOSPHOR_HOT}; font-size: 10px; font-weight: bold;"
            ))

        row.addStretch()

        sel_btn = QPushButton("select all")
        sel_btn.clicked.connect(self.select_all_clicked)
        row.addWidget(sel_btn)


# ---------------------------------------------------------------------------
# _CollapsibleRows — animated container for a group's rows
# ---------------------------------------------------------------------------

class _CollapsibleRows(QWidget):
    """Wraps assignment rows for one group and supports animated collapse."""

    _ANIM_MS = 120   # fast snap — CRT aesthetic

    def __init__(self, rows: List["_AssignmentRow"], parent=None):
        super().__init__(parent)
        self._rows = rows
        self._collapsed = False
        self._full_height = len(rows) * 32
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        for row in rows:
            layout.addWidget(row)

        self.setMaximumHeight(self._full_height)
        self.setMinimumHeight(0)

        self._anim = QPropertyAnimation(self, b"maximumHeight")
        self._anim.setDuration(self._ANIM_MS)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def set_collapsed(self, collapsed: bool, animate: bool = True) -> None:
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        target = 0 if collapsed else self._full_height
        if animate and self._full_height > 0:
            self._anim.stop()
            self._anim.setStartValue(self.maximumHeight())
            self._anim.setEndValue(target)
            self._anim.start()
        else:
            self.setMaximumHeight(target)

    def is_collapsed(self) -> bool:
        return self._collapsed

    # Forward drag events to children — prevents silent rejection when cursor
    # is between rows (in layout margins).
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        """Drop between rows: find the nearest row and forward the drop."""
        md = event.mimeData()
        if not md.hasFormat("application/x-assignment-id"):
            event.ignore()
            return
        source_aid = int(md.data("application/x-assignment-id").data().decode())
        event.acceptProposedAction()
        # Find the closest row to the drop y position
        cursor_y = event.position().toPoint().y()
        best_row = None
        best_dist = float("inf")
        for row in self._rows:
            if not row.isVisible():
                continue
            dist = abs(row.y() + row.height() // 2 - cursor_y)
            if dist < best_dist:
                best_dist = dist
                best_row = row
        if best_row is None:
            return
        panel = self.parent()
        while panel and not isinstance(panel, AssignmentPanel):
            panel = panel.parent()
        if panel:
            target_group_id = best_row.data().get("group_id")
            panel._handle_assignment_drop(source_aid, best_row._aid, target_group_id)


# ---------------------------------------------------------------------------
# _GroupBand — collapsible, draggable section header for "By Group" view
# ---------------------------------------------------------------------------

class _GroupBand(QFrame):
    """Collapsible, draggable header band for an assignment group (By Group view).

    Click anywhere on the band to toggle collapse.
    Drag the band to reorder groups.
    """

    select_all_clicked  = Signal()
    collapse_toggled    = Signal(int, bool)   # (group_id, is_now_collapsed)
    reorder_requested   = Signal(int, int)    # (from_group_id, drop_before_group_id)

    _BASE_QSS = """
        QFrame {{
            background: transparent;
            border: none;
            border-left: 3px solid {color};
        }}
        QFrame QLabel {{ background: transparent; border: none; }}
        QFrame QPushButton {{
            background: transparent;
            border: none;
            color: {glow};
            font-size: 10px;
            padding: 0 4px;
        }}
        QFrame QPushButton:hover {{ color: {color}; }}
    """
    _HOVER_QSS = """
        QFrame {{
            background: rgba(58,40,8,0.18);
            border: none;
            border-left: 3px solid {color};
        }}
        QFrame QLabel {{ background: transparent; border: none; }}
        QFrame QPushButton {{
            background: transparent;
            border: none;
            color: {glow};
            font-size: 10px;
            padding: 0 4px;
        }}
        QFrame QPushButton:hover {{ color: {color}; }}
    """
    # Drop-target: amber top-edge glow
    _DROP_TOP_QSS = """
        QFrame {{
            background: rgba(58,40,8,0.18);
            border: none;
            border-top: 2px solid {hot};
            border-left: 3px solid {color};
        }}
        QFrame QLabel {{ background: transparent; border: none; }}
        QFrame QPushButton {{
            background: transparent; border: none;
            color: {glow}; font-size: 10px; padding: 0 4px;
        }}
    """

    def __init__(self, group_name: str, color: str, item_count: int,
                 weight: Optional[float] = None, parent=None):
        super().__init__(parent)
        self._group_id: Optional[int] = None
        self._color     = color
        self._item_count = item_count
        self._collapsed  = False
        self._drag_start_pos = None

        self.setFixedHeight(28)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_qss(False)

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 6, 0)
        row.setSpacing(5)

        # ── Chevron ─────────────────────────────────────────────────────
        self._chevron = QLabel("⌄")
        self._chevron.setFixedWidth(12)
        self._chevron.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._chevron.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 9px; background: transparent; border: none;"
        )
        row.addWidget(self._chevron)

        # ── Group name ───────────────────────────────────────────────────
        self._name_lbl = QLabel(group_name.upper())
        self._name_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        self._name_lbl.setMinimumWidth(0)
        row.addWidget(self._name_lbl)

        # ── Item count / collapsed badge ─────────────────────────────────
        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: 10px; background: transparent; border: none;"
        )
        self._count_lbl.setMinimumWidth(0)
        row.addWidget(self._count_lbl)
        self._update_count_label()

        # ── Weight ───────────────────────────────────────────────────────
        if weight is not None and weight > 0:
            sep = QLabel("·")
            sep.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: 10px; background: transparent; border: none;"
            )
            sep.setMinimumWidth(0)
            row.addWidget(sep)
            w_lbl = QLabel(f"{weight:.0f}%")
            w_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent; border: none;"
            )
            w_lbl.setMinimumWidth(0)
            row.addWidget(w_lbl)

        row.addStretch()

        sel_btn = QPushButton("select all")
        sel_btn.clicked.connect(self.select_all_clicked)
        row.addWidget(sel_btn)

    # -- State ---------------------------------------------------------------

    def set_group_id(self, gid: int) -> None:
        self._group_id = gid

    def group_id(self) -> Optional[int]:
        return self._group_id

    def set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        self._chevron.setText("›" if collapsed else "⌄")
        self._update_count_label()

    def is_collapsed(self) -> bool:
        return self._collapsed

    # -- Helpers -------------------------------------------------------------

    def _update_count_label(self) -> None:
        if self._collapsed:
            n = self._item_count
            self._count_lbl.setText(
                f"· {n} hidden" if n else ""
            )
        else:
            n = self._item_count
            if n:
                txt = f"· {n} assignment{'s' if n != 1 else ''}"
            else:
                txt = ""
            self._count_lbl.setText(txt)

    def _apply_qss(self, hover: bool) -> None:
        tpl = self._HOVER_QSS if hover else self._BASE_QSS
        self.setStyleSheet(tpl.format(
            color=self._color, glow=PHOSPHOR_GLOW, hot=PHOSPHOR_HOT
        ))

    def _find_panel(self):
        w = self.parent()
        while w and not isinstance(w, AssignmentPanel):
            w = w.parent()
        return w

    # -- Mouse events --------------------------------------------------------

    def enterEvent(self, event) -> None:
        self._apply_qss(True)
        self._chevron.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 9px; background: transparent; border: none;"
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_qss(False)
        self._chevron.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 9px; background: transparent; border: none;"
        )
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.pos()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if (event.button() == Qt.MouseButton.LeftButton
                and self._drag_start_pos is not None):
            # Only toggle if we didn't drag
            if (event.pos() - self._drag_start_pos).manhattanLength() < 6:
                self._toggle_collapse()
        self._drag_start_pos = None
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (self._drag_start_pos is not None
                and (event.buttons() & Qt.MouseButton.LeftButton)
                and (event.pos() - self._drag_start_pos).manhattanLength() >= 8):
            self._start_band_drag()
        super().mouseMoveEvent(event)

    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        self.set_collapsed(self._collapsed)
        if self._group_id is not None:
            self.collapse_toggled.emit(self._group_id, self._collapsed)

    # -- Band drag (group reorder) ------------------------------------------

    def _start_band_drag(self) -> None:
        if self._group_id is None:
            return
        drag = QDrag(self)
        md = QMimeData()
        md.setData("application/x-group-id", str(self._group_id).encode())
        drag.setMimeData(md)
        # Semi-transparent band snapshot
        pix = QPixmap(self.size())
        pix.fill(QColor(0, 0, 0, 0))
        self.render(pix)
        painter = QPainter(pix)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_DestinationIn
        )
        painter.fillRect(pix.rect(), QColor(0, 0, 0, 160))
        painter.end()
        drag.setPixmap(pix)
        drag.exec(Qt.DropAction.MoveAction)
        self._drag_start_pos = None

    # -- Drop target (assignment drops + group reorder drops) ---------------

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-assignment-id") or md.hasFormat("application/x-group-id"):
            event.acceptProposedAction()
            self.setStyleSheet(self._DROP_TOP_QSS.format(
                color=self._color, glow=PHOSPHOR_GLOW, hot=PHOSPHOR_HOT
            ))
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-assignment-id") or md.hasFormat("application/x-group-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._apply_qss(False)
        event.accept()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        self._apply_qss(False)

        if md.hasFormat("application/x-group-id"):
            dragged_gid = int(md.data("application/x-group-id").data().decode())
            event.acceptProposedAction()
            panel = self._find_panel()
            if panel and self._group_id is not None and dragged_gid != self._group_id:
                panel._handle_band_reorder(dragged_gid, self._group_id)

        elif md.hasFormat("application/x-assignment-id"):
            aid = int(md.data("application/x-assignment-id").data().decode())
            event.acceptProposedAction()
            panel = self._find_panel()
            if panel and self._group_id is not None:
                panel._handle_group_drop(aid, self._group_id)


# ---------------------------------------------------------------------------
# _DropSentinel — invisible drop zone at the bottom of the group list
# ---------------------------------------------------------------------------

class _DropSentinel(QFrame):
    """Thin drop zone below the last group band.

    Accepts:
    - application/x-group-id  → append that group to the end of the order
    - application/x-assignment-id → move that assignment to the last group
    """

    _BASE_QSS = "QFrame { background: transparent; border: none; }"
    _HOT_QSS  = (
        f"QFrame {{ background: rgba(240,168,48,0.04);"
        f" border-top: 1px solid {PHOSPHOR_HOT}; border-bottom: none;"
        f" border-left: none; border-right: none; }}"
    )

    def __init__(self, last_group_id: int, parent=None):
        super().__init__(parent)
        self._last_group_id = last_group_id
        self.setMinimumHeight(48)
        self.setAcceptDrops(True)
        self.setStyleSheet(self._BASE_QSS)

    def _find_panel(self):
        w = self.parent()
        while w and not isinstance(w, AssignmentPanel):
            w = w.parent()
        return w

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-group-id") or md.hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
            self.setStyleSheet(self._HOT_QSS)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-group-id") or md.hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.setStyleSheet(self._BASE_QSS)
        event.accept()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        self.setStyleSheet(self._BASE_QSS)
        panel = self._find_panel()

        if md.hasFormat("application/x-group-id") and panel:
            gid = int(md.data("application/x-group-id").data().decode())
            event.acceptProposedAction()
            # -1 sentinel: _handle_band_reorder appends to end when not in order
            panel._handle_band_reorder(gid, -1)

        elif md.hasFormat("application/x-assignment-id") and panel:
            source_aid = int(md.data("application/x-assignment-id").data().decode())
            event.acceptProposedAction()
            panel._handle_group_drop(source_aid, self._last_group_id)


# ---------------------------------------------------------------------------
# _NowDivider
# ---------------------------------------------------------------------------

class _NowDivider(QFrame):
    """Visual "TODAY" line separating past from future assignments."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(22)
        self.setStyleSheet("QFrame { background: transparent; border: none; }")

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 0, 8, 0)
        row.setSpacing(6)

        def _line(left: bool) -> QFrame:
            f = QFrame()
            f.setFixedHeight(1)
            if left:
                grad = f"qlineargradient(x1:0,y1:0,x2:1,y2:0," \
                       f"stop:0 transparent, stop:1 {PHOSPHOR_HOT})"
            else:
                grad = f"qlineargradient(x1:0,y1:0,x2:1,y2:0," \
                       f"stop:0 {PHOSPHOR_HOT}, stop:1 transparent)"
            f.setStyleSheet(f"QFrame {{ background: {grad}; border: none; }}")
            return f

        label = QLabel("◉  TODAY")
        label.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 10px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 1px;"
        )

        row.addWidget(_line(left=True), 1)
        row.addWidget(label)
        row.addWidget(_line(left=False), 1)


# ---------------------------------------------------------------------------
# _MessageRow — loading / empty placeholder
# ---------------------------------------------------------------------------

class _MessageRow(QLabel):
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setMinimumWidth(0)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 12px;"
            f" background: transparent; border: none;"
            f" padding: 32px 16px;"
        )


# ---------------------------------------------------------------------------
# AssignmentPanel
# ---------------------------------------------------------------------------

class AssignmentPanel(QFrame):
    """Right pane: timeline of assignments for the selected course."""

    run_requested  = Signal(list, str, int, bool, bool)  # items, name, id, mark_incomplete, run_aic
    has_selection  = Signal(bool)
    edit_completed = Signal()                       # emitted after a successful Canvas mutation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("assignmentPanel")
        self.setStyleSheet(_PANEL_QSS)

        self._course_id:   int = 0
        self._course_name: str = ""
        self._groups_data: List[dict] = []
        self._checked_ids: Set[int] = set()
        self._view_mode:   str = "deadline"        # "deadline" | "group"
        self._editor = None                        # CanvasEditor instance
        self._active_edit_workers: list = []       # prevent premature GC

        # By-Group view state (keyed by course_id str)
        self._group_order: List[int] = []          # ordered group IDs for current course
        self._collapsed_groups: Set[int] = set()   # collapsed group IDs for current course
        self._col_containers: Dict[int, _CollapsibleRows] = {}  # gid → container
        self._group_assignment_order: Dict[int, List[int]] = {}  # gid → [aid, ...] display order

        # id → _AssignmentRow (live widgets in scroll area)
        self._rows: Dict[int, _AssignmentRow] = {}

        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(SPACING_SM)

        # ── Header: course name + ungraded summary ──────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self._course_label = QLabel("Select a course")
        self._course_label.setProperty("heading", "true")
        f = QFont()
        f.setPointSize(FONT_LARGE)
        f.setBold(True)
        self._course_label.setFont(f)
        self._course_label.setWordWrap(True)
        header_row.addWidget(self._course_label, 1)

        self._ungraded_badge = QLabel()
        self._ungraded_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._ungraded_badge.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 11px;"
            f" background: rgba(240,168,48,0.12);"
            f" border: 1px solid rgba(240,168,48,0.30);"
            f" border-radius: 4px; padding: 2px 8px;"
        )
        self._ungraded_badge.hide()
        header_row.addWidget(self._ungraded_badge)

        outer.addLayout(header_row)

        # ── Scanline separator ──────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0.00 rgba(240,168,48,0),
                    stop:0.20 rgba(240,168,48,0.35),
                    stop:0.50 rgba(240,168,48,0.70),
                    stop:0.80 rgba(240,168,48,0.35),
                    stop:1.00 rgba(240,168,48,0));
                border: none;
            }
        """)
        outer.addWidget(sep)

        # ── Toolbar ─────────────────────────────────────────────────────
        outer.addWidget(self._build_toolbar())

        # ── Column header + scroll area in one stable container ──────────
        # The header is a plain layout sibling of the scroll area inside a
        # shared container widget.  Because both share the same parent layout
        # their widths are always identical — no viewport geometry tricks needed
        # and no jumping when content changes.
        scroll_wrap = QWidget()
        scroll_wrap.setObjectName("scrollWrap")
        scroll_wrap.setStyleSheet(f"""
            QWidget#scrollWrap {{
                background: {BG_INSET};
                border: 1px solid {BORDER_DARK};
                border-radius: 6px;
            }}
        """)
        wrap_layout = QVBoxLayout(scroll_wrap)
        wrap_layout.setContentsMargins(0, 0, 0, 0)
        wrap_layout.setSpacing(0)

        # Column header — margins align with row contents:
        #   left:  row_left(14) + checkbox(16) + spacing(6) = 36
        #   right: row_right(8)
        col_hdr = QWidget()
        col_hdr.setFixedHeight(22)
        col_hdr.setStyleSheet("background: transparent;")
        hdr_row = QHBoxLayout(col_hdr)
        hdr_row.setContentsMargins(36, 0, 8, 0)
        hdr_row.setSpacing(6)

        def _col_hdr_lbl(text, width=None, align=Qt.AlignmentFlag.AlignLeft):
            lbl = QLabel(text)
            lbl.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: 10px;"
                f" font-weight: bold;"
                f" background: transparent; border: none;"
            )
            if width:
                lbl.setFixedWidth(width)
            lbl.setAlignment(align | Qt.AlignmentFlag.AlignVCenter)
            return lbl

        hdr_row.addWidget(_col_hdr_lbl("ASSIGNMENT"), 1)
        hdr_row.addWidget(_col_hdr_lbl("DUE",       70, Qt.AlignmentFlag.AlignCenter))
        hdr_row.addWidget(_col_hdr_lbl("PUBLISHED", 80, Qt.AlignmentFlag.AlignCenter))
        hdr_row.addWidget(_col_hdr_lbl("TYPE",      95, Qt.AlignmentFlag.AlignCenter))
        hdr_row.addWidget(_col_hdr_lbl("UNGRADED",  48, Qt.AlignmentFlag.AlignCenter))
        wrap_layout.addWidget(col_hdr)

        # 1-px separator between header and scroll content
        hdr_sep = QFrame()
        hdr_sep.setFixedHeight(1)
        hdr_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        wrap_layout.addWidget(hdr_sep)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("timelineScroll")
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet(_SCROLL_QSS)
        self._scroll.setAcceptDrops(True)
        wrap_layout.addWidget(self._scroll, 1)

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {BG_INSET}; border: none;")
        self._content.setAcceptDrops(True)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._content_layout.addStretch()

        self._scroll.setWidget(self._content)
        self._scroll.viewport().setAcceptDrops(True)
        outer.addWidget(scroll_wrap, 1)

        # ── Bottom bar ──────────────────────────────────────────────────
        bottom = QHBoxLayout()
        self._count_label = QLabel("0 selected")
        self._count_label.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        bottom.addWidget(self._count_label)
        bottom.addStretch()
        self._run_btn = QPushButton("▶  Run Autograder")
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._on_run_clicked)
        make_run_button(self._run_btn)
        bottom.addWidget(self._run_btn)
        outer.addLayout(bottom)

    def _build_toolbar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background: transparent;")
        row = QHBoxLayout(bar)
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(5)

        # ── View mode toggle ─────────────────────────────────────────────
        from gui.widgets.view_toggle import ViewToggle
        self._view_toggle = ViewToggle()
        self._view_toggle.mode_changed.connect(self._set_view_mode)
        row.addWidget(self._view_toggle)

        # Separator between toggle and filter pills
        _tsep = QFrame()
        _tsep.setFrameShape(QFrame.Shape.VLine)
        _tsep.setFixedWidth(1)
        _tsep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        row.addWidget(_tsep)
        row.addSpacing(4)
        self._toggle_sep = _tsep

        def _pill(label: str) -> QPushButton:
            btn = QPushButton(f"○  {label}")
            btn.setCheckable(True)
            btn.setStyleSheet(_PILL_QSS)
            btn.toggled.connect(
                lambda v, b=btn, t=label: b.setText(f"{'●' if v else '○'}  {t}")
            )
            return btn

        # ── Selection filter pills ───────────────────────────────────────
        self._btn_past_due = _pill("Past Due")
        self._btn_ungraded = _pill("Has Submissions")
        self._btn_all      = _pill("All")
        self._btn_past_due.setToolTip("Select / deselect all past-due assignments")
        self._btn_ungraded.setToolTip("Select / deselect assignments with ungraded submissions")
        self._btn_all.setToolTip("Select / deselect every assignment")

        self._btn_past_due.toggled.connect(lambda v: self._on_filter_changed("past_due", v))
        self._btn_ungraded.toggled.connect(lambda v: self._on_filter_changed("ungraded", v))
        self._btn_all.toggled.connect(lambda v: self._on_filter_changed("all", v))

        row.addWidget(self._btn_past_due)
        row.addWidget(self._btn_ungraded)
        row.addWidget(self._btn_all)

        # Clear
        clr = QPushButton("✕  Clear")
        clr.setFlat(True)
        clr.setStyleSheet(_CLEAR_QSS)
        clr.setToolTip("Deselect all")
        clr.clicked.connect(self._select_none)
        row.addWidget(clr)

        row.addStretch()

        # ── Separator ────────────────────────────────────────────────────
        vsep = QFrame()
        vsep.setFrameShape(QFrame.Shape.VLine)
        vsep.setFixedWidth(1)
        vsep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        row.addWidget(vsep)
        row.addSpacing(4)

        # ── Grading behaviour toggle (distinct from selection) ───────────
        # TODO: wire mark_incomplete into RunWorker / automation_engine when backend is ready
        self._mark_incomplete_cb = _SwitchToggle("Grade missing submissions as Incomplete")
        self._mark_incomplete_cb.setToolTip(
            "When running the autograder, also assign an Incomplete grade\n"
            "to students who never submitted on past-due assignments."
        )

        # Load persisted state
        try:
            from settings import load_settings
            self._mark_incomplete_cb.setChecked(
                bool(load_settings().get("grade_missing_as_incomplete", False))
            )
        except Exception:
            pass

        # Persist on change
        self._mark_incomplete_cb.toggled.connect(self._save_mark_incomplete)

        row.addWidget(self._mark_incomplete_cb)

        row.addSpacing(6)
        _aic_sep = QFrame()
        _aic_sep.setFrameShape(QFrame.Shape.VLine)
        _aic_sep.setFixedWidth(1)
        _aic_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        row.addWidget(_aic_sep)
        row.addSpacing(4)

        self._run_aic_cb = _SwitchToggle("Run academic integrity check")
        self._run_aic_cb.setToolTip(
            "Run the academic integrity checker alongside grading.\n"
            "Flags are reported but do not affect grades."
        )
        try:
            from settings import load_settings
            self._run_aic_cb.setChecked(
                bool(load_settings().get("run_aic_default", False))
            )
        except Exception:
            pass
        self._run_aic_cb.toggled.connect(self._save_run_aic)
        row.addWidget(self._run_aic_cb)

        return bar

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_course(self, course_id: int, course_name: str) -> None:
        self._course_id   = course_id
        self._course_name = course_name
        self._course_label.setText(course_name)
        # Load persisted group UI state for this course
        self._group_order, self._collapsed_groups = _load_group_ui_state(course_id)
        self.clear_assignments()

    def show_loading(self) -> None:
        self._clear_scroll_content()
        self._rows.clear()
        self._content_layout.insertWidget(
            0, _MessageRow("Loading assignments…")
        )

    def show_empty(self) -> None:
        self._clear_scroll_content()
        self._rows.clear()
        self._content_layout.insertWidget(
            0, _MessageRow("No assignments found in this course.")
        )

    def clear_assignments(self) -> None:
        self._groups_data = []
        self._checked_ids.clear()
        self._rows.clear()
        self._col_containers.clear()
        self._clear_scroll_content()
        self._reset_filter_buttons()
        self._update_run_btn()
        self._ungraded_badge.hide()

    def set_editor(self, editor) -> None:
        """Wire in a CanvasEditor instance for mutations."""
        self._editor = editor

    def populate_tree(self, groups: list) -> None:
        """Populate from assignment-group dicts (name kept for back-compat)."""
        if not groups:
            self._groups_data = []
            self._checked_ids.clear()
            self.show_empty()
            return

        self._groups_data = groups
        self._rebuild()

    # ------------------------------------------------------------------
    # Scroll content management
    # ------------------------------------------------------------------

    def _clear_scroll_content(self) -> None:
        """Remove all widgets from the scroll content layout (keep the stretch)."""
        # Remove every item except the trailing stretch
        while self._content_layout.count() > 1:
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _set_view_mode(self, mode: str) -> None:
        """Slot called by ViewToggle when the user switches between deadline/group view."""
        self._view_mode = mode
        self._rebuild()

    def _rebuild(self) -> None:
        """Dispatch to the appropriate rebuild based on current view mode."""
        if self._view_mode == "group":
            self._rebuild_by_group()
        else:
            self._rebuild_by_deadline()

    def _rebuild_by_deadline(self) -> None:
        """Re-render scroll content from _groups_data (timeline view)."""
        self._clear_scroll_content()
        self._rows.clear()

        now      = datetime.now(timezone.utc)
        enriched = self._enriched_assignments(now)

        # Categorise into timeline buckets
        buckets: Dict[str, List[dict]] = {s["key"]: [] for s in _SECTIONS}
        for a in enriched:
            dt = a["due_dt"]
            if dt is None:
                buckets["NONE"].append(a)
            elif dt < now:
                buckets["PAST"].append(a)
            elif (dt - now).total_seconds() <= _SEVEN_DAYS:
                buckets["WEEK"].append(a)
            else:
                buckets["FUTURE"].append(a)

        # Sort each bucket
        _far = datetime(9999, 12, 31, tzinfo=timezone.utc)
        buckets["PAST"].sort(key=lambda a: a["due_dt"] or now)
        buckets["WEEK"].sort(key=lambda a: a["due_dt"] or _far)
        buckets["FUTURE"].sort(key=lambda a: a["due_dt"] or _far)
        buckets["NONE"].sort(key=lambda a: a["name"].lower())

        has_past   = bool(buckets["PAST"])
        has_future = any(buckets[k] for k in ("WEEK", "FUTURE", "NONE"))

        insert_pos = 0   # we insert before the trailing stretch

        def _insert(w: QWidget) -> None:
            nonlocal insert_pos
            self._content_layout.insertWidget(insert_pos, w)
            insert_pos += 1

        # ── Past sections ──────────────────────────────────────────────
        for sec_key in ("PAST",):
            items = buckets[sec_key]
            if not items:
                continue
            sec = next(s for s in _SECTIONS if s["key"] == sec_key)
            ungraded = sum(1 for a in items if a["needs_grading_count"] > 0)
            band = _SectionBand(sec["label"], sec["color"], len(items), ungraded)
            band.select_all_clicked.connect(
                lambda ids=[a["id"] for a in items if a["id"] is not None]:
                    self._select_by_ids(ids)
            )
            _insert(band)
            for a in items:
                row = _AssignmentRow(a, sec_key)
                row.toggled.connect(self._on_row_toggled)
                row.deadline_edit_requested.connect(self._on_deadline_edit)
                if a["id"] is not None:
                    self._rows[a["id"]] = row
                _insert(row)

        # ── TODAY divider ──────────────────────────────────────────────
        if has_past and has_future:
            _insert(_NowDivider())
        elif has_future and not has_past:
            # No past items — still show the divider for context
            _insert(_NowDivider())

        # ── Future sections ────────────────────────────────────────────
        for sec_key in ("WEEK", "FUTURE", "NONE"):
            items = buckets[sec_key]
            if not items:
                continue
            sec = next(s for s in _SECTIONS if s["key"] == sec_key)
            ungraded = sum(1 for a in items if a["needs_grading_count"] > 0)
            band = _SectionBand(sec["label"], sec["color"], len(items), ungraded)
            ids_in_section = [a["id"] for a in items if a["id"] is not None]
            band.select_all_clicked.connect(
                lambda ids=ids_in_section: self._select_by_ids(ids)
            )
            _insert(band)
            for a in items:
                row = _AssignmentRow(a, sec_key)
                row.toggled.connect(self._on_row_toggled)
                row.deadline_edit_requested.connect(self._on_deadline_edit)
                if a["id"] is not None:
                    self._rows[a["id"]] = row
                _insert(row)

        # Restore check state
        for aid, row in self._rows.items():
            row.set_checked(aid in self._checked_ids)

        # Update total-ungraded badge in header
        total_ngr = sum(
            a.get("needs_grading_count", 0) or 0
            for a in enriched
        )
        if total_ngr:
            self._ungraded_badge.setText(f"{total_ngr} ungraded")
            self._ungraded_badge.show()
        else:
            self._ungraded_badge.hide()

        self._update_run_btn()

        # Scroll so that the TODAY divider (or start of PAST) is in view
        if has_past:
            # Scroll to bottom of past section — divider sits just below
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()
            )
            # We scroll to the divider after layout is realised; a single-shot
            # approach avoids a layout-not-ready race.
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._scroll_to_divider)

    def _scroll_to_divider(self) -> None:
        """Scroll so the _NowDivider (if present) is visible with past rows above."""
        for i in range(self._content_layout.count()):
            item = self._content_layout.itemAt(i)
            if item and isinstance(item.widget(), _NowDivider):
                w = item.widget()
                # w.y() is its position within self._content (direct child)
                target_y = max(0, w.y() - 80)
                self._scroll.verticalScrollBar().setValue(target_y)
                return

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------

    def _enriched_assignments(self, now: datetime) -> List[dict]:
        result = []
        for group in self._groups_data:
            group_id   = group.get("id")
            group_name = group.get("name", "Unknown Group")
            for a in group.get("assignments", []):
                aid    = a.get("id")
                gtypes = a.get("submission_types") or []
                gtype  = a.get("grading_type", "points")
                ngc    = int(a.get("needs_grading_count") or 0)
                due_dt = _parse_due(a.get("due_at"))
                auto   = _is_autogradeable(gtype, gtypes)

                result.append({
                    "type":                "assignment",
                    "id":                  aid,
                    "name":                a.get("name", "?"),
                    "group_id":            group_id,
                    "group_name":          group_name,
                    "grading_type":        gtype,
                    "submission_types":    gtypes,
                    "needs_grading_count": ngc,
                    "due_at":              a.get("due_at") or None,
                    "due_dt":              due_dt,
                    "autogradeable":       auto,
                    "published":           bool(a.get("published", True)),
                    "points_possible":     a.get("points_possible"),
                })
        return result

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_row_toggled(self, aid: int, checked: bool) -> None:
        if checked:
            self._checked_ids.add(aid)
        else:
            self._checked_ids.discard(aid)
        self._update_run_btn()

    # ------------------------------------------------------------------
    # Filter toggle logic
    # ------------------------------------------------------------------

    def _ids_for_filter(self, filter_name: str) -> set:
        """Return the set of row IDs matched by the named filter."""
        now = datetime.now(timezone.utc)
        if filter_name == "past_due":
            ids = set()
            for aid, row in self._rows.items():
                dt = row.data().get("due_dt")
                if dt and dt < now:
                    ids.add(aid)
            return ids
        if filter_name == "ungraded":
            return {
                aid for aid, row in self._rows.items()
                if row.data().get("needs_grading_count", 0) > 0
            }
        # "all"
        return set(self._rows.keys())

    def _ids_from_active_filters(self, exclude: str = None) -> set:
        """Union of IDs from all currently-active filters except *exclude*."""
        result: set = set()
        mapping = {
            "past_due": self._btn_past_due,
            "ungraded": self._btn_ungraded,
            "all":      self._btn_all,
        }
        for name, btn in mapping.items():
            if name != exclude and btn.isChecked():
                result |= self._ids_for_filter(name)
        return result

    def _on_filter_changed(self, filter_name: str, active: bool) -> None:
        ids = self._ids_for_filter(filter_name)
        if active:
            self._checked_ids |= ids
        else:
            # Remove only IDs not still covered by another active filter
            retained = self._ids_from_active_filters(exclude=filter_name)
            self._checked_ids -= (ids - retained)
        for aid, row in self._rows.items():
            row.set_checked(aid in self._checked_ids)
        self._update_run_btn()

    def _reset_filter_buttons(self) -> None:
        """Silently uncheck all filter pills and reset their labels."""
        for btn, label in (
            (self._btn_past_due, "Past Due"),
            (self._btn_ungraded, "Has Submissions"),
            (self._btn_all,      "All"),
        ):
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.setText(f"○  {label}")
            btn.blockSignals(False)

    # ------------------------------------------------------------------
    # Quick-select actions
    # ------------------------------------------------------------------

    def _select_by_ids(self, ids: List[int]) -> None:
        for aid in ids:
            self._checked_ids.add(aid)
            if aid in self._rows:
                self._rows[aid].set_checked(True)
        self._update_run_btn()

    def _select_none(self) -> None:
        self._reset_filter_buttons()
        self._checked_ids.clear()
        for row in self._rows.values():
            row.set_checked(False)
        self._update_run_btn()

    # ------------------------------------------------------------------
    # Run button
    # ------------------------------------------------------------------

    def _update_run_btn(self) -> None:
        selected = self._get_selected_assignments()
        n = len(selected)
        self._count_label.setText(f"{n} selected")
        self._run_btn.setEnabled(n > 0)
        self.has_selection.emit(n > 0)

    def _get_selected_assignments(self) -> list:
        result = []
        for aid, row in self._rows.items():
            if row.is_checked():
                result.append(row.data())
        return result

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------

    def _save_mark_incomplete(self, value: bool) -> None:
        try:
            from settings import load_settings, save_settings
            s = load_settings()
            s["grade_missing_as_incomplete"] = value
            save_settings(s)
        except Exception:
            pass

    def _save_run_aic(self, value: bool) -> None:
        try:
            from settings import load_settings, save_settings
            s = load_settings()
            s["run_aic_default"] = value
            save_settings(s)
        except Exception:
            pass

    def _on_run_clicked(self) -> None:
        selected = self._get_selected_assignments()
        if selected:
            mark_incomplete = self._mark_incomplete_cb.isChecked()
            run_aic = self._run_aic_cb.isChecked()
            self.run_requested.emit(
                selected, self._course_name, self._course_id,
                mark_incomplete, run_aic,
            )

    # ------------------------------------------------------------------
    # By Group view
    # ------------------------------------------------------------------

    def _rebuild_by_group(self) -> None:
        """Render scroll content grouped by Canvas assignment groups."""
        self._clear_scroll_content()
        self._rows.clear()
        self._col_containers.clear()

        now = datetime.now(timezone.utc)
        enriched = self._enriched_assignments(now)

        # Collect group metadata
        groups: Dict[int, List[dict]] = {}
        group_names: Dict[int, str] = {}
        group_weights: Dict[int, Optional[float]] = {}
        for a in enriched:
            gid = a.get("group_id")
            if gid is None:
                continue
            groups.setdefault(gid, []).append(a)
            group_names.setdefault(gid, a.get("group_name", "Unknown Group"))
        for g in self._groups_data:
            gid = g.get("id")
            if gid is not None:
                group_weights[gid] = g.get("group_weight")

        # Determine display order:
        # 1. Start with saved order (only keep IDs still present)
        # 2. Append any new groups not in saved order (alpha sorted)
        known_gids = set(groups.keys())
        ordered = [gid for gid in self._group_order if gid in known_gids]
        new_gids = sorted(
            known_gids - set(ordered),
            key=lambda gid: group_names.get(gid, "").lower(),
        )
        sorted_gids = ordered + new_gids

        # First open for this course (no saved order) → collapse everything by default.
        # Subsequent opens restore whatever the user last left.
        if not self._group_order:
            self._collapsed_groups = set(sorted_gids)

        # Persist the canonical order (including new groups)
        self._group_order = sorted_gids
        _save_group_ui_state(
            self._course_id, self._group_order, self._collapsed_groups
        )

        _far = datetime(9999, 12, 31, tzinfo=timezone.utc)
        insert_pos = 0

        def _insert(w: QWidget) -> None:
            nonlocal insert_pos
            self._content_layout.insertWidget(insert_pos, w)
            insert_pos += 1

        for gid in sorted_gids:
            items = groups.get(gid, [])
            items.sort(key=lambda a: (a["due_dt"] or _far, a["name"].lower()))

            gname = group_names.get(gid, "Unknown Group")
            weight = group_weights.get(gid)
            color = PHOSPHOR_MID
            is_collapsed = gid in self._collapsed_groups

            # ── Band ──────────────────────────────────────────────────
            band = _GroupBand(gname, color, len(items), weight)
            band.set_group_id(gid)
            band.set_collapsed(is_collapsed)
            ids_in_group = [a["id"] for a in items if a["id"] is not None]
            band.select_all_clicked.connect(
                lambda ids=ids_in_group: self._select_by_ids(ids)
            )
            band.collapse_toggled.connect(self._on_group_collapse_toggled)
            _insert(band)

            # ── Rows container ────────────────────────────────────────
            row_widgets: List[_AssignmentRow] = []
            aid_order: List[int] = []
            for a in items:
                dt = a["due_dt"]
                if dt is None:
                    sk = "NONE"
                elif dt < now:
                    sk = "PAST"
                elif (dt - now).total_seconds() <= _SEVEN_DAYS:
                    sk = "WEEK"
                else:
                    sk = "FUTURE"
                row = _AssignmentRow(a, sk, drag_enabled=True)
                row.toggled.connect(self._on_row_toggled)
                row.deadline_edit_requested.connect(self._on_deadline_edit)
                if a["id"] is not None:
                    self._rows[a["id"]] = row
                    aid_order.append(a["id"])
                row_widgets.append(row)

            self._group_assignment_order[gid] = aid_order

            container = _CollapsibleRows(row_widgets)
            self._col_containers[gid] = container
            if is_collapsed:
                container.set_collapsed(True, animate=False)
            _insert(container)

        # Drop sentinel — allows dragging groups/assignments to the very last position
        if sorted_gids:
            sentinel = _DropSentinel(last_group_id=sorted_gids[-1])
            _insert(sentinel)

        # Restore check state
        for aid, row in self._rows.items():
            row.set_checked(aid in self._checked_ids)

        # Total-ungraded badge
        total_ngr = sum(a.get("needs_grading_count", 0) or 0 for a in enriched)
        if total_ngr:
            self._ungraded_badge.setText(f"{total_ngr} ungraded")
            self._ungraded_badge.show()
        else:
            self._ungraded_badge.hide()

        self._update_run_btn()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        """Right-click context menu for assignments."""
        if not self._editor or not self._course_id:
            return

        # Find which row was clicked
        clicked_row = None
        global_pos = event.globalPos()
        for row in self._rows.values():
            if row.isVisible():
                row_rect = row.rect()
                row_global_tl = row.mapToGlobal(row_rect.topLeft())
                row_global_br = row.mapToGlobal(row_rect.bottomRight())
                from PySide6.QtCore import QRect, QPoint
                row_global_rect = QRect(row_global_tl, row_global_br)
                if row_global_rect.contains(global_pos):
                    clicked_row = row
                    break

        if clicked_row is None:
            return

        is_bulk = clicked_row.is_checked() and len(self._checked_ids) > 1

        menu = QMenu(self)
        if is_bulk:
            self._build_bulk_menu(menu)
        else:
            self._build_single_menu(menu, clicked_row)

        menu.exec(global_pos)

    def _build_single_menu(self, menu: QMenu, row: _AssignmentRow) -> None:
        data = row.data()

        # Open in Canvas
        open_act = menu.addAction("Open in Canvas")
        open_act.triggered.connect(lambda: self._open_in_canvas(data))

        menu.addSeparator()

        # Rename
        rename_act = menu.addAction("Rename...")
        rename_act.triggered.connect(lambda: self._ctx_rename(data))

        # Change Due Date
        due_act = menu.addAction("Change Due Date...")
        due_act.triggered.connect(lambda: self._ctx_change_due_date(data))

        # Change Grading Type submenu
        gt_menu = menu.addMenu("Change Grading Type")
        current_gt = data.get("grading_type", "points")
        for gt_key, gt_label in _GRADING_LABELS.items():
            act = gt_menu.addAction(gt_label)
            act.setEnabled(gt_key != current_gt)
            act.triggered.connect(
                lambda checked, k=gt_key: self._ctx_change_grading_type(data, k)
            )

        # Set Points
        pts_act = menu.addAction("Set Points...")
        pts_act.triggered.connect(lambda: self._ctx_set_points(data))

        # Move to Group submenu
        grp_menu = menu.addMenu("Move to Group")
        current_gid = data.get("group_id")
        for g in self._groups_data:
            gid = g.get("id")
            gname = g.get("name", "?")
            act = grp_menu.addAction(gname)
            act.setEnabled(gid != current_gid)
            act.triggered.connect(
                lambda checked, target_gid=gid: self._ctx_move_to_group(
                    data, target_gid
                )
            )

        menu.addSeparator()

        # Publish / Unpublish
        published = data.get("published", True)
        pub_label = "Unpublish" if published else "Publish"
        pub_act = menu.addAction(pub_label)
        pub_act.triggered.connect(lambda: self._ctx_toggle_publish(data))

    def _build_bulk_menu(self, menu: QMenu) -> None:
        shift_act = menu.addAction("Shift Deadlines...")
        shift_act.triggered.connect(self._ctx_bulk_shift)

        gt_menu = menu.addMenu("Change Grading Type")
        for gt_key, gt_label in _GRADING_LABELS.items():
            act = gt_menu.addAction(gt_label)
            act.triggered.connect(
                lambda checked, k=gt_key: self._ctx_bulk_grading_type(k)
            )

        menu.addSeparator()

        pub_act = menu.addAction("Publish All")
        pub_act.triggered.connect(lambda: self._ctx_bulk_publish(True))

        unpub_act = menu.addAction("Unpublish All")
        unpub_act.triggered.connect(lambda: self._ctx_bulk_publish(False))

    # ------------------------------------------------------------------
    # Context menu actions — single assignment
    # ------------------------------------------------------------------

    def _open_in_canvas(self, data: dict) -> None:
        base = self._editor.base_url if self._editor else ""
        url = f"{base}/courses/{self._course_id}/assignments/{data['id']}"
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    def _ctx_rename(self, data: dict) -> None:
        name, ok = QInputDialog.getText(
            self, "Rename Assignment", "New name:",
            text=data.get("name", ""),
        )
        if ok and name and name.strip():
            self._run_edit(
                lambda: self._editor.rename_assignment(
                    self._course_id, data["id"], name.strip()
                )
            )

    def _ctx_change_due_date(self, data: dict) -> None:
        from gui.dialogs.date_picker_dialog import DatePickerDialog
        dlg = DatePickerDialog(current_due_at=data.get("due_at"), parent=self)
        if dlg.exec():
            accepted, iso_str = dlg.get_result()
            if accepted:
                self._run_deadline_edit(data, iso_str)

    def _ctx_change_grading_type(self, data: dict, new_type: str) -> None:
        current_type = data.get("grading_type", "points")
        self._run_preflight_then_edit(
            preflight_fn=lambda: self._editor.preflight_grading_type_change(
                self._course_id, data["id"], new_type, current_type
            ),
            edit_fn=lambda: self._editor.set_grading_type(
                self._course_id, data["id"], new_type
            ),
        )

    def _ctx_set_points(self, data: dict) -> None:
        current = data.get("points_possible", 0) or 0
        points, ok = QInputDialog.getDouble(
            self, "Set Points", "Points possible:",
            value=float(current), min=0, max=100000, decimals=2,
        )
        if ok:
            self._run_preflight_then_edit(
                preflight_fn=lambda: self._editor.preflight_points_change(
                    self._course_id, data["id"], points, float(current)
                ),
                edit_fn=lambda: self._editor.set_points_possible(
                    self._course_id, data["id"], points
                ),
            )

    def _ctx_move_to_group(self, data: dict, target_gid: int) -> None:
        source_gid = data.get("group_id")
        if source_gid == target_gid:
            return
        self._run_preflight_then_edit(
            preflight_fn=lambda: self._editor.preflight_group_move(
                self._course_id, data["id"], source_gid, target_gid
            ),
            edit_fn=lambda: self._editor.move_assignment_group(
                self._course_id, data["id"], target_gid
            ),
        )

    def _ctx_toggle_publish(self, data: dict) -> None:
        currently_published = data.get("published", True)
        if currently_published:
            self._run_preflight_then_edit(
                preflight_fn=lambda: self._editor.preflight_unpublish(
                    self._course_id, data["id"]
                ),
                edit_fn=lambda: self._editor.set_published(
                    self._course_id, data["id"], False
                ),
            )
        else:
            self._run_edit(
                lambda: self._editor.set_published(
                    self._course_id, data["id"], True
                )
            )

    # ------------------------------------------------------------------
    # Context menu actions — bulk
    # ------------------------------------------------------------------

    def _ctx_bulk_shift(self) -> None:
        checked = self._get_selected_assignments()
        if not checked:
            return
        aids = [a["id"] for a in checked if a.get("id")]
        names = {a["id"]: a.get("name", "?") for a in checked if a.get("id")}

        from gui.dialogs.bulk_shift_dialog import BulkShiftDialog
        dlg = BulkShiftDialog(
            api=None,
            editor=self._editor,
            course_id=self._course_id,
            assignment_ids=aids,
            assignment_names=names,
            parent=self,
        )
        dlg.exec()
        if dlg.was_modified:
            self.edit_completed.emit()

    def _ctx_bulk_grading_type(self, new_type: str) -> None:
        checked = self._get_selected_assignments()
        if not checked:
            return
        reply = QMessageBox.question(
            self, "Change Grading Type",
            f"Change grading type to "
            f"'{_GRADING_LABELS.get(new_type, new_type)}' "
            f"for {len(checked)} assignments?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for a in checked:
            self._run_edit(
                lambda aid=a["id"]: self._editor.set_grading_type(
                    self._course_id, aid, new_type
                ),
                refresh=False,
            )
        self.edit_completed.emit()

    def _ctx_bulk_publish(self, publish: bool) -> None:
        checked = self._get_selected_assignments()
        if not checked:
            return
        action = "Publish" if publish else "Unpublish"
        reply = QMessageBox.question(
            self, f"{action} All",
            f"{action} {len(checked)} assignments?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        for a in checked:
            self._run_edit(
                lambda aid=a["id"]: self._editor.set_published(
                    self._course_id, aid, publish
                ),
                refresh=False,
            )
        self.edit_completed.emit()

    # ------------------------------------------------------------------
    # Inline deadline edit handler
    # ------------------------------------------------------------------

    def _on_deadline_edit(self, aid: int, new_due_str) -> None:
        """Called from _AssignmentRow when double-click inline edit completes."""
        data = None
        if aid in self._rows:
            data = self._rows[aid].data()
        if data is None:
            return
        self._run_deadline_edit(data, new_due_str)

    def _run_deadline_edit(self, data: dict, new_due_str) -> None:
        """Execute a deadline change with preflight if shortening."""
        current_due = data.get("due_at")
        self._run_preflight_then_edit(
            preflight_fn=lambda: self._editor.preflight_deadline_change(
                self._course_id, data["id"], new_due_str, current_due
            ),
            edit_fn=lambda: self._editor.set_deadlines(
                self._course_id, data["id"], new_due_str
            ),
        )

    # ------------------------------------------------------------------
    # Drag-and-drop group move handler
    # ------------------------------------------------------------------

    def _handle_group_drop(self, assignment_id: int,
                           target_group_id: int) -> None:
        """Handle an assignment dropped onto a group band (move to that group)."""
        if assignment_id not in self._rows:
            return
        data = self._rows[assignment_id].data()
        source_gid = data.get("group_id")
        if source_gid == target_group_id:
            return
        self._ctx_move_to_group(data, target_group_id)

    def _handle_assignment_drop(self, source_aid: int, target_aid: int,
                                 target_group_id: int) -> None:
        """Handle an assignment dropped onto another assignment row."""
        if source_aid not in self._rows or source_aid == target_aid:
            return
        data = self._rows[source_aid].data()
        source_gid = data.get("group_id")

        if source_gid != target_group_id:
            # Cross-group move
            self._ctx_move_to_group(data, target_group_id)
        else:
            # Within-group reorder via Canvas position field
            if not self._editor or not self._course_id:
                return
            order = self._group_assignment_order.get(target_group_id, [])
            if target_aid not in order:
                return
            # Position is 1-based; drop before the target
            new_pos = order.index(target_aid) + 1
            course_id = self._course_id
            self._run_edit(
                lambda: self._editor.set_assignment_position(course_id, source_aid, new_pos),
                refresh=True,
            )

    # ------------------------------------------------------------------
    # Group collapse
    # ------------------------------------------------------------------

    def _on_group_collapse_toggled(self, group_id: int,
                                   is_collapsed: bool) -> None:
        """Animate rows and persist collapse state."""
        container = self._col_containers.get(group_id)
        if container:
            container.set_collapsed(is_collapsed)

        if is_collapsed:
            self._collapsed_groups.add(group_id)
        else:
            self._collapsed_groups.discard(group_id)

        _save_group_ui_state(
            self._course_id, self._group_order, self._collapsed_groups
        )

    # ------------------------------------------------------------------
    # Group band reorder (drag bands to change group order)
    # ------------------------------------------------------------------

    def _handle_band_reorder(self, dragged_gid: int,
                              drop_before_gid: int) -> None:
        """Move dragged_gid to just before drop_before_gid in the order."""
        if dragged_gid not in self._group_order:
            return
        new_order = [g for g in self._group_order if g != dragged_gid]
        idx = new_order.index(drop_before_gid) if drop_before_gid in new_order else len(new_order)
        new_order.insert(idx, dragged_gid)
        self._group_order = new_order
        _save_group_ui_state(
            self._course_id, self._group_order, self._collapsed_groups
        )
        # Rebuild to apply new order
        self._rebuild_by_group()
        # Sync positions to Canvas
        if self._editor and self._course_id:
            self._sync_group_positions_to_canvas()

    def _sync_group_positions_to_canvas(self) -> None:
        """Send position updates to Canvas for all groups in current order."""
        order = list(self._group_order)
        course_id = self._course_id

        def _do_sync():
            from canvas_editor import EditResult
            for pos, gid in enumerate(order, start=1):
                try:
                    self._editor.set_group_position(course_id, gid, pos)
                except Exception:
                    pass
            return EditResult(ok=True, message="Group order synced.")

        self._run_edit(_do_sync, refresh=False)

    # ------------------------------------------------------------------
    # Edit execution plumbing
    # ------------------------------------------------------------------

    def _run_edit(self, fn, refresh: bool = True) -> None:
        """Run a CanvasEditor mutation in a worker thread."""
        if not self._editor:
            return
        from gui.workers import EditAssignmentWorker
        w = EditAssignmentWorker(api=None, editor=self._editor, fn=fn)
        if refresh:
            w.result_ready.connect(self._on_edit_result)
        else:
            w.result_ready.connect(self._on_edit_result_quiet)
        w.finished.connect(lambda: self._active_edit_workers.remove(w)
                           if w in self._active_edit_workers else None)
        self._active_edit_workers.append(w)
        w.start()

    def _run_preflight_then_edit(self, preflight_fn, edit_fn) -> None:
        """Run preflight in worker, show warnings if needed, then edit."""
        if not self._editor:
            return
        from gui.workers import EditAssignmentWorker

        w = EditAssignmentWorker(
            api=None, editor=self._editor, fn=preflight_fn
        )
        w.result_ready.connect(
            lambda result: self._handle_preflight_result(result, edit_fn)
        )
        w.finished.connect(lambda: self._active_edit_workers.remove(w)
                           if w in self._active_edit_workers else None)
        self._active_edit_workers.append(w)
        w.start()

    def _handle_preflight_result(self, result, edit_fn) -> None:
        """Process a PreflightResult and either proceed, warn, or block."""
        if hasattr(result, 'safe'):
            # It's a PreflightResult
            if result.safe:
                self._run_edit(edit_fn)
                return
            if not result.can_proceed:
                msgs = "\n\n".join(w.message for w in result.blocking_warnings)
                QMessageBox.critical(self, "Cannot Proceed", msgs)
                return
            if result.advisory_warnings:
                msgs = "\n\n".join(
                    w.message for w in result.advisory_warnings
                )
                reply = QMessageBox.warning(
                    self, "Warning",
                    msgs + "\n\nApply anyway?",
                    QMessageBox.StandardButton.Yes
                    | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._run_edit(edit_fn)
                return
            self._run_edit(edit_fn)
        else:
            # Unexpected type — treat as error
            if hasattr(result, 'ok') and not result.ok:
                QMessageBox.warning(
                    self, "Preflight Error", result.message
                )
                return
            self._run_edit(edit_fn)

    def _on_edit_result(self, result) -> None:
        """Handle EditResult from a mutation worker."""
        if hasattr(result, 'ok'):
            if result.ok:
                self.edit_completed.emit()
            else:
                QMessageBox.warning(
                    self, "Edit Failed",
                    result.message or "The change could not be applied."
                )

    def _on_edit_result_quiet(self, result) -> None:
        """Handle EditResult without emitting edit_completed (bulk use)."""
        if hasattr(result, 'ok') and not result.ok:
            QMessageBox.warning(
                self, "Edit Failed",
                result.message or "The change could not be applied."
            )
