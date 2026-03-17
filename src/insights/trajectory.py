"""
TrajectoryAnalyzer — Cross-run analysis for semester-level visibility.

Loads all completed insight runs for a course, computes:
  - Theme evolution (recurring / new / fading / one-time)
  - Engagement trends (word counts, submission rates over time)
  - Concern trends (concern signal counts over time)
  - Exhaustion indicators (late, short, missing — STRUCTURAL signals)
  - Top readings (most-referenced, correlated with engagement)
  - Per-student arcs (week-by-week trajectory sparkline data)

All trends are STRUCTURAL signals about the course, not individual report cards.
"Exhaustion increasing" is a course design signal, not a student failure signal.
"""

import json
import logging
from collections import Counter, defaultdict
from typing import Dict, List, Optional

from insights.models import (
    CourseTrajectory,
    ReadingEngagement,
    StudentArc,
    ThemeEvolution,
    WeekMetric,
)

log = logging.getLogger(__name__)


class TrajectoryAnalyzer:
    """Analyze patterns across multiple insight runs for a course."""

    def __init__(self, store):
        self._store = store

    def analyze_course_trajectory(self, course_id: str) -> Optional[CourseTrajectory]:
        """Load all completed runs for a course, compute semester patterns.

        Returns None if fewer than 2 runs exist (no trajectory to compute).
        """
        runs = self._store.get_runs(course_id)
        # Only completed runs, sorted oldest first
        completed = [
            r for r in runs
            if r.get("completed_at")
        ]
        completed.sort(key=lambda r: r.get("started_at", ""))

        if len(completed) < 2:
            return None

        course_name = completed[0].get("course_name", "")
        date_range = self._format_date_range(completed)

        # Load quick analysis + coding data for each run
        run_data = []
        for run in completed:
            rid = run["run_id"]
            qa_json = run.get("quick_analysis")
            qa = None
            if qa_json:
                try:
                    from insights.models import QuickAnalysisResult
                    if isinstance(qa_json, str):
                        qa = QuickAnalysisResult.model_validate_json(qa_json)
                    else:
                        qa = QuickAnalysisResult.model_validate(qa_json)
                except Exception:
                    log.debug("Could not parse quick_analysis for run %s", rid)

            codings = self._store.get_codings(rid)
            coding_records = []
            for row in codings:
                rec = row.get("coding_record", {})
                if isinstance(rec, str):
                    try:
                        rec = json.loads(rec)
                    except (json.JSONDecodeError, TypeError):
                        rec = {}
                coding_records.append(rec)

            themes_row = self._store.get_themes(rid)
            theme_names = []
            if themes_row:
                ts_raw = themes_row.get("theme_set", "{}")
                try:
                    ts = json.loads(ts_raw) if isinstance(ts_raw, str) else ts_raw
                    for t in ts.get("themes", []):
                        theme_names.append(t.get("name", ""))
                except (json.JSONDecodeError, TypeError):
                    pass

            run_data.append({
                "run": run,
                "qa": qa,
                "codings": coding_records,
                "theme_names": [n for n in theme_names if n],
            })

        # Compute all trajectory components
        theme_evolution = self._compute_theme_evolution(run_data)
        engagement_trend = self._compute_engagement_trend(run_data)
        concern_trend = self._compute_concern_trend(run_data)
        exhaustion_trend = self._compute_exhaustion_trend(run_data)
        top_readings = self._compute_top_readings(run_data)
        student_trajectories = self._compute_student_arcs(run_data)

        return CourseTrajectory(
            course_id=course_id,
            course_name=course_name,
            run_count=len(completed),
            date_range=date_range,
            theme_evolution=theme_evolution,
            engagement_trend=engagement_trend,
            concern_trend=concern_trend,
            exhaustion_trend=exhaustion_trend,
            top_readings=top_readings,
            student_trajectories=student_trajectories,
        )

    # ------------------------------------------------------------------
    # Theme evolution
    # ------------------------------------------------------------------

    def _compute_theme_evolution(self, run_data: list) -> List[ThemeEvolution]:
        """Track which themes appear in which weeks and classify their lifecycle."""
        # Map theme name → list of week indices where it appeared
        theme_weeks: Dict[str, List[int]] = defaultdict(list)
        total_weeks = len(run_data)

        for week_idx, rd in enumerate(run_data):
            for name in rd["theme_names"]:
                normalized = name.strip().lower()
                theme_weeks[normalized].append(week_idx)

        results = []
        for name, weeks in theme_weeks.items():
            first = min(weeks)
            # Classify status
            if len(weeks) >= total_weeks * 0.6:
                status = "recurring"
            elif first == total_weeks - 1:
                status = "new"
            elif max(weeks) < total_weeks - 2 and len(weeks) > 1:
                status = "fading"
            elif len(weeks) == 1:
                status = "one-time"
            else:
                status = "recurring" if len(weeks) > 1 else "one-time"

            # Use the original casing from first occurrence
            display_name = name
            for rd in run_data:
                for tn in rd["theme_names"]:
                    if tn.strip().lower() == name:
                        display_name = tn
                        break
                else:
                    continue
                break

            results.append(ThemeEvolution(
                theme_name=display_name,
                weeks_present=sorted(weeks),
                first_appeared=first,
                status=status,
            ))

        # Sort: recurring first, then by first appearance
        results.sort(key=lambda t: (
            {"recurring": 0, "new": 1, "fading": 2, "one-time": 3}.get(t.status, 4),
            t.first_appeared,
        ))
        return results

    # ------------------------------------------------------------------
    # Engagement trend
    # ------------------------------------------------------------------

    def _compute_engagement_trend(self, run_data: list) -> List[WeekMetric]:
        """Compute per-week engagement metrics from quick analysis data."""
        metrics = []
        for week_idx, rd in enumerate(run_data):
            qa = rd["qa"]
            run = rd["run"]
            label = run.get("assignment_name", f"Run {week_idx + 1}")

            avg_words = 0.0
            sub_rate = 0.0
            if qa:
                avg_words = qa.stats.word_count_mean
                total = qa.stats.total_enrollment or qa.stats.total_submissions
                if total > 0:
                    sub_rate = qa.stats.total_submissions / total
                else:
                    sub_rate = 1.0

            metrics.append(WeekMetric(
                week=week_idx,
                label=label[:30],
                avg_words=round(avg_words, 1),
                submission_rate=round(sub_rate, 2),
            ))
        return metrics

    # ------------------------------------------------------------------
    # Concern trend
    # ------------------------------------------------------------------

    def _compute_concern_trend(self, run_data: list) -> List[WeekMetric]:
        """Compute per-week concern signal counts."""
        metrics = []
        for week_idx, rd in enumerate(run_data):
            qa = rd["qa"]
            run = rd["run"]
            label = run.get("assignment_name", f"Run {week_idx + 1}")

            concern_count = 0
            concern_types: List[str] = []
            if qa and qa.concern_signals:
                concern_count = len(qa.concern_signals)
                concern_types = list({s.signal_type for s in qa.concern_signals})

            # Also count LLM concerns from codings
            for rec in rd["codings"]:
                concerns = rec.get("concerns", [])
                concern_count += len(concerns)

            metrics.append(WeekMetric(
                week=week_idx,
                label=label[:30],
                concern_count=concern_count,
                concern_types=concern_types,
            ))
        return metrics

    # ------------------------------------------------------------------
    # Exhaustion trend (structural signal)
    # ------------------------------------------------------------------

    def _compute_exhaustion_trend(self, run_data: list) -> List[WeekMetric]:
        """Track late, short, and missing submissions — course design signals."""
        metrics = []
        for week_idx, rd in enumerate(run_data):
            qa = rd["qa"]
            run = rd["run"]
            label = run.get("assignment_name", f"Run {week_idx + 1}")

            late = 0
            short = 0
            silence = 0
            if qa:
                timing = qa.stats.timing
                late = timing.get("late", 0) + timing.get("very_late", 0)
                silence = timing.get("missing", 0)

                # "Short" = below 40% of median word count
                median = qa.stats.word_count_median
                if median > 0:
                    for ps in qa.per_submission.values():
                        if ps.word_count < median * 0.4:
                            short += 1

            metrics.append(WeekMetric(
                week=week_idx,
                label=label[:30],
                late_count=late,
                short_count=short,
                silence_count=silence,
            ))
        return metrics

    # ------------------------------------------------------------------
    # Top readings
    # ------------------------------------------------------------------

    def _compute_top_readings(self, run_data: list) -> List[ReadingEngagement]:
        """Aggregate readings_referenced across all runs."""
        reading_counts: Counter = Counter()
        reading_word_sums: Dict[str, float] = defaultdict(float)
        reading_word_n: Dict[str, int] = defaultdict(int)

        for rd in run_data:
            for rec in rd["codings"]:
                refs = rec.get("readings_referenced", [])
                wc = rec.get("word_count", 0)
                for ref in refs:
                    ref_norm = ref.strip()
                    if ref_norm:
                        reading_counts[ref_norm] += 1
                        reading_word_sums[ref_norm] += wc
                        reading_word_n[ref_norm] += 1

        results = []
        for reading, count in reading_counts.most_common(15):
            avg_wc = reading_word_sums[reading] / max(reading_word_n[reading], 1)
            results.append(ReadingEngagement(
                reading=reading,
                times_referenced=count,
                avg_word_count=round(avg_wc, 1),
            ))
        return results

    # ------------------------------------------------------------------
    # Student arcs
    # ------------------------------------------------------------------

    def _compute_student_arcs(self, run_data: list) -> List[StudentArc]:
        """Compute per-student week-by-week trajectory data."""
        # Gather all student IDs and names across all runs
        all_students: Dict[str, str] = {}  # id → name
        for rd in run_data:
            for rec in rd["codings"]:
                sid = rec.get("student_id", "")
                sname = rec.get("student_name", "")
                if sid:
                    all_students[sid] = sname

        arcs = []
        total_weeks = len(run_data)

        for sid, sname in sorted(all_students.items(), key=lambda x: x[1]):
            word_counts: List[Optional[int]] = []
            statuses: List[str] = []
            concern_flags: List[int] = []

            for rd in run_data:
                qa = rd["qa"]
                # Find this student in the codings
                found = False
                for rec in rd["codings"]:
                    if rec.get("student_id") == sid:
                        found = True
                        wc = rec.get("word_count", 0)
                        word_counts.append(wc)

                        # Determine timing status from quick analysis
                        status = "on_time"
                        if qa and qa.per_submission:
                            ps = qa.per_submission.get(sid)
                            # Timing is in stats.timing (aggregate), not per-student
                            # Use word count heuristic: 0 words = missing
                            if wc == 0:
                                status = "missing"

                        statuses.append(status)
                        concern_flags.append(len(rec.get("concerns", [])))
                        break

                if not found:
                    word_counts.append(None)
                    statuses.append("missing")
                    concern_flags.append(0)

            # Compute trend from word counts
            trend = self._classify_trend(word_counts)

            arcs.append(StudentArc(
                student_id=sid,
                student_name=sname,
                weekly_word_counts=word_counts,
                weekly_submission_status=statuses,
                weekly_concern_flags=concern_flags,
                trend=trend,
            ))
        return arcs

    @staticmethod
    def _classify_trend(word_counts: List[Optional[int]]) -> str:
        """Classify a student's trajectory as steady/improving/declining/irregular."""
        valid = [(i, wc) for i, wc in enumerate(word_counts) if wc is not None and wc > 0]
        if len(valid) < 2:
            return "irregular"

        # Simple linear slope via least-squares
        n = len(valid)
        sx = sum(i for i, _ in valid)
        sy = sum(wc for _, wc in valid)
        sxx = sum(i * i for i, _ in valid)
        sxy = sum(i * wc for i, wc in valid)
        denom = n * sxx - sx * sx
        if denom == 0:
            return "steady"

        slope = (n * sxy - sx * sy) / denom
        mean_y = sy / n

        # Normalize slope relative to mean
        if mean_y == 0:
            return "steady"
        rel_slope = slope / mean_y

        if rel_slope > 0.08:
            return "improving"
        elif rel_slope < -0.08:
            return "declining"

        # Check variance for irregularity
        values = [wc for _, wc in valid]
        mean_v = sum(values) / len(values)
        variance = sum((v - mean_v) ** 2 for v in values) / len(values)
        cv = (variance ** 0.5) / mean_v if mean_v > 0 else 0
        if cv > 0.5:
            return "irregular"

        return "steady"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_date_range(runs: list) -> str:
        """Format the date range from first to last run."""
        try:
            from datetime import datetime
            first = runs[0].get("started_at", "")
            last = runs[-1].get("started_at", "")
            d1 = datetime.fromisoformat(first.replace("Z", "+00:00"))
            d2 = datetime.fromisoformat(last.replace("Z", "+00:00"))
            return f"{d1.strftime('%b %d')} \u2013 {d2.strftime('%b %d, %Y')}"
        except Exception:
            return ""
