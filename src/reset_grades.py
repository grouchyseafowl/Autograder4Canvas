#!/usr/bin/env python3
"""
Canvas Autograder - Grade Reset Utility
Clears all autograder-posted grades back to ungraded for all configured courses/assignments.
"""

import json
import sys
import requests
from pathlib import Path
from typing import Dict, List, Any

sys.path.insert(0, str(Path(__file__).parent))

from automation.canvas_helpers import CanvasAutomationAPI


def load_config(config_path: str) -> Dict:
    with open(config_path) as f:
        return json.load(f)


def get_graded_submissions(api: CanvasAutomationAPI, course_id: int, assignment_id: int) -> Dict[int, Dict]:
    """Fetch all submissions that have a grade (score is not None)."""
    url = f"{api.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    params = {"per_page": 100}
    submissions = api._get_paginated(url, params)

    graded = {}
    for sub in submissions:
        uid = sub.get("user_id")
        # A submission has been graded if it has a non-None score
        if uid and sub.get("score") is not None:
            graded[uid] = sub
    return graded


def clear_grades(api: CanvasAutomationAPI, course_id: int, assignment_id: int, user_ids: List[int]):
    """POST empty posted_grade to clear grades for given users."""
    url = f"{api.base_url}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/update_grades"

    payload = {
        "grade_data": {
            str(uid): {"posted_grade": ""}
            for uid in user_ids
        }
    }

    response = requests.post(url, headers=api.headers, json=payload, timeout=60)
    response.raise_for_status()
    return response


def main():
    config_path = Path(__file__).parent.parent / ".autograder_config" / "course_configs.json"
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    config = load_config(str(config_path))
    api = CanvasAutomationAPI()

    dry_run = "--dry-run" in sys.argv

    print()
    print("=" * 60)
    print("GRADE RESET UTILITY")
    print("=" * 60)
    if dry_run:
        print("  MODE: DRY RUN — no changes will be made")
    else:
        print("  MODE: LIVE — grades will be cleared")
    print()

    total_cleared = 0

    for course_id_str, course in config.get("courses", {}).items():
        course_id = int(course_id_str)
        course_name = course.get("course_name", f"Course {course_id}")

        if not course.get("enabled", False):
            print(f"  ⏭️  Skipping {course_name} (disabled)")
            continue

        print(f"📚 {course_name} ({course_id})")

        for rule in course.get("assignment_rules", []):
            group_name = rule.get("assignment_group_name", "Unknown")
            group_id = rule.get("assignment_group_id")

            # Get all assignments in this group
            assignments = api.get_assignments_in_group(course_id, group_id)
            if not assignments:
                continue

            print(f"  📁 {group_name} ({len(assignments)} assignments)")

            for assignment in assignments:
                assignment_id = assignment["id"]
                assignment_name = assignment.get("name", f"Assignment {assignment_id}")

                graded = get_graded_submissions(api, course_id, assignment_id)
                if not graded:
                    print(f"    ✓ {assignment_name} — nothing to clear")
                    continue

                print(f"    🔧 {assignment_name} — {len(graded)} graded submission(s)")

                if not dry_run:
                    try:
                        clear_grades(api, course_id, assignment_id, list(graded.keys()))
                        total_cleared += len(graded)
                        print(f"       ✅ Cleared {len(graded)} grade(s)")
                    except requests.exceptions.RequestException as e:
                        print(f"       ❌ Failed: {e}")
                else:
                    total_cleared += len(graded)
                    print(f"       (would clear {len(graded)} grade(s))")

        print()

    print("=" * 60)
    if dry_run:
        print(f"DRY RUN COMPLETE — {total_cleared} grade(s) would be cleared")
        print()
        print("To execute for real, run without --dry-run")
    else:
        print(f"RESET COMPLETE — {total_cleared} grade(s) cleared")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
