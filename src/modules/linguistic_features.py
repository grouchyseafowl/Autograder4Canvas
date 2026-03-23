"""
Linguistic Feature Detection — Shared Layer for AIC + Insights.

Detects individual linguistic features from student writing.  Each feature
carries its own bias profile, asset label, and pipeline adjustments.
Features — not population categories — drive all downstream behavior.

A student's unique combination of features determines:
  - Sentiment reliability tier (suppress / caveat / pass-through)
  - AIC weight adjustments (per-marker multipliers)
  - LLM prompt context (asset-framed guidance for the coding model)
  - Teacher-facing asset labels (green chips, never deficit framing)

Design principles:
  - Features are linguistic OBSERVATIONS, not demographic classifications
  - Every detected feature has an asset framing (community cultural wealth)
  - Detection must not be worse than non-detection (if we detect and do
    nothing useful, that's surveillance; detect + surface assets = support)
  - Pure functions, no LLM calls, no network, no side effects

Citation:
  - AAVE features: Blodgett et al. (EMNLP 2017), Rickford (1999)
  - ESL L1 transfer: Odlin (1989), Swan & Smith (2001)
  - Community cultural wealth: Yosso (2005)
  - GoEmotions: Demszky et al. (ACL 2020)
"""

import logging
import re
import statistics
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel
except ImportError:
    # Fallback for environments without pydantic (testing, standalone use)
    from dataclasses import dataclass, field as dc_field

    class _BaseModelMeta(type):
        """Minimal BaseModel shim that makes type annotations work like pydantic."""
        def __new__(mcs, name, bases, namespace):
            annotations = namespace.get("__annotations__", {})
            defaults = {}
            for attr, _type in annotations.items():
                if attr in namespace:
                    defaults[attr] = namespace[attr]
            cls = super().__new__(mcs, name, bases, namespace)
            orig_init = cls.__init__ if hasattr(cls, "__init__") else None

            def __init__(self, **kwargs):
                for attr in annotations:
                    val = kwargs.get(attr, defaults.get(attr))
                    if val is None and attr not in kwargs and attr not in defaults:
                        raise TypeError(f"Missing required argument: {attr}")
                    setattr(self, attr, val)
            cls.__init__ = __init__
            return cls

    class BaseModel(metaclass=_BaseModelMeta):
        pass

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════════

class LinguisticFeature(BaseModel):
    """One detected linguistic feature."""
    name: str                    # e.g., "zero_copula"
    category: str                # e.g., "syntactic_variation"
    evidence: List[str] = []     # matched text excerpts (max 3)
    asset_label: str = ""        # teacher-facing positive framing
    sentiment_effect: str = "none"  # "suppress" | "caveat" | "none"
    aic_weight_adjustments: Dict[str, float] = {}  # marker → multiplier


class LinguisticFeatureResult(BaseModel):
    """Full detection result for one submission."""
    features: List[LinguisticFeature] = []

    # Aggregated outputs — derived from features, ready for consumers
    sentiment_tier: str = "high"         # high | low | suppressed
    sentiment_triggers: List[str] = []
    sentiment_caveat: str = ""
    asset_labels: List[str] = []         # deduped teacher-facing labels
    llm_context_note: str = ""           # ≤3 sentences for coding prompt
    aic_adjustments: Dict[str, float] = {}  # merged weight adjustments


# ═══════════════════════════════════════════════════════════════════════════
# Category: Syntactic Variation (AAVE)
# ═══════════════════════════════════════════════════════════════════════════
# These markers are linguistic features of a complete grammatical system,
# NOT errors.  Both VADER and GoEmotions systematically misread AAVE
# affect (Blodgett et al., EMNLP 2017).

