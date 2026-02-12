"""
Canvas Autograder - Automation Engine
Main orchestration engine for automated grading.
"""

import os
import sys
import logging
import requests
import importlib.util
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime
from dateutil import parser
import pytz

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from .course_config import AutomationConfig, CourseConfig, AssignmentRule
from .canvas_helpers import CanvasAutomationAPI
from .grade_checker import GradeChecker
from .flag_aggregator import FlagAggregator
from .notification_manager import NotificationManager, IncompleteEvent


class AutomationEngine:
    """Main automation engine for Canvas autograding."""

    def __init__(self, config_path: str, dry_run: bool = False, course_filter: Optional[int] = None):
        """
        Initialize automation engine.

        Args:
            config_path: Path to configuration JSON file
            dry_run: If True, don't actually submit grades
            course_filter: If set, only process this course ID
        """
        self.config_path = Path(config_path)
        self.dry_run = dry_run
        self.course_filter = course_filter

        # Load configuration
        self.config = AutomationConfig.load(self.config_path)

        # Initialize helpers
        self.api = CanvasAutomationAPI()
        self.grade_checker = GradeChecker()
        self.flag_aggregator = FlagAggregator(
            self.config.global_settings.flag_excel_path
        )

        # Setup logging
        self.logger = self._setup_logging()

        # Notification manager (only if configured)
        gs = self.config.global_settings
        if gs.n8n_webhook_url and gs.notify_email:
            self.notifier = NotificationManager(gs.n8n_webhook_url, gs.notify_email)
        else:
            self.notifier = None

        # Canvas API details
        self.base_url = os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com")
        self.api_token = os.getenv("CANVAS_API_TOKEN")
        self.headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }

    def _setup_logging(self) -> logging.Logger:
        """Setup logging to file and console."""
        logger = logging.getLogger('autograder_automation')
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers.clear()

        # File handler
        log_path = Path(self.config.global_settings.log_file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(message)s')
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        return logger

    def run(self):
        """Main execution - runs unattended."""
        self.logger.info("=" * 60)
        self.logger.info("AUTOMATION RUN STARTED")
        self.logger.info("=" * 60)

        if self.dry_run:
            self.logger.info("🔍 DRY RUN MODE - No grades will be submitted")

        # Check for new assignments (if enabled)
        if self.config.global_settings.auto_update_enabled:
            self._check_for_new_assignments()

        # Process each enabled course
        stats = {
            'courses': 0,
            'assignments': 0,
            'submissions_graded': 0,
            'submissions_skipped': 0,
            'flags': 0
        }

        for course_id, course_config in self.config.courses.items():
            # Apply course filter if set
            if self.course_filter and course_id != self.course_filter:
                continue

            if not course_config.enabled:
                self.logger.info(f"⏭️  Skipping disabled course: {course_config.course_name}")
                continue

            try:
                course_stats = self._process_course(course_id, course_config)
                stats['courses'] += 1
                stats['assignments'] += course_stats['assignments']
                stats['submissions_graded'] += course_stats['submissions_graded']
                stats['submissions_skipped'] += course_stats['submissions_skipped']
                stats['flags'] += course_stats['flags']

            except Exception as e:
                self.logger.error(f"❌ Course {course_id} ({course_config.course_name}) failed: {e}", exc_info=True)
                # Continue to next course

        # Save aggregated flags
        if stats['flags'] > 0:
            self.flag_aggregator.save()

        # Generate summary report
        self._generate_summary(stats)

        # Send notification digest if any incompletes were found
        if self.notifier:
            self.notifier.send_digest()

        self.logger.info("=" * 60)
        self.logger.info("AUTOMATION RUN COMPLETED")
        self.logger.info("=" * 60)

    def _process_course(self, course_id: int, config: CourseConfig) -> Dict[str, int]:
        """
        Process all assignment groups in a course.

        Args:
            course_id: Canvas course ID
            config: Course configuration

        Returns:
            Dictionary of statistics
        """
        self.logger.info("")
        self.logger.info(f"📚 Processing course: {config.course_name} ({course_id})")

        stats = {
            'assignments': 0,
            'submissions_graded': 0,
            'submissions_skipped': 0,
            'flags': 0
        }

        for rule in config.assignment_rules:
            # Get assignments matching this rule
            assignments = self._get_assignments_for_rule(course_id, rule)

            self.logger.info(f"  📁 Group: {rule.assignment_group_name} ({len(assignments)} assignments)")

            for assignment in assignments:
                # Skip checks
                if self._should_skip_assignment(assignment, rule):
                    continue

                # Grade based on type
                try:
                    if rule.assignment_type == "complete_incomplete":
                        graded_count, skipped_count = self._run_complete_incomplete(
                            course_id, assignment, rule, config.course_name
                        )
                    elif rule.assignment_type == "discussion_forum":
                        graded_count, skipped_count = self._run_discussion_forum(
                            course_id, assignment, rule, config.course_name
                        )
                    else:
                        continue

                    stats['assignments'] += 1
                    stats['submissions_graded'] += graded_count
                    stats['submissions_skipped'] += skipped_count

                    # Run ADC if enabled and submissions were graded
                    if rule.run_adc and graded_count > 0:
                        flags = self._run_adc(course_id, assignment, config.course_name)
                        if flags:
                            self.flag_aggregator.add_flags(flags)
                            stats['flags'] += len(flags)

                except Exception as e:
                    self.logger.error(f"    ❌ Failed to grade {assignment['name']}: {e}")
                    continue

        return stats

    def _should_skip_assignment(self, assignment: Dict[str, Any], rule: AssignmentRule) -> bool:
        """
        Intelligent skipping logic.

        Args:
            assignment: Assignment dictionary
            rule: Assignment rule

        Returns:
            True if should skip
        """
        # Skip if future deadline
        if self.config.global_settings.skip_future_assignments:
            if self.api.is_future_assignment(assignment):
                self.logger.info(f"    ⏭️  Skipping {assignment['name']}: future deadline")
                return True

        # Skip if no submissions
        if self.config.global_settings.skip_no_submissions:
            submission_count = self.api.get_submission_count(
                assignment['course_id'], assignment['id']
            )
            if submission_count == 0:
                self.logger.info(f"    ⏭️  Skipping {assignment['name']}: no submissions")
                return True

        return False

    def _get_assignments_for_rule(self, course_id: int, rule: AssignmentRule) -> List[Dict[str, Any]]:
        """
        Get assignments matching a rule.

        Args:
            course_id: Canvas course ID
            rule: Assignment rule

        Returns:
            List of assignment dictionaries
        """
        assignments = self.api.get_assignments_in_group(course_id, rule.assignment_group_id)
        return assignments

    def _run_complete_incomplete(self, course_id: int, assignment: Dict[str, Any],
                                 rule: AssignmentRule, course_name: str = "") -> tuple:
        """
        Execute complete/incomplete grading.

        Args:
            course_id: Canvas course ID
            assignment: Assignment dictionary
            rule: Assignment rule
            course_name: Course name for notification events

        Returns:
            Tuple of (graded_count, skipped_count)
        """
        # Dynamic import for hyphenated filename
        module_path = Path(__file__).parent.parent / "Programs" / "Autograder_Complete-Incomplete_v1-3.py"
        spec = importlib.util.spec_from_file_location("autograder_ci", module_path)
        autograder_ci = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(autograder_ci)

        assignment_id = assignment['id']
        assignment_name = assignment['name']

        self.logger.info(f"    📝 Grading: {assignment_name}")

        # Fetch data
        students = autograder_ci.get_active_students(course_id)
        submissions = autograder_ci.get_submissions(course_id, assignment_id)

        # Filter out students who never submitted
        submissions = {
            user_id: sub for user_id, sub in submissions.items()
            if sub.get('submitted_at') is not None
        }

        # Build student name lookup
        student_names = {}
        for enrollment in students:
            user = enrollment.get('user', {})
            student_names[user.get('id')] = user.get('name', f"Student {user.get('id', '?')}")

        # Apply grade preservation filter
        if rule.preserve_existing_grades:
            original_count = len(submissions)
            submissions = self.grade_checker.filter_gradeable(submissions)
            skipped_count = original_count - len(submissions)

            if skipped_count > 0:
                self.logger.info(f"      ℹ️  {skipped_count} already graded, skipping")
        else:
            skipped_count = 0

        if not submissions:
            self.logger.info(f"      ⏭️  All submissions already graded")
            return 0, skipped_count

        # Evaluate submissions
        grade_data = {}
        all_submissions_list = list(submissions.values())

        for user_id, submission in submissions.items():
            is_complete, flags = autograder_ci.evaluate_submission(
                submission, all_submissions_list, rule.min_word_count
            )

            if is_complete:
                grade_data[user_id] = {"posted_grade": "complete"}
            else:
                grade_data[user_id] = {"posted_grade": "incomplete"}
                # Collect notification event
                if self.notifier:
                    body = submission.get("body", "")
                    word_count = self._count_words(body) if body else 0
                    self.notifier.add_event(IncompleteEvent(
                        course_name=course_name,
                        assignment_name=assignment_name,
                        student_name=student_names.get(user_id, f"Student {user_id}"),
                        student_id=user_id,
                        course_id=course_id,
                        assignment_id=assignment_id,
                        word_count=word_count,
                        required_words=rule.min_word_count or 0,
                        category="ci"
                    ))

        # Submit grades to Canvas (unless dry-run)
        if not self.dry_run and grade_data:
            self._submit_grades(course_id, assignment_id, grade_data)
            complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
            incomplete_count = len(grade_data) - complete_count
            self.logger.info(f"      ✅ Graded {len(grade_data)}: {complete_count} complete, {incomplete_count} incomplete")
        elif self.dry_run:
            complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
            self.logger.info(f"      🔍 Would grade {len(grade_data)} ({complete_count} complete, {len(grade_data) - complete_count} incomplete)")
        else:
            self.logger.info(f"      ℹ️  No submissions to evaluate")

        return len(grade_data), skipped_count

    def _run_discussion_forum(self, course_id: int, assignment: Dict[str, Any],
                             rule: AssignmentRule, course_name: str = "") -> tuple:
        """
        Execute discussion forum grading.

        Handles two modes:
        - "separate": Posts and replies evaluated independently against their own
          word count thresholds. Student must have >= min_posts qualifying posts
          AND >= min_replies qualifying replies.
        - "combined": All messages (posts + replies) pooled together. Total word
          count checked against post_min_words as the threshold.

        Args:
            course_id: Canvas course ID
            assignment: Assignment dictionary (must have discussion_topic link)
            rule: Assignment rule
            course_name: Course name for notification events

        Returns:
            Tuple of (graded_count, skipped_count)
        """
        assignment_id = assignment['id']
        assignment_name = assignment['name']

        # Get the linked discussion topic ID
        topic_id = self._get_discussion_topic_id(assignment)
        if not topic_id:
            self.logger.warning(f"    ⚠️  {assignment_name}: no linked discussion topic found")
            return 0, 0

        self.logger.info(f"    💬 Discussion: {assignment_name} (topic {topic_id})")

        # Fetch discussion entries from Canvas
        entries = self._fetch_discussion_entries(course_id, topic_id)
        if not entries:
            self.logger.info(f"      ℹ️  No entries in this discussion")
            return 0, 0

        # Categorize entries into posts vs replies per student
        student_data = self._categorize_discussion_entries(entries)
        self.logger.info(f"      ℹ️  {len(student_data)} student(s) participated")

        # Build student name lookup from entries (Canvas includes user info)
        student_names = {}
        for entry in entries:
            uid = entry.get("user_id")
            user = entry.get("user", {})
            if uid and user:
                student_names[uid] = user.get("name", f"Student {uid}")

        # Grade preservation: fetch existing submissions to skip already-graded students
        skipped_count = 0
        if rule.preserve_existing_grades:
            try:
                existing = self._fetch_submissions(course_id, assignment_id)
                already_graded = self.grade_checker.get_graded_user_ids(existing)
                if already_graded:
                    skipped_count = len(already_graded & set(student_data.keys()))
                    student_data = {
                        uid: data for uid, data in student_data.items()
                        if uid not in already_graded
                    }
                    self.logger.info(f"      ℹ️  {skipped_count} already graded, skipping")
            except Exception as e:
                self.logger.warning(f"      ⚠️  Could not check existing grades: {e}")

        if not student_data:
            self.logger.info(f"      ⏭️  All participants already graded")
            return 0, skipped_count

        # Evaluate each student
        mode = rule.discussion_grading_mode or "separate"
        grading_type = rule.grading_type or "complete_incomplete"
        grade_data = {}

        for user_id, data in student_data.items():
            if grading_type == "points":
                score = self._score_discussion_student(data, rule, mode)
                grade_data[user_id] = {"score": score}
                # Notify if zero score (didn't meet any threshold)
                if self.notifier and score == 0:
                    post_words = sum(self._count_words(m) for m in data["posts"])
                    self.notifier.add_event(IncompleteEvent(
                        course_name=course_name,
                        assignment_name=assignment_name,
                        student_name=student_names.get(user_id, f"Student {user_id}"),
                        student_id=user_id,
                        course_id=course_id,
                        assignment_id=assignment_id,
                        word_count=post_words,
                        required_words=rule.post_min_words or 200,
                        category="discussion_post"
                    ))
            else:
                is_complete = self._evaluate_discussion_student(data, rule, mode)
                if is_complete:
                    grade_data[user_id] = {"posted_grade": "complete"}
                else:
                    grade_data[user_id] = {"posted_grade": "incomplete"}
                    # Collect notification events for what's missing
                    if self.notifier and mode == "separate":
                        post_threshold = rule.post_min_words or 200
                        reply_threshold = rule.reply_min_words or 50
                        qualifying_posts = sum(
                            1 for m in data["posts"] if self._count_words(m) >= post_threshold
                        )
                        min_posts_req = rule.min_posts if rule.min_posts is not None else 1
                        if qualifying_posts < min_posts_req:
                            post_words = sum(self._count_words(m) for m in data["posts"])
                            self.notifier.add_event(IncompleteEvent(
                                course_name=course_name,
                                assignment_name=assignment_name,
                                student_name=student_names.get(user_id, f"Student {user_id}"),
                                student_id=user_id,
                                course_id=course_id,
                                assignment_id=assignment_id,
                                word_count=post_words,
                                required_words=post_threshold,
                                category="discussion_post"
                            ))
                        qualifying_replies = sum(
                            1 for m in data["replies"] if self._count_words(m) >= reply_threshold
                        )
                        min_replies_req = rule.min_replies if rule.min_replies is not None else 2
                        if qualifying_replies < min_replies_req:
                            reply_words = sum(self._count_words(m) for m in data["replies"])
                            self.notifier.add_event(IncompleteEvent(
                                course_name=course_name,
                                assignment_name=assignment_name,
                                student_name=student_names.get(user_id, f"Student {user_id}"),
                                student_id=user_id,
                                course_id=course_id,
                                assignment_id=assignment_id,
                                word_count=reply_words,
                                required_words=reply_threshold,
                                category="discussion_reply"
                            ))
                    elif self.notifier and mode == "combined":
                        all_words = sum(self._count_words(m) for m in data["posts"] + data["replies"])
                        self.notifier.add_event(IncompleteEvent(
                            course_name=course_name,
                            assignment_name=assignment_name,
                            student_name=student_names.get(user_id, f"Student {user_id}"),
                            student_id=user_id,
                            course_id=course_id,
                            assignment_id=assignment_id,
                            word_count=all_words,
                            required_words=rule.post_min_words or 200,
                            category="discussion_post"
                        ))

        # Submit grades
        if not self.dry_run and grade_data:
            self._submit_grades(course_id, assignment_id, grade_data)
            if grading_type == "points":
                scores = [g["score"] for g in grade_data.values()]
                self.logger.info(f"      ✅ Graded {len(grade_data)}: scores range {min(scores):.1f}–{max(scores):.1f}")
            else:
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                self.logger.info(f"      ✅ Graded {len(grade_data)}: {complete_count} complete, {len(grade_data) - complete_count} incomplete")
        elif self.dry_run:
            if grading_type == "points":
                scores = [g["score"] for g in grade_data.values()]
                self.logger.info(f"      🔍 Would grade {len(grade_data)}: scores range {min(scores):.1f}–{max(scores):.1f}")
            else:
                complete_count = sum(1 for g in grade_data.values() if g.get("posted_grade") == "complete")
                self.logger.info(f"      🔍 Would grade {len(grade_data)}: {complete_count} complete, {len(grade_data) - complete_count} incomplete")

        return len(grade_data), skipped_count

    def _get_discussion_topic_id(self, assignment: Dict[str, Any]) -> Optional[int]:
        """
        Extract discussion topic ID from an assignment.

        Canvas includes a discussion_topic object on graded discussion assignments,
        or we can fall back to fetching it separately if submission_types indicates
        this is a discussion.

        Args:
            assignment: Assignment dictionary

        Returns:
            Topic ID or None
        """
        # Direct link in assignment object (most common)
        topic = assignment.get('discussion_topic')
        if topic and isinstance(topic, dict):
            return topic.get('id')

        # Some responses put it as a flat field
        if assignment.get('discussion_topic_id'):
            return assignment['discussion_topic_id']

        # If submission_types includes online_discussion but no topic link,
        # try fetching the discussion topic separately
        submission_types = assignment.get('submission_types', [])
        if 'online_discussion' in submission_types:
            # Fetch all topics for the course and find the one matching this assignment
            try:
                url = f"{self.base_url}/api/v1/courses/{assignment['course_id']}/discussion_topics"
                response = requests.get(url, headers=self.headers, params={'per_page': 100}, timeout=30)
                response.raise_for_status()
                topics = response.json()

                for topic in topics:
                    linked_assignment = topic.get('assignment', {})
                    if linked_assignment and linked_assignment.get('id') == assignment['id']:
                        return topic['id']
            except Exception as e:
                self.logger.warning(f"      ⚠️  Failed to fetch discussion topics: {e}")

        return None

    def _fetch_discussion_entries(self, course_id: int, topic_id: int) -> List[Dict[str, Any]]:
        """
        Fetch all entries (posts and nested replies) for a discussion topic.

        Uses Canvas's /discussion_topics/{id}/view endpoint which returns
        the full nested tree of entries.

        Args:
            course_id: Canvas course ID
            topic_id: Discussion topic ID

        Returns:
            List of top-level entry dicts (each may contain nested replies)
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view"
        try:
            response = requests.get(url, headers=self.headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data.get("view", [])
        except Exception as e:
            self.logger.error(f"      ❌ Failed to fetch discussion entries: {e}")
            return []

    def _categorize_discussion_entries(self, entries: List[Dict[str, Any]]) -> Dict[int, Dict[str, List[str]]]:
        """
        Walk the nested entry tree and separate each student's posts from replies.

        Canvas returns entries as a nested structure:
            view: [
                {id, user_id, message, replies: [
                    {id, user_id, message, replies: [...]},
                    ...
                ]},
                ...
            ]

        Top-level entries in the view array are original posts. Anything nested
        inside a replies array is a reply (regardless of further nesting depth).

        Args:
            entries: Top-level entry list from the /view endpoint

        Returns:
            Dict of {user_id: {"posts": [message_texts], "replies": [message_texts]}}
        """
        student_data: Dict[int, Dict[str, List[str]]] = {}

        def ensure_student(uid: int):
            if uid not in student_data:
                student_data[uid] = {"posts": [], "replies": []}

        def collect_replies(reply_list: List[Dict[str, Any]]):
            """Recursively collect all replies (and replies-to-replies)."""
            for reply in reply_list:
                uid = reply.get("user_id")
                message = reply.get("message", "")
                if uid and message:
                    ensure_student(uid)
                    student_data[uid]["replies"].append(message)
                # Replies can have their own nested replies
                if "replies" in reply:
                    collect_replies(reply["replies"])

        # Top-level entries are posts
        for entry in entries:
            uid = entry.get("user_id")
            message = entry.get("message", "")
            if uid and message:
                ensure_student(uid)
                student_data[uid]["posts"].append(message)

            # Everything nested under a post is a reply
            if "replies" in entry:
                collect_replies(entry["replies"])

        return student_data

    def _evaluate_discussion_student(self, student_data: Dict[str, List[str]],
                                      rule: AssignmentRule, mode: str) -> bool:
        """
        Evaluate a single student's discussion participation against the rule.

        Separate mode: Student must have >= min_posts posts each meeting
        post_min_words, AND >= min_replies replies each meeting reply_min_words.
        Either threshold can be set to 0 to skip that check.

        Combined mode: Total word count across ALL messages (posts + replies)
        must meet post_min_words as the threshold.

        Args:
            student_data: {"posts": [message_texts], "replies": [message_texts]}
            rule: Assignment rule with discussion settings
            mode: "separate" or "combined"

        Returns:
            True if student meets the requirements
        """
        posts = student_data["posts"]
        replies = student_data["replies"]

        if mode == "combined":
            # Pool everything together, check total word count
            all_messages = posts + replies
            total_words = sum(self._count_words(msg) for msg in all_messages)
            threshold = rule.post_min_words or 200
            qualifies = total_words >= threshold
            self.logger.info(
                f"        [combined] {len(all_messages)} messages, {total_words} total words "
                f"(need {threshold}) → {'✅' if qualifies else '❌'}"
            )
            return qualifies

        else:  # "separate"
            # Posts check
            min_posts_required = rule.min_posts if rule.min_posts is not None else 1
            post_threshold = rule.post_min_words or 200
            qualifying_posts = sum(1 for msg in posts if self._count_words(msg) >= post_threshold)

            # Replies check
            min_replies_required = rule.min_replies if rule.min_replies is not None else 2
            reply_threshold = rule.reply_min_words or 50
            qualifying_replies = sum(1 for msg in replies if self._count_words(msg) >= reply_threshold)

            posts_ok = qualifying_posts >= min_posts_required
            replies_ok = qualifying_replies >= min_replies_required

            self.logger.info(
                f"        [separate] posts: {qualifying_posts}/{min_posts_required} "
                f"(need {post_threshold} words each) → {'✅' if posts_ok else '❌'} | "
                f"replies: {qualifying_replies}/{min_replies_required} "
                f"(need {reply_threshold} words each) → {'✅' if replies_ok else '❌'}"
            )
            return posts_ok and replies_ok

    def _score_discussion_student(self, student_data: Dict[str, List[str]],
                                    rule: AssignmentRule, mode: str) -> float:
        """
        Calculate numeric score for a student's discussion participation.

        In separate mode:
            score = post_points (if at least one qualifying post)
                  + (qualifying_reply_count × reply_points)

        In combined mode:
            score = (post_points + reply_points) if total words >= threshold, else 0
            (Combined mode with points is binary — you either meet the total or you don't)

        Args:
            student_data: {"posts": [message_texts], "replies": [message_texts]}
            rule: Assignment rule with points settings
            mode: "separate" or "combined"

        Returns:
            Calculated score as float
        """
        posts = student_data["posts"]
        replies = student_data["replies"]
        post_pts = rule.post_points if rule.post_points is not None else 1.0
        reply_pts = rule.reply_points if rule.reply_points is not None else 0.5

        if mode == "combined":
            all_messages = posts + replies
            total_words = sum(self._count_words(msg) for msg in all_messages)
            threshold = rule.post_min_words or 200
            if total_words >= threshold:
                # Award full post points + per-reply points for combined
                score = post_pts + (len(replies) * reply_pts)
            else:
                score = 0.0
            self.logger.info(
                f"        [combined/points] {total_words} total words (need {threshold}) → "
                f"score: {score:.1f} (post: {post_pts}, {len(replies)} replies × {reply_pts})"
            )
            return score

        else:  # "separate"
            score = 0.0
            post_threshold = rule.post_min_words or 200
            reply_threshold = rule.reply_min_words or 50

            # Posts: award post_points if student has at least one qualifying post
            qualifying_posts = sum(1 for msg in posts if self._count_words(msg) >= post_threshold)
            if qualifying_posts > 0:
                score += post_pts

            # Replies: award reply_points for EACH qualifying reply
            qualifying_replies = sum(1 for msg in replies if self._count_words(msg) >= reply_threshold)
            score += qualifying_replies * reply_pts

            self.logger.info(
                f"        [separate/points] posts: {qualifying_posts} qualifying "
                f"(+{post_pts if qualifying_posts > 0 else 0}) | "
                f"replies: {qualifying_replies} qualifying (+{qualifying_replies * reply_pts:.1f}) → "
                f"score: {score:.1f}"
            )
            return score

    def _count_words(self, text: str) -> int:
        """
        Count words in a message, stripping HTML tags first.

        Canvas discussion messages are HTML. This strips tags and counts
        whitespace-delimited tokens.

        Args:
            text: Raw message text (may contain HTML)

        Returns:
            Word count
        """
        import re
        # Strip HTML tags
        clean = re.sub(r'<[^>]+>', ' ', text or "")
        # Collapse whitespace and split
        words = clean.split()
        return len(words)

    def _fetch_submissions(self, course_id: int, assignment_id: int) -> Dict[int, Dict[str, Any]]:
        """
        Fetch current submissions for an assignment (for grade preservation).

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID

        Returns:
            Dict of {user_id: submission_data}
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {"per_page": 100}

        submissions = {}
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=30)
            response.raise_for_status()
            for sub in response.json():
                uid = sub.get("user_id")
                if uid:
                    submissions[uid] = sub
        except Exception as e:
            self.logger.warning(f"      ⚠️  Failed to fetch submissions: {e}")

        return submissions

    def _submit_grades(self, course_id: int, assignment_id: int, grade_data: Dict[int, Dict[str, Any]]):
        """
        Submit grades to Canvas.

        Args:
            course_id: Canvas course ID
            assignment_id: Assignment ID
            grade_data: Dictionary of {user_id: grade_info}
        """
        url = f"{self.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/update_grades"

        payload = {
            "grade_data": {
                str(user_id): data
                for user_id, data in grade_data.items()
            }
        }

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=60)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"      ❌ Failed to submit grades: {e}")
            raise

    def _run_adc(self, course_id: int, assignment: Dict[str, Any], course_name: str) -> List[Dict[str, Any]]:
        """
        Run Academic Dishonesty Check on graded submissions.

        Args:
            course_id: Canvas course ID
            assignment: Assignment dictionary
            course_name: Course name

        Returns:
            List of flag dictionaries
        """
        # Note: ADC integration would require importing and running Academic_Dishonesty_Check_v2
        # This is a placeholder that returns empty list
        # Full implementation would involve:
        # 1. Import AcademicDishonestyDetector from Academic_Dishonesty_Check_v2
        # 2. Analyze each submission
        # 3. Return flagged results

        self.logger.info(f"      🔍 Running academic dishonesty check...")

        # For now, return empty list
        # TODO: Implement full ADC integration
        return []

    def _check_for_new_assignments(self):
        """Check for new assignment groups in configured courses."""
        self.logger.info("🔍 Checking for new assignment groups...")

        updates_found = False

        for course_id, course_config in self.config.courses.items():
            known_group_ids = {rule.assignment_group_id for rule in course_config.assignment_rules}
            new_groups = self.api.check_for_new_assignments(course_id, known_group_ids)

            if new_groups:
                updates_found = True
                self.logger.info(f"  ℹ️  Found {len(new_groups)} new group(s) in {course_config.course_name}")
                for group in new_groups:
                    self.logger.info(f"      - {group['name']}")

        if not updates_found:
            self.logger.info("  ✅ No new assignment groups found")

        self.logger.info("")

    def _generate_summary(self, stats: Dict[str, int]):
        """
        Generate summary report.

        Args:
            stats: Statistics dictionary
        """
        self.logger.info("")
        self.logger.info("📊 SUMMARY")
        self.logger.info("-" * 60)
        self.logger.info(f"  Courses processed: {stats['courses']}")
        self.logger.info(f"  Assignments graded: {stats['assignments']}")
        self.logger.info(f"  Submissions graded: {stats['submissions_graded']}")
        self.logger.info(f"  Submissions skipped: {stats['submissions_skipped']}")
        self.logger.info(f"  Academic dishonesty flags: {stats['flags']}")
        self.logger.info("")

        if stats['flags'] > 0:
            self.logger.info(f"  📁 Flags saved to: {self.config.global_settings.flag_excel_path}")
