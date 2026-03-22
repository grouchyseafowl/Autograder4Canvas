"""
Human Presence Detection Module
Version 2.2.0

Detects markers of human presence across five dimensions:
- Authentic Voice (15%)
- Productive Messiness (10%)
- Cognitive Struggle (20%)
- Emotional Stakes (20%)
- Contextual Grounding (35% - highest, hardest to fake)

Paradigm shift: From "Does this look like AI?" to "Does this show a human mind at work?"
"""

import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Try to import marker loader
try:
    from modules.marker_loader import MarkerLoader
    HAS_MARKER_LOADER = True
except ImportError:
    HAS_MARKER_LOADER = False


@dataclass
class CategoryScore:
    """Score for a single human presence category."""
    category_id: str
    category_name: str
    raw_score: float
    weighted_score: float
    weight: float
    marker_count: int
    markers_found: List[str] = field(default_factory=list)
    details: Dict = field(default_factory=dict)


@dataclass
class HumanPresenceResult:
    """Result of human presence detection analysis."""
    # Overall scores
    total_score: float  # Sum of weighted category scores (0-100)
    confidence_level: str  # very_high, high, medium, low, very_low
    confidence_percentage: float  # 0-100

    # Category breakdowns
    authentic_voice: CategoryScore
    productive_messiness: CategoryScore
    cognitive_struggle: CategoryScore
    emotional_stakes: CategoryScore
    contextual_grounding: CategoryScore

    # Analysis details
    total_markers_found: int
    significant_combinations: List[str] = field(default_factory=list)
    strongest_signals: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)

    # Metadata
    word_count: int = 0
    analysis_notes: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in fallback patterns
# ---------------------------------------------------------------------------
# These ensure the detector works even if YAML marker files cannot be loaded.
# Each entry is (pattern_string, is_regex, weight).

