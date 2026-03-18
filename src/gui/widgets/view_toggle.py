"""CRT-style rocker toggle for switching between two or more labelled views."""

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
    """A rocker toggle painted as a single rounded rectangle with N equal segments.

    Supports 2 or more segments. When ``segments`` is provided it takes
    precedence over the legacy ``left_label / right_label / left_mode /
    right_mode`` keyword arguments (which remain for backward compatibility).

    Signals
    -------
    mode_changed(str)
        Emitted with the active mode string when the active segment changes.
    """

    mode_changed = Signal(str)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None, *,
                 left_label: str = "Deadline",
                 right_label: str = "Group",
                 left_mode: str = "deadline",
                 right_mode: str = "group",
                 segments: list | None = None) -> None:
        super().__init__(parent)

        if segments is not None:
            self._segments: list[tuple[str, str]] = list(segments)
        else:
            self._segments = [
                (left_label, left_mode),
                (right_label, right_mode),
            ]

        self._mode: str = self._segments[0][1]   # default to first segment
        self._hover_idx: int | None = None

        # Auto-size width from label text
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(font)
        seg_widths = [fm.horizontalAdvance(lbl) + 40 for lbl, _ in self._segments]
        total_w = max(sum(seg_widths), 180)

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
        if mode not in (m for _, m in self._segments):
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
    def _segment_rect(self, i: int) -> QRect:
        n = len(self._segments)
        seg_w = self.width() // n
        x = i * seg_w
        # Last segment absorbs any rounding remainder
        w = self.width() - x if i == n - 1 else seg_w
        return QRect(x, 0, w, self.height())

    def _idx_at(self, pos: QPoint) -> int:
        n = len(self._segments)
        seg_w = self.width() // n
        return max(0, min(pos.x() // seg_w, n - 1))

    def _side_at(self, pos: QPoint) -> str:
        """Return the mode string for the segment under ``pos``."""
        return self._segments[self._idx_at(pos)][1]

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            idx = self._idx_at(event.position().toPoint())
            mode = self._segments[idx][1]
            if mode != self._mode:
                self._mode = mode
                self.update()
                self.mode_changed.emit(self._mode)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        idx = self._idx_at(event.position().toPoint())
        if idx != self._hover_idx:
            self._hover_idx = idx
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_idx = None
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
        n = len(self._segments)
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

        # Active segment index
        active_idx = next(
            (i for i, (_, m) in enumerate(self._segments) if m == self._mode), 0
        )

        # --- hover fill on inactive hovered segment ---
        if self._hover_idx is not None and self._hover_idx != active_idx:
            hover_rect = self._segment_rect(self._hover_idx)
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

        # --- active segment fill (radial glow) ---
        active_rect = self._segment_rect(active_idx)
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

        # --- bloom halo on active segment ---
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

        # --- dividers between segments ---
        seg_w = w // n
        p.setPen(QPen(QColor("#2A1A04"), 1.0))
        for i in range(1, n):
            x = i * seg_w
            p.drawLine(x, 2, x, h - 3)

        # --- text for each segment ---
        font = QFont()
        font.setPixelSize(11)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        for i, (label, mode) in enumerate(self._segments):
            rect = self._segment_rect(i)
            is_active = self._mode == mode
            is_hovered = self._hover_idx == i and not is_active

            if is_active:
                # Subtle glow behind text
                glow_color = QColor(PHOSPHOR_HOT)
                glow_color.setAlpha(60)
                p.setPen(glow_color)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(rect.adjusted(dx, dy, dx, dy), Qt.AlignmentFlag.AlignCenter, label)
                p.setPen(QColor(PHOSPHOR_HOT))
            elif is_hovered:
                p.setPen(QColor(PHOSPHOR_MID))
            else:
                p.setPen(QColor("#4A3010"))

            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        p.end()
