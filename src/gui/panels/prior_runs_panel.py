"""
Prior Runs Panel — Academic Integrity Review Dashboard.

Four-layer progressive drill-down:
  Sidebar (Run Browser) + Right content area:
    Layer 1: Class Landscape  — default cohort scatter plot
    Layer 3: Student Trajectory — sparklines across the semester
    Layer 4: Student Detail     — marker breakdown, notes, profile override

Ethics: "Patterns for conversation, not verdicts"
  - Ethical framing strip always visible, never dismissible
  - Smoking guns: ROSE_ACCENT glow border, separate from "high concern"
  - Burnout signals labelled as such in trajectory view
  - Class landscape is default (teacher sees whole cohort first)
"""

import math
from typing import Dict, List, Optional, Any

from PySide6.QtWidgets import (
    QWidget, QFrame, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QTextEdit, QTextBrowser, QSizePolicy, QComboBox,
    QCheckBox, QStackedWidget,
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize
from PySide6.QtGui import (
    QColor, QPainter, QPen, QBrush, QFont, QFontMetrics,
    QRadialGradient, QLinearGradient, QPainterPath, QPaintEvent, QMouseEvent,
)

from gui.styles import (
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, ROSE_DIM, WARN_PINK, TERM_GREEN, BURN_RED, AMBER_BTN,
    BG_VOID, BG_CARD, BG_PANEL, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    CARD_GRADIENT, PANEL_GRADIENT,
    make_secondary_button, make_run_button,
    make_section_label, make_h_rule, GripSplitter, PANE_BG_GRADIENT,
)
from gui.widgets.switch_toggle import SwitchToggle


# ──────────────────────────────────────────────────────────────────────────────
# Local stylesheets
# ──────────────────────────────────────────────────────────────────────────────

_COMBO_QSS = f"""
    QComboBox {{
        background: {BG_INSET};
        color: {PHOSPHOR_MID};
        border: 1px solid {BORDER_DARK};
        border-radius: 4px;
        padding: 3px 8px;
        font-size: 12px;
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

_RUN_ROW_QSS = f"""
    QFrame {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-bottom: 1px solid {BORDER_DARK};
    }}
    QFrame:hover {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(240,168,48,0.14),stop:0.45 rgba(240,168,48,0.04),stop:1.0 transparent);
        border-left-color: {BORDER_AMBER};
    }}
"""

_RUN_ROW_SEL_QSS = f"""
    QFrame {{
        background: qradialgradient(cx:0.06,cy:0.5,radius:1.2,fx:0.02,fy:0.5,
            stop:0.0 rgba(204,82,130,0.22),stop:0.45 rgba(204,82,130,0.06),stop:1.0 transparent);
        border: none;
        border-left: 3px solid {BORDER_AMBER};
        border-bottom: 1px solid {BORDER_DARK};
    }}
"""

_SECTION_HDR_QSS = f"""
    color: {PHOSPHOR_DIM};
    font-size: 10px;
    font-weight: bold;
    letter-spacing: 1px;
"""

_CARD_QSS = f"""
    QFrame {{
        background: {CARD_GRADIENT};
        border: 1px solid {BORDER_DARK};
        border-radius: 6px;
    }}
"""

_SMOKING_GUN_CARD_QSS = f"""
    QFrame {{
        background: {CARD_GRADIENT};
        border: 1.5px solid {ROSE_DIM};
        border-radius: 6px;
    }}
"""

_NOTE_EDIT_QSS = f"""
    QTextEdit {{
        background: {BG_INSET};
        color: {PHOSPHOR_MID};
        border: 1px solid {BORDER_DARK};
        border-radius: 4px;
        font-size: 12px;
        padding: 6px;
    }}
    QTextEdit:focus {{ border-color: {BORDER_AMBER}; }}
