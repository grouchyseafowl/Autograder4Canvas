"""
AI Detection Markers Module
Loads and provides access to the comprehensive academic dishonesty detection dataset.

This module can be imported by the Academic_Dishonesty_Check script to access
the full marker database for detecting AI-generated student work.

Usage:
    from ai_detection_markers import AIDetectionMarkers
    
    markers = AIDetectionMarkers()
    
    # Get all transition phrases
    transitions = markers.get_markers('linguistic_patterns', 'ai_transition_phrases')
    
    # Check text against all naive-level markers
    flags = markers.analyze_text(text, detection_level='naive')
    
    # Get assignment-specific markers
    reflection_markers = markers.get_assignment_markers('personal_reflection')
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict


class AIDetectionMarkers:
    """
    Provides access to AI detection markers and analysis utilities.
    """
    
    def __init__(self, markers_file: Optional[Path] = None):
        """
        Initialize the markers database.
        
        Args:
            markers_file: Path to the JSON markers file. If None, looks in same directory.
        """
        if markers_file is None:
            # Look for markers file in same directory as this module
            markers_file = Path(__file__).parent / "ai_detection_markers.json"
        
        self.markers_file = Path(markers_file)
        self._data = None
        self._compiled_patterns = {}
        
    def _load_data(self) -> Dict:
        """Load the markers data from JSON file."""
        if self._data is None:
            if not self.markers_file.exists():
                raise FileNotFoundError(f"Markers file not found: {self.markers_file}")
            
            with open(self.markers_file, 'r', encoding='utf-8') as f:
                self._data = json.load(f)
        
        return self._data
    
    @property
    def data(self) -> Dict:
        """Access the raw markers data."""
        return self._load_data()
    
    def get_categories(self) -> List[str]:
        """Get all detection category names."""
        return list(self.data.get('detection_categories', {}).keys())
    
    def get_markers(self, category: str, marker_type: str) -> Dict[str, Any]:
        """
        Get markers for a specific category and type.
        
        Args:
            category: e.g., 'linguistic_patterns', 'structural_patterns'
            marker_type: e.g., 'ai_transition_phrases', 'hedge_phrases'
            
        Returns:
            Dictionary containing the marker definition
        """
        categories = self.data.get('detection_categories', {})
        if category not in categories:
            raise KeyError(f"Unknown category: {category}")
        
        cat_data = categories[category]
        if marker_type not in cat_data:
            raise KeyError(f"Unknown marker type '{marker_type}' in category '{category}'")
        
        return cat_data[marker_type]
    
    def get_marker_list(self, category: str, marker_type: str) -> List[str]:
        """
        Get just the list of marker strings for a category/type.
        
        Returns:
            List of marker strings (phrases or patterns)
        """
        marker_data = self.get_markers(category, marker_type)
        markers = marker_data.get('markers', [])
        
        # Handle different marker formats
        if markers and isinstance(markers[0], dict):
            # Extract the relevant field (e.g., 'inflated' for vocabulary)
            if 'inflated' in markers[0]:
                return [m['inflated'] for m in markers]
            elif 'pattern' in markers[0]:
                return [m['pattern'] for m in markers]
            elif 'name' in markers[0]:
                return [m['name'] for m in markers]
        
        return markers
    
    def get_all_phrase_markers(self, detection_level: Optional[str] = None) -> Dict[str, List[str]]:
        """
        Get all phrase-based markers, optionally filtered by detection level.
        
        Args:
            detection_level: 'naive', 'intermediate', 'advanced', or None for all
            
        Returns:
            Dictionary mapping marker type to list of phrases
        """
        result = {}
        categories = self.data.get('detection_categories', {})
        
        for cat_name, cat_data in categories.items():
            for marker_name, marker_data in cat_data.items():
                if not isinstance(marker_data, dict):
                    continue
                
                # Check detection level filter
                if detection_level:
                    marker_level = marker_data.get('detection_level', '')
                    if detection_level not in marker_level and marker_level != 'all_levels':
                        continue
                
                # Get markers if they exist
                markers = marker_data.get('markers', [])
                if markers:
                    key = f"{cat_name}.{marker_name}"
                    if isinstance(markers[0], str):
                        result[key] = markers
                    elif isinstance(markers[0], dict) and 'inflated' in markers[0]:
                        result[key] = [m['inflated'] for m in markers]
        
        return result
    
    def compile_pattern(self, phrase: str, word_boundary: bool = True) -> re.Pattern:
        """
        Compile a phrase into a regex pattern with caching.
        
        Args:
            phrase: The phrase to compile
            word_boundary: Whether to add word boundaries
            
        Returns:
            Compiled regex pattern
        """
        cache_key = (phrase, word_boundary)
        
        if cache_key not in self._compiled_patterns:
            if word_boundary:
                pattern = r'\b' + re.escape(phrase) + r'\b'
            else:
                pattern = re.escape(phrase)
            
            self._compiled_patterns[cache_key] = re.compile(pattern, re.IGNORECASE)
        
        return self._compiled_patterns[cache_key]
    
    def count_phrase_occurrences(self, text: str, phrases: List[str]) -> Dict[str, int]:
        """
        Count occurrences of each phrase in text.
        
        Args:
            text: Text to analyze
            phrases: List of phrases to look for
            
        Returns:
            Dictionary mapping phrase to count
        """
        results = {}
        text_lower = text.lower()
        
        for phrase in phrases:
            pattern = self.compile_pattern(phrase)
            matches = pattern.findall(text_lower)
            if matches:
                results[phrase] = len(matches)
        
        return results
    
    def analyze_text(self, text: str, detection_level: str = 'all') -> Dict[str, Any]:
        """
        Analyze text against all markers at specified detection level.
        
        Args:
            text: Text to analyze
            detection_level: 'naive', 'intermediate', 'advanced', 'all'
            
        Returns:
            Dictionary containing analysis results
        """
        results = {
            'flags': [],
            'scores': defaultdict(float),
            'details': {},
            'word_count': len(text.split()),
            'sentence_count': len(re.findall(r'[.!?]+', text))
        }
        
        # Get all phrase markers for this level
        phrase_markers = self.get_all_phrase_markers(
            detection_level if detection_level != 'all' else None
        )
        
        for marker_key, phrases in phrase_markers.items():
            occurrences = self.count_phrase_occurrences(text, phrases)
            
            if occurrences:
                total = sum(occurrences.values())
                results['details'][marker_key] = {
                    'count': total,
                    'matches': occurrences
                }
                
                # Get threshold info
                category, marker_type = marker_key.split('.', 1)
                try:
                    marker_data = self.get_markers(category, marker_type)
                    threshold = marker_data.get('threshold', {})
                    threshold_count = threshold.get('count', 3)
                    
                    if total >= threshold_count:
                        flag_msg = threshold.get('flag_message', f'{marker_type}: {total} instances')
                        flag_msg = flag_msg.replace('{count}', str(total))
                        results['flags'].append({
                            'type': marker_key,
                            'message': flag_msg,
                            'count': total,
                            'confidence': marker_data.get('confidence', 'medium')
                        })
                except KeyError:
                    pass
        
        # Check for absence of authenticity markers
        self._check_authenticity_absence(text, results)
        
        # Check structural patterns
        self._check_structural_patterns(text, results)
        
        return results
    
    def _check_authenticity_absence(self, text: str, results: Dict):
        """Check for absence of authenticity markers."""
        text_lower = text.lower()
        
        # Personal voice check
        personal_markers = self.get_markers('authenticity_markers', 'personal_voice_indicators')
        positive_patterns = personal_markers.get('positive_markers', [])
        
        found_personal = False
        for pattern in positive_patterns:
            if re.search(pattern, text_lower):
                found_personal = True
                break
        
        if not found_personal and results['word_count'] > 100:
            results['flags'].append({
                'type': 'authenticity_markers.personal_voice_indicators',
                'message': personal_markers.get('absence_flag', 'Lacks personal voice'),
                'confidence': 'high'
            })
        
        # Emotional language check
        emotional_markers = self.get_markers('authenticity_markers', 'emotional_vulnerability')
        emotional_words = emotional_markers.get('positive_markers', [])
        
        found_emotional = any(word in text_lower for word in emotional_words)
        
        if not found_emotional and results['word_count'] > 100:
            results['flags'].append({
                'type': 'authenticity_markers.emotional_vulnerability',
                'message': emotional_markers.get('absence_flag', 'No emotional language'),
                'confidence': 'high'
            })
    
    def _check_structural_patterns(self, text: str, results: Dict):
        """Check structural patterns in text."""
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]
        
        if len(sentences) < 5:
            return
        
        # Check sentence length uniformity
        lengths = [len(s.split()) for s in sentences]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            std_dev = variance ** 0.5
            
            if std_dev < 4 and avg_len > 10:
                results['flags'].append({
                    'type': 'structural_patterns.sentence_uniformity',
                    'message': f'Abnormally uniform sentence lengths (std dev: {std_dev:.1f})',
                    'confidence': 'medium'
                })
        
        # Check complete sentence ratio
        complete = sum(1 for s in sentences if self._is_complete_sentence(s))
        ratio = complete / len(sentences) if sentences else 0
        
        if ratio > 0.80 and len(sentences) > 5:
            results['flags'].append({
                'type': 'structural_patterns.complete_sentence_ratio',
                'message': f'Suspiciously polished ({int(ratio*100)}% complete sentences)',
                'confidence': 'medium'
            })
    
    def _is_complete_sentence(self, sentence: str) -> bool:
        """Check if a sentence is grammatically complete."""
        sentence = sentence.strip()
        if not sentence:
            return False
        
        # Simple heuristic: has subject-like start and reasonable length
        words = sentence.split()
        if len(words) < 3:
            return False
        
        # Check for common sentence starters
        first_word = words[0].lower()
        subject_starters = ['i', 'we', 'you', 'he', 'she', 'it', 'they', 'the', 'a', 'an', 
                          'this', 'that', 'these', 'those', 'my', 'our', 'your', 'his', 
                          'her', 'its', 'their', 'there', 'here', 'what', 'which', 'who',
                          'when', 'where', 'why', 'how', 'if', 'although', 'because',
                          'since', 'while', 'after', 'before', 'as', 'so', 'but', 'and',
                          'however', 'therefore', 'furthermore', 'moreover', 'in', 'on',
                          'at', 'for', 'with', 'to', 'from', 'by', 'about', 'into']
        
        return first_word in subject_starters or first_word[0].isupper()
    
    def get_assignment_markers(self, assignment_type: str) -> Dict[str, Any]:
        """
        Get markers specific to an assignment type.
        
        Args:
            assignment_type: 'personal_reflection', 'analytical_essay', 'research_paper', 
                           'discussion_post', 'creative_writing'
                           
        Returns:
            Dictionary with required/suspicious markers for that type
        """
        type_specific = self.data.get('detection_categories', {}).get('assignment_type_specific', {})
        
        if assignment_type not in type_specific:
            return {}
        
        return type_specific[assignment_type]
    
    def get_detection_strategy(self, user_level: str) -> Dict[str, Any]:
        """
        Get the detection strategy for a user sophistication level.
        
        Args:
            user_level: 'naive', 'intermediate', 'advanced', 'very_advanced'
            
        Returns:
            Strategy dictionary with markers and thresholds
        """
        strategies = self.data.get('detection_strategies', {})
        key_map = {
            'naive': 'naive_user_detection',
            'intermediate': 'intermediate_user_detection',
            'advanced': 'advanced_user_detection',
            'very_advanced': 'very_advanced_user_detection'
        }
        
        strategy_key = key_map.get(user_level)
        if strategy_key and strategy_key in strategies:
            return strategies[strategy_key]
        
        return {}
    
    def get_scoring_weights(self) -> Dict[str, float]:
        """Get the scoring weights for different marker categories."""
        return self.data.get('scoring_weights', {})
    
    def get_false_positive_considerations(self) -> Dict[str, Any]:
        """Get factors to consider for avoiding false positives."""
        return self.data.get('false_positive_considerations', {})
    
    def calculate_suspicion_score(self, analysis_results: Dict[str, Any]) -> Tuple[float, str]:
        """
        Calculate an overall suspicion score from analysis results.
        
        Args:
            analysis_results: Results from analyze_text()
            
        Returns:
            Tuple of (score, level) where level is 'low', 'medium', 'high', 'very_high'
        """
        weights = self.get_scoring_weights()
        score = 0.0
        
        for flag in analysis_results.get('flags', []):
            flag_type = flag.get('type', '')
            confidence = flag.get('confidence', 'medium')
            
            # Get category from flag type
            category = flag_type.split('.')[0] if '.' in flag_type else flag_type
            
            # Base weight from category
            base_weight = 1.0
            for weight_key, weight_val in weights.items():
                if weight_key in category or weight_key in flag_type:
                    base_weight = weight_val
                    break
            
            # Confidence multiplier
            confidence_mult = {'low': 0.5, 'medium': 1.0, 'high': 1.5, 'very_high': 2.0}
            mult = confidence_mult.get(confidence, 1.0)
            
            score += base_weight * mult
        
        # Determine level
        if score < 2:
            level = 'low'
        elif score < 5:
            level = 'medium'
        elif score < 10:
            level = 'high'
        else:
            level = 'very_high'
        
        return score, level


def create_default_markers_file(output_path: Path):
    """
    Create the default markers JSON file.
    
    This function can be called to regenerate the markers file if needed.
    """
    # This would contain the full JSON structure - for now, just note that
    # the ai_detection_markers.json file should be in the same directory
    print(f"Markers file should be placed at: {output_path}")
    print("Use the ai_detection_markers.json file provided with this module.")


# Convenience functions for quick access
def load_markers(markers_file: Optional[Path] = None) -> AIDetectionMarkers:
    """Load and return an AIDetectionMarkers instance."""
    return AIDetectionMarkers(markers_file)


def quick_analyze(text: str, markers_file: Optional[Path] = None) -> Dict[str, Any]:
    """Quick analysis of text using default settings."""
    markers = AIDetectionMarkers(markers_file)
    return markers.analyze_text(text)


if __name__ == '__main__':
    # Demo usage
    import sys
    
    print("AI Detection Markers Module")
    print("=" * 50)
    
    try:
        markers = AIDetectionMarkers()
        
        print(f"\nLoaded markers from: {markers.markers_file}")
        print(f"\nAvailable categories:")
        for cat in markers.get_categories():
            print(f"  - {cat}")
        
        # Demo analysis
        sample_text = """
        It is important to note that in today's society, many individuals utilize 
        various methodologies to demonstrate their understanding of complex topics. 
        Furthermore, research indicates that this multifaceted approach can facilitate 
        better learning outcomes. On the one hand, some scholars argue that traditional 
        methods remain optimal. On the other hand, others contend that innovative 
        strategies are of paramount importance. In conclusion, it is clear that both 
        perspectives have merit, and a balanced approach is recommended.
        """
        
        print(f"\n\nSample Analysis:")
        print("-" * 50)
        results = markers.analyze_text(sample_text)
        
        print(f"Word count: {results['word_count']}")
        print(f"Flags found: {len(results['flags'])}")
        
        for flag in results['flags']:
            print(f"  - [{flag['confidence']}] {flag['message']}")
        
        score, level = markers.calculate_suspicion_score(results)
        print(f"\nSuspicion score: {score:.1f} ({level})")
        
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Make sure ai_detection_markers.json is in the same directory.")
        sys.exit(1)
