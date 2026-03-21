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
import os
import tempfile
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QSizePolicy, QComboBox, QLineEdit,
    QTextBrowser, QStackedWidget, QTextEdit, QSlider, QMenu,
)
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QThread, QUrl
from PySide6.QtGui import (
    QColor, QPainter, QPen, QFont, QFontMetrics,
    QRadialGradient, QPainterPath, QPixmap, QDesktopServices, QAction,
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from gui.styles import (
    px,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, ROSE_DIM, WARN_PINK, TERM_GREEN, BURN_RED, AMBER_BTN,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    CARD_GRADIENT, PANEL_GRADIENT,
    make_secondary_button, make_run_button, GripSplitter,
    make_section_label, make_h_rule, make_content_pane,
    combo_qss,
)
from gui.aic_palette import CONCERN_COLOR, CONCERN_LABEL
from gui.widgets.crt_combo import CRTComboBox
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

_FILTER_COMBO_QSS = combo_qss()

_SEARCH_QSS = f"""
    QLineEdit {{
        background: {BG_INSET};
        color: {PHOSPHOR_HOT};
        border: 1px solid {BORDER_DARK};
        border-radius: 4px;
        padding: 4px 8px;
        font-size: {px(11)}px;
    }}
    QLineEdit:focus {{ border-color: {PHOSPHOR_HOT}; }}
"""

_ASSIGNMENT_ROW_QSS = f"""
    QFrame {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        padding: 2px 0;
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.15,cy:0.5,radius:1.20,
            stop:0.00 #231A06,stop:0.70 #191406,stop:1.00 #141003);
    }}
"""

_ASSIGNMENT_ROW_SEL_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.15,cy:0.5,radius:1.30,
            stop:0.00 #3A2408,stop:0.65 #2C1C08,stop:1.00 #1A1205);
        border: none;
        border-left: 3px solid {ROSE_ACCENT};
    }}
"""

_STUDENT_ROW_QSS = """
    QFrame {
        background: transparent;
        border: none;
    }
    QFrame:hover {
        background: qradialgradient(cx:0.20,cy:0.5,radius:0.85,
            stop:0.0 rgba(240,168,48,45),stop:0.6 rgba(240,168,48,15),stop:1.0 transparent);
    }
"""

_STUDENT_ROW_SEL_QSS = """
    QFrame {
        background: qradialgradient(cx:0.20,cy:0.5,radius:0.85,
            stop:0.0 rgba(204,82,130,65),stop:0.6 rgba(204,82,130,15),stop:1.0 transparent);
        border: none;
    }
"""

_STUDENT_ROW_FLAGGED_QSS = """
    QFrame {
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(224,128,42,0.14),stop:0.45 rgba(224,128,42,0.04),stop:1.0 transparent);
        border: none;
    }
    QFrame:hover {
        background: qradialgradient(cx:0.20,cy:0.5,radius:0.85,
            stop:0.0 rgba(240,168,48,45),stop:0.6 rgba(240,168,48,15),stop:1.0 transparent);
    }
