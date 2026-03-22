"""
First-launch setup dialog: Canvas URL + API token entry.
Two-panel layout — form (left) + token guide (right).
Retro-futurist amber terminal aesthetic.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QSizePolicy, QToolButton, QCheckBox, QSpinBox, QComboBox,
)
from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QFont, QPainter, QPen, QColor, QPainterPath

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD,
    BG_CARD, BG_PANEL, BG_INSET,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    AMBER_BTN, ROSE_ACCENT, WARN_PINK,
    TERM_GREEN, BURN_RED,
    BORDER_DARK, BORDER_AMBER,
    STATUS_OK, STATUS_ERR,
    CARD_GRADIENT, PANEL_GRADIENT, MONO_FONT,
    make_secondary_button,
    combo_qss,
)

_MONO     = MONO_FONT
_CARD_BG  = CARD_GRADIENT
_PANEL_BG = PANEL_GRADIENT
_BTN_BG   = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #201A0A,stop:1 #181205)"
_BTN_HOV  = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2A220E,stop:1 #1E1808)"
_BTN_PRE  = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #181205,stop:1 #131003)"


# ---------------------------------------------------------------------------
# Eye button — drawn icon, amber shades
# ---------------------------------------------------------------------------

class _EyeButton(QToolButton):
    """Amber-tinted eye icon — semi-transparent, 4 shades."""

    _SHADES = [
        QColor(90,  60,  8,  65),
        QColor(160, 106, 16, 120),
        QColor(200, 140, 20, 155),
        QColor(240, 168, 48, 195),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        checked = self.isChecked()
        hovered = self.underMouse()
        if   checked and hovered: color = self._SHADES[3]
        elif checked:              color = self._SHADES[2]
        elif hovered:              color = self._SHADES[1]
        else:                      color = self._SHADES[0]

        cx, cy = self.width() / 2.0, self.height() / 2.0

        path = QPainterPath()
        path.moveTo(cx - 8, cy)
        path.cubicTo(cx - 8, cy - 5, cx - 2, cy - 6, cx, cy - 6)
        path.cubicTo(cx + 2, cy - 6, cx + 8, cy - 5, cx + 8, cy)
        path.cubicTo(cx + 8, cy + 5, cx + 2, cy + 6, cx, cy + 6)
        path.cubicTo(cx - 2, cy + 6, cx - 8, cy + 5, cx - 8, cy)
        path.closeSubpath()
        painter.setPen(QPen(color, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawEllipse(int(cx - 2.5), int(cy - 2.5), 5, 5)

        if not checked:
            painter.setPen(QPen(color, 1.4))
            painter.drawLine(int(cx - 6), int(cy + 5), int(cx + 6), int(cy - 5))

        painter.end()


# ---------------------------------------------------------------------------
# Token field with inset eye button
# ---------------------------------------------------------------------------

class _TokenLineEdit(QLineEdit):
    """QLineEdit with an eye-toggle button pinned to the right edge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setPlaceholderText("paste token here ···")

        self._eye = _EyeButton(self)
        self._eye.setCheckable(True)
        self._eye.setToolTip("Show / hide token")
        self._eye.toggled.connect(self._on_toggle)

        self._apply_style(focused=False)

    def _apply_style(self, focused: bool) -> None:
        border = f"2px solid {PHOSPHOR_HOT}" if focused else f"1px solid {BORDER_AMBER}"
        self.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                border: none;
                border-bottom: {border};
                border-radius: 0;
                padding: 4px 2px 3px 2px;
                color: {PHOSPHOR_HOT};
                font-family: {_MONO};
                font-size: {px(13)}px;
                selection-background-color: {PHOSPHOR_GLOW};
                selection-color: {PHOSPHOR_HOT};
            }}
        """)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self._apply_style(focused=True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self._apply_style(focused=False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        bw = self.height() - 6
        self._eye.setFixedSize(bw, bw)
        self._eye.move(self.width() - bw - 4, (self.height() - bw) // 2)
        self.setTextMargins(0, 0, bw + 8, 0)

    def _on_toggle(self, checked: bool) -> None:
        self.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)
        self._eye.update()


# ---------------------------------------------------------------------------
# URL row — shared underline across https:// + input + .instructure.com
# ---------------------------------------------------------------------------

def _make_url_row() -> tuple[QFrame, QLineEdit]:
    """Returns (container_frame, url_lineedit)."""
    _QSS_BLUR = f"""
        QFrame#urlRow {{
            background: transparent; border: none;
            border-bottom: 1px solid {BORDER_AMBER}; border-radius: 0;
        }}
        QFrame#urlRow QLabel {{
            background: transparent; border: none; border-radius: 0;
        }}
    """
    _QSS_FOCUS = f"""
        QFrame#urlRow {{
            background: transparent; border: none;
            border-bottom: 2px solid {PHOSPHOR_HOT}; border-radius: 0;
        }}
        QFrame#urlRow QLabel {{
            background: transparent; border: none; border-radius: 0;
        }}
    """

    container = QFrame()
    container.setObjectName("urlRow")
    container.setStyleSheet(_QSS_BLUR)

    hbox = QHBoxLayout(container)
    hbox.setContentsMargins(0, 0, 0, 0)
    hbox.setSpacing(2)

    def _static_lbl(text):
        l = QLabel(text)
        f = QFont("Menlo, Consolas, Courier New, monospace")
        f.setPointSize(13)
        l.setFont(f)
        l.setStyleSheet(f"color: {PHOSPHOR_DIM};")
        l.setFixedHeight(30)
        return l

    inp = QLineEdit()
    inp.setPlaceholderText("your-institution")
    f = QFont("Menlo, Consolas, Courier New, monospace")
    f.setPointSize(13)
    inp.setFont(f)
    inp.setFixedHeight(30)
    inp.setStyleSheet(f"""
        QLineEdit {{
            background: transparent; border: none; border-radius: 0;
            padding: 4px 2px 3px 2px;
            color: {PHOSPHOR_HOT};
            selection-background-color: {PHOSPHOR_GLOW};
            selection-color: {PHOSPHOR_HOT};
        }}
    """)

    hbox.addWidget(_static_lbl("https://"))
    hbox.addWidget(inp, 1)
    hbox.addWidget(_static_lbl(".instructure.com"))

    class _FocusBridge(QObject):
        def eventFilter(self, obj, event):
            if event.type() == QEvent.Type.FocusIn:
                container.setStyleSheet(_QSS_FOCUS)
            elif event.type() == QEvent.Type.FocusOut:
                container.setStyleSheet(_QSS_BLUR)
            return False

    bridge = _FocusBridge(container)
    inp.installEventFilter(bridge)
    container._bridge = bridge

    return container, inp


# ---------------------------------------------------------------------------
# Warning toast widget
# ---------------------------------------------------------------------------

def _make_warning_toast(text: str) -> QFrame:
    """Big amber ⚠ (centered) + soft pink text on translucent rose panel."""
    frame = QFrame()
    frame.setObjectName("warnToast")
    frame.setStyleSheet(f"""
        QFrame#warnToast {{
            background-color: rgba(110, 40, 72, 0.30);
            border: 1px solid rgba(180, 70, 110, 0.38);
            border-radius: 6px;
        }}
        QFrame#warnToast QLabel {{
            background: transparent; border: none; border-radius: 0;
        }}
    """)

    hbox = QHBoxLayout(frame)
    hbox.setContentsMargins(10, 8, 10, 8)
    hbox.setSpacing(10)

    icon = QLabel("\u26a0")
    f = QFont("Menlo, Consolas, Courier New, monospace")
    f.setPointSize(20)
    icon.setFont(f)
    icon.setStyleSheet(f"color: {PHOSPHOR_HOT};")
    icon.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
    icon.setFixedWidth(26)
    hbox.addWidget(icon, 0, Qt.AlignmentFlag.AlignVCenter)

    lbl = QLabel(text)
    f2 = QFont("Menlo, Consolas, Courier New, monospace")
    f2.setPointSize(12)
    lbl.setFont(f2)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(f"color: {WARN_PINK};")
    lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
    hbox.addWidget(lbl, 1)

    return frame


# ---------------------------------------------------------------------------
# Scanline separator
# ---------------------------------------------------------------------------

def _make_scanline_sep() -> QFrame:
    sep = QFrame()
    sep.setFixedHeight(2)
    sep.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(240,168,48, 0),
                stop:0.15 rgba(240,168,48, 0.25),
                stop:0.40 rgba(240,168,48, 0.70),
                stop:0.50 rgba(255,200,80, 1.00),
                stop:0.60 rgba(240,168,48, 0.70),
                stop:0.85 rgba(240,168,48, 0.25),
                stop:1.00 rgba(240,168,48, 0));
            border: none;
        }
    """)
    return sep


