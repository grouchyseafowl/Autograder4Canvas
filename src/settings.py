"""
Settings management for Canvas Autograder.
Shared by both the TUI (run_autograder.py) and the GUI.
"""
from pathlib import Path

SETTINGS_FILE = Path.home() / ".canvas_autograder_settings"

_DEFAULTS = {
    "auto_open_folder": False,
    "cleanup_mode": "none",               # "none", "archive", or "trash" (legacy TUI key)
    "cleanup_threshold_days": 180,        # legacy TUI key
    "cleanup_targets": "all",             # legacy TUI key
    "grade_missing_as_incomplete": False, # grade unsubmitted past-due assignments as Incomplete
    # Grading defaults (used as pre-populated values in run dialogs)
    "default_min_words": 200,             # C/I assignment minimum word count
    "default_post_words": 200,            # discussion post minimum word count
    "default_reply_words": 50,            # discussion reply minimum word count
    # Data retention — auto-delete internal SQLite data on app startup
    "data_retention_enabled": True,       # master toggle
    "data_retention_days": 180,           # age threshold (total days = years*365 + days)
    "data_retention_years": 0,            # age threshold — years component
    "data_retention_grading": True,       # include grading report data (C/I, discussion)
    "data_retention_aic": True,           # include Academic Integrity (AIC) data
    "data_retention_insights": True,      # include Insights analysis data
    "data_retention_notes": False,        # include teacher notes
    "data_retention_notes_years": 3,      # notes age threshold — years
    "data_retention_notes_days": 0,       # notes age threshold — days
    # Institution / population profile (legacy)
    "institution_type": "community_college",  # community_college, four_year, university, other
    "context_profile": "community_college",   # maps to config/context_profiles/<id>.yaml (legacy)
    # Phase 8: Two-axis weight system — education level (fallback when not in credential profile)
    # Per-institution values live in credentials.json; this is the app-wide fallback.
    "education_level": "community_college",   # high_school, community_college, four_year, university, online
    "population_esl": "none",                 # none, low, moderate, high
    "population_first_gen": "none",           # none, low, moderate, high
    "population_neurodivergent_aware": False,  # enable neurodivergent-aware scoring
    # Insights Engine
    "insights_whisper_model": "base",
    "insights_translation_backend": "ollama",
    "insights_translation_model": "llama3.1:8b",
    "insights_model_tier": "auto",            # persistent depth toggle default (auto/lightweight/medium/deep_thinking)
    "insights_throttle_delay": 20,
    "insights_keep_awake": True,
    "insights_deepening_pass": True,
    "insights_setup_complete": False,         # gates first-run wizard
    "insights_cloud_privacy": "",             # "", "free_enhancement", "privacy_enhancement", "browser_handoff", "institutional_dpa"
    # Accessibility
    "font_scale": 1.25,                   # 1.0 = small, 1.25 = default, 1.5 = extra large
    "insights_draft_feedback": False,
    "insights_translate_enabled": True,
    "insights_transcribe_enabled": True,
    "insights_image_transcribe_enabled": True,
    "review_sidebar_show_all": True,
    "warn_grading_type_reinterpret": True,  # warn when existing grades will be reinterpreted
}


def load_settings() -> dict:
    """Load settings from file, returning defaults for any missing keys."""
    if not SETTINGS_FILE.exists():
        return dict(_DEFAULTS)

    try:
        settings: dict = {}
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if value.lower() in ('true', '1', 'yes'):
                        settings[key] = True
                    elif value.lower() in ('false', '0', 'no'):
                        settings[key] = False
                    elif value.isdigit():
                        settings[key] = int(value)
                    else:
                        settings[key] = value
        return {**_DEFAULTS, **settings}
    except Exception:
        return dict(_DEFAULTS)


def save_settings(settings: dict) -> bool:
    """Save settings dict to file. Returns True on success."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write("# Canvas Autograder Settings\n")
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        return True
    except Exception as e:
        print(f"Warning: Could not save settings: {e}")
        return False
