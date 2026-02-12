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
                lines.append(f"    • {marker_type}:")
                for ex in examples[:3]:  # Show up to 3 examples
                    lines.append(f"      - \"{ex}\"")
                if len(examples) > 3:
                    lines.append(f"      ... and {len(examples) - 3} more")
        
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