# --- Lexical markers (incorporated from patterns.py _AAVE_MARKERS) ---
_AAVE_LEXICAL = re.compile(
    r"\b("
    r"finna|tryna|ima|imma|"                           # modal/aspect contractions
    r"ain'?t|"                                          # general negation
    r"deadass|lowkey|highkey|"                          # truth/intensity markers
    r"fr\s+fr|no\s+cap|on\s+god|"                      # truth verification phrases
    r"fasho|"                                           # for sure
    r"bruh|"                                            # address term
    r"y'?all|"                                          # 2nd-person plural
    r"they\s+was|we\s+was|you\s+was|"                  # leveled 'was' agreement
    r"(?:he|she|they|we|y'?all)\s+be\b|"               # habitual be
    r"he\s+don'?t|she\s+don'?t|they\s+don'?t|"        # 3rd-person singular don't
    r"done\s+told|done\s+said|done\s+went|"            # completive done (original)
    r"done\s+(?:knew|seen|ran|got|came|lost|left|finished)"  # completive done (expanded)
    r")",
    re.IGNORECASE,
)

# --- Syntactic markers (new — deeper AAVE grammar) ---

# Zero copula: pronoun + predicate adjective with no intervening copula
# FALSE POSITIVE GUARD: negative lookahead for following preposition
_ZERO_COPULA = re.compile(
    r"(?:^|[.!?]\s+|,\s*)"
    r"(she|he|they|we|it|that)\s+"
    r"(tired|ready|cool|good|bad|hungry|sick|cold|hot|mad|glad|sad|"
    r"real|right|wrong|crazy|wild|done|fine|grown)"
    r"(?!\s+(?:of|to|for|from|about|with|at|in|on))"
    r"(?:\s*[.!?,]|\s+(?:and|but|so|now|too|tho|though)|\s*$)",
    re.IGNORECASE | re.MULTILINE,
)

# Negative concord: double negation
_NEGATIVE_CONCORD = re.compile(
    r"\b(didn'?t|ain'?t|can'?t|don'?t|won'?t|wasn'?t|couldn'?t)\s+"
    r"(nobody|nothing|no\s+\w+|nowhere|never)\b"
    r"|\b(nobody|nothing)\s+(didn'?t|ain'?t|can'?t|don'?t|won'?t)\b",
    re.IGNORECASE,
)

# Remote past BIN: "been" + past participle without auxiliary
# FALSE POSITIVE GUARD: negative lookbehind for "have/has/had"
_REMOTE_PAST_BIN = re.compile(
    r"(?<!\bhave )(?<!\bhas )(?<!\bhad )"
    r"\bbeen\s+(knew|seen|had|gone|done|lost|told|said|ran|got|"
    r"left|came|started|working|running|saying|doing|trying|going|living)\b",
    re.IGNORECASE,
)

# Existential "it's": "it's a lot of X" instead of "there are many X"
_EXISTENTIAL_ITS = re.compile(r"\bit'?s\s+a\s+lot\s+of\b", re.IGNORECASE)

_AAVE_AIC_ADJUSTMENTS = {"grammatical_perfection": 0.5}
_AAVE_ASSET = "AAVE linguistic features — authentic voice"

# --- spaCy POS cascade helpers (optional, for better zero copula detection) ---

_SPACY_CHECKED = False
_SPACY_OK = False
_SPACY_NLP = None  # cached spaCy model


def _spacy_available() -> bool:
    """Check whether spaCy + en_core_web_sm are importable. Caches result."""
    global _SPACY_CHECKED, _SPACY_OK
    if _SPACY_CHECKED:
        return _SPACY_OK
    _SPACY_CHECKED = True
    try:
        import spacy  # noqa: F811
        spacy.load("en_core_web_sm", exclude=["parser", "lemmatizer"])
        _SPACY_OK = True
    except Exception:
        _SPACY_OK = False
    return _SPACY_OK


def _get_spacy_nlp():
    """Return a cached spaCy nlp model (parser+lemmatizer excluded for speed)."""
    global _SPACY_NLP
    if _SPACY_NLP is None:
        import spacy
        _SPACY_NLP = spacy.load("en_core_web_sm", exclude=["parser", "lemmatizer"])
    return _SPACY_NLP


