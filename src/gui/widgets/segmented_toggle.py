"""SegmentedToggle — N-segment mutually-exclusive rocker.

Rose (pink) accent for AIC mode selector.
Amber accent available for general use.

Height matches OptionRocker (44 px) so the two widgets sit flush
when placed in the same layout.
"""

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QRadialGradient,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from gui.styles import PHOSPHOR_HOT, PHOSPHOR_MID, BORDER_AMBER, BG_INSET

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
_ROSE_HOT  = QColor("#FF6090")
_ROSE_MID  = QColor("#CC5282")
_ROSE_DIM  = QColor("#4A2030")
_ROSE_BDR  = QColor(200, 80, 120, 180)
_ROSE_RGB  = (255, 96, 144)

_AMBER_HOT = QColor(PHOSPHOR_HOT)
_AMBER_MID = QColor(PHOSPHOR_MID)
_AMBER_DIM = QColor("#4A3010")
_AMBER_BDR = QColor(BORDER_AMBER)
_AMBER_RGB = (240, 168, 48)

_HEIGHT    = 40
_RADIUS    = 5
_FONT_PX   = 11


class SegmentedToggle(QWidget):
    """N-segment mutually-exclusive rocker toggle.

    Parameters
    ----------
    *options : (label: str, mode: str) tuples
    accent   : "rose" | "amber"  (default "rose")
    """

    mode_changed = Signal(str)

    def __init__(self, *options, accent: str = "rose", parent=None):
        super().__init__(parent)
        self._options: list = list(options)
        self._mode: str     = options[0][1]
        self._hover_idx: int | None = None
        self._accent = accent

        font = QFont("Menlo")
        font.setPixelSize(_FONT_PX)
        font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(font)
        # Base segment width on the full label so text fits on one line
        seg_min = max(
            fm.horizontalAdvance(lbl) + 28
            for lbl, _ in options
        )
        total_w = seg_min * len(options)

        self.setFixedHeight(_HEIGHT)
        self.setMinimumWidth(total_w)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── Public API ────────────────────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        if mode != self._mode and any(m == mode for _, m in self._options):
            self._mode = mode
            self.update()

    def sizeHint(self) -> QSize:
        return QSize(self.minimumWidth(), _HEIGHT)

    # ── Interaction ───────────────────────────────────────────────────────────
    def _idx_at(self, x: int) -> int:
        n = len(self._options)
        return max(0, min(int(x / (self.width() / n)), n - 1))

    def _seg_rect(self, idx: int) -> QRect:
        n   = len(self._options)
        sw  = self.width() / n
        return QRect(int(idx * sw), 0,
                     int((idx + 1) * sw) - int(idx * sw), self.height())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            new = self._options[self._idx_at(event.position().toPoint().x())][1]
            if new != self._mode:
                self._mode = new
                self.update()
                self.mode_changed.emit(self._mode)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        idx = self._idx_at(event.position().toPoint().x())
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_idx = None
        self.update()
        super().leaveEvent(event)

    # ── Painting ──────────────────────────────────────────────────────────────
    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h  = self.width(), self.height()
        n     = len(self._options)

        if self._accent == "rose":
            hot, mid, dim = _ROSE_HOT, _ROSE_MID, _ROSE_DIM
            bdr = _ROSE_BDR
            rgb = _ROSE_RGB
            div = QColor("#2A0A14")
        else:
            hot, mid, dim = _AMBER_HOT, _AMBER_MID, _AMBER_DIM
            bdr = _AMBER_BDR
            rgb = _AMBER_RGB
            div = QColor("#2A1A04")

        outer = QRect(0, 0, w - 1, h - 1)
        p.setPen(QPen(bdr, 1.5))
        p.setBrush(QColor(BG_INSET))
        p.drawRoundedRect(outer, _RADIUS, _RADIUS)

        clip = QPainterPath()
        clip.addRoundedRect(outer.adjusted(1, 1, 0, 0), _RADIUS, _RADIUS)

        for idx, (_, mode) in enumerate(self._options):
            rect     = self._seg_rect(idx)
            active   = mode == self._mode
            hovered  = self._hover_idx == idx and not active
            cx, cy   = rect.center().x(), rect.center().y()
            dim_size = max(rect.width(), rect.height())
            r, g, b  = rgb

            if active:
                grad = QRadialGradient(cx, cy, dim_size * 0.8)
                grad.setColorAt(0.0, QColor(r, g, b, 90))
                grad.setColorAt(1.0, QColor(r, g, b, 0))
                p.save()
                p.setClipPath(clip)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(grad)
                p.drawRect(rect)
                bloom = QRadialGradient(cx, cy, dim_size * 0.5)
                bloom.setColorAt(0.0, QColor(r, g, b, 50))
                bloom.setColorAt(0.6, QColor(r, g, b, 18))
                bloom.setColorAt(1.0, QColor(r, g, b, 0))
                p.setBrush(bloom)
                p.drawRect(rect)
                p.restore()
            elif hovered:
                hg = QRadialGradient(cx, cy, dim_size * 0.8)
                hg.setColorAt(0.0, QColor(r, g, b, 40))
                hg.setColorAt(1.0, QColor(r, g, b, 0))
                p.save()
                p.setClipPath(clip)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(hg)
                p.drawRect(rect)
                p.restore()

        # Dividers
        for i in range(1, n):
            p.setPen(QPen(div, 1.0))
            p.drawLine(int(i * w / n), 3, int(i * w / n), h - 4)

        # Labels
        font = QFont("Menlo")
        font.setPixelSize(_FONT_PX)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        for idx, (label, mode) in enumerate(self._options):
            rect    = self._seg_rect(idx)
            active  = mode == self._mode
            hovered = self._hover_idx == idx and not active

            if active:
                gc = QColor(hot)
                gc.setAlpha(60)
                p.setPen(gc)
                _flags = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(rect.adjusted(dx, dy, dx, dy), _flags, label)
                p.setPen(hot)
            elif hovered:
                p.setPen(mid)
            else:
                p.setPen(dim)

            p.drawText(rect,
                       Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap,
                       label)

        p.end()
