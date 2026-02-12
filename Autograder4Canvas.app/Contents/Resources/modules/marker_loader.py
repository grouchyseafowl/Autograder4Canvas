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
        
        Returns:
            Dictionary with scores, marker counts, and details
        """
        matches = self.find_markers_in_text(text)
        
        suspicious_score = 0.0
        authenticity_score = 0.0
        marker_counts = {}
        details = {}
        
        # Categorize markers
        suspicious_markers = {'ai_transitions', 'generic_phrases', 'hedge_phrases', 'inflated_vocabulary'}
        authenticity_markers = {'personal_voice_markers'}
        
        for match in matches:
            # Count markers
            if match.marker_id not in marker_counts:
                marker_counts[match.marker_id] = 0
                details[match.marker_id] = {'matches': [], 'total_weight': 0}
            
            marker_counts[match.marker_id] += 1
            details[match.marker_id]['matches'].append({
                'phrase': match.matched_text,
                'weight': match.weight,
                'confidence': match.confidence
            })
            details[match.marker_id]['total_weight'] += match.weight
            
            # Add to appropriate score
            if match.marker_id in suspicious_markers:
                suspicious_score += match.weight
            elif match.marker_id in authenticity_markers:
                authenticity_score += match.weight
        
        # Apply clustering bonuses
        for marker_id, count in marker_counts.items():
            if count >= 3 and marker_id in suspicious_markers:
                # Check if markers specify clustering rules
                marker_config = self._loaded_markers.markers.get(marker_id, {})
                clustering = marker_config.get('clustering', {})
                threshold = clustering.get('threshold', 3)
                boost = clustering.get('weight_boost', 2.0)
                
                if count >= threshold:
                    suspicious_score += boost
        
        return {
            'suspicious_score': round(suspicious_score, 2),
            'authenticity_score': round(authenticity_score, 2),
            'marker_counts': marker_counts,
            'details': details,
            'total_matches': len(matches)
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
