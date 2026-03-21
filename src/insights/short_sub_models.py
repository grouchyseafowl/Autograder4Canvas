"""
Pydantic models for the Short Submission Review pipeline.

ShortSubReview is the structured verdict returned by review_short_submission().
The LLM can only CREDIT or escalate to TEACHER_REVIEW — it can never condemn.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class ShortSubReview(BaseModel):
    """LLM assessment of whether a below-threshold submission demonstrates engagement."""

    verdict: Literal["CREDIT", "TEACHER_REVIEW"]
    brevity_category: Literal[
        "concise_complete",   # says what it needs to in fewer words
        "dense_engagement",   # high substance-to-word ratio
        "format_appropriate", # bullets/outline/notes — brevity IS the format
        "multilingual",       # engagement crosses languages
        "partial_attempt",    # started but didn't finish
        "wrong_submission",   # wrong file/content
        "placeholder",        # "will finish later"
        "unclear",            # can't determine
    ]
    rationale: str = Field(description="1-2 sentences for the teacher")
    engagement_evidence: List[str] = Field(
        default_factory=list,
        description="Verbatim snippets from the submission showing engagement",
    )
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    teacher_note: Optional[str] = Field(
        default=None,
        description=(
            "Optional care-framed note, e.g. 'Consider checking in — "
            "brevity may reflect circumstances beyond the assignment'"
        ),
    )
    bias_warning: Optional[str] = Field(
        default=None,
        description="Set by post-processing if LLM output shows register bias. Never set by LLM.",
    )
    # Discussion-specific: stored for review dialog thread context view
    thread_context: Optional[dict] = Field(
        default=None,
        description="For discussions: {parent_post, sibling_replies, reviewed_reply_index}",
    )
