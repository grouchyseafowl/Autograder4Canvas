"""
Demographic Collector Module
Version 2.0.0

Collects institutional demographic data for context-aware analysis.
Provides three ways to gather demographic information:
1. Automatic API Integration - Fetch from Canvas (if available)
2. Manual Input - User enters demographics for their institution  
3. National Averages - Default to typical community college demographics

This data is used ONLY for:
- Adjusting marker weights appropriately
- Reducing false positives for diverse learners
- Improving accuracy for specific student populations

This data is NOT shared externally or used for any purpose other than
improving analysis accuracy.
"""

import os
import json
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict


# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class DemographicData:
    """Core demographic data for an institution."""
    
    # Basic info
    institution_id: str = ""
    institution_type: str = "community_college"  # community_college, university, etc.
    data_source: str = "national_average"  # manual_input, canvas_api, national_average
    last_updated: str = ""
    academic_year: str = ""
    
    # Key demographics (percentages)
    esl_learners: float = 35.0
    first_generation: float = 55.0
    disability_services: float = 12.0
    pell_recipients: float = 55.0
    working_students: float = 70.0
    working_full_time: float = 25.0
    
    # Age distribution
    traditional_age_18_24: float = 55.0
    adult_25_39: float = 30.0
    mature_40_plus: float = 15.0
    
    # Confidence in data
    confidence: str = "estimated"  # high, medium, low, estimated
    notes: str = ""


@dataclass
class MarkerAdjustments:
    """Calculated marker weight adjustments based on demographics."""
    
    ai_transitions: float = 1.0
    inflated_vocabulary: float = 1.0
    grammatical_perfection: float = 1.0
    formal_essay_structure: float = 1.0
    personal_voice_markers: float = 1.0
    generic_phrases: float = 1.0
    hedge_phrases: float = 1.0
    
    # Threshold adjustments
    flag_concern_level: float = 3.0  # Points needed to flag
    peer_comparison_percentile: float = 90.0  # Flag top X%
    
    # Rationale for adjustments
    rationale: List[str] = field(default_factory=list)


@dataclass
class InstitutionProfile:
    """Complete institution profile with demographics and adjustments."""
    
    demographics: DemographicData
    adjustments: MarkerAdjustments
    created_date: str = ""
    version: str = "2.0"


# =============================================================================
# NATIONAL AVERAGES
# =============================================================================

NATIONAL_AVERAGES = {
    'community_college': DemographicData(
        institution_type='community_college',
        data_source='national_average',
        esl_learners=35.0,
        first_generation=55.0,
        disability_services=12.0,
        pell_recipients=55.0,
        working_students=70.0,
        working_full_time=25.0,
        traditional_age_18_24=55.0,
        adult_25_39=30.0,
        mature_40_plus=15.0,
        confidence='national_average',
        notes='Based on AACC national data'
    ),
    'public_university': DemographicData(
        institution_type='public_university',
        data_source='national_average',
        esl_learners=15.0,
        first_generation=35.0,
        disability_services=10.0,
        pell_recipients=35.0,
        working_students=50.0,
        working_full_time=15.0,
        traditional_age_18_24=75.0,
        adult_25_39=18.0,
        mature_40_plus=7.0,
        confidence='national_average',
        notes='Based on national averages for public 4-year institutions'
    ),
    'private_university': DemographicData(
        institution_type='private_university',
        data_source='national_average',
        esl_learners=12.0,
        first_generation=25.0,
        disability_services=10.0,
        pell_recipients=20.0,
        working_students=40.0,
        working_full_time=10.0,
        traditional_age_18_24=85.0,
        adult_25_39=12.0,
        mature_40_plus=3.0,
        confidence='national_average',
        notes='Based on national averages for private 4-year institutions'
    )
}


# =============================================================================
# DEMOGRAPHIC COLLECTOR CLASS
# =============================================================================

