"""
Assignment template management.

Templates are named configurations (word counts, AIC settings, grading type)
that get mapped to Canvas assignment groups by fuzzy keyword matching or manual
assignment.  They let teachers configure once and apply everywhere.

Storage: ~/.canvas_autograder_templates.json
"""

import json
import re
from pathlib import Path
from typing import Optional

TEMPLATES_FILE = Path.home() / ".canvas_autograder_templates.json"

# ---------------------------------------------------------------------------
# Built-in starter templates
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# AIC mode weight presets — single source of truth for mode-to-weight mapping
#
# Four teacher-facing dimensions:
#   weight_personal_voice  — how much personal/emotional language counts as authentic
#   weight_ai_patterns     — how hard to flag AI transition phrases & generic summaries
#   weight_course_content  — importance of course-specific content references
#   weight_rough_work      — value of drafty, in-progress, messy quality
#
# Templates store the actual float values; modes are shortcuts to populate defaults.
# ---------------------------------------------------------------------------

AIC_MODE_WEIGHT_PRESETS: dict = {
    "auto": {
        "personal_voice_authentic":  True,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     1.0,
        "weight_ai_patterns":        1.0,
        "weight_course_content":     1.0,
        "weight_rough_work":         1.0,
    },
    "notes": {
        # In notes: complete prose = suspicious; fragments = authentic.
        # Personal voice not expected → silence as authenticity signal.
        "personal_voice_authentic":  False,
        "invert_sentence_signals":   True,
        "weight_personal_voice":     0.5,
        "weight_ai_patterns":        1.8,   # extra-strong AI transition detection
        "weight_course_content":     1.4,
        "weight_rough_work":         1.4,   # fragments, bullets, gaps = authentic
    },
    "discussion": {
        "personal_voice_authentic":  True,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     1.3,
        "weight_ai_patterns":        1.0,
        "weight_course_content":     1.4,   # must engage with readings/peers
        "weight_rough_work":         0.9,
    },
    "draft": {
        "personal_voice_authentic":  True,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     1.0,
        "weight_ai_patterns":        1.0,
        "weight_course_content":     1.0,
        "weight_rough_work":         1.5,   # in-progress messiness is the signal
    },
    "personal": {
        "personal_voice_authentic":  True,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     1.5,   # strongest personal-voice weighting
        "weight_ai_patterns":        1.0,
        "weight_course_content":     1.2,
        "weight_rough_work":         1.1,
    },
    "essay": {
        "personal_voice_authentic":  False,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     0.5,   # formal register → personal voice quieter
        "weight_ai_patterns":        1.3,
        "weight_course_content":     1.3,
        "weight_rough_work":         1.3,   # still value intellectual struggle
    },
    "lab": {
        "personal_voice_authentic":  False,
        "invert_sentence_signals":   False,
        "weight_personal_voice":     0.4,
        "weight_ai_patterns":        1.5,
        "weight_course_content":     1.5,   # specific experimental details essential
        "weight_rough_work":         1.1,
    },
    "outline": {
        # Hierarchical lists / bullets = authentic; polished prose = suspicious (like notes).
        # Outlines don't need personal voice.  AI-generated outlines tend to be
        # suspiciously symmetrical with generic section headings.
        "personal_voice_authentic":  False,
        "invert_sentence_signals":   True,
        "weight_personal_voice":     0.7,
        "weight_ai_patterns":        1.6,   # generic symmetrical structure is a flag
        "weight_course_content":     1.3,   # should reference course material
        "weight_rough_work":         1.2,   # planning docs can be rough
    },
}