"""

_STUDENT_ROW_AIC_QSS = """
    QFrame {
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(120,180,220,0.12),stop:0.45 rgba(120,180,220,0.03),stop:1.0 transparent);
        border: none;
    }
    QFrame:hover {
        background: qradialgradient(cx:0.20,cy:0.5,radius:0.85,
            stop:0.0 rgba(240,168,48,45),stop:0.6 rgba(240,168,48,15),stop:1.0 transparent);
    }
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
            # Glow ring (baby blue — AIC system colour)
            glow = QRadialGradient(cx, cy, 7)
            glow.setColorAt(0.0, QColor(120, 180, 220))
            glow.setColorAt(0.5, QColor(120, 180, 220, 120))
            glow.setColorAt(1.0, QColor(120, 180, 220, 0))
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
    arrow_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;")
    hl.addWidget(arrow_lbl)
    title_lbl = QLabel(text.upper())
    title_lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
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
        self._filter_combo = CRTComboBox()
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
                color: {PHOSPHOR_DIM}; font-size: {px(14)}px;
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
            arrow.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;")
            hl.addWidget(arrow)

            name_lbl = QLabel(data["name"].upper())
            name_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
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
            indicator.setStyleSheet(f"color: {WARN_PINK}; font-size: {px(11)}px; background: transparent;")
        elif has_grading_flag:
            indicator = QLabel("⚠")
            indicator.setStyleSheet(f"color: #E0802A; font-size: {px(11)}px; background: transparent;")
        elif has_aic_concern:
            indicator = QLabel("●")
            indicator.setStyleSheet(f"color: {ROSE_ACCENT}; font-size: {px(11)}px; background: transparent;")
        else:
            indicator = QLabel("✓")
            indicator.setStyleSheet(f"color: {TERM_GREEN}; font-size: {px(11)}px; background: transparent; opacity: 0.6;")
        indicator.setFixedWidth(20)
        rl.addWidget(indicator)

        # Assignment name
        name_lbl = QLabel(aname)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT if is_selected else PHOSPHOR_MID};"
            f" font-size: {px(12)}px; background: transparent;"
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
            f"color: {color}; font-size: {px(10)}px; background: transparent;"
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
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" background: transparent;"
        )
        top_row.addWidget(self._title_lbl, 1)

        self._export_btn = QPushButton("Export XLSX")
        self._export_btn.setFixedHeight(24)
        self._export_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: 1px solid {BORDER_DARK};
                color: {PHOSPHOR_DIM}; font-size: {px(10)}px; padding: 2px 10px;
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
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        hl.addWidget(self._subtitle_lbl)

        # AIC aggregate banner (hidden by default)
        self._aic_banner = QLabel("")
        self._aic_banner.setWordWrap(True)
        self._aic_banner.setStyleSheet(
            f"color: #78B4DC; font-size: {px(10)}px; background: transparent;"
            f" border: none; padding: 3px 0px;"
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

        self._sort_combo = CRTComboBox()
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
            f"font-size: {px(11)}px; font-weight: bold; background: transparent; border: none;"
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

        # Summary label (inline at bottom of scroll area)
        self._summary_lbl = QLabel("")
        self._review_progress = QLabel("")

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
            # Show everyone who is NOT complete (includes incomplete, ungraded, no submission)
            filtered = [s for s in filtered if s.get("grade", "").lower() != "complete"]
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

        # Name — dim by default, bright only when needs attention
        name_lbl = QLabel(name)
        is_aic_concern = aic_concern in ("elevated", "high") or aic_sg
        needs_attention = flagged or is_aic_concern
        if is_selected:
            name_color = PHOSPHOR_HOT
        elif needs_attention and not has_override:
            name_color = PHOSPHOR_MID
        else:
            name_color = PHOSPHOR_DIM
        name_lbl.setStyleSheet(f"color: {name_color}; font-size: {px(12)}px; background: transparent;")
        rl.addWidget(name_lbl, 1)

        # Flagged / needs review badge
        # Show for: grading flags on a real submission, OR elevated+ AIC concern
        if (flagged or is_aic_concern) and not has_override:
            flag_lbl = QLabel("NEEDS REVIEW")
            if is_aic_concern and not flagged:
                # AIC-only: baby blue
                badge_color = "#78B4DC"
                bg_rgba = "rgba(120,180,220,0.12)"
                border_rgba = "rgba(120,180,220,0.3)"
            else:
                # Grading flags: amber
                badge_color = "#E0802A"
                bg_rgba = "rgba(224,128,42,0.12)"
                border_rgba = "rgba(224,128,42,0.3)"
            flag_lbl.setStyleSheet(
                f"color: {badge_color}; font-size: {px(9)}px; font-weight: bold;"
                f" background: {bg_rgba}; border: 1px solid {border_rgba};"
                f" border-radius: 2px; padding: 1px 4px;"
            )
            rl.addWidget(flag_lbl)
        elif has_override:
            check_lbl = QLabel("✓")
            check_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(11)}px; background: transparent;"
            )
            check_lbl.setToolTip("Teacher reviewed")
            rl.addWidget(check_lbl)

        # Grade badge
        reason = s.get("reason", "")
        badge = GradeBadge(grade)
        if grade.lower() != "complete" and reason:
            badge.setToolTip(reason)
        rl.addWidget(badge)

        # Reason hint for non-complete students (compact, elided)
        if grade.lower() != "complete" and reason and reason not in ("Incomplete submission", "Meets requirements"):
            reason_lbl = QLabel(reason)
            reason_lbl.setMaximumWidth(160)
            reason_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
                f" background: transparent;"
            )
            reason_lbl.setToolTip(reason)
            from PySide6.QtWidgets import QSizePolicy as _SP
            reason_lbl.setSizePolicy(_SP.Policy.Preferred, _SP.Policy.Fixed)
            rl.addWidget(reason_lbl)

        # Word count
        wc_lbl = QLabel(f"{wc}w" if wc else "—")
        wc_lbl.setFixedWidth(40)
        wc_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        wc_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;")
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
        not_comp = total - comp
        self._summary_lbl.setText(
            f"{comp} comp · {not_comp} inc"
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
            f"color: {color}; font-size: {px(11)}px; font-weight: bold;"
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
# Attachment display helpers
# ──────────────────────────────────────────────────────────────────────────────

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".heif", ".tiff"}
_AUDIO_EXTS = {".mp3", ".m4a", ".wav", ".ogg", ".aac", ".flac", ".opus", ".weba"}
_VIDEO_EXTS = {".mp4", ".mov", ".webm", ".mkv", ".avi"}


