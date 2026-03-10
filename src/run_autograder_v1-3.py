#!/usr/bin/env python3
"""
Canvas Autograder Launcher
Cross-platform launcher for Canvas autograding tools
"""

import os
import sys
import subprocess
import platform
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import getpass

# Windows cmd.exe defaults to cp1252; switch stdout/stderr to UTF-8 so
# emoji in print() doesn't crash with UnicodeEncodeError.
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # Python < 3.7 fallback: silently continue

# Try to import the utilities module (may not exist in all installations)
try:
    from autograder_utils import (
        get_output_base_dir, get_output_dir, get_archive_dir,
        move_to_trash, trash_old_files, archive_old_files,
        open_folder, print_output_location,
        is_first_run, run_first_time_setup, change_output_directory,
        SUBDIRS
    )
    HAS_UTILS = True
except ImportError:
    HAS_UTILS = False
    # Fallback subdirectory names (must match autograder_utils.py SUBDIRS)
    SUBDIRS = {
        "Academic_Dishonesty": "Academic Dishonesty Reports",
        "Discussion_Forum": "Discussion Forums",
        "Complete-Incomplete": "Complete-Incomplete Assignments",
    }

# === CONFIGURATION ===
def get_base_exports_dir() -> Path:
    """Get base exports directory in a cross-platform way."""
    if HAS_UTILS:
        return get_output_base_dir()
    
    # Fallback implementation
    system = platform.system()
    
    if os.path.isdir("/output"):
        return Path("/output")
    
    if system == "Windows":
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        documents = Path.home() / "Documents"
    
    return documents / "Autograder Rationales"

SCRIPT_DIR = Path(__file__).parent.resolve()  # Where this script lives (src/ or Resources/)
PROGRAMS_DIR = SCRIPT_DIR / "Programs"
REQUIREMENTS_FILE = SCRIPT_DIR / "requirements.txt"

# Determine where to put the .venv
# If we're inside an app bundle (Resources/), put venv in user's home
# Otherwise, put it in the parent of src/
if "Contents/Resources" in str(SCRIPT_DIR):
    # Running from inside .app bundle
    VENV_DIR = Path.home() / ".canvas_autograder_venv"
else:
    # Running from src/ folder
    BASE_DIR = SCRIPT_DIR.parent
    VENV_DIR = BASE_DIR / ".venv"

# Settings file location
SETTINGS_FILE = Path.home() / ".canvas_autograder_settings"

def print_header():
    """Print welcome header."""
    print("ðŸŽ“ Canvas Autograder")
    print("=" * 70)
    print()

def open_url_in_browser(url):
    """Open a URL in the default web browser."""
    import webbrowser
    try:
        webbrowser.open(url)
        return True
    except Exception:
        return False

def check_python_version():
    """Verify Python version is 3.7+."""
    version = sys.version_info
    if version < (3, 7):
        print("âŒ Python 3.7 or higher is required.")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        print()
        print("=" * 70)
        print("ðŸ“¥ PYTHON INSTALLATION REQUIRED")
        print("=" * 70)
        print()
        print("To use Canvas Autograder, you need Python 3.7 or higher.")
        print()
        print("Download from: https://www.python.org/downloads/")
        print()
        print("IMPORTANT for Windows users:")
        print("  âœ“ CHECK the box 'Add Python to PATH' during installation")
        print("  âœ“ This is required for the autograder to work properly")
        print()
        print("Options:")
        print("  [1] Open Python download page in browser")
        print("  [2] Exit and install manually")
        print()
        
        try:
            choice = input("Choose option (1 or 2, default=2): ").strip() or "2"
            
            if choice == "1":
                print("\nðŸŒ Opening Python download page in your browser...")
                if open_url_in_browser("https://www.python.org/downloads/"):
                    print("âœ… Browser opened successfully")
                else:
                    print("âš ï¸  Could not open browser automatically")
                    print("   Please manually visit: https://www.python.org/downloads/")
                
                print()
                print("After installing Python:")
                print("  1. Make sure to CHECK 'Add Python to PATH' (Windows)")
                print("  2. Complete the installation")
                print("  3. Press Enter to restart this program")
                print()
                input("Press Enter after installing Python to continue...")
                
                # Restart the script
                print("\nðŸ”„ Restarting Canvas Autograder...\n")
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                print("\nðŸ‘‹ Please install Python 3.7+ and run this program again.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\n\nðŸ‘‹ Goodbye!")
            sys.exit(1)
    
    print(f"âœ… Python {version.major}.{version.minor}.{version.micro}")

def check_pip():
    """Verify pip is available."""
    try:
        import pip
        print("âœ… pip available")
        return True
    except ImportError:
        print("âŒ pip is not installed.")
        print()
        print("=" * 70)
        print("ðŸ“¥ PIP INSTALLATION REQUIRED")
        print("=" * 70)
        print()
        print("pip is Python's package installer and is required for Canvas Autograder.")
        print()
        print("Installation instructions: https://pip.pypa.io/en/stable/installation/")
        print()
        print("Most Python installations include pip by default.")
        print("If you just installed Python, try restarting your terminal/command prompt.")
        print()
        print("Options:")
        print("  [1] Open pip installation guide in browser")
        print("  [2] Try restarting this script (if you just installed Python)")
        print("  [3] Exit")
        print()
        
        try:
            choice = input("Choose option (1/2/3, default=3): ").strip() or "3"
            
            if choice == "1":
                print("\nðŸŒ Opening pip installation guide in your browser...")
                if open_url_in_browser("https://pip.pypa.io/en/stable/installation/"):
                    print("âœ… Browser opened successfully")
                else:
                    print("âš ï¸  Could not open browser automatically")
                    print("   Please manually visit: https://pip.pypa.io/en/stable/installation/")
                
                print()
                print("After installing pip:")
                print("  1. Follow the installation instructions on the website")
                print("  2. Press Enter to restart this program")
                print()
                input("Press Enter after installing pip to continue...")
                
                # Restart the script
                print("\nðŸ”„ Restarting Canvas Autograder...\n")
                python = sys.executable
                os.execl(python, python, *sys.argv)
            elif choice == "2":
                # Restart the script
                print("\nðŸ”„ Restarting Canvas Autograder...\n")
                python = sys.executable
                os.execl(python, python, *sys.argv)
            else:
                print("\nðŸ‘‹ Please install pip and run this program again.")
                sys.exit(1)
        except (KeyboardInterrupt, EOFError):
            print("\n\nðŸ‘‹ Goodbye!")
            sys.exit(1)

def get_venv_python():
    """Get path to Python executable in virtual environment."""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "python.exe"
    else:
        return VENV_DIR / "bin" / "python"

def get_venv_pip():
    """Get path to pip executable in virtual environment."""
    if platform.system() == "Windows":
        return VENV_DIR / "Scripts" / "pip.exe"
    else:
        return VENV_DIR / "bin" / "pip"

def load_settings():
    """Load settings from file."""
    defaults = {
        "auto_open_folder": True,
        "cleanup_mode": "none",  # "none", "archive", or "trash"
        "cleanup_threshold_days": 180,
        "cleanup_targets": "all"  # "all" or comma-separated: "ad_csv,ad_excel,ad_txt,ci_csv,df_csv"
    }
    
    if not SETTINGS_FILE.exists():
        return defaults
    
    try:
        settings = {}
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    # Handle boolean values
                    if value.lower() in ('true', '1', 'yes'):
                        settings[key] = True
                    elif value.lower() in ('false', '0', 'no'):
                        settings[key] = False
                    # Handle integer values
                    elif value.isdigit():
                        settings[key] = int(value)
                    else:
                        settings[key] = value
        return {**defaults, **settings}
    except Exception:
        return defaults

def save_settings(settings):
    """Save settings to file."""
    try:
        with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
            f.write("# Canvas Autograder Settings\n")
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        return True
    except Exception as e:
        print(f"âš ï¸  Could not save settings: {e}")
        return False

def toggle_auto_open():
    """Toggle the auto-open folder setting."""
    settings = load_settings()
    current = settings.get("auto_open_folder", True)
    settings["auto_open_folder"] = not current
    
    if save_settings(settings):
        new_state = "ON" if settings["auto_open_folder"] else "OFF"
        print(f"âœ… Auto-open Grading Rationales folder is now {new_state}")
    
    return settings["auto_open_folder"]

