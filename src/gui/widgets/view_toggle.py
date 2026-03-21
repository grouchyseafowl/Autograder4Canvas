"""CRT-style rocker toggle for switching between two or more labelled views.

Matches the CRT phosphor aesthetic used by CRTComboBox: rounded shape
(radius 6), radial-gradient background with warm depth, bottom glow line,
and 34 px height.

Each segment can have its own accent color via the ``segment_colors``
parameter, creating a colored-backlight effect as if analog bulbs of
different hues sit behind the screen.
"""

from PySide6.QtCore import QPoint, QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QMouseEvent,
    QPainter,
    QPainterPath,
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

# Rose accent palette
ROSE_HOT = "#FF6090"
ROSE_MID = "#CC5282"
ROSE_DIM = "#4A2030"
ROSE_BORDER = "#C85080"

_HEIGHT = 34
_RADIUS = 6.0
_FONT_PX = 12

# ---------------------------------------------------------------------------
# Preset color tuples: (r, g, b, hot_hex, mid_hex, dim_hex, border_hex)
# ---------------------------------------------------------------------------
_PRESETS = {
    "amber": (240, 168, 48,  "#F0A830", "#A06A10", "#4A3010", "#6A4A12"),
    "rose":  (255, 96,  144, "#FF6090", "#CC5282", "#4A2030", "#C85080"),
    "blue":  (120, 180, 220, "#78B4DC", "#5A8AA8", "#2A3E50", "#4A7A9A"),
}


def _preset(name: str) -> tuple:
    return _PRESETS.get(name, _PRESETS["amber"])


