"""
Settings tab: Canvas connection, output folder, cleanup, grading defaults.
"""
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QFormLayout, QGroupBox,
    QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox, QSpinBox,
    QHBoxLayout, QButtonGroup, QRadioButton, QFileDialog, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QFont

from gui.styles import SPACING_SM, SPACING_MD, make_secondary_button


class SettingsPanel(QWidget):
    """Full settings panel displayed in Tab 2."""

    settings_saved = Signal()     # emitted when Save is clicked successfully
    open_folder_requested = Signal()

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._setup_ui()
        self._load_current_settings()

    def _setup_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        outer.addWidget(scroll)

        container = QWidget()
        scroll.setWidget(container)
        vbox = QVBoxLayout(container)
        vbox.setContentsMargins(16, 16, 16, 16)
        vbox.setSpacing(SPACING_MD)

        # --- Canvas Connection ---
        conn_box = QGroupBox("Canvas Connection")
        conn_form = QFormLayout(conn_box)
        conn_form.setSpacing(SPACING_SM)

        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://yourschool.instructure.com")
        conn_form.addRow("Canvas URL:", self._url_edit)

        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("Paste your API token here")
        conn_form.addRow("API Token:", self._token_edit)

        test_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.clicked.connect(self._on_test_connection)
        make_secondary_button(self._test_btn)
        test_row.addWidget(self._test_btn)
        self._test_status = QLabel()
        test_row.addWidget(self._test_status)
        test_row.addStretch()
        conn_form.addRow("", test_row)

        profile_row = QHBoxLayout()
        self._profile_combo = QComboBox()
        self._profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_switched)
        profile_row.addWidget(self._profile_combo)
        manage_btn = QPushButton("Manage Profiles…")
        manage_btn.clicked.connect(self._on_manage_profiles)
        profile_row.addWidget(manage_btn)
        conn_form.addRow("Institution:", profile_row)

        vbox.addWidget(conn_box)

        # --- Output ---
        out_box = QGroupBox("Output")
        out_form = QFormLayout(out_box)
        out_form.setSpacing(SPACING_SM)

        folder_row = QHBoxLayout()
        self._output_edit = QLineEdit()
        folder_row.addWidget(self._output_edit)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._on_browse_output)
        folder_row.addWidget(browse_btn)
        out_form.addRow("Folder:", folder_row)

        self._auto_open_cb = QCheckBox("Auto-open folder after grading completes")
        out_form.addRow("", self._auto_open_cb)

        open_btn = QPushButton("Open Output Folder")
        open_btn.clicked.connect(self.open_folder_requested)
        out_form.addRow("", open_btn)

        vbox.addWidget(out_box)

        # --- File Cleanup ---
        clean_box = QGroupBox("File Cleanup")
        clean_vbox = QVBoxLayout(clean_box)
        clean_vbox.setSpacing(SPACING_SM)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode:"))
        self._cleanup_bg = QButtonGroup(self)
        for label, val in [("None", "none"), ("Archive", "archive"), ("Move to Trash", "trash")]:
            rb = QRadioButton(label)
            rb.setProperty("cleanup_val", val)
            self._cleanup_bg.addButton(rb)
            mode_row.addWidget(rb)
            if val == "none":
                rb.setChecked(True)
        mode_row.addStretch()
        clean_vbox.addLayout(mode_row)

        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Threshold:"))
        self._cleanup_days = QSpinBox()
        self._cleanup_days.setRange(1, 3650)
        self._cleanup_days.setValue(180)
        self._cleanup_days.setSuffix(" days")
        thresh_row.addWidget(self._cleanup_days)
        thresh_row.addStretch()
        clean_vbox.addLayout(thresh_row)

        clean_vbox.addWidget(QLabel("File types to clean:"))
        self._cleanup_checks = {}
        type_labels = {
            "ad_csv":   "Academic Integrity CSVs",
            "ad_excel": "Academic Integrity Excel reports",
            "ad_txt":   "Academic Integrity text reports",
            "ci_csv":   "Complete/Incomplete CSVs",
            "df_csv":   "Discussion Forum CSVs",
        }
        for key, label in type_labels.items():
            cb = QCheckBox(label)
            cb.setChecked(True)
            clean_vbox.addWidget(cb)
            self._cleanup_checks[key] = cb

        cleanup_now_btn = QPushButton("Run Cleanup Now…")
        cleanup_now_btn.clicked.connect(self._on_run_cleanup)
        clean_vbox.addWidget(cleanup_now_btn)

        vbox.addWidget(clean_box)

        # --- Grading Defaults ---
        grad_box = QGroupBox("Grading Defaults")
        grad_form = QFormLayout(grad_box)
        grad_form.setSpacing(SPACING_SM)

        self._default_min_words = QSpinBox()
        self._default_min_words.setRange(0, 10000)
        self._default_min_words.setValue(200)
        grad_form.addRow("Default min word count (C/I):", self._default_min_words)

        self._default_post_words = QSpinBox()
        self._default_post_words.setRange(0, 10000)
        self._default_post_words.setValue(200)
        grad_form.addRow("Default post min words:", self._default_post_words)

        self._default_reply_words = QSpinBox()
        self._default_reply_words.setRange(0, 10000)
        self._default_reply_words.setValue(50)
        grad_form.addRow("Default reply min words:", self._default_reply_words)

        vbox.addWidget(grad_box)

        # --- Save button ---
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._on_save)
        vbox.addWidget(save_btn)
        vbox.addStretch()

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        try:
            from credentials import load_credentials, get_active_profile
            from settings import load_settings
            from autograder_utils import get_output_base_dir

            # Output dir
            try:
                self._output_edit.setText(str(get_output_base_dir()))
            except Exception:
                pass

            # App settings
            s = load_settings()
            self._auto_open_cb.setChecked(bool(s.get("auto_open_folder", True)))
            mode = s.get("cleanup_mode", "none")
            for btn in self._cleanup_bg.buttons():
                if btn.property("cleanup_val") == mode:
                    btn.setChecked(True)
            self._cleanup_days.setValue(int(s.get("cleanup_threshold_days", 180)))
            targets = s.get("cleanup_targets", "all")
            for key, cb in self._cleanup_checks.items():
                cb.setChecked(targets == "all" or key in targets)

            # Credentials / profiles
            data = load_credentials()
            self._refresh_profile_combo(data)

        except Exception:
            pass

    def _refresh_profile_combo(self, data: dict) -> None:
        from credentials import get_active_profile
        self._profile_combo.blockSignals(True)
        self._profile_combo.clear()
        profiles = data.get("profiles", {})
        active_name, active_profile = get_active_profile(data)
        for name in sorted(profiles):
            self._profile_combo.addItem(name, userData=name)

        if active_name:
            idx = self._profile_combo.findData(active_name)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
            self._url_edit.setText(active_profile.get("canvas_base_url", ""))
            token = active_profile.get("canvas_api_token", "")
            self._token_edit.setText(token if token else "")
            self._token_edit.setPlaceholderText("saved" if token else "Paste your API token here")

        self._profile_combo.blockSignals(False)

    def _on_profile_switched(self, index: int) -> None:
        name = self._profile_combo.itemData(index)
        if not name:
            return
        from credentials import load_credentials
        data = load_credentials()
        profile = data.get("profiles", {}).get(name, {})
        self._url_edit.setText(profile.get("canvas_base_url", ""))
        token = profile.get("canvas_api_token", "")
        self._token_edit.setText(token if token else "")
        self._token_edit.setPlaceholderText("saved" if token else "Paste your API token here")

    def _on_test_connection(self) -> None:
        from automation.canvas_helpers import CanvasAutomationAPI
        from gui.workers import TestConnectionWorker

        url = self._url_edit.text().strip()
        token = self._token_edit.text().strip()
        if not url or not token:
            self._test_status.setText("Enter URL and token first")
            return

        self._test_status.setText("Testing…")
        self._test_btn.setEnabled(False)

        test_api = CanvasAutomationAPI(base_url=url, api_token=token)
        self._test_worker = TestConnectionWorker(test_api)
        self._test_worker.result_ready.connect(self._on_test_result)
        self._test_worker.start()

    def _on_test_result(self, ok: bool, name: str) -> None:
        self._test_btn.setEnabled(True)
        from gui.styles import STATUS_OK, STATUS_ERR
        if ok:
            label = f"Connected as {name}" if name else "Connected"
            self._test_status.setText(f"✓ {label}")
            self._test_status.setStyleSheet(f"color: {STATUS_OK}; font-weight: 600;")
        else:
            self._test_status.setText(f"✗ {name or 'Connection failed'}")
            self._test_status.setStyleSheet(f"color: {STATUS_ERR}; font-weight: 600;")

    def _on_browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Folder",
                                                   self._output_edit.text())
        if folder:
            self._output_edit.setText(folder)

    def _on_run_cleanup(self) -> None:
        from gui.dialogs.cleanup_dialog import CleanupDialog
        dlg = CleanupDialog(parent=self)
        dlg.exec()

    def _on_manage_profiles(self) -> None:
        from gui.dialogs.profile_dialog import ProfileDialog
        dlg = ProfileDialog(parent=self)
        dlg.exec()
        # Reload profile combo after dialog
        from credentials import load_credentials
        self._refresh_profile_combo(load_credentials())

    def _on_save(self) -> None:
        try:
            from credentials import (
                load_credentials, save_credentials, get_active_profile,
                profile_name_from_url,
            )
            from settings import save_settings, load_settings
            from autograder_utils import set_output_directory

            # Save credentials
            url = self._url_edit.text().strip()
            token = self._token_edit.text().strip()
            if url or token:
                data = load_credentials()
                active_name, _ = get_active_profile(data)
                profile_name = self._profile_combo.currentData() or active_name or profile_name_from_url(url) or "default"
                if "profiles" not in data:
                    data["profiles"] = {}
                if profile_name not in data["profiles"]:
                    data["profiles"][profile_name] = {}
                if url:
                    data["profiles"][profile_name]["canvas_base_url"] = url
                if token:
                    data["profiles"][profile_name]["canvas_api_token"] = token
                data["active_profile"] = profile_name
                save_credentials(data)

            # Save output dir
            out_path = self._output_edit.text().strip()
            if out_path:
                try:
                    set_output_directory(Path(out_path))
                except Exception:
                    pass

            # Save app settings
            s = load_settings()
            s["auto_open_folder"] = self._auto_open_cb.isChecked()
            for btn in self._cleanup_bg.buttons():
                if btn.isChecked():
                    s["cleanup_mode"] = btn.property("cleanup_val")
                    break
            s["cleanup_threshold_days"] = self._cleanup_days.value()
            checked = [k for k, cb in self._cleanup_checks.items() if cb.isChecked()]
            s["cleanup_targets"] = "all" if len(checked) == 5 else ",".join(checked)
            save_settings(s)

            self.settings_saved.emit()

        except Exception as exc:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Save Error", str(exc))

    # ------------------------------------------------------------------
    # Public API (called from main window after settings saved)
    # ------------------------------------------------------------------

    def get_api_credentials(self):
        """Returns (url, token) from the current field values."""
        return self._url_edit.text().strip(), self._token_edit.text().strip()
