"""
TeacherProfileManager — Manages the persistent teacher analysis profile.

Records edits (theme renames, splits, merges, concern actions, tag edits)
and generates prompt fragments that shape future pipeline runs.

Uses existing TeacherAnalysisProfile model + store save_profile/get_profile.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from insights.insights_store import InsightsStore
from insights.models import TeacherAnalysisProfile


# ---------------------------------------------------------------------------
# Wellbeing signal protection
# ---------------------------------------------------------------------------
# Concern patterns that must always surface, even if previously dismissed.
# These can be reduced but never below WELLBEING_SENSITIVITY_FLOOR.
# The teacher still decides what to do — but the system doesn't go silent
# on safety.
PROTECTED_WELLBEING_PATTERNS = {
    "distress",
    "self-harm", "self harm",
    "suicide", "suicidal",
    "crisis",
    "harm",
    "safety",
    "abuse",
    "violence",
    "isolation",
    "hopeless",
    "help",
}

WELLBEING_SENSITIVITY_FLOOR = 0.3  # Never suppress below this

WELLBEING_FLOOR_NOTE = (
    "Safety signals remain active at minimum sensitivity — "
    "these patterns always surface so students in crisis are visible."
)


def is_protected_concern(concern_text: str) -> bool:
    """Check if a concern contains wellbeing/safety language that should
    never be fully suppressed.

    Matches against PROTECTED_WELLBEING_PATTERNS using case-insensitive
    substring search. A single hit is enough — err on the side of surfacing.
    """
    lower = concern_text.lower()
    return any(pattern in lower for pattern in PROTECTED_WELLBEING_PATTERNS)


class TeacherProfileManager:
    """Wraps InsightsStore profile persistence with edit-recording helpers.

    Each edit method mutates the in-memory profile and auto-saves.
    Prompt fragment generators build text from accumulated profile data.
    """

    DEFAULT_PROFILE_ID = "default"

    def __init__(self, store: InsightsStore, profile_id: str = ""):
        self._store = store
        self._profile_id = profile_id or self.DEFAULT_PROFILE_ID
        self._profile = self._load()

    def _load(self) -> TeacherAnalysisProfile:
        raw = self._store.get_profile(self._profile_id)
        if raw:
            try:
                return TeacherAnalysisProfile.model_validate(raw)
            except Exception:
                pass
        return TeacherAnalysisProfile()

    def _save(self) -> None:
        self._store.save_profile(
            self._profile_id, self._profile.model_dump()
        )

    @property
    def profile(self) -> TeacherAnalysisProfile:
        return self._profile

    # ── Edit recording methods ─────────────────────────────────────────

    def record_theme_rename(self, old: str, new: str) -> None:
        """Record that the teacher renamed a theme label."""
        self._profile.theme_renames[old] = new
        self._append_history("theme_rename", {"old": old, "new": new})
        self._save()

    def record_theme_split(self, original: str, children: List[str]) -> None:
        """Record that a theme was split into children."""
        self._profile.theme_splits.append({
            "original": original,
            "children": children,
        })
        self._append_history("theme_split", {
            "original": original, "children": children,
        })
        self._save()

    def record_theme_merge(self, sources: List[str], target: str) -> None:
        """Record that multiple themes were merged into one.

        Each source name is recorded as a rename → target, so the theme
        vocabulary fragment will guide future runs to use the merged name.
        """
        for source in sources:
            if source != target:
                self._profile.theme_renames[source] = target
        self._append_history("theme_merge", {
            "sources": sources, "target": target,
        })
        self._save()

    def record_concern_action(
        self, concern_text: str, action: str,
    ) -> Optional[str]:
        """Adjust concern sensitivity based on teacher action.

        action: "acknowledge" or "dismiss"

        Returns a notification string when a protected wellbeing concern
        hits the sensitivity floor, so the caller can surface it to the
        teacher. Returns None otherwise.

        Protected concerns (distress, self-harm, crisis, etc.) can never
        be suppressed below WELLBEING_SENSITIVITY_FLOOR.  The teacher
        still decides what to act on — but the system will keep surfacing
        safety signals so students in crisis remain visible.
        """
        key = concern_text[:80]
        current = self._profile.concern_sensitivity.get(key, 0.5)
        note: Optional[str] = None

        if action == "acknowledge":
            self._profile.concern_sensitivity[key] = min(1.0, current + 0.1)
        elif action == "dismiss":
            new_val = current - 0.1
            protected = is_protected_concern(key)
            if protected:
                floor = WELLBEING_SENSITIVITY_FLOOR
                new_val = max(floor, new_val)
                if new_val <= floor:
                    note = WELLBEING_FLOOR_NOTE
            else:
                new_val = max(0.0, new_val)
            self._profile.concern_sensitivity[key] = new_val

        self._append_history("concern_action", {
            "concern": key, "action": action,
        })
        self._save()
        return note

    def record_tag_edit(
        self, student_id: str, added: List[str], removed: List[str],
    ) -> None:
        """Log tag vocabulary changes from teacher edits."""
        self._append_history("tag_edit", {
            "student_id": student_id,
            "added": added,
            "removed": removed,
        })
        self._save()

    def record_theme_delete(self, theme_name: str) -> None:
        """Record that a theme was deleted by the teacher."""
        self._append_history("theme_delete", {"theme": theme_name})
        self._save()

    def record_interest_areas(self, interests: List[str]) -> None:
        """Persist teacher's ranked interest areas into the profile."""
        self._profile.interest_areas = interests[:5]
        self._save()

    def record_analysis_lens(self, lens: Optional[Dict]) -> None:
        """Persist the teacher's analysis lens for future run defaults."""
        if lens:
            self._profile.custom_patterns["_analysis_lens"] = str(lens)
        self._save()

    def record_subject_area(self, subject: str) -> None:
        """Set the teacher's subject area (shapes equity framing)."""
        self._profile.subject_area = subject
        self._save()

    def add_custom_concern_pattern(self, pattern: str) -> None:
        """Add a teacher-defined concern pattern.

        pattern is a plain-English description of what to flag:
          "student makes a factual claim without citing a source"
          "student attributes behavior to genetics or biology without evidence"
        """
        pattern = pattern.strip()
        if pattern and pattern not in self._profile.custom_concern_patterns:
            self._profile.custom_concern_patterns.append(pattern)
            self._append_history("concern_pattern_add", {"pattern": pattern})
            self._save()

    def remove_custom_concern_pattern(self, pattern: str) -> None:
        """Remove a teacher-defined concern pattern."""
        pattern = pattern.strip()
        if pattern in self._profile.custom_concern_patterns:
            self._profile.custom_concern_patterns.remove(pattern)
            self._append_history("concern_pattern_remove", {"pattern": pattern})
            self._save()

    def reset_concern_sensitivity(self) -> None:
        """Clear all accumulated concern sensitivity adjustments.

        Resets concern_sensitivity to empty, removes concern_action entries
        from edit_history, and saves. Does not affect other profile data
        (patterns, renames, subject area, etc.).
        """
        self._profile.concern_sensitivity = {}
        self._profile.edit_history = [
            e for e in self._profile.edit_history
            if e.get("action") != "concern_action"
        ]
        self._append_history("calibration_reset", {})
        self._save()

    def disable_default_pattern(self, pattern_label: str) -> None:
        """Mute a default concern pattern for this course.

        Wellbeing/crisis signals are silently preserved regardless —
        only pedagogical patterns (essentializing, colorblind, tone
        policing) should be passed here.
        """
        PROTECTED = {"wellbeing", "crisis", "self-harm", "personal distress"}
        if any(p in pattern_label.lower() for p in PROTECTED):
            return  # silently refuse to disable safety signals
        label = pattern_label.strip()
        if label and label not in self._profile.disabled_default_patterns:
            self._profile.disabled_default_patterns.append(label)
            self._append_history("default_pattern_disable", {"pattern": label})
            self._save()

    def enable_default_pattern(self, pattern_label: str) -> None:
        """Re-enable a previously muted default pattern."""
        label = pattern_label.strip()
        if label in self._profile.disabled_default_patterns:
            self._profile.disabled_default_patterns.remove(label)
            self._append_history("default_pattern_enable", {"pattern": label})
            self._save()

    def add_strength_pattern(self, pattern: str) -> None:
        """Add a teacher-defined strength pattern to surface in analysis.

        Examples:
          "student connects course material to community or family knowledge"
          "student demonstrates translanguaging or multilingual thinking"
          "student makes an unexpected cross-disciplinary connection"
        """
        pattern = pattern.strip()
        if pattern and pattern not in self._profile.custom_strength_patterns:
            self._profile.custom_strength_patterns.append(pattern)
            self._append_history("strength_pattern_add", {"pattern": pattern})
            self._save()

    def remove_strength_pattern(self, pattern: str) -> None:
        """Remove a teacher-defined strength pattern."""
        pattern = pattern.strip()
        if pattern in self._profile.custom_strength_patterns:
            self._profile.custom_strength_patterns.remove(pattern)
            self._append_history("strength_pattern_remove", {"pattern": pattern})
            self._save()

    # ── Template save / load ───────────────────────────────────────────

    def save_as_template(self, template_name: str) -> None:
        """Snapshot the current profile as a named reusable template.

        The snapshot includes subject_area, custom patterns, disabled defaults,
        strengths patterns, theme vocabulary, and interest areas — everything
        a teacher would want to carry forward to a new semester.
        Edit history and per-student concern_sensitivity are NOT copied:
        those are run-specific, not course-design decisions.
        """
        snapshot = self._profile.model_dump()
        # Strip run-specific accumulated data
        snapshot["concern_sensitivity"] = {}
        snapshot["edit_history"] = []
        self._store.save_profile_template(template_name, snapshot)

    @classmethod
    def fork_from_template(
        cls,
        store: "InsightsStore",
        template_name: str,
        profile_id: str,
    ) -> "TeacherProfileManager":
        """Create (or overwrite) a profile by copying a saved template.

        Returns a TeacherProfileManager loaded with the forked profile.
        The caller is responsible for confirming overwrite if the profile_id
        already has data.
        """
        template_data = store.get_profile_template(template_name)
        if template_data:
            store.save_profile(profile_id, template_data)
        mgr = cls(store, profile_id)
        return mgr

    def _append_history(self, action: str, details: Dict) -> None:
        self._profile.edit_history.append({
            "action": action,
            "details": details,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        # Keep history bounded
        if len(self._profile.edit_history) > 200:
            self._profile.edit_history = self._profile.edit_history[-200:]

    # ── Prompt fragment generators ─────────────────────────────────────

    def get_theme_vocabulary_fragment(self) -> str:
        """Build a prompt fragment from accumulated renames + splits."""
        lines = []
        if self._profile.theme_renames:
            lines.append("TEACHER THEME VOCABULARY (use these names):")
            for old, new in self._profile.theme_renames.items():
                lines.append(f'  - Use "{new}" instead of "{old}"')
        if self._profile.theme_splits:
            lines.append("TEACHER THEME REFINEMENTS:")
            for split in self._profile.theme_splits[-5:]:
                children = ", ".join(f'"{c}"' for c in split["children"])
                lines.append(
                    f'  - "{split["original"]}" should be split into: {children}'
                )
        return "\n".join(lines)

    def get_concern_sensitivity_fragment(self) -> str:
        """Build a prompt fragment from concern sensitivity adjustments.

        Protected wellbeing concerns at the sensitivity floor are annotated
        so the LLM understands these are safety signals that always surface,
        regardless of the teacher's dismiss history.
        """
        if not self._profile.concern_sensitivity:
            return ""
        lines = ["TEACHER CONCERN CALIBRATION:"]
        for key, val in sorted(
            self._profile.concern_sensitivity.items(), key=lambda x: -x[1]
        )[:10]:
            if val >= 0.7:
                lines.append(f"  - High sensitivity: {key}")
            elif val <= WELLBEING_SENSITIVITY_FLOOR and is_protected_concern(key):
                lines.append(
                    f"  - {key} — sensitivity is at minimum "
                    "(safety signal — always surfaces)"
                )
            elif val <= 0.3:
                lines.append(f"  - Low sensitivity (often dismissed): {key}")
        return "\n".join(lines) if len(lines) > 1 else ""

    def get_custom_concern_fragment(self) -> str:
        """Build a prompt fragment from teacher-defined concern patterns.

        These are injected into the concern detection prompt alongside the
        default patterns, allowing teachers to define subject-specific flags
        (e.g. "student claims a group behavior is biological/genetic").
        The fragment uses subject-agnostic language to avoid terminology
        that only makes sense in a humanities context.
        """
        patterns = self._profile.custom_concern_patterns
        if not patterns:
            return ""
        lines = [
            "ADDITIONAL CONCERN PATTERNS (defined by this teacher — "
            "flag these alongside the default patterns above):"
        ]
        for p in patterns[:10]:
            lines.append(f"  - {p}")
        return "\n".join(lines)

    def get_interests_fragment(self) -> str:
        """Build a prompt fragment from teacher interest areas."""
        if not self._profile.interest_areas:
            return ""
        areas = ", ".join(self._profile.interest_areas[:5])
        return f"TEACHER INTEREST AREAS: {areas}"

    def get_equity_fragment(self) -> str:
        """Return the equity attention prompt fragment for this teacher's subject.

        The power analysis always runs at full depth. What shifts is how
        it's APPLIED to the subject matter — whose bodies, whose labor,
        whose knowledge, whose silence.
        """
        from insights.lens_templates import get_equity_fragment
        return get_equity_fragment(self._profile.subject_area)

    def get_concern_framing_fragment(self) -> str:
        """Return subject-specific concern framing for this teacher's subject.

        Adjusts which default concern patterns are most/least relevant and
        adds subject-appropriate patterns (e.g. scientific essentialism for
        biology, historical inevitability for history).
        """
        from insights.lens_templates import get_concern_framing_fragment
        return get_concern_framing_fragment(self._profile.subject_area)

    def get_disabled_defaults_fragment(self) -> str:
        """Build a prompt fragment suppressing teacher-muted default patterns."""
        patterns = self._profile.disabled_default_patterns
        if not patterns:
            return ""
        lines = [
            "THE FOLLOWING DEFAULT CONCERN PATTERNS ARE MUTED FOR THIS COURSE "
            "(teacher has determined they are not applicable — do not flag these "
            "unless they cross into wellbeing territory):"
        ]
        for p in patterns:
            lines.append(f"  - {p}")
        return "\n".join(lines)

    def get_calibration_fragment(self) -> str:
        """Build a prompt fragment from recent teacher corrections.

        This closes the feedback loop: corrections saved via save_calibration()
        (tag edits, concern actions, theme renames, etc.) are formatted into
        natural-language examples that teach the LLM the teacher's judgment.

        The fragment is anonymized — no student names or IDs are included.
        Submission text is truncated to avoid leaking student work across
        students.  Returns empty string if no corrections exist.
        """
        import json as _json

        corrections = self._store.get_recent_corrections(
            self._profile_id, limit=5,
        )
        if not corrections:
            return ""

        lines = [
            "TEACHER CORRECTIONS (learn from these):",
            "The teacher has corrected similar assessments in the past:",
        ]

        for c in corrections:
            correction_type = c.get("correction_type", "general")
            original_raw = c.get("original_coding", "")
            corrected_raw = c.get("corrected_coding", "")

            # Parse JSON payloads safely
            try:
                original = _json.loads(original_raw) if original_raw else {}
            except (_json.JSONDecodeError, TypeError):
                original = {}
            try:
                corrected = _json.loads(corrected_raw) if corrected_raw else {}
            except (_json.JSONDecodeError, TypeError):
                corrected = {}

            # Build a human-readable correction line based on type
            description = self._format_correction(
                correction_type, original, corrected,
            )
            if description:
                lines.append(f"- {description}")

        # Only emit if we produced at least one concrete correction line
        if len(lines) <= 2:
            return ""

        lines.append(
            "Apply these corrections to similar cases in this analysis."
        )
        return "\n".join(lines)

    @staticmethod
    def _format_correction(
        correction_type: str, original: dict, corrected: dict,
    ) -> str:
        """Format a single correction record into a prompt-safe description.

        Returns empty string if the correction can't be meaningfully described.
        All output is anonymized — no student names or IDs.
        """
        if correction_type == "tag_remove":
            removed = set(original.get("theme_tags", [])) - set(
                corrected.get("theme_tags", [])
            )
            if removed:
                return (
                    f"Tag(s) {', '.join(repr(t) for t in removed)} were removed "
                    f"by the teacher as not applicable."
                )

        elif correction_type == "tag_add":
            added = set(corrected.get("theme_tags", [])) - set(
                original.get("theme_tags", [])
            )
            if added:
                return (
                    f"Tag(s) {', '.join(repr(t) for t in added)} were added "
                    f"by the teacher as missing from the original coding."
                )

        elif correction_type == "concern_dismiss":
            why = corrected.get("why_flagged", "")
            if why:
                return (
                    f"A concern flagged as \"{why[:120]}\" was dismissed "
                    f"by the teacher as not applicable."
                )

        elif correction_type == "concern_acknowledge":
            why = corrected.get("why_flagged", "")
            if why:
                return (
                    f"A concern flagged as \"{why[:120]}\" was acknowledged "
                    f"by the teacher as valid — keep flagging similar cases."
                )

        elif correction_type == "theme_rename":
            old_name = original.get("name", "")
            new_name = corrected.get("name", "")
            if old_name and new_name:
                return (
                    f"Theme \"{old_name}\" was renamed to \"{new_name}\" — "
                    f"use the new name in future analysis."
                )

        elif correction_type == "theme_delete":
            theme = original.get("theme", "")
            if theme:
                return (
                    f"Theme \"{theme}\" was deleted by the teacher as not useful."
                )

        elif correction_type == "feedback_edit":
            return (
                "Draft feedback was edited by the teacher to better match "
                "their voice and pedagogical approach."
            )

        elif correction_type == "outlier_to_theme":
            theme = corrected.get("theme", "")
            if theme:
                return (
                    f"An outlier submission was reclassified into theme "
                    f"\"{theme}\" by the teacher."
                )

        elif correction_type == "outlier_create_theme":
            theme = corrected.get("theme", "")
            if theme:
                return (
                    f"The teacher created a new theme \"{theme}\" from an "
                    f"outlier submission — consider this theme category."
                )

        # Fallback for unknown types: skip rather than leak raw JSON
        return ""

    def get_strengths_fragment(self) -> str:
        """Build a prompt fragment for strength patterns to surface.

        Uses teacher-defined custom patterns when available; falls back to
        subject-area defaults from lens_templates. These flow into the coding
        prompt to ensure the pipeline surfaces community cultural wealth,
        code-switching, unexpected connections, and non-dominant engagement.
        """
        patterns = self._profile.custom_strength_patterns
        if not patterns:
            from insights.lens_templates import get_default_strength_patterns
            subject = getattr(self._profile, "subject_area", "general") or "general"
            patterns = get_default_strength_patterns(subject)
        if not patterns:
            return ""
        using_defaults = not self._profile.custom_strength_patterns
        header = (
            "STRENGTH PATTERNS TO SURFACE "
            "(look for these — note as positive observations in theme_tags or lens_observations):"
            if using_defaults
            else
            "STRENGTH PATTERNS TO SURFACE (defined by this teacher — "
            "note these as positive observations in theme_tags or lens_observations):"
        )
        lines = [header]
        for p in patterns[:10]:
            lines.append(f"  - {p}")
        return "\n".join(lines)

    def get_full_profile_fragment(self) -> str:
        """Combine all profile fragments into one block for prompt injection.

        Includes: theme vocabulary, concern calibration, prompt calibration
        feedback loop, interests, equity attention framing, AND teacher-defined
        strength patterns.
        Strength patterns flow into coding prompts as positive surfacing
        instructions; they are benign noise in concern detection prompts.
        """
        parts = [
            self.get_theme_vocabulary_fragment(),
            self.get_concern_framing_fragment(),
            self.get_concern_sensitivity_fragment(),
            self.get_disabled_defaults_fragment(),
            self.get_custom_concern_fragment(),
            self.get_calibration_fragment(),
            self.get_strengths_fragment(),
            self.get_interests_fragment(),
            self.get_equity_fragment(),
        ]
        combined = "\n\n".join(p for p in parts if p)
        if not combined:
            return ""
        return f"\n--- TEACHER PROFILE ---\n{combined}\n--- END PROFILE ---\n"
