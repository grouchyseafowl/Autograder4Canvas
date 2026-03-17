"""
WeightComposer — Two-Axis Per-Marker Weight System for Academic Integrity Check.

Composes per-marker weights from:
  1. Education level YAML profile (base weights for typical student at that level)
  2. Population overlays (school-level deviations from typical for that institution type)
  3. Per-student overrides (individual student flags, composed via max())

The composition formula per marker:
    effective_weight[m] = edu_level[m] × esl_overlay[m] × first_gen_overlay[m] × nd_overlay[m]

The distributional peer comparison still catches outliers on calibrated metrics.
A student with 5x the ai_specific_org of peers still gets surfaced, even with
reduced per-match weights. What changes is which markers have the most
distributional power for each institution type.

Usage:
    from modules.weight_composer import WeightComposer, PopulationSettings

    composer = WeightComposer()
    weights = composer.compose("community_college", PopulationSettings())
    # weights.marker_weights["ai_transitions"] → 0.35

    # With population overlays:
    pop = PopulationSettings(esl_level="high", neurodivergent_aware=True)
    weights = composer.compose("high_school", pop)

    # With per-student overrides (student gets max protection):
    student_pop = PopulationSettings(esl_level="moderate")
    weights = composer.compose("community_college", class_pop, student_overrides=student_pop)

All weight values are hypotheses. Calibration with DAIGT/ASAP data refines them.
"""

from __future__ import annotations

import platform
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass
class PopulationSettings:
    """
    Class-level population settings (per institution/profile).

    esl_level and first_gen_level are graduated: none < low < moderate < high.
    When composing with per-student overrides, the more protective (higher) level wins.
    neurodivergent_aware is boolean: OR composition (on if either class or student sets it).
    """
    esl_level: str = "none"           # none | low | moderate | high
    first_gen_level: str = "none"     # none | low | moderate | high
    neurodivergent_aware: bool = False

    VALID_GRADUATED_LEVELS = ("none", "low", "moderate", "high")
    _LEVEL_ORDER: Dict[str, int] = field(default_factory=lambda: {
        "none": 0, "low": 1, "moderate": 2, "high": 3
    }, init=False, repr=False, compare=False)

    def __post_init__(self):
        if self.esl_level not in ("none", "low", "moderate", "high"):
            raise ValueError(f"Invalid esl_level: {self.esl_level!r}. "
                             f"Must be one of: none, low, moderate, high")
        if self.first_gen_level not in ("none", "low", "moderate", "high"):
            raise ValueError(f"Invalid first_gen_level: {self.first_gen_level!r}. "
                             f"Must be one of: none, low, moderate, high")

    def max_with(self, other: "PopulationSettings") -> "PopulationSettings":
        """
        Compose two settings by taking the more protective value for each axis.

        Student always gets the MORE protective setting:
        - Graduated levels: take the higher of the two
        - Neurodivergent: OR composition (on if either sets it)
        """
        level_order = {"none": 0, "low": 1, "moderate": 2, "high": 3}

        def max_level(a: str, b: str) -> str:
            return a if level_order.get(a, 0) >= level_order.get(b, 0) else b

        return PopulationSettings(
            esl_level=max_level(self.esl_level, other.esl_level),
            first_gen_level=max_level(self.first_gen_level, other.first_gen_level),
            neurodivergent_aware=self.neurodivergent_aware or other.neurodivergent_aware,
        )

    def to_dict(self) -> Dict:
        return {
            "esl_level": self.esl_level,
            "first_gen_level": self.first_gen_level,
            "neurodivergent_aware": self.neurodivergent_aware,
        }


@dataclass
class ComposedWeights:
    """
    Result of weight composition — per-marker effective weights ready for use.

    Pass to DishonestyAnalyzer as composed_weights=. When present, the
    analyzer uses these per-marker weights instead of hardcoded defaults and
    skips the flat context_multiplier.
    """
    marker_weights: Dict[str, float]        # marker_id -> effective per-match weight
    outlier_percentile: float               # percentile threshold for peer comparison
    cognitive_protection_floor: float       # minimum multiplier for strong protection (4+ markers)
    education_level: str                    # which edu level profile was used
    population: PopulationSettings          # effective population settings (after override merge)
    composition_log: List[str]             # audit trail of composition steps

    def summary(self) -> str:
        """Human-readable summary of the composed weights."""
        lines = [
            f"Education level: {self.education_level}",
            f"Population: ESL={self.population.esl_level}, "
            f"first_gen={self.population.first_gen_level}, "
            f"ND-aware={self.population.neurodivergent_aware}",
            "Effective weights:",
        ]
        for marker, weight in sorted(self.marker_weights.items()):
            lines.append(f"  {marker}: {weight:.3f}")
        lines.append(f"Outlier percentile: {self.outlier_percentile}")
        lines.append(f"Cognitive protection floor: {self.cognitive_protection_floor}")
        return "\n".join(lines)


# ── Composer ──────────────────────────────────────────────────────────────────


