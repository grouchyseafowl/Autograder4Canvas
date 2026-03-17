"""
ExportReportsDialog — stub for the Academic Integrity export surface.

The SQLite RunStore is the source of truth. Exports (Excel, PDF, per-student
summary) are a separate surface from the live dashboard — they'll be built here.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PySide6.QtCore import Qt

from gui.styles import (
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_INSET,
    CARD_GRADIENT, make_secondary_button,
)

_PLANNED = [
    ("Class Summary Report",
     "One-page PDF per run: cohort scatter, distribution, smoking gun count. "
     "Suitable for department records."),
    ("Per-Student Report",
     "Individual PDF per flagged student: marker breakdown, conversation starters, "
     "teacher notes. For your own reference — not for students."),
    ("Excel Export",
     "All runs for a course exported to .xlsx with one row per student per assignment. "
     "Includes all marker counts for external analysis."),
    ("Trajectory Summary",
     "Semester-long sparkline export for each student — suspicion, human presence, "
     "word count, submission timing — in a printable format."),
]


class ExportReportsDialog(QDialog):
    """Stub export dialog — shows planned export types, not yet implemented."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Export Reports")
        self.setMinimumSize(520, 420)
        self.resize(560, 480)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Title bar
        title_bar = QFrame()
        title_bar.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER_AMBER};
            }}
        """)
        tb = QVBoxLayout(title_bar)
        tb.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        tb.setSpacing(4)
        title = QLabel("EXPORT REPORTS")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 14px; font-weight: bold; letter-spacing: 2px;")
        tb.addWidget(title)
        sub = QLabel("SQLite RunStore is the source of truth — exports are a read-only surface.")
        sub.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
        tb.addWidget(sub)
        root.addWidget(title_bar)

        # Coming soon banner
        banner = QFrame()
        banner.setStyleSheet(f"""
            QFrame {{
                background: {BG_INSET};
                border-bottom: 1px solid {BORDER_DARK};
            }}
        """)
        bl = QHBoxLayout(banner)
        bl.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        banner_lbl = QLabel("COMING SOON")
        banner_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 22px; font-weight: bold; letter-spacing: 6px;")
        bl.addStretch()
        bl.addWidget(banner_lbl)
        bl.addStretch()
        root.addWidget(banner)

        # Planned export list
        body = QVBoxLayout()
        body.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        body.setSpacing(SPACING_SM)

        hdr = QLabel("PLANNED EXPORT TYPES")
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        body.addWidget(hdr)

        for title_txt, desc_txt in _PLANNED:
            card = QFrame()
            card.setStyleSheet(f"""
                QFrame {{
                    background: {CARD_GRADIENT};
                    border: 1px solid {BORDER_DARK};
                    border-radius: 5px;
                }}
            """)
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)
            card_layout.setSpacing(2)

            t_lbl = QLabel(title_txt)
            t_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: 12px; font-weight: bold;")
            card_layout.addWidget(t_lbl)

            d_lbl = QLabel(desc_txt)
            d_lbl.setWordWrap(True)
            d_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: 11px;")
            card_layout.addWidget(d_lbl)

            body.addWidget(card)

        body.addStretch()
        root.addLayout(body)

        # Footer
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER_DARK};
            }}
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        fl.addStretch()
        close_btn = QPushButton("Close")
        make_secondary_button(close_btn)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        fl.addWidget(close_btn)
        root.addWidget(footer)