def _spacy_zero_copula(text: str) -> List[LinguisticFeature]:
    """Detect zero copula via spaCy POS tagging.

    Looks for PRON token followed within a 3-token window by ADJ/NOUN
    where no AUX or copula verb (be/is/are/was/were) intervenes.
    """
    try:
        nlp = _get_spacy_nlp()
        doc = nlp(text)
    except Exception:
        return []

    _COPULA_LEMMAS = {"be", "is", "are", "was", "were"}
    evidence: List[str] = []

    tokens = list(doc)
    for i, tok in enumerate(tokens):
        if tok.pos_ != "PRON":
            continue
        # Look ahead up to 3 tokens
        window_end = min(i + 4, len(tokens))
        found_copula = False
        for j in range(i + 1, window_end):
            t = tokens[j]
            if t.pos_ == "AUX" or (t.pos_ == "VERB" and t.text.lower() in _COPULA_LEMMAS):
                found_copula = True
                break
            if t.pos_ in ("ADJ", "NOUN"):
                if not found_copula:
                    evidence.append(f"{tok.text} {t.text}")
                break

    if not evidence:
        return []

    return [LinguisticFeature(
        name="zero_copula_pos",
        category="syntactic_variation",
        evidence=evidence[:3],
        asset_label=_AAVE_ASSET,
        sentiment_effect="caveat",
        aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
    )]


def _detect_syntactic_variation(text: str) -> List[LinguisticFeature]:
    """Detect AAVE syntactic and lexical features."""
    features: List[LinguisticFeature] = []

    # Lexical markers — count distinct matches
    lexical_matches = _AAVE_LEXICAL.findall(text)
    distinct_lexical = set(m.strip().lower() for m in lexical_matches)
    if distinct_lexical:
        features.append(LinguisticFeature(
            name="aave_lexical",
            category="syntactic_variation",
            evidence=sorted(distinct_lexical)[:3],
            asset_label=_AAVE_ASSET,
            sentiment_effect="suppress" if len(distinct_lexical) >= 2 else "caveat",
            aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
        ))

    # Zero copula
    zc_matches = _ZERO_COPULA.findall(text)
    if zc_matches:
        features.append(LinguisticFeature(
            name="zero_copula",
            category="syntactic_variation",
            evidence=[f"{m[0]} {m[1]}" for m in zc_matches[:3]],
            asset_label=_AAVE_ASSET,
            sentiment_effect="caveat",
            aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
        ))

    # Negative concord
    nc_matches = _NEGATIVE_CONCORD.findall(text)
    if nc_matches:
        features.append(LinguisticFeature(
            name="negative_concord",
            category="syntactic_variation",
            evidence=[" ".join(m).strip() for m in nc_matches[:3]],
            asset_label=_AAVE_ASSET,
            sentiment_effect="caveat",
            aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
        ))

    # Remote past BIN
    bin_matches = _REMOTE_PAST_BIN.findall(text)
    if bin_matches:
        features.append(LinguisticFeature(
            name="remote_past_bin",
            category="syntactic_variation",
            evidence=[f"been {m}" for m in bin_matches[:3]],
            asset_label=_AAVE_ASSET,
            sentiment_effect="caveat",
            aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
        ))

    # Existential "it's"
    if _EXISTENTIAL_ITS.search(text):
        features.append(LinguisticFeature(
            name="existential_its",
            category="syntactic_variation",
            evidence=["it's a lot of"],
            asset_label=_AAVE_ASSET,
            sentiment_effect="caveat",
            aic_weight_adjustments=_AAVE_AIC_ADJUSTMENTS,
        ))

    # --- spaCy POS cascade (optional, runs only when regex found ≥1 feature) ---
    if features and _spacy_available():
        pos_features = _spacy_zero_copula(text)
        # Add any POS-detected features not already found by regex
        existing_names = {f.name for f in features}
        for pf in pos_features:
            if pf.name not in existing_names:
                features.append(pf)

    return features


