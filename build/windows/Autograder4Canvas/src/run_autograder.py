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
    # Fallback subdirectory names
    SUBDIRS = {
        "Academic_Dishonesty": "Academic Dishonesty Reports",
        "Discussion_Forum": "Discussion Grades",
        "Complete-Incomplete": "Assignment Grades",
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
    print("🎓 Canvas Autograder")
    print("=" * 70)
    print()

def check_python_version():
    """Verify Python version is 3.7+."""
    version = sys.version_info
    if version < (3, 7):
        print("❌ Python 3.7 or higher is required.")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        print()
        print("Please install Python 3.7+ from https://www.python.org/downloads/")
        sys.exit(1)
    
    print(f"✅ Python {version.major}.{version.minor}.{version.micro}")

def check_pip():
    """Verify pip is available."""
    try:
        import pip
        print("✅ pip available")
        return True
    except ImportError:
        print("❌ pip is not installed.")
        print("   Install pip: https://pip.pypa.io/en/stable/installation/")
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
        "cleanup_targets": "all"  # "all" or comma-separated: "ad_csv,ad_excel,ci_csv,df_csv"
    }
    
    if not SETTINGS_FILE.exists():
        return defaults
    
    try:
        settings = {}
        with open(SETTINGS_FILE, 'r') as f:
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
        with open(SETTINGS_FILE, 'w') as f:
            f.write("# Canvas Autograder Settings\n")
            for key, value in settings.items():
                f.write(f"{key}={value}\n")
        return True
    except Exception as e:
        print(f"⚠️  Could not save settings: {e}")
        return False

def toggle_auto_open():
    """Toggle the auto-open folder setting."""
    settings = load_settings()
    current = settings.get("auto_open_folder", True)
    settings["auto_open_folder"] = not current
    
    if save_settings(settings):
        new_state = "ON" if settings["auto_open_folder"] else "OFF"
        print(f"✅ Auto-open Grading Rationales folder is now {new_state}")
    
    return settings["auto_open_folder"]

def configure_cleanup():
    """Configure automatic cleanup settings."""
    settings = load_settings()
    system = platform.system()
    
    current_mode = settings.get("cleanup_mode", "none")
    current_days = settings.get("cleanup_threshold_days", 180)
    current_targets = settings.get("cleanup_targets", "all")
    
    print()
    print("🗑️  Automatic Cleanup Settings")
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
            print("❌ Invalid choice. Keeping current mode.")
        
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
                        print("❌ Days must be at least 1. Keeping current threshold.")
                    else:
                        settings["cleanup_threshold_days"] = days
                except ValueError:
                    print("❌ Invalid number. Keeping current threshold.")
            
            # Ask which files to clean up
            print()
            print("Which output files should be automatically cleaned up?")
            print()
            print("  Academic Dishonesty Check:")
            print("    [1] CSV files only")
            print("    [2] Excel files only")
            print("    [3] Both CSV and Excel files")
            print()
            print("  Complete/Incomplete Autograder:")
            print("    [4] CSV files")
            print()
            print("  Discussion Forum Autograder:")
            print("    [5] CSV files")
            print()
            print("  Other options:")
            print("    [A] All files from all tools (default)")
            print()
            print("  (You can select multiple, e.g., '1 4 5' or '2,4')")
            
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
                            valid_targets.append("ad_csv")
                            valid_targets.append("ad_excel")
                        elif sel == '4':
                            valid_targets.append("ci_csv")
                        elif sel == '5':
                            valid_targets.append("df_csv")
                    
                    if valid_targets:
                        # Remove duplicates
                        valid_targets = list(dict.fromkeys(valid_targets))
                        settings["cleanup_targets"] = ",".join(valid_targets)
                    else:
                        print("❌ No valid selections. Keeping current targets.")
        
        if save_settings(settings):
            new_mode = mode_display.get(settings.get("cleanup_mode", "none"), "None")
            new_days = settings.get("cleanup_threshold_days", 180)
            new_targets = settings.get("cleanup_targets", "all")
            print()
            if settings.get("cleanup_mode", "none") == "none":
                print(f"✅ Cleanup mode set to: {new_mode}")
            else:
                print(f"✅ Cleanup mode set to: {new_mode}")
                print(f"   Threshold: {new_days} days")
                print(f"   Targets: {new_targets}")
    
    except (KeyboardInterrupt, EOFError):
        print("\n⏭️  Cancelled. Settings unchanged.")