def configure_cleanup():
    """Configure automatic cleanup settings."""
    settings = load_settings()
    system = platform.system()
    
    current_mode = settings.get("cleanup_mode", "none")
    current_days = settings.get("cleanup_threshold_days", 180)
    current_targets = settings.get("cleanup_targets", "all")
    
    print()
    print("ðŸ—‘ï¸  Automatic Cleanup Settings")
    print("=" * 50)
    print()
    print("This controls what happens to old grading rationale files")
    print("each time you run a grading tool.")
    print()
    print("Cleanup mode options:")
    print("  [N] None - Keep all files (do nothing)")
    print("  [A] Archive - Move old files to 'Archived Reports' subfolder")
    if system == "Darwin":
        print("  [T] Trash - Move old files to Trash")
    elif system == "Windows":
        print("  [T] Trash - Move old files to Recycle Bin")
    else:
        print("  [T] Trash - Move old files to Trash")
    print()
    
    # Show current settings
    mode_display = {"none": "None", "archive": "Archive", "trash": "Trash"}
    print(f"Current mode: {mode_display.get(current_mode, 'None')}")
    print(f"Current threshold: {current_days} days")
    if current_mode != "none":
        print(f"Current targets: {current_targets}")
    print()
    
    try:
        mode_choice = input("Choose cleanup mode (N/A/T, or Enter to keep current): ").strip().upper()
        
        if mode_choice == 'N':
            settings["cleanup_mode"] = "none"
        elif mode_choice == 'A':
            settings["cleanup_mode"] = "archive"
        elif mode_choice == 'T':
            settings["cleanup_mode"] = "trash"
        elif mode_choice != '':
            print("âŒ Invalid choice. Keeping current mode.")
        
        # Only ask for threshold and targets if mode is not "none"
        if settings.get("cleanup_mode", "none") != "none":
            print()
            print("How old should files be before cleanup?")
            print("  Common options: 30, 60, 90, 180, 365 days")
            days_input = input(f"Enter days (or Enter to keep {current_days}): ").strip()
            
            if days_input:
                try:
                    days = int(days_input)
                    if days < 1:
                        print("âŒ Days must be at least 1. Keeping current threshold.")
                    else:
                        settings["cleanup_threshold_days"] = days
                except ValueError:
                    print("âŒ Invalid number. Keeping current threshold.")
            
            # Ask which files to clean up
            print()
            print("Which output files should be automatically cleaned up?")
            print()
            print("  Academic Dishonesty Check:")
            print("    [1] CSV files only")
            print("    [2] Excel files only")
            print("    [3] TXT report files only")
            print("    [4] CSV and Excel files")
            print("    [5] All Academic Dishonesty files (CSV, Excel, TXT)")
            print()
            print("  Complete/Incomplete Autograder:")
            print("    [6] CSV files")
            print()
            print("  Discussion Forum Autograder:")
            print("    [7] CSV files")
            print()
            print("  Other options:")
            print("    [A] All files from all tools (default)")
            print()
            print("  (You can select multiple, e.g., '1 6 7' or '2,6')")

            target_input = input(f"Enter selection (or Enter to keep '{current_targets}'): ").strip().upper()

            if target_input:
                if target_input == 'A':
                    settings["cleanup_targets"] = "all"
                else:
                    # Parse and validate selections
                    selections = target_input.replace(',', ' ').split()
                    valid_targets = []

                    for sel in selections:
                        if sel == '1':
                            valid_targets.append("ad_csv")
                        elif sel == '2':
                            valid_targets.append("ad_excel")
                        elif sel == '3':
                            valid_targets.append("ad_txt")
                        elif sel == '4':
                            valid_targets.append("ad_csv")
                            valid_targets.append("ad_excel")
                        elif sel == '5':
                            valid_targets.append("ad_csv")
                            valid_targets.append("ad_excel")
                            valid_targets.append("ad_txt")
                        elif sel == '6':
                            valid_targets.append("ci_csv")
                        elif sel == '7':
                            valid_targets.append("df_csv")
                    
                    if valid_targets:
                        # Remove duplicates
                        valid_targets = list(dict.fromkeys(valid_targets))
                        settings["cleanup_targets"] = ",".join(valid_targets)
                    else:
                        print("âŒ No valid selections. Keeping current targets.")
        
        if save_settings(settings):
            new_mode = mode_display.get(settings.get("cleanup_mode", "none"), "None")
            new_days = settings.get("cleanup_threshold_days", 180)
            new_targets = settings.get("cleanup_targets", "all")
            print()
            if settings.get("cleanup_mode", "none") == "none":
                print(f"âœ… Cleanup mode set to: {new_mode}")
            else:
                print(f"âœ… Cleanup mode set to: {new_mode}")
                print(f"   Threshold: {new_days} days")
                print(f"   Targets: {new_targets}")
    
    except (KeyboardInterrupt, EOFError):
        print("\nâ­ï¸  Cancelled. Settings unchanged.")

