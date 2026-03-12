#!/usr/bin/env python3
"""
Canvas Autograder Bootstrap
Cross-platform setup: Python check, venv, pip install, credentials, then launch.
Stdlib-only (runs before venv exists).
"""

import os
import sys
import subprocess
import platform
import shutil
import json
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. UTF-8 encoding fix for Windows cmd.exe
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7

# ---------------------------------------------------------------------------
# 2. Python version check (3.7+)
# ---------------------------------------------------------------------------
def check_python_version():
    v = sys.version_info
    if v >= (3, 7):
        return
    print(f"Python 3.7+ is required (you have {v.major}.{v.minor}.{v.micro}).")
    print("Download from: https://www.python.org/downloads/")
    try:
        import webbrowser
        webbrowser.open("https://www.python.org/downloads/")
    except Exception:
        pass
    input("Press Enter to exit...")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Microsoft Store stub detection (Windows)
# ---------------------------------------------------------------------------
def is_ms_store_python():
    if sys.platform != "win32":
        return False
    return "WindowsApps" in sys.executable

# ---------------------------------------------------------------------------
# 4. Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).parent.resolve()          # src/ or Resources/
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"
AUTOGRADER_SCRIPT = SCRIPT_DIR / "run_autograder.py"

def _get_venv_dir():
    """Determine venv location."""
    if "Contents/Resources" in str(SCRIPT_DIR):
        return Path.home() / ".canvas_autograder_venv"
    return SCRIPT_DIR.parent / ".venv"

VENV_DIR = _get_venv_dir()

def _venv_python():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"

def _venv_pip():
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    return VENV_DIR / "bin" / "pip"

# ---------------------------------------------------------------------------
# 5. Venv creation / validation
# ---------------------------------------------------------------------------
def ensure_venv():
    """Create or repair the virtual environment."""
    venv_py = _venv_python()

    # If venv python exists, health-check it
    if venv_py.exists():
        try:
            subprocess.run(
                [str(venv_py), "-c", ""],
                capture_output=True, timeout=10
            ).check_returncode()
            return  # healthy
        except Exception:
            print("  Virtual environment is broken -- rebuilding...")
            shutil.rmtree(VENV_DIR, ignore_errors=True)

    print("  Creating virtual environment (one-time setup)...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", str(VENV_DIR)],
        capture_output=True
    )
    if result.returncode != 0:
        print("  ERROR: Could not create virtual environment.")
        print(result.stderr.decode(errors="replace"))
        if sys.platform == "win32":
            print()
            print("  This may happen with Microsoft Store Python.")
            print("  Install Python from https://www.python.org/downloads/")
            try:
                import webbrowser
                webbrowser.open("https://www.python.org/downloads/")
            except Exception:
                pass
        shutil.rmtree(VENV_DIR, ignore_errors=True)
        input("Press Enter to exit...")
        sys.exit(1)
    print("  Virtual environment created.")

