"""
File cleanup functions for Canvas Autograder.
Shared by both the TUI (run_autograder.py) and the GUI.
"""
import os
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

try:
    from autograder_utils import get_archive_dir, move_to_trash
    _HAS_UTILS = True
except Exception:
    _HAS_UTILS = False

try:
    from settings import load_settings
except ImportError:
    try:
        from src.settings import load_settings
    except ImportError:
        def load_settings() -> dict:  # type: ignore[misc]
            return {
                "auto_open_folder": True,
                "cleanup_mode": "none",
                "cleanup_threshold_days": 180,
                "cleanup_targets": "all",
            }


def _get_base_exports_dir() -> Path:
    try:
        from autograder_utils import get_output_base_dir
        return get_output_base_dir()
    except Exception:
        pass
    if os.path.isdir("/output"):
        return Path("/output")
    if platform.system() == "Windows":
        documents = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
    else:
        documents = Path.home() / "Documents"
    return documents / "Autograder Rationales"


def _get_archive_dir_for_type(script_type: str) -> Path:
    if _HAS_UTILS:
        return get_archive_dir(script_type)
    archive_map = {
        "Academic_Dishonesty": "Academic Dishonesty",
        "Discussion_Forum": "Discussions",
        "Complete-Incomplete": "Assignments",
    }
    archive_subdir = archive_map.get(script_type, "Other")
    return _get_base_exports_dir() / "Archived Reports" / archive_subdir


def _move_to_trash(file_path: Path) -> bool:
    """Move a single file to the system trash. Cross-platform."""
    if _HAS_UTILS:
        return move_to_trash(file_path)
    system = platform.system()
    try:
        if system == "Darwin":
            os.system(f'osascript -e \'tell app "Finder" to delete POSIX file "{file_path}"\'')
            return True
        elif system == "Windows":
            ps = (
                "Add-Type -AssemblyName Microsoft.VisualBasic; "
                f"[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile("
                f"'{file_path}','OnlyErrorDialogs','SendToRecycleBin')"
            )
            r = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
            return r.returncode == 0
        else:
            r = subprocess.run(["gio", "trash", str(file_path)], capture_output=True, text=True)
            if r.returncode == 0:
                return True
            trash_dir = Path.home() / ".local" / "share" / "Trash" / "files"
            trash_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(trash_dir / file_path.name))
            return True
    except Exception:
        return False


def _iter_files(target_dir: Path, script_type: str, file_type: str):
    """Yield (file_path, dest_parent_or_None) tuples matching the criteria."""
    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            source_dir = target_dir / "csv"
            pattern = "*.csv"
        elif file_type == "excel":
            source_dir = target_dir / "excel"
            pattern = "*.xlsx"
        else:  # txt
            source_dir = target_dir
            pattern = "*_report.txt"
        if source_dir.exists():
            yield from source_dir.glob(pattern)
    else:
        if target_dir.exists():
            pattern = "*.csv" if file_type == "csv" else "*.xlsx"
            yield from target_dir.glob(pattern)


def archive_files_by_type(
    target_dir: Path,
    script_type: str,
    file_type: str,
    threshold_days: int = 180,
) -> int:
    """Archive old files of a specific type. Returns count moved."""
    archive_dir = _get_archive_dir_for_type(script_type)
    cutoff = datetime.now() - timedelta(days=threshold_days)
    moved = 0

    if script_type == "Academic_Dishonesty":
        if file_type == "csv":
            dest_dir = archive_dir / "csv"
        elif file_type == "excel":
            dest_dir = archive_dir / "excel"
        else:
            dest_dir = archive_dir
    else:
        dest_dir = archive_dir

    for f in _iter_files(target_dir, script_type, file_type):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dest_dir / f.name))
            moved += 1
    return moved


def trash_files_by_type(
    target_dir: Path,
    script_type: str,
    file_type: str,
    threshold_days: int = 180,
) -> int:
    """Move old files of a specific type to Trash. Returns count moved."""
    cutoff = datetime.now() - timedelta(days=threshold_days)
    moved = 0
    for f in _iter_files(target_dir, script_type, file_type):
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
            if _move_to_trash(f):
                moved += 1
    return moved


def count_files_to_clean(
    target_dir: Path,
    script_type: str,
    file_type: str,
    threshold_days: int = 180,
) -> int:
    """Count files that would be affected by cleanup (dry-run preview)."""
    cutoff = datetime.now() - timedelta(days=threshold_days)
    return sum(
        1
        for f in _iter_files(target_dir, script_type, file_type)
        if datetime.fromtimestamp(f.stat().st_mtime) < cutoff
    )


def cleanup_old_files(target_dir: Path, script_type: str) -> None:
    """Auto-clean files based on saved settings. Called after each grading run."""
    settings = load_settings()
    mode = settings.get("cleanup_mode", "none")
    if mode == "none":
        return

    days = settings.get("cleanup_threshold_days", 180)
    targets_str = settings.get("cleanup_targets", "all")

    pairs: list = []
    if targets_str == "all":
        if script_type == "Academic_Dishonesty":
            pairs = [("Academic_Dishonesty", "csv"), ("Academic_Dishonesty", "excel"), ("Academic_Dishonesty", "txt")]
        elif script_type == "Complete-Incomplete":
            pairs = [("Complete-Incomplete", "csv")]
        elif script_type == "Discussion_Forum":
            pairs = [("Discussion_Forum", "csv")]
    else:
        mapping = {
            "ad_csv":   ("Academic_Dishonesty", "csv"),
            "ad_excel": ("Academic_Dishonesty", "excel"),
            "ad_txt":   ("Academic_Dishonesty", "txt"),
            "ci_csv":   ("Complete-Incomplete", "csv"),
            "df_csv":   ("Discussion_Forum", "csv"),
        }
        for t in targets_str.split(","):
            t = t.strip()
            entry = mapping.get(t)
            if entry and entry[0] == script_type:
                pairs.append(entry)

    for st, ft in pairs:
        if mode == "archive":
            archive_files_by_type(target_dir, st, ft, days)
        elif mode == "trash":
            trash_files_by_type(target_dir, st, ft, days)
