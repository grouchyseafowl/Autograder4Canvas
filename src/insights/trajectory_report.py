"""
trajectory_report.py — Per-student longitudinal narrative report generator.

Two-phase architecture:
  Phase 1 (pure Python): Compress N submissions into a fixed-size "semester arc"
    (~800-1200 tokens regardless of assignment count). Extracts theme evolution,
    curated quotes, intellectual threads, engagement patterns, and trajectory
    signals from existing pipeline coding records.
  Phase 2 (LLM call): Generate a narrative report from the arc. The LLM is
    narrating from pre-digested structured data, not re-analysing raw text.

This is a second-order synthesis — it builds on the first-order per-assignment
analyses already in the store. The report generator never sees raw submission
text.

Equity frames active in this module:

  #COMMUNITY_CULTURAL_WEALTH — The report describes what the student has
  BUILT, not what they're lacking. Linguistic repertoire (AAVE, multilingual
  mixing, nonstandard registers) named as features of what the student CAN do.

  #CRIP_TIME — Variable output is described, never pathologised. "variable"
  not "irregular".

  #LANGUAGE_JUSTICE — Non-English submissions noted with original language.
  Monolingual English is not the baseline.

  #TRANSFORMATIVE_JUSTICE — Teacher Notes section is private. "Do not reference
  data or metrics in conversations with students."

  #FEMINIST_TECHNOSCIENCE — No register privileged. Passionate, personal, and
  analytical are all valid modes of engagement.

  #NEURODIVERSITY — Variable engagement patterns described neutrally. No single
  metric defines the student's trajectory.

  #CRITICAL_PEDAGOGY — Inverts the report card model. Narrative of intellectual
  growth, not bank of grades.

  #ALGORITHMIC_JUSTICE — Batch generation must produce genuinely individual
  narratives, not templates with names swapped.

Public API
----------
    generate_trajectory_report(backend, store, student_id, student_name,
                                course_id, course_name, teacher_profile) -> str

    generate_course_trajectory_reports(backend, store, course_id, course_name,
                                       teacher_profile, progress_callback) -> Dict

Returns markdown narrative report, or "" on failure / insufficient data.
"""

from __future__ import annotations

import logging
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from insights.llm_backend import BackendConfig, send_text
from insights.trajectory_context import (
    _classify_word_count_trend,
    _get_wellness_signal,
)

_log = logging.getLogger(__name__)

# Minimum submissions to generate a meaningful trajectory report.
_MIN_SUBMISSIONS = 2

# Maximum quotes to send to the LLM (curated from all assignments).
_MAX_QUOTES = 8

# Maximum number of recent lens_observations to include.
_MAX_LENS_OBS = 4

# Engagement depth ordering for identifying peak assignments.
_DEPTH_ORDER = {"strong": 3, "moderate": 2, "limited": 1, "minimal": 0}


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

def _format_date(iso_ts: str) -> str:
    """Format ISO timestamp as 'Mon DD' (e.g. 'Feb 10')."""
    if not iso_ts:
        return ""
    try:
        ts = iso_ts.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%b %-d")
    except (ValueError, TypeError):
        return ""


def _format_date_range(dates: List[str]) -> str:
    """Format a list of ISO timestamps into a date range string."""
    parsed = []
    for d in dates:
        if not d:
            continue
        try:
            ts = d.strip()
            if ts.endswith("Z"):
                ts = ts[:-1] + "+00:00"
            parsed.append(datetime.fromisoformat(ts))
        except (ValueError, TypeError):
            pass
    if not parsed:
        return ""
    parsed.sort()
    first = parsed[0].strftime("%b %-d, %Y")
    last = parsed[-1].strftime("%b %-d, %Y")
    if first == last:
        return first
    return f"{first} – {last}"


# ---------------------------------------------------------------------------
# Data extraction from a single coding record
# ---------------------------------------------------------------------------

def _get_cr(entry: Dict[str, Any]) -> Dict[str, Any]:
    """Extract the coding_record dict from a history entry."""
    return entry.get("coding_record") or {}