def _att_ext(att: Dict) -> str:
    return Path(att.get("filename", "")).suffix.lower()


def _is_image(att: Dict) -> bool:
    ct = att.get("content_type", "")
    return ct.startswith("image/") or _att_ext(att) in _IMAGE_EXTS


def _is_audio(att: Dict) -> bool:
    ct = att.get("content_type", "")
    return (
        ct.startswith("audio/") or ct.startswith("video/")
        or _att_ext(att) in _AUDIO_EXTS
        or _att_ext(att) in _VIDEO_EXTS
    )


class _DownloadThread(QThread):
    """Download a URL to a temp file, emit the path when done."""
    finished_path = Signal(str)   # temp file path
    failed = Signal(str)          # error message

    def __init__(self, url: str, headers: dict, suffix: str = "", parent=None):
        super().__init__(parent)
        self._url = url
        self._headers = headers
        self._suffix = suffix

    def run(self):
        try:
            req = urllib.request.Request(self._url, headers=self._headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read()
            fd, path = tempfile.mkstemp(suffix=self._suffix)
            os.write(fd, data)
            os.close(fd)
            self.finished_path.emit(path)
        except Exception as e:
            self.failed.emit(str(e))


class _ImageAttachmentWidget(QFrame):
    """Shows a Canvas image attachment inline with async download."""

    def __init__(self, att: Dict, api=None, parent=None):
        super().__init__(parent)
        self._att = att
        self._api = api
        self._tmp_path: Optional[str] = None
        self._thread: Optional[_DownloadThread] = None

        self.setStyleSheet(
            f"QFrame {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; }}"
        )

        vl = QVBoxLayout(self)
        vl.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        vl.setSpacing(4)

        name_lbl = QLabel(f"🖼  {att.get('filename', 'image')}")
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; background: transparent;"
        )
        vl.addWidget(name_lbl)

        self._img_lbl = QLabel("Loading…")
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        self._img_lbl.setMinimumHeight(120)
        vl.addWidget(self._img_lbl)

        url = att.get("url", "")
        if url:
            headers = (api.headers if api else {})
            ext = _att_ext(att) or ".png"
            self._thread = _DownloadThread(url, headers, suffix=ext, parent=self)
            self._thread.finished_path.connect(self._on_downloaded)
            self._thread.failed.connect(self._on_error)
            self._thread.start()
        else:
            self._img_lbl.setText("(no URL available)")

    def _on_downloaded(self, path: str):
        self._tmp_path = path
        px_map = QPixmap(path)
        if px_map.isNull():
            self._img_lbl.setText("(could not render image)")
            return
        max_w = 480
        if px_map.width() > max_w:
            px_map = px_map.scaledToWidth(max_w, Qt.TransformationMode.SmoothTransformation)
        self._img_lbl.setPixmap(px_map)
        self._img_lbl.setFixedHeight(px_map.height())

    def _on_error(self, msg: str):
        self._img_lbl.setText(f"(download failed: {msg})")

    def closeEvent(self, event):
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.unlink(self._tmp_path)
            except OSError:
                pass
        super().closeEvent(event)