class WeightComposer:
    """
    Loads education level profiles + population overlays and composes per-marker weights.

    Thread-safe for reads (no mutable state after initialization). Caches loaded
    YAML files to avoid re-reading on each call.
    """

    # Valid education level profile IDs
    VALID_EDUCATION_LEVELS = (
        "high_school",
        "community_college",
        "four_year",
        "university",
        "online",
    )

    def __init__(self, config_dir: Optional[Path] = None):
        self._config_dir = config_dir or self._default_config_dir()
        self._context_profiles_dir = self._config_dir / "context_profiles"
        self._overlays_cache: Optional[Dict] = None
        self._edu_level_cache: Dict[str, Dict] = {}

    def compose(
        self,
        education_level: str,
        population: PopulationSettings,
        student_overrides: Optional[PopulationSettings] = None,
    ) -> ComposedWeights:
        """
        Compose per-marker weights for the given education level and population.

        Args:
            education_level: Profile ID (e.g. "community_college", "high_school")
            population: Class-level population settings (per institution)
            student_overrides: Optional per-student flags; merged via max() —
                               student always gets the MORE protective setting

        Returns:
            ComposedWeights ready to pass to DishonestyAnalyzer
        """
        if not HAS_YAML:
            raise ImportError("PyYAML is required for WeightComposer. "
                              "Install with: pip install pyyaml")

        log: List[str] = []

        # Merge student overrides using max() — student always gets more protection
        effective_pop = population
        if student_overrides:
            effective_pop = population.max_with(student_overrides)
            log.append(
                f"Student overrides merged (max composition): "
                f"esl={effective_pop.esl_level}, "
                f"first_gen={effective_pop.first_gen_level}, "
                f"nd_aware={effective_pop.neurodivergent_aware}"
            )

        # Load full education level YAML (returns entire parsed data)
        edu_data = self._load_edu_level(education_level)
        log.append(f"Loaded education level profile: {education_level}")

        # Access marker_weights section (has suspicious + authenticity subsections)
        mw_section = edu_data.get("marker_weights", {})

        # Thresholds can be at top level (preferred) or inside marker_weights (legacy)
        thresholds = edu_data.get("thresholds", mw_section.get("thresholds", {}))

        # Flatten base weights from suspicious + authenticity sections
        suspicious_base = mw_section.get("suspicious", {})
        auth_base = mw_section.get("authenticity", {})

        marker_weights: Dict[str, float] = {}
        marker_weights.update({k: float(v) for k, v in suspicious_base.items()})
        marker_weights.update({k: float(v) for k, v in auth_base.items()})

        outlier_percentile = float(thresholds.get("outlier_percentile", 95))
        cognitive_protection_floor = float(thresholds.get("cognitive_protection_floor", 0.5))

        log.append(f"Base weights loaded: {len(marker_weights)} markers")

        # Load overlays
        overlays = self._load_overlays()

        # ── Apply ESL overlay ───────────────────────────────────────────────
        if effective_pop.esl_level != "none":
            esl_overlays = (
                overlays.get("esl", {})
                .get("levels", {})
                .get(effective_pop.esl_level, {})
            )
            for marker, mult in esl_overlays.items():
                if marker in marker_weights:
                    old = marker_weights[marker]
                    marker_weights[marker] = round(old * float(mult), 4)
                    log.append(
                        f"  ESL {effective_pop.esl_level}: "
                        f"{marker} {old:.3f} × {mult} = {marker_weights[marker]:.3f}"
                    )

        # ── Apply first-gen overlay ─────────────────────────────────────────
        if effective_pop.first_gen_level != "none":
            fg_overlays = (
                overlays.get("first_gen", {})
                .get("levels", {})
                .get(effective_pop.first_gen_level, {})
            )
            for marker, mult in fg_overlays.items():
                if marker in marker_weights:
                    old = marker_weights[marker]
                    marker_weights[marker] = round(old * float(mult), 4)
                    log.append(
                        f"  first_gen {effective_pop.first_gen_level}: "
                        f"{marker} {old:.3f} × {mult} = {marker_weights[marker]:.3f}"
                    )

        # ── Apply neurodivergent overlay ────────────────────────────────────
        nd_setting = "on" if effective_pop.neurodivergent_aware else "off"
        nd_overlays = (
            overlays.get("neurodivergent", {})
            .get("settings", {})
            .get(nd_setting, {})
        )
        for marker, value in nd_overlays.items():
            if marker == "cognitive_protection_floor":
                old_floor = cognitive_protection_floor
                cognitive_protection_floor = float(value)
                log.append(
                    f"  ND-aware: cognitive_protection_floor "
                    f"{old_floor} → {cognitive_protection_floor}"
                )
            elif marker in marker_weights:
                old = marker_weights[marker]
                marker_weights[marker] = round(old * float(value), 4)
                log.append(
                    f"  ND-aware: {marker} {old:.3f} × {value} = {marker_weights[marker]:.3f}"
                )

        if effective_pop.neurodivergent_aware:
            log.append(
                "  ND-aware mode active: ai_specific_org reduced, "
                "cognitive_diversity boosted, stronger protection floor"
            )

        return ComposedWeights(
            marker_weights=marker_weights,
            outlier_percentile=outlier_percentile,
            cognitive_protection_floor=cognitive_protection_floor,
            education_level=education_level,
            population=effective_pop,
            composition_log=log,
        )

    # ── Internal loaders ──────────────────────────────────────────────────────

    def _load_edu_level(self, profile_id: str) -> Dict:
        """
        Load a full education level YAML profile.

        Returns the entire parsed YAML dict (not just marker_weights) so that
        both marker_weights and thresholds can be accessed at their correct
        positions (thresholds is at top level, marker_weights is nested).
        """
        if profile_id in self._edu_level_cache:
            return self._edu_level_cache[profile_id]

        profile_path = self._context_profiles_dir / f"{profile_id}.yaml"
        if not profile_path.exists():
            raise FileNotFoundError(
                f"Education level profile not found: {profile_path}\n"
                f"Valid options: {', '.join(self.VALID_EDUCATION_LEVELS)}"
            )

        with open(profile_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data.get("marker_weights"):
            raise ValueError(
                f"Profile {profile_id}.yaml has no 'marker_weights' section. "
                f"Only v3 profiles (with marker_weights) are supported by WeightComposer."
            )

        self._edu_level_cache[profile_id] = data
        return data

    def _load_overlays(self) -> Dict:
        """Load population overlays YAML (cached)."""
        if self._overlays_cache is not None:
            return self._overlays_cache

        overlays_path = self._context_profiles_dir / "population_overlays.yaml"
        if not overlays_path.exists():
            self._overlays_cache = {}
            return {}

        with open(overlays_path, "r", encoding="utf-8") as f:
            self._overlays_cache = yaml.safe_load(f) or {}

        return self._overlays_cache

    @staticmethod
    def _default_config_dir() -> Path:
        """Find config directory (same discovery logic as MarkerLoader)."""
        system = platform.system()
        if system == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            user_dir = base / "CanvasAutograder"
        elif system == "Darwin":
            user_dir = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
        else:
            user_dir = Path.home() / ".config" / "CanvasAutograder"

        if (user_dir / "context_profiles").exists():
            return user_dir

        # Fall back to src/config/ (dev / running from source)
        src_config = Path(__file__).parent.parent / "config"
        if (src_config / "context_profiles").exists():
            return src_config

        return user_dir


# ── Convenience function ──────────────────────────────────────────────────────


def compose_weights(
    education_level: str = "community_college",
    esl_level: str = "none",
    first_gen_level: str = "none",
    neurodivergent_aware: bool = False,
    student_overrides: Optional[PopulationSettings] = None,
    config_dir: Optional[Path] = None,
) -> ComposedWeights:
    """
    Convenience function to compose weights without instantiating WeightComposer.

    Args:
        education_level: Profile ID (high_school, community_college, four_year,
                         university, online)
        esl_level: ESL population level (none, low, moderate, high)
        first_gen_level: First-gen population level (none, low, moderate, high)
        neurodivergent_aware: Enable neurodivergent-aware mode
        student_overrides: Per-student overrides (merged via max())
        config_dir: Override config directory (default: auto-discover)

    Returns:
        ComposedWeights ready to pass to DishonestyAnalyzer
    """
    composer = WeightComposer(config_dir=config_dir)
    population = PopulationSettings(
        esl_level=esl_level,
        first_gen_level=first_gen_level,
        neurodivergent_aware=neurodivergent_aware,
    )
    return composer.compose(education_level, population, student_overrides)


# ── Credential profile helpers ────────────────────────────────────────────────


def population_from_profile(profile: Dict) -> PopulationSettings:
    """
    Extract PopulationSettings from a credential profile dict.

    The profile dict comes from credentials.json and contains Canvas URL,
    API token, and now also education_level + population_* settings.

    Example profile:
        {
            "canvas_base_url": "...",
            "canvas_api_token": "...",
            "education_level": "community_college",
            "population_esl": "moderate",
            "population_first_gen": "high",
            "population_neurodivergent_aware": false
        }
    """
    return PopulationSettings(
        esl_level=profile.get("population_esl", "none"),
        first_gen_level=profile.get("population_first_gen", "none"),
        neurodivergent_aware=bool(profile.get("population_neurodivergent_aware", False)),
    )


def compose_from_profile(
    profile: Dict,
    student_overrides: Optional[PopulationSettings] = None,
    config_dir: Optional[Path] = None,
) -> ComposedWeights:
    """
    Compose weights directly from a credential profile dict.

    Args:
        profile: Credential profile dict (from credentials.json)
        student_overrides: Per-student overrides (merged via max())
        config_dir: Override config directory

    Returns:
        ComposedWeights ready to pass to DishonestyAnalyzer
    """
    education_level = profile.get("education_level", "community_college")
    population = population_from_profile(profile)
    composer = WeightComposer(config_dir=config_dir)
    return composer.compose(education_level, population, student_overrides)