# ═══════════════════════════════════════════════════════════════════════════
# Category: Multilingual Patterns
# ═══════════════════════════════════════════════════════════════════════════
# Non-standard syntax from L1 transfer is a marker of multilingual
# competence, not confusion.  These patterns are ported from
# context_analyzer.py (ESL detection) and extended.

_ESL_TENSE_MIXING = re.compile(r"\b(is|are|was|were)\s+\w+ing\b.*\byesterday\b", re.I)
_ESL_AGREEMENT = re.compile(r"\bthe\s+\w+s\s+(is|was)\b", re.I)
_ESL_UNCOUNTABLE = re.compile(
    r"\bmany\s+(information|advice|knowledge|homework|research)s?\b", re.I,
)
_ESL_YEAR_FORMAT = re.compile(r"\bin\s+\d{4}\s+year\b", re.I)
_ESL_SINCE_DURATION = re.compile(r"\bsince\s+\d+\s+years?\b", re.I)

# Article errors — common across Mandarin, Russian, Korean, Arabic L1 speakers
_ARTICLE_ERROR = re.compile(
    r"\b(the|a)\s+(homework|information|advice|research|furniture)\b",
    re.IGNORECASE,
)

# Preposition transfer — common L1 transfer errors
_PREPOSITION_TRANSFER = re.compile(
    r"\b(depend\s+of|interested\s+for|consist\s+from|"
    r"married\s+with|arrive\s+to|explain\s+me|"
    r"discuss\s+about|emphasize\s+on|mention\s+about)\b",
    re.IGNORECASE,
)

# Code-mixing: ≥2 consecutive non-ASCII word tokens
_CODE_MIXING = re.compile(r"(?:[^\x00-\x7F]+\s+){2,}[^\x00-\x7F]+")

_MULTILINGUAL_AIC = {
    "grammatical_perfection": 0.7,
    "ai_transitions": 0.6,
    "inflated_vocabulary": 0.6,
}


def _langdetect_code_mixing(text: str) -> List[LinguisticFeature]:
    """Detect code-mixing via langdetect (optional — graceful fallback).

    Splits text into sentences, runs langdetect on each, and emits a
    code_mixing_langdetect feature if >=2 different languages are detected
    across sentences (with at least one non-English).
    """
    try:
        from langdetect import detect
    except ImportError:
        return []

    # Simple sentence split (period/question/exclamation followed by space+capital)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) >= 10]

    if len(sentences) < 2:
        return []

    detected_langs: set = set()
    for sent in sentences:
        try:
            lang = detect(sent)
            detected_langs.add(lang)
        except Exception:
            continue

    # Need >=2 different languages, at least one non-English
    non_english = detected_langs - {"en"}
    if len(detected_langs) >= 2 and non_english:
        return [LinguisticFeature(
            name="code_mixing_langdetect",
            category="multilingual",
            evidence=[f"languages detected: {', '.join(sorted(detected_langs))}"],
            asset_label="Multilingual — code-mixing as communicative resource",
            sentiment_effect="caveat",
            aic_weight_adjustments={"personal_voice": 0.8},
        )]

    return []


