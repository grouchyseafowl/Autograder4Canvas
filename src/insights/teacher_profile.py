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

    def record_concern_action(self, concern_text: str, action: str) -> None:
        """Adjust concern sensitivity based on teacher action.

        action: "acknowledge" or "dismiss"
        """
        key = concern_text[:80]
        current = self._profile.concern_sensitivity.get(key, 0.5)
        if action == "acknowledge":
            self._profile.concern_sensitivity[key] = min(1.0, current + 0.1)
        elif action == "dismiss":
            self._profile.concern_sensitivity[key] = max(0.0, current - 0.1)
        self._append_history("concern_action", {
            "concern": key, "action": action,
        })
        self._save()

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
        """Build a prompt fragment from concern sensitivity adjustments."""
        if not self._profile.concern_sensitivity:
            return ""
        lines = ["TEACHER CONCERN CALIBRATION:"]
        for key, val in sorted(
            self._profile.concern_sensitivity.items(), key=lambda x: -x[1]
        )[:10]:
            if val >= 0.7:
                lines.append(f"  - High sensitivity: {key}")
            elif val <= 0.3:
                lines.append(f"  - Low sensitivity (often dismissed): {key}")
        return "\n".join(lines) if len(lines) > 1 else ""

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

    def get_full_profile_fragment(self) -> str:
        """Combine all profile fragments into one block for prompt injection.

        Includes: theme vocabulary, concern calibration, interests, AND
        equity attention framing for this teacher's subject area.
        """
        parts = [
            self.get_theme_vocabulary_fragment(),
            self.get_concern_sensitivity_fragment(),
            self.get_interests_fragment(),
            self.get_equity_fragment(),
        ]
        combined = "\n\n".join(p for p in parts if p)
        if not combined:
            return ""
        return f"\n--- TEACHER PROFILE ---\n{combined}\n--- END PROFILE ---\n"