class ViewToggle(QWidget):
    """A rocker toggle painted as a single rounded rectangle with N equal segments.

    Supports 2 or more segments. When ``segments`` is provided it takes
    precedence over the legacy ``left_label / right_label / left_mode /
    right_mode`` keyword arguments (which remain for backward compatibility).

    Parameters
    ----------
    segment_colors : list[str] | None
        Per-segment accent names (e.g. ``["amber", "blue", "rose"]``).
        When provided, each segment uses its own color for glow, text,
        and border effects.  Falls back to ``accent`` for any missing entry.

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
                 segments: list | None = None,
                 accent: str = "amber",
                 segment_colors: list | None = None) -> None:
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
        self._accent: str = accent  # fallback accent

        # Per-segment color presets
        n = len(self._segments)
        if segment_colors and len(segment_colors) == n:
            self._seg_colors = [_preset(c) for c in segment_colors]
        else:
            self._seg_colors = [_preset(accent)] * n

        # Auto-size width from label text — generous padding per segment
        font = QFont("Menlo")
        font.setPixelSize(_FONT_PX)
        font.setWeight(QFont.Weight.Medium)
        fm = QFontMetrics(font)
        seg_widths = [fm.horizontalAdvance(lbl) + 48 for lbl, _ in self._segments]
        total_w = max(sum(seg_widths), 200)

        from PySide6.QtWidgets import QSizePolicy
        self.setFixedHeight(_HEIGHT)
        self.setMinimumWidth(total_w)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
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
        return QSize(self.minimumWidth(), _HEIGHT)

    def minimumSizeHint(self) -> QSize:  # noqa: N802
        return QSize(self.minimumWidth(), _HEIGHT)

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
    # Painting  — CRT colored-backlight aesthetic
    # ------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        n = len(self._segments)

        # Active segment index
        active_idx = next(
            (i for i, (_, m) in enumerate(self._segments) if m == self._mode), 0
        )

        # Active segment's color drives the border + bottom glow
        ar, ag, ab, a_hot, a_mid, a_dim, a_border = self._seg_colors[active_idx]

        any_hover = self._hover_idx is not None

        # ── Outer rounded shape ────────────────────────────────────────
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), _RADIUS, _RADIUS)

        # ── Background: deep warm void ─────────────────────────────────
        bg = QRadialGradient(w * 0.5, h * 0.42, w * 0.8)
        bg.setColorAt(0.0, QColor(24, 18, 8))
        bg.setColorAt(0.5, QColor(16, 12, 4))
        bg.setColorAt(1.0, QColor(14, 10, 2))
        p.setClipPath(shape)
        p.fillRect(0, 0, w, h, bg)
        p.setClipping(False)

        # ── Border: constant neutral (color comes from interior glow) ──
        p.setPen(QPen(QColor(50, 40, 20, 120), 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(shape)

        # Interior clip
        clip = QPainterPath()
        clip.addRoundedRect(QRectF(1, 1, w - 2, h - 2), _RADIUS - 0.5, _RADIUS - 0.5)

        # ── Hover glow on inactive hovered segment ────────────────────
        if self._hover_idx is not None and self._hover_idx != active_idx:
            hi = self._hover_idx
            hr, hg, hb = self._seg_colors[hi][:3]
            hover_rect = self._segment_rect(hi)
            hx = hover_rect.center().x()
            hy = hover_rect.center().y()
            hover_grad = QRadialGradient(
                hx, hy, max(hover_rect.width(), hover_rect.height()) * 0.8
            )
            hover_grad.setColorAt(0.0, QColor(hr, hg, hb, 40))
            hover_grad.setColorAt(0.6, QColor(hr, hg, hb, 12))
            hover_grad.setColorAt(1.0, QColor(hr, hg, hb, 0))
            p.save()
            p.setClipPath(clip)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hover_grad)
            p.drawRect(hover_rect)
            p.restore()

        # ── Active segment: analog backlight glow ──────────────────────
        # Simulates a colored bulb behind the CRT screen — the glow
        # bleeds outward from the center of the segment, fading at edges.
        active_rect = self._segment_rect(active_idx)
        cx = active_rect.center().x()
        cy = active_rect.center().y()
        dim = max(active_rect.width(), active_rect.height())

        p.save()
        p.setClipPath(clip)
        p.setPen(Qt.PenStyle.NoPen)

        # Layer 1: wide ambient wash (simulates light scattering in glass)
        wash = QRadialGradient(cx, cy * 0.9, dim * 1.0)
        wash.setColorAt(0.0, QColor(ar, ag, ab, 50))
        wash.setColorAt(0.4, QColor(ar, ag, ab, 20))
        wash.setColorAt(0.8, QColor(ar, ag, ab, 5))
        wash.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setBrush(wash)
        p.drawRect(active_rect)

        # Layer 2: concentrated bulb hotspot (slightly above center)
        hotspot = QRadialGradient(cx, cy * 0.75, dim * 0.45)
        hotspot.setColorAt(0.0, QColor(ar, ag, ab, 70))
        hotspot.setColorAt(0.3, QColor(ar, ag, ab, 35))
        hotspot.setColorAt(0.7, QColor(ar, ag, ab, 10))
        hotspot.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setBrush(hotspot)
        p.drawRect(active_rect)

        # Layer 3: tiny bright filament core
        filament = QRadialGradient(cx, cy * 0.7, dim * 0.22)
        filament.setColorAt(0.0, QColor(ar, ag, ab, 45))
        filament.setColorAt(0.5, QColor(ar, ag, ab, 12))
        filament.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setBrush(filament)
        p.drawRect(active_rect)

        p.restore()

        # ── Bottom glow line: active segment's color bleeds along base ─
        glow_line = QLinearGradient(0, h - 1, w, h - 1)
        # The glow concentrates under the active segment
        seg_w_f = w / n
        active_start = active_idx * seg_w_f / w
        active_end = (active_idx + 1) * seg_w_f / w
        active_mid = (active_start + active_end) / 2
        # Clamp gradient stops
        fade_start = max(0.0, active_start - 0.08)
        fade_end = min(1.0, active_end + 0.08)
        glow_alpha = 80 if any_hover else 60
        glow_line.setColorAt(0.0, QColor(ar, ag, ab, 0))
        if fade_start > 0.01:
            glow_line.setColorAt(fade_start, QColor(ar, ag, ab, 0))
        glow_line.setColorAt(active_mid, QColor(ar, ag, ab, glow_alpha))
        if fade_end < 0.99:
            glow_line.setColorAt(fade_end, QColor(ar, ag, ab, 0))
        glow_line.setColorAt(1.0, QColor(ar, ag, ab, 0))
        p.setPen(QPen(glow_line, 2.0))
        p.drawLine(1, h - 1, w - 1, h - 1)

        # (No divider lines — the glow contrast is sufficient)

        # ── Text labels ───────────────────────────────────────────────
        font = QFont("Menlo")
        font.setPixelSize(_FONT_PX)
        font.setWeight(QFont.Weight.Medium)
        p.setFont(font)

        for i, (label, mode) in enumerate(self._segments):
            rect = self._segment_rect(i)
            is_active = self._mode == mode
            is_hovered = self._hover_idx == i and not is_active

            # Each segment uses its own color
            _r, _g, _b, s_hot, s_mid, s_dim, _ = self._seg_colors[i]

            if is_active:
                # Text glow (bloom behind text) — colored by this segment
                glow_color = QColor(s_hot)
                glow_color.setAlpha(55)
                p.setPen(glow_color)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    p.drawText(rect.adjusted(dx, dy, dx, dy),
                               Qt.AlignmentFlag.AlignCenter, label)
                p.setPen(QColor(s_hot))
            elif is_hovered:
                p.setPen(QColor(s_mid))
            else:
                p.setPen(QColor(s_dim))

            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, label)

        p.end()
