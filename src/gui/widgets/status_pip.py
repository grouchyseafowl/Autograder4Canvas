"""StatusPip — CRT phosphor status indicator dot.

Exports
-------
draw_pip(painter, cx, cy, diameter, r, g, b, bloom_alpha, core_alpha)
    Module-level helper — draw a single pip at any position.
    Caller owns painter state (save/restore around call if needed).

StatusPip(QWidget)
    Self-contained blinking dot widget. States: ok / error / connecting / off.
"""

import math

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

# ---------------------------------------------------------------------------
# State → colour map
# ---------------------------------------------------------------------------
_STATES: dict[str, tuple[int, int, int, int, int]] = {
    #              R    G    B  bloom  core
    "ok":         (114, 184,  90,  55, 210),   # TERM_GREEN  #72B85A
    "error":      (192,  64,  32,  60, 220),   # BURN_RED    #C04020
    "connecting": (240, 168,  48,  40, 180),   # PHOSPHOR_HOT #F0A830
    "off":        ( 58,  40,   8,   0,  90),   # dim ember
}


def draw_pip(
    painter: QPainter,
    cx: float,
    cy: float,
    diameter: float,
    r: int,
    g: int,
    b: int,
    bloom_alpha: int,
    core_alpha: int,
) -> None:
    """Draw a single phosphor pip at (cx, cy).

    Outer bloom halo + solid core dot.  No pen is set on exit.
    Caller is responsible for save/restore if needed.
    """
    painter.setPen(Qt.PenStyle.NoPen)

    # Outer bloom halo (only when bloom_alpha > 0)
    if bloom_alpha > 0:
        bloom_r = diameter * 2.0
        bloom = QRadialGradient(cx, cy, bloom_r)
        bloom.setColorAt(0.00, QColor(r, g, b, bloom_alpha))
        bloom.setColorAt(0.35, QColor(r, g, b, max(0, bloom_alpha // 3)))
        bloom.setColorAt(1.00, QColor(r, g, b, 0))
        painter.setBrush(bloom)
        br = bloom_r * 2
        painter.drawEllipse(int(cx - bloom_r), int(cy - bloom_r), int(br), int(br))

    # Core dot
    half = diameter / 2.0
    core = QRadialGradient(cx, cy, half)
    core.setColorAt(0.0, QColor(r, g, b, core_alpha))
    core.setColorAt(1.0, QColor(r, g, b, max(0, core_alpha // 2)))
    painter.setBrush(core)
    painter.drawEllipse(int(cx - half), int(cy - half),
                        int(diameter), int(diameter))


class StatusPip(QWidget):
    """Glowing CRT-style status indicator dot.

    Parameters
    ----------
    state    : "ok" | "error" | "connecting" | "off"
    diameter : core dot diameter in pixels (default 8)
    """

    def __init__(self, state: str = "off", diameter: int = 8,
                 parent=None) -> None:
        super().__init__(parent)
        self._state    = state
        self._diameter = diameter
        self._pulse    = 0.0
        self._timer    = QTimer(self)
        self._timer.timeout.connect(self._tick)
        sz = diameter * 4
        self.setFixedSize(sz, sz)
        self._update_timer()

    def set_state(self, state: str) -> None:
        self._state = state
        self._update_timer()
        self.update()

    def state(self) -> str:
        return self._state

    # ── Internal ──────────────────────────────────────────────────────────
    def _update_timer(self) -> None:
        if self._state == "connecting":
            if not self._timer.isActive():
                self._timer.start(40)
        else:
            self._timer.stop()
            self._pulse = 0.0

    def _tick(self) -> None:
        self._pulse = (self._pulse + 0.08) % (2 * math.pi)
        self.update()

    # ── Qt overrides ──────────────────────────────────────────────────────
    def sizeHint(self) -> QSize:
        sz = self._diameter * 4
        return QSize(sz, sz)

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width()  / 2.0
        cy = self.height() / 2.0

        r, g, b, bloom_a, core_a = _STATES.get(self._state, _STATES["off"])

        if self._state == "connecting":
            boost   = int(25 * (0.5 + 0.5 * math.sin(self._pulse)))
            bloom_a = min(255, bloom_a + boost)
            core_a  = min(255, core_a  + boost)

        p.save()
        draw_pip(p, cx, cy, self._diameter, r, g, b, bloom_a, core_a)
        p.restore()
        p.end()
