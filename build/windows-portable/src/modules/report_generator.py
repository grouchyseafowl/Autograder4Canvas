"""
Report Generator Module
Generates pedagogically-framed reports for academic integrity analysis.
"""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SubmissionReport:
    """Report for a single submission."""
    student_id: str
    student_name: str
    concern_level: str
    suspicious_score: float
    authenticity_score: float
    markers_found: Dict[str, List[str]]
    conversation_starters: List[str]
    verification_questions: List[str]
    revision_guidance: str
    context_notes: List[str]
    
    # Peer comparison (if available)
    percentile: Optional[float] = None
    is_outlier: bool = False
    outlier_reasons: List[str] = None


class ReportGenerator:
    """
    Generates pedagogically-framed reports.
    
    Key principles:
    1. Reports are conversation starters, not verdicts
    2. Each flag includes explanation and context
    3. Instructor guidance focuses on learning, not punishment
    4. False positive awareness is built in
    """
    
    def __init__(self, profile_name: str = "Standard"):
        self.profile_name = profile_name
    
    def generate_batch_report(self,
                              results: List[SubmissionReport],
                              assignment_name: str = "Assignment",
                              include_peer_stats: bool = True) -> str:
        """
        Generate a complete report for a batch of submissions.
        
        Args:
            results: List of SubmissionReport objects
            assignment_name: Name of the assignment
            include_peer_stats: Whether to include peer comparison statistics
            
        Returns:
            Formatted report string
        """
        lines = []
        
        # Header
        lines.append("=" * 70)
        lines.append("ACADEMIC INTEGRITY ANALYSIS REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append(f"Assignment: {assignment_name}")
        lines.append(f"Profile: {self.profile_name}")
        lines.append(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"Submissions Analyzed: {len(results)}")
        lines.append("")
        
        # Important notice
        lines.append("-" * 70)
        lines.append("IMPORTANT: HOW TO USE THIS REPORT")
        lines.append("-" * 70)
        lines.append("""
This report identifies submissions that may warrant further review.
It is a CONVERSATION STARTER, not a verdict.

Before taking any action:
1. Review the submission yourself
2. Consider the student's background and context
3. Use the conversation starters to discuss with the student
4. Remember that false positives are possible

Flags indicate deviation from expected patterns, not proof of dishonesty.
""")
        lines.append("")
        
        # Summary by concern level
        lines.append("-" * 70)
        lines.append("SUMMARY BY CONCERN LEVEL")
        lines.append("-" * 70)
        
        concern_counts = {
            'high': 0, 'elevated': 0, 'moderate': 0, 'low': 0, 'none': 0
        }
        for r in results:
            level = r.concern_level.lower()
            if level in concern_counts:
                concern_counts[level] += 1
        
        lines.append(f"  HIGH:      {concern_counts['high']:3d}  - Recommend structured conversation")
        lines.append(f"  ELEVATED:  {concern_counts['elevated']:3d}  - Recommend brief check-in")
        lines.append(f"  MODERATE:  {concern_counts['moderate']:3d}  - Note for pattern tracking")
        lines.append(f"  LOW:       {concern_counts['low']:3d}  - Minor indicators only")
        lines.append(f"  NONE:      {concern_counts['none']:3d}  - No concerns identified")
        lines.append("")
        
        # Peer comparison stats (if available)
        if include_peer_stats and any(r.percentile is not None for r in results):
            lines.append("-" * 70)
            lines.append("PEER COMPARISON STATISTICS")
            lines.append("-" * 70)
            
            sus_scores = [r.suspicious_score for r in results]
            auth_scores = [r.authenticity_score for r in results]
            
            if sus_scores:
                import statistics
                lines.append(f"Suspicious Scores: mean={statistics.mean(sus_scores):.2f}, "
                           f"median={statistics.median(sus_scores):.2f}")
            if auth_scores:
                lines.append(f"Authenticity Scores: mean={statistics.mean(auth_scores):.2f}, "
                           f"median={statistics.median(auth_scores):.2f}")
            
            outlier_count = sum(1 for r in results if r.is_outlier)
            lines.append(f"Statistical Outliers: {outlier_count}")
            lines.append("")
        
        # Detailed results for high/elevated concern
        high_elevated = [r for r in results if r.concern_level.lower() in ['high', 'elevated']]
        
        if high_elevated:
            lines.append("-" * 70)
            lines.append("DETAILED ANALYSIS: HIGH & ELEVATED CONCERN")
            lines.append("-" * 70)
            
            for r in sorted(high_elevated, 
                          key=lambda x: (0 if x.concern_level.lower() == 'high' else 1, 
                                        -x.suspicious_score)):
                lines.append("")
                lines.extend(self._format_submission_detail(r))
        
        # Brief list of moderate concerns
        moderate = [r for r in results if r.concern_level.lower() == 'moderate']
        if moderate:
            lines.append("")
            lines.append("-" * 70)
            lines.append("MODERATE CONCERN (Brief Summary)")
            lines.append("-" * 70)
            
            for r in moderate:
                markers = ', '.join(r.markers_found.keys()) if r.markers_found else 'None'
                lines.append(f"  {r.student_name}: sus={r.suspicious_score:.1f}, "
                           f"auth={r.authenticity_score:.1f} | {markers}")
        
        # Footer
        lines.append("")
        lines.append("=" * 70)
        lines.append("END OF REPORT")
        lines.append("=" * 70)
        lines.append("")
        lines.append("Remember: This tool supports instructor judgment. It does not replace it.")
        
        return "\n".join(lines)
    
    def _format_submission_detail(self, r: SubmissionReport) -> List[str]:
        """Format detailed output for a single submission."""
        lines = []
        
        # Header with concern level
        level_emoji = {
            'high': '🔴', 'elevated': '🟠', 'moderate': '🟡', 'low': '🟢', 'none': '⚪'
        }
        emoji = level_emoji.get(r.concern_level.lower(), '⚪')
        
        lines.append(f"┌{'─' * 66}┐")
        lines.append(f"│ {emoji} {r.student_name:<52} {r.concern_level.upper():>10} │")
        lines.append(f"└{'─' * 66}┘")
        
        # Scores
        lines.append(f"  Suspicious Score: {r.suspicious_score:.2f}")
        lines.append(f"  Authenticity Score: {r.authenticity_score:.2f}")
        
        if r.percentile is not None:
            lines.append(f"  Percentile (in class): {r.percentile:.1f}%")
        
        if r.is_outlier and r.outlier_reasons:
            lines.append(f"  Outlier: Yes - {', '.join(r.outlier_reasons)}")
        
        # Markers found
        if r.markers_found:
            lines.append("")
            lines.append("  MARKERS DETECTED:")
            for marker_type, examples in r.markers_found.items():
                lines.append(f"    • {marker_type}: {len(examples)} instance(s)")
                # Privacy: Do not include actual student text in reports
                # Quantitative data (counts) is sufficient for instructor review

        # AI-specific organizational patterns (special handling)
        if hasattr(r, 'ai_organizational_score') and r.ai_organizational_score > 0:
            lines.append("")
            lines.append("  AI-SPECIFIC ORGANIZATIONAL PATTERNS:")
            lines.append(f"    Overall Score: {r.ai_organizational_score:.1f}")
            lines.append("")

            if hasattr(r, 'organizational_analysis') and r.organizational_analysis:
                org = r.organizational_analysis

                # Header analysis
                header_info = org.get('header_analysis', {})
                if header_info.get('excessive') or header_info.get('hierarchical'):
                    lines.append("    Header Structure:")
                    lines.append(f"      • Total headers: {header_info.get('total_count', 0)}")
                    lines.append(f"      • Deepest level: H{header_info.get('deepest_level', 0)}")
                    if header_info.get('excessive'):
                        lines.append("      ⚠ EXCESSIVE for word count (AI signature)")
                    if header_info.get('hierarchical'):
                        lines.append("      ⚠ UNNECESSARILY DEEP hierarchy (AI signature)")
                    lines.append("")

                # Section balance
                section_info = org.get('section_analysis', {})
                if section_info.get('balanced'):
                    lines.append("    Section Balance:")
                    variance = section_info.get('variance_coefficient', 0)
                    lines.append(f"      • Variance coefficient: {variance:.3f}")
                    lines.append(f"      ⚠ SUSPICIOUSLY UNIFORM (AI signature)")
                    lines.append(f"      Note: Neurodivergent students show uneven depth due to hyperfocus")
                    lines.append("")

                # Paragraph uniformity
                para_info = org.get('paragraph_analysis', {})
                if para_info.get('uniform'):
                    lines.append("    Paragraph Structure:")
                    variance = para_info.get('variance_coefficient', 0)
                    lines.append(f"      • Variance coefficient: {variance:.3f}")
                    lines.append(f"      ⚠ SUSPICIOUSLY UNIFORM (AI signature)")
                    lines.append("")

            lines.append("    IMPORTANT: These patterns are AI-SPECIFIC and do NOT overlap")
            lines.append("    with neurodivergent writing styles. They remain fully weighted")
            lines.append("    even when cognitive diversity protection is active.")

        # Human Presence Detection (PARADIGM SHIFT)
        if hasattr(r, 'human_presence_confidence') and r.human_presence_confidence is not None:
            lines.append("")
            lines.append("=" * 66)
            lines.append("  HUMAN PRESENCE DETECTION")
            lines.append("=" * 66)
            lines.append("")

            # Overall confidence
            confidence = r.human_presence_confidence
            level = r.human_presence_level if hasattr(r, 'human_presence_level') else 'unknown'

            # Visual confidence bar
            confidence_bar = self._create_confidence_bar(confidence)
            lines.append(f"  Overall Confidence: {confidence:.1f}% {confidence_bar}")
            lines.append(f"  Level: {level.upper().replace('_', ' ')}")
            lines.append("")

            # Interpretation
            if level == 'very_high':
                lines.append("  ✓ STRONG EVIDENCE of genuine human authorship")
                lines.append("    Multiple dimensions of human presence detected")
            elif level == 'high':
                lines.append("  ✓ GOOD EVIDENCE of human authorship")
                lines.append("    Meaningful engagement with course material evident")
            elif level == 'medium':
                lines.append("  ⚠ MODERATE EVIDENCE - some human markers present")
                lines.append("    Review recommended to confirm authenticity")
            elif level == 'low':
                lines.append("  ⚠ LIMITED EVIDENCE - few human presence markers")
                lines.append("    Recommend instructor conversation with student")
            else:  # very_low
                lines.append("  ⚠ VERY LIMITED human presence markers detected")
                lines.append("    Recommend verification of student authorship")
            lines.append("")

            # Category breakdown
            if hasattr(r, 'human_presence_details') and r.human_presence_details:
                details = r.human_presence_details

                lines.append("  CATEGORY BREAKDOWN:")
                lines.append("")

                # Extract category scores
                categories = [
                    ('contextual_grounding', '  Contextual Grounding (35%)', 'Course participation, specific references'),
                    ('emotional_stakes', '  Emotional Stakes (20%)', 'Personal investment, stakes articulation'),
                    ('cognitive_struggle', '  Cognitive Struggle (20%)', 'Working through complexity, metacognition'),
                    ('authentic_voice', '  Authentic Voice (15%)', 'Code-meshing, cultural grounding'),
                    ('productive_messiness', '  Productive Messiness (10%)', 'Self-correction, revision thinking')
                ]

                for cat_key, cat_label, cat_desc in categories:
                    if cat_key in details:
                        cat_data = details[cat_key]
                        marker_count = cat_data.get('marker_count', 0)
                        weighted_score = cat_data.get('weighted_score', 0)

                        # Visual indicator
                        indicator = self._create_category_indicator(marker_count)

                        lines.append(f"    {cat_label}")
                        lines.append(f"      {indicator} {marker_count} markers | Score: {weighted_score:.1f}")
                        lines.append(f"      ({cat_desc})")
                        lines.append("")

                # Significant combinations
                if 'significant_combinations' in details and details['significant_combinations']:
                    lines.append("  SIGNIFICANT COMBINATIONS DETECTED:")
                    for combo in details['significant_combinations']:
                        lines.append(f"    ✓ {combo}")
                    lines.append("")

                # Strongest signals
                if 'strongest_signals' in details and details['strongest_signals']:
                    lines.append("  STRONGEST HUMAN PRESENCE SIGNALS:")
                    for signal in details['strongest_signals'][:5]:  # Top 5
                        lines.append(f"    • {signal}")
                    lines.append("")

                # Concerns
                if 'concerns' in details and details['concerns']:
                    lines.append("  ⚠ CONCERNS:")
                    for concern in details['concerns']:
                        lines.append(f"    • {concern}")
                    lines.append("")

                # Analysis notes
                if 'analysis_notes' in details and details['analysis_notes']:
                    lines.append("  ANALYSIS NOTES:")
                    for note in details['analysis_notes'][:3]:  # Top 3
                        lines.append(f"    ℹ {note}")
                    lines.append("")

            lines.append("  WHAT THIS MEANS:")
            if level in ['very_high', 'high']:
                lines.append("    This analysis shows clear evidence of a human mind engaging")
                lines.append("    with course material. The writing shows authentic voice,")
                lines.append("    thinking-in-progress, and connection to THIS specific course.")
            elif level == 'medium':
                lines.append("    Some human markers present, but not comprehensive.")
                lines.append("    Consider reviewing for contextual grounding (course-specific")
                lines.append("    references) as this is hardest for AI to fake.")
            else:
                lines.append("    Limited human presence markers suggest possible AI generation")
                lines.append("    or disconnection from course materials. Recommend conversation")
                lines.append("    with student about their writing process and course engagement.")

            lines.append("")
            lines.append("  NOTE: Human presence detection looks for COMBINATIONS of markers")
            lines.append("  across multiple dimensions. Contextual grounding (35%) weighted")
            lines.append("  highest as it's hardest for AI to fake without course access.")

        # PHASE 6: Student-provided context (privacy-focused, optional)
        if hasattr(r, 'student_context') and r.student_context:
            lines.append("")
            lines.append("=" * 66)
            lines.append("  STUDENT-PROVIDED CONTEXT")
            lines.append("=" * 66)
            lines.append("")
            lines.append("  The student shared this about their writing process:")
            lines.append(f"    \"{r.student_context}\"")

            if hasattr(r, 'student_context_applied') and r.student_context_applied:
                lines.append("")
                lines.append("  Adjustments applied based on student context:")
                if hasattr(r, 'student_context_adjustments'):
                    for adjustment in r.student_context_adjustments:
                        lines.append(f"    ✓ {adjustment}")
            else:
                lines.append("")
                lines.append("  No adjustments triggered (context noted for awareness)")

        # Context notes
        if r.context_notes:
            lines.append("")
            lines.append("  CONTEXT NOTES:")
            for note in r.context_notes:
                lines.append(f"    ℹ {note}")
        
        # Conversation starters
        if r.conversation_starters:
            lines.append("")
            lines.append("  SUGGESTED CONVERSATION STARTERS:")
            for starter in r.conversation_starters[:2]:  # Show up to 2
                lines.append(f"    → \"{starter}\"")
        
        # Verification questions
        if r.verification_questions:
            lines.append("")
            lines.append("  VERIFICATION QUESTIONS:")
            for q in r.verification_questions[:2]:
                lines.append(f"    ? \"{q}\"")
        
        # Revision guidance
        if r.revision_guidance:
            lines.append("")
            lines.append("  IF REQUIRING REVISION:")
            lines.append(f"    {r.revision_guidance}")
        
        return lines
    
    def generate_single_report(self, r: SubmissionReport) -> str:
        """Generate a report for a single submission."""
        lines = []
        
        lines.append("=" * 60)
        lines.append("SUBMISSION ANALYSIS")
        lines.append("=" * 60)
        lines.append("")
        lines.append(f"Student: {r.student_name}")
        lines.append(f"Concern Level: {r.concern_level.upper()}")
        lines.append("")
        
        lines.extend(self._format_submission_detail(r))
        
        lines.append("")
        lines.append("-" * 60)
        lines.append("This analysis is a conversation starter, not a verdict.")
        
        return "\n".join(lines)
    
    def format_for_console(self, text: str, width: int = 80) -> str:
        """Format report text for console display."""
        # Simple text wrapping for console
        lines = []
        for line in text.split('\n'):
            if len(line) > width:
                # Wrap long lines
                words = line.split()
                current_line = ""
                for word in words:
                    if len(current_line) + len(word) + 1 <= width:
                        current_line += (" " if current_line else "") + word
                    else:
                        lines.append(current_line)
                        current_line = "    " + word  # Indent continuation
                if current_line:
                    lines.append(current_line)
            else:
                lines.append(line)
        return "\n".join(lines)

    def _create_confidence_bar(self, confidence: float) -> str:
        """Create a visual confidence bar."""
        # Create a 20-character bar
        filled = int((confidence / 100) * 20)
        bar = "█" * filled + "░" * (20 - filled)
        return f"[{bar}]"

    def _create_category_indicator(self, marker_count: int) -> str:
        """Create a visual indicator for category marker counts."""
        if marker_count >= 10:
            return "●●●●●"  # Very strong
        elif marker_count >= 7:
            return "●●●●○"  # Strong
        elif marker_count >= 5:
            return "●●●○○"  # Good
        elif marker_count >= 3:
            return "●●○○○"  # Moderate
        elif marker_count >= 1:
            return "●○○○○"  # Weak
        else:
            return "○○○○○"  # None


def create_submission_report(student_id: str,
                            student_name: str,
                            concern_level: str,
                            suspicious_score: float,
                            authenticity_score: float,
                            markers_found: Dict[str, List[str]] = None,
                            conversation_starters: List[str] = None,
                            verification_questions: List[str] = None,
                            revision_guidance: str = "",
                            context_notes: List[str] = None,
                            percentile: float = None,
                            is_outlier: bool = False,
                            outlier_reasons: List[str] = None) -> SubmissionReport:
    """Convenience function to create a SubmissionReport."""
    return SubmissionReport(
        student_id=student_id,
        student_name=student_name,
        concern_level=concern_level,
        suspicious_score=suspicious_score,
        authenticity_score=authenticity_score,
        markers_found=markers_found or {},
        conversation_starters=conversation_starters or [],
        verification_questions=verification_questions or [],
        revision_guidance=revision_guidance,
        context_notes=context_notes or [],
        percentile=percentile,
        is_outlier=is_outlier,
        outlier_reasons=outlier_reasons or []
    )
