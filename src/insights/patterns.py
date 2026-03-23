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
from typing import Dict, List, NamedTuple, Optional, Tuple

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

    # Direct address — student testing whether teacher reads submissions.
    # This is a trust/relationship signal.  The system surfaces it so the
    # teacher can respond ("yes, I read your work"), building trust.
    "teacher_test": re.compile(
        r"(if you(?:'re| are) (?:actually )?reading this|"
        r"bet (?:you |nobody |no one )(?:(?:even |actually )?read|notice)|"
        r"does anyone (?:actually |even )?read th(?:is|ese)|"
        r"is anyone (?:going to |gonna )?read this|"
        r"wonder if (?:anyone|you|my teacher) will (?:read|notice|see) this|"
        r"checking if (?:anyone|you|my teacher) (?:read|notice)|"
        r"if you (?:see|notice|read) this[\s,]|"
        r"(?:extra credit|smiley|emoji|star) if you (?:read|see|made it) this|"
        r"this is (?:a test|to see if)|"
        r"hello,? teacher|"
        r"(?:is this thing on|anyone home)\??|"
        # --- expanded patterns ---
        r"(?:i )?doubt (?:anyone|you|nobody) (?:even )?read(?:s)? th|"
        r"nobody (?:ever )?reads? th(?:is|ese)|"
        r"do you (?:actually|even) (?:grade|read) th(?:is|ese)|"
        r"does (?:the|my) teacher (?:even )?read|"
        r"are these (?:even )?(?:graded|read)|"
        r"i could (?:write|put|say) anything (?:here|in here)|"
        r"testing,?\s*(?:1,?\s*2,?\s*3|testing)|"
        r"leaving this (?:here )?to see if|"
        r"proof (?:that )?you (?:read|saw) this|"
        r"say \w+ in class if you (?:read|see) this|"
        r"mention \w+ if you(?:'re| are) reading|"
        r"raise your hand if you (?:read|see|made it) this)",
        re.IGNORECASE,
        # NOTE: Greetings like "hey teacher" / "hi Ms. Johnson" are intentionally
        # NOT included — those are normal discussion post openings, not reader tests.
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
        r"\b(scared|afraid|unsafe|crisis|can't cope|"
        r"can't do this anymore|don't see the point|want to disappear|"
        r"nobody would care|give up on everything)\b", re.IGNORECASE
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
    "direct_address": ["teacher_test"],
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

    # Direct address — student testing whether teacher reads their work
    # This is a trust/relationship signal, not a concern. Always surface it.
    ("positive", "direct_address"): (
        "TEACHER NOTE",
        "Student is directly addressing the reader — wants to know their work is being read",
    ),
    ("negative", "direct_address"): (
        "TEACHER NOTE",
        "Student is testing whether teacher reads submissions — may reflect frustration or distrust",
    ),
    ("neutral", "direct_address"): (
        "TEACHER NOTE",
        "Student embedded a message to check if teacher reads submissions — respond to build trust",
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


# ---------------------------------------------------------------------------
# Sentiment reliability / suppression layer
# ---------------------------------------------------------------------------
# AAVE (African American Vernacular English) lexical + syntactic markers.
# Presence suggests sentiment model scores are unreliable — both VADER and
# GoEmotions were trained predominantly on standard written English and
# systematically misread AAVE affect (Blodgett et al., EMNLP 2017).
# These markers are linguistic features of a dialect, NOT errors.
_AAVE_MARKERS: re.Pattern = re.compile(
    r"\b("
    r"finna|tryna|ima|imma|"                           # modal/aspect contractions
    r"ain'?t|"                                          # AAVE general negation
    r"deadass|lowkey|highkey|"                          # truth/intensity markers
    r"fr\s+fr|no\s+cap|on\s+god|"                      # truth verification phrases
    r"fasho|"                                           # for sure
    r"bruh|"                                            # address term
    r"y'?all|"                                          # 2nd-person plural — very reliable AAVE/Southern marker
    r"they\s+was|we\s+was|you\s+was|"                  # leveled 'was' agreement
    r"(?:he|she|they|we|y'?all)\s+be\b|"               # habitual be — syntactic AAVE marker
    r"he\s+don'?t|she\s+don'?t|they\s+don'?t|"        # 3rd-person singular don't
    r"done\s+told|done\s+said|done\s+went|"            # AAVE completive done (original)
    r"done\s+(?:knew|seen|ran|got|came|lost|left|finished)"  # completive done (expanded irregular forms)
    r")",
    re.IGNORECASE,
)

_AAVE_SUPPRESS_THRESHOLD = 2   # ≥ 2 distinct AAVE markers → suppressed
_AAVE_CAUTION_THRESHOLD = 1    # 1 AAVE marker → low (caveat)
_SHORT_SUBMISSION_WORDS = 80   # < 80 words → suppressed (sample too small)
_LOW_VOCAB_OVERLAP = 0.10      # assignment_connection vocab overlap below this → low


class SentimentReliabilityResult(NamedTuple):
    """Output of assess_sentiment_reliability().

    Tiers
    -----
    high      — score is plausible; pass through to prompt unchanged.
    low       — score may be unreliable; include with explicit caveat.
    suppressed — score is not shown; LLM instructed to read register
                 directly from text.
    """
    tier: str               # "high" | "low" | "suppressed"
    caveat: str             # explanation for low/suppressed (empty for high)
    triggers: List[str]     # which conditions fired (diagnostic, not shown to LLM)


def assess_sentiment_reliability(
    text: str,
    word_count: int,
    *,
    was_translated: bool = False,
    was_transcribed: bool = False,
    assignment_connection_overlap: Optional[float] = None,
    compound_score: float = 0.0,
) -> SentimentReliabilityResult:
    """Assess whether the emotional register signal is reliable for this submission.

    Suppression is non-negotiable for ESL and AAVE writers.  A biased baseline
    score shown to the LLM without caveat constitutes a harm — it anchors
    the model toward a false reading.

    Parameters
    ----------
    text : str
        Submission text (used for AAVE marker detection).
    word_count : int
        Submission word count.
    was_translated : bool
        True if the submission was translated from another language (ESL proxy).
    was_transcribed : bool
        True if the submission was transcribed from audio.  Sentiment models
        trained on written text misread spoken register (disfluencies, hedges,
        fragmentation). This is a data-quality concern, not demographic bias —
        triggers soft caution rather than hard suppression.
    assignment_connection_overlap : float or None
        Vocabulary overlap score (0.0–1.0) from AssignmentConnectionScore.
        None if assignment connection was not computed.
    compound_score : float
        Raw compound score from the sentiment model (-1.0 to 1.0).

    Returns
    -------
    SentimentReliabilityResult with tier, caveat, and trigger list.
    """
    triggers: List[str] = []

    # --- Hard suppression checks (any one → tier: suppressed) ---

    # Too short: sample size insufficient for any sentiment signal
    if word_count < _SHORT_SUBMISSION_WORDS:
        triggers.append(f"short_submission({word_count}_words)")

    # ESL: translated submission + non-trivial compound score
    # Sentiment models trained on standard English systematically
    # penalise translated writing patterns as more negative.
    if was_translated and abs(compound_score) > 0.1:
        triggers.append("esl_translated_with_nontrivial_score")

    # AAVE: count distinct marker matches
    aave_matches = _AAVE_MARKERS.findall(text)
    distinct_aave = len(set(m.strip().lower() for m in aave_matches))
    if distinct_aave >= _AAVE_SUPPRESS_THRESHOLD:
        triggers.append(f"aave_markers({distinct_aave})")

    if triggers:
        # Any hard-suppression trigger fires → suppressed
        suppression_reason = " / ".join(triggers)
        return SentimentReliabilityResult(
            tier="suppressed",
            caveat=(
                f"Emotional register score withheld ({suppression_reason}). "
                "Bias risk: score unreliable for this submission. "
                "Read affective tone directly from the student's text."
            ),
            triggers=triggers,
        )

    # --- Soft caution checks (any one → tier: low) ---
    soft_triggers: List[str] = []

    # Single AAVE marker (caution, not full suppression)
    if distinct_aave == _AAVE_CAUTION_THRESHOLD:
        soft_triggers.append(f"aave_marker({distinct_aave})")

    # Low vocabulary overlap: student may be engaging through personal/cultural
    # frame rather than assignment vocabulary.  Score may not reflect topic engagement.
    if (
        assignment_connection_overlap is not None
        and assignment_connection_overlap < _LOW_VOCAB_OVERLAP
    ):
        soft_triggers.append(
            f"low_assignment_connection({assignment_connection_overlap:.2f})"
        )

    # Oral transcription: sentiment models trained on written text misread spoken
    # register — disfluencies, hedging, non-linear structure all skew the score.
    # This is a data-quality concern (not demographic bias) → soft caution only.
    if was_transcribed:
        soft_triggers.append("oral_transcription")

    if soft_triggers:
        caveat_reason = " / ".join(soft_triggers)
        return SentimentReliabilityResult(
            tier="low",
            caveat=(
                f"[CAUTION — {caveat_reason}] "
                "Emotional register score may not reflect this student's actual affect. "
                "Treat as a weak signal only."
            ),
            triggers=soft_triggers,
        )

    return SentimentReliabilityResult(tier="high", caveat="", triggers=[])