def _extract_quotes(
    cr: Dict[str, Any], assignment: str,
) -> List[Dict[str, str]]:
    """Extract notable quotes from a coding record, tagged with assignment."""
    quotes = cr.get("notable_quotes") or []
    result = []
    for q in quotes:
        if isinstance(q, dict):
            text = q.get("text", "")
            sig = q.get("significance", "")
        elif hasattr(q, "text"):
            text = q.text
            sig = getattr(q, "significance", "")
        else:
            continue
        if text.strip():
            result.append({
                "text": text.strip(),
                "significance": sig.strip(),
                "assignment": assignment,
            })
    return result


def _engagement_score(
    cr: Dict[str, Any],
    teacher_interests: Optional[List[str]] = None,
) -> float:
    """Compute a composite engagement score for ranking assignments.

    Higher = deeper engagement. Used to identify peak assignments, not to
    judge students — every student's "peak" is relative to their own work.

    When teacher_interests are provided, assignments that engage with those
    areas score higher — same data, different emphasis.
    """
    score = 0.0
    es = cr.get("engagement_signals") or {}
    if isinstance(es, dict):
        depth = es.get("engagement_depth", "")
        score += _DEPTH_ORDER.get(depth, 0) * 2  # 0-6

    # Rich quotes = deeper engagement
    quotes = cr.get("notable_quotes") or []
    score += min(len(quotes), 3)  # 0-3

    # Personal connections signal authentic engagement
    personal = cr.get("personal_connections") or []
    score += min(len(personal), 2)  # 0-2

    # Readings referenced = doing the work
    readings = cr.get("readings_referenced") or []
    score += min(len(readings), 2)  # 0-2

    # Concepts applied = intellectual processing
    concepts = cr.get("concepts_applied") or []
    score += min(len(concepts), 2)  # 0-2

    # Teacher profile boost: if teacher priorities are present and this
    # assignment's themes/concepts/readings align, boost the score.
    # Same data, different emphasis — the teacher told us what matters.
    if teacher_interests:
        interests_lower = {i.lower() for i in teacher_interests}
        theme_tags = {t.lower() for t in (cr.get("theme_tags") or [])}
        concepts_lower = {c.lower() for c in concepts}
        readings_lower = {r.lower() for r in readings}
        all_content = theme_tags | concepts_lower | readings_lower
        overlap = all_content & interests_lower
        score += len(overlap) * 1.5  # boost per matching priority

    return score


# ---------------------------------------------------------------------------
# Phase 1: Semester arc builder (pure Python, no LLM)
# ---------------------------------------------------------------------------

