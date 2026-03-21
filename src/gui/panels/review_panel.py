"""
Review Panel — Shared sidebar + three content sub-tabs.

Layout:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  REVIEW  [Grading Review ◆ | ◆ Academic Integrity | Insights]      │
  │  Review grading results, integrity patterns, and course insights.   │
  │  ──────────────────────────────────────────────────────────────── │
  ├───────────────┬─────────────────────────────────────────────────────┤
  │  ReviewSidebar│   QStackedWidget:                                   │
  │  (shared)     │     index 0: GradingResultsPanel (content-only)     │
  │               │     index 1: PriorRunsPanel (content-only)          │
  │               │     index 2: InsightsPanel (review content)         │
  └───────────────┴─────────────────────────────────────────────────────┘

The sidebar persists across all 3 sub-tabs.  Tabs change the right panel
only.  Selection in the sidebar triggers load_assignment() on the active
content panel.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QStackedWidget, QWidget,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette

from gui.styles import (
    px,
    PHOSPHOR_HOT, PHOSPHOR_DIM,
    BORDER_DARK, BORDER_AMBER,
    BG_VOID,
    PANE_BG_GRADIENT, GripSplitter,
    make_h_rule,
)


class ReviewPanel(QWidget):
    """Page 3 container: shared ReviewSidebar + ViewToggle + stacked
    GradingResultsPanel / PriorRunsPanel / InsightsPanel.

    Background is BG_VOID (black) — sidebar and content panels float as
    distinct rounded cards, matching the Course Select page layout.
    """

    def __init__(self, api=None, store=None, insights_panel=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._store = store
        self._insights_panel = insights_panel

        # Black void background — panels float on top
        self.setAutoFillBackground(True)
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        self.setPalette(pal)

        self._active_mode = "grading"
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # ── Page header: title + ViewToggle (on black background) ────
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
                    ("Grading Review",     "grading"),
                    ("Academic Integrity", "aic"),
                    ("Insights",           "insights"),
                ],
                segment_colors=["amber", "blue", "rose"],
            )
        else:
            self._toggle = ViewToggle(
                parent=self,
                left_label="Grading Review",
                right_label="Academic Integrity",
                left_mode="grading",
                right_mode="aic",
                segment_colors=["amber", "blue"],
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

        # Amber gradient separator (matches Course Select)
        layout.addWidget(make_h_rule())

        # ── Splitter: sidebar left, content right ──────────────────────
        self._splitter = GripSplitter.create(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(10)

        # Left: shared sidebar (already has its own card frame)
        from gui.widgets.review_sidebar import ReviewSidebar
        self._sidebar = ReviewSidebar()
        self._splitter.addWidget(self._sidebar)

        # Right: stacked content panels wrapped in a card frame
        content_card = QFrame()
        content_card.setObjectName("reviewContentCard")
        content_card.setStyleSheet(f"""
            QFrame#reviewContentCard {{
                background: {PANE_BG_GRADIENT};
                border: 1px solid {BORDER_DARK};
                border-top-color: {BORDER_AMBER};
                border-radius: 8px;
            }}
        """)
        card_layout = QVBoxLayout(content_card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        self._stack = QStackedWidget()

        # Index 0: Grading Results (content-only — sidebar removed)
        from gui.panels.grading_results_panel import GradingResultsPanel
        self._grading_panel = GradingResultsPanel(api=self._api)
        self._stack.addWidget(self._grading_panel)

        # Index 1: Prior Runs (AIC) (content-only — sidebar removed)
        from gui.panels.prior_runs_panel import PriorRunsPanel
        self._aic_panel = PriorRunsPanel(api=self._api, store=self._store)
        self._stack.addWidget(self._aic_panel)

        # Index 2: Insights (optional)
        if self._insights_panel is not None:
            self._stack.addWidget(self._insights_panel)

        self._stack.setCurrentIndex(0)
        card_layout.addWidget(self._stack)

        self._splitter.addWidget(content_card)
        self._splitter.setStretchFactor(0, 0)
        self._splitter.setStretchFactor(1, 1)
        self._splitter.setSizes([260, 800])

        layout.addWidget(self._splitter, 1)

    def _connect_signals(self) -> None:
        self._toggle.mode_changed.connect(self._on_mode_changed)
        self._sidebar.assignment_selected.connect(self._on_sidebar_assignment)
        self._sidebar.refresh_requested.connect(self._on_sidebar_refresh)
        # Cross-navigation: grading → AIC → back to grading
        self._grading_panel.view_aic_detail.connect(self._switch_to_aic)
        self._aic_panel.return_to_grading.connect(self._return_to_grading)

    # ── Mode switching ────────────────────────────────────────────────

    def _on_mode_changed(self, mode: str) -> None:
        self._active_mode = mode
        if mode == "grading":
            self._stack.setCurrentIndex(0)
            self._grading_panel.refresh()
        elif mode == "aic":
            self._stack.setCurrentIndex(1)
        elif mode == "insights" and self._insights_panel is not None:
            self._stack.setCurrentIndex(2)
        # Update sidebar brightness for active tab
        self._sidebar.set_active_tab(mode)

    # ── Sidebar → content wiring ──────────────────────────────────────

    def _on_sidebar_assignment(self, data: dict) -> None:
        """Route sidebar selection to the active content panel."""
        cid = data.get("course_id", "")
        aid = data.get("assignment_id", "")
        cname = data.get("course_name", "")
        aname = data.get("assignment_name", "")

        # Empty dict means deselection — nothing to load
        if not aid:
            return

        if self._active_mode == "grading":
            self._grading_panel.load_assignment(cid, aid, cname, aname)
        elif self._active_mode == "aic":
            self._aic_panel.load_assignment(cid, aid)
        elif self._active_mode == "insights":
            if self._insights_panel is not None:
                self._insights_panel.load_assignment(cid, aid)

    def _on_sidebar_refresh(self) -> None:
        """Re-query stores and refresh the sidebar."""
        self._sidebar._rebuild_assignment_list()

    # ── Public API ────────────────────────────────────────────────────

    def set_courses(
        self,
        courses_by_term: list,
        assignments_cache: Optional[dict] = None,
    ) -> None:
        """Populate the sidebar with courses and assignments.

        courses_by_term: [(term_id, term_name, is_current, [course_dicts])]
        assignments_cache: {course_id: [assignment_group_dicts]}
        """
        self._sidebar.set_courses(courses_by_term, assignments_cache)

    def set_stores(self, grading_store=None, insights_store=None) -> None:
        """Provide stores to the sidebar for data availability queries."""
        self._sidebar.set_stores(grading_store, insights_store)

    def set_course(self, course_id: int, course_name: str) -> None:
        """Legacy: propagate course selection from Course Select."""
        # Still useful for grading panel's filter
        self._grading_panel.set_course(str(course_id), course_name)

    def _switch_to_aic(self, student_id: str, assignment_id: str) -> None:
        """Cross-navigate from grading detail to AIC detail view."""
        self._toggle.set_mode("aic")
        self._on_mode_changed("aic")
        self._aic_panel.navigate_to_student(student_id, assignment_id)

    def _return_to_grading(self) -> None:
        """Return from AIC detail back to grading review."""
        self._toggle.set_mode("grading")
        self._on_mode_changed("grading")
