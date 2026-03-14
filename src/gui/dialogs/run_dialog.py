"""
Run Autograder dialog: tool picker, options, confirmation, live log.
"""
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel, QPushButton,
    QTextEdit, QRadioButton, QButtonGroup, QCheckBox, QSpinBox, QComboBox,
    QGroupBox, QDialogButtonBox, QMessageBox, QDoubleSpinBox, QFrame,
    QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.styles import SPACING_SM, SPACING_MD, FONT_MONO, make_run_button, make_secondary_button, make_monospace_textedit


class RunDialog(QDialog):
    """Modal dialog to configure and run a grading job."""

    def __init__(self, api, selected_items: List[dict], course_name: str,
                 course_id: int, term_id: int, run_aic_default: bool = False,
                 parent=None):
        super().__init__(parent)
        self._api = api
        self._selected = selected_items
        self._course_name = course_name
        self._course_id = course_id
        self._term_id = term_id
        self._worker = None

        self.setWindowTitle("Run Autograder")
        self.setMinimumWidth(560)
        self._setup_ui()
        self._run_aic.setChecked(run_aic_default)
        self._update_options_visibility()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header
        info_label = QLabel(
            f"<b>Course:</b> {self._course_name}<br>"
            f"<b>Selected:</b> {', '.join(i['name'] for i in self._selected)} "
            f"({len(self._selected)} assignment{'s' if len(self._selected) != 1 else ''})"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Tool selection
        tool_box = QGroupBox("Tool")
        tool_vbox = QVBoxLayout(tool_box)
        tool_vbox.setSpacing(SPACING_SM)
        self._tool_bg = QButtonGroup(self)
        tools = [
            ("ci",   "Complete / Incomplete"),
            ("df",   "Discussion Forum"),
            ("aic",  "Academic Integrity Checker"),
        ]
        for key, label in tools:
            rb = QRadioButton(label)
            rb.setProperty("tool_key", key)
            self._tool_bg.addButton(rb)
            tool_vbox.addWidget(rb)
            if key == "ci":
                rb.setChecked(True)
        self._tool_bg.buttonClicked.connect(lambda _: self._update_options_visibility())
        layout.addWidget(tool_box)

        # Options
        self._options_box = QGroupBox("Options")
        self._opt_form = QFormLayout(self._options_box)
        self._opt_form.setSpacing(SPACING_SM)

        self._min_words = QSpinBox()
        self._min_words.setRange(0, 10000)
        self._min_words.setValue(200)
        self._opt_form.addRow("Min word count:", self._min_words)

        # Discussion mode
        self._disc_mode_bg = QButtonGroup(self)
        disc_mode_row = QHBoxLayout()
        for val, label in [("separate", "Separate posts & replies"), ("combined", "Combined word count")]:
            rb = QRadioButton(label)
            rb.setProperty("mode_val", val)
            self._disc_mode_bg.addButton(rb)
            disc_mode_row.addWidget(rb)
            if val == "separate":
                rb.setChecked(True)
        self._disc_mode_bg.buttonClicked.connect(lambda _: self._update_options_visibility())
        self._disc_mode_row_widget = QWidget()
        self._disc_mode_row_widget.setLayout(disc_mode_row)
        self._opt_form.addRow("Mode:", self._disc_mode_row_widget)

        # Grading type (C/I vs points)
        self._grading_type_bg = QButtonGroup(self)
        grading_row = QHBoxLayout()
        for val, label in [("complete_incomplete", "Complete/Incomplete"), ("points", "Points")]:
            rb = QRadioButton(label)
            rb.setProperty("grading_val", val)
            self._grading_type_bg.addButton(rb)
            grading_row.addWidget(rb)
            if val == "complete_incomplete":
                rb.setChecked(True)
        self._grading_type_bg.buttonClicked.connect(lambda _: self._update_options_visibility())
        self._grading_type_widget = QWidget()
        self._grading_type_widget.setLayout(grading_row)
        self._opt_form.addRow("Grading type:", self._grading_type_widget)

        self._post_words = QSpinBox()
        self._post_words.setRange(0, 10000)
        self._post_words.setValue(200)
        self._opt_form.addRow("Post min words:", self._post_words)

        self._reply_words = QSpinBox()
        self._reply_words.setRange(0, 10000)
        self._reply_words.setValue(50)
        self._opt_form.addRow("Reply min words:", self._reply_words)

        self._post_points = QDoubleSpinBox()
        self._post_points.setRange(0, 100)
        self._post_points.setValue(1.0)
        self._post_points.setSingleStep(0.5)
        self._opt_form.addRow("Post points:", self._post_points)

        self._reply_points = QDoubleSpinBox()
        self._reply_points.setRange(0, 100)
        self._reply_points.setValue(0.5)
        self._reply_points.setSingleStep(0.25)
        self._opt_form.addRow("Reply points:", self._reply_points)

        self._min_posts = QSpinBox()
        self._min_posts.setRange(1, 100)
        self._min_posts.setValue(1)
        self._opt_form.addRow("Min posts:", self._min_posts)

        self._min_replies = QSpinBox()
        self._min_replies.setRange(0, 100)
        self._min_replies.setValue(2)
        self._opt_form.addRow("Min replies:", self._min_replies)

        self._run_aic = QCheckBox("Run Academic Integrity Checker alongside")
        self._opt_form.addRow("", self._run_aic)

        self._preserve_grades = QCheckBox("Preserve existing grades")
        self._preserve_grades.setChecked(True)
        self._opt_form.addRow("", self._preserve_grades)

        layout.addWidget(self._options_box)

        # Action buttons: Cancel | …stretch… | Preview Run | Run & Post Grades
        btn_row = QHBoxLayout()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()
        self._preview_btn = QPushButton("⊙  Preview Run")
        self._preview_btn.setToolTip(
            "Run the grader and integrity check, but do NOT post any grades to Canvas.\n"
            "Review the output before committing."
        )
        self._preview_btn.clicked.connect(lambda: self._on_run(dry_run=True))
        make_secondary_button(self._preview_btn)
        btn_row.addWidget(self._preview_btn)
        self._run_btn = QPushButton("▶  Run & Post Grades")
        self._run_btn.clicked.connect(lambda: self._on_run(dry_run=False))
        make_run_button(self._run_btn)
        btn_row.addWidget(self._run_btn)
        layout.addLayout(btn_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep2)

        # Log output
        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        make_monospace_textedit(self._log_output)
        self._log_output.setVisible(False)
        self._log_output.setMinimumHeight(200)
        layout.addWidget(self._log_output)

        # Bottom actions (visible after run)
        self._post_row = QHBoxLayout()
        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        self._post_row.addWidget(self._stop_btn)
        self._open_btn = QPushButton("Open Output")
        self._open_btn.clicked.connect(self._on_open_output)
        self._post_row.addWidget(self._open_btn)
        self._post_row.addStretch()
        self._post_widget = QWidget()
        self._post_widget.setLayout(self._post_row)
        self._post_widget.setVisible(False)
        layout.addWidget(self._post_widget)

    def _update_options_visibility(self) -> None:
        tool = self._current_tool()
        is_ci = tool == "ci"
        is_df = tool == "df"
        is_aic = tool == "aic"

        mode = self._current_disc_mode()
        is_separate = mode == "separate"

        grading = self._current_grading_type()
        is_points = grading == "points"

        self._set_row_visible("Min word count:", is_ci)
        self._set_row_visible("Mode:", is_df)
        self._set_row_visible("Grading type:", is_df)
        self._set_row_visible("Post min words:", is_df)
        self._set_row_visible("Reply min words:", is_df and is_separate)
        self._set_row_visible("Post points:", is_df and is_points)
        self._set_row_visible("Reply points:", is_df and is_points)
        self._set_row_visible("Min posts:", is_df and not is_points)
        self._set_row_visible("Min replies:", is_df and is_separate and not is_points)
        self._run_aic.setVisible(is_ci or is_df)
        self._preserve_grades.setVisible(is_ci or is_df)

    def _set_row_visible(self, label_text: str, visible: bool) -> None:
        """Show/hide a form row by its label text."""
        form = self._opt_form
        for i in range(form.rowCount()):
            label_item = form.itemAt(i, QFormLayout.ItemRole.LabelRole)
            field_item = form.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if label_item and label_item.widget():
                if label_item.widget().text() == label_text:
                    label_item.widget().setVisible(visible)
                    if field_item and field_item.widget():
                        field_item.widget().setVisible(visible)
                    return

    def _current_tool(self) -> str:
        btn = self._tool_bg.checkedButton()
        return btn.property("tool_key") if btn else "ci"

    def _current_disc_mode(self) -> str:
        btn = self._disc_mode_bg.checkedButton()
        return btn.property("mode_val") if btn else "separate"

    def _current_grading_type(self) -> str:
        btn = self._grading_type_bg.checkedButton()
        return btn.property("grading_val") if btn else "complete_incomplete"

    def _on_run(self, dry_run: bool = False) -> None:
        tool = self._current_tool()

        # Determine assignment type
        if tool == "ci":
            atype = "complete_incomplete"
        elif tool == "df":
            atype = "discussion_forum"
        else:
            atype = "complete_incomplete"

        # Confirmation dialog
        dry_line = "Preview Run — results shown, no grades posted to Canvas" if dry_run else \
                   "LIVE RUN — grades WILL be posted to Canvas"
        names = ", ".join(i["name"] for i in self._selected)
        msg = (
            f"<b>Course:</b> {self._course_name}<br>"
            f"<b>Assignments:</b> {names}<br>"
            f"<b>Tool:</b> {self._tool_bg.checkedButton().text()}<br>"
            f"<b>{dry_line}</b>"
        )
        box = QMessageBox(self)
        box.setWindowTitle("Confirm Grading Run")
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(msg)
        box.setStandardButtons(QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Ok)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Ok:
            return

        # Determine group from first selected item
        first = self._selected[0]
        group_id = first.get("group_id", 0)
        group_name = first.get("group_name", "")

        self._log_output.setVisible(True)
        self._post_widget.setVisible(True)
        self._run_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)
        self._log_output.clear()

        from gui.workers import RunWorker
        self._worker = RunWorker(
            api=self._api,
            course_id=self._course_id,
            course_name=self._course_name,
            term_id=self._term_id,
            group_name=group_name,
            group_id=group_id,
            assignment_type=atype,
            min_word_count=self._min_words.value(),
            post_min_words=self._post_words.value(),
            reply_min_words=self._reply_words.value(),
            discussion_mode=self._current_disc_mode(),
            grading_type=self._current_grading_type(),
            post_points=self._post_points.value(),
            reply_points=self._reply_points.value(),
            min_posts=self._min_posts.value(),
            min_replies=self._min_replies.value(),
            run_adc=self._run_aic.isChecked() or tool == "aic",
            preserve_grades=self._preserve_grades.isChecked(),
            dry_run=dry_run,
        )
        self._worker.log_line.connect(self._append_log)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _append_log(self, line: str) -> None:
        self._log_output.append(line)
        sb = self._log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_finished(self, success: bool, message: str) -> None:
        self._run_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        icon = "Done" if success else "Error"
        self._append_log(f"\n[{icon}] {message}")

        # Auto-open folder if setting enabled
        try:
            from settings import load_settings
            from autograder_utils import open_folder, get_output_base_dir
            s = load_settings()
            if s.get("auto_open_folder"):
                open_folder(get_output_base_dir())
        except Exception:
            pass

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("\n[Stopped] Cancellation requested.")

    def _on_open_output(self) -> None:
        try:
            from autograder_utils import open_folder, get_output_base_dir
            open_folder(get_output_base_dir())
        except Exception:
            pass