def _build_theme_evolution(
    history: List[Dict[str, Any]],
) -> str:
    """Build a compact theme evolution summary.

    Tracks which themes appeared, persisted, faded, or emerged. Uses
    theme_confidence to weight importance.
    """
    # Collect themes per assignment in chronological order
    all_themes: List[Tuple[str, List[str], Dict[str, float]]] = []
    theme_counts: Counter = Counter()
    # Weighted counts: frequency * average confidence for that theme
    theme_weighted: Counter = Counter()
    for entry in history:
        cr = _get_cr(entry)
        tags = cr.get("theme_tags") or []
        confidence = cr.get("theme_confidence") or {}
        assignment = entry.get("assignment_name", "?")
        all_themes.append((assignment, tags, confidence))
        for t in tags:
            t_lower = t.lower()
            theme_counts[t_lower] += 1
            # Weight by confidence: high-confidence tags count more
            conf = confidence.get(t, confidence.get(t_lower, 0.5))
            theme_weighted[t_lower] += conf

    if not theme_counts:
        return "No themes coded across assignments."

    n = len(history)
    parts: List[str] = []

    # Persistent themes: appear in >50% of assignments, ranked by
    # confidence-weighted count (not just raw frequency)
    persistent = [
        t for t, _ in theme_weighted.most_common()
        if theme_counts[t] >= max(2, n // 2)
    ]
    if persistent:
        parts.append(f"Persistent threads: {', '.join(persistent[:5])}")

    # Recent themes (in last 2 assignments but not in first half)
    first_half_themes = set()
    for _, tags, _ in all_themes[: n // 2]:
        first_half_themes.update(t.lower() for t in tags)
    recent_themes = set()
    for _, tags, _ in all_themes[-2:]:
        recent_themes.update(t.lower() for t in tags)
    emerging = recent_themes - first_half_themes
    if emerging:
        parts.append(f"Recently emerging: {', '.join(list(emerging)[:4])}")

    # Fading themes (in first half but not last 2)
    late_themes = set()
    for _, tags, _ in all_themes[-2:]:
        late_themes.update(t.lower() for t in tags)
    fading = first_half_themes - late_themes
    # Only report if they were actually persistent (appeared 2+ times early)
    early_counts: Counter = Counter()
    for _, tags, _ in all_themes[: max(1, n // 2)]:
        for t in tags:
            early_counts[t.lower()] += 1
    fading = {t for t in fading if early_counts.get(t, 0) >= 2}
    if fading:
        parts.append(f"Faded: {', '.join(list(fading)[:3])}")

    return " | ".join(parts) if parts else "Themes varied across assignments."


def _build_intellectual_thread(history: List[Dict[str, Any]]) -> str:
    """Trace the what_student_is_reaching_for across assignments.

    Also incorporates confusion_or_questions to show intellectual curiosity arc.
    """
    reaches: List[str] = []
    questions: List[str] = []
    for entry in history:
        cr = _get_cr(entry)
        r = cr.get("what_student_is_reaching_for")
        if r:
            assignment = entry.get("assignment_name", "")
            reaches.append(f"[{assignment}] {r}")
        q = cr.get("confusion_or_questions")
        if q:
            questions.append(q)

    parts: List[str] = []
    if reaches:
        # Show all — Phase 1 compresses, but intellectual reach is the core arc
        parts.append("Intellectual reach across assignments:")
        for r in reaches:
            parts.append(f"  - {r}")
    if questions:
        parts.append("Questions and confusions across semester:")
        for q in questions:
            parts.append(f"  - {q}")
    return "\n".join(parts)


def _curate_key_quotes(
    history: List[Dict[str, Any]],
) -> str:
    """Select top quotes across the semester.

    Selection criteria: theme_confidence weighting, chronological spread,
    thematic diversity. Returns formatted string for the LLM prompt.
    """
    all_quotes: List[Dict[str, str]] = []
    for entry in history:
        cr = _get_cr(entry)
        assignment = entry.get("assignment_name", "Assignment")
        all_quotes.extend(_extract_quotes(cr, assignment))

    if not all_quotes:
        return "No notable quotes captured across assignments."

    # If we have few enough, include all
    if len(all_quotes) <= _MAX_QUOTES:
        selected = all_quotes
    else:
        # Spread across assignments: take max 2 per assignment, prefer those
        # with significance notes
        by_assignment: Dict[str, List[Dict[str, str]]] = {}
        for q in all_quotes:
            by_assignment.setdefault(q["assignment"], []).append(q)

        selected = []
        # First pass: 1 per assignment (prefer those with significance),
        # but cap at _MAX_QUOTES. When more assignments than slots,
        # spread evenly by taking from chronologically spaced assignments.
        assignments_in_order = list(by_assignment.keys())
        if len(assignments_in_order) > _MAX_QUOTES:
            # Sample evenly across the semester
            step = len(assignments_in_order) / _MAX_QUOTES
            indices = [int(i * step) for i in range(_MAX_QUOTES)]
            assignments_in_order = [assignments_in_order[i] for i in indices]

        for assignment in assignments_in_order:
            if len(selected) >= _MAX_QUOTES:
                break
            quotes = by_assignment[assignment]
            with_sig = [q for q in quotes if q["significance"]]
            selected.append(with_sig[0] if with_sig else quotes[0])

        # Second pass: fill up to _MAX_QUOTES from remaining
        used_texts = {q["text"] for q in selected}
        for q in all_quotes:
            if len(selected) >= _MAX_QUOTES:
                break
            if q["text"] not in used_texts:
                selected.append(q)
                used_texts.add(q["text"])

    lines = ["Key quotes across the semester:"]
    for q in selected:
        line = f'  - "{q["text"]}" [{q["assignment"]}]'
        if q["significance"]:
            line += f" — {q['significance']}"
        lines.append(line)
    return "\n".join(lines)


def _build_engagement_patterns(
    history: List[Dict[str, Any]],
    teacher_interests: Optional[List[str]] = None,
) -> str:
    """Analyze intellectual mode responsiveness and thematic engagement rhythm.

    Not "essay vs discussion" but what KIND of thinking sparks this student.
    Connected to themes present at engagement peaks.

    When teacher_interests are provided, assignments aligned with teacher
    priorities score higher in the peak ranking — same data, different emphasis.
    """
    # Score each assignment and gather context
    scored: List[Tuple[float, str, Dict[str, Any]]] = []
    for entry in history:
        cr = _get_cr(entry)
        assignment = entry.get("assignment_name", "?")
        score = _engagement_score(cr, teacher_interests=teacher_interests)
        scored.append((score, assignment, cr))

    if not scored:
        return ""

    scored.sort(key=lambda x: x[0], reverse=True)
    parts: List[str] = []

    # Identify what's present on peak assignments
    top_n = min(3, max(1, len(scored) // 3))
    peaks = scored[:top_n]
    bottom_n = min(2, max(1, len(scored) // 3))
    valleys = scored[-bottom_n:] if len(scored) > top_n else []

    # What intellectual modes are present at peaks?
    peak_modes: List[str] = []
    peak_themes: List[str] = []
    for _score, assignment, cr in peaks:
        personal = cr.get("personal_connections") or []
        readings = cr.get("readings_referenced") or []
        concepts = cr.get("concepts_applied") or []
        events = cr.get("current_events_referenced") or []
        register = cr.get("emotional_register", "")

        if personal:
            peak_modes.append("personal-to-theory connection")
        if readings:
            peak_modes.append("textual analysis")
        if concepts:
            peak_modes.append("conceptual application")
        if events:
            peak_modes.append("current events engagement")
        if register in ("passionate", "urgent"):
            peak_modes.append("emotionally invested work")
        if register == "analytical":
            peak_modes.append("analytical reasoning")

        for t in (cr.get("theme_tags") or []):
            peak_themes.append(t)

    # Deduplicate while preserving order
    seen = set()
    unique_modes = []
    for m in peak_modes:
        if m not in seen:
            unique_modes.append(m)
            seen.add(m)

    if unique_modes:
        parts.append(
            f"Intellectual modes at engagement peaks: {', '.join(unique_modes[:5])}"
        )
        peak_names = [a for _, a, _ in peaks]
        parts.append(f"Strongest work in: {', '.join(peak_names)}")

    if peak_themes:
        theme_counts = Counter(t.lower() for t in peak_themes)
        top_themes = [t for t, _ in theme_counts.most_common(3)]
        parts.append(f"Themes at peaks: {', '.join(top_themes)}")

    # Emotional notes at peaks — richer than register label alone
    peak_emotional_notes: List[str] = []
    for _score, assignment, cr in peaks:
        enotes = cr.get("emotional_notes")
        if enotes:
            peak_emotional_notes.append(f"[{assignment}] {enotes}")
    if peak_emotional_notes:
        parts.append(
            "What's at stake at peaks:\n"
            + "\n".join(f"  - {n}" for n in peak_emotional_notes[:3])
        )

    # Engagement rhythm: temporal pattern
    n = len(history)
    if n >= 4:
        first_half_scores = [_engagement_score(_get_cr(e)) for e in history[: n // 2]]
        second_half_scores = [_engagement_score(_get_cr(e)) for e in history[n // 2 :]]
        first_avg = sum(first_half_scores) / len(first_half_scores) if first_half_scores else 0
        second_avg = sum(second_half_scores) / len(second_half_scores) if second_half_scores else 0

        if second_avg > first_avg * 1.3:
            parts.append("Engagement rhythm: building momentum across the semester")
        elif first_avg > second_avg * 1.3:
            parts.append("Engagement rhythm: strong start, more variable later")
        else:
            parts.append("Engagement rhythm: relatively consistent across semester")

    return "\n".join(parts)


def _build_strengths_trajectory(history: List[Dict[str, Any]]) -> str:
    """Track developing strengths: linguistic repertoire, register range."""
    early_assets: set = set()
    late_assets: set = set()
    all_registers: List[str] = []
    n = len(history)

    for i, entry in enumerate(history):
        cr = _get_cr(entry)
        assets = cr.get("linguistic_assets") or []
        register = cr.get("emotional_register", "")

        if i < n // 2:
            early_assets.update(a for a in assets)
        else:
            late_assets.update(a for a in assets)

        if register:
            all_registers.append(register)

    parts: List[str] = []

    # Repertoire growth
    new_assets = late_assets - early_assets
    if new_assets:
        parts.append(
            f"Linguistic repertoire expanded: {', '.join(sorted(new_assets))} "
            f"appeared in later work"
        )
    if early_assets & late_assets:
        consistent = early_assets & late_assets
        parts.append(f"Consistent repertoire features: {', '.join(sorted(consistent))}")

    # Register range
    unique_registers = list(dict.fromkeys(all_registers))
    if len(unique_registers) >= 3:
        parts.append(f"Register range across semester: {', '.join(unique_registers)}")
    elif len(unique_registers) == 1:
        parts.append(f"Consistent register: {unique_registers[0]}")

    return "\n".join(parts)


def _build_world_connections(history: List[Dict[str, Any]]) -> str:
    """Track current_events_referenced across semester — the student's
    'intellectual address' (where they think from in the world)."""
    events: List[Tuple[str, List[str]]] = []
    for entry in history:
        cr = _get_cr(entry)
        refs = cr.get("current_events_referenced") or []
        if refs:
            assignment = entry.get("assignment_name", "?")
            events.append((assignment, refs))

    if not events:
        return ""

    parts = ["World connections across semester:"]
    for assignment, refs in events:
        parts.append(f"  - [{assignment}] {', '.join(refs[:3])}")
    return "\n".join(parts)


def _build_wellbeing_arc(history: List[Dict[str, Any]]) -> str:
    """Summarize wellbeing trajectory and word count trend."""
    signals = []
    word_counts = []
    for entry in history:
        cr = _get_cr(entry)
        ws = _get_wellness_signal(cr)
        if ws:
            signals.append(ws)
        wc = cr.get("word_count")
        if wc is not None and wc > 0:
            word_counts.append(wc)

    parts: List[str] = []

    if word_counts:
        trend = _classify_word_count_trend(word_counts)
        avg_wc = round(sum(word_counts) / len(word_counts))
        parts.append(f"Word count trend: {trend} (avg {avg_wc})")

    if signals:
        unique = list(dict.fromkeys(signals))
        if len(unique) == 1:
            parts.append(f"Wellbeing: {unique[0]} throughout")
        else:
            parts.append(f"Wellbeing arc: {' → '.join(unique)}")

    return " | ".join(parts)


def _build_lens_observations(history: List[Dict[str, Any]]) -> str:
    """Extract teacher-configured lens observations across assignments."""
    obs: List[Tuple[str, Dict[str, str]]] = []
    for entry in history:
        cr = _get_cr(entry)
        lens = cr.get("lens_observations")
        if lens and isinstance(lens, dict):
            assignment = entry.get("assignment_name", "?")
            obs.append((assignment, lens))

    if not obs:
        return ""

    # Take most recent lens observations (these are teacher-configured)
    recent = obs[-_MAX_LENS_OBS:]
    parts = ["Teacher lens observations:"]
    for assignment, lens_dict in recent:
        for lens_name, observation in lens_dict.items():
            if observation:
                parts.append(f"  - [{assignment}] {lens_name}: {observation}")
    return "\n".join(parts) if len(parts) > 1 else ""


def _build_prior_feedback_note(history: List[Dict[str, Any]]) -> str:
    """Note what feedback was previously generated for this student.

    Helps the LLM avoid repeating suggestions and notice when the student
    acted on prior feedback.
    """
    feedback: List[Tuple[str, str]] = []
    for entry in history:
        cr = _get_cr(entry)
        fb = cr.get("draft_feedback")
        if fb:
            assignment = entry.get("assignment_name", "?")
            # Truncate to first 100 chars to save tokens
            feedback.append((assignment, fb[:100]))

    if not feedback:
        return ""

    parts = ["Prior feedback generated:"]
    for assignment, fb in feedback[-3:]:  # last 3 only
        parts.append(f"  - [{assignment}] {fb}")
    parts.append("(Avoid repeating; note if student acted on prior feedback.)")
    return "\n".join(parts)


def _build_integrity_signals(history: List[Dict[str, Any]]) -> str:
    """Surface longitudinal integrity pattern shifts in a structural frame.

    Delta-from-self only. Framed as pattern observation, never accusation.
    The teacher interprets — they know their student.
    """
    z_scores: List[Tuple[str, float]] = []
    # Track formulaic: only flag as shift if it was ABSENT in earlier work
    # and then APPEARED later. Present from the start = pre-existing style.
    seen_non_formulaic = False
    formulaic_shift = False

    for entry in history:
        cr = _get_cr(entry)
        assignment = entry.get("assignment_name", "?")

        z = cr.get("cohort_z_score")
        if z is not None:
            z_scores.append((assignment, z))

        assets = cr.get("linguistic_assets") or []
        has_formulaic = "formulaic_essay_structure" in assets
        if not has_formulaic:
            seen_non_formulaic = True
        elif has_formulaic and seen_non_formulaic:
            formulaic_shift = True

    parts: List[str] = []

    # Z-score divergence from self
    if len(z_scores) >= 3:
        values = [z for _, z in z_scores]
        early_avg = sum(values[: len(values) // 2]) / max(1, len(values) // 2)
        late_avg = sum(values[len(values) // 2 :]) / max(1, len(values) - len(values) // 2)
        if abs(late_avg - early_avg) > 1.0:
            direction = "toward" if late_avg > early_avg else "away from"
            parts.append(
                f"Writing pattern shifted {direction} class norms in later assignments"
            )

    if formulaic_shift:
        parts.append(
            "Formulaic essay structure appeared in later work "
            "(not present in earlier submissions)"
        )

    if not parts:
        return ""
    return "Integrity pattern note: " + ". ".join(parts) + "."


def _build_cluster_trajectory(history: List[Dict[str, Any]]) -> str:
    """Track movement between thematic clusters across assignments."""
    clusters: List[Tuple[str, Optional[int]]] = []
    for entry in history:
        cr = _get_cr(entry)
        cid = cr.get("cluster_id")
        assignment = entry.get("assignment_name", "?")
        clusters.append((assignment, cid))

    valid = [(a, c) for a, c in clusters if c is not None]
    if len(valid) < 2:
        return ""

    unique_clusters = set(c for _, c in valid)
    if len(unique_clusters) == 1:
        return "Thematic positioning: consistently in same cluster (depth)"
    else:
        return f"Thematic positioning: moved across {len(unique_clusters)} clusters (range)"


def build_semester_arc(
    history: List[Dict[str, Any]],
    teacher_profile: Optional[Dict[str, Any]] = None,
) -> str:
    """Phase 1: Build a fixed-size semester arc from N submission records.

    Pure Python — no LLM. Compresses any number of submissions into ~800-1200
    tokens for the LLM narrative generation call.

    Parameters
    ----------
    history : List[Dict]
        From get_student_history(). Chronological.
    teacher_profile : Optional[Dict]
        TeacherAnalysisProfile data. Shapes emphasis.

    Returns
    -------
    str
        Structured arc text for the LLM prompt.
    """
    sections: List[str] = []

    # Theme evolution
    themes = _build_theme_evolution(history)
    if themes:
        sections.append(themes)

    # Intellectual thread (reaching_for + confusion_or_questions)
    thread = _build_intellectual_thread(history)
    if thread:
        sections.append(thread)

    # Curated quotes
    quotes = _curate_key_quotes(history)
    if quotes:
        sections.append(quotes)

    # Engagement patterns (intellectual mode + thematic rhythm)
    # Teacher interests re-weight which assignments count as "peaks"
    teacher_interests = None
    if teacher_profile:
        teacher_interests = teacher_profile.get("interest_areas")
    engagement = _build_engagement_patterns(
        history, teacher_interests=teacher_interests,
    )
    if engagement:
        sections.append(engagement)

    # World connections (current_events_referenced)
    world = _build_world_connections(history)
    if world:
        sections.append(world)

    # Developing strengths (repertoire + register range)
    strengths = _build_strengths_trajectory(history)
    if strengths:
        sections.append(strengths)

    # Wellbeing arc + word count trend
    wellbeing = _build_wellbeing_arc(history)
    if wellbeing:
        sections.append(wellbeing)

    # Cluster trajectory
    clusters = _build_cluster_trajectory(history)
    if clusters:
        sections.append(clusters)

    # Lens observations (teacher-configured)
    lens = _build_lens_observations(history)
    if lens:
        sections.append(lens)

    # Prior feedback (for growth edges — don't repeat)
    feedback = _build_prior_feedback_note(history)
    if feedback:
        sections.append(feedback)

    # Integrity signals (for Teacher Notes)
    integrity = _build_integrity_signals(history)
    if integrity:
        sections.append(integrity)

    # Teacher profile emphasis
    if teacher_profile:
        profile_parts: List[str] = []
        interest_areas = teacher_profile.get("interest_areas") or []
        if interest_areas:
            profile_parts.append(
                f"Teacher priorities for this course: {', '.join(interest_areas)}"
            )
        subject = teacher_profile.get("subject_area", "")
        if subject and subject != "general":
            profile_parts.append(f"Subject area: {subject}")
        custom_strengths = teacher_profile.get("custom_strength_patterns") or []
        if custom_strengths:
            profile_parts.append(
                f"Strengths to surface: {', '.join(custom_strengths[:4])}"
            )
        if profile_parts:
            sections.append("Teacher profile:\n" + "\n".join(profile_parts))

    return "\n\n".join(sections)


# ---------------------------------------------------------------------------
# Preamble builder (non-LLM, factual header)
# ---------------------------------------------------------------------------

def build_preamble(
    student_name: str,
    course_name: str,
    history: List[Dict[str, Any]],
    all_course_assignments: Optional[List[str]] = None,
    generated_at: Optional[str] = None,
    model_name: str = "",
) -> str:
    """Build the factual report header. No LLM — no hallucination risk.

    Parameters
    ----------
    all_course_assignments : list of str, optional
        All assignment names in this course (from runs table). When provided,
        the preamble discloses which assignments are covered and which aren't.
    """
    lines: List[str] = []
    lines.append(f"# Semester Summary: {student_name}")
    if course_name:
        lines.append(f"**Course:** {course_name}")

    # Date range
    dates = [e.get("started_at", "") for e in history]
    date_range = _format_date_range(dates)
    if date_range:
        lines.append(f"**Period:** {date_range}")

    # Assignment coverage
    covered_assignments = [e.get("assignment_name", "?") for e in history]
    covered_count = len(covered_assignments)

    if all_course_assignments:
        total = len(all_course_assignments)
        lines.append(f"**Coverage:** {covered_count} of {total} assignments analyzed")
        missing = [a for a in all_course_assignments if a not in covered_assignments]
        if missing:
            lines.append(f"**Not included:** {', '.join(missing)}")
    else:
        lines.append(f"**Assignments analyzed:** {covered_count}")

    if generated_at:
        gen_date = _format_date(generated_at)
        if gen_date:
            note = f"**Generated:** {gen_date}"
            if model_name:
                note += f" ({model_name})"
            lines.append(note)

    lines.append("")  # blank line before narrative
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def _get_course_assignment_names(
    store: Any, course_id: str,
) -> List[str]:
    """Get all unique assignment names for a course from the runs table."""
    try:
        runs = store.get_runs(course_id=course_id)
        names = []
        seen = set()
        for r in runs:
            name = r.get("assignment_name", "")
            if name and name not in seen:
                names.append(name)
                seen.add(name)
        return names
    except Exception:
        return []


def _get_course_student_list(
    store: Any, course_id: str,
) -> List[Dict[str, str]]:
    """Get all unique students across completed runs in a course.

    Returns list of {"student_id": ..., "student_name": ...}.
    """
    try:
        runs = store.get_runs(course_id=course_id)
        completed_run_ids = [
            r["run_id"] for r in runs if r.get("completed_at")
        ]
        students: Dict[str, str] = {}  # id → name
        for run_id in completed_run_ids:
            codings = store.get_codings(run_id)
            for c in codings:
                sid = c.get("student_id", "")
                sname = c.get("student_name", "")
                if sid and sid not in students:
                    students[sid] = sname
        return [
            {"student_id": sid, "student_name": sname}
            for sid, sname in sorted(students.items(), key=lambda x: x[1])
        ]
    except Exception as e:
        _log.warning("Failed to get course student list: %s", e)
        return []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_trajectory_report(
    backend: BackendConfig,
    store: Any,  # InsightsStore
    student_id: str,
    student_name: str,
    course_id: str,
    course_name: str = "",
    *,
    teacher_profile: Optional[Dict[str, Any]] = None,
    max_tokens: int = 1500,
) -> str:
    """Generate an asset-framed narrative trajectory report for one student.

    Two-phase: Phase 1 builds a fixed-size semester arc from all submissions
    (pure Python). Phase 2 sends the arc to the LLM for narrative generation.

    Parameters
    ----------
    backend : BackendConfig
        LLM backend for narrative generation.
    store : InsightsStore
        Database handle.
    student_id : str
        Canvas user ID.
    student_name : str
        Display name.
    course_id : str
        Canvas course ID.
    course_name : str
        Human-readable course name.
    teacher_profile : dict, optional
        TeacherAnalysisProfile data for course-specific emphasis.
    max_tokens : int
        Token limit for the LLM response.

    Returns
    -------
    str
        Markdown report (preamble + narrative), or "" if insufficient data.
    """
    from insights.prompts import (
        TRAJECTORY_REPORT_SYSTEM_PROMPT,
        TRAJECTORY_REPORT_PROMPT,
    )

    # Fetch all completed submissions for this student in this course
    history = store.get_student_history(student_id, course_id)

    if len(history) < _MIN_SUBMISSIONS:
        _log.info(
            "Trajectory report skipped for %s: only %d submission(s)",
            student_name, len(history),
        )
        return ""

    # Phase 1: Build fixed-size semester arc
    arc = build_semester_arc(history, teacher_profile=teacher_profile)

    # Build non-LLM preamble
    all_assignments = _get_course_assignment_names(store, course_id)
    preamble = build_preamble(
        student_name=student_name,
        course_name=course_name,
        history=history,
        all_course_assignments=all_assignments if all_assignments else None,
        model_name=backend.model,
    )

    # Phase 2: LLM narrative generation from the arc
    prompt = TRAJECTORY_REPORT_PROMPT.format(
        student_name=student_name,
        course_name=course_name or "this course",
        submission_count=len(history),
        semester_arc=arc,
    )

    try:
        narrative = send_text(
            backend,
            prompt,
            system_prompt=TRAJECTORY_REPORT_SYSTEM_PROMPT,
            max_tokens=max_tokens,
        )
    except Exception as e:
        _log.error(
            "Trajectory report generation failed for %s: %s", student_name, e,
        )
        return ""

    if not narrative or not narrative.strip():
        _log.warning("Trajectory report empty for %s", student_name)
        return ""

    return preamble + narrative.strip() + "\n"


def generate_course_trajectory_reports(
    backend: BackendConfig,
    store: Any,  # InsightsStore
    course_id: str,
    course_name: str = "",
    *,
    teacher_profile: Optional[Dict[str, Any]] = None,
    max_tokens: int = 1500,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
) -> Dict[str, str]:
    """Generate trajectory reports for all students in a course (batch mode).

    Parameters
    ----------
    progress_callback : callable, optional
        Called with (student_name, current_index, total) for progress UI.

    Returns
    -------
    Dict[str, str]
        Mapping of student_id → report text. Empty string for students
        with insufficient data.
    """
    students = _get_course_student_list(store, course_id)
    total = len(students)
    results: Dict[str, str] = {}

    for i, student in enumerate(students):
        sid = student["student_id"]
        sname = student["student_name"]

        if progress_callback:
            progress_callback(sname, i + 1, total)

        report = generate_trajectory_report(
            backend=backend,
            store=store,
            student_id=sid,
            student_name=sname,
            course_id=course_id,
            course_name=course_name,
            teacher_profile=teacher_profile,
            max_tokens=max_tokens,
        )

        results[sid] = report

        # Save to store
        if report:
            try:
                store.save_trajectory_report(
                    student_id=sid,
                    course_id=course_id,
                    student_name=sname,
                    report_text=report,
                    model_name=backend.model,
                )
            except Exception as e:
                _log.warning("Failed to save trajectory report for %s: %s", sname, e)

    return results
