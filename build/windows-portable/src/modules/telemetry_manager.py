"""
Telemetry Manager Module
Version 2.0.0

Manages anonymous data collection for improving detection accuracy.
All data collection is OPT-IN with explicit consent.

THREE SEPARATE DATA SYSTEMS:
1. Program Usage Data - Crashes, errors, compatibility issues
2. Dishonesty Marker Data - Pattern effectiveness feedback
3. Batch Feedback - Workflow feature for Canvas comments

Each system has separate consent and can be toggled independently.
"""

import os
import json
import hashlib
import platform
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum


class TelemetrySystem(Enum):
    """The three separate telemetry systems."""
    PROGRAM_USAGE = "program_usage"
    MARKER_DATA = "dishonesty_markers"
    BATCH_FEEDBACK = "batch_feedback"


@dataclass
class UsageEvent:
    """Program usage/error event."""
    event_type: str  # startup, shutdown, error, crash
    timestamp: str
    version: str
    platform: str
    python_version: str
    error_message: Optional[str] = None
    stack_trace: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MarkerFeedback:
    """Feedback on marker effectiveness."""
    marker_id: str
    marker_version: str
    assignment_profile: str
    was_flagged: bool
    instructor_confirmed: Optional[bool] = None  # True = agreed, False = false positive
    context_factors: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass 
class TelemetryConsent:
    """User's consent preferences for each system."""
    program_usage: bool = False
    marker_data: bool = False
    batch_feedback: bool = False
    consent_version: str = "2.0"
    consent_date: Optional[str] = None
    upload_frequency: str = "manual"  # manual, weekly, monthly
    
    def has_any_consent(self) -> bool:
        return self.program_usage or self.marker_data


