"""CRT-style rocker toggle for switching between two labelled views."""

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


class ViewToggle(QWidget):
    """A rocker toggle painted as a single rounded rectangle with two zones.

    Signals
    -------
    mode_changed(str)
        Emitted with the active mode string when the active side changes.
    """

    mode_changed = Signal(str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None, *,
                 left_label: str = "Deadline",
                 right_label: str = "Group",
                 left_mode: str = "deadline",
                 right_mode: str = "group") -> None:
        super().__init__(parent)
        self._label_left = left_label
        self._label_right = right_label
        self._mode_left = left_mode
        self._mode_right = right_mode
        self._mode: str = self._mode_left  # default active side
        self._hover_side: str | None = None  # which side the cursor is over

        # Auto-size width from label text
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(font)
        left_w = fm.horizontalAdvance(left_label) + 24
        right_w = fm.horizontalAdvance(right_label) + 24
        total_w = max(left_w + right_w, 140)

        self.setFixedSize(total_w, 24)
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
        if mode not in (self._mode_left, self._mode_right):
            return
        if mode != self._mode:
            self._mode = mode
            self.update()

    # ------------------------------------------------------------------
    # Size hints
    # ------------------------------------------------------------------
    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return self.size()

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return self.size()

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
            return self._mode_left
        return self._mode_right

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

        # Clip path used for all fills
        from PySide6.QtGui import QPainterPath
        clip = QPainterPath()
        clip.addRoundedRect(outer.adjusted(1, 1, 0, 0), radius, radius)

        # --- hover fill on inactive hovered side ---
        if self._hover_side is not None and self._hover_side != self._mode:
            hover_rect = self._left_rect() if self._hover_side == self._mode_left else self._right_rect()
            hx = hover_rect.center().x()
            hy = hover_rect.center().y()
            hover_grad = QRadialGradient(hx, hy, max(hover_rect.width(), hover_rect.height()) * 0.8)
            hover_grad.setColorAt(0.0, QColor(240, 168, 48, 36))
            hover_grad.setColorAt(1.0, QColor(240, 168, 48, 0))
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_grad)
            p.drawRect(hover_rect)
            p.restore()

        # --- active side fill (radial glow) ---
        active_rect = self._left_rect() if self._mode == self._mode_left else self._right_rect()
        cx = active_rect.center().x()
        cy = active_rect.center().y()
        grad = QRadialGradient(cx, cy, max(active_rect.width(), active_rect.height()) * 0.8)
        grad.setColorAt(0.0, QColor(240, 168, 48, 80))
        grad.setColorAt(1.0, QColor(240, 168, 48, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.save()
        p.setClipPath(clip)
        p.drawRect(active_rect)
        p.restore()

        # --- bloom halo on active side ---
        bloom = QRadialGradient(cx, cy, max(active_rect.width(), active_rect.height()) * 0.5)
        bloom.setColorAt(0.0, QColor(240, 168, 48, 40))
        bloom.setColorAt(0.6, QColor(240, 168, 48, 14))
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
            (self._mode_left, self._label_left, self._left_rect()),
            (self._mode_right, self._label_right, self._right_rect()),
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
                p.setPen(QColor(PHOSPHOR_MID))
            else:
                p.setPen(QColor("#4A3010"))

            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        p.end()
