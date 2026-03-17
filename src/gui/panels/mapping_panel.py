"""
Assignment Mapping Panel — middle panel in Bulk Run.

Shows Canvas assignment groups for each selected course, with a template
dropdown per group.  Auto-matches by keyword; user can override.
Persists mappings to ~/.canvas_autograder_templates.json.
"""
from typing import Optional, Dict, List

from PySide6.QtWidgets import (
    QFrame, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QComboBox, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from gui.styles import (
    SPACING_SM, SPACING_MD,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    ROSE_ACCENT, AMBER_BTN, TERM_GREEN, WARN_PINK,
    BORDER_DARK, BORDER_AMBER,
    BG_VOID, BG_CARD, BG_INSET, BG_PANEL,
    PANE_BG_GRADIENT,
    make_secondary_button,
)

# ---------------------------------------------------------------------------
# Stylesheets
# ---------------------------------------------------------------------------

_PANE_QSS = (
    f"QFrame#mappingPane {{"
    f"  background: {PANE_BG_GRADIENT};"
    f"  border: 1px solid {BORDER_DARK};"
    f"  border-top-color: {BORDER_AMBER};"
    f"  border-radius: 8px;"
    f"}}"
)

_SCROLL_QSS = f"""
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: {BG_INSET}; }}
"""

_SECTION_HDR_QSS = (
    f"QPushButton {{"
    f"  color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
    f"  letter-spacing: 1px; background: transparent; border: none;"
    f"  text-align: left; padding: 8px 8px 3px 8px;"
    f"}}"
    f"QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}"
)

_COMBO_QSS = f"""
    QComboBox {{
        background: {BG_INSET};
        border: 1px solid {BORDER_DARK};
        border-radius: 3px;
        padding: 2px 6px;
        color: {PHOSPHOR_MID};
        font-size: 11px;
        min-height: 20px;
    }}
    QComboBox:focus {{ border-color: {BORDER_AMBER}; }}
    QComboBox QAbstractItemView {{
        background: {BG_CARD};
        border: 1px solid {BORDER_DARK};
        color: {PHOSPHOR_MID};
        selection-background-color: #2C1C08;
        selection-color: {PHOSPHOR_HOT};
    }}
"""

_UNASSIGNED = "— Skip (do not grade) —"


# ---------------------------------------------------------------------------
# _GroupMappingRow
# ---------------------------------------------------------------------------

class _GroupMappingRow(QWidget):
    """Single assignment group row: name | template dropdown | status dot."""

    mapping_changed = Signal(int, str, object)   # (group_id, group_name, template_name_or_None)

    def __init__(self, group: dict, course_id: int,
                 templates: dict, mappings: dict, parent=None):
        super().__init__(parent)
        self._group = group
        self._course_id = course_id
        self._group_id = group.get("id", 0)
        self._group_name = group.get("name", "")
        self.setStyleSheet("background: transparent;")

        from assignment_templates import resolve_group
        resolved_name, _src = resolve_group(
            course_id, self._group_name, templates, mappings
        )

        row = QHBoxLayout(self)
        row.setContentsMargins(8, 3, 8, 3)
        row.setSpacing(6)

        # Group name — fixed width so all rows' combos align
        name_lbl = QLabel(self._group_name)
        name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: 11px;"
            f" background: transparent; border: none;"
        )
        name_lbl.setFixedWidth(150)
        name_lbl.setToolTip(self._group_name)
        row.addWidget(name_lbl, 0)

        # Template dropdown
        self._combo = QComboBox()
        self._combo.setStyleSheet(_COMBO_QSS)
        self._combo.setFixedHeight(22)
        self._combo.setMinimumWidth(130)
        self._combo.setMaximumWidth(220)
        self._combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._combo.addItem(_UNASSIGNED)
        for tname in sorted(templates.keys()):
            self._combo.addItem(tname)
        if resolved_name:
            idx = self._combo.findText(resolved_name)
            if idx >= 0:
                self._combo.setCurrentIndex(idx)
        self._combo.currentTextChanged.connect(self._on_changed)
        row.addWidget(self._combo)

        # Status indicator
        self._status = QLabel()
        self._status.setFixedWidth(16)
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("background: transparent; border: none;")
        row.addWidget(self._status)

        self._refresh_status()

    def _on_changed(self, text: str) -> None:
        tname = None if text == _UNASSIGNED else text
        from assignment_templates import set_mapping
        set_mapping(self._course_id, self._group_name, tname)
        self._refresh_status()
        self.mapping_changed.emit(self._group_id, self._group_name, tname)

    def _refresh_status(self) -> None:
        assigned = self._combo.currentText() != _UNASSIGNED
        if assigned:
            self._status.setText("✓")
            self._status.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: 12px;"
                f" background: transparent; border: none;"
            )
        else:
            self._status.setText("—")
            self._status.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 13px;"
                f" background: transparent; border: none;"
            )

    def is_assigned(self) -> bool:
        return self._combo.currentText() != _UNASSIGNED

    def current_template_name(self) -> Optional[str]:
        t = self._combo.currentText()
        return None if t == _UNASSIGNED else t

    def group_id(self) -> int:
        return self._group_id

    def reload_templates(self, templates: dict) -> None:
        """Refresh the dropdown when templates change."""
        current = self._combo.currentText()
        self._combo.blockSignals(True)
        self._combo.clear()
        self._combo.addItem(_UNASSIGNED)
        for tname in sorted(templates.keys()):
            self._combo.addItem(tname)
        idx = self._combo.findText(current)
        self._combo.setCurrentIndex(idx if idx >= 0 else 0)
        self._combo.blockSignals(False)
        self._refresh_status()


