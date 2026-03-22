"""
SignalTriad — Verdict-first engagement signal display.

Replaces three separate equal-weight bars with:
  • A conversation-opportunity badge + personal-connection % on a single header row
  • One "Engagement Spectrum" bar: fill = personal connection (0 → limited, 100 → strong)
    with a gradient (rose → amber → teal) so the fill edge immediately shows
    where the submission sits on the spectrum
  • A midpoint equilibrium marker at 50%
  • A compact support row: engagement depth · authenticity score · connection%

This makes the big picture obvious (single bar = one conclusion) while
preserving the three underlying metrics for teachers who want the detail.
"""

from typing import Optional

from PySide6.QtWidgets import QWidget, QSizePolicy
from PySide6.QtCore import Qt, QSize, QRectF, QPointF
from PySide6.QtGui import (
    QPainter, QPen, QColor, QFont,
    QLinearGradient, QRadialGradient, QPainterPath,
)

from gui.styles import (
    BG_INSET, BORDER_DARK, BORDER_AMBER,
    PHOSPHOR_DIM, PHOSPHOR_MID,
    px,
)
from gui.aic_palette import CONCERN_COLOR, CONCERN_LABEL


# ──────────────────────────────────────────────────────────────────────────────
# Colour helpers
# ──────────────────────────────────────────────────────────────────────────────

def _lerp_color(c0: tuple, c1: tuple, t: float) -> QColor:
    t = max(0.0, min(1.0, t))
    r = int(c0[0] + (c1[0] - c0[0]) * t)
    g = int(c0[1] + (c1[1] - c0[1]) * t)
    b = int(c0[2] + (c1[2] - c0[2]) * t)
    return QColor(r, g, b)


_ROSE  = (192, 64, 100)   # low HP: AI signals
_AMBER = (232, 160, 48)   # midpoint: equilibrium
_TEAL  = (88,  200, 184)  # high HP: human


def _hp_color(hp_frac: float) -> QColor:
    """Colour at a given personal-connection fraction (0 = limited/rose, 1 = strong/teal)."""
    if hp_frac <= 0.5:
        return _lerp_color(_ROSE, _AMBER, hp_frac / 0.5)
    return _lerp_color(_AMBER, _TEAL, (hp_frac - 0.5) / 0.5)


# ──────────────────────────────────────────────────────────────────────────────
# Widget
# ──────────────────────────────────────────────────────────────────────────────