def _detect_multilingual(
    text: str, was_translated: bool, compound_score: float,
) -> List[LinguisticFeature]:
    """Detect multilingual / ESL writing patterns."""
    features: List[LinguisticFeature] = []

    # was_translated flag from preprocessing
    if was_translated:
        suppress = abs(compound_score) > 0.1
        features.append(LinguisticFeature(
            name="was_translated",
            category="multilingual",
            evidence=["submission was translated from another language"],
            asset_label="Multilingual — writing across languages",
            sentiment_effect="suppress" if suppress else "none",
            aic_weight_adjustments=_MULTILINGUAL_AIC,
        ))

    _esl_patterns = [
        ("tense_mixing", _ESL_TENSE_MIXING),
        ("agreement_variation", _ESL_AGREEMENT),
        ("uncountable_noun", _ESL_UNCOUNTABLE),
        ("year_format", _ESL_YEAR_FORMAT),
        ("since_duration", _ESL_SINCE_DURATION),
        ("article_error", _ARTICLE_ERROR),
        ("preposition_transfer", _PREPOSITION_TRANSFER),
    ]

    for name, pattern in _esl_patterns:
        matches = pattern.findall(text)
        if matches:
            evidence = [m if isinstance(m, str) else " ".join(m).strip() for m in matches[:3]]
            features.append(LinguisticFeature(
                name=name,
                category="multilingual",
                evidence=evidence,
                asset_label="Multilingual writing pattern",
                sentiment_effect="caveat",
                aic_weight_adjustments=_MULTILINGUAL_AIC,
            ))

    # Code-mixing
    if _CODE_MIXING.search(text):
        features.append(LinguisticFeature(
            name="code_mixing",
            category="multilingual",
            evidence=_CODE_MIXING.findall(text)[:3],
            asset_label="Multilingual — code-mixing as communicative resource",
            sentiment_effect="caveat",
            aic_weight_adjustments={"personal_voice": 0.8},
        ))

    # langdetect-based code-mixing (more accurate than regex)
    if not any(f.name == "code_mixing" for f in features):
        _lang_features = _langdetect_code_mixing(text)
        features.extend(_lang_features)

    return features


# ═══════════════════════════════════════════════════════════════════════════
# Category: Register & Affect
# ═══════════════════════════════════════════════════════════════════════════

_HEDGES = re.compile(
    r"\b(maybe|perhaps|possibly|might|could be|kind of|sort of|"
    r"i think|i guess|i feel like|it seems|apparently|"
    r"not sure|don'?t know)\b",
    re.IGNORECASE,
)

_COMMUNAL_PRONOUNS = re.compile(r"\b(we|our|us|ourselves)\b", re.I)
_INDIVIDUAL_PRONOUNS = re.compile(r"\b(I|my|me|myself|mine)\b")

_NARRATIVE_MARKERS = re.compile(
    r'(?:"[^"]{5,}")|'                             # Dialogue in quotes
    r"(?:\byou know\b|\blisten\b|\bimagine\b)|"    # Direct address
    r"(?:\bfirst\b.*\bthen\b.*\bso\b)",            # Sequential narration
    re.IGNORECASE | re.DOTALL,
)

# Complex emotional engagement — GoEmotions pairs
_COMPLEX_AFFECT_PAIRS = [
    (frozenset({"grief", "sadness"}), frozenset({"admiration", "love", "caring"})),
    (frozenset({"anger", "annoyance"}), frozenset({"caring", "love", "admiration"})),
    (frozenset({"fear", "nervousness"}), frozenset({"optimism", "love", "pride"})),
]

_ENGAGEMENT_CATEGORIES = frozenset({
    "critical_analysis", "conceptual_connection",
    "personal_reflection", "evidence_use",
})


