"""
Context Analyzer Module
Population-aware adjustments for diverse student populations.
Reduces false positives for ESL, first-generation, and neurodivergent students.
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from pathlib import Path

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class ContextAdjustment:
    """Represents an adjustment applied based on context."""
    adjustment_type: str  # 'esl', 'first_gen', 'neurodivergent', 'institution'
    marker_id: str
    original_weight: float
    adjusted_weight: float
    multiplier: float
    rationale: str


@dataclass
class StudentContext:
    """Context information about a student or submission."""
    is_esl: bool = False
    is_first_gen: bool = False
    is_neurodivergent: bool = False
    is_non_traditional: bool = False
    institution_type: str = "community_college"
    
    # Inferred from text analysis
    has_esl_error_patterns: bool = False
    has_first_gen_patterns: bool = False
    
    # Additional context
    notes: List[str] = field(default_factory=list)


@dataclass 
class ContextAnalysisResult:
    """Result of context-aware analysis."""
    context: StudentContext
    adjustments_applied: List[ContextAdjustment]
    adjusted_weights: Dict[str, float]
    context_notes: List[str]
    false_positive_warnings: List[str]


class ContextAnalyzer:
    """
    Analyzes student context and applies appropriate adjustments.
    
    Philosophy:
    Community college populations include high proportions of ESL and
    first-generation students. Patterns that look like AI markers may
    actually be legitimate learned structures from:
    - ESL grammar instruction
    - Developmental English classes
    - Translation tool usage
    - Writing center templates
    
    This analyzer:
    1. Detects context clues in the text itself (ESL error patterns)
    2. Applies population-level adjustments based on institution type
    3. Explains each adjustment in the output
    """
    
    # Default context profile (community college)
    DEFAULT_PROFILE = {
        'marker_adjustments': {
            'ai_transitions': {'multiplier': 0.7, 'rationale': 'ESL students learn formal transitions in grammar classes'},
            'inflated_vocabulary': {'multiplier': 0.67, 'rationale': 'Thesaurus use is legitimate language learning'},
            'grammatical_perfection': {'multiplier': 0.3, 'rationale': 'Grammar checkers are widely used and often required'},
            'formal_essay_structure': {'multiplier': 0.5, 'rationale': 'Five-paragraph structure is taught in developmental English'},
            'personal_voice': {'multiplier': 0.8, 'rationale': 'ESL/first-gen students may have less confident academic voice'},
        },
        'threshold_adjustments': {
            'flag_concern_level': 4.0,  # Higher than standard 3.0
            'percentile': 95,  # Flag only top 5%, not top 10%
            'minimum_markers': 3,  # Require 3 marker types, not 2
        },
        'esl_error_patterns': [
            r'\b(is|are|was|were)\s+\w+ing\b.*\byesterday\b',  # Tense mixing
            r'\bthe\s+\w+s\s+(is|was)\b',  # Plural subject + singular verb
            r'\bmany\s+(information|advice|knowledge)s?\b',  # Uncountable as countable
            r'\bin\s+\d{4}\s+year\b',  # "in 2020 year"
            r'\bsince\s+\d+\s+years?\b',  # "since 5 years"
        ]
    }
    
    def __init__(self, context_profile_path: Optional[Path] = None):
        """
        Initialize the context analyzer.
        
        Args:
            context_profile_path: Path to YAML context profile
        """
        self.profile = self._load_profile(context_profile_path)
    
    def _load_profile(self, profile_path: Optional[Path]) -> Dict:
        """Load context profile from YAML or use defaults."""
        if profile_path and profile_path.exists() and HAS_YAML:
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not load context profile: {e}")
        
        return self.DEFAULT_PROFILE
    
    def analyze_context(self, 
                        text: str,
                        known_context: Optional[StudentContext] = None) -> ContextAnalysisResult:
        """
        Analyze context and determine appropriate adjustments.
        
        Args:
            text: The submission text
            known_context: Any known context about the student
            
        Returns:
            ContextAnalysisResult with adjustments and explanations
        """
        import re
        
        # Start with known context or create new
        context = known_context or StudentContext()
        
        # Detect ESL patterns in text
        esl_patterns_found = []
        for pattern in self.profile.get('esl_error_patterns', self.DEFAULT_PROFILE['esl_error_patterns']):
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    esl_patterns_found.append(pattern)
            except re.error:
                pass
        
        if esl_patterns_found:
            context.has_esl_error_patterns = True
            context.notes.append(f"ESL error patterns detected ({len(esl_patterns_found)} types)")
        
        # Detect first-gen patterns (formulaic structure)
        first_gen_indicators = self._detect_first_gen_patterns(text)
        if first_gen_indicators:
            context.has_first_gen_patterns = True
            context.notes.append(f"Formulaic structure detected ({len(first_gen_indicators)} indicators)")
        
        # Calculate adjustments
        adjustments = []
        adjusted_weights = {}
        context_notes = []
        false_positive_warnings = []
        
        marker_adjustments = self.profile.get('marker_adjustments', self.DEFAULT_PROFILE['marker_adjustments'])
        
        for marker_id, adjustment_config in marker_adjustments.items():
            multiplier = adjustment_config.get('multiplier', 1.0)
            rationale = adjustment_config.get('rationale', '')
            
            # Base institution adjustment
            adjusted_weights[marker_id] = multiplier
            
            adjustment = ContextAdjustment(
                adjustment_type='institution',
                marker_id=marker_id,
                original_weight=1.0,
                adjusted_weight=multiplier,
                multiplier=multiplier,
                rationale=rationale
            )
            adjustments.append(adjustment)
            
            # Additional ESL adjustment if patterns detected
            if context.has_esl_error_patterns and marker_id in ['ai_transitions', 'inflated_vocabulary']:
                esl_multiplier = 0.8  # Additional 20% reduction
                adjusted_weights[marker_id] *= esl_multiplier
                
                esl_adjustment = ContextAdjustment(
                    adjustment_type='esl_detected',
                    marker_id=marker_id,
                    original_weight=multiplier,
                    adjusted_weight=adjusted_weights[marker_id],
                    multiplier=esl_multiplier,
                    rationale="ESL error patterns in text suggest human author"
                )
                adjustments.append(esl_adjustment)
                
                false_positive_warnings.append(
                    f"ESL patterns detected: {marker_id} weight reduced to avoid false positive"
                )
        
        # Build context notes
        if context.has_esl_error_patterns:
            context_notes.append(
                "ESL error patterns detected in text. These errors (article usage, "
                "tense mixing, etc.) are strong indicators of human authorship, as "
                "AI models typically don't make these mistakes."
            )
        
        if context.has_first_gen_patterns:
            context_notes.append(
                "Formulaic essay structure detected (explicit topic sentences, "
                "transition words). This is commonly taught in developmental English "
                "and should not be considered suspicious."
            )
        
        if context.institution_type == 'community_college':
            context_notes.append(
                "Community college context applied: Higher thresholds account for "
                "diverse student populations with varying English proficiency and "
                "academic preparation."
            )
        
        return ContextAnalysisResult(
            context=context,
            adjustments_applied=adjustments,
            adjusted_weights=adjusted_weights,
            context_notes=context_notes,
            false_positive_warnings=false_positive_warnings
        )
    
    def _detect_first_gen_patterns(self, text: str) -> List[str]:
        """Detect patterns common in first-generation college student writing."""
        patterns_found = []
        
        # Check for explicit five-paragraph structure
        paragraphs = text.split('\n\n')
        if len(paragraphs) >= 3:
            # Check for formulaic intro/body/conclusion
            first_para = paragraphs[0].lower()
            last_para = paragraphs[-1].lower()
            
            intro_markers = ['in this essay', 'this paper will', 'i will discuss', 'i am going to']
            if any(marker in first_para for marker in intro_markers):
                patterns_found.append('formulaic_introduction')
            
            conclusion_markers = ['in conclusion', 'to conclude', 'in summary', 'to sum up']
            if any(marker in last_para for marker in conclusion_markers):
                patterns_found.append('formulaic_conclusion')
        
        # Check for explicit transition words at paragraph starts
        transition_starters = ['firstly', 'secondly', 'thirdly', 'furthermore', 'moreover', 'additionally']
        for para in paragraphs[1:-1] if len(paragraphs) > 2 else []:
            first_word = para.split()[0].lower() if para.split() else ''
            if first_word.rstrip(',') in transition_starters:
                patterns_found.append('explicit_paragraph_transition')
                break
        
        return patterns_found
    
    def get_threshold_adjustments(self) -> Dict[str, Any]:
        """Get threshold adjustments for this context."""
        return self.profile.get('threshold_adjustments', self.DEFAULT_PROFILE['threshold_adjustments'])
    
    def format_context_notes(self, result: ContextAnalysisResult) -> str:
        """Format context notes for inclusion in report."""
        lines = []
        
        if result.context_notes:
            lines.append("CONTEXT ADJUSTMENTS APPLIED:")
            lines.append("-" * 40)
            for note in result.context_notes:
                lines.append(f"• {note}")
            lines.append("")
        
        if result.false_positive_warnings:
            lines.append("FALSE POSITIVE AWARENESS:")
            lines.append("-" * 40)
            for warning in result.false_positive_warnings:
                lines.append(f"⚠ {warning}")
            lines.append("")
        
        return "\n".join(lines)


def analyze_student_context(text: str,
                           context_profile: str = "community_college",
                           known_context: Optional[StudentContext] = None) -> ContextAnalysisResult:
    """
    Convenience function to analyze student context.
    
    Args:
        text: Submission text
        context_profile: Profile ID or path
        known_context: Any known student information
        
    Returns:
        ContextAnalysisResult
    """
    analyzer = ContextAnalyzer()
    return analyzer.analyze_context(text, known_context)
