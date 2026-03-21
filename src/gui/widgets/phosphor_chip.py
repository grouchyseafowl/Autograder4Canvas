"""PhosphorChip — CRT-style toggle chip or action button, fully custom-painted.

Two accents:
  "amber"  — default, warm phosphor (filter chips, mode toggles)
  "rose"   — destructive / primary accent (Clear button, warning actions)

Two modes:
  action=False (default)  — persistent toggle: click flips active/inactive state
  action=True             — fire-and-forget: emits toggled(True) on press,
                            never stays visually checked (e.g. "✕ Clear")
"""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

# ---------------------------------------------------------------------------
# Palette (self-contained — no styles.py import)
# ---------------------------------------------------------------------------
_BG_INSET = QColor("#0E0A02")
_RADIUS   = 10   # px — matches legacy pill border-radius

_AMBER_HOT         = QColor("#F0A830")
_AMBER_MID         = QColor("#A06A10")
_AMBER_DIM         = QColor("#5A3C08")
_AMBER_BORDER_REST = QColor(106,  74,  18, 140)
_AMBER_BORDER_ACT  = QColor(200, 140,  30, 200)
_AMBER_RGB         = (240, 168, 48)

_ROSE_HOT          = QColor("#FF6090")
_ROSE_MID          = QColor("#CC5282")
_ROSE_DIM          = QColor("#7A3458")
_ROSE_BORDER_REST  = QColor(160,  60, 100, 140)
_ROSE_BORDER_ACT   = QColor(204,  82, 130, 210)
_ROSE_RGB          = (204, 82, 130)


class PhosphorChip(QWidget):
    """Painted CRT-style chip: radial backlit glow + text bloom when active."""

    toggled = Signal(bool)

    def __init__(
        self,
        label: str,
        active: bool = False,
        accent: str = "amber",
        action: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._label   = label
        self._active  = (active and not action)
        self._accent  = accent
        self._action  = action
        self._hovered = False

        self.setFixedHeight(24)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Size ─────────────────────────────────────────────────────────────
    def sizeHint(self) -> QSize:
        font = QFont("Menlo")
        font.setPixelSize(11)
        fm = QFontMetrics(font)
        return QSize(fm.horizontalAdvance(self._label) + 22, 24)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ── Public API (matches QPushButton's checkable interface) ────────────
    def isChecked(self) -> bool:
        return self._active

    def setChecked(self, v: bool) -> None:
        if self._action:
            return
        self._active = bool(v)
        self.update()
        if not self.signalsBlocked():
            self.toggled.emit(self._active)

    def setText(self, text: str) -> None:
        """Strip legacy ○/● prefixes silently so old call sites keep working."""
        if len(text) >= 3 and text[:3] in ("○  ", "●  "):
            text = text[3:]
        self._label = text
        self.update()

    def text(self) -> str:
        return self._label

    # ── Interaction ───────────────────────────────────────────────────────
    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._action:
                if not self.signalsBlocked():
                    self.toggled.emit(True)
            else:
                self._active = not self._active
                self.update()
                if not self.signalsBlocked():
                    self.toggled.emit(self._active)
        super().mousePressEvent(event)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ── Painting ──────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        outer = QRect(0, 0, w - 1, h - 1)

        # 1. Base fill (dark void)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(_BG_INSET)
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)

        # 2. Radial glow — origin slightly upper-left (emphasises first word)
        if self._active or self._hovered:
            r, g, b = _ROSE_RGB if self._accent == "rose" else _AMBER_RGB
            primary_a = 75 if self._active else 45
            bloom_a   = 38 if self._active else 0   # bloom only when active

            clip = QPainterPath()
            clip.addRoundedRect(outer.adjusted(1, 1, 0, 0), _RADIUS, _RADIUS)

            # Primary glow pass
            cx, cy = w * 0.35, h * 0.40
            grad = QRadialGradient(cx, cy, max(w, h) * 0.85)
            grad.setColorAt(0.0, QColor(r, g, b, primary_a))
            grad.setColorAt(1.0, QColor(r, g, b, 0))
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(grad)
            p.drawRoundedRect(outer, _RADIUS, _RADIUS)

            # Bloom pass (active only)
            if self._active:
                bloom = QRadialGradient(cx, cy, max(w, h) * 0.48)
                bloom.setColorAt(0.0, QColor(r, g, b, bloom_a))
                bloom.setColorAt(1.0, QColor(r, g, b, 0))
                p.setBrush(bloom)
                p.drawRoundedRect(outer, _RADIUS, _RADIUS)

            p.restore()

        # 3. Border — three levels: active > hover > rest
        if self._accent == "rose":
            if self._active:
                border = _ROSE_BORDER_ACT
            elif self._hovered:
                border = QColor(180, 70, 115, 170)
            else:
                border = _ROSE_BORDER_REST
        else:
            if self._active:
                border = _AMBER_BORDER_ACT
            elif self._hovered:
                border = QColor(160, 110, 24, 170)
            else:
                border = _AMBER_BORDER_REST
        p.setPen(QPen(border, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)

        # 4. Text (with glow-offset copies when active)
        font = QFont("Menlo")
        font.setPixelSize(11)
        if self._active:
            font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        if self._accent == "rose":
            hot, mid, dim = _ROSE_HOT, _ROSE_MID, _ROSE_DIM
        else:
            hot, mid, dim = _AMBER_HOT, _AMBER_MID, _AMBER_DIM

        if self._active:
            gc = QColor(hot)
            gc.setAlpha(55)
            p.setPen(gc)
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                p.drawText(outer.adjusted(dx, dy, dx, dy),
                           Qt.AlignmentFlag.AlignCenter, self._label)
            p.setPen(hot)
        elif self._hovered:
            p.setPen(mid)
        else:
            p.setPen(dim)

        p.drawText(outer, Qt.AlignmentFlag.AlignCenter, self._label)
        p.end()