class DemographicCollector:
    """
    Collects and manages institutional demographic data.
    """
    
    def __init__(self, config_dir: Path = None, canvas_url: str = None, 
                 canvas_token: str = None):
        """
        Initialize demographic collector.
        
        Args:
            config_dir: Configuration directory
            canvas_url: Canvas instance URL (optional)
            canvas_token: Canvas API token (optional)
        """
        if config_dir is None:
            config_dir = self._get_config_dir()
        
        self.config_dir = Path(config_dir)
        self.profiles_dir = self.config_dir / "institution_profiles"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self.canvas_url = canvas_url
        self.canvas_token = canvas_token
        
        self._current_profile: Optional[InstitutionProfile] = None
    
    def _get_config_dir(self) -> Path:
        """Get platform-appropriate config directory."""
        system = platform.system()
        
        if system == "Windows":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
            return base / "CanvasAutograder"
        elif system == "Darwin":
            return Path.home() / "Library" / "Application Support" / "CanvasAutograder"
        else:
            return Path.home() / ".config" / "CanvasAutograder"
    
    # =========================================================================
    # PROFILE MANAGEMENT
    # =========================================================================
    
    def get_current_profile(self) -> Optional[InstitutionProfile]:
        """Get the currently loaded institution profile."""
        if self._current_profile is not None:
            return self._current_profile
        
        # Try to load default profile
        default_path = self.profiles_dir / "current_institution.json"
        if default_path.exists():
            return self.load_profile("current_institution")
        
        return None
    
    def load_profile(self, profile_id: str) -> Optional[InstitutionProfile]:
        """Load an institution profile from disk."""
        profile_path = self.profiles_dir / f"{profile_id}.json"
        
        if not profile_path.exists():
            return None
        
        try:
            with open(profile_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            demographics = DemographicData(**data.get('demographics', {}))
            adjustments = MarkerAdjustments(**data.get('adjustments', {}))
            
            self._current_profile = InstitutionProfile(
                demographics=demographics,
                adjustments=adjustments,
                created_date=data.get('created_date', ''),
                version=data.get('version', '2.0')
            )
            
            return self._current_profile
        
        except Exception as e:
            print(f"Error loading profile: {e}")
            return None
    
    def save_profile(self, profile: InstitutionProfile, profile_id: str = "current_institution"):
        """Save an institution profile to disk."""
        profile_path = self.profiles_dir / f"{profile_id}.json"
        
        data = {
            'demographics': asdict(profile.demographics),
            'adjustments': asdict(profile.adjustments),
            'created_date': profile.created_date or datetime.now().isoformat(),
            'version': profile.version
        }
        
        with open(profile_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
        
        self._current_profile = profile
    
    def list_profiles(self) -> List[str]:
        """List all saved institution profiles."""
        profiles = []
        for f in self.profiles_dir.glob("*.json"):
            profiles.append(f.stem)
        return profiles
    
    # =========================================================================
    # DATA COLLECTION METHODS
    # =========================================================================
    
    def gather_demographics_interactive(self) -> InstitutionProfile:
        """
        Interactive wizard to gather demographic data.
        
        Returns:
            Complete InstitutionProfile with demographics and calculated adjustments
        """
        print("\n" + "=" * 70)
        print("INSTITUTIONAL DEMOGRAPHIC DATA COLLECTION")
        print("=" * 70)
        print("""
To provide context-appropriate analysis, this tool adjusts its detection
based on your institution's student population.

This data is used ONLY for:
  ✓ Adjusting marker weights appropriately
  ✓ Reducing false positives for diverse learners
  ✓ Improving accuracy for YOUR students

This data is NOT:
  ✗ Shared with anyone
  ✗ Uploaded anywhere
  ✗ Used for any other purpose
""")
        
        input("Press Enter to continue...")
        
        # Choose data source
        print("\n" + "-" * 50)
        print("DATA SOURCE")
        print("-" * 50)
        print("""
How would you like to provide demographic data?

  1. Use national averages for community colleges
  2. Enter your institution's specific data manually
  3. Try to fetch from Canvas API (limited data)
""")
        
        while True:
            choice = input("Choose option (1/2/3, default=1): ").strip()
            
            if choice in ['', '1']:
                demographics = self._use_national_averages()
                break
            elif choice == '2':
                demographics = self._collect_manual_data()
                break
            elif choice == '3':
                demographics = self._try_canvas_api()
                if demographics is None:
                    print("\nCanvas API data not available. Using national averages.")
                    demographics = self._use_national_averages()
                break
            else:
                print("Please enter 1, 2, or 3")
        
        # Calculate adjustments
        adjustments = self._calculate_adjustments(demographics)
        
        # Create profile
        profile = InstitutionProfile(
            demographics=demographics,
            adjustments=adjustments,
            created_date=datetime.now().isoformat()
        )
        
        # Show summary and save
        self._show_profile_summary(profile)
        
        save = input("\nSave this profile? (Y/n): ").strip().lower()
        if save in ['', 'y', 'yes']:
            self.save_profile(profile)
            print("✓ Profile saved")
        
        return profile
    
    def _use_national_averages(self) -> DemographicData:
        """Use national averages for institution type."""
        print("\n" + "-" * 50)
        print("INSTITUTION TYPE")
        print("-" * 50)
        print("""
Select your institution type:

  1. Community College (2-year)
  2. Public University (4-year)
  3. Private University
""")
        
        while True:
            choice = input("Choose type (1/2/3, default=1): ").strip()
            
            if choice in ['', '1']:
                inst_type = 'community_college'
                break
            elif choice == '2':
                inst_type = 'public_university'
                break
            elif choice == '3':
                inst_type = 'private_university'
                break
            else:
                print("Please enter 1, 2, or 3")
        
        demographics = DemographicData(**asdict(NATIONAL_AVERAGES[inst_type]))
        demographics.last_updated = datetime.now().isoformat()
        demographics.academic_year = self._get_academic_year()
        
        return demographics
    
    def _collect_manual_data(self) -> DemographicData:
        """Interactively collect demographic data from user."""
        print("\n" + "-" * 50)
        print("MANUAL DATA ENTRY")
        print("-" * 50)
        print("""
Enter your institution's demographic data.
Press Enter to use national average for any field.
Enter percentages as numbers (e.g., 45 for 45%).
""")
        
        demographics = DemographicData()
        demographics.data_source = 'manual_input'
        demographics.last_updated = datetime.now().isoformat()
        demographics.academic_year = self._get_academic_year()
        
        # Institution type
        print("\nInstitution type:")
        print("  1. Community College")
        print("  2. Public University")
        print("  3. Private University")
        type_choice = input("Choose (1/2/3, default=1): ").strip()
        if type_choice == '2':
            demographics.institution_type = 'public_university'
        elif type_choice == '3':
            demographics.institution_type = 'private_university'
        else:
            demographics.institution_type = 'community_college'
        
        # Get national average for defaults
        defaults = NATIONAL_AVERAGES.get(demographics.institution_type, 
                                         NATIONAL_AVERAGES['community_college'])
        
        # ESL learners
        demographics.esl_learners = self._get_percentage(
            "ESL/ELL students", defaults.esl_learners,
            "Students whose first language is not English"
        )
        
        # First generation
        demographics.first_generation = self._get_percentage(
            "First-generation college students", defaults.first_generation,
            "Students whose parents did not attend college"
        )
        
        # Disability services
        demographics.disability_services = self._get_percentage(
            "Students registered with disability services", defaults.disability_services,
            "Includes learning disabilities, neurodivergent students"
        )
        
        # Pell recipients
        demographics.pell_recipients = self._get_percentage(
            "Pell Grant recipients", defaults.pell_recipients,
            "Indicator of low-income students"
        )
        
        # Working students
        demographics.working_students = self._get_percentage(
            "Students working while enrolled", defaults.working_students,
            "Any employment during semester"
        )
        
        demographics.working_full_time = self._get_percentage(
            "Students working full-time (35+ hours)", defaults.working_full_time,
            "Significant time constraint"
        )
        
        # Age distribution
        print("\n--- Age Distribution ---")
        demographics.traditional_age_18_24 = self._get_percentage(
            "Traditional age (18-24)", defaults.traditional_age_18_24
        )
        demographics.adult_25_39 = self._get_percentage(
            "Adult learners (25-39)", defaults.adult_25_39
        )
        demographics.mature_40_plus = self._get_percentage(
            "Mature students (40+)", defaults.mature_40_plus
        )
        
        # Confidence level
        print("\nHow confident are you in this data?")
        print("  1. High (from institutional research)")
        print("  2. Medium (from informal sources)")
        print("  3. Low (rough estimates)")
        conf = input("Choose (1/2/3, default=2): ").strip()
        if conf == '1':
            demographics.confidence = 'high'
        elif conf == '3':
            demographics.confidence = 'low'
        else:
            demographics.confidence = 'medium'
        
        # Notes
        notes = input("\nAny notes about this data? (optional): ").strip()
        demographics.notes = notes
        
        return demographics
    
    def _get_percentage(self, field_name: str, default: float, 
                        description: str = None) -> float:
        """Get percentage input with default."""
        prompt = f"\n{field_name}"
        if description:
            prompt += f"\n  ({description})"
        prompt += f"\n  [default: {default}%]: "
        
        while True:
            value = input(prompt).strip()
            if value == '':
                return default
            try:
                pct = float(value)
                if 0 <= pct <= 100:
                    return pct
                print("  Please enter a value between 0 and 100")
            except ValueError:
                print("  Please enter a number")
    
    def _try_canvas_api(self) -> Optional[DemographicData]:
        """Try to fetch demographic data from Canvas API."""
        if not self.canvas_url or not self.canvas_token:
            print("\nCanvas API credentials not configured.")
            return None
        
        print("\nAttempting to fetch data from Canvas...")
        
        # Canvas doesn't directly provide demographic data
        # This would require custom institution integrations
        # For now, return None to fall back to manual/national
        
        print("Canvas API does not provide demographic data directly.")
        print("Consider asking your Institutional Research office for this data.")
        
        return None
    
    def _get_academic_year(self) -> str:
        """Determine current academic year."""
        now = datetime.now()
        if now.month >= 8:  # Fall semester starts
            return f"{now.year}-{now.year + 1}"
        else:
            return f"{now.year - 1}-{now.year}"
    
    # =========================================================================
    # ADJUSTMENT CALCULATION
    # =========================================================================
    
    def _calculate_adjustments(self, demographics: DemographicData) -> MarkerAdjustments:
        """
        Calculate marker weight adjustments based on demographics.
        
        Logic:
        - Higher ESL → Lower weight on transition/vocabulary markers
        - Higher first-gen → Lower weight on formal structure markers
        - Higher working students → Higher thresholds overall
        """
        adjustments = MarkerAdjustments()
        rationale = []
        
        # ESL adjustments
        if demographics.esl_learners >= 40:
            adjustments.ai_transitions = 0.6
            adjustments.inflated_vocabulary = 0.5
            adjustments.grammatical_perfection = 0.3
            rationale.append(
                f"High ESL population ({demographics.esl_learners}%): "
                "Significantly reduced weights on language markers"
            )
        elif demographics.esl_learners >= 25:
            adjustments.ai_transitions = 0.75
            adjustments.inflated_vocabulary = 0.7
            adjustments.grammatical_perfection = 0.5
            rationale.append(
                f"Moderate ESL population ({demographics.esl_learners}%): "
                "Reduced weights on language markers"
            )
        
        # First-generation adjustments
        if demographics.first_generation >= 50:
            adjustments.formal_essay_structure = 0.6
            adjustments.personal_voice_markers = 0.85
            rationale.append(
                f"High first-gen population ({demographics.first_generation}%): "
                "Reduced weight on formal structure (may follow templates rigidly)"
            )
        elif demographics.first_generation >= 35:
            adjustments.formal_essay_structure = 0.75
            adjustments.personal_voice_markers = 0.9
            rationale.append(
                f"Moderate first-gen population ({demographics.first_generation}%): "
                "Slightly reduced structure expectations"
            )
        
        # Working student adjustments (threshold changes)
        if demographics.working_full_time >= 30:
            adjustments.flag_concern_level = 4.0
            adjustments.peer_comparison_percentile = 95.0
            rationale.append(
                f"High full-time work rate ({demographics.working_full_time}%): "
                "Raised flagging thresholds (students have significant time constraints)"
            )
        elif demographics.working_students >= 70:
            adjustments.flag_concern_level = 3.5
            adjustments.peer_comparison_percentile = 92.0
            rationale.append(
                f"Many working students ({demographics.working_students}%): "
                "Slightly raised thresholds"
            )
        
        # Default rationale if none triggered
        if not rationale:
            rationale.append(
                "Demographics near national averages: Using standard marker weights"
            )
        
        adjustments.rationale = rationale
        
        return adjustments
    
    def _show_profile_summary(self, profile: InstitutionProfile):
        """Display summary of the profile."""
        d = profile.demographics
        a = profile.adjustments
        
        print("\n" + "=" * 70)
        print("INSTITUTION PROFILE SUMMARY")
        print("=" * 70)
        
        print(f"""
Institution Type: {d.institution_type.replace('_', ' ').title()}
Data Source:      {d.data_source.replace('_', ' ').title()}
Academic Year:    {d.academic_year}
Confidence:       {d.confidence.title()}

DEMOGRAPHICS:
  ESL/ELL Students:       {d.esl_learners}%
  First-Generation:       {d.first_generation}%
  Disability Services:    {d.disability_services}%
  Pell Recipients:        {d.pell_recipients}%
  Working Students:       {d.working_students}%
  Working Full-Time:      {d.working_full_time}%

AGE DISTRIBUTION:
  18-24 (Traditional):    {d.traditional_age_18_24}%
  25-39 (Adult):          {d.adult_25_39}%
  40+ (Mature):           {d.mature_40_plus}%

CALCULATED ADJUSTMENTS:
  AI Transitions:         {a.ai_transitions}x weight
  Inflated Vocabulary:    {a.inflated_vocabulary}x weight
  Grammar Perfection:     {a.grammatical_perfection}x weight
  Formal Structure:       {a.formal_essay_structure}x weight
  Personal Voice:         {a.personal_voice_markers}x weight
  
  Flag Threshold:         {a.flag_concern_level} points
  Peer Comparison:        Top {100 - a.peer_comparison_percentile}% flagged

RATIONALE:
""")
        
        for r in a.rationale:
            print(f"  • {r}")
        
        if d.notes:
            print(f"\nNotes: {d.notes}")
    
    # =========================================================================
    # INTEGRATION WITH ANALYSIS
    # =========================================================================
    
    def get_marker_adjustments(self) -> Dict[str, float]:
        """
        Get marker weight adjustments for use in analysis.
        
        Returns:
            Dictionary of marker_id -> weight_multiplier
        """
        profile = self.get_current_profile()
        
        if profile is None:
            return {}  # No adjustments
        
        a = profile.adjustments
        
        return {
            'ai_transitions': a.ai_transitions,
            'inflated_vocabulary': a.inflated_vocabulary,
            'grammatical_perfection': a.grammatical_perfection,
            'formal_essay_structure': a.formal_essay_structure,
            'personal_voice_markers': a.personal_voice_markers,
            'generic_phrases': a.generic_phrases,
            'hedge_phrases': a.hedge_phrases,
        }
    
    def get_threshold_adjustments(self) -> Dict[str, float]:
        """
        Get threshold adjustments for use in analysis.
        
        Returns:
            Dictionary with flag_concern_level and peer_comparison_percentile
        """
        profile = self.get_current_profile()
        
        if profile is None:
            return {
                'flag_concern_level': 3.0,
                'peer_comparison_percentile': 90.0
            }
        
        return {
            'flag_concern_level': profile.adjustments.flag_concern_level,
            'peer_comparison_percentile': profile.adjustments.peer_comparison_percentile
        }
    
    def get_context_summary(self) -> str:
        """Get a brief summary of demographic context for reports."""
        profile = self.get_current_profile()
        
        if profile is None:
            return "No institutional profile configured. Using default weights."
        
        d = profile.demographics
        
        highlights = []
        if d.esl_learners >= 30:
            highlights.append(f"{d.esl_learners}% ESL")
        if d.first_generation >= 40:
            highlights.append(f"{d.first_generation}% first-gen")
        if d.working_full_time >= 20:
            highlights.append(f"{d.working_full_time}% working full-time")
        
        if highlights:
            return f"Context: {', '.join(highlights)} — weights adjusted accordingly"
        else:
            return f"Context: {d.institution_type.replace('_', ' ').title()} with typical demographics"


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_collector: Optional[DemographicCollector] = None

def get_demographic_collector(config_dir: Path = None) -> DemographicCollector:
    """Get or create the global demographic collector."""
    global _collector
    if _collector is None:
        _collector = DemographicCollector(config_dir)
    return _collector


def get_marker_adjustments() -> Dict[str, float]:
    """Convenience function to get marker adjustments."""
    return get_demographic_collector().get_marker_adjustments()


def get_context_summary() -> str:
    """Convenience function to get context summary."""
    return get_demographic_collector().get_context_summary()
