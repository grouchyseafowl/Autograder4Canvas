"""
Class-wide trajectory context builder for the Longitudinal Trajectory Comparator.

Produces a compact (~150-token) structured block describing engagement trends,
exhaustion signals, theme evolution, and student arc counts across prior runs
for a course.  This block is injected into the observation synthesis prompt so
teachers read individual student changes through a structural lens first — when
many students shift simultaneously that is a course-design signal, not 30
individual problems.

Equity principles embedded here:
  #DISABILITY_STUDIES / #CRIP_TIME — "variable" not "irregular"; variable output
    is a description, not a deficit.
  #DISABILITY_STUDIES — class-wide decline framed as structural/environmental.
  Trend labels: "increasing"/"decreasing" not "improving"/"declining".
  Student arcs: mapped from trajectory.py's internal labels to our labels.
"""

import logging
from typing import List, Optional

from insights.models import CourseTrajectory, StudentArc, ThemeEvolution, WeekMetric
from insights.trajectory import TrajectoryAnalyzer

log = logging.getLogger(__name__)

# ── Trend label mapping ──────────────────────────────────────────────────────
# trajectory.py uses "improving" / "declining" / "irregular" internally.
# We use "increasing" / "decreasing" / "variable" in all user-facing text.

_ARC_LABEL_MAP = {
    "steady": "steady",
    "improving": "increasing",
    "declining": "decreasing",
    "irregular": "variable",
}


# ── Least-squares trend classifier ──────────────────────────────────────────
# Copied (and relabelled) from TrajectoryAnalyzer._classify_trend so this
# module is self-contained and doesn't depend on internal trajectory.py state.

def _classify_word_count_trend(values: List[float]) -> str:
    """Classify a sequence of word-count values as steady/increasing/decreasing/variable.

    Uses least-squares linear fit normalised against the mean.
    Returns "variable" (not "irregular") per #CRIP_TIME framing.
    Returns "steady" for sequences shorter than 2 data points.
    """
    valid = [(i, v) for i, v in enumerate(values) if v is not None and v > 0]
    if len(valid) < 2:
        return "steady"

    n = len(valid)
    sx = sum(i for i, _ in valid)
    sy = sum(v for _, v in valid)
    sxx = sum(i * i for i, _ in valid)
    sxy = sum(i * v for i, v in valid)
    denom = n * sxx - sx * sx
    if denom == 0:
        return "steady"

    slope = (n * sxy - sx * sy) / denom
    mean_y = sy / n
    if mean_y == 0:
        return "steady"

    rel_slope = slope / mean_y
    if rel_slope > 0.08:
        return "increasing"
    if rel_slope < -0.08:
        return "decreasing"

    # Near-zero slope — check variance for variable vs steady
    raw_values = [v for _, v in valid]
    mean_v = sum(raw_values) / len(raw_values)
    variance = sum((v - mean_v) ** 2 for v in raw_values) / len(raw_values)
    cv = (variance ** 0.5) / mean_v if mean_v > 0 else 0
    if cv > 0.5:
        return "variable"

    return "steady"


# ── Section builders ─────────────────────────────────────────────────────────

def _format_engagement_line(engagement_trend: List[WeekMetric]) -> Optional[str]:
    """Build the engagement trend sentence.

    Returns None if there are fewer than 2 data points.

    Example output:
        "Class word count steady (avg 420 → 440 → 430)."
    """
    word_counts = [m.avg_words for m in engagement_trend if m.avg_words > 0]
    if len(word_counts) < 2:
        return None

    trend = _classify_word_count_trend(word_counts)
    # Show up to 4 values to keep the line short; round to nearest int
    display_counts = word_counts[-4:] if len(word_counts) > 4 else word_counts
    avg_str = " → ".join(str(int(round(v))) for v in display_counts)
    return f"Class word count {trend} (avg {avg_str})."


def _format_exhaustion_line(exhaustion_trend: List[WeekMetric]) -> Optional[str]:
    """Build the exhaustion signal sentence(s).

    Compares the most-recent week against the prior week.
    Returns None when there are fewer than 2 exhaustion metrics.

    Example output:
        "Late submissions increased (3 → 5). Missing: 2 students.
        This may be a course design signal, not individual student issues."
    """
    if len(exhaustion_trend) < 2:
        return None

    prior = exhaustion_trend[-2]
    current = exhaustion_trend[-1]

    parts: List[str] = []

    # Late submissions
    if current.late_count > 0 or prior.late_count > 0:
        direction = (
            "increased" if current.late_count > prior.late_count
            else "decreased" if current.late_count < prior.late_count
            else "unchanged"
        )
        parts.append(
            f"Late submissions {direction} ({prior.late_count} → {current.late_count})."
        )

    # Missing submissions
    if current.silence_count > 0:
        parts.append(f"Missing: {current.silence_count} student{'s' if current.silence_count != 1 else ''}.")

    if not parts:
        return None

    line = " ".join(parts)

    # Structural framing when exhaustion is rising
    late_rising = current.late_count > prior.late_count
    silence_rising = current.silence_count > prior.silence_count
    if late_rising or silence_rising:
        line += " This may be a course design signal, not individual student issues."

    return line


