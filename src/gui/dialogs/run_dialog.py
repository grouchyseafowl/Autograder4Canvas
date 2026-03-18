"""
Run Autograder dialog — CRT amber terminal redesign.

Two-page QStackedWidget:
  Page 0 — CONFIG:    grading scope, options, switches, run button
  Page 1 — PROGRESS:  phosphor progress bar, live log, stop/close
"""
import datetime
from pathlib import Path
from typing import List

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QComboBox,
    QFrame, QSizePolicy, QWidget, QStackedWidget,
)
from PySide6.QtCore import Qt, QRect, QSize, Signal
from PySide6.QtGui import (
    QColor, QFont, QFontMetrics, QPainter, QPainterPath,
    QBrush, QLinearGradient, QPen, QRadialGradient,
)

from gui.styles import (
    px,
    BG_VOID, BG_INSET,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    BORDER_DARK, BORDER_AMBER,
    make_run_button, make_monospace_textedit,
    make_content_pane, make_section_label, make_h_rule,
    apply_phosphor_glow,
)
from gui.widgets.switch_toggle import SwitchToggle
from gui.widgets.option_rocker import OptionRocker
from gui.widgets.segmented_toggle import SegmentedToggle
from assignment_templates import aic_config_from_mode, get_aic_config, load_templates, SYSTEM_DEFAULT_NAMES


# ---------------------------------------------------------------------------
# CRT Phosphor Progress Bar
# ---------------------------------------------------------------------------

class _PhosphorProgressBar(QWidget):
    """Amber-phosphor CRT progress bar — QPainter-based, no native widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._maximum = 100
        self._format = "%p%"
        self.setFixedHeight(22)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def setValue(self, v: int) -> None:
        self._value = max(0, min(v, self._maximum))
        self.update()

    def setMaximum(self, m: int) -> None:
        self._maximum = max(1, m)
        self.update()

    def setFormat(self, fmt: str) -> None:
        self._format = fmt
        self.update()

    def _pct(self) -> float:
        return self._value / self._maximum if self._maximum > 0 else 0.0

    def paintEvent(self, _) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        r = h / 2

        track_path = QPainterPath()
        track_path.addRoundedRect(0.5, 0.5, w - 1, h - 1, r, r)
        p.fillPath(track_path, QColor(BG_INSET))
        p.setPen(QColor(BORDER_DARK))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(track_path)

        pct = self._pct()
        fill_w = max(0.0, (w - 2) * pct)
        if fill_w > 1:
            fill_path = QPainterPath()
            fill_path.addRoundedRect(1, 1, fill_w, h - 2, r - 0.5, r - 0.5)

            grad = QLinearGradient(0, 0, fill_w + 1, 0)
            grad.setColorAt(0.00, QColor(90, 60, 8, 180))
            grad.setColorAt(0.55, QColor(160, 100, 15, 200))
            grad.setColorAt(0.82, QColor(210, 140, 22, 220))
            grad.setColorAt(1.00, QColor(240, 168, 48, 255))
            p.fillPath(fill_path, QBrush(grad))

            if fill_w > 6:
                edge_x = 1 + fill_w
                p.setPen(Qt.PenStyle.NoPen)
                glow = QLinearGradient(edge_x - 5, 0, edge_x + 3, 0)
                glow.setColorAt(0.0, QColor(240, 168, 48, 0))
                glow.setColorAt(0.6, QColor(240, 168, 48, 110))
                glow.setColorAt(1.0, QColor(255, 200, 80, 0))
                p.setBrush(QBrush(glow))
                p.drawRect(int(edge_x - 5), 1, 8, h - 2)

        pct_int = int(pct * 100)
        text = (self._format
                .replace("%p", str(pct_int))
                .replace("%v", str(self._value))
                .replace("%m", str(self._maximum)))
        p.setPen(QColor(PHOSPHOR_HOT) if pct > 0.15 else QColor(PHOSPHOR_DIM))
        font = p.font()
        font.setPixelSize(10)
        p.setFont(font)
        p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)
        p.end()


# _SegmentedToggle: alias for the shared widget (kept for call-site compat)
_SegmentedToggle = SegmentedToggle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scanline_sep() -> QFrame:
    """Amber-phosphor scanline separator — matches setup_dialog divider style."""
    sep = QFrame()
    sep.setFixedHeight(2)
    sep.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(240,168,48, 0),
                stop:0.15 rgba(240,168,48, 0.25),
                stop:0.40 rgba(240,168,48, 0.70),
                stop:0.50 rgba(255,200,80, 1.00),
                stop:0.60 rgba(240,168,48, 0.70),
                stop:0.85 rgba(240,168,48, 0.25),
                stop:1.00 rgba(240,168,48, 0));
            border: none;
        }
    """)
    return sep


