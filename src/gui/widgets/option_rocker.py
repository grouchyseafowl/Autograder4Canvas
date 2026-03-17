"""OptionRocker — two-option mutually-exclusive painted toggle.

Two halves, only one active at a time.  Left side = isChecked() True,
right side = isChecked() False.  Emits changed(bool) on flip.

Amber phosphor aesthetic — matches PhosphorChip and ViewToggle.
Supports multi-line labels (split on \\n).
"""

from typing import Optional

from PySide6.QtCore import QRect, Signal, Qt
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

# ---------------------------------------------------------------------------
# Palette (self-contained)
# ---------------------------------------------------------------------------
_BG_INSET     = QColor("#0E0A02")
_AMBER_HOT    = QColor("#F0A830")
_AMBER_MID    = QColor("#A06A10")
_AMBER_DIM    = QColor("#5A3C08")
_BORDER_AMBER = QColor(106, 74, 18, 160)
_BORDER_DARK  = QColor("#3A2808")
_AMBER_RGB    = (240, 168, 48)

_RADIUS   = 5
_HEIGHT   = 36   # single-line labels at 11 px
_FONT_PX  = 11
_PAD_H    = 7    # horizontal text padding inside each half


class OptionRocker(QWidget):
    """Painted two-option rocker toggle.

    Parameters
    ----------
    label_left  : str   label for the True  (left)  option; use \\n for wrap
    label_right : str   label for the False (right) option; use \\n for wrap
    value       : bool  initial active side (True = left, False = right)
    """

    changed = Signal(bool)  # True = left now active, False = right now active

    def __init__(
        self,
        label_left: str,
        label_right: str,
        value: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._labels = (label_left, label_right)
        self._value  = value
        self._hover: Optional[bool] = None   # True=hovering left, False=right, None=off

        self.setFixedHeight(_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Public API ────────────────────────────────────────────────────────────
    def isChecked(self) -> bool:
        """True = left option active."""
        return self._value

    def setChecked(self, v: bool) -> None:
        self._value = bool(v)
        self.update()

    # ── Interaction ───────────────────────────────────────────────────────────
    def _side(self, x: int) -> bool:
        return x < self.width() // 2

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            new = self._side(event.pos().x())
            if new != self._value:
                self._value = new
                self.update()
                self.changed.emit(self._value)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        side = self._side(event.pos().x())
        if side != self._hover:
            self._hover = side
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover = None
        self.update()
        super().leaveEvent(event)

    # ── Painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h   = self.width(), self.height()
        half   = w // 2
        outer  = QRect(0, 0, w - 1, h - 1)

        # Background + outer border
        p.setPen(QPen(_BORDER_AMBER, 1.0))
        p.setBrush(_BG_INSET)
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)

        clip = QPainterPath()
        clip.addRoundedRect(outer.adjusted(1, 1, 0, 0), _RADIUS, _RADIUS)

        # Side fills
        for left in (True, False):
            active  = (left == self._value)
            hovered = (self._hover == left) and not active
            r = QRect(0, 0, half, h) if left else QRect(half, 0, w - half, h)

            if active or hovered:
                cx, cy   = r.center().x(), r.center().y()
                a_main   = 75 if active else 32
                a_bloom  = 38 if active else 0

                grad = QRadialGradient(cx, cy, max(r.width(), r.height()) * 0.85)
                grad.setColorAt(0.0, QColor(*_AMBER_RGB, a_main))
                grad.setColorAt(1.0, QColor(*_AMBER_RGB, 0))

                p.save()
                p.setClipPath(clip)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                p.drawRect(r)

                if a_bloom:
                    bloom = QRadialGradient(cx, cy, max(r.width(), r.height()) * 0.45)
                    bloom.setColorAt(0.0, QColor(*_AMBER_RGB, a_bloom))
                    bloom.setColorAt(1.0, QColor(*_AMBER_RGB, 0))
                    p.setBrush(bloom)
                    p.drawRect(r)

                p.restore()

        # Centre divider
        p.setPen(QPen(_BORDER_DARK, 1.0))
        p.drawLine(half, 3, half, h - 4)

        # Text
        font = QFont("Menlo")
        font.setPixelSize(_FONT_PX)
        p.setFont(font)
        fm = QFontMetrics(font)

        for left in (True, False):
            active  = (left == self._value)
            hovered = (self._hover == left) and not active
            label   = self._labels[0 if left else 1]
            text_r  = (QRect(_PAD_H, 0, half - _PAD_H * 2, h) if left
                       else QRect(half + _PAD_H, 0, w - half - _PAD_H * 2, h))

            if active:
                font.setWeight(QFont.Weight.Medium)
                p.setFont(font)
                gc = QColor(_AMBER_HOT)
                gc.setAlpha(55)
                p.setPen(gc)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    _draw_lines(p, fm, text_r.adjusted(dx, dy, dx, dy), label)
                p.setPen(_AMBER_HOT)
            elif hovered:
                font.setWeight(QFont.Weight.Normal)
                p.setFont(font)
                p.setPen(_AMBER_MID)
            else:
                font.setWeight(QFont.Weight.Normal)
                p.setFont(font)
                p.setPen(_AMBER_DIM)

            _draw_lines(p, fm, text_r, label)

        p.end()


def _draw_lines(p: QPainter, fm: QFontMetrics, rect: QRect, label: str) -> None:
    """Draw a \\n-split label centred (both axes) inside rect."""
    lines    = label.split("\n")
    line_h   = fm.height()
    gap      = 2
    total_h  = len(lines) * line_h + (len(lines) - 1) * gap
    y_base   = rect.top() + (rect.height() - total_h) // 2 + fm.ascent()
    for i, line in enumerate(lines):
        text_w = fm.horizontalAdvance(line)
        x = rect.left() + (rect.width() - text_w) // 2
        p.drawText(x, y_base + i * (line_h + gap), line)