# ---------------------------------------------------------------------------
# Shared button factory
# ---------------------------------------------------------------------------

def _make_btn(text: str, accent_hex: str, bold: bool = True) -> QPushButton:
    r, g, b = int(accent_hex[1:3], 16), int(accent_hex[3:5], 16), int(accent_hex[5:7], 16)
    bdr     = f"rgba({r},{g},{b}, 0.50)"
    bdr_hot = f"rgba({r},{g},{b}, 0.90)"
    weight  = "font-weight: 600;" if bold else ""
    btn = QPushButton(text)
    f = QFont("Menlo, Consolas, Courier New, monospace")
    f.setPointSize(13)
    btn.setFont(f)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {_BTN_BG};
            color: {accent_hex};
            border: 1px solid {bdr};
            border-radius: 4px;
            padding: 6px 14px;
            {weight}
        }}
        QPushButton:hover {{
            background: {_BTN_HOV};
            border: 1px solid {bdr_hot};
            color: {accent_hex};
        }}
        QPushButton:pressed {{
            background: {_BTN_PRE};
            padding-top: 7px; padding-bottom: 5px;
            padding-left: 15px; padding-right: 13px;
            border-color: rgba({r},{g},{b}, 0.35);
        }}
        QPushButton:disabled {{
            color: rgba({r},{g},{b}, 0.30);
            border-color: rgba({r},{g},{b}, 0.20);
        }}
    """)
    btn.setFixedHeight(32)
    return btn


def _make_ghost_btn(text: str) -> QPushButton:
    btn = QPushButton(text)
    f = QFont("Menlo, Consolas, Courier New, monospace")
    f.setPointSize(13)
    btn.setFont(f)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: transparent;
            color: {PHOSPHOR_DIM};
            border: 1px solid {BORDER_DARK};
            border-radius: 4px;
            padding: 6px 14px;
        }}
        QPushButton:hover {{
            color: {PHOSPHOR_MID};
            border-color: {BORDER_AMBER};
        }}
        QPushButton:pressed {{
            padding-top: 7px; padding-bottom: 5px;
            padding-left: 15px; padding-right: 13px;
            border-color: {BORDER_AMBER};
        }}
    """)
    btn.setFixedHeight(32)
    return btn


