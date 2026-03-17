"""
Insights Engine — assignment-level analysis pipeline.

Phase 1: Non-LLM analysis (Quick Analysis) + preprocessing integration.
Phase 2+: LLM-assisted coding, theme generation, synthesis, feedback.
"""

from insights.models import (
    ConcernRecord,
    ConcernSignal,
    Contradiction,
    ContradictionSignal,
    DraftFeedback,
    EmbeddingCluster,
    KeywordHit,
    OutlierRecord,
    OutlierReport,
    PerSubmissionSummary,
    PipelineConfidence,
    PreprocessingMetadata,
    QuickAnalysisResult,
    QuoteRecord,
    SharedReference,
    SubmissionCodingRecord,
    SubmissionStats,
    SynthesisReport,
    TeacherAnalysisProfile,
    TermFrequency,
    TermScore,
    Theme,
    ThemeSet,
)
from insights.data_fetcher import DataFetcher
from insights.engine import InsightsEngine
from insights.insights_store import InsightsStore
from insights.patterns import INSIGHT_PATTERNS, signal_matrix_classify
from insights.quick_analyzer import QuickAnalyzer
from insights.llm_backend import auto_detect_backend, BackendConfig, send_text
from insights.submission_coder import code_submission
from insights.concern_detector import detect_concerns
from insights.theme_generator import generate_themes, surface_outliers
from insights.synthesizer import synthesize
from insights.teacher_profile import TeacherProfileManager
from insights.lens_templates import (
    LENS_TEMPLATES,
    LensTemplate,
    get_template,
    get_template_choices,
    get_equity_fragment,
)

__all__ = [
    # Engine
    "InsightsEngine",
    "QuickAnalyzer",
    "DataFetcher",
    "InsightsStore",
    # LLM Pipeline
    "auto_detect_backend",
    "BackendConfig",
    "send_text",
    "code_submission",
    "detect_concerns",
    "generate_themes",
    "surface_outliers",
    "synthesize",
    # Patterns
    "INSIGHT_PATTERNS",
    "signal_matrix_classify",
    # Models
    "QuickAnalysisResult",
    "SubmissionCodingRecord",
    "ConcernRecord",
    "ConcernSignal",
    "QuoteRecord",
    "PreprocessingMetadata",
    "SubmissionStats",
    "TermFrequency",
    "TermScore",
    "KeywordHit",
    "EmbeddingCluster",
    "SharedReference",
    "ContradictionSignal",
    "PerSubmissionSummary",
    "Theme",
    "Contradiction",
    "ThemeSet",
    "OutlierRecord",
    "OutlierReport",
    "SynthesisReport",
    "DraftFeedback",
    "TeacherAnalysisProfile",
    "PipelineConfidence",
    # Teacher Profile
    "TeacherProfileManager",
    # Lens Templates
    "LENS_TEMPLATES",
    "LensTemplate",
    "get_template",
    "get_template_choices",
    "get_equity_fragment",
]
