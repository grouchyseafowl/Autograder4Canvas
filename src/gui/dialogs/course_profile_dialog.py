"""
Course Profile Dialog — manage per-course teacher profiles and reusable templates.

Three-panel layout (mirrors TemplateEditorDialog):
  Left   — saved template list + New / Delete buttons
  Centre — profile identity: display name, subject area
  Right  — patterns: custom concerns, disabled defaults, strength signals

A "profile" is a live course configuration (accumulated edits, patterns).
A "template" is a named snapshot that can be forked into a new course profile.

Usage:
    dlg = CourseProfileDialog(store, current_profile_id, parent=self)
    if dlg.exec():
        new_profile_id = dlg.selected_profile_id
"""
from typing import List, Optional

from PySide6.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QScrollArea, QSplitter,
    QVBoxLayout, QWidget, QComboBox,
)
from PySide6.QtCore import Qt, Signal

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, AMBER_BTN, TERM_GREEN, BURN_RED,
    BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_INSET, BG_PANEL,
    PANE_BG_GRADIENT,
    make_section_label, make_h_rule,
    combo_qss,
)

# ---------------------------------------------------------------------------
# Shared stylesheets (same vocabulary as template_editor_dialog.py)
# ---------------------------------------------------------------------------

_PANE_QSS = (
    f"QFrame#profilePane {{"
    f"  background: {PANE_BG_GRADIENT};"
    f"  border: 1px solid {BORDER_DARK};"
    f"  border-top-color: {BORDER_AMBER};"
    f"  border-radius: 8px;"
    f"}}"
)

_LIST_QSS = f"""
    QListWidget {{
        background: {BG_INSET};
        border: none;
        font-size: {px(12)}px;
        outline: none;
    }}
    QListWidget::item {{
        padding: 6px 10px;
        border-left: 3px solid transparent;
        border-radius: 0;
        color: {PHOSPHOR_GLOW};
    }}
    QListWidget::item:selected {{
        background: #2C1C08;
        color: {PHOSPHOR_HOT};
        border-left: 3px solid {ROSE_ACCENT};
        font-weight: 600;
    }}
    QListWidget::item:hover:!selected {{
        background: #1A1008;
        color: {PHOSPHOR_MID};
    }}
"""

_FIELD_LABEL_QSS = (
    f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: normal;"
    f" letter-spacing: 0.5px; background: transparent; border: none;"
)

_INPUT_QSS = f"""
    QLineEdit {{
        background: {BG_INSET};
        border: 1px solid {BORDER_DARK};
        border-radius: 3px;
        padding: 4px 8px;
        color: {PHOSPHOR_HOT};
        font-size: {px(12)}px;
    }}
    QLineEdit:focus {{ border-color: {BORDER_AMBER}; }}
"""

_SMALL_BTN_QSS = (
    f"QPushButton {{"
    f" background: transparent; color: {PHOSPHOR_DIM};"
    f" border: 1px solid {BORDER_DARK}; border-radius: 3px;"
    f" padding: 3px 10px; font-size: {px(11)}px; }}"
    f"QPushButton:hover {{"
    f" border-color: {BORDER_AMBER}; color: {PHOSPHOR_MID}; }}"
    f"QPushButton:pressed {{ color: {PHOSPHOR_HOT}; }}"
)

_DELETE_BTN_QSS = (
    f"QPushButton {{"
    f" background: transparent; color: rgba(192,64,32,0.70);"
    f" border: 1px solid rgba(192,64,32,0.35); border-radius: 3px;"
    f" padding: 3px 10px; font-size: {px(11)}px; }}"
    f"QPushButton:hover {{"
    f" border-color: rgba(192,64,32,0.80); color: {BURN_RED}; }}"
    f"QPushButton:disabled {{ color: {PHOSPHOR_GLOW}; border-color: {BORDER_DARK}; }}"
)

_STATUS_QSS_OK  = f"color: {TERM_GREEN}; font-size: {px(10)}px; background: transparent;"
_STATUS_QSS_ERR = f"color: {BURN_RED}; font-size: {px(10)}px; background: transparent;"


def _field_label(text: str) -> QLabel:
    lbl = QLabel(text.upper())
    lbl.setStyleSheet(_FIELD_LABEL_QSS)
    return lbl


