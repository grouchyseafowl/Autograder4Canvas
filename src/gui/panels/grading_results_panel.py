"""
Grading Results Panel — Three-column master-detail view for reviewing grading results.

Layout:
  Left column (sidebar):   Course → Assignment tree with status indicators
  Middle column:            Student list with grades, flags, AIC pips
  Right column:             Student detail (grade card, AIC card, submission viewer, triage)

Indicators per assignment:
  ⚠ amber  — grading flags or manual review needed
  ● rose   — AIC concern (elevated+ or smoking gun)
  ✓ green  — all clear
"""

import json
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QSizePolicy, QComboBox, QLineEdit,
    QTextBrowser, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer
from PySide6.QtGui import (
    QColor, QPainter, QPen, QFont, QFontMetrics,
    QRadialGradient, QPainterPath,
)

from gui.styles import (
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, ROSE_DIM, WARN_PINK, TERM_GREEN, BURN_RED, AMBER_BTN,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    CARD_GRADIENT, PANEL_GRADIENT,
    make_secondary_button, make_run_button, GripSplitter,
    make_section_label, make_h_rule, make_content_pane,
)
from gui.aic_palette import CONCERN_COLOR, CONCERN_LABEL
from gui.widgets.phosphor_chip import PhosphorChip


# ──────────────────────────────────────────────────────────────────────────────
# Local stylesheets
# ──────────────────────────────────────────────────────────────────────────────

_SIDEBAR_QSS = f"""
    QFrame#gradingSidebar {{
        background: {PANEL_GRADIENT};
        border-right: 1px solid {BORDER_DARK};
    }}
"""

_FILTER_COMBO_QSS = f"""
    QComboBox {{
        background: {BG_INSET};
        color: {PHOSPHOR_MID};
        border: 1px solid {BORDER_DARK};
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 11px;
    }}
    QComboBox:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_HOT}; }}
    QComboBox::drop-down {{ border: none; width: 18px; }}
    QComboBox QAbstractItemView {{
        background: {BG_CARD};
        color: {PHOSPHOR_MID};
        selection-background-color: {BG_PANEL};
        selection-color: {PHOSPHOR_HOT};
        border: 1px solid {BORDER_DARK};
    }}
"""

_SEARCH_QSS = f"""
    QLineEdit {{
        background: {BG_INSET};
        color: {PHOSPHOR_HOT};
        border: 1px solid {BORDER_DARK};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: 11px;
    }}
    QLineEdit:focus {{ border-color: {PHOSPHOR_HOT}; }}
"""

_ASSIGNMENT_ROW_QSS = f"""
    QFrame {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-bottom: 1px solid {BORDER_DARK};
        padding: 2px 0;
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(240,168,48,0.14),stop:0.45 rgba(240,168,48,0.04),stop:1.0 transparent);
        border-left-color: {BORDER_AMBER};
    }}
"""

_ASSIGNMENT_ROW_SEL_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(204,82,130,0.22),stop:0.45 rgba(204,82,130,0.06),stop:1.0 transparent);
        border: none;
        border-left: 3px solid {PHOSPHOR_HOT};
        border-bottom: 1px solid {BORDER_DARK};
    }}
"""

_STUDENT_ROW_QSS = f"""
    QFrame {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-bottom: 1px solid {BORDER_DARK};
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(240,168,48,0.12),stop:0.45 rgba(240,168,48,0.03),stop:1.0 transparent);
        border-left-color: {BORDER_AMBER};
    }}
"""

_STUDENT_ROW_SEL_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(204,82,130,0.22),stop:0.45 rgba(204,82,130,0.06),stop:1.0 transparent);
        border: none;
        border-left: 3px solid {PHOSPHOR_HOT};
        border-bottom: 1px solid {BORDER_DARK};
    }}
"""

_STUDENT_ROW_FLAGGED_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(224,128,42,0.14),stop:0.45 rgba(224,128,42,0.04),stop:1.0 transparent);
        border: none;
        border-left: 3px solid {WARN_PINK};
        border-bottom: 1px solid {BORDER_DARK};
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(224,128,42,0.22),stop:0.45 rgba(224,128,42,0.06),stop:1.0 transparent);
    }}
