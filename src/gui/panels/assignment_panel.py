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
    run_requested(selected_items, course_name, course_id)
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
    QDialog, QFormLayout, QComboBox, QSpinBox,
)
from gui.dialogs.message_dialog import (
    show_info, show_warning, show_critical, show_question,
    show_warning_suppressible,
)
from PySide6.QtCore import (
    Signal, Qt, QSize, QTimer, QMimeData, QDateTime,
    QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import (
    QFont, QColor, QBrush, QPainter, QPainterPath, QPen,
    QDrag, QPixmap, QAction, QDesktopServices, QCursor,
    QLinearGradient, QRadialGradient,
)

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD, FONT_LARGE, make_run_button,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    BG_CARD, BG_VOID, BG_INSET, PANE_BG_GRADIENT,
    make_glow_label, apply_phosphor_glow, remove_glow,
    make_section_label,
)
from gui.widgets.phosphor_chip import PhosphorChip
from gui.widgets.status_pip import draw_pip

_ROSE_HOT  = "#FF6090"   # bright pink for hover/active glow
_ROSE_DIM  = "#6B2040"   # faded pink — AIC resting state (mirrors PHOSPHOR_MID in amber)

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
        background: {PANE_BG_GRADIENT};
        border: 1px solid {BORDER_DARK};
        border-top-color: {BORDER_AMBER};
        border-radius: 8px;
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
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.85,
            stop:0.00 rgba(80,55,12,0.35),
            stop:0.65 rgba(40,28,6,0.25),
            stop:1.00 rgba(10,7,2,0.30));
        color: {PHOSPHOR_MID};
        border: 1px solid rgba(106,74,18,0.40);
        border-radius: 10px;
        padding: 2px 11px;
        font-size: {px(11)}px;
        min-height: 22px;
    }}
    QPushButton:hover:!checked {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.85,
            stop:0.00 rgba(120,80,16,0.55),
            stop:0.65 rgba(65,45,10,0.35),
            stop:1.00 rgba(15,10,3,0.35));
        color: {PHOSPHOR_HOT};
        border-color: rgba(106,74,18,0.65);
    }}
    QPushButton:checked {{
        background: qradialgradient(cx:0.50,cy:0.50,radius:0.85,
            stop:0.00 rgba(240,168,48,0.32),
            stop:0.50 rgba(180,110,20,0.16),
            stop:1.00 rgba(10,7,2,0.20));
        color: {PHOSPHOR_HOT};
        border: 1px solid rgba(200,140,30,0.68);
        font-weight: 600;
    }}
