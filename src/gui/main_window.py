"""
Main application window: menu bar, unified nav/action bar, stacked-page layout, status bar.
"""
import os
from typing import Optional

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QStackedWidget,
    QStatusBar, QLabel, QMenuBar, QMessageBox, QHBoxLayout, QVBoxLayout,
    QPushButton, QButtonGroup, QFrame,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QKeySequence, QColor

from gui.styles import (
    px,
    WIN_MIN_W, WIN_MIN_H, WIN_DEFAULT_W, WIN_DEFAULT_H,
    LEFT_PANEL_MIN, LEFT_PANEL_PREF,
    BG_VOID, BG_PANEL, BORDER_DARK, BORDER_AMBER,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT, GripSplitter,
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
        font-size: {px(12)}px;
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
        font-size: {px(12)}px;
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
# Main window
# ---------------------------------------------------------------------------

_PROFILE_LABEL = {"hs": "High School", "cc": "Community College"}


class MainWindow(QMainWindow):
    def __init__(self, demo_mode: bool = False, demo_profile: str = "hs"):
        super().__init__()
        self._demo_mode    = demo_mode
        self._demo_profile = demo_profile
        self._api = None
        self._editor = None
        self._current_course_id: Optional[int] = None
        self._current_course_name: Optional[str] = None
        self._current_term_id: Optional[int] = None
        self._courses_worker = None
        self._assignment_worker = None
        self._prefetch_worker = None
        self._assignments_cache: dict = {}  # course_id → [group_dicts]
        self._active_workers: list = []  # prevent premature GC of running workers

        if demo_mode:
            label = _PROFILE_LABEL.get(demo_profile, demo_profile)
            title = f"Autograder4Canvas — Demo ({label})"
        else:
            title = "Autograder4Canvas"
        self.setWindowTitle(title)
        self.setMinimumSize(WIN_MIN_W, WIN_MIN_H)
        self.resize(WIN_DEFAULT_W, WIN_DEFAULT_H)

        if not demo_mode:
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

        # Bulk Run → page 4
        self._btn_bulk = _nav_btn("Bulk Run")
        self._btn_bulk.clicked.connect(self._show_bulk_run_page)
        self._nav_group.addButton(self._btn_bulk)
        h.addWidget(self._btn_bulk)

        # Review → page 3 (Grading + AIC + Insights)
        self._btn_prior = _nav_btn("Review")
        self._btn_prior.clicked.connect(self._show_review_page)
        self._nav_group.addButton(self._btn_prior)
        h.addWidget(self._btn_prior)

        # Automation → page 1
        self._btn_automation = _nav_btn("Automation")
        self._btn_automation.clicked.connect(lambda: self._stack.setCurrentIndex(1))
        self._nav_group.addButton(self._btn_automation)
        if not self._demo_mode:
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

        # Refresh → action (label differs in demo mode)
        refresh_label = "Refresh" if self._demo_mode else "Refresh from Canvas"
        btn_refresh = _action_btn(refresh_label)
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
        self._course_splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        self._course_splitter.setHandleWidth(10)
        self._course_splitter.addWidget(self._course_panel)
        self._course_splitter.addWidget(self._assignment_panel)
        self._course_splitter.setStretchFactor(0, 0)
        self._course_splitter.setStretchFactor(1, 1)
        self._course_splitter.setSizes([LEFT_PANEL_PREF, WIN_DEFAULT_W - LEFT_PANEL_PREF])
        self._course_panel.setMinimumWidth(LEFT_PANEL_MIN)

        from PySide6.QtGui import QPalette
        courses_container = QWidget()
        courses_container.setAutoFillBackground(True)
        pal = courses_container.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        courses_container.setPalette(pal)
        cl = QVBoxLayout(courses_container)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        # Page header (matches Bulk Run's title bar)
        cs_title = QLabel("COURSE SELECT")
        cs_title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none; letter-spacing: 2px;"
        )
        cs_sub = QLabel(
            "Select a course to view assignments and run the autograder."
        )
        cs_sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        cs_sub.setWordWrap(True)
        cl.addWidget(cs_title)
        cl.addWidget(cs_sub)

        from gui.styles import make_h_rule
        cl.addWidget(make_h_rule())

        cl.addWidget(self._course_splitter, 1)
        self._stack.addWidget(courses_container)   # index 0

        # ── Page 1: Automation ────────────────────────────────────────────
        self._automation_panel = AutomationPanel(api=self._api)
        self._stack.addWidget(self._automation_panel)  # index 1

        # ── Page 2: Settings ──────────────────────────────────────────────
        self._settings_panel = SettingsPanel(api=self._api)
        self._stack.addWidget(self._settings_panel)    # index 2

        # ── Insights panel (lives inside ReviewPanel, not a top-level stack page) ─
        from insights.insights_store import InsightsStore
        from gui.panels.insights_panel import InsightsPanel
        self._insights_store = InsightsStore()
        self._insights_panel = InsightsPanel(
            api=self._api, store=self._insights_store, demo_mode=self._demo_mode
        )

        # ── Page 3: Review (Grading Results + AIC + Insights) ─────────────
        from gui.panels.review_panel import ReviewPanel
        if self._demo_mode:
            from automation.demo_store import DemoRunStore
            self._review_panel = ReviewPanel(
                api=None,
                store=DemoRunStore(profile=self._demo_profile),
                insights_panel=self._insights_panel,
            )
        else:
            self._review_panel = ReviewPanel(
                api=self._api,
                insights_panel=self._insights_panel,
            )
        self._stack.addWidget(self._review_panel)  # index 3

        # ── Page 4: Bulk Run ──────────────────────────────────────────────
        from gui.dialogs.bulk_run_dialog import BulkRunPage
        self._bulk_run_page = BulkRunPage(api=self._api, demo_mode=self._demo_mode)
        self._stack.addWidget(self._bulk_run_page)            # index 4

        self._stack.setCurrentIndex(0)


    def _show_review_page(self) -> None:
        """Switch to the Review page, ensuring Insights has fresh course data."""
        courses_by_term = self._course_panel.get_all_courses_by_term()
        self._insights_panel.refresh_courses(
            courses_by_term, self._assignments_cache
        )
        self._stack.setCurrentIndex(3)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label)
        if self._demo_mode:
            label = _PROFILE_LABEL.get(self._demo_profile, self._demo_profile)
            demo_badge = QLabel(f"  DEMO — {label}  ")
            demo_badge.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; background: rgba(90,60,8,0.35);"
                f" border: 1px solid {BORDER_AMBER}; border-radius: 3px;"
                f" font-family: 'Menlo','Consolas','Courier New',monospace;"
                f" font-size: {px(11)}px; font-weight: bold; padding: 1px 4px;"
            )
            sb.addPermanentWidget(demo_badge)

    # ------------------------------------------------------------------
    # Signal wiring
    # ------------------------------------------------------------------

    def _connect_signals(self) -> None:
        self._course_panel.course_selected.connect(self._on_course_selected)
        self._course_panel.term_selected.connect(self._on_term_selected)
        self._assignment_panel.run_requested.connect(self._open_run_dialog)
        self._assignment_panel.edit_completed.connect(self._on_edit_completed)
        self._settings_panel.settings_saved.connect(self._on_settings_saved)

        # Sync course-panel width between Course Select and Bulk Run
        self._course_splitter.splitterMoved.connect(self._sync_to_bulk_run)
        self._bulk_run_page._pane_splitter.splitterMoved.connect(self._sync_to_course_select)

        # Pass editor to panels that support Canvas mutations
        if self._editor:
            self._assignment_panel.set_editor(self._editor)
            self._course_panel.set_editor(self._editor)

    # ------------------------------------------------------------------
    # Course / assignment loading
    # ------------------------------------------------------------------

    def _refresh_courses(self) -> None:
        if self._demo_mode:
            self._load_demo_courses()
            return
        if not self._api:
            self._set_status("No Canvas credentials configured — check Settings.")
            return
        self._cancel_workers()
        self._course_panel.clear()
        self._assignments_cache.clear()
        self._set_status("Loading courses…")

        from gui.workers import LoadCoursesWorker
        w = LoadCoursesWorker(self._api)
        w.terms_loaded.connect(self._course_panel.populate_terms)
        w.courses_loaded.connect(self._course_panel.add_courses_for_term)
        w.courses_loaded.connect(lambda tid, c: self._set_status(f"Loaded {len(c)} courses.") if c else None)
        w.error.connect(lambda msg: self._set_status(f"Error loading courses: {msg}"))
        w.finished.connect(self._on_courses_loaded_start_prefetch)
        w.start()
        self._courses_worker = w
        self._track_worker(w)

    def _load_demo_courses(self) -> None:
        """Synchronously populate the course panel with demo data."""
        from demo_data import get_demo_terms, get_demo_courses, get_demo_assignment_groups
        p = self._demo_profile
        self._course_panel.clear()
        self._assignments_cache.clear()

        terms = get_demo_terms(profile=p)
        self._course_panel.populate_terms(terms)

        for term_id, term_name, is_current in terms:
            courses = get_demo_courses(term_id, profile=p)
            self._course_panel.add_courses_for_term(term_id, courses)
            for c in courses:
                cid = c["id"]
                self._assignments_cache[cid] = get_demo_assignment_groups(cid, profile=p)

        self._set_status("Demo courses loaded. Select a course to get started.")

    def _on_course_selected(self, course_id: int, course_name: str) -> None:
        self._current_course_id = course_id
        self._current_course_name = course_name
        self._assignment_panel.set_course(course_id, course_name)
        self._review_panel.set_course(course_id, course_name)

        # Serve from prefetch cache instantly — no API call needed.
        if course_id in self._assignments_cache:
            self._on_assignments_loaded(self._assignments_cache[course_id])
            return

        if self._demo_mode:
            # Demo data should already be cached; nothing to fetch
            self._on_assignments_loaded([])
            return

        # Cache miss: prefetch hasn't reached this course yet — fetch on demand.
        self._assignment_panel.show_loading()
        if self._assignment_worker:
            self._assignment_worker.cancel()
        self._set_status(f"Loading assignments for {course_name}…")

        from gui.workers import LoadAssignmentsWorker
        w = LoadAssignmentsWorker(self._api, course_id)
        w.assignments_loaded.connect(self._on_assignments_loaded)
        w.assignments_loaded.connect(
            lambda groups, cid=course_id: self._assignments_cache.update({cid: groups})
        )
        w.error.connect(lambda msg: self._set_status(f"Error: {msg}"))
        w.start()
        self._assignment_worker = w
        self._track_worker(w)

    def _refresh_assignments(self) -> None:
        """Re-fetch assignments for the currently selected course (bypasses cache)."""
        if not self._current_course_id or not self._api or self._demo_mode:
            return
        if self._assignment_worker:
            self._assignment_worker.cancel()
        self._set_status("Refreshing assignments…")
        cid = self._current_course_id
        from gui.workers import LoadAssignmentsWorker
        w = LoadAssignmentsWorker(self._api, cid)
        w.assignments_loaded.connect(self._on_assignments_loaded)
        w.assignments_loaded.connect(
            lambda groups, _cid=cid: self._assignments_cache.update({_cid: groups})
        )
        w.error.connect(lambda msg: self._set_status(f"Error: {msg}"))
        w.start()
        self._assignment_worker = w
        self._track_worker(w)

    def _on_courses_loaded_start_prefetch(self) -> None:
        """Called when the course list finishes loading. Refreshes any selected
        course then kicks off a background fetch for all other courses."""
        self._refresh_assignments()
        self._start_assignment_prefetch()

    def _start_assignment_prefetch(self) -> None:
        """Fetch assignments for every course in the sidebar in the background."""
        if not self._api or self._demo_mode:
            return
        courses_by_term = self._course_panel.get_all_courses_by_term()
        course_ids = [
            c["id"]
            for _, _, _, courses in courses_by_term
            for c in courses
            if c.get("id") and c["id"] != self._current_course_id
        ]
        if not course_ids:
            return
        from gui.workers import LoadAllAssignmentsWorker
        w = LoadAllAssignmentsWorker(self._api, course_ids)
        w.course_assignments_loaded.connect(self._on_prefetched_assignments)
        w.start()
        self._prefetch_worker = w
        self._track_worker(w)

    def _on_prefetched_assignments(self, course_id: int, groups: list) -> None:
        """Store prefetched assignments in cache. If the user already navigated
        to this course while the prefetch was running, populate the panel now."""
        self._assignments_cache[course_id] = groups
        if (course_id == self._current_course_id
                and (self._assignment_worker is None
                     or not self._assignment_worker.isRunning())):
            self._on_assignments_loaded(groups)

    def _on_assignments_loaded(self, groups: list) -> None:
        self._assignment_panel.populate_tree(groups)
        self._set_status("Assignments loaded.")

    # ------------------------------------------------------------------
    # Run dialog
    # ------------------------------------------------------------------

    def _open_run_dialog(self, selected: list, course_name: str, course_id: int) -> None:
        if not self._api and not self._demo_mode:
            from gui.dialogs.message_dialog import show_warning
            show_warning(self, "No Credentials",
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
            demo_mode=self._demo_mode,
            parent=self,
        )
        dlg.exec()
        if self._demo_mode:
            # Zero out needs_grading_count badges for the graded assignments
            selected_ids = {a.get("id") for a in selected}
            if course_id in self._assignments_cache:
                for group in self._assignments_cache[course_id]:
                    for a in group.get("assignments", []):
                        if a.get("id") in selected_ids:
                            a["needs_grading_count"] = 0
                self._on_assignments_loaded(self._assignments_cache[course_id])
            self._set_status(
                "Grading complete — 1 student flagged for review. See Review Prior Runs \u2192"
            )
        else:
            self._refresh_assignments()

    def _show_bulk_run_page(self) -> None:
        # Refresh the course list from whatever is currently loaded
        courses_by_term = self._course_panel.get_all_courses_by_term()
        self._bulk_run_page.refresh_courses(courses_by_term)
        if self._demo_mode:
            # Pre-seed mapping panel cache so it doesn't try to call the API
            from demo_data import SPRING_2026, FALL_2025, get_demo_courses, get_demo_assignment_groups
            p  = self._demo_profile
            mp = self._bulk_run_page._mapping_panel
            for term_id in (SPRING_2026, FALL_2025):
                for c in get_demo_courses(term_id, profile=p):
                    mp._groups_cache[c["id"]] = get_demo_assignment_groups(c["id"], profile=p)
        self._stack.setCurrentIndex(4)

    def _on_term_selected(self, term_id: int) -> None:
        self._current_term_id = term_id

    # ------------------------------------------------------------------
    # Splitter width sync
    # ------------------------------------------------------------------

    def _sync_to_bulk_run(self, pos: int, index: int) -> None:
        """Course Select splitter moved → update Bulk Run left pane width."""
        cs_sizes = self._course_splitter.sizes()
        if not cs_sizes:
            return
        br_sizes = self._bulk_run_page._pane_splitter.sizes()
        if len(br_sizes) < 3:
            return
        delta = cs_sizes[0] - br_sizes[0]
        br_sizes[0] = cs_sizes[0]
        br_sizes[1] = max(100, br_sizes[1] - delta)
        self._bulk_run_page._pane_splitter.blockSignals(True)
        self._bulk_run_page._pane_splitter.setSizes(br_sizes)
        self._bulk_run_page._pane_splitter.blockSignals(False)

    def _sync_to_course_select(self, pos: int, index: int) -> None:
        """Bulk Run splitter moved → update Course Select left pane width."""
        if index != 1:
            return  # only sync when the left handle moves
        br_sizes = self._bulk_run_page._pane_splitter.sizes()
        if not br_sizes:
            return
        cs_sizes = self._course_splitter.sizes()
        if len(cs_sizes) < 2:
            return
        total = sum(cs_sizes)
        cs_sizes[0] = br_sizes[0]
        cs_sizes[1] = total - cs_sizes[0]
        self._course_splitter.blockSignals(True)
        self._course_splitter.setSizes(cs_sizes)
        self._course_splitter.blockSignals(False)

    # ------------------------------------------------------------------
    # Settings saved
    # ------------------------------------------------------------------

    def _on_edit_completed(self) -> None:
        """Re-fetch assignments after a Canvas edit to get fresh data."""
        self._refresh_assignments()

    def _on_settings_saved(self) -> None:
        self._set_status("Settings saved.")
        if not self._demo_mode:
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
        """Keep a strong Python reference until the thread finishes (prevents GC crash)."""
        self._active_workers.append(w)
        w.finished.connect(lambda: self._active_workers.remove(w)
                           if w in self._active_workers else None)

    def _cancel_workers(self) -> None:
        for w in (self._courses_worker, self._assignment_worker, self._prefetch_worker):
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
        # Cancel then wait — must call wait() so the OS thread fully exits before
        # Python GC can destroy the QThread C++ object (avoids "Destroyed while running").
        for w in list(self._active_workers):
            w.cancel()
        for w in list(self._active_workers):
            w.wait(3000)
        # Also stop workers not tracked by _active_workers
        if hasattr(self._bulk_run_page, "_mapping_panel"):
            self._bulk_run_page._mapping_panel.stop_and_wait()
        if hasattr(self, "_insights_panel"):
            self._insights_panel.cleanup()
        event.accept()