def _classify_selection(selected_items: list) -> tuple:
    """Return (n_discussions, n_ci, df_grading_type).

    df_grading_type is read from Canvas assignment data:
      "points"               → letter-grade / points mode
      "complete_incomplete"  → pass/fail mode
    """
    n_df = 0
    has_points = False
    for a in selected_items:
        if "discussion_topic" in (a.get("submission_types") or []):
            n_df += 1
            if a.get("grading_type") == "points":
                has_points = True
    df_gt = "points" if has_points else "complete_incomplete"
    return n_df, len(selected_items) - n_df, df_gt


# ---------------------------------------------------------------------------
# Run Dialog
# ---------------------------------------------------------------------------

class RunDialog(QDialog):
    """Modal dialog to configure and execute a grading job.

    Parameters
    ----------
    selections : list of (course_name, course_id, [assignment_dicts])
        One entry per course. Courses are run sequentially.
    """

    def __init__(self, api,
                 selections: List[tuple],
                 term_id: int, demo_mode: bool = False, parent=None):
        super().__init__(parent)
        self._api        = api
        self._selections = selections   # [(course_name, course_id, [items]), ...]
        self._term_id    = term_id
        self._demo_mode  = demo_mode
        self._worker     = None
        self._run_queue: List[tuple] = []

        # Classify the flat union of all assignments for the config pane
        all_items = [a for _, _, items in selections for a in items]
        self._n_df, self._n_ci, self._df_grading_type = _classify_selection(all_items)

        self.setWindowTitle("Run Autograder4Canvas")
        self.setMinimumWidth(540)
        self._setup_ui()
        self._load_settings_defaults()
        self._update_visibility()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        self._stack.addWidget(self._build_config_page())
        self._stack.addWidget(self._build_progress_page())
        self._stack.setCurrentIndex(0)

    # ── Page 0: Config ──────────────────────────────────────────────────────

    def _build_config_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("configPage")
        page.setStyleSheet(f"QWidget#configPage {{ background: {BG_VOID}; }}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        # ── Header ──────────────────────────────────────────────────────────
        n_courses = len(self._selections)
        all_items = [a for _, _, items in self._selections for a in items]
        n_total   = len(all_items)

        if n_courses == 1:
            title_text = self._selections[0][0].upper()
        else:
            title_text = f"{n_total} ASSIGNMENTS  ·  {n_courses} COURSES"

        title_lbl = QLabel(title_text)
        title_lbl.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        apply_phosphor_glow(title_lbl, color=PHOSPHOR_HOT, blur=10, strength=0.40)
        layout.addWidget(title_lbl)

        layout.addSpacing(4)

        # Per-course assignment summary
        sub_lines = []
        for cname, _, items in self._selections:
            names = ", ".join(i["name"] for i in items[:3])
            if len(items) > 3:
                names += f"  +{len(items) - 3} more"
            prefix = f"{cname}:  " if n_courses > 1 else ""
            sub_lines.append(f"{prefix}{names}")

        sub_lbl = QLabel("\n".join(sub_lines))
        sub_lbl.setWordWrap(True)
        sub_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        layout.addWidget(sub_lbl)

        layout.addSpacing(12)
        layout.addWidget(_make_scanline_sep())
        layout.addSpacing(12)

        # ── Content panes ───────────────────────────────────────────────────
        layout.addWidget(self._build_scope_pane())
        layout.addSpacing(8)
        layout.addWidget(self._build_aic_pane())

        layout.addStretch()

        # ── Button row ──────────────────────────────────────────────────────
        layout.addSpacing(12)
        layout.addWidget(_make_scanline_sep())
        layout.addSpacing(8)

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(10)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        btn_row.addStretch()

        n_total = sum(len(items) for _, _, items in self._selections)
        n_courses = len(self._selections)
        if n_courses > 1:
            run_label = f"▶  Run All  ({n_total})"
        else:
            run_label = "▶  Run Autograder"
        self._run_btn = QPushButton(run_label)
        self._run_btn.clicked.connect(self._on_run)
        make_run_button(self._run_btn)
        btn_row.addWidget(self._run_btn)

        layout.addLayout(btn_row)
        return page

    def _build_scope_pane(self) -> QFrame:
        pane = make_content_pane("scopePane")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(6)

        # ── Scope summary ────────────────────────────────────────────────────
        lo.addWidget(make_section_label("Grading Scope"))

        parts = []
        if self._n_df > 0:
            parts.append(f"{self._n_df} Discussion Forum{'s' if self._n_df != 1 else ''}")
        if self._n_ci > 0:
            parts.append(f"{self._n_ci} Complete / Incomplete")
        scope_lbl = QLabel("  " + "  ·  ".join(parts))
        scope_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px; background: transparent; border: none;"
        )
        lo.addWidget(scope_lbl)

        if self._n_df > 0:
            if self._df_grading_type == "points":
                gt_text = "ᵢ  Discussion grading: Points / Letter grades"
            else:
                gt_text = "ᵢ  Discussion grading: Complete / Incomplete"
            canvas_gt_lbl = QLabel(gt_text)
            canvas_gt_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent; border: none;"
            )
            lo.addWidget(canvas_gt_lbl)

        self._mixed_warn_lbl = QLabel(
            "\u26a0  Mixed selection \u2014 each type will run its own script"
            " with the parameters configured below."
        )
        self._mixed_warn_lbl.setWordWrap(True)
        self._mixed_warn_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
            f" background: transparent; border: none; padding-top: 2px;"
        )
        lo.addWidget(self._mixed_warn_lbl)

        # ── Options ──────────────────────────────────────────────────────────
        lo.addWidget(make_h_rule())
        lo.addWidget(make_section_label("Options"))
        lo.addSpacing(4)

        self._mark_incomplete_sw = OptionRocker(
            "Grade absent work as Incomplete",
            "Leave absent work ungraded",
            value=False,
        )
        self._mark_incomplete_sw.setToolTip(
            "Grade as Incomplete: assign Incomplete to students who never submitted.\n"
            "Leave ungraded: skip absent students — do not post a grade."
        )
        self._mark_incomplete_sw.changed.connect(
            lambda v: self._save_setting("grade_missing_as_incomplete", v))

        self._preserve_grades_sw = OptionRocker(
            "Grade new submissions only",
            "Regrade from scratch",
            value=True,
        )
        self._preserve_grades_sw.setToolTip(
            "New submissions only: grade work Canvas marks as ungraded (including\n"
            "  re-submissions after an Incomplete). Existing grades are untouched.\n"
            "Regrade from scratch: overwrite all grades as if none had been posted."
        )
        self._preserve_grades_sw.changed.connect(
            lambda v: self._save_setting("preserve_existing_grades", v))

        rocker_col = QVBoxLayout()
        rocker_col.setContentsMargins(0, 0, 0, 0)
        rocker_col.setSpacing(6)
        rocker_col.addWidget(self._mark_incomplete_sw)
        rocker_col.addWidget(self._preserve_grades_sw)
        lo.addLayout(rocker_col)

        return pane

    def _build_aic_pane(self) -> QFrame:
        pane = make_content_pane("aicPane")
        lo = QVBoxLayout(pane)
        lo.setContentsMargins(20, 16, 20, 16)
        lo.setSpacing(6)

        lo.addWidget(make_section_label("Academic Integrity Check"))
        lo.addSpacing(4)

        self._aic_seg = _SegmentedToggle(
            ("Grade only",   "grade_only"),
            ("Grade + AIC",  "grade_and_aic"),
            ("AIC only",     "aic_only"),
            accent="rose",
        )
        self._aic_seg.set_mode("grade_and_aic")
        self._aic_seg.mode_changed.connect(lambda m: (
            self._update_visibility(),
            self._save_setting("aic_mode_default", m),
        ))
        aic_row = QHBoxLayout()
        aic_row.setContentsMargins(0, 0, 0, 0)
        aic_row.addWidget(self._aic_seg)
        aic_row.addStretch()
        lo.addLayout(aic_row)

        lo.addSpacing(4)
        lo.addWidget(make_h_rule())
        lo.addSpacing(2)

        lo.addWidget(make_section_label("Assignment Type  —  for AIC only"))

        note = QLabel(
            "Tells the AIC which marker weight profile to apply."
            "  Doesn't affect grading."
        )
        note.setWordWrap(True)
        note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent; border: none;"
        )
        lo.addWidget(note)

        type_row = QHBoxLayout()
        type_row.setContentsMargins(0, 4, 0, 0)
        type_row.setSpacing(8)

        self._type_combo = QComboBox()
        self._populate_type_combo()
        type_row.addWidget(self._type_combo, 1)

        edit_types_btn = QPushButton("Edit Types")
        edit_types_btn.setToolTip("Open the Assignment Type editor")
        edit_types_btn.clicked.connect(self._open_type_editor)
        type_row.addWidget(edit_types_btn)
        lo.addLayout(type_row)

        self._aic_type_note = QLabel(
            "ᵢ Affects AIC marker weights only"
        )
        self._aic_type_note.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; background: transparent; border: none;"
        )
        lo.addWidget(self._aic_type_note)

        return pane

    # ── Page 1: Progress ─────────────────────────────────────────────────────

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        page.setObjectName("progressPage")
        page.setStyleSheet(f"QWidget#progressPage {{ background: {BG_VOID}; }}")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(10)

        self._progress_heading = QLabel("RUNNING")
        self._progress_heading.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        layout.addWidget(self._progress_heading)

        self._progress_status = QLabel("Preparing…")
        self._progress_status.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; background: transparent; border: none;"
        )
        layout.addWidget(self._progress_status)

        self._progress_bar = _PhosphorProgressBar()
        layout.addWidget(self._progress_bar)

        log_pane = make_content_pane("logPane")
        log_inner = QVBoxLayout(log_pane)
        log_inner.setContentsMargins(4, 4, 4, 4)
        self._log_output = QTextEdit()
        self._log_output.setReadOnly(True)
        make_monospace_textedit(self._log_output)
        self._log_output.setMinimumHeight(240)
        log_inner.addWidget(self._log_output)
        layout.addWidget(log_pane, 1)

        layout.addWidget(_make_scanline_sep())

        btn_row = QHBoxLayout()
        btn_row.setContentsMargins(0, 6, 0, 0)
        btn_row.setSpacing(10)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.clicked.connect(self._on_stop)
        btn_row.addWidget(self._stop_btn)

        self._open_btn = QPushButton("Open Output")
        self._open_btn.clicked.connect(self._on_open_output)
        btn_row.addWidget(self._open_btn)

        btn_row.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.accept)
        self._close_btn.setEnabled(False)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)
        return page

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------

    def _load_settings_defaults(self) -> None:
        try:
            from settings import load_settings
            s = load_settings()
            self._mark_incomplete_sw.setChecked(
                bool(s.get("grade_missing_as_incomplete", False)))
            self._preserve_grades_sw.setChecked(
                bool(s.get("preserve_existing_grades", True)))
            aic_default = s.get("aic_mode_default", "grade_and_aic")
            self._aic_seg.set_mode(aic_default)
        except Exception:
            self._preserve_grades_sw.setChecked(True)

    def _save_setting(self, key: str, value) -> None:
        try:
            from settings import load_settings, save_settings
            s = load_settings()
            s[key] = value
            save_settings(s)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Visibility logic
    # ------------------------------------------------------------------

    def _update_visibility(self) -> None:
        has_df   = self._n_df > 0
        has_ci   = self._n_ci > 0
        aic_mode = self._aic_seg.mode
        aic_on   = aic_mode != "grade_only"

        is_mixed = has_ci and has_df
        self._mixed_warn_lbl.setVisible(is_mixed)
        self._aic_type_note.setVisible(aic_on)

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    def _on_run(self) -> None:
        self._run_queue = list(self._selections)
        n_total = sum(len(items) for _, _, items in self._selections)

        self._stack.setCurrentIndex(1)
        self._progress_heading.setText("RUNNING")
        self._progress_status.setText("Starting…")
        self._progress_bar.setValue(0)
        self._progress_bar.setMaximum(max(1, n_total))
        self._stop_btn.setEnabled(True)
        self._close_btn.setEnabled(False)
        self._log_output.clear()
        self._run_next_course()

    def _run_next_course(self) -> None:
        if not self._run_queue:
            self._on_all_done()
            return

        course_name, course_id, selected = self._run_queue.pop(0)
        n_courses   = len(self._selections)
        done_count  = n_courses - len(self._run_queue) - 1
        if n_courses > 1:
            self._progress_status.setText(
                f"Running {course_name}  ({done_count + 1} of {n_courses})…"
            )
        else:
            self._progress_status.setText("Starting…")

        aic_mode      = self._aic_seg.mode
        aic_only      = aic_mode == "aic_only"
        grade_only    = aic_mode == "grade_only"
        effective_aic = not grade_only

        n_df, n_ci, df_gt = _classify_selection(selected)
        if aic_only:
            atype = "aic"
        elif n_df > 0 and n_ci > 0:
            atype = "mixed"
        elif n_df > 0:
            atype = "discussion_forum"
        else:
            atype = "complete_incomplete"

        mode_settings = self._resolve_mode_settings()

        if self._demo_mode:
            from gui.workers import DemoRunWorker
            self._worker = DemoRunWorker(selected_items=selected)
        else:
            from gui.workers import RunWorker
            self._worker = RunWorker(
                api=self._api,
                course_id=course_id,
                course_name=course_name,
                selected_assignments=selected,
                assignment_type=atype,
                min_word_count=mode_settings["min_word_count"],
                post_min_words=mode_settings["post_min_words"],
                reply_min_words=mode_settings["reply_min_words"],
                grading_type=df_gt,
                post_points=1.0,
                reply_points=0.5,
                min_posts=1,
                min_replies=2,
                run_adc=effective_aic,
                preserve_grades=self._preserve_grades_sw.isChecked(),
                mark_incomplete=self._mark_incomplete_sw.isChecked(),
                dry_run=False,
                mode_settings=mode_settings,
            )
        self._worker.log_line.connect(self._append_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_course_finished)
        self._worker.start()

    def _on_course_finished(self, success: bool, message: str) -> None:
        icon = "Done" if success else "Error"
        self._append_log(f"\n[{icon}] {message}")
        if self._run_queue:
            self._run_next_course()
        else:
            self._on_all_done()

    def _on_all_done(self) -> None:
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)
        n_total = sum(len(items) for _, _, items in self._selections)
        self._progress_bar.setValue(self._progress_bar._maximum)
        self._progress_heading.setText("COMPLETE")
        self._progress_status.setText(f"Done — {n_total} assignment{'s' if n_total != 1 else ''} graded.")

    def _on_progress(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)
        pct = int(done / total * 100) if total > 0 else 0
        if done < total:
            self._progress_status.setText(
                f"Grading {done} of {total} students…  ({pct}%)"
            )
        else:
            self._progress_status.setText(f"Finishing up…  ({pct}%)")

    def _append_log(self, line: str) -> None:
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self._log_output.append(f"[{ts}] {line}")
        sb = self._log_output.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _on_stop(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("\n[Stopped] Cancellation requested.")
        self._stop_btn.setEnabled(False)
        self._close_btn.setEnabled(True)

    def _on_open_output(self) -> None:
        try:
            from autograder_utils import open_folder, get_output_base_dir
            open_folder(get_output_base_dir())
        except Exception:
            pass

    def _resolve_mode_settings(self) -> dict:
        """Return aic_mode, aic_config, and word counts from the selected template."""
        tmpl_name = self._type_combo.currentData()
        if not tmpl_name or tmpl_name == "auto":
            tmpl = {}
            base = {"aic_mode": "auto", "aic_config": aic_config_from_mode("auto")}
        else:
            tmpl = load_templates().get(tmpl_name, {})
            base = {
                "aic_mode":   tmpl.get("aic_mode", "auto"),
                "aic_config": get_aic_config(tmpl),
            }
        return {
            **base,
            "min_word_count":  tmpl.get("min_word_count", 200),
            "post_min_words":  tmpl.get("post_min_words", 200),
            "reply_min_words": tmpl.get("reply_min_words", 50),
        }

    def _populate_type_combo(self) -> None:
        """Rebuild the assignment-type combo from the current template store."""
        current = self._type_combo.currentData()
        self._type_combo.clear()
        self._type_combo.addItem("Auto-detect", "auto")

        templates = load_templates()
        _mode_order = ["notes", "discussion", "draft", "personal", "essay", "lab"]

        def _sort_key(name: str) -> int:
            mode = templates[name].get("aic_mode", "z")
            try:
                return _mode_order.index(mode)
            except ValueError:
                return 99

        sys_names = sorted(
            (n for n, t in templates.items() if t.get("is_system_default")),
            key=_sort_key,
        )
        user_names = sorted(
            n for n, t in templates.items() if not t.get("is_system_default")
        )
        for name in sys_names:
            self._type_combo.addItem(name, name)
        if user_names:
            self._type_combo.insertSeparator(self._type_combo.count())
            for name in user_names:
                self._type_combo.addItem(name, name)

        # Restore previous selection if it still exists
        if current:
            idx = self._type_combo.findData(current)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)

    def _open_type_editor(self) -> None:
        try:
            from gui.dialogs.template_editor_dialog import TemplateEditorDialog
            dlg = TemplateEditorDialog(parent=self)
            dlg.exec()
            self._populate_type_combo()   # refresh after edits
        except Exception as exc:
            from gui.dialogs.message_dialog import show_warning
            show_warning(self, "Not Available", str(exc))
