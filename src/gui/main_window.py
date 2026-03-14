"""
Main application window: menu bar, unified nav/action bar, stacked-page layout, status bar.
"""
import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QSplitter, QSplitterHandle, QStackedWidget,
    QStatusBar, QLabel, QMenuBar, QMessageBox, QHBoxLayout, QVBoxLayout,
    QPushButton, QButtonGroup, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QPainter, QColor

from gui.styles import (
    WIN_MIN_W, WIN_MIN_H, WIN_DEFAULT_W, WIN_DEFAULT_H,
    LEFT_PANEL_MIN, LEFT_PANEL_PREF,
    BG_VOID, BG_PANEL, BORDER_DARK, BORDER_AMBER,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT,
)
from gui.panels.course_panel import CoursePanel
from gui.panels.assignment_panel import AssignmentPanel
from gui.panels.settings_panel import SettingsPanel
from gui.panels.automation_panel import AutomationPanel


# ---------------------------------------------------------------------------
# Nav bar button stylesheets
# ---------------------------------------------------------------------------

_NAV_BTN_QSS = f"""
    QPushButton {{
        background: transparent;
        color: {PHOSPHOR_DIM};
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0;
        padding: 0 18px;
        font-family: "Menlo", "Consolas", "Courier New", monospace;
        font-size: 12px;
        min-height: 46px;
    }}
    QPushButton:hover:!checked {{
        color: {PHOSPHOR_MID};
        background: rgba(90, 60, 8, 0.10);
    }}
    QPushButton:checked {{
        color: {PHOSPHOR_HOT};
        border-bottom: 2px solid {ROSE_ACCENT};
        font-weight: bold;
        background: qradialgradient(cx:0.50,cy:1.00,radius:1.10,
            stop:0.00 #2A1E08,stop:0.70 #181408,stop:1.00 {BG_PANEL});
    }}
    QPushButton:pressed {{
        background: rgba(90, 60, 8, 0.15);
    }}
"""

_ACTION_BTN_QSS = f"""
    QPushButton {{
        background: transparent;
        color: {PHOSPHOR_DIM};
        border: none;
        border-radius: 0;
        padding: 0 18px;
        font-family: "Menlo", "Consolas", "Courier New", monospace;
        font-size: 12px;
        min-height: 46px;
    }}
    QPushButton:hover {{
        color: {PHOSPHOR_MID};
        background: rgba(90, 60, 8, 0.10);
    }}
    QPushButton:pressed {{
        color: {PHOSPHOR_HOT};
        background: rgba(90, 60, 8, 0.15);
    }}
"""