# ---------------------------------------------------------------------------
# Main dialog
# ---------------------------------------------------------------------------

class SetupDialog(QDialog):
    """Shown modally before the main window if no credentials are configured."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Welcome to Autograder4Canvas")
        self.setMinimumSize(860, 680)
        self.setModal(True)
        self.demo_requested = False  # set True when user clicks a demo button
        self.demo_profile   = "hs"   # "hs" or "cc"
        self._setup_ui()

    # ── UI construction ─────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        body = QHBoxLayout()
        body.setSpacing(12)
        body.addWidget(self._build_form_panel(), stretch=55)
        body.addWidget(self._build_guide_panel(), stretch=45)
        root.addLayout(body, stretch=1)

        root.addWidget(_make_scanline_sep())

        footer = QHBoxLayout()
        footer.setSpacing(SPACING_SM)

        self._test_btn = _make_btn("TEST CONNECTION", ROSE_ACCENT)
        self._test_btn.clicked.connect(self._on_test)
        footer.addWidget(self._test_btn)

        self._test_status = QLabel()
        f = QFont("Menlo, Consolas, Courier New, monospace")
        f.setPointSize(12)
        self._test_status.setFont(f)
        footer.addWidget(self._test_status)
        footer.addStretch()

        self._cancel_btn = _make_ghost_btn("CANCEL")
        self._cancel_btn.clicked.connect(self.reject)
        footer.addWidget(self._cancel_btn)

        self._demo_hs_btn = _make_ghost_btn("HIGH SCHOOL DEMO")
        self._demo_hs_btn.setToolTip("Sample high school courses — no Canvas account needed")
        self._demo_hs_btn.clicked.connect(lambda: self._on_try_demo("hs"))
        footer.addWidget(self._demo_hs_btn)

        self._demo_cc_btn = _make_ghost_btn("COMMUNITY COLLEGE DEMO")
        self._demo_cc_btn.setToolTip("Sample community college courses — no Canvas account needed")
        self._demo_cc_btn.clicked.connect(lambda: self._on_try_demo("cc"))
        footer.addWidget(self._demo_cc_btn)

        self._save_btn = _make_btn("SAVE + CONTINUE", AMBER_BTN)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        footer.addWidget(self._save_btn)

        root.addLayout(footer)

    def _build_form_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("formPanel")
        panel.setStyleSheet(f"""
            QFrame#formPanel {{
                background: {_CARD_BG};
                border: 1px solid {BORDER_DARK};
                border-top-color: {BORDER_AMBER};
                border-left-color: {BORDER_AMBER};
                border-radius: 14px;
            }}
            QFrame#formPanel QLabel {{
                background: transparent; border: none; border-radius: 0;
            }}
        """)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(22, 22, 22, 22)
        lay.setSpacing(SPACING_MD)

        title = QLabel("Connect to Canvas")
        tf = QFont()
        tf.setPointSize(16)
        tf.setBold(True)
        title.setFont(tf)
        title.setStyleSheet(f"color: {PHOSPHOR_HOT};")
        lay.addWidget(title)

        subtitle = QLabel("Enter your institution\u2019s URL and API token.")
        subtitle.setWordWrap(True)
        sf = QFont("Menlo, Consolas, Courier New, monospace")
        sf.setPointSize(13)
        subtitle.setFont(sf)
        subtitle.setStyleSheet(f"color: {PHOSPHOR_MID};")
        lay.addWidget(subtitle)

        lay.addSpacing(4)

        # Canvas URL
        url_lbl = QLabel("CANVAS URL")
        ulf = QFont("Menlo, Consolas, Courier New, monospace")
        ulf.setPointSize(13)
        url_lbl.setFont(ulf)
        url_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; letter-spacing: 1px;")
        lay.addWidget(url_lbl)

        self._url_row, self._url_edit = _make_url_row()
        self._url_row.setMinimumHeight(34)
        lay.addWidget(self._url_row)

        lay.addSpacing(8)

        # API Token
        tok_lbl = QLabel("API TOKEN")
        tok_lbl.setFont(ulf)
        tok_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; letter-spacing: 1px;")
        lay.addWidget(tok_lbl)

        self._token_edit = _TokenLineEdit()
        self._token_edit.setFixedHeight(34)
        self._token_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        lay.addWidget(self._token_edit)

        # ── Institution Profile ──────────────────────────────────────────
        lay.addSpacing(10)
        lay.addWidget(_make_scanline_sep())
        lay.addSpacing(8)

        inst_hdr = QLabel("INSTITUTION PROFILE")
        inst_hdr.setFont(ulf)
        inst_hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; letter-spacing: 1.5px; font-weight: 600; font-size: {px(11)}px;"
        )
        lay.addWidget(inst_hdr)

        inst_desc = QLabel(
            "Calibrates Academic Integrity (AIC) analysis thresholds for your student population."
        )
        inst_desc.setWordWrap(True)
        _f11 = QFont("Menlo, Consolas, Courier New, monospace")
        _f11.setPointSize(11)
        inst_desc.setFont(_f11)
        inst_desc.setStyleSheet(f"color: {PHOSPHOR_DIM};")
        lay.addWidget(inst_desc)

        lay.addSpacing(4)

        inst_type_row = QHBoxLayout()
        inst_type_lbl = QLabel("INSTITUTION TYPE")
        inst_type_lbl.setFont(ulf)
        inst_type_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; letter-spacing: 1px; font-size: {px(11)}px;")
        inst_type_row.addWidget(inst_type_lbl)
        inst_type_row.addSpacing(8)

        self._institution_combo = QComboBox()
        self._institution_combo.setFont(_f11)
        self._institution_combo.addItem("Community College",        userData="community_college")
        self._institution_combo.addItem("Four-Year College",        userData="four_year")
        self._institution_combo.addItem("University / Research",    userData="university")
        self._institution_combo.addItem("Other",                    userData="other")
        self._institution_combo.setFixedWidth(200)
        self._institution_combo.setStyleSheet(combo_qss())
        inst_type_row.addWidget(self._institution_combo)
        inst_type_row.addStretch()
        lay.addLayout(inst_type_row)

        # ── Data Retention ───────────────────────────────────────────────
        lay.addSpacing(10)
        lay.addWidget(_make_scanline_sep())
        lay.addSpacing(8)

        ret_hdr = QLabel("DATA RETENTION")
        ret_hdr.setFont(ulf)
        ret_hdr.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; letter-spacing: 1.5px; font-weight: 600; font-size: {px(11)}px;"
        )
        lay.addWidget(ret_hdr)

        ret_desc = QLabel(
            "Grading reports and Academic Integrity (AIC) data are stored internally "
            "and only exported as external reports on demand. "
            "Configure auto-deletion of aged internal data below."
        )
        ret_desc.setWordWrap(True)
        ret_desc.setFont(_f11)
        ret_desc.setStyleSheet(f"color: {PHOSPHOR_DIM};")
        lay.addWidget(ret_desc)

        lay.addSpacing(4)

        auto_row = QHBoxLayout()
        self._retention_enabled_cb = QCheckBox("Auto-delete internal data older than")
        self._retention_enabled_cb.setFont(_f11)
        self._retention_enabled_cb.setStyleSheet(f"color: {PHOSPHOR_HOT};")
        auto_row.addWidget(self._retention_enabled_cb)

        self._retention_days = QSpinBox()
        self._retention_days.setRange(1, 3650)
        self._retention_days.setValue(90)
        self._retention_days.setSuffix(" days")
        self._retention_days.setFont(_f11)
        self._retention_days.setMinimumHeight(28)
        self._retention_days.setMinimumWidth(90)
        self._retention_days.setStyleSheet(f"""
            QSpinBox {{
                background: {BG_INSET};
                color: {PHOSPHOR_HOT};
                border: 1px solid {BORDER_AMBER};
                border-radius: 3px;
                padding: 2px 4px;
                font-weight: 600;
            }}
        """)
        auto_row.addWidget(self._retention_days)
        auto_row.addStretch()
        lay.addLayout(auto_row)

        cats_row = QHBoxLayout()
        cats_row.addSpacing(24)
        self._retention_grading_cb = QCheckBox("Grading Reports")
        self._retention_grading_cb.setFont(_f11)
        self._retention_grading_cb.setStyleSheet(f"color: {PHOSPHOR_MID};")
        self._retention_grading_cb.setChecked(True)
        cats_row.addWidget(self._retention_grading_cb)

        cats_row.addSpacing(12)
        self._retention_aic_cb = QCheckBox("Engagement Analysis (AIC) data")
        self._retention_aic_cb.setFont(_f11)
        self._retention_aic_cb.setStyleSheet(f"color: {PHOSPHOR_MID};")
        self._retention_aic_cb.setChecked(True)
        cats_row.addWidget(self._retention_aic_cb)
        cats_row.addStretch()
        lay.addLayout(cats_row)

        self._retention_enabled_cb.toggled.connect(self._on_retention_toggled)
        self._on_retention_toggled(False)

        lay.addStretch()

        multi_note = QLabel("You can add profiles for additional institutions later in Settings.")
        multi_note.setWordWrap(True)
        multi_note.setFont(_f11)
        multi_note.setStyleSheet(f"color: {PHOSPHOR_DIM};")
        lay.addWidget(multi_note)

        return panel

    def _on_retention_toggled(self, enabled: bool) -> None:
        self._retention_days.setEnabled(enabled)
        self._retention_grading_cb.setEnabled(enabled)
        self._retention_aic_cb.setEnabled(enabled)

    def _build_guide_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("guidePanel")
        panel.setStyleSheet(f"""
            QFrame#guidePanel {{
                background: {_PANEL_BG};
                border: 1px solid {BORDER_DARK};
                border-top-color: #2A1E08;
                border-radius: 10px;
            }}
            QFrame#guidePanel QLabel {{
                background: transparent; border: none; border-radius: 0;
            }}
        """)

        lay = QVBoxLayout(panel)
        lay.setContentsMargins(16, 18, 16, 18)
        lay.setSpacing(6)

        def _lbl(text, color, size=13, bold=False, wrap=False):
            l = QLabel(text)
            f = QFont("Menlo, Consolas, Courier New, monospace")
            f.setPointSize(size)
            f.setBold(bold)
            l.setFont(f)
            l.setStyleSheet(f"color: {color};")
            if wrap:
                l.setWordWrap(True)
            return l

        lay.addWidget(_lbl("> ABOUT API TOKENS", PHOSPHOR_HOT, size=14, bold=True))
        lay.addSpacing(4)
        lay.addWidget(_lbl(
            "An API token lets this app talk to Canvas on your behalf \u2014 "
            "reading courses, downloading submissions, and posting grades.",
            PHOSPHOR_MID, size=12, wrap=True
        ))
        lay.addSpacing(6)
        lay.addWidget(_make_warning_toast(
            "Treat this like a password \u2014 anyone with it can access "
            "your Canvas account as you. Stored locally on this machine only."
        ))

        lay.addSpacing(8)
        lay.addWidget(_lbl("> TO GENERATE YOURS:", PHOSPHOR_HOT, size=14, bold=True))

        for i, step in enumerate([
            "Log in to Canvas",
            "Profile picture  \u2192  Settings",
            "Scroll: Approved Integrations",
            "+ New Access Token \u00b7 name it",
            "Generate \u00b7 copy immediately",
            "Canvas shows it only once",
        ], 1):
            lay.addWidget(_lbl(f"  {i}.  {step}", PHOSPHOR_MID, size=13))

        lay.addStretch()
        lay.addSpacing(4)
        lay.addWidget(_lbl(
            "\u2713  CONNECTED  \u00b7  J. SMITH", TERM_GREEN, size=13, bold=True
        ))
        return panel

    # ── Logic ────────────────────────────────────────────────────────────────

    def _resolve_url(self, raw: str) -> str:
        raw = raw.strip().rstrip("/")
        if not raw:
            return ""
        if raw.startswith("http"):
            return raw
        if "." in raw:
            return "https://" + raw
        return f"https://{raw}.instructure.com"

    def _on_test(self) -> None:
        from automation.canvas_helpers import CanvasAutomationAPI
        from gui.workers import TestConnectionWorker

        url = self._resolve_url(self._url_edit.text())
        token = self._token_edit.text().strip()
        if not url or not token:
            self._test_status.setText("Enter both URL and token first.")
            self._test_status.setStyleSheet(f"color: {PHOSPHOR_MID};")
            return

        self._test_status.setText("Testing\u2026")
        self._test_status.setStyleSheet(f"color: {PHOSPHOR_DIM};")
        self._test_btn.setEnabled(False)

        api = CanvasAutomationAPI(base_url=url, api_token=token)
        self._worker = TestConnectionWorker(api)
        self._worker.result_ready.connect(self._on_test_result)
        self._worker.start()

    def _on_test_result(self, ok: bool, name: str) -> None:
        self._test_btn.setEnabled(True)
        if ok:
            label = f"Connected as {name}" if name else "Connected"
            self._test_status.setText(f"\u2713 {label}")
            self._test_status.setStyleSheet(f"color: {TERM_GREEN}; font-weight: 600;")
            self._save_btn.setEnabled(True)
        else:
            self._test_status.setText(f"\u2717 {name or 'Invalid token'}")
            self._test_status.setStyleSheet(f"color: {BURN_RED}; font-weight: 600;")
            self._save_btn.setEnabled(False)

    def _on_save(self) -> None:
        from credentials import save_credentials, load_credentials, profile_name_from_url

        url = self._resolve_url(self._url_edit.text())
        token = self._token_edit.text().strip()
        if not url or not token:
            return

        data = load_credentials()
        name = profile_name_from_url(url)
        if "profiles" not in data:
            data["profiles"] = {}
        data["profiles"][name] = {"canvas_base_url": url, "canvas_api_token": token}
        data["active_profile"] = name
        save_credentials(data)

        import os
        os.environ["CANVAS_BASE_URL"] = url
        os.environ["CANVAS_API_TOKEN"] = token

        # Save institution profile + data retention settings
        try:
            from settings import load_settings, save_settings
            s = load_settings()

            inst_type = self._institution_combo.currentData()
            s["institution_type"] = inst_type
            # Map institution type to context profile id
            s["context_profile"] = "community_college" if inst_type == "community_college" else "standard"

            enabled = self._retention_enabled_cb.isChecked()
            days = self._retention_days.value()
            incl_grading = self._retention_grading_cb.isChecked()
            incl_aic = self._retention_aic_cb.isChecked()

            s["data_retention_enabled"] = enabled
            s["data_retention_days"] = days
            s["data_retention_grading"] = incl_grading
            s["data_retention_aic"] = incl_aic
            s["cleanup_mode"] = "trash" if enabled else "none"
            s["cleanup_threshold_days"] = days
            targets = []
            if incl_grading:
                targets += ["ci_csv", "df_csv"]
            if incl_aic:
                targets += ["ad_csv", "ad_excel", "ad_txt"]
            s["cleanup_targets"] = "all" if len(targets) == 5 else ",".join(targets)

            save_settings(s)
        except Exception:
            pass

        self.accept()

    def _on_try_demo(self, profile: str = "hs") -> None:
        self.demo_requested = True
        self.demo_profile   = profile
        self.accept()