def run_onetime_cleanup():
    """Run a one-time cleanup with user-specified options."""
    system = platform.system()
    base_dir = get_base_exports_dir()
    
    print()
    print("🗑️  One-Time Cleanup")
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
            print("⏭️  Cleanup cancelled.")
            return
        
        if mode_choice not in ('A', 'T'):
            print("❌ Invalid choice. Cleanup cancelled.")
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
                    print("❌ Days must be at least 1. Using default of 180.")
                    threshold_days = 180
            except ValueError:
                print("❌ Invalid number. Using default of 180.")
                threshold_days = 180
        
        # Ask which tools/file types to clean
        print()
        print("Which output files do you want to clean up?")
        print()
        print("  Academic Dishonesty Check:")
        print("    [1] CSV files only")
        print("    [2] Excel files only")
        print("    [3] Both CSV and Excel files")
        print()
        print("  Complete/Incomplete Autograder:")
        print("    [4] CSV files")
        print()
        print("  Discussion Forum Autograder:")
        print("    [5] CSV files")
        print()
        print("  Other options:")
        print("    [A] All files from all tools")
        print("    [C] Cancel")
        print()
        print("  (You can select multiple, e.g., '1 4 5' or '2,4')")
        
        selection = input("Enter selection: ").strip().upper()
        
        if selection == 'C' or selection == '':
            print("⏭️  Cleanup cancelled.")
            return
        
        # Parse selection
        cleanup_targets = []
        
        if selection == 'A':
            # All files
            cleanup_targets = [
                ("Academic_Dishonesty", "csv"),
                ("Academic_Dishonesty", "excel"),
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
                    cleanup_targets.append(("Academic_Dishonesty", "csv"))
                    cleanup_targets.append(("Academic_Dishonesty", "excel"))
                elif sel == '4':
                    cleanup_targets.append(("Complete-Incomplete", "csv"))
                elif sel == '5':
                    cleanup_targets.append(("Discussion_Forum", "csv"))
        
        if not cleanup_targets:
            print("❌ No valid selections. Cleanup cancelled.")
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
            print(f"  • {folder_name}: {file_type.upper()} files")
        
        print()
        confirm = input("Proceed? (y/N): ").strip().lower()
        
        if confirm != 'y':
            print("⏭️  Cleanup cancelled.")
            return
        
        # Perform cleanup
        for script_type, file_type in cleanup_targets:
            info = script_type_info.get(script_type, {})
            target_dir = base_dir / info.get("subdir", script_type)
            
            if not target_dir.exists():
                print(f"\nℹ️  Folder not found: {info.get('subdir', script_type)} (skipping)")
                continue
            
            print()
            print(f"Processing: {info.get('subdir', script_type)} ({file_type.upper()} files)")
            
            if mode_choice == 'A':
                archive_files_by_type(target_dir, script_type, file_type, threshold_days)
            else:
                trash_files_by_type(target_dir, script_type, file_type, threshold_days)
        
        print()
        print("✅ One-time cleanup complete!")
    
    except (KeyboardInterrupt, EOFError):
        print("\n⏭️  Cleanup cancelled.")

def create_virtual_environment():
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists():
        print("✅ Virtual environment exists")
        return
    
    print("📦 Creating virtual environment...")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(VENV_DIR)],
            check=True,
            capture_output=True
        )
        print("✅ Virtual environment created")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to create virtual environment: {e}")
        sys.exit(1)

def install_dependencies():
    """Install required dependencies."""
    if not REQUIREMENTS_FILE.exists():
        print(f"❌ requirements.txt not found at: {REQUIREMENTS_FILE}")
        sys.exit(1)
    
    print("📦 Installing dependencies...")
    
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
        
        print("✅ Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        print(f"   Error output: {e.stderr.decode() if e.stderr else 'N/A'}")
        sys.exit(1)

def verify_structure():
    """Verify project structure is correct."""
    if not PROGRAMS_DIR.exists():
        print(f"❌ Missing 'Programs/' directory at: {PROGRAMS_DIR}")
        print()
        print("Expected: Programs/ folder in same directory as run_autograder.py")
        sys.exit(1)
    
    if not REQUIREMENTS_FILE.exists():
        print(f"❌ Missing 'requirements.txt' at: {REQUIREMENTS_FILE}")
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
            "subdir": SUBDIRS.get("Discussion_Forum", "Discussion Grades"),
            "subdir_key": "Discussion_Forum"
        },
        "Complete-Incomplete": {
            "display": "Complete/Incomplete Autograder",
            "pattern": "*Complete*Incomplete*.py",
            "subdir": SUBDIRS.get("Complete-Incomplete", "Assignment Grades"),
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
                "subdir": info["subdir"]
            }
    
    if not found_scripts:
        print("❌ No autograder scripts found in:", PROGRAMS_DIR)
        print()
        print("Looking for:")
        for info in script_types.values():
            print(f"   • {info['pattern']}")
        sys.exit(1)
    
    return found_scripts

def select_script(scripts):
    """Prompt user to select which script to run or access settings."""
    base_dir = get_base_exports_dir()
    
    print()
    print("🎓 Canvas Autograder - Main Menu")
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
    
    print(f"  [O] Open Grading Rationales folder")
    print()
    print(f"  [Q] Quit")
    print()
    
    while True:
        try:
            choice = input(f"Enter choice (1-{len(script_list)}, S, A, C, R, O, or Q): ").strip().upper()
            
            # Check for settings options
            if choice == 'S':
                if HAS_UTILS:
                    change_output_directory()
                else:
                    print("⚠️  Settings not available (utilities module not found)")
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
            elif choice == 'O':
                print(f"📂 Opening: {base_dir}")
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
            elif choice == 'Q':
                print("\n👋 Goodbye!")
                sys.exit(0)
            
            # Check for grading tool selection
            choice_num = int(choice)
            if 1 <= choice_num <= len(script_list):
                selected_type, selected_info = script_list[choice_num - 1]
                return selected_info
            else:
                print(f"❌ Please enter a number between 1 and {len(script_list)}, S, A, C, R, O, or Q")
        except ValueError:
            print("❌ Invalid input. Please try again.")
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            sys.exit(0)