"""


# ──────────────────────────────────────────────────────────────────────────────
# Concern colour map — imported from shared palette
# ──────────────────────────────────────────────────────────────────────────────

from gui.aic_palette import CONCERN_COLOR as _CONCERN_COLOR, CONCERN_LABEL as _CONCERN_LABEL

# Scatter-specific dot colours — overrides palette for visibility on dark bg.
# "none" concern uses cool teal (instead of near-invisible dark amber).
_SCATTER_COLOR = {
    "none":     "#58C8B8",   # cool teal — clearly safe
    "low":      "#78B870",   # soft green — low concern
    "moderate": "#C4708A",   # warm pink — moderate
    "elevated": "#E0802A",   # orange — elevated
    "high":     "#C04020",   # red — high
}

_PROFILE_OPTIONS = [
    ("standard",          "Standard"),
    ("community_college", "Community College"),
    ("esl",               "ESL"),
    ("neurodivergent",    "Neurodivergent"),
    ("first_gen",         "First-Generation"),
]

# Per-student composable override levels (for StudentDetailView)
_OVERRIDE_LEVEL_OPTIONS = [
    ("none",     "None  (inherit from class)"),
    ("low",      "Low"),
    ("moderate", "Moderate"),
    ("high",     "High"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _section_label(text: str, parent=None) -> QLabel:
    lbl = QLabel(text.upper(), parent)
    lbl.setStyleSheet(_SECTION_HDR_QSS)
    return lbl


def _h_rule() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"background: {BORDER_DARK}; max-height: 1px;")
    return line


def _make_card(smoking_gun: bool = False) -> QFrame:
    card = QFrame()
    card.setStyleSheet(_SMOKING_GUN_CARD_QSS if smoking_gun else _CARD_QSS)
    return card


def _fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return "—"
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y")
    except Exception:
        return iso[:10]


# ──────────────────────────────────────────────────────────────────────────────
# CohortScatterWidget — QPainter scatter plot
# ──────────────────────────────────────────────────────────────────────────────

class CohortScatterWidget(QWidget):
    """
    Scatter plot: X = human presence confidence (0–100), Y = suspicion score.
    Dot size ∝ word count.  Colours map to concern level.
    Smoking-gun submissions get a rose-glow ring.
    Click a dot → dot_clicked(student_id, assignment_id) emitted.
    """

    dot_clicked = Signal(str, str)   # (student_id, assignment_id)
    dot_hovered = Signal(str)        # student name or "" on leave

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: List[Dict] = []
        self._assignment_id: str = ""
        self._hover_idx: Optional[int] = None
        self._profile_label: str = ""
        self.setMouseTracking(True)
        self.setMinimumSize(300, 220)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, rows: List[Dict], assignment_id: str, profile_label: str = "") -> None:
        self._rows = rows
        self._assignment_id = assignment_id
        self._profile_label = profile_label
        self._hover_idx = None
        self.update()

    # ── geometry ─────────────────────────────────────────────────────────────

    def _plot_rect(self) -> QRect:
        return QRect(56, 10, self.width() - 56 - 14, self.height() - 10 - 40)

    def _dot_pos(self, row: Dict, pr: QRect) -> QPoint:
        hp = float(row.get("human_presence_confidence") or 50)
        sus = float(row.get("adjusted_suspicious_score") or row.get("suspicious_score") or 0)
        max_sus = max((float(r.get("adjusted_suspicious_score") or r.get("suspicious_score") or 0)
                       for r in self._rows), default=1.0) or 1.0
        x = pr.left() + int(hp / 100 * pr.width())
        y = pr.bottom() - int(sus / max_sus * pr.height())
        return QPoint(x, y)

    def _dot_radius(self, row: Dict) -> int:
        wc = int(row.get("word_count") or 200)
        return max(4, min(13, int(4 + math.sqrt(wc / 50))))

    def _find_dot(self, pos: QPoint) -> Optional[int]:
        pr = self._plot_rect()
        for i, row in enumerate(self._rows):
            dp = self._dot_pos(row, pr)
            if (pos - dp).manhattanLength() < self._dot_radius(row) + 8:
                return i
        return None

    # ── events ────────────────────────────────────────────────────────────────

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        idx = self._find_dot(event.position().toPoint())
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()
            self.dot_hovered.emit(self._rows[idx]["student_name"] if idx is not None else "")

    def leaveEvent(self, _event) -> None:
        if self._hover_idx is not None:
            self._hover_idx = None
            self.update()
            self.dot_hovered.emit("")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._find_dot(event.position().toPoint())
            if idx is not None:
                row = self._rows[idx]
                self.dot_clicked.emit(str(row["student_id"]), self._assignment_id)

    # ── painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event: QPaintEvent) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        pr = self._plot_rect()

        # ── Background ────────────────────────────────────────────────────
        p.fillRect(0, 0, w, h, QColor(BG_INSET))

        # Subtle vertical zone tint: teal at bottom (safe) → rose at top (concern)
        zone = QLinearGradient(0, pr.bottom(), 0, pr.top())
        zone.setColorAt(0.00, QColor(88, 200, 176, 10))
        zone.setColorAt(0.35, QColor(0, 0, 0, 0))
        zone.setColorAt(0.65, QColor(0, 0, 0, 0))
        zone.setColorAt(1.00, QColor(204, 82, 130, 14))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(zone)
        p.drawRect(pr)

        # ── Grid lines (quartiles) ────────────────────────────────────────
        p.setPen(QPen(QColor(PHOSPHOR_GLOW), 1, Qt.PenStyle.DotLine))
        for frac in (0.25, 0.5, 0.75):
            gx = pr.left() + int(frac * pr.width())
            gy = pr.bottom() - int(frac * pr.height())
            p.drawLine(gx, pr.top(), gx, pr.bottom())
            p.drawLine(pr.left(), gy, pr.right(), gy)

        # ── Axis borders ──────────────────────────────────────────────────
        p.setPen(QPen(QColor(BORDER_DARK), 1))
        p.drawLine(pr.left(), pr.top(), pr.left(), pr.bottom())
        p.drawLine(pr.left(), pr.bottom(), pr.right(), pr.bottom())

        # ── Y axis: rotated label + tick values ───────────────────────────
        label_font = QFont()
        label_font.setPixelSize(9)

        # Rotated title
        p.save()
        rot_font = QFont()
        rot_font.setPixelSize(9)
        rot_font.setBold(True)
        p.setFont(rot_font)
        p.setPen(QColor(PHOSPHOR_DIM))
        p.translate(12, pr.top() + pr.height() // 2)
        p.rotate(-90)
        p.drawText(QRect(-pr.height() // 2, 0, pr.height(), 14),
                   Qt.AlignmentFlag.AlignCenter, "PATTERN STRENGTH")
        p.restore()

        # Tick labels
        p.setFont(label_font)
        max_sus = max(
            (float(r.get("adjusted_suspicious_score") or r.get("suspicious_score") or 0)
             for r in self._rows), default=1.0) or 1.0
        for frac, label in ((0.0, "0"), (0.5, f"{max_sus * 0.5:.1f}"), (1.0, f"{max_sus:.1f}")):
            gy = pr.bottom() - int(frac * pr.height())
            p.setPen(QColor(PHOSPHOR_DIM))
            p.drawText(QRect(pr.left() - 34, gy - 7, 30, 14),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       label)

        # Zone hint labels (right edge of plot)
        hint_font = QFont()
        hint_font.setPixelSize(8)
        p.setFont(hint_font)
        p.setPen(QColor(88, 200, 176, 160))
        p.drawText(QRect(pr.right() - 110, pr.bottom() - 16, 106, 14),
                   Qt.AlignmentFlag.AlignRight, "fewer patterns")
        p.setPen(QColor(204, 82, 130, 160))
        p.drawText(QRect(pr.right() - 110, pr.top() + 2, 106, 14),
                   Qt.AlignmentFlag.AlignRight, "more patterns")

        # ── X axis labels ─────────────────────────────────────────────────
        p.setFont(label_font)
        p.setPen(QColor(PHOSPHOR_DIM))
        p.drawText(QRect(pr.left(), pr.bottom() + 6, pr.width(), 14),
                   Qt.AlignmentFlag.AlignLeft, "← less human presence")
        p.drawText(QRect(pr.left(), pr.bottom() + 6, pr.width(), 14),
                   Qt.AlignmentFlag.AlignRight, "more human presence →")

        # ── Dots with CRT bloom ───────────────────────────────────────────
        for i, row in enumerate(self._rows):
            dp = self._dot_pos(row, pr)
            rad = self._dot_radius(row)
            concern = row.get("concern_level", "none")
            is_sg = bool(row.get("smoking_gun"))
            is_hovered = i == self._hover_idx

            dot_color = QColor(_SCATTER_COLOR.get(concern, _SCATTER_COLOR["none"]))

            # Bloom halo (always — CRT glow aesthetic)
            bloom_r = rad * 2.5
            bloom_a = 75 if is_hovered else 45
            glow = QRadialGradient(float(dp.x()), float(dp.y()), bloom_r)
            glow.setColorAt(0.00, QColor(dot_color.red(), dot_color.green(),
                                         dot_color.blue(), bloom_a))
            glow.setColorAt(0.40, QColor(dot_color.red(), dot_color.green(),
                                         dot_color.blue(), bloom_a // 3))
            glow.setColorAt(1.00, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(dp, int(bloom_r), int(bloom_r))

            # Smoking-gun outer glow + ring
            if is_sg:
                sg_glow = QRadialGradient(float(dp.x()), float(dp.y()), float(rad + 10))
                sg_glow.setColorAt(0.0, QColor(204, 82, 130, 90))
                sg_glow.setColorAt(0.5, QColor(204, 82, 130, 25))
                sg_glow.setColorAt(1.0, QColor(0, 0, 0, 0))
                p.setBrush(sg_glow)
                p.drawEllipse(dp, rad + 10, rad + 10)
                p.setPen(QPen(QColor(ROSE_ACCENT), 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(dp, rad + 4, rad + 4)

            # Hover extra glow
            if is_hovered:
                hover_c = QColor(dot_color)
                hover_c.setAlpha(80)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hover_c)
                p.drawEllipse(dp, rad + 6, rad + 6)

            # Core dot
            p.setPen(QPen(dot_color.darker(120), 1))
            p.setBrush(dot_color)
            p.drawEllipse(dp, rad, rad)

            # Inner highlight (CRT phosphor hot-spot)
            hl = QRadialGradient(float(dp.x() - 1), float(dp.y() - 1), float(rad))
            hl.setColorAt(0.0, QColor(255, 255, 255, 45))
            hl.setColorAt(0.5, QColor(255, 255, 255, 0))
            hl.setColorAt(1.0, QColor(0, 0, 0, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hl)
            p.drawEllipse(dp, rad, rad)

        # ── Hover tooltip ─────────────────────────────────────────────────
        if self._hover_idx is not None:
            row = self._rows[self._hover_idx]
            dp = self._dot_pos(row, pr)
            name = row.get("student_name", "")
            concern = _CONCERN_LABEL.get(row.get("concern_level", "none"), "")
            sus = row.get("adjusted_suspicious_score") or row.get("suspicious_score") or 0
            tip = f"{name}  ·  {concern}  ·  {sus:.2f}"
            tip_font = QFont()
            tip_font.setPixelSize(11)
            p.setFont(tip_font)
            fm = QFontMetrics(tip_font)
            tw = fm.horizontalAdvance(tip) + 16
            tx = min(dp.x() + 12, w - tw - 4)
            ty = max(dp.y() - 24, 4)
            # Tooltip background with glow
            tip_bg = QPainterPath()
            tip_bg.addRoundedRect(tx - 6, ty - 3, tw + 8, 22, 4, 4)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(28, 21, 8, 220))
            p.drawPath(tip_bg)
            p.setPen(QPen(QColor(BORDER_DARK), 0.5))
            p.drawPath(tip_bg)
            p.setPen(QColor(PHOSPHOR_HOT))
            p.drawText(QPoint(tx, ty + 13), tip)

        # ── Profile recalc label ──────────────────────────────────────────
        if self._profile_label:
            p.setPen(QColor(WARN_PINK))
            pf = QFont()
            pf.setPixelSize(10)
            p.setFont(pf)
            p.drawText(QRect(pr.left(), h - 14, pr.width(), 14),
                       Qt.AlignmentFlag.AlignRight,
                       f"Recalculated with {self._profile_label} profile")

        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# SparklineWidget — QPainter multi-line sparklines
# ──────────────────────────────────────────────────────────────────────────────

class SparklineWidget(QWidget):
    """
    Single-series sparkline. Data: list of (x_label, value or None).
    Color, title, and optional floor label configurable.
    """

    def __init__(self, title: str, color: str, parent=None):
        super().__init__(parent)
        self._title = title
        self._color = QColor(color)
        self._data: List[tuple] = []   # [(label, value_or_None), ...]
        self._note: str = ""
        self.setMinimumHeight(70)
        self.setMaximumHeight(90)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, data: List[tuple], note: str = "") -> None:
        self._data = data
        self._note = note
        self.update()

    def paintEvent(self, _: QPaintEvent) -> None:
        if not self._data:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        title_h = 16
        note_h = 14 if self._note else 0
        label_h = 12
        pl = 8; pr_m = 8
        pt = title_h + 2; pb = label_h + note_h + 4
        pw = w - pl - pr_m
        ph = h - pt - pb
        if ph < 10:
            return

        p.fillRect(0, 0, w, h, QColor(BG_INSET))

        # Title
        font = QFont(); font.setPixelSize(9); font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(PHOSPHOR_DIM))
        p.drawText(QRect(pl, 2, pw, title_h), Qt.AlignmentFlag.AlignLeft, self._title.upper())

        # Values and scale
        vals = [v for _, v in self._data if v is not None]
        if not vals:
            return
        vmin, vmax = min(vals), max(vals)
        span = vmax - vmin or 1.0

        def to_px(val):
            return pt + ph - int((val - vmin) / span * ph)

        n = len(self._data)
        x_step = pw / max(n - 1, 1)

        # Grid line at midpoint
        p.setPen(QPen(QColor(PHOSPHOR_GLOW), 1, Qt.PenStyle.DotLine))
        mid_y = pt + ph // 2
        p.drawLine(pl, mid_y, pl + pw, mid_y)

        # Connect valid points
        p.setPen(QPen(self._color, 1.5))
        prev = None
        for i, (_, val) in enumerate(self._data):
            if val is None:
                prev = None
                continue
            cx = int(pl + i * x_step)
            cy = to_px(val)
            if prev is not None:
                p.drawLine(prev[0], prev[1], cx, cy)
            prev = (cx, cy)

        # Dots
        p.setPen(QPen(self._color.darker(120), 1))
        p.setBrush(self._color)
        for i, (_, val) in enumerate(self._data):
            if val is None:
                continue
            cx = int(pl + i * x_step)
            cy = to_px(val)
            p.drawEllipse(QPoint(cx, cy), 3, 3)

        # X-axis labels (assignment short names)
        label_font = QFont(); label_font.setPixelSize(8)
        p.setFont(label_font)
        p.setPen(QColor(PHOSPHOR_DIM))
        for i, (lbl, _) in enumerate(self._data):
            cx = int(pl + i * x_step)
            lbl_short = lbl[:8] if lbl else ""
            p.drawText(QRect(cx - 20, h - label_h - note_h, 40, label_h),
                       Qt.AlignmentFlag.AlignCenter, lbl_short)

        # Note (burnout signal label)
        if self._note:
            note_font = QFont(); note_font.setPixelSize(9)
            p.setFont(note_font)
            p.setPen(QColor(WARN_PINK))
            p.drawText(QRect(pl, h - note_h, pw, note_h),
                       Qt.AlignmentFlag.AlignLeft, self._note)

        p.end()


# ──────────────────────────────────────────────────────────────────────────────
# Layer 1: Class Landscape
# ──────────────────────────────────────────────────────────────────────────────

class ClassLandscapeView(QFrame):
    """Cohort scatter + distribution bar for one run."""

    student_selected = Signal(str, str)   # (student_id, assignment_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._run_meta: Dict = {}
        self._rows: List[Dict] = []
        self._profile_id = "standard"
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_SM)

        # ── Header ──────────────────────────────────────────────────────────
        self._header_lbl = QLabel("")
        self._header_lbl.setStyleSheet(f"color: {PHOSPHOR_HOT}; font-size: 13px; font-weight: bold;")
        root.addWidget(self._header_lbl)

        # Profile selector
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(SPACING_SM)
        ctrl_lbl = QLabel("Population profile:")
        ctrl_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        ctrl_row.addWidget(ctrl_lbl)
        self._profile_combo = QComboBox()
        self._profile_combo.setStyleSheet(_COMBO_QSS)
        for pid, plabel in _PROFILE_OPTIONS:
            self._profile_combo.addItem(plabel, pid)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        ctrl_row.addWidget(self._profile_combo)
        ctrl_row.addStretch()
        self._hover_lbl = QLabel("")
        self._hover_lbl.setStyleSheet(f"color: {PHOSPHOR_MID}; font-size: 11px;")
        ctrl_row.addWidget(self._hover_lbl)
        root.addLayout(ctrl_row)

        # ── Scatter ──────────────────────────────────────────────────────────
        self._scatter = CohortScatterWidget()
        self._scatter.dot_clicked.connect(self.student_selected)
        self._scatter.dot_hovered.connect(self._hover_lbl.setText)
        root.addWidget(self._scatter, 1)

        # ── Distribution bar ─────────────────────────────────────────────────
        root.addWidget(_section_label("Cohort Distribution"))
        self._dist_lbl = QLabel("")
        self._dist_lbl.setStyleSheet(f"color: {PHOSPHOR_MID}; font-size: 12px;")
        self._dist_lbl.setWordWrap(True)
        root.addWidget(self._dist_lbl)

        # ── Click hint ───────────────────────────────────────────────────────
        hint = QLabel("Click a dot to view student detail.")
        hint.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        root.addWidget(hint)

    def load(self, run_meta: Dict, rows: List[Dict]) -> None:
        self._run_meta = run_meta
        self._rows = rows
        self._refresh()

    def _refresh(self) -> None:
        meta = self._run_meta
        aname = meta.get("assignment_name", "")
        cname = meta.get("course_name", "")
        date = _fmt_date(meta.get("last_run"))
        count = meta.get("analyzed_count", 0)
        self._header_lbl.setText(f"{cname}  ·  {aname}  ·  {date}  ·  {count} students")

        pid = self._profile_id
        plabel = dict(_PROFILE_OPTIONS).get(pid, "")
        self._scatter.set_data(
            self._rows,
            str(meta.get("assignment_id", "")),
            plabel if pid != "standard" else "",
        )
        self._update_dist()

    def _on_profile_changed(self) -> None:
        self._profile_id = self._profile_combo.currentData()
        self._refresh()

    def _update_dist(self) -> None:
        counts: Dict[str, int] = {}
        guns = 0
        for r in self._rows:
            cl = r.get("concern_level", "none")
            counts[cl] = counts.get(cl, 0) + 1
            if r.get("smoking_gun"):
                guns += 1
        parts = []
        for k in ("none", "low", "moderate", "elevated", "high"):
            n = counts.get(k, 0)
            if n:
                label = _CONCERN_LABEL.get(k, k)
                parts.append(f"{label}: {n}")
        txt = "  ·  ".join(parts)
        if guns:
            txt += f"  |  !! {guns} smoking gun{'s' if guns > 1 else ''}"
        self._dist_lbl.setText(txt)


# ──────────────────────────────────────────────────────────────────────────────
# Layer 3: Student Trajectory
# ──────────────────────────────────────────────────────────────────────────────

class StudentTrajectoryView(QFrame):
    """Sparklines across all assignments for one student in one course."""

    back_requested = Signal()
    assignment_selected = Signal(str, str)  # (student_id, assignment_id)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._student_id = ""
        self._course_id = ""
        self._rows: List[Dict] = []
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_SM)

        # ── Nav bar ──────────────────────────────────────────────────────────
        nav = QHBoxLayout()
        back_btn = QPushButton("← Back to Class Landscape")
        make_secondary_button(back_btn)
        back_btn.clicked.connect(self.back_requested)
        nav.addWidget(back_btn)
        nav.addStretch()
        root.addLayout(nav)

        # ── Header ───────────────────────────────────────────────────────────
        self._header_lbl = QLabel("")
        self._header_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 13px; font-weight: bold;")
        root.addWidget(self._header_lbl)
        root.addWidget(_h_rule())

        # ── Scrollable sparklines ─────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"QScrollArea {{ background: {BG_VOID}; border: none; }}")
        content = QWidget()
        content.setStyleSheet(f"background: {BG_VOID};")
        self._spark_layout = QVBoxLayout(content)
        self._spark_layout.setSpacing(SPACING_MD)
        self._spark_layout.setContentsMargins(0, 0, 0, 0)
        scroll.setWidget(content)
        root.addWidget(scroll, 1)

        # ── Hint ─────────────────────────────────────────────────────────────
        hint = QLabel("Click an assignment name below to view its detail.")
        hint.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        root.addWidget(hint)

    def load(self, student_name: str, course_name: str,
             student_id: str, course_id: str, rows: List[Dict]) -> None:
        self._student_id = student_id
        self._course_id = course_id
        self._rows = rows
        self._header_lbl.setText(f"{student_name}  ·  {course_name}")
        self._rebuild_sparklines()

    def _rebuild_sparklines(self) -> None:
        # Clear old widgets
        while self._spark_layout.count():
            item = self._spark_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not self._rows:
            lbl = QLabel("No data found for this student.")
            lbl.setStyleSheet(f"color: {PHOSPHOR_DIM};")
            self._spark_layout.addWidget(lbl)
            return

        labels = [r.get("assignment_name", "?")[:12] for r in self._rows]

        # Suspicion sparkline
        sus_data = [(labels[i], r.get("adjusted_suspicious_score") or r.get("suspicious_score"))
                    for i, r in enumerate(self._rows)]
        sus_spark = SparklineWidget("Suspicion Score", BURN_RED)
        sus_spark.set_data(sus_data)
        self._spark_layout.addWidget(_section_label("Suspicion Score Over Semester"))
        self._spark_layout.addWidget(sus_spark)

        # Human presence sparkline
        hp_data = [(labels[i], r.get("human_presence_confidence"))
                   for i, r in enumerate(self._rows)]
        hp_spark = SparklineWidget("Human Presence %", TERM_GREEN)
        hp_spark.set_data(hp_data)
        self._spark_layout.addWidget(_section_label("Human Presence Confidence"))
        self._spark_layout.addWidget(hp_spark)

        # Word count sparkline — check for burnout signal
        wc_data = [(labels[i], r.get("word_count")) for i, r in enumerate(self._rows)]
        wc_vals = [v for _, v in wc_data if v]
        burnout_note = ""
        if len(wc_vals) >= 2 and wc_vals[0]:
            peak = max(wc_vals)
            latest = wc_vals[-1]
            if latest < peak * 0.6:
                burnout_note = (
                    "Word count declined significantly — may indicate burnout or "
                    "increased workload, not necessarily AI use."
                )
        wc_spark = SparklineWidget("Word Count", PHOSPHOR_MID)
        wc_spark.set_data(wc_data, burnout_note)
        self._spark_layout.addWidget(_section_label("Word Count"))
        self._spark_layout.addWidget(wc_spark)

        # Submission timing sparkline (hour of day)
        timing_data = []
        for i, r in enumerate(self._rows):
            iso = r.get("submitted_at")
            hour = None
            if iso:
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                    hour = dt.hour + dt.minute / 60
                except Exception:
                    pass
            timing_data.append((labels[i], hour))
        late_night_note = ""
        late_hours = [h for _, h in timing_data if h is not None and (h >= 22 or h < 4)]
        if len(late_hours) >= 2:
            late_night_note = (
                "Multiple late-night submissions detected. This may reflect a work "
                "schedule or caregiving responsibilities — not necessarily urgency."
            )
        timing_spark = SparklineWidget("Submission Hour (0–23)", PHOSPHOR_DIM)
        timing_spark.set_data(timing_data, late_night_note)
        self._spark_layout.addWidget(_section_label("Submission Timing (hour of day)"))
        self._spark_layout.addWidget(timing_spark)

        # Assignment link list
        self._spark_layout.addWidget(_h_rule())
        self._spark_layout.addWidget(_section_label("Assignments (click to view detail)"))
        for row in self._rows:
            a_id = str(row.get("assignment_id", ""))
            a_name = row.get("assignment_name", "?")
            concern = row.get("concern_level", "none")
            sg = bool(row.get("smoking_gun"))
            color = _CONCERN_COLOR.get(concern, PHOSPHOR_DIM)
            prefix = "!! " if sg else ""
            btn = QPushButton(f"{prefix}{a_name}  [{_CONCERN_LABEL.get(concern, concern)}]")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent; border: none;
                    color: {ROSE_ACCENT if sg else color};
                    font-size: 12px; text-align: left; padding: 2px 0;
                }}
                QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(
                lambda checked=False, sid=self._student_id, aid=a_id:
                    self.assignment_selected.emit(sid, aid)
            )
            self._spark_layout.addWidget(btn)

        self._spark_layout.addStretch()


# ──────────────────────────────────────────────────────────────────────────────
# Local helpers for Student Detail View
# ──────────────────────────────────────────────────────────────────────────────

def _collapsible_section(title: str, initially_open: bool = False) -> tuple:
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
    arrow_lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent;")
    hl.addWidget(arrow_lbl)
    title_lbl = QLabel(title.upper())
    title_lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
        f" letter-spacing: 1.5px; background: transparent;")
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


def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.1f} MB"


def _clear_layout(layout) -> None:
    """Recursively remove all widgets and sub-layouts from a layout."""
    while layout.count():
        item = layout.takeAt(0)
        if item.widget():
            item.widget().deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


# ──────────────────────────────────────────────────────────────────────────────
# Layer 4: Student Detail
# ──────────────────────────────────────────────────────────────────────────────

class StudentDetailView(QFrame):
    """Full detail for one student + assignment.

    Three-zone layout:
      1. Header strip — identity, concern pill, word count, override controls
      2. Left pane   — submission viewer (QTextBrowser or attachment list)
      3. Right pane  — analysis: signal triad, marker breakdown, conversation
                       tools, teacher notes, context adjustments (collapsed)
    """

    back_requested = Signal()
    trajectory_requested = Signal(str, str)  # (student_id, course_id)
    profile_override_changed = Signal(str, str)  # (student_id, legacy_profile_id)

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        self._detail: Dict = {}
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        self._build_ui()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        from gui.widgets.signal_triad import SignalTriad  # local import avoids circular
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ── Header strip ──────────────────────────────────────────────────────
        self._header = QFrame()
        self._header.setObjectName("detailHeader")
        self._header.setStyleSheet(f"""
            QFrame#detailHeader {{
                background: {PANEL_GRADIENT};
                border-bottom: 1px solid {BORDER_AMBER};
            }}
            QFrame#detailHeader > QLabel {{
                background: transparent; border: none;
            }}
        """)
        header_layout = QVBoxLayout(self._header)
        header_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        header_layout.setSpacing(SPACING_XS)

        # Row 1: nav + identity + concern + word count
        nav_row = QHBoxLayout()
        nav_row.setSpacing(SPACING_SM)
        self._back_btn = QPushButton("← Back")
        make_secondary_button(self._back_btn)
        self._back_btn.clicked.connect(self.back_requested)
        nav_row.addWidget(self._back_btn)

        self._nav_title = QLabel("")
        self._nav_title.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 12px;")
        nav_row.addWidget(self._nav_title)
        nav_row.addStretch()

        self._concern_label = QLabel("")
        self._concern_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 12px; font-weight: bold;")
        nav_row.addWidget(self._concern_label)

        self._word_count_label = QLabel("")
        self._word_count_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        nav_row.addWidget(self._word_count_label)

        header_layout.addLayout(nav_row)

        # Row 2: smoking gun banner (hidden by default)
        self._sg_banner = QFrame()
        self._sg_banner.setObjectName("sgBanner")
        self._sg_banner.setStyleSheet(f"""
            QFrame#sgBanner {{
                background: qradialgradient(cx:0.3,cy:0.5,radius:1.0,
                    stop:0.0 rgba(204,82,130,0.18),
                    stop:0.6 rgba(204,82,130,0.06),
                    stop:1.0 transparent);
                border: none;
                border-left: 3px solid {ROSE_ACCENT};
                padding: 4px 8px;
            }}
            QFrame#sgBanner > QLabel {{ background: transparent; border: none; }}
        """)
        sg_inner = QVBoxLayout(self._sg_banner)
        sg_inner.setContentsMargins(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS)
        sg_inner.setSpacing(2)
        self._sg_title = QLabel("")
        self._sg_title.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: 11px; font-weight: bold;"
            f" letter-spacing: 1px;")
        sg_inner.addWidget(self._sg_title)
        self._sg_details_layout = QVBoxLayout()
        sg_inner.addLayout(self._sg_details_layout)
        self._sg_banner.hide()
        header_layout.addWidget(self._sg_banner)

        # Row 3: population override controls
        override_row = QHBoxLayout()
        override_row.setSpacing(SPACING_SM)

        self._override_nd = SwitchToggle("Neurodivergent-Aware", wrap_width=130)
        override_row.addWidget(self._override_nd)

        esl_lbl = QLabel("ESL:")
        esl_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px;")
        override_row.addWidget(esl_lbl)
        self._override_esl_combo = QComboBox()
        self._override_esl_combo.setStyleSheet(_COMBO_QSS)
        self._override_esl_combo.setFixedWidth(160)
        for pid, plabel in _OVERRIDE_LEVEL_OPTIONS:
            self._override_esl_combo.addItem(plabel, pid)
        override_row.addWidget(self._override_esl_combo)

        fg_lbl = QLabel("First-Gen:")
        fg_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px;")
        override_row.addWidget(fg_lbl)
        self._override_fg_combo = QComboBox()
        self._override_fg_combo.setStyleSheet(_COMBO_QSS)
        self._override_fg_combo.setFixedWidth(160)
        for pid, plabel in _OVERRIDE_LEVEL_OPTIONS:
            self._override_fg_combo.addItem(plabel, pid)
        override_row.addWidget(self._override_fg_combo)

        apply_btn = QPushButton("Apply Override")
        make_secondary_button(apply_btn)
        apply_btn.clicked.connect(self._on_composable_override)
        override_row.addWidget(apply_btn)

        self._recalc_note = QLabel("")
        self._recalc_note.setStyleSheet(f"color: {WARN_PINK}; font-size: 10px;")
        self._recalc_note.setWordWrap(True)
        override_row.addWidget(self._recalc_note)
        override_row.addStretch()

        header_layout.addLayout(override_row)
        outer.addWidget(self._header)

        # ── Two-pane split ────────────────────────────────────────────────────
        self._splitter = GripSplitter.create(Qt.Orientation.Horizontal)

        # Left pane: submission viewer
        left_frame = QFrame()
        left_frame.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        left_layout = QVBoxLayout(left_frame)
        left_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_SM, SPACING_MD)
        left_layout.setSpacing(SPACING_SM)

        left_layout.addWidget(make_section_label("STUDENT SUBMISSION"))
        left_layout.addWidget(make_h_rule())

        self._sub_type_label = QLabel("No submission loaded")
        self._sub_type_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;")
        left_layout.addWidget(self._sub_type_label)

        self._sub_viewer = QTextBrowser()
        self._sub_viewer.setOpenExternalLinks(True)
        self._sub_viewer.setStyleSheet(f"""
            QTextBrowser {{
                background: {BG_INSET};
                color: {PHOSPHOR_MID};
                border: 1px solid {BORDER_DARK};
                border-radius: 4px;
                padding: 8px;
                font-size: 12px;
            }}
        """)
        self._sub_viewer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        left_layout.addWidget(self._sub_viewer, 1)

        self._att_container = QWidget()
        self._att_container.setStyleSheet("background: transparent;")
        self._att_layout = QVBoxLayout(self._att_container)
        self._att_layout.setContentsMargins(0, 0, 0, 0)
        self._att_container.hide()
        left_layout.addWidget(self._att_container)

        self._splitter.addWidget(left_frame)

        # Right pane: analysis (scrollable)
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right_scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG_VOID}; border: none; }}")
        self._right_body = QWidget()
        self._right_body.setStyleSheet(f"background: {BG_VOID};")
        self._right_layout = QVBoxLayout(self._right_body)
        self._right_layout.setContentsMargins(
            SPACING_SM, SPACING_SM, SPACING_MD, SPACING_MD)
        self._right_layout.setSpacing(SPACING_SM)
        right_scroll.setWidget(self._right_body)

        self._splitter.addWidget(right_scroll)
        self._splitter.setStretchFactor(0, 45)
        self._splitter.setStretchFactor(1, 55)

        outer.addWidget(self._splitter, 1)

    # ── Data loading ──────────────────────────────────────────────────────────

    def load(self, detail: Dict) -> None:
        self._detail = detail
        self._rebuild()

    def _rebuild(self) -> None:
        from gui.widgets.signal_triad import SignalTriad
        d = self._detail
        if not d:
            return

        name    = d.get("student_name", "Unknown")
        aname   = d.get("assignment_name", "")
        date    = _fmt_date(d.get("submitted_at") or d.get("last_analyzed_at"))
        concern = d.get("concern_level", "none")
        is_sg   = bool(d.get("smoking_gun"))
        wc      = d.get("word_count") or 0

        # ── Header strip ──────────────────────────────────────────────────────
        self._nav_title.setText(f"{name}  ·  {aname}  ·  {date}")

        c_color = _CONCERN_COLOR.get(concern, PHOSPHOR_DIM)
        c_text  = _CONCERN_LABEL.get(concern, concern).upper()
        self._concern_label.setText(f"● {c_text}")
        self._concern_label.setStyleSheet(
            f"color: {c_color}; font-size: 12px; font-weight: bold;")
        self._word_count_label.setText(f"{wc:,} words")

        # Smoking gun banner
        if is_sg:
            self._sg_title.setText("⚠ SMOKING GUN: CHATBOT PASTE ARTIFACTS")
            # Clear any previous detail labels
            while self._sg_details_layout.count():
                item = self._sg_details_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            for detail_txt in (d.get("smoking_gun_details") or []):
                det = QLabel(f"  >> {detail_txt}")
                det.setWordWrap(True)
                det.setStyleSheet(
                    f"color: {WARN_PINK}; font-size: 11px;"
                    f" background: transparent; border: none;")
                self._sg_details_layout.addWidget(det)
            self._sg_banner.show()
        else:
            self._sg_banner.hide()

        # Override combos
        student_id_str = str(d.get("student_id", ""))
        stored = self._store.get_composable_overrides(student_id_str)
        esl_idx = self._override_esl_combo.findData(stored.get("esl_level", "none"))
        if esl_idx >= 0:
            self._override_esl_combo.setCurrentIndex(esl_idx)
        fg_idx = self._override_fg_combo.findData(stored.get("first_gen_level", "none"))
        if fg_idx >= 0:
            self._override_fg_combo.setCurrentIndex(fg_idx)
        self._override_nd.setChecked(bool(stored.get("neurodivergent_aware", False)))

        if (stored.get("esl_level", "none") != "none"
                or stored.get("first_gen_level", "none") != "none"
                or stored.get("neurodivergent_aware", False)):
            self._recalc_note.setText("Custom population override active — scores adjusted.")
        else:
            self._recalc_note.setText("")

        # ── Left pane: submission content ─────────────────────────────────────
        sub_content = None
        try:
            sid = str(d.get("student_id", ""))
            aid = str(d.get("assignment_id", ""))
            if sid and aid:
                sub_content = self._store.get_submission_content(sid, aid)
        except Exception:
            pass

        if sub_content and sub_content.get("submission_body"):
            body = sub_content["submission_body"]
            sub_type = (sub_content.get("submission_type") or "online_text_entry").upper()
            self._sub_type_label.setText(sub_type.replace("_", " "))
            self._sub_viewer.setHtml(body) if body.lstrip().startswith("<") else self._sub_viewer.setPlainText(body)
            self._sub_viewer.show()
            self._att_container.hide()
        elif sub_content and sub_content.get("attachment_meta"):
            attachments = sub_content["attachment_meta"]
            if isinstance(attachments, list) and attachments:
                self._sub_viewer.hide()
                self._att_container.show()
                # Clear old attachment labels
                while self._att_layout.count():
                    item = self._att_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()
                self._sub_type_label.setText("ATTACHMENTS")
                for att in attachments:
                    fname = att.get("filename") or att.get("display_name") or "file"
                    fsize = att.get("size") or att.get("content-length") or 0
                    att_lbl = QLabel(f"  📎 {fname}  ({_fmt_size(fsize)})")
                    att_lbl.setStyleSheet(
                        f"color: {PHOSPHOR_MID}; font-size: 12px;"
                        f" background: transparent; border: none;")
                    self._att_layout.addWidget(att_lbl)
            else:
                self._sub_type_label.setText("NO SUBMISSION CONTENT")
                self._sub_viewer.setPlainText("No submission content available.")
                self._sub_viewer.show()
                self._att_container.hide()
        else:
            self._sub_type_label.setText("")
            self._sub_viewer.setPlainText("No submission content available.")
            self._sub_viewer.show()
            self._att_container.hide()

        # ── Right pane: clear and rebuild ─────────────────────────────────────
        while self._right_layout.count():
            item = self._right_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                _clear_layout(item.layout())

        sus  = d.get("adjusted_suspicious_score") or d.get("suspicious_score") or 0
        auth = d.get("authenticity_score") or 0
        hp   = d.get("human_presence_confidence")

        # a. Signal Overview
        self._right_layout.addWidget(make_section_label("SIGNAL OVERVIEW"))
        self._right_layout.addWidget(make_h_rule())
        triad = SignalTriad()
        triad.set_scores(
            suspicion=sus,
            authenticity=auth,
            human_presence=hp,
            concern_level=concern,
        )
        self._right_layout.addWidget(triad)
        self._right_layout.addWidget(make_h_rule())

        # b. Marker Breakdown
        mc = d.get("marker_counts") or {}
        if mc:
            self._right_layout.addWidget(make_section_label("MARKER BREAKDOWN"))
            self._right_layout.addWidget(make_h_rule())
            cols = QHBoxLayout()
            sus_col  = QVBoxLayout()
            auth_col = QVBoxLayout()
            sus_col_hdr = QLabel("Suspicion Markers")
            sus_col_hdr.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
                f" background: transparent; border: none;")
            sus_col.addWidget(sus_col_hdr)
            auth_col_hdr = QLabel("Authenticity Markers")
            auth_col_hdr.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
                f" background: transparent; border: none;")
            auth_col.addWidget(auth_col_hdr)
            sus_keys = {"inflated_vocabulary", "ai_transitions", "generic_phrases",
                        "balance_markers", "ai_specific_organization"}
            for key, val in sorted(mc.items(), key=lambda x: -x[1]):
                if key.startswith("sg_"):
                    continue
                lbl = QLabel(f"  {key.replace('_', ' ')}:  {val}")
                lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 11px;"
                    f" background: transparent; border: none;")
                if key in sus_keys:
                    sus_col.addWidget(lbl)
                else:
                    auth_col.addWidget(lbl)
            sus_col.addStretch()
            auth_col.addStretch()
            cols.addLayout(sus_col)
            cols.addLayout(auth_col)
            self._right_layout.addLayout(cols)
            self._right_layout.addWidget(make_h_rule())

        # c. Conversation Tools
        starters = d.get("conversation_starters") or []
        vqs      = d.get("verification_questions") or []
        if starters or vqs:
            self._right_layout.addWidget(make_section_label("CONVERSATION TOOLS"))
            self._right_layout.addWidget(make_h_rule())
            for s in starters[:4]:
                lbl = QLabel(f'  "{s}"')
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 12px;"
                    f" background: transparent; border: none;")
                self._right_layout.addWidget(lbl)
            for q in vqs[:3]:
                lbl = QLabel(f"  • {q}")
                lbl.setWordWrap(True)
                lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 12px;"
                    f" background: transparent; border: none;")
                self._right_layout.addWidget(lbl)
            self._right_layout.addWidget(make_h_rule())

        # d. Teacher Notes
        self._right_layout.addWidget(make_section_label("TEACHER NOTES"))
        self._right_layout.addWidget(make_h_rule())
        self._build_notes_section()
        self._right_layout.addWidget(make_h_rule())

        # e. Context Adjustments (collapsed)
        ctx = d.get("context_adjustments") or []
        if ctx:
            ctx_header, ctx_content, _ = _collapsible_section("CONTEXT ADJUSTMENTS", False)
            ctx_layout = QVBoxLayout(ctx_content)
            ctx_layout.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
            for adj in ctx:
                a_lbl = QLabel(f"  • {adj}")
                a_lbl.setWordWrap(True)
                a_lbl.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: 12px;"
                    f" background: transparent; border: none;")
                ctx_layout.addWidget(a_lbl)
            self._right_layout.addWidget(ctx_header)
            self._right_layout.addWidget(ctx_content)

        # f. Action buttons row
        btn_row = QHBoxLayout()
        exp_btn = QPushButton("Export Reports")
        make_secondary_button(exp_btn)
        exp_btn.clicked.connect(self._open_export_dialog)
        btn_row.addWidget(exp_btn)

        traj_btn = QPushButton("View Student Trajectory")
        make_secondary_button(traj_btn)
        traj_btn.clicked.connect(self._on_trajectory)
        btn_row.addWidget(traj_btn)
        btn_row.addStretch()
        self._right_layout.addLayout(btn_row)
        self._right_layout.addStretch()

    def _build_notes_section(self) -> None:
        """Add note rows + composer directly to _right_layout."""
        student_id  = str(self._detail.get("student_id", ""))
        course_id   = str(self._detail.get("course_id", ""))
        assignment_id = str(self._detail.get("assignment_id", ""))

        notes = self._store.get_notes(student_id, course_id)
        if notes:
            for note in notes:
                self._right_layout.addWidget(
                    self._make_note_row(note, student_id, course_id))
        else:
            empty = QLabel("No notes yet.")
            empty.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 12px;"
                f" background: transparent; border: none;")
            self._right_layout.addWidget(empty)

        # Composer
        composer_lbl = QLabel("Add a note:")
        composer_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
            f" background: transparent; border: none;")
        self._right_layout.addWidget(composer_lbl)

        self._note_edit = QTextEdit()
        self._note_edit.setPlaceholderText(
            "Conversation summary, student context, follow-up reminders…\n"
            "Notes do not affect scores. They are for your reference only.")
        self._note_edit.setFixedHeight(72)
        self._note_edit.setStyleSheet(_NOTE_EDIT_QSS)
        self._right_layout.addWidget(self._note_edit)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("Save Note")
        make_secondary_button(save_btn)
        save_btn.clicked.connect(
            lambda: self._save_note(student_id, course_id, assignment_id))
        btn_row.addWidget(save_btn)
        btn_row.addStretch()
        scope_lbl = QLabel("Notes are per student, not per assignment.")
        scope_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px;"
            f" background: transparent; border: none;")
        btn_row.addWidget(scope_lbl)
        self._right_layout.addLayout(btn_row)

    def _make_note_row(self, note: Dict, student_id: str, course_id: str) -> QFrame:
        """A single note row with inline edit and delete."""
        row = QFrame()
        row.setStyleSheet(f"""
            QFrame {{
                background: {BG_INSET};
                border: 1px solid {BORDER_DARK};
                border-radius: 4px;
            }}
        """)
        v = QVBoxLayout(row)
        v.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        v.setSpacing(SPACING_XS)

        # Date + action buttons
        top_row = QHBoxLayout()
        date_lbl = QLabel(_fmt_date(note.get("created_at")))
        date_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px;")
        top_row.addWidget(date_lbl)
        top_row.addStretch()

        note_id = note.get("id")

        edit_btn = QPushButton("Edit")
        edit_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {PHOSPHOR_DIM}; font-size: 10px; padding: 0 4px;
            }}
            QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
        """)
        top_row.addWidget(edit_btn)

        del_btn = QPushButton("Delete")
        del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {PHOSPHOR_DIM}; font-size: 10px; padding: 0 4px;
            }}
            QPushButton:hover {{ color: {BURN_RED}; }}
        """)
        top_row.addWidget(del_btn)
        v.addLayout(top_row)

        # Note text (switches to edit mode on Edit click)
        note_text = note.get("note_text", "")
        text_lbl = QLabel(note_text)
        text_lbl.setWordWrap(True)
        text_lbl.setStyleSheet(f"color: {PHOSPHOR_MID}; font-size: 12px;")
        v.addWidget(text_lbl)

        # Inline editor (hidden by default)
        editor = QTextEdit()
        editor.setPlainText(note_text)
        editor.setFixedHeight(56)
        editor.setStyleSheet(_NOTE_EDIT_QSS)
        editor.hide()
        v.addWidget(editor)

        save_edit_btn = QPushButton("Save")
        make_secondary_button(save_edit_btn)
        save_edit_btn.hide()
        v.addWidget(save_edit_btn)

        # Edit toggle
        def toggle_edit():
            editing = editor.isVisible()
            if editing:
                editor.hide()
                save_edit_btn.hide()
                text_lbl.show()
                edit_btn.setText("Edit")
            else:
                editor.setPlainText(text_lbl.text())
                text_lbl.hide()
                editor.show()
                save_edit_btn.show()
                edit_btn.setText("Cancel")

        edit_btn.clicked.connect(toggle_edit)

        # Save edit
        def save_edit():
            new_text = editor.toPlainText().strip()
            if new_text and note_id is not None:
                self._store.update_note(note_id, new_text)
                self._rebuild()

        save_edit_btn.clicked.connect(save_edit)

        # Delete
        def delete_note():
            if note_id is not None:
                self._store.delete_note(note_id)
                self._rebuild()

        del_btn.clicked.connect(delete_note)

        return row

    def _save_note(self, student_id: str, course_id: str, assignment_id: str) -> None:
        text = self._note_edit.toPlainText().strip()
        if not text:
            return
        self._store.save_note(student_id, course_id, text, assignment_id or None)
        self._note_edit.clear()
        self._rebuild()

    def _on_composable_override(self) -> None:
        student_id = str(self._detail.get("student_id", ""))
        if not student_id:
            return
        esl = self._override_esl_combo.currentData() or "none"
        fg = self._override_fg_combo.currentData() or "none"
        nd = self._override_nd.isChecked()
        self._store.set_composable_overrides(student_id, esl_level=esl,
                                             first_gen_level=fg, neurodivergent_aware=nd)
        if esl == "none" and fg == "none" and not nd:
            self._recalc_note.setText("")
        else:
            parts = []
            if esl != "none":
                parts.append(f"ESL={esl}")
            if fg != "none":
                parts.append(f"first-gen={fg}")
            if nd:
                parts.append("ND-aware")
            self._recalc_note.setText(f"Override active: {', '.join(parts)}")
        # Emit legacy signal with derived profile_id for any existing slots
        legacy_pid = self._store.get_profile_override(student_id) or "standard"
        self.profile_override_changed.emit(student_id, legacy_pid)

    def _open_export_dialog(self) -> None:
        from gui.dialogs.export_reports_dialog import ExportReportsDialog
        ExportReportsDialog(parent=self).exec()

    def _on_trajectory(self) -> None:
        student_id = str(self._detail.get("student_id", ""))
        course_id = str(self._detail.get("course_id", ""))
        self.trajectory_requested.emit(student_id, course_id)


# ──────────────────────────────────────────────────────────────────────────────
# Run Browser Sidebar
# ──────────────────────────────────────────────────────────────────────────────

class RunBrowserSidebar(QFrame):
    """Left sidebar: list of (course, assignment) runs with counts."""

    run_selected = Signal(dict)  # run_meta dict

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        self._rows: List[Dict] = []
        self._selected_idx: Optional[int] = None
        self._row_frames: List[QFrame] = []
        self.setMinimumWidth(220)
        self.setMaximumWidth(300)
        self.setStyleSheet(f"QFrame {{ background: {PANEL_GRADIENT}; border-right: 1px solid {BORDER_DARK}; }}")
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QFrame()
        hdr.setStyleSheet(f"QFrame {{ background: {BG_CARD}; border-bottom: 1px solid {BORDER_DARK}; }}")
        hdr_layout = QHBoxLayout(hdr)
        hdr_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_SM, SPACING_SM)
        hdr_lbl = QLabel("PRIOR RUNS")
        hdr_lbl.setStyleSheet(_SECTION_HDR_QSS)
        hdr_layout.addWidget(hdr_lbl)
        hdr_layout.addStretch()
        refresh_btn = QPushButton("↻")
        refresh_btn.setFixedSize(24, 24)
        refresh_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; border: none;
                color: {PHOSPHOR_DIM}; font-size: 14px;
            }}
            QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
        """)
        refresh_btn.setToolTip("Refresh run list")
        refresh_btn.clicked.connect(self.refresh)
        hdr_layout.addWidget(refresh_btn)
        root.addWidget(hdr)

        # Scroll area for run rows
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG_PANEL}; border: none; }}")
        self._list_widget = QWidget()
        self._list_widget.setStyleSheet(f"background: {BG_PANEL};")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, SPACING_XS, 0, SPACING_XS)
        self._list_layout.setSpacing(0)
        self._scroll.setWidget(self._list_widget)
        root.addWidget(self._scroll, 1)

        self._empty_lbl = QLabel("No runs found.\nRun the Academic\nIntegrity Check first.")
        self._empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px; padding: 20px;")
        self._list_layout.addWidget(self._empty_lbl)
        self._list_layout.addStretch()

    def refresh(self) -> None:
        try:
            rows = self._store.get_runs()
            self.set_runs(rows)
        except Exception:
            pass

    def set_runs(self, rows: List[Dict]) -> None:
        self._rows = rows
        self._selected_idx = None
        self._row_frames.clear()

        # Clear list
        while self._list_layout.count():
            item = self._list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not rows:
            lbl = QLabel("No runs found.\nRun the Academic\nIntegrity Check first.")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px; padding: 20px;")
            self._list_layout.addWidget(lbl)
            self._list_layout.addStretch()
            return

        for i, run in enumerate(rows):
            frame = self._make_run_row(run, i)
            self._row_frames.append(frame)
            self._list_layout.addWidget(frame)

        self._list_layout.addStretch()

    def _make_run_row(self, run: Dict, idx: int) -> QFrame:
        frame = QFrame()
        frame.setStyleSheet(_RUN_ROW_QSS)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        layout.setSpacing(2)

        course = QLabel(run.get("course_name", "").upper()[:28])
        course.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(course)

        aname = QLabel(run.get("assignment_name", ""))
        aname.setStyleSheet(f"color: {PHOSPHOR_MID}; font-size: 12px;")
        aname.setWordWrap(True)
        layout.addWidget(aname)

        date = _fmt_date(run.get("last_run"))
        count = run.get("analyzed_count", 0)
        meta_lbl = QLabel(f"{date}  ·  {count} students")
        meta_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 10px;")
        layout.addWidget(meta_lbl)

        guns = int(run.get("smoking_gun_count") or 0)
        if guns:
            gun_lbl = QLabel(f"!! {guns} smoking gun{'s' if guns > 1 else ''}")
            gun_lbl.setStyleSheet(f"color: {ROSE_ACCENT}; font-size: 10px; font-weight: bold;")
            layout.addWidget(gun_lbl)

        # Click handler via mouse press event override
        frame.mousePressEvent = lambda event, i=idx: self._select(i)
        return frame

    def _select(self, idx: int) -> None:
        if self._selected_idx == idx:
            return
        # Deselect previous
        if self._selected_idx is not None and self._selected_idx < len(self._row_frames):
            self._row_frames[self._selected_idx].setStyleSheet(_RUN_ROW_QSS)
        self._selected_idx = idx
        self._row_frames[idx].setStyleSheet(_RUN_ROW_SEL_QSS)
        self.run_selected.emit(self._rows[idx])


