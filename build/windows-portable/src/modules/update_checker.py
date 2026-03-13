"""
Update Checker Module
Checks for updates to marker files and configurations.
Notifies users of available updates without auto-installing.
"""

import json
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Network requests optional
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class UpdateInfo:
    """Information about an available update."""
    component: str  # marker_id or profile_id
    component_type: str  # marker, profile, context_profile
    current_version: str
    available_version: str
    change_summary: str
    is_critical: bool


@dataclass
class UpdateCheckResult:
    """Result of checking for updates."""
    check_time: str
    updates_available: int
    critical_updates: int
    updates: List[UpdateInfo]
    error: Optional[str] = None


class UpdateChecker:
    """
    Checks for updates to marker configurations.
    
    Philosophy:
    Updates are NOT auto-installed. Instructors should review
    any changes to detection patterns before deploying them.
    This ensures instructors maintain control over what patterns
    are flagged in their courses.
    
    Update sources:
    - Remote manifest (if configured)
    - Local file checksums (detect modifications)
    """
    
    # Update manifest URL (would be configured in production)
    UPDATE_MANIFEST_URL = None  # Set to actual URL when available
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize update checker."""
        self.config_dir = config_dir or self._get_default_config_dir()
        self.markers_dir = self.config_dir / "config" / "dishonesty_markers"
        self.cache_file = self.config_dir / ".update_cache.json"
        self.check_interval = timedelta(days=7)  # Weekly checks
    
    def _get_default_config_dir(self) -> Path:
        """Get default config directory."""
        import platform
        import os
        system = platform.system()
        
        if system == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "CanvasAutograder"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "CanvasAutograder"
        else:
            return Path.home() / ".config" / "CanvasAutograder"
    
    def should_check(self) -> bool:
        """Check if enough time has passed since last check."""
        if not self.cache_file.exists():
            return True
        
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            
            last_check = datetime.fromisoformat(cache.get('last_check', '2000-01-01'))
            return datetime.now() - last_check > self.check_interval
        except Exception:
            return True
    
    def check_for_updates(self, force: bool = False) -> UpdateCheckResult:
        """
        Check for available updates.
        
        Args:
            force: Check even if recently checked
            
        Returns:
            UpdateCheckResult with available updates
        """
        if not force and not self.should_check():
            return self._load_cached_result()
        
        updates = []
        error = None
        
        # Check remote manifest if configured and available
        if self.UPDATE_MANIFEST_URL and HAS_REQUESTS:
            remote_updates, remote_error = self._check_remote_manifest()
            if remote_error:
                error = remote_error
            else:
                updates.extend(remote_updates)
        
        # Check local file integrity
        local_updates = self._check_local_integrity()
        updates.extend(local_updates)
        
        # Create result
        result = UpdateCheckResult(
            check_time=datetime.now().isoformat(),
            updates_available=len(updates),
            critical_updates=sum(1 for u in updates if u.is_critical),
            updates=updates,
            error=error
        )
        
        # Cache result
        self._save_cache(result)
        
        return result
    
    def _check_remote_manifest(self) -> Tuple[List[UpdateInfo], Optional[str]]:
        """Check remote manifest for updates."""
        try:
            response = requests.get(self.UPDATE_MANIFEST_URL, timeout=10)
            response.raise_for_status()
            
            manifest = response.json()
            updates = []
            
            # Compare versions
            local_manifest = self._load_local_manifest()
            
            for marker_id, remote_info in manifest.get('markers', {}).items():
                local_version = local_manifest.get('core_markers', {}).get(
                    marker_id, {}
                ).get('version', '0.0.0')
                remote_version = remote_info.get('version', '0.0.0')
                
                if self._version_compare(remote_version, local_version) > 0:
                    updates.append(UpdateInfo(
                        component=marker_id,
                        component_type='marker',
                        current_version=local_version,
                        available_version=remote_version,
                        change_summary=remote_info.get('change_summary', 'No summary'),
                        is_critical=remote_info.get('is_critical', False)
                    ))
            
            return updates, None
            
        except Exception as e:
            return [], f"Could not check remote updates: {str(e)}"
    
    def _check_local_integrity(self) -> List[UpdateInfo]:
        """Check local files for modifications."""
        updates = []
        
        manifest = self._load_local_manifest()
        if not manifest:
            return updates
        
        # Check each marker file
        core_dir = self.markers_dir / "core"
        if core_dir.exists():
            for marker_id, info in manifest.get('core_markers', {}).items():
                marker_file = core_dir / f"{marker_id}.yaml"
                
                if not marker_file.exists():
                    updates.append(UpdateInfo(
                        component=marker_id,
                        component_type='marker',
                        current_version=info.get('version', 'unknown'),
                        available_version='missing',
                        change_summary='Marker file is missing',
                        is_critical=True
                    ))
                    continue
                
                # Check checksum if stored
                stored_checksum = info.get('checksum')
                if stored_checksum:
                    current_checksum = self._file_checksum(marker_file)
                    if current_checksum != stored_checksum:
                        updates.append(UpdateInfo(
                            component=marker_id,
                            component_type='marker',
                            current_version=info.get('version', 'unknown'),
                            available_version='modified',
                            change_summary='File has been modified locally',
                            is_critical=False
                        ))
        
        return updates
    
    def _load_local_manifest(self) -> Dict:
        """Load local marker manifest."""
        manifest_file = self.markers_dir / "marker_manifest.yaml"
        
        if not manifest_file.exists():
            return {}
        
        try:
            import yaml
            with open(manifest_file, 'r') as f:
                return yaml.safe_load(f) or {}
        except ImportError:
            # Try JSON fallback
            json_file = self.markers_dir / "marker_manifest.json"
            if json_file.exists():
                with open(json_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception:
            return {}
    
    def _version_compare(self, v1: str, v2: str) -> int:
        """
        Compare version strings.
        Returns: >0 if v1 > v2, <0 if v1 < v2, 0 if equal
        """
        def parse_version(v):
            try:
                return tuple(int(x) for x in v.split('.'))
            except (ValueError, AttributeError):
                return (0, 0, 0)
        
        p1 = parse_version(v1)
        p2 = parse_version(v2)
        
        if p1 > p2:
            return 1
        elif p1 < p2:
            return -1
        return 0
    
    def _file_checksum(self, path: Path) -> str:
        """Calculate file checksum."""
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except Exception:
            return ""
    
    def _save_cache(self, result: UpdateCheckResult):
        """Save check result to cache."""
        try:
            self.config_dir.mkdir(parents=True, exist_ok=True)
            
            cache = {
                'last_check': result.check_time,
                'updates_available': result.updates_available,
                'critical_updates': result.critical_updates,
                'updates': [
                    {
                        'component': u.component,
                        'component_type': u.component_type,
                        'current_version': u.current_version,
                        'available_version': u.available_version,
                        'change_summary': u.change_summary,
                        'is_critical': u.is_critical
                    }
                    for u in result.updates
                ]
            }
            
            with open(self.cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
        except Exception:
            pass  # Non-critical
    
    def _load_cached_result(self) -> UpdateCheckResult:
        """Load cached check result."""
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            
            return UpdateCheckResult(
                check_time=cache.get('last_check', ''),
                updates_available=cache.get('updates_available', 0),
                critical_updates=cache.get('critical_updates', 0),
                updates=[
                    UpdateInfo(**u) for u in cache.get('updates', [])
                ],
                error=None
            )
        except Exception:
            return UpdateCheckResult(
                check_time='',
                updates_available=0,
                critical_updates=0,
                updates=[],
                error='Could not load cached result'
            )
    
    def compute_checksums(self) -> Dict[str, str]:
        """
        Compute checksums for all marker files.
        Useful for populating manifest initially.
        """
        checksums = {}
        
        core_dir = self.markers_dir / "core"
        if core_dir.exists():
            for yaml_file in core_dir.glob("*.yaml"):
                marker_id = yaml_file.stem
                checksums[marker_id] = self._file_checksum(yaml_file)
        
        return checksums
    
    def format_update_notice(self, result: UpdateCheckResult) -> str:
        """Format update result as user-friendly notice."""
        if result.error:
            return f"⚠ Update check error: {result.error}"
        
        if result.updates_available == 0:
            return "✓ All markers are up to date."
        
        lines = []
        
        if result.critical_updates > 0:
            lines.append(f"⚠ {result.critical_updates} CRITICAL update(s) available!")
        
        lines.append(f"{result.updates_available} update(s) available:")
        
        for update in result.updates:
            critical = " [CRITICAL]" if update.is_critical else ""
            lines.append(
                f"  • {update.component}: {update.current_version} → "
                f"{update.available_version}{critical}"
            )
            lines.append(f"    {update.change_summary}")
        
        lines.append("")
        lines.append("Updates are not auto-installed. Review changes before applying.")
        
        return "\n".join(lines)


def check_for_updates(config_dir: Optional[Path] = None, 
                      force: bool = False) -> UpdateCheckResult:
    """
    Convenience function to check for updates.
    
    Args:
        config_dir: Configuration directory
        force: Force check even if recently checked
        
    Returns:
        UpdateCheckResult
    """
    checker = UpdateChecker(config_dir)
    return checker.check_for_updates(force)


def get_update_notice(config_dir: Optional[Path] = None) -> str:
    """Get formatted update notice if updates available."""
    checker = UpdateChecker(config_dir)
    
    if not checker.should_check():
        result = checker._load_cached_result()
        if result.updates_available == 0:
            return ""  # No notice needed
    else:
        result = checker.check_for_updates()
    
    if result.updates_available > 0:
        return checker.format_update_notice(result)
    
    return ""