class SignalTriad(QWidget):
    """Authorship Spectrum bar with verdict badge and support metrics.

    Call set_scores() to populate; the widget repaints automatically.
    """

    _BAR_H = 20     # spectrum bar height
    _PAD   = 8      # outer padding

    def __init__(self, parent=None):
        super().__init__(parent)
        self._suspicion:    float = 0.0
        self._authenticity: float = 0.0
        self._human:        Optional[float] = None
        self._concern:      str = "none"

        # Dynamic height so everything stays proportional under font scaling
        h = (
            self._PAD
            + px(13) + 4          # header row
            + px(10) + 4          # legend row
            + self._BAR_H + 2     # spectrum bar
            + px(10) + 4          # tick row
            + px(10) + 4          # support row
            + self._PAD
        )
        self.setFixedHeight(h)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

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
        return QSize(300, self.height())

    # ── Painting ──────────────────────────────────────────────────────────────

    def paintEvent(self, _event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w   = self.width()
        pd  = self._PAD

        hp_frac = (self._human / 100.0) if self._human is not None else None
        hp_str  = f"{self._human:.0f}%" if self._human is not None else "—"

        c_hex  = CONCERN_COLOR.get(self._concern, PHOSPHOR_DIM)
        c_text = CONCERN_LABEL.get(self._concern, self._concern).upper()
        c_col  = QColor(c_hex)

        # ── Fonts ─────────────────────────────────────────────────────────────
        hdr_font  = QFont("Menlo", px(10))
        hdr_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.0)
        val_font  = QFont("Menlo", px(12))
        val_font.setBold(True)
        leg_font  = QFont("Menlo", px(10))
        tick_font = QFont("Menlo", px(9))
        sup_font  = QFont("Menlo", px(10))

        dim_c = QColor(PHOSPHOR_DIM)
        mid_c = QColor(PHOSPHOR_MID)
        trk_c = QColor(BG_INSET)
        bdr_c = QColor(BORDER_DARK)

        # ── Row 1: header — "ENGAGEMENT SPECTRUM"  conn%  [OPPORTUNITY] ─────
        y = self._PAD
        row_h = px(13)

        p.setFont(hdr_font)
        p.setPen(dim_c)
        p.drawText(
            QRectF(pd, y, w * 0.45, row_h),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "ENGAGEMENT SPECTRUM",
        )

        # Concern badge — measure first so HP text can avoid it
        p.setFont(hdr_font)
        fm  = p.fontMetrics()
        btw = fm.horizontalAdvance(c_text)
        bw  = btw + px(14)
        bh  = row_h
        bx  = w - pd - bw
        by  = y

        # HP% value — positioned between header and badge
        if hp_frac is not None:
            hp_edge_col = _hp_color(hp_frac)
            p.setFont(val_font)
            p.setPen(hp_edge_col)
            hp_left = w * 0.45
            hp_avail = bx - hp_left - px(6)   # gap before badge
            p.drawText(
                QRectF(hp_left, y, max(hp_avail, 0), row_h),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
                hp_str + " connected",
            )

        badge_rect = QRectF(bx, by, bw, bh)
        badge_path = QPainterPath()
        badge_path.addRoundedRect(badge_rect, bh / 2, bh / 2)

        bg = QColor(c_col)
        bg.setAlpha(35)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(badge_path, bg)
        p.setPen(QPen(c_col, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(badge_path)

        p.setPen(c_col)
        p.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, c_text)

        y += row_h + 4

        # ── Row 2: axis legend ─────────────────────────────────────────────────
        leg_h = px(10)
        p.setFont(leg_font)
        p.setPen(dim_c)
        bar_x = pd
        bar_w = w - pd * 2

        p.drawText(
            QRectF(bar_x, y, bar_w * 0.5, leg_h + 2),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "← limited engagement",
        )
        p.drawText(
            QRectF(bar_x, y, bar_w, leg_h + 2),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight,
            "strong engagement →",
        )

        y += leg_h + 4

        # ── Row 3: spectrum bar ────────────────────────────────────────────────
        bar_rect = QRectF(bar_x, y, bar_w, self._BAR_H)
        bar_path = QPainterPath()
        bar_path.addRoundedRect(bar_rect, 3, 3)

        # Track (background)
        p.setPen(Qt.PenStyle.NoPen)
        p.fillPath(bar_path, trk_c)
        p.setPen(QPen(bdr_c, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(bar_path)

        # Spectrum fill: gradient rose → amber → teal clipped to hp_frac
        if hp_frac is not None and hp_frac > 0.01:
            fill_w = hp_frac * bar_w
            fill_rect = QRectF(bar_x, y, fill_w, self._BAR_H)
            fill_path = QPainterPath()
            fill_path.addRoundedRect(fill_rect, 3, 3)
            clipped = fill_path.intersected(bar_path)

            # Gradient spans the full bar width so the visible colour at the
            # fill edge corresponds exactly to the HP fraction position.
            grad = QLinearGradient(bar_x, 0, bar_x + bar_w, 0)
            grad.setColorAt(0.00, QColor(_ROSE[0],  _ROSE[1],  _ROSE[2],  110))
            grad.setColorAt(0.50, QColor(_AMBER[0], _AMBER[1], _AMBER[2], 160))
            grad.setColorAt(1.00, QColor(_TEAL[0],  _TEAL[1],  _TEAL[2],  190))

            p.setPen(Qt.PenStyle.NoPen)
            p.fillPath(clipped, grad)

            # Glow at fill edge
            ec   = _hp_color(hp_frac)
            gx   = bar_x + fill_w
            gy   = y + self._BAR_H / 2
            gr   = self._BAR_H * 1.4
            glow = QRadialGradient(gx, gy, gr)
            glow.setColorAt(0.0, QColor(ec.red(), ec.green(), ec.blue(), 60))
            glow.setColorAt(1.0, QColor(ec.red(), ec.green(), ec.blue(), 0))
            p.save()
            p.setClipPath(bar_path)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(
                int(gx - gr), int(gy - gr),
                int(gr * 2),  int(gr * 2),
            )
            p.restore()

        # Midpoint equilibrium line (dashed amber)
        mid_x = bar_x + bar_w * 0.5
        p.setPen(QPen(QColor(BORDER_AMBER), 1, Qt.PenStyle.DashLine))
        p.drawLine(
            QPointF(mid_x, y + 3),
            QPointF(mid_x, y + self._BAR_H - 3),
        )

        y += self._BAR_H + 2

        # ── Row 4: tick labels ─────────────────────────────────────────────────
        tick_h = px(10)
        p.setFont(tick_font)
        p.setPen(dim_c)
        p.drawText(
            QRectF(bar_x, y, 28, tick_h + 2),
            Qt.AlignmentFlag.AlignLeft, "0%",
        )
        p.drawText(
            QRectF(bar_x, y, bar_w, tick_h + 2),
            Qt.AlignmentFlag.AlignCenter, "50%",
        )
        p.drawText(
            QRectF(bar_x, y, bar_w, tick_h + 2),
            Qt.AlignmentFlag.AlignRight, "100%",
        )

        y += tick_h + 4

        # ── Row 5: support metrics ─────────────────────────────────────────────
        sup_h   = px(10)
        sus_lbl = f"depth {self._suspicion:.2f}"
        aut_lbl = f"auth {self._authenticity:.2f}"
        hp_lbl  = f"{hp_str} connection"
        support = f"{sus_lbl}  ·  {aut_lbl}  ·  {hp_lbl}"

        p.setFont(sup_font)
        p.setPen(dim_c)
        p.drawText(
            QRectF(bar_x, y, bar_w, sup_h + 4),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            support,
        )

        p.end()
