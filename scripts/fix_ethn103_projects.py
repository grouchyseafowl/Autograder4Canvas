"""
Fix incorrect 0 grades on ETHN-1-03 Project 1 (discussion forum, assignment 688047).

The autograder previously submitted score=0 for students whose discussion posts
didn't meet the word count threshold. This script finds those grades and corrects
them to the assignment's full points_possible value, then prints a summary.

Usage:
    python3 fix_ethn103_projects.py          # dry run (no changes made)
    python3 fix_ethn103_projects.py --fix    # apply fixes to Canvas

Requires CANVAS_API_TOKEN in environment or a .env file in the project root.
"""

import os
import sys
import argparse
import requests
from pathlib import Path

# Load .env from project root (two levels up from scripts/)
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

CANVAS_BASE_URL = os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com")
API_TOKEN = os.getenv("CANVAS_API_TOKEN")

if not API_TOKEN:
    print("❌ CANVAS_API_TOKEN not set. Export it or add it to .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}

COURSE_ID = 44106        # ETHN-1-03 Intro Ethnic Studies 2026SP
TOPIC_ID = 688047        # Project 1 discussion topic ID


def get_paginated(url, params=None):
    items = []
    params = params or {}
    while url:
        r = requests.get(url, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        items.extend(r.json())
        url = r.links.get("next", {}).get("url")
        params = {}
    return items


def get_assignment_for_topic(course_id, topic_id):
    """Fetch the discussion topic and return its linked assignment."""
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/discussion_topics/{topic_id}"
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    topic = r.json()
    assignment = topic.get("assignment")
    if not assignment:
        raise ValueError(
            f"Discussion topic {topic_id} has no linked assignment. "
            f"Topic title: {topic.get('title', '?')}"
        )
    return assignment


def get_submissions(course_id, assignment_id):
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    return get_paginated(url, {"per_page": 100, "include[]": "user"})


def fix_grade(course_id, assignment_id, user_id, new_score):
    url = (
        f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}"
        f"/assignments/{assignment_id}/submissions/{user_id}"
    )
    r = requests.put(
        url,
        headers=HEADERS,
        json={"submission": {"posted_grade": str(new_score)}},
        timeout=30,
    )
    r.raise_for_status()
    return r.json().get("score")


def main():
    parser = argparse.ArgumentParser(
        description="Fix Project 1 zero grades in ETHN-1-03"
    )
    parser.add_argument("--fix", action="store_true", help="Apply fixes (default: dry run)")
    args = parser.parse_args()
    dry_run = not args.fix

    if dry_run:
        print("🔍 DRY RUN — no changes will be made. Pass --fix to apply.\n")
    else:
        print("⚠️  LIVE MODE — grades will be updated in Canvas.\n")

    # Resolve assignment from discussion topic ID
    assignment = get_assignment_for_topic(COURSE_ID, TOPIC_ID)
    ASSIGNMENT_ID = assignment["id"]
    POST_POINTS = assignment.get("points_possible") or 6.0
    print(f"Discussion topic {TOPIC_ID} → assignment id {ASSIGNMENT_ID}")
    print(f"Assignment: {assignment['name']}")
    print(f"Points possible: {assignment.get('points_possible')} → will award {POST_POINTS} pts")
    print(f"Grading type: {assignment.get('grading_type')}\n")

    submissions = get_submissions(COURSE_ID, ASSIGNMENT_ID)

    # Find graded submissions with score = 0
    zero_subs = [
        s for s in submissions
        if s.get("workflow_state") == "graded"
        and (s.get("score") == 0 or s.get("score") == 0.0)
    ]

    already_ok = [
        s for s in submissions
        if s.get("workflow_state") == "graded"
        and s.get("score") is not None
        and s.get("score") > 0
    ]

    ungraded = [
        s for s in submissions
        if s.get("workflow_state") not in ("graded",)
        and s.get("submitted_at") is not None
    ]

    print(f"Total submissions fetched: {len(submissions)}")
    print(f"  Graded with score > 0 (OK):  {len(already_ok)}")
    print(f"  Graded with score = 0 (FIX): {len(zero_subs)}")
    print(f"  Submitted but not yet graded: {len(ungraded)}")
    print()

    if not zero_subs:
        print("✅ No zero-scored graded submissions found. Nothing to fix.")
        return

    print(f"{'─' * 55}")
    print(f"Students to {'[DRY RUN] fix' if dry_run else 'fix'} → {POST_POINTS} pts:\n")

    fixed = 0
    failed = 0
    for sub in zero_subs:
        user = sub.get("user") or {}
        name = user.get("name", f"Student {sub['user_id']}")
        user_id = sub["user_id"]

        if dry_run:
            print(f"  [DRY RUN] {name} (id {user_id}): 0 → {POST_POINTS}")
        else:
            try:
                returned_score = fix_grade(COURSE_ID, ASSIGNMENT_ID, user_id, POST_POINTS)
                print(f"  ✅ {name} (id {user_id}): 0 → {returned_score}")
                fixed += 1
            except requests.exceptions.RequestException as e:
                print(f"  ❌ {name} (id {user_id}): FAILED — {e}")
                failed += 1

    print(f"\n{'─' * 55}")
    if dry_run:
        print(f"Would fix {len(zero_subs)} submission(s).")
        print(f"\nRun with --fix to apply.")
    else:
        print(f"Fixed: {fixed}  |  Failed: {failed}")
        if failed:
            print("⚠️  Some fixes failed — check errors above and retry.")


if __name__ == "__main__":
    main()
