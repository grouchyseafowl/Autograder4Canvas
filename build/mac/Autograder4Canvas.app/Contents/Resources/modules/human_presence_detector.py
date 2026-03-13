"""
Human Presence Detection Module
Version 2.1.0

Detects markers of human presence across five dimensions:
- Authentic Voice (15%)
- Productive Messiness (10%)
- Cognitive Struggle (20%)
- Emotional Stakes (20%)
- Contextual Grounding (35% - highest, hardest to fake)

Paradigm shift: From "Does this look like AI?" to "Does this show a human mind at work?"
"""

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
        'very_high': (90, 100),    # 90-100: Deep contextual + multiple dimensions
        'high': (75, 89),           # 75-89: Strong contextual + other dimensions
        'medium': (50, 74),         # 50-74: Multi-dimensional but lighter
        'low': (25, 49),            # 25-49: Unclear, needs review
        'very_low': (0, 24)         # 0-24: Little/no human presence
    }

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize the detector."""
        self.config_dir = config_dir
        self.marker_loader = None

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
        authentic_voice = self._analyze_category(text, 'authentic_voice', assignment_type)
        productive_messiness = self._analyze_category(text, 'productive_messiness', assignment_type)
        cognitive_struggle = self._analyze_category(text, 'cognitive_struggle', assignment_type)
        emotional_stakes = self._analyze_category(text, 'emotional_stakes', assignment_type)
        contextual_grounding = self._analyze_category(text, 'contextual_grounding', assignment_type)

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
                          assignment_type: Optional[str] = None) -> CategoryScore:
        """Analyze text for a specific category of markers."""
        # For now, use pattern matching (later can integrate with marker_loader)
        # Load patterns from the YAML files via marker_loader

        markers_found = []
        raw_score = 0.0
        marker_count = 0

        # Use marker_loader if available
        if self.marker_loader and HAS_MARKER_LOADER:
            try:
                # Load all markers
                loaded_markers = self.marker_loader.load_all_markers()

                # Get patterns for this category
                if category_id in loaded_markers.compiled_patterns:
                    patterns = loaded_markers.compiled_patterns[category_id]

                    for regex, weight, confidence in patterns:
                        matches = list(regex.finditer(text))
                        if matches:
                            marker_count += len(matches)
                            raw_score += weight * len(matches)
                            # Store first few matches
                            for match in matches[:3]:
                                markers_found.append(match.group())
            except Exception as e:
                pass  # Graceful fallback

        # Normalize raw score to 0-100 scale for this category
        # (raw scores can vary, normalize based on typical ranges)
        normalized_score = min(raw_score * 10, 100)  # Simple normalization

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
        if total_score < 25:
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
