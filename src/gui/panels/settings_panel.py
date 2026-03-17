"""
Settings tab — redesigned to match the amber terminal aesthetic.

Layout:
  ┌─ CANVAS CONNECTION ────────┬─ DATA RETENTION ──────────────┐
  │  profile, URL, token, test │  auto-delete + category chips │
  │  AIC calibration           │                               │
  └────────────────────────────┴───────────────────────────────┘
                                              [Save Settings ▶]
"""
from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton,
    QComboBox, QSpinBox, QSizePolicy,
)
from PySide6.QtCore import Signal, Qt

from gui.widgets.phosphor_chip import PhosphorChip
from gui.widgets.switch_toggle import SwitchToggle

_EDU_LEVEL_OPTIONS = [
    ("community_college", "Community College  (default)"),
    ("high_school",       "High School"),
    ("four_year",         "Four-Year College / Liberal Arts"),
    ("university",        "Research University"),
    ("online",            "Online / Distance Learning"),
]

# ESL enrollment rates: low < 10%, moderate 10–25%, high > 25%
_ESL_LEVEL_OPTIONS = [
    ("none",     "Default"),
    ("low",      "Low  (< 10% of enrollment)"),
    ("moderate", "Moderate  (10–25%)"),
    ("high",     "High  (> 25%)"),
]

# First-generation college student rates: low < 20%, moderate 20–45%, high > 45%
_FIRST_GEN_LEVEL_OPTIONS = [
    ("none",     "Default"),
    ("low",      "Low  (< 20% of enrollment)"),
    ("moderate", "Moderate  (20–45%)"),
    ("high",     "High  (> 45%)"),
]

from gui.styles import (
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    BG_VOID, BG_INSET, BORDER_DARK,
    STATUS_OK, STATUS_ERR, STATUS_WARN,
    BORDER_AMBER, AMBER_BTN,
    make_run_button, make_secondary_button,
    make_section_label, make_h_rule, make_content_pane,
)

# ---------------------------------------------------------------------------
# Small local helpers
# ---------------------------------------------------------------------------

def _field_label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: 11px; font-weight: 500;"
        f" letter-spacing: 0.8px; background: transparent; border: none;"
        f" text-transform: uppercase;"
    )
    return lbl


# ---------------------------------------------------------------------------
# SettingsPanel
# ---------------------------------------------------------------------------