def run_onetime_cleanup():
    """Run a one-time cleanup with user-specified options."""
    system = platform.system()
    base_dir = get_base_exports_dir()
    
    print()
    print("ðŸ—‘ï¸  One-Time Cleanup")
    print("=" * 50)
    print()
    print(f"Grading Rationales folder: {base_dir}")
    print()
    
    # Ask for cleanup mode
    print("Cleanup mode:")
    print("  [A] Archive - Move old files to 'Archived Reports' subfolder")
    if system == "Darwin":
        print("  [T] Trash - Move old files to Trash")
    elif system == "Windows":
        print("  [T] Trash - Move old files to Recycle Bin")
    else:
        print("  [T] Trash - Move old files to Trash")
    print("  [C] Cancel")
    print()
    
    try:
        mode_choice = input("Choose (A/T/C): ").strip().upper()
        
        if mode_choice == 'C' or mode_choice == '':
            print("â­ï¸  Cleanup cancelled.")
            return
        
        if mode_choice not in ('A', 'T'):
            print("âŒ Invalid choice. Cleanup cancelled.")
            return
        
        # Ask for threshold
        print()
        print("How old should files be before cleanup?")
        print("  Common options: 30, 60, 90, 180, 365 days")
        days_input = input("Enter days (default 180): ").strip()
        
        if days_input == '':
            threshold_days = 180
        else:
            try:
                threshold_days = int(days_input)
                if threshold_days < 1:
                    print("âŒ Days must be at least 1. Using default of 180.")
                    threshold_days = 180
            except ValueError:
                print("âŒ Invalid number. Using default of 180.")
                threshold_days = 180
        
        # Ask which tools/file types to clean
        print()
        print("Which output files do you want to clean up?")
        print()
        print("  Academic Dishonesty Check:")
        print("    [1] CSV files only")
        print("    [2] Excel files only")
        print("    [3] TXT report files only")
        print("    [4] CSV and Excel files")
        print("    [5] All Academic Dishonesty files (CSV, Excel, TXT)")
        print()
        print("  Complete/Incomplete Autograder:")
        print("    [6] CSV files")
        print()
        print("  Discussion Forum Autograder:")
        print("    [7] CSV files")
        print()
        print("  Other options:")
        print("    [A] All files from all tools")
        print("    [C] Cancel")
        print()
        print("  (You can select multiple, e.g., '1 6 7' or '2,6')")
        
        selection = input("Enter selection: ").strip().upper()
        
        if selection == 'C' or selection == '':
            print("â­ï¸  Cleanup cancelled.")
            return
        
        # Parse selection
        cleanup_targets = []
        
        if selection == 'A':
            # All files
            cleanup_targets = [
                ("Academic_Dishonesty", "csv"),
                ("Academic_Dishonesty", "excel"),
                ("Academic_Dishonesty", "txt"),
                ("Complete-Incomplete", "csv"),
                ("Discussion_Forum", "csv")
            ]
        else:
            # Parse individual selections
            # Handle both space and comma separators
            selections = selection.replace(',', ' ').split()
            
            for sel in selections:
                if sel == '1':
                    cleanup_targets.append(("Academic_Dishonesty", "csv"))
                elif sel == '2':
                    cleanup_targets.append(("Academic_Dishonesty", "excel"))
                elif sel == '3':
                    cleanup_targets.append(("Academic_Dishonesty", "txt"))
                elif sel == '4':
                    cleanup_targets.append(("Academic_Dishonesty", "csv"))
                    cleanup_targets.append(("Academic_Dishonesty", "excel"))
                elif sel == '5':
                    cleanup_targets.append(("Academic_Dishonesty", "csv"))
                    cleanup_targets.append(("Academic_Dishonesty", "excel"))
                    cleanup_targets.append(("Academic_Dishonesty", "txt"))
                elif sel == '6':
                    cleanup_targets.append(("Complete-Incomplete", "csv"))
                elif sel == '7':
                    cleanup_targets.append(("Discussion_Forum", "csv"))
        
        if not cleanup_targets:
            print("âŒ No valid selections. Cleanup cancelled.")
            return
        
        # Remove duplicates while preserving order
        seen = set()
        unique_targets = []
        for target in cleanup_targets:
            if target not in seen:
                seen.add(target)
                unique_targets.append(target)
        cleanup_targets = unique_targets
        
        # Show summary and confirm
        print()
        print(f"Will clean up files older than {threshold_days} days:")
        script_type_info = get_script_type_info()
        for script_type, file_type in cleanup_targets:
            info = script_type_info.get(script_type, {})
            folder_name = info.get("subdir", script_type)
            print(f"  â€¢ {folder_name}: {file_type.upper()} files")
        
        print()
        confirm = input("Proceed? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("â­ï¸  Cleanup cancelled.")
            return
        
        # Perform cleanup
        for script_type, file_type in cleanup_targets:
            info = script_type_info.get(script_type, {})
            target_dir = base_dir / info.get("subdir", script_type)
            
            if not target_dir.exists():
                print(f"\nâ„¹ï¸  Folder not found: {info.get('subdir', script_type)} (skipping)")
                continue
            
            print()
            print(f"Processing: {info.get('subdir', script_type)} ({file_type.upper()} files)")
            
            if mode_choice == 'A':
                archive_files_by_type(target_dir, script_type, file_type, threshold_days)
            else:
                trash_files_by_type(target_dir, script_type, file_type, threshold_days)
        
        print()
        print("âœ… One-time cleanup complete!")
    
    except (KeyboardInterrupt, EOFError):
        print("\nâ­ï¸  Cleanup cancelled.")

def create_virtual_environment():
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists():
        print("âœ… Virtual environment exists")
        return
    
    print("ðŸ“¦ Creating virtual environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        print("âœ… Virtual environment created")
    except subprocess.CalledProcessError as e:
        print(f"âŒ Failed to create virtual environment: {e}")
        sys.exit(1)

def check_dependencies_installed():
    """Check if required dependencies are already installed."""
    if not REQUIREMENTS_FILE.exists():
        return False
    
    pip_exe = get_venv_pip()
    python_exe = get_venv_python()
    
    if not pip_exe.exists() or not python_exe.exists():
        return False
    
    try:
        # Read requirements
        with open(REQUIREMENTS_FILE, 'r', encoding='utf-8') as f:
            requirements = [line.strip().split('==')[0].split('>=')[0].split('[')[0]
                          for line in f if line.strip() and not line.startswith('#')]
        
        # Check if each package is installed
        result = subprocess.run(
            [str(pip_exe), "list", "--format=freeze"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            return False
        
        installed = {line.split('==')[0].lower() for line in result.stdout.strip().split('\n') if '==' in line}
        
        for req in requirements:
            if req.lower() not in installed:
                return False
        
        return True
        
    except Exception:
        return False


def install_dependencies():
    """Install required dependencies if not already installed."""
    if not REQUIREMENTS_FILE.exists():
        print(f"âŒ requirements.txt not found at: {REQUIREMENTS_FILE}")
        sys.exit(1)
    
    # Check if dependencies are already installed
    if check_dependencies_installed():
        print("âœ… Dependencies already installed")
        return
    
    print("ðŸ“¦ Installing dependencies...")
    
    pip_exe = get_venv_pip()
    
    try:
        # Upgrade pip first
        subprocess.run(
            [str(pip_exe), "install", "--quiet", "--upgrade", "pip"],
            check=True,
            capture_output=True
        )
        
        # Install requirements
        subprocess.run(
            [str(pip_exe), "install", "--quiet", "-r", str(REQUIREMENTS_FILE)],
            check=True,
            capture_output=True
        )
        
        print("âœ… Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"âŒ Failed to install dependencies: {e}")
        print(f"   Error output: {e.stderr.decode() if e.stderr else 'N/A'}")
        sys.exit(1)

def verify_structure():
    """Verify project structure is correct."""
    if not PROGRAMS_DIR.exists():
        print(f"âŒ Missing 'Programs/' directory at: {PROGRAMS_DIR}")
        print()
        print("Expected: Programs/ folder in same directory as run_autograder.py")
        sys.exit(1)
    
    if not REQUIREMENTS_FILE.exists():
        print(f"âŒ Missing 'requirements.txt' at: {REQUIREMENTS_FILE}")
        sys.exit(1)

def get_script_type_info():
    """Get information about script types and directories."""
    return {
        "Academic_Dishonesty": {
            "display": "Academic Dishonesty Check",
            "pattern": "*Academic*Dishonesty*.py",
            "subdir": SUBDIRS.get("Academic_Dishonesty", "Academic Dishonesty Reports"),
            "subdir_key": "Academic_Dishonesty"
        },
        "Discussion_Forum": {
            "display": "Discussion Forum Autograder",
            "pattern": "*Discussion*Forum*.py",
            "subdir": SUBDIRS.get("Discussion_Forum", "Discussion Forums"),
            "subdir_key": "Discussion_Forum"
        },
        "Complete-Incomplete": {
            "display": "Complete/Incomplete Autograder",
            "pattern": "*Complete*Incomplete*.py",
            "subdir": SUBDIRS.get("Complete-Incomplete", "Complete-Incomplete Assignments"),
            "subdir_key": "Complete-Incomplete"
        }
    }

def find_scripts():
    """Find available autograder scripts."""
    script_types = get_script_type_info()
    found_scripts = {}
    
    for script_type, info in script_types.items():
        pattern = info["pattern"]
        matches = list(PROGRAMS_DIR.glob(pattern))
        if matches:
            found_scripts[script_type] = {
                "path": matches[0],
                "display": info["display"],
                "subdir": info["subdir"],
                "subdir_key": info["subdir_key"]  # Include subdir_key for cleanup identification
            }
    
    if not found_scripts:
        print("âŒ No autograder scripts found in:", PROGRAMS_DIR)
        print()
        print("Looking for:")
        for info in script_types.values():
            print(f"   â€¢ {info['pattern']}")
        sys.exit(1)
    
    return found_scripts

def select_script(scripts):
    """Prompt user to select which script to run or access settings."""
    base_dir = get_base_exports_dir()
    
    print()
    print("ðŸŽ“ Canvas Autograder - Main Menu")
    print("=" * 50)
    print()
    print("Grading Tools:")
    
    # Create ordered list
    script_list = []
    for script_type, info in scripts.items():
        script_list.append((script_type, info))
    
    # Display grading tool options
    for idx, (script_type, info) in enumerate(script_list, 1):
        print(f"  [{idx}] {info['display']}")
    
    print()
    print("Settings:")
    print(f"  [S] Change Grading Rationales folder location")
    print(f"      Current: {base_dir}")
    
    settings = load_settings()
    auto_open_status = "ON" if settings.get("auto_open_folder", True) else "OFF"
    print(f"  [A] Toggle auto-open Grading Rationales folder after grading [{auto_open_status}]")
    
    # Show cleanup setting status
    cleanup_mode = settings.get("cleanup_mode", "none")
    cleanup_days = settings.get("cleanup_threshold_days", 180)
    if cleanup_mode == "none":
        cleanup_status = "OFF"
    else:
        mode_label = "Archive" if cleanup_mode == "archive" else "Trash"
        cleanup_status = f"{mode_label} after {cleanup_days} days"
    print(f"  [C] Configure automatic cleanup of old files [{cleanup_status}]")
    print(f"  [R] Run one-time cleanup now")
    print(f"  [T] Change Canvas API token")
    print(f"  [U] Change Canvas URL")

    print(f"  [O] Open Grading Rationales folder")
    print(f"  [H] Help - Definitions and Instructions")
    print()
    print(f"  [Q] Quit")
    print()

    while True:
        try:
            choice = input(f"Enter choice (1-{len(script_list)}, S, A, C, R, T, U, O, H, or Q): ").strip().upper()
            
            # Check for settings options
            if choice == 'S':
                if HAS_UTILS:
                    change_output_directory()
                else:
                    print("âš ï¸  Settings not available (utilities module not found)")
                # Return None to indicate we should show the menu again
                return None
            elif choice == 'A':
                toggle_auto_open()
                return None
            elif choice == 'C':
                configure_cleanup()
                return None
            elif choice == 'R':
                run_onetime_cleanup()
                return None
            elif choice == 'T':
                change_canvas_token()
                return None
            elif choice == 'U':
                change_canvas_url()
                return None
            elif choice == 'O':
                print(f"ðŸ“‚ Opening: {base_dir}")
                if HAS_UTILS:
                    open_folder(base_dir)
                else:
                    # Fallback
                    system = platform.system()
                    if system == "Darwin":
                        subprocess.run(['open', str(base_dir)])
                    elif system == "Windows":
                        subprocess.run(['explorer', str(base_dir)])
                    else:
                        subprocess.run(['xdg-open', str(base_dir)])
                return None
            elif choice == 'H':
                show_help_menu()
                return None
            elif choice == 'Q':
                print("\nðŸ‘‹ Goodbye!")
                sys.exit(0)
            
            # Check for grading tool selection
            choice_num = int(choice)
            if 1 <= choice_num <= len(script_list):
                selected_type, selected_info = script_list[choice_num - 1]
                return selected_info
            else:
                print(f"âŒ Please enter a number between 1 and {len(script_list)}, S, A, C, R, T, O, H, or Q")
        except ValueError:
            print("âŒ Invalid input. Please try again.")
        except (KeyboardInterrupt, EOFError):
            print("\n\nðŸ‘‹ Goodbye!")
            sys.exit(0)

def get_canvas_url():
    """Get Canvas base URL from environment or user input."""
    canvas_url = os.environ.get("CANVAS_BASE_URL")

    if canvas_url:
        return canvas_url

    print()
    print("=" * 70)
    print("🌐 CANVAS URL REQUIRED")
    print("=" * 70)
    print()
    print("First, we need to know which Canvas site you use.")
    print()
    print("📍 WHERE TO FIND YOUR CANVAS URL:")
    print("=" * 70)
    print()
    print("1. Open your web browser")
    print("2. Log in to Canvas like you normally do")
    print("3. Look at the address bar at the top of your browser")
    print("4. Copy everything BEFORE '/courses' or '/login'")
    print()
    print("EXAMPLES:")
    print("  • If you see: https://example.instructure.com/courses/12345")
    print("    You need:   https://example.instructure.com")
    print()
    print("  • If you see: https://canvas.university.edu/login")
    print("    You need:   https://canvas.university.edu")
    print()
    print("=" * 70)
    print()

    while True:
        canvas_url = input("Enter your Canvas URL: ").strip()

        if not canvas_url:
            print("❌ Canvas URL is required. Please try again.")
            print()
            continue

        # Remove trailing slashes
        canvas_url = canvas_url.rstrip('/')

        # Basic validation
        if not canvas_url.startswith('http'):
            print("⚠️  URL should start with https:// or http://")
            retry = input("Did you mean: https://" + canvas_url + "? (Y/n): ").strip().lower()
            if retry in ['', 'y', 'yes']:
                canvas_url = "https://" + canvas_url
            else:
                continue

        # Confirm with user
        print()
        print(f"✅ Canvas URL: {canvas_url}")
        confirm = input("Is this correct? (Y/n): ").strip().lower()

        if confirm in ['', 'y', 'yes']:
            # Ask if they want to save it
            print()
            save = input("Save this URL permanently? (Y/n): ").strip().lower()
            if save in ['', 'y', 'yes']:
                save_canvas_url_permanently(canvas_url)
            else:
                print("✅ URL accepted (session only - will need to re-enter next time)")

            return canvas_url
        else:
            print("Let's try again...")
            print()

def save_canvas_url_permanently(canvas_url):
    """Save Canvas URL to shell config file."""
    system = platform.system()

    if system == "Windows":
        # Portable mode: write to credentials.bat if launched via run.bat
        creds_file = os.environ.get("AUTOGRADER_CREDS_FILE", "")
        if creds_file and os.path.exists(creds_file):
            try:
                with open(creds_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                updated = False
                for i, line in enumerate(lines):
                    if line.strip().startswith("set CANVAS_BASE_URL="):
                        lines[i] = f"set CANVAS_BASE_URL={canvas_url}\n"
                        updated = True
                        break
                if not updated:
                    lines.append(f"set CANVAS_BASE_URL={canvas_url}\n")
                with open(creds_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("Canvas URL saved to credentials.bat")
            except Exception as e:
                print(f"Could not save to credentials.bat: {e}")
        else:
            print()
            print("To save permanently, open credentials.bat in Notepad and set:")
            print(f"  CANVAS_BASE_URL={canvas_url}")
        return

    # Unix-like systems (macOS, Linux)
    home = Path.home()

    # Determine which shell config file to use
    shell_config = None
    if (home / ".zshrc").exists() or os.environ.get("SHELL", "").endswith("zsh"):
        shell_config = home / ".zshrc"
    elif (home / ".bashrc").exists():
        shell_config = home / ".bashrc"
    elif (home / ".bash_profile").exists():
        shell_config = home / ".bash_profile"
    else:
        # Create .zshrc as default for macOS
        shell_config = home / ".zshrc"

    try:
        # Read existing config
        if shell_config.exists():
            with open(shell_config, 'r') as f:
                content = f.read()

            # Check if URL already exists
            if "CANVAS_BASE_URL=" in content:
                # Update existing entry
                lines = content.split('\n')
                with open(shell_config, 'w') as f:
                    for line in lines:
                        if line.startswith('export CANVAS_BASE_URL='):
                            f.write(f'export CANVAS_BASE_URL="{canvas_url}"\n')
                        else:
                            f.write(line + '\n')
                print(f"✅ Updated Canvas URL in {shell_config}")
                return

        # Append new entry
        with open(shell_config, 'a') as f:
            f.write(f'\n# Canvas Autograder - Canvas URL\n')
            f.write(f'export CANVAS_BASE_URL="{canvas_url}"\n')

        print(f"✅ Canvas URL saved to {shell_config}")
        print()
        print("⚠️  IMPORTANT: The URL will be available in new terminal windows.")
        print("   For this session, I'll use it temporarily.")

        # Set for current session
        os.environ["CANVAS_BASE_URL"] = canvas_url

    except Exception as e:
        print(f"⚠️  Could not save URL automatically: {e}")
        print()
        print(f"To save manually, add this line to {shell_config}:")
        print(f'export CANVAS_BASE_URL="{canvas_url}"')

def get_canvas_token():
    """Get Canvas API token from environment or user input."""
    token = os.environ.get("CANVAS_API_TOKEN")

    if token:
        return token
    
    print()
    print("=" * 70)
    print("ðŸ”‘ CANVAS API TOKEN REQUIRED")
    print("=" * 70)
    print()
    print("To use Canvas Autograder, you need a Canvas API access token.")
    print("This token allows the program to access your Canvas courses and grades.")
    print()
    print("=" * 70)
    print("HOW TO GET YOUR CANVAS API TOKEN:")
    print("=" * 70)
    print()
    print("1. Log in to Canvas (e.g., institution.instructure.com)")
    print("2. Click your profile picture (top-left) â†’ Settings")
    print("3. Scroll down to 'Approved Integrations'")
    print("4. Click '+ New Access Token'")
    print("5. Enter a purpose (e.g., 'Autograder')")
    print("6. Click 'Generate Token'")
    print("7. COPY THE TOKEN immediately (you can't see it again!)")
    print()
    print("âš ï¸  IMPORTANT: Keep your token secret - it has access to your Canvas!")
    print()
    print("=" * 70)
    print()
    print("Options:")
    print("  [1] I have my token - enter it now (session only)")
    print("  [2] I have my token - save it permanently")
    print("  [3] Open Canvas login page in browser to get token")
    print("  [4] Exit (get token later)")
    print()
    
    while True:
        try:
            choice = input("Choose option (1/2/3/4, default=4): ").strip() or "4"
            if choice in ["1", "2", "3", "4"]:
                break
            print("âŒ Please enter 1, 2, 3, or 4")
        except (KeyboardInterrupt, EOFError):
            print("\n\nâŒ Cancelled by user")
            sys.exit(0)
    
    if choice == "3":
        # Open Canvas in browser - use already configured URL if available
        print("\n🌐 Opening Canvas in your browser...")

        canvas_url = os.environ.get("CANVAS_BASE_URL")

        if canvas_url:
            print(f"\nUsing your Canvas URL: {canvas_url}")
        else:
            print()
            print("Enter your Canvas URL to open it in the browser.")
            print()
            canvas_url = input("Canvas URL (e.g., https://institution.instructure.com): ").strip()

        if not canvas_url:
            print("⚠️  No Canvas URL available - skipping browser open")

        
        if open_url_in_browser(canvas_url):
            print(f"âœ… Opened {canvas_url} in your browser")
        else:
            print("âš ï¸  Could not open browser automatically")
            print(f"   Please manually visit: {canvas_url}")
        
        print()
        print("After getting your Canvas API token:")
        print("  1. Follow the steps listed above to generate a token")
        print("  2. Copy the token")
        print("  3. Return here and choose option 1 or 2")
        print()
        
        # Ask again after opening browser
        return get_canvas_token()
    
    elif choice == "4":
        print("\nðŸ‘‹ Please get your Canvas API token and run this program again.")
        print()
        print("Quick reference:")
        print("  Canvas â†’ Profile â†’ Settings â†’ Approved Integrations â†’ New Access Token")
        sys.exit(0)
    
    # Options 1 or 2 - get the token
    print()
    print("Paste your Canvas API token below:")
    print("(You should be able to see the token as you type)")
    print()
    token = input("Canvas API Token: ").strip()
    
    if not token:
        print("âŒ No token entered.")
        sys.exit(0)
    
    if choice == "2":
        save_token_permanently(token)
    else:
        print("âœ… Token accepted (session only - will need to re-enter next time)")
    
    return token

def save_token_permanently(token):
    """Save token to shell config file."""
    system = platform.system()
    
    if system == "Windows":
        # Portable mode: write to credentials.bat if launched via run.bat
        creds_file = os.environ.get("AUTOGRADER_CREDS_FILE", "")
        if creds_file and os.path.exists(creds_file):
            try:
                with open(creds_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                updated = False
                for i, line in enumerate(lines):
                    if line.strip().startswith("set CANVAS_API_TOKEN="):
                        lines[i] = f"set CANVAS_API_TOKEN={token}\n"
                        updated = True
                        break
                if not updated:
                    lines.append(f"set CANVAS_API_TOKEN={token}\n")
                with open(creds_file, 'w', encoding='utf-8') as f:
                    f.writelines(lines)
                print("API token saved to credentials.bat")
            except Exception as e:
                print(f"Could not save to credentials.bat: {e}")
        else:
            print()
            print("To save permanently, open credentials.bat in Notepad and set:")
            print(f"  CANVAS_API_TOKEN={token}")
        return
    
    # Unix-like systems
    shell = os.environ.get("SHELL", "")
    
    if "zsh" in shell:
        rc_file = Path.home() / ".zshrc"
    elif "bash" in shell:
        rc_file = Path.home() / ".bashrc"
    else:
        rc_file = Path.home() / ".profile"
    
    try:
        # Check if token already exists in file
        if rc_file.exists():
            with open(rc_file, 'r') as f:
                content = f.read()
                if "CANVAS_API_TOKEN=" in content:
                    print(f"âš ï¸  Token variable already exists in {rc_file}")
                    return
        
        # Append token to file
        with open(rc_file, 'a') as f:
            f.write("\n")
            f.write("# Canvas API token for autograder\n")
            f.write(f'export CANVAS_API_TOKEN="{token}"\n')
        
        print(f"âœ… Saved token to {rc_file}")
        print("   (Restart your terminal for it to take effect)")
    except Exception as e:
        print(f"âš ï¸  Could not save token: {e}")

def show_help_menu():
    """Display help menu with definitions and instructions."""
    while True:
        print()
        print("=" * 70)
        print("ℹ️  CANVAS AUTOGRADER HELP")
        print("=" * 70)
        print()
        print("Help Topics:")
        print("  [1] What is an API token?")
        print("  [2] How to get/change my Canvas API token")
        print("  [3] What are 'Grading Rationales'?")
        print("  [4] What does 'autograding' mean?")
        print("  [5] Understanding file cleanup options")
        print("  [6] Troubleshooting common issues")
        print()
        print("  [B] Back to main menu")
        print()
        
        try:
            choice = input("Select a topic (1-6 or B): ").strip().upper()
            
            if choice == 'B':
                return
            elif choice == '1':
                print()
                print("=" * 70)
                print("WHAT IS AN API TOKEN?")
                print("=" * 70)
                print()
                print("An API token is like a special password that allows this program")
                print("to access your Canvas account safely.")
                print()
                print("Think of it like a key that only works for specific tasks:")
                print("  ✓ The program can read your course information")
                print("  ✓ The program can view student submissions")
                print("  ✓ The program can enter grades")
                print("  ✗ But it can't change your personal settings or password")
                print()
                print("Why use a token instead of your Canvas password?")
                print("  ✓ More secure - if someone gets the token, they can't")
                print("    access everything in your Canvas account")
                print("  ✓ You can delete/disable the token anytime without changing")
                print("    your password")
                print("  ✓ The program never sees or stores your actual Canvas password")
                print()
                print("⚠️  IMPORTANT: Keep your API token private! Don't share it with")
                print("   others, just like you wouldn't share your password.")
                print()
                input("Press Enter to continue...")
                
            elif choice == '2':
                print()
                print("=" * 70)
                print("HOW TO GET/CHANGE YOUR CANVAS API TOKEN")
                print("=" * 70)
                print()
                print("GETTING YOUR TOKEN FOR THE FIRST TIME:")
                print()
                print("1. Log in to your Canvas site (e.g., institution.instructure.com)")
                print("2. Click on your profile picture or name in the top-left corner")
                print("3. Select 'Settings' from the dropdown menu")
                print("4. Scroll down to the section called 'Approved Integrations'")
                print("5. Click the '+ New Access Token' button")
                print("6. In the popup window:")
                print("   - Enter a name like 'Autograder' in the 'Purpose' field")
                print("   - Leave the expiration date blank (or set it far in the future)")
                print("   - Click 'Generate Token'")
                print("7. IMPORTANT: Copy the token immediately!")
                print("   - Canvas shows it only once")
                print("   - If you close the window, you'll need to create a new token")
                print()
                print("CHANGING YOUR TOKEN:")
                print()
                print("If you need to change your token (e.g., it expired or was lost):")
                print("1. From the main menu, select [T] 'Change Canvas API token'")
                print("2. Follow the prompts to enter your new token")
                print("3. Choose whether to save it permanently or just for this session")
                print()
                print("You can also delete old tokens from Canvas:")
                print("1. Go to Canvas → Settings → Approved Integrations")
                print("2. Find the old token in the list")
                print("3. Click the 'X' or 'Delete' button next to it")
                print()
                input("Press Enter to continue...")
                
            elif choice == '3':
                print()
                print("=" * 70)
                print("WHAT ARE 'GRADING RATIONALES'?")
                print("=" * 70)
                print()
                print("'Grading Rationales' is the folder where this program saves all")
                print("the reports and spreadsheets it creates.")
                print()
                print("When you run an autograding tool, it creates files like:")
                print("  📄 Spreadsheets (.xlsx files) with student scores")
                print("  📄 Reports (.csv files) for uploading to Canvas")
                print("  📄 Academic dishonesty reports (if you run that check)")
                print()
                print("By default, these files are saved in:")
                print("  📁 Documents/Autograder Rationales/")
                print()
                print("Inside this folder, files are organized by type:")
                print("  📂 Academic Dishonesty Reports/")
                print("  📂 Discussion Forums/")
                print("  📂 Complete-Incomplete Assignments/")
                print()
                print("You can change where files are saved:")
                print("  - Select [S] from the main menu")
                print("  - Choose a new location (like your Desktop)")
                print()
                input("Press Enter to continue...")
                
            elif choice == '4':
                print()
                print("=" * 70)
                print("WHAT DOES 'AUTOGRADING' MEAN?")
                print("=" * 70)
                print()
                print("'Autograding' means the computer automatically checks student work")
                print("and assigns grades based on rules you've set up.")
                print()
                print("This program includes three autograding tools:")
                print()
                print("1. DISCUSSION FORUM AUTOGRADER")
                print("   - Checks if students posted in discussion forums")
                print("   - Verifies they met requirements (word count, replies, etc.)")
                print("   - Gives credit for complete participation")
                print()
                print("2. COMPLETE/INCOMPLETE AUTOGRADER")
                print("   - For assignments graded as Complete or Incomplete")
                print("   - Checks if student submitted something")
                print("   - Awards full credit if they turned it in")
                print()
                print("3. ACADEMIC DISHONESTY CHECK")
                print("   - Scans student work for potential AI usage or copying")
                print("   - Creates a report for YOU to review")
                print("   - Does NOT automatically fail students")
                print("   - You make the final decision on each case")
                print()
                print("⚠️  Important: These tools help speed up grading, but you should")
                print("   always review the results before finalizing grades!")
                print()
                input("Press Enter to continue...")
                
            elif choice == '5':
                print()
                print("=" * 70)
                print("UNDERSTANDING FILE CLEANUP OPTIONS")
                print("=" * 70)
                print()
                print("Over time, this program creates many files. The cleanup feature")
                print("helps you manage old files automatically.")
                print()
                print("THREE CLEANUP OPTIONS:")
                print()
                print("1. NONE (default)")
                print("   - All files are kept forever")
                print("   - You manually delete files when needed")
                print("   - Best if you want complete control")
                print()
                print("2. ARCHIVE")
                print("   - Old files are moved to an 'Archived' subfolder")
                print("   - Files are still accessible if you need them")
                print("   - Keeps your main folders tidy")
                print("   - Recommended for most users")
                print()
                print("3. TRASH/RECYCLE BIN")
                print("   - Old files are moved to your computer's Trash/Recycle Bin")
                print("   - You can restore them if needed")
                print("   - Files are permanently deleted when you empty the trash")
                print()
                print("You can set:")
                print("  ➡️  How old files must be before cleanup (default: 180 days)")
                print("  ➡️  Which file types to clean up (CSV, Excel, or both)")
                print()
                print("To configure: Select [C] from the main menu")
                print("To run cleanup once: Select [R] from the main menu")
                print()
                input("Press Enter to continue...")
                
            elif choice == '6':
                print()
                print("=" * 70)
                print("TROUBLESHOOTING COMMON ISSUES")
                print("=" * 70)
                print()
                print("PROBLEM: 'Invalid API token' or 'Authentication failed'")
                print("SOLUTION:")
                print("  1. Your token may have expired - create a new one in Canvas")
                print("  2. Select [T] from the main menu to update your token")
                print("  3. Make sure you copied the entire token (no spaces)")
                print()
                print("PROBLEM: Can't find the output files")
                print("SOLUTION:")
                print("  1. Check the 'Grading Rationales' folder in your Documents")
                print("  2. Select [O] from the main menu to open the folder")
                print("  3. Look inside the subfolders (Academic Dishonesty, etc.)")
                print()
                print("PROBLEM: Program crashes or shows errors")
                print("SOLUTION:")
                print("  1. Make sure you're connected to the internet")
                print("  2. Check that your Canvas site is accessible")
                print("  3. Try running the program again")
                print("  4. If it keeps failing, contact your IT support")
                print()
                print("PROBLEM: Grades aren't uploading to Canvas")
                print("SOLUTION:")
                print("  1. The autograder creates files - YOU upload them to Canvas")
                print("  2. Open the Excel/CSV file it created")
                print("  3. In Canvas, use the grade import feature")
                print("  4. Upload the file the autograder created")
                print()
                print("PROBLEM: Want to change where files are saved")
                print("SOLUTION:")
                print("  1. Select [S] from the main menu")
                print("  2. Enter the full path to your preferred folder")
                print("  3. Or press Enter to browse and select a folder")
                print()
                input("Press Enter to continue...")
                
            else:
                print("❌ Please enter a number from 1-6 or B")
                
        except (KeyboardInterrupt, EOFError):
            print("\n")
            return


def change_canvas_token():
    """Allow user to change their Canvas API token."""
    print()
    print("=" * 70)
    print("🔑 CHANGE CANVAS API TOKEN")
    print("=" * 70)
    print()
    print("This will update your Canvas API token.")
    print()
    print("Options:")
    print("  [1] I need help getting a new token from Canvas")
    print("  [2] I have a new token ready - enter it now")
    print("  [3] Remove saved token (you'll be asked each session)")
    print("  [4] Cancel - go back to main menu")
    print()
    
    try:
        choice = input("Choose option (1/2/3/4, default=4): ").strip() or "4"
        
        if choice == "1":
            # Show instructions for getting a token
            print()
            print("=" * 70)
            print("HOW TO GET YOUR CANVAS API TOKEN")
            print("=" * 70)
            print()
            print("Follow these steps to get a new token from Canvas:")
            print()
            print("1. Open Canvas in your web browser")
            print("   (e.g., institution.instructure.com)")
            print()
            print("2. Click on your profile picture or name in the top-left corner")
            print()
            print("3. Select 'Settings' from the dropdown menu")
            print()
            print("4. Scroll down to the section called 'Approved Integrations'")
            print()
            print("5. Click the '+ New Access Token' button")
            print()
            print("6. In the popup window:")
            print("   - Purpose: Enter 'Autograder' (or any name you prefer)")
            print("   - Expiration: Leave blank or set a far future date")
            print("   - Click 'Generate Token'")
            print()
            print("7. ⚠️  IMPORTANT: Copy the token IMMEDIATELY!")
            print("   - Canvas only shows it once")
            print("   - If you close the window, you'll need to create a new one")
            print()
            print("=" * 70)
            print()
            print("What would you like to do?")
            print("  [1] Open Canvas in browser to get my token")
            print("  [2] I have my token - enter it now")
            print("  [3] Cancel - go back to main menu")
            print()
            
            sub_choice = input("Choose option (1/2/3, default=3): ").strip() or "3"
            
            if sub_choice == "1":
                # Open Canvas in browser
                canvas_url = os.environ.get("CANVAS_BASE_URL")

                if not canvas_url:
                    print()
                    print("Enter your Canvas instance URL")
                    print()
                    canvas_url = input("Canvas URL (e.g., https://institution.instructure.com): ").strip()

                if not canvas_url:
                    print("❌ No Canvas URL available")
                    print("❌ Cancelled - no changes made to your token")
                    return
                
                print()
                print(f"🌐 Opening {canvas_url} in your browser...")
                if open_url_in_browser(canvas_url):
                    print("✅ Browser opened")
                else:
                    print("⚠️  Could not open browser automatically")
                    print(f"   Please manually visit: {canvas_url}")
                
                print()
                print("After you get your token from Canvas, come back here.")
                print()
                print("What would you like to do?")
                print("  [1] I have my token - enter it now")
                print("  [2] Cancel - I'll do this later")
                print()
                
                token_choice = input("Choose option (1/2, default=2): ").strip() or "2"
                
                if token_choice == "1":
                    # Fall through to token entry
                    pass
                else:
                    print("❌ Cancelled - no changes made to your token")
                    return
            elif sub_choice == "2":
                # Fall through to token entry
                pass
            else:
                print("❌ Cancelled - no changes made to your token")
                return
            
            # Token entry section (reached from sub_choice 1 or 2)
            print()
            print("Enter your new Canvas API token below:")
            print("(You can paste it - you should see the text as you type)")
            print()
            print("Or type 'cancel' to abort without making changes")
            print()
            new_token = input("Canvas API Token: ").strip()
            
            if not new_token or new_token.lower() == 'cancel':
                print("❌ Cancelled - no changes made to your token")
                return
            
            print()
            print("How should this token be saved?")
            print("  [1] Session only (you'll need to re-enter it next time)")
            print("  [2] Save permanently (recommended)")
            print("  [3] Cancel - don't save this token")
            print()
            save_choice = input("Choose (1/2/3, default=2): ").strip() or "2"
            
            if save_choice == "3":
                print("❌ Cancelled - no changes made to your token")
                return
            elif save_choice == "2":
                # First remove old token if it exists
                remove_saved_token()
                # Then save new token
                save_token_permanently(new_token)
                print()
                print("✅ New token saved permanently")
                print("   You won't need to enter it again in future sessions")
            else:
                # Just set for this session
                os.environ["CANVAS_API_TOKEN"] = new_token
                print()
                print("✅ New token set for this session only")
                print("   You'll need to enter it again next time you run the program")
        
        elif choice == "2":
            # Direct token entry
            print()
            print("Enter your new Canvas API token below:")
            print("(You can paste it - you should see the text as you type)")
            print()
            print("Or type 'cancel' to abort without making changes")
            print()
            new_token = input("Canvas API Token: ").strip()
            
            if not new_token or new_token.lower() == 'cancel':
                print("❌ Cancelled - no changes made to your token")
                return
            
            print()
            print("How should this token be saved?")
            print("  [1] Session only (you'll need to re-enter it next time)")
            print("  [2] Save permanently (recommended)")
            print("  [3] Cancel - don't save this token")
            print()
            save_choice = input("Choose (1/2/3, default=2): ").strip() or "2"
            
            if save_choice == "3":
                print("❌ Cancelled - no changes made to your token")
                return
            elif save_choice == "2":
                # First remove old token if it exists
                remove_saved_token()
                # Then save new token
                save_token_permanently(new_token)
                print()
                print("✅ New token saved permanently")
                print("   You won't need to enter it again in future sessions")
            else:
                # Just set for this session
                os.environ["CANVAS_API_TOKEN"] = new_token
                print()
                print("✅ New token set for this session only")
                print("   You'll need to enter it again next time you run the program")
            
        elif choice == "3":
            print()
            confirm = input("Remove saved token? You'll need to enter it each session (y/n, default=n): ").strip().lower()
            if confirm == 'y':
                remove_saved_token()
                # Also clear from environment for this session
                if "CANVAS_API_TOKEN" in os.environ:
                    del os.environ["CANVAS_API_TOKEN"]
                print("✅ Saved token removed")
            else:
                print("❌ Cancelled - no changes made")
        else:
            print("❌ Cancelled - no changes made to your token")
            
    except (KeyboardInterrupt, EOFError):
        print("\n\n❌ Cancelled - no changes made to your token")


def change_canvas_url():
    """Allow user to change their Canvas URL."""
    print()
    print("=" * 70)
    print("🌐 CHANGE CANVAS URL")
    print("=" * 70)
    print()

    current_url = os.environ.get("CANVAS_BASE_URL")
    if current_url:
        print(f"Current Canvas URL: {current_url}")
        print()

    print("Options:")
    print("  [1] Enter a new Canvas URL")
    print("  [2] Remove saved URL (you'll be asked each session)")
    print("  [3] Cancel - go back to main menu")
    print()

    try:
        choice = input("Choose option (1/2/3, default=3): ").strip() or "3"

        if choice == "1":
            # Get new URL
            print()
            print("=" * 70)
            print("ENTER YOUR CANVAS URL")
            print("=" * 70)
            print()
            print("📍 WHERE TO FIND YOUR CANVAS URL:")
            print()
            print("1. Open your web browser and log in to Canvas")
            print("2. Look at the address bar")
            print("3. Copy everything BEFORE '/courses' or '/login'")
            print()
            print("EXAMPLES:")
            print("  If you see: https://example.instructure.com/courses/12345")
            print("  You need:   https://example.instructure.com")
            print()
            print("=" * 70)
            print()

            while True:
                new_url = input("Enter your Canvas URL: ").strip()

                if not new_url:
                    print("❌ Canvas URL cannot be empty")
                    retry = input("Try again? (Y/n): ").strip().lower()
                    if retry in ['', 'y', 'yes']:
                        continue
                    else:
                        print("❌ Cancelled - no changes made")
                        return

                # Remove trailing slashes
                new_url = new_url.rstrip('/')

                # Add https if missing
                if not new_url.startswith('http'):
                    confirm = input(f"Add https:// prefix? (Y/n): ").strip().lower()
                    if confirm in ['', 'y', 'yes']:
                        new_url = "https://" + new_url

                # Confirm
                print()
                print(f"New Canvas URL: {new_url}")
                confirm = input("Is this correct? (Y/n): ").strip().lower()

                if confirm in ['', 'y', 'yes']:
                    break
                print("Let's try again...")
                print()

            # Ask if they want to save permanently
            print()
            save = input("Save this URL permanently? (Y/n): ").strip().lower()

            if save in ['', 'y', 'yes']:
                save_canvas_url_permanently(new_url)
            else:
                # Set for current session only
                os.environ["CANVAS_BASE_URL"] = new_url
                print("✅ Canvas URL updated (session only)")

        elif choice == "2":
            # Remove saved URL
            remove_saved_canvas_url()

        elif choice == "3":
            print("❌ Cancelled - no changes made")
            return
        else:
            print("❌ Invalid choice - no changes made")
            return

    except (KeyboardInterrupt, EOFError):
        print("\n\n❌ Cancelled - no changes made")
        return

def remove_saved_canvas_url():
    """Remove saved Canvas URL from config files."""
    system = platform.system()

    if system == "Windows":
        print("⚠️  On Windows, please remove the URL manually from System Environment Variables")
        print("   1. Search for 'Environment Variables' in Windows")
        print("   2. Click 'Environment Variables' button")
        print("   3. Find and delete CANVAS_BASE_URL from User variables")
        return

    # Unix-like systems - try to remove from shell config files
    shell = os.environ.get("SHELL", "")

    if "zsh" in shell:
        rc_file = Path.home() / ".zshrc"
    elif "bash" in shell:
        rc_file = Path.home() / ".bashrc"
    else:
        rc_file = Path.home() / ".bashrc"  # Default to .bashrc

    if not rc_file.exists():
        print(f"⚠️  {rc_file} not found - nothing to remove")
        return

    try:
        with open(rc_file, 'r') as f:
            lines = f.readlines()

        # Filter out the Canvas URL line
        new_lines = []
        removed = False
        skip_next_comment = False

        for line in lines:
            if 'export CANVAS_BASE_URL=' in line:
                removed = True
                skip_next_comment = False
                continue
            if skip_next_comment and line.strip().startswith('#') and 'Canvas' in line:
                skip_next_comment = False
                continue
            if '# Canvas Autograder - Canvas URL' in line:
                skip_next_comment = True
                continue
            new_lines.append(line)

        if removed:
            with open(rc_file, 'w') as f:
                f.writelines(new_lines)
            print(f"✅ Removed Canvas URL from {rc_file}")
            print("   (Will take effect in new terminal sessions)")

            # Remove from current session too
            if "CANVAS_BASE_URL" in os.environ:
                del os.environ["CANVAS_BASE_URL"]
                print("   Removed from current session as well")
        else:
            print(f"⚠️  No saved Canvas URL found in {rc_file}")

    except Exception as e:
        print(f"❌ Error removing URL: {e}")

def remove_saved_token():
    """Remove saved Canvas API token from config files."""
    system = platform.system()
    
    if system == "Windows":
        print("âš ï¸  On Windows, please remove the token manually from System Environment Variables")
        print("   1. Search for 'Environment Variables' in Windows")
        print("   2. Click 'Environment Variables' button")
        print("   3. Find and delete CANVAS_API_TOKEN from User variables")
        return
    
    # Unix-like systems - try to remove from shell config files
    shell = os.environ.get("SHELL", "")
    
    if "zsh" in shell:
        rc_file = Path.home() / ".zshrc"
    elif "bash" in shell:
        rc_file = Path.home() / ".bashrc"
    else:
        rc_file = Path.home() / ".profile"
    
    try:
        if not rc_file.exists():
            return
        
        with open(rc_file, 'r') as f:
            lines = f.readlines()
        
        # Remove lines containing CANVAS_API_TOKEN
        new_lines = []
        skip_next = False
        for line in lines:
            if "CANVAS_API_TOKEN" in line:
                skip_next = False  # Don't skip the line itself
                continue
            elif skip_next:
                skip_next = False
                continue
            elif "Canvas API token for autograder" in line:
                skip_next = True  # Skip the export line after the comment
                continue
            else:
                new_lines.append(line)
        
        # Write back
        with open(rc_file, 'w') as f:
            f.writelines(new_lines)
        
        print(f"âœ… Removed token from {rc_file}")
        print("   (Restart your terminal for it to take effect)")
        
    except Exception as e:
        print(f"âš ï¸  Could not remove token: {e}")

def cleanup_old_files(target_dir, script_type):
    """Automatically clean up old files based on settings."""
    settings = load_settings()
    cleanup_mode = settings.get("cleanup_mode", "none")
    
    if cleanup_mode == "none":
        return  # No cleanup configured
    
    cleanup_days = settings.get("cleanup_threshold_days", 180)
    cleanup_targets = settings.get("cleanup_targets", "all")
    
    # Determine which file types to clean for this script type
    targets_to_clean = []
    
    if cleanup_targets == "all":
        # Clean all file types for this script
        if script_type == "Academic_Dishonesty":
            targets_to_clean = [("Academic_Dishonesty", "csv"), ("Academic_Dishonesty", "excel"), ("Academic_Dishonesty", "txt")]
        elif script_type == "Complete-Incomplete":
            targets_to_clean = [("Complete-Incomplete", "csv")]
        elif script_type == "Discussion_Forum":
            targets_to_clean = [("Discussion_Forum", "csv")]
    else:
        # Parse specific targets
        target_list = cleanup_targets.split(",")
        for target in target_list:
            target = target.strip()
            if script_type == "Academic_Dishonesty":
                if target == "ad_csv":
                    targets_to_clean.append(("Academic_Dishonesty", "csv"))
                elif target == "ad_excel":
                    targets_to_clean.append(("Academic_Dishonesty", "excel"))
                elif target == "ad_txt":
                    targets_to_clean.append(("Academic_Dishonesty", "txt"))
            elif script_type == "Complete-Incomplete" and target == "ci_csv":
                targets_to_clean.append(("Complete-Incomplete", "csv"))
            elif script_type == "Discussion_Forum" and target == "df_csv":
                targets_to_clean.append(("Discussion_Forum", "csv"))
    
    if not targets_to_clean:
        return  # No targets configured for this script type
    
    print()
    print(f"ðŸ—‘ï¸  Checking for files older than {cleanup_days} days...")
    
    for st, file_type in targets_to_clean:
        if cleanup_mode == "archive":
            archive_files_by_type(target_dir, st, file_type, cleanup_days)
        elif cleanup_mode == "trash":
            trash_files_by_type(target_dir, st, file_type, cleanup_days)

def archive_files(target_dir, script_type, threshold_days=180):
    """Archive old files to archived subfolder."""
    # Determine archive directory
    if HAS_UTILS:
        archive_dir = get_archive_dir(script_type)
    else:
        archive_map = {
            "Academic_Dishonesty": "Academic Dishonesty",
            "Discussion_Forum": "Discussions",
            "Complete-Incomplete": "Assignments"
        }
        archive_subdir = archive_map.get(script_type, "Other")
        archive_base = get_base_exports_dir() / "Archived Reports"
        archive_dir = archive_base / archive_subdir
    
    # Create archive directory
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    # Calculate cutoff date using threshold_days
    cutoff_date = datetime.now() - timedelta(days=threshold_days)
    
    moved_count = 0
    
    # For Academic Dishonesty, handle csv and excel subdirs
    if script_type == "Academic_Dishonesty":
        csv_dir = target_dir / "csv"
        excel_dir = target_dir / "excel"
        
        archive_csv = archive_dir / "csv"
        archive_excel = archive_dir / "excel"
        archive_csv.mkdir(parents=True, exist_ok=True)
        archive_excel.mkdir(parents=True, exist_ok=True)
        
        # Move old CSV files
        if csv_dir.exists():
            for file in csv_dir.glob("*.csv"):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    shutil.move(str(file), str(archive_csv / file.name))
                    moved_count += 1
        
        # Move old Excel files
        if excel_dir.exists():
            for file in excel_dir.glob("*.xlsx"):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    shutil.move(str(file), str(archive_excel / file.name))
                    moved_count += 1
    else:
        # For other types, just move CSV files
        for file in target_dir.glob("*.csv"):
            if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                shutil.move(str(file), str(archive_dir / file.name))
                moved_count += 1
    
    if moved_count > 0:
        print(f"âœ… Moved {moved_count} old files to {archive_dir}")
        print("âš ï¸  Archived files can only be deleted manually â€” this program will not touch them.")
    else:
        print("âœ… No old files found to archive")

def trash_files(target_dir, script_type, threshold_days=180):
    """Move old files to Trash/Recycle Bin - cross-platform."""
    system = platform.system()
    cutoff_date = datetime.now() - timedelta(days=threshold_days)
    moved_count = 0
    
    def move_single_file_to_trash(file_path: Path) -> bool:
        """Move a single file to trash - cross-platform."""
        if HAS_UTILS:
            return move_to_trash(file_path)
        
        # Fallback implementations
        try:
            if system == "Darwin":
                os.system(f'osascript -e \'tell app "Finder" to delete POSIX file "{file_path}"\'')
                return True
            elif system == "Windows":
                # Try PowerShell method
                ps_command = f'''
                Add-Type -AssemblyName Microsoft.VisualBasic
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                    '{file_path}',
                    'OnlyErrorDialogs',
                    'SendToRecycleBin'
                )
                '''
                result = subprocess.run(
                    ['powershell', '-Command', ps_command],
                    capture_output=True, text=True
                )
                return result.returncode == 0
            else:
                # Linux: Try gio trash first, then fallback
                result = subprocess.run(
                    ['gio', 'trash', str(file_path)],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return True
                # Fallback: move to ~/.local/share/Trash/files
                trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
                trash_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(trash_dir / file_path.name))
                return True
        except Exception as e:
            print(f"   âš ï¸  Could not trash {file_path.name}: {e}")
            return False
    
    # For Academic Dishonesty, handle csv and excel subdirs
    if script_type == "Academic_Dishonesty":
        csv_dir = target_dir / "csv"
        excel_dir = target_dir / "excel"
        
        # Move old CSV files
        if csv_dir.exists():
            for file in csv_dir.glob("*.csv"):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    if move_single_file_to_trash(file):
                        moved_count += 1
        
        # Move old Excel files
        if excel_dir.exists():
            for file in excel_dir.glob("*.xlsx"):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    if move_single_file_to_trash(file):
                        moved_count += 1
    else:
        # For other types, move CSV and Excel files
        for pattern in ["*.csv", "*.xlsx"]:
            for file in target_dir.glob(pattern):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    if move_single_file_to_trash(file):
                        moved_count += 1
    
    if moved_count > 0:
        trash_name = "Trash" if system != "Windows" else "Recycle Bin"
        print(f"âœ… Moved {moved_count} old files to {trash_name}")
    else:
        print("âœ… No old files found to trash")

def archive_files_by_type(target_dir, script_type, file_type, threshold_days=180):
    """Archive old files of a specific type to archived subfolder."""
    # Determine archive directory
    if HAS_UTILS:
        archive_dir = get_archive_dir(script_type)
    else:
        archive_map = {
            "Academic_Dishonesty": "Academic Dishonesty",
            "Discussion_Forum": "Discussions",
            "Complete-Incomplete": "Assignments"
        }
        archive_subdir = archive_map.get(script_type, "Other")
        archive_base = get_base_exports_dir() / "Archived Reports"
        archive_dir = archive_base / archive_subdir
    
    # Calculate cutoff date
    cutoff_date = datetime.now() - timedelta(days=threshold_days)
    moved_count = 0
    
    # For Academic Dishonesty, files are in subdirectories (except txt)
    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            source_dir = target_dir / "csv"
            dest_dir = archive_dir / "csv"
            pattern = "*.csv"
        elif file_type == "excel":
            source_dir = target_dir / "excel"
            dest_dir = archive_dir / "excel"
            pattern = "*.xlsx"
        else:  # txt - stored directly in target_dir
            source_dir = target_dir
            dest_dir = archive_dir
            pattern = "*_report.txt"

        if source_dir.exists():
            dest_dir.mkdir(parents=True, exist_ok=True)
            for file in source_dir.glob(pattern):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    shutil.move(str(file), str(dest_dir / file.name))
                    moved_count += 1
    else:
        # For other types, files are directly in the target directory
        archive_dir.mkdir(parents=True, exist_ok=True)
        pattern = "*.csv" if file_type == "csv" else "*.xlsx"
        for file in target_dir.glob(pattern):
            if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                shutil.move(str(file), str(archive_dir / file.name))
                moved_count += 1
    
    if moved_count > 0:
        print(f"   âœ… Archived {moved_count} {file_type.upper()} files")
    else:
        print(f"   âœ… No old {file_type.upper()} files found to archive")

def trash_files_by_type(target_dir, script_type, file_type, threshold_days=180):
    """Move old files of a specific type to Trash/Recycle Bin."""
    system = platform.system()
    cutoff_date = datetime.now() - timedelta(days=threshold_days)
    moved_count = 0
    
    def move_single_file_to_trash(file_path: Path) -> bool:
        """Move a single file to trash - cross-platform."""
        if HAS_UTILS:
            return move_to_trash(file_path)
        
        try:
            if system == "Darwin":
                os.system(f'osascript -e \'tell app "Finder" to delete POSIX file "{file_path}"\'')
                return True
            elif system == "Windows":
                ps_command = f'''
                Add-Type -AssemblyName Microsoft.VisualBasic
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(
                    '{file_path}',
                    'OnlyErrorDialogs',
                    'SendToRecycleBin'
                )
                '''
                result = subprocess.run(
                    ['powershell', '-Command', ps_command],
                    capture_output=True, text=True
                )
                return result.returncode == 0
            else:
                result = subprocess.run(
                    ['gio', 'trash', str(file_path)],
                    capture_output=True, text=True
                )
                if result.returncode == 0:
                    return True
                trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
                trash_dir.mkdir(parents=True, exist_ok=True)
                shutil.move(str(file_path), str(trash_dir / file_path.name))
                return True
        except Exception as e:
            print(f"   âš ï¸  Could not trash {file_path.name}: {e}")
            return False
    
    # For Academic Dishonesty, files are in subdirectories (except txt)
    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            source_dir = target_dir / "csv"
            pattern = "*.csv"
        elif file_type == "excel":
            source_dir = target_dir / "excel"
            pattern = "*.xlsx"
        else:  # txt - stored directly in target_dir
            source_dir = target_dir
            pattern = "*_report.txt"

        if source_dir.exists():
            for file in source_dir.glob(pattern):
                if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                    if move_single_file_to_trash(file):
                        moved_count += 1
    else:
        # For other types, files are directly in the target directory
        pattern = "*.csv" if file_type == "csv" else "*.xlsx"
        for file in target_dir.glob(pattern):
            if datetime.fromtimestamp(file.stat().st_mtime) < cutoff_date:
                if move_single_file_to_trash(file):
                    moved_count += 1
    
    if moved_count > 0:
        trash_name = "Trash" if system != "Windows" else "Recycle Bin"
        print(f"   âœ… Moved {moved_count} {file_type.upper()} files to {trash_name}")
    else:
        print(f"   âœ… No old {file_type.upper()} files found to trash")

def run_script(script_info, token):
    """Run the selected Python script."""
    script_path = script_info["path"]
    script_name = script_path.name
    
    # Set up environment
    env = os.environ.copy()
    env["CANVAS_API_TOKEN"] = token
    
    # Determine target directory using the friendly name
    base_dir = get_base_exports_dir()
    target_dir = base_dir / script_info["subdir"]
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Cleanup old files - use subdir_key for script type identification
    script_type = script_info.get("subdir_key", "Unknown")
    cleanup_old_files(target_dir, script_type)
    
    print()
    print(f"ðŸ“¤ Running {script_name}...")
    print(f"ðŸ“ Output will be saved to: {target_dir}")
    print()
    
    # Get Python executable from venv
    python_exe = get_venv_python()
    
    # Change to src directory and run
    try:
        result = subprocess.run(
            [str(python_exe), str(script_path)],
            cwd=str(SCRIPT_DIR),
            env=env,
            check=False  # Don't raise exception on non-zero exit
        )
        
        print()
        if result.returncode == 0:
            print("âœ… Script completed successfully!")
        else:
            print(f"âš ï¸  Script exited with code {result.returncode}")
        
        # Check auto-open setting
        settings = load_settings()
        auto_open = settings.get("auto_open_folder", True)
        
        # Show output location and optionally open folder
        if HAS_UTILS:
            print_output_location(target_dir, auto_open=auto_open)
        else:
            print(f"ðŸ“ Results saved to: {target_dir}")
            if auto_open:
                print("   Opening folder...")
                system = platform.system()
                try:
                    if system == "Darwin":
                        subprocess.run(['open', str(target_dir)])
                    elif system == "Windows":
                        subprocess.run(['explorer', str(target_dir)])
                    else:
                        subprocess.run(['xdg-open', str(target_dir)])
                except Exception:
                    pass
        
    except KeyboardInterrupt:
        print("\n\nâŒ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\nâŒ Error running script: {e}")
        sys.exit(1)

def main():
    """Main entry point."""
    print_header()
    
    # System checks
    check_python_version()
    check_pip()
    verify_structure()
    
    print()
    
    # Setup virtual environment and dependencies
    create_virtual_environment()
    install_dependencies()
    
    print()
    print("âœ… Setup complete")
    
    # First-time setup if needed
    if HAS_UTILS and is_first_run():
        run_first_time_setup()
    
    # Find available scripts
    scripts = find_scripts()
    
    # Menu loop - allows returning to menu after settings changes
    while True:
        # Let user select script (or settings option)
        selected_script = select_script(scripts)
        
        # If None returned, user accessed settings - show menu again
        if selected_script is None:
            continue

        # Get Canvas URL (required first)
        canvas_url = get_canvas_url()

        # Set it in environment so scripts can use it
        os.environ["CANVAS_BASE_URL"] = canvas_url

        # Get Canvas API token
        token = get_canvas_token()

        # Create base exports directory
        base_dir = get_base_exports_dir()
        base_dir.mkdir(parents=True, exist_ok=True)

        # Run the script
        run_script(selected_script, token)
        
        # After running, ask if they want to run another
        print()
        try:
            again = input("Run another tool? (y/n, default=n): ").strip().lower()
            if again != 'y':
                print("\nðŸ‘‹ Goodbye!")
                break
        except (KeyboardInterrupt, EOFError):
            print("\n\nðŸ‘‹ Goodbye!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nðŸ‘‹ Goodbye!")
        sys.exit(0)