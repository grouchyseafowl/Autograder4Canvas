"""
RunAICDialog — Run the Academic Integrity Check on a single assignment.

Lets the teacher pick any course + assignment and run the check directly,
without going through the full grading workflow. Results are saved to RunStore
and immediately visible in the Prior Runs panel.
"""

import io
import sys
from typing import List, Dict, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QFrame, QTextEdit, QSizePolicy, QCheckBox,
)

from gui.widgets.crt_combo import CRTComboBox
from gui.styles import (
    px, combo_qss,
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT, TERM_GREEN, BURN_RED, WARN_PINK,
    BG_VOID, BG_CARD, BG_INSET,
    BORDER_DARK, BORDER_AMBER, CARD_GRADIENT,
    make_run_button, make_secondary_button, make_monospace_textedit,
)

_COMBO_QSS = combo_qss()

_EDU_LEVEL_OPTIONS = [
    ("community_college", "Community College  (default)"),
    ("high_school",       "High School"),
    ("four_year",         "Four-Year College / Liberal Arts"),
    ("university",        "Research University"),
    ("online",            "Online / Distance Learning"),
]

_POPULATION_LEVEL_OPTIONS = [
    ("none",     "None  (typical for this institution type)"),
    ("low",      "Low  (slightly above average)"),
    ("moderate", "Moderate  (significantly above average)"),
    ("high",     "High  (major defining feature)"),
]


# ──────────────────────────────────────────────────────────────────────────────
# Worker
# ──────────────────────────────────────────────────────────────────────────────

class _AICWorker(QThread):
    """Runs analyze_assignment() in a thread; emits stdout lines as signals."""

    log_line  = Signal(str)
    finished  = Signal(int, int)   # (analyzed_count, smoking_gun_count)
    error     = Signal(str)

    def __init__(self, course_id: int, assignment_id: int,
                 education_level: str, esl_level: str,
                 first_gen_level: str, neurodivergent_aware: bool,
                 course_name: str = "", parent=None):
        super().__init__(parent)
        self._course_id = course_id
        self._assignment_id = assignment_id
        self._education_level = education_level
        self._esl_level = esl_level
        self._first_gen_level = first_gen_level
        self._neurodivergent_aware = neurodivergent_aware
        self._course_name = course_name

    def run(self) -> None:
        # Capture print() output and relay as Qt signals
        buf = _SignalStream(self.log_line)
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            from Academic_Dishonesty_Check_v2 import analyze_assignment
            # Compose per-marker weights from dialog settings
            composed_weights = None
            try:
                from modules.weight_composer import compose_weights
                composed_weights = compose_weights(
                    education_level=self._education_level,
                    esl_level=self._esl_level,
                    first_gen_level=self._first_gen_level,
                    neurodivergent_aware=self._neurodivergent_aware,
                )
            except Exception as e:
                self.log_line.emit(f"⚠ Weight composer unavailable, using legacy path: {e}")

            results, report_path = analyze_assignment(
                course_id=self._course_id,
                assignment_id=self._assignment_id,
                context_profile=self._education_level,
                composed_weights=composed_weights,
                course_name=self._course_name,
            )
            smoking_guns = sum(1 for r in results if r.smoking_gun)
            if report_path:
                self.log_line.emit(f"\nReport saved to: {report_path}")
            self.finished.emit(len(results), smoking_guns)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            sys.stdout = old_stdout


class _SignalStream:
    """Wraps a Signal(str) as a file-like object for print() redirection."""

    def __init__(self, signal: Signal):
        self._signal = signal
        self._buf = ""

    def write(self, text: str) -> None:
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            self._signal.emit(line)

    def flush(self) -> None:
        if self._buf:
            self._signal.emit(self._buf)
            self._buf = ""


# ──────────────────────────────────────────────────────────────────────────────
# Dialog
# ──────────────────────────────────────────────────────────────────────────────