"""

_STUDENT_ROW_AIC_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(204,82,130,0.12),stop:0.45 rgba(204,82,130,0.03),stop:1.0 transparent);
        border: none;
        border-left: 3px solid {ROSE_DIM};
        border-bottom: 1px solid {BORDER_DARK};
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(204,82,130,0.22),stop:0.45 rgba(204,82,130,0.06),stop:1.0 transparent);
    }}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Helper widgets
# ──────────────────────────────────────────────────────────────────────────────

class AICPipWidget(QWidget):
    """Small QPainter-drawn concern-level pip with optional smoking-gun glow."""

    def __init__(self, concern_level: str = "none", smoking_gun: bool = False,
                 parent: QWidget = None):
        super().__init__(parent)
        self._concern = concern_level
        self._smoking_gun = smoking_gun
        self.setFixedSize(16, 16)
        self.setToolTip(self._tooltip_text())

    def set_concern(self, level: str, smoking_gun: bool = False) -> None:
        self._concern = level
        self._smoking_gun = smoking_gun
        self.setToolTip(self._tooltip_text())
        self.update()

    def _tooltip_text(self) -> str:
        label = CONCERN_LABEL.get(self._concern, self._concern)
        tip = label
        if self._smoking_gun:
            tip += " · Smoking gun detected"
        return tip

    def paintEvent(self, event) -> None:
        if self._concern == "none" and not self._smoking_gun:
            return  # nothing to draw
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(CONCERN_COLOR.get(self._concern, PHOSPHOR_DIM))
        cx, cy = self.width() // 2, self.height() // 2

        if self._smoking_gun:
            # Glow ring
            glow = QRadialGradient(cx, cy, 7)
            glow.setColorAt(0.0, QColor(ROSE_ACCENT))
            glow.setColorAt(0.5, QColor(204, 82, 130, 120))
            glow.setColorAt(1.0, QColor(204, 82, 130, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(cx - 7, cy - 7, 14, 14)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        p.drawEllipse(cx - 4, cy - 4, 8, 8)
        p.end()


class GradeBadge(QWidget):
    """Small grade indicator: COMP (green) / INC (amber) / override."""

    def __init__(self, grade: str = "", parent: QWidget = None):
        super().__init__(parent)
        self._grade = grade
        self.setFixedSize(48, 18)

    def set_grade(self, grade: str) -> None:
        self._grade = grade
        self.update()

    def paintEvent(self, event) -> None:
        if not self._grade:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        is_complete = self._grade.lower() in ("complete", "comp")
        color = QColor(TERM_GREEN) if is_complete else QColor("#E0802A")
        text = "COMP" if is_complete else "INC"

        # Badge background
        rect = self.rect().adjusted(1, 1, -1, -1)
        path = QPainterPath()
        path.addRoundedRect(rect, 3, 3)
        fill = QColor(color)
        fill.setAlpha(30)
        p.fillPath(path, fill)
        p.setPen(QPen(color, 1.0))
        p.drawPath(path)

        # Text
        font = p.font()
        font.setPixelSize(10)
        font.setWeight(QFont.Weight.Bold)
        p.setFont(font)
        p.setPen(color)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)
        p.end()


def _make_card(object_name: str = "card") -> QFrame:
    card = QFrame()
    card.setObjectName(object_name)
    card.setStyleSheet(f"""
        QFrame#{object_name} {{
            background: {CARD_GRADIENT};
            border: 1px solid {BORDER_DARK};
            border-radius: 6px;
        }}
    """)
    return card


def _collapsible_header(text: str, initially_open: bool = True) -> tuple:
    """Return (header_frame, content_widget, toggle_fn)."""
    header = QFrame()
    header.setFixedHeight(28)
    header.setStyleSheet(f"""
        QFrame {{
            background: {BG_PANEL};
            border: none;
            border-bottom: 1px solid {BORDER_DARK};
        }}
        QFrame:hover {{ background: #1A1205; }}
    """)
    header.setCursor(Qt.CursorShape.PointingHandCursor)
    hl = QHBoxLayout(header)
    hl.setContentsMargins(SPACING_SM, 0, SPACING_SM, 0)
    arrow_lbl = QLabel("▾" if initially_open else "▸")
    arrow_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;")
    hl.addWidget(arrow_lbl)
    title_lbl = QLabel(text.upper())
    title_lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
        f" letter-spacing: 1.5px; background: transparent;"
    )
    hl.addWidget(title_lbl)
    hl.addStretch()

    content = QWidget()
    content.setVisible(initially_open)

    def toggle():
        vis = not content.isVisible()
        content.setVisible(vis)
        arrow_lbl.setText("▾" if vis else "▸")

    header.mousePressEvent = lambda e: toggle()
    return header, content, toggle


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar: Course → Assignment tree
# ──────────────────────────────────────────────────────────────────────────────

class _GradingSidebar(QFrame):
    """Left sidebar: filter combo + course→assignment tree."""

    assignment_selected = Signal(str, str, str, str)  # course_id, assignment_id, course_name, assignment_name
    refresh_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("gradingSidebar")
        self.setStyleSheet(_SIDEBAR_QSS)
        self.setMinimumWidth(200)

        self._assignments: List[Dict] = []
        self._selected_key: tuple = ()
        self._filter_mode = "all"
        self._course_collapsed: dict = {}  # course_id -> bool

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Filter combo
        filter_row = QHBoxLayout()
        filter_row.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        self._filter_combo = QComboBox()
        self._filter_combo.setStyleSheet(_FILTER_COMBO_QSS)
        self._filter_combo.addItem("All", "all")
        self._filter_combo.addItem("Needs Attention", "attention")
        self._filter_combo.addItem("Manual Review", "review")
        self._filter_combo.addItem("AIC Concerns", "aic")
        self._filter_combo.currentIndexChanged.connect(self._on_filter_changed)
        filter_row.addWidget(self._filter_combo, 1)

        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setToolTip("Refresh from database")
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {PHOSPHOR_DIM}; font-size: 14px;
            }}
            QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
        """)
        refresh_btn.clicked.connect(self.refresh_requested)
        filter_row.addWidget(refresh_btn)
        layout.addLayout(filter_row)

        # Scrollable assignment tree
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_PANEL}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {BG_PANEL}; }}
        """)
        self._tree_container = QWidget()
        self._tree_container.setStyleSheet(f"background: {BG_PANEL};")
        self._tree_layout = QVBoxLayout(self._tree_container)
        self._tree_layout.setContentsMargins(0, 0, 0, 0)
        self._tree_layout.setSpacing(0)
        self._tree_layout.addStretch()
        scroll.setWidget(self._tree_container)
        layout.addWidget(scroll, 1)

    def populate(self, assignments: List[Dict]) -> None:
        """Populate sidebar from get_grading_assignments() result."""
        self._assignments = assignments
        self._rebuild_tree()

    def _on_filter_changed(self, idx: int) -> None:
        self._filter_mode = self._filter_combo.itemData(idx)
        self._rebuild_tree()

    def _rebuild_tree(self) -> None:
        # Clear
        while self._tree_layout.count():
            item = self._tree_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Group by course
        courses: dict = {}
        for a in self._assignments:
            cid = a.get("course_id", "")
            cname = a.get("course_name", "Unknown Course")
            if cid not in courses:
                courses[cid] = {"name": cname, "assignments": []}
            courses[cid]["assignments"].append(a)

        for cid, data in courses.items():
            # Apply filter
            filtered = self._filter_assignments(data["assignments"])
            if not filtered and self._filter_mode != "all":
                continue

            items = filtered if filtered else data["assignments"]

            # Course header
            header = QFrame()
            header.setFixedHeight(28)
            header.setCursor(Qt.CursorShape.PointingHandCursor)
            header.setStyleSheet(f"""
                QFrame {{
                    background: {BG_CARD};
                    border: none;
                    border-bottom: 1px solid {BORDER_DARK};
                }}
                QFrame:hover {{
                    background: qradialgradient(cx:0.3,cy:0.5,radius:0.9,
                        stop:0.0 rgba(240,168,48,0.10),stop:0.6 {BG_CARD},stop:1.0 {BG_CARD});
                }}
            """)
            hl = QHBoxLayout(header)
            hl.setContentsMargins(SPACING_SM, 0, SPACING_SM, 0)
            hl.setSpacing(4)

            is_collapsed = self._course_collapsed.get(cid, False)
            arrow = QLabel("▸" if is_collapsed else "▾")
            arrow.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;")
            hl.addWidget(arrow)

            name_lbl = QLabel(data["name"].upper())
            name_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
                f" letter-spacing: 1px; background: transparent;"
            )
            hl.addWidget(name_lbl)
            hl.addStretch()

            # Container for this course's assignments
            container = QWidget()
            container.setStyleSheet(f"background: {BG_PANEL};")
            container.setVisible(not is_collapsed)
            cl = QVBoxLayout(container)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(0)

            def make_toggle(cid=cid, container=container, arrow=arrow):
                def toggle(event):
                    vis = not container.isVisible()
                    container.setVisible(vis)
                    arrow.setText("▸" if not vis else "▾")
                    self._course_collapsed[cid] = not vis
                return toggle

            header.mousePressEvent = make_toggle()

            for a in items:
                row = self._make_assignment_row(a)
                cl.addWidget(row)

            self._tree_layout.addWidget(header)
            self._tree_layout.addWidget(container)

        self._tree_layout.addStretch()

    def _filter_assignments(self, assignments: List[Dict]) -> List[Dict]:
        mode = self._filter_mode
        if mode == "all":
            return assignments
        result = []
        for a in assignments:
            flagged = a.get("flagged_count", 0)
            aic_elevated = a.get("aic_elevated_count", 0)
            aic_sg = a.get("aic_smoking_gun_count", 0)
            if mode == "attention" and (flagged > 0 or aic_elevated > 0 or aic_sg > 0):
                result.append(a)
            elif mode == "review" and flagged > 0:
                result.append(a)
            elif mode == "aic" and (aic_elevated > 0 or aic_sg > 0):
                result.append(a)
        return result

    def _make_assignment_row(self, a: Dict) -> QFrame:
        cid = a.get("course_id", "")
        aid = a.get("assignment_id", "")
        cname = a.get("course_name", "")
        aname = a.get("assignment_name", "Unknown")
        total = a.get("total_students", 0)
        complete = a.get("complete_count", 0)
        flagged = a.get("flagged_count", 0)
        aic_elevated = a.get("aic_elevated_count", 0)
        aic_sg = a.get("aic_smoking_gun_count", 0)

        is_selected = self._selected_key == (cid, aid)
        has_grading_flag = flagged > 0
        has_aic_concern = aic_elevated > 0 or aic_sg > 0

        row = QFrame()
        row.setFixedHeight(36)
        row.setCursor(Qt.CursorShape.PointingHandCursor)
        row.setStyleSheet(_ASSIGNMENT_ROW_SEL_QSS if is_selected else _ASSIGNMENT_ROW_QSS)

        rl = QHBoxLayout(row)
        rl.setContentsMargins(SPACING_MD, 2, SPACING_SM, 2)
        rl.setSpacing(6)

        # Status indicators
        if has_grading_flag and has_aic_concern:
            indicator = QLabel("⚠ ●")
            indicator.setStyleSheet(f"color: {WARN_PINK}; font-size: 11px; background: transparent;")
        elif has_grading_flag:
            indicator = QLabel("⚠")
            indicator.setStyleSheet(f"color: #E0802A; font-size: 11px; background: transparent;")
        elif has_aic_concern:
            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {ROSE_ACCENT}; font-size: 11px; background: transparent;")
        else:
            indicator = QLabel("✓")
            indicator.setStyleSheet(f"color: {TERM_GREEN}; font-size: 11px; background: transparent; opacity: 0.6;")
        indicator.setFixedWidth(20)
        rl.addWidget(indicator)

        # Assignment name
        name_lbl = QLabel(aname)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT if is_selected else PHOSPHOR_MID};"
            f" font-size: 12px; background: transparent;"
        )
        rl.addWidget(name_lbl, 1)

        # Count label
        parts = []
        if total:
            parts.append(f"{complete}/{total}")
        if flagged:
            parts.append(f"{flagged} flagged")
        if aic_sg:
            parts.append(f"{aic_sg} SG")
        count_text = " · ".join(parts) if parts else ""
        count_lbl = QLabel(count_text)
        color = WARN_PINK if flagged else (ROSE_ACCENT if aic_sg else PHOSPHOR_DIM)
        count_lbl.setStyleSheet(
            f"color: {color}; font-size: 10px; background: transparent;"
        )
        rl.addWidget(count_lbl)

        row.mousePressEvent = lambda e, c=cid, a=aid, cn=cname, an=aname: (
            self._on_assignment_clicked(c, a, cn, an)
        )
        return row

    def select_first_for_course(self, course_id: str) -> None:
        """Auto-select the first assignment in the sidebar matching course_id."""
        for a in self._assignments:
            if str(a.get("course_id", "")) == course_id:
                self._on_assignment_clicked(
                    course_id,
                    str(a.get("assignment_id", "")),
                    a.get("course_name", ""),
                    a.get("assignment_name", "Unknown"),
                )
                return

    def _on_assignment_clicked(self, cid, aid, cname, aname) -> None:
        self._selected_key = (cid, aid)
        self._rebuild_tree()
        self.assignment_selected.emit(cid, aid, cname, aname)


# ──────────────────────────────────────────────────────────────────────────────
# Middle column: Student list
# ──────────────────────────────────────────────────────────────────────────────

class _StudentList(QFrame):
    """Middle column: assignment header + filter chips + student rows."""

    student_selected = Signal(dict)  # full student row dict
    export_requested = Signal()
    prev_flagged = Signal()
    next_flagged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._students: List[Dict] = []
        self._filtered: List[Dict] = []
        self._selected_id: str = ""
        self._filter_mode = "all"
        self._sort_key = "name"
        self._search_text = ""
        self._assignment_name = ""
        self._flagged_index = -1
        self._flash_timer: Optional[QTimer] = None

        self.setFocusPolicy(Qt.FocusPolicy.ClickFocus)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = QFrame()
        self._header.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border-bottom: 1px solid {BORDER_DARK}; }}
        """)
        hl = QVBoxLayout(self._header)
        hl.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        hl.setSpacing(4)

        top_row = QHBoxLayout()
        self._title_lbl = QLabel("Select an assignment")
        self._title_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 13px; font-weight: bold;"
            f" background: transparent;"
        )
        top_row.addWidget(self._title_lbl, 1)

        self._export_btn = QPushButton("Export XLSX")
        self._export_btn.setFixedHeight(24)
        self._export_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {BORDER_DARK};
                color: {PHOSPHOR_DIM}; font-size: 10px; padding: 2px 10px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_HOT}; }}
        """)
        self._export_btn.clicked.connect(self.export_requested)
        self._export_btn.setVisible(False)
        top_row.addWidget(self._export_btn)
        hl.addLayout(top_row)

        self._subtitle_lbl = QLabel("")
        self._subtitle_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
        )
        hl.addWidget(self._subtitle_lbl)

        # AIC aggregate banner (hidden by default)
        self._aic_banner = QLabel("")
        self._aic_banner.setWordWrap(True)
        self._aic_banner.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: 10px; background: rgba(204,82,130,0.08);"
            f" border: 1px solid {ROSE_DIM}; border-radius: 3px; padding: 3px 6px;"
        )
        self._aic_banner.setVisible(False)
        hl.addWidget(self._aic_banner)

        # Filter chips + sort + search
        chip_row = QHBoxLayout()
        chip_row.setSpacing(4)

        self._chip_buttons = []
        for label, mode in [("All", "all"), ("Complete", "complete"),
                            ("Incomplete", "incomplete"), ("Flagged", "flagged")]:
            chip = PhosphorChip(label, active=(mode == "all"))
            chip.toggled.connect(lambda _, m=mode: self._set_filter(m))
            chip_row.addWidget(chip)
            self._chip_buttons.append((chip, mode))

        chip_row.addStretch()

        self._sort_combo = QComboBox()
        self._sort_combo.setStyleSheet(_FILTER_COMBO_QSS)
        self._sort_combo.setFixedWidth(100)
        self._sort_combo.addItem("Name", "name")
        self._sort_combo.addItem("Grade", "grade")
        self._sort_combo.addItem("Words", "word_count")
        self._sort_combo.addItem("AIC", "aic_concern")
        self._sort_combo.currentIndexChanged.connect(self._on_sort_changed)
        chip_row.addWidget(self._sort_combo)
        hl.addLayout(chip_row)

        # Search
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Search by name...")
        self._search_input.setStyleSheet(_SEARCH_QSS)
        self._search_input.setFixedHeight(24)
        self._search_input.textChanged.connect(self._on_search_changed)
        hl.addWidget(self._search_input)

        layout.addWidget(self._header)

        # Flash feedback bar (triage result notification)
        self._flash_bar = QLabel("")
        self._flash_bar.setFixedHeight(24)
        self._flash_bar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._flash_bar.setStyleSheet(
            f"font-size: 11px; font-weight: bold; background: transparent; border: none;"
        )
        self._flash_bar.setVisible(False)
        layout.addWidget(self._flash_bar)

        # Student rows scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_VOID}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {BG_VOID}; }}
        """)
        self._list_container = QWidget()
        self._list_container.setStyleSheet(f"background: {BG_VOID};")
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 0, 0)
        self._list_layout.setSpacing(0)
        self._list_layout.addStretch()
        scroll.setWidget(self._list_container)
        layout.addWidget(scroll, 1)

        # Footer: summary + nav buttons
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{ background: {BG_CARD}; border-top: 1px solid {BORDER_DARK}; }}
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(SPACING_MD, SPACING_XS, SPACING_MD, SPACING_XS)

        self._summary_lbl = QLabel("")
        self._summary_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
        )
        fl.addWidget(self._summary_lbl, 1)

        self._review_progress = QLabel("")
        self._review_progress.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
        )
        fl.addWidget(self._review_progress)

        prev_btn = QPushButton("← Prev flagged")
        prev_btn.setFixedHeight(22)
        prev_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {BORDER_DARK};
                color: {PHOSPHOR_DIM}; font-size: 10px; padding: 1px 6px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}
        """)
        prev_btn.clicked.connect(self.prev_flagged)
        fl.addWidget(prev_btn)

        next_btn = QPushButton("Next flagged →")
        next_btn.setFixedHeight(22)
        next_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {BORDER_DARK};
                color: {PHOSPHOR_DIM}; font-size: 10px; padding: 1px 6px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}
        """)
        next_btn.clicked.connect(self.next_flagged)
        fl.addWidget(next_btn)

        layout.addWidget(footer)

    def set_assignment(self, name: str, subtitle: str) -> None:
        self._assignment_name = name
        self._title_lbl.setText(name)
        self._subtitle_lbl.setText(subtitle)
        self._export_btn.setVisible(True)

    def populate(self, students: List[Dict]) -> None:
        self._students = students
        self._apply_filters()

        # AIC banner
        aic_students = [s for s in students if s.get("aic_concern_level") not in (None, "none", "low")]
        aic_sg = [s for s in students if s.get("aic_smoking_gun")]
        if aic_students or aic_sg:
            parts = []
            if aic_students:
                parts.append(f"{len(aic_students)} elevated+")
            if aic_sg:
                parts.append(f"{len(aic_sg)} smoking gun")
            overlap = [s for s in aic_students
                       if s.get("grade", "").lower() == "incomplete"]
            if overlap:
                parts.append(f"{len(overlap)} overlap with incomplete")
            self._aic_banner.setText("AIC: " + ", ".join(parts))
            self._aic_banner.setVisible(True)
        else:
            self._aic_banner.setVisible(False)

    def _set_filter(self, mode: str) -> None:
        self._filter_mode = mode
        for chip, m in self._chip_buttons:
            chip.blockSignals(True)
            chip.setChecked(m == mode)
            chip.blockSignals(False)
        self._apply_filters()

    def _on_sort_changed(self, idx: int) -> None:
        self._sort_key = self._sort_combo.itemData(idx)
        self._apply_filters()

    def _on_search_changed(self, text: str) -> None:
        self._search_text = text.lower().strip()
        self._apply_filters()

    def _apply_filters(self) -> None:
        filtered = list(self._students)

        # Text search
        if self._search_text:
            filtered = [s for s in filtered
                        if self._search_text in s.get("student_name", "").lower()]

        # Grade filter
        if self._filter_mode == "complete":
            filtered = [s for s in filtered if s.get("grade", "").lower() == "complete"]
        elif self._filter_mode == "incomplete":
            filtered = [s for s in filtered if s.get("grade", "").lower() == "incomplete"]
        elif self._filter_mode == "flagged":
            filtered = [s for s in filtered if s.get("is_flagged")]

        # Sort
        if self._sort_key == "name":
            filtered.sort(key=lambda s: s.get("student_name", "").lower())
        elif self._sort_key == "grade":
            filtered.sort(key=lambda s: (0 if s.get("grade", "").lower() == "incomplete" else 1,
                                         s.get("student_name", "").lower()))
        elif self._sort_key == "word_count":
            filtered.sort(key=lambda s: s.get("word_count", 0))
        elif self._sort_key == "aic_concern":
            order = {"high": 0, "elevated": 1, "moderate": 2, "low": 3, "none": 4}
            filtered.sort(key=lambda s: order.get(s.get("aic_concern_level", "none"), 5))

        self._filtered = filtered
        self._rebuild_list()
        self._update_summary()

    def _rebuild_list(self) -> None:
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for s in self._filtered:
            row = self._make_student_row(s)
            self._list_layout.addWidget(row)

        self._list_layout.addStretch()

    def _make_student_row(self, s: Dict) -> QFrame:
        sid = str(s.get("student_id", ""))
        name = s.get("student_name", "Unknown")
        grade = s.get("grade", "")
        wc = s.get("word_count", 0)
        flagged = s.get("is_flagged", 0)
        aic_concern = s.get("aic_concern_level", "none")
        aic_sg = s.get("aic_smoking_gun", False)
        has_override = s.get("teacher_override") is not None
        was_skipped = s.get("was_skipped", 0)

        is_selected = self._selected_id == sid

        row = QFrame()
        row.setFixedHeight(38)
        row.setCursor(Qt.CursorShape.PointingHandCursor)

        if is_selected:
            row.setStyleSheet(_STUDENT_ROW_SEL_QSS)
        elif flagged:
            row.setStyleSheet(_STUDENT_ROW_FLAGGED_QSS)
        elif aic_concern not in ("none", "low", None):
            row.setStyleSheet(_STUDENT_ROW_AIC_QSS)
        else:
            row.setStyleSheet(_STUDENT_ROW_QSS)

        rl = QHBoxLayout(row)
        rl.setContentsMargins(SPACING_SM, 2, SPACING_SM, 2)
        rl.setSpacing(6)

        # AIC pip
        pip = AICPipWidget(aic_concern or "none", bool(aic_sg))
        rl.addWidget(pip)

        # Name
        name_lbl = QLabel(name)
        name_color = PHOSPHOR_HOT if is_selected else PHOSPHOR_MID
        name_lbl.setStyleSheet(f"color: {name_color}; font-size: 12px; background: transparent;")
        rl.addWidget(name_lbl, 1)

        # Flagged / needs review badge
        # Show for: grading flags on a real submission, OR elevated+ AIC concern
        is_aic_concern = aic_concern in ("elevated", "high") or aic_sg
        if (flagged or is_aic_concern) and not has_override:
            flag_lbl = QLabel("NEEDS REVIEW")
            badge_color = ROSE_ACCENT if (is_aic_concern and not flagged) else "#E0802A"
            flag_lbl.setStyleSheet(
                f"color: {badge_color}; font-size: 9px; font-weight: bold;"
                f" background: rgba(224,128,42,0.12); border: 1px solid rgba(224,128,42,0.3);"
                f" border-radius: 2px; padding: 1px 4px;"
            )
            rl.addWidget(flag_lbl)
        elif has_override:
            check_lbl = QLabel("✓")
            check_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: 11px; background: transparent;"
            )
            check_lbl.setToolTip("Teacher reviewed")
            rl.addWidget(check_lbl)

        # Grade badge
        badge = GradeBadge(grade)
        rl.addWidget(badge)

        # Word count
        wc_lbl = QLabel(f"{wc}w" if wc else "—")
        wc_lbl.setFixedWidth(40)
        wc_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        wc_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;")
        rl.addWidget(wc_lbl)

        row.mousePressEvent = lambda e, student=s: self._on_student_clicked(student)
        return row

    def _on_student_clicked(self, student: Dict) -> None:
        self._selected_id = str(student.get("student_id", ""))
        self._rebuild_list()
        self.student_selected.emit(student)

    def _update_summary(self) -> None:
        total = len(self._students)
        comp = sum(1 for s in self._students if s.get("grade", "").lower() == "complete")
        inc = sum(1 for s in self._students if s.get("grade", "").lower() == "incomplete")
        skip = sum(1 for s in self._students if s.get("was_skipped"))
        self._summary_lbl.setText(
            f"{comp} comp · {inc} inc" + (f" · {skip} skip" if skip else "")
        )

        # Review progress
        flagged = [s for s in self._students if s.get("is_flagged")]
        reviewed = [s for s in flagged if s.get("teacher_override") is not None]
        if flagged:
            self._review_progress.setText(
                f"Reviewed {len(reviewed)}/{len(flagged)} flagged"
            )
        else:
            self._review_progress.setText("")

    def select_next_flagged(self, direction: int = 1) -> None:
        """Select the next (or previous) unreviewed flagged student."""
        flagged = [s for s in self._filtered
                   if s.get("is_flagged") and s.get("teacher_override") is None]
        if not flagged:
            return
        current_idx = -1
        for i, s in enumerate(flagged):
            if str(s.get("student_id", "")) == self._selected_id:
                current_idx = i
                break
        next_idx = (current_idx + direction) % len(flagged)
        self._on_student_clicked(flagged[next_idx])

    def select_next_flagged_after(self, student_id: str) -> None:
        """After triaging student_id, advance to the next unreviewed flagged student."""
        flagged = [s for s in self._filtered
                   if s.get("is_flagged") and s.get("teacher_override") is None]
        if not flagged:
            return
        # Find the student's position in full _filtered list to preserve ordering
        prev_idx = -1
        for i, s in enumerate(self._filtered):
            if str(s.get("student_id", "")) == student_id:
                prev_idx = i
                break
        # Pick the next flagged student that comes after prev_idx
        for s in flagged:
            idx = self._filtered.index(s) if s in self._filtered else -1
            if idx > prev_idx:
                self._on_student_clicked(s)
                return
        # Wrap: pick first flagged student
        self._on_student_clicked(flagged[0])

    def flash_result(self, success: bool, message: str = "") -> None:
        """Briefly show a triage result notification bar."""
        if self._flash_timer and self._flash_timer.isActive():
            self._flash_timer.stop()
        color = TERM_GREEN if success else BURN_RED
        bg = "rgba(114,184,90,0.12)" if success else "rgba(220,80,80,0.12)"
        text = message or ("✓ Saved" if success else "✗ Failed")
        self._flash_bar.setText(text)
        self._flash_bar.setStyleSheet(
            f"color: {color}; font-size: 11px; font-weight: bold;"
            f" background: {bg}; border-bottom: 1px solid {color}40;"
        )
        self._flash_bar.setVisible(True)
        self._flash_timer = QTimer(self)
        self._flash_timer.setSingleShot(True)
        self._flash_timer.timeout.connect(self._hide_flash)
        self._flash_timer.start(2500)

    def _hide_flash(self) -> None:
        self._flash_bar.setVisible(False)

    def keyPressEvent(self, event) -> None:
        """Up/Down arrows navigate the student list; Enter re-emits selection."""
        key = event.key()
        if not self._filtered:
            super().keyPressEvent(event)
            return
        if key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
            # Find current position
            cur = -1
            for i, s in enumerate(self._filtered):
                if str(s.get("student_id", "")) == self._selected_id:
                    cur = i
                    break
            if key == Qt.Key.Key_Down:
                nxt = min(cur + 1, len(self._filtered) - 1) if cur >= 0 else 0
            else:
                nxt = max(cur - 1, 0) if cur >= 0 else 0
            self._on_student_clicked(self._filtered[nxt])
        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            for s in self._filtered:
                if str(s.get("student_id", "")) == self._selected_id:
                    self.student_selected.emit(s)
                    break
        else:
            super().keyPressEvent(event)


