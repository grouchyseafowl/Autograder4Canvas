"""AIC Signal Tuning dialog — adjust per-marker sensitivity weights."""

from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen, QRadialGradient,
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QWidget, QPushButton, QSizePolicy,
    QStackedWidget,
)

from gui.styles import (
    px,
    BG_VOID, BG_INSET,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    BORDER_DARK, BORDER_AMBER, ROSE_ACCENT,
    PANE_BG_GRADIENT,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    make_secondary_button, apply_phosphor_glow,
)
from gui.widgets.segmented_toggle import SegmentedToggle


def _glow_rule() -> QFrame:
    """1px horizontal rule — bright amber centre, fades to transparent at edges."""
    rule = QFrame()
    rule.setFixedHeight(1)
    rule.setStyleSheet(
        "QFrame { background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
        "  stop:0.00 rgba(240,168,48,0),"
        "  stop:0.20 rgba(240,168,48,0.35),"
        "  stop:0.50 rgba(240,168,48,0.70),"
        "  stop:0.80 rgba(240,168,48,0.35),"
        "  stop:1.00 rgba(240,168,48,0));"
        " border: none; }"
    )
    return rule


# -- Marker data --------------------------------------------------------------

SUSPICIOUS_MARKERS = [
    {
        "id": "ai_transitions",
        "name": "AI Transition Phrases",
        "examples": '"delving into" \u00b7 "serves as a testament" \u00b7 "plays a pivotal role" \u00b7 "furthermore" \u00b7 "moreover"',
        "default_pips": 3,
    },
    {
        "id": "ai_specific_org",
        "name": "Uniform Structure",
        "examples": 'perfectly balanced paragraphs \u00b7 excessive headers \u00b7 meta-announcements \u00b7 "this essay will explore"',
        "default_pips": 4,
    },
    {
        "id": "generic_phrases",
        "name": "Generic Filler",
        "examples": '"throughout history" \u00b7 "studies show" \u00b7 "cannot be overstated" \u00b7 "in today\'s society"',
        "default_pips": 3,
    },
    {
        "id": "inflated_vocabulary",
        "name": "Inflated Vocabulary",
        "examples": '"utilize" vs "use" \u00b7 "commence" \u00b7 "facilitate" \u00b7 "multifaceted" \u00b7 "plethora"',
        "default_pips": 3,
    },
    {
        "id": "hedge_phrases",
        "name": "Empty Hedging",
        "examples": '"both sides have valid points" \u00b7 no position taken \u00b7 avoids commitment \u00b7 excessive qualification',
        "default_pips": 3,
    },
    {
        "id": "citation_markers",
        "name": "Vague Citations",
        "examples": '"studies show" with no source \u00b7 fabricated references \u00b7 vague attribution \u00b7 "experts agree"',
        "default_pips": 3,
    },
]

AUTHENTICITY_MARKERS = [
    {
        "id": "personal_voice",
        "name": "Personal Voice",
        "examples": 'first-person perspective \u00b7 specific names, dates, places \u00b7 "I felt scared" \u00b7 sensory details',
        "default_pips": 3,
    },
    {
        "id": "authentic_voice",
        "name": "Linguistic Identity",
        "examples": "code-meshing \u00b7 translanguaging \u00b7 tonal shifts \u00b7 cultural grounding \u00b7 AAVE patterns",
        "default_pips": 3,
    },
    {
        "id": "cognitive_struggle",
        "name": "Working Through Ideas",
        "examples": '"I\'m struggling to understand" \u00b7 self-questioning \u00b7 perspective shifts \u00b7 contradictions explored',
        "default_pips": 3,
    },
    {
        "id": "cognitive_diversity",
        "name": "Diverse Thinking Patterns",
        "examples": "hyperfocus depth \u00b7 associative leaps \u00b7 tangential connections \u00b7 visible organizational effort",
        "default_pips": 3,
    },
    {
        "id": "productive_messiness",
        "name": "Productive Messiness",
        "examples": 'self-correction \u00b7 false starts \u00b7 "actually, I think..." \u00b7 circling back with new understanding',
        "default_pips": 3,
    },
    {
        "id": "emotional_language",
        "name": "Emotional Expression",
        "examples": 'named emotions \u00b7 "my stomach dropped" \u00b7 embodied reactions \u00b7 informal emotional language',
        "default_pips": 3,
    },
    {
        "id": "emotional_stakes",
        "name": "Personal Stakes",
        "examples": '"this matters to me because" \u00b7 intellectual passion \u00b7 discomfort \u00b7 hope for change',
        "default_pips": 3,
    },
    {
        "id": "balance_markers",
        "name": "Intellectual Honesty",
        "examples": '"I\'m not sure" \u00b7 "I changed my mind" \u00b7 genuine uncertainty \u00b7 "I could be missing..."',
        "default_pips": 3,
    },
    {
        "id": "contextual_grounding",
        "name": "Course-Specific Details",
        "examples": "class discussion references \u00b7 page numbers \u00b7 peer interactions \u00b7 assignment-specific details",
        "default_pips": 3,
    },
]


