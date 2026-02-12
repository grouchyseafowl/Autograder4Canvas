"""
Canvas Autograder - Flag Aggregation System
Maintains persistent Excel file with student-level summaries and detailed flag logs.
"""

import pandas as pd
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime


class FlagAggregator:
    """Manages persistent Excel flag log with summary and detail sheets."""

    def __init__(self, excel_path: str):
        """
        Initialize flag aggregator.

        Args:
            excel_path: Path to Excel file for flag storage
        """
        self.excel_path = Path(excel_path)
        self.summary: Dict[int, Dict[str, Any]] = {}  # {student_id: summary_data}
        self.details: List[Dict[str, Any]] = []  # List of detail records
        self.load_existing()

    def load_existing(self):
        """Load existing flag data from Excel."""
        if not self.excel_path.exists():
            return

        try:
            # Load summary sheet
            summary_df = pd.read_excel(self.excel_path, sheet_name='Summary')
            if not summary_df.empty:
                self.summary = summary_df.set_index('Student ID').to_dict('index')

            # Load details sheet
            details_df = pd.read_excel(self.excel_path, sheet_name='Details')
            if not details_df.empty:
                self.details = details_df.to_dict('records')

        except Exception as e:
            # If file corrupt or missing sheets, start fresh
            print(f"⚠️  Could not load existing flags: {e}")
            self.summary = {}
            self.details = []

    def add_flags(self, adc_results: List[Dict[str, Any]]):
        """
        Add new flags from ADC run, updating student totals.

        Args:
            adc_results: List of ADC analysis results with student info
        """
        for result in adc_results:
            # Only process if concern level warrants flagging
            concern_level = result.get('concern_level', 'None')
            if concern_level in ['Low', 'None']:
                continue

            student_id = result.get('student_id')
            student_name = result.get('student_name', 'Unknown')
            course_name = result.get('course_name', 'Unknown')
            assignment_name = result.get('assignment_name', 'Unknown')

            if student_id is None:
                continue

            # Add to details sheet
            self.details.append({
                'Student Name': student_name,
                'Student ID': student_id,
                'Course': course_name,
                'Assignment': assignment_name,
                'Flag Date': datetime.now().strftime('%Y-%m-%d'),
                'Concern Level': concern_level,
                'Suspicious Score': result.get('suspicious_score', 0),
                'Authenticity Score': result.get('authenticity_score', 0),
                'Markers Found': self._format_markers(result),
                'Context': result.get('context_adjustments', '')
            })

            # Update summary
            if student_id in self.summary:
                self.summary[student_id]['Total Flags'] += 1
                self.summary[student_id]['Last Flag Date'] = datetime.now().strftime('%Y-%m-%d')

                # Add course if new
                courses_str = str(self.summary[student_id].get('Courses', ''))
                courses = set(c.strip() for c in courses_str.split(',') if c.strip())
                courses.add(course_name)
                self.summary[student_id]['Courses'] = ', '.join(sorted(courses))

                # Add high-risk assignment if High/Very High concern
                if concern_level in ['High', 'Very High']:
                    high_risk = str(self.summary[student_id].get('High-Risk Assignments', ''))
                    if high_risk:
                        high_risk += f", {assignment_name}"
                    else:
                        high_risk = assignment_name
                    self.summary[student_id]['High-Risk Assignments'] = high_risk
            else:
                # Create new student summary
                self.summary[student_id] = {
                    'Student Name': student_name,
                    'Student ID': student_id,
                    'Total Flags': 1,
                    'Last Flag Date': datetime.now().strftime('%Y-%m-%d'),
                    'Courses': course_name,
                    'High-Risk Assignments': assignment_name
                        if concern_level in ['High', 'Very High'] else ''
                }

    def _format_markers(self, result: Dict[str, Any]) -> str:
        """
        Format detected markers into a readable string.

        Args:
            result: ADC result dictionary

        Returns:
            Formatted marker string
        """
        markers = []

        # AI transition words
        ai_count = result.get('ai_transition_count', 0)
        if ai_count > 0:
            markers.append(f"AI transitions ({ai_count})")

        # Generic phrases
        generic_count = result.get('generic_phrase_count', 0)
        if generic_count > 0:
            markers.append(f"Generic phrases ({generic_count})")

        # Linguistic patterns
        linguistic = result.get('linguistic_patterns', [])
        if linguistic:
            markers.append(f"Linguistic patterns ({len(linguistic)})")

        # Complexity anomalies
        complexity = result.get('complexity_anomaly', False)
        if complexity:
            markers.append("Complexity anomaly")

        # If no markers, return summary
        if not markers:
            return "No specific markers"

        return ', '.join(markers)

    def save(self):
        """Write to Excel with both sheets."""
        # Ensure parent directory exists
        self.excel_path.parent.mkdir(parents=True, exist_ok=True)

        # Create summary DataFrame (sorted by total flags)
        summary_df = pd.DataFrame(self.summary.values())
        if not summary_df.empty:
            summary_df = summary_df.sort_values('Total Flags', ascending=False)

        # Create details DataFrame (sorted by date, newest first)
        details_df = pd.DataFrame(self.details)
        if not details_df.empty:
            details_df = details_df.sort_values('Flag Date', ascending=False)

        # Write to Excel
        try:
            with pd.ExcelWriter(self.excel_path, engine='openpyxl') as writer:
                if not summary_df.empty:
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                else:
                    # Create empty summary sheet
                    pd.DataFrame(columns=[
                        'Student Name', 'Student ID', 'Total Flags',
                        'Last Flag Date', 'Courses', 'High-Risk Assignments'
                    ]).to_excel(writer, sheet_name='Summary', index=False)

                if not details_df.empty:
                    details_df.to_excel(writer, sheet_name='Details', index=False)
                else:
                    # Create empty details sheet
                    pd.DataFrame(columns=[
                        'Student Name', 'Student ID', 'Course', 'Assignment',
                        'Flag Date', 'Concern Level', 'Suspicious Score',
                        'Authenticity Score', 'Markers Found', 'Context'
                    ]).to_excel(writer, sheet_name='Details', index=False)

            print(f"✅ Flags saved to: {self.excel_path}")

        except Exception as e:
            print(f"❌ Failed to save flags: {e}")

    def get_student_flag_count(self, student_id: int) -> int:
        """
        Get total flag count for a student.

        Args:
            student_id: Canvas student ID

        Returns:
            Number of flags
        """
        if student_id in self.summary:
            return self.summary[student_id].get('Total Flags', 0)
        return 0

    def get_students_with_high_flags(self, threshold: int = 5) -> List[Dict[str, Any]]:
        """
        Get students with flag count above threshold.

        Args:
            threshold: Minimum flag count

        Returns:
            List of student summary dictionaries
        """
        high_flag_students = []

        for student_id, summary in self.summary.items():
            if summary.get('Total Flags', 0) >= threshold:
                high_flag_students.append(summary)

        # Sort by total flags descending
        high_flag_students.sort(key=lambda x: x.get('Total Flags', 0), reverse=True)

        return high_flag_students
