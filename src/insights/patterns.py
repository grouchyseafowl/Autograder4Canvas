"""
Keyword patterns and VADER+keyword signal matrix for the Insights Engine.

INSIGHT_PATTERNS: regex dict for educational content analysis.
signal_matrix_classify(): crosses VADER sentiment with keyword categories
to produce concern pre-screening signals.

The signal matrix runs in the non-LLM pass, BEFORE any LLM concern call.
It pre-identifies likely concern candidates and explicitly codes
"VADER negative + critical keywords" as NOT a concern (counteracting
model bias toward flagging passionate critique).
"""

import re
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Keyword pattern dictionary
# ---------------------------------------------------------------------------

INSIGHT_PATTERNS: Dict[str, re.Pattern] = {
    # Content engagement
    "conceptual_connection": re.compile(
        r"\b(connect|relate|remind|similar|parallel|link)\w*\b", re.IGNORECASE
    ),
    "critical_analysis": re.compile(
        r"\b(argue|critique|challenge|question|problematize|tension)\w*\b", re.IGNORECASE
    ),
    "personal_reflection": re.compile(
        r"\b(personally|my experience|in my life|growing up|my family)\b", re.IGNORECASE
    ),
    "current_events": re.compile(
        r"\b(today|current|recent|news|happening now|right now)\b", re.IGNORECASE
    ),

    # Confusion signals
    "confusion_markers": re.compile(
        r"\b(confus\w*|unclear|don't understand|lost|not sure what)\b", re.IGNORECASE
    ),
    "structural_confusion": re.compile(
        r"\b(where do I|how do I submit|canvas|format|instructions)\b", re.IGNORECASE
    ),

    # Concern signals
    "essentializing": re.compile(
        r"\b(all \w+ people|they always|those people|that culture)\b", re.IGNORECASE
    ),
    "colorblind_ideology": re.compile(
        r"\b(don't see (race|color)|not about race|reverse racism)\b", re.IGNORECASE
    ),
    "tone_policing": re.compile(
        r"\b(too (angry|aggressive|emotional)|calm down|be civil)\b", re.IGNORECASE
    ),
    "distress_markers": re.compile(
        r"\b(scared|afraid|unsafe|trigger\w*|crisis|can't cope)\b", re.IGNORECASE
    ),

    # Engagement quality
    "evidence_use": re.compile(
        r"\b(according to|the author|the reading|the text states)\w*\b", re.IGNORECASE
    ),
    "peer_engagement": re.compile(
        r"\b(I agree with|building on|like \w+ said|responding to)\b", re.IGNORECASE
    ),
}

# Keywords that indicate structural critique (NOT concerns)
CRITICAL_KEYWORDS = re.compile(
    r"\b(structural racism|white supremacy|colonialism|resistance|oppression|"
    r"systemic|institutional racism|decoloni\w+|indigenous sovereignty|"
    r"injustice|inequality|discrimination|marginali\w+|liberation)\b",
    re.IGNORECASE,
)

# Categories for signal matrix columns
KEYWORD_CATEGORIES = {
    "critical": ["critical_analysis", "evidence_use"],
    "essentializing": ["essentializing", "colorblind_ideology", "tone_policing"],
    "distress": ["distress_markers"],
    "disengagement": [],  # detected by low word count + no keyword hits
}


# ---------------------------------------------------------------------------
# VADER + Keyword Signal Matrix
# ---------------------------------------------------------------------------
# Crosses VADER sentiment (positive/negative/neutral) with keyword categories
# to produce concern pre-screening signals.