# ──────────────────────────────────────────────────────────────────────────────
# Right column: Student detail
# ──────────────────────────────────────────────────────────────────────────────

class _StudentDetail(QFrame):
    """Right column: grade card, AIC card, submission viewer, triage actions."""

    override_requested = Signal(str, str, str, str)  # student_id, assignment_id, grade, reason
    view_aic_detail = Signal(str, str)  # student_id, assignment_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._student: Dict = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_VOID}; border: none; }}
            QScrollArea > QWidget > QWidget {{ background: {BG_VOID}; }}
        """)
        self._content = QWidget()
        self._content.setStyleSheet(f"background: {BG_VOID};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        self._content_layout.setSpacing(SPACING_SM)
        scroll.setWidget(self._content)
        layout.addWidget(scroll, 1)

        # Empty state
        self._empty_label = QLabel("Select a student to view details")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 13px; background: transparent;"
        )
        self._content_layout.addStretch()
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()

    def load(self, student: Dict) -> None:
        self._student = student
        self._rebuild()

    def clear(self) -> None:
        self._student = {}
        self._clear_content()
        self._empty_label = QLabel("Select a student to view details")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 13px; background: transparent;"
        )
        self._content_layout.addStretch()
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _rebuild(self) -> None:
        s = self._student
        if not s:
            return

        self._clear_content()

        name = s.get("student_name", "Unknown")
        grade = s.get("grade", "")
        reason = s.get("reason", "")
        wc = s.get("word_count", 0)
        flags = s.get("flags", [])
        if isinstance(flags, str):
            try:
                flags = json.loads(flags)
            except (json.JSONDecodeError, TypeError):
                flags = [flags] if flags else []
        sub_type = s.get("submission_type", "")
        sub_body = s.get("submission_body", "")
        attachments = s.get("attachment_meta", [])
        if isinstance(attachments, str):
            try:
                attachments = json.loads(attachments)
            except (json.JSONDecodeError, TypeError):
                attachments = []
        grading_tool = s.get("grading_tool", "ci")
        override = s.get("teacher_override")
        is_flagged = s.get("is_flagged", 0)

        # AIC data (from LEFT JOIN)
        aic_concern = s.get("aic_concern_level")
        aic_score = s.get("aic_suspicious_score")
        aic_human = s.get("aic_human_presence_confidence")
        aic_sg = s.get("aic_smoking_gun")

        # ── Cards row (Grade + AIC side by side) ───────────────────────────
        cards_row = QHBoxLayout()
        cards_row.setSpacing(SPACING_SM)

        # Grade card
        grade_card = _make_card("gradeCard")
        gc_layout = QVBoxLayout(grade_card)
        gc_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        gc_layout.setSpacing(4)

        gc_header = QLabel("GRADE")
        gc_header.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1.5px; background: transparent;"
        )
        gc_layout.addWidget(gc_header)

        display_grade = override if override else grade
        is_comp = display_grade.lower() in ("complete", "comp") if display_grade else False
        grade_color = TERM_GREEN if is_comp else "#E0802A"
        grade_text = display_grade.upper() if display_grade else "—"

        gc_grade = QLabel(grade_text)
        gc_grade.setStyleSheet(
            f"color: {grade_color}; font-size: 16px; font-weight: bold; background: transparent;"
        )
        gc_layout.addWidget(gc_grade)

        if override and override != grade:
            orig = QLabel(f"Original: {grade}")
            orig.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
            )
            gc_layout.addWidget(orig)

        gc_reason = QLabel(reason)
        gc_reason.setWordWrap(True)
        gc_reason.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 11px; background: transparent;"
        )
        gc_layout.addWidget(gc_reason)

        gc_meta = QLabel(f"{wc} words · {sub_type or 'unknown'} · {grading_tool.upper()}")
        gc_meta.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
        )
        gc_layout.addWidget(gc_meta)

        # DF-specific fields
        if grading_tool == "df":
            post_count = s.get("post_count")
            reply_count = s.get("reply_count")
            avg_words = s.get("avg_words_per_post")
            if post_count is not None:
                df_lbl = QLabel(
                    f"Posts: {post_count} · Replies: {reply_count or 0}"
                    f" · Avg words/post: {avg_words:.0f}" if avg_words else ""
                )
                df_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;"
                )
                gc_layout.addWidget(df_lbl)

        # Flags
        if flags:
            gc_layout.addWidget(make_h_rule())
            for flag_text in flags:
                fl = QLabel(f"⚠ {flag_text}")
                fl.setWordWrap(True)
                fl.setStyleSheet(
                    f"color: #E0802A; font-size: 11px; background: transparent;"
                )
                gc_layout.addWidget(fl)

        cards_row.addWidget(grade_card, 1)

        # AIC card (only if AIC data exists)
        if aic_concern and aic_concern != "none":
            aic_card = _make_card("aicCard")
            ac_layout = QVBoxLayout(aic_card)
            ac_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
            ac_layout.setSpacing(4)

            ac_header = QLabel("AIC")
            ac_header.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
                f" letter-spacing: 1.5px; background: transparent;"
            )
            ac_layout.addWidget(ac_header)

            concern_color = CONCERN_COLOR.get(aic_concern, PHOSPHOR_DIM)
            concern_label = CONCERN_LABEL.get(aic_concern, aic_concern)
            pip_row = QHBoxLayout()
            pip = AICPipWidget(aic_concern, bool(aic_sg))
            pip_row.addWidget(pip)
            cl_lbl = QLabel(concern_label)
            cl_lbl.setStyleSheet(
                f"color: {concern_color}; font-size: 13px; font-weight: bold;"
                f" background: transparent;"
            )
            pip_row.addWidget(cl_lbl)
            pip_row.addStretch()
            ac_layout.addLayout(pip_row)

            if aic_score is not None:
                score_lbl = QLabel(f"Suspicion: {aic_score:.2f}")
                score_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 11px; background: transparent;"
                )
                ac_layout.addWidget(score_lbl)

            if aic_human is not None:
                human_lbl = QLabel(f"Human presence: {aic_human:.0%}")
                human_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 11px; background: transparent;"
                )
                ac_layout.addWidget(human_lbl)

            if aic_sg:
                sg_lbl = QLabel("SMOKING GUN DETECTED")
                sg_lbl.setStyleSheet(
                    f"color: {ROSE_ACCENT}; font-size: 10px; font-weight: bold;"
                    f" background: transparent;"
                )
                ac_layout.addWidget(sg_lbl)

            # Link to full AIC detail
            aic_link = QPushButton("View Full AIC Detail →")
            aic_link.setCursor(Qt.CursorShape.PointingHandCursor)
            aic_link.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {ROSE_ACCENT}; font-size: 11px; text-align: left;
                    padding: 2px 0;
                }}
                QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
            """)
            sid = str(s.get("student_id", ""))
            aid = str(s.get("assignment_id", ""))
            aic_link.clicked.connect(lambda _, si=sid, ai=aid: self.view_aic_detail.emit(si, ai))
            ac_layout.addWidget(aic_link)

            cards_row.addWidget(aic_card, 1)

        self._content_layout.addLayout(cards_row)

        # ── Student Work viewer ────────────────────────────────────────────
        work_header, work_content, _ = _collapsible_header("Student Work", True)
        self._content_layout.addWidget(work_header)

        work_layout = QVBoxLayout(work_content)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(4)

        if sub_body:
            viewer = QTextBrowser()
            viewer.setOpenExternalLinks(True)
            viewer.setStyleSheet(f"""
                QTextBrowser {{
                    background: {BG_INSET};
                    color: {PHOSPHOR_MID};
                    border: 1px solid {BORDER_DARK};
                    border-radius: 4px;
                    padding: 8px;
                    font-size: 12px;
                }}
            """)
            viewer.setMinimumHeight(450)
            viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            viewer.setHtml(sub_body)
            work_layout.addWidget(viewer, 1)
        elif attachments:
            for att in attachments:
                att_lbl = QLabel(
                    f"📎 {att.get('filename', 'file')}  "
                    f"({_fmt_size(att.get('size', 0))})"
                )
                att_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 12px; background: transparent;"
                    f" padding: 4px 0;"
                )
                work_layout.addWidget(att_lbl)
        else:
            no_sub = QLabel("No submission content available")
            no_sub.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 12px; background: transparent;"
                f" padding: 12px 0;"
            )
            no_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            work_layout.addWidget(no_sub)

        self._content_layout.addWidget(work_content, 1)  # stretch to fill

        # ── Triage actions (for flagged students) ──────────────────────────
        if is_flagged and not override:
            triage_card = _make_card("triageCard")
            triage_card.setStyleSheet(f"""
                QFrame#triageCard {{
                    background: {CARD_GRADIENT};
                    border: 1px solid #E0802A;
                    border-radius: 6px;
                }}
            """)
            tl = QVBoxLayout(triage_card)
            tl.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
            tl.setSpacing(SPACING_SM)

            triage_hdr = QLabel("TRIAGE")
            triage_hdr.setStyleSheet(
                f"color: #E0802A; font-size: 10px; font-weight: bold;"
                f" letter-spacing: 1.5px; background: transparent;"
            )
            tl.addWidget(triage_hdr)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(SPACING_SM)

            complete_btn = QPushButton("✓ Mark Complete")
            complete_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(114,184,90,0.10); border: 1px solid {TERM_GREEN};
                    color: {TERM_GREEN}; font-size: 12px; padding: 6px 14px;
                    border-radius: 4px; font-weight: bold;
                }}
                QPushButton:hover {{ background: rgba(114,184,90,0.20); }}
            """)
            sid = str(s.get("student_id", ""))
            aid = str(s.get("assignment_id", ""))
            complete_btn.clicked.connect(
                lambda _, si=sid, ai=aid: self.override_requested.emit(
                    si, ai, "complete", "Teacher override: marked complete after review"
                )
            )
            btn_row.addWidget(complete_btn)

            keep_btn = QPushButton("✗ Keep Incomplete")
            keep_btn.setStyleSheet(f"""
                QPushButton {{
                    background: rgba(224,128,42,0.10); border: 1px solid #E0802A;
                    color: #E0802A; font-size: 12px; padding: 6px 14px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ background: rgba(224,128,42,0.20); }}
            """)
            keep_btn.clicked.connect(
                lambda _, si=sid, ai=aid: self.override_requested.emit(
                    si, ai, "incomplete", "Teacher confirmed: keep incomplete"
                )
            )
            btn_row.addWidget(keep_btn)

            skip_btn = QPushButton("⊘ Skip")
            skip_btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: 1px solid {BORDER_DARK};
                    color: {PHOSPHOR_DIM}; font-size: 12px; padding: 6px 14px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}
            """)
            btn_row.addWidget(skip_btn)

            tl.addLayout(btn_row)
            self._content_layout.addWidget(triage_card)

        self._content_layout.addStretch()


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


# ──────────────────────────────────────────────────────────────────────────────
# Main panel: 3-column master-detail
# ──────────────────────────────────────────────────────────────────────────────

class GradingResultsPanel(QFrame):
    """Three-column grading results review panel.

    Signals
    -------
    view_aic_detail(str, str)
        Emitted when user clicks "View Full AIC Detail →" — (student_id, assignment_id).
        Parent should switch ViewToggle to AIC mode and drill into that student.
    """

    view_aic_detail = Signal(str, str)

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._store = None
        self._current_course_id = ""
        self._current_assignment_id = ""
        self._filter_course_id = ""   # course selected in Course Select — used for auto-select
        self._worker = None
        self._active_workers: list = []
        self._advance_after_id: str = ""   # student_id to advance past after triage save

        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._build_ui()
        self._connect_signals()

    def _get_store(self):
        if self._store is None:
            from automation.run_store import RunStore
            self._store = RunStore()
        return self._store

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 3-column splitter
        self._splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(10)

        self._sidebar = _GradingSidebar()
        self._student_list = _StudentList()
        self._student_detail = _StudentDetail()

        self._splitter.addWidget(self._sidebar)
        self._splitter.addWidget(self._student_list)
        self._splitter.addWidget(self._student_detail)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 0)
        self._splitter.setStretchFactor(2, 1)
        self._splitter.setSizes([220, 380, 500])

        self._sidebar.setMinimumWidth(180)
        self._student_list.setMinimumWidth(280)

        layout.addWidget(self._splitter, 1)

    def _connect_signals(self) -> None:
        self._sidebar.assignment_selected.connect(self._on_assignment_selected)
        self._sidebar.refresh_requested.connect(self.refresh)
        self._student_list.student_selected.connect(self._on_student_selected)
        self._student_list.export_requested.connect(self._on_export)
        self._student_list.prev_flagged.connect(lambda: self._student_list.select_next_flagged(-1))
        self._student_list.next_flagged.connect(lambda: self._student_list.select_next_flagged(1))
        self._student_detail.override_requested.connect(self._on_override)
        self._student_detail.view_aic_detail.connect(self.view_aic_detail)

    # ── Public API ────────────────────────────────────────────────────────

    def set_course(self, course_id: str, course_name: str) -> None:
        """Called when the user selects a course in Course Select.

        Stores the course context; the sidebar will auto-select the first
        assignment for that course next time assignments load.
        """
        self._filter_course_id = str(course_id)

    def refresh(self) -> None:
        """Reload assignment tree from SQLite."""
        from gui.workers import LoadGradingAssignmentsWorker
        store = self._get_store()
        w = LoadGradingAssignmentsWorker(store)
        w.assignments_loaded.connect(self._on_assignments_loaded)
        w.error.connect(lambda msg: print(f"LoadGradingAssignments error: {msg}"))
        w.start()
        self._track_worker(w)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.refresh()

    # ── Slots ─────────────────────────────────────────────────────────────

    def _on_assignments_loaded(self, assignments: List[Dict]) -> None:
        self._sidebar.populate(assignments)
        if not assignments:
            self._student_list.set_assignment(
                "No grading runs yet",
                "Run the autograder to see results here."
            )
            return
        if self._filter_course_id:
            self._sidebar.select_first_for_course(self._filter_course_id)

    def _on_assignment_selected(self, cid: str, aid: str, cname: str, aname: str) -> None:
        self._current_course_id = cid
        self._current_assignment_id = aid
        self._student_detail.clear()

        from gui.workers import LoadGradingCohortWorker
        store = self._get_store()
        w = LoadGradingCohortWorker(store, cid, aid)
        w.cohort_loaded.connect(self._on_cohort_loaded)
        w.error.connect(lambda msg: print(f"LoadGradingCohort error: {msg}"))
        w.start()
        self._track_worker(w)

        self._student_list.set_assignment(aname, f"Loading students...")

    def _on_cohort_loaded(self, students: List[Dict]) -> None:
        total = len(students)
        comp = sum(1 for s in students if s.get("grade", "").lower() == "complete")
        inc = total - comp
        self._student_list.set_assignment(
            self._student_list._assignment_name,
            f"{total} students · {comp} complete · {inc} incomplete"
        )
        self._student_list.populate(students)
        # Auto-advance to next unreviewed flagged student after triage save
        if self._advance_after_id:
            self._student_list.select_next_flagged_after(self._advance_after_id)
            self._advance_after_id = ""

    def _on_override(self, student_id: str, assignment_id: str,
                     grade: str, reason: str) -> None:
        from gui.workers import SaveTeacherOverrideWorker
        store = self._get_store()
        w = SaveTeacherOverrideWorker(
            store, self._api,
            self._current_course_id, assignment_id,
            student_id, grade, reason,
        )
        w.override_saved.connect(
            lambda ok, msg: self._on_override_saved(ok, msg, student_id)
        )
        w.start()
        self._track_worker(w)

    def _on_override_saved(self, ok: bool, msg: str, student_id: str) -> None:
        if ok:
            self._student_list.flash_result(True, "✓ Saved — advancing to next")
            self._advance_after_id = student_id
            # Reload cohort to reflect the override
            self._on_assignment_selected(
                self._current_course_id,
                self._current_assignment_id,
                "", self._student_list._assignment_name,
            )
        else:
            self._student_list.flash_result(False, f"✗ {msg or 'Save failed'}")
            print(f"Override failed: {msg}")

    def _on_export(self) -> None:
        if not self._current_course_id or not self._current_assignment_id:
            return

        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Grading Results",
            f"grading_results_{self._current_assignment_id}.xlsx",
            "Excel Files (*.xlsx)",
        )
        if not path:
            return

        from gui.workers import ExportXLSXWorker
        store = self._get_store()
        w = ExportXLSXWorker(store, self._current_course_id,
                             self._current_assignment_id, path)
        w.export_done.connect(self._on_export_done)
        w.start()
        self._track_worker(w)

    def _on_export_done(self, ok: bool, path_or_error: str) -> None:
        if ok:
            import subprocess, sys
            # Open containing folder
            from pathlib import Path
            folder = str(Path(path_or_error).parent)
            if sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", folder])
            else:
                subprocess.Popen(["xdg-open", folder])

    def _track_worker(self, w) -> None:
        self._active_workers.append(w)
        w.finished.connect(lambda: self._active_workers.remove(w)
                           if w in self._active_workers else None)

    def _on_student_selected(self, student: Dict) -> None:
        self._student_detail.load(student)