def _scroll_wrap(inner: QWidget) -> QScrollArea:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.Shape.NoFrame)
    scroll.setStyleSheet(
        "QScrollArea { background: transparent; border: none; }"
        f"QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}"
    )
    scroll.setWidget(inner)
    return scroll


# ---------------------------------------------------------------------------
# _PatternList — reusable add/remove list widget for patterns
# ---------------------------------------------------------------------------

class _PatternList(QWidget):
    """A labelled QListWidget with inline add (QLineEdit + button) and per-item remove."""

    changed = Signal()

    def __init__(self, label: str, placeholder: str = "Add pattern…", parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label(label))

        self._list = QListWidget()
        self._list.setStyleSheet(_LIST_QSS)
        self._list.setMinimumHeight(80)
        lo.addWidget(self._list)

        # Add row
        add_row = QHBoxLayout()
        add_row.setSpacing(SPACING_SM)
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setStyleSheet(_INPUT_QSS)
        add_btn = QPushButton("Add")
        add_btn.setStyleSheet(_SMALL_BTN_QSS)
        add_btn.clicked.connect(self._add_item)
        self._input.returnPressed.connect(self._add_item)
        add_row.addWidget(self._input, 1)
        add_row.addWidget(add_btn)
        lo.addLayout(add_row)

        # Remove selected button
        rm_btn = QPushButton("Remove selected")
        rm_btn.setStyleSheet(_DELETE_BTN_QSS)
        rm_btn.clicked.connect(self._remove_selected)
        lo.addWidget(rm_btn)

    def _add_item(self) -> None:
        text = self._input.text().strip()
        if not text:
            return
        # Prevent duplicates
        for i in range(self._list.count()):
            if self._list.item(i).text() == text:
                self._input.clear()
                return
        self._list.addItem(QListWidgetItem(text))
        self._input.clear()
        self.changed.emit()

    def _remove_selected(self) -> None:
        for item in self._list.selectedItems():
            self._list.takeItem(self._list.row(item))
        self.changed.emit()

    def load(self, items: List[str]) -> None:
        self._list.clear()
        for item in items:
            self._list.addItem(QListWidgetItem(item))

    def get_items(self) -> List[str]:
        return [self._list.item(i).text() for i in range(self._list.count())]


# ---------------------------------------------------------------------------
# _ToggleList — list of items that can be enabled/disabled (for default patterns)
# ---------------------------------------------------------------------------

