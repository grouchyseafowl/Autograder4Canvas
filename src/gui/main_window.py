"""
Main application window: menu bar, toolbar, 3-tab layout, status bar.
"""
import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QSplitterHandle, QTabWidget, QToolBar,
    QStatusBar, QLabel, QMenuBar, QMessageBox,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QPainter, QColor

from gui.styles import (
    WIN_MIN_W, WIN_MIN_H, WIN_DEFAULT_W, WIN_DEFAULT_H,
    LEFT_PANEL_MIN, LEFT_PANEL_PREF,
)
from gui.panels.course_panel import CoursePanel
from gui.panels.assignment_panel import AssignmentPanel
from gui.panels.settings_panel import SettingsPanel
from gui.panels.automation_panel import AutomationPanel
from gui.styles import BG_VOID, BORDER_DARK, PHOSPHOR_DIM


class _GripHandle(QSplitterHandle):
    """Splitter handle — void background so negative space reads between panels."""

    _BG    = QColor(BG_VOID)
    _DOT   = QColor(PHOSPHOR_DIM)
    _DOT_H = QColor("#8A5E1A")   # amber when hovered

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), self._BG)

        # thin border line on the left edge
        p.fillRect(0, 0, 1, self.height(), QColor(BORDER_DARK))

        # three grip dots centred vertically
        dot = self._DOT_H if self.underMouse() else self._DOT
        p.setBrush(dot)
        p.setPen(Qt.PenStyle.NoPen)
        cx = self.width() // 2
        cy = self.height() // 2
        for dy in (-6, 0, 6):
            p.drawEllipse(cx - 2, cy + dy - 2, 4, 4)
        p.end()

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)