_BUILTIN_PATTERNS: Dict[str, List[Tuple[str, bool, float]]] = {
    'authentic_voice': [
        # Code-meshing / colloquial anchors
        (r"\b(this stuff|the thing is)\b", True, 0.6),
        ("what really gets me is", False, 0.7),
        ("let's be real", False, 0.7),
        ("honestly,", False, 0.5),
        ("in my neighborhood", False, 0.8),
        ("where I'm from", False, 0.8),
        ("in our community", False, 0.8),
        # Translanguaging
        ("I don't know the English word for", False, 0.8),
        ("This is hard to translate", False, 0.7),
        # Tonal shifts
        (r"In academic terms.{0,40}but (honestly|really)", True, 0.7),
        (r"The textbook says.{0,40}which I guess", True, 0.7),
        # Personal asides
        ("You might be wondering", False, 0.6),
        ("Think about it this way", False, 0.5),
        ("Let me explain what I mean", False, 0.6),
        ("Here's what I'm trying to say", False, 0.6),
        # Cultural grounding
        ("in my culture", False, 0.9),
        ("where I grew up", False, 0.8),
        (r"my (family|ancestors|elders|community) (believe|teach|say|told me)", True, 0.9),
        # Unique phrasings
        (r"(weird|strange|interesting) (thing|part) is", True, 0.5),
        # General personal voice
        (r"\bI\s", True, 0.15),
        (r"\bmy\b", True, 0.15),
    ],
    'productive_messiness': [
        # Self-correction
        ("Actually, I think", False, 0.8),
        ("Wait, that's not quite right", False, 0.9),
        ("Let me rephrase that", False, 0.7),
        ("No, what I mean is", False, 0.8),
        ("On second thought", False, 0.7),
        ("What I really mean is", False, 0.7),
        ("Or rather", False, 0.6),
        # Genuine hedging
        (r"I think.{0,30}because", True, 0.6),
        (r"Maybe.{0,30}but I'm not (entirely )?sure", True, 0.7),
        ("I could be wrong, but", False, 0.7),
        ("I might be misunderstanding", False, 0.7),
        # False starts
        ("What I mean to say is", False, 0.7),
        ("Or I guess", False, 0.5),
        ("Or maybe", False, 0.5),
        ("I mean", False, 0.4),
        # Circling back
        ("Going back to what I said earlier", False, 0.8),
        ("This connects to my earlier point", False, 0.8),
        ("Like I said before", False, 0.6),
        # Revision thinking
        ("I realize I haven't explained", False, 0.7),
        ("Looking back at what I wrote", False, 0.7),
        ("Now I realize", False, 0.7),
        ("Let me back up", False, 0.7),
        ("I'm getting ahead of myself", False, 0.7),
        # Awkward genuine
        (r"\bSo basically\b", True, 0.5),
        ("The thing is that", False, 0.5),
        ("if that makes sense", False, 0.6),
        ("At least that's how I understand it", False, 0.6),
        # Incomplete synthesis
        ("I see both sides but can't fully reconcile", False, 0.9),
        (r"I'm still (working through|figuring out|grappling with)", True, 0.7),
        (r"I'm (torn|conflicted|unsure) about", True, 0.6),
    ],
    'cognitive_struggle': [
        # Metacognitive
        (r"I'm (struggling|having trouble) to understand (how|why)", True, 0.9),
        ("This is confusing because", False, 0.8),
        ("I'm having trouble reconciling", False, 0.9),
        ("I think I understand this part, but", False, 0.8),
        ("I'm trying to understand", False, 0.7),
        (r"I'm (confused|uncertain|unsure) about", True, 0.6),
        # Working through
        (r"I used to think.{0,50}but now", True, 0.8),
        ("My understanding has changed because", False, 0.9),
        ("As I worked through", False, 0.7),
        ("Breaking this down", False, 0.6),
        # Self-questioning
        (r"But (what|how|why|when) (does|is|would)", True, 0.7),
        ("This raises the question", False, 0.6),
        ("I'm left wondering", False, 0.7),
        ("But wouldn't that mean", False, 0.7),
        # Complexity acknowledgment
        (r"(This is|It's) more (complicated|complex|nuanced) than", True, 0.8),
        ("The more I think about it, the more complicated", False, 0.8),
        (r"There's a lot to (unpack|consider|think about)", True, 0.7),
        ("I didn't realize how", False, 0.7),
        # Contradictions explored
        (r"On (the )?one hand.{0,100}on the other", True, 0.7),
        (r"This (seems|appears) to contradict", True, 0.8),
        ("I'm trying to reconcile", False, 0.9),
        ("How can both be true", False, 0.9),
        ("There's a tension between", False, 0.8),
        # Honest confusion
        (r"I honestly don't (know|understand)", True, 0.8),
        (r"I don't (fully |really )?get", True, 0.6),
        ("This doesn't make sense to me", False, 0.7),
        ("I can't figure out", False, 0.7),
        # Perspective shifts
        (r"I never (thought about|considered)", True, 0.8),
        (r"This (changed|shifted) (how|the way) I think about", True, 0.8),
        (r"Now I (see|understand|realize)", True, 0.7),
        # Metacognitive reflection (real-time processing — human mind at work)
        # These overlap with AIC's cognitive_diversity markers but were missing here.
        ("now that I think about it", False, 0.6),
        (r"I'm realizing (as I write|as I think)", True, 0.7),
        ("I just realized", False, 0.5),
        ("thinking about it now", False, 0.5),
        (r"my (thought process|brain keeps going to)", True, 0.6),
        ("as I'm thinking through this", False, 0.6),
        # Associative connections (mind making links in real time)
        (r"this reminds me of", False, 0.5),
        ("I see a pattern", False, 0.5),
        # Authentic struggle articulation
        ("this is harder to explain than I thought", False, 0.7),
        (r"I'm having trouble (explaining|putting)", True, 0.7),
        ("trying to make this make sense", False, 0.6),
    ],
    'emotional_stakes': [
        # Personal connection
        (r"(This|That) (matters|is important) to me because", True, 0.9),
        (r"I care (deeply )?about this because", True, 0.9),
        ("This is personal", False, 0.9),
        (r"As someone who (has|is)", True, 0.7),
        ("This hits home", False, 0.8),
        (r"(This|It) reminds me of (my|when I)", True, 0.7),
        ("Speaking from experience", False, 0.8),
        # Emotional language
        (r"(I|It) makes me (angry|frustrated|sad|disappointed|hopeful)", True, 0.8),
        (r"I (feel|felt) (strongly|deeply) about", True, 0.7),
        (r"I'm (passionate|concerned|worried|hopeful|excited) about", True, 0.7),
        ("I can't help but feel", False, 0.6),
        ("This breaks my heart", False, 0.8),
        ("This gives me hope", False, 0.7),
        # Stakes articulation
        (r"(This|That) matters because", True, 0.7),
        ("What's at stake", False, 0.8),
        ("This affects real people", False, 0.7),
        # Discomfort naming
        (r"This is (hard|difficult|uncomfortable) to", True, 0.7),
        ("This makes me uncomfortable", False, 0.7),
        ("I'm troubled by", False, 0.7),
        # Relational thinking
        (r"I (think|worry) about (people|those) who", True, 0.7),
        (r"(Our|My) community", True, 0.6),
        ("I think about my family", False, 0.8),
        # Resistance / pushback
        (r"I (can't|won't) accept", True, 0.7),
        (r"This (violates|contradicts) my (values|beliefs|experience)", True, 0.8),
        ("Something feels wrong about", False, 0.6),
        # Hope / investment
        (r"I hope (that|we can)", True, 0.6),
        (r"I want to (see|believe|hope)", True, 0.6),
        ("I can't stop thinking about", False, 0.7),
        # Intellectual passion
        (r"(I'm|I am) (fascinated|intrigued|captivated) by", True, 0.6),
        (r"What (really )?(interests|fascinates|intrigues) me", True, 0.6),
    ],
    'contextual_grounding': [
        # Class discussion references
        (r"In class (when|on|during) (we|the class)", True, 1.5),
        (r"(During|In) (Monday|Tuesday|Wednesday|Thursday|Friday)'s (lecture|class|discussion)", True, 1.5),
        (r"When (Professor|Dr\.|Prof\.)", True, 1.3),
        (r"Our class (debate|discussion|conversation) about", True, 1.4),
        (r"When we (talked|discussed|covered) (this |that )?in class", True, 1.3),
        # Course material references
        (r"(Our|The) textbook (on page|page|chapter) [0-9]+", True, 1.5),
        (r"The (syllabus|assignment) (mentioned|said|asked)", True, 1.3),
        (r"The reading (from|for) (week|module|chapter) [0-9]+", True, 1.3),
        (r"(On|From) page [0-9]+", True, 1.2),
        (r"In (chapter|section) [0-9]+", True, 1.1),
        # Assignment-specific engagement
        (r"The (assignment|prompt) (asked|required|wanted us)", True, 1.4),
        (r"For this (assignment|paper|essay)", True, 1.0),
        (r"The (instructions|guidelines|rubric) (said|mentioned)", True, 1.3),
        # Temporal grounding
        (r"(Last|This) (week|Monday|Tuesday|semester)", True, 1.1),
        (r"(Recently|Earlier this) (week|month|semester)", True, 1.0),
        (r"So far in (this|the) (course|class|semester)", True, 1.0),
        # Local / embodied knowledge
        (r"Where I (live|work|grew up|am from)", True, 1.0),
        (r"In (my|our) (neighborhood|community|town|city)", True, 0.9),
        (r"At (my|the local) (job|workplace|school)", True, 0.9),
        # Learning narrative
        (r"(Before|At the start of) this (course|class).{0,50}(I|my understanding)", True, 1.3),
        (r"(Through|After) (this course|these readings|our discussions)", True, 1.2),
        (r"Over the (course|semester|weeks)", True, 1.0),
        # Dialogue with materials
        (r"(The author|They) (argue|claim|suggest).{0,50}(but|however|yet) I", True, 1.1),
        (r"I (agree|disagree) with.{0,50}(when they|where they)", True, 1.0),
        # Peer interaction
        (r"(My|A) classmate (said|mentioned|argued)", True, 1.3),
        (r"In our group (discussion|project|work)", True, 1.2),
        (r"Another student (pointed out|mentioned|said)", True, 1.1),
    ],
}


