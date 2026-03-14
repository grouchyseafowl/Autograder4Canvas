"""
Credential management for Canvas Autograder.
Shared by both the TUI (run_autograder.py) and the GUI.
"""
import os
import json
import platform
from pathlib import Path
from typing import Optional, Tuple


def get_credentials_file() -> Path:
    """Get path to credentials.json in platform config directory."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        config_dir = base / "CanvasAutograder"
    elif system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        config_dir = Path.home() / ".config" / "CanvasAutograder"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "credentials.json"


def load_credentials() -> dict:
    """Load credentials from JSON file (profile format)."""
    cf = get_credentials_file()
    if cf.exists():
        try:
            with open(cf, 'r', encoding='utf-8') as f:
                data = json.load(f)
            # Migrate flat format to profile format if needed
            if "profiles" not in data and (data.get("canvas_base_url") or data.get("canvas_api_token")):
                url = data.get("canvas_base_url", "")
                token = data.get("canvas_api_token", "")
                name = profile_name_from_url(url) if url else "default"
                data = {
                    "active_profile": name,
                    "profiles": {
                        name: {"canvas_base_url": url, "canvas_api_token": token}
                    }
                }
                save_credentials(data)
            return data
        except (ValueError, IOError):
            pass
    return {"active_profile": "", "profiles": {}}


def save_credentials(data: dict) -> None:
    """Save credentials to JSON file."""
    cf = get_credentials_file()
    with open(cf, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)


def profile_name_from_url(url: str) -> str:
    """Derive a short profile name from a Canvas URL."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or url
    except Exception:
        host = url
    if host.endswith(".instructure.com"):
        return host.replace(".instructure.com", "")
    return host


def get_active_profile(data: dict = None) -> Tuple[Optional[str], dict]:
    """Return (name, profile_dict) for the active profile, or (None, {})."""
    if data is None:
        data = load_credentials()
    profiles = data.get("profiles", {})
    active = data.get("active_profile", "")
    if active and active in profiles:
        return active, profiles[active]
    if profiles:
        name = next(iter(profiles))
        return name, profiles[name]
    return None, {}


def set_env_from_profile(data: dict = None) -> None:
    """Set CANVAS_BASE_URL and CANVAS_API_TOKEN env vars from active profile."""
    _, profile = get_active_profile(data)
    if profile.get("canvas_base_url"):
        os.environ["CANVAS_BASE_URL"] = profile["canvas_base_url"]
    if profile.get("canvas_api_token"):
        os.environ["CANVAS_API_TOKEN"] = profile["canvas_api_token"]


def save_canvas_url_permanently(canvas_url: str) -> None:
    """Save Canvas URL to active profile in credentials.json."""
    try:
        data = load_credentials()
        name, _ = get_active_profile(data)
        if not name:
            name = profile_name_from_url(canvas_url)
        if "profiles" not in data:
            data["profiles"] = {}
        if name not in data["profiles"]:
            data["profiles"][name] = {}
        data["profiles"][name]["canvas_base_url"] = canvas_url
        data["active_profile"] = name
        save_credentials(data)
        os.environ["CANVAS_BASE_URL"] = canvas_url
    except Exception as e:
        print(f"  Could not save URL: {e}")


def save_token_permanently(token: str) -> None:
    """Save token to active profile in credentials.json."""
    try:
        data = load_credentials()
        name, _ = get_active_profile(data)
        if not name:
            name = "default"
        if "profiles" not in data:
            data["profiles"] = {}
        if name not in data["profiles"]:
            data["profiles"][name] = {}
        data["profiles"][name]["canvas_api_token"] = token
        data["active_profile"] = name
        save_credentials(data)
        os.environ["CANVAS_API_TOKEN"] = token
    except Exception as e:
        print(f"  Could not save token: {e}")


def remove_saved_canvas_url() -> None:
    """Remove saved Canvas URL from active profile."""
    try:
        data = load_credentials()
        name, profile = get_active_profile(data)
        if name and "canvas_base_url" in profile:
            del data["profiles"][name]["canvas_base_url"]
            save_credentials(data)
        if "CANVAS_BASE_URL" in os.environ:
            del os.environ["CANVAS_BASE_URL"]
    except Exception as e:
        print(f"  Could not remove URL: {e}")


def remove_saved_token() -> None:
    """Remove saved Canvas API token from active profile."""
    try:
        data = load_credentials()
        name, profile = get_active_profile(data)
        if name and "canvas_api_token" in profile:
            del data["profiles"][name]["canvas_api_token"]
            save_credentials(data)
        if "CANVAS_API_TOKEN" in os.environ:
            del os.environ["CANVAS_API_TOKEN"]
    except Exception as e:
        print(f"  Could not remove token: {e}")
