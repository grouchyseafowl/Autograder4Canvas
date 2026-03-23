"""
InsightsStore — SQLite persistence for Insights Engine results.

Follows the RunStore pattern: WAL mode, upsert, JSON columns for complex data,
check_same_thread=False for GUI thread safety.

DB lives at: <output_dir>/insights.db
"""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


# ──────────────────────────────────────────────────────────────────────────────
# DB path helper
# ──────────────────────────────────────────────────────────────────────────────

def get_default_db_path() -> Path:
    """Return the path to insights.db in the configured output directory."""
    try:
        import sys
        src_dir = Path(__file__).parent.parent
        if str(src_dir) not in sys.path:
            sys.path.insert(0, str(src_dir))
        from autograder_utils import get_output_base_dir
        base = get_output_base_dir()
    except Exception:
        base = Path.home() / "Canvas Grading"
    base.mkdir(parents=True, exist_ok=True)
    return base / "insights.db"


# ──────────────────────────────────────────────────────────────────────────────
# DDL
# ──────────────────────────────────────────────────────────────────────────────

_DDL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- insights_runs: one row per analysis run
CREATE TABLE IF NOT EXISTS insights_runs (
    run_id              TEXT PRIMARY KEY,
    course_id           TEXT NOT NULL,
    course_name         TEXT,
    assignment_id       TEXT NOT NULL,
    assignment_name     TEXT,
    started_at          TEXT,
    completed_at        TEXT,
    model_tier          TEXT,
    model_name          TEXT,
    total_submissions   INTEGER,
    stages_completed    TEXT DEFAULT '[]',
    pipeline_confidence TEXT,
    teacher_context     TEXT,
    analysis_lens_config TEXT,
    quick_analysis      TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_course
    ON insights_runs (course_id, assignment_id);

-- insights_codings: one row per student submission coding
CREATE TABLE IF NOT EXISTS insights_codings (
    run_id              TEXT NOT NULL,
    student_id          TEXT NOT NULL,
    student_name        TEXT,
    coding_record       TEXT,
    submission_text     TEXT,
    teacher_edited      INTEGER DEFAULT 0,
    teacher_edits       TEXT,
    PRIMARY KEY (run_id, student_id)
);

-- insights_themes: themes for a run
CREATE TABLE IF NOT EXISTS insights_themes (
    run_id              TEXT PRIMARY KEY,
    theme_set           TEXT,
    outlier_report      TEXT,
    synthesis_report    TEXT,
    teacher_edited      INTEGER DEFAULT 0,
    teacher_edits       TEXT
);

-- insights_feedback: draft student feedback
CREATE TABLE IF NOT EXISTS insights_feedback (
    run_id              TEXT NOT NULL,
    student_id          TEXT NOT NULL,
    student_name        TEXT,
    draft_text          TEXT,
    approved_text       TEXT,
    status              TEXT DEFAULT 'pending',
    confidence          REAL DEFAULT 0.0,
    posted_at           TEXT,
    PRIMARY KEY (run_id, student_id)
);

-- teacher_profiles: persistent teacher analysis profile (one per course)
CREATE TABLE IF NOT EXISTS teacher_profiles (
    profile_id          TEXT PRIMARY KEY,
    profile_data        TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

-- course_profile_templates: reusable profile snapshots (save/load across semesters)
CREATE TABLE IF NOT EXISTS course_profile_templates (
    template_name       TEXT PRIMARY KEY,
    profile_data        TEXT,
    created_at          TEXT,
    updated_at          TEXT
);

-- prompt_calibration: teacher corrections for prompt optimization
CREATE TABLE IF NOT EXISTS prompt_calibration (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id          TEXT NOT NULL,
    submission_text     TEXT,
    original_coding     TEXT,
    corrected_coding    TEXT,
    correction_type     TEXT,
    created_at          TEXT
);
"""


# ──────────────────────────────────────────────────────────────────────────────
# InsightsStore
# ──────────────────────────────────────────────────────────────────────────────

class InsightsStore:
    """SQLite persistence for insights analysis runs and results.

    Thread-safety: single connection with check_same_thread=False; WAL mode
    handles concurrent readers. All writes are short transactions.
    """

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_default_db_path()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._migrate()

    def close(self) -> None:
        self._conn.close()

    # ── Private helpers ────────────────────────────────────────────────────

    def _migrate(self) -> None:
        self._conn.executescript(_DDL)
        self._conn.commit()
        self._migrate_v2()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _j(value: Any) -> str:
        if value is None:
            return "[]"
        if isinstance(value, str):
            return value
        return json.dumps(value, default=str)

    @staticmethod
    def _jd(value: Any) -> str:
        if value is None:
            return "{}"
        if isinstance(value, str):
            return value
        return json.dumps(value, default=str)

    def _migrate_v2(self) -> None:
        """Phase 3 idempotent schema migration: add teacher_notes column."""
        try:
            self._conn.execute(
                "ALTER TABLE insights_codings ADD COLUMN teacher_notes TEXT"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        self._migrate_v3()

    def _migrate_v3(self) -> None:
        """Phase 4 idempotent schema migration: add feedback columns."""
        for col, typ in [
            ("student_name", "TEXT"),
            ("confidence", "REAL DEFAULT 0.0"),
        ]:
            try:
                self._conn.execute(
                    f"ALTER TABLE insights_feedback ADD COLUMN {col} {typ}"
                )
                self._conn.commit()
            except sqlite3.OperationalError:
                pass  # column already exists
        self._migrate_v4()

    def _migrate_v4(self) -> None:
        """Add submission_text column to codings for chatbot export."""
        try:
            self._conn.execute(
                "ALTER TABLE insights_codings ADD COLUMN submission_text TEXT"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        self._migrate_v5()

    def _migrate_v5(self) -> None:
        """Add course_profile_id to runs; create course_profile_templates table."""
        try:
            self._conn.execute(
                "ALTER TABLE insights_runs ADD COLUMN "
                "course_profile_id TEXT DEFAULT 'default'"
            )
            self._conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS course_profile_templates (
                template_name   TEXT PRIMARY KEY,
                profile_data    TEXT,
                created_at      TEXT,
                updated_at      TEXT
            );
            """
        )
        self._conn.commit()

    @staticmethod
    def generate_run_id() -> str:
        return str(uuid.uuid4())

    # ── Runs ───────────────────────────────────────────────────────────────

    def create_run(
        self,
        *,
        run_id: str,
        course_id: str,
        course_name: str,
        assignment_id: str,
        assignment_name: str,
        model_tier: str = "lightweight",
        model_name: str = "",
        total_submissions: int = 0,
        teacher_context: str = "",
        analysis_lens_config: Optional[Dict] = None,
        course_profile_id: str = "default",
    ) -> None:
        """Create a new analysis run record."""
        self._conn.execute(
            """
            INSERT INTO insights_runs (
                run_id, course_id, course_name, assignment_id, assignment_name,
                started_at, model_tier, model_name, total_submissions,
                stages_completed, teacher_context, analysis_lens_config,
                course_profile_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '[]', ?, ?, ?)
            ON CONFLICT (run_id) DO UPDATE SET
                started_at = excluded.started_at,
                model_tier = excluded.model_tier,
                total_submissions = excluded.total_submissions
            """,
            (
                run_id, str(course_id), course_name, str(assignment_id),
                assignment_name, self._now(), model_tier, model_name,
                total_submissions, teacher_context,
                self._jd(analysis_lens_config),
                course_profile_id,
            ),
        )
        self._conn.commit()

    def complete_stage(self, run_id: str, stage_name: str) -> None:
        """Mark a pipeline stage as completed."""
        row = self._conn.execute(
            "SELECT stages_completed FROM insights_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return
        stages = json.loads(row["stages_completed"] or "[]")
        if stage_name not in stages:
            stages.append(stage_name)
        self._conn.execute(
            "UPDATE insights_runs SET stages_completed = ? WHERE run_id = ?",
            (json.dumps(stages), run_id),
        )
        self._conn.commit()

    def complete_run(self, run_id: str, confidence: Optional[Dict] = None) -> None:
        """Mark a run as completed."""
        self._conn.execute(
            "UPDATE insights_runs SET completed_at = ?, pipeline_confidence = ? "
            "WHERE run_id = ?",
            (self._now(), self._jd(confidence), run_id),
        )
        self._conn.commit()

    def save_quick_analysis(self, run_id: str, result_json: str) -> None:
        """Save the QuickAnalysisResult JSON for a run."""
        self._conn.execute(
            "UPDATE insights_runs SET quick_analysis = ? WHERE run_id = ?",
            (result_json, run_id),
        )
        self._conn.commit()

    def get_run(self, run_id: str) -> Optional[Dict]:
        """Get a single run by ID with JSON decoded."""
        row = self._conn.execute(
            "SELECT * FROM insights_runs WHERE run_id = ?", (run_id,)
        ).fetchone()
        if not row:
            return None
        return self._decode_run(dict(row))

    def get_runs(self, course_id: Optional[str] = None) -> List[Dict]:
        """Get all runs, optionally filtered by course, newest first."""
        if course_id:
            rows = self._conn.execute(
                "SELECT * FROM insights_runs WHERE course_id = ? "
                "ORDER BY started_at DESC",
                (str(course_id),),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM insights_runs ORDER BY started_at DESC"
            ).fetchall()
        return [self._decode_run(dict(r)) for r in rows]

    def get_completed_runs(self) -> List[Dict]:
        """Get all completed runs for the review sidebar."""
        rows = self._conn.execute(
            "SELECT * FROM insights_runs WHERE completed_at IS NOT NULL "
            "ORDER BY completed_at DESC"
        ).fetchall()
        return [self._decode_run(dict(r)) for r in rows]

    def _decode_run(self, d: Dict) -> Dict:
        for col in ("stages_completed",):
            raw = d.get(col)
            if raw:
                try:
                    d[col] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    d[col] = []
        for col in ("pipeline_confidence", "analysis_lens_config"):
            raw = d.get(col)
            if raw:
                try:
                    d[col] = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    d[col] = {}
        return d

    # ── Codings ────────────────────────────────────────────────────────────

    def save_coding(
        self, run_id: str, student_id: str, student_name: str,
        coding_record_json: str, submission_text: str = "",
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO insights_codings
                (run_id, student_id, student_name, coding_record, submission_text)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (run_id, student_id) DO UPDATE SET
                student_name = excluded.student_name,
                coding_record = excluded.coding_record,
                submission_text = COALESCE(
                    NULLIF(excluded.submission_text, ''),
                    insights_codings.submission_text
                )
            """,
            (run_id, str(student_id), student_name, coding_record_json,
             submission_text),
        )
        self._conn.commit()

    def get_codings(self, run_id: str) -> List[Dict]:
        rows = self._conn.execute(
            "SELECT * FROM insights_codings WHERE run_id = ?", (run_id,)
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("coding_record"):
                try:
                    d["coding_record"] = json.loads(d["coding_record"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def get_coding_record(self, run_id: str, student_id: str) -> Optional[Dict]:
        """Fetch a single coding record for one student."""
        row = self._conn.execute(
            "SELECT * FROM insights_codings WHERE run_id = ? AND student_id = ?",
            (run_id, str(student_id)),
        ).fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("coding_record"):
            try:
                d["coding_record"] = json.loads(d["coding_record"])
            except (json.JSONDecodeError, TypeError):
                pass
        if d.get("teacher_edits"):
            try:
                d["teacher_edits"] = json.loads(d["teacher_edits"])
            except (json.JSONDecodeError, TypeError):
                pass
        return d

    def update_coding_tags(
        self, run_id: str, student_id: str,
        coding_record_json: str, teacher_edits: Dict,
    ) -> None:
        """Update coding record after teacher tag edits."""
        self._conn.execute(
            """UPDATE insights_codings
               SET coding_record = ?, teacher_edited = 1, teacher_edits = ?
               WHERE run_id = ? AND student_id = ?""",
            (coding_record_json, self._jd(teacher_edits),
             run_id, str(student_id)),
        )
        self._conn.commit()

    def update_coding_concerns(
        self, run_id: str, student_id: str,
        coding_record_json: str, teacher_edits: Dict,
    ) -> None:
        """Update coding record after teacher concern edits."""
        self._conn.execute(
            """UPDATE insights_codings
               SET coding_record = ?, teacher_edited = 1, teacher_edits = ?
               WHERE run_id = ? AND student_id = ?""",
            (coding_record_json, self._jd(teacher_edits),
             run_id, str(student_id)),
        )
        self._conn.commit()

    def update_coding_note(
        self, run_id: str, student_id: str, note: str,
    ) -> None:
        """Write teacher_notes column for a coding record."""
        self._conn.execute(
            """UPDATE insights_codings
               SET teacher_notes = ?
               WHERE run_id = ? AND student_id = ?""",
            (note, run_id, str(student_id)),
        )
        self._conn.commit()

    # ── Themes ─────────────────────────────────────────────────────────────

    def save_themes(
        self, run_id: str,
        theme_set_json: Optional[str] = None,
        outlier_report_json: Optional[str] = None,
        synthesis_report_json: Optional[str] = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO insights_themes (run_id, theme_set, outlier_report, synthesis_report)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (run_id) DO UPDATE SET
                theme_set = COALESCE(excluded.theme_set, insights_themes.theme_set),
                outlier_report = COALESCE(excluded.outlier_report, insights_themes.outlier_report),
                synthesis_report = COALESCE(excluded.synthesis_report, insights_themes.synthesis_report)
            """,
            (run_id, theme_set_json, outlier_report_json, synthesis_report_json),
        )
        self._conn.commit()

    def get_themes(self, run_id: str) -> Optional[Dict]:
        """Get themes/outliers/synthesis data for a run."""
        row = self._conn.execute(
            "SELECT theme_set, outlier_report, synthesis_report "
            "FROM insights_themes WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if not row:
            return None
        return dict(row)

    def update_theme_set(
        self, run_id: str, theme_set_json: str, teacher_edits: Dict,
    ) -> None:
        """Replace theme_set and mark teacher_edited."""
        self._conn.execute(
            """UPDATE insights_themes
               SET theme_set = ?, teacher_edited = 1, teacher_edits = ?
               WHERE run_id = ?""",
            (theme_set_json, self._jd(teacher_edits), run_id),
        )
        self._conn.commit()

    def update_outlier_report(self, run_id: str, outlier_report_json: str) -> None:
        """Update outlier report (for outlier→theme moves)."""
        self._conn.execute(
            "UPDATE insights_themes SET outlier_report = ? WHERE run_id = ?",
            (outlier_report_json, run_id),
        )
        self._conn.commit()

    def update_synthesis_report(self, run_id: str, synthesis_json: str) -> None:
        """Update synthesis report after direct edits."""
        self._conn.execute(
            "UPDATE insights_themes SET synthesis_report = ? WHERE run_id = ?",
            (synthesis_json, run_id),
        )
        self._conn.commit()

    # ── Teacher profiles ───────────────────────────────────────────────────

    def save_profile(self, profile_id: str, profile_data: Dict) -> None:
        now = self._now()
        self._conn.execute(
            """
            INSERT INTO teacher_profiles (profile_id, profile_data, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (profile_id) DO UPDATE SET
                profile_data = excluded.profile_data,
                updated_at = excluded.updated_at
            """,
            (profile_id, self._jd(profile_data), now, now),
        )
        self._conn.commit()

    def get_profile(self, profile_id: str) -> Optional[Dict]:
        row = self._conn.execute(
            "SELECT profile_data FROM teacher_profiles WHERE profile_id = ?",
            (profile_id,),
        ).fetchone()
        if not row or not row["profile_data"]:
            return None
        try:
            return json.loads(row["profile_data"])
        except (json.JSONDecodeError, TypeError):
            return None

    def list_profiles(self) -> List[str]:
        """Return all profile_ids that have been saved."""
        rows = self._conn.execute(
            "SELECT profile_id FROM teacher_profiles ORDER BY profile_id"
        ).fetchall()
        return [r["profile_id"] for r in rows]

    # ── Course profile templates ────────────────────────────────────────

    def save_profile_template(self, template_name: str, profile_data: Dict) -> None:
        """Save a profile snapshot as a reusable template."""
        now = self._now()
        self._conn.execute(
            """
            INSERT INTO course_profile_templates
                (template_name, profile_data, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (template_name) DO UPDATE SET
                profile_data = excluded.profile_data,
                updated_at = excluded.updated_at
            """,
            (template_name, self._jd(profile_data), now, now),
        )
        self._conn.commit()

    def get_profile_template(self, template_name: str) -> Optional[Dict]:
        """Load a profile template by name."""
        row = self._conn.execute(
            "SELECT profile_data FROM course_profile_templates "
            "WHERE template_name = ?",
            (template_name,),
        ).fetchone()
        if not row or not row["profile_data"]:
            return None
        try:
            return json.loads(row["profile_data"])
        except (json.JSONDecodeError, TypeError):
            return None

    def list_profile_templates(self) -> List[str]:
        """Return all saved template names, alphabetically."""
        rows = self._conn.execute(
            "SELECT template_name FROM course_profile_templates "
            "ORDER BY template_name"
        ).fetchall()
        return [r["template_name"] for r in rows]

    def delete_profile_template(self, template_name: str) -> None:
        """Delete a saved template."""
        self._conn.execute(
            "DELETE FROM course_profile_templates WHERE template_name = ?",
            (template_name,),
        )
        self._conn.commit()

    def save_calibration(
        self,
        profile_id: str,
        submission_text: str,
        original_json: str,
        corrected_json: str,
        correction_type: str,
    ) -> None:
        """Insert a calibration record for prompt optimization."""
        self._conn.execute(
            """INSERT INTO prompt_calibration
               (profile_id, submission_text, original_coding, corrected_coding,
                correction_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (profile_id, submission_text, original_json, corrected_json,
             correction_type, self._now()),
        )
        self._conn.commit()

    # ── Feedback ───────────────────────────────────────────────────────────

    def save_feedback(
        self,
        run_id: str,
        student_id: str,
        student_name: str = "",
        draft_text: str = "",
        confidence: float = 0.0,
    ) -> None:
        """Save or update a draft feedback row."""
        self._conn.execute(
            """
            INSERT INTO insights_feedback
                (run_id, student_id, student_name, draft_text, confidence, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
            ON CONFLICT (run_id, student_id) DO UPDATE SET
                student_name = excluded.student_name,
                draft_text = excluded.draft_text,
                confidence = excluded.confidence
            """,
            (run_id, str(student_id), student_name, draft_text, confidence),
        )
        self._conn.commit()

    def get_feedback(self, run_id: str) -> List[Dict]:
        """Get all feedback rows for a run."""
        rows = self._conn.execute(
            "SELECT * FROM insights_feedback WHERE run_id = ? "
            "ORDER BY student_name",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_approved_feedback(self, run_id: str) -> List[Dict]:
        """Get only approved (not yet posted) feedback."""
        rows = self._conn.execute(
            "SELECT * FROM insights_feedback "
            "WHERE run_id = ? AND status = 'approved'",
            (run_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def update_feedback_status(
        self,
        run_id: str,
        student_id: str,
        status: str,
        approved_text: Optional[str] = None,
    ) -> None:
        """Update feedback status and optionally the approved text."""
        if approved_text is not None:
            self._conn.execute(
                "UPDATE insights_feedback SET status = ?, approved_text = ? "
                "WHERE run_id = ? AND student_id = ?",
                (status, approved_text, run_id, str(student_id)),
            )
        else:
            self._conn.execute(
                "UPDATE insights_feedback SET status = ? "
                "WHERE run_id = ? AND student_id = ?",
                (status, run_id, str(student_id)),
            )
        if status == "posted":
            self._conn.execute(
                "UPDATE insights_feedback SET posted_at = ? "
                "WHERE run_id = ? AND student_id = ?",
                (self._now(), run_id, str(student_id)),
            )
        self._conn.commit()

    def update_feedback_text(
        self, run_id: str, student_id: str, text: str,
    ) -> None:
        """Update the draft text after teacher editing."""
        self._conn.execute(
            "UPDATE insights_feedback SET draft_text = ? "
            "WHERE run_id = ? AND student_id = ?",
            (text, run_id, str(student_id)),
        )
        self._conn.commit()

    # ── Cleanup ────────────────────────────────────────────────────────────

    def delete_run(self, run_id: str) -> None:
        """Delete a run and all its associated data."""
        self._conn.execute("DELETE FROM insights_codings WHERE run_id = ?", (run_id,))
        self._conn.execute("DELETE FROM insights_themes WHERE run_id = ?", (run_id,))
        self._conn.execute("DELETE FROM insights_feedback WHERE run_id = ?", (run_id,))
        self._conn.execute("DELETE FROM insights_runs WHERE run_id = ?", (run_id,))
        self._conn.commit()

    def count_for_cleanup(self, days: int) -> int:
        """Count runs older than N days."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        row = self._conn.execute(
            "SELECT COUNT(*) FROM insights_runs WHERE started_at < ?",
            (cutoff,),
        ).fetchone()
        return row[0] if row else 0

    def delete_for_cleanup(self, days: int) -> int:
        """Delete runs older than N days. Returns count deleted."""
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        rows = self._conn.execute(
            "SELECT run_id FROM insights_runs WHERE started_at < ?",
            (cutoff,),
        ).fetchall()
        count = 0
        for row in rows:
            self.delete_run(row["run_id"])
            count += 1
        return count