_SIGNAL_MATRIX: Dict[Tuple[str, str], Tuple[str, str]] = {
    # (vader_polarity, keyword_category) → (signal_type, interpretation)

    # Critical keywords present
    ("positive", "critical"): (
        "APPROPRIATE",
        "Sophisticated analysis — student engaging well",
    ),
    ("negative", "critical"): (
        "APPROPRIATE",
        "Political urgency about injustice — NOT a concern",
    ),
    ("neutral", "critical"): (
        "APPROPRIATE",
        "Measured critical analysis",
    ),

    # Essentializing keywords present
    ("positive", "essentializing"): (
        "POSSIBLE CONCERN",
        "'Sounds nice' but essentializing language detected",
    ),
    ("negative", "essentializing"): (
        "CONCERN",
        "Hostile + essentializing = high priority for review",
    ),
    ("neutral", "essentializing"): (
        "CONCERN",
        "Normalized prejudice — potentially insidious, flag for review",
    ),

    # Distress keywords present
    ("positive", "distress"): (
        "VERIFY",
        "Unlikely combination — verify context",
    ),
    ("negative", "distress"): (
        "CHECK IN",
        "Possible student distress — teacher should check in",
    ),
    ("neutral", "distress"): (
        "CHECK IN",
        "Understated distress — check carefully",
    ),

    # Disengagement signals
    ("positive", "disengagement"): (
        "SURFACE COMPLIANCE",
        "Surface compliance — check engagement depth",
    ),
    ("negative", "disengagement"): (
        "LOW ENGAGEMENT",
        "Low engagement — may need outreach",
    ),
    ("neutral", "disengagement"): (
        "PERFUNCTORY",
        "Perfunctory response",
    ),
}


def classify_vader_polarity(compound: float) -> str:
    """Map VADER compound score to positive/negative/neutral."""
    if compound >= 0.05:
        return "positive"
    elif compound <= -0.05:
        return "negative"
    return "neutral"


def match_keyword_category(text: str) -> List[str]:
    """Return which keyword categories have matches in the text."""
    matched = []
    for cat, pattern_names in KEYWORD_CATEGORIES.items():
        if cat == "disengagement":
            continue  # handled separately by word count heuristic
        for pname in pattern_names:
            pat = INSIGHT_PATTERNS.get(pname)
            if pat and pat.search(text):
                matched.append(cat)
                break
    # Also check dedicated concern patterns
    for pname in ("essentializing", "colorblind_ideology", "tone_policing"):
        pat = INSIGHT_PATTERNS.get(pname)
        if pat and pat.search(text) and "essentializing" not in matched:
            matched.append("essentializing")
            break
    for pname in ("distress_markers",):
        pat = INSIGHT_PATTERNS.get(pname)
        if pat and pat.search(text) and "distress" not in matched:
            matched.append("distress")
            break
    return matched


def signal_matrix_classify(
    text: str,
    vader_compound: float,
    word_count: int = 0,
    median_word_count: float = 0.0,
) -> List[Tuple[str, str, str, str]]:
    """Run the VADER+keyword signal matrix on one submission.

    Returns list of (signal_type, keyword_category, vader_polarity, interpretation)
    tuples — one per matched category.

    Also detects disengagement via low word count + no content keyword hits.
    """
    results = []
    polarity = classify_vader_polarity(vader_compound)
    categories = match_keyword_category(text)

    # Check for disengagement: low word count and no content engagement hits
    if median_word_count > 0 and word_count < median_word_count * 0.4:
        has_engagement = any(
            INSIGHT_PATTERNS[p].search(text)
            for p in ("conceptual_connection", "critical_analysis",
                       "personal_reflection", "evidence_use", "peer_engagement")
            if p in INSIGHT_PATTERNS
        )
        if not has_engagement:
            categories.append("disengagement")

    for cat in categories:
        key = (polarity, cat)
        if key in _SIGNAL_MATRIX:
            signal_type, interpretation = _SIGNAL_MATRIX[key]
            results.append((signal_type, cat, polarity, interpretation))

    return results


def has_critical_keywords(text: str) -> bool:
    """Check if text contains structural critique keywords (NOT concerns)."""
    return bool(CRITICAL_KEYWORDS.search(text))


def match_all_patterns(text: str) -> Dict[str, int]:
    """Match all INSIGHT_PATTERNS against text. Returns pattern_name → hit count."""
    hits = {}
    for name, pat in INSIGHT_PATTERNS.items():
        matches = pat.findall(text)
        if matches:
            hits[name] = len(matches)
    return hits
