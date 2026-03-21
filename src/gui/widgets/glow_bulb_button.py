"""
GlowBulbButton — an illuminated pushbutton with analog-bulb backlight.

Designed for high-visibility action buttons (e.g. "Run AIC") that need to
stand out against the CRT amber terminal aesthetic without clashing.

Visual language:
  - Dark inset body with subtle bevel (like a physical recessed button)
  - Baby-blue phosphor text
  - Radial glow halo painted *behind* the button body, as though a backlit
    bulb shines through the bezel gap
  - Hover intensifies the halo; press triggers a brief flash
  - Border picks up the warm amber of the CRT surround

The button is entirely custom-painted (no QSS) so the glow can bleed
outside the button rect via the ``_MARGIN`` padding.
"""

from PySide6.QtCore import (
    QPropertyAnimation,
    QRectF,
    QSize,
    Qt,
    Property,
)
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QRadialGradient,
)
from PySide6.QtWidgets import QPushButton, QGraphicsDropShadowEffect

# ---------------------------------------------------------------------------
# Palette constants (self-contained for portability)
# ---------------------------------------------------------------------------
_BABY_BLUE      = QColor(126, 200, 227)       # #7EC8E3 — text + glow
_BABY_BLUE_HOT  = QColor(170, 225, 248)       # brighter blue for hover text
_BABY_BLUE_DIM  = QColor(80, 140, 170)        # dimmed blue for disabled
_BG_INSET       = QColor(14, 10, 2)           # #0E0A02
_BG_BEVEL_TOP   = QColor(26, 22, 8)           # lighter lip (top bevel)
_BG_BEVEL_BOT   = QColor(8, 6, 1)             # shadow lip  (bottom bevel)
_BORDER_AMBER   = QColor(106, 74, 18)         # #6A4A12
_BORDER_REST    = QColor(70, 50, 12, 140)     # subdued amber border at rest

# Glow intensities (alpha 0–255)
_GLOW_REST      = 55
_GLOW_HOVER     = 120
_GLOW_FLASH     = 210

# Layout
_MARGIN   = 10     # extra paint margin around the body for the halo bleed
_RADIUS   = 6.0    # body corner radius
_FONT_PX  = 13

# Flash animation duration (ms)
_FLASH_MS = 180


