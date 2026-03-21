"""
Chatbot Export Dialog — export analysis packages for external chatbots.

Shows a FERPA warning that the teacher must acknowledge before exporting.
Offers two modes: Full Analysis (raw submissions) or Synthesis Only
(pre-coded records). Provides Copy to Clipboard and Save as File options.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QCheckBox, QComboBox, QFileDialog, QTextEdit,
    QScrollArea, QWidget,
)
from PySide6.QtCore import Qt

from gui.widgets.crt_combo import CRTComboBox
from gui.styles import (
    px,
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT, ROSE_DIM, TERM_GREEN, BURN_RED,
    STATUS_WARN, AMBER_BTN,
    BG_VOID, BG_CARD, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    make_section_label, make_h_rule, make_content_pane,
    make_run_button, make_secondary_button,
    combo_qss,
)

log = logging.getLogger(__name__)


class ChatbotExportDialog(QDialog):
    """Dialog for exporting analysis data to paste into a chatbot.

    Shows FERPA warning, export mode selector, preview, and
    copy/save actions.
    """

    def __init__(
        self,
        *,
        store,
        run_id: str,
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._run_id = run_id
        self._export_content = ""

        self.setWindowTitle("Export for Chatbot Analysis")
        self.setMinimumSize(700, 600)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")

        self._build_ui()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        lo.setSpacing(SPACING_MD)

        # Title
        title = QLabel("EXPORT FOR CHATBOT")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        lo.addWidget(title)

        # ── FERPA Warning (prominent, must acknowledge) ──
        ferpa_frame = make_content_pane("ferpaWarning")
        ferpa_frame.setStyleSheet(
            f"QFrame#ferpaWarning {{"
            f"  background: rgba(192,64,32,0.12);"
            f"  border: 2px solid {BURN_RED};"
            f"  border-radius: 8px;"
            f"}}"
        )
        ferpa_lo = QVBoxLayout(ferpa_frame)
        ferpa_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        ferpa_lo.setSpacing(SPACING_SM)

        warn_icon = QLabel("\u26a0\ufe0f  FERPA WARNING")
        warn_icon.setStyleSheet(
            f"color: {BURN_RED}; font-size: {px(15)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        ferpa_lo.addWidget(warn_icon)

        warn_text = QLabel(
            "This export contains student names and their actual coursework. "
            "Before pasting into ANY chatbot or AI tool, you must verify:\n\n"
            "\u2022  Your institution has a Data Processing Agreement (DPA) "
            "with the chatbot provider\n"
            "\u2022  Your use is authorized under your institution's AI policy\n"
            "\u2022  The chatbot is NOT using your inputs for training\n\n"
            "If you are unsure about any of these, do not export. "
            "Run the analysis locally instead \u2014 the Insights Engine "
            "keeps all student data on your computer."
        )
        warn_text.setWordWrap(True)
        warn_text.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        ferpa_lo.addWidget(warn_text)

        self._ferpa_check = QCheckBox(
            "I confirm my institutional chatbot use is FERPA-compliant "
            "for student data"
        )
        self._ferpa_check.setStyleSheet(
            f"QCheckBox {{ color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" font-weight: bold; background: transparent; }}"
        )
        self._ferpa_check.toggled.connect(self._on_ferpa_toggled)
        ferpa_lo.addWidget(self._ferpa_check)

        lo.addWidget(ferpa_frame)

        # ── Export mode selector ──
        mode_row = QHBoxLayout()
        mode_row.setSpacing(SPACING_SM)
        mode_row.addWidget(QLabel("Export mode:"))

        self._mode_combo = CRTComboBox()
        self._mode_combo.addItems([
            "Synthesis (coded records + prompt)  [recommended]",
            "Full Analysis (submissions + prompt)",
        ])
        self._mode_combo.currentIndexChanged.connect(self._generate_preview)
        mode_row.addWidget(self._mode_combo, 1)
        lo.addLayout(mode_row)

        # Mode descriptions
        self._mode_desc = QLabel("")
        self._mode_desc.setWordWrap(True)
        self._mode_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._mode_desc)

        # ── Preview ──
        lo.addWidget(make_section_label("Preview"))

        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setStyleSheet(
            f"QTextEdit {{"
            f"  background: {BG_INSET};"
            f"  border: 1px solid {BORDER_DARK};"
            f"  border-radius: 6px;"
            f"  color: {PHOSPHOR_DIM};"
            f"  font-family: 'JetBrains Mono', 'Cascadia Code', 'Menlo',"
            f"   'Consolas', monospace;"
            f"  font-size: {px(10)}px;"
            f"  padding: 8px;"
            f"}}"
        )
        lo.addWidget(self._preview, 1)

        # ── Size indicator ──
        self._size_label = QLabel("")
        self._size_label.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._size_label)

        # ── Action buttons (disabled until FERPA acknowledged) ──
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._copy_btn = QPushButton("Copy to Clipboard")
        make_run_button(self._copy_btn)
        self._copy_btn.setEnabled(False)
        self._copy_btn.clicked.connect(self._on_copy)
        btn_row.addWidget(self._copy_btn)

        self._save_btn = QPushButton("Save as File")
        make_secondary_button(self._save_btn)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)

        close_btn = QPushButton("Cancel")
        close_btn.clicked.connect(self.reject)
        btn_row.addWidget(close_btn)

        lo.addLayout(btn_row)

        # Generate initial preview
        self._generate_preview()

    def _on_ferpa_toggled(self, checked: bool):
        """Enable/disable export buttons based on FERPA acknowledgment."""
        self._copy_btn.setEnabled(checked)
        self._save_btn.setEnabled(checked)

    def _generate_preview(self):
        """Generate the export content and show preview."""
        from insights.chatbot_export import (
            export_full_analysis,
            export_synthesis_only,
            format_quick_analysis_for_export,
        )

        run = self._store.get_run(self._run_id)
        if not run:
            self._preview.setPlainText("Run not found.")
            return

        course_name = run.get("course_name", "")
        assignment_name = run.get("assignment_name", "")
        teacher_context = run.get("teacher_context", "")
        qa_json = run.get("quick_analysis", "")

        qa_summary = format_quick_analysis_for_export(qa_json) if qa_json else ""

        mode_idx = self._mode_combo.currentIndex()

        # Load coded records (available for both modes)
        codings = self._store.get_codings(self._run_id)
        records = []
        for row in codings:
            rec = row.get("coding_record", {})
            if isinstance(rec, str):
                try:
                    rec = json.loads(rec)
                except Exception:
                    rec = {}
            records.append(rec)

        if mode_idx == 0:
            # Synthesis — use coded records (recommended)
            self._mode_desc.setText(
                "Exports the coded analysis records (themes, quotes, concerns "
                "per student) with a synthesis prompt. The chatbot interprets "
                "and connects the patterns. Best when local coding completed "
                "but synthesis timed out, or you want a more capable model's "
                "interpretation."
            )

            self._export_content = export_synthesis_only(
                course_name=course_name,
                assignment_name=assignment_name,
                coding_records=records,
                teacher_context=teacher_context,
                quick_analysis_summary=qa_summary,
            )

        else:
            # Full Analysis — uses coded records since raw text isn't stored
            self._mode_desc.setText(
                "Exports coding records with a full analysis prompt that asks "
                "the chatbot to re-examine patterns, generate themes, surface "
                "outliers, and build a complete report. Best when you want a "
                "fresh perspective from a more capable model.\n\n"
                "Note: Raw submission texts are not stored after analysis. "
                "This export uses the coded records (quotes, themes, concepts) "
                "which contain the essential content from each submission."
            )

            # Build submissions from stored text (or coded records as fallback)
            submissions = []
            for i, rec in enumerate(records):
                row = codings[i] if i < len(codings) else {}
                stored_text = row.get("submission_text", "")

                if stored_text and stored_text.strip():
                    body = stored_text
                else:
                    # Fallback: reconstruct from quotes + connections
                    parts = []
                    for q in rec.get("notable_quotes", []):
                        text = q.get("text", "") if isinstance(q, dict) else str(q)
                        if text:
                            parts.append(text)
                    connections = rec.get("personal_connections", [])
                    if connections:
                        parts.append("Personal connections: " + "; ".join(connections))
                    body = "\n".join(parts) if parts else ""

                submissions.append({
                    "student_name": rec.get("student_name", "Unknown"),
                    "body": body,
                    "word_count": rec.get("word_count", 0),
                })

            self._export_content = export_full_analysis(
                course_name=course_name,
                assignment_name=assignment_name,
                submissions=submissions,
                teacher_context=teacher_context,
                quick_analysis_summary=qa_summary,
            )

        # Show preview (first 3000 chars)
        preview_text = self._export_content
        if len(preview_text) > 3000:
            preview_text = preview_text[:3000] + "\n\n... (truncated in preview)"
        self._preview.setPlainText(preview_text)

        # Size info
        size_kb = len(self._export_content.encode("utf-8")) / 1024
        word_count = len(self._export_content.split())
        # Rough token estimate (1 token ≈ 4 chars for English)
        token_est = len(self._export_content) // 4

        size_text = f"{size_kb:.1f} KB  ·  ~{word_count:,} words  ·  ~{token_est:,} tokens"

        if token_est > 100_000:
            size_text += (
                f"  ·  \u26a0 This may exceed some chatbot context limits. "
                f"Consider using Synthesis Only mode."
            )
            self._size_label.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )
        else:
            self._size_label.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
                f" background: transparent; border: none;"
            )

        self._size_label.setText(size_text)

    def _on_copy(self):
        """Copy export content to clipboard."""
        clipboard = QApplication.clipboard()
        clipboard.setText(self._export_content)
        self._copy_btn.setText("\u2713  Copied!")
        self._copy_btn.setEnabled(False)
        # Re-enable after 2 seconds
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2000, lambda: (
            self._copy_btn.setText("Copy to Clipboard"),
            self._copy_btn.setEnabled(self._ferpa_check.isChecked()),
        ))

    def _on_save(self):
        """Save export content to a file."""
        run = self._store.get_run(self._run_id)
        assign_name = run.get("assignment_name", "analysis") if run else "analysis"
        # Sanitize for filename
        safe_name = "".join(c if c.isalnum() or c in " -_" else "_" for c in assign_name)
        default_name = f"{safe_name}_chatbot_export.md"

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Chatbot Export",
            default_name,
            "Markdown Files (*.md);;Text Files (*.txt);;All Files (*)",
        )
        if path:
            try:
                Path(path).write_text(self._export_content, encoding="utf-8")
                self._save_btn.setText("\u2713  Saved!")
                from PySide6.QtCore import QTimer
                QTimer.singleShot(2000, lambda: self._save_btn.setText("Save as File"))
            except Exception as e:
                self._save_btn.setText(f"Error: {e}")
