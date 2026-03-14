"""
Settings management for Canvas Autograder.
Shared by both the TUI (run_autograder.py) and the GUI.
"""
from pathlib import Path

SETTINGS_FILE = Path.home() / ".canvas_autograder_settings"

_DEFAULTS = {
    "auto_open_folder": True,
    "cleanup_mode": "none",               # "none", "archive", or "trash"
    "cleanup_threshold_days": 180,
    "cleanup_targets": "all",             # "all" or comma-separated: "ad_csv,ad_excel,ad_txt,ci_csv,df_csv"
    "grade_missing_as_incomplete": False, # grade unsubmitted past-due assignments as Incomplete
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
