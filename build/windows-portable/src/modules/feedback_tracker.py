"""
Instructor Feedback Tracker

Allows instructors to record outcomes of flagged submissions to:
- Track false positive rates
- Calibrate detection thresholds
- Build institutional knowledge about what patterns are/aren't concerning
"""

import csv
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict
from dataclasses import dataclass, asdict


@dataclass
class FeedbackRecord:
    """Record of instructor feedback on a flagged submission."""
    timestamp: str
    student_id: str
    student_name: str
    assignment_name: str
    concern_level: str  # high, elevated, moderate, low, none
    suspicious_score: float
    authenticity_score: float

    # Instructor feedback
    outcome: str  # "false_positive", "confirmed_concern", "needs_revision", "uncertain"
    notes: str

    # Context
    esl_detected: bool
    context_profile: str  # community_college, standard, etc.

    # Marker counts (for tracking which markers are predictive)
    markers_present: str  # JSON string of marker counts, e.g. '{"ai_transitions": 5, "generic_phrases": 3}'


class FeedbackTracker:
    """
    Track instructor feedback on flagged submissions.

    Philosophy: This data helps improve the tool over time by learning
    which patterns are actually concerning vs. normal variation in your
    specific student population.
    """

    def __init__(self, feedback_file: Optional[Path] = None):
        """
        Initialize feedback tracker.

        Args:
            feedback_file: Path to CSV file for storing feedback
                          Default: ~/Documents/Autograder Rationales/feedback_log.csv
        """
        if feedback_file is None:
            from Programs.Academic_Dishonesty_Check_v2 import get_output_base_dir
            base_dir = get_output_base_dir() / "Academic Dishonesty Reports"
            self.feedback_file = base_dir / "feedback_log.csv"
        else:
            self.feedback_file = Path(feedback_file)

        # Ensure directory exists
        self.feedback_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)

        # Create file with headers if it doesn't exist
        if not self.feedback_file.exists():
            self._create_feedback_file()

    def _create_feedback_file(self):
        """Create feedback CSV file with headers."""
        headers = [
            "timestamp", "student_id", "student_name", "assignment_name",
            "concern_level", "suspicious_score", "authenticity_score",
            "outcome", "notes", "esl_detected", "context_profile", "markers_present"
        ]

        with open(self.feedback_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()

    def record_feedback(self, record: FeedbackRecord) -> bool:
        """
        Record instructor feedback.

        Args:
            record: FeedbackRecord with instructor's assessment

        Returns:
            True if successful
        """
        try:
            # Append to CSV
            with open(self.feedback_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=asdict(record).keys())
                writer.writerow(asdict(record))
            return True
        except Exception as e:
            print(f"⚠ Warning: Could not save feedback: {e}")
            return False

    def get_feedback_for_student(self, student_id: str) -> List[FeedbackRecord]:
        """
        Get all feedback records for a specific student.

        Args:
            student_id: Student ID to look up

        Returns:
            List of FeedbackRecord objects
        """
        if not self.feedback_file.exists():
            return []

        records = []
        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['student_id'] == student_id:
                        # Convert string values back to proper types
                        row['suspicious_score'] = float(row['suspicious_score'])
                        row['authenticity_score'] = float(row['authenticity_score'])
                        row['esl_detected'] = row['esl_detected'].lower() == 'true'
                        records.append(FeedbackRecord(**row))
        except Exception as e:
            print(f"⚠ Warning: Could not read feedback: {e}")

        return records

    def get_statistics(self) -> Dict[str, any]:
        """
        Get overall statistics from feedback data.

        Returns:
            Dictionary with statistics about feedback
        """
        if not self.feedback_file.exists():
            return {
                "total_records": 0,
                "false_positive_rate": 0.0,
                "confirmed_rate": 0.0,
                "outcomes": {}
            }

        total = 0
        outcomes = {}

        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    total += 1
                    outcome = row['outcome']
                    outcomes[outcome] = outcomes.get(outcome, 0) + 1

            false_positives = outcomes.get('false_positive', 0)
            confirmed = outcomes.get('confirmed_concern', 0)

            return {
                "total_records": total,
                "false_positive_rate": (false_positives / total * 100) if total > 0 else 0.0,
                "confirmed_rate": (confirmed / total * 100) if total > 0 else 0.0,
                "outcomes": outcomes
            }
        except Exception as e:
            print(f"⚠ Warning: Could not calculate statistics: {e}")
            return {"total_records": 0, "error": str(e)}

    def interactive_feedback(self, student_name: str, student_id: str,
                           assignment_name: str, concern_level: str,
                           suspicious_score: float, authenticity_score: float,
                           marker_counts: Optional[Dict[str, int]] = None,
                           esl_detected: bool = False,
                           context_profile: str = "standard") -> Optional[FeedbackRecord]:
        """
        Interactive prompt to collect instructor feedback.

        Args:
            student_name: Student's name
            student_id: Student ID
            assignment_name: Assignment name
            concern_level: Detected concern level
            suspicious_score: Calculated suspicious score
            authenticity_score: Calculated authenticity score
            marker_counts: Dict of marker types and their counts (e.g., {"ai_transitions": 5})
            esl_detected: Whether ESL patterns were detected
            context_profile: Context profile used

        Returns:
            FeedbackRecord if feedback was provided, None if skipped
        """
        print("\n" + "="*60)
        print("INSTRUCTOR FEEDBACK")
        print("="*60)
        print(f"Student: {student_name} ({student_id})")
        print(f"Assignment: {assignment_name}")
        print(f"Concern Level: {concern_level}")
        print(f"Suspicious Score: {suspicious_score}")
        print(f"Authenticity Score: {authenticity_score}")
        if esl_detected:
            print("⚠ ESL patterns detected (human authorship indicator)")
        print()
        print("After your conversation with this student, what was the outcome?")
        print()
        print("  [1] False Positive - Work was legitimate")
        print("  [2] Confirmed Concern - Academic integrity issue")
        print("  [3] Needs Revision - Student needs to improve, but no dishonesty")
        print("  [4] Uncertain - Need more information")
        print("  [S] Skip - Don't record feedback now")
        print()

        choice = input("Enter selection: ").strip().upper()

        outcome_map = {
            '1': 'false_positive',
            '2': 'confirmed_concern',
            '3': 'needs_revision',
            '4': 'uncertain'
        }

        if choice == 'S' or choice == '':
            print("Feedback skipped.")
            return None

        if choice not in outcome_map:
            print("Invalid selection. Feedback skipped.")
            return None

        outcome = outcome_map[choice]

        print()
        notes = input("Optional notes (or Enter to skip): ").strip()

        import json
        markers_json = json.dumps(marker_counts if marker_counts else {})

        record = FeedbackRecord(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            student_id=student_id,
            student_name=student_name,
            assignment_name=assignment_name,
            concern_level=concern_level,
            suspicious_score=suspicious_score,
            authenticity_score=authenticity_score,
            outcome=outcome,
            notes=notes,
            esl_detected=esl_detected,
            context_profile=context_profile,
            markers_present=markers_json
        )

        if self.record_feedback(record):
            print("✅ Feedback recorded successfully.")
            return record
        else:
            print("⚠ Failed to record feedback.")
            return None


    def get_marker_effectiveness(self) -> Dict[str, Dict[str, float]]:
        """
        Analyze which markers are most predictive of actual concerns.

        Returns:
            Dictionary mapping marker types to their effectiveness metrics
        """
        import json

        if not self.feedback_file.exists():
            return {}

        marker_stats = {}
        # Track: for each marker, how often was it present in confirmed vs false positive cases

        try:
            with open(self.feedback_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    outcome = row['outcome']
                    markers_json = row.get('markers_present', '{}')

                    try:
                        markers = json.loads(markers_json)
                    except:
                        markers = {}

                    for marker_type, count in markers.items():
                        if marker_type not in marker_stats:
                            marker_stats[marker_type] = {
                                'confirmed': 0,
                                'false_positive': 0,
                                'needs_revision': 0,
                                'uncertain': 0,
                                'total': 0
                            }

                        marker_stats[marker_type][outcome] += 1
                        marker_stats[marker_type]['total'] += 1

            # Calculate effectiveness metrics
            for marker_type in marker_stats:
                stats = marker_stats[marker_type]
                total = stats['total']
                if total > 0:
                    stats['confirmation_rate'] = (stats['confirmed'] / total) * 100
                    stats['false_positive_rate'] = (stats['false_positive'] / total) * 100
                    stats['precision'] = (stats['confirmed'] / (stats['confirmed'] + stats['false_positive'])) * 100 if (stats['confirmed'] + stats['false_positive']) > 0 else 0

            return marker_stats

        except Exception as e:
            print(f"⚠ Warning: Could not analyze marker effectiveness: {e}")
            return {}


def print_feedback_summary(feedback_file: Optional[Path] = None):
    """Print summary of all feedback collected."""
    tracker = FeedbackTracker(feedback_file)
    stats = tracker.get_statistics()

    if stats['total_records'] == 0:
        print("\nNo feedback records yet.")
        print("Tip: Use interactive_feedback() after conversations with students")
        print("     to track which flags were accurate vs. false positives.")
        return

    print("\n" + "="*60)
    print("FEEDBACK SUMMARY")
    print("="*60)
    print(f"Total records: {stats['total_records']}")
    print(f"False positive rate: {stats['false_positive_rate']:.1f}%")
    print(f"Confirmed concern rate: {stats['confirmed_rate']:.1f}%")
    print()
    print("Outcome breakdown:")
    for outcome, count in stats['outcomes'].items():
        pct = (count / stats['total_records'] * 100)
        outcome_label = outcome.replace('_', ' ').title()
        print(f"  {outcome_label}: {count} ({pct:.1f}%)")

    # Show marker effectiveness
    marker_stats = tracker.get_marker_effectiveness()
    if marker_stats:
        print("\n" + "-"*60)
        print("MARKER EFFECTIVENESS (Sorted by Precision)")
        print("-"*60)
        print(f"{'Marker':<30} {'Total':<8} {'Confirmed':<10} {'False+':<10} {'Precision':<10}")
        print("-"*60)

        # Sort by precision (highest first)
        sorted_markers = sorted(marker_stats.items(), key=lambda x: x[1].get('precision', 0), reverse=True)

        for marker_type, stats in sorted_markers:
            if stats['total'] >= 3:  # Only show markers with at least 3 instances
                marker_label = marker_type.replace('_', ' ').title()[:28]
                print(f"{marker_label:<30} {stats['total']:<8} "
                      f"{stats['confirmed']:<10} {stats['false_positive']:<10} "
                      f"{stats['precision']:.1f}%")

        print("\nPrecision = Confirmed / (Confirmed + False Positives)")
        print("High precision markers are most trustworthy for flagging concerns.")

    print("="*60)
