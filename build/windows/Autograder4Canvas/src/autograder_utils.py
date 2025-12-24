"""
Canvas Autograder - Cross-Platform Utilities
Shared utility functions for file paths, trash handling, configuration, and output management.
"""

import os
import platform
import shutil
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta

# =============================================================================
# Configuration Management
# =============================================================================

def get_config_dir() -> Path:
    """Get the configuration directory for storing settings."""
    system = platform.system()
    
    if system == "Windows":
        # Windows: Use %LOCALAPPDATA%\CanvasAutograder
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        config_dir = base / "CanvasAutograder"
    elif system == "Darwin":
        # macOS: Use ~/Library/Application Support/CanvasAutograder
        config_dir = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        # Linux: Use ~/.config/CanvasAutograder
        config_dir = Path.home() / ".config" / "CanvasAutograder"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get path to the configuration file."""
    return get_config_dir() / "settings.json"


def load_config() -> dict:
    """Load configuration from file."""
    config_file = get_config_file()
    
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_config(config: dict):
    """Save configuration to file."""
    config_file = get_config_file()
    
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
    except IOError as e:
        print(f"⚠️  Could not save settings: {e}")


def get_default_output_location() -> Path:
    """Get the default output location."""
    system = platform.system()
    
    if system == "Windows":
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        documents = Path.home() / "Documents"
    
    return documents / "Autograder Rationales"


def get_output_base_dir() -> Path:
    """
    Get the base output directory for grading reports.
    Uses saved preference, or prompts user on first run.
    """
    # Check for container/override directory first
    if os.path.isdir("/output"):
        return Path("/output")
    
    # Load saved config
    config = load_config()
    
    if "output_directory" in config:
        saved_path = Path(config["output_directory"])
        # Verify the saved path is still valid (or can be created)
        try:
            saved_path.mkdir(parents=True, exist_ok=True)
            return saved_path
        except (PermissionError, OSError):
            # Fall through to default if saved path is invalid
            pass
    
    # Return default location
    return get_default_output_location()


def set_output_directory(path: Path) -> bool:
    """
    Set the output directory preference.
    
    Args:
        path: New output directory path
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Verify we can create/access the directory
        path.mkdir(parents=True, exist_ok=True)
        
        # Save to config
        config = load_config()
        config["output_directory"] = str(path)
        save_config(config)
        
        return True
    except (PermissionError, OSError) as e:
        print(f"❌ Cannot use that location: {e}")
        return False


def is_first_run() -> bool:
    """Check if this is the first time running the application."""
    config = load_config()
    return "output_directory" not in config


def run_first_time_setup() -> Path:
    """
    Run first-time setup to configure output directory.
    
    Returns:
        The configured output directory path
    """
    print()
    print("=" * 60)
    print("  📁 FIRST-TIME SETUP: Choose Output Location")
    print("=" * 60)
    print()
    print("Where would you like to save grading reports?")
    print()
    
    # Get default locations
    default_path = get_default_output_location()
    desktop_path = Path.home() / "Desktop" / "Autograder Rationales"
    
    print(f"  [1] Documents folder (recommended)")
    print(f"      {default_path}")
    print()
    print(f"  [2] Desktop")
    print(f"      {desktop_path}")
    print()
    print(f"  [3] Custom location")
    print()
    
    while True:
        try:
            choice = input("Choose (1/2/3, default=1): ").strip() or "1"
            
            if choice == "1":
                selected_path = default_path
                break
            elif choice == "2":
                selected_path = desktop_path
                break
            elif choice == "3":
                print()
                custom = input("Enter full path: ").strip()
                if custom:
                    selected_path = Path(custom).expanduser().resolve()
                    break
                else:
                    print("❌ No path entered. Please try again.")
            else:
                print("❌ Please enter 1, 2, or 3")
        except (KeyboardInterrupt, EOFError):
            print("\n\nUsing default location.")
            selected_path = default_path
            break
    
    # Create the directory and save preference
    if set_output_directory(selected_path):
        print()
        print(f"✅ Grading reports will be saved to:")
        print(f"   {selected_path}")
        print()
        print("   You can change this later from the main menu.")
        print()
    
    return selected_path


