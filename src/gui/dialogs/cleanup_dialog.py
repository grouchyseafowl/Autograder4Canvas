"""
One-time cleanup wizard — immediately deletes selected records from the internal SQLite database.

This is a full system clear; it is separate from the auto-delete schedule in Settings > Data Retention.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QLabel,
)

from gui.styles import (
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT,
    make_section_label, make_h_rule, make_content_pane,
    make_run_button, make_secondary_button,
    BG_VOID,
)
from gui.widgets.switch_toggle import SwitchToggle
from gui.dialogs.message_dialog import show_info, show_warning


class CleanupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run Cleanup")
        self.setMinimumWidth(440)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")
        self._setup_ui()
        self._update_preview()

    # ── UI construction ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)

        # Categories pane
        pane = make_content_pane("cleanupCatsPane")
        pane_lo = QVBoxLayout(pane)
        pane_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        pane_lo.setSpacing(SPACING_SM)

        pane_lo.addWidget(make_section_label("Data to Remove"))
        pane_lo.addWidget(make_h_rule())

        self._sw_grading = SwitchToggle("Grading results  (Complete/Incomplete and Discussion Forum runs)", wrap_width=300)
        self._sw_grading.setChecked(True)
        self._sw_grading.toggled.connect(self._update_preview)
        pane_lo.addWidget(self._sw_grading)

        self._sw_aic = SwitchToggle("Academic Integrity Check results", wrap_width=300)
        self._sw_aic.setChecked(True)
        self._sw_aic.toggled.connect(self._update_preview)
        pane_lo.addWidget(self._sw_aic)

        self._sw_notes = SwitchToggle("Teacher notes", wrap_width=300)
        self._sw_notes.setChecked(False)
        self._sw_notes.toggled.connect(self._update_preview)
        pane_lo.addWidget(self._sw_notes)

        self._sw_profiles = SwitchToggle(
            "Per-student profile overrides", wrap_width=300
        )
        self._sw_profiles.setChecked(False)
        self._sw_profiles.toggled.connect(self._update_preview)
        pane_lo.addWidget(self._sw_profiles)

        layout.addWidget(pane)

        # Preview
        self._preview_label = QLabel("Preview: calculating\u2026")
        self._preview_label.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 11px; background: transparent;"
        )
        layout.addWidget(self._preview_label)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        from PySide6.QtWidgets import QPushButton
        cancel = QPushButton("Cancel")
        make_secondary_button(cancel)
        cancel.clicked.connect(self.reject)
        self._run_btn = QPushButton("Delete Records")
        make_run_button(self._run_btn)
        self._run_btn.clicked.connect(self._on_run)
        btn_row.addWidget(cancel)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

    # ── Helpers ────────────────────────────────────────────────────────────

    def _update_preview(self, *_) -> None:
        if not any([
            self._sw_grading.isChecked(),
            self._sw_aic.isChecked(),
            self._sw_notes.isChecked(),
            self._sw_profiles.isChecked(),
        ]):
            self._preview_label.setText("Preview: select at least one category.")
            return
        try:
            from automation.run_store import RunStore
            store = RunStore()
            counts = store.count_for_cleanup(
                0,
                include_aic=self._sw_aic.isChecked(),
                include_grading=self._sw_grading.isChecked(),
                include_notes=self._sw_notes.isChecked(),
                include_profiles=self._sw_profiles.isChecked(),
            )
            store.close()
            total = sum(counts.values())
            parts = []
            if self._sw_grading.isChecked():
                parts.append(f"{counts['grading']} grading")
            if self._sw_aic.isChecked():
                parts.append(f"{counts['aic']} AIC")
            if self._sw_notes.isChecked():
                parts.append(f"{counts['notes']} notes")
            if self._sw_profiles.isChecked():
                parts.append(f"{counts['profiles']} profile overrides")
            detail = ",  ".join(parts)
            self._preview_label.setText(
                f"Preview: {total} record{'s' if total != 1 else ''} would be deleted  \u2014  {detail}"
            )
        except Exception as exc:
            self._preview_label.setText(f"Preview unavailable: {exc}")

    def _on_run(self) -> None:
        if not any([
            self._sw_grading.isChecked(),
            self._sw_aic.isChecked(),
            self._sw_notes.isChecked(),
            self._sw_profiles.isChecked(),
        ]):
            show_warning(self, "No Categories", "Select at least one data category.")
            return
        try:
            from automation.run_store import RunStore
            store = RunStore()
            deleted = store.delete_for_cleanup(
                0,
                include_aic=self._sw_aic.isChecked(),
                include_grading=self._sw_grading.isChecked(),
                include_notes=self._sw_notes.isChecked(),
                include_profiles=self._sw_profiles.isChecked(),
            )
            store.close()
            total = sum(deleted.values())
            parts = []
            if self._sw_grading.isChecked():
                parts.append(f"{deleted['grading']} grading")
            if self._sw_aic.isChecked():
                parts.append(f"{deleted['aic']} AIC")
            if self._sw_notes.isChecked():
                parts.append(f"{deleted['notes']} notes")
            if self._sw_profiles.isChecked():
                parts.append(f"{deleted['profiles']} profile overrides")
            detail = ",  ".join(parts)
            show_info(
                self, "Cleanup Complete",
                f"Deleted {total} record{'s' if total != 1 else ''}.\n{detail}",
            )
            self.accept()
        except Exception as exc:
            show_warning(self, "Cleanup Error", str(exc))
