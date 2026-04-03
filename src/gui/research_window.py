"""
ResearchWindow — minimal QMainWindow shell for the research comparison tool.

Launched from scripts/launch_research.py. Never imported by the main GUI.
"""

from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from gui.styles import BG_VOID


class ResearchWindow(QMainWindow):
    def __init__(self, api=None, store=None, parent=None):
        super().__init__(parent)
        self._api   = api
        self._store = store

        self.setWindowTitle("Research Comparison — Autograder4Canvas")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 900)
        self.setStyleSheet(f"QMainWindow {{ background: {BG_VOID}; }}")

        from gui.panels.research_panel import ResearchPanel
        self._panel = ResearchPanel(api=api, store=store)
        self.setCentralWidget(self._panel)

        if api:
            self._load_courses()

    def _load_courses(self) -> None:
        from gui.workers import LoadCoursesWorker
        self._courses_worker = LoadCoursesWorker(self._api)
        self._courses_worker.terms_loaded.connect(self._panel.on_terms_loaded)
        self._courses_worker.courses_loaded.connect(self._panel.on_courses_loaded)
        self._courses_worker.finished.connect(
            lambda: self._panel.on_courses_done()
        )
        self._courses_worker.start()

    def closeEvent(self, event) -> None:
        self._panel.cleanup()
        event.accept()