def _format_themes_line(theme_evolution: List[ThemeEvolution], run_count: int) -> Optional[str]:
    """Build the theme-continuity sentence(s).

    Shows recurring themes first, then new themes.  Fading themes are included
    only when present (graceful omission).

    Returns None when there is no theme data.
    """
    recurring = [t for t in theme_evolution if t.status == "recurring"]
    new = [t for t in theme_evolution if t.status == "new"]
    fading = [t for t in theme_evolution if t.status == "fading"]

    parts: List[str] = []

    if recurring:
        names = [f'"{t.theme_name}"' for t in recurring[:3]]
        if len(recurring) > 3:
            names.append(f"and {len(recurring) - 3} more")
        week_word = f"all {run_count - 1} prior" if run_count > 2 else "prior"
        parts.append(
            f"{_oxford_join(names)} persisted across {week_word} week{'s' if run_count - 1 != 1 else ''}."
        )

    if new:
        new_names = [f'"{t.theme_name}"' for t in new[:2]]
        verb = "are" if len(new) > 1 else "is"
        parts.append(f"{_oxford_join(new_names)} {verb} new this week.")

    if fading:
        fading_names = [f'"{t.theme_name}"' for t in fading[:2]]
        parts.append(f"{_oxford_join(fading_names)} fading.")

    if not parts:
        return None

    return " ".join(parts)


def _format_arc_line(student_trajectories: List[StudentArc]) -> Optional[str]:
    """Build the student arc summary line.

    Maps trajectory.py internal labels to user-facing labels.
    Never names individual students.

    Example output:
        "22 steady, 3 increasing, 3 decreasing, 2 variable."
    """
    if not student_trajectories:
        return None

    counts = {"steady": 0, "increasing": 0, "decreasing": 0, "variable": 0}
    for arc in student_trajectories:
        mapped = _ARC_LABEL_MAP.get(arc.trend, "variable")
        counts[mapped] += 1

    # Only include categories that have at least 1 student
    segments = [
        f"{v} {k}"
        for k, v in counts.items()
        if v > 0
    ]
    if not segments:
        return None

    return ", ".join(segments) + "."


# ── Utility ──────────────────────────────────────────────────────────────────

def _oxford_join(items: List[str]) -> str:
    """Join a list with Oxford comma style."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"


# ── Public API ───────────────────────────────────────────────────────────────

def build_class_trajectory_context(
    store,          # InsightsStore — not typed to avoid circular import
    course_id: str,
    current_run_id: str,
) -> str:
    """Build a compact class-wide trajectory context block for synthesis injection.

    Uses ``TrajectoryAnalyzer`` to load all completed prior runs for the course.
    Returns an empty string when fewer than 2 completed runs exist (nothing to
    compare against).

    Args:
        store: An InsightsStore instance.
        course_id: The Canvas course ID string.
        current_run_id: The run_id for the current pipeline run.  Not used in
            the trajectory query (TrajectoryAnalyzer already filters to
            completed runs only) but reserved for future per-run exclusion.

    Returns:
        A formatted multi-line string for injection into the synthesis prompt,
        or ``""`` if insufficient data is available.

    Target length: ~150 tokens.
    """
    try:
        analyzer = TrajectoryAnalyzer(store)
        trajectory: Optional[CourseTrajectory] = analyzer.analyze_course_trajectory(course_id)
    except Exception:
        log.warning(
            "class_trajectory_context: TrajectoryAnalyzer failed for course %s",
            course_id,
            exc_info=True,
        )
        return ""

    # Need at least 2 runs to say anything meaningful
    if trajectory is None or trajectory.run_count < 2:
        return ""

    run_count = trajectory.run_count
    prior_count = run_count - 1  # exclude the current run being analysed

    lines: List[str] = []

    # Header
    week_label = f"week {run_count}"
    prior_label = f"{prior_count} prior run{'s' if prior_count != 1 else ''}"
    lines.append(f"This is {week_label} of analysis for this course ({prior_label}).")
    lines.append("")

    # Engagement trend
    engagement_line = _format_engagement_line(trajectory.engagement_trend)
    if engagement_line:
        lines.append(f"Engagement: {engagement_line}")

    # Exhaustion signals
    exhaustion_line = _format_exhaustion_line(trajectory.exhaustion_trend)
    if exhaustion_line:
        lines.append(f"Exhaustion: {exhaustion_line}")

    # Theme evolution
    themes_line = _format_themes_line(trajectory.theme_evolution, run_count)
    if themes_line:
        lines.append(f"Themes: {themes_line}")

    # Student arc summary
    arc_line = _format_arc_line(trajectory.student_trajectories)
    if arc_line:
        lines.append(f"Student patterns: {arc_line}")

    # If none of the data sections produced output, return empty string
    # (header alone is not useful)
    data_lines = [l for l in lines if l and not l.startswith("This is")]
    if not data_lines:
        return ""

    # Always-present structural framing note
    lines.append("")
    lines.append(
        "Note: When many students show similar shifts simultaneously, that often reflects"
    )
    lines.append("course design or material difficulty rather than individual disengagement.")

    body = "\n".join(lines)
    return (
        "CLASS TRAJECTORY (patterns from prior weeks in this course):\n"
        "---\n"
        f"{body}\n"
        "---"
    )