class SettingsPanel(QWidget):
    """Settings page — Canvas connection, output, data retention, grading defaults."""

    settings_saved = Signal()

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._setup_ui()
        self._load_current_settings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        root.addWidget(scroll, 1)

        page = QWidget()
        page.setObjectName("settingsPage")
        page.setStyleSheet(f"QWidget#settingsPage {{ background: {BG_VOID}; }}")
        scroll.setWidget(page)

        vbox = QVBoxLayout(page)
        vbox.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        vbox.setSpacing(SPACING_MD)

        # Page header
        title = QLabel("SETTINGS")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: 16px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        sub = QLabel("Configure Canvas connection and data retention.")
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        vbox.addWidget(title)
        vbox.addWidget(sub)
        vbox.addWidget(make_h_rule())

        # Two-column row: left = Canvas Connection, right = Output + Grading Defaults + Data Retention
        cols = QHBoxLayout()
        cols.setSpacing(SPACING_MD)

        left_pane = make_content_pane("settingsConnPane")
        left_lo = QVBoxLayout(left_pane)
        left_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        left_lo.setSpacing(SPACING_SM)
        self._build_connection_section(left_lo)
        cols.addWidget(left_pane, stretch=3)

        right_col = QVBoxLayout()
        right_col.setSpacing(SPACING_SM)

        ret_pane = make_content_pane("settingsRetPane")
        ret_lo = QVBoxLayout(ret_pane)
        ret_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        ret_lo.setSpacing(SPACING_SM)
        self._build_retention_section(ret_lo)
        right_col.addWidget(ret_pane)

        acc_pane = make_content_pane("settingsAccPane")
        acc_lo = QVBoxLayout(acc_pane)
        acc_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        acc_lo.setSpacing(SPACING_SM)
        self._build_accessibility_section(acc_lo)
        right_col.addWidget(acc_pane)

        right_col.addStretch()
        cols.addLayout(right_col, stretch=1)
        vbox.addLayout(cols)

        # Insights & AI section (full-width below the two columns)
        insights_pane = make_content_pane("settingsInsightsPane")
        ins_lo = QVBoxLayout(insights_pane)
        ins_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        ins_lo.setSpacing(SPACING_SM)
        self._build_insights_section(ins_lo)
        vbox.addWidget(insights_pane)

        vbox.addStretch()

        # Footer lives OUTSIDE the scroll area so QGraphicsDropShadowEffect
        # is not clipped by the scroll viewport — matches assignment_panel pattern.
        from PySide6.QtWidgets import QFrame as _QFrame
        footer_sep = _QFrame()
        footer_sep.setFixedHeight(1)
        footer_sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        root.addWidget(footer_sep)

        footer_bar = _QFrame()
        footer_bar.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        footer_lo = QHBoxLayout(footer_bar)
        footer_lo.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        self._save_status = QLabel("")
        self._save_status.setStyleSheet(
            f"font-size: 11px; background: transparent; border: none;"
        )
        footer_lo.addStretch()
        footer_lo.addWidget(self._save_status)
        footer_lo.addSpacing(SPACING_SM)
        save_btn = QPushButton("▶  Save Settings")
        save_btn.clicked.connect(self._on_save)
        make_run_button(save_btn)
        footer_lo.addWidget(save_btn)
        root.addWidget(footer_bar)

    def _build_connection_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Canvas Connection"))
        lo.addWidget(make_h_rule())

        # Profile first
        lo.addWidget(_field_label("Institution Profile"))
        profile_row = QHBoxLayout()
        self._profile_combo = QComboBox()
        self._profile_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._profile_combo.currentIndexChanged.connect(self._on_profile_switched)
        profile_row.addWidget(self._profile_combo)
        manage_btn = QPushButton("Manage Profiles…")
        make_secondary_button(manage_btn)
        manage_btn.clicked.connect(self._on_manage_profiles)
        profile_row.addWidget(manage_btn)
        lo.addLayout(profile_row)

        lo.addWidget(make_h_rule())

        lo.addWidget(_field_label("Canvas URL"))
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("https://yourschool.instructure.com")
        lo.addWidget(self._url_edit)

        lo.addSpacing(4)
        lo.addWidget(_field_label("API Token"))
        token_row = QHBoxLayout()
        self._token_edit = QLineEdit()
        self._token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._token_edit.setPlaceholderText("Paste your API token here")
        token_row.addWidget(self._token_edit)
        self._test_btn = QPushButton("Test Connection")
        make_secondary_button(self._test_btn)
        self._test_btn.clicked.connect(self._on_test_connection)
        token_row.addWidget(self._test_btn)
        lo.addLayout(token_row)

        self._test_status = QLabel("")
        self._test_status.setStyleSheet("font-size: 12px; padding: 2px 0; background: transparent;")
        lo.addWidget(self._test_status)

        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("Academic Integrity — Per-Profile Calibration"))
        aic_note = QLabel(
            "These settings travel with the institution profile. "
            "Weights adjust to your school's specific student population."
        )
        aic_note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; background: transparent; padding: 2px 0;"
        )
        aic_note.setWordWrap(True)
        lo.addWidget(aic_note)

        lo.addWidget(_field_label("Education Level"))
        self._edu_level_combo = QComboBox()
        self._edu_level_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._edu_level_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _EDU_LEVEL_OPTIONS:
            self._edu_level_combo.addItem(plabel, pid)
        edu_row = QHBoxLayout()
        edu_row.addWidget(self._edu_level_combo)
        edu_row.addStretch()
        lo.addLayout(edu_row)

        lo.addSpacing(4)
        pop_row = QHBoxLayout()
        pop_row.setSpacing(16)

        esl_col = QVBoxLayout()
        esl_col.setSpacing(2)
        esl_col.addWidget(_field_label("ESL Population"))
        self._pop_esl_combo = QComboBox()
        self._pop_esl_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._pop_esl_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _ESL_LEVEL_OPTIONS:
            self._pop_esl_combo.addItem(plabel, pid)
        esl_col.addWidget(self._pop_esl_combo)
        pop_row.addLayout(esl_col)

        fg_col = QVBoxLayout()
        fg_col.setSpacing(2)
        fg_col.addWidget(_field_label("First-Gen Population"))
        self._pop_first_gen_combo = QComboBox()
        self._pop_first_gen_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._pop_first_gen_combo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        for pid, plabel in _FIRST_GEN_LEVEL_OPTIONS:
            self._pop_first_gen_combo.addItem(plabel, pid)
        fg_col.addWidget(self._pop_first_gen_combo)
        pop_row.addLayout(fg_col)

        pop_row.addStretch()
        lo.addLayout(pop_row)

        lo.addSpacing(4)
        self._pop_nd_check = SwitchToggle("Neurodivergent-aware scoring", wrap_width=200)
        lo.addWidget(self._pop_nd_check)

        lo.addSpacing(8)
        tune_btn = QPushButton("Fine-Tune Signals…")
        make_secondary_button(tune_btn)
        tune_btn.clicked.connect(self._on_open_signal_tuning)
        lo.addWidget(tune_btn)
        lo.addStretch()

    def _build_insights_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Insights & AI"))
        lo.addWidget(make_h_rule())
        lo.addWidget(QLabel(
            "Configure the AI models used by Generate Insights.\n"
            "Local models keep student data on your machine (FERPA-safe)."
        ))

        # Two-column: left = local model, right = cloud/institutional
        cols = QHBoxLayout()
        cols.setSpacing(SPACING_LG)

        # ── Left: Local Model ──
        left = QVBoxLayout()
        left.setSpacing(SPACING_SM)

        left.addWidget(_field_label("Local Model Backend"))
        self._llm_backend_combo = QComboBox()
        self._llm_backend_combo.addItem("Ollama (recommended)", "ollama")
        self._llm_backend_combo.addItem("MLX (Apple Silicon)", "mlx")
        self._llm_backend_combo.currentIndexChanged.connect(
            self._on_llm_backend_changed
        )
        left.addWidget(self._llm_backend_combo)

        left.addWidget(_field_label("Ollama Model"))
        self._llm_model_edit = QLineEdit()
        self._llm_model_edit.setPlaceholderText("llama3.1:8b")
        self._llm_model_edit.setText("llama3.1:8b")
        left.addWidget(self._llm_model_edit)

        left.addWidget(_field_label("Ollama URL"))
        self._ollama_url_edit = QLineEdit()
        self._ollama_url_edit.setPlaceholderText("http://localhost:11434")
        self._ollama_url_edit.setText("http://localhost:11434")
        left.addWidget(self._ollama_url_edit)

        # Status check
        self._llm_status = QLabel("")
        self._llm_status.setStyleSheet(
            f"font-size: 11px; background: transparent; border: none;"
        )
        left.addWidget(self._llm_status)

        check_btn = QPushButton("Check Model")
        make_secondary_button(check_btn)
        check_btn.clicked.connect(self._check_llm_status)
        left.addWidget(check_btn)

        left.addStretch()
        cols.addLayout(left, stretch=1)

        # ── Right: Cloud / Institutional API ──
        right = QVBoxLayout()
        right.setSpacing(SPACING_SM)

        right.addWidget(_field_label("Institutional / Cloud API (optional)"))
        right.addWidget(QLabel(
            "If your institution provides an AI API, configure it here.\n"
            "Used for Medium and Deep Thinking analysis tiers.\n"
            "Check with your IT department for FERPA compliance."
        ))

        right.addWidget(_field_label("API Base URL"))
        self._cloud_url_edit = QLineEdit()
        self._cloud_url_edit.setPlaceholderText(
            "e.g., https://your-institution.openai.azure.com/v1"
        )
        right.addWidget(self._cloud_url_edit)

        right.addWidget(_field_label("API Key"))
        self._cloud_key_edit = QLineEdit()
        self._cloud_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._cloud_key_edit.setPlaceholderText("Paste institutional API key")
        right.addWidget(self._cloud_key_edit)

        right.addWidget(_field_label("Model Name"))
        self._cloud_model_edit = QLineEdit()
        self._cloud_model_edit.setPlaceholderText("e.g., gpt-4o, claude-sonnet-4-20250514")
        right.addWidget(self._cloud_model_edit)

        self._ferpa_label = QLabel(
            "⚠ Cloud APIs send student text to external servers.\n"
            "Only use if your institution has a data processing agreement."
        )
        self._ferpa_label.setWordWrap(True)
        self._ferpa_label.setStyleSheet(
            f"color: {STATUS_WARN}; font-size: 11px;"
            f" background: transparent; border: none; padding: 4px 0;"
        )
        right.addWidget(self._ferpa_label)

        right.addStretch()
        cols.addLayout(right, stretch=1)

        lo.addLayout(cols)

        # ── Bottom row: throttle + whisper ──
        lo.addWidget(make_h_rule())
        bottom = QHBoxLayout()
        bottom.setSpacing(SPACING_LG)

        # Throttle
        throttle_col = QVBoxLayout()
        throttle_col.addWidget(_field_label("Pause Between Prompts"))
        self._throttle_spin = QSpinBox()
        self._throttle_spin.setRange(0, 30)
        self._throttle_spin.setValue(0)
        self._throttle_spin.setSuffix(" seconds")
        throttle_col.addWidget(self._throttle_spin)
        throttle_col.addWidget(QLabel(
            "How long to pause between AI prompts.\n"
            "0 = fastest (best for overnight / while you sleep).\n"
            "10-15 = keeps your computer responsive if you're\n"
            "still working while the analysis runs."
        ))
        bottom.addLayout(throttle_col, stretch=1)

        # Whisper model
        whisper_col = QVBoxLayout()
        whisper_col.addWidget(_field_label("Whisper Model (Audio Transcription)"))
        self._whisper_combo = QComboBox()
        self._whisper_combo.addItem("tiny — fastest, lowest quality", "tiny")
        self._whisper_combo.addItem("base — good balance (recommended)", "base")
        self._whisper_combo.addItem("small — better quality, ~2GB RAM", "small")
        self._whisper_combo.addItem("medium — high quality, ~5GB RAM", "medium")
        self._whisper_combo.addItem("large-v3 — best quality, ~10GB RAM", "large-v3")
        self._whisper_combo.setCurrentIndex(1)  # base
        whisper_col.addWidget(self._whisper_combo)
        whisper_col.addWidget(QLabel(
            "Used for transcribing audio/video submissions.\n"
            "Runs locally — no audio data leaves your machine."
        ))
        bottom.addLayout(whisper_col, stretch=1)

        lo.addLayout(bottom)

    def _on_llm_backend_changed(self, index: int) -> None:
        is_ollama = self._llm_backend_combo.currentData() == "ollama"
        self._llm_model_edit.setEnabled(is_ollama)
        self._ollama_url_edit.setEnabled(is_ollama)

    def _check_llm_status(self) -> None:
        """Test if the configured LLM backend is reachable."""
        import requests as _req
        backend = self._llm_backend_combo.currentData()
        if backend == "ollama":
            url = self._ollama_url_edit.text().strip() or "http://localhost:11434"
            model = self._llm_model_edit.text().strip() or "llama3.1:8b"
            try:
                r = _req.get(f"{url}/api/tags", timeout=5)
                if r.status_code == 200:
                    models = [m["name"] for m in r.json().get("models", [])]
                    if any(m == model or m.startswith(model.split(":")[0])
                           for m in models):
                        self._llm_status.setText(f"✓ {model} available")
                        self._llm_status.setStyleSheet(
                            f"color: {STATUS_OK}; font-size: 11px;"
                            f" background: transparent; border: none;"
                        )
                    else:
                        available = ", ".join(models[:5])
                        self._llm_status.setText(
                            f"✗ {model} not found. Available: {available}"
                        )
                        self._llm_status.setStyleSheet(
                            f"color: {STATUS_ERR}; font-size: 11px;"
                            f" background: transparent; border: none;"
                        )
                else:
                    self._llm_status.setText("✗ Ollama not responding")
                    self._llm_status.setStyleSheet(
                        f"color: {STATUS_ERR}; font-size: 11px;"
                        f" background: transparent; border: none;"
                    )
            except Exception:
                self._llm_status.setText(
                    "✗ Cannot reach Ollama. Is it running? "
                    "(Terminal: ollama serve)"
                )
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_ERR}; font-size: 11px;"
                    f" background: transparent; border: none;"
                )
        elif backend == "mlx":
            try:
                import mlx_lm  # noqa: F401
                self._llm_status.setText("✓ MLX available")
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_OK}; font-size: 11px;"
                    f" background: transparent; border: none;"
                )
            except ImportError:
                self._llm_status.setText(
                    "✗ mlx-lm not installed. "
                    "Terminal: pip install mlx-lm"
                )
                self._llm_status.setStyleSheet(
                    f"color: {STATUS_ERR}; font-size: 11px;"
                    f" background: transparent; border: none;"
                )

    def _build_retention_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Data Retention"))
        lo.addWidget(make_h_rule())

        desc = QLabel(
            "Reports and AIC data are stored internally and exported on demand. "
            "Auto-delete aged internal data below."
        )
        desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px;"
            f" background: transparent; padding: 2px 0;"
        )
        desc.setWordWrap(True)
        lo.addWidget(desc)

        # Auto-delete master toggle + threshold
        self._retention_enabled_cb = SwitchToggle("Auto-delete internal data", wrap_width=160)
        lo.addWidget(self._retention_enabled_cb)

        days_row = QHBoxLayout()
        days_row.addSpacing(43)   # indent past track width
        older_lbl = QLabel("older than")
        older_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 11px; background: transparent;"
        )
        days_row.addWidget(older_lbl)
        self._retention_days = QSpinBox()
        self._retention_days.setRange(1, 3650)
        self._retention_days.setValue(90)
        self._retention_days.setSuffix(" days")
        days_row.addWidget(self._retention_days)
        days_row.addStretch()
        lo.addLayout(days_row)

        # Category selection chips (which data types to include)
        cats_row = QHBoxLayout()
        cats_row.addSpacing(43)
        self._retention_grading_cb = PhosphorChip("Grading Reports", accent="amber")
        self._retention_grading_cb.setChecked(True)
        cats_row.addWidget(self._retention_grading_cb)
        cats_row.addSpacing(6)
        self._retention_aic_cb = PhosphorChip("AIC Data", accent="amber")
        self._retention_aic_cb.setChecked(True)
        cats_row.addWidget(self._retention_aic_cb)
        cats_row.addStretch()
        lo.addLayout(cats_row)

        self._retention_enabled_cb.toggled.connect(self._on_retention_toggled)
        self._on_retention_toggled(self._retention_enabled_cb.isChecked())

        lo.addStretch()
        lo.addWidget(make_h_rule())

        cleanup_row = QHBoxLayout()
        cleanup_row.addStretch()
        cleanup_btn = QPushButton("⊙  Clean Up Now…")
        cleanup_btn.clicked.connect(self._on_run_cleanup)
        make_secondary_button(cleanup_btn)
        cleanup_row.addWidget(cleanup_btn)
        lo.addLayout(cleanup_row)

    def _build_accessibility_section(self, lo: QVBoxLayout) -> None:
        lo.addWidget(make_section_label("Accessibility"))
        lo.addWidget(make_h_rule())

        lo.addWidget(_field_label("Text Size"))
        self._text_size_combo = QComboBox()
        self._text_size_combo.addItem("Small", 1.0)
        self._text_size_combo.addItem("Default", 1.25)
        self._text_size_combo.addItem("Large", 1.5)
        lo.addWidget(self._text_size_combo)

        note = QLabel("Takes effect after saving and restarting.")
        note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        note.setWordWrap(True)
        lo.addWidget(note)
        lo.addStretch()

    def _on_open_signal_tuning(self) -> None:
        from gui.dialogs.signal_tuning_dialog import SignalTuningDialog
        dlg = SignalTuningDialog(parent=self)
        dlg.exec()

    # ------------------------------------------------------------------
    # Signals / slots
    # ------------------------------------------------------------------

    def _on_retention_toggled(self, enabled: bool) -> None:
        self._retention_days.setEnabled(enabled)

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
        if ok:
            label = f"Connected as {name}" if name else "Connected"
            self._test_status.setText(f"✓ {label}")
            self._test_status.setStyleSheet(f"color: {STATUS_OK}; font-weight: 600; background: transparent;")
        else:
            self._test_status.setText(f"✗ {name or 'Connection failed'}")
            self._test_status.setStyleSheet(f"color: {STATUS_ERR}; font-weight: 600; background: transparent;")

    def _on_run_cleanup(self) -> None:
        from gui.dialogs.cleanup_dialog import CleanupDialog
        dlg = CleanupDialog(parent=self)
        dlg.exec()

    def _on_manage_profiles(self) -> None:
        from gui.dialogs.profile_dialog import ProfileDialog
        dlg = ProfileDialog(parent=self)
        dlg.exec()
        from credentials import load_credentials
        self._refresh_profile_combo(load_credentials())

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------

    def _load_current_settings(self) -> None:
        try:
            from credentials import load_credentials
            from settings import load_settings

            s = load_settings()

            # Data retention — prefer new keys, fall back to legacy cleanup keys
            retention_enabled = s.get("data_retention_enabled",
                                       s.get("cleanup_mode", "none") != "none")
            self._retention_enabled_cb.setChecked(bool(retention_enabled))

            legacy_days = s.get("cleanup_threshold_days", 180)
            self._retention_days.setValue(int(s.get("data_retention_days", legacy_days)))

            self._retention_grading_cb.setChecked(bool(s.get("data_retention_grading", True)))
            self._retention_aic_cb.setChecked(bool(s.get("data_retention_aic", True)))
            self._on_retention_toggled(bool(retention_enabled))

            # Insights & AI settings
            backend = s.get("insights_llm_backend", "ollama")
            idx = self._llm_backend_combo.findData(backend)
            if idx >= 0:
                self._llm_backend_combo.setCurrentIndex(idx)
            self._llm_model_edit.setText(
                s.get("insights_translation_model", "llama3.1:8b")
            )
            self._ollama_url_edit.setText(
                s.get("insights_ollama_url", "http://localhost:11434")
            )
            self._cloud_url_edit.setText(s.get("insights_cloud_url", ""))
            self._cloud_key_edit.setText(s.get("insights_cloud_key", ""))
            self._cloud_model_edit.setText(s.get("insights_cloud_model", ""))
            self._throttle_spin.setValue(
                int(s.get("insights_throttle_delay", 2))
            )
            whisper = s.get("insights_whisper_model", "base")
            widx = self._whisper_combo.findData(whisper)
            if widx >= 0:
                self._whisper_combo.setCurrentIndex(widx)

            # Accessibility
            font_scale = float(s.get("font_scale", 1.0))
            sidx = self._text_size_combo.findData(font_scale)
            if sidx >= 0:
                self._text_size_combo.setCurrentIndex(sidx)

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
            display = name.replace("_", " ").replace("-", " ").title()
            self._profile_combo.addItem(display, userData=name)
        if active_name:
            idx = self._profile_combo.findData(active_name)
            if idx >= 0:
                self._profile_combo.setCurrentIndex(idx)
            self._url_edit.setText(active_profile.get("canvas_base_url", ""))
            token = active_profile.get("canvas_api_token", "")
            self._token_edit.setText(token if token else "")
            self._token_edit.setPlaceholderText("saved" if token else "Paste your API token here")
            self._load_aic_from_profile(active_profile)
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
        self._load_aic_from_profile(profile)

    def _load_aic_from_profile(self, profile: dict) -> None:
        """Populate the AIC calibration controls from a credential profile dict."""
        edu = profile.get("education_level", "community_college")
        idx = self._edu_level_combo.findData(edu)
        if idx >= 0:
            self._edu_level_combo.setCurrentIndex(idx)

        esl = profile.get("population_esl", "none")
        idx = self._pop_esl_combo.findData(esl)
        if idx >= 0:
            self._pop_esl_combo.setCurrentIndex(idx)

        fg = profile.get("population_first_gen", "none")
        idx = self._pop_first_gen_combo.findData(fg)
        if idx >= 0:
            self._pop_first_gen_combo.setCurrentIndex(idx)

        self._pop_nd_check.setChecked(bool(profile.get("population_neurodivergent_aware", False)))

    def _on_save(self) -> None:
        try:
            from credentials import (
                load_credentials, save_credentials, get_active_profile,
                profile_name_from_url,
            )
            from settings import save_settings, load_settings

            # Credentials
            url = self._url_edit.text().strip()
            token = self._token_edit.text().strip()
            data = load_credentials()
            active_name, _ = get_active_profile(data)
            profile_name = (
                self._profile_combo.currentData()
                or active_name
                or profile_name_from_url(url)
                or "default"
            )
            if "profiles" not in data:
                data["profiles"] = {}
            if profile_name not in data["profiles"]:
                data["profiles"][profile_name] = {}
            if url:
                data["profiles"][profile_name]["canvas_base_url"] = url
            if token:
                data["profiles"][profile_name]["canvas_api_token"] = token
            # AIC per-profile calibration settings
            data["profiles"][profile_name]["education_level"] = (
                self._edu_level_combo.currentData() or "community_college"
            )
            data["profiles"][profile_name]["population_esl"] = (
                self._pop_esl_combo.currentData() or "none"
            )
            data["profiles"][profile_name]["population_first_gen"] = (
                self._pop_first_gen_combo.currentData() or "none"
            )
            data["profiles"][profile_name]["population_neurodivergent_aware"] = (
                self._pop_nd_check.isChecked()
            )
            if url or token:
                data["active_profile"] = profile_name
            save_credentials(data)

            s = load_settings()

            # Data retention — save new keys and also translate to legacy cleanup keys
            enabled = self._retention_enabled_cb.isChecked()
            days = self._retention_days.value()
            incl_grading = self._retention_grading_cb.isChecked()
            incl_aic = self._retention_aic_cb.isChecked()

            s["data_retention_enabled"] = enabled
            s["data_retention_days"] = days
            s["data_retention_grading"] = incl_grading
            s["data_retention_aic"] = incl_aic

            # Legacy cleanup keys (used by TUI and cleanup.py)
            s["cleanup_mode"] = "trash" if enabled else "none"
            s["cleanup_threshold_days"] = days
            targets = []
            if incl_grading:
                targets += ["ci_csv", "df_csv"]
            if incl_aic:
                targets += ["ad_csv", "ad_excel", "ad_txt"]
            s["cleanup_targets"] = "all" if len(targets) == 5 else ",".join(targets)

            # Insights & AI
            s["insights_llm_backend"] = (
                self._llm_backend_combo.currentData() or "ollama"
            )
            s["insights_translation_model"] = (
                self._llm_model_edit.text().strip() or "llama3.1:8b"
            )
            s["insights_ollama_url"] = (
                self._ollama_url_edit.text().strip() or "http://localhost:11434"
            )
            s["insights_cloud_url"] = self._cloud_url_edit.text().strip()
            s["insights_cloud_key"] = self._cloud_key_edit.text().strip()
            s["insights_cloud_model"] = self._cloud_model_edit.text().strip()
            s["insights_throttle_delay"] = self._throttle_spin.value()
            s["insights_whisper_model"] = (
                self._whisper_combo.currentData() or "base"
            )

            # Accessibility
            s["font_scale"] = self._text_size_combo.currentData() or 1.0

            save_settings(s)
            self.settings_saved.emit()
            self._flash_save_status("Settings saved.", ok=True)

        except Exception as exc:
            self._flash_save_status(f"Save failed: {exc}", ok=False)

    def _flash_save_status(self, msg: str, ok: bool) -> None:
        from PySide6.QtCore import QTimer
        color = STATUS_OK if ok else STATUS_ERR
        self._save_status.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent; border: none;"
        )
        self._save_status.setText(msg)
        QTimer.singleShot(3000, lambda: self._save_status.setText(""))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_api_credentials(self):
        """Returns (url, token) from the current field values."""
        return self._url_edit.text().strip(), self._token_edit.text().strip()
