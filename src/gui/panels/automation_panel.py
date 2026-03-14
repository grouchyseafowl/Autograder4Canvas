"""
Automation tab: configured courses, scheduling, global options.
"""
import platform

from PySide6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QTreeWidget, QTreeWidgetItem, QPushButton, QCheckBox,
    QComboBox, QTimeEdit, QLineEdit, QSizePolicy, QMessageBox,
)
from PySide6.QtCore import Qt, QTime, Signal
from PySide6.QtGui import QFont

from gui.styles import SPACING_SM, SPACING_MD


class AutomationPanel(QWidget):
    """Automation tab contents."""

    config_saved = Signal()

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._setup_ui()
        self._load_config()

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

        # --- Configured Courses ---
        courses_box = QGroupBox("Configured Courses")
        courses_vbox = QVBoxLayout(courses_box)
        courses_vbox.setSpacing(SPACING_SM)

        self._courses_tree = QTreeWidget()
        self._courses_tree.setColumnCount(3)
        self._courses_tree.setHeaderLabels(["Course", "# Rules", "Enabled"])
        self._courses_tree.header().setStretchLastSection(False)
        self._courses_tree.header().setSectionResizeMode(0, self._courses_tree.header().ResizeMode.Stretch)
        self._courses_tree.header().setSectionResizeMode(1, self._courses_tree.header().ResizeMode.Fixed)
        self._courses_tree.header().setSectionResizeMode(2, self._courses_tree.header().ResizeMode.Fixed)
        self._courses_tree.setColumnWidth(1, 80)
        self._courses_tree.setColumnWidth(2, 80)
        self._courses_tree.setMaximumHeight(200)
        courses_vbox.addWidget(self._courses_tree)

        btn_row = QHBoxLayout()
        self._add_course_btn = QPushButton("+ Add Course")
        self._add_course_btn.clicked.connect(self._on_add_course)
        btn_row.addWidget(self._add_course_btn)
        self._edit_course_btn = QPushButton("Edit Selected")
        self._edit_course_btn.clicked.connect(self._on_edit_course)
        btn_row.addWidget(self._edit_course_btn)
        self._remove_course_btn = QPushButton("Remove Selected")
        self._remove_course_btn.clicked.connect(self._on_remove_course)
        btn_row.addWidget(self._remove_course_btn)
        btn_row.addStretch()
        courses_vbox.addLayout(btn_row)
        vbox.addWidget(courses_box)

        # --- Schedule ---
        sched_box = QGroupBox("Schedule")
        sched_vbox = QVBoxLayout(sched_box)
        sched_vbox.setSpacing(SPACING_SM)

        self._sched_enabled = QCheckBox("Enable scheduled runs")
        sched_vbox.addWidget(self._sched_enabled)

        freq_row = QHBoxLayout()
        freq_row.addWidget(QLabel("Run every:"))
        self._freq_combo = QComboBox()
        self._freq_combo.addItems(["Daily", "Weekdays", "Custom"])
        freq_row.addWidget(self._freq_combo)
        freq_row.addSpacing(SPACING_SM)
        freq_row.addWidget(QLabel("At:"))
        self._time_edit = QTimeEdit(QTime(3, 0))
        self._time_edit.setDisplayFormat("hh:mm AP")
        freq_row.addWidget(self._time_edit)
        freq_row.addStretch()
        sched_vbox.addLayout(freq_row)

        sys_name = platform.system()
        if sys_name == "Darwin":
            note = "Will create a launchd agent"
        elif sys_name == "Windows":
            note = "Will create a Windows Task Scheduler entry"
        else:
            note = "Will create a cron job"
        platform_note = QLabel(note)
        platform_note.setEnabled(False)
        font = QFont()
        font.setItalic(True)
        platform_note.setFont(font)
        sched_vbox.addWidget(platform_note)

        apply_btn = QPushButton("Apply Schedule")
        apply_btn.clicked.connect(self._on_apply_schedule)
        sched_vbox.addWidget(apply_btn)
        vbox.addWidget(sched_box)

        # --- Global Options ---
        global_box = QGroupBox("Global Options")
        global_vbox = QVBoxLayout(global_box)
        global_vbox.setSpacing(SPACING_SM)

        self._skip_future = QCheckBox("Skip assignments with future due dates")
        self._skip_future.setChecked(True)
        global_vbox.addWidget(self._skip_future)

        self._skip_empty = QCheckBox("Skip assignments with no submissions")
        self._skip_empty.setChecked(True)
        global_vbox.addWidget(self._skip_empty)

        self._auto_check = QCheckBox("Auto-check for new assignment groups")
        self._auto_check.setChecked(True)
        global_vbox.addWidget(self._auto_check)

        email_row = QHBoxLayout()
        email_row.addWidget(QLabel("Notification email:"))
        self._email_edit = QLineEdit()
        self._email_edit.setPlaceholderText("optional")
        email_row.addWidget(self._email_edit)
        global_vbox.addLayout(email_row)

        webhook_row = QHBoxLayout()
        webhook_row.addWidget(QLabel("Webhook URL:"))
        self._webhook_edit = QLineEdit()
        self._webhook_edit.setPlaceholderText("optional (n8n/Slack)")
        webhook_row.addWidget(self._webhook_edit)
        global_vbox.addLayout(webhook_row)

        vbox.addWidget(global_box)

        # --- Bottom Buttons ---
        bottom = QHBoxLayout()
        save_btn = QPushButton("Save Configuration")
        save_btn.clicked.connect(self._on_save_config)
        bottom.addWidget(save_btn)
        dry_run_btn = QPushButton("Dry Run Now")
        dry_run_btn.clicked.connect(self._on_dry_run)
        bottom.addWidget(dry_run_btn)
        bottom.addStretch()
        vbox.addLayout(bottom)
        vbox.addStretch()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load_config(self) -> None:
        try:
            from automation.course_config import AutomationConfig
            from autograder_utils import get_output_base_dir

            config_path = get_output_base_dir() / ".autograder_config" / "course_configs.json"
            if not config_path.exists():
                return

            config = AutomationConfig.load(config_path)
            self._courses_tree.clear()
            for course in config.courses.values():
                item = QTreeWidgetItem([
                    f"{course.course_name} (ID {course.course_id})",
                    str(len(course.assignment_rules)),
                    "Yes" if course.enabled else "No",
                ])
                item.setData(0, Qt.ItemDataRole.UserRole, course.course_id)
                self._courses_tree.addTopLevelItem(item)

            gs = config.global_settings
            if gs:
                self._skip_future.setChecked(gs.skip_future_assignments)
                self._skip_empty.setChecked(gs.skip_no_submissions)
                self._auto_check.setChecked(gs.auto_update_enabled)
                self._email_edit.setText(gs.notify_email or "")
                self._webhook_edit.setText(gs.n8n_webhook_url or "")

        except Exception:
            pass

    def _on_add_course(self) -> None:
        QMessageBox.information(self, "Add Course",
            "Connect to Canvas first (set credentials in Settings tab), "
            "then courses will be available to configure here.")

    def _on_edit_course(self) -> None:
        sel = self._courses_tree.selectedItems()
        if not sel:
            QMessageBox.information(self, "Edit Course", "Select a course first.")
            return
        QMessageBox.information(self, "Edit Course",
            "Course rule editing is available in the full automation config file.\n"
            "Use Run Autograder from the Courses tab to run a one-shot grading.")

    def _on_remove_course(self) -> None:
        sel = self._courses_tree.selectedItems()
        if not sel:
            return
        if QMessageBox.question(self, "Remove Course",
                                "Remove this course from automation config?") == QMessageBox.StandardButton.Yes:
            for item in sel:
                idx = self._courses_tree.indexOfTopLevelItem(item)
                self._courses_tree.takeTopLevelItem(idx)

    def _on_apply_schedule(self) -> None:
        if not self._sched_enabled.isChecked():
            QMessageBox.information(self, "Schedule", "Enable scheduled runs first.")
            return
        t = self._time_edit.time()
        try:
            from gui.scheduler import get_scheduler
            import sys
            scheduler = get_scheduler()
            scheduler.install(
                hour=t.hour(),
                minute=t.minute(),
                python_path=sys.executable,
                script_path=str(__import__("pathlib").Path(__file__).parent.parent / "gui_main.py"),
            )
            QMessageBox.information(self, "Schedule", "Schedule applied successfully.")
        except Exception as exc:
            QMessageBox.warning(self, "Schedule Error", str(exc))

    def _on_save_config(self) -> None:
        try:
            from automation.course_config import AutomationConfig, GlobalSettings
            from autograder_utils import get_output_base_dir
            from credentials import load_credentials, get_active_profile

            config_dir = get_output_base_dir() / ".autograder_config"
            config_dir.mkdir(parents=True, exist_ok=True)
            config_path = config_dir / "course_configs.json"

            if config_path.exists():
                config = AutomationConfig.load(config_path)
            else:
                config = AutomationConfig()

            data = load_credentials()
            _, profile = get_active_profile(data)
            url = profile.get("canvas_base_url", "")
            token = profile.get("canvas_api_token", "")
            import os
            if url:
                os.environ["CANVAS_BASE_URL"] = url
            if token:
                os.environ["CANVAS_API_TOKEN"] = token

            if config.global_settings is None:
                config.global_settings = GlobalSettings(
                    current_semester_term_ids=[],
                    log_file_path=str(get_output_base_dir() / "automation.log"),
                    flag_excel_path=str(get_output_base_dir() / "flags.xlsx"),
                )
            gs = config.global_settings
            gs.skip_future_assignments = self._skip_future.isChecked()
            gs.skip_no_submissions = self._skip_empty.isChecked()
            gs.auto_update_enabled = self._auto_check.isChecked()
            gs.notify_email = self._email_edit.text().strip()
            gs.n8n_webhook_url = self._webhook_edit.text().strip()

            config.save(config_path)
            self.config_saved.emit()
            QMessageBox.information(self, "Saved", "Automation configuration saved.")

        except Exception as exc:
            QMessageBox.warning(self, "Save Error", str(exc))

    def _on_dry_run(self) -> None:
        QMessageBox.information(self, "Dry Run",
            "Dry run for all configured courses is not yet implemented in the GUI.\n"
            "Use the Courses tab to run individual assignments in dry-run mode.")
