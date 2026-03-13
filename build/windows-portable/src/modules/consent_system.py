"""
Data Consent System
Manages user consent for data collection and usage.
Required for ethical deployment of academic integrity tools.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from dataclasses import dataclass, asdict


@dataclass
class ConsentRecord:
    """Record of user's consent choices."""
    
    # Consent timestamp
    consent_date: str
    consent_version: str
    
    # Program usage consent (required)
    program_usage: bool  # Must be True to use the tool
    
    # Optional consents
    anonymous_marker_feedback: bool  # Help improve marker accuracy
    usage_statistics: bool  # Anonymous usage stats
    
    # User acknowledgments
    understands_limitations: bool
    understands_not_detector: bool
    agrees_conversation_first: bool
    
    # Institution info (optional)
    institution_type: Optional[str] = None
    approximate_class_size: Optional[str] = None


class ConsentManager:
    """
    Manages consent collection and verification.
    
    Philosophy:
    This tool affects students' academic careers. Users must:
    1. Understand the tool's limitations
    2. Agree to use it as a conversation starter, not a verdict
    3. Acknowledge that false positives are possible
    
    Data collection is optional and anonymized.
    """
    
    CONSENT_VERSION = "2.0.0"
    
    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize consent manager."""
        self.config_dir = config_dir or self._get_default_config_dir()
        self.consent_file = self.config_dir / "consent.json"
        self._consent: Optional[ConsentRecord] = None
    
    def _get_default_config_dir(self) -> Path:
        """Get default config directory."""
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
    
    def has_valid_consent(self) -> bool:
        """Check if user has valid consent on file."""
        if not self.consent_file.exists():
            return False
        
        try:
            consent = self.load_consent()
            if consent is None:
                return False
            
            # Check required consents
            if not consent.program_usage:
                return False
            if not consent.understands_limitations:
                return False
            if not consent.understands_not_detector:
                return False
            if not consent.agrees_conversation_first:
                return False
            
            # Check version (may require re-consent on major updates)
            if consent.consent_version.split('.')[0] != self.CONSENT_VERSION.split('.')[0]:
                return False
            
            return True
        except Exception:
            return False
    
    def load_consent(self) -> Optional[ConsentRecord]:
        """Load consent from file."""
        if not self.consent_file.exists():
            return None
        
        try:
            with open(self.consent_file, 'r') as f:
                data = json.load(f)
            
            self._consent = ConsentRecord(**data)
            return self._consent
        except Exception as e:
            print(f"Warning: Could not load consent: {e}")
            return None
    
    def save_consent(self, consent: ConsentRecord) -> bool:
        """Save consent to file."""
        try:
            # Security: Restrict permissions to owner only
            self.config_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            
            with open(self.consent_file, 'w') as f:
                json.dump(asdict(consent), f, indent=2)
            
            self._consent = consent
            return True
        except Exception as e:
            print(f"Error saving consent: {e}")
            return False
    
    def collect_consent_interactive(self) -> Optional[ConsentRecord]:
        """Collect consent through interactive prompts."""
        print("\n" + "=" * 60)
        print("ACADEMIC DISHONESTY CHECK v2.0 - FIRST TIME SETUP")
        print("=" * 60)
        
        print("""
Before using this tool, please read and acknowledge the following.

IMPORTANT LIMITATIONS
---------------------
This tool:
• Is NOT an AI detector and cannot prove AI use
• Can produce false positives, especially for ESL students
• Should NEVER be the sole basis for academic action
• Is designed as a CONVERSATION STARTER, not a verdict

The tool identifies patterns that MAY warrant further discussion.
Many legitimate factors can trigger these patterns.
""")
        
        # Required acknowledgments
        print("\nREQUIRED ACKNOWLEDGMENTS")
        print("-" * 30)
        
        understands_limitations = self._get_yes_no(
            "I understand this tool has significant limitations and can produce "
            "false positives"
        )
        if not understands_limitations:
            print("\nYou must acknowledge the limitations to use this tool.")
            return None
        
        understands_not_detector = self._get_yes_no(
            "I understand this is NOT an AI detector and cannot prove AI use"
        )
        if not understands_not_detector:
            print("\nYou must acknowledge this is not a detector to use this tool.")
            return None
        
        agrees_conversation_first = self._get_yes_no(
            "I agree to use flags as conversation starters, not as evidence "
            "of dishonesty"
        )
        if not agrees_conversation_first:
            print("\nYou must agree to the conversation-first approach.")
            return None
        
        program_usage = self._get_yes_no(
            "I agree to use this tool responsibly according to these principles"
        )
        if not program_usage:
            print("\nConsent required to use the tool.")
            return None
        
        # Optional consents
        print("\nOPTIONAL DATA SHARING")
        print("-" * 30)
        print("""