DEFAULT_TEMPLATES: dict = {
    "Notes / Summary": {
        "description": "Lecture notes, reading summaries, and any note-taking work",
        "assignment_type": "complete_incomplete",
        "min_word_count": 100,
        "post_min_words": 100,
        "reply_min_words": 30,
        "run_aic": False,
        "aic_mode": "notes",
        "aic_context": "standard",
        "aic_sensitivity": "lenient",
        "keywords": ["notes", "note", "summary", "recap", "reading",
                     "module", "lecture", "chapter"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["notes"],
    },
    "Outline / Structure": {
        "description": "Structured outlines, topic trees, hierarchical plans, and pre-writing frameworks",
        "assignment_type": "complete_incomplete",
        "min_word_count": 75,
        "post_min_words": 75,
        "reply_min_words": 25,
        "run_aic": True,
        "aic_mode": "outline",
        "aic_context": "standard",
        "aic_sensitivity": "lenient",
        "keywords": ["outline", "structure", "framework", "hierarchy",
                     "map", "pre-writing", "prewriting", "skeleton"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["outline"],
    },
    "Discussion / Response": {
        "description": "Discussion board posts, replies, and peer responses",
        "assignment_type": "discussion_forum",
        "min_word_count": 200,
        "post_min_words": 200,
        "reply_min_words": 50,
        "run_aic": True,
        "aic_mode": "discussion",
        "aic_context": "standard",
        "aic_sensitivity": "medium",
        "keywords": ["discussion", "forum", "post", "reply", "thread", "respond"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["discussion"],
    },
    "Draft (any stage)": {
        "description": "In-progress drafts, rough work, brainstorming, and outlines",
        "assignment_type": "complete_incomplete",
        "min_word_count": 150,
        "post_min_words": 150,
        "reply_min_words": 50,
        "run_aic": True,
        "aic_mode": "draft",
        "aic_context": "standard",
        "aic_sensitivity": "lenient",
        "keywords": ["draft", "brainstorm", "rough", "in-progress", "plan"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["draft"],
    },
    "Personal / Reflective": {
        "description": "Journals, reflections, personal responses, and self-assessments",
        "assignment_type": "complete_incomplete",
        "min_word_count": 150,
        "post_min_words": 200,
        "reply_min_words": 50,
        "run_aic": True,
        "aic_mode": "personal",
        "aic_context": "community_college",
        "aic_sensitivity": "lenient",
        "keywords": ["reflection", "journal", "response", "reflect", "personal", "self"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["personal"],
    },
    "Formal Essay / Research": {
        "description": "Formal essays, research papers, analytical and argumentative writing",
        "assignment_type": "complete_incomplete",
        "min_word_count": 400,
        "post_min_words": 400,
        "reply_min_words": 100,
        "run_aic": True,
        "aic_mode": "essay",
        "aic_context": "standard",
        "aic_sensitivity": "high",
        "keywords": ["essay", "paper", "report", "analysis", "research",
                     "argument", "thesis", "final"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["essay"],
    },
    "Lab / Technical": {
        "description": "Lab reports, technical write-ups, and methodology sections",
        "assignment_type": "complete_incomplete",
        "min_word_count": 200,
        "post_min_words": 200,
        "reply_min_words": 50,
        "run_aic": True,
        "aic_mode": "lab",
        "aic_context": "standard",
        "aic_sensitivity": "high",
        "keywords": ["lab", "technical", "report", "experiment", "methodology",
                     "procedure", "results", "data"],
        "is_system_default": True,
        **AIC_MODE_WEIGHT_PRESETS["lab"],
    },
}

# Names of templates that ship with the app and cannot be deleted
SYSTEM_DEFAULT_NAMES: frozenset = frozenset(
    name for name, t in DEFAULT_TEMPLATES.items() if t.get("is_system_default")
)

# Field defaults for new templates
TEMPLATE_FIELD_DEFAULTS: dict = {
    "description": "",
    "assignment_type": "complete_incomplete",
    "min_word_count": 200,
    "post_min_words": 200,
    "reply_min_words": 50,
    "run_aic": False,
    "aic_mode": "auto",
    "aic_context": "standard",
    "aic_sensitivity": "medium",
    "keywords": [],
    "is_system_default": False,
    # AIC signal config — inline weights (mode preset values on creation)
    **AIC_MODE_WEIGHT_PRESETS["auto"],
}

# Human-readable labels for AIC modes (v3.0)
AIC_MODE_LABELS = {
    "auto":       "Auto-detect",
    "notes":      "Notes / Summary",
    "outline":    "Outline / Structure",
    "discussion": "Discussion / Response",
    "draft":      "Draft (any stage)",
    "personal":   "Personal / Reflective",
    "essay":      "Formal Essay / Research",
    "lab":        "Lab / Technical",
}

# Migration map: old aic_profile keys → new aic_mode keys
_AIC_PROFILE_MIGRATION = {
    "standard":           "auto",
    "personal_reflection": "personal",
    "analytical_essay":   "essay",
    "discussion_post":    "discussion",
    "rough_draft":        "draft",
}

AIC_CONTEXT_LABELS = {
    "standard":          "Standard",
    "community_college": "Community College (more lenient)",
}

AIC_SENSITIVITY_LABELS = {
    "lenient": "Lenient",
    "medium":  "Medium",
    "high":    "High",
    "strict":  "Strict",
}

AIC_STUDENT_PROFILE_LABELS = {
    "standard":            "Standard",
    "esl":                 "ESL / English Language Learner",
    "neurodivergent":      "Neurodivergent",
    "learning_disability": "Learning Disability",
    "first_generation":    "First-Generation Student",
}

ASSIGNMENT_TYPE_LABELS = {
    "complete_incomplete": "Complete / Incomplete",
    "discussion_forum":    "Discussion Forum",
    "mixed":               "Mixed (auto-detect)",
}


# ---------------------------------------------------------------------------
# AIC config helper — single extraction point used by workers and run_dialog
# ---------------------------------------------------------------------------

def get_aic_config(template: dict) -> dict:
    """Extract AIC runtime config from a template dict.

    Returns a flat dict with all 7 keys the analyzer needs.
    Falls back to TEMPLATE_FIELD_DEFAULTS for any key missing from the template
    (backward compat: stored templates that predate weight fields get 1.0 multipliers).
    """
    mode = template.get("aic_mode", "auto")
    # Preset provides the safe fallback chain: template value > mode preset > auto preset
    preset = AIC_MODE_WEIGHT_PRESETS.get(mode, AIC_MODE_WEIGHT_PRESETS["auto"])
    d = TEMPLATE_FIELD_DEFAULTS
    return {
        "aic_mode":                 mode,
        "personal_voice_authentic": template.get("personal_voice_authentic",
                                        preset["personal_voice_authentic"]),
        "invert_sentence_signals":  template.get("invert_sentence_signals",
                                        preset["invert_sentence_signals"]),
        "weight_personal_voice":    template.get("weight_personal_voice",
                                        preset["weight_personal_voice"]),
        "weight_ai_patterns":       template.get("weight_ai_patterns",
                                        preset["weight_ai_patterns"]),
        "weight_course_content":    template.get("weight_course_content",
                                        preset["weight_course_content"]),
        "weight_rough_work":        template.get("weight_rough_work",
                                        preset["weight_rough_work"]),
    }


def aic_config_from_mode(mode: str) -> dict:
    """Build an aic_config dict from a bare mode key (no template needed)."""
    preset = AIC_MODE_WEIGHT_PRESETS.get(mode, AIC_MODE_WEIGHT_PRESETS["auto"])
    return {"aic_mode": mode, **preset}


# ---------------------------------------------------------------------------
# Load / save
# ---------------------------------------------------------------------------

def _load_file() -> dict:
    if not TEMPLATES_FILE.exists():
        return {}
    try:
        return json.loads(TEMPLATES_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_file(data: dict) -> None:
    try:
        TEMPLATES_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass


def _migrate_template(tmpl: dict) -> dict:
    """Migrate a template from aic_profile (v2) to aic_mode (v3) in-place. Returns tmpl."""
    if "aic_profile" in tmpl and "aic_mode" not in tmpl:
        old = tmpl.pop("aic_profile")
        tmpl["aic_mode"] = _AIC_PROFILE_MIGRATION.get(old, "auto")
    return tmpl


def load_templates() -> dict:
    """Return templates dict. Built-ins are included; user edits/additions win."""
    stored = _load_file().get("templates", {})
    # Migrate any stored templates that still use the old aic_profile field
    stored = {name: _migrate_template(t) for name, t in stored.items()}
    merged = {**DEFAULT_TEMPLATES}
    merged.update(stored)
    # Re-apply the system flag after merge so stored edits can't accidentally strip it
    for name in SYSTEM_DEFAULT_NAMES:
        if name in merged:
            merged[name]["is_system_default"] = True
    return merged


def save_templates(templates: dict) -> None:
    data = _load_file()
    data["templates"] = templates
    _save_file(data)


def load_mappings() -> dict:
    """Return {mapping_key: template_name | None} cache."""
    return _load_file().get("mappings", {})


def save_mappings(mappings: dict) -> None:
    data = _load_file()
    data["mappings"] = mappings
    _save_file(data)


def set_mapping(course_id: int, group_name: str, template_name: Optional[str]) -> None:
    """Persist a single mapping entry."""
    mappings = load_mappings()
    mappings[mapping_key(course_id, group_name)] = template_name
    save_mappings(mappings)


# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

def mapping_key(course_id: int, group_name: str) -> str:
    return f"{course_id}:{group_name}"


# ---------------------------------------------------------------------------
# Auto-matching
# ---------------------------------------------------------------------------

def auto_match(group_name: str, templates: dict) -> Optional[str]:
    """
    Fuzzy keyword match — returns template name with most keyword hits, or None.
    Substring match scores 2 pts; whole-token match scores 1 pt.
    """
    name_lower = group_name.lower()
    name_tokens = set(re.split(r"[\s\-_/\.]+", name_lower))

    best_name: Optional[str] = None
    best_score = 0

    for tname, tmpl in templates.items():
        keywords = [k.lower() for k in tmpl.get("keywords", [])]
        score = 0
        for kw in keywords:
            if kw in name_lower:
                score += 2
            elif kw in name_tokens:
                score += 1
        if score > best_score:
            best_score = score
            best_name = tname

    return best_name if best_score > 0 else None


def resolve_group(
    course_id: int, group_name: str, templates: dict, mappings: dict
) -> tuple[Optional[str], str]:
    """
    Return (template_name, match_source).
    match_source: 'cached' | 'keyword' | 'none'
    """
    key = mapping_key(course_id, group_name)
    if key in mappings:
        tname = mappings[key]
        if tname is None:
            return None, "cached"           # explicitly unassigned
        return (tname if tname in templates else None), "cached"
    matched = auto_match(group_name, templates)
    return matched, ("keyword" if matched else "none")
