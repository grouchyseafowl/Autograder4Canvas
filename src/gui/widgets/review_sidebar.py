"""
Review Sidebar — Shared course-first navigation for Review tab.

Two-dropdown filter (semester → course) + assignment list organized
by deadline or assignment group. Brightness indicates data availability
for the active tab. QPainter-painted rows with radial glow + pip pattern
matching _CourseRow in bulk_run_dialog.py.

Persists across Grading Review / Academic Integrity / Insights sub-tabs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from PySide6.QtCore import Qt, QRect, Signal, QSize
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget,
)

from settings import load_settings, save_settings
from gui.styles import (
    px,
    SPACING_XS, SPACING_SM, SPACING_MD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    PANEL_GRADIENT, PANE_BG_GRADIENT,
    make_section_label, make_h_rule,
    combo_qss,
)
from gui.widgets.crt_combo import CRTComboBox
from gui.widgets.status_pip import draw_pip
from gui.widgets.switch_toggle import SwitchToggle
from gui.widgets.view_toggle import ViewToggle


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SidebarAssignment:
    course_id: str = ""
    course_name: str = ""
    assignment_id: str = ""
    assignment_name: str = ""
    due_at: Optional[str] = None
    group_name: str = ""
    has_grading: bool = False
    has_aic: bool = False
    has_insights: bool = False
    aic_flag_count: int = 0   # elevated + smoking_gun detections


# ---------------------------------------------------------------------------
# Deadline classification
# ---------------------------------------------------------------------------

_SEVEN_DAYS = 7 * 24 * 3600

_PAST_COLOR   = "#F0A830"   # amber hot  — deadline passed
_WEEK_COLOR   = "#C87C10"   # deep gold  — due this week
_FUTURE_COLOR = "#6B4F2A"   # warm brown — upcoming
_NONE_COLOR   = "#3A2808"   # barely-there — no deadline


def _classify_deadline(due_at: Optional[str]) -> str:
    if not due_at:
        return "NONE"
    try:
        dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = (dt - datetime.now(timezone.utc)).total_seconds()
        if delta < 0:
            return "PAST"
        if delta <= _SEVEN_DAYS:
            return "WEEK"
        return "FUTURE"
    except Exception:
        return "NONE"


_DEADLINE_ORDER = {"PAST": 0, "WEEK": 1, "FUTURE": 2, "NONE": 3}
_DEADLINE_LABEL = {
    "PAST": "DEADLINE PASSED",
    "WEEK": "DUE THIS WEEK",
    "FUTURE": "UPCOMING",
    "NONE": "NO DEADLINE",
}
_DEADLINE_COLOR = {
    "PAST": _PAST_COLOR,
    "WEEK": _WEEK_COLOR,
    "FUTURE": _FUTURE_COLOR,
    "NONE": _NONE_COLOR,
}


# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_COMBO_QSS = combo_qss()


# ---------------------------------------------------------------------------
# _SectionHeader — deadline / group separator
# ---------------------------------------------------------------------------

class _SectionHeader(QWidget):
    """Thin colored section divider for deadline or group buckets."""

    def __init__(self, label: str, color: str = PHOSPHOR_DIM, parent=None):
        super().__init__(parent)
        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 8, 8, 2)
        lo.setSpacing(6)

        bar = QFrame()
        bar.setFixedSize(2, 12)
        bar.setStyleSheet(f"background: {color}; border: none;")
        lo.addWidget(bar)

        lbl = QLabel(label)
        lbl.setStyleSheet(
            f"color: {color}; font-size: {px(9)}px; font-weight: bold;"
            f" letter-spacing: 1.5px; background: transparent; border: none;"
        )
        lo.addWidget(lbl)
        lo.addStretch()


# ---------------------------------------------------------------------------
# _AssignmentRow — QPainter-painted row with radial glow + pip
# ---------------------------------------------------------------------------

# System color coding
_CLR_AIC      = (120, 180, 220)   # baby blue — Academic Integrity
_CLR_INSIGHTS = (204, 82, 130)    # pink/rose — Insights


class _AssignmentRow(QWidget):
    """Single assignment row with CRT phosphor glow.

    Painted identically to _CourseRow in bulk_run_dialog.py:
    - Void base (#0A0800)
    - Selected: rose radial glow + pip
    - Hover: amber radial glow + pip
    - At rest: transparent (dim or bright text depending on data)

    When the active tab is 'grading', small right-aligned markers show
    AIC flag count (baby blue) and insights availability (pink pip).
    """

    clicked = Signal(object)  # emits the SidebarAssignment

    def __init__(self, item: SidebarAssignment, row_index: int = 0, parent=None):
        super().__init__(parent)
        self.item = item
        self._row_index = row_index  # for alternating shading
        self._selected = False
        self._hovered = False
        self._has_data = False  # set by set_has_data based on active tab
        self._active_tab: str = "grading"

        self.setFixedHeight(38)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_selected(self, v: bool) -> None:
        self._selected = v
        self.update()

    def set_has_data(self, v: bool) -> None:
        self._has_data = v
        self.update()

    def set_active_tab(self, tab: str) -> None:
        self._active_tab = tab
        self.update()

    # ── Interaction ────────────────────────────────────────────────────

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.item)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ── Painting ──────────────────────────────────────────────────────

    def paintEvent(self, event) -> None:
        is_selected = self._selected
        is_hovered = self._hovered

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Alternating row shading for visual parsing
        if self._row_index % 2 == 1 and not is_selected and not is_hovered:
            p.fillRect(self.rect(), QColor(255, 255, 255, 8))

        if is_selected or is_hovered:
            # Opaque void base
            p.fillRect(self.rect(), QColor("#0A0800"))

            # Radial glow from left
            glow_cx = w * 0.20
            glow_cy = h * 0.50

            if is_selected:
                center_col = QColor(204, 82, 130, 65)
                bloom_col = QColor(204, 82, 130, 30)
            else:
                center_col = QColor(240, 168, 48, 45)
                bloom_col = QColor(240, 168, 48, 18)

            clip = QPainterPath()
            clip.addRect(self.rect())
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)

            grad = QRadialGradient(glow_cx, glow_cy, w * 0.85)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.6, QColor(
                center_col.red(), center_col.green(), center_col.blue(), 15))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(grad)
            p.drawRect(self.rect())

            bloom = QRadialGradient(glow_cx, glow_cy, w * 0.42)
            bloom.setColorAt(0.0, bloom_col)
            bloom.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setBrush(bloom)
            p.drawRect(self.rect())
            p.restore()

            # Pip
            pip_cx = 10.0
            pip_cy = h / 2.0
            if is_selected:
                draw_pip(p, pip_cx, pip_cy, 10, 204, 82, 130,
                         bloom_alpha=55, core_alpha=200)
            else:
                draw_pip(p, pip_cx, pip_cy, 8, 240, 168, 48,
                         bloom_alpha=28, core_alpha=130)

        # ── Right-aligned data markers (grading tab only) ─────────────
        # Reserve right margin for markers so text doesn't overlap
        marker_margin = 0
        if self._active_tab == "grading":
            marker_margin = self._paint_markers(p, w, h)

        # Text
        font = QFont("Menlo", -1)
        font.setPixelSize(px(12))
        p.setFont(font)

        if is_selected:
            p.setPen(QColor(PHOSPHOR_HOT))
        elif self._has_data:
            p.setPen(QColor(PHOSPHOR_MID))
        else:
            p.setPen(QColor(PHOSPHOR_GLOW))

        text_x = 24
        text_rect = self.rect().adjusted(text_x, 0, -(8 + marker_margin), 0)
        fm = QFontMetrics(font)
        elided = fm.elidedText(
            self.item.assignment_name,
            Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, elided)

        # Bottom separator
        p.setPen(QColor(BORDER_DARK))
        p.drawLine(0, h - 1, w, h - 1)

        p.end()

    def _paint_markers(self, p: QPainter, w: int, h: int) -> int:
        """Paint AIC count badge + insights pip on the right edge.

        Returns the total width consumed by markers (for text elide margin).
        """
        right_x = w - 6   # right edge inset
        max_w = 0

        font = QFont("Menlo", -1)
        font.setPixelSize(px(8))
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        fm = QFontMetrics(font)
        badge_h = 13

        def _draw_badge(text: str, rgb: tuple, cy: float,
                        alpha: int = 210, bg_alpha: int = 50,
                        border_alpha: int = 100):
            nonlocal max_w
            r, g, b = rgb
            tw = fm.horizontalAdvance(text)
            bw = max(tw + 8, 16)
            bx = right_x - bw
            by = int(cy - badge_h / 2)

            bg = QRadialGradient(bx + bw / 2, cy, bw * 0.8)
            bg.setColorAt(0.0, QColor(r, g, b, bg_alpha))
            bg.setColorAt(1.0, QColor(r, g, b, bg_alpha // 4))

            path = QPainterPath()
            path.addRoundedRect(bx, by, bw, badge_h, 3, 3)
            p.setPen(QPen(QColor(r, g, b, border_alpha), 1.0))
            p.setBrush(bg)
            p.drawPath(path)

            p.setPen(QColor(r, g, b, alpha))
            p.drawText(QRect(bx, by, bw, badge_h),
                       Qt.AlignmentFlag.AlignCenter, text)
            max_w = max(max_w, bw + 6)

        has_both = ((self.item.aic_flag_count > 0 or self.item.has_aic)
                    and self.item.has_insights)

        # ── AIC badge (baby blue) — upper right ──────────────────────
        aic_cy = (h * 0.30) if has_both else (h / 2.0)
        if self.item.aic_flag_count > 0:
            _draw_badge(str(self.item.aic_flag_count), _CLR_AIC, aic_cy)
        elif self.item.has_aic:
            _draw_badge("—", _CLR_AIC, aic_cy,
                        alpha=100, bg_alpha=20, border_alpha=50)

        # ── Insights badge (pink) — lower right (★ star symbol) ───
        ins_cy = (h * 0.70) if has_both else (h / 2.0)
        if self.item.has_insights:
            _draw_badge("★", _CLR_INSIGHTS, ins_cy)

        return max_w

    def sizeHint(self) -> QSize:
        return QSize(200, 38)


# ---------------------------------------------------------------------------
# ReviewSidebar — main widget
# ---------------------------------------------------------------------------

class ReviewSidebar(QFrame):
    """Shared sidebar for the Review tab.

    Provides semester + course dropdowns, sort toggle, show-all toggle,
    and a scrollable assignment list with QPainter-painted rows.

    Signals
    -------
    assignment_selected(dict)
        SidebarAssignment fields as a dict.
    refresh_requested()
        User clicked the refresh button.
    """

    assignment_selected = Signal(dict)
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("reviewSidebar")
        self.setStyleSheet(f"""
            QFrame#reviewSidebar {{
                background: {PANE_BG_GRADIENT};
                border: 1px solid {BORDER_DARK};
                border-top-color: {BORDER_AMBER};
                border-radius: 8px;
            }}
            QFrame#reviewSidebar QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self.setMinimumWidth(260)
        self.setMaximumWidth(420)

        self._courses_by_term: list = []  # [(term_id, term_name, is_current, [course_dicts])]
        self._assignments_cache: dict = {}  # course_id → [group_dicts]
        self._all_items: List[SidebarAssignment] = []
        self._row_widgets: List[_AssignmentRow] = []
        self._selected_id: Optional[str] = None
        self._active_tab: str = "grading"  # "grading"|"aic"|"insights"
        self._show_all: bool = load_settings().get("review_sidebar_show_all", True)
        self._sort_mode: str = "deadline"  # "deadline"|"group"

        # Store references for data availability queries
        self._grading_store = None
        self._insights_store = None

        self._build_ui()
        self._connect_signals()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header area with dropdowns + controls ─────────────────────
        header = QWidget()
        header.setStyleSheet(f"background: transparent;")
        hdr_lo = QVBoxLayout(header)
        hdr_lo.setContentsMargins(12, 10, 12, 6)
        hdr_lo.setSpacing(SPACING_XS)

        # Semester dropdown
        self._term_combo = CRTComboBox()
        hdr_lo.addWidget(self._term_combo)

        # Course dropdown
        self._course_combo = CRTComboBox()
        hdr_lo.addWidget(self._course_combo)

        # Sort toggle row: [Deadline | Group] + [Show all] + [↻]
        ctrl_row = QHBoxLayout()
        ctrl_row.setContentsMargins(0, 2, 0, 0)
        ctrl_row.setSpacing(6)

        self._sort_toggle = ViewToggle(
            parent=self,
            left_label="Deadline",
            right_label="Group",
            left_mode="deadline",
            right_mode="group",
        )
        self._sort_toggle.setMinimumWidth(140)
        ctrl_row.addWidget(self._sort_toggle, 1)

        self._show_all_switch = SwitchToggle("All", wrap_width=24)
        self._show_all_switch.setChecked(self._show_all)
        self._show_all_switch.setFixedWidth(60)
        ctrl_row.addWidget(self._show_all_switch, 0)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(22, 22)
        refresh_btn.setToolTip("Refresh data from stores")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {PHOSPHOR_DIM}; font-size: {px(13)}px;
            }}
            QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
        """)
        refresh_btn.clicked.connect(self.refresh_requested)
        ctrl_row.addWidget(refresh_btn, 0)

        hdr_lo.addLayout(ctrl_row)
        root.addWidget(header)

        # Amber gradient separator (matches course panel)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0.00 rgba(240,168,48,0),
                    stop:0.20 rgba(240,168,48,0.35),
                    stop:0.50 rgba(240,168,48,0.70),
                    stop:0.80 rgba(240,168,48,0.35),
                    stop:1.00 rgba(240,168,48,0));
                border: none;
            }}
        """)
        root.addWidget(sep)

        # ── Scrollable assignment list ────────────────────────────────
        # Side-origin gradient matching course panel (light bleeds from left)
        _SIDE_GRADIENT = (
            "qradialgradient(cx:0.08,cy:0.45,radius:1.20,fx:0.03,fy:0.40,"
            "stop:0.00 #201A08,stop:0.55 #130E04,stop:1.00 #090702)"
        )
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(f"""
            QScrollArea {{
                background: {BG_INSET};
                border: none;
                border-bottom-left-radius: 6px;
                border-bottom-right-radius: 6px;
            }}
            QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}
        """)
        self._list_container = QWidget()
        self._list_container.setStyleSheet(f"background: {BG_INSET};")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        self._scroll.setWidget(self._list_container)
        root.addWidget(self._scroll, 1)

        # Empty state label is created on-demand in _rebuild_assignment_list

    def _connect_signals(self) -> None:
        self._term_combo.currentIndexChanged.connect(self._on_term_changed)
        self._course_combo.currentIndexChanged.connect(self._on_course_changed)
        self._sort_toggle.mode_changed.connect(self._on_sort_changed)
        self._show_all_switch.toggled.connect(self._on_show_all_changed)

    # ── Public API ────────────────────────────────────────────────────

    def set_courses(
        self,
        courses_by_term: list,
        assignments_cache: Optional[dict] = None,
    ) -> None:
        """Populate semester + course dropdowns.

        courses_by_term: [(term_id, term_name, is_current, [course_dicts])]
        assignments_cache: {course_id: [assignment_group_dicts]}
        """
        self._courses_by_term = courses_by_term
        if assignments_cache:
            self._assignments_cache = assignments_cache

        # Rebuild semester dropdown
        self._term_combo.blockSignals(True)
        self._term_combo.clear()
        self._term_combo.addItem("All Semesters", "all")

        current_idx = 0
        for i, (tid, tname, is_current, _courses) in enumerate(courses_by_term):
            self._term_combo.addItem(tname, tid)
            if is_current:
                current_idx = i + 1  # +1 because "All Semesters" is index 0

        self._term_combo.setCurrentIndex(current_idx)
        self._term_combo.blockSignals(False)

        # Trigger course dropdown rebuild
        self._rebuild_course_dropdown()

    def set_stores(self, grading_store=None, insights_store=None) -> None:
        """Provide store references for data availability queries."""
        self._grading_store = grading_store
        self._insights_store = insights_store

    def set_active_tab(self, tab: str) -> None:
        """Set which tab is active: 'grading'|'aic'|'insights'.

        Controls which assignments appear bright vs dim, and — when
        show-all is off — which assignments are visible at all.
        """
        if tab != self._active_tab:
            self._active_tab = tab
            if not self._show_all:
                # Filtered set depends on the active tab — full rebuild
                self._rebuild_assignment_list()
            else:
                self._update_data_flags()

    def select_assignment(self, assignment_id: str) -> None:
        """Programmatically select an assignment by ID."""
        for row in self._row_widgets:
            if row.item.assignment_id == assignment_id:
                self._do_select(row.item)
                return

    def selected_assignment_id(self) -> Optional[str]:
        return self._selected_id

    # ── Internal: dropdown cascading ──────────────────────────────────

    def _rebuild_course_dropdown(self) -> None:
        """Rebuild course dropdown based on selected semester."""
        self._course_combo.blockSignals(True)
        self._course_combo.clear()
        self._course_combo.addItem("All Courses", "all")

        selected_term = self._term_combo.currentData()
        for tid, tname, is_current, courses in self._courses_by_term:
            if selected_term != "all" and tid != selected_term:
                continue
            for c in courses:
                self._course_combo.addItem(
                    c.get("name", "Unknown"),
                    str(c.get("id", "")),
                )

        self._course_combo.setCurrentIndex(0)
        self._course_combo.blockSignals(False)
        self._rebuild_assignment_list()

    def _on_term_changed(self, idx: int) -> None:
        self._rebuild_course_dropdown()

    def _on_course_changed(self, idx: int) -> None:
        self._rebuild_assignment_list()

    def _on_sort_changed(self, mode: str) -> None:
        self._sort_mode = mode
        self._rebuild_assignment_list()

    def _on_show_all_changed(self, checked: bool) -> None:
        self._show_all = checked
        # Persist across sessions
        s = load_settings()
        s["review_sidebar_show_all"] = checked
        save_settings(s)
        self._rebuild_assignment_list()

    # ── Build assignment list ─────────────────────────────────────────

    def _get_visible_courses(self) -> List[dict]:
        """Return course dicts matching the current semester + course filter."""
        selected_term = self._term_combo.currentData()
        selected_course = self._course_combo.currentData()
        result = []
        for tid, tname, is_current, courses in self._courses_by_term:
            if selected_term != "all" and tid != selected_term:
                continue
            for c in courses:
                cid = str(c.get("id", ""))
                if selected_course != "all" and cid != selected_course:
                    continue
                result.append(c)
        return result

    def _build_sidebar_items(self) -> List[SidebarAssignment]:
        """Build SidebarAssignment items from visible courses + cache."""
        courses = self._get_visible_courses()
        items: List[SidebarAssignment] = []

        # Query stores for data availability + AIC flag counts
        grading_aids: set = set()
        aic_aids: set = set()
        aic_counts: Dict[str, int] = {}   # assignment_id → flag count
        insights_aids: set = set()
        try:
            if self._grading_store:
                for row in self._grading_store.get_grading_assignments():
                    aid = str(row.get("assignment_id", ""))
                    grading_aids.add(aid)
                    # get_grading_assignments already LEFT JOINs aic_results
                    elevated = int(row.get("aic_elevated_count", 0) or 0)
                    smoking = int(row.get("aic_smoking_gun_count", 0) or 0)
                    if elevated or smoking:
                        aic_aids.add(aid)
                        aic_counts[aid] = elevated + smoking
        except Exception:
            pass
        try:
            if self._grading_store:
                for row in self._grading_store.get_runs():
                    aid = str(row.get("assignment_id", ""))
                    aic_aids.add(aid)
                    if aid not in aic_counts:
                        aic_counts[aid] = int(row.get("smoking_gun_count", 0) or 0)
        except Exception:
            pass
        try:
            if self._insights_store:
                for row in self._insights_store.get_runs():
                    insights_aids.add(str(row.get("assignment_id", "")))
        except Exception:
            pass

        for c in courses:
            cid = str(c.get("id", ""))
            cname = c.get("name", "Unknown")
            groups = self._assignments_cache.get(int(cid), []) or self._assignments_cache.get(cid, [])
            for g in groups:
                gname = g.get("name", "")
                for a in g.get("assignments", []):
                    aid = str(a.get("id", ""))
                    items.append(SidebarAssignment(
                        course_id=cid,
                        course_name=cname,
                        assignment_id=aid,
                        assignment_name=a.get("name", "Unknown"),
                        due_at=a.get("due_at"),
                        group_name=gname,
                        has_grading=aid in grading_aids,
                        has_aic=aid in aic_aids,
                        has_insights=aid in insights_aids,
                        aic_flag_count=aic_counts.get(aid, 0),
                    ))

        return items

    def _rebuild_assignment_list(self) -> None:
        """Rebuild the scrollable assignment list."""
        self._all_items = self._build_sidebar_items()
        self._row_widgets.clear()

        # Clear all widgets (each rebuild creates fresh widgets)
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        items = self._all_items

        # Filter: hide items with no data for the active tab if show_all is off
        if not self._show_all:
            tab = self._active_tab
            if tab == "grading":
                items = [it for it in items if it.has_grading]
            elif tab == "aic":
                items = [it for it in items if it.has_aic]
            elif tab == "insights":
                items = [it for it in items if it.has_insights]

        if not items:
            empty_lbl = QLabel("Select a course to browse assignments.")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setWordWrap(True)
            empty_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
                f" padding: 20px; background: transparent;"
            )
            self._list_layout.addWidget(empty_lbl)
            self._list_layout.addStretch()
            return

        if self._sort_mode == "deadline":
            self._populate_by_deadline(items)
        else:
            self._populate_by_group(items)

        self._list_layout.addStretch()
        self._update_data_flags()

    def _populate_by_deadline(self, items: List[SidebarAssignment]) -> None:
        """Sort and section by deadline bucket."""
        # Sort: deadline bucket first, then due_at within bucket
        def sort_key(it):
            bucket = _DEADLINE_ORDER.get(_classify_deadline(it.due_at), 3)
            try:
                dt = datetime.fromisoformat(
                    (it.due_at or "").replace("Z", "+00:00"))
                ts = dt.timestamp()
            except Exception:
                ts = 0
            return (bucket, ts, it.assignment_name.lower())

        items = sorted(items, key=sort_key)

        current_bucket = None
        row_idx = 0
        for it in items:
            bucket = _classify_deadline(it.due_at)
            if bucket != current_bucket:
                current_bucket = bucket
                row_idx = 0  # reset alternation per section
                hdr = _SectionHeader(
                    _DEADLINE_LABEL.get(bucket, ""),
                    _DEADLINE_COLOR.get(bucket, PHOSPHOR_DIM),
                )
                self._list_layout.addWidget(hdr)

            row = _AssignmentRow(it, row_index=row_idx)
            row.clicked.connect(self._on_row_clicked)
            if self._selected_id and it.assignment_id == self._selected_id:
                row.set_selected(True)
            self._row_widgets.append(row)
            self._list_layout.addWidget(row)
            row_idx += 1

    def _populate_by_group(self, items: List[SidebarAssignment]) -> None:
        """Sort and section by assignment group."""
        groups: Dict[str, List[SidebarAssignment]] = {}
        for it in items:
            gn = it.group_name or "Ungrouped"
            groups.setdefault(gn, []).append(it)

        for gname in sorted(groups.keys()):
            hdr = _SectionHeader(gname.upper(), PHOSPHOR_DIM)
            self._list_layout.addWidget(hdr)

            row_idx = 0
            for it in sorted(groups[gname], key=lambda x: x.assignment_name.lower()):
                row = _AssignmentRow(it, row_index=row_idx)
                row.clicked.connect(self._on_row_clicked)
                if self._selected_id and it.assignment_id == self._selected_id:
                    row.set_selected(True)
                self._row_widgets.append(row)
                self._list_layout.addWidget(row)
                row_idx += 1

    def _update_data_flags(self) -> None:
        """Update bright/dim state and active tab on all rows."""
        tab = self._active_tab
        for row in self._row_widgets:
            it = row.item
            row.set_active_tab(tab)
            if tab == "grading":
                row.set_has_data(it.has_grading)
            elif tab == "aic":
                row.set_has_data(it.has_aic)
            elif tab == "insights":
                row.set_has_data(it.has_insights)
            else:
                row.set_has_data(True)

    # ── Selection ─────────────────────────────────────────────────────

    def _on_row_clicked(self, item: SidebarAssignment) -> None:
        self._do_select(item)

    def _do_select(self, item: SidebarAssignment) -> None:
        # Toggle: clicking the already-selected item deselects it
        if self._selected_id == item.assignment_id:
            self._selected_id = None
            for row in self._row_widgets:
                row.set_selected(False)
            self.assignment_selected.emit({})
            return

        self._selected_id = item.assignment_id
        for row in self._row_widgets:
            row.set_selected(row.item.assignment_id == item.assignment_id)
        self.assignment_selected.emit({
            "course_id": item.course_id,
            "course_name": item.course_name,
            "assignment_id": item.assignment_id,
            "assignment_name": item.assignment_name,
            "due_at": item.due_at,
            "group_name": item.group_name,
            "has_grading": item.has_grading,
            "has_aic": item.has_aic,
            "has_insights": item.has_insights,
        })
