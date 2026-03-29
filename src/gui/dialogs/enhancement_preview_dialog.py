"""
EnhancementPreviewDialog — Shows anonymized payload before cloud enhancement sends.

The teacher can review exactly what data will leave their machine, then confirm
or cancel. No student names or writing are included in the payload.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit,
)

from gui.styles import (
    px,
    BG_VOID, PHOSPHOR_DIM,
    SPACING_LG, SPACING_MD, SPACING_SM,
    make_section_label, make_h_rule,
    make_run_button, make_secondary_button, make_monospace_textedit,
)


class EnhancementPreviewDialog(QDialog):
    """Shows anonymized payload before cloud enhancement sends."""

    def __init__(self, payload: str, provider_label: str, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Enhance Analysis")
        self.setModal(True)
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")

        self._build_ui(payload, provider_label)

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self, payload: str, provider_label: str) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_MD)
        root.setSpacing(SPACING_SM)

        # Section header
        root.addWidget(make_section_label("Enhance Analysis"))

        # Horizontal rule
        root.addWidget(make_h_rule())

        # Info label
        info = QLabel("This is what will be sent. No student names or writing.")
        info.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
            f" padding: {SPACING_SM}px 0 {SPACING_SM}px 0;"
        )
        root.addWidget(info)

        # Payload preview
        self._payload_view = QTextEdit()
        self._payload_view.setReadOnly(True)
        self._payload_view.setPlainText(payload)
        self._payload_view.setMinimumHeight(200)
        self._payload_view.setMaximumHeight(350)
        make_monospace_textedit(self._payload_view)
        root.addWidget(self._payload_view)

        # Provider label
        provider_lbl = QLabel(f"Sending to: {provider_label}")
        provider_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-style: italic;"
            f" background: transparent; border: none;"
            f" padding: {SPACING_SM}px 0 0 0;"
        )
        root.addWidget(provider_lbl)

        # Button row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(SPACING_SM)
        btn_row.setContentsMargins(0, SPACING_MD, 0, 0)
        btn_row.addStretch()

        cancel_btn = QPushButton("Cancel")
        make_secondary_button(cancel_btn)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        send_btn = QPushButton("Send && Enhance")
        make_run_button(send_btn)
        send_btn.clicked.connect(self.accept)
        btn_row.addWidget(send_btn)

        root.addLayout(btn_row)