You may optionally help improve the tool by sharing anonymous data.
No student work or identifying information is ever collected.
""")
        
        anonymous_marker_feedback = self._get_yes_no(
            "Help improve detection accuracy by sharing anonymous pattern data",
            default=False
        )
        
        usage_statistics = self._get_yes_no(
            "Share anonymous usage statistics (e.g., which profiles are used)",
            default=False
        )
        
        # Optional institution info
        print("\nOPTIONAL CONTEXT (helps calibrate defaults)")
        print("-" * 30)
        
        institution_type = self._get_choice(
            "Institution type",
            ["community_college", "four_year", "university", "high_school", "other", "skip"],
            default="skip"
        )
        if institution_type == "skip":
            institution_type = None
        
        class_size = self._get_choice(
            "Typical class size",
            ["small (<20)", "medium (20-40)", "large (40+)", "skip"],
            default="skip"
        )
        if class_size == "skip":
            class_size = None
        
        # Create consent record
        consent = ConsentRecord(
            consent_date=datetime.now().isoformat(),
            consent_version=self.CONSENT_VERSION,
            program_usage=program_usage,
            anonymous_marker_feedback=anonymous_marker_feedback,
            usage_statistics=usage_statistics,
            understands_limitations=understands_limitations,
            understands_not_detector=understands_not_detector,
            agrees_conversation_first=agrees_conversation_first,
            institution_type=institution_type,
            approximate_class_size=class_size
        )
        
        # Save
        if self.save_consent(consent):
            print("\n✓ Consent saved. Thank you for using this tool responsibly.")
            return consent
        else:
            print("\n✗ Could not save consent. Please try again.")
            return None
    
    def _get_yes_no(self, prompt: str, default: bool = True) -> bool:
        """Get yes/no response."""
        default_str = "Y/n" if default else "y/N"
        while True:
            response = input(f"\n{prompt}? [{default_str}]: ").strip().lower()
            if response == "":
                return default
            if response in ['y', 'yes']:
                return True
            if response in ['n', 'no']:
                return False
            print("Please enter 'y' or 'n'")
    
    def _get_choice(self, prompt: str, choices: list, default: str = None) -> str:
        """Get choice from list."""
        print(f"\n{prompt}:")
        for i, choice in enumerate(choices, 1):
            marker = "*" if choice == default else " "
            print(f"  {marker}{i}. {choice}")
        
        while True:
            response = input(f"Enter number [default: {default}]: ").strip()
            if response == "" and default:
                return default
            try:
                idx = int(response) - 1
                if 0 <= idx < len(choices):
                    return choices[idx]
            except ValueError:
                pass
            print(f"Please enter a number 1-{len(choices)}")
    
    def get_consent_summary(self) -> str:
        """Get summary of current consent status."""
        if not self.has_valid_consent():
            return "No valid consent on file. Run setup to continue."
        
        consent = self.load_consent()
        lines = [
            f"Consent Version: {consent.consent_version}",
            f"Consent Date: {consent.consent_date}",
            f"Anonymous Feedback: {'Enabled' if consent.anonymous_marker_feedback else 'Disabled'}",
            f"Usage Statistics: {'Enabled' if consent.usage_statistics else 'Disabled'}",
        ]
        
        if consent.institution_type:
            lines.append(f"Institution Type: {consent.institution_type}")
        
        return "\n".join(lines)


def require_consent(config_dir: Optional[Path] = None) -> bool:
    """
    Ensure valid consent exists, collecting if needed.
    
    Returns:
        True if consent is valid, False if user declined
    """
    manager = ConsentManager(config_dir)
    
    if manager.has_valid_consent():
        return True
    
    consent = manager.collect_consent_interactive()
    return consent is not None


def get_consent_manager(config_dir: Optional[Path] = None) -> ConsentManager:
    """Get consent manager instance."""
    return ConsentManager(config_dir)
