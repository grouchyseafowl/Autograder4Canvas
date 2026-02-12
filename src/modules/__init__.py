# Academic Dishonesty Check v2.0 Modules
# These modules provide the core analysis functionality.

"""
Available modules:
- marker_loader: Load and manage YAML marker configurations
- peer_comparison: Statistical outlier detection
- context_analyzer: Population-aware adjustments
- report_generator: Pedagogical report generation
- draft_comparison: Compare rough drafts to finals
- citation_verifier: Verify citation validity
- consent_system: User consent management
- update_checker: Check for marker updates
- telemetry_manager: Anonymous data collection (opt-in)
- demographic_collector: Institution demographic data
"""

__version__ = "2.0.0"

# Module availability flags
HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass


# Lazy imports to avoid errors if dependencies missing
def get_marker_loader():
    from .marker_loader import MarkerLoader, load_markers
    return MarkerLoader, load_markers


def get_peer_comparison():
    from .peer_comparison import PeerComparisonAnalyzer, create_submission_metrics
    return PeerComparisonAnalyzer, create_submission_metrics


def get_context_analyzer():
    from .context_analyzer import ContextAnalyzer, analyze_student_context, StudentContext
    return ContextAnalyzer, analyze_student_context, StudentContext


def get_report_generator():
    from .report_generator import ReportGenerator, create_submission_report
    return ReportGenerator, create_submission_report


def get_draft_comparison():
    from .draft_comparison import DraftComparisonAnalyzer, compare_draft_to_final
    return DraftComparisonAnalyzer, compare_draft_to_final


def get_citation_verifier():
    from .citation_verifier import CitationAnalyzer, analyze_citations
    return CitationAnalyzer, analyze_citations


def get_consent_system():
    from .consent_system import ConsentManager, require_consent
    return ConsentManager, require_consent


def get_update_checker():
    from .update_checker import UpdateChecker, check_for_updates, get_update_notice
    return UpdateChecker, check_for_updates, get_update_notice


def get_telemetry_manager():
    from .telemetry_manager import TelemetryManager, TelemetrySystem, get_telemetry_manager as _get
    return TelemetryManager, TelemetrySystem, _get


def get_demographic_collector():
    from .demographic_collector import DemographicCollector, get_demographic_collector as _get
    return DemographicCollector, _get