# -- PipControl widget --------------------------------------------------------


class PipControl(QWidget):
    """Five-pip sensitivity control: - @@@@@ +"""

    value_changed = Signal(int)

    PIP_COUNT   = 5
    PIP_RADIUS  = 4
    PIP_SPACING = 5
    BTN_PAD     = 8

    def __init__(self, value: int = 3, parent=None):
        super().__init__(parent)
        self._value = max(1, min(self.PIP_COUNT, value))
        self._hover_minus = False
        self._hover_plus = False
        self._hover_pip = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedHeight(18)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def value(self) -> int:
        return self._value

    def setValue(self, v: int):
        v = max(1, min(self.PIP_COUNT, v))
        if v != self._value:
            self._value = v
            self.update()
            self.value_changed.emit(self._value)

    def sizeHint(self) -> QSize:
        font = QFont("Menlo")
        font.setPixelSize(12)
        fm = QFontMetrics(font)
        minus_w = fm.horizontalAdvance("\u2212")
        plus_w = fm.horizontalAdvance("+")
        pips_w = self.PIP_COUNT * (self.PIP_RADIUS * 2) + (self.PIP_COUNT - 1) * self.PIP_SPACING
        total = minus_w + self.BTN_PAD + pips_w + self.BTN_PAD + plus_w + 4
        return QSize(total, 18)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def _layout(self):
        font = QFont("Menlo")
        font.setPixelSize(12)
        fm = QFontMetrics(font)
        minus_w = fm.horizontalAdvance("\u2212")
        plus_w = fm.horizontalAdvance("+")
        pips_w = self.PIP_COUNT * (self.PIP_RADIUS * 2) + (self.PIP_COUNT - 1) * self.PIP_SPACING

        x = 0
        minus_rect = QRect(x, 0, minus_w + 4, self.height())
        x += minus_w + self.BTN_PAD
        pips_x0 = x
        x += pips_w + self.BTN_PAD
        plus_rect = QRect(x, 0, plus_w + 4, self.height())

        pip_rects = []
        px = pips_x0
        cy = self.height() // 2
        for i in range(self.PIP_COUNT):
            cx = px + self.PIP_RADIUS
            r = self.PIP_RADIUS + 3
            pip_rects.append(QRect(cx - r, cy - r, r * 2, r * 2))
            px += self.PIP_RADIUS * 2 + self.PIP_SPACING

        return minus_rect, plus_rect, pip_rects, pips_x0

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton:
            return
        minus_rect, plus_rect, pip_rects, _ = self._layout()
        pos = event.position().toPoint()
        if minus_rect.contains(pos):
            self.setValue(self._value - 1)
        elif plus_rect.contains(pos):
            self.setValue(self._value + 1)
        else:
            for i, r in enumerate(pip_rects):
                if r.contains(pos):
                    self.setValue(i + 1)
                    break

    def mouseMoveEvent(self, event):
        minus_rect, plus_rect, pip_rects, _ = self._layout()
        pos = event.position().toPoint()
        old = (self._hover_minus, self._hover_plus, self._hover_pip)
        self._hover_minus = minus_rect.contains(pos)
        self._hover_plus = plus_rect.contains(pos)
        self._hover_pip = -1
        for i, r in enumerate(pip_rects):
            if r.contains(pos):
                self._hover_pip = i
                break
        if (self._hover_minus, self._hover_plus, self._hover_pip) != old:
            self.update()

    def leaveEvent(self, event):
        self._hover_minus = False
        self._hover_plus = False
        self._hover_pip = -1
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        font = QFont("Menlo")
        font.setPixelSize(12)
        p.setFont(font)

        minus_rect, plus_rect, pip_rects, pips_x0 = self._layout()

        clr = QColor(PHOSPHOR_HOT) if self._hover_minus else QColor(PHOSPHOR_MID)
        p.setPen(clr)
        p.drawText(minus_rect, Qt.AlignmentFlag.AlignCenter, "\u2212")

        cy = self.height() // 2
        px = pips_x0
        for i in range(self.PIP_COUNT):
            cx = px + self.PIP_RADIUS
            filled = (i < self._value)
            hovered = (i == self._hover_pip)

            if filled:
                color = QColor(PHOSPHOR_HOT)
                if hovered:
                    color = color.lighter(120)
            else:
                color = QColor("#2A1C06")
                if hovered:
                    color = QColor(PHOSPHOR_DIM)

            p.setPen(QPen(QColor(BORDER_AMBER if filled else BORDER_DARK), 1.0))
            p.setBrush(color)
            p.drawEllipse(cx - self.PIP_RADIUS, cy - self.PIP_RADIUS,
                          self.PIP_RADIUS * 2, self.PIP_RADIUS * 2)

            if filled:
                glow = QRadialGradient(cx, cy, self.PIP_RADIUS)
                glow.setColorAt(0.0, QColor(240, 168, 48, 180))
                glow.setColorAt(0.6, QColor(240, 168, 48, 60))
                glow.setColorAt(1.0, QColor(240, 168, 48, 0))
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(cx - self.PIP_RADIUS, cy - self.PIP_RADIUS,
                              self.PIP_RADIUS * 2, self.PIP_RADIUS * 2)

            px += self.PIP_RADIUS * 2 + self.PIP_SPACING

        clr = QColor(PHOSPHOR_HOT) if self._hover_plus else QColor(PHOSPHOR_MID)
        p.setPen(clr)
        p.drawText(plus_rect, Qt.AlignmentFlag.AlignCenter, "+")

        p.end()