def _compile_builtin_patterns() -> Dict[str, List[Tuple[re.Pattern, float]]]:
    """Pre-compile built-in fallback patterns (called once at import)."""
    compiled: Dict[str, List[Tuple[re.Pattern, float]]] = {}
    for category_id, pattern_list in _BUILTIN_PATTERNS.items():
        compiled_list: List[Tuple[re.Pattern, float]] = []
        for pattern_str, is_regex, weight in pattern_list:
            try:
                if is_regex:
                    regex = re.compile(pattern_str, re.IGNORECASE)
                else:
                    escaped = re.escape(pattern_str)
                    regex = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
                compiled_list.append((regex, weight))
            except re.error:
                pass  # Skip invalid patterns
        compiled[category_id] = compiled_list
    return compiled


_COMPILED_BUILTINS = _compile_builtin_patterns()

# ---------------------------------------------------------------------------
# Expected raw-score midpoints per category for calibration.
# These are the raw_score values at which a category should read ~50%
# (i.e. "moderate" presence).  Derived from typical student essay
# pattern-match counts and average weights from the YAML files.
# ---------------------------------------------------------------------------
_RAW_SCORE_MIDPOINTS: Dict[str, float] = {
    'authentic_voice': 3.0,
    'productive_messiness': 2.0,
    'cognitive_struggle': 3.5,
    'emotional_stakes': 3.0,
    'contextual_grounding': 5.0,
}


