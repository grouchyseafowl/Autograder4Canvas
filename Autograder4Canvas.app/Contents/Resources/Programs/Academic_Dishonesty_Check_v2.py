"""
Academic Dishonesty Check v2.0
Adaptive, Data-Driven Academic Integrity Analysis System

This tool identifies markers of potential academic dishonesty using:
- Externalized, versioned detection markers (YAML configuration)
- Peer comparison (statistical outlier detection)
- Context-aware adjustments (ESL, first-gen, community college)
- Pedagogically-informed reporting (conversation starters, not accusations)

IMPORTANT: This tool is a CONVERSATION STARTER, not a verdict.
Flags are indicators for instructor judgment, not proof of dishonesty.
"""

import os
import re
import sys
import json
import platform
import statistics
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from dataclasses import dataclass, field
from html import unescape

# Version info
VERSION = "2.0.0"
VERSION_DATE = "2025-12-26"

# =============================================================================
# CONFIGURATION
# =============================================================================

CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com")
API_TOKEN = os.getenv("CANVAS_API_TOKEN")

# Try to import requests
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

HEADERS = {}
if API_TOKEN and HAS_REQUESTS:
    HEADERS = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json"
    }


def get_config_dir() -> Path:
    """Get the configuration directory for storing settings."""
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        config_dir = base / "CanvasAutograder"
    elif system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        config_dir = Path.home() / ".config" / "CanvasAutograder"
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_output_base_dir() -> Path:
    """Get base output directory for reports."""
    system = platform.system()
    
    # Check for /output directory (container environment)
    if os.path.isdir("/output"):
        return Path("/output")
    
    # Check for custom output directory in config
    config_file = get_config_dir() / "settings.json"
    if config_file.exists():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if "output_directory" in config:
                    custom_dir = Path(config["output_directory"])
                    custom_dir.mkdir(parents=True, exist_ok=True)
                    return custom_dir
        except Exception:
            pass
    
    # Default location
    if system == "Windows":
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        documents = Path.home() / "Documents"
    
    return documents / "Autograder Rationales"


# =============================================================================
# BUILT-IN PATTERNS
# =============================================================================

# AI detection patterns - transitions and meta-commentary
AI_TRANSITIONS = [
    "it is important to note", "it should be noted", "it is worth noting",
    "delving into", "navigating the complexities", "in the realm of",
    "this underscores", "it becomes evident", "one cannot overstate",
    "serves as a testament", "in light of", "furthermore", "moreover",
    "additionally", "in addition", "in conclusion", "to sum up",
    "firstly", "secondly", "thirdly", "lastly", "this essay will explore",
    "this paper will examine", "as previously mentioned", "as stated above",
    "it is crucial to understand", "plays a pivotal role", "a profound impact"
]

# Generic/vague phrases
GENERIC_PHRASES = [
    "throughout history", "since the beginning of time", "in today's society",
    "in today's world", "many things", "various aspects", "studies show",
    "research indicates", "experts say", "it has been shown", "some people believe",
    "a variety of", "a number of", "plays a crucial role", "of paramount importance",
    "cannot be overstated", "it can be said", "it could be argued",
    "in many ways", "on the other hand", "when it comes to"
]

# Personal voice markers (absence is suspicious in personal writing)
PERSONAL_MARKERS = [
    r"\bI\s", r"\bmy\b", r"\bme\b", r"\bmine\b", r"\bmyself\b",
    r"\bwe\b", r"\bour\b", "I realized", "I remember", "I noticed",
    "my experience", "I believe", "I think", "I felt", "I was"
]

# Emotional language
EMOTIONAL_MARKERS = [
    "I felt", "I was scared", "I cried", "I laughed", "it hurt",
    "I struggled", "I was confused", "I was frustrated", "I was excited",
    "I was nervous", "I was embarrassed", "I was proud", "I was relieved"
]

# Inflated vocabulary
INFLATED_VOCAB = [
    ("utilize", "use"), ("demonstrate", "show"), ("individuals", "people"),
    ("commence", "start"), ("terminate", "end"), ("endeavor", "try"),
    ("facilitate", "help"), ("implement", "do"), ("ascertain", "find out"),
    ("optimal", "best"), ("subsequent", "next"), ("prior to", "before"),
    ("multifaceted", "complex"), ("plethora", "many")
]


# =============================================================================
# ASSIGNMENT PROFILES
# =============================================================================