def change_output_directory() -> Path:
    """
    Interactive prompt to change the output directory.
    
    Returns:
        The new output directory path
    """
    current = get_output_base_dir()
    
    print()
    print("=" * 60)
    print("  📁 CHANGE OUTPUT LOCATION")
    print("=" * 60)
    print()
    print(f"Current location: {current}")
    print()
    
    # Get suggested locations
    default_path = get_default_output_location()
    desktop_path = Path.home() / "Desktop" / "Autograder Rationales"
    
    print("Choose a new location:")
    print()
    print(f"  [1] Documents folder")
    print(f"      {default_path}")
    print()
    print(f"  [2] Desktop")
    print(f"      {desktop_path}")
    print()
    print(f"  [3] Custom location")
    print()
    print(f"  [4] Keep current location (cancel)")
    print()
    
    while True:
        try:
            choice = input("Choose (1/2/3/4): ").strip()
            
            if choice == "1":
                selected_path = default_path
                break
            elif choice == "2":
                selected_path = desktop_path
                break
            elif choice == "3":
                print()
                custom = input("Enter full path: ").strip()
                if custom:
                    selected_path = Path(custom).expanduser().resolve()
                    break
                else:
                    print("❌ No path entered. Please try again.")
            elif choice == "4" or choice == "":
                print("⏭️  Keeping current location.")
                return current
            else:
                print("❌ Please enter 1, 2, 3, or 4")
        except (KeyboardInterrupt, EOFError):
            print("\n⏭️  Keeping current location.")
            return current
    
    # Save the new preference
    if set_output_directory(selected_path):
        print()
        print(f"✅ Grading reports will now be saved to:")
        print(f"   {selected_path}")
        
        # Ask about moving existing files
        if current.exists() and any(current.iterdir()):
            print()
            move = input("Move existing files to new location? (y/n, default=n): ").strip().lower()
            if move == 'y':
                try:
                    for item in current.iterdir():
                        dest = selected_path / item.name
                        if item.is_dir():
                            if dest.exists():
                                # Merge directories
                                for subitem in item.iterdir():
                                    shutil.move(str(subitem), str(dest / subitem.name))
                                item.rmdir()
                            else:
                                shutil.move(str(item), str(dest))
                        else:
                            shutil.move(str(item), str(dest))
                    print(f"✅ Moved existing files to new location")
                    
                    # Try to remove old empty directory
                    try:
                        current.rmdir()
                    except OSError:
                        pass  # Directory not empty or can't be removed
                        
                except Exception as e:
                    print(f"⚠️  Could not move some files: {e}")
    
    return selected_path


# =============================================================================
# Subdirectory Names (friendly names with spaces)
# =============================================================================

SUBDIRS = {
    "Academic_Dishonesty": "Academic Dishonesty Reports",
    "Discussion_Forum": "Discussion Forums",
    "Complete-Incomplete": "Complete-Incomplete Assignments",
    "Archived": "Archived Reports"
}


def get_output_dir(subdir_key: str) -> Path:
    """
    Get a specific output subdirectory and ensure it exists.
    
    Args:
        subdir_key: Key for subdirectory (e.g., "Academic_Dishonesty", "Discussion_Forum")
    
    Returns:
        Path to the output subdirectory
    """
    base = get_output_base_dir()
    subdir_name = SUBDIRS.get(subdir_key, subdir_key)
    output_dir = base / subdir_name
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def get_archive_dir(subdir_key: str) -> Path:
    """
    Get the archive directory for a specific output type.
    
    Args:
        subdir_key: Key for the original subdirectory
    
    Returns:
        Path to the archive subdirectory
    """
    base = get_output_base_dir()
    archive_base = base / SUBDIRS["Archived"]
    
    # Map to archive subdirectory names
    archive_names = {
        "Academic_Dishonesty": "Academic Dishonesty",
        "Discussion_Forum": "Discussions",
        "Complete-Incomplete": "Assignments"
    }
    
    archive_name = archive_names.get(subdir_key, subdir_key)
    archive_dir = archive_base / archive_name
    archive_dir.mkdir(parents=True, exist_ok=True)
    return archive_dir


# =============================================================================
# File Operations
# =============================================================================