class TelemetryManager:
    """
    Manages telemetry data collection and upload.
    
    Privacy-First Design:
    - All collection is OPT-IN
    - No personal data ever collected
    - Institution IDs are hashed
    - Data stored locally until explicit upload
    - User can view/delete all data
    """
    
    # Remote endpoint (if configured)
    TELEMETRY_ENDPOINT = None  # Set to URL when server is available
    
    def __init__(self, config_dir: Path = None):
        """
        Initialize telemetry manager.
        
        Args:
            config_dir: Configuration directory (auto-detected if None)
        """
        if config_dir is None:
            config_dir = self._get_config_dir()
        
        self.config_dir = Path(config_dir)
        # Security: Restrict permissions to owner only
        self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        
        self.db_path = self.config_dir / "telemetry.db"
        self.consent_path = self.config_dir / "telemetry_consent.json"
        
        self._consent: Optional[TelemetryConsent] = None
        self._init_database()
    
    def _get_config_dir(self) -> Path:
        """Get platform-appropriate config directory."""
        system = platform.system()
        
        if system == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "CanvasAutograder"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "CanvasAutograder"
        else:
            return Path.home() / ".config" / "CanvasAutograder"
    
    def _init_database(self):
        """Initialize SQLite database for local telemetry storage."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Usage events table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS usage_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_type TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                version TEXT,
                platform TEXT,
                python_version TEXT,
                error_message TEXT,
                stack_trace TEXT,
                context_json TEXT,
                uploaded INTEGER DEFAULT 0
            )
        """)
        
        # Marker feedback table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS marker_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                marker_id TEXT NOT NULL,
                marker_version TEXT,
                assignment_profile TEXT,
                was_flagged INTEGER,
                instructor_confirmed INTEGER,
                context_json TEXT,
                timestamp TEXT NOT NULL,
                uploaded INTEGER DEFAULT 0
            )
        """)
        
        # Upload history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS upload_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                system TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                records_uploaded INTEGER,
                success INTEGER
            )
        """)
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # CONSENT MANAGEMENT
    # =========================================================================
    
    def get_consent(self) -> TelemetryConsent:
        """Get current consent preferences."""
        if self._consent is not None:
            return self._consent
        
        if self.consent_path.exists():
            try:
                with open(self.consent_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._consent = TelemetryConsent(
                        program_usage=data.get('program_usage', False),
                        marker_data=data.get('marker_data', False),
                        batch_feedback=data.get('batch_feedback', False),
                        consent_version=data.get('consent_version', '2.0'),
                        consent_date=data.get('consent_date'),
                        upload_frequency=data.get('upload_frequency', 'manual')
                    )
                    return self._consent
            except Exception:
                pass
        
        # Default: no consent
        self._consent = TelemetryConsent()
        return self._consent
    
    def update_consent(self, system: TelemetrySystem, enabled: bool, 
                       upload_frequency: str = None):
        """
        Update consent for a specific telemetry system.
        
        Args:
            system: Which system to update
            enabled: Whether to enable data collection
            upload_frequency: How often to upload (manual, weekly, monthly)
        """
        consent = self.get_consent()
        
        if system == TelemetrySystem.PROGRAM_USAGE:
            consent.program_usage = enabled
        elif system == TelemetrySystem.MARKER_DATA:
            consent.marker_data = enabled
        elif system == TelemetrySystem.BATCH_FEEDBACK:
            consent.batch_feedback = enabled
        
        if upload_frequency:
            consent.upload_frequency = upload_frequency
        
        consent.consent_date = datetime.now().isoformat()
        
        self._save_consent(consent)
    
    def _save_consent(self, consent: TelemetryConsent):
        """Save consent preferences to disk."""
        self._consent = consent
        
        with open(self.consent_path, 'w', encoding='utf-8') as f:
            json.dump({
                'program_usage': consent.program_usage,
                'marker_data': consent.marker_data,
                'batch_feedback': consent.batch_feedback,
                'consent_version': consent.consent_version,
                'consent_date': consent.consent_date,
                'upload_frequency': consent.upload_frequency
            }, f, indent=2)
    
    def is_enabled(self, system: TelemetrySystem) -> bool:
        """Check if a specific telemetry system is enabled."""
        consent = self.get_consent()
        
        if system == TelemetrySystem.PROGRAM_USAGE:
            return consent.program_usage
        elif system == TelemetrySystem.MARKER_DATA:
            return consent.marker_data
        elif system == TelemetrySystem.BATCH_FEEDBACK:
            return consent.batch_feedback
        
        return False
    
    # =========================================================================
    # PROGRAM USAGE DATA
    # =========================================================================
    
    def log_startup(self, version: str):
        """Log program startup (if consented)."""
        if not self.is_enabled(TelemetrySystem.PROGRAM_USAGE):
            return
        
        event = UsageEvent(
            event_type="startup",
            timestamp=datetime.now().isoformat(),
            version=version,
            platform=f"{platform.system()} {platform.release()}",
            python_version=platform.python_version()
        )
        
        self._store_usage_event(event)
    
    def log_error(self, error_message: str, stack_trace: str = None,
                  context: Dict = None, version: str = "unknown"):
        """Log an error (if consented)."""
        if not self.is_enabled(TelemetrySystem.PROGRAM_USAGE):
            return
        
        event = UsageEvent(
            event_type="error",
            timestamp=datetime.now().isoformat(),
            version=version,
            platform=f"{platform.system()} {platform.release()}",
            python_version=platform.python_version(),
            error_message=error_message,
            stack_trace=stack_trace,
            context=context or {}
        )
        
        self._store_usage_event(event)
    
    def log_feature_use(self, feature: str, context: Dict = None,
                        version: str = "unknown"):
        """Log feature usage (if consented)."""
        if not self.is_enabled(TelemetrySystem.PROGRAM_USAGE):
            return
        
        event = UsageEvent(
            event_type="feature_use",
            timestamp=datetime.now().isoformat(),
            version=version,
            platform=f"{platform.system()} {platform.release()}",
            python_version=platform.python_version(),
            context={"feature": feature, **(context or {})}
        )
        
        self._store_usage_event(event)
    
    def _store_usage_event(self, event: UsageEvent):
        """Store usage event in local database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO usage_events 
            (event_type, timestamp, version, platform, python_version,
             error_message, stack_trace, context_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event.event_type,
            event.timestamp,
            event.version,
            event.platform,
            event.python_version,
            event.error_message,
            event.stack_trace,
            json.dumps(event.context) if event.context else None
        ))
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # MARKER FEEDBACK DATA
    # =========================================================================
    
    def log_marker_result(self, marker_id: str, marker_version: str,
                          assignment_profile: str, was_flagged: bool,
                          instructor_confirmed: bool = None,
                          context_factors: Dict = None):
        """
        Log marker detection result for effectiveness tracking.
        
        Args:
            marker_id: Which marker triggered
            marker_version: Version of marker file
            assignment_profile: Which profile was used
            was_flagged: Whether this marker flagged the submission
            instructor_confirmed: True if instructor agreed with flag
            context_factors: ESL, first-gen, etc.
        """
        if not self.is_enabled(TelemetrySystem.MARKER_DATA):
            return
        
        feedback = MarkerFeedback(
            marker_id=marker_id,
            marker_version=marker_version,
            assignment_profile=assignment_profile,
            was_flagged=was_flagged,
            instructor_confirmed=instructor_confirmed,
            context_factors=context_factors or {}
        )
        
        self._store_marker_feedback(feedback)
    
    def log_analysis_result(self, analysis_summary: Dict,
                            instructor_feedback: Dict = None):
        """
        Log complete analysis results.
        
        Args:
            analysis_summary: Summary of what was flagged
            instructor_feedback: Which flags instructor agreed/disagreed with
        """
        if not self.is_enabled(TelemetrySystem.MARKER_DATA):
            return
        
        # Log each marker that fired
        for marker_id, marker_data in analysis_summary.get('markers_triggered', {}).items():
            confirmed = None
            if instructor_feedback:
                confirmed = instructor_feedback.get(marker_id)
            
            self.log_marker_result(
                marker_id=marker_id,
                marker_version=marker_data.get('version', 'unknown'),
                assignment_profile=analysis_summary.get('profile', 'standard'),
                was_flagged=True,
                instructor_confirmed=confirmed,
                context_factors=analysis_summary.get('context', {})
            )
    
    def _store_marker_feedback(self, feedback: MarkerFeedback):
        """Store marker feedback in local database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO marker_feedback
            (marker_id, marker_version, assignment_profile, was_flagged,
             instructor_confirmed, context_json, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            feedback.marker_id,
            feedback.marker_version,
            feedback.assignment_profile,
            1 if feedback.was_flagged else 0,
            None if feedback.instructor_confirmed is None else (1 if feedback.instructor_confirmed else 0),
            json.dumps(feedback.context_factors) if feedback.context_factors else None,
            feedback.timestamp
        ))
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # DATA VIEWING & DELETION
    # =========================================================================
    
    def get_stored_data_summary(self) -> Dict:
        """Get summary of all stored telemetry data."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count usage events
        cursor.execute("SELECT COUNT(*) FROM usage_events WHERE uploaded = 0")
        pending_usage = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM usage_events WHERE uploaded = 1")
        uploaded_usage = cursor.fetchone()[0]
        
        # Count marker feedback
        cursor.execute("SELECT COUNT(*) FROM marker_feedback WHERE uploaded = 0")
        pending_markers = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM marker_feedback WHERE uploaded = 1")
        uploaded_markers = cursor.fetchone()[0]
        
        # Last upload
        cursor.execute("""
            SELECT timestamp FROM upload_history 
            WHERE success = 1 ORDER BY timestamp DESC LIMIT 1
        """)
        last_upload = cursor.fetchone()
        
        conn.close()
        
        return {
            'usage_events': {
                'pending': pending_usage,
                'uploaded': uploaded_usage,
                'total': pending_usage + uploaded_usage
            },
            'marker_feedback': {
                'pending': pending_markers,
                'uploaded': uploaded_markers,
                'total': pending_markers + uploaded_markers
            },
            'last_upload': last_upload[0] if last_upload else None
        }
    
    def view_pending_data(self, system: TelemetrySystem, limit: int = 50) -> List[Dict]:
        """View pending (not yet uploaded) data for review."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if system == TelemetrySystem.PROGRAM_USAGE:
            cursor.execute("""
                SELECT event_type, timestamp, version, platform, error_message
                FROM usage_events WHERE uploaded = 0
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            columns = ['event_type', 'timestamp', 'version', 'platform', 'error_message']
        
        elif system == TelemetrySystem.MARKER_DATA:
            cursor.execute("""
                SELECT marker_id, assignment_profile, was_flagged, instructor_confirmed, timestamp
                FROM marker_feedback WHERE uploaded = 0
                ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
            columns = ['marker_id', 'profile', 'flagged', 'confirmed', 'timestamp']
        
        else:
            return []
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(zip(columns, row)) for row in rows]
    
    def delete_all_data(self, system: TelemetrySystem = None):
        """
        Delete stored telemetry data.
        
        Args:
            system: Specific system to delete, or None for all
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if system is None or system == TelemetrySystem.PROGRAM_USAGE:
            cursor.execute("DELETE FROM usage_events")
        
        if system is None or system == TelemetrySystem.MARKER_DATA:
            cursor.execute("DELETE FROM marker_feedback")
        
        conn.commit()
        conn.close()
    
    # =========================================================================
    # DATA UPLOAD
    # =========================================================================
    
    def upload_pending_data(self, system: TelemetrySystem = None) -> Dict:
        """
        Upload pending telemetry data to remote server.
        
        Args:
            system: Specific system to upload, or None for all enabled
            
        Returns:
            Upload result with counts and any errors
        """
        if self.TELEMETRY_ENDPOINT is None:
            return {
                'success': False,
                'error': 'No telemetry endpoint configured',
                'records_uploaded': 0
            }
        
        results = {
            'success': True,
            'systems_uploaded': [],
            'total_records': 0,
            'errors': []
        }
        
        systems_to_upload = []
        if system:
            systems_to_upload = [system]
        else:
            if self.is_enabled(TelemetrySystem.PROGRAM_USAGE):
                systems_to_upload.append(TelemetrySystem.PROGRAM_USAGE)
            if self.is_enabled(TelemetrySystem.MARKER_DATA):
                systems_to_upload.append(TelemetrySystem.MARKER_DATA)
        
        for sys in systems_to_upload:
            try:
                count = self._upload_system_data(sys)
                results['systems_uploaded'].append(sys.value)
                results['total_records'] += count
            except Exception as e:
                results['errors'].append(f"{sys.value}: {str(e)}")
                results['success'] = False
        
        return results
    
    def _upload_system_data(self, system: TelemetrySystem) -> int:
        """Upload data for a specific system."""
        # This would connect to remote server
        # For now, just mark as uploaded locally
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if system == TelemetrySystem.PROGRAM_USAGE:
            cursor.execute("UPDATE usage_events SET uploaded = 1 WHERE uploaded = 0")
            count = cursor.rowcount
        elif system == TelemetrySystem.MARKER_DATA:
            cursor.execute("UPDATE marker_feedback SET uploaded = 1 WHERE uploaded = 0")
            count = cursor.rowcount
        else:
            count = 0
        
        # Log upload
        cursor.execute("""
            INSERT INTO upload_history (system, timestamp, records_uploaded, success)
            VALUES (?, ?, ?, 1)
        """, (system.value, datetime.now().isoformat(), count))
        
        conn.commit()
        conn.close()
        
        return count
    
    def should_auto_upload(self) -> bool:
        """Check if automatic upload is due based on frequency setting."""
        consent = self.get_consent()
        
        if consent.upload_frequency == 'manual':
            return False
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT timestamp FROM upload_history 
            WHERE success = 1 ORDER BY timestamp DESC LIMIT 1
        """)
        
        last = cursor.fetchone()
        conn.close()
        
        if last is None:
            return True
        
        last_upload = datetime.fromisoformat(last[0])
        now = datetime.now()
        
        if consent.upload_frequency == 'weekly':
            return (now - last_upload) > timedelta(days=7)
        elif consent.upload_frequency == 'monthly':
            return (now - last_upload) > timedelta(days=30)
        
        return False