# ---------------------------------------------------------------------------
# _CourseMappingSection
# ---------------------------------------------------------------------------

class _CourseMappingSection(QWidget):
    """Collapsible section per course showing its group rows."""

    any_changed = Signal()

    def __init__(self, course_id: int, course_name: str, parent=None):
        super().__init__(parent)
        self._course_id = course_id
        self._rows: List[_GroupMappingRow] = []
        self._collapsed = True
        self._populated = False  # True once populate() has been called
        self.setStyleSheet("background: transparent;")

        lo = QVBoxLayout(self)
        lo.setContentsMargins(0, 0, 0, 0)
        lo.setSpacing(0)

        # Header button
        self._hdr = QPushButton()
        self._hdr.setFlat(True)
        self._hdr.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hdr.setStyleSheet(_SECTION_HDR_QSS)
        self._hdr.clicked.connect(self._toggle)
        lo.addWidget(self._hdr)

        # Rows container
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        self._body_lo = QVBoxLayout(self._body)
        self._body_lo.setContentsMargins(0, 0, 0, 4)
        self._body_lo.setSpacing(1)
        lo.addWidget(self._body)
        self._body.setVisible(False)

        self._short_name = course_name
        self._refresh_header()

    def set_loading(self) -> None:
        arrow = ">" if self._collapsed else "v"
        self._hdr.setText(f"{arrow}  {self._short_name.upper()}  ···")

    def populate(self, groups: list, templates: dict, mappings: dict) -> None:
        """Fill with group rows (called when groups arrive from worker)."""
        # Clear existing
        while self._body_lo.count():
            item = self._body_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows.clear()
        self._populated = True
        # Restore visibility in case the user toggled while we were loading
        self._body.setVisible(not self._collapsed)

        for group in groups:
            row = _GroupMappingRow(group, self._course_id, templates, mappings)
            row.mapping_changed.connect(lambda *_: self.any_changed.emit())
            self._rows.append(row)
            self._body_lo.addWidget(row)

        if not groups:
            empty_lbl = QLabel("No assignment groups found in Canvas")
            empty_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 11px; font-style: italic;"
                f" background: transparent; border: none; padding: 6px 12px;"
            )
            self._body_lo.addWidget(empty_lbl)

        self._refresh_header()

    def _toggle(self) -> None:
        self._collapsed = not self._collapsed
        self._body.setVisible(not self._collapsed)
        self._refresh_header()

    def _refresh_header(self) -> None:
        arrow = ">" if self._collapsed else "v"
        n = len(self._rows)
        unmatched = sum(1 for r in self._rows if not r.is_assigned())
        if not self._populated:
            suffix = ""
        elif n == 0:
            suffix = "  — no groups found"
        elif unmatched:
            suffix = f"  — {unmatched} skipped"
        else:
            suffix = "  ✓"
        self._hdr.setText(f"{arrow}  {self._short_name.upper()}{suffix}")

    def row_list(self) -> List[_GroupMappingRow]:
        return self._rows

    def reload_templates(self, templates: dict) -> None:
        for row in self._rows:
            row.reload_templates(templates)
        self._refresh_header()


# ---------------------------------------------------------------------------
# MappingPanel (public API)
# ---------------------------------------------------------------------------