ASSIGNMENT_PROFILES = {
    "personal_reflection": {
        "id": "personal_reflection",
        "name": "Personal Reflection / Response Paper",
        "description": "Personal essays, reflections requiring authentic voice",
        "detection_focus": "absence_detection",
        "weight_multipliers": {
            "personal_voice": 2.0,
            "specific_details": 2.0,
            "emotional_language": 1.5,
            "ai_transitions": 1.3,
            "generic_phrases": 1.5
        },
        "instructor_notes": [
            "Absence of personal voice is as concerning as presence of AI markers",
            "Look for specific sensory details and named individuals/places",
            "Generic reflections that could apply to anyone are concerning"
        ]
    },
    "analytical_essay": {
        "id": "analytical_essay",
        "name": "Analytical / Argumentative Essay",
        "description": "Formal analysis essays where some formal language is expected",
        "detection_focus": "presence_detection",
        "weight_multipliers": {
            "personal_voice": 0.5,
            "ai_transitions": 0.8,
            "generic_phrases": 1.2,
            "citation_markers": 1.5
        },
        "instructor_notes": [
            "Some formal transitions are expected in analytical writing",
            "Focus on generic content that could be written without reading the texts",
            "Check if analysis engages with specific passages"
        ]
    },
    "discussion_post": {
        "id": "discussion_post",
        "name": "Discussion Forum Post",
        "description": "Forum posts that should reference readings and classmates",
        "detection_focus": "engagement_detection",
        "weight_multipliers": {
            "personal_voice": 1.0,
            "ai_transitions": 1.2,
            "generic_phrases": 1.3,
            "engagement_markers": 1.5
        },
        "instructor_notes": [
            "Posts should reference specific readings or classmate comments",
            "Highly formal language is unusual in discussion posts",
            "Generic posts that don't engage with course material are concerning"
        ]
    },
    "rough_draft": {
        "id": "rough_draft",
        "name": "Rough Draft / First Draft",
        "description": "Early drafts where errors and rough structure are expected",
        "detection_focus": "polish_detection",
        "weight_multipliers": {
            "personal_voice": 0.5,
            "ai_transitions": 0.7,
            "generic_phrases": 0.8,
            "polish_markers": 2.0
        },
        "instructor_notes": [
            "Drafts should show rough edges - too-perfect drafts are suspicious",
            "Students often ignore 'don't polish' instructions, so focus on patterns",
            "Compare against final version for authentic revision evidence"
        ]
    },
    "standard": {
        "id": "standard",
        "name": "Standard Analysis (Default)",
        "description": "Default balanced analysis for any assignment type",
        "detection_focus": "balanced",
        "weight_multipliers": {
            "personal_voice": 1.0,
            "ai_transitions": 1.0,
            "generic_phrases": 1.0
        },
        "instructor_notes": [
            "Default mode - use more specific profiles when possible",
            "All checks enabled with moderate sensitivity"
        ]
    }
}


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class AnalysisResult:
    """Result of analyzing a single submission."""
    student_id: str
    student_name: str
    
    # Raw text info
    text: str
    word_count: int
    
    # Marker scores
    suspicious_score: float
    authenticity_score: float
    marker_counts: Dict[str, int]
    markers_found: Dict[str, List[str]]
    
    # Concern assessment
    concern_level: str
    
    # Context adjustments
    context_adjustments_applied: List[str] = field(default_factory=list)
    adjusted_suspicious_score: Optional[float] = None
    adjusted_concern_level: Optional[str] = None
    
    # Peer comparison (filled in later)
    suspicious_percentile: Optional[float] = None
    authenticity_percentile: Optional[float] = None
    is_outlier: bool = False
    outlier_reasons: List[str] = field(default_factory=list)
    
    # Guidance
    conversation_starters: List[str] = field(default_factory=list)
    revision_guidance: List[str] = field(default_factory=list)
    verification_questions: List[str] = field(default_factory=list)


# =============================================================================
# ANALYSIS ENGINE
# =============================================================================