class GlowBulbButton(QPushButton):
    """Illuminated pushbutton with baby-blue backlit-bulb glow.

    Drop-in replacement for QPushButton — just instantiate with label text.
    The glow extends a few pixels outside the widget's logical rect, handled
    by reserving ``_MARGIN`` of internal padding.
    """

    # ── construction ──────────────────────────────────────────────────────

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)

        # Animated glow strength (0.0 – 1.0) used during flash
        self._glow_strength: float = 0.0
        self._hovered = False

        # Flash animation
        self._flash_anim = QPropertyAnimation(self, b"glowStrength")
        self._flash_anim.setDuration(_FLASH_MS)

        # Outer drop shadow (complements the painted radial glow)
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(18)
        self._shadow.setOffset(0, 0)
        self._shadow.setColor(QColor(126, 200, 227, _GLOW_REST))
        self.setGraphicsEffect(self._shadow)

        # Font
        self._font = QFont("Menlo", _FONT_PX)
        self._font.setStyleHint(QFont.StyleHint.Monospace)
        self._font.setWeight(QFont.Weight.DemiBold)

    # ── Qt property for animation ─────────────────────────────────────────

    def _get_glow(self) -> float:
        return self._glow_strength

    def _set_glow(self, v: float) -> None:
        self._glow_strength = v
        self.update()

    glowStrength = Property(float, _get_glow, _set_glow)

    # ── size hint ─────────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self._font)
        tw = fm.horizontalAdvance(self.text()) + 2 * 18  # padding
        th = fm.height() + 2 * 8
        return QSize(tw + 2 * _MARGIN, th + 2 * _MARGIN)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    # ── events ────────────────────────────────────────────────────────────

    def enterEvent(self, event):
        self._hovered = True
        self._shadow.setColor(QColor(126, 200, 227, _GLOW_HOVER))
        self._shadow.setBlurRadius(24)
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self._hovered = False
        self._shadow.setColor(QColor(126, 200, 227, _GLOW_REST))
        self._shadow.setBlurRadius(18)
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        # Trigger flash: ramp up instantly, then decay
        self._flash_anim.stop()
        self._flash_anim.setStartValue(1.0)
        self._flash_anim.setEndValue(0.0)
        self._flash_anim.start()
        super().mousePressEvent(event)

    # ── painting ──────────────────────────────────────────────────────────

    def paintEvent(self, _event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        disabled = not self.isEnabled()

        # Body rect (inset from the paint margin)
        body = QRectF(_MARGIN, _MARGIN, w - 2 * _MARGIN, h - 2 * _MARGIN)

        # ── 1. Radial glow halo (painted behind the body) ────────────────
        if not disabled:
            cx = w / 2
            cy = h / 2
            # Blend between rest, hover, and flash intensities
            if self._glow_strength > 0:
                alpha = int(_GLOW_FLASH * self._glow_strength
                            + (_GLOW_HOVER if self._hovered else _GLOW_REST)
                            * (1.0 - self._glow_strength))
            elif self._hovered:
                alpha = _GLOW_HOVER
            else:
                alpha = _GLOW_REST

            glow_radius = max(w, h) * 0.75
            glow = QRadialGradient(cx, cy, glow_radius)
            glow.setColorAt(0.0, QColor(126, 200, 227, alpha))
            glow.setColorAt(0.45, QColor(126, 200, 227, alpha // 3))
            glow.setColorAt(1.0, QColor(126, 200, 227, 0))

            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            # Paint an ellipse larger than the body to let the glow bleed
            glow_rect = body.adjusted(-_MARGIN, -_MARGIN, _MARGIN, _MARGIN)
            p.drawEllipse(glow_rect)

        # ── 2. Button body (dark inset with bevel) ───────────────────────
        body_path = QPainterPath()
        body_path.addRoundedRect(body, _RADIUS, _RADIUS)

        # Top bevel highlight
        bevel_top = QLinearGradient(body.topLeft(), body.bottomLeft())
        bevel_top.setColorAt(0.0, _BG_BEVEL_TOP)
        bevel_top.setColorAt(0.08, _BG_INSET)
        bevel_top.setColorAt(0.92, _BG_INSET)
        bevel_top.setColorAt(1.0, _BG_BEVEL_BOT)
        p.fillPath(body_path, bevel_top)

        # ── 3. Inner radial glow on the body surface (subtle bulb bloom) ─
        if not disabled:
            inner_alpha = alpha // 4 if not disabled else 0
            inner = QRadialGradient(body.center().x(), body.center().y(),
                                    body.width() * 0.6)
            inner.setColorAt(0.0, QColor(126, 200, 227, inner_alpha))
            inner.setColorAt(0.7, QColor(126, 200, 227, inner_alpha // 4))
            inner.setColorAt(1.0, QColor(126, 200, 227, 0))
            p.fillPath(body_path, inner)

        # ── 4. Border ────────────────────────────────────────────────────
        border_color = _BORDER_AMBER if (self._hovered or self._glow_strength > 0.1) else _BORDER_REST
        if disabled:
            border_color = QColor(50, 36, 10, 80)
        p.setPen(border_color)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(body, _RADIUS, _RADIUS)

        # ── 5. Pressed inset — shift text 1px down-right on click ────────
        pressed = self.isDown()
        text_offset_x = 1 if pressed else 0
        text_offset_y = 1 if pressed else 0

        # ── 6. Text ──────────────────────────────────────────────────────
        p.setFont(self._font)
        if disabled:
            p.setPen(_BABY_BLUE_DIM)
        elif self._hovered or self._glow_strength > 0.1:
            p.setPen(_BABY_BLUE_HOT)
        else:
            p.setPen(_BABY_BLUE)

        text_rect = body.adjusted(0, text_offset_y, text_offset_x, 0)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.text())

        # ── 7. Scanline overlay (faint horizontal lines for CRT texture) ─
        if not disabled:
            p.save()
            p.setClipPath(body_path)
            scanline_pen = QColor(0, 0, 0, 18)
            p.setPen(scanline_pen)
            y = int(body.top()) + 2
            while y < int(body.bottom()):
                p.drawLine(int(body.left()), y, int(body.right()), y)
                y += 3
            p.restore()

        p.end()