class MappingPanel(QFrame):
    """
    Middle panel in Bulk Run: shows assignment group → template mappings.

    Public API:
        on_course_toggled(course_id, course_name, checked, api)
        get_group_overrides() -> dict   {group_id: template_settings_dict}
        get_unmatched_count() -> int
        reload_templates()
    """

    status_changed = Signal()

    def __init__(self, api=None, parent=None):
        super().__init__(parent)
        self._api = api
        self._sections: Dict[int, _CourseMappingSection] = {}
        self._groups_cache: Dict[int, list] = {}   # course_id → groups
        self._active_courses: Dict[int, str] = {}  # course_id → course_name
        self._pending_fetch: set = set()           # course_ids queued for batch fetch
        self._worker = None
        self._zombie_workers: list = []            # old workers kept alive until finished

        self._templates = {}
        self._mappings = {}
        self._reload_data()

        self.setObjectName("mappingPane")
        self.setStyleSheet(_PANE_QSS)
        self._build_ui()

    def _reload_data(self) -> None:
        from assignment_templates import load_templates, load_mappings
        self._templates = load_templates()
        self._mappings = load_mappings()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        lo = QVBoxLayout(self)
        lo.setContentsMargins(12, 12, 12, 12)
        lo.setSpacing(SPACING_SM)

        # ── Header ────────────────────────────────────────────────────
        hdr_row = QHBoxLayout()
        hdr_lbl = QLabel("ASSIGNMENT MAPPINGS")
        hdr_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        hdr_row.addWidget(hdr_lbl)
        hdr_row.addStretch()

        self._manage_btn = QPushButton("Manage Templates")
        make_secondary_button(self._manage_btn)
        self._manage_btn.clicked.connect(self._open_template_editor)
        hdr_row.addWidget(self._manage_btn)
        lo.addLayout(hdr_row)

        # ── Status line ───────────────────────────────────────────────
        self._status_lbl = QLabel("Select courses to load assignment mappings.")
        self._status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: 10px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._status_lbl)

        lo.addWidget(self._hsep())

        # ── Scroll area ───────────────────────────────────────────────
        self._scroll = QScrollArea()
        self._scroll.setStyleSheet(_SCROLL_QSS)
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {BG_INSET};")
        self._content_lo = QVBoxLayout(self._content)
        self._content_lo.setContentsMargins(0, 2, 0, 4)
        self._content_lo.setSpacing(0)
        self._content_lo.addStretch()
        self._scroll.setWidget(self._content)
        lo.addWidget(self._scroll, 1)

        # ── Hint ──────────────────────────────────────────────────────
        hint = QLabel("Auto-matched by keyword  ·  — = will be skipped")
        hint.setStyleSheet(
            f"color: {PHOSPHOR_GLOW}; font-size: 10px;"
            f" background: transparent; border: none; padding-top: 4px;"
        )
        lo.addWidget(hint)

    @staticmethod
    def _hsep() -> QFrame:
        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: {BORDER_DARK}; border: none;")
        return sep

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def on_course_toggled(
        self, course_id: int, course_name: str, checked: bool, api
    ) -> None:
        """Called when a course checkbox changes in the left panel."""
        self._api = api
        if checked:
            self._active_courses[course_id] = course_name
            self._ensure_section(course_id, course_name)
            if course_id not in self._groups_cache:
                # Queue for batch fetch — avoids one-worker-per-course when
                # multiple courses are toggled rapidly (e.g. "Select All").
                self._pending_fetch.add(course_id)
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, self._flush_fetch)
            else:
                # Already cached — populate immediately
                section = self._sections[course_id]
                section.populate(
                    self._groups_cache[course_id], self._templates, self._mappings
                )
        else:
            self._active_courses.pop(course_id, None)
            self._pending_fetch.discard(course_id)
            self._remove_section(course_id)

        self._refresh_status()

    def get_group_overrides(self) -> dict:
        """
        Returns {group_id: template_settings_dict} for all assigned groups
        across all visible courses.  Used by BulkRunWorker.
        """
        overrides: dict = {}
        for section in self._sections.values():
            for row in section.row_list():
                tname = row.current_template_name()
                if tname and tname in self._templates:
                    overrides[row.group_id()] = dict(self._templates[tname])
        return overrides

    def get_unmatched_count(self) -> int:
        total = 0
        for section in self._sections.values():
            total += sum(1 for r in section.row_list() if not r.is_assigned())
        return total

    def preload_groups(self, course_entries: list) -> None:
        """
        Fetch assignment groups for all courses upfront (call when page opens).

        course_entries: [(course_id, course_name), ...]

        Results land in _groups_cache.  Sections that already exist get
        populated immediately; sections created later (on checkbox toggle)
        will use the cache and require no network call.
        """
        if not self._api:
            return
        uncached = [
            (cid, cname) for cid, cname in course_entries
            if cid not in self._groups_cache
        ]
        if uncached:
            self._fetch_groups(uncached)

    def reload_templates(self) -> None:
        """Refresh from storage — call after template editor closes."""
        self._reload_data()
        for section in self._sections.values():
            section.reload_templates(self._templates)
        self._refresh_status()

    def clear(self) -> None:
        """Remove all sections (called on full course refresh)."""
        self._stop_worker()
        self._pending_fetch.clear()
        for cid in list(self._sections.keys()):
            self._remove_section(cid)
        self._active_courses.clear()
        self._groups_cache.clear()
        self._refresh_status()

    def stop_and_wait(self) -> None:
        """Cancel in-flight fetch and wait for thread to exit (call before GC)."""
        self._stop_worker()

    def _flush_fetch(self) -> None:
        """Fetch groups for all pending courses in one batched worker call."""
        if not self._pending_fetch:
            return
        pending = set(self._pending_fetch)
        self._pending_fetch.clear()

        # Courses that arrived via preload while they were queued — populate now
        now_cached = {cid for cid in pending if cid in self._groups_cache}
        for cid in now_cached:
            sec = self._sections.get(cid)
            if sec and not sec._populated:
                sec.populate(self._groups_cache[cid], self._templates, self._mappings)

        entries = [
            (cid, self._active_courses[cid])
            for cid in (pending - now_cached)
            if cid in self._active_courses
        ]
        if entries:
            self._fetch_groups(entries)

    def _stop_worker(self) -> None:
        if self._worker:
            old = self._worker
            old.cancel()
            # Keep a reference until the thread finishes so Qt doesn't
            # destroy the QThread while the OS thread is still running.
            self._zombie_workers.append(old)
            old.finished.connect(
                lambda w=old: self._zombie_workers.remove(w)
                if w in self._zombie_workers else None
            )
        self._worker = None

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _ensure_section(self, course_id: int, course_name: str) -> "_CourseMappingSection":
        if course_id not in self._sections:
            sec = _CourseMappingSection(course_id, course_name)
            sec.any_changed.connect(self._refresh_status)
            self._sections[course_id] = sec
            # Insert before the trailing stretch
            count = self._content_lo.count()
            self._content_lo.insertWidget(count - 1, sec)
        return self._sections[course_id]

    def _remove_section(self, course_id: int) -> None:
        sec = self._sections.pop(course_id, None)
        if sec:
            self._content_lo.removeWidget(sec)
            sec.deleteLater()

    def _fetch_groups(self, course_entries: list) -> None:
        """Start a background fetch for the given [(course_id, course_name)] list."""
        # If a worker is already running, re-queue these entries and let the
        # current worker finish — cancelling it would drop already-in-flight
        # course data and leave sections permanently empty.
        if self._worker and self._worker.isRunning():
            for cid, cname in course_entries:
                if cid in self._active_courses:
                    self._pending_fetch.add(cid)
            return

        from gui.workers import LoadGroupsForCoursesWorker

        for cid, cname in course_entries:
            sec = self._sections.get(cid)
            if sec:
                sec.set_loading()

        self._worker = LoadGroupsForCoursesWorker(self._api, course_entries)
        self._worker.groups_loaded.connect(self._on_groups_loaded)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_all_done(self) -> None:
        self._refresh_status()
        # Flush any courses that were queued while the worker was running
        if self._pending_fetch:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, self._flush_fetch)

    def _on_groups_loaded(self, course_id: int, course_name: str, groups: list) -> None:
        self._groups_cache[course_id] = groups
        sec = self._sections.get(course_id)
        if sec:
            sec.populate(groups, self._templates, self._mappings)
        self._refresh_status()

    def _refresh_status(self) -> None:
        total_groups = sum(
            len(s.row_list()) for s in self._sections.values()
        )
        unmatched = self.get_unmatched_count()
        n_courses = len(self._sections)

        if n_courses == 0:
            self._status_lbl.setText(
                "Select courses to load assignment mappings."
            )
            self._status_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px;"
                f" background: transparent; border: none;"
            )
        elif total_groups == 0:
            self._status_lbl.setText("Loading groups…")
            self._status_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px;"
                f" background: transparent; border: none;"
            )
        elif unmatched == 0:
            self._status_lbl.setText(
                f"✓  All {total_groups} groups mapped across {n_courses} course(s)"
            )
            self._status_lbl.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: 10px; font-weight: 600;"
                f" background: transparent; border: none;"
            )
        else:
            self._status_lbl.setText(
                f"{total_groups - unmatched} groups will be graded  ·  "
                f"{unmatched} skipped"
            )
            self._status_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: 10px;"
                f" background: transparent; border: none;"
            )

        self.status_changed.emit()

    def _open_template_editor(self) -> None:
        from gui.dialogs.template_editor_dialog import TemplateEditorDialog
        dlg = TemplateEditorDialog(parent=self)
        dlg.exec()
        self.reload_templates()