def get_canvas_token():
    """Get Canvas API token from environment or user input."""
    token = os.environ.get("CANVAS_API_TOKEN")
    
    if token:
        return token
    
    print()
    print("❌ CANVAS_API_TOKEN not set.")
    print()
    print("Options:")
    print("  [1] Enter token once (not saved)")
    print("  [2] Save token permanently")
    print()
    
    while True:
        try:
            choice = input("Choose (1 or 2): ").strip()
            if choice in ["1", "2"]:
                break
            print("❌ Please enter 1 or 2")
        except (KeyboardInterrupt, EOFError):
            print("\n\n❌ Cancelled by user")
            sys.exit(0)
    
    print()
    token = getpass.getpass("Enter Canvas API token: ")
    
    if choice == "2":
        save_token_permanently(token)
    
    return token

def save_token_permanently(token):
    """Save token to shell config file."""
    system = platform.system()
    
    if system == "Windows":
        # Windows: Set as system environment variable
        print()
        print("To save permanently on Windows:")
        print("1. Search for 'Environment Variables' in Start Menu")
        print("2. Click 'Environment Variables'")
        print("3. Under 'User variables', click 'New'")
        print("4. Variable name: CANVAS_API_TOKEN")
        print(f"5. Variable value: {token}")
        print()
        print("Or run in PowerShell (as Administrator):")
        print(f'[Environment]::SetEnvironmentVariable("CANVAS_API_TOKEN", "{token}", "User")')
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
                    print(f"⚠️  Token variable already exists in {rc_file}")
                    return
        
        # Append token to file
        with open(rc_file, 'a') as f:
            f.write("\n")
            f.write("# Canvas API token for autograder\n")
            f.write(f'export CANVAS_API_TOKEN="{token}"\n')
        
        print(f"✅ Saved token to {rc_file}")
        print("   (Restart your terminal for it to take effect)")
    except Exception as e:
        print(f"⚠️  Could not save token: {e}")

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
            targets_to_clean = [("Academic_Dishonesty", "csv"), ("Academic_Dishonesty", "excel")]
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
            elif script_type == "Complete-Incomplete" and target == "ci_csv":
                targets_to_clean.append(("Complete-Incomplete", "csv"))
            elif script_type == "Discussion_Forum" and target == "df_csv":
                targets_to_clean.append(("Discussion_Forum", "csv"))
    
    if not targets_to_clean:
        return  # No targets configured for this script type
    
    print()
    print(f"🗑️  Checking for files older than {cleanup_days} days...")
    
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
        print(f"✅ Moved {moved_count} old files to {archive_dir}")
        print("⚠️  Archived files can only be deleted manually — this program will not touch them.")
    else:
        print("✅ No old files found to archive")

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
            print(f"   ⚠️  Could not trash {file_path.name}: {e}")
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
        print(f"✅ Moved {moved_count} old files to {trash_name}")
    else:
        print("✅ No old files found to trash")

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
    
    # For Academic Dishonesty, files are in subdirectories
    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            source_dir = target_dir / "csv"
            dest_dir = archive_dir / "csv"
            pattern = "*.csv"
        else:  # excel
            source_dir = target_dir / "excel"
            dest_dir = archive_dir / "excel"
            pattern = "*.xlsx"
        
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
        print(f"   ✅ Archived {moved_count} {file_type.upper()} files")
    else:
        print(f"   ✅ No old {file_type.upper()} files found to archive")

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
            print(f"   ⚠️  Could not trash {file_path.name}: {e}")
            return False
    
    # For Academic Dishonesty, files are in subdirectories
    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            source_dir = target_dir / "csv"
            pattern = "*.csv"
        else:  # excel
            source_dir = target_dir / "excel"
            pattern = "*.xlsx"
        
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
        print(f"   ✅ Moved {moved_count} {file_type.upper()} files to {trash_name}")
    else:
        print(f"   ✅ No old {file_type.upper()} files found to trash")

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
    print(f"📤 Running {script_name}...")
    print(f"📁 Output will be saved to: {target_dir}")
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
            print("✅ Script completed successfully!")
        else:
            print(f"⚠️  Script exited with code {result.returncode}")
        
        # Check auto-open setting
        settings = load_settings()
        auto_open = settings.get("auto_open_folder", True)
        
        # Show output location and optionally open folder
        if HAS_UTILS:
            print_output_location(target_dir, auto_open=auto_open)
        else:
            print(f"📁 Results saved to: {target_dir}")
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
        print("\n\n❌ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error running script: {e}")
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
    print("✅ Setup complete")
    
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
                print("\n👋 Goodbye!")
                break
        except (KeyboardInterrupt, EOFError):
            print("\n\n👋 Goodbye!")
            break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
        sys.exit(0)