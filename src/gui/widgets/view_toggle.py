"""CRT-style rocker toggle for switching between Deadline and Group views."""

from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import QWidget

# ---------------------------------------------------------------------------
# Palette (self-contained — no imports from styles.py)
# ---------------------------------------------------------------------------
PHOSPHOR_HOT = "#F0A830"
PHOSPHOR_MID = "#A06A10"
PHOSPHOR_DIM = "#5A3C08"
PHOSPHOR_GLOW = "#2E1C06"
BORDER_DARK = "#3A2808"
BORDER_AMBER = "#6A4A12"
BG_INSET = "#0E0A02"

# Labels
_LABEL_LEFT = "\u25C8 Deadline"  # ◈ Deadline
_LABEL_RIGHT = "Group"

# Modes emitted with the signal
_MODE_LEFT = "deadline"
_MODE_RIGHT = "group"


class ViewToggle(QWidget):
    """A rocker toggle painted as a single rounded rectangle with two zones.

    Signals
    -------
    mode_changed(str)
        Emitted with ``"deadline"`` or ``"group"`` when the active side changes.
    """

    mode_changed = Signal(str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._mode: str = _MODE_LEFT  # default active side
        self._hover_side: str | None = None  # which side the cursor is over

        self.setFixedSize(180, 24)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        """Programmatically switch the toggle without emitting a signal."""
        if mode not in (_MODE_LEFT, _MODE_RIGHT):
            return
        if mode != self._mode:
            self._mode = mode
            self.update()

    # ------------------------------------------------------------------
    # Size hints
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(180, 24)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(180, 24)

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _left_rect(self) -> QRect:
        return QRect(0, 0, self.width() // 2, self.height())

    def _right_rect(self) -> QRect:
        half = self.width() // 2
        return QRect(half, 0, self.width() - half, self.height())

    def _side_at(self, pos: QPoint) -> str:
        if pos.x() < self.width() // 2:
            return _MODE_LEFT
        return _MODE_RIGHT

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            clicked = self._side_at(event.position().toPoint())
            if clicked != self._mode:
                self._mode = clicked
                self.update()
                self.mode_changed.emit(self._mode)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        side = self._side_at(event.position().toPoint())
        if side != self._hover_side:
            self._hover_side = side
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_side = None
        self.update()
        super().leaveEvent(event)

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        half = w // 2
        radius = 3

        # --- overall background & border ---
        outer = QRect(0, 0, w - 1, h - 1)
        p.setPen(QPen(QColor(BORDER_AMBER), 1.0))
        p.setBrush(QColor(BG_INSET))
        p.drawRoundedRect(outer, radius, radius)

        # --- active side fill (radial glow) ---
        active_rect = self._left_rect() if self._mode == _MODE_LEFT else self._right_rect()
        cx = active_rect.center().x()
        cy = active_rect.center().y()
        grad = QRadialGradient(cx, cy, max(active_rect.width(), active_rect.height()) * 0.8)
        grad.setColorAt(0.0, QColor(240, 168, 48, 64))   # rgba(240,168,48,0.25)
        grad.setColorAt(1.0, QColor(240, 168, 48, 0))     # fade to transparent
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        # Clip to the rounded rect so the fill doesn't bleed outside
        p.save()
        path = p.clipPath()
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addRoundedRect(outer.adjusted(1, 1, 0, 0), radius, radius)
        p.setClipPath(clip)
        p.drawRect(active_rect)
        p.restore()

        # --- bloom halo on active side ---
        bloom = QRadialGradient(cx, cy, max(active_rect.width(), active_rect.height()) * 0.5)
        bloom.setColorAt(0.0, QColor(240, 168, 48, 30))
        bloom.setColorAt(0.6, QColor(240, 168, 48, 10))
        bloom.setColorAt(1.0, QColor(240, 168, 48, 0))
        p.save()
        p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bloom)
        p.drawRect(active_rect)
        p.restore()

        # --- centre divider ---
        p.setPen(QPen(QColor("#2A1A04"), 1.0))
        p.drawLine(half, 2, half, h - 3)

        # --- text ---
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        fm = QFontMetrics(font)

        for side, label, rect in (
            (_MODE_LEFT, _LABEL_LEFT, self._left_rect()),
            (_MODE_RIGHT, _LABEL_RIGHT, self._right_rect()),
        ):
            is_active = self._mode == side
            is_hovered = self._hover_side == side and not is_active

            if is_active:
                # Subtle glow behind text (draw text twice, blurred layer first)
                glow_color = QColor(PHOSPHOR_HOT)
                glow_color.setAlpha(60)
                p.setPen(glow_color)
                # Offset copies for a cheap "glow" effect
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(rect.adjusted(dx, dy, dx, dy), Qt.AlignmentFlag.AlignCenter, label)
                # Main bright text
                p.setPen(QColor(PHOSPHOR_HOT))
            elif is_hovered:
                p.setPen(QColor(PHOSPHOR_DIM))
            else:
                p.setPen(QColor(BORDER_DARK))

            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        p.end()