def _normalize_score(raw_score: float, category_id: str, word_count: int) -> float:
    """Normalize a raw category score to 0-100 using a logistic curve.

    The logistic function maps any positive raw_score into (0, 100) with
    a smooth S-curve centred on the category's expected midpoint, scaled
    for text length.  This avoids the cliff-edge behaviour of the
    previous linear ``min(raw * 10, 100)`` approach and ensures that:

    * A moderate number of matches produces a score around 50.
    * Diminishing returns kick in naturally for many matches.
    * Very short texts with a few strong matches still score well.

    The length adjustment lowers the midpoint for shorter texts (under
    ~500 words) so that a 200-word essay with 3 strong contextual
    references is not penalised relative to a 1000-word essay with 6.
    """
    if raw_score <= 0:
        return 0.0

    midpoint = _RAW_SCORE_MIDPOINTS.get(category_id, 3.0)

    # Length adjustment: for texts under 500 words scale the midpoint
    # down proportionally (floor at 40% of midpoint).
    if word_count > 0 and word_count < 500:
        length_factor = max(0.4, word_count / 500.0)
        midpoint = midpoint * length_factor

    # Steepness of the logistic curve.  Higher k → sharper transition.
    k = 1.5 / midpoint  # ensures slope centred around midpoint

    # Standard logistic:  100 / (1 + e^(-k*(x - midpoint)))
    # Shifted so f(0) ≈ 0:  we subtract f(0) and rescale.
    raw_logistic = 1.0 / (1.0 + math.exp(-k * (raw_score - midpoint)))
    floor_logistic = 1.0 / (1.0 + math.exp(-k * (0 - midpoint)))

    # Rescale so that raw_score=0 maps to 0 and the ceiling approaches 100.
    normalized = (raw_logistic - floor_logistic) / (1.0 - floor_logistic) * 100.0

    return min(max(normalized, 0.0), 100.0)