# =============================================================================
# INTERACTIVE CONSENT WIZARD
# =============================================================================

def run_telemetry_consent_wizard() -> TelemetryConsent:
    """
    Interactive wizard for first-time telemetry consent setup.
    
    Returns:
        TelemetryConsent with user's preferences
    """
    print("\n" + "=" * 70)
    print("DATA COLLECTION PREFERENCES")
    print("=" * 70)
    print("""
This tool can optionally collect anonymous data to improve detection
accuracy. ALL data collection is:

  • OPT-IN (disabled by default)
  • ANONYMOUS (no personal or student data)
  • TRANSPARENT (you can view all stored data)
  • DELETABLE (you can delete anytime)

You'll now choose settings for THREE separate data systems.
""")
    
    input("Press Enter to continue...")
    
    # System 1: Program Usage
    print("\n" + "-" * 50)
    print("SYSTEM 1: Program Usage Data")
    print("-" * 50)
    print("""
WHAT IT COLLECTS:
  • Crash reports and error messages
  • Feature usage statistics (which tools you use)
  • Platform/Python version (for compatibility)

WHAT IT DOES NOT COLLECT:
  • Student names, IDs, or submissions
  • Assignment content
  • Your institution name
  • Canvas API tokens or credentials

PURPOSE: Help fix bugs and improve compatibility
""")
    
    usage_consent = _get_yes_no("Enable program usage data collection? (y/n): ", default=False)
    
    # System 2: Marker Data
    print("\n" + "-" * 50)
    print("SYSTEM 2: Dishonesty Marker Feedback")
    print("-" * 50)
    print("""
WHAT IT COLLECTS:
  • Which markers triggered (e.g., "ai_transitions flagged 3 times")
  • Whether you confirmed or dismissed flags
  • Assignment profile used
  • Context factors (ESL prevalence, etc.)

WHAT IT DOES NOT COLLECT:
  • Actual submission text
  • Student names or identifiers
  • Your feedback comments

PURPOSE: Improve marker accuracy, reduce false positives
""")
    
    marker_consent = _get_yes_no("Enable marker effectiveness feedback? (y/n): ", default=False)
    
    # Upload frequency (if either enabled)
    upload_freq = "manual"
    if usage_consent or marker_consent:
        print("\n" + "-" * 50)
        print("UPLOAD FREQUENCY")
        print("-" * 50)
        print("""
How often should collected data be uploaded?

  1. Manual only (you choose when to upload)
  2. Weekly (automatic, with notification)
  3. Monthly (automatic, with notification)

Data is stored locally until uploaded. You can always
view and delete stored data before uploading.
""")
        
        while True:
            choice = input("Choose upload frequency (1/2/3, default=1): ").strip()
            if choice in ['', '1']:
                upload_freq = 'manual'
                break
            elif choice == '2':
                upload_freq = 'weekly'
                break
            elif choice == '3':
                upload_freq = 'monthly'
                break
            print("Please enter 1, 2, or 3")
    
    # Create consent object
    consent = TelemetryConsent(
        program_usage=usage_consent,
        marker_data=marker_consent,
        batch_feedback=False,  # Separate feature
        consent_date=datetime.now().isoformat(),
        upload_frequency=upload_freq
    )
    
    # Summary
    print("\n" + "=" * 70)
    print("DATA COLLECTION SUMMARY")
    print("=" * 70)
    print(f"""
Your choices:
  Program usage data:     {"ENABLED" if usage_consent else "DISABLED"}
  Marker feedback:        {"ENABLED" if marker_consent else "DISABLED"}
  Upload frequency:       {upload_freq.upper()}

You can change these settings anytime from:
  Settings > Data Collection & Privacy
""")
    
    input("Press Enter to continue...")
    
    return consent


def _get_yes_no(prompt: str, default: bool = False) -> bool:
    """Get yes/no input from user."""
    while True:
        response = input(prompt).strip().lower()
        if response in ['y', 'yes']:
            return True
        elif response in ['n', 'no', '']:
            return default
        print("Please enter 'y' or 'n'")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_manager: Optional[TelemetryManager] = None

def get_telemetry_manager() -> TelemetryManager:
    """Get or create the global telemetry manager."""
    global _manager
    if _manager is None:
        _manager = TelemetryManager()
    return _manager


def log_startup(version: str):
    """Convenience function to log startup."""
    get_telemetry_manager().log_startup(version)


def log_error(error_message: str, stack_trace: str = None, 
              context: Dict = None, version: str = "unknown"):
    """Convenience function to log error."""
    get_telemetry_manager().log_error(error_message, stack_trace, context, version)


def log_feature_use(feature: str, context: Dict = None, version: str = "unknown"):
    """Convenience function to log feature usage."""
    get_telemetry_manager().log_feature_use(feature, context, version)
