"""
Reusable SwitchTrack + SwitchToggle widgets — shared across the GUI.

Extracted from assignment_panel.py so that run_dialog.py (and any future panel)
can import them without pulling in the entire assignment panel module.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QBrush, QRadialGradient

from gui.styles import (
    PHOSPHOR_HOT, PHOSPHOR_MID,
    apply_phosphor_glow, remove_glow,
)


class SwitchTrack(QWidget):
    """Painted sliding-pill track — 36 × 20 px."""

    _W, _H = 36, 20

    def __init__(self, hover_color: QColor = None, parent=None):
        super().__init__(parent)
        self._on = False
        self._hovered = False
        # Default hover: amber
        self._hover_fill   = hover_color or QColor(240, 168, 48, 45)
        self._hover_border = QColor(
            hover_color.red(), hover_color.green(), hover_color.blue(), 180
        ) if hover_color else QColor(240, 168, 48, 180)
        self._hover_knob   = hover_color or QColor(240, 168, 48)
        # Resting state: faded version of hover_color, or default amber
        if hover_color:
            r, g, b = hover_color.red() // 2, hover_color.green() // 2, hover_color.blue() // 2
            self._rest_knob   = QColor(r, g, b)
            self._rest_fill   = QColor(r, g, b, 100)
            self._rest_border = QColor(r, g, b, 140)
        else:
            self._rest_knob   = QColor(90, 62, 14)
            self._rest_fill   = QColor(58, 40, 8, 160)
            self._rest_border = QColor(106, 74, 18)
        self.setFixedSize(self._W, self._H)

    def set_on(self, v: bool) -> None:
        self._on = v
        self.update()

    def set_hovered(self, v: bool) -> None:
        self._hovered = v
        self.update()

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self._W, self._H
        r = h / 2

        knob_d  = h - 6
        knob_x  = w - knob_d - 4 if self._on else 4
        knob_cx = knob_x + knob_d / 2
        knob_cy = h / 2

        # Three intensity levels — like a CRT indicator light:
        #   hovered   → full 100% (interactive, responsive)
        #   on-rest   → calm 65% (status: confirmed but not demanding attention)
        #   off-rest  → dim  (available but inactive)
        if self._hovered:
            knob_color   = self._hover_knob
            track_alpha  = 55
            bloom_alpha  = 55
            bloom_mid    = 16
        elif self._on:
            knob_color   = self._hover_knob
            track_alpha  = 34       # noticeably calmer than hover
            bloom_alpha  = 32
            bloom_mid    = 10
        else:
            knob_color   = self._rest_knob
            track_alpha  = 30
            bloom_alpha  = 0
            bloom_mid    = 0

        r_, g_, b_ = knob_color.red(), knob_color.green(), knob_color.blue()

        track = QPainterPath()
        track.addRoundedRect(0.5, 0.5, w - 1, h - 1, r, r)

        # Track fill: radial bloom concentrated at knob position (not centred)
        track_fill = QRadialGradient(knob_cx, knob_cy, h * 1.4)
        track_fill.setColorAt(0.0, QColor(r_, g_, b_, track_alpha))
        track_fill.setColorAt(1.0, QColor(r_, g_, b_, 0))
        p.fillPath(track, QBrush(track_fill))

        # Track border
        border = self._hover_border if (self._hovered or self._on) else self._rest_border
        p.setPen(border)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(track)

        # Bloom halo around knob — full when hovered, soft when on-rest, absent when off
        if bloom_alpha > 0:
            p.save()
            p.setClipPath(track)
            bloom = QRadialGradient(knob_cx, knob_cy, knob_d * 1.3)
            bloom.setColorAt(0.0, QColor(r_, g_, b_, bloom_alpha))
            bloom.setColorAt(0.6, QColor(r_, g_, b_, bloom_mid))
            bloom.setColorAt(1.0, QColor(r_, g_, b_, 0))
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(bloom))
            bs = knob_d * 2.6
            p.drawEllipse(int(knob_cx - bs / 2), int(knob_cy - bs / 2), int(bs), int(bs))
            p.restore()

        # Knob: phosphor dot — bright hot centre fading to dim edge, like a lit CRT pixel
        p.setPen(Qt.PenStyle.NoPen)
        knob_grad = QRadialGradient(knob_cx, knob_cy - 1, knob_d * 0.5)
        knob_grad.setColorAt(0.0, QColor(min(r_ + 55, 255), min(g_ + 40, 255), min(b_ + 30, 255)))
        knob_grad.setColorAt(0.5, knob_color)
        knob_grad.setColorAt(1.0, QColor(max(r_ - 30, 0), max(g_ - 20, 0), max(b_ - 10, 0)))
        p.setBrush(QBrush(knob_grad))
        p.drawEllipse(int(knob_x), 3, knob_d, knob_d)
        p.end()


class SwitchToggle(QWidget):
    """A labelled toggle switch with two-line wrapping label.

    hover_color: QColor to use for label + track on hover (default: amber).
                 Pass a rose QColor for the AIC toggle.
    """

    toggled = Signal(bool)

    def __init__(self, label: str, wrap_width: int = 115,
                 hover_color: QColor = None, rest_css: str = None, parent=None):
        super().__init__(parent)
        self._checked = False
        self._hovered = False
        # label color when active (hover or checked)
        self._hover_css = (
            f"rgb({hover_color.red()},{hover_color.green()},{hover_color.blue()})"
            if hover_color else PHOSPHOR_HOT
        )
        # hex color for glow effect (QGraphicsDropShadowEffect needs a string)
        self._glow_hex = hover_color.name() if hover_color else PHOSPHOR_HOT
        # label color when resting (unchecked, not hovered)
        self._rest_css = rest_css or PHOSPHOR_MID

        lo = QHBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(7)

        self._track = SwitchTrack(hover_color=hover_color)
        lo.addWidget(self._track, 0, Qt.AlignmentFlag.AlignVCenter)

        self._lbl = QLabel(label)
        self._lbl.setWordWrap(True)
        self._lbl.setFixedWidth(wrap_width)
        self._lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 11px; line-height: 1.35;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._lbl)
        lo.addStretch()

        self.setMinimumWidth(0)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self._refresh()

    def mousePressEvent(self, _event) -> None:
        self.setChecked(not self._checked)
        self.toggled.emit(self._checked)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self._track.set_hovered(True)
        self._refresh()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self._track.set_hovered(False)
        self._refresh()
        super().leaveEvent(event)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, v: bool) -> None:
        self._checked = v
        self._track.set_on(v)
        self._refresh()

    def _refresh(self) -> None:
        if self._hovered:
            color = self._hover_css
            apply_phosphor_glow(self._lbl, color=self._glow_hex, blur=7, strength=0.55)
        elif self._checked:
            # On but not hovered: full color, soft resting glow (calm, not demanding)
            color = self._hover_css
            apply_phosphor_glow(self._lbl, color=self._glow_hex, blur=5, strength=0.22)
        else:
            color = self._rest_css
            remove_glow(self._lbl)
        self._lbl.setStyleSheet(
            f"color: {color}; font-size: 11px; line-height: 1.35;"
            f" background: transparent; border: none;"
        )
