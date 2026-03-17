"""
Assignment Configuration System
PHASE 7: Configurable assignment type profiles

This module loads and applies assignment-specific configurations to adjust
human presence detection and analysis based on assignment context.
"""

import yaml
import os
from typing import Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class AssignmentProfile:
    """Configuration profile for a specific assignment type."""
    name: str
    description: str
    expected_word_count: Tuple[int, int]
    marker_weight_adjustments: Dict[str, float]
    notes: str
    # v3.0 mode flags
    personal_voice_authentic: bool = True   # when False, personal voice ≠ authenticity signal
    invert_sentence_signals: bool = False   # when True (notes), smooth prose = suspicious


@dataclass
class CourseLevelConfig:
    """Configuration for course level adjustments."""
    name: str
    description: str
    suspicious_threshold_multiplier: float
    authenticity_boost: float
    notes: str


@dataclass
class InstitutionalContextConfig:
    """Configuration for institutional context adjustments."""
    name: str
    description: str
    suspicious_threshold_multiplier: float
    notes: str


class AssignmentConfigLoader:
    """
    Loads and manages assignment type configurations.

    PHASE 7: Allows instructors to configure analysis based on:
    - Assignment type (discussion, essay, reflection, etc.)
    - Course level (developmental, intro, advanced, etc.)
    - Institutional context (community college, liberal arts, etc.)
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.

        Args:
            config_path: Path to assignment_types.yaml. If None, uses default location.
        """
        if config_path is None:
            # Default: src/config/assignment_types.yaml
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, 'config', 'assignment_types.yaml')

        self.config_path = config_path
        self.config_data = {}
        self.assignment_profiles = {}
        self.course_levels = {}
        self.institutional_contexts = {}

        self._load_config()

    def _load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)

            # Load assignment type profiles
            for key, data in self.config_data.items():
                if key in ['version', 'last_updated', 'course_levels', 'institutional_contexts', 'default']:
                    continue

                self.assignment_profiles[key] = AssignmentProfile(
                    name=data.get('name', key),
                    description=data.get('description', ''),
                    expected_word_count=tuple(data.get('expected_word_count', [0, 10000])),
                    marker_weight_adjustments=data.get('marker_weight_adjustments', {}),
                    notes=data.get('notes', ''),
                    personal_voice_authentic=data.get('personal_voice_authentic', True),
                    invert_sentence_signals=data.get('invert_sentence_signals', False),
                )

            # Load course level configurations
            if 'course_levels' in self.config_data:
                for key, data in self.config_data['course_levels'].items():
                    adjustments = data.get('adjustments', {})
                    self.course_levels[key] = CourseLevelConfig(
                        name=data.get('name', key),
                        description=data.get('description', ''),
                        suspicious_threshold_multiplier=adjustments.get('suspicious_threshold_multiplier', 1.0),
                        authenticity_boost=adjustments.get('authenticity_boost', 1.0),
                        notes=adjustments.get('notes', '')
                    )

            # Load institutional context configurations
            if 'institutional_contexts' in self.config_data:
                for key, data in self.config_data['institutional_contexts'].items():
                    adjustments = data.get('adjustments', {})
                    self.institutional_contexts[key] = InstitutionalContextConfig(
                        name=data.get('name', key),
                        description=data.get('description', ''),
                        suspicious_threshold_multiplier=adjustments.get('suspicious_threshold_multiplier', 1.0),
                        notes=adjustments.get('notes', '')
                    )

        except FileNotFoundError:
            print(f"⚠ Warning: Configuration file not found at {self.config_path}")
            print("  Using default configuration")
        except yaml.YAMLError as e:
            print(f"⚠ Warning: Error parsing configuration file: {e}")
            print("  Using default configuration")

    def get_assignment_profile(self, profile_id: str) -> Optional[AssignmentProfile]:
        """
        Get assignment profile by ID.

        Args:
            profile_id: Assignment type identifier (e.g., 'discussion_post', 'research_paper')

        Returns:
            AssignmentProfile if found, None otherwise
        """
        return self.assignment_profiles.get(profile_id)

    def get_course_level_config(self, level_id: str) -> Optional[CourseLevelConfig]:
        """
        Get course level configuration by ID.

        Args:
            level_id: Course level identifier (e.g., 'introductory', 'advanced')

        Returns:
            CourseLevelConfig if found, None otherwise
        """
        return self.course_levels.get(level_id)

    def get_institutional_context_config(self, context_id: str) -> Optional[InstitutionalContextConfig]:
        """
        Get institutional context configuration by ID.

        Args:
            context_id: Context identifier (e.g., 'community_college', 'online')

        Returns:
            InstitutionalContextConfig if found, None otherwise
        """
        return self.institutional_contexts.get(context_id)

    def get_mode_flags(self, assignment_type: str) -> Tuple[bool, bool]:
        """
        Return (personal_voice_authentic, invert_sentence_signals) for a mode.
        Defaults to (True, False) when mode not found.
        """
        profile = self.get_assignment_profile(assignment_type)
        if profile:
            return profile.personal_voice_authentic, profile.invert_sentence_signals
        return True, False

    def get_marker_weight_adjustments(self, assignment_type: str) -> Dict[str, float]:
        """
        Get marker weight adjustments for a specific assignment type.

        Args:
            assignment_type: Assignment type identifier

        Returns:
            Dictionary of marker categories to weight multipliers
        """
        profile = self.get_assignment_profile(assignment_type)
        if profile:
            return profile.marker_weight_adjustments.copy()
        return {}

    def get_combined_multiplier(self,
                                course_level: Optional[str] = None,
                                institutional_context: Optional[str] = None) -> Tuple[float, float]:
        """
        Get combined multipliers from course level and institutional context.

        Args:
            course_level: Course level identifier
            institutional_context: Institutional context identifier

        Returns:
            (suspicious_multiplier, authenticity_boost)
        """
        suspicious_multiplier = 1.0
        authenticity_boost = 1.0

        # Apply course level adjustments
        if course_level:
            level_config = self.get_course_level_config(course_level)
            if level_config:
                suspicious_multiplier *= level_config.suspicious_threshold_multiplier
                authenticity_boost *= level_config.authenticity_boost

        # Apply institutional context adjustments
        if institutional_context:
            context_config = self.get_institutional_context_config(institutional_context)
            if context_config:
                suspicious_multiplier *= context_config.suspicious_threshold_multiplier

        return (suspicious_multiplier, authenticity_boost)

    def list_assignment_types(self) -> Dict[str, str]:
        """
        List all available assignment types.

        Returns:
            Dictionary mapping profile_id to name
        """
        return {key: profile.name for key, profile in self.assignment_profiles.items()}

    def list_course_levels(self) -> Dict[str, str]:
        """
        List all available course levels.

        Returns:
            Dictionary mapping level_id to name
        """
        return {key: level.name for key, level in self.course_levels.items()}

    def list_institutional_contexts(self) -> Dict[str, str]:
        """
        List all available institutional contexts.

        Returns:
            Dictionary mapping context_id to name
        """
        return {key: context.name for key, context in self.institutional_contexts.items()}

    def export_configuration(self, format: str = 'json') -> str:
        """
        Export current configuration to JSON or CSV format.

        Args:
            format: 'json' or 'csv'

        Returns:
            Formatted string representation
        """
        if format == 'json':
            import json
            export_data = {
                'assignment_types': {
                    key: {
                        'name': profile.name,
                        'description': profile.description,
                        'expected_word_count': profile.expected_word_count,
                        'marker_adjustments': profile.marker_weight_adjustments
                    }
                    for key, profile in self.assignment_profiles.items()
                },
                'course_levels': {
                    key: {
                        'name': level.name,
                        'description': level.description,
                        'suspicious_multiplier': level.suspicious_threshold_multiplier,
                        'authenticity_boost': level.authenticity_boost
                    }
                    for key, level in self.course_levels.items()
                },
                'institutional_contexts': {
                    key: {
                        'name': context.name,
                        'description': context.description,
                        'suspicious_multiplier': context.suspicious_threshold_multiplier
                    }
                    for key, context in self.institutional_contexts.items()
                }
            }
            return json.dumps(export_data, indent=2)

        elif format == 'csv':
            # Export assignment types as CSV
            lines = []
            lines.append("Assignment Types")
            lines.append("ID,Name,Description,Min Words,Max Words,Contextual,Emotional,Voice,Struggle,Messiness")

            for key, profile in self.assignment_profiles.items():
                adj = profile.marker_weight_adjustments
                lines.append(f"{key},{profile.name},{profile.description},"
                           f"{profile.expected_word_count[0]},{profile.expected_word_count[1]},"
                           f"{adj.get('contextual_grounding', 1.0)},"
                           f"{adj.get('emotional_stakes', 1.0)},"
                           f"{adj.get('authentic_voice', 1.0)},"
                           f"{adj.get('cognitive_struggle', 1.0)},"
                           f"{adj.get('productive_messiness', 1.0)}")

            lines.append("")
            lines.append("Course Levels")
            lines.append("ID,Name,Description,Suspicious Multiplier,Authenticity Boost")

            for key, level in self.course_levels.items():
                lines.append(f"{key},{level.name},{level.description},"
                           f"{level.suspicious_threshold_multiplier},{level.authenticity_boost}")

            return "\n".join(lines)

        else:
            raise ValueError(f"Unknown export format: {format}. Use 'json' or 'csv'")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_default_config_loader() -> AssignmentConfigLoader:
    """Get configuration loader with default settings."""
    return AssignmentConfigLoader()