def _detect_register_affect(
    text: str,
    word_count: int,
    compound_score: float,
    emotions: Dict[str, float],
    keyword_hits: Dict[str, int],
) -> List[LinguisticFeature]:
    """Detect register and affect features."""
    features: List[LinguisticFeature] = []

    # Flat affect + engagement
    if word_count >= 50 and abs(compound_score) < 0.15:
        engaged_categories = sum(
            1 for cat in _ENGAGEMENT_CATEGORIES
            if keyword_hits.get(cat, 0) >= 1
        )
        if engaged_categories >= 2:
            features.append(LinguisticFeature(
                name="flat_affect_engaged",
                category="register_affect",
                evidence=[f"compound={compound_score:.3f}, {engaged_categories} engagement categories"],
                asset_label="Deep engagement, understated expression",
                sentiment_effect="caveat",
            ))

    # Hedging density
    if word_count >= 50:
        hedge_count = len(_HEDGES.findall(text))
        density = (hedge_count / word_count) * 100
        if density > 3.0:
            features.append(LinguisticFeature(
                name="hedging_density",
                category="register_affect",
                evidence=[f"{density:.1f} hedges per 100 words"],
                asset_label="Indirect/hedged expression style",
                sentiment_effect="caveat",
                aic_weight_adjustments={"personal_voice": 0.8},
            ))

    # Communal voice
    communal_count = len(_COMMUNAL_PRONOUNS.findall(text))
    individual_count = len(_INDIVIDUAL_PRONOUNS.findall(text))
    if communal_count > individual_count and communal_count >= 3:
        features.append(LinguisticFeature(
            name="communal_voice",
            category="register_affect",
            evidence=[f"we/our/us: {communal_count}, I/my/me: {individual_count}"],
            asset_label="Engagement through communal/collective voice",
            sentiment_effect="none",
        ))

    # Narrative markers
    narrative_matches = _NARRATIVE_MARKERS.findall(text)
    if len(narrative_matches) >= 2:
        features.append(LinguisticFeature(
            name="narrative_structure",
            category="register_affect",
            evidence=[m[:50] for m in narrative_matches[:3]],
            asset_label="Engagement through narrative tradition",
            sentiment_effect="none",
        ))

    # Complex emotional engagement (from GoEmotions)
    if emotions:
        for neg_set, pos_set in _COMPLEX_AFFECT_PAIRS:
            neg_score = max((emotions.get(e, 0.0) for e in neg_set), default=0.0)
            pos_score = max((emotions.get(e, 0.0) for e in pos_set), default=0.0)
            if neg_score > 0.1 and pos_score > 0.1:
                neg_label = max(neg_set, key=lambda e: emotions.get(e, 0.0))
                pos_label = max(pos_set, key=lambda e: emotions.get(e, 0.0))
                features.append(LinguisticFeature(
                    name="complex_emotional_engagement",
                    category="register_affect",
                    evidence=[f"{neg_label} ({neg_score:.2f}) + {pos_label} ({pos_score:.2f})"],
                    asset_label="Complex emotional engagement with course material",
                    sentiment_effect="none",
                ))
                break  # only report first matching pair

    # Oral register
    # (was_transcribed is checked but we don't have it here — handled by caller
    #  passing a separate feature if needed)

    return features


# ═══════════════════════════════════════════════════════════════════════════
# Category: Academic Convention (First-Gen Patterns)
# ═══════════════════════════════════════════════════════════════════════════
# Formulaic essay structure taught in developmental English.
# NOT a deficit — students are following learned conventions.
# Ported from context_analyzer._detect_first_gen_patterns().

_FORMULAIC_INTRO = ["in this essay", "this paper will", "i will discuss", "i am going to"]
_FORMULAIC_CONCLUSION = ["in conclusion", "to conclude", "in summary", "to sum up"]
_FORMULAIC_TRANSITIONS = frozenset({
    "firstly", "secondly", "thirdly", "furthermore", "moreover", "additionally",
})


