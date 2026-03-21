"""OptionPair — compact two-option radio-text selector.

Two labels stacked vertically with a small dot indicator.
Active option is bright amber; inactive is dim.
Click either line to select it.

Emits changed(bool): True = top option active, False = bottom option active.
"""

from PySide6.QtCore import Signal, Qt, QRect
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPen,
)
from PySide6.QtWidgets import QWidget, QSizePolicy

from gui.styles import PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM

_FONT_PX   = 13
_DOT_R     = 4        # dot radius
_DOT_GAP   = 10       # space between dot and text
_LINE_PAD  = 4        # vertical padding per line
_AMBER_HOT = QColor(PHOSPHOR_HOT)
_AMBER_MID = QColor(PHOSPHOR_MID)
_AMBER_DIM = QColor(PHOSPHOR_DIM)


class OptionPair(QWidget):
    """Compact two-option selector rendered as radio-style text lines.

    Parameters
    ----------
    label_a : str  — label for the True (top) option
    label_b : str  — label for the False (bottom) option
    value   : bool — initial selection (True = top)
    """

    changed = Signal(bool)

    def __init__(self, label_a: str, label_b: str,
                 value: bool = True, parent=None):
        super().__init__(parent)
        self._labels = (label_a, label_b)
        self._value = value
        self._hover_side: int = -1   # 0=top, 1=bottom, -1=none

        self._font = QFont("Menlo", 0)
        self._font.setPixelSize(_FONT_PX)
        fm = QFontMetrics(self._font)
        line_h = fm.height() + _LINE_PAD * 2
        self.setFixedHeight(line_h * 2)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Public ────────────────────────────────────────────────────────────
    def isChecked(self) -> bool:
        return self._value

    def setChecked(self, v: bool) -> None:
        self._value = bool(v)
        self.update()

    # ── Interaction ───────────────────────────────────────────────────────
    def _hit(self, y: int) -> int:
        return 0 if y < self.height() // 2 else 1

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            side = self._hit(ev.pos().y())
            new_val = (side == 0)
            if new_val != self._value:
                self._value = new_val
                self.update()
                self.changed.emit(self._value)
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        side = self._hit(ev.pos().y())
        if side != self._hover_side:
            self._hover_side = side
            self.update()
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        self._hover_side = -1
        self.update()
        super().leaveEvent(ev)

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(self._font)
        fm = QFontMetrics(self._font)

        w = self.width()
        line_h = self.height() // 2
        text_x = _DOT_R * 2 + _DOT_GAP + 4   # left edge for text

        for i, label in enumerate(self._labels):
            is_active = (i == 0) == self._value
            is_hovered = (i == self._hover_side) and not is_active
            y_top = i * line_h
            cy = y_top + line_h // 2

            # Dot
            if is_active:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(_AMBER_HOT)
                p.drawEllipse(4 - _DOT_R, int(cy - _DOT_R), _DOT_R * 2, _DOT_R * 2)
            else:
                dot_color = _AMBER_MID if is_hovered else _AMBER_DIM
                p.setPen(QPen(dot_color, 1.2))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(4 - _DOT_R, int(cy - _DOT_R), _DOT_R * 2, _DOT_R * 2)

            # Text
            if is_active:
                p.setPen(_AMBER_HOT)
                self._font.setWeight(QFont.Weight.Medium)
            elif is_hovered:
                p.setPen(_AMBER_MID)
                self._font.setWeight(QFont.Weight.Normal)
            else:
                p.setPen(_AMBER_DIM)
                self._font.setWeight(QFont.Weight.Normal)
            p.setFont(self._font)

            text_rect = QRect(text_x, y_top, w - text_x, line_h)
            p.drawText(text_rect,
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                       label)

        p.end()
