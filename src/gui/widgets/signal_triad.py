"""
SignalTriad — three horizontal score bars with CRT phosphor glow.

Displays suspicion, authenticity, and human-presence scores as
coloured fill bars with a bloom edge, consistent with the amber
terminal aesthetic used throughout the Prior Runs panel.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QSize, QRectF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont,
    QRadialGradient, QLinearGradient, QPainterPath,
)

from gui.styles import BG_INSET, BORDER_DARK, PHOSPHOR_DIM


# ──────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lerp_color(c0: tuple, c1: tuple, t: float) -> QColor:
    """Linear interpolate between two RGB tuples at parameter t (0–1)."""
    t = max(0.0, min(1.0, t))
    r = int(c0[0] + (c1[0] - c0[0]) * t)
    g = int(c0[1] + (c1[1] - c0[1]) * t)
    b = int(c0[2] + (c1[2] - c0[2]) * t)
    return QColor(r, g, b)


# Named colour stops (RGB tuples)
_TEAL     = (88, 200, 184)
_AMBER    = (240, 168, 48)
_BURN_RED = (192, 64, 32)
_TERM_GRN = (114, 184, 90)


def _suspicion_color(v: float) -> QColor:
    """teal → amber → red as suspicion rises (0→1)."""
    if v <= 0.4:
        return _lerp_color(_TEAL, _AMBER, v / 0.4)
    return _lerp_color(_AMBER, _BURN_RED, (v - 0.4) / 0.6)


def _authenticity_color(v: float) -> QColor:
    """red → amber → green — high value is good."""
    if v <= 0.5:
        return _lerp_color(_BURN_RED, _AMBER, v / 0.5)
    return _lerp_color(_AMBER, _TERM_GRN, (v - 0.5) / 0.5)


# ──────────────────────────────────────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────────────────────────────────────

class SignalTriad(QWidget):
    """Three horizontal phosphor score bars.

    Call set_scores() to populate; the widget repaints automatically.
    """

    _LABEL_W  = 110   # px reserved for right-aligned label text
    _VALUE_W  = 52    # px reserved for right-aligned value text
    _BAR_H    = 22
    _GAP      = 5
    _Y_START  = 4
    _HEIGHT   = _Y_START + 3 * (_BAR_H + _GAP) + 4

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suspicion:     float = 0.0
        self._authenticity:  float = 0.0
        self._human:         Optional[float] = None
        self._concern:       str = "none"
        self.setFixedHeight(self._HEIGHT)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )

    def set_scores(
        self,
        suspicion: float,
        authenticity: float,
        human_presence,
        concern_level: str = "none",
    ) -> None:
        self._suspicion    = float(suspicion or 0.0)
        self._authenticity = float(authenticity or 0.0)
        self._human        = float(human_presence) if human_presence is not None else None
        self._concern      = concern_level or "none"
        self.update()

    def sizeHint(self) -> QSize:
        return QSize(300, self._HEIGHT)

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        lw = self._LABEL_W
        vw = self._VALUE_W
        bar_x = lw + 8
        bar_w = max(20, w - bar_x - vw - 8)

        bars = [
            ("SUSPICION",      self._suspicion,    _suspicion_color(self._suspicion),    self._fmt_suspicion()),
            ("AUTHENTICITY",   self._authenticity,  _authenticity_color(self._authenticity), self._fmt_authenticity()),
            ("HUMAN PRESENCE", (self._human or 0.0) / 100.0, _authenticity_color((self._human or 0.0) / 100.0), self._fmt_human()),
        ]

        font = QFont("Menlo", 11)
        font_b = QFont("Menlo", 11)
        font_b.setBold(True)

        track_bg  = QColor(BG_INSET)
        track_bdr = QColor(BORDER_DARK)
        label_col = QColor(PHOSPHOR_DIM)

        for i, (label, frac, bar_color, val_text) in enumerate(bars):
            by = self._Y_START + i * (self._BAR_H + self._GAP)
            bcy = by + self._BAR_H / 2

            # 1. Label (right-aligned in lw area)
            p.setFont(font)
            p.setPen(label_col)
            p.drawText(
                int(0), int(by), int(lw), int(self._BAR_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                label,
            )

            # 2. Bar track
            track_rect = QRectF(bar_x, by + 2, bar_w, self._BAR_H - 4)
            track_path = QPainterPath()
            track_path.addRoundedRect(track_rect, 3, 3)
            p.fillPath(track_path, track_bg)
            p.setPen(QPen(track_bdr, 1))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(track_path)

            # 3. Bar fill gradient (clipped to track)
            fill_w = max(0.0, frac * bar_w)
            if fill_w > 1:
                fill_grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
                r, g, b = bar_color.red(), bar_color.green(), bar_color.blue()
                fill_grad.setColorAt(0.0, QColor(r, g, b, 180))
                bloom_stop = max(0.0, min(1.0, frac - 0.05))
                fill_grad.setColorAt(bloom_stop, QColor(r, g, b, 220))
                fill_grad.setColorAt(min(1.0, frac), QColor(r, g, b, 60))
                if frac < 1.0:
                    fill_grad.setColorAt(min(1.0, frac + 0.001), QColor(r, g, b, 0))

                fill_rect = QRectF(bar_x, by + 2, fill_w, self._BAR_H - 4)
                fill_path = QPainterPath()
                fill_path.addRoundedRect(fill_rect, 3, 3)
                # Clip to track boundary
                clipped = fill_path.intersected(track_path)
                p.setPen(Qt.PenStyle.NoPen)
                p.fillPath(clipped, fill_grad)

                # 4. Glow at fill edge
                glow_cx = bar_x + fill_w
                glow_r  = self._BAR_H * 1.2
                glow = QRadialGradient(glow_cx, bcy, glow_r)
                glow.setColorAt(0.0, QColor(r, g, b, 55))
                glow.setColorAt(1.0, QColor(r, g, b, 0))
                p.save()
                p.setClipPath(track_path)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(glow)
                p.drawEllipse(
                    int(glow_cx - glow_r), int(bcy - glow_r),
                    int(glow_r * 2), int(glow_r * 2),
                )
                p.restore()

            # 5. Value text (right-aligned in value area)
            p.setFont(font_b)
            p.setPen(bar_color)
            p.drawText(
                int(bar_x + bar_w + 4), int(by), int(vw), int(self._BAR_H),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                val_text,
            )

        p.end()

    def _fmt_suspicion(self) -> str:
        return f"{self._suspicion:.2f}"

    def _fmt_authenticity(self) -> str:
        return f"{self._authenticity:.2f}"

    def _fmt_human(self) -> str:
        if self._human is None:
            return "—"
        return f"{self._human:.0f}%"
