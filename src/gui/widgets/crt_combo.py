"""
CRT-styled QComboBox — QPainter-painted closed state + styled popup.

macOS ignores QAbstractItemView styling on native combo popups.  This
widget forces a QListView popup and paints both states with the amber
phosphor CRT aesthetic.
"""

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
from PySide6.QtWidgets import (
    QComboBox,
    QListView,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
)

# ── palette (self-contained) ──────────────────────────────────────────────
_BG          = "#0E0A02"
_BG_WARM     = "#140E04"
_BORDER      = "#3A2808"
_BORDER_AMB  = "#6A4A12"
_HOT         = "#F0A830"
_MID         = "#C08820"
_DIM         = "#7A5418"
_GLOW        = "#4A3210"
_SEL_BG      = "#2C1C08"


# ── delegate for popup items ──────────────────────────────────────────────

class _ItemDelegate(QStyledItemDelegate):
    """Draws each popup row with a left-edge glow on hover/selection."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index) -> None:
        painter.save()
        rect = option.rect
        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)
        is_hov = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # ── background ────────────────────────────────────────────────
        if is_sel or is_hov:
            # Radial glow from left edge, extending further right
            grad = QRadialGradient(rect.x() + rect.width() * 0.10,
                                   rect.center().y(),
                                   rect.width() * 1.2)
            if is_sel:
                grad.setColorAt(0.0, QColor(240, 168, 48, 55))
                grad.setColorAt(0.4, QColor(240, 168, 48, 18))
                grad.setColorAt(0.75, QColor(240, 168, 48, 5))
            else:
                grad.setColorAt(0.0, QColor(240, 168, 48, 30))
                grad.setColorAt(0.4, QColor(240, 168, 48, 10))
                grad.setColorAt(0.75, QColor(240, 168, 48, 3))
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRect(rect)

        # ── text ──────────────────────────────────────────────────────
        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        font = QFont("Menlo")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPixelSize(13)
        painter.setFont(font)

        text_color = QColor(_HOT) if is_sel else QColor(_MID)
        painter.setPen(text_color)

        text_rect = rect.adjusted(12, 0, -8, 0)
        fm = QFontMetrics(font)
        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        return QSize(option.rect.width() or 200, 30)


# ── popup list view ───────────────────────────────────────────────────────

_POPUP_QSS = f"""
    QListView {{
        background: {_BG};
        border: 1px solid {_BORDER_AMB};
        border-top: none;
        border-bottom-left-radius: 6px;
        border-bottom-right-radius: 6px;
        padding: 4px 0;
        outline: none;
    }}
    QListView::item {{
        border: none;
        padding: 0;
    }}
