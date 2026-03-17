"""
Styled drop-in replacements for QMessageBox — amber terminal aesthetic.

Usage (same call signature as QMessageBox):

    from gui.dialogs.message_dialog import show_info, show_warning, show_critical, show_question

    show_info(parent, "Name Updated", f"Canvas course name updated to:\n{nickname}")
    show_warning(parent, "Save Error", str(exc))

    if show_question(parent, "Remove Profile", f"Remove profile '{name}'?"):
        ...  # returns True when user clicks Yes/OK, False otherwise

    reply = show_warning(
        parent, "Unpublish?", msg,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
    )
    if reply == QMessageBox.StandardButton.Yes: ...
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QPushButton,
    QMessageBox,
)
from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QFont

from gui.styles import (
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    BORDER_DARK, BORDER_AMBER,
    BURN_RED,
)

# ---------------------------------------------------------------------------
# Shared colours / QSS
# ---------------------------------------------------------------------------

_BG         = "#120900"
_HDR_BG     = "#0A0700"
_MONO_STACK = '"Menlo", "Consolas", "Courier New", monospace'

_BTN_SECONDARY = f"""
    QPushButton {{
        background: #1A0F00;
        color: {PHOSPHOR_DIM};
        border: 1px solid #3A2808;
        border-radius: 4px;
        padding: 5px 18px;
        font-family: {_MONO_STACK};
        font-size: 11px;
    }}
    QPushButton:hover {{
        background: #241400;
        color: {PHOSPHOR_MID};
        border-color: {BORDER_DARK};
    }}
    QPushButton:pressed {{ background: #1A0F00; }}
"""

_BTN_PRIMARY = f"""
    QPushButton {{
        background: #1E1200;
        color: {PHOSPHOR_HOT};
        border: 1px solid {BORDER_AMBER};
        border-radius: 4px;
        padding: 5px 18px;
        font-family: {_MONO_STACK};
        font-size: 11px;
    }}
    QPushButton:hover {{
        background: #2E1A00;
        border-color: {PHOSPHOR_HOT};
    }}
    QPushButton:pressed {{ background: #3A2200; }}
"""

_BTN_DANGER = f"""
    QPushButton {{
        background: #1A0800;
        color: {BURN_RED};
        border: 1px solid #5A1808;
        border-radius: 4px;
        padding: 5px 18px;
        font-family: {_MONO_STACK};
        font-size: 11px;
    }}
    QPushButton:hover {{
        background: #280C00;
        border-color: {BURN_RED};
    }}
    QPushButton:pressed {{ background: #380F00; }}
"""

_SB = QMessageBox.StandardButton


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mono(size: int, bold: bool = False) -> QFont:
    f = QFont("Menlo")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPointSize(size)
    f.setBold(bold)
    return f


def _parse_buttons(flags: _SB, severity: str) -> list[tuple[str, str, _SB]]:
    """Convert a StandardButton flags value into (label, role, std_btn) triples.

    Left-to-right order: Cancel → No → Don't Save → Yes/Save/OK
    """
    specs: list[tuple[str, str, _SB]] = []
    primary_role = "danger" if severity == "critical" else "primary"

    if flags & _SB.Cancel:
        specs.append(("Cancel",     "secondary", _SB.Cancel))
    if flags & _SB.No:
        specs.append(("No",         "secondary", _SB.No))
    if flags & _SB.Discard:
        specs.append(("Don't Save", "danger",    _SB.Discard))
    if flags & _SB.Yes:
        specs.append(("Yes",        primary_role, _SB.Yes))
    if flags & _SB.Save:
        specs.append(("Save",       primary_role, _SB.Save))
    if flags & _SB.Ok:
        specs.append(("OK",         primary_role, _SB.Ok))
    if not specs:
        specs.append(("OK",         primary_role, _SB.Ok))

    return specs


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class _AmberDialog(QDialog):
    """Frameless, amber-terminal dialog. Replaces QMessageBox system dialogs."""

    def __init__(
        self,
        parent,
        title: str,
        text: str,
        *,
        severity: str,
        btn_specs: list[tuple[str, str, _SB]],
    ) -> None:
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setModal(True)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedWidth(460)

        _accent = {
            "info":     PHOSPHOR_DIM,
            "warning":  PHOSPHOR_HOT,
            "critical": BURN_RED,
            "question": PHOSPHOR_MID,
        }.get(severity, PHOSPHOR_MID)

        self.setStyleSheet(f"""
            QDialog {{
                background: {_BG};
                border: 1px solid {_accent};
            }}
            QLabel {{ background: transparent; border: none; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────────
        hdr = QFrame()
        hdr.setObjectName("amberDlgHdr")
        hdr.setStyleSheet(f"""
            QFrame#amberDlgHdr {{
                background: {_HDR_BG};
                border: none;
                border-bottom: 1px solid {BORDER_DARK};
            }}
        """)
        hlay = QHBoxLayout(hdr)
        hlay.setContentsMargins(14, 9, 14, 9)
        hlay.setSpacing(9)

        _icon = {"warning": "⚠", "critical": "⊗", "question": "?", "info": "·"}.get(
            severity, "⚠"
        )
        icon_lbl = QLabel(_icon)
        icon_lbl.setFont(_mono(12))
        icon_lbl.setStyleSheet(f"color: {_accent}; background: transparent; border: none;")
        hlay.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        title_lbl = QLabel(title.upper())
        title_lbl.setFont(_mono(9))
        title_lbl.setStyleSheet(
            f"color: {_accent}; letter-spacing: 1.5px;"
            f" background: transparent; border: none;"
        )
        hlay.addWidget(title_lbl, 1)

        root.addWidget(hdr)

        # ── Body ──────────────────────────────────────────────────────────
        body = QFrame()
        body.setObjectName("amberDlgBody")
        body.setStyleSheet(
            "QFrame#amberDlgBody { background: transparent; border: none; }"
        )
        blay = QVBoxLayout(body)
        blay.setContentsMargins(20, 14, 20, 14)
        blay.setSpacing(8)

        # Split on \n\n — first paragraph is "lead" (brighter), rest are "detail" (dim)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            lbl = QLabel(para)
            lbl.setWordWrap(True)
            if i == 0:
                lbl.setFont(_mono(12))
                lbl.setStyleSheet(f"color: {PHOSPHOR_MID};")
            else:
                lbl.setFont(_mono(11))
                lbl.setStyleSheet(f"color: {PHOSPHOR_DIM};")
            blay.addWidget(lbl)

        root.addWidget(body)

        # ── Footer separator ──────────────────────────────────────────────
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        root.addWidget(sep)

        # ── Buttons ───────────────────────────────────────────────────────
        foot = QFrame()
        foot.setObjectName("amberDlgFoot")
        foot.setStyleSheet(
            "QFrame#amberDlgFoot { background: transparent; border: none; }"
        )
        flay = QHBoxLayout(foot)
        flay.setContentsMargins(16, 8, 16, 12)
        flay.setSpacing(8)
        flay.addStretch()

        self._chosen: _SB = _SB.Cancel

        for label, role, std_btn in btn_specs:
            qss = {"secondary": _BTN_SECONDARY, "danger": _BTN_DANGER}.get(
                role, _BTN_PRIMARY
            )
            btn = QPushButton(label)
            btn.setStyleSheet(qss)
            btn.clicked.connect(lambda _checked=False, b=std_btn: self._finish(b))
            flay.addWidget(btn)

        root.addWidget(foot)

        # Drag support (frameless window needs manual move)
        self._drag_pos: QPoint | None = None

    def _finish(self, result: _SB) -> None:
        self._chosen = result
        self.accept()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = (
                ev.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )

    def mouseReleaseEvent(self, ev) -> None:
        self._drag_pos = None

    def mouseMoveEvent(self, ev) -> None:
        if self._drag_pos and ev.buttons() == Qt.MouseButton.LeftButton:
            self.move(ev.globalPosition().toPoint() - self._drag_pos)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _run(parent, title: str, text: str, severity: str, btn_specs) -> _SB:
    dlg = _AmberDialog(parent, title, text, severity=severity, btn_specs=btn_specs)
    dlg.exec()
    return dlg._chosen


def show_info(parent, title: str, text: str) -> None:
    """Show an informational message. No return value."""
    _run(parent, title, text, "info", [("OK", "primary", _SB.Ok)])


def show_warning(
    parent,
    title: str,
    text: str,
    buttons: _SB = _SB.Ok,
) -> _SB:
    """Show a warning message. Returns the StandardButton clicked."""
    return _run(parent, title, text, "warning", _parse_buttons(buttons, "warning"))


def show_critical(
    parent,
    title: str,
    text: str,
    buttons: _SB = _SB.Ok,
) -> _SB:
    """Show a critical / blocking error. Returns the StandardButton clicked."""
    return _run(parent, title, text, "critical", _parse_buttons(buttons, "critical"))


def show_question(
    parent,
    title: str,
    text: str,
    buttons: _SB = _SB.Yes | _SB.No,
) -> _SB:
    """Show a confirmation question. Returns the StandardButton clicked."""
    return _run(parent, title, text, "question", _parse_buttons(buttons, "question"))
