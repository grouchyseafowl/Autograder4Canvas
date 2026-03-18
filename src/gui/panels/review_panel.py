"""
Review Panel — Container with ViewToggle switching between Grading Review,
Academic Integrity, and Insights.

Sits at Page 3 in the main window stack. All three views share the same
SQLite database and operate on the same students/assignments.

Layout:
  ┌────────────────────────────────────────────────────────────────┐
  │  REVIEW  [Grading Review ◆ | ◆ Academic Integrity | Insights] │  ← page header
  │  Review grading results, integrity patterns, and insights.     │  ← subtitle
  │  ────────────────────────────────────────────────────────────  │  ← h_rule
  ├────────────────────────────────────────────────────────────────┤
  │  QStackedWidget:                                               │
  │    index 0: GradingResultsPanel                               │
  │    index 1: PriorRunsPanel (AIC) — has own ethical strip      │
  │    index 2: InsightsPanel (optional, when passed in)          │
  └────────────────────────────────────────────────────────────────┘
"""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget,
)

from gui.styles import (
    px,
    PHOSPHOR_HOT, PHOSPHOR_DIM,
    BORDER_DARK, BORDER_AMBER,
    PANE_BG_GRADIENT,
)


class ReviewPanel(QFrame):
    """Page 3 container: ViewToggle + stacked GradingResultsPanel /
    PriorRunsPanel / InsightsPanel."""

    def __init__(self, api=None, store=None, insights_panel=None, parent=None):
        super().__init__(parent)
        self._api             = api
        self._store           = store
        self._insights_panel  = insights_panel
        self.setObjectName("reviewPanel")
        self.setStyleSheet(f"""
            QFrame#reviewPanel {{
                background: {PANE_BG_GRADIENT};
                border: 1px solid {BORDER_DARK};
                border-top-color: {BORDER_AMBER};
                border-radius: 8px;
            }}
            QFrame#reviewPanel > QLabel {{
                background: transparent;
                border: none;
            }}
        """)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 0)
        layout.setSpacing(10)

        # ── Page header: title + ViewToggle on one line, subtitle, h_rule ─
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title = QLabel("REVIEW")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        header_row.addWidget(title)

        from gui.widgets.view_toggle import ViewToggle
        if self._insights_panel is not None:
            self._toggle = ViewToggle(
                parent=self,
                segments=[
                    ("Grading Review",       "grading"),
                    ("Academic Integrity",   "aic"),
                    ("Insights",             "insights"),
                ],
            )
        else:
            self._toggle = ViewToggle(
                parent=self,
                left_label="Grading Review",
                right_label="Academic Integrity",
                left_mode="grading",
                right_mode="aic",
            )
        header_row.addWidget(self._toggle)
        header_row.addStretch()
        layout.addLayout(header_row)

        if self._insights_panel is not None:
            subtitle_text = (
                "Review grading results, academic integrity patterns, and course insights."
            )
        else:
            subtitle_text = (
                "Review grading results and academic integrity patterns across assignments."
            )
        sub = QLabel(subtitle_text)
        sub.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        sub.setWordWrap(True)
        layout.addWidget(sub)

        # Amber gradient separator (matches course panel)
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0.00 rgba(240,168,48,0),
                    stop:0.20 rgba(240,168,48,0.35),
                    stop:0.50 rgba(240,168,48,0.70),
                    stop:0.80 rgba(240,168,48,0.35),
                    stop:1.00 rgba(240,168,48,0));
                border: none;
            }}
        """)
        layout.addWidget(sep)

        # ── Stacked content ───────────────────────────────────────────────
        self._stack = QStackedWidget()

        # Index 0: Grading Results
        from gui.panels.grading_results_panel import GradingResultsPanel
        self._grading_panel = GradingResultsPanel(api=self._api)
        self._stack.addWidget(self._grading_panel)

        # Index 1: Prior Runs (AIC)
        from gui.panels.prior_runs_panel import PriorRunsPanel
        self._aic_panel = PriorRunsPanel(api=self._api, store=self._store)
        self._stack.addWidget(self._aic_panel)

        # Index 2: Insights (optional)
        if self._insights_panel is not None:
            self._stack.addWidget(self._insights_panel)

        self._stack.setCurrentIndex(0)
        layout.addWidget(self._stack, 1)

    def _connect_signals(self) -> None:
        self._toggle.mode_changed.connect(self._on_mode_changed)
        # Cross-navigation: grading → AIC
        self._grading_panel.view_aic_detail.connect(self._switch_to_aic)

    def _on_mode_changed(self, mode: str) -> None:
        if mode == "grading":
            self._stack.setCurrentIndex(0)
            self._grading_panel.refresh()
        elif mode == "aic":
            self._stack.setCurrentIndex(1)
        elif mode == "insights" and self._insights_panel is not None:
            self._stack.setCurrentIndex(2)

    def set_course(self, course_id: int, course_name: str) -> None:
        """Propagate course selection from Course Select to both review sub-panels."""
        self._grading_panel.set_course(str(course_id), course_name)

    def _switch_to_aic(self, student_id: str, assignment_id: str) -> None:
        """Cross-navigate from grading detail to AIC detail view for a specific student."""
        self._toggle.set_mode("aic")
        self._on_mode_changed("aic")
        self._aic_panel.navigate_to_student(student_id, assignment_id)
