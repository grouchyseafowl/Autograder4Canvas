"""
Pydantic data models for the Insights Engine.

These models define the structured data that flows between pipeline stages.
Structured data between stages (never free text) is the primary mitigation
against map-reduce information loss.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Preprocessing metadata (carried from PreprocessedSubmission)
# ---------------------------------------------------------------------------

class PreprocessingMetadata(BaseModel):
    """Metadata about what preprocessing was applied to a submission."""
    was_translated: bool = False
    was_transcribed: bool = False
    was_image_transcribed: bool = False
    original_language_name: Optional[str] = None
    original_text: Optional[str] = None
    teacher_comment: Optional[str] = None
    needs_teacher_comment: bool = False


# ---------------------------------------------------------------------------
# Sub-records used in SubmissionCodingRecord
# ---------------------------------------------------------------------------

class QuoteRecord(BaseModel):
    """A verbatim quote from a student submission with significance note."""
    text: str
    significance: str  # why this quote matters (1 sentence)


class ConcernRecord(BaseModel):
    """A flagged passage for teacher review.

    NOTE: No concern_type field. The model surfaces, the teacher classifies.
    This is honest about what 8B can do.
    """
    flagged_passage: str
    surrounding_context: str  # 2-3 sentences around the flagged passage
    why_flagged: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


# ---------------------------------------------------------------------------
# Per-submission coding record (Phase 2+ LLM output)
# ---------------------------------------------------------------------------

class SubmissionCodingRecord(BaseModel):
    """Structured record for one student submission.

    This is the atomic data unit — synthesis never sees raw submissions,
    only these records. Richness here = nuance preserved downstream.

    NOTE: No engagement_depth categorical field (8B can't judge this reliably).
    Instead we surface evidence: quotes, concepts_applied, personal_connections,
    readings_referenced. Teacher judges depth.

    NOTE: No uniqueness_flag (model hasn't seen other submissions at coding time).
    Uniqueness detected in outlier pass.
    """
    student_id: str
    student_name: str

    # Theme coding (1-5 tags, from open vocabulary)
    theme_tags: List[str] = []
    theme_confidence: Dict[str, float] = {}  # tag → 0.0-1.0

    # Notable quotes (verbatim — teacher hears the student's actual voice)
    notable_quotes: List[QuoteRecord] = []  # max 3

    # Emotional register
    emotional_register: str = ""  # analytical|passionate|personal|urgent|reflective|disengaged
    emotional_notes: str = ""

    # Content engagement evidence
    readings_referenced: List[str] = []
    concepts_applied: List[str] = []
    personal_connections: List[str] = []
    current_events_referenced: List[str] = []

    # Concern flags (populated by DEDICATED concerns call — always separate)
    concerns: List[ConcernRecord] = []

    # Analysis lens alignment — observations, NOT scores or levels
    lens_observations: Optional[Dict[str, str]] = None

    # Metadata from non-LLM pass (carried forward for synthesis)
    word_count: int = 0
    cluster_id: Optional[int] = None
    vader_sentiment: float = 0.0
    keyword_hits: Dict[str, int] = {}

    # Preprocessing metadata
    preprocessing: Optional[PreprocessingMetadata] = None

    # Draft student feedback (Phase 2+)
    draft_feedback: Optional[str] = None


# ---------------------------------------------------------------------------
# Quick Analysis Result (non-LLM pass output)
# ---------------------------------------------------------------------------

class TermFrequency(BaseModel):
    term: str
    count: int


class TermScore(BaseModel):
    term: str
    score: float


class SubmissionStats(BaseModel):
    total_submissions: int = 0
    total_enrollment: int = 0  # 0 = unknown
    word_count_mean: float = 0.0
    word_count_median: float = 0.0
    word_count_min: int = 0
    word_count_max: int = 0
    word_counts: List[int] = []
    format_breakdown: Dict[str, int] = {}  # format → count
    timing: Dict[str, int] = {}  # on_time, late, very_late, missing


class KeywordHit(BaseModel):
    pattern_name: str
    count: int
    student_ids: List[str] = []
    examples: List[str] = []  # brief excerpts of matching text


class EmbeddingCluster(BaseModel):
    cluster_id: int
    size: int
    student_ids: List[str] = []
    student_names: List[str] = []
    top_terms: List[str] = []
    centroid_text: str = ""  # representative snippet


class ConcernSignal(BaseModel):
    """Non-LLM concern pre-screening from VADER+keyword signal matrix."""
    student_id: str
    student_name: str
    signal_type: str  # matrix cell label (e.g. "POSSIBLE CONCERN")
    keyword_category: str  # which keyword category matched
    vader_polarity: str  # positive, negative, neutral
    matched_text: str  # the text that matched
    interpretation: str  # from the signal matrix


class SharedReference(BaseModel):
    reference: str
    student_ids: List[str] = []
    count: int = 0


class ContradictionSignal(BaseModel):
    """Detected when students have opposing sentiment about the same reference."""
    reference: str
    positive_students: List[str] = []
    negative_students: List[str] = []
    description: str = ""


class PerSubmissionSummary(BaseModel):
    """Summary data for one submission in the quick analysis."""
    student_id: str
    student_name: str
    word_count: int = 0
    submission_type: str = ""
    vader_compound: float = 0.0
    keyword_hits: Dict[str, int] = {}
    cluster_id: Optional[int] = None
    was_translated: bool = False
    was_transcribed: bool = False
    # Gibberish gate result
    is_gibberish: bool = False
    gibberish_reason: str = ""
    gibberish_detail: str = ""


class PairwiseSimilarityStats(BaseModel):
    """Class-level pairwise cosine similarity statistics.

    Surfaces ONLY aggregate patterns — never individual pair identities.
    High similarity can indicate community, collaboration, or shared cultural
    knowledge, not only copying.  The first interpretive question is always:
    "Is the assignment designed to produce diverse responses?"
    """
    mean_similarity: float = 0.0
    max_similarity: float = 0.0
    pairs_above_085: int = 0   # high-similarity pairs (threshold 0.85)
    pairs_above_070: int = 0   # moderate-similarity pairs (threshold 0.70)
    total_pairs: int = 0
    observation: str = ""      # human-readable class-level note for the teacher


class QuickAnalysisResult(BaseModel):
    """Complete output of the non-LLM analysis pass.

    Available in seconds, no LLM required. This alone is a useful tool.
    """
    assignment_id: str
    assignment_name: str = ""
    course_id: str = ""
    course_name: str = ""
    analyzed_at: str = ""

    # Submission statistics
    stats: SubmissionStats = Field(default_factory=SubmissionStats)

    # Word frequency (stopword-filtered, top N)
    top_terms: List[TermFrequency] = []

    # TF-IDF distinctive terms
    tfidf_terms: List[TermScore] = []

    # Named entities (spaCy)
    named_entities: Dict[str, List[str]] = {}  # entity_type → [entities]

    # Keyword pattern hits
    keyword_hits: Dict[str, KeywordHit] = {}

    # VADER sentiment per submission
    sentiments: Dict[str, Dict[str, float]] = {}  # student_id → {pos,neg,neu,compound}
    sentiment_distribution: Dict[str, int] = {}  # register → count

    # Embedding clusters
    clusters: List[EmbeddingCluster] = []
    embedding_outlier_ids: List[str] = []

    # Pairwise cosine similarity (class-level aggregate — no individual flags)
    pairwise_similarity: Optional[PairwiseSimilarityStats] = None

    # Cross-submission patterns
    shared_references: List[SharedReference] = []
    contradictions: List[ContradictionSignal] = []

    # Concern signals from VADER+keyword matrix
    concern_signals: List[ConcernSignal] = []

    # Per-submission summaries
    per_submission: Dict[str, PerSubmissionSummary] = {}

    # Citation analysis (only populated when citations are found)
    citation_report: Optional[Dict] = None  # CitationReport serialized

    # Gibberish gate results (student_ids flagged as non-analyzable)
    gibberish_ids: List[str] = []

    # Analysis notes (what components ran, what was skipped)
    analysis_notes: List[str] = []


# ---------------------------------------------------------------------------
# Theme generation (Phase 2+)
# ---------------------------------------------------------------------------

class Theme(BaseModel):
    name: str
    description: str = ""
    frequency: int = 0
    student_ids: List[str] = []
    supporting_quotes: List[QuoteRecord] = []
    confidence: float = 0.0
    sub_themes: Optional[List[str]] = None


class Contradiction(BaseModel):
    """Opposing views explicitly preserved — tensions are productive, not problems."""
    description: str
    side_a: str
    side_a_students: List[str] = []
    side_b: str
    side_b_students: List[str] = []
    pedagogical_significance: str = ""


class ThemeSet(BaseModel):
    themes: List[Theme] = []
    contradictions: List[Contradiction] = []


# ---------------------------------------------------------------------------
# Outlier surfacing (Phase 2+)
# ---------------------------------------------------------------------------

class OutlierRecord(BaseModel):
    student_id: str
    student_name: str
    why_notable: str
    relationship_to_themes: str = ""
    notable_quote: Optional[QuoteRecord] = None
    teacher_recommendation: str = ""


class OutlierReport(BaseModel):
    outliers: List[OutlierRecord] = []


# ---------------------------------------------------------------------------
# Synthesis (Phase 2+)
# ---------------------------------------------------------------------------

class SynthesisReport(BaseModel):
    """Final analytical report with named sections."""
    sections: Dict[str, str] = {}  # section_name → markdown text
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Draft feedback (Phase 2+)
# ---------------------------------------------------------------------------

class DraftFeedback(BaseModel):
    student_id: str
    student_name: str
    feedback_text: str = ""
    strengths_noted: List[str] = []
    areas_for_growth: List[str] = []
    question_for_student: str = ""
    confidence: float = 0.0


# ---------------------------------------------------------------------------
# Teacher analysis profile
# ---------------------------------------------------------------------------

class TeacherAnalysisProfile(BaseModel):
    """Persisted preferences that shape future pipeline runs.
    Starts empty. Grows with each teacher interaction."""

    theme_renames: Dict[str, str] = {}
    theme_splits: List[Dict] = []
    concern_sensitivity: Dict[str, float] = {}
    interest_areas: List[str] = []
    subject_area: str = "general"
    feedback_style: str = "warm"
    feedback_length: str = "moderate"
    custom_patterns: Dict[str, str] = {}
    edit_history: List[Dict] = []


# ---------------------------------------------------------------------------
# Pipeline confidence
# ---------------------------------------------------------------------------

class PipelineConfidence(BaseModel):
    overall: float = 0.0
    data_quality: float = 0.0
    coding_reliability: float = 0.0
    theme_coherence: float = 0.0
    synthesis_coverage: float = 0.0
    concerns: List[str] = []


# ---------------------------------------------------------------------------
# Cross-validation (Phase 5)
# ---------------------------------------------------------------------------

class ValidationFlag(BaseModel):
    """One disagreement (or agreement) between LLM and non-LLM analysis."""
    domain: str  # "concerns" | "themes" | "outliers"
    student_id: str = ""
    student_name: str = ""
    llm_says: str = ""
    matrix_says: str = ""
    agreement: str = "agree"  # "agree" | "llm_only" | "matrix_only"
    confidence_note: str = ""


# ---------------------------------------------------------------------------
# Cross-run trajectory (Phase 5)
# ---------------------------------------------------------------------------

class ThemeEvolution(BaseModel):
    theme_name: str
    weeks_present: List[int] = []
    first_appeared: int = 0
    status: str = "one-time"  # "recurring" | "new" | "fading" | "one-time"


class WeekMetric(BaseModel):
    week: int = 0
    label: str = ""  # human-readable week label (e.g. assignment name)
    avg_words: float = 0.0
    submission_rate: float = 0.0
    concern_count: int = 0
    concern_types: List[str] = []
    late_count: int = 0
    short_count: int = 0
    silence_count: int = 0


class ReadingEngagement(BaseModel):
    reading: str
    times_referenced: int = 0
    avg_word_count: float = 0.0  # avg words of submissions that reference this


class StudentArc(BaseModel):
    student_id: str
    student_name: str
    weekly_word_counts: List[Optional[int]] = []
    weekly_submission_status: List[str] = []  # "on_time" | "late" | "missing"
    weekly_concern_flags: List[int] = []  # count per week
    trend: str = "steady"  # "steady" | "improving" | "declining" | "irregular"


class CourseTrajectory(BaseModel):
    course_id: str
    course_name: str = ""
    run_count: int = 0
    date_range: str = ""  # e.g. "Jan 15 – Mar 10, 2026"
    theme_evolution: List[ThemeEvolution] = []
    engagement_trend: List[WeekMetric] = []
    concern_trend: List[WeekMetric] = []
    exhaustion_trend: List[WeekMetric] = []
    top_readings: List[ReadingEngagement] = []
    student_trajectories: List[StudentArc] = []