"""

_CLEAR_QSS = f"""
    QPushButton {{
        background: transparent;
        color: {PHOSPHOR_DIM};
        border: 1px solid transparent;
        border-radius: 10px;
        padding: 2px 9px;
        font-size: {px(11)}px;
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


def _load_group_ui_state(
    course_id: int,
) -> Tuple[List[int], Set[int], Dict[int, List[int]]]:
    """Return (group_order, collapsed_group_ids, assignment_order) for this course."""
    try:
        data = json.loads(_UI_STATE_FILE.read_text())
        key = str(course_id)
        order = data.get("group_order", {}).get(key, [])
        collapsed = set(data.get("collapsed_groups", {}).get(key, []))
        raw_asgn = data.get("assignment_order", {}).get(key, {})
        # JSON keys are strings; convert to int
        asgn_order = {int(gid): [int(a) for a in aids] for gid, aids in raw_asgn.items()}
        return order, collapsed, asgn_order
    except Exception:
        return [], set(), {}


def _save_group_ui_state(
    course_id: int,
    group_order: List[int],
    collapsed_groups: Set[int],
    assignment_order: Optional[Dict[int, List[int]]] = None,
) -> None:
    """Persist group order, collapsed state, and per-group assignment order."""
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
        if assignment_order is not None:
            data.setdefault("assignment_order", {})[key] = {
                str(gid): aids for gid, aids in assignment_order.items()
            }
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
    return _GRADING_LABELS.get(grading_type, "Points")


def _kind_label(submission_types: List[str]) -> str:
    """Return a short submission-category tag shown in the KIND column."""
    stypes = submission_types or []
    if "discussion_topic" in stypes:
        return "DISC"
    if "online_quiz" in stypes:
        return "QUIZ"
    return "—"


# ---------------------------------------------------------------------------
# _ClickableLabel — QLabel that emits clicked() on left mouse press
# ---------------------------------------------------------------------------

class _ClickableLabel(QLabel):
    """QLabel that emits clicked() when the user left-clicks it."""

    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mousePressEvent(event)


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
    publish_badge_clicked = Signal(int)    # (assignment_id)
    type_badge_clicked = Signal(int)       # (assignment_id)

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
        self._drag_enabled = drag_enabled

        ngr  = assignment["needs_grading_count"]
        auto = assignment["autogradeable"]
        self._auto = auto
        self._ngr  = ngr

        # Row background tint
        tint = {"PAST": _PAST_BG, "WEEK": _WEEK_BG}.get(section_key)
        if tint is not None:
            r, g, b, a = tint.red(), tint.green(), tint.blue(), tint.alpha()
            bg_css = f"rgba({r},{g},{b},{a})"
        else:
            bg_css = "transparent"

        self._tint   = tint   # QColor or None — used in paintEvent
        self._bg_css = bg_css
        self._hovered = False
        self.setFixedHeight(32)
        self.setMouseTracking(True)
        self._apply_row_qss(False)

        self._drag_start = None

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 0, 8, 0)
        row.setSpacing(6)
        self._row_layout = row

        # ── Selection state — no QCheckBox; pip drawn in paintEvent ─────
        self._is_checked = False
        # 16-px transparent spacer keeps column alignment (header indent = 36px)
        _pip_spacer = QWidget()
        _pip_spacer.setFixedSize(16, 16)
        _pip_spacer.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        _pip_spacer.setStyleSheet("background: transparent;")
        row.addWidget(_pip_spacer)

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
        name_lbl.setStyleSheet(f"color: {name_color}; font-size: {px(12)}px;")
        row.addWidget(name_lbl, 1)

        # ── Due date ────────────────────────────────────────────────────
        self._due_lbl = QLabel(_fmt_due(assignment["due_dt"]))
        self._due_lbl.setFixedWidth(70)
        self._due_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if section_key == "PAST" and ngr > 0:
            self._due_lbl.setStyleSheet(f"color: {_PAST_COLOR}; font-size: {px(11)}px;")
            apply_phosphor_glow(self._due_lbl, color=_PAST_COLOR, blur=7, strength=0.40,
                                xOffset=-2, yOffset=1)
        elif section_key == "PAST":
            self._due_lbl.setStyleSheet(f"color: #7A5520; font-size: {px(11)}px;")
        else:
            self._due_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;")
        row.addWidget(self._due_lbl)

        # ── Published status badge (clickable) ──────────────────────────
        published = assignment.get("published", True)
        if published:
            pub_text  = "✓"
            pub_color = PHOSPHOR_MID
        else:
            pub_text  = "✗"
            pub_color = PHOSPHOR_GLOW
        self._pub_lbl = _ClickableLabel(pub_text)
        self._pub_lbl.setFixedWidth(80)
        self._pub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._pub_lbl.setStyleSheet(f"color: {pub_color}; font-size: {px(10)}px;")
        self._pub_lbl.setToolTip("Click to toggle publish state")
        self._pub_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pub_lbl.clicked.connect(lambda: self.publish_badge_clicked.emit(self._aid))
        row.addWidget(self._pub_lbl)

        # ── Kind indicator (DISC / QUIZ / —) ────────────────────────────
        kind = _kind_label(assignment["submission_types"])
        kind_col = PHOSPHOR_MID if kind != "—" else PHOSPHOR_DIM
        kind_lbl = QLabel(kind)
        kind_lbl.setFixedWidth(50)
        kind_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        kind_lbl.setStyleSheet(f"color: {kind_col}; font-size: {px(10)}px;")
        kind_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(kind_lbl)

        # ── Type badge (clickable) ───────────────────────────────────────
        tag = _type_label(assignment["grading_type"], assignment["submission_types"])
        badge_col = PHOSPHOR_DIM if not auto else PHOSPHOR_MID
        self._tag_lbl = _ClickableLabel(tag)
        self._tag_lbl.setFixedWidth(95)
        self._tag_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tag_lbl.setStyleSheet(f"""
            color: {badge_col};
            background: rgba(58,40,8,0.45);
            border: 1px solid rgba(90,60,8,0.30);
            border-radius: 3px;
            font-size: {px(10)}px;
            padding: 1px 4px;
        """)
        self._tag_lbl.setToolTip("Click to change grading type")
        self._tag_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tag_lbl.clicked.connect(lambda: self.type_badge_clicked.emit(self._aid))
        row.addWidget(self._tag_lbl)

        # ── To-grade count ──────────────────────────────────────────────
        if ngr > 0:
            ngr_css = f"color: {PHOSPHOR_HOT}; font-weight: bold; font-size: {px(11)}px;"
            ngr_txt = str(ngr)
        else:
            ngr_css = f"color: {PHOSPHOR_GLOW}; font-size: {px(11)}px;"
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
        if not auto and not drag_enabled:
            self.setCursor(Qt.CursorShape.ForbiddenCursor)

        if drag_enabled:
            self.setAcceptDrops(True)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            self.setToolTip(assignment["name"])
            for lbl in self.findChildren(QLabel):
                if not isinstance(lbl, _ClickableLabel):
                    lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    # public helpers
    def set_checked(self, v: bool) -> None:
        self._is_checked = bool(v)
        self.update()

    def is_checked(self) -> bool:
        return self._is_checked

    def assignment_id(self) -> int:
        return self._aid

    def data(self) -> dict:
        return self._data

    # -- Hover + pip painting ------------------------------------------------

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, _event) -> None:
        is_checked = self._is_checked
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = float(self.width()), float(self.height())
        cy = h / 2.0

        # 1. Section tint base (PAST / WEEK amber wash)
        if self._tint is not None:
            if self._section_key == "PAST":
                # Asymmetric phosphor bloom: hot spot near left edge, bleeds unevenly rightward
                r, g, b = self._tint.red(), self._tint.green(), self._tint.blue()
                tint_grad = QRadialGradient(w * 0.22, h, w * 1.50)
                tint_grad.setColorAt(0.00, QColor(r, g, b, 14))
                tint_grad.setColorAt(0.50, QColor(r, g, b, 6))
                tint_grad.setColorAt(1.00, QColor(r, g, b, 1))
                p.fillRect(self.rect(), QBrush(tint_grad))
            else:
                p.fillRect(self.rect(), self._tint)

        # 2. Selection / hover glow
        if is_checked or self._hovered:
            glow_cx = w * 0.25
            glow_cy = cy
            if is_checked:
                mid_r, mid_g, mid_b = 204, 82, 130   # rose
                glow_a, bloom_a, tail_a = 72, 35, 18
            else:
                mid_r, mid_g, mid_b = 240, 168, 48   # amber
                glow_a, bloom_a, tail_a = 50, 20, 10

            # Linear wash first — ensures the tint is visible across the full row width
            wash = QLinearGradient(0, 0, w, 0)
            wash.setColorAt(0.00, QColor(mid_r, mid_g, mid_b, glow_a // 2))
            wash.setColorAt(0.45, QColor(mid_r, mid_g, mid_b, tail_a))
            wash.setColorAt(1.00, QColor(mid_r, mid_g, mid_b, tail_a))
            p.fillRect(self.rect(), QBrush(wash))

            # Radial glow on top — concentrated left-side phosphor bloom
            grad = QRadialGradient(glow_cx, glow_cy, w * 0.8)
            grad.setColorAt(0.00, QColor(mid_r, mid_g, mid_b, glow_a))
            grad.setColorAt(0.40, QColor(mid_r, mid_g, mid_b, glow_a // 4))
            grad.setColorAt(1.00, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), QBrush(grad))

            bloom = QRadialGradient(glow_cx, glow_cy, w * 0.40)
            bloom.setColorAt(0.00, QColor(mid_r, mid_g, mid_b, bloom_a))
            bloom.setColorAt(1.00, QColor(0, 0, 0, 0))
            p.fillRect(self.rect(), QBrush(bloom))

        # 3. Pip at x=22 (14px left margin + 8px = center of old checkbox area)
        pip_x = 22.0
        if is_checked:
            draw_pip(p, pip_x, cy, 5, 204, 82, 130, 60, 200)
        elif self._hovered:
            draw_pip(p, pip_x, cy, 5, 240, 168, 48, 25, 140)
        else:
            draw_pip(p, pip_x, cy, 5, 58, 40, 8, 0, 90)

        p.end()
        # Do NOT call super() — that would repaint transparent background over our painting

    # -- Double-click to edit deadline (opens DatePickerDialog) --

    def mouseDoubleClickEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            super().mouseDoubleClickEvent(event)
            return
        from gui.dialogs.date_picker_dialog import DatePickerDialog
        dlg = DatePickerDialog(
            current_due_at=self._data.get("due_at"),
            parent=self.window(),
        )
        if dlg.exec():
            accepted, iso_str = dlg.get_result()
            if accepted:
                new_due = _parse_due(iso_str) if iso_str else None
                self._due_lbl.setText(_fmt_due(new_due))
                self._data["due_at"] = iso_str
                self.deadline_edit_requested.emit(self._aid, iso_str)
        event.accept()

    # -- Stylesheet helpers --

    def _apply_row_qss(self, drop_target: bool) -> None:
        # Background and section tint are painted in paintEvent.
        # QSS only handles child transparency and the separator line.
        if drop_target:
            self.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                    border-top: 2px solid {PHOSPHOR_HOT};
                    border-bottom: 1px solid rgba(58,40,8,0.25);
                }}
                QFrame QLabel {{ background: transparent; border: none; }}
            """)
        else:
            self.setStyleSheet(f"""
                QFrame {{
                    background: transparent;
                    border: none;
                    border-bottom: 1px solid rgba(58,40,8,0.25);
                }}
                QFrame QLabel {{ background: transparent; border: none; }}
            """)

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
        if event.button() == Qt.MouseButton.LeftButton:
            # In drag-enabled view, clicks outside the pip zone start a potential drag
            # regardless of whether this assignment is autogradeable.
            if self._drag_enabled and event.pos().x() >= 36:
                self._drag_start = event.pos()
                event.accept()
                return
            # Pip-zone click (or non-drag view): attempt selection toggle.
            if not self._auto:
                self._show_not_gradeable_notice()
                event.accept()
                return
            if self._ngr == 0:
                event.accept()
                return
            self._is_checked = not self._is_checked
            self.toggled.emit(self._aid, self._is_checked)
            self.update()
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drag_start is not None:
            # Short move = click not drag → try to toggle (auto rows only)
            if (event.pos() - self._drag_start).manhattanLength() < 10:
                if self._auto and self._ngr > 0:
                    self._is_checked = not self._is_checked
                    self.toggled.emit(self._aid, self._is_checked)
                    self.update()
                elif not self._auto:
                    self._show_not_gradeable_notice()
            self._drag_start = None
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def _show_not_gradeable_notice(self) -> None:
        gtype = self._data.get("grading_type", "points")
        type_label = _GRADING_LABELS.get(gtype, "Points")
        name = self._data.get("name", "This assignment")

        # Walk up to the panel to check for editor
        panel = self.parent()
        while panel and not isinstance(panel, AssignmentPanel):
            panel = panel.parent()
        has_editor = bool(panel and getattr(panel, "_editor", None))

        if has_editor:
            from gui.dialogs.message_dialog import show_with_action
            if show_with_action(
                self.window(),
                "Convert Grading Type",
                f"{name} currently uses {type_label} grading.\n\n"
                f"Autograding requires Complete / Incomplete.",
                "Convert to C/I",
                severity="info",
            ):
                aid = self._data.get("id")
                if aid is not None:
                    panel._pending_auto_check = aid
                panel._ctx_change_grading_type(self._data, "pass_fail")
        else:
            show_warning(
                self.window(),
                "Cannot Autograde",
                f"{name} uses {type_label} grading.\n\n"
                f"Change it to Complete / Incomplete in Canvas to autograde it.",
            )

    # Drag-and-drop target (for inserting above this row in group view)
    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
            parent = self.parent()
            if isinstance(parent, _CollapsibleRows):
                parent.show_drop_at(self.y())
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # Don't hide here — let _CollapsibleRows.dragLeaveEvent handle it when
        # the drag truly exits the container.  This prevents flicker between rows.
        event.accept()

    def dropEvent(self, event):
        md = event.mimeData()
        parent = self.parent()
        if isinstance(parent, _CollapsibleRows):
            parent.hide_drop()
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
                font-size: {px(10)}px;
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
            f"color: {color}; font-size: {px(10)}px; font-weight: bold; letter-spacing: 1px;"
        ))

        # Item count
        if item_count:
            row.addWidget(_band_lbl(
                f"{item_count} assignment{'s' if item_count != 1 else ''}",
                f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"
            ))

        # Ungraded count — only if > 0
        if ungraded:
            row.addWidget(_band_lbl("·", f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"))
            row.addWidget(_band_lbl(
                f"{ungraded} ungraded",
                f"color: {PHOSPHOR_HOT}; font-size: {px(10)}px; font-weight: bold;"
            ))

        row.addStretch()

        sel_btn = QPushButton("select all")
        sel_btn.clicked.connect(self.select_all_clicked)
        row.addWidget(sel_btn)


# ---------------------------------------------------------------------------
# _DropLine — floating insertion indicator drawn between assignment rows
# ---------------------------------------------------------------------------

def _paint_insertion_glow(p: QPainter, w: int, cy: int, h: int) -> None:
    """Paint the shared phosphor-glow insertion indicator.

    Three layers (back → front):
      1. Wide bloom  — soft amber haze filling the full height, fades left
      2. Inner glow  — tighter band centred on the line, fades left
      3. Core line   — 2 px bright gradient, fades left → full amber right
    The effect mimics backlit CRT phosphor: most intense on the right,
    bleeding light leftward, nearly transparent at the far left.
    """
    p.setPen(Qt.PenStyle.NoPen)

    # 1. Bloom — full widget height
    bloom = QLinearGradient(0, 0, w, 0)
    bloom.setColorAt(0.00, QColor(240, 168, 48, 42))
    bloom.setColorAt(0.45, QColor(240, 168, 48, 22))
    bloom.setColorAt(0.82, QColor(240, 168, 48,  8))
    bloom.setColorAt(1.00, QColor(240, 168, 48,  0))
    p.setBrush(QBrush(bloom))
    p.drawRect(0, 0, w, h)

    # 2. Inner glow — 8 px band around the core
    inner = QLinearGradient(0, 0, w, 0)
    inner.setColorAt(0.00, QColor(240, 168, 48, 85))
    inner.setColorAt(0.45, QColor(240, 168, 48, 55))
    inner.setColorAt(0.82, QColor(240, 168, 48, 18))
    inner.setColorAt(1.00, QColor(240, 168, 48,  0))
    p.setBrush(QBrush(inner))
    p.drawRect(0, cy - 4, w, 8)

    # 3. Core line — 2 px
    core = QLinearGradient(0, 0, w, 0)
    core.setColorAt(0.00, QColor(240, 168, 48, 255))
    core.setColorAt(0.68, QColor(240, 168, 48, 220))
    core.setColorAt(0.90, QColor(240, 168, 48, 130))
    core.setColorAt(1.00, QColor(240, 168, 48,   0))
    p.setBrush(QBrush(core))
    p.drawRect(0, cy - 1, w, 2)


class _DropLine(QWidget):
    """Phosphor-glow insertion indicator floating above assignment rows.

    Absolutely positioned inside _CollapsibleRows; sits on top of sibling
    _AssignmentRow widgets because it is a non-layout child added last.
    """
    _H = 14   # total height — gives bloom room to breathe

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setFixedHeight(self._H)
        self.hide()

    def show_at(self, y: int) -> None:
        pw = self.parent().width() if self.parent() else 300
        self.setGeometry(0, max(0, y - self._H // 2), pw, self._H)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        _paint_insertion_glow(p, self.width(), self._H // 2, self._H)
        p.end()


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

        # Floating insertion indicator (child widget, paints on top of rows)
        self._drop_line = _DropLine(self)

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

    def move_row(self, source_aid: int, target_aid: int) -> None:
        """Move the row for source_aid to just before the row for target_aid."""
        aids = [r._aid for r in self._rows]
        if source_aid not in aids or target_aid not in aids or source_aid == target_aid:
            return
        src_idx = aids.index(source_aid)
        src_row = self._rows.pop(src_idx)
        layout = self.layout()
        layout.removeWidget(src_row)
        new_tgt_idx = [r._aid for r in self._rows].index(target_aid)
        self._rows.insert(new_tgt_idx, src_row)
        layout.insertWidget(new_tgt_idx, src_row)

    # -- Insertion indicator helpers -----------------------------------------

    def show_drop_at(self, y: int) -> None:
        """Show the ◈─── indicator at pixel y within this container."""
        self._drop_line.show_at(y)

    def hide_drop(self) -> None:
        self._drop_line.hide()

    def _indicator_y_for_cursor(self, cursor_y: int) -> Optional[int]:
        """Return the y pixel where the indicator should appear for cursor_y."""
        for row in self._rows:
            if row.isVisible() and cursor_y <= row.y() + row.height() // 2:
                return row.y()
        # Below all visible rows — append position
        visible = [r for r in self._rows if r.isVisible()]
        if visible:
            return visible[-1].y() + visible[-1].height()
        return None

    # -- Drag events (gaps between rows / container margins) -----------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
            y = self._indicator_y_for_cursor(event.position().toPoint().y())
            if y is not None:
                self.show_drop_at(y)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat("application/x-assignment-id"):
            event.acceptProposedAction()
            y = self._indicator_y_for_cursor(event.position().toPoint().y())
            if y is not None:
                self.show_drop_at(y)
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self.hide_drop()
        event.accept()

    def dropEvent(self, event) -> None:
        """Drop between rows: use indicator position to pick the target row."""
        self.hide_drop()
        md = event.mimeData()
        if not md.hasFormat("application/x-assignment-id"):
            event.ignore()
            return
        source_aid = int(md.data("application/x-assignment-id").data().decode())
        event.acceptProposedAction()
        cursor_y = event.position().toPoint().y()
        # Find target row: first row whose midpoint is below cursor
        target_row = None
        for row in self._rows:
            if row.isVisible() and cursor_y <= row.y() + row.height() // 2:
                target_row = row
                break
        if target_row is None:
            # Dropped below all rows — use last visible row as target
            visible = [r for r in self._rows if r.isVisible()]
            if visible:
                target_row = visible[-1]
        if target_row is None:
            return
        panel = self.parent()
        while panel and not isinstance(panel, AssignmentPanel):
            panel = panel.parent()
        if panel:
            panel._handle_assignment_drop(source_aid, target_row._aid, target_row.data().get("group_id"))


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
            font-size: {px10}px;
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
            font-size: {px10}px;
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
            color: {glow}; font-size: {px10}px; padding: 0 4px;
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
        self._is_drop_target = False

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
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; background: transparent; border: none;"
        )
        row.addWidget(self._chevron)

        # ── Group name ───────────────────────────────────────────────────
        self._name_lbl = QLabel(group_name.upper())
        self._name_lbl.setStyleSheet(
            f"color: {color}; font-size: {px(10)}px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        self._name_lbl.setMinimumWidth(0)
        row.addWidget(self._name_lbl)

        # ── Item count / collapsed badge ─────────────────────────────────
        self._count_lbl = QLabel()
        self._count_lbl.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px; background: transparent; border: none;"
        )
        self._count_lbl.setMinimumWidth(0)
        row.addWidget(self._count_lbl)
        self._update_count_label()

        # ── Weight ───────────────────────────────────────────────────────
        if weight is not None and weight > 0:
            sep = QLabel("·")
            sep.setStyleSheet(
                f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px; background: transparent; border: none;"
            )
            sep.setMinimumWidth(0)
            row.addWidget(sep)
            w_lbl = QLabel(f"{weight:.0f}%")
            w_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent; border: none;"
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
            color=self._color, glow=PHOSPHOR_GLOW, hot=PHOSPHOR_HOT,
            px10=px(10),
        ))

    def paintEvent(self, event) -> None:  # noqa: N802
        super().paintEvent(event)
        if self._is_drop_target:
            # Phosphor glow at the top edge — same visual language as _DropLine
            p = QPainter(self)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            _paint_insertion_glow(p, self.width(), 0, 10)
            p.end()

    def _find_panel(self):
        w = self.parent()
        while w and not isinstance(w, AssignmentPanel):
            w = w.parent()
        return w

    # -- Mouse events --------------------------------------------------------

    def enterEvent(self, event) -> None:
        self._apply_qss(True)
        self._chevron.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(9)}px; background: transparent; border: none;"
        )
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._apply_qss(False)
        self._chevron.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; background: transparent; border: none;"
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

    def _set_drop_target(self, active: bool) -> None:
        self._is_drop_target = active
        self._apply_qss(False)   # base stylesheet; paintEvent adds the glow
        self.update()

    def dragEnterEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-assignment-id") or md.hasFormat("application/x-group-id"):
            event.acceptProposedAction()
            self._set_drop_target(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        md = event.mimeData()
        if md.hasFormat("application/x-assignment-id") or md.hasFormat("application/x-group-id"):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._set_drop_target(False)
        event.accept()

    def dropEvent(self, event) -> None:
        md = event.mimeData()
        self._set_drop_target(False)

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
            f"color: {PHOSPHOR_HOT}; font-size: {px(10)}px; font-weight: bold;"
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
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
            f" padding: 32px 16px;"
        )


# ---------------------------------------------------------------------------
# AssignmentPanel
# ---------------------------------------------------------------------------

class AssignmentPanel(QFrame):
    """Right pane: timeline of assignments for the selected course."""

    run_requested  = Signal(list, str, int)  # items, course_name, course_id
    has_selection  = Signal(bool)
    edit_completed = Signal()                       # emitted after a successful Canvas mutation

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("assignmentPanel")
        self.setStyleSheet(_PANEL_QSS)

        self._course_id:          int = 0
        self._course_name:        str = ""
        self._groups_data:        List[dict] = []
        self._checked_ids:        Set[int] = set()
        self._view_mode:          str = "deadline"   # "deadline" | "group"
        self._editor              = None              # CanvasEditor instance
        self._canvas_base_url:    str = ""            # for "Open in Canvas" links
        self._active_edit_workers: list = []          # prevent premature GC
        self._pending_auto_check: int | None = None   # auto-select after refresh
        self._preserve_scroll:    bool = False         # skip divider scroll on next rebuild

        # By-Group view state (keyed by course_id str)
        self._group_order: List[int] = []          # ordered group IDs for current course
        self._collapsed_groups: Set[int] = set()   # collapsed group IDs for current course
        self._saved_assignment_order: Dict[int, List[int]] = {}  # gid → saved aid order
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

        # ── Header: section label + course name + ungraded badge ────────
        section_lbl = make_section_label("Assignments")
        outer.addWidget(section_lbl)

        header_row = QHBoxLayout()
        header_row.setSpacing(8)

        self._course_label = QLabel("")
        self._course_label.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        self._course_label.setWordWrap(True)
        header_row.addWidget(self._course_label, 1)

        self._ungraded_badge = QLabel()
        self._ungraded_badge.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._ungraded_badge.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(11)}px;"
            f" background: rgba(240,168,48,0.12);"
            f" border: 1px solid rgba(240,168,48,0.30);"
            f" border-radius: 4px; padding: 2px 8px;"
        )
        apply_phosphor_glow(self._ungraded_badge, color=PHOSPHOR_HOT, blur=10, strength=0.50,
                            xOffset=-3, yOffset=1)
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
                f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px;"
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
        hdr_row.addWidget(_col_hdr_lbl("KIND",      50, Qt.AlignmentFlag.AlignCenter))
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

        # ── Footer ──────────────────────────────────────────────────────
        footer_sep = QFrame()
        footer_sep.setFixedHeight(1)
        footer_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        outer.addWidget(footer_sep)

        # Single bottom row: count label | stretch | Run button
        bottom = QHBoxLayout()
        bottom.setContentsMargins(0, 8, 0, 0)
        bottom.setSpacing(10)

        self._count_label = QLabel("0 selected")
        self._count_label.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;")
        bottom.addWidget(self._count_label, 0, Qt.AlignmentFlag.AlignVCenter)
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

        # ── Selection filter chips ───────────────────────────────────────
        self._btn_past_due = PhosphorChip("Past Due",        accent="amber")
        self._btn_ungraded = PhosphorChip("Has Submissions", accent="amber")
        self._btn_all      = PhosphorChip("All",             accent="amber")
        self._btn_past_due.setToolTip("Select / deselect all past-due assignments")
        self._btn_ungraded.setToolTip("Select / deselect assignments with ungraded submissions")
        self._btn_all.setToolTip("Select / deselect every assignment")

        self._btn_past_due.toggled.connect(lambda v: self._on_filter_changed("past_due", v))
        self._btn_ungraded.toggled.connect(lambda v: self._on_filter_changed("ungraded", v))
        self._btn_all.toggled.connect(lambda v: self._on_filter_changed("all", v))

        row.addWidget(self._btn_past_due)
        row.addWidget(self._btn_ungraded)
        row.addWidget(self._btn_all)

        # Clear — rose action chip (hover-only, no toggle state)
        clr = PhosphorChip("✕  Clear", accent="rose", action=True)
        clr.setToolTip("Deselect all")
        clr.toggled.connect(lambda _: self._select_none())
        row.addWidget(clr)

        row.addStretch()
        return bar

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_course(self, course_id: int, course_name: str) -> None:
        self._course_id   = course_id
        self._course_name = course_name
        self._course_label.setText(course_name)
        # Load persisted group UI state for this course
        self._group_order, self._collapsed_groups, self._saved_assignment_order = \
            _load_group_ui_state(course_id)
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
        if editor and hasattr(editor, "base_url"):
            self._canvas_base_url = editor.base_url

    def set_canvas_url(self, url: str) -> None:
        """Set the Canvas base URL (for 'Open in Canvas' without a full editor)."""
        self._canvas_base_url = url.rstrip("/") if url else ""

    def populate_tree(self, groups: list, preserve_scroll: bool = False) -> None:
        """Populate from assignment-group dicts (name kept for back-compat)."""
        if not groups:
            self._groups_data = []
            self._checked_ids.clear()
            self.show_empty()
            return

        self._preserve_scroll = preserve_scroll
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
        saved_scroll = (self._scroll.verticalScrollBar().value()
                        if self._preserve_scroll else None)
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
                self._connect_row(row)
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
                self._connect_row(row)
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

        # Auto-check pending assignment (e.g. after C/I conversion)
        if self._pending_auto_check is not None:
            aid = self._pending_auto_check
            self._pending_auto_check = None
            if aid in self._rows:
                self._checked_ids.add(aid)
                self._rows[aid].set_checked(True)

        self._update_run_btn()

        if saved_scroll is not None:
            # Restore previous scroll position after edit-triggered refresh
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(saved_scroll))
            self._preserve_scroll = False
        elif has_past:
            # Scroll so that the TODAY divider (or start of PAST) is in view
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
                # Canvas sometimes omits submission_types for discussions;
                # fall back to checking the discussion_topic key directly.
                is_discussion = (
                    "discussion_topic" in gtypes
                    or bool(a.get("discussion_topic"))
                )
                auto = _is_autogradeable(gtype, gtypes) or is_discussion

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
                    "discussion_topic":    a.get("discussion_topic"),
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
        """Return the set of autogradeable row IDs matched by the named filter.

        Autogradeability is determined by the row's pre-computed ``autogradeable``
        field (set by ``_is_autogradeable``).  When support for new grading types
        is added, only ``_is_autogradeable`` needs updating — this method
        automatically reflects the change.
        """
        now = datetime.now(timezone.utc)
        if filter_name == "past_due":
            return {
                aid for aid, row in self._rows.items()
                if row.data().get("autogradeable")
                and (dt := row.data().get("due_dt")) and dt < now
            }
        if filter_name == "ungraded":
            return {
                aid for aid, row in self._rows.items()
                if row.data().get("autogradeable")
                and row.data().get("needs_grading_count", 0) > 0
            }
        # "all"
        return {
            aid for aid, row in self._rows.items()
            if row.data().get("autogradeable")
        }

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
        """Silently uncheck all filter chips."""
        for btn in (self._btn_past_due, self._btn_ungraded, self._btn_all):
            btn.blockSignals(True)
            btn.setChecked(False)
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

    def get_selected_assignments(self) -> list:
        """Public: return currently selected assignment dicts."""
        return self._get_selected_assignments()

    def get_selected_ids(self) -> set:
        """Public: return a copy of the currently selected assignment ID set."""
        return self._checked_ids.copy()

    def restore_selection(self, ids: set) -> None:
        """Re-check assignments by ID — call after populate_tree to restore a saved selection."""
        self._select_by_ids(list(ids))

    def _on_run_clicked(self) -> None:
        selected = self._get_selected_assignments()
        if selected:
            self.run_requested.emit(selected, self._course_name, self._course_id)

    # ------------------------------------------------------------------
    # By Group view
    # ------------------------------------------------------------------

    def _rebuild_by_group(self) -> None:
        """Render scroll content grouped by Canvas assignment groups."""
        saved_scroll = (self._scroll.verticalScrollBar().value()
                        if self._preserve_scroll else None)
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
            saved_order = self._saved_assignment_order.get(gid, [])
            if saved_order:
                # Respect user's manual reorder; new assignments go at end sorted by date
                aid_to_item = {a["id"]: a for a in items if a["id"] is not None}
                ordered_items = [aid_to_item[aid] for aid in saved_order if aid in aid_to_item]
                new_items = sorted(
                    [a for a in items if a["id"] not in set(saved_order)],
                    key=lambda a: (a["due_dt"] or _far, a["name"].lower()),
                )
                items = ordered_items + new_items
            else:
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
                self._connect_row(row)
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

        # Auto-check pending assignment (e.g. after C/I conversion)
        if self._pending_auto_check is not None:
            aid = self._pending_auto_check
            self._pending_auto_check = None
            if aid in self._rows:
                self._checked_ids.add(aid)
                self._rows[aid].set_checked(True)

        # Total-ungraded badge
        total_ngr = sum(a.get("needs_grading_count", 0) or 0 for a in enriched)
        if total_ngr:
            self._ungraded_badge.setText(f"{total_ngr} ungraded")
            self._ungraded_badge.show()
        else:
            self._ungraded_badge.hide()

        self._update_run_btn()

        if saved_scroll is not None:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self._scroll.verticalScrollBar().setValue(saved_scroll))
            self._preserve_scroll = False

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def contextMenuEvent(self, event):
        """Right-click context menu for assignments."""
        if not self._course_id:
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

        from gui.styles import menu_qss
        menu = QMenu(self)
        menu.setStyleSheet(menu_qss())
        if is_bulk:
            self._build_bulk_menu(menu)
        else:
            self._build_single_menu(menu, clicked_row)

        menu.exec(global_pos)

    def _build_single_menu(self, menu: QMenu, row: _AssignmentRow) -> None:
        data = row.data()
        has_editor = bool(self._editor)

        # Open in Canvas — always available when we know the base URL
        has_url = bool(self._canvas_base_url)
        open_act = menu.addAction("Open in Canvas")
        open_act.setEnabled(has_url)
        if has_url:
            open_act.triggered.connect(lambda: self._open_in_canvas(data))

        menu.addSeparator()

        # Rename
        rename_act = menu.addAction("Rename...")
        rename_act.setEnabled(has_editor)
        if has_editor:
            rename_act.triggered.connect(lambda: self._ctx_rename(data))

        # Change Due Date
        due_act = menu.addAction("Change Due Date...")
        due_act.setEnabled(has_editor)
        if has_editor:
            due_act.triggered.connect(lambda: self._ctx_change_due_date(data))

        # Change Grading Type submenu
        gt_menu = menu.addMenu("Change Grading Type")
        gt_menu.setEnabled(has_editor)
        current_gt = data.get("grading_type", "points")
        for gt_key, gt_label in _GRADING_LABELS.items():
            act = gt_menu.addAction(gt_label)
            act.setEnabled(gt_key != current_gt)
            if has_editor:
                act.triggered.connect(
                    lambda checked, k=gt_key: self._ctx_change_grading_type(data, k)
                )

        # Set Points
        pts_act = menu.addAction("Set Points...")
        pts_act.setEnabled(has_editor)
        if has_editor:
            pts_act.triggered.connect(lambda: self._ctx_set_points(data))

        # Move to Group submenu
        grp_menu = menu.addMenu("Move to Group")
        grp_menu.setEnabled(has_editor)
        current_gid = data.get("group_id")
        for g in self._groups_data:
            gid = g.get("id")
            gname = g.get("name", "?")
            act = grp_menu.addAction(gname)
            act.setEnabled(gid != current_gid)
            if has_editor:
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
        pub_act.setEnabled(has_editor)
        if has_editor:
            pub_act.triggered.connect(lambda: self._ctx_toggle_publish(data))

    def _build_bulk_menu(self, menu: QMenu) -> None:
        has_editor = bool(self._editor)

        shift_act = menu.addAction("Shift Deadlines...")
        shift_act.setEnabled(has_editor)
        if has_editor:
            shift_act.triggered.connect(self._ctx_bulk_shift)

        gt_menu = menu.addMenu("Change Grading Type")
        gt_menu.setEnabled(has_editor)
        for gt_key, gt_label in _GRADING_LABELS.items():
            act = gt_menu.addAction(gt_label)
            if has_editor:
                act.triggered.connect(
                    lambda checked, k=gt_key: self._ctx_bulk_grading_type(k)
                )

        menu.addSeparator()

        pub_act = menu.addAction("Publish All")
        pub_act.setEnabled(has_editor)
        if has_editor:
            pub_act.triggered.connect(lambda: self._ctx_bulk_publish(True))

        unpub_act = menu.addAction("Unpublish All")
        unpub_act.setEnabled(has_editor)
        if has_editor:
            unpub_act.triggered.connect(lambda: self._ctx_bulk_publish(False))

    # ------------------------------------------------------------------
    # Context menu actions — single assignment
    # ------------------------------------------------------------------

    def _open_in_canvas(self, data: dict) -> None:
        base = self._canvas_base_url
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
        reply = show_question(
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
        reply = show_question(
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
            # Within-group reorder — local only (Canvas date-sort would undo API changes)
            order = list(self._group_assignment_order.get(target_group_id, []))
            if target_aid not in order or source_aid not in order:
                return
            # Move source before target in the order list
            order.remove(source_aid)
            tgt_idx = order.index(target_aid)
            order.insert(tgt_idx, source_aid)
            # Persist
            self._group_assignment_order[target_group_id] = order
            self._saved_assignment_order[target_group_id] = order
            _save_group_ui_state(
                self._course_id, self._group_order, self._collapsed_groups,
                self._saved_assignment_order,
            )
            # Visual reorder without a full rebuild
            container = self._col_containers.get(target_group_id)
            if container:
                container.move_row(source_aid, target_aid)

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

    def _connect_row(self, row: "_AssignmentRow") -> None:
        """Wire all signals from a newly created _AssignmentRow."""
        row.toggled.connect(self._on_row_toggled)
        row.deadline_edit_requested.connect(self._on_deadline_edit)
        row.publish_badge_clicked.connect(self._on_inline_publish_click)
        row.type_badge_clicked.connect(self._on_inline_type_click)

    def _on_inline_publish_click(self, aid: int) -> None:
        """Toggle publish state when user clicks the ✓/✗ badge."""
        if not self._editor:
            show_info(
                self, "Not Connected",
                "Connect to Canvas in the Settings tab to edit assignments.",
            )
            return
        row = self._rows.get(aid)
        if row is None:
            return
        self._ctx_toggle_publish(row.data())

    def _on_inline_type_click(self, aid: int) -> None:
        """Show a grading-type popup menu when the type badge is clicked."""
        if not self._editor:
            show_info(
                self, "Not Connected",
                "Connect to Canvas in the Settings tab to edit assignments.",
            )
            return
        row = self._rows.get(aid)
        if row is None:
            return
        data = row.data()
        current_gt = data.get("grading_type", "points")

        from gui.styles import menu_qss
        menu = QMenu(self)
        menu.setStyleSheet(menu_qss())
        for gt_key, gt_label in _GRADING_LABELS.items():
            act = menu.addAction(gt_label)
            act.setEnabled(gt_key != current_gt)
            act.triggered.connect(
                lambda checked, k=gt_key: self._ctx_change_grading_type(data, k)
            )
        # Position the popup near the badge
        if row.isVisible():
            badge_global = row._tag_lbl.mapToGlobal(row._tag_lbl.rect().bottomLeft())
            menu.exec(badge_global)
        else:
            menu.exec(QCursor.pos())

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
                show_critical(self, "Cannot Proceed", msgs)
                return
            if result.advisory_warnings:
                from settings import load_settings, save_settings
                s = load_settings()
                if not s.get("warn_grading_type_reinterpret", True):
                    # User previously suppressed this warning
                    self._run_edit(edit_fn)
                    return
                msgs = "\n\n".join(
                    w.message for w in result.advisory_warnings
                )
                reply, suppress = show_warning_suppressible(
                    self, "Existing Grades",
                    msgs + "\n\nApply anyway?",
                    checkbox_label="Don't warn me again",
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if suppress:
                        s["warn_grading_type_reinterpret"] = False
                        save_settings(s)
                    self._run_edit(edit_fn)
                return
            self._run_edit(edit_fn)
        else:
            # Unexpected type — treat as error
            if hasattr(result, 'ok') and not result.ok:
                show_warning(self, "Preflight Error", result.message)
                return
            self._run_edit(edit_fn)

    def _on_edit_result(self, result) -> None:
        """Handle EditResult from a mutation worker."""
        if hasattr(result, 'ok'):
            if result.ok:
                self.edit_completed.emit()
            else:
                show_warning(
                    self, "Edit Failed",
                    result.message or "The change could not be applied."
                )

    def _on_edit_result_quiet(self, result) -> None:
        """Handle EditResult without emitting edit_completed (bulk use)."""
        if hasattr(result, 'ok') and not result.ok:
            show_warning(
                self, "Edit Failed",
                result.message or "The change could not be applied."
            )