# ---------------------------------------------------------------------------
# 6. pip install
# ---------------------------------------------------------------------------
def ensure_dependencies():
    """Install packages from requirements.txt if any are missing."""
    if not REQUIREMENTS_FILE.exists():
        return

    pip_exe = _venv_pip()
    venv_py = _venv_python()

    if not pip_exe.exists() or not venv_py.exists():
        # venv broken somehow
        ensure_venv()

    # Quick check: are all required packages installed?
    try:
        with open(REQUIREMENTS_FILE, "r", encoding="utf-8") as f:
            reqs = [
                line.strip().split("==")[0].split(">=")[0].split("[")[0].lower()
                for line in f if line.strip() and not line.startswith("#")
            ]
        result = subprocess.run(
            [str(pip_exe), "list", "--format=freeze"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            installed = {
                line.split("==")[0].lower()
                for line in result.stdout.strip().splitlines()
                if "==" in line
            }
            if all(r in installed for r in reqs):
                return  # all present
    except Exception:
        pass

    print("  Installing required packages...")
    # Upgrade pip first
    subprocess.run(
        [str(venv_py), "-m", "pip", "install", "--quiet", "--upgrade", "pip"],
        capture_output=True
    )
    result = subprocess.run(
        [str(pip_exe), "install", "--quiet", "-r", str(REQUIREMENTS_FILE)],
        capture_output=True
    )
    if result.returncode != 0:
        print("  ERROR: Package installation failed.")
        print(result.stderr.decode(errors="replace"))
        print("  Check your internet connection and try again.")
        input("Press Enter to exit...")
        sys.exit(1)
    print("  Packages installed.")

# ---------------------------------------------------------------------------
# 7. Credential management (JSON-based)
# ---------------------------------------------------------------------------
def _get_config_dir():
    """Platform config directory (mirrors autograder_utils.get_config_dir)."""
    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        d = base / "CanvasAutograder"
    elif system == "Darwin":
        d = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        d = Path.home() / ".config" / "CanvasAutograder"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _creds_file():
    return _get_config_dir() / "credentials.json"

def _load_creds():
    cf = _creds_file()
    if cf.exists():
        try:
            with open(cf, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}

def _save_creds(creds):
    cf = _creds_file()
    cf.parent.mkdir(parents=True, exist_ok=True)
    with open(cf, "w", encoding="utf-8") as f:
        json.dump(creds, f, indent=2)

def _migrate_old_credentials():
    """Migrate from old credentials.bat or env vars on first run."""
    creds = _load_creds()
    if creds.get("canvas_base_url") and creds.get("canvas_api_token"):
        return creds  # already migrated

    # Try old credentials.bat (look in several places)
    bat_paths = []
    # scripts/windows/credentials.bat (relative to project root)
    project_root = SCRIPT_DIR.parent
    bat_paths.append(project_root / "scripts" / "windows" / "credentials.bat")
    bat_paths.append(project_root / "credentials.bat")
    # AUTOGRADER_CREDS_FILE env var from old run.bat
    old_creds_env = os.environ.get("AUTOGRADER_CREDS_FILE", "")
    if old_creds_env:
        bat_paths.insert(0, Path(old_creds_env))

    for bat_path in bat_paths:
        if bat_path.exists():
            try:
                with open(bat_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.lower().startswith("set "):
                            rest = line[4:]
                            if "=" in rest:
                                k, v = rest.split("=", 1)
                                k = k.strip().upper()
                                if k == "CANVAS_BASE_URL" and v and "yourschool" not in v:
                                    creds["canvas_base_url"] = v
                                elif k == "CANVAS_API_TOKEN" and v and v != "your_api_token_here":
                                    creds["canvas_api_token"] = v
            except Exception:
                pass
            if creds.get("canvas_base_url") and creds.get("canvas_api_token"):
                break

    # Also check env vars (set by old shell configs)
    if not creds.get("canvas_base_url"):
        env_url = os.environ.get("CANVAS_BASE_URL", "")
        if env_url and "yourschool" not in env_url:
            creds["canvas_base_url"] = env_url
    if not creds.get("canvas_api_token"):
        env_tok = os.environ.get("CANVAS_API_TOKEN", "")
        if env_tok and env_tok != "your_api_token_here":
            creds["canvas_api_token"] = env_tok

    if creds.get("canvas_base_url") or creds.get("canvas_api_token"):
        _save_creds(creds)
        print("  Migrated existing credentials to new JSON format.")

    return creds

def _prompt_credentials(creds):
    """Interactive first-time credential setup if values are missing."""
    changed = False

    if not creds.get("canvas_base_url"):
        print()
        print("  " + "=" * 56)
        print("   First-Time Setup")
        print("  " + "=" * 56)
        print("  Enter your Canvas credentials below. They will be saved")
        print("  so you won't be asked again.")
        print()
        print("  Canvas URL -- the web address you use to log in to Canvas.")
        print("  Example: https://myschool.instructure.com")
        print()
        try:
            url = input("  Canvas URL: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(1)
        if not url:
            print("  No URL entered. Please run again.")
            input("Press Enter to exit...")
            sys.exit(1)
        creds["canvas_base_url"] = url
        changed = True

    if not creds.get("canvas_api_token"):
        print()
        print("  API Token -- find it in Canvas:")
        print("    1. Click your profile picture (top right)")
        print("    2. Click Settings")
        print("    3. Scroll to Approved Integrations")
        print("    4. Click New Access Token, give it a name, click Generate")
        print("    5. Copy the token and paste it here")
        print()
        try:
            token = input("  API Token: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Cancelled.")
            sys.exit(1)
        if not token:
            print("  No token entered. Please run again.")
            input("Press Enter to exit...")
            sys.exit(1)
        creds["canvas_api_token"] = token
        changed = True

    if changed:
        _save_creds(creds)
        print()
        print("  Credentials saved.")

    return creds

def setup_credentials():
    """Load/migrate/prompt for credentials, set env vars."""
    creds = _migrate_old_credentials()
    creds = _prompt_credentials(creds)

    # Set env vars so run_autograder.py can read them
    if creds.get("canvas_base_url"):
        os.environ["CANVAS_BASE_URL"] = creds["canvas_base_url"]
    if creds.get("canvas_api_token"):
        os.environ["CANVAS_API_TOKEN"] = creds["canvas_api_token"]

# ---------------------------------------------------------------------------
# 8. Launch autograder
# ---------------------------------------------------------------------------
def launch():
    """Exec into venv python + run_autograder.py."""
    venv_py = str(_venv_python())
    script = str(AUTOGRADER_SCRIPT)

    if not Path(script).exists():
        print(f"  ERROR: {script} not found.")
        input("Press Enter to exit...")
        sys.exit(1)

    args = [venv_py, script] + sys.argv[1:]

    if sys.platform == "win32":
        # os.execv doesn't truly replace on Windows; use subprocess
        rc = subprocess.run(args).returncode
        sys.exit(rc)
    else:
        os.execv(venv_py, args)

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print()
    print("========================================")
    print("   Canvas Autograder")
    print("========================================")
    print()

    check_python_version()

    if is_ms_store_python():
        print("  WARNING: Microsoft Store Python detected.")
        print("  This may not work correctly. Install from https://www.python.org/downloads/")
        print()

    ensure_venv()
    ensure_dependencies()
    setup_credentials()
    print()
    launch()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        import traceback
        print("\n" + "=" * 60)
        print("  Bootstrap error")
        print("=" * 60)
        traceback.print_exc()
        print()
        input("Press Enter to close...")
        sys.exit(1)
