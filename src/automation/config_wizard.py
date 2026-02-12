"""
Canvas Autograder - Configuration Wizard
Interactive setup wizard for configuring automation.
"""

import os
import sys
import platform
import subprocess
import plistlib
from pathlib import Path
from typing import List, Dict, Any, Optional

from .canvas_helpers import CanvasAutomationAPI
from .course_config import (
    AutomationConfig, CourseConfig, AssignmentRule,
    GlobalSettings, ConfigValidator
)


class ConfigWizard:
    """Interactive configuration wizard."""

    def __init__(self, update_mode: bool = False):
        """
        Initialize configuration wizard.

        Args:
            update_mode: If True, update existing config instead of creating new
        """
        self.update_mode = update_mode
        self.api = CanvasAutomationAPI()
        self.config: Optional[AutomationConfig] = None

    def run(self):
        """Run the interactive configuration wizard."""
        print()
        print("=" * 60)
        print("  CANVAS AUTOGRADER - AUTOMATION SETUP WIZARD")
        print("=" * 60)
        print()

        # Test Canvas connection
        print("Testing Canvas API connection...")
        if not self.api.test_connection():
            print("❌ Could not connect to Canvas API")
            print("   Please check your CANVAS_API_TOKEN environment variable")
            sys.exit(1)
        print("✅ Connected to Canvas")
        print()

        # Step 1: Detect current semester
        print("Step 1: Detect Current Semester")
        print("-" * 40)
        term_ids = self._select_terms()
        print()

        # Step 2: Select courses
        print("Step 2: Fetch Your Courses")
        print("-" * 40)
        selected_courses = self._select_courses(term_ids)
        print()

        # Create configuration
        self._create_config(term_ids, selected_courses)

        # Step 3: Configure each course (one at a time)
        total_courses = len(selected_courses)
        for idx, course_data in enumerate(selected_courses, 1):
            print()
            print("=" * 60)
            print(f"COURSE {idx} of {total_courses}: {course_data['name']}")
            print("=" * 60)
            self._configure_course(course_data, idx, total_courses)

            # Show summary after configuring this course
            if course_data['id'] in self.config.courses:
                self._show_course_summary(self.config.courses[course_data['id']])

            # Ask if user wants to continue to next course (if not last)
            if idx < total_courses:
                print()
                print("-" * 60)
                continue_choice = input(f"Continue to next course ({selected_courses[idx]['name']})? [Y/n]: ").strip().lower()
                if continue_choice == 'n':
                    print("⏹️  Configuration stopped. Remaining courses not configured.")
                    break
            print()

        # Save configuration
        config_path = self._get_config_path()
        print("Configuration Complete!")
        print("-" * 40)

        # Validate
        errors = ConfigValidator.validate_config(self.config)
        if errors:
            print("⚠️  Configuration has errors:")
            for error in errors:
                print(f"   - {error}")
            print()
            proceed = input("Save anyway? [y/N]: ").strip().lower()
            if proceed != 'y':
                print("Configuration not saved")
                return

        self.config.save(config_path)
        print(f"✅ Configuration saved to: {config_path}")
        print()

        # Show summary
        self._show_summary()

        # Offer to run dry-run
        print()
        print("Options:")
        print("  [1] Run dry-run preview (see what would be graded)")
        print("  [2] Exit (scheduled run will use this config)")
        print()

        choice = input("Choice [2]: ").strip() or "2"
        if choice == "1":
            self._run_dry_run()

        # Generate command reference
        self._generate_command_reference()

    def check_for_updates(self):
        """Check for new courses/assignments by pulling fresh data from Canvas."""
        print("=" * 60)
        print("  CHECK FOR UPDATES")
        print("=" * 60)
        print()

        config_path = self._get_config_path()
        if not config_path.exists():
            print("❌ No existing configuration found")
            print("   Run setup first: python run_automation.py --setup")
            return

        # Load existing config
        self.config = AutomationConfig.load(config_path)

        # Fetch fresh course list from Canvas
        canvas_courses = self._fetch_all_courses()
        if not canvas_courses:
            print("❌ Could not fetch courses from Canvas")
            return

        updates_found = False
        new_courses_found = []
        course_count = len(canvas_courses)

        for idx, course in enumerate(canvas_courses, 1):
            course_id = int(course['id'])
            course_name = course['name']

            print()
            print("=" * 60)
            print(f"CHECKING COURSE {idx} of {course_count}: {course_name}")
            print("=" * 60)

            if course_id not in self.config.courses:
                # Entirely new course
                print(f"  📂 NEW COURSE — not in your configuration yet")
                new_courses_found.append(course)
                add_it = input(f"     Add this course? [y/N]: ").strip().lower()
                if add_it == 'y':
                    self._add_new_course(course)
                    updates_found = True
            else:
                # Existing course — check for new groups
                course_config = self.config.courses[course_id]
                known_group_ids = {rule.assignment_group_id for rule in course_config.assignment_rules}
                new_groups = self.api.check_for_new_assignments(course_id, known_group_ids)

                if new_groups:
                    updates_found = True
                    print(f"  ✅ Found {len(new_groups)} new assignment group(s)")
                    print()

                    for group in new_groups:
                        print(f"  📁 {group['name']}")
                        configure = input(f"     Configure this group? [y/N]: ").strip().lower()
                        if configure == 'y':
                            rule = self._configure_assignment_group(group, course_config.course_name)
                            if rule:
                                course_config.add_rule(rule)
                                print(f"     ✅ Added to configuration")
                        print()
                else:
                    print("  ✅ No new assignment groups")

            # Ask to continue to next course
            if idx < course_count:
                print()
                continue_choice = input(f"Continue to next course? [Y/n]: ").strip().lower()
                if continue_choice == 'n':
                    print("⏹️  Update check stopped.")
                    break

        # Summary
        print()
        print("=" * 60)
        if updates_found:
            self.config.save(config_path)
            print("✅ Configuration updated and saved")
        else:
            print("✅ Configuration is up to date")
        print("=" * 60)

    def _select_terms(self) -> List[int]:
        """
        Select enrollment terms for current semester.

        Returns:
            List of selected term IDs
        """
        print("Fetching enrollment terms from Canvas...")
        terms = self.api.get_current_term_ids()

        if not terms:
            print("❌ No current terms found")
            sys.exit(1)

        print(f"✅ Found {len(terms)} active term(s)")
        print()
        print("Current term(s):")

        for i, term in enumerate(terms, 1):
            print(f"  [{i}] {term['name']} (ID: {term['id']})")
            print(f"      {term['start_at'][:10]} to {term['end_at'][:10]}")

        print()

        if len(terms) == 1:
            print(f"Using term: {terms[0]['name']}")
            return [terms[0]['id']]

        # Multiple terms - let user select
        while True:
            selection = input("Select term(s) [1,2 or 'all']: ").strip().lower()

            if selection == 'all':
                return [t['id'] for t in terms]

            try:
                indices = [int(s.strip()) - 1 for s in selection.split(',')]
                if all(0 <= i < len(terms) for i in indices):
                    return [terms[i]['id'] for i in indices]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Invalid input. Enter numbers separated by commas or 'all'")

    def _select_courses(self, term_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Select courses to configure.

        Args:
            term_ids: List of term IDs to fetch courses from

        Returns:
            List of selected course dictionaries
        """
        all_courses = []

        for term_id in term_ids:
            print(f"Fetching courses for term {term_id}...")
            courses = self.api.get_courses_in_term(term_id)
            all_courses.extend(courses)

        if not all_courses:
            print("❌ No courses found where you are teacher")
            sys.exit(1)

        print(f"✅ Found {len(all_courses)} course(s)")
        print()
        print("Your courses:")

        for i, course in enumerate(all_courses, 1):
            print(f"  [{i}] {course['name']} (ID: {course['id']})")

        print()

        while True:
            selection = input("Select courses [1,2 or 'all']: ").strip().lower()

            if selection == 'all':
                return all_courses

            try:
                indices = [int(s.strip()) - 1 for s in selection.split(',')]
                if all(0 <= i < len(all_courses) for i in indices):
                    return [all_courses[i] for i in indices]
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Invalid input. Enter numbers separated by commas or 'all'")

    def _create_config(self, term_ids: List[int], selected_courses: List[Dict[str, Any]]):
        """
        Create initial configuration object.

        Args:
            term_ids: List of term IDs
            selected_courses: List of selected courses
        """
        # Set up paths
        repo_dir = Path(__file__).parent.parent.parent
        log_path = str(Path.home() / "Documents" / "Autograder Rationales" / "automation.log")
        flag_path = str(repo_dir / "autograder_flags.xlsx")

        # Create config
        self.config = AutomationConfig.create_default(term_ids, log_path, flag_path)

    def _configure_course(self, course_data: Dict[str, Any], course_num: int, total_courses: int):
        """
        Configure assignment rules for a course.

        Args:
            course_data: Course dictionary from Canvas API
            course_num: Current course number (1-indexed)
            total_courses: Total number of courses to configure
        """
        course_id = course_data['id']
        course_name = course_data['name']

        print()
        print(f"📚 Fetching assignment groups for {course_name}...")
        groups = self.api.get_assignment_groups(course_id)

        if not groups:
            print("  ⚠️  No assignment groups found in this course")
            return

        print(f"✅ Found {len(groups)} assignment group(s)")
        print()
        print("Available assignment groups:")
        print("-" * 60)

        for i, group in enumerate(groups, 1):
            assignment_count = len(group.get('assignments', []))
            print(f"  [{i}] {group['name']}")
            print(f"      ({assignment_count} assignment(s))")

        print("-" * 60)
        print()

        while True:
            selection = input("Select groups to auto-grade [1,2,3 or 'all' or 'none']: ").strip().lower()

            if selection == 'none':
                print("⏭️  Skipping this course")
                return

            if selection == 'all':
                selected_groups = groups
                break

            try:
                indices = [int(s.strip()) - 1 for s in selection.split(',')]
                if all(0 <= i < len(groups) for i in indices):
                    selected_groups = [groups[i] for i in indices]
                    break
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Invalid input. Enter numbers separated by commas, 'all', or 'none'")

        # Create course config
        term_id = self.config.global_settings.current_semester_term_ids[0]

        course_config = CourseConfig(
            course_id=course_id,
            course_name=course_name,
            semester_term_id=term_id,
            enabled=True
        )

        # Configure each selected group one by one
        print()
        print("=" * 60)
        print(f"Now configuring {len(selected_groups)} assignment group(s) for this course")
        print("=" * 60)

        for idx, group in enumerate(selected_groups, 1):
            print()
            print(f"📁 Assignment Group {idx} of {len(selected_groups)}")
            print("-" * 60)
            rule = self._configure_assignment_group(group, course_name)
            if rule:
                course_config.add_rule(rule)
                print(f"   ✅ Configured: {group['name']}")
            else:
                print(f"   ⏭️  Skipped: {group['name']}")

        # Add to main config
        if course_config.assignment_rules:
            self.config.add_course(course_config)
            print()
            print(f"✅ Course configuration complete: {course_name}")
            print(f"   {len(course_config.assignment_rules)} assignment group(s) will be auto-graded")
        else:
            print()
            print(f"⚠️  No assignment groups configured for {course_name}")

    def _configure_assignment_group(self, group: Dict[str, Any],
                                    course_name: str) -> Optional[AssignmentRule]:
        """
        Configure a single assignment group.

        Args:
            group: Assignment group dictionary
            course_name: Course name for display

        Returns:
            Configured AssignmentRule or None if skipped
        """
        print()
        print(f"Configuring: {group['name']}")

        # Ask for assignment type
        while True:
            type_choice = input("  Assignment type? [C]omplete/Incomplete, [D]iscussion, [S]kip: ").strip().upper()

            if type_choice == 'S':
                return None

            if type_choice in ['C', 'D']:
                break

            print("  ❌ Please enter C, D, or S")

        # Create rule based on type
        if type_choice == 'C':
            return self._configure_complete_incomplete(group)
        else:
            return self._configure_discussion(group)

    def _configure_complete_incomplete(self, group: Dict[str, Any]) -> AssignmentRule:
        """Configure complete/incomplete assignment group."""
        min_words = input("  Minimum word count [200]: ").strip() or "200"
        run_adc = input("  Run academic dishonesty check? [Y/n]: ").strip().lower()

        return AssignmentRule(
            rule_id=f"rule_{group['id']}",
            assignment_group_name=group['name'],
            assignment_group_id=group['id'],
            assignment_type="complete_incomplete",
            min_word_count=int(min_words),
            run_adc=(run_adc != 'n'),
            preserve_existing_grades=True
        )

    def _configure_discussion(self, group: Dict[str, Any]) -> AssignmentRule:
        """Configure discussion forum assignment group with grading mode and type selection."""
        print()
        print("  How should posts and replies be graded?")
        print("  [S] Separate — posts and replies checked independently")
        print("      Example: need 1 post (200 words) AND 2 replies (50 words each)")
        print("  [C] Combined — total word count across all messages")
        print("      Example: need 300 total words across posts + replies")
        print()

        while True:
            mode_choice = input("  Grading mode [S/C]: ").strip().upper()
            if mode_choice in ['S', 'C']:
                break
            print("  ❌ Please enter S or C")

        mode = "separate" if mode_choice == 'S' else "combined"

        if mode == "separate":
            # Ask grading type: points vs complete/incomplete
            print()
            print("  How should the grade be reported?")
            print("  [P] Points — numeric score (post earns X pts, each reply earns Y pts)")
            print("  [I] Complete/Incomplete — pass/fail based on meeting minimums")
            print()

            while True:
                type_choice = input("  Grading type [P/I]: ").strip().upper()
                if type_choice in ['P', 'I']:
                    break
                print("  ❌ Please enter P or I")

            grading_type = "points" if type_choice == 'P' else "complete_incomplete"

            if grading_type == "points":
                # Points mode: configure point values
                print()
                print("  --- Post Settings ---")
                post_words = input("  Words per post to qualify [200]: ").strip() or "200"
                post_pts = input("  Points for a qualifying post [1.0]: ").strip() or "1.0"

                print()
                print("  --- Reply Settings ---")
                reply_words = input("  Words per reply to qualify [50]: ").strip() or "50"
                reply_pts = input("  Points per qualifying reply [0.5]: ").strip() or "0.5"

                print()
                print(f"  Example: 1 post + 3 replies = {float(post_pts) + 3 * float(reply_pts):.1f} pts")
                print(f"           1 post + 0 replies = {float(post_pts):.1f} pts")

                rule = AssignmentRule(
                    rule_id=f"rule_{group['id']}",
                    assignment_group_name=group['name'],
                    assignment_group_id=group['id'],
                    assignment_type="discussion_forum",
                    discussion_grading_mode="separate",
                    grading_type="points",
                    post_min_words=int(post_words),
                    post_points=float(post_pts),
                    reply_min_words=int(reply_words),
                    reply_points=float(reply_pts),
                    run_adc=(input("  Run academic dishonesty check? [Y/n]: ").strip().lower() != 'n'),
                    preserve_existing_grades=True
                )
            else:
                # Complete/Incomplete mode: configure minimums
                print()
                print("  --- Posts ---")
                min_posts = input("  Minimum qualifying posts [1] (0 = don't check posts): ").strip() or "1"
                post_words = input("  Words per post to qualify [200]: ").strip() or "200"

                print()
                print("  --- Replies ---")
                min_replies = input("  Minimum qualifying replies [2] (0 = don't check replies): ").strip() or "2"
                reply_words = input("  Words per reply to qualify [50]: ").strip() or "50"

                rule = AssignmentRule(
                    rule_id=f"rule_{group['id']}",
                    assignment_group_name=group['name'],
                    assignment_group_id=group['id'],
                    assignment_type="discussion_forum",
                    discussion_grading_mode="separate",
                    grading_type="complete_incomplete",
                    min_posts=int(min_posts),
                    post_min_words=int(post_words),
                    min_replies=int(min_replies),
                    reply_min_words=int(reply_words),
                    run_adc=(input("  Run academic dishonesty check? [Y/n]: ").strip().lower() != 'n'),
                    preserve_existing_grades=True
                )
        else:
            # Combined mode: single total word count threshold (always complete/incomplete)
            total_words = input("  Total minimum words across all messages [250]: ").strip() or "250"

            rule = AssignmentRule(
                rule_id=f"rule_{group['id']}",
                assignment_group_name=group['name'],
                assignment_group_id=group['id'],
                assignment_type="discussion_forum",
                discussion_grading_mode="combined",
                grading_type="complete_incomplete",
                post_min_words=int(total_words),  # used as total threshold in combined mode
                reply_min_words=0,
                run_adc=(input("  Run academic dishonesty check? [Y/n]: ").strip().lower() != 'n'),
                preserve_existing_grades=True
            )

        return rule

    def _show_course_summary(self, course_config: CourseConfig):
        """
        Show summary for a single course configuration.

        Args:
            course_config: Course configuration to summarize
        """
        print()
        print("─" * 60)
        print(f"📋 SUMMARY: {course_config.course_name}")
        print("─" * 60)

        if not course_config.assignment_rules:
            print("  ⚠️  No assignment groups configured")
            return

        for idx, rule in enumerate(course_config.assignment_rules, 1):
            print(f"\n  {idx}. {rule.assignment_group_name}")
            print(f"     Type: {rule.assignment_type}")

            if rule.assignment_type == "complete_incomplete":
                print(f"     Minimum words: {rule.min_word_count}")
            elif rule.assignment_type == "discussion_forum":
                mode = rule.discussion_grading_mode or "separate"
                gtype = rule.grading_type or "complete_incomplete"
                print(f"     Mode: {mode.upper()} | Grading: {gtype.replace('_', ' ').title()}")
                if mode == "separate":
                    if gtype == "points":
                        print(f"     Post: {rule.post_min_words} words → {rule.post_points or 1.0} pts")
                        print(f"     Reply: {rule.reply_min_words or 50} words → {rule.reply_points or 0.5} pts each")
                    else:
                        print(f"     Posts: need {rule.min_posts or 1} post(s) of {rule.post_min_words} words each")
                        print(f"     Replies: need {rule.min_replies or 2} reply(s) of {rule.reply_min_words or 50} words each")
                else:
                    print(f"     Total minimum: {rule.post_min_words} words across all messages")

            print(f"     Academic dishonesty check: {'Yes' if rule.run_adc else 'No'}")
            print(f"     Preserve existing grades: {'Yes' if rule.preserve_existing_grades else 'No'}")

        print()
        print(f"✅ {len(course_config.assignment_rules)} assignment group(s) configured")
        print("─" * 60)

    def _show_summary(self):
        """Show configuration summary."""
        print()
        print("=" * 60)
        print("FINAL CONFIGURATION SUMMARY")
        print("=" * 60)
        print()
        print(f"✅ {len(self.config.courses)} course(s) configured")

        total_groups = sum(
            len(course.assignment_rules)
            for course in self.config.courses.values()
        )
        print(f"✅ {total_groups} assignment group(s) will be auto-graded")
        print()

        for idx, course in enumerate(self.config.courses.values(), 1):
            print(f"{idx}. {course.course_name}:")
            if course.assignment_rules:
                for rule in course.assignment_rules:
                    type_label = "C/I" if rule.assignment_type == "complete_incomplete" else "Discussion"
                    print(f"   • {rule.assignment_group_name} ({type_label})")
            else:
                print(f"   • No assignment groups")
        print()
        print("=" * 60)

    def _get_config_path(self) -> Path:
        """Get configuration file path."""
        repo_dir = Path(__file__).parent.parent.parent
        return repo_dir / ".autograder_config" / "course_configs.json"

    def _fetch_all_courses(self) -> List[Dict[str, Any]]:
        """
        Fetch all instructor courses for current semester from Canvas.

        Returns:
            List of course dictionaries from Canvas API, sorted by name
        """
        print("Fetching your courses from Canvas...")
        terms = self.api.get_current_term_ids()

        if not terms:
            print("❌ No current terms found on Canvas")
            return []

        all_courses = []
        for term in terms:
            courses = self.api.get_courses_in_term(term['id'])
            for course in courses:
                course['_term_name'] = term['name']
                course['_term_id'] = term['id']
            all_courses.extend(courses)

        # Sort by name for consistent display
        all_courses.sort(key=lambda c: c['name'])
        return all_courses

    def _display_course_list(self, canvas_courses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Display all Canvas courses with configured/unconfigured status.

        Args:
            canvas_courses: Fresh list of courses from Canvas API

        Returns:
            The same list (for reference by index)
        """
        print()
        print("=" * 60)
        print("  YOUR COURSES (Current Semester)")
        print("=" * 60)
        print()

        for i, course in enumerate(canvas_courses, 1):
            course_id = int(course['id'])
            if self.config and course_id in self.config.courses:
                cfg = self.config.courses[course_id]
                rule_count = len(cfg.assignment_rules)
                status = "✅ Enabled" if cfg.enabled else "⚠️  Disabled"
                print(f"  [{i}] {course['name']}")
                print(f"       {status} — {rule_count} group(s) configured")
            else:
                print(f"  [{i}] {course['name']}")
                print(f"       ○ Not configured")

        print()
        print("-" * 60)
        return canvas_courses

    def edit_configuration(self):
        """Edit existing configuration — pulls live courses from Canvas."""
        print()
        print("=" * 60)
        print("  EDIT AUTOMATION CONFIGURATION")
        print("=" * 60)
        print()

        config_path = self._get_config_path()

        # Load existing config (or create empty one if none exists)
        if config_path.exists():
            self.config = AutomationConfig.load(config_path)
        else:
            # Start with empty config so user can add courses from scratch
            repo_dir = Path(__file__).parent.parent.parent
            log_path = str(Path.home() / "Documents" / "Autograder Rationales" / "automation.log")
            flag_path = str(repo_dir / "autograder_flags.xlsx")
            self.config = AutomationConfig.create_default([], log_path, flag_path)

        # Fetch fresh course list from Canvas
        canvas_courses = self._fetch_all_courses()
        if not canvas_courses:
            print("❌ Could not fetch courses. Check your Canvas API token.")
            return

        while True:
            # Display all courses with status
            self._display_course_list(canvas_courses)

            print("Options:")
            print("  [1-9]  Select a course to edit/configure")
            print("  [T]    Toggle course enabled/disabled")
            print("  [G]    Edit global settings")
            print("  [S]    Save and exit")
            print("  [X]    Exit without saving")
            print()

            choice = input("Select option: ").strip().upper()

            if choice == 'S':
                self.config.save(config_path)
                print()
                print("✅ Configuration saved")
                self._show_summary()
                break
            elif choice == 'X':
                print()
                print("⚠️  Exiting without saving changes")
                break
            elif choice == 'T':
                self._edit_toggle_by_list(canvas_courses)
            elif choice == 'G':
                self._edit_global_settings()
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(canvas_courses):
                    course = canvas_courses[idx]
                    course_id = int(course['id'])
                    if course_id in self.config.courses:
                        # Already configured — edit it
                        self._edit_course_details(self.config.courses[course_id])
                    else:
                        # Not configured — offer to add it
                        self._add_new_course(course)
                else:
                    print("❌ Invalid course number")
            else:
                print("❌ Invalid option")

    def _add_new_course(self, course_data: Dict[str, Any]):
        """
        Add a brand-new course to the configuration.

        Args:
            course_data: Course dictionary from Canvas API
        """
        course_id = course_data['id']
        course_name = course_data['name']

        print()
        print("=" * 60)
        print(f"ADD COURSE: {course_name}")
        print("=" * 60)

        confirm = input(f"\nAdd {course_name} to your automation config? [Y/n]: ").strip().lower()
        if confirm == 'n':
            return

        # Fetch assignment groups
        print(f"\n📚 Fetching assignment groups for {course_name}...")
        groups = self.api.get_assignment_groups(course_id)

        if not groups:
            print("  ⚠️  No assignment groups found in this course")
            return

        print(f"✅ Found {len(groups)} assignment group(s)\n")
        print("Available assignment groups:")
        print("-" * 60)
        for i, group in enumerate(groups, 1):
            assignment_count = len(group.get('assignments', []))
            print(f"  [{i}] {group['name']} ({assignment_count} assignment(s))")
        print("-" * 60)
        print()

        while True:
            selection = input("Select groups to auto-grade [1,2,3 or 'all' or 'none']: ").strip().lower()

            if selection == 'none':
                print("⏭️  Skipping this course")
                return

            if selection == 'all':
                selected_groups = groups
                break

            try:
                indices = [int(s.strip()) - 1 for s in selection.split(',')]
                if all(0 <= i < len(groups) for i in indices):
                    selected_groups = [groups[i] for i in indices]
                    break
                else:
                    print("❌ Invalid selection. Please try again.")
            except ValueError:
                print("❌ Invalid input. Enter numbers separated by commas, 'all', or 'none'")

        # Create course config
        term_id = course_data.get('_term_id', 0)
        course_config = CourseConfig(
            course_id=course_id,
            course_name=course_name,
            semester_term_id=term_id,
            enabled=True
        )

        # Configure each selected group
        for idx, group in enumerate(selected_groups, 1):
            print()
            print(f"📁 Assignment Group {idx} of {len(selected_groups)}")
            print("-" * 60)
            rule = self._configure_assignment_group(group, course_name)
            if rule:
                course_config.add_rule(rule)
                print(f"   ✅ Configured: {group['name']}")
            else:
                print(f"   ⏭️  Skipped: {group['name']}")

        # Add to main config
        if course_config.assignment_rules:
            self.config.add_course(course_config)
            print()
            self._show_course_summary(course_config)
        else:
            print()
            print(f"⚠️  No assignment groups configured for {course_name}")

    def _edit_course_details(self, course_config: CourseConfig):
        """Edit details of assignment groups in a course — with inline add/delete."""
        while True:
            print()
            print("=" * 60)
            print(f"EDITING: {course_config.course_name}")
            print("=" * 60)
            print()

            if course_config.assignment_rules:
                print("Assignment Groups:")
                print("-" * 60)
                for i, rule in enumerate(course_config.assignment_rules, 1):
                    print(f"  [{i}] {rule.assignment_group_name}")
                    print(f"      Type: {rule.assignment_type}")
                    if rule.assignment_type == "complete_incomplete":
                        print(f"      Min words: {rule.min_word_count}")
                    elif rule.assignment_type == "discussion_forum":
                        mode = rule.discussion_grading_mode or "separate"
                        gtype = rule.grading_type or "complete_incomplete"
                        if mode == "separate":
                            if gtype == "points":
                                print(f"      Mode: SEPARATE | Points | Post: {rule.post_min_words or 200}w → {rule.post_points or 1.0} pts | Reply: {rule.reply_min_words or 50}w → {rule.reply_points or 0.5} pts each")
                            else:
                                print(f"      Mode: SEPARATE | C/I | Posts: {rule.min_posts or 1}x{rule.post_min_words or 200}w | Replies: {rule.min_replies or 2}x{rule.reply_min_words or 50}w")
                        else:
                            print(f"      Mode: COMBINED | Total min: {rule.post_min_words} words")
                    print(f"      ADC: {'Yes' if rule.run_adc else 'No'}")
                    print()
                print("-" * 60)
            else:
                print("  (No assignment groups configured yet)")
                print("-" * 60)

            print()
            print("Options:")
            print("  [1-9]  Edit a specific group's settings")
            print("  [A]    Add new assignment groups")
            print("  [D]    Delete an assignment group")
            print("  [B]    Back to course list")
            print()

            choice = input("Select option: ").strip().upper()

            if choice == 'B' or choice == '':
                return
            elif choice == 'A':
                self._edit_add_groups_for_course(course_config)
            elif choice == 'D':
                self._edit_delete_groups_for_course(course_config)
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(course_config.assignment_rules):
                    rule = course_config.assignment_rules[idx]
                    self._edit_assignment_rule(rule)
                else:
                    print("❌ Invalid group number")
            else:
                print("❌ Invalid option")

    def _edit_assignment_rule(self, rule: AssignmentRule):
        """Edit a specific assignment rule."""
        print()
        print(f"Editing: {rule.assignment_group_name}")
        print()

        # Allow switching assignment type
        current_type = "C/I" if rule.assignment_type == "complete_incomplete" else "Discussion"
        print(f"  Current type: {current_type}")
        print(f"  [C] Complete/Incomplete  [D] Discussion Forum  [Enter] Keep current")
        type_choice = input(f"  Change type? ").strip().upper()
        if type_choice == 'C' and rule.assignment_type != "complete_incomplete":
            rule.assignment_type = "complete_incomplete"
            rule.min_word_count = rule.min_word_count or 200
            print(f"  ✅ Switched to Complete/Incomplete")
        elif type_choice == 'D' and rule.assignment_type != "discussion_forum":
            rule.assignment_type = "discussion_forum"
            rule.discussion_grading_mode = rule.discussion_grading_mode or "separate"
            rule.grading_type = rule.grading_type or "complete_incomplete"
            rule.post_min_words = rule.post_min_words or 200
            rule.reply_min_words = rule.reply_min_words or 50
            print(f"  ✅ Switched to Discussion Forum")
        print()

        if rule.assignment_type == "complete_incomplete":
            new_words = input(f"  Minimum word count [{rule.min_word_count}]: ").strip()
            if new_words:
                rule.min_word_count = int(new_words)
        elif rule.assignment_type == "discussion_forum":
            current_mode = rule.discussion_grading_mode or "separate"
            print(f"  Current mode: {current_mode.upper()}")
            print(f"  [S] Separate  [C] Combined  [Enter] Keep current")
            mode_choice = input(f"  Change mode? ").strip().upper()
            if mode_choice == 'S':
                rule.discussion_grading_mode = "separate"
                current_mode = "separate"
            elif mode_choice == 'C':
                rule.discussion_grading_mode = "combined"
                current_mode = "combined"

            if current_mode == "separate":
                # Show/edit grading type (points vs complete_incomplete)
                current_gtype = rule.grading_type or "complete_incomplete"
                print(f"  Current grading type: {current_gtype.replace('_', ' ').title()}")
                print(f"  [P] Points  [I] Complete/Incomplete  [Enter] Keep current")
                gtype_choice = input(f"  Change grading type? ").strip().upper()
                if gtype_choice == 'P':
                    rule.grading_type = "points"
                    current_gtype = "points"
                elif gtype_choice == 'I':
                    rule.grading_type = "complete_incomplete"
                    current_gtype = "complete_incomplete"

                if current_gtype == "points":
                    # Points mode: word thresholds + point values
                    print()
                    print("  --- Post Settings ---")
                    new_post = input(f"  Words per post to qualify [{rule.post_min_words or 200}]: ").strip()
                    if new_post:
                        rule.post_min_words = int(new_post)

                    new_post_pts = input(f"  Points for a qualifying post [{rule.post_points or 1.0}]: ").strip()
                    if new_post_pts:
                        rule.post_points = float(new_post_pts)

                    print()
                    print("  --- Reply Settings ---")
                    new_reply = input(f"  Words per reply to qualify [{rule.reply_min_words or 50}]: ").strip()
                    if new_reply:
                        rule.reply_min_words = int(new_reply)

                    new_reply_pts = input(f"  Points per qualifying reply [{rule.reply_points or 0.5}]: ").strip()
                    if new_reply_pts:
                        rule.reply_points = float(new_reply_pts)

                    print()
                    post_pts = rule.post_points or 1.0
                    reply_pts = rule.reply_points or 0.5
                    print(f"  Example: 1 post + 3 replies = {post_pts + 3 * reply_pts:.1f} pts")
                else:
                    # Complete/incomplete mode: min counts + word thresholds
                    new_min_posts = input(f"  Min qualifying posts [{rule.min_posts or 1}]: ").strip()
                    if new_min_posts:
                        rule.min_posts = int(new_min_posts)

                    new_post = input(f"  Words per post to qualify [{rule.post_min_words or 200}]: ").strip()
                    if new_post:
                        rule.post_min_words = int(new_post)

                    new_min_replies = input(f"  Min qualifying replies [{rule.min_replies or 2}]: ").strip()
                    if new_min_replies:
                        rule.min_replies = int(new_min_replies)

                    new_reply = input(f"  Words per reply to qualify [{rule.reply_min_words or 50}]: ").strip()
                    if new_reply:
                        rule.reply_min_words = int(new_reply)
            else:  # combined
                new_total = input(f"  Total min words [{rule.post_min_words}]: ").strip()
                if new_total:
                    rule.post_min_words = int(new_total)

        adc_choice = input(f"  Run ADC? [Y/n] (current: {'Yes' if rule.run_adc else 'No'}): ").strip().lower()
        if adc_choice:
            rule.run_adc = (adc_choice == 'y')

        print()
        print("✅ Rule updated")

    def _edit_add_groups_for_course(self, course_config: CourseConfig):
        """Add new assignment groups to a specific course (called from within course edit)."""
        print(f"\nFetching assignment groups for {course_config.course_name}...")

        groups = self.api.get_assignment_groups(course_config.course_id)
        known_group_ids = {rule.assignment_group_id for rule in course_config.assignment_rules}

        # Filter to only unconfigured groups
        available_groups = [g for g in groups if g['id'] not in known_group_ids]

        if not available_groups:
            print("⚠️  All assignment groups already configured")
            return

        print()
        print("Available groups to add:")
        print("-" * 60)
        for i, group in enumerate(available_groups, 1):
            assignment_count = len(group.get('assignments', []))
            print(f"  [{i}] {group['name']} ({assignment_count} assignment(s))")
        print("-" * 60)
        print()

        selection = input("Select groups to add [1,2,3 or 'all']: ").strip().lower()

        if selection == 'all':
            selected_groups = available_groups
        else:
            try:
                indices = [int(s.strip()) - 1 for s in selection.split(',')]
                selected_groups = [available_groups[i] for i in indices if 0 <= i < len(available_groups)]
            except (ValueError, IndexError):
                print("❌ Invalid selection")
                return

        # Configure each selected group
        for group in selected_groups:
            print()
            print("-" * 60)
            rule = self._configure_assignment_group(group, course_config.course_name)
            if rule:
                course_config.add_rule(rule)
                print(f"✅ Added: {group['name']}")

    def _edit_delete_groups_for_course(self, course_config: CourseConfig):
        """Delete assignment groups from a specific course (called from within course edit)."""
        if not course_config.assignment_rules:
            print("⚠️  No assignment groups configured for this course")
            return

        print()
        print(f"Assignment groups in {course_config.course_name}:")
        for i, rule in enumerate(course_config.assignment_rules, 1):
            print(f"  [{i}] {rule.assignment_group_name}")
        print()

        selection = input("Select groups to delete [1,2,3]: ").strip()
        try:
            indices = [int(s.strip()) - 1 for s in selection.split(',')]
            # Remove in reverse order to maintain indices
            for idx in sorted(indices, reverse=True):
                if 0 <= idx < len(course_config.assignment_rules):
                    removed_rule = course_config.assignment_rules.pop(idx)
                    print(f"✅ Deleted: {removed_rule.assignment_group_name}")
        except (ValueError, IndexError):
            print("❌ Invalid selection")

    def _edit_global_settings(self):
        """Edit global automation settings (skip future, skip no submissions, etc.)."""
        if not self.config or not self.config.global_settings:
            print("⚠️  No global settings available")
            return

        gs = self.config.global_settings

        while True:
            print()
            print("=" * 60)
            print("  GLOBAL SETTINGS")
            print("=" * 60)
            print()
            print(f"  [1] Skip future assignments:    {'ON  ✅' if gs.skip_future_assignments else 'OFF ❌'}")
            print(f"      (Don't grade assignments whose due date hasn't passed)")
            print()
            print(f"  [2] Skip no-submission checks:  {'ON  ✅' if gs.skip_no_submissions else 'OFF ❌'}")
            print(f"      (Don't process assignments with zero submissions)")
            print()
            print(f"  [3] Auto-update on run:         {'ON  ✅' if gs.auto_update_enabled else 'OFF ❌'}")
            print(f"      (Check for new assignment groups each time automation runs)")
            print()
            if platform.system() == "Darwin":
                print(f"  [4] Edit run schedule           (change what time automation runs)")
                print()
            notif_status = "ON  ✅" if (gs.notify_email and gs.n8n_webhook_url) else "OFF ❌"
            print(f"  [5] Incomplete notifications:  {notif_status}")
            if gs.notify_email:
                print(f"      → {gs.notify_email}")
            else:
                print(f"      (email you when students are marked incomplete)")
            print()
            print("  [B] Back to main menu")
            print()

            choice = input("Select option: ").strip().upper()

            if choice == 'B' or choice == '':
                return
            elif choice == '1':
                gs.skip_future_assignments = not gs.skip_future_assignments
                state = "ON" if gs.skip_future_assignments else "OFF"
                print(f"  ✅ Skip future assignments is now {state}")
            elif choice == '2':
                gs.skip_no_submissions = not gs.skip_no_submissions
                state = "ON" if gs.skip_no_submissions else "OFF"
                print(f"  ✅ Skip no-submission checks is now {state}")
            elif choice == '3':
                gs.auto_update_enabled = not gs.auto_update_enabled
                state = "ON" if gs.auto_update_enabled else "OFF"
                print(f"  ✅ Auto-update on run is now {state}")
            elif choice == '4' and platform.system() == "Darwin":
                self._edit_schedule()
            elif choice == '5':
                self._edit_notifications()
            else:
                print("  ❌ Invalid option")

    def _edit_schedule(self):
        """Edit the automation run schedule (launchd plist + pmset wake)."""
        plist_path = Path.home() / "Library" / "LaunchAgents" / "com.autograder.automation.plist"

        # Read current schedule from launchd plist
        current_hour = None
        current_minute = None
        if plist_path.exists():
            try:
                with open(plist_path, 'rb') as f:
                    plist_data = plistlib.load(f)
                interval = plist_data.get('StartCalendarInterval', {})
                current_hour = interval.get('Hour')
                current_minute = interval.get('Minute')
            except Exception:
                pass

        print()
        if current_hour is not None:
            print(f"  Current schedule: {current_hour}:{current_minute:02d} daily")
            print(f"  (wake at {current_hour}:{current_minute - 5:02d} via pmset)")
        else:
            print(f"  Could not read current schedule")
            print(f"  (plist expected at: {plist_path})")
        print()

        # Get new time
        new_hour_str = input(f"  New hour (0-23) [{current_hour or 5}]: ").strip()
        new_minute_str = input(f"  New minute (0-59) [{current_minute or 0}]: ").strip()

        new_hour = int(new_hour_str) if new_hour_str else (current_hour if current_hour is not None else 5)
        new_minute = int(new_minute_str) if new_minute_str else (current_minute if current_minute is not None else 0)

        if not (0 <= new_hour <= 23 and 0 <= new_minute <= 59):
            print("  ❌ Invalid time")
            return

        # Calculate wake time (5 minutes before)
        wake_minute = new_minute - 5
        wake_hour = new_hour
        if wake_minute < 0:
            wake_minute += 60
            wake_hour -= 1
            if wake_hour < 0:
                wake_hour = 23

        # Update launchd plist
        if plist_path.exists():
            try:
                with open(plist_path, 'rb') as f:
                    plist_data = plistlib.load(f)
                plist_data['StartCalendarInterval'] = {
                    'Hour': new_hour,
                    'Minute': new_minute
                }
                with open(plist_path, 'wb') as f:
                    plistlib.dump(plist_data, f)

                # Reload launchd job
                subprocess.run(['launchctl', 'unload', str(plist_path)], capture_output=True)
                subprocess.run(['launchctl', 'load', str(plist_path)], capture_output=True)
                print(f"  ✅ Updated launchd schedule to {new_hour}:{new_minute:02d}")
            except Exception as e:
                print(f"  ❌ Failed to update launchd: {e}")
        else:
            print(f"  ⚠️  Launchd plist not found — skipping launchd update")

        # Update pmset wake schedule
        wake_time = f"{wake_hour:02d}:{wake_minute:02d}:00"
        try:
            result = subprocess.run(
                ['sudo', 'pmset', 'repeat', 'wakeorpoweron', 'MTWRFSU', wake_time],
                capture_output=True, text=True
            )
            if result.returncode == 0:
                print(f"  ✅ Updated pmset wake to {wake_hour}:{wake_minute:02d}")
            else:
                print(f"  ⚠️  pmset requires sudo — enter your password if prompted")
                # Retry without capture so password prompt shows
                subprocess.run(
                    ['sudo', 'pmset', 'repeat', 'wakeorpoweron', 'MTWRFSU', wake_time]
                )
        except Exception as e:
            print(f"  ⚠️  Could not update pmset: {e}")
            print(f"  Run manually: sudo pmset repeat wakeorpoweron MTWRFSU {wake_time}")

        print()
        print(f"  New schedule: wake {wake_hour}:{wake_minute:02d} → run {new_hour}:{new_minute:02d}")

    def _edit_notifications(self):
        """Edit incomplete-notification settings (email + n8n webhook URL)."""
        gs = self.config.global_settings

        print()
        print("=" * 60)
        print("  INCOMPLETE NOTIFICATIONS")
        print("=" * 60)
        print()
        print("  Sends a daily digest email listing students who were")
        print("  marked incomplete (didn't meet word count).")
        print("  Uses an n8n webhook to send via your Gmail.")
        print()

        while True:
            active = bool(gs.notify_email and gs.n8n_webhook_url)
            print(f"  Status: {'ON  ✅' if active else 'OFF ❌'}")
            if gs.notify_email:
                print(f"  Email:   {gs.notify_email}")
            if gs.n8n_webhook_url:
                print(f"  Webhook: {gs.n8n_webhook_url[:60]}...")
            print()
            print("  [E] Edit email address")
            print("  [W] Edit n8n webhook URL")
            print("  [B] Back")
            print()

            choice = input("  Select: ").strip().upper()

            if choice == 'B' or choice == '':
                return
            elif choice == 'E':
                new_email = input(f"  Email [{gs.notify_email or 'none'}]: ").strip()
                if new_email:
                    gs.notify_email = new_email
                    print(f"  ✅ Email set to {new_email}")
                else:
                    gs.notify_email = ""
                    print(f"  ✅ Email cleared (notifications disabled)")
            elif choice == 'W':
                new_url = input(f"  Webhook URL [{'set' if gs.n8n_webhook_url else 'none'}]: ").strip()
                if new_url:
                    gs.n8n_webhook_url = new_url
                    print(f"  ✅ Webhook URL set")
                else:
                    gs.n8n_webhook_url = ""
                    print(f"  ✅ Webhook URL cleared (notifications disabled)")
            else:
                print("  ❌ Invalid option")

    def _edit_toggle_by_list(self, canvas_courses: List[Dict[str, Any]]):
        """Toggle a course enabled/disabled, using the full Canvas course list."""
        print()
        print("Toggle Course Enabled/Disabled:")
        print("-" * 60)
        for i, course in enumerate(canvas_courses, 1):
            course_id = int(course['id'])
            if course_id in self.config.courses:
                cfg = self.config.courses[course_id]
                status = "✅ Enabled" if cfg.enabled else "❌ Disabled"
                print(f"  [{i}] {course['name']} — {status}")
            else:
                print(f"  [{i}] {course['name']} — (not configured)")
        print("-" * 60)
        print()

        selection = input("Enter course number to toggle [or Enter to cancel]: ").strip()
        if not selection.isdigit():
            return

        idx = int(selection) - 1
        if 0 <= idx < len(canvas_courses):
            course_id = int(canvas_courses[idx]['id'])
            if course_id in self.config.courses:
                course_config = self.config.courses[course_id]
                course_config.enabled = not course_config.enabled
                status = "enabled" if course_config.enabled else "disabled"
                print(f"✅ {course_config.course_name} is now {status}")
            else:
                print("⚠️  This course is not configured yet. Add it first.")
        else:
            print("❌ Invalid course number")

    def _generate_command_reference(self):
        """Generate command reference file."""
        try:
            from .command_reference import generate_command_reference
            output_path = generate_command_reference()
            print()
            print("=" * 60)
            print("📚 COMMAND REFERENCE CREATED")
            print("=" * 60)
            print()
            print(f"✅ A handy command reference has been saved to:")
            print(f"   {output_path}")
            print()
            print("View it anytime with:")
            print(f"   cat {output_path.name}")
            print()
            print("It contains ALL commands you'll need, including:")
            print("  • How to edit your configuration")
            print("  • How to run automation manually")
            print("  • How to test scheduling")
            print("  • How to view logs")
            print("  • Troubleshooting steps")
            print()
            print("💡 TIP: Keep this reference handy - you'll need it in 6 months!")
            print()
        except Exception as e:
            # Non-critical, just skip if fails
            pass

    def _run_dry_run(self):
        """Run dry-run preview (if automation_engine available)."""
        print()
        print("Dry-run functionality requires running:")
        print("  python3 src/run_automation.py --dry-run")
        print()