# ──────────────────────────────────────────────────────────────────────────────
# Main Panel
# ──────────────────────────────────────────────────────────────────────────────

class PriorRunsPanel(QFrame):
    """
    Main Prior Runs / Academic Integrity dashboard.

    Layout:
      Top: Ethical framing strip + "How It Works" button
      Below: Horizontal splitter → Run Browser sidebar | Right content stack
    """

    def __init__(self, api=None, store=None, parent=None):
        super().__init__(parent)
        self._api = api
        self.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")

        if store is not None:
            self._store = store
        else:
            try:
                from automation.run_store import RunStore
                self._store = RunStore()
            except Exception:
                self._store = None

        self._nav_history: List[int] = []  # stack of content indices for back nav
        self._current_run: Dict = {}
        self._current_student_id = ""
        self._current_course_id = ""

        self._build_ui()
        self._load_runs()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Ethical framing strip ─────────────────────────────────────────────
        strip = QFrame()
        strip.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER_DARK};
            }}
        """)
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
        strip_layout.setSpacing(SPACING_MD)

        framing_lbl = QLabel("PATTERNS FOR CONVERSATION, NOT VERDICTS")
        framing_lbl.setStyleSheet(
            f"color: {ROSE_ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        strip_layout.addWidget(framing_lbl)
        strip_layout.addStretch()

        info_btn = QPushButton("How the Academic Integrity Check Works")
        make_secondary_button(info_btn)
        info_btn.clicked.connect(self._show_aic_info)
        strip_layout.addWidget(info_btn)

        run_aic_btn = QPushButton("Run Academic Integrity Check")
        make_run_button(run_aic_btn)
        run_aic_btn.setEnabled(self._api is not None)
        run_aic_btn.clicked.connect(self._open_run_aic_dialog)
        strip_layout.addWidget(run_aic_btn)

        root.addWidget(strip)

        # ── Main body: sidebar + content ──────────────────────────────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        splitter.setStyleSheet("QSplitter::handle { background: " + BORDER_DARK + "; width: 1px; }")

        # Sidebar
        if self._store:
            self._sidebar = RunBrowserSidebar(self._store)
            self._sidebar.run_selected.connect(self._on_run_selected)
        else:
            self._sidebar = QLabel("RunStore unavailable.")
            self._sidebar.setStyleSheet(f"color: {BURN_RED}; padding: 20px;")
        splitter.addWidget(self._sidebar)

        # Right content stack
        self._content_stack = QStackedWidget()
        splitter.addWidget(self._content_stack)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([240, 800])

        # Layer 0: Empty state (no run selected)
        empty = QFrame()
        empty.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        empty_layout = QVBoxLayout(empty)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_lbl = QLabel("Select a run from the sidebar to view the class landscape.")
        empty_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 13px;")
        empty_layout.addWidget(empty_lbl)
        self._content_stack.addWidget(empty)   # index 0

        # Layer 1: Class Landscape
        self._landscape = ClassLandscapeView()
        self._landscape.student_selected.connect(self._on_student_selected)
        self._content_stack.addWidget(self._landscape)  # index 1

        # Layer 3: Student Trajectory
        self._trajectory = StudentTrajectoryView()
        self._trajectory.back_requested.connect(self._nav_back)
        self._trajectory.assignment_selected.connect(self._on_student_selected)
        self._content_stack.addWidget(self._trajectory)  # index 2

        # Layer 4: Student Detail
        if self._store:
            self._detail = StudentDetailView(self._store)
            self._detail.back_requested.connect(self._nav_back)
            self._detail.trajectory_requested.connect(self._on_trajectory_requested)
        else:
            self._detail = QLabel("RunStore unavailable.")
        self._content_stack.addWidget(self._detail)   # index 3

        root.addWidget(splitter, 1)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_runs(self) -> None:
        if not self._store:
            return
        try:
            from gui.workers import LoadRunsWorker
            self._runs_worker = LoadRunsWorker(self._store, parent=self)
            self._runs_worker.runs_loaded.connect(self._on_runs_loaded)
            self._runs_worker.error.connect(self._on_error)
            self._runs_worker.start()
        except Exception:
            pass

    def _on_runs_loaded(self, rows: List[Dict]) -> None:
        if isinstance(self._sidebar, RunBrowserSidebar):
            self._sidebar.set_runs(rows)

    def _on_run_selected(self, run_meta: Dict) -> None:
        self._current_run = run_meta
        if not self._store:
            return
        try:
            from gui.workers import LoadCohortWorker
            w = LoadCohortWorker(
                self._store,
                str(run_meta.get("course_id", "")),
                str(run_meta.get("assignment_id", "")),
                parent=self,
            )
            w.cohort_loaded.connect(
                lambda rows: self._landscape.load(run_meta, rows))
            w.cohort_loaded.connect(
                lambda _: self._nav_to(1))
            w.error.connect(self._on_error)
            w.start()
        except Exception:
            pass

    def _on_student_selected(self, student_id: str, assignment_id: str) -> None:
        if not self._store:
            return
        try:
            from gui.workers import LoadDetailWorker
            w = LoadDetailWorker(self._store, student_id, assignment_id, parent=self)
            w.detail_loaded.connect(self._on_detail_loaded)
            w.error.connect(self._on_error)
            w.start()
        except Exception:
            pass

    def _on_detail_loaded(self, detail: Dict) -> None:
        if not detail:
            return
        if isinstance(self._detail, StudentDetailView):
            self._detail.load(detail)
        self._nav_to(3)

    def _on_trajectory_requested(self, student_id: str, course_id: str) -> None:
        self._current_student_id = student_id
        self._current_course_id = course_id
        if not self._store:
            return
        try:
            from gui.workers import LoadTrajectoryWorker
            rows = self._store.get_trajectory(student_id, course_id)
            # Get student name from detail if loaded
            student_name = ""
            if isinstance(self._detail, StudentDetailView) and self._detail._detail:
                student_name = self._detail._detail.get("student_name", "")
            course_name = self._current_run.get("course_name", "")
            self._trajectory.load(student_name, course_name, student_id, course_id, rows)
            self._nav_to(2)
        except Exception:
            pass

    # ── Navigation ────────────────────────────────────────────────────────────

    def _nav_to(self, idx: int) -> None:
        current = self._content_stack.currentIndex()
        if current != idx:
            self._nav_history.append(current)
            if len(self._nav_history) > 10:
                self._nav_history.pop(0)
        self._content_stack.setCurrentIndex(idx)

    def _nav_back(self) -> None:
        if self._nav_history:
            self._content_stack.setCurrentIndex(self._nav_history.pop())
        else:
            self._content_stack.setCurrentIndex(1)

    # ── Misc ─────────────────────────────────────────────────────────────────

    def _show_aic_info(self) -> None:
        from gui.dialogs.aic_info_dialog import AICInfoDialog
        AICInfoDialog(parent=self).exec()

    def _open_run_aic_dialog(self) -> None:
        from gui.dialogs.run_aic_dialog import RunAICDialog
        dlg = RunAICDialog(api=self._api, parent=self)
        dlg.run_completed.connect(self._load_runs)
        dlg.exec()

    def navigate_to_student(self, student_id: str, assignment_id: str) -> None:
        """Cross-navigate from grading panel: jump straight to a student's AIC detail."""
        # Select the matching run in the sidebar for visual context
        if isinstance(self._sidebar, RunBrowserSidebar):
            for i, run in enumerate(self._sidebar._rows):
                if str(run.get("assignment_id", "")) == str(assignment_id):
                    self._sidebar._selected_idx = i
                    for j, frame in enumerate(self._sidebar._row_frames):
                        frame.setStyleSheet(_RUN_ROW_SEL_QSS if j == i else _RUN_ROW_QSS)
                    break
        # Load student detail directly (skips landscape)
        self._on_student_selected(student_id, assignment_id)

    def _on_error(self, msg: str) -> None:
        # Surface to status bar if we have a parent main window
        parent = self.parent()
        if parent and hasattr(parent, "statusBar"):
            parent.statusBar().showMessage(f"Prior Runs error: {msg}", 5000)