class _ToggleList(QWidget):
    """Shows default concern patterns with checkboxes; protected ones are greyed out."""

    changed = Signal()

    # Patterns that cannot be disabled (wellbeing/safety signals)
    _PROTECTED = {"wellbeing", "crisis", "self-harm", "personal distress"}

    # Human-readable default patterns the teacher can see and toggle
    DEFAULT_PATTERNS = [
        ("essentializing", "Essentializing language about identity groups"),
        ("colorblind", "Colorblind framing ('I don't see race / gender / etc.')"),
        ("tone policing", "Tone policing — concern about how something is said rather than what"),
        ("dismissing lived experience", "Dismissing lived experience as 'just personal opinion'"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(4)

        lo.addWidget(make_section_label("Default concern patterns"))

        subtext = QLabel(
            "Uncheck to mute for this course. Wellbeing/crisis signals cannot be muted."
        )
        subtext.setWordWrap(True)
        subtext.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        lo.addWidget(subtext)

        self._checks = {}
        for key, label in self.DEFAULT_PATTERNS:
            cb = QCheckBox(label)
            cb.setStyleSheet(
                f"QCheckBox {{ color: {PHOSPHOR_MID}; font-size: {px(11)}px; }}"
                f"QCheckBox::indicator {{ width: 14px; height: 14px; }}"
            )
            cb.setChecked(True)  # enabled by default
            cb.stateChanged.connect(lambda _: self.changed.emit())
            lo.addWidget(cb)
            self._checks[key] = cb

        lo.addStretch()

    def load(self, disabled: List[str]) -> None:
        """Check all by default; uncheck any that are in disabled list."""
        for key, cb in self._checks.items():
            cb.setChecked(key not in disabled)

    def get_disabled(self) -> List[str]:
        return [key for key, cb in self._checks.items() if not cb.isChecked()]


# ---------------------------------------------------------------------------
# _ProfileSettingsForm — centre panel
# ---------------------------------------------------------------------------

class _ProfileSettingsForm(QWidget):
    """Profile identity: display name + subject area picker."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label("Profile settings"))
        lo.addWidget(make_h_rule())

        # Profile ID (course key — used as storage key)
        lo.addWidget(_field_label("Course key"))
        self._id_input = QLineEdit()
        self._id_input.setPlaceholderText("e.g. ethnic_studies or native_studies_f2026")
        self._id_input.setStyleSheet(_INPUT_QSS)
        self._id_input.textChanged.connect(self.changed.emit)
        lo.addWidget(self._id_input)

        id_hint = QLabel(
            "Used internally to link runs to this profile. "
            "Short, lowercase, no spaces. Cannot be changed after first use."
        )
        id_hint.setWordWrap(True)
        id_hint.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        lo.addWidget(id_hint)

        lo.addSpacing(SPACING_SM)

        # Display name
        lo.addWidget(_field_label("Display name"))
        self._name_input = QLineEdit()
        self._name_input.setPlaceholderText("e.g. Ethnic Studies, Native Studies")
        self._name_input.setStyleSheet(_INPUT_QSS)
        self._name_input.textChanged.connect(self.changed.emit)
        lo.addWidget(self._name_input)

        lo.addSpacing(SPACING_SM)

        # Subject area
        lo.addWidget(_field_label("Subject area"))
        self._subject_combo = QComboBox()
        self._subject_combo.setStyleSheet(combo_qss())
        self._subject_combo.currentIndexChanged.connect(self.changed.emit)
        lo.addWidget(self._subject_combo)

        subject_hint = QLabel(
            "Sets the concern vocabulary and equity framing for this course. "
            "You can fine-tune patterns on the right."
        )
        subject_hint.setWordWrap(True)
        subject_hint.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent;"
        )
        lo.addWidget(subject_hint)

        lo.addStretch()

        # Populate subject choices
        try:
            from insights.lens_templates import get_template_choices
            for key, name in get_template_choices():
                self._subject_combo.addItem(name, key)
        except Exception:
            self._subject_combo.addItem("General", "general")

    def load(self, profile_id: str, display_name: str, subject_area: str) -> None:
        self._loading = True
        self._id_input.setText(profile_id)
        self._name_input.setText(display_name)
        idx = self._subject_combo.findData(subject_area)
        if idx >= 0:
            self._subject_combo.setCurrentIndex(idx)
        self._loading = False

    def set_id_editable(self, editable: bool) -> None:
        self._id_input.setEnabled(editable)

    def get_profile_id(self) -> str:
        return self._id_input.text().strip().replace(" ", "_").lower()

    def get_display_name(self) -> str:
        return self._name_input.text().strip()

    def get_subject_area(self) -> str:
        return self._subject_combo.currentData() or "general"


# ---------------------------------------------------------------------------
# _PatternsForm — right panel
# ---------------------------------------------------------------------------

class _PatternsForm(QWidget):
    """Custom concerns, disabled defaults, strength patterns."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        inner = QWidget()
        lo = QVBoxLayout(inner)
        lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        lo.setSpacing(SPACING_MD)

        lo.addWidget(make_section_label("Analysis patterns"))
        lo.addWidget(make_h_rule())

        self._toggle_list = _ToggleList()
        self._toggle_list.changed.connect(self.changed.emit)
        lo.addWidget(self._toggle_list)

        lo.addWidget(make_h_rule())

        self._concern_list = _PatternList(
            "Custom concern patterns",
            "e.g. student attributes behavior to genetics without evidence",
        )
        self._concern_list.changed.connect(self.changed.emit)
        lo.addWidget(self._concern_list)

        lo.addWidget(make_h_rule())

        self._strength_list = _PatternList(
            "Strength patterns to surface",
            "e.g. student connects material to community knowledge",
        )
        self._strength_list.changed.connect(self.changed.emit)
        lo.addWidget(self._strength_list)

        lo.addStretch()

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(_scroll_wrap(inner))

    def load(
        self,
        custom_concerns: List[str],
        disabled_defaults: List[str],
        strengths: List[str],
    ) -> None:
        self._concern_list.load(custom_concerns)
        self._toggle_list.load(disabled_defaults)
        self._strength_list.load(strengths)

    def get_custom_concerns(self) -> List[str]:
        return self._concern_list.get_items()

    def get_disabled_defaults(self) -> List[str]:
        return self._toggle_list.get_disabled()

    def get_strengths(self) -> List[str]:
        return self._strength_list.get_items()


# ---------------------------------------------------------------------------
# CourseProfileDialog
# ---------------------------------------------------------------------------

class CourseProfileDialog(QDialog):
    """Manage course profiles and reusable templates.

    On accept(), `selected_profile_id` contains the profile_id to use
    for the current run. If the user saves a new profile, it becomes selected.
    """

    def __init__(
        self,
        store,
        current_profile_id: str = "default",
        parent=None,
    ):
        super().__init__(parent)
        self._store = store
        self._current_profile_id = current_profile_id
        self._dirty = False
        self._loading = False

        self.selected_profile_id = current_profile_id

        self.setWindowTitle("Course Profiles")
        self.setMinimumSize(900, 580)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")

        self._build_ui()
        self._populate_template_list()

        # Try to load current profile on open
        if current_profile_id and current_profile_id != "default":
            self._load_profile(current_profile_id)

    # ── UI construction ────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        root.setSpacing(SPACING_SM)

        # Title
        title = QLabel("Course Profiles & Templates")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; font-weight: 700;"
            f" background: transparent;"
        )
        root.addWidget(title)

        subtitle = QLabel(
            "Each course profile stores its own concern vocabulary, strength patterns, "
            "and subject framing. Save a profile as a template to reuse it each semester."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent;"
        )
        root.addWidget(subtitle)

        root.addWidget(make_h_rule())

        # Three-panel splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet(
            "QSplitter::handle { background: transparent; width: 6px; }"
        )

        splitter.addWidget(self._build_left_panel())
        splitter.addWidget(self._build_centre_panel())
        splitter.addWidget(self._build_right_panel())
        splitter.setSizes([200, 320, 380])

        root.addWidget(splitter, 1)

        # Status + bottom buttons
        bottom = QHBoxLayout()
        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(_STATUS_QSS_OK)
        bottom.addWidget(self._status_lbl, 1)

        self._save_btn = QPushButton("Save profile")
        self._save_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._save_btn.setEnabled(False)
        self._save_btn.clicked.connect(self._on_save)
        bottom.addWidget(self._save_btn)

        close_btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        close_btn.rejected.connect(self._on_close)
        bottom.addWidget(close_btn)

        root.addLayout(bottom)

    def _build_left_panel(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("profilePane")
        pane.setStyleSheet(_PANE_QSS)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label("Saved templates"))

        self._template_list = QListWidget()
        self._template_list.setStyleSheet(_LIST_QSS)
        self._template_list.itemSelectionChanged.connect(self._on_template_selected)
        lo.addWidget(self._template_list, 1)

        btn_row = QHBoxLayout()
        self._load_btn = QPushButton("Load →")
        self._load_btn.setStyleSheet(_SMALL_BTN_QSS)
        self._load_btn.setEnabled(False)
        self._load_btn.setToolTip("Fork this template into the active profile")
        self._load_btn.clicked.connect(self._on_load_template)
        btn_row.addWidget(self._load_btn)

        self._del_tmpl_btn = QPushButton("Delete")
        self._del_tmpl_btn.setStyleSheet(_DELETE_BTN_QSS)
        self._del_tmpl_btn.setEnabled(False)
        self._del_tmpl_btn.clicked.connect(self._on_delete_template)
        btn_row.addWidget(self._del_tmpl_btn)
        lo.addLayout(btn_row)

        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("Active profiles"))

        self._profile_list = QListWidget()
        self._profile_list.setStyleSheet(_LIST_QSS)
        self._profile_list.itemSelectionChanged.connect(self._on_profile_selected)
        lo.addWidget(self._profile_list, 1)

        new_btn = QPushButton("+ New profile")
        new_btn.setStyleSheet(_SMALL_BTN_QSS)
        new_btn.clicked.connect(self._on_new_profile)
        lo.addWidget(new_btn)

        use_btn = QPushButton("Use for this run")
        use_btn.setStyleSheet(
            f"QPushButton {{ background: {AMBER_BTN}; color: {BG_VOID};"
            f" border: none; border-radius: 3px; padding: 4px 10px;"
            f" font-size: {px(11)}px; font-weight: 700; }}"
            f"QPushButton:hover {{ background: {PHOSPHOR_HOT}; }}"
            f"QPushButton:disabled {{ background: {BORDER_DARK}; color: {PHOSPHOR_DIM}; }}"
        )
        use_btn.clicked.connect(self._on_use_profile)
        lo.addWidget(use_btn)

        return pane

    def _build_centre_panel(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("profilePane")
        pane.setStyleSheet(_PANE_QSS)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(0, 0, 0, 0)

        self._settings_form = _ProfileSettingsForm()
        self._settings_form.changed.connect(self._on_form_changed)
        lo.addWidget(_scroll_wrap(self._settings_form))

        # "Save as template" row at the bottom of centre panel
        tmpl_row = QHBoxLayout()
        tmpl_row.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        self._tmpl_name_input = QLineEdit()
        self._tmpl_name_input.setPlaceholderText("Template name…")
        self._tmpl_name_input.setStyleSheet(_INPUT_QSS)
        save_tmpl_btn = QPushButton("Save as template")
        save_tmpl_btn.setStyleSheet(_SMALL_BTN_QSS)
        save_tmpl_btn.clicked.connect(self._on_save_as_template)
        tmpl_row.addWidget(self._tmpl_name_input, 1)
        tmpl_row.addWidget(save_tmpl_btn)
        lo.addLayout(tmpl_row)

        return pane

    def _build_right_panel(self) -> QWidget:
        pane = QFrame()
        pane.setObjectName("profilePane")
        pane.setStyleSheet(_PANE_QSS)
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(0, 0, 0, 0)

        self._patterns_form = _PatternsForm()
        self._patterns_form.changed.connect(self._on_form_changed)
        lo.addWidget(self._patterns_form)

        return pane

    # ── Data loading ───────────────────────────────────────────────────

    def _populate_template_list(self) -> None:
        self._template_list.clear()
        self._profile_list.clear()
        for name in self._store.list_profile_templates():
            self._template_list.addItem(QListWidgetItem(name))
        for pid in self._store.list_profiles():
            item = QListWidgetItem(pid)
            if pid == self._current_profile_id:
                f = item.font()
                f.setBold(True)
                item.setFont(f)
                item.setForeground(Qt.GlobalColor.yellow)
            self._profile_list.addItem(item)

    def _load_profile(self, profile_id: str) -> None:
        """Load a profile's data into the form."""
        self._loading = True
        try:
            from insights.teacher_profile import TeacherProfileManager
            mgr = TeacherProfileManager(self._store, profile_id)
            p = mgr.profile

            display_name = p.custom_patterns.get("_display_name", "") or profile_id
            self._settings_form.load(profile_id, display_name, p.subject_area or "general")
            self._settings_form.set_id_editable(False)  # existing profile — key is fixed
            self._patterns_form.load(
                p.custom_concern_patterns,
                p.disabled_default_patterns,
                p.custom_strength_patterns,
            )
            self._tmpl_name_input.setText(display_name)
            self._dirty = False
            self._save_btn.setEnabled(False)
            self._status_lbl.setText("")
        finally:
            self._loading = False

    # ── Interaction handlers ───────────────────────────────────────────

    def _on_form_changed(self) -> None:
        if self._loading:
            return
        self._dirty = True
        self._save_btn.setEnabled(True)

    def _on_template_selected(self) -> None:
        has = bool(self._template_list.selectedItems())
        self._load_btn.setEnabled(has)
        self._del_tmpl_btn.setEnabled(has)

    def _on_profile_selected(self) -> None:
        items = self._profile_list.selectedItems()
        if not items:
            return
        profile_id = items[0].text()
        if self._dirty:
            from gui.dialogs.message_dialog import show_question
            if not show_question(
                self, "Unsaved changes",
                "You have unsaved changes. Discard them and load this profile?",
            ):
                return
        self._load_profile(profile_id)

    def _on_load_template(self) -> None:
        items = self._template_list.selectedItems()
        if not items:
            return
        template_name = items[0].text()
        if self._dirty:
            from gui.dialogs.message_dialog import show_question
            if not show_question(
                self, "Unsaved changes",
                "Loading a template will overwrite unsaved changes. Continue?",
            ):
                return
        # Fork template into current profile
        profile_id = self._settings_form.get_profile_id()
        if not profile_id:
            self._flash_status("Set a course key first.", error=True)
            return
        from insights.teacher_profile import TeacherProfileManager
        TeacherProfileManager.fork_from_template(self._store, template_name, profile_id)
        self._load_profile(profile_id)
        self._populate_template_list()
        self._flash_status(f"Loaded template '{template_name}' into profile.")

    def _on_delete_template(self) -> None:
        items = self._template_list.selectedItems()
        if not items:
            return
        name = items[0].text()
        from gui.dialogs.message_dialog import show_question
        if show_question(self, "Delete template", f"Delete template '{name}'?"):
            self._store.delete_profile_template(name)
            self._populate_template_list()
            self._flash_status(f"Deleted template '{name}'.")

    def _on_new_profile(self) -> None:
        if self._dirty:
            from gui.dialogs.message_dialog import show_question
            if not show_question(
                self, "Unsaved changes",
                "Discard unsaved changes and start a new profile?",
            ):
                return
        self._loading = True
        self._settings_form.load("", "", "general")
        self._settings_form.set_id_editable(True)
        self._patterns_form.load([], [], [])
        self._tmpl_name_input.clear()
        self._dirty = False
        self._save_btn.setEnabled(False)
        self._loading = False

    def _on_save(self) -> None:
        profile_id = self._settings_form.get_profile_id()
        if not profile_id:
            self._flash_status("Course key cannot be empty.", error=True)
            return

        from insights.teacher_profile import TeacherProfileManager
        from insights.models import TeacherAnalysisProfile
        mgr = TeacherProfileManager(self._store, profile_id)
        p = mgr.profile

        p.subject_area = self._settings_form.get_subject_area()
        p.custom_concern_patterns = self._patterns_form.get_custom_concerns()
        p.disabled_default_patterns = self._patterns_form.get_disabled_defaults()
        p.custom_strength_patterns = self._patterns_form.get_strengths()

        # Store display_name in custom_patterns under a reserved key
        display_name = self._settings_form.get_display_name() or profile_id
        p.custom_patterns["_display_name"] = display_name

        mgr._profile = p
        mgr._save()

        self._dirty = False
        self._save_btn.setEnabled(False)
        self._populate_template_list()
        self._flash_status("Profile saved.")

    def _on_save_as_template(self) -> None:
        profile_id = self._settings_form.get_profile_id()
        if not profile_id:
            self._flash_status("Save the profile first.", error=True)
            return
        template_name = self._tmpl_name_input.text().strip()
        if not template_name:
            self._flash_status("Enter a template name.", error=True)
            return
        from insights.teacher_profile import TeacherProfileManager
        mgr = TeacherProfileManager(self._store, profile_id)
        mgr.save_as_template(template_name)
        self._populate_template_list()
        self._flash_status(f"Saved as template '{template_name}'.")

    def _on_use_profile(self) -> None:
        """Set the selected profile as the one to use for the current run."""
        items = self._profile_list.selectedItems()
        if not items:
            self._flash_status("Select a profile from the list first.", error=True)
            return
        self.selected_profile_id = items[0].text()
        self.accept()

    def _on_close(self) -> None:
        if self._dirty:
            from gui.dialogs.message_dialog import show_question
            if not show_question(
                self, "Unsaved changes",
                "Close without saving?",
            ):
                return
        self.reject()

    def _flash_status(self, msg: str, error: bool = False) -> None:
        self._status_lbl.setStyleSheet(_STATUS_QSS_ERR if error else _STATUS_QSS_OK)
        self._status_lbl.setText(msg)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(3000, lambda: self._status_lbl.setText(""))