# -- MarkerRow widget ----------------------------------------------------------

_ROW_REST_BG = "transparent"
_ROW_HOVER_BG = (
    "qradialgradient(cx:0.20,cy:0.50,radius:1.00,"
    "stop:0.00 rgba(240,168,48,18),stop:0.60 rgba(240,168,48,4),stop:1.00 transparent)"
)


class MarkerRow(QFrame):
    """Single marker row: name + pip control. Emits hovered signal for hint bar."""

    hovered = Signal(str)    # emits examples text
    unhovered = Signal()

    def __init__(self, marker: dict, parent=None):
        super().__init__(parent)
        self._marker = marker
        self._obj_name = f"marker_{marker['id']}"
        self.setObjectName(self._obj_name)
        self.setMouseTracking(True)

        lo = QHBoxLayout(self)
        lo.setContentsMargins(SPACING_MD, 6, SPACING_MD, 6)
        lo.setSpacing(SPACING_SM)

        name = QLabel(marker["name"])
        name.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(name)
        lo.addStretch()

        self._pip = PipControl(value=marker.get("default_pips", 3))
        lo.addWidget(self._pip)

        self._apply_bg(_ROW_REST_BG)

    def _apply_bg(self, bg: str):
        self.setStyleSheet(
            f"QFrame#{self._obj_name} {{ background: {bg}; border: none;"
            f"  border-radius: 4px; }}"
        )

    def enterEvent(self, event):
        self._apply_bg(_ROW_HOVER_BG)
        self.hovered.emit(self._marker["examples"])
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._apply_bg(_ROW_REST_BG)
        self.unhovered.emit()
        super().leaveEvent(event)


# -- Hint bar ------------------------------------------------------------------