class _AudioAttachmentWidget(QFrame):
    """Play/pause control for a Canvas audio or video attachment."""

    def __init__(self, att: Dict, api=None, parent=None):
        super().__init__(parent)
        self._att = att
        self._api = api
        self._tmp_path: Optional[str] = None
        self._thread: Optional[_DownloadThread] = None

        self.setStyleSheet(
            f"QFrame {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; }}"
        )

        hl = QHBoxLayout(self)
        hl.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        hl.setSpacing(SPACING_SM)

        self._play_btn = QPushButton("▶  Load")
        self._play_btn.setFixedWidth(90)
        self._play_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(180,130,60,0.15); border: 1px solid {BORDER_AMBER};
                color: {PHOSPHOR_MID}; font-size: {px(11)}px; padding: 4px 8px;
                border-radius: 3px;
            }}
            QPushButton:hover {{ background: rgba(180,130,60,0.30); color: {PHOSPHOR_HOT}; }}
        """)
        hl.addWidget(self._play_btn)

        name_lbl = QLabel(f"🎵  {att.get('filename', 'audio')}")
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; background: transparent;"
        )
        hl.addWidget(name_lbl, 1)

        self._status_lbl = QLabel(f"({_fmt_size(att.get('size', 0))})")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        hl.addWidget(self._status_lbl)

        # Media player (lazy-init)
        self._player: Optional[QMediaPlayer] = None
        self._audio_out: Optional[QAudioOutput] = None
        self._loaded = False

        self._play_btn.clicked.connect(self._on_play_clicked)

    def _on_play_clicked(self):
        if not self._loaded:
            self._status_lbl.setText("Downloading…")
            self._play_btn.setEnabled(False)
            url = self._att.get("url", "")
            if not url:
                self._status_lbl.setText("(no URL)")
                self._play_btn.setEnabled(True)
                return
            headers = (self._api.headers if self._api else {})
            ext = _att_ext(self._att) or ".mp3"
            self._thread = _DownloadThread(url, headers, suffix=ext, parent=self)
            self._thread.finished_path.connect(self._on_downloaded)
            self._thread.failed.connect(self._on_error)
            self._thread.start()
        elif self._player:
            if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
                self._player.pause()
                self._play_btn.setText("▶  Play")
            else:
                self._player.play()
                self._play_btn.setText("⏸  Pause")

    def _on_downloaded(self, path: str):
        self._tmp_path = path
        self._loaded = True
        self._audio_out = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_out)
        self._player.setSource(QUrl.fromLocalFile(path))
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.play()
        self._play_btn.setText("⏸  Pause")
        self._play_btn.setEnabled(True)
        self._status_lbl.setText("Playing")

    def _on_error(self, msg: str):
        self._status_lbl.setText(f"Error: {msg}")
        self._play_btn.setEnabled(True)

    def _on_state_changed(self, state):
        if state == QMediaPlayer.PlaybackState.StoppedState:
            self._play_btn.setText("▶  Play")
            self._status_lbl.setText("Done")

    def closeEvent(self, event):
        if self._player:
            self._player.stop()
        if self._tmp_path and os.path.exists(self._tmp_path):
            try:
                os.unlink(self._tmp_path)
            except OSError:
                pass
        super().closeEvent(event)


# ──────────────────────────────────────────────────────────────────────────────

class _StudentDetail(QFrame):
    """Right column: grade card, AIC card, submission viewer, triage actions."""

    override_requested = Signal(str, str, str, str)  # student_id, assignment_id, grade, reason
    view_aic_detail = Signal(str, str)  # student_id, assignment_id
    post_comment_requested = Signal(str, str, str, str)  # course_id, assignment_id, student_id, text

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._student: Dict = {}
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
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
            f"color: {PHOSPHOR_DIM}; font-size: {px(13)}px; background: transparent;"
        )
        self._content_layout.addStretch()
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()

    def _show_context_menu(self, pos) -> None:
        s = self._student
        if not s:
            return
        base_url = (self._api.base_url.rstrip("/") if self._api and self._api.base_url else "")
        course_id = s.get("course_id", "")
        assignment_id = s.get("assignment_id", "")
        student_id = s.get("student_id", "")

        from gui.styles import menu_qss
        menu = QMenu(self)
        menu.setStyleSheet(menu_qss())

        if base_url and course_id and assignment_id and student_id:
            sg_url = (
                f"{base_url}/courses/{course_id}/gradebook/speed_grader"
                f"?assignment_id={assignment_id}&student_id={student_id}"
            )
            open_sg = QAction("Open in SpeedGrader ↗", self)
            open_sg.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(sg_url)))
            menu.addAction(open_sg)

            assign_url = f"{base_url}/courses/{course_id}/assignments/{assignment_id}"
            open_assign = QAction("Open Assignment Page ↗", self)
            open_assign.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(assign_url)))
            menu.addAction(open_assign)
        else:
            no_api = QAction("(Canvas URL not configured)", self)
            no_api.setEnabled(False)
            menu.addAction(no_api)

        menu.exec(self.mapToGlobal(pos))

    def load(self, student: Dict) -> None:
        self._student = student
        self._rebuild()

    def clear(self) -> None:
        self._student = {}
        self._clear_content()
        self._empty_label = QLabel("Select a student to view details")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(13)}px; background: transparent;"
        )
        self._content_layout.addStretch()
        self._content_layout.addWidget(self._empty_label)
        self._content_layout.addStretch()

    def _clear_content(self) -> None:
        def _delete_item(item):
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                lay = item.layout()
                while lay.count():
                    _delete_item(lay.takeAt(0))
                lay.deleteLater()

        while self._content_layout.count():
            _delete_item(self._content_layout.takeAt(0))

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

        # ── Cards column (Grade + AIC stacked) ─────────────────────────────
        cards_row = QVBoxLayout()
        cards_row.setSpacing(SPACING_SM)

        # Grade card
        grade_card = _make_card("gradeCard")
        gc_layout = QVBoxLayout(grade_card)
        gc_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        gc_layout.setSpacing(4)

        gc_header = QLabel("GRADE")
        gc_header.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
            f" letter-spacing: 1.5px; background: transparent;"
        )
        gc_layout.addWidget(gc_header)

        display_grade = override if override else grade
        is_comp = display_grade.lower() in ("complete", "comp") if display_grade else False
        grade_color = TERM_GREEN if is_comp else "#E0802A"
        grade_text = display_grade.upper() if display_grade else "—"

        gc_grade = QLabel(grade_text)
        gc_grade.setStyleSheet(
            f"color: {grade_color}; font-size: {px(16)}px; font-weight: bold; background: transparent;"
        )
        gc_layout.addWidget(gc_grade)

        if override and override != grade:
            orig = QLabel(f"Original: {grade}")
            orig.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
            )
            gc_layout.addWidget(orig)

        gc_reason = QLabel(reason)
        gc_reason.setWordWrap(True)
        gc_reason.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; background: transparent;"
        )
        gc_layout.addWidget(gc_reason)

        gc_meta = QLabel(f"{wc} words · {sub_type or 'unknown'} · {grading_tool.upper()}")
        gc_meta.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
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
                    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
                )
                gc_layout.addWidget(df_lbl)

        # Flags
        if flags:
            gc_layout.addWidget(make_h_rule())
            for flag_text in flags:
                fl = QLabel(f"⚠ {flag_text}")
                fl.setWordWrap(True)
                fl.setStyleSheet(
                    f"color: #E0802A; font-size: {px(11)}px; background: transparent;"
                )
                gc_layout.addWidget(fl)

        cards_row.addWidget(grade_card)

        # AIC card (only if AIC data exists)
        if aic_concern and aic_concern != "none":
            aic_card = _make_card("aicCard")
            ac_layout = QVBoxLayout(aic_card)
            ac_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
            ac_layout.setSpacing(4)

            # Header + concern level
            concern_color = CONCERN_COLOR.get(aic_concern, PHOSPHOR_DIM)
            concern_label = CONCERN_LABEL.get(aic_concern, aic_concern)
            ac_header = QLabel(f"AIC — {concern_label}")
            ac_header.setStyleSheet(
                f"color: {concern_color}; font-size: {px(11)}px; font-weight: bold;"
                f" background: transparent;"
            )
            ac_layout.addWidget(ac_header)

            # Smoking gun details
            if aic_sg:
                sg_details = s.get("aic_smoking_gun_details", [])
                if isinstance(sg_details, str):
                    try:
                        sg_details = json.loads(sg_details)
                    except (json.JSONDecodeError, TypeError):
                        sg_details = []
                sg_text = "; ".join(sg_details) if sg_details else "Chatbot artifacts detected"
                sg_lbl = QLabel(f"Smoking gun: {sg_text}")
                sg_lbl.setWordWrap(True)
                sg_lbl.setStyleSheet(
                    f"color: #90C8F0; font-size: {px(10)}px; background: transparent;"
                )
                ac_layout.addWidget(sg_lbl)

            # Marker-based reasons (the WHY)
            marker_counts = s.get("aic_marker_counts", {})
            if isinstance(marker_counts, str):
                try:
                    marker_counts = json.loads(marker_counts)
                except (json.JSONDecodeError, TypeError):
                    marker_counts = {}

            # Suspicious markers (higher count = more concern)
            _MARKER_LABELS = {
                "ai_transitions": "Formal transitions / academic phrasing",
                "generic_phrases": "Generic or vague language",
                "inflated_vocabulary": "Unusually formal vocabulary",
                "ai_specific_organization": "AI-style organizational patterns",
            }
            # Positive markers (presence = authenticity signals)
            _POSITIVE_LABELS = {
                "personal_voice": "Personal voice",
                "emotional_language": "Emotional language",
                "cognitive_diversity": "Cognitive diversity",
            }

            has_markers = False
            for mid, label in _MARKER_LABELS.items():
                count = marker_counts.get(mid, 0)
                if count > 0:
                    has_markers = True
                    m_lbl = QLabel(f"  ▸ {label} ({count})")
                    m_lbl.setStyleSheet(
                        f"color: #78B4DC; font-size: {px(10)}px; background: transparent;"
                    )
                    ac_layout.addWidget(m_lbl)

            # Show positive signals present (these are protective)
            has_positive = False
            for mid, label in _POSITIVE_LABELS.items():
                count = marker_counts.get(mid, 0)
                if count > 0:
                    has_positive = True
                    m_lbl = QLabel(f"  ✓ {label} ({count})")
                    m_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
                    )
                    ac_layout.addWidget(m_lbl)

            # Show absent positive signals only when suspicious markers exist
            if has_markers:
                for mid, label in _POSITIVE_LABELS.items():
                    count = marker_counts.get(mid, 0)
                    if count == 0:
                        m_lbl = QLabel(f"  ✗ No {label.lower()} detected")
                        m_lbl.setStyleSheet(
                            f"color: #5A7A90; font-size: {px(10)}px; background: transparent;"
                        )
                        ac_layout.addWidget(m_lbl)

            # Context adjustments (equity notes)
            ctx = s.get("aic_context_adjustments", [])
            if isinstance(ctx, str):
                try:
                    ctx = json.loads(ctx)
                except (json.JSONDecodeError, TypeError):
                    ctx = []
            if ctx:
                for note in ctx[:2]:
                    ctx_lbl = QLabel(f"  Note: {note}")
                    ctx_lbl.setWordWrap(True)
                    ctx_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                        f" font-style: italic; background: transparent;"
                    )
                    ac_layout.addWidget(ctx_lbl)

            # Link to full AIC detail
            aic_link = QPushButton("View Full AIC Detail →")
            aic_link.setCursor(Qt.CursorShape.PointingHandCursor)
            aic_link.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: #78B4DC; font-size: {px(11)}px; text-align: left;
                    padding: 2px 0;
                }}
                QPushButton:hover {{ color: #90C8F0; }}
            """)
            sid = str(s.get("student_id", ""))
            aid = str(s.get("assignment_id", ""))
            aic_link.clicked.connect(lambda _, si=sid, ai=aid: self.view_aic_detail.emit(si, ai))
            ac_layout.addWidget(aic_link)

            cards_row.addWidget(aic_card)

        self._content_layout.addLayout(cards_row)

        # ── Student Work viewer ────────────────────────────────────────────
        work_header, work_content, _ = _collapsible_header("Student Work", True)
        self._content_layout.addWidget(work_header)

        work_layout = QVBoxLayout(work_content)
        work_layout.setContentsMargins(0, 0, 0, 0)
        work_layout.setSpacing(4)

        has_content = False

        if sub_body:
            has_content = True
            viewer = QTextBrowser()
            viewer.setOpenExternalLinks(True)
            viewer.setStyleSheet(f"""
                QTextBrowser {{
                    background: {BG_INSET};
                    color: {PHOSPHOR_DIM};
                    border: 1px solid {BORDER_DARK};
                    border-radius: 4px;
                    padding: 10px;
                    font-size: {px(12)}px;
                }}
            """)
            viewer.document().setDefaultStyleSheet(
                f"body {{ line-height: 1.6; color: {PHOSPHOR_DIM}; }}"
            )
            viewer.setMinimumHeight(200)
            viewer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            viewer.setHtml(sub_body)
            work_layout.addWidget(viewer, 1)

        # Render each attachment by type (images inline, audio with player, others as link)
        for att in attachments:
            has_content = True
            if _is_image(att):
                img_w = _ImageAttachmentWidget(att, api=self._api)
                work_layout.addWidget(img_w)
            elif _is_audio(att):
                aud_w = _AudioAttachmentWidget(att, api=self._api)
                work_layout.addWidget(aud_w)
            else:
                # Generic file — show filename + open-in-browser button
                row = QHBoxLayout()
                row.setSpacing(SPACING_SM)
                att_lbl = QLabel(
                    f"📎  {att.get('filename', 'file')}  "
                    f"({_fmt_size(att.get('size', 0))})"
                )
                att_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(11)}px; background: transparent;"
                )
                row.addWidget(att_lbl, 1)
                url = att.get("url", "")
                if url:
                    open_btn = QPushButton("Open ↗")
                    open_btn.setStyleSheet(f"""
                        QPushButton {{
                            background: transparent; border: 1px solid {BORDER_DARK};
                            color: {PHOSPHOR_DIM}; font-size: {px(10)}px;
                            padding: 2px 8px; border-radius: 3px;
                        }}
                        QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}
                    """)
                    open_btn.clicked.connect(
                        lambda _, u=url: QDesktopServices.openUrl(QUrl(u))
                    )
                    row.addWidget(open_btn)
                row_w = QWidget()
                row_w.setStyleSheet("background: transparent;")
                row_w.setLayout(row)
                work_layout.addWidget(row_w)

        if not has_content:
            no_sub = QLabel("No submission content available")
            no_sub.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px; background: transparent;"
                f" padding: 12px 0;"
            )
            no_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
            work_layout.addWidget(no_sub)

        self._content_layout.addWidget(work_content, 1)  # stretch to fill

        sid = str(s.get("student_id", ""))
        aid = str(s.get("assignment_id", ""))
        cid = str(s.get("course_id", ""))

        # ── Comment composer (default expanded) ────────────────────────────
        comment_header, comment_content, _ = _collapsible_header("Post Comment to Canvas", True)
        self._content_layout.addWidget(comment_header)

        cc_layout = QVBoxLayout(comment_content)
        cc_layout.setContentsMargins(0, SPACING_SM, 0, 0)
        cc_layout.setSpacing(SPACING_SM)

        self._comment_edit = QTextEdit()
        self._comment_edit.setPlaceholderText("Type a comment to post on the student's submission…")
        self._comment_edit.setMaximumHeight(100)
        self._comment_edit.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_INSET}; color: {PHOSPHOR_MID};
                border: 1px solid {BORDER_DARK}; border-radius: 4px;
                padding: 6px; font-size: {px(12)}px;
            }}
            QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}
        """)
        cc_layout.addWidget(self._comment_edit)

        self._post_btn = QPushButton("Post Comment")
        self._post_btn.setStyleSheet(f"""
            QPushButton {{
                background: rgba(180,130,60,0.15); border: 1px solid {BORDER_AMBER};
                color: {PHOSPHOR_MID}; font-size: {px(12)}px; padding: 6px 16px;
                border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background: rgba(180,130,60,0.30); color: {PHOSPHOR_HOT}; }}
            QPushButton:disabled {{ opacity: 0.4; }}
        """)
        self._post_btn.clicked.connect(
            lambda: self._on_post_comment(cid, aid, sid)
        )
        self._comment_result_lbl = QLabel("")
        self._comment_result_lbl.setStyleSheet(
            f"color: {TERM_GREEN}; font-size: {px(11)}px; background: transparent;"
        )
        btn_row2 = QHBoxLayout()
        btn_row2.addWidget(self._post_btn)
        btn_row2.addWidget(self._comment_result_lbl, 1)
        cc_layout.addLayout(btn_row2)

        self._content_layout.addWidget(comment_content)

        # ── Triage actions (always shown unless already overridden) ─────────
        if not override:
            triage_card = _make_card("triageCard")
            triage_card.setStyleSheet(f"""
                QFrame#triageCard {{
                    background: {CARD_GRADIENT};
                    border: 1px solid {BORDER_DARK};
                    border-radius: 6px;
                }}
            """)
            tl = QVBoxLayout(triage_card)
            tl.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
            tl.setSpacing(SPACING_SM)

            triage_hdr = QLabel("TRIAGE")
            triage_hdr.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
                f" letter-spacing: 1.5px; background: transparent;"
            )
            tl.addWidget(triage_hdr)

            btn_row = QHBoxLayout()
            btn_row.setSpacing(SPACING_SM)

            if grading_tool == "points" or grading_tool == "df":
                # Points / discussion forum grading — adjust grade
                approve_btn = QPushButton("✓ Approve Grade")
                approve_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(114,184,90,0.10); border: 1px solid {TERM_GREEN};
                        color: {TERM_GREEN}; font-size: {px(12)}px; padding: 6px 14px;
                        border-radius: 4px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background: rgba(114,184,90,0.20); }}
                """)
                approve_btn.clicked.connect(
                    lambda _, si=sid, ai=aid, g=grade: self.override_requested.emit(
                        si, ai, g, "Teacher approved grade after review"
                    )
                )
                btn_row.addWidget(approve_btn)

                adjust_btn = QPushButton("✎ Adjust Grade")
                adjust_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(224,128,42,0.10); border: 1px solid {BORDER_AMBER};
                        color: {PHOSPHOR_MID}; font-size: {px(12)}px; padding: 6px 14px;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{ background: rgba(224,128,42,0.20); color: {PHOSPHOR_HOT}; }}
                """)
                adjust_btn.clicked.connect(
                    lambda _, si=sid, ai=aid: self.override_requested.emit(
                        si, ai, "adjust", "Teacher requested grade adjustment"
                    )
                )
                btn_row.addWidget(adjust_btn)
            else:
                # Complete/incomplete grading
                complete_btn = QPushButton("✓ Mark Complete")
                complete_btn.setStyleSheet(f"""
                    QPushButton {{
                        background: rgba(114,184,90,0.10); border: 1px solid {TERM_GREEN};
                        color: {TERM_GREEN}; font-size: {px(12)}px; padding: 6px 14px;
                        border-radius: 4px; font-weight: bold;
                    }}
                    QPushButton:hover {{ background: rgba(114,184,90,0.20); }}
                """)
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
                        color: #E0802A; font-size: {px(12)}px; padding: 6px 14px;
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
                    color: {PHOSPHOR_DIM}; font-size: {px(12)}px; padding: 6px 14px;
                    border-radius: 4px;
                }}
                QPushButton:hover {{ border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}
            """)
            btn_row.addWidget(skip_btn)

            tl.addLayout(btn_row)
            self._content_layout.addWidget(triage_card)

        self._content_layout.addStretch()

    def _on_post_comment(self, course_id: str, assignment_id: str, student_id: str) -> None:
        text = self._comment_edit.toPlainText().strip()
        if not text:
            return
        self._post_btn.setEnabled(False)
        self._comment_result_lbl.setText("Posting…")
        self.post_comment_requested.emit(course_id, assignment_id, student_id, text)

    def comment_post_result(self, ok: bool, msg: str) -> None:
        """Called by parent after the comment API call completes."""
        self._post_btn.setEnabled(True)
        if ok:
            self._comment_result_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(11)}px; background: transparent;"
            )
            self._comment_result_lbl.setText("✓ Posted")
            self._comment_edit.clear()
        else:
            self._comment_result_lbl.setStyleSheet(
                f"color: {BURN_RED}; font-size: {px(11)}px; background: transparent;"
            )
            self._comment_result_lbl.setText(f"✗ {msg or 'Failed'}")


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

        # 2-column splitter (sidebar removed — shared ReviewSidebar at parent level)
        self._splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(10)

        self._student_list = _StudentList()
        self._student_detail = _StudentDetail(api=self._api)

        self._splitter.addWidget(self._student_list)
        self._splitter.addWidget(self._student_detail)

        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([380, 600])

        self._student_list.setMinimumWidth(280)

        layout.addWidget(self._splitter, 1)

    def _connect_signals(self) -> None:
        self._student_list.student_selected.connect(self._on_student_selected)
        self._student_list.export_requested.connect(self._on_export)
        self._student_detail.override_requested.connect(self._on_override)
        self._student_detail.view_aic_detail.connect(self.view_aic_detail)
        self._student_detail.post_comment_requested.connect(self._on_post_comment)

    # ── Public API ────────────────────────────────────────────────────────

    def set_course(self, course_id: str, course_name: str) -> None:
        """Called when the user selects a course in Course Select."""
        self._filter_course_id = str(course_id)

    def load_assignment(self, course_id: str, assignment_id: str,
                        course_name: str = "", assignment_name: str = "") -> None:
        """Load an assignment selected via the shared ReviewSidebar."""
        self._on_assignment_selected(course_id, assignment_id, course_name, assignment_name)

    def refresh(self) -> None:
        """No-op — sidebar is now external. Kept for backward compat."""
        pass

    def showEvent(self, event) -> None:
        super().showEvent(event)

    # ── Slots ─────────────────────────────────────────────────────────────

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

    def _on_post_comment(self, course_id: str, assignment_id: str,
                         student_id: str, text: str) -> None:
        from gui.workers import PostCanvasCommentWorker
        w = PostCanvasCommentWorker(self._api, course_id, assignment_id, student_id, text)
        w.comment_result.connect(self._student_detail.comment_post_result)
        w.start()
        self._track_worker(w)

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