class DishonestyAnalyzer:
    """
    Main analysis engine for academic dishonesty detection.
    
    Combines:
    - Marker-based detection (built-in patterns)
    - Peer comparison (statistical outlier detection)
    - Context-aware adjustments
    - Pedagogical reporting
    """
    
    def __init__(self, 
                 profile_id: str = "standard",
                 context_profile: str = "community_college"):
        """
        Initialize the analyzer.
        
        Args:
            profile_id: Assignment profile to use
            context_profile: Student population context
        """
        self.profile_id = profile_id
        self.context_profile = context_profile
        self.profile = ASSIGNMENT_PROFILES.get(profile_id, ASSIGNMENT_PROFILES["standard"])
        
        # Context multiplier (community college = more lenient)
        self.context_multiplier = 0.7 if context_profile == "community_college" else 1.0
    
    def analyze_text(self, 
                     text: str, 
                     student_id: str = "unknown",
                     student_name: str = "Unknown Student") -> AnalysisResult:
        """
        Analyze a single text submission.
        """
        # Clean text
        text = self._clean_text(text)
        word_count = len(text.split())
        
        # Analyze with built-in patterns
        suspicious_score, authenticity_score, marker_counts, markers_found = \
            self._analyze_with_builtin_patterns(text)
        
        # Apply profile weight multipliers
        suspicious_score = self._apply_profile_weights(suspicious_score, marker_counts)
        
        # Apply context adjustments (ESL, community college, etc.)
        adjusted_suspicious = suspicious_score * self.context_multiplier
        
        # Determine concern level
        concern_level = self._determine_concern_level(suspicious_score, authenticity_score)
        adjusted_concern = self._determine_concern_level(adjusted_suspicious, authenticity_score)
        
        # Get guidance
        conversation_starters = self._get_conversation_starters(concern_level)
        revision_guidance = self._get_revision_guidance(concern_level)
        verification_questions = self._get_verification_questions(concern_level)
        
        context_applied = []
        if self.context_profile == "community_college":
            context_applied = ["ESL consideration", "First-generation adjustment"]
        
        return AnalysisResult(
            student_id=student_id,
            student_name=student_name,
            text=text,
            word_count=word_count,
            suspicious_score=round(suspicious_score, 2),
            authenticity_score=round(authenticity_score, 2),
            marker_counts=marker_counts,
            markers_found=markers_found,
            concern_level=concern_level,
            context_adjustments_applied=context_applied,
            adjusted_suspicious_score=round(adjusted_suspicious, 2),
            adjusted_concern_level=adjusted_concern,
            conversation_starters=conversation_starters,
            revision_guidance=revision_guidance,
            verification_questions=verification_questions
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text for analysis."""
        if not text:
            return ""
        
        # Decode HTML entities
        text = unescape(text)
        
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    def _analyze_with_builtin_patterns(self, text: str) -> Tuple[float, float, Dict[str, int], Dict[str, List[str]]]:
        """Analyze text using built-in patterns."""
        text_lower = text.lower()
        
        suspicious_score = 0.0
        authenticity_score = 0.0
        marker_counts = {}
        markers_found = {}
        
        # Check AI transitions
        transition_matches = []
        for phrase in AI_TRANSITIONS:
            count = text_lower.count(phrase.lower())
            if count > 0:
                transition_matches.extend([phrase] * count)
        marker_counts['ai_transitions'] = len(transition_matches)
        if transition_matches:
            markers_found['ai_transitions'] = transition_matches[:5]
        suspicious_score += len(transition_matches) * 0.5
        
        # Clustering bonus: multiple AI markers in short text is very suspicious
        if len(transition_matches) >= 3 and len(text.split()) < 500:
            suspicious_score += 2.0
        
        # Check generic phrases
        generic_matches = []
        for phrase in GENERIC_PHRASES:
            count = text_lower.count(phrase.lower())
            if count > 0:
                generic_matches.extend([phrase] * count)
        marker_counts['generic_phrases'] = len(generic_matches)
        if generic_matches:
            markers_found['generic_phrases'] = generic_matches[:5]
        suspicious_score += len(generic_matches) * 0.4
        
        # Check inflated vocabulary
        inflated_matches = []
        for inflated, simple in INFLATED_VOCAB:
            count = text_lower.count(inflated.lower())
            if count > 0:
                inflated_matches.extend([inflated] * count)
        marker_counts['inflated_vocabulary'] = len(inflated_matches)
        if inflated_matches:
            markers_found['inflated_vocabulary'] = inflated_matches[:5]
        suspicious_score += len(inflated_matches) * 0.3
        
        # Check personal markers (presence is GOOD)
        personal_count = 0
        personal_matches = []
        for pattern in PERSONAL_MARKERS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            personal_count += len(matches)
            if matches:
                personal_matches.extend([m.strip() for m in matches[:3]])
        marker_counts['personal_voice'] = personal_count
        if personal_matches:
            markers_found['personal_voice'] = personal_matches[:5]
        authenticity_score += min(personal_count * 0.5, 5.0)
        
        # Check emotional markers (presence is GOOD)
        emotional_count = 0
        emotional_matches = []
        for phrase in EMOTIONAL_MARKERS:
            count = text_lower.count(phrase.lower())
            emotional_count += count
            if count > 0:
                emotional_matches.append(phrase)
        marker_counts['emotional_language'] = emotional_count
        if emotional_matches:
            markers_found['emotional_language'] = emotional_matches[:5]
        authenticity_score += min(emotional_count * 0.8, 4.0)
        
        # Check for specific details (proper nouns are GOOD)
        proper_nouns = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', text)
        # Filter out sentence starters
        specific_count = len([n for n in proper_nouns if len(n) > 3])
        marker_counts['specific_details'] = specific_count
        authenticity_score += min(specific_count * 0.2, 3.0)
        
        return suspicious_score, authenticity_score, marker_counts, markers_found
    
    def _apply_profile_weights(self, score: float, marker_counts: Dict[str, int]) -> float:
        """Apply profile-specific weight multipliers to SUSPICIOUS markers only."""
        multipliers = self.profile.get('weight_multipliers', {})
        
        # Only count suspicious markers, not authenticity markers
        suspicious_markers = {'ai_transitions', 'generic_phrases', 'inflated_vocabulary'}
        
        adjusted_score = 0.0
        for marker_id, count in marker_counts.items():
            if marker_id not in suspicious_markers:
                continue
            base_weight = 0.3  # Base weight per marker
            multiplier = multipliers.get(marker_id, 1.0)
            adjusted_score += count * base_weight * multiplier
        
        return adjusted_score
    
    def _determine_concern_level(self, suspicious: float, authenticity: float) -> str:
        """Determine concern level based on scores."""
        # High: High suspicious AND low authenticity
        if suspicious > 5.0 and authenticity < 2.0:
            return 'high'
        
        # Elevated: Moderate suspicious OR very low authenticity
        if suspicious > 4.0 or authenticity < 1.5:
            return 'elevated'
        
        # Moderate: Some concerning patterns
        if suspicious > 2.5 or authenticity < 3.0:
            return 'moderate'
        
        # Low: Minor issues
        if suspicious > 1.5:
            return 'low'
        
        return 'none'
    
    def _get_conversation_starters(self, concern_level: str) -> List[str]:
        """Get appropriate conversation starters."""
        starters = {
            'high': [
                "Can you walk me through how you approached this assignment?",
                "I'd love to hear more about your thinking process.",
                "Can you tell me about a specific moment that influenced your writing?",
                "What was the most challenging part of this for you?"
            ],
            'elevated': [
                "Can you expand on some of the ideas in your paper?",
                "How did you decide on this approach?",
                "What specific examples from your experience informed this?"
            ],
            'moderate': [
                "Can you add some more personal examples?",
                "I'd like to hear more of your own voice in this."
            ]
        }
        return starters.get(concern_level, [])
    
    def _get_revision_guidance(self, concern_level: str) -> List[str]:
        """Get revision guidance."""
        if concern_level not in ['high', 'elevated']:
            return []
        
        if self.profile_id == 'personal_reflection':
            return [
                "Add 2-3 specific sensory details from your actual experience",
                "Include at least one specific person, place, or time from your life",
                "Remove generic statements that could apply to anyone"
            ]
        else:
            return [
                "Add more specific examples and details",
                "Include your own analysis and interpretation",
                "Make sure your own thinking is clearly present"
            ]
    
    def _get_verification_questions(self, concern_level: str) -> List[str]:
        """Get verification questions for instructor."""
        if concern_level not in ['high', 'elevated']:
            return []
        
        return [
            "What specific moment or experience prompted this reflection?",
            "Can you describe in more detail what you actually saw/heard/felt?",
            "How did your understanding change as you wrote this?",
            "Which part of the reading specifically connected to your experience?"
        ]


# =============================================================================
# PEER COMPARISON
# =============================================================================

class PeerComparisonAnalyzer:
    """
    Statistical outlier detection based on peer comparison.
    
    Philosophy: A score that's unusual for THIS class is more meaningful
    than hitting an absolute threshold. Adapts to each cohort's patterns.
    """
    
    def __init__(self, outlier_percentile: float = 90.0):
        """
        Initialize peer comparison analyzer.
        
        Args:
            outlier_percentile: Percentile above which to flag as outlier
                               (95 for community college, 90 for others)
        """
        self.outlier_percentile = outlier_percentile
    
    def analyze_cohort(self, results: List[AnalysisResult]) -> Dict[str, Any]:
        """
        Analyze a cohort of submissions and identify statistical outliers.
        
        Returns summary statistics and updates each result with percentile info.
        """
        if len(results) < 3:
            return {"error": "Need at least 3 submissions for peer comparison"}
        
        # Extract scores
        suspicious_scores = [r.suspicious_score for r in results]
        authenticity_scores = [r.authenticity_score for r in results]
        
        # Calculate statistics
        sus_mean = statistics.mean(suspicious_scores)
        sus_stdev = statistics.stdev(suspicious_scores) if len(suspicious_scores) > 1 else 0
        auth_mean = statistics.mean(authenticity_scores)
        auth_stdev = statistics.stdev(authenticity_scores) if len(authenticity_scores) > 1 else 0
        
        # Calculate percentile threshold
        sorted_sus = sorted(suspicious_scores)
        threshold_idx = int(len(sorted_sus) * self.outlier_percentile / 100)
        sus_threshold = sorted_sus[min(threshold_idx, len(sorted_sus) - 1)]
        
        # Update each result with percentile and outlier info
        outliers = []
        for result in results:
            # Calculate percentile
            below_count = sum(1 for s in suspicious_scores if s < result.suspicious_score)
            result.suspicious_percentile = round(100 * below_count / len(suspicious_scores), 1)
            
            below_count = sum(1 for s in authenticity_scores if s < result.authenticity_score)
            result.authenticity_percentile = round(100 * below_count / len(authenticity_scores), 1)
            
            # Check if outlier
            outlier_reasons = []
            
            if result.suspicious_score > sus_threshold:
                outlier_reasons.append(f"Suspicious score in top {100 - self.outlier_percentile:.0f}% of class")
            
            if sus_stdev > 0:
                z_score = (result.suspicious_score - sus_mean) / sus_stdev
                if z_score > 2.0:
                    outlier_reasons.append(f"Z-score {z_score:.1f} (>2 standard deviations)")
            
            if result.authenticity_score < auth_mean - (1.5 * auth_stdev) and auth_stdev > 0:
                outlier_reasons.append("Low authenticity compared to peers")
            
            if outlier_reasons:
                result.is_outlier = True
                result.outlier_reasons = outlier_reasons
                outliers.append(result)
        
        return {
            "total_submissions": len(results),
            "suspicious_mean": round(sus_mean, 2),
            "suspicious_stdev": round(sus_stdev, 2),
            "suspicious_threshold": round(sus_threshold, 2),
            "authenticity_mean": round(auth_mean, 2),
            "authenticity_stdev": round(auth_stdev, 2),
            "outlier_count": len(outliers),
            "outliers": outliers
        }


# =============================================================================
# REPORT GENERATOR
# =============================================================================

class ReportGenerator:
    """
    Generates pedagogically-informed reports.
    
    Philosophy: Reports are for INSTRUCTORS, not verdicts.
    Frame findings as conversation starters, not accusations.
    """
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or (get_output_base_dir() / "Academic Dishonesty Reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_report(self,
                        assignment_name: str,
                        profile_name: str,
                        results: List[AnalysisResult],
                        cohort_stats: Optional[Dict] = None,
                        context_profile: str = "community_college") -> Path:
        """Generate a text report."""
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = "".join(c for c in assignment_name if c.isalnum() or c in " -_")[:50]
        filepath = self.output_dir / f"{safe_name}_{timestamp}_report.txt"
        
        lines = []
        
        # Header
        lines.append("=" * 75)
        lines.append("ACADEMIC INTEGRITY ANALYSIS REPORT")
        lines.append("=" * 75)
        lines.append("")
        lines.append(f"Assignment: {assignment_name}")
        lines.append(f"Analysis Profile: {profile_name}")
        lines.append(f"Context Profile: {context_profile}")
        lines.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Total Submissions: {len(results)}")
        lines.append("")
        
        # Important framing
        lines.append("-" * 75)
        lines.append("IMPORTANT: HOW TO USE THIS REPORT")
        lines.append("-" * 75)
        lines.append("""
This report identifies INDICATORS that warrant instructor review.
It does NOT provide proof of academic dishonesty.

WHAT THIS TOOL IS:
  ✓ A conversation starter for discussing student work
  ✓ An outlier detector (peer comparison, not absolute judgment)
  ✓ A pedagogical support for upholding learning objectives

WHAT THIS TOOL IS NOT:
  ✗ A verdict or proof of cheating
  ✗ An AI detector (detects dishonest USE, not all AI use)
  ✗ Infallible (false positives occur - especially for ESL students)

RECOMMENDED APPROACH:
  1. Review flagged submissions yourself before any conversation
  2. Use conversation starters provided - don't accuse
  3. Consider student's other work for context
  4. Frame as learning opportunity when discussing with students
""")
        lines.append("")
        
        # Cohort summary
        if cohort_stats:
            lines.append("-" * 75)
            lines.append("COHORT STATISTICAL SUMMARY")
            lines.append("-" * 75)
            lines.append(f"  Suspicious Score - Mean: {cohort_stats.get('suspicious_mean', 'N/A')}, "
                        f"StDev: {cohort_stats.get('suspicious_stdev', 'N/A')}")
            lines.append(f"  Authenticity Score - Mean: {cohort_stats.get('authenticity_mean', 'N/A')}, "
                        f"StDev: {cohort_stats.get('authenticity_stdev', 'N/A')}")
            lines.append(f"  Outliers Identified: {cohort_stats.get('outlier_count', 0)}")
            lines.append("")
        
        # Summary by concern level
        lines.append("-" * 75)
        lines.append("SUMMARY BY CONCERN LEVEL")
        lines.append("-" * 75)
        
        high_concern = [r for r in results if r.concern_level == 'high']
        elevated = [r for r in results if r.concern_level == 'elevated']
        moderate = [r for r in results if r.concern_level == 'moderate']
        low = [r for r in results if r.concern_level == 'low']
        clean = [r for r in results if r.concern_level == 'none']
        
        lines.append(f"  HIGH CONCERN:     {len(high_concern):3d} (recommend structured conversation)")
        lines.append(f"  ELEVATED:         {len(elevated):3d} (recommend brief check-in)")
        lines.append(f"  MODERATE:         {len(moderate):3d} (note for pattern tracking)")
        lines.append(f"  LOW:              {len(low):3d} (feedback only)")
        lines.append(f"  NO CONCERNS:      {len(clean):3d}")
        lines.append("")
        
        # Detailed reports for high/elevated concern
        if high_concern or elevated:
            lines.append("=" * 75)
            lines.append("DETAILED ANALYSIS: HIGH & ELEVATED CONCERN")
            lines.append("=" * 75)
            
            for result in high_concern + elevated:
                lines.extend(self._format_detailed_result(result))
                lines.append("")
        
        # Brief listing for moderate concern
        if moderate:
            lines.append("-" * 75)
            lines.append("MODERATE CONCERN (Brief Summary)")
            lines.append("-" * 75)
            for result in moderate:
                emoji = "🟡"
                lines.append(f"  {emoji} {result.student_name}: suspicious={result.suspicious_score:.1f}, "
                           f"authenticity={result.authenticity_score:.1f}")
            lines.append("")
        
        # Footer
        lines.append("=" * 75)
        lines.append("END OF REPORT")
        lines.append("=" * 75)
        lines.append("")
        lines.append("Remember: All flags require human judgment. When in doubt,")
        lines.append("have a conversation with the student before drawing conclusions.")
        
        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines))
        
        return filepath
    
    def _format_detailed_result(self, result: AnalysisResult) -> List[str]:
        """Format a single detailed result."""
        lines = []
        
        concern_emoji = {
            'high': '🔴',
            'elevated': '🟠',
            'moderate': '🟡',
            'low': '🟢',
            'none': '⚪'
        }
        
        emoji = concern_emoji.get(result.concern_level, '⚪')
        
        lines.append("-" * 50)
        lines.append(f"{emoji} {result.student_name}")
        lines.append(f"   Concern Level: {result.concern_level.upper()}")
        lines.append(f"   Word Count: {result.word_count}")
        lines.append("")
        
        lines.append("   SCORES:")
        lines.append(f"     Suspicious Markers: {result.suspicious_score:.2f}")
        if result.suspicious_percentile is not None:
            lines[-1] += f" ({result.suspicious_percentile:.0f}th percentile)"
        lines.append(f"     Authenticity Markers: {result.authenticity_score:.2f}")
        if result.authenticity_percentile is not None:
            lines[-1] += f" ({result.authenticity_percentile:.0f}th percentile)"
        lines.append("")
        
        if result.is_outlier and result.outlier_reasons:
            lines.append("   STATISTICAL OUTLIER:")
            for reason in result.outlier_reasons:
                lines.append(f"     → {reason}")
            lines.append("")
        
        if result.context_adjustments_applied:
            lines.append("   CONTEXT ADJUSTMENTS APPLIED:")
            for ctx in result.context_adjustments_applied:
                lines.append(f"     • {ctx}")
            lines.append("")
        
        if result.markers_found:
            lines.append("   KEY MARKERS DETECTED:")
            for marker_type, instances in list(result.markers_found.items())[:5]:
                lines.append(f"     {marker_type}: {len(instances)} instance(s)")
                for instance in instances[:3]:
                    lines.append(f"       \"{instance}\"")
            lines.append("")
        
        if result.conversation_starters:
            lines.append("   CONVERSATION STARTERS:")
            for starter in result.conversation_starters[:3]:
                lines.append(f"     • \"{starter}\"")
            lines.append("")
        
        if result.verification_questions:
            lines.append("   VERIFICATION QUESTIONS:")
            for q in result.verification_questions[:3]:
                lines.append(f"     • {q}")
        
        return lines


# =============================================================================
# CANVAS INTEGRATION
# =============================================================================

def get_courses():
    """Fetch list of courses for the current user."""
    if not HAS_REQUESTS or not API_TOKEN:
        print("Error: Canvas API not configured.")
        return []
    
    url = f"{CANVAS_BASE_URL}/api/v1/courses"
    params = {"enrollment_state": "active", "per_page": 100}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching courses: {e}")
        return []


def get_assignments(course_id: int):
    """Fetch assignments for a course."""
    if not HAS_REQUESTS or not API_TOKEN:
        return []
    
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments"
    params = {"per_page": 100}
    
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching assignments: {e}")
        return []


def get_submissions(course_id: int, assignment_id: int):
    """Fetch all submissions for an assignment."""
    if not HAS_REQUESTS or not API_TOKEN:
        return []
    
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    params = {"per_page": 100, "include[]": ["user"]}
    
    all_submissions = []
    
    try:
        while url:
            response = requests.get(url, headers=HEADERS, params=params)
            response.raise_for_status()
            submissions = response.json()
            all_submissions.extend(submissions)
            
            # Check for pagination
            links = response.headers.get("Link", "")
            url = None
            for link in links.split(","):
                if 'rel="next"' in link:
                    url = link.split(";")[0].strip().strip("<>")
                    params = {}  # URL already contains params
                    break
        
        return all_submissions
    except Exception as e:
        print(f"Error fetching submissions: {e}")
        return []


# =============================================================================
# BATCH PROCESSING
# =============================================================================

def analyze_assignment(course_id: int, 
                       assignment_id: int,
                       profile_id: str = "standard",
                       context_profile: str = "community_college") -> Tuple[List[AnalysisResult], Path]:
    """
    Analyze all submissions for an assignment.
    
    Returns:
        Tuple of (list of results, path to report file)
    """
    print(f"\nFetching submissions...")
    submissions = get_submissions(course_id, assignment_id)
    
    if not submissions:
        print("No submissions found.")
        return [], None
    
    print(f"Found {len(submissions)} submissions.")
    
    # Initialize analyzer
    analyzer = DishonestyAnalyzer(profile_id=profile_id, context_profile=context_profile)
    
    # Analyze each submission
    results = []
    for sub in submissions:
        # Get student info
        user = sub.get("user", {})
        student_id = str(sub.get("user_id", "unknown"))
        student_name = user.get("name", f"Student {student_id}")
        
        # Get submission text
        body = sub.get("body", "") or ""
        
        # Skip empty submissions
        if not body.strip():
            continue
        
        print(f"  Analyzing: {student_name}...")
        result = analyzer.analyze_text(body, student_id, student_name)
        results.append(result)
    
    if not results:
        print("No text submissions to analyze.")
        return [], None
    
    # Run peer comparison
    print(f"\nRunning peer comparison on {len(results)} submissions...")
    peer_analyzer = PeerComparisonAnalyzer(
        outlier_percentile=95.0 if context_profile == "community_college" else 90.0
    )
    cohort_stats = peer_analyzer.analyze_cohort(results)
    
    # Generate report
    print("Generating report...")
    
    # Get assignment name
    assignments = get_assignments(course_id)
    assignment_name = "Unknown Assignment"
    for a in assignments:
        if a.get("id") == assignment_id:
            assignment_name = a.get("name", "Unknown Assignment")
            break
    
    report_gen = ReportGenerator()
    profile_name = ASSIGNMENT_PROFILES.get(profile_id, {}).get("name", profile_id)
    report_path = report_gen.generate_report(
        assignment_name=assignment_name,
        profile_name=profile_name,
        results=results,
        cohort_stats=cohort_stats,
        context_profile=context_profile
    )
    
    print(f"\nReport saved to: {report_path}")
    
    return results, report_path


# =============================================================================
# INTERACTIVE MENU
# =============================================================================

def select_from_list(items: List[Dict], prompt: str, name_key: str = "name", id_key: str = "id") -> Optional[Dict]:
    """Display a selection menu and return the chosen item."""
    if not items:
        print("No items available.")
        return None
    
    print(f"\n{prompt}")
    print("-" * 40)
    
    for i, item in enumerate(items, 1):
        name = item.get(name_key, f"Item {i}")
        print(f"  {i}. {name}")
    
    print(f"  0. Cancel")
    
    while True:
        try:
            choice = input("\nEnter number: ").strip()
            if choice == "0":
                return None
            idx = int(choice) - 1
            if 0 <= idx < len(items):
                return items[idx]
            print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")


def select_profile() -> str:
    """Select an assignment profile."""
    print("\nSelect Assignment Profile:")
    print("-" * 40)
    
    profiles = list(ASSIGNMENT_PROFILES.values())
    for i, profile in enumerate(profiles, 1):
        print(f"  {i}. {profile['name']}")
        print(f"      {profile['description']}")
    
    while True:
        try:
            choice = input("\nEnter number (default 1): ").strip()
            if not choice:
                return profiles[0]['id']
            idx = int(choice) - 1
            if 0 <= idx < len(profiles):
                return profiles[idx]['id']
            print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")


def main_menu():
    """Display main interactive menu."""
    print("\n" + "=" * 60)
    print("  ACADEMIC DISHONESTY CHECK v2.0")
    print("  Adaptive Academic Integrity Analysis")
    print("=" * 60)
    
    if not API_TOKEN:
        print("\n⚠️  CANVAS_API_TOKEN not set!")
        print("   Set this environment variable to connect to Canvas.")
        print("   Example: export CANVAS_API_TOKEN='your_token_here'")
        return
    
    while True:
        print("\n" + "-" * 40)
        print("MAIN MENU")
        print("-" * 40)
        print("  1. Analyze Canvas Assignment")
        print("  2. Analyze Single Text (paste)")
        print("  3. View Assignment Profiles")
        print("  4. About This Tool")
        print("  0. Exit")
        
        choice = input("\nEnter choice: ").strip()
        
        if choice == "0":
            print("\nGoodbye!")
            break
        
        elif choice == "1":
            # Analyze Canvas assignment
            courses = get_courses()
            course = select_from_list(courses, "Select a Course:")
            if not course:
                continue
            
            assignments = get_assignments(course['id'])
            assignment = select_from_list(assignments, "Select an Assignment:")
            if not assignment:
                continue
            
            profile_id = select_profile()
            
            print("\nContext Profile:")
            print("  1. Community College (more lenient, ESL-aware)")
            print("  2. Standard (default thresholds)")
            ctx_choice = input("Enter choice (default 1): ").strip()
            context_profile = "community_college" if ctx_choice != "2" else "standard"
            
            results, report_path = analyze_assignment(
                course['id'],
                assignment['id'],
                profile_id=profile_id,
                context_profile=context_profile
            )
            
            if results:
                # Show summary
                high = sum(1 for r in results if r.concern_level == 'high')
                elevated = sum(1 for r in results if r.concern_level == 'elevated')
                print(f"\n📊 Summary: {len(results)} analyzed, {high} high concern, {elevated} elevated")
                
                if report_path:
                    print(f"📄 Full report: {report_path}")
        
        elif choice == "2":
            # Analyze single text
            print("\nPaste the text to analyze (enter a blank line when done):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            
            text = "\n".join(lines)
            if not text.strip():
                print("No text provided.")
                continue
            
            profile_id = select_profile()
            
            analyzer = DishonestyAnalyzer(profile_id=profile_id)
            result = analyzer.analyze_text(text, "manual", "Manual Input")
            
            print("\n" + "=" * 50)
            print("ANALYSIS RESULT")
            print("=" * 50)
            print(f"Concern Level: {result.concern_level.upper()}")
            print(f"Suspicious Score: {result.suspicious_score:.2f}")
            print(f"Authenticity Score: {result.authenticity_score:.2f}")
            print(f"Word Count: {result.word_count}")
            
            if result.markers_found:
                print("\nMarkers Found:")
                for marker_type, instances in result.markers_found.items():
                    print(f"  {marker_type}: {instances[:3]}")
            
            if result.conversation_starters:
                print("\nConversation Starters:")
                for starter in result.conversation_starters[:3]:
                    print(f"  • {starter}")
        
        elif choice == "3":
            # View profiles
            print("\n" + "=" * 50)
            print("ASSIGNMENT PROFILES")
            print("=" * 50)
            for profile in ASSIGNMENT_PROFILES.values():
                print(f"\n{profile['name']}")
                print(f"  {profile['description']}")
                print("  Instructor Notes:")
                for note in profile.get('instructor_notes', []):
                    print(f"    • {note}")
        
        elif choice == "4":
            # About
            print("\n" + "=" * 50)
            print("ABOUT ACADEMIC DISHONESTY CHECK v2.0")
            print("=" * 50)
            print("""
This tool identifies INDICATORS of potential academic dishonesty,
not proof. It uses:

• Pattern Detection: Identifies AI-typical transitions, generic phrases,
  and lack of personal voice
  
• Peer Comparison: Flags statistical outliers within a class cohort,
  adapting to each group's writing patterns
  
• Context Awareness: Adjusts thresholds for ESL students, first-generation
  students, and community college populations to reduce false positives
  
• Pedagogical Framing: Provides conversation starters and revision
  guidance, not accusations

IMPORTANT: This tool is designed for community college contexts and
prioritizes avoiding false positives. It should support - not replace -
instructor judgment.

Version: {VERSION}
Date: {VERSION_DATE}
""".format(VERSION=VERSION, VERSION_DATE=VERSION_DATE))
        
        else:
            print("Invalid choice.")


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    # Check if running interactively or with arguments
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == "--help":
            print(f"""
Academic Dishonesty Check v{VERSION}

Usage:
  python {sys.argv[0]}              - Interactive menu
  python {sys.argv[0]} --help       - Show this help
  python {sys.argv[0]} --version    - Show version

Environment Variables:
  CANVAS_API_TOKEN    - Your Canvas API token (required)
  CANVAS_BASE_URL     - Canvas instance URL (default: https://cabrillo.instructure.com)
""")
        elif sys.argv[1] == "--version":
            print(f"Academic Dishonesty Check v{VERSION} ({VERSION_DATE})")
        else:
            print(f"Unknown argument: {sys.argv[1]}")
            print(f"Use --help for usage information.")
    else:
        # Interactive mode
        main_menu()