class HumanPresenceDetector:
    """
    Detects evidence of human presence across multiple dimensions.

    Uses combination scoring - individual markers less meaningful than
    patterns across multiple categories.
    """

    # Category weights (must sum to 1.0)
    CATEGORY_WEIGHTS = {
        'contextual_grounding': 0.35,  # Highest - hardest to fake
        'emotional_stakes': 0.20,
        'cognitive_struggle': 0.20,
        'authentic_voice': 0.15,
        'productive_messiness': 0.10
    }

    # Confidence thresholds (based on weighted score 0-100)
    CONFIDENCE_THRESHOLDS = {
        'very_high': (85, 100),    # 85-100: Deep contextual + multiple dimensions
        'high': (65, 84),          # 65-84: Strong contextual + other dimensions
        'medium': (40, 64),        # 40-64: Multi-dimensional but lighter
        'low': (20, 39),           # 20-39: Unclear, needs review
        'very_low': (0, 19)        # 0-19: Little/no human presence
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the detector."""
        self.config_dir = config_dir
        self.marker_loader = None
        self._yaml_load_failed = False

        if HAS_MARKER_LOADER:
            self.marker_loader = MarkerLoader(config_dir)

    def analyze(self, text: str, assignment_type: Optional[str] = None) -> HumanPresenceResult:
        """
        Analyze text for human presence markers.

        Args:
            text: The text to analyze
            assignment_type: Optional assignment type for context adjustments

        Returns:
            HumanPresenceResult with comprehensive analysis
        """
        if not text or not text.strip():
            return self._create_empty_result()

        word_count = len(text.split())

        # Analyze each category
        authentic_voice = self._analyze_category(text, 'authentic_voice', assignment_type, word_count)
        productive_messiness = self._analyze_category(text, 'productive_messiness', assignment_type, word_count)
        cognitive_struggle = self._analyze_category(text, 'cognitive_struggle', assignment_type, word_count)
        emotional_stakes = self._analyze_category(text, 'emotional_stakes', assignment_type, word_count)
        contextual_grounding = self._analyze_category(text, 'contextual_grounding', assignment_type, word_count)

        # Calculate total score (0-100)
        total_score = (
            authentic_voice.weighted_score +
            productive_messiness.weighted_score +
            cognitive_struggle.weighted_score +
            emotional_stakes.weighted_score +
            contextual_grounding.weighted_score
        )

        # Determine confidence level
        confidence_level = self._determine_confidence_level(total_score)
        confidence_percentage = total_score

        # Identify significant combinations
        significant_combinations = self._identify_combinations(
            authentic_voice, productive_messiness, cognitive_struggle,
            emotional_stakes, contextual_grounding
        )

        # Identify strongest signals
        strongest_signals = self._identify_strongest_signals(
            authentic_voice, productive_messiness, cognitive_struggle,
            emotional_stakes, contextual_grounding
        )

        # Generate concerns
        concerns = self._generate_concerns(
            total_score, authentic_voice, productive_messiness, cognitive_struggle,
            emotional_stakes, contextual_grounding
        )

        # Count total markers
        total_markers = (
            authentic_voice.marker_count +
            productive_messiness.marker_count +
            cognitive_struggle.marker_count +
            emotional_stakes.marker_count +
            contextual_grounding.marker_count
        )

        # Generate analysis notes
        analysis_notes = self._generate_analysis_notes(
            total_score, confidence_level, word_count, total_markers,
            contextual_grounding, emotional_stakes, cognitive_struggle
        )

        return HumanPresenceResult(
            total_score=round(total_score, 2),
            confidence_level=confidence_level,
            confidence_percentage=round(confidence_percentage, 1),
            authentic_voice=authentic_voice,
            productive_messiness=productive_messiness,
            cognitive_struggle=cognitive_struggle,
            emotional_stakes=emotional_stakes,
            contextual_grounding=contextual_grounding,
            total_markers_found=total_markers,
            significant_combinations=significant_combinations,
            strongest_signals=strongest_signals,
            concerns=concerns,
            word_count=word_count,
            analysis_notes=analysis_notes
        )

    def _analyze_category(self, text: str, category_id: str,
                          assignment_type: Optional[str] = None,
                          word_count: int = 0) -> CategoryScore:
        """Analyze text for a specific category of markers."""
        markers_found: List[str] = []
        raw_score = 0.0
        marker_count = 0
        used_yaml = False

        # ------------------------------------------------------------------
        # Try YAML-loaded patterns first (richer, configurable)
        # ------------------------------------------------------------------
        if self.marker_loader and HAS_MARKER_LOADER and not self._yaml_load_failed:
            try:
                loaded_markers = self.marker_loader.load_all_markers()

                if category_id in loaded_markers.compiled_patterns:
                    patterns = loaded_markers.compiled_patterns[category_id]
                    for regex, weight, _confidence in patterns:
                        matches = list(regex.finditer(text))
                        if matches:
                            marker_count += len(matches)
                            raw_score += weight * len(matches)
                            for match in matches[:3]:
                                markers_found.append(match.group())
                    used_yaml = True
            except Exception as e:
                # Log the failure once so it isn't invisible, then fall back
                # to built-in patterns for all subsequent calls.
                print(f"  [HPD] YAML marker loading failed ({e}); using built-in patterns")
                self._yaml_load_failed = True

        # ------------------------------------------------------------------
        # Fallback: built-in compiled patterns (always available)
        # ------------------------------------------------------------------
        if not used_yaml:
            builtin = _COMPILED_BUILTINS.get(category_id, [])
            for regex, weight in builtin:
                matches = list(regex.finditer(text))
                if matches:
                    marker_count += len(matches)
                    raw_score += weight * len(matches)
                    for match in matches[:3]:
                        markers_found.append(match.group())

        # ------------------------------------------------------------------
        # Normalize raw score to 0-100 using calibrated logistic curve
        # ------------------------------------------------------------------
        normalized_score = _normalize_score(raw_score, category_id, word_count)

        # Apply category weight
        weight = self.CATEGORY_WEIGHTS[category_id]
        weighted_score = normalized_score * weight

        # Category names
        category_names = {
            'authentic_voice': 'Authentic Voice',
            'productive_messiness': 'Productive Messiness',
            'cognitive_struggle': 'Cognitive Struggle',
            'emotional_stakes': 'Emotional Stakes',
            'contextual_grounding': 'Contextual Grounding'
        }

        return CategoryScore(
            category_id=category_id,
            category_name=category_names[category_id],
            raw_score=round(raw_score, 2),
            weighted_score=round(weighted_score, 2),
            weight=weight,
            marker_count=marker_count,
            markers_found=markers_found[:10],  # Keep first 10
            details={'normalized_score': round(normalized_score, 2)}
        )

    def _determine_confidence_level(self, total_score: float) -> str:
        """Determine confidence level from total score."""
        for level, (min_score, max_score) in self.CONFIDENCE_THRESHOLDS.items():
            if min_score <= total_score <= max_score:
                return level
        return 'very_low'

    def _identify_combinations(self, av: CategoryScore, pm: CategoryScore,
                                cs: CategoryScore, es: CategoryScore,
                                cg: CategoryScore) -> List[str]:
        """Identify significant combinations of markers across categories."""
        combinations = []

        # Strong combinations (as per guide)
        if cg.marker_count >= 3 and cs.marker_count >= 2 and av.marker_count >= 2:
            combinations.append("Contextual grounding + cognitive struggle + authentic voice (VERY STRONG)")

        if cg.marker_count >= 3 and es.marker_count >= 2:
            combinations.append("Contextual grounding + emotional stakes (STRONG)")

        if av.marker_count >= 3 and es.marker_count >= 2:
            combinations.append("Authentic voice + emotional stakes (STRONG)")

        if pm.marker_count >= 3 and cs.marker_count >= 2:
            combinations.append("Productive messiness + cognitive struggle (STRONG thinking-in-progress)")

        # Multi-dimensional presence
        categories_with_markers = sum([
            1 if av.marker_count > 0 else 0,
            1 if pm.marker_count > 0 else 0,
            1 if cs.marker_count > 0 else 0,
            1 if es.marker_count > 0 else 0,
            1 if cg.marker_count > 0 else 0
        ])

        if categories_with_markers >= 4:
            combinations.append(f"Multi-dimensional presence across {categories_with_markers}/5 categories")

        return combinations

    def _identify_strongest_signals(self, av: CategoryScore, pm: CategoryScore,
                                     cs: CategoryScore, es: CategoryScore,
                                     cg: CategoryScore) -> List[str]:
        """Identify the strongest human presence signals."""
        signals = []

        # Contextual grounding is always most important
        if cg.marker_count >= 5:
            signals.append(f"Strong contextual grounding ({cg.marker_count} markers) - hardest to fake")
        elif cg.marker_count >= 3:
            signals.append(f"Moderate contextual grounding ({cg.marker_count} markers)")

        # Cognitive struggle with evolution of understanding
        if cs.marker_count >= 5:
            signals.append(f"Significant cognitive struggle ({cs.marker_count} markers) - genuine engagement")

        # Emotional investment
        if es.marker_count >= 5:
            signals.append(f"Clear emotional stakes ({es.marker_count} markers) - personal investment")

        # Authentic voice with cultural grounding
        if av.marker_count >= 5:
            signals.append(f"Strong authentic voice ({av.marker_count} markers) - unique perspective")

        # Thinking-in-progress
        if pm.marker_count >= 5:
            signals.append(f"Visible thinking-in-progress ({pm.marker_count} markers)")

        return signals

    def _generate_concerns(self, total_score: float, av: CategoryScore,
                          pm: CategoryScore, cs: CategoryScore,
                          es: CategoryScore, cg: CategoryScore) -> List[str]:
        """Generate concerns based on analysis."""
        concerns = []

        # Low contextual grounding is most concerning
        if cg.marker_count < 2 and total_score < 50:
            concerns.append("Very low contextual grounding - little evidence of course participation")

        # Low overall score
        if total_score < 20:
            concerns.append("Very low overall human presence score")

        # No markers in multiple categories
        categories_missing = []
        if av.marker_count == 0:
            categories_missing.append("authentic voice")
        if pm.marker_count == 0:
            categories_missing.append("productive messiness")
        if cs.marker_count == 0:
            categories_missing.append("cognitive struggle")
        if es.marker_count == 0:
            categories_missing.append("emotional stakes")
        if cg.marker_count == 0:
            categories_missing.append("contextual grounding")

        if len(categories_missing) >= 4:
            concerns.append(f"No markers detected in {len(categories_missing)}/5 categories")

        return concerns

    def _generate_analysis_notes(self, total_score: float, confidence_level: str,
                                 word_count: int, total_markers: int,
                                 cg: CategoryScore, es: CategoryScore,
                                 cs: CategoryScore) -> List[str]:
        """Generate human-readable analysis notes."""
        notes = []

        # Overall assessment
        if confidence_level == 'very_high':
            notes.append("Strong evidence of genuine human authorship across multiple dimensions")
        elif confidence_level == 'high':
            notes.append("Good evidence of human authorship with meaningful engagement")
        elif confidence_level == 'medium':
            notes.append("Moderate evidence - some human markers present but not comprehensive")
        elif confidence_level == 'low':
            notes.append("Limited evidence of human presence - recommend instructor review")
        else:
            notes.append("Very limited human presence markers - recommend conversation with student")

        # Marker density
        if word_count > 0:
            markers_per_100_words = (total_markers / word_count) * 100
            if markers_per_100_words > 2:
                notes.append(f"High marker density ({markers_per_100_words:.1f} markers per 100 words)")

        # Contextual grounding note
        if cg.marker_count >= 5:
            notes.append("Excellent contextual grounding - clear course participation")
        elif cg.marker_count >= 3:
            notes.append("Moderate contextual grounding detected")
        elif cg.marker_count < 2:
            notes.append("Limited contextual grounding - verify student participated in course")

        return notes

    def _create_empty_result(self) -> HumanPresenceResult:
        """Create an empty result for invalid input."""
        empty_category = CategoryScore(
            category_id="",
            category_name="",
            raw_score=0.0,
            weighted_score=0.0,
            weight=0.0,
            marker_count=0
        )

        return HumanPresenceResult(
            total_score=0.0,
            confidence_level='very_low',
            confidence_percentage=0.0,
            authentic_voice=empty_category,
            productive_messiness=empty_category,
            cognitive_struggle=empty_category,
            emotional_stakes=empty_category,
            contextual_grounding=empty_category,
            total_markers_found=0,
            word_count=0,
            analysis_notes=["No text provided for analysis"]
        )


def analyze_human_presence(text: str, assignment_type: Optional[str] = None,
                            config_dir: Optional[Path] = None) -> HumanPresenceResult:
    """
    Convenience function to analyze text for human presence.

    Args:
        text: The text to analyze
        assignment_type: Optional assignment type for context adjustments
        config_dir: Optional config directory path

    Returns:
        HumanPresenceResult with comprehensive analysis
    """
    detector = HumanPresenceDetector(config_dir)
    return detector.analyze(text, assignment_type)