def _detect_academic_convention(text: str) -> List[LinguisticFeature]:
    """Detect formulaic essay structure (first-gen patterns)."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) < 3:
        return []

    signals = 0
    evidence: List[str] = []

    # Check intro
    first_lower = paragraphs[0].lower()
    if any(marker in first_lower for marker in _FORMULAIC_INTRO):
        signals += 1
        evidence.append("formulaic introduction")

    # Check conclusion
    last_lower = paragraphs[-1].lower()
    if any(marker in last_lower for marker in _FORMULAIC_CONCLUSION):
        signals += 1
        evidence.append("formulaic conclusion")

    # Check transitions
    for para in paragraphs[1:-1]:
        words = para.split()
        if words:
            first_word = words[0].lower().rstrip(",")
            if first_word in _FORMULAIC_TRANSITIONS:
                signals += 1
                evidence.append(f"explicit transition: {first_word}")
                break

    if signals >= 2:
        return [LinguisticFeature(
            name="formulaic_structure",
            category="academic_convention",
            evidence=evidence,
            asset_label="Taught essay structure — following learned conventions",
            sentiment_effect="none",
            aic_weight_adjustments={"ai_specific_org": 0.6},
        )]
    return []


# ═══════════════════════════════════════════════════════════════════════════
# Category: Structural Variation
# ═══════════════════════════════════════════════════════════════════════════

_SENTENCE_SPLIT = re.compile(r"[.!?]\s+(?=[A-Z])")

_SHORT_SUBMISSION_WORDS = 80


def _detect_structural(text: str, word_count: int) -> List[LinguisticFeature]:
    """Detect structural features (short submission, high variance)."""
    features: List[LinguisticFeature] = []

    # Short submission — sample too small for reliable sentiment
    if word_count < _SHORT_SUBMISSION_WORDS:
        features.append(LinguisticFeature(
            name="short_submission",
            category="structural",
            evidence=[f"{word_count} words (threshold: {_SHORT_SUBMISSION_WORDS})"],
            # NOT an asset — just a data quality gate. No asset_label.
            asset_label="",
            sentiment_effect="suppress",
        ))

    # High variance sentence structure
    sentences = _SENTENCE_SPLIT.split(text)
    if len(sentences) >= 5:
        lengths = [len(s.split()) for s in sentences if s.strip()]
        if len(lengths) >= 5:
            mean_len = statistics.mean(lengths)
            std_len = statistics.stdev(lengths)
            if mean_len > 0 and std_len > 2 * mean_len:
                features.append(LinguisticFeature(
                    name="high_variance_structure",
                    category="structural",
                    evidence=[f"sentence length std={std_len:.1f}, mean={mean_len:.1f}"],
                    asset_label="Variable structure — diverse rhetorical moves",
                    sentiment_effect="none",
                    aic_weight_adjustments={"ai_specific_org": 0.7},
                ))

    return features


# ═══════════════════════════════════════════════════════════════════════════
# Aggregation
# ═══════════════════════════════════════════════════════════════════════════

def _derive_tier(features: List[LinguisticFeature]) -> str:
    """Derive sentiment reliability tier from detected features.

    Rules:
    - 'suppressed' if ANY feature has sentiment_effect="suppress"
      (the detector already applied its own threshold — e.g., 2+ distinct
      AAVE markers before setting effect to "suppress")
    - 'low' if any feature has sentiment_effect="caveat"
    - 'high' otherwise
    """
    for f in features:
        if f.sentiment_effect == "suppress":
            return "suppressed"
    for f in features:
        if f.sentiment_effect == "caveat":
            return "low"
    return "high"


def _merge_aic(features: List[LinguisticFeature]) -> Dict[str, float]:
    """Merge AIC weight adjustments — most protective (lowest) wins."""
    merged: Dict[str, float] = {}
    for f in features:
        for marker, mult in f.aic_weight_adjustments.items():
            if marker in merged:
                merged[marker] = min(merged[marker], mult)
            else:
                merged[marker] = mult
    return merged


def _dedupe_assets(features: List[LinguisticFeature]) -> List[str]:
    """Dedupe asset labels — one per unique label, preserving order."""
    seen: set = set()
    result: List[str] = []
    for f in features:
        if f.asset_label and f.asset_label not in seen:
            seen.add(f.asset_label)
            result.append(f.asset_label)
    return result


_CATEGORY_NOTES = {
    "syntactic_variation": (
        "This student's writing includes AAVE linguistic features. "
        "AAVE is a complete linguistic system — read engagement through "
        "their actual voice, not standard English expectations."
    ),
    "multilingual": (
        "This student is a multilingual writer. Non-standard syntax "
        "reflects language transfer between linguistic systems, not "
        "confusion or lack of understanding."
    ),
    "register_affect": (
        "This student's engagement may be understated in tone but "
        "substantive in content. Read ideas and substance, not affect markers."
    ),
    # No LLM note for academic_convention or structural — not relevant to coding
}


def _build_llm_context(features: List[LinguisticFeature]) -> str:
    """Build ≤3 sentence LLM context note from detected features."""
    categories_present = set(f.category for f in features if f.asset_label)
    notes = []
    for cat in ("syntactic_variation", "multilingual", "register_affect"):
        if cat in categories_present and cat in _CATEGORY_NOTES:
            notes.append(_CATEGORY_NOTES[cat])
    return " ".join(notes[:3])


def _build_caveat(features: List[LinguisticFeature], tier: str) -> str:
    """Build diagnostic caveat string (for logging, not for LLM prompt)."""
    if tier == "high":
        return ""
    triggers = [f.name for f in features if f.sentiment_effect in ("suppress", "caveat")]
    trigger_str = " / ".join(triggers)
    if tier == "suppressed":
        return f"Emotional register score withheld ({trigger_str}). Read tone from text."
    return f"Emotional register score may be unreliable ({trigger_str}). Treat as weak signal."


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def detect_features(
    text: str,
    word_count: int,
    *,
    was_translated: bool = False,
    was_transcribed: bool = False,
    compound_score: float = 0.0,
    emotions: Optional[Dict[str, float]] = None,
    keyword_hits: Optional[Dict[str, int]] = None,
    assignment_connection_overlap: Optional[float] = None,
) -> LinguisticFeatureResult:
    """Detect linguistic features in a student submission.

    Parameters
    ----------
    text : str
        Submission text.
    word_count : int
        Word count (pre-computed for efficiency).
    was_translated : bool
        True if submission was translated from another language.
    was_transcribed : bool
        True if submission was transcribed from audio.
    compound_score : float
        Raw compound score from the emotional register scorer (-1.0 to 1.0).
    emotions : dict or None
        GoEmotions label→score dict (empty or None if VADER fallback).
    keyword_hits : dict or None
        Pattern name → match count from match_all_patterns().
    assignment_connection_overlap : float or None
        Vocabulary overlap score (0.0–1.0).  Currently unused but reserved
        for future low-overlap detection.

    Returns
    -------
    LinguisticFeatureResult with detected features and all aggregated outputs.
    """
    if emotions is None:
        emotions = {}
    if keyword_hits is None:
        keyword_hits = {}

    features: List[LinguisticFeature] = []

    # 1. Run all detectors
    try:
        features.extend(_detect_syntactic_variation(text))
    except Exception as e:
        log.warning("Syntactic variation detection failed: %s", e)

    try:
        features.extend(_detect_multilingual(text, was_translated, compound_score))
    except Exception as e:
        log.warning("Multilingual detection failed: %s", e)

    try:
        features.extend(_detect_register_affect(
            text, word_count, compound_score, emotions, keyword_hits,
        ))
    except Exception as e:
        log.warning("Register/affect detection failed: %s", e)

    try:
        features.extend(_detect_academic_convention(text))
    except Exception as e:
        log.warning("Academic convention detection failed: %s", e)

    try:
        features.extend(_detect_structural(text, word_count))
    except Exception as e:
        log.warning("Structural detection failed: %s", e)

    # Oral transcription — add as a soft caveat feature
    if was_transcribed:
        features.append(LinguisticFeature(
            name="oral_transcription",
            category="register_affect",
            evidence=["submission transcribed from audio"],
            asset_label="Oral expression style",
            sentiment_effect="caveat",
        ))

    # 2. Aggregate
    tier = _derive_tier(features)
    triggers = [f.name for f in features if f.sentiment_effect in ("suppress", "caveat")]
    caveat = _build_caveat(features, tier)
    assets = _dedupe_assets(features)
    context = _build_llm_context(features)
    aic_adj = _merge_aic(features)

    return LinguisticFeatureResult(
        features=features,
        sentiment_tier=tier,
        sentiment_triggers=triggers,
        sentiment_caveat=caveat,
        asset_labels=assets,
        llm_context_note=context,
        aic_adjustments=aic_adj,
    )
