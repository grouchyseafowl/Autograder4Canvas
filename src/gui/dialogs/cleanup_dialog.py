"""
One-time cleanup wizard dialog.
"""
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QRadioButton, QButtonGroup, QCheckBox, QSpinBox,
    QDialogButtonBox, QMessageBox,
)
from PySide6.QtCore import Qt

from gui.styles import SPACING_SM, SPACING_MD


class CleanupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Run Cleanup")
        self.setMinimumWidth(420)
        self._setup_ui()
        self._update_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(20, 20, 20, 20)

        # Mode
        mode_box = QGroupBox("Mode")
        mode_vbox = QVBoxLayout(mode_box)
        self._mode_bg = QButtonGroup(self)
        for val, label in [("archive", "Archive (move to Archived Reports)"),
                            ("trash",   "Move to Trash")]:
            rb = QRadioButton(label)
            rb.setProperty("mode_val", val)
            self._mode_bg.addButton(rb)
            mode_vbox.addWidget(rb)
            if val == "archive":
                rb.setChecked(True)
        self._mode_bg.buttonClicked.connect(lambda _: self._update_preview())
        layout.addWidget(mode_box)

        # Threshold
        thresh_row = QHBoxLayout()
        thresh_row.addWidget(QLabel("Older than:"))
        self._days = QSpinBox()
        self._days.setRange(1, 3650)
        self._days.setValue(90)
        self._days.setSuffix(" days")
        self._days.valueChanged.connect(self._update_preview)
        thresh_row.addWidget(self._days)
        thresh_row.addStretch()
        layout.addLayout(thresh_row)

        # File types
        types_box = QGroupBox("File types")
        types_vbox = QVBoxLayout(types_box)
        self._type_checks = {}
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
            cb.stateChanged.connect(self._update_preview)
            types_vbox.addWidget(cb)
            self._type_checks[key] = cb
        layout.addWidget(types_box)

        # Preview
        self._preview_label = QLabel("Preview: calculating…")
        layout.addWidget(self._preview_label)

        # Buttons
        btn_box = QDialogButtonBox()
        self._cancel_btn = btn_box.addButton(QDialogButtonBox.StandardButton.Cancel)
        self._cancel_btn.clicked.connect(self.reject)
        self._run_btn = btn_box.addButton("Run Cleanup", QDialogButtonBox.ButtonRole.AcceptRole)
        self._run_btn.clicked.connect(self._on_run)
        layout.addWidget(btn_box)

    def _current_mode(self) -> str:
        btn = self._mode_bg.checkedButton()
        return btn.property("mode_val") if btn else "archive"

    def _checked_types(self) -> list:
        return [k for k, cb in self._type_checks.items() if cb.isChecked()]

    def _update_preview(self) -> None:
        try:
            from cleanup import count_files_to_clean
            from autograder_utils import get_output_base_dir

            base = get_output_base_dir()
            days = self._days.value()
            total = 0

            type_map = {
                "ad_csv":   ("Academic_Dishonesty", "csv"),
                "ad_excel": ("Academic_Dishonesty", "excel"),
                "ad_txt":   ("Academic_Dishonesty", "txt"),
                "ci_csv":   ("Complete-Incomplete", "csv"),
                "df_csv":   ("Discussion_Forum",    "csv"),
            }
            for key in self._checked_types():
                script_type, file_type = type_map[key]
                target_dir = base / {
                    "Academic_Dishonesty": "Academic Dishonesty Reports",
                    "Complete-Incomplete": "Complete-Incomplete Assignments",
                    "Discussion_Forum":    "Discussion Forums",
                }[script_type]
                total += count_files_to_clean(target_dir, script_type, file_type, days)

            self._preview_label.setText(f"Preview: {total} file{'s' if total != 1 else ''} would be affected")
        except Exception as exc:
            self._preview_label.setText(f"Preview unavailable: {exc}")

    def _on_run(self) -> None:
        mode = self._current_mode()
        days = self._days.value()
        types = self._checked_types()
        if not types:
            QMessageBox.warning(self, "No Types", "Select at least one file type.")
            return

        try:
            from cleanup import archive_files_by_type, trash_files_by_type
            from autograder_utils import get_output_base_dir

            base = get_output_base_dir()
            type_map = {
                "ad_csv":   ("Academic_Dishonesty", "csv"),
                "ad_excel": ("Academic_Dishonesty", "excel"),
                "ad_txt":   ("Academic_Dishonesty", "txt"),
                "ci_csv":   ("Complete-Incomplete", "csv"),
                "df_csv":   ("Discussion_Forum",    "csv"),
            }
            dir_map = {
                "Academic_Dishonesty": "Academic Dishonesty Reports",
                "Complete-Incomplete": "Complete-Incomplete Assignments",
                "Discussion_Forum":    "Discussion Forums",
            }
            total = 0
            for key in types:
                script_type, file_type = type_map[key]
                target_dir = base / dir_map[script_type]
                if mode == "archive":
                    total += archive_files_by_type(target_dir, script_type, file_type, days)
                else:
                    total += trash_files_by_type(target_dir, script_type, file_type, days)

            action = "Archived" if mode == "archive" else "Moved to Trash"
            dest = "Archived Reports" if mode == "archive" else "Trash"
            QMessageBox.information(self, "Cleanup Complete",
                                    f"{action} {total} file{'s' if total != 1 else ''} to {dest}.")
            self.accept()
        except Exception as exc:
            QMessageBox.warning(self, "Cleanup Error", str(exc))