class HintBar(QFrame):
    """Fixed-position bar that shows examples for the hovered signal."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("hintBar")
        self.setFixedHeight(44)
        self.setStyleSheet(
            f"QFrame#hintBar {{"
            f"  background: {BG_INSET};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-radius: 6px;"
            f"}}"
        )

        lo = QHBoxLayout(self)
        lo.setContentsMargins(SPACING_MD, 0, SPACING_MD, 0)

        self._gutter = QFrame()
        self._gutter.setFixedSize(2, 20)
        self._gutter.setStyleSheet(
            f"background: {PHOSPHOR_DIM}; border: none; border-radius: 1px;"
        )
        lo.addWidget(self._gutter)
        lo.addSpacing(8)

        self._label = QLabel("")
        self._label.setWordWrap(True)
        self._label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._label, 1)

        self._set_idle()

    def show_examples(self, text: str):
        self._label.setText(text)
        self._label.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        self._gutter.setStyleSheet(
            f"background: {PHOSPHOR_DIM}; border: none; border-radius: 1px;"
        )

    def clear(self):
        self._set_idle()

    def _set_idle(self):
        self._label.setText("Hover a signal to see what it looks for")
        self._label.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: {px(10)}px; font-style: italic;"
            f" background: transparent; border: none;"
        )
        self._gutter.setStyleSheet(
            f"background: {PHOSPHOR_GLOW}; border: none; border-radius: 1px;"
        )


# -- Marker list (just the rows + hint bar, no pane chrome) --------------------


class MarkerList(QWidget):
    """List of MarkerRows wired to a shared HintBar."""

    def __init__(self, markers: list, hint_bar: HintBar, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        for i, m in enumerate(markers):
            row = MarkerRow(m)
            row.hovered.connect(hint_bar.show_examples)
            row.unhovered.connect(hint_bar.clear)
            lo.addWidget(row)
            if i < len(markers) - 1:
                lo.addWidget(_glow_rule())

        lo.addStretch()


# -- Dialog --------------------------------------------------------------------

_SUBTITLES = {
    "suspicious":   "Structural indicators \u2014 more pips = weight this signal more",
    "authenticity": "Engagement signals \u2014 more pips = give more credit",
}


class SignalTuningDialog(QDialog):
    """AIC Signal Tuning dialog."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Engagement Analysis \u2014 Signal Tuning")
        self.setMinimumSize(420, 460)
        self.resize(460, 540)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- Scrollable body ---------------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll, 1)

        page = QWidget()
        page.setObjectName("tuningPage")
        page.setStyleSheet(f"QWidget#tuningPage {{ background: {BG_VOID}; }}")
        scroll.setWidget(page)

        body = QVBoxLayout(page)
        body.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        body.setSpacing(SPACING_SM)

        # Title
        title = QLabel("ACADEMIC INTEGRITY \u2014 SIGNAL TUNING")
        title.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(13)}px; font-weight: 500;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        body.addWidget(title)

        desc = QLabel(
            "Adjust how much weight each signal carries in the overall assessment."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        body.addWidget(desc)

        body.addSpacing(SPACING_XS)

        # -- Content pane (toggle + subtitle + markers + hint) -----------------
        pane = QFrame()
        pane.setObjectName("signalPane")
        pane.setStyleSheet(
            f"QFrame#signalPane {{"
            f"  background: {PANE_BG_GRADIENT};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-top: 2px solid {BORDER_AMBER};"
            f"  border-radius: 8px;"
            f"}}"
        )
        pane_lo = QVBoxLayout(pane)
        pane_lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        pane_lo.setSpacing(SPACING_XS)

        # Toggle -- left-justified, inside the pane
        self._toggle = SegmentedToggle(
            ("Structural Indicators", "suspicious"),
            ("Engagement Signals", "authenticity"),
            accent="amber",
        )
        self._toggle.setFixedHeight(22)
        self._toggle.mode_changed.connect(self._on_mode_changed)

        toggle_row = QHBoxLayout()
        toggle_row.setContentsMargins(0, 0, 0, 0)
        toggle_row.addStretch()
        toggle_row.addWidget(self._toggle)
        toggle_row.addStretch()
        pane_lo.addLayout(toggle_row)

        # Subtitle -- changes per mode
        self._subtitle = QLabel(_SUBTITLES["suspicious"])
        self._subtitle.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
            f" padding: 0 {SPACING_XS}px;"
        )
        pane_lo.addWidget(self._subtitle)
        pane_lo.addWidget(_glow_rule())

        # Shared hint bar
        self._hint_bar = HintBar()

        # Stacked marker lists
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")

        self._suspicious_list = MarkerList(SUSPICIOUS_MARKERS, self._hint_bar)
        self._stack.addWidget(self._suspicious_list)

        self._authenticity_list = MarkerList(AUTHENTICITY_MARKERS, self._hint_bar)
        self._stack.addWidget(self._authenticity_list)

        pane_lo.addWidget(self._stack, 1)

        # Hint bar at bottom of pane
        pane_lo.addSpacing(SPACING_XS)
        pane_lo.addWidget(self._hint_bar)

        body.addWidget(pane, 1)

        # -- Footer ------------------------------------------------------------
        footer_sep = QFrame()
        footer_sep.setFixedHeight(1)
        footer_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        root.addWidget(footer_sep)

        footer = QFrame()
        footer.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        footer_lo = QHBoxLayout(footer)
        footer_lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)

        defaults_btn = QPushButton("Restore Defaults")
        make_secondary_button(defaults_btn)
        defaults_btn.clicked.connect(self._on_restore_defaults)
        footer_lo.addWidget(defaults_btn)

        footer_lo.addStretch()

        close_btn = QPushButton("Done")
        close_btn.setProperty("accent", "true")
        close_btn.style().unpolish(close_btn)
        close_btn.style().polish(close_btn)
        apply_phosphor_glow(close_btn, color=ROSE_ACCENT, blur=14, strength=0.50)
        close_btn.clicked.connect(self.accept)
        footer_lo.addWidget(close_btn)

        root.addWidget(footer)

    def _on_mode_changed(self, mode: str):
        self._stack.setCurrentIndex(0 if mode == "suspicious" else 1)
        self._subtitle.setText(_SUBTITLES[mode])
        self._hint_bar.clear()

    def _on_restore_defaults(self):
        for pip in self.findChildren(PipControl):
            pip.setValue(3)