class _GripSplitter(QSplitter):
    def createHandle(self):
        return _GripHandle(self.orientation(), self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._api = None
        self._editor = None
        self._current_course_id: Optional[int] = None
        self._current_term_id: Optional[int] = None
        self._courses_worker = None
        self._assignment_worker = None
        self._active_workers: list = []  # prevent premature GC of running workers

        self.setWindowTitle("Autograder4Canvas")
        self.setMinimumSize(WIN_MIN_W, WIN_MIN_H)
        self.resize(WIN_DEFAULT_W, WIN_DEFAULT_H)

        self._init_api()
        self._build_ui()
        self._connect_signals()
        self._refresh_courses()

    # ------------------------------------------------------------------
    # API initialisation
    # ------------------------------------------------------------------

    def _init_api(self) -> None:
        try:
            from automation.canvas_helpers import CanvasAutomationAPI
            from credentials import load_credentials, get_active_profile, set_env_from_profile
            data = load_credentials()
            set_env_from_profile(data)
            _, profile = get_active_profile(data)
            url = profile.get("canvas_base_url") or os.environ.get("CANVAS_BASE_URL", "")
            token = profile.get("canvas_api_token") or os.environ.get("CANVAS_API_TOKEN", "")
            if url and token:
                self._api = CanvasAutomationAPI(base_url=url, api_token=token)
                from canvas_editor import CanvasEditor
                self._editor = CanvasEditor(base_url=url, api_token=token)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self._build_menu()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()

    def _build_menu(self) -> None:
        mb = self.menuBar()

        # File
        file_menu = mb.addMenu("File")
        open_action = QAction("Open Output Folder", self)
        open_action.triggered.connect(self._open_output_folder)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # Tools
        tools_menu = mb.addMenu("Tools")
        cleanup_action = QAction("Run Cleanup Now…", self)
        cleanup_action.triggered.connect(self._run_cleanup)
        tools_menu.addAction(cleanup_action)

        # Help
        help_menu = mb.addMenu("Help")
        help_action = QAction("Help Topics…", self)
        help_action.triggered.connect(self._show_help)
        help_menu.addAction(help_action)
        help_menu.addSeparator()
        about_action = QAction("About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        refresh_action = QAction("Refresh", self)
        refresh_action.setToolTip("Re-fetch courses from Canvas")
        refresh_action.triggered.connect(self._refresh_courses)
        tb.addAction(refresh_action)

        output_action = QAction("Output Folder", self)
        output_action.setToolTip("Open output folder")
        output_action.triggered.connect(self._open_output_folder)
        tb.addAction(output_action)

        tb.addSeparator()

        self._run_toolbar_action = QAction("Run Autograder", self)
        self._run_toolbar_action.setToolTip("Run autograder for selected assignments")
        self._run_toolbar_action.setEnabled(False)
        self._run_toolbar_action.triggered.connect(self._on_run_from_toolbar)
        tb.addAction(self._run_toolbar_action)

        self._bulk_run_action = QAction("Bulk Run…", self)
        self._bulk_run_action.setToolTip("Run autograder across multiple courses at once")
        self._bulk_run_action.triggered.connect(self._open_bulk_run_dialog)
        tb.addAction(self._bulk_run_action)

    def _build_central(self) -> None:
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        self._tabs = tabs

        # Tab 0 — Courses
        self._course_panel = CoursePanel()
        self._assignment_panel = AssignmentPanel()
        splitter = _GripSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(10)
        splitter.addWidget(self._course_panel)
        splitter.addWidget(self._assignment_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([LEFT_PANEL_PREF, WIN_DEFAULT_W - LEFT_PANEL_PREF])
        self._course_panel.setMinimumWidth(LEFT_PANEL_MIN)

        # Void container — panels float on the near-black background with
        # visible negative space around them (matches setup dialog depth cues)
        from gui.styles import BG_VOID
        from PySide6.QtWidgets import QVBoxLayout
        courses_container = QWidget()
        courses_container.setAutoFillBackground(True)
        from PySide6.QtGui import QPalette
        pal = courses_container.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        courses_container.setPalette(pal)
        cl = QVBoxLayout(courses_container)
        cl.setContentsMargins(8, 8, 8, 8)
        cl.setSpacing(0)
        cl.addWidget(splitter)
        tabs.addTab(courses_container, "Courses")

        # Tab 1 — Automation
        self._automation_panel = AutomationPanel(api=self._api)
        tabs.addTab(self._automation_panel, "Automation")

        # Tab 2 — Settings
        self._settings_panel = SettingsPanel(api=self._api)
        tabs.addTab(self._settings_panel, "Settings")

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._course_panel.course_selected.connect(self._on_course_selected)
        self._course_panel.term_selected.connect(self._on_term_selected)
        self._assignment_panel.run_requested.connect(self._open_run_dialog)
        self._assignment_panel.has_selection.connect(self._run_toolbar_action.setEnabled)
        self._assignment_panel.edit_completed.connect(self._on_edit_completed)
        self._settings_panel.settings_saved.connect(self._on_settings_saved)
        self._settings_panel.open_folder_requested.connect(self._open_output_folder)

        # Pass editor to panels that support Canvas mutations
        if self._editor:
            self._assignment_panel.set_editor(self._editor)
            self._course_panel.set_editor(self._editor)

    # ------------------------------------------------------------------
    # Course / assignment loading
    # ------------------------------------------------------------------

    def _refresh_courses(self) -> None:
        if not self._api:
            self._set_status("No Canvas credentials configured — check Settings.")
            return
        self._cancel_workers()
        self._course_panel.clear()
        self._set_status("Loading courses…")

        from gui.workers import LoadCoursesWorker
        w = LoadCoursesWorker(self._api)
        # Use the atomic signal so the panel is populated in one shot —
        # avoids the flash of empty term rows before courses arrive.
        w.terms_loaded.connect(self._course_panel.populate_terms)
        w.courses_loaded.connect(self._course_panel.add_courses_for_term)
        w.courses_loaded.connect(lambda tid, c: self._set_status(f"Loaded {len(c)} courses.") if c else None)
        w.error.connect(lambda msg: self._set_status(f"Error loading courses: {msg}"))
        w.start()
        self._courses_worker = w
        self._track_worker(w)

    def _on_course_selected(self, course_id: int, course_name: str) -> None:
        self._current_course_id = course_id
        self._assignment_panel.set_course(course_id, course_name)
        self._assignment_panel.show_loading()
        self._run_toolbar_action.setEnabled(False)

        # Cancel any in-flight workers
        if self._assignment_worker:
            self._assignment_worker.cancel()

        self._set_status(f"Loading assignments for {course_name}…")

        from gui.workers import LoadAssignmentsWorker
        w = LoadAssignmentsWorker(self._api, course_id)
        w.assignments_loaded.connect(self._on_assignments_loaded)
        w.error.connect(lambda msg: self._set_status(f"Error: {msg}"))
        w.start()
        self._assignment_worker = w
        self._track_worker(w)

    def _on_assignments_loaded(self, groups: list) -> None:
        self._assignment_panel.populate_tree(groups)
        self._set_status("Assignments loaded.")


    # ------------------------------------------------------------------
    # Run dialog
    # ------------------------------------------------------------------

    def _open_run_dialog(self, selected: list, course_name: str, course_id: int,
                         mark_incomplete_no_sub: bool = False,
                         run_aic: bool = False) -> None:
        if not self._api:
            QMessageBox.warning(self, "No Credentials",
                                "Configure Canvas credentials in the Settings tab first.")
            return

        term_id = self._current_term_id or 0

        from gui.dialogs.run_dialog import RunDialog
        dlg = RunDialog(
            api=self._api,
            selected_items=selected,
            course_name=course_name,
            course_id=course_id,
            term_id=term_id,
            run_aic_default=run_aic,
            parent=self,
        )
        dlg.exec()

    def _open_bulk_run_dialog(self) -> None:
        if not self._api:
            QMessageBox.warning(self, "No Credentials",
                                "Configure Canvas credentials in the Settings tab first.")
            return
        courses_by_term = self._course_panel.get_all_courses_by_term()
        if not courses_by_term:
            QMessageBox.information(self, "No Courses",
                                    "No courses loaded yet. Refresh first.")
            return
        from gui.dialogs.bulk_run_dialog import BulkRunDialog
        dlg = BulkRunDialog(api=self._api, courses_by_term=courses_by_term, parent=self)
        dlg.exec()

    def _on_run_from_toolbar(self) -> None:
        self._assignment_panel._on_run_clicked()

    def _on_term_selected(self, term_id: int) -> None:
        self._current_term_id = term_id

# ------------------------------------------------------------------
    # Settings saved
    # ------------------------------------------------------------------

    def _on_edit_completed(self) -> None:
        """Re-fetch assignments after a Canvas edit to get fresh data."""
        if self._current_course_id and self._api:
            self._set_status("Refreshing assignments…")
            from gui.workers import LoadAssignmentsWorker
            w = LoadAssignmentsWorker(self._api, self._current_course_id)
            w.assignments_loaded.connect(self._on_assignments_loaded)
            w.error.connect(lambda msg: self._set_status(f"Error: {msg}"))
            w.start()
            self._assignment_worker = w
            self._track_worker(w)

    def _on_settings_saved(self) -> None:
        self._set_status("Settings saved.")
        # Re-init API with new credentials
        self._init_api()
        if self._editor:
            self._assignment_panel.set_editor(self._editor)
            self._course_panel.set_editor(self._editor)
        if self._automation_panel._api is None:
            self._automation_panel._api = self._api
        self._refresh_courses()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _track_worker(self, w) -> None:
        """Keep a reference to w until its thread finishes (prevents premature GC)."""
        self._active_workers.append(w)
        w.finished.connect(lambda: self._active_workers.remove(w)
                           if w in self._active_workers else None)

    def _cancel_workers(self) -> None:
        for w in (self._courses_worker, self._assignment_worker):
            if w:
                w.cancel()

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _open_output_folder(self) -> None:
        try:
            from autograder_utils import open_folder, get_output_base_dir
            open_folder(get_output_base_dir())
        except Exception:
            pass

    def _run_cleanup(self) -> None:
        from gui.dialogs.cleanup_dialog import CleanupDialog
        dlg = CleanupDialog(parent=self)
        dlg.exec()

    def _show_help(self) -> None:
        from gui.dialogs.help_dialog import HelpDialog
        dlg = HelpDialog(parent=self)
        dlg.exec()

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About Autograder4Canvas",
            "<b>Autograder4Canvas</b><br>"
            "A desktop GUI for Canvas autograding tools.<br><br>"
            "Grades Canvas discussions and complete/incomplete assignments,<br>"
            "with an Academic Integrity Checker.",
        )

    def closeEvent(self, event) -> None:
        self._cancel_workers()
        event.accept()