def open_folder(path: Path) -> bool:
    """
    Open a folder in the system file browser.
    Works on macOS, Windows, and Linux.
    
    Args:
        path: Path to the folder to open
    
    Returns:
        True if successful, False otherwise
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    
    system = platform.system()
    
    try:
        if system == "Darwin":
            subprocess.run(['open', str(path)], check=True)
        elif system == "Windows":
            subprocess.run(['explorer', str(path)], check=True)
        else:
            # Linux: Try xdg-open
            subprocess.run(['xdg-open', str(path)], check=True)
        return True
    except Exception:
        return False


def move_to_trash(file_path: Path) -> bool:
    """
    Move a file to the system trash/recycle bin.
    Works on macOS, Windows, and Linux.
    
    Args:
        file_path: Path to the file to trash
    
    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        return False
    
    system = platform.system()
    
    try:
        if system == "Darwin":
            # macOS: Use osascript to move to Trash
            result = subprocess.run(
                ['osascript', '-e', f'tell app "Finder" to delete POSIX file "{file_path}"'],
                capture_output=True,
                text=True
            )
            return result.returncode == 0
            
        elif system == "Windows":
            # Windows: Use PowerShell to move to Recycle Bin
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
                capture_output=True,
                text=True
            )
            return result.returncode == 0
                
        else:
            # Linux: Try gio trash first, then fallback to XDG trash
            result = subprocess.run(
                ['gio', 'trash', str(file_path)],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return True
            
            # Fallback: Move to XDG trash manually
            trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
            trash_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate unique name if file already exists in trash
            dest = trash_dir / file_path.name
            counter = 1
            while dest.exists():
                stem = file_path.stem
                suffix = file_path.suffix
                dest = trash_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            shutil.move(str(file_path), str(dest))
            return True
            
    except Exception as e:
        print(f"   ⚠️  Could not move to trash: {e}")
        return False


def trash_old_files(directory: Path, extensions: list = None, days_old: int = 180) -> int:
    """
    Move files older than specified days to trash.
    
    Args:
        directory: Directory to scan
        extensions: List of file extensions to include (e.g., ['.csv', '.xlsx'])
                   If None, includes all files
        days_old: Age threshold in days
    
    Returns:
        Number of files moved to trash
    """
    if not directory.exists():
        return 0
    
    cutoff_date = datetime.now() - timedelta(days=days_old)
    moved_count = 0
    
    # Get all files matching extensions
    if extensions:
        files = []
        for ext in extensions:
            files.extend(directory.glob(f"*{ext}"))
    else:
        files = [f for f in directory.iterdir() if f.is_file()]
    
    for file_path in files:
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_date:
                if move_to_trash(file_path):
                    moved_count += 1
        except Exception as e:
            print(f"   ⚠️  Error processing {file_path.name}: {e}")
    
    return moved_count


def archive_old_files(source_dir: Path, archive_dir: Path, 
                      extensions: list = None, days_old: int = 180) -> int:
    """
    Archive files older than specified days to an archive directory.
    
    Args:
        source_dir: Directory to scan for old files
        archive_dir: Directory to move files to
        extensions: List of file extensions to include
        days_old: Age threshold in days
    
    Returns:
        Number of files archived
    """
    if not source_dir.exists():
        return 0
    
    archive_dir.mkdir(parents=True, exist_ok=True)
    cutoff_date = datetime.now() - timedelta(days=days_old)
    moved_count = 0
    
    # Get all files matching extensions
    if extensions:
        files = []
        for ext in extensions:
            files.extend(source_dir.glob(f"*{ext}"))
    else:
        files = [f for f in source_dir.iterdir() if f.is_file()]
    
    for file_path in files:
        try:
            mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
            if mtime < cutoff_date:
                dest = archive_dir / file_path.name
                # Handle duplicates
                counter = 1
                while dest.exists():
                    stem = file_path.stem
                    suffix = file_path.suffix
                    dest = archive_dir / f"{stem}_{counter}{suffix}"
                    counter += 1
                
                shutil.move(str(file_path), str(dest))
                moved_count += 1
        except Exception as e:
            print(f"   ⚠️  Error archiving {file_path.name}: {e}")
    
    return moved_count


def print_output_location(output_path: Path, auto_open: bool = True):
    """
    Print the output location and optionally open it.
    
    Args:
        output_path: Path to the output directory or file
        auto_open: Whether to automatically open the folder
    """
    folder = output_path.parent if output_path.is_file() else output_path
    
    print()
    print(f"📁 Output saved to: {folder}")
    
    if auto_open:
        print("   Opening folder...")
        if open_folder(folder):
            print("   ✅ Folder opened")
        else:
            # Print manual instructions if auto-open fails
            system = platform.system()
            if system == "Darwin":
                print(f"   To open manually: open \"{folder}\"")
            elif system == "Windows":
                print(f"   To open manually: explorer \"{folder}\"")
            else:
                print(f"   To open manually: xdg-open \"{folder}\"")