def apply_assignment_config_to_detector(detector,
                                        assignment_type: Optional[str] = None,
                                        course_level: Optional[str] = None,
                                        institutional_context: Optional[str] = None):
    """
    Apply assignment configuration to a HumanPresenceDetector instance.

    Returns:
        (suspicious_multiplier, authenticity_boost, personal_voice_authentic, invert_sentence_signals)
    """
    config_loader = get_default_config_loader()

    # Apply marker weight adjustments
    if assignment_type:
        adjustments = config_loader.get_marker_weight_adjustments(assignment_type)
        if adjustments:
            for category, multiplier in adjustments.items():
                if hasattr(detector, 'CATEGORY_WEIGHTS') and category in detector.CATEGORY_WEIGHTS:
                    if not hasattr(detector, '_original_weights'):
                        detector._original_weights = detector.CATEGORY_WEIGHTS.copy()
                    detector.CATEGORY_WEIGHTS[category] = detector._original_weights[category] * multiplier

            total = sum(detector.CATEGORY_WEIGHTS.values())
            if total > 0:
                for key in detector.CATEGORY_WEIGHTS:
                    detector.CATEGORY_WEIGHTS[key] /= total

    multipliers = config_loader.get_combined_multiplier(course_level, institutional_context)
    pva, iss = config_loader.get_mode_flags(assignment_type or '')
    return multipliers[0], multipliers[1], pva, iss