class RunAICDialog(QDialog):
    """Dialog to run the Academic Integrity Check on a selected assignment."""

    run_completed = Signal()  # emitted on success so Prior Runs panel can refresh

    def __init__(self, api, parent=None):
        super().__init__(parent)
        self._api = api
        self._courses: List[Dict] = []     # flat list of {id, name}
        self._assignments: List[Dict] = [] # flat list of {id, name}
        self._worker: Optional[_AICWorker] = None

        self.setWindowTitle("Run Engagement Analysis")
        self.setMinimumSize(580, 520)
        self.resize(620, 580)
        self._build_ui()
        self._load_courses()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # Title bar
        title_bar = QFrame()
        title_bar.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER_AMBER};
            }}
        """)
        tb = QVBoxLayout(title_bar)
        tb.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        tb.setSpacing(4)
        title = QLabel("RUN ACADEMIC INTEGRITY CHECK")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; font-weight: bold; letter-spacing: 2px;")
        tb.addWidget(title)
        sub = QLabel(
            "Analyzes submissions for integrity patterns. "
            "Results save to the Prior Runs dashboard automatically."
        )
        sub.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;")
        sub.setWordWrap(True)
        tb.addWidget(sub)
        root.addWidget(title_bar)

        # Config section
        config_frame = QFrame()
        config_frame.setStyleSheet(f"QFrame {{ background: {BG_VOID}; border: none; }}")
        cf = QVBoxLayout(config_frame)
        cf.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_SM)
        cf.setSpacing(SPACING_SM)

        # Course row
        course_row = QHBoxLayout()
        course_lbl = QLabel("Course:")
        course_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; min-width: 80px;")
        course_row.addWidget(course_lbl)
        self._course_combo = CRTComboBox()
        self._course_combo.addItem("Loading courses…")
        self._course_combo.setEnabled(False)
        self._course_combo.currentIndexChanged.connect(self._on_course_changed)
        course_row.addWidget(self._course_combo, 1)
        cf.addLayout(course_row)

        # Assignment row
        assign_row = QHBoxLayout()
        assign_lbl = QLabel("Assignment:")
        assign_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; min-width: 80px;")
        assign_row.addWidget(assign_lbl)
        self._assign_combo = CRTComboBox()
        self._assign_combo.addItem("Select a course first")
        self._assign_combo.setEnabled(False)
        assign_row.addWidget(self._assign_combo, 1)
        cf.addLayout(assign_row)

        # Education level row
        edu_row = QHBoxLayout()
        edu_lbl = QLabel("Institution:")
        edu_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; min-width: 80px;")
        edu_row.addWidget(edu_lbl)
        self._edu_combo = CRTComboBox()
        for pid, plabel in _EDU_LEVEL_OPTIONS:
            self._edu_combo.addItem(plabel, pid)
        edu_row.addWidget(self._edu_combo, 1)
        cf.addLayout(edu_row)

        # Population overlays — compact 2-column grid
        pop_row1 = QHBoxLayout()
        esl_lbl = QLabel("ESL Population:")
        esl_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; min-width: 80px;")
        pop_row1.addWidget(esl_lbl)
        self._esl_combo = CRTComboBox()
        for pid, plabel in _POPULATION_LEVEL_OPTIONS:
            self._esl_combo.addItem(plabel, pid)
        pop_row1.addWidget(self._esl_combo, 1)
        cf.addLayout(pop_row1)

        pop_row2 = QHBoxLayout()
        fg_lbl = QLabel("First-Gen Pop.:")
        fg_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; min-width: 80px;")
        pop_row2.addWidget(fg_lbl)
        self._first_gen_combo = CRTComboBox()
        for pid, plabel in _POPULATION_LEVEL_OPTIONS:
            self._first_gen_combo.addItem(plabel, pid)
        pop_row2.addWidget(self._first_gen_combo, 1)
        cf.addLayout(pop_row2)

        nd_row = QHBoxLayout()
        nd_row.addSpacing(88)  # align with combo boxes
        self._nd_check = QCheckBox("Neurodivergent-Aware Mode")
        self._nd_check.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
        )
        nd_row.addWidget(self._nd_check)
        nd_row.addStretch()
        cf.addLayout(nd_row)

        # Ethics note
        ethics = QLabel(
            "Results are patterns for conversation — not verdicts. "
            "Review flagged submissions before any action."
        )
        ethics.setWordWrap(True)
        ethics.setStyleSheet(f"color: {ROSE_ACCENT}; font-size: {px(11)}px; padding-top: 4px;")
        cf.addWidget(ethics)

        root.addWidget(config_frame)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"background: {BORDER_DARK}; max-height: 1px;")
        root.addWidget(sep)

        # Log area
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background: {BG_INSET};
                color: {PHOSPHOR_MID};
                border: none;
                font-family: "Menlo", "Consolas", "Courier New", monospace;
                font-size: {px(12)}px;
                padding: 8px;
            }}
        """)
        self._log.setPlaceholderText(
            "Select a course and assignment, then click Run.")
        root.addWidget(self._log, 1)

        # Footer
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER_DARK};
            }}
        """)
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;")
        fl.addWidget(self._status_lbl)
        fl.addStretch()

        self._close_btn = QPushButton("Close")
        make_secondary_button(self._close_btn)
        self._close_btn.setFixedWidth(80)
        self._close_btn.clicked.connect(self.reject)
        fl.addWidget(self._close_btn)

        self._run_btn = QPushButton("Run Engagement Analysis")
        make_run_button(self._run_btn)
        self._run_btn.setEnabled(False)
        self._run_btn.clicked.connect(self._start_run)
        fl.addWidget(self._run_btn)

        root.addWidget(footer)

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_courses(self) -> None:
        from gui.workers import CancellableWorker

        class _CoursesWorker(CancellableWorker):
            courses_ready = Signal(list)
            def run(self):
                try:
                    by_term = self._api.get_all_teacher_courses()
                    flat = []
                    for courses in by_term.values():
                        flat.extend(courses)
                    self.courses_ready.emit(flat)
                except Exception as exc:
                    self.error.emit(str(exc))

        self._courses_worker = _CoursesWorker(self._api, parent=self)
        self._courses_worker.courses_ready.connect(self._on_courses_loaded)
        self._courses_worker.error.connect(
            lambda e: self._set_status(f"Could not load courses: {e}", error=True))
        self._courses_worker.start()

    def _on_courses_loaded(self, courses: List[Dict]) -> None:
        self._courses = courses
        self._course_combo.clear()
        self._course_combo.addItem("— select a course —", None)
        for c in courses:
            self._course_combo.addItem(c.get("name", str(c["id"])), c["id"])
        self._course_combo.setEnabled(True)
        self._set_status(f"{len(courses)} courses loaded.")

    def _on_course_changed(self) -> None:
        course_id = self._course_combo.currentData()
        self._assign_combo.clear()
        self._assign_combo.addItem("Loading assignments…")
        self._assign_combo.setEnabled(False)
        self._run_btn.setEnabled(False)

        if not course_id:
            self._assign_combo.clear()
            self._assign_combo.addItem("Select a course first")
            return

        from gui.workers import CancellableWorker

        class _AssignmentsWorker(CancellableWorker):
            assignments_ready = Signal(list)
            def __init__(self, api, course_id, parent=None):
                super().__init__(api, parent)
                self._cid = course_id
            def run(self):
                try:
                    groups = self._api.get_assignment_groups(self._cid)
                    flat = []
                    for group in groups:
                        for a in group.get("assignments", []):
                            # Only online_text_entry has analyzable body text
                            types = a.get("submission_types", [])
                            if "online_text_entry" in types:
                                flat.append(a)
                    self.assignments_ready.emit(flat)
                except Exception as exc:
                    self.error.emit(str(exc))

        self._assign_worker = _AssignmentsWorker(self._api, course_id, parent=self)
        self._assign_worker.assignments_ready.connect(self._on_assignments_loaded)
        self._assign_worker.error.connect(
            lambda e: self._set_status(f"Could not load assignments: {e}", error=True))
        self._assign_worker.start()

    def _on_assignments_loaded(self, assignments: List[Dict]) -> None:
        self._assignments = assignments
        self._assign_combo.clear()
        if not assignments:
            self._assign_combo.addItem("No text assignments found in this course")
            self._set_status("Only online_text_entry assignments can be analyzed.")
            return
        self._assign_combo.addItem("— select an assignment —", None)
        for a in assignments:
            self._assign_combo.addItem(a.get("name", str(a["id"])), a["id"])
        self._assign_combo.setEnabled(True)
        self._assign_combo.currentIndexChanged.connect(self._on_assign_changed)
        self._set_status(f"{len(assignments)} text assignments found.")

    def _on_assign_changed(self) -> None:
        has_selection = self._assign_combo.currentData() is not None
        self._run_btn.setEnabled(has_selection)

    # ── Run ───────────────────────────────────────────────────────────────────

    def _start_run(self) -> None:
        course_id = self._course_combo.currentData()
        assignment_id = self._assign_combo.currentData()
        if not course_id or not assignment_id:
            return

        education_level = self._edu_combo.currentData()
        esl_level = self._esl_combo.currentData()
        first_gen_level = self._first_gen_combo.currentData()
        neurodivergent_aware = self._nd_check.isChecked()
        course_name = self._course_combo.currentText()
        assignment_name = self._assign_combo.currentText()

        self._log.clear()
        self._log.append(
            f"Running Engagement Analysis\n"
            f"Course:      {course_name}\n"
            f"Assignment:  {assignment_name}\n"
            f"Institution: {education_level}\n"
            f"ESL pop.:    {esl_level}  |  First-gen: {first_gen_level}"
            + ("  |  ND-aware ON" if neurodivergent_aware else "") + "\n"
            f"{'─' * 50}"
        )

        self._run_btn.setEnabled(False)
        self._close_btn.setEnabled(False)
        self._set_status("Running…")

        self._worker = _AICWorker(
            course_id=int(course_id),
            assignment_id=int(assignment_id),
            education_level=education_level,
            esl_level=esl_level,
            first_gen_level=first_gen_level,
            neurodivergent_aware=neurodivergent_aware,
            course_name=course_name,
            parent=self,
        )
        self._worker.log_line.connect(self._log.append)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_finished(self, analyzed: int, smoking_guns: int) -> None:
        summary = f"\n{'─' * 50}\nDone. {analyzed} submission(s) analyzed."
        if smoking_guns:
            summary += f"\n!! {smoking_guns} smoking gun(s) detected."
        self._log.append(summary)
        self._set_status(
            f"Complete — {analyzed} analyzed"
            + (f", {smoking_guns} smoking gun(s)" if smoking_guns else ""),
            ok=True,
        )
        self._run_btn.setEnabled(True)
        self._close_btn.setEnabled(True)
        self.run_completed.emit()

    def _on_error(self, msg: str) -> None:
        self._log.append(f"\nERROR: {msg}")
        self._set_status(f"Failed: {msg}", error=True)
        self._run_btn.setEnabled(True)
        self._close_btn.setEnabled(True)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, text: str, error: bool = False, ok: bool = False) -> None:
        color = BURN_RED if error else (TERM_GREEN if ok else PHOSPHOR_DIM)
        self._status_lbl.setStyleSheet(f"color: {color}; font-size: {px(11)}px;")
        self._status_lbl.setText(text)

    def closeEvent(self, event) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().closeEvent(event)
