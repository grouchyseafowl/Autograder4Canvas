"""
Marker Loader Module
Loads detection markers from YAML configuration files.
Applies context and profile adjustments to marker weights.
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class MarkerMatch:
    """A single marker match in text."""
    marker_id: str
    pattern: str
    matched_text: str
    position: int
    weight: float
    confidence: str  # high, medium, monitoring


@dataclass
class LoadedMarkers:
    """Collection of loaded markers with applied adjustments."""
    markers: Dict[str, Dict]  # marker_id -> marker config
    compiled_patterns: Dict[str, List[Tuple[re.Pattern, float, str]]]  # marker_id -> [(pattern, weight, confidence)]
    context_multipliers: Dict[str, float]  # marker_id -> multiplier
    profile_multipliers: Dict[str, float]  # marker_id -> multiplier
    

class MarkerLoader:
    """
    Loads and manages detection markers from YAML files.
    
    Handles:
    - Loading core and custom markers
    - Applying context profile adjustments
    - Applying assignment profile weights
    - Compiling regex patterns for efficient matching
    """
    
    def __init__(self, config_dir: Optional[Path] = None):
        """
        Initialize the marker loader.
        
        Args:
            config_dir: Path to configuration directory
        """
        self.config_dir = config_dir or self._get_default_config_dir()
        self.markers_dir = self.config_dir / "dishonesty_markers"
        self.profiles_dir = self.config_dir / "profiles"
        self.context_dir = self.config_dir / "context_profiles"
        
        self._loaded_markers: Optional[LoadedMarkers] = None
        self._context_profile: Optional[Dict] = None
        self._assignment_profile: Optional[Dict] = None
        
    def _get_default_config_dir(self) -> Path:
        """Get the default configuration directory."""
        import platform
        import os
        system = platform.system()
        
        if system == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "CanvasAutograder"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "CanvasAutograder"
        else:
            return Path.home() / ".config" / "CanvasAutograder"
    
    def load_all_markers(self, 
                         profile_id: str = "standard",
                         context_profile: str = "community_college") -> LoadedMarkers:
        """
        Load all markers with profile and context adjustments.
        
        Args:
            profile_id: Assignment profile to use
            context_profile: Context profile for population adjustments
            
        Returns:
            LoadedMarkers object with all markers and adjustments
        """
        if not HAS_YAML:
            raise ImportError("PyYAML is required for YAML marker loading")
        
        # Load context profile
        self._load_context_profile(context_profile)
        
        # Load assignment profile
        self._load_assignment_profile(profile_id)
        
        # Load core markers
        markers = {}
        core_dir = self.markers_dir / "core"
        if core_dir.exists():
            for yaml_file in core_dir.glob("*.yaml"):
                if yaml_file.name == "marker_manifest.yaml":
                    continue
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        marker_data = yaml.safe_load(f)
                        marker_id = marker_data.get('metadata', {}).get('marker_id', yaml_file.stem)
                        markers[marker_id] = marker_data
                except Exception as e:
                    print(f"Warning: Could not load marker {yaml_file.name}: {e}")
        
        # Load custom markers
        custom_dir = self.markers_dir / "custom"
        if custom_dir.exists():
            for yaml_file in custom_dir.glob("*.yaml"):
                try:
                    with open(yaml_file, 'r', encoding='utf-8') as f:
                        marker_data = yaml.safe_load(f)
                        marker_id = marker_data.get('metadata', {}).get('marker_id', yaml_file.stem)
                        markers[marker_id] = marker_data
                except Exception as e:
                    print(f"Warning: Could not load custom marker {yaml_file.name}: {e}")
        
        # Apply adjustments and compile patterns
        context_multipliers = self._get_context_multipliers(markers)
        profile_multipliers = self._get_profile_multipliers(markers)
        compiled_patterns = self._compile_patterns(markers, context_multipliers, profile_multipliers)
        
        self._loaded_markers = LoadedMarkers(
            markers=markers,
            compiled_patterns=compiled_patterns,
            context_multipliers=context_multipliers,
            profile_multipliers=profile_multipliers
        )
        
        return self._loaded_markers
    
    def _load_context_profile(self, profile_id: str):
        """Load a context profile."""
        profile_path = self.context_dir / f"{profile_id}.yaml"
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self._context_profile = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not load context profile: {e}")
                self._context_profile = None
    
    def _load_assignment_profile(self, profile_id: str):
        """Load an assignment profile."""
        profile_path = self.profiles_dir / f"{profile_id}.yaml"
        if profile_path.exists():
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    self._assignment_profile = yaml.safe_load(f)
            except Exception as e:
                print(f"Warning: Could not load assignment profile: {e}")
                self._assignment_profile = None
    
    def _get_context_multipliers(self, markers: Dict) -> Dict[str, float]:
        """Get context-based weight multipliers."""
        multipliers = {}
        
        if self._context_profile:
            marker_adjustments = self._context_profile.get('marker_adjustments', {})
            for marker_id, adjustment in marker_adjustments.items():
                if isinstance(adjustment, dict):
                    multipliers[marker_id] = adjustment.get('multiplier', 1.0)
                else:
                    multipliers[marker_id] = adjustment
        
        return multipliers
    
    def _get_profile_multipliers(self, markers: Dict) -> Dict[str, float]:
        """Get profile-based weight multipliers."""
        multipliers = {}
        
        if self._assignment_profile:
            weight_priorities = self._assignment_profile.get('weight_priorities', {})
            for marker_id, priority in weight_priorities.items():
                if isinstance(priority, dict):
                    multipliers[marker_id] = priority.get('multiplier', 1.0)
                else:
                    multipliers[marker_id] = priority
        
        return multipliers
    
    def _compile_patterns(self, 
                          markers: Dict,
                          context_mult: Dict[str, float],
                          profile_mult: Dict[str, float]) -> Dict[str, List[Tuple[re.Pattern, float, str]]]:
        """Compile regex patterns with adjusted weights."""
        compiled = {}
        
        for marker_id, marker_data in markers.items():
            patterns = []
            
            # Get base context and profile multipliers
            ctx_mult = context_mult.get(marker_id, 1.0)
            prof_mult = profile_mult.get(marker_id, 1.0)
            
            # Process each marker section
            marker_section = marker_data.get('markers', {})
            for confidence_level, items in marker_section.items():
                if not isinstance(items, list):
                    if isinstance(items, dict) and 'patterns' in items:
                        items = items['patterns']
                    else:
                        continue
                
                for item in items:
                    if isinstance(item, dict):
                        pattern_str = item.get('pattern', '')
                        base_weight = item.get('weight', 0.5)
                        is_regex = item.get('regex', False)
                    else:
                        pattern_str = str(item)
                        base_weight = 0.5
                        is_regex = False
                    
                    if not pattern_str:
                        continue
                    
                    # Apply multipliers
                    adjusted_weight = base_weight * ctx_mult * prof_mult
                    
                    # Compile pattern
                    try:
                        if is_regex:
                            regex = re.compile(pattern_str, re.IGNORECASE)
                        else:
                            # Escape and create word-boundary pattern
                            escaped = re.escape(pattern_str)
                            regex = re.compile(rf'\b{escaped}\b', re.IGNORECASE)
                        
                        patterns.append((regex, adjusted_weight, confidence_level))
                    except re.error as e:
                        print(f"Warning: Invalid pattern '{pattern_str}': {e}")
            
            if patterns:
                compiled[marker_id] = patterns
        
        return compiled
    
    def find_markers_in_text(self, text: str) -> List[MarkerMatch]:
        """
        Find all marker matches in text.
        
        Returns:
            List of MarkerMatch objects
        """
        if not self._loaded_markers:
            return []
        
        matches = []
        text_lower = text.lower()
        
        for marker_id, patterns in self._loaded_markers.compiled_patterns.items():
            for regex, weight, confidence in patterns:
                for match in regex.finditer(text):
                    matches.append(MarkerMatch(
                        marker_id=marker_id,
                        pattern=regex.pattern,
                        matched_text=match.group(),
                        position=match.start(),
                        weight=weight,
                        confidence=confidence
                    ))
        
        return matches
    
    def calculate_marker_scores(self, text: str) -> Dict[str, Any]:
        """
        Calculate suspicious and authenticity scores for text.

        Implements cognitive diversity protection:
        - When cognitive diversity markers are present, reduces weight of organizational bias markers
        - Provides transparency about which markers were flagged

        Returns:
            Dictionary with scores, marker counts, details, and transparency information
        """
        matches = self.find_markers_in_text(text)

        suspicious_score = 0.0
        authenticity_score = 0.0
        marker_counts = {}
        details = {}
        transparency_flags = []  # What was flagged for instructor review

        # Categorize markers
        # AI-SPECIFIC markers - NEVER receive cognitive protection
        ai_specific_markers = {'ai_specific_organization'}

        # OVERLAPPING markers - subject to cognitive protection when neurodivergent patterns present
        overlapping_organizational_markers = {'ai_transitions', 'generic_phrases', 'hedge_phrases', 'inflated_vocabulary'}

        # All suspicious markers (for scoring)
        suspicious_markers = ai_specific_markers | overlapping_organizational_markers

        # Authenticity markers (presence is good)
        authenticity_markers = {'personal_voice_markers', 'balance_markers', 'emotional_language', 'cognitive_diversity_markers'}

        # First pass: count all markers
        for match in matches:
            if match.marker_id not in marker_counts:
                marker_counts[match.marker_id] = 0
                details[match.marker_id] = {'matches': [], 'total_weight': 0}

            marker_counts[match.marker_id] += 1
            details[match.marker_id]['matches'].append({
                'phrase': match.matched_text,
                'weight': match.weight,
                'confidence': match.confidence
            })

        # Check for cognitive diversity protection
        cognitive_diversity_count = marker_counts.get('cognitive_diversity_markers', 0)
        cognitive_protection_active = False
        cognitive_protection_multiplier = 1.0

        if cognitive_diversity_count >= 2:
            cognitive_protection_active = True
            if cognitive_diversity_count >= 4:
                cognitive_protection_multiplier = 0.5  # Strong protection: 50% reduction
                transparency_flags.append({
                    'type': 'cognitive_diversity_protection',
                    'level': 'strong',
                    'description': f'{cognitive_diversity_count} cognitive diversity markers detected - reducing organizational bias weight by 50%'
                })
            else:
                cognitive_protection_multiplier = 0.7  # Moderate protection: 30% reduction
                transparency_flags.append({
                    'type': 'cognitive_diversity_protection',
                    'level': 'moderate',
                    'description': f'{cognitive_diversity_count} cognitive diversity markers detected - reducing organizational bias weight by 30%'
                })

        # Second pass: calculate scores with protection applied
        for match in matches:
            weight = match.weight

            # Apply cognitive diversity protection ONLY to overlapping markers, NOT AI-specific
            if cognitive_protection_active and match.marker_id in overlapping_organizational_markers:
                weight = weight * cognitive_protection_multiplier

            # AI-specific markers NEVER get protection
            # (no adjustment needed - they keep full weight)

            details[match.marker_id]['total_weight'] += weight

            # Add to appropriate score
            if match.marker_id in suspicious_markers:
                suspicious_score += weight
            elif match.marker_id in authenticity_markers:
                # Negative weights boost authenticity
                authenticity_score += abs(weight)

        # Apply clustering bonuses (also subject to cognitive protection)
        for marker_id, count in marker_counts.items():
            if count >= 3 and marker_id in suspicious_markers:
                marker_config = self._loaded_markers.markers.get(marker_id, {})
                clustering = marker_config.get('clustering', {})
                threshold = clustering.get('threshold', 3)
                boost = clustering.get('weight_boost', 2.0)

                if count >= threshold:
                    # Apply cognitive protection to clustering bonus for OVERLAPPING markers only
                    if cognitive_protection_active and marker_id in overlapping_organizational_markers:
                        boost = boost * cognitive_protection_multiplier
                    # AI-specific markers keep full clustering bonus (no protection)

                    suspicious_score += boost
                    transparency_flags.append({
                        'type': 'clustering_bonus',
                        'marker': marker_id,
                        'description': f'{count} {marker_id} markers in short text (clustering bonus applied)'
                    })

        # Generate transparency information about what was flagged
        if marker_counts.get('ai_transitions', 0) > 0:
            transparency_flags.append({
                'type': 'pattern_detected',
                'marker': 'ai_transitions',
                'count': marker_counts['ai_transitions'],
                'description': f'Formal transitions and academic phrasing detected ({marker_counts["ai_transitions"]} instances)'
            })

        if marker_counts.get('generic_phrases', 0) > 0:
            transparency_flags.append({
                'type': 'pattern_detected',
                'marker': 'generic_phrases',
                'count': marker_counts['generic_phrases'],
                'description': f'Generic or vague language detected ({marker_counts["generic_phrases"]} instances)'
            })

        if marker_counts.get('inflated_vocabulary', 0) > 0:
            transparency_flags.append({
                'type': 'pattern_detected',
                'marker': 'inflated_vocabulary',
                'count': marker_counts['inflated_vocabulary'],
                'description': f'Formal vocabulary usage detected ({marker_counts["inflated_vocabulary"]} instances)'
            })

        if marker_counts.get('hedge_phrases', 0) > 0:
            transparency_flags.append({
                'type': 'pattern_detected',
                'marker': 'hedge_phrases',
                'count': marker_counts['hedge_phrases'],
                'description': f'Hedging language detected ({marker_counts["hedge_phrases"]} instances)'
            })

        # Note positive indicators
        if marker_counts.get('personal_voice_markers', 0) > 0:
            transparency_flags.append({
                'type': 'positive_indicator',
                'marker': 'personal_voice_markers',
                'count': marker_counts['personal_voice_markers'],
                'description': f'Personal voice detected ({marker_counts["personal_voice_markers"]} instances) - positive indicator'
            })

        if marker_counts.get('balance_markers', 0) > 0:
            transparency_flags.append({
                'type': 'positive_indicator',
                'marker': 'balance_markers',
                'count': marker_counts['balance_markers'],
                'description': f'Intellectual uncertainty/rough edges detected ({marker_counts["balance_markers"]} instances) - positive indicator'
            })

        if marker_counts.get('emotional_language', 0) > 0:
            transparency_flags.append({
                'type': 'positive_indicator',
                'marker': 'emotional_language',
                'count': marker_counts['emotional_language'],
                'description': f'Emotional language detected ({marker_counts["emotional_language"]} instances) - positive indicator'
            })

        # AI-specific organizational markers (NOT protected by cognitive diversity)
        if marker_counts.get('ai_specific_organization', 0) > 0:
            transparency_flags.append({
                'type': 'ai_specific_pattern',
                'marker': 'ai_specific_organization',
                'count': marker_counts['ai_specific_organization'],
                'description': f'AI-specific organizational patterns detected ({marker_counts["ai_specific_organization"]} instances) - NOT subject to cognitive protection',
                'note': 'These patterns are AI signatures (excessive headers, perfect balance, etc.)'
            })

        return {
            'suspicious_score': round(suspicious_score, 2),
            'authenticity_score': round(authenticity_score, 2),
            'marker_counts': marker_counts,
            'details': details,
            'total_matches': len(matches),
            'cognitive_protection_active': cognitive_protection_active,
            'cognitive_protection_level': 'strong' if cognitive_diversity_count >= 4 else 'moderate' if cognitive_diversity_count >= 2 else 'none',
            'transparency_flags': transparency_flags
        }


def load_markers(config_dir: Optional[Path] = None,
                 profile_id: str = "standard",
                 context_profile: str = "community_college") -> Optional[LoadedMarkers]:
    """
    Convenience function to load markers.
    
    Returns:
        LoadedMarkers if successful, None if YAML not available
    """
    if not HAS_YAML:
        return None
    
    loader = MarkerLoader(config_dir)
    return loader.load_all_markers(profile_id, context_profile)
