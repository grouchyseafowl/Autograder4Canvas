"""
trajectory_context.py — Per-student trajectory context builder.

Builds a compact context block that is injected into the observation prompt
so the LLM sees this submission against the student's own prior pattern in the
same course. Compare-to-self, never compare-to-cohort.

Equity frames active in this module:

  #CRIP_TIME — Variable output is described, never pathologised. "variable" not
  "irregular". Variable output is normal for neurodivergent students, working
  students, and students with care responsibilities.

  #COMMUNITY_CULTURAL_WEALTH — Unknown-word-rate signal is suppressed when
  linguistic assets are increasing. A student bringing more authentic voice is
  not declining.

  #LANGUAGE_JUSTICE — English word count is not a proxy for engagement. When
  preprocessing shows a non-English original language, a note is added so the
  teacher reads word count changes in context.

  #FEMINIST_TECHNOSCIENCE — Attachment-only submissions (word_count==0 but
  preprocessing present) are included as "attachment submission", not omitted as
  zero-output failures.

  #ALGORITHMIC_JUSTICE / #NEURODIVERSITY — Multi-signal requirement: a pattern
  break requires 2+ simultaneous signal shifts. A single metric changing is
  NEVER labelled as a pattern break.

  #ETHNIC_STUDIES — Register shifts are described neutrally. No register is
  "better" or "worse". Passionate→analytical reflects material, not disengagement.

  #TRANSFORMATIVE_JUSTICE — Output is teacher-facing only. No data should be
  referenced when speaking with students. That disclaimer lives in the synthesis
  prompt (Phase D), not in this module.

Public API
----------
    build_trajectory_context(store, student_id, course_id, current_run_id,
                             current_word_count, current_submitted_at) -> str

Returns "" when there are no prior submissions.
Returns a compact ~200-token text block when prior submissions exist.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

_log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Engagement depth ordering — used for decline detection
_DEPTH_ORDER = {"strong": 3, "moderate": 2, "limited": 1, "minimal": 0}

# Registers that count as "disengaged" for the disengagement signal
_DISENGAGED_REGISTERS = {"disengaged"}

# Maximum number of prior submissions shown with full detail lines
_MAX_DETAIL_LINES = 3

# Relative slope thresholds (copied from trajectory.py _classify_trend)
_SLOPE_INCREASING = 0.08
_SLOPE_DECREASING = -0.08
_CV_VARIABLE = 0.5

# Hour-of-day range considered late-night (inclusive)
_LATE_NIGHT_START = 22   # 10 PM
_LATE_NIGHT_END = 4      # 4 AM (wraps midnight)

# Hours outside median before submission-time shift is flagged
_TIME_SHIFT_HOURS = 4.0

# Variance threshold: if student's prior hours span more than this, skip time signal
_HIGH_TIME_VARIANCE_HOURS = 4.0

# Unknown-word-rate multiplier for "spiking" signal
_UWR_SPIKE_MULTIPLIER = 2.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _classify_word_count_trend(word_counts: List[Optional[int]]) -> str:
    """Classify a word-count sequence as steady/increasing/decreasing/variable.

    Copied and adapted from TrajectoryAnalyzer._classify_trend() in trajectory.py.
    Label changes from the original:
      "improving"  → "increasing"
      "declining"  → "decreasing"
      "irregular"  → "variable"   (#CRIP_TIME — description, not deficit)

    Same numeric thresholds: rel_slope ±0.08, CV > 0.5.
    """
    valid = [(i, wc) for i, wc in enumerate(word_counts) if wc is not None and wc > 0]
    if len(valid) < 2:
        return "variable"

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

    if mean_y == 0:
        return "steady"
    rel_slope = slope / mean_y

    if rel_slope > _SLOPE_INCREASING:
        return "increasing"
    if rel_slope < _SLOPE_DECREASING:
        return "decreasing"

    # Check variance for variability
    values = [wc for _, wc in valid]
    mean_v = sum(values) / len(values)
    variance = sum((v - mean_v) ** 2 for v in values) / len(values)
    cv = (variance ** 0.5) / mean_v if mean_v > 0 else 0
    if cv > _CV_VARIABLE:
        return "variable"

    return "steady"


def _get_wellness_signal(coding_record: Dict[str, Any]) -> Optional[str]:
    """Return best-available wellness signal from a coding record dict.

    Primary path: wellbeing_axis field (CRISIS|BURNOUT|ENGAGED|NONE).
    Fallback for older records that pre-date wellbeing_axis: len(concerns).

    Returns None when neither field is present or meaningful.
    """
    wellbeing = coding_record.get("wellbeing_axis")
    if wellbeing is not None:
        return str(wellbeing)

    concerns = coding_record.get("concerns")
    if concerns is not None:
        count = len(concerns) if isinstance(concerns, list) else 0
        return f"{count} concern{'s' if count != 1 else ''}"

    return None


def _parse_hour(iso_ts: str) -> Optional[float]:
    """Extract fractional hour-of-day from an ISO 8601 timestamp string.

    Returns None on parse failure. Handles timestamps with or without timezone.
    """
    if not iso_ts:
        return None
    try:
        # Strip trailing Z or +00:00 style suffixes for fromisoformat compat
        ts = iso_ts.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.hour + dt.minute / 60.0
    except (ValueError, TypeError):
        return None


def _analyze_submission_time(
    prior_timestamps: List[str],
    current_timestamp: str,
) -> Tuple[str, bool]:
    """Analyze submission time patterns.

    Returns (description, is_shifted) where:
      - description: human-readable time pattern summary (always non-empty)
      - is_shifted: True only when current submission is detectably outside the
        student's own established window AND lands in late-night range

    Rules (#CRIP_TIME guardrail):
    - Need 2+ parseable prior timestamps to establish a pattern.
    - If prior hours vary by more than _HIGH_TIME_VARIANCE_HOURS: student has a
      variable schedule → return ("variable submission times", False).
    - If student ALWAYS submits late-night: that is their pattern → no shift.
    - Shift requires: current is 4+ hours outside median AND in late-night range
      while typical is daytime. A student whose pattern IS late-night is not flagged.
    """
    prior_hours = [_parse_hour(ts) for ts in prior_timestamps]
    prior_hours = [h for h in prior_hours if h is not None]

    if len(prior_hours) < 2:
        return ("", False)

    median_hour = sorted(prior_hours)[len(prior_hours) // 2]

    # Detect student whose entire pattern is late-night
    def _is_late_night(h: float) -> bool:
        return h >= _LATE_NIGHT_START or h < _LATE_NIGHT_END

    all_late_night = all(_is_late_night(h) for h in prior_hours)
    if all_late_night:
        return ("typically submits late evening", False)

    # Detect high-variance schedule (working student, variable responsibilities)
    prior_range = max(prior_hours) - min(prior_hours)
    # Handle wrap-around midnight for range calculation
    if prior_range > 12:
        prior_range = 24 - prior_range
    if prior_range > _HIGH_TIME_VARIANCE_HOURS:
        return ("variable submission times", False)

    # Build typical window description from median
    def _hour_label(h: float) -> str:
        if 5 <= h < 12:
            return "morning"
        if 12 <= h < 17:
            return "mid-afternoon" if 13 <= h < 16 else "afternoon"
        if 17 <= h < 20:
            return "evening"
        return "late evening"

    description = f"typically submits {_hour_label(median_hour)}"

    current_hour = _parse_hour(current_timestamp)
    if current_hour is None:
        return (description, False)

    # Compute circular distance between hours
    raw_diff = abs(current_hour - median_hour)
    diff = min(raw_diff, 24 - raw_diff)

    is_shifted = diff >= _TIME_SHIFT_HOURS and _is_late_night(current_hour) and not _is_late_night(median_hour)

    return (description, is_shifted)


def _detect_pattern_break(
    prior_records: List[Dict[str, Any]],
    current_word_count: int,
    current_submitted_at: str,
    current_engagement_depth: Optional[str],
    current_unknown_word_rate: float,
    current_linguistic_assets: List[str],
    current_theme_tags: List[str],
    current_register: str,
    prior_timestamps: List[str],
    current_personal_connections: Optional[List[str]] = None,
    current_readings_referenced: Optional[List[str]] = None,
) -> Tuple[bool, int]:
    """Check ten signals for a multi-signal pattern break.

    Returns (is_break, signal_count). A pattern break requires 2+ signals.
    A single-signal shift is NEVER flagged (#ALGORITHMIC_JUSTICE, #NEURODIVERSITY).

    Signals:
      1. word_count_decreasing — trend == "decreasing"
      2. register_to_disengaged — 2+ consecutive prior registers are "disengaged"
         AND current is also "disengaged"
      3. submission_time_shifted — current outside typical window (2+ prior times needed)
      4. wellness_shifting — wellbeing_axis moved toward distress OR concern count
         increasing across prior records
      5. engagement_depth_declining — shifted strong/moderate → limited/minimal
         across 2+ prior records
      6. unknown_word_rate_spiking — current >2x student avg, sustained over 2+
         prior records. SUPPRESSED when linguistic_assets also increasing
         (#COMMUNITY_CULTURAL_WEALTH).
      7. theme_continuity_dropped — current shares 0 tags with union of all prior
         tags AND student had established themes (prior union non-empty)
      8. personal_connections_vanished — student had consistent personal connections
         (avg ≥1 across priors) but current has 0 ("going through the motions")
      9. readings_disappeared — student referenced readings consistently (avg ≥1
         across priors) but current has 0 ("stopped doing the readings")
     10. formulaic_shift — student gained formulaic_essay_structure in linguistic
         assets when they didn't have it before (possible safety loss or AI shift)
    """
    signals: List[bool] = []

    word_counts = [r.get("word_count") for r in prior_records]
    word_counts.append(current_word_count if current_word_count > 0 else None)

    # ---- Signal 1: word count decreasing ----
    trend = _classify_word_count_trend(word_counts)
    signals.append(trend == "decreasing")

    # ---- Signal 2: register → sustained disengaged ----
    # Require: last 2 prior registers are disengaged AND current is too
    prior_registers = [r.get("emotional_register", "") for r in prior_records[-2:]]
    sig2 = (
        len(prior_registers) >= 2
        and all(reg in _DISENGAGED_REGISTERS for reg in prior_registers)
        and current_register in _DISENGAGED_REGISTERS
    )
    signals.append(sig2)

    # ---- Signal 3: submission time shifted ----
    _time_desc, time_shifted = _analyze_submission_time(prior_timestamps, current_submitted_at)
    signals.append(time_shifted)

    # ---- Signal 4: wellness shifting ----
    _WELLNESS_PRIORITY = {"CRISIS": 0, "BURNOUT": 1, "ENGAGED": 2, "NONE": 3}
    wellness_signals = [_get_wellness_signal(r) for r in prior_records]
    wellness_signals_clean = [w for w in wellness_signals if w is not None]
    sig4 = False
    if len(wellness_signals_clean) >= 2:
        # Check for ENGAGED → BURNOUT/CRISIS transition in recent records
        axis_values = []
        for r in prior_records:
            w = r.get("wellbeing_axis")
            if w in _WELLNESS_PRIORITY:
                axis_values.append(_WELLNESS_PRIORITY[w])
        if len(axis_values) >= 2:
            # Lower number = worse wellbeing; a decreasing sequence is bad
            sig4 = axis_values[-1] < axis_values[0]
        else:
            # Fallback: concern count increasing
            concern_counts = []
            for r in prior_records:
                c = r.get("concerns")
                if c is not None:
                    concern_counts.append(len(c) if isinstance(c, list) else 0)
            if len(concern_counts) >= 2:
                sig4 = concern_counts[-1] > concern_counts[0]
    signals.append(sig4)

    # ---- Signal 5: engagement depth declining ----
    depth_values = []
    for r in prior_records:
        es = r.get("engagement_signals") or {}
        d = es.get("engagement_depth") if isinstance(es, dict) else None
        if d in _DEPTH_ORDER:
            depth_values.append(_DEPTH_ORDER[d])
    if current_engagement_depth and current_engagement_depth in _DEPTH_ORDER:
        depth_values.append(_DEPTH_ORDER[current_engagement_depth])
    sig5 = False
    if len(depth_values) >= 3:
        # Require: prior average strong/moderate, current limited/minimal
        prior_avg = sum(depth_values[:-1]) / len(depth_values[:-1])
        current_d = depth_values[-1]
        sig5 = prior_avg >= 2.0 and current_d <= 1
    signals.append(sig5)

    # ---- Signal 6: unknown word rate spiking (suppressed if linguistic assets rising) ----
    prior_uwr = [r.get("unknown_word_rate", 0.0) for r in prior_records]
    prior_uwr_valid = [x for x in prior_uwr if isinstance(x, (int, float)) and x > 0]
    sig6 = False
    if len(prior_uwr_valid) >= 2 and current_unknown_word_rate > 0:
        avg_prior_uwr = sum(prior_uwr_valid) / len(prior_uwr_valid)
        rate_spiking = current_unknown_word_rate > _UWR_SPIKE_MULTIPLIER * avg_prior_uwr

        # #COMMUNITY_CULTURAL_WEALTH: suppress when linguistic assets increasing
        prior_asset_counts = [
            len(r.get("linguistic_assets", []) or []) for r in prior_records
        ]
        assets_increasing = (
            len(prior_asset_counts) >= 2
            and prior_asset_counts[-1] > prior_asset_counts[0]
        ) or (
            len(current_linguistic_assets) > (prior_asset_counts[-1] if prior_asset_counts else 0)
        )

        sig6 = rate_spiking and not assets_increasing
    signals.append(sig6)

    # ---- Signal 7: theme continuity dropped ----
    prior_theme_union: set = set()
    for r in prior_records:
        tags = r.get("theme_tags") or []
        if isinstance(tags, list):
            prior_theme_union.update(t.lower() for t in tags)
    current_themes_lower = {t.lower() for t in (current_theme_tags or [])}
    sig7 = (
        bool(prior_theme_union)
        and bool(current_themes_lower)
        and len(current_themes_lower & prior_theme_union) == 0
    )
    signals.append(sig7)

    # ---- Signal 8: personal connections vanished ("going through the motions") ----
    # Student had consistent personal connections but current has none.
    # This catches the student who keeps writing but stops bringing themselves.
    prior_pc_counts = [
        len(r.get("personal_connections") or []) for r in prior_records
    ]
    valid_pc = [c for c in prior_pc_counts if c > 0]
    current_pc = current_personal_connections or []
    sig8 = (
        len(valid_pc) >= 2  # had connections in 2+ prior submissions
        and sum(prior_pc_counts) / max(len(prior_pc_counts), 1) >= 1.0  # avg ≥ 1
        and len(current_pc) == 0  # current has none
    )
    signals.append(sig8)

    # ---- Signal 9: readings disappeared ----
    # Student referenced readings consistently but stopped entirely.
    prior_rr_counts = [
        len(r.get("readings_referenced") or []) for r in prior_records
    ]
    valid_rr = [c for c in prior_rr_counts if c > 0]
    current_rr = current_readings_referenced or []
    sig9 = (
        len(valid_rr) >= 2  # referenced readings in 2+ prior submissions
        and sum(prior_rr_counts) / max(len(prior_rr_counts), 1) >= 1.0  # avg ≥ 1
        and len(current_rr) == 0  # current has none
    )
    signals.append(sig9)

    # ---- Signal 10: formulaic shift ----
    # Student gained formulaic_essay_structure asset when they didn't have it
    # before. Could indicate lost safety or AI outsourcing.
    prior_had_formulaic = any(
        "formulaic_essay_structure" in (r.get("linguistic_assets") or [])
        for r in prior_records
    )
    current_has_formulaic = "formulaic_essay_structure" in current_linguistic_assets
    sig10 = current_has_formulaic and not prior_had_formulaic and len(prior_records) >= 2
    signals.append(sig10)

    signal_count = sum(signals)
    return (signal_count >= 2, signal_count)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _format_date(run_started_at: str) -> str:
    """Format ISO timestamp as 'Mon DD' (e.g. 'Feb 10')."""
    if not run_started_at:
        return "?"
    try:
        ts = run_started_at.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%b %-d")
    except (ValueError, TypeError):
        return "?"


def _format_time(iso_ts: str) -> str:
    """Format ISO timestamp as 12-hour time, e.g. '3:15 PM'."""
    if not iso_ts:
        return ""
    try:
        ts = iso_ts.strip()
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%-I:%M %p")
    except (ValueError, TypeError):
        return ""


def _describe_word_count_pattern(word_counts: List[int], avg: int) -> str:
    """Build a narrative word count description that detects inflection points.

    Instead of a single slope label across all history, compares the recent
    window to the earlier baseline. This catches:
    - "Was increasing, then collapsed" (inflection after peak)
    - "Burnout, recovery, burnout again" (oscillation)
    - "Steady" / "Consistently increasing/decreasing" (simple cases)

    The LLM already sees the raw per-submission numbers. This summary helps
    it interpret the pattern without being misled by a full-history slope.
    """
    n = len(word_counts)
    if n == 0 or avg == 0:
        return ""

    if n <= 2:
        # Too few points for pattern detection — just report average
        return f"Word count around {avg}."

    # Split into earlier baseline and recent window
    split = max(1, n - 2)  # recent = last 2, earlier = the rest
    earlier = word_counts[:split]
    recent = word_counts[split:]

    earlier_avg = round(sum(earlier) / len(earlier))
    recent_avg = round(sum(recent) / len(recent))

    # Also check overall trend for simple monotonic cases
    overall_trend = _classify_word_count_trend(word_counts)

    # Detect two-phase pattern: recent diverges from earlier
    # Check both window average AND last individual submission,
    # because a high+low recent pair can average out and mask a collapse.
    if earlier_avg > 0:
        window_ratio = recent_avg / earlier_avg
        last_ratio = word_counts[-1] / earlier_avg
    else:
        window_ratio = 1.0
        last_ratio = 1.0

    if window_ratio < 0.6 or last_ratio <= 0.5:
        # Recent submissions (or the last one) significantly lower
        last_wc = word_counts[-1]
        return (
            f"Word count was around {earlier_avg}, "
            f"most recent prior was {last_wc} words (avg {avg})."
        )
    elif window_ratio > 1.6 or last_ratio > 2.0:
        # Recent submissions significantly higher
        last_wc = word_counts[-1]
        return (
            f"Word count was around {earlier_avg}, "
            f"most recent prior was {last_wc} words (avg {avg})."
        )
    elif overall_trend == "variable":
        # High variance throughout
        lo = min(word_counts)
        hi = max(word_counts)
        return f"Word count variable ({lo}–{hi} range, avg {avg})."
    elif overall_trend == "decreasing":
        return f"Word count has been decreasing (avg {avg})."
    elif overall_trend == "increasing":
        return f"Word count has been increasing (avg {avg})."
    else:
        return f"Word count steady (avg {avg})."


def _truncate_reaching_for(text: Optional[str]) -> str:
    """Take first sentence, cap at 80 characters."""
    if not text:
        return ""
    # Split on first sentence boundary
    for sep in (".", "!", "?"):
        idx = text.find(sep)
        if idx != -1:
            sentence = text[: idx + 1].strip()
            break
    else:
        sentence = text.strip()
    if len(sentence) > 80:
        sentence = sentence[:77].rstrip() + "..."
    return sentence


def _truncate_observation_summary(text: Optional[str]) -> str:
    """Extract first sentence of an observation, capped at 100 chars.

    Provides a compact summary of what a prior observation noticed,
    enabling later observations to reference continuity or shifts
    in the student's intellectual work across assignments.
    """
    if not text:
        return ""
    # Take first sentence
    for sep in (".", "!", "?"):
        idx = text.find(sep)
        if idx != -1 and idx < 120:
            sentence = text[: idx + 1].strip()
            break
    else:
        sentence = text.strip()
    if len(sentence) > 100:
        sentence = sentence[:97].rstrip() + "..."
    return sentence


def _build_prior_line(record: Dict[str, Any], run_data: Dict[str, Any]) -> str:
    """Build a single bullet line for one prior submission."""
    parts: List[str] = []

    assignment = run_data.get("assignment_name", "Assignment")
    date_str = _format_date(run_data.get("started_at", ""))
    header = f'"{assignment}" ({date_str}):'

    wc = record.get("word_count", 0)
    preprocessing = record.get("preprocessing") or {}
    if isinstance(preprocessing, dict):
        orig_lang = preprocessing.get("original_language_name")
    else:
        # PreprocessingMetadata object (shouldn't appear here but guard anyway)
        orig_lang = getattr(preprocessing, "original_language_name", None)

    if wc == 0 and preprocessing:
        parts.append("attachment submission")
    elif wc > 0:
        parts.append(f"{wc} words")
        if orig_lang:
            parts.append(f"[in {orig_lang}]")
    # wc==0 and no preprocessing → should have been filtered upstream

    register = record.get("emotional_register")
    if register:
        parts.append(register)

    wellness = _get_wellness_signal(record)
    if wellness:
        parts.append(wellness)

    es = record.get("engagement_signals") or {}
    if isinstance(es, dict):
        depth = es.get("engagement_depth")
        if depth:
            parts.append(f"{depth} engagement")

    ts = record.get("submitted_at") or ""
    time_str = _format_time(ts)
    if time_str:
        parts.append(time_str)

    line = "- " + header + " " + ", ".join(parts)

    # Append compact observation summary so later observations can reference
    # continuity or shifts in the student's intellectual arc.
    obs_summary = _truncate_observation_summary(record.get("observation"))
    if obs_summary:
        line += f"\n  Prior observation: {obs_summary}"

    return line


def _build_summary_line(earlier_records: List[Dict[str, Any]]) -> str:
    """Build 'Plus N earlier submissions (avg X words).' summary."""
    n = len(earlier_records)
    valid_wc = [r.get("word_count", 0) for r in earlier_records if (r.get("word_count") or 0) > 0]
    if valid_wc:
        avg = round(sum(valid_wc) / len(valid_wc))
        return f"Plus {n} earlier submission{'s' if n != 1 else ''} (avg {avg} words)."
    return f"Plus {n} earlier submission{'s' if n != 1 else ''}."


def _summarize_wellness_sequence(records: List[Dict[str, Any]]) -> str:
    """Describe wellbeing axis values across a list of records."""
    signals = [_get_wellness_signal(r) for r in records]
    signals = [s for s in signals if s is not None]
    if not signals:
        return ""
    unique = list(dict.fromkeys(signals))  # preserve order, deduplicate
    if len(unique) == 1:
        return f"{unique[0]} across all prior submissions."
    return f"{', '.join(unique[:-1])} → {unique[-1]} across prior submissions."


def _summarize_engagement_depth(records: List[Dict[str, Any]]) -> str:
    """Describe engagement depth range across records."""
    depths = []
    for r in records:
        es = r.get("engagement_signals") or {}
        if isinstance(es, dict):
            d = es.get("engagement_depth")
            if d:
                depths.append(d)
    if not depths:
        return ""
    unique = list(dict.fromkeys(depths))
    if len(unique) == 1:
        return f"Engagement depth: {unique[0]}."
    return f"Engagement depth: {' to '.join([unique[0], unique[-1]])}."


def _format_trajectory_block(
    detail_records: List[Dict[str, Any]],
    detail_run_data: List[Dict[str, Any]],
    earlier_records: List[Dict[str, Any]],
    total_prior_count: int,
    current_word_count: int,
    current_submitted_at: str,
    current_register: str,
    current_engagement_depth: Optional[str],
    current_unknown_word_rate: float,
    current_linguistic_assets: List[str],
    current_theme_tags: List[str],
    is_single_prior: bool,
    current_personal_connections: Optional[List[str]] = None,
    current_readings_referenced: Optional[List[str]] = None,
) -> str:
    """Assemble the final trajectory context block."""
    lines: List[str] = []

    lines.append("TRAJECTORY CONTEXT (this student's prior submissions in this course):")
    lines.append("---")

    if is_single_prior:
        lines.append("One prior submission — a comparison point, not a trend.")
        lines.append("")

    # Prior submission detail lines
    count_label = str(total_prior_count)
    lines.append(f"Prior submission{'s' if total_prior_count != 1 else ''} ({count_label}):")

    for rec, run in zip(detail_records, detail_run_data):
        lines.append(_build_prior_line(rec, run))

    if earlier_records:
        lines.append(_build_summary_line(earlier_records))

    lines.append("")

    # --- Pattern summary (only for 2+ priors) ---
    if not is_single_prior:
        all_prior_wc = [r.get("word_count") for r in earlier_records + detail_records]
        all_prior_wc = [wc for wc in all_prior_wc if wc is not None and wc > 0]
        avg_wc = round(sum(all_prior_wc) / len(all_prior_wc)) if all_prior_wc else 0

        # Smart word count description: detect two-phase patterns (inflection)
        # instead of relying on a single slope across all history.
        wc_description = _describe_word_count_pattern(all_prior_wc, avg_wc)

        # Register summary
        registers = [r.get("emotional_register", "") for r in detail_records if r.get("emotional_register")]
        unique_registers = list(dict.fromkeys(registers))
        if len(unique_registers) == 1:
            reg_note = f"Register consistently {unique_registers[0]}."
        elif len(unique_registers) > 1:
            reg_note = f"Register varied: {', '.join(unique_registers)}."
        else:
            reg_note = ""

        wc_note = wc_description if wc_description else f"Word count data limited."
        pattern_parts = [wc_note]
        if reg_note:
            pattern_parts.append(reg_note)
        lines.append("Pattern: " + " ".join(pattern_parts))

        # Wellness summary
        wellness_summary = _summarize_wellness_sequence(earlier_records + detail_records)
        depth_summary = _summarize_engagement_depth(earlier_records + detail_records)
        if wellness_summary or depth_summary:
            wellness_line_parts = []
            if wellness_summary:
                wellness_line_parts.append(f"Wellness: {wellness_summary}")
            if depth_summary:
                wellness_line_parts.append(depth_summary)
            lines.append(" ".join(wellness_line_parts))

        # Submission time pattern
        prior_timestamps = [
            r.get("submitted_at", "") or "" for r in earlier_records + detail_records
        ]
        time_desc, _shifted = _analyze_submission_time(prior_timestamps, current_submitted_at)
        if time_desc:
            lines.append(time_desc.capitalize() + ".")

        lines.append("")

    # --- Current submission line ---
    current_parts: List[str] = []
    if current_word_count == 0:
        current_parts.append("attachment submission")
    else:
        current_parts.append(f"{current_word_count} words")
    if current_submitted_at:
        t = _format_time(current_submitted_at)
        if t:
            current_parts.append(f"submitted {t}")
    if current_register:
        current_parts.append(current_register)

    lines.append(f"Current submission: {', '.join(current_parts)}.")

    # --- Pattern break block (only for 2+ priors) ---
    if not is_single_prior:
        prior_records_all = earlier_records + detail_records
        prior_timestamps_all = [r.get("submitted_at", "") or "" for r in prior_records_all]

        is_break, signal_count = _detect_pattern_break(
            prior_records=prior_records_all,
            current_word_count=current_word_count,
            current_submitted_at=current_submitted_at,
            current_engagement_depth=current_engagement_depth,
            current_unknown_word_rate=current_unknown_word_rate,
            current_linguistic_assets=current_linguistic_assets,
            current_theme_tags=current_theme_tags,
            current_register=current_register,
            prior_timestamps=prior_timestamps_all,
            current_personal_connections=current_personal_connections,
            current_readings_referenced=current_readings_referenced,
        )

        if is_break:
            # Word count drop percentage
            all_prior_wc = [r.get("word_count") for r in prior_records_all]
            all_prior_wc = [wc for wc in all_prior_wc if wc is not None and wc > 0]
            avg_wc = round(sum(all_prior_wc) / len(all_prior_wc)) if all_prior_wc else 0

            what_changed_parts: List[str] = []

            if avg_wc > 0 and current_word_count > 0:
                pct = round(current_word_count / avg_wc * 100)
                if pct <= 50:
                    what_changed_parts.append(f"Word count dropped to {pct}% of average.")

            # Time shift detail
            prior_timestamps_clean = [ts for ts in prior_timestamps_all if ts]
            if len(prior_timestamps_clean) >= 2 and current_submitted_at:
                _td, time_shifted = _analyze_submission_time(prior_timestamps_clean, current_submitted_at)
                if time_shifted:
                    what_changed_parts.append("Submission time outside typical window.")

            what_changed_parts.append(
                "Multiple signals shifted from this student's established pattern."
            )
            lines.append("What changed: " + " ".join(what_changed_parts))

    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_trajectory_context(
    store: Any,  # InsightsStore — typed as Any to avoid circular import
    student_id: str,
    course_id: str,
    current_run_id: str,
    current_word_count: int = 0,
    current_submitted_at: str = "",
    current_register: str = "",
    current_engagement_depth: Optional[str] = None,
    current_unknown_word_rate: float = 0.0,
    current_linguistic_assets: Optional[List[str]] = None,
    current_theme_tags: Optional[List[str]] = None,
    current_personal_connections: Optional[List[str]] = None,
    current_readings_referenced: Optional[List[str]] = None,
) -> str:
    """Build the per-student trajectory context string for injection into prompts.

    Parameters
    ----------
    store : InsightsStore
        Database handle — must implement get_student_history().
    student_id : str
        Canvas user ID for the student.
    course_id : str
        Canvas course ID — history is scoped to this course only.
    current_run_id : str
        The run being analysed — excluded from history query.
    current_word_count : int
        Word count of the submission currently being observed.
    current_submitted_at : str
        ISO 8601 timestamp from Canvas for the current submission.
    current_register : str
        Emotional register of the current submission (may be "").
    current_engagement_depth : Optional[str]
        Engagement depth label for the current submission, if available.
    current_unknown_word_rate : float
        Unknown-word rate (per 100 words) for the current submission.
    current_linguistic_assets : Optional[List[str]]
        Linguistic asset labels detected for the current submission.
    current_theme_tags : Optional[List[str]]
        Theme tags for the current submission.

    Returns
    -------
    str
        Empty string when there are no prior submissions.
        A compact ~200-token context block otherwise.
    """
    if current_linguistic_assets is None:
        current_linguistic_assets = []
    if current_theme_tags is None:
        current_theme_tags = []

    # --- Fetch history ---
    try:
        history: List[Dict[str, Any]] = store.get_student_history(
            student_id, course_id, exclude_run_id=current_run_id
        )
    except Exception:
        _log.warning(
            "trajectory_context: get_student_history() failed for student=%s course=%s",
            student_id,
            course_id,
            exc_info=True,
        )
        return ""

    if not history:
        return ""

    # --- Filter out truly absent submissions (word_count==0, no preprocessing) ---
    def _is_usable(entry: Dict[str, Any]) -> bool:
        rec = entry.get("coding_record") or {}
        wc = rec.get("word_count", 0) or 0
        preprocessing = rec.get("preprocessing") or {}
        if wc == 0 and not preprocessing:
            return False
        return True

    history = [e for e in history if _is_usable(e)]
    if not history:
        return ""

    total_prior = len(history)
    is_single_prior = total_prior == 1

    # Split into detail (most recent ≤3) and earlier (summarised)
    detail_entries = history[-_MAX_DETAIL_LINES:]
    earlier_entries = history[:-_MAX_DETAIL_LINES] if total_prior > _MAX_DETAIL_LINES else []

    detail_records = [e.get("coding_record") or {} for e in detail_entries]
    detail_run_data = [
        {
            "assignment_name": e.get("assignment_name", "Assignment"),
            "started_at": e.get("started_at", ""),
        }
        for e in detail_entries
    ]
    earlier_records = [e.get("coding_record") or {} for e in earlier_entries]

    return _format_trajectory_block(
        detail_records=detail_records,
        detail_run_data=detail_run_data,
        earlier_records=earlier_records,
        total_prior_count=total_prior,
        current_word_count=current_word_count,
        current_submitted_at=current_submitted_at,
        current_register=current_register,
        current_engagement_depth=current_engagement_depth,
        current_unknown_word_rate=current_unknown_word_rate,
        current_linguistic_assets=current_linguistic_assets,
        current_theme_tags=current_theme_tags,
        is_single_prior=is_single_prior,
        current_personal_connections=current_personal_connections,
        current_readings_referenced=current_readings_referenced,
    )