"""


# ── main widget ───────────────────────────────────────────────────────────

class CRTComboBox(QComboBox):
    """Drop-in QComboBox replacement with full CRT phosphor styling.

    The closed state is QPainter-painted (radial backlight, chevron arrow).
    The popup uses a QListView with a custom delegate so macOS can't
    override our styling with native controls.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self._hovered = False

        # Force non-native popup
        lv = QListView()
        lv.setStyleSheet(_POPUP_QSS)
        lv.setMouseTracking(True)
        lv.setItemDelegate(_ItemDelegate())
        self.setView(lv)

        self.setMouseTracking(True)
        self.setFixedHeight(34)
        self.setMinimumWidth(140)

        # Minimal QSS — just suppress native chrome; painting is in paintEvent
        self.setStyleSheet(f"""
            QComboBox {{
                background: transparent;
                border: none;
                color: transparent;
                padding: 0;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 0;
            }}
            QComboBox::down-arrow {{
                image: none;
            }}
        """)

    # ── interaction ───────────────────────────────────────────────────

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    # ── size ──────────────────────────────────────────────────────────

    def sizeHint(self) -> QSize:
        fm = QFontMetrics(self._font())
        text_w = max(fm.horizontalAdvance(self.itemText(i))
                     for i in range(self.count())) if self.count() else 100
        return QSize(text_w + 52, 34)

    def minimumSizeHint(self) -> QSize:
        return QSize(100, 34)

    # ── painting ──────────────────────────────────────────────────────

    @staticmethod
    def _font() -> QFont:
        f = QFont("Menlo")
        f.setStyleHint(QFont.StyleHint.Monospace)
        f.setPixelSize(13)
        return f

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        w, h = self.width(), self.height()
        is_open = self.view().isVisible()
        is_disabled = not self.isEnabled()

        # ── outer shape ───────────────────────────────────────────────
        radius = 6.0
        if is_open:
            # Square off bottom corners when popup is showing
            path = QPainterPath()
            path.moveTo(0, h)
            path.lineTo(0, radius)
            path.arcTo(0, 0, radius * 2, radius * 2, 180, -90)
            path.lineTo(w - radius, 0)
            path.arcTo(w - radius * 2, 0, radius * 2, radius * 2, 90, -90)
            path.lineTo(w, h)
            path.closeSubpath()
        else:
            path = QPainterPath()
            path.addRoundedRect(0.5, 0.5, w - 1, h - 1, radius, radius)

        # ── background — radial glow from right side ──────────────────
        bg = QRadialGradient(w * 0.82, h * 0.45, w * 0.9)
        if is_disabled:
            bg.setColorAt(0.0, QColor(20, 16, 6, 120))
            bg.setColorAt(1.0, QColor(14, 10, 2, 200))
        elif is_open:
            bg.setColorAt(0.0, QColor(38, 28, 12))
            bg.setColorAt(0.5, QColor(22, 16, 6))
            bg.setColorAt(1.0, QColor(14, 10, 2))
        elif self._hovered:
            bg.setColorAt(0.0, QColor(32, 24, 10))
            bg.setColorAt(0.5, QColor(20, 14, 5))
            bg.setColorAt(1.0, QColor(14, 10, 2))
        else:
            bg.setColorAt(0.0, QColor(24, 18, 8))
            bg.setColorAt(0.5, QColor(16, 12, 4))
            bg.setColorAt(1.0, QColor(14, 10, 2))

        p.setClipPath(path)
        p.fillRect(0, 0, w, h, bg)
        p.setClipping(False)

        # ── border ────────────────────────────────────────────────────
        if is_disabled:
            border_color = QColor(_BORDER)
        elif is_open or self._hovered:
            border_color = QColor(_MID)
        else:
            border_color = QColor(_BORDER_AMB)

        p.setPen(QPen(border_color, 1.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # ── bottom glow line (subtle backlight bleed) ─────────────────
        if not is_open and not is_disabled:
            glow = QLinearGradient(0, h - 1, w, h - 1)
            alpha = 35 if self._hovered else 18
            glow.setColorAt(0.0, QColor(240, 168, 48, 0))
            glow.setColorAt(0.3, QColor(240, 168, 48, alpha))
            glow.setColorAt(0.7, QColor(240, 168, 48, alpha))
            glow.setColorAt(1.0, QColor(240, 168, 48, 0))
            p.setPen(QPen(glow, 1.0))
            p.drawLine(int(w * 0.08), h - 1, int(w * 0.92), h - 1)

        # ── text ──────────────────────────────────────────────────────
        font = self._font()
        p.setFont(font)
        fm = QFontMetrics(font)

        text = self.currentText()
        text_rect = QRect(12, 0, w - 40, h)

        if is_disabled:
            text_color = QColor(_DIM)
        elif is_open:
            text_color = QColor(_HOT)
        elif self._hovered:
            text_color = QColor(_HOT)
        else:
            text_color = QColor(_MID)

        elided = fm.elidedText(text, Qt.TextElideMode.ElideRight, text_rect.width())
        p.setPen(text_color)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided)

        # ── chevron arrow ─────────────────────────────────────────────
        arrow_x = w - 22
        arrow_y = h / 2

        if is_disabled:
            arrow_color = QColor(_GLOW)
        elif self._hovered or is_open:
            arrow_color = QColor(_HOT)
        else:
            arrow_color = QColor(_DIM)

        p.setPen(QPen(arrow_color, 1.5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        if is_open:
            # Up chevron
            p.drawLine(arrow_x - 4, int(arrow_y + 2), arrow_x, int(arrow_y - 2))
            p.drawLine(arrow_x, int(arrow_y - 2), arrow_x + 4, int(arrow_y + 2))
        else:
            # Down chevron
            p.drawLine(arrow_x - 4, int(arrow_y - 2), arrow_x, int(arrow_y + 2))
            p.drawLine(arrow_x, int(arrow_y + 2), arrow_x + 4, int(arrow_y - 2))

        p.end()