# ---------------------------------------------------------------------------
# Custom splitter handle
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

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

    def _build_nav_bar(self) -> QFrame:
        """Single unified nav/action bar replacing the old toolbar + tab bar."""
        bar = QFrame()
        bar.setObjectName("navBar")
        bar.setFixedHeight(48)
        bar.setStyleSheet(f"""
            QFrame#navBar {{
                background: {BG_PANEL};
                border-bottom: 1px solid {BORDER_DARK};
            }}
            QFrame#navBar QLabel {{
                background: transparent;
                border: none;
            }}
        """)

        h = QHBoxLayout(bar)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(0)

        # ── App name label ────────────────────────────────────────────────
        name_lbl = QLabel(
            f"<span style='color:{PHOSPHOR_HOT};letter-spacing:2px;"
            f"font-weight:700;font-size:11px;line-height:1.3;'>"
            f"AUTOGRADER<br>"
            f"<span style='color:{ROSE_ACCENT};'>4CANVAS</span></span>"
        )
        name_lbl.setTextFormat(Qt.TextFormat.RichText)
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        name_lbl.setFixedWidth(110)
        name_lbl.setFixedHeight(48)
        name_lbl.setStyleSheet(f"""
            QLabel {{
                padding: 0 12px;
                border-right: 1px solid {BORDER_DARK};
            }}
        """)
        h.addWidget(name_lbl)

        # ── Nav buttons (mutually exclusive, page switchers) ──────────────
        self._nav_group = QButtonGroup(bar)
        self._nav_group.setExclusive(True)

        from PySide6.QtGui import QFont
        _mono = QFont("Menlo")
        _mono.setStyleHint(QFont.StyleHint.TypeWriter)
        _mono.setPixelSize(12)

        def _nav_btn(label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFont(_mono)
            btn.setStyleSheet(_NAV_BTN_QSS)
            return btn

        def _action_btn(label: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setFont(_mono)
            btn.setStyleSheet(_ACTION_BTN_QSS)
            return btn

        # Course Select → page 0
        self._btn_courses = _nav_btn("Course Select")
        self._btn_courses.clicked.connect(lambda: self._stack.setCurrentIndex(0))
        self._nav_group.addButton(self._btn_courses)
        h.addWidget(self._btn_courses)

        # Bulk Run → opens dialog (action, not a page)
        btn_bulk = _action_btn("Bulk Run")
        btn_bulk.clicked.connect(self._open_bulk_run_dialog)
        h.addWidget(btn_bulk)

        # Review Prior Runs → page 3
        self._btn_prior = _nav_btn("Review Prior Runs")
        self._btn_prior.clicked.connect(lambda: self._stack.setCurrentIndex(3))
        self._nav_group.addButton(self._btn_prior)
        h.addWidget(self._btn_prior)

        # Automation → page 1
        self._btn_automation = _nav_btn("Automation")
        self._btn_automation.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        self._nav_group.addButton(self._btn_automation)
        h.addWidget(self._btn_automation)

        # Settings → page 2
        self._btn_settings = _nav_btn("Settings")
        self._btn_settings.clicked.connect(lambda: self._stack.setCurrentIndex(2))
        self._nav_group.addButton(self._btn_settings)
        h.addWidget(self._btn_settings)

        # ── Spacer + separator before Refresh ────────────────────────────
        h.addStretch()

        sep = QWidget()
        sep.setFixedWidth(1)
        sep.setFixedHeight(28)
        sep.setStyleSheet(f"background: {BORDER_DARK};")
        h.addWidget(sep, 0, Qt.AlignmentFlag.AlignVCenter)

        # Refresh from Canvas → action
        btn_refresh = _action_btn("Refresh from Canvas")
        btn_refresh.clicked.connect(self._refresh_courses)
        h.addWidget(btn_refresh)

        # Default to courses page active
        self._btn_courses.setChecked(True)

        return bar

    def _build_central(self) -> None:
        # Root container: nav bar on top, stacked content below
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_nav_bar())

        self._stack = QStackedWidget()
        root_layout.addWidget(self._stack, 1)

        self.setCentralWidget(root)

        # ── Page 0: Courses ───────────────────────────────────────────────
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

        from PySide6.QtGui import QPalette
        courses_container = QWidget()
        courses_container.setAutoFillBackground(True)
        pal = courses_container.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        courses_container.setPalette(pal)
        cl = QVBoxLayout(courses_container)
        cl.setContentsMargins(8, 8, 8, 8)
        cl.setSpacing(0)
        cl.addWidget(splitter)
        self._stack.addWidget(courses_container)   # index 0

        # ── Page 1: Automation ────────────────────────────────────────────
        self._automation_panel = AutomationPanel(api=self._api)
        self._stack.addWidget(self._automation_panel)  # index 1

        # ── Page 2: Settings ──────────────────────────────────────────────
        self._settings_panel = SettingsPanel(api=self._api)
        self._stack.addWidget(self._settings_panel)    # index 2

        # ── Page 3: Prior Runs ────────────────────────────────────────────
        self._stack.addWidget(self._build_prior_runs_page())  # index 3

        self._stack.setCurrentIndex(0)

    def _build_prior_runs_page(self) -> QWidget:
        """Simple page pointing users to the output folder for run history."""
        from gui.styles import make_secondary_button
        from PySide6.QtGui import QPalette

        page = QWidget()
        page.setAutoFillBackground(True)
        pal = page.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        page.setPalette(pal)

        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(12)

        title = QLabel("PRIOR RUNS")
        title.setProperty("heading", "true")
        layout.addWidget(title)

        desc = QLabel(
            "Grading results are saved to your configured output folder. "
            "Open it to browse run history, reports, and CSVs."
        )
        desc.setProperty("muted", "true")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(8)

        open_btn = QPushButton("Open Output Folder")
        make_secondary_button(open_btn)
        open_btn.setFixedWidth(200)
        open_btn.clicked.connect(self._open_output_folder)
        layout.addWidget(open_btn)

        layout.addStretch()
        return page

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
        self._assignment_panel.edit_completed.connect(self._on_edit_completed)
        self._settings_panel.settings_saved.connect(self._on_settings_saved)

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
                         run_aic: bool = False,
                         preserve_grades: bool = True) -> None:
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
            preserve_grades_default=preserve_grades,
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
