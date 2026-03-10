#!/usr/bin/env python3
"""
Standalone test script for LLM reply quality evaluation.

Fetches real discussion reply data from Canvas and runs each reply through
OllamaReplyChecker to validate PASS/FAIL classifications. Read-only —
no state changes, no grade submissions.

Usage:
    .venv/bin/python3 src/automation/test_reply_quality.py --course 44106 --topic 964046
    .venv/bin/python3 src/automation/test_reply_quality.py --course 44106 --topic 964048
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

import requests

sys.path.insert(0, str(Path(__file__).parent))
from reply_quality_checker import OllamaReplyChecker


# ── helpers ────────────────────────────────────────────────────────────────

def clean_html(text: str) -> str:
    return re.sub(r'<[^>]+>', ' ', text or "").strip()


def count_words(text: str) -> int:
    return len(clean_html(text).split())


def snippet(text: str, max_words: int = 14) -> str:
    words = clean_html(text).split()
    s = " ".join(words[:max_words])
    return f'"{s}..."' if len(words) > max_words else f'"{s}"'


# ── Canvas fetch ────────────────────────────────────────────────────────────

def fetch_entries(base_url: str, headers: dict, course_id: int, topic_id: int) -> List[Dict]:
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json().get("view", [])


def fetch_participants(base_url: str, headers: dict, course_id: int, topic_id: int) -> Dict[int, str]:
    url = f"{base_url}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view"
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return {p["id"]: p.get("display_name", f"Student {p['id']}")
            for p in data.get("participants", [])}


# ── entry tree walk ─────────────────────────────────────────────────────────

def collect_replies(reply_list: List[Dict], parent_message: str, out: List[Dict]) -> None:
    """Recursively collect replies, attaching parent_message context."""
    for reply in reply_list:
        msg = reply.get("message", "")
        uid = reply.get("user_id")
        if uid and msg:
            out.append({
                "id": reply.get("id"),
                "user_id": uid,
                "message": msg,
                "parent_message": parent_message,
            })
        if "replies" in reply:
            collect_replies(reply["replies"], parent_message=msg, out=out)


def categorize(entries: List[Dict]) -> Dict[int, Dict[str, List]]:
    """Return {user_id: {"posts": [...], "replies": [...]}}"""
    student_data: Dict[int, Dict[str, List]] = {}

    def ensure(uid: int):
        if uid not in student_data:
            student_data[uid] = {"posts": [], "replies": []}

    for entry in entries:
        uid = entry.get("user_id")
        msg = entry.get("message", "")
        if uid and msg:
            ensure(uid)
            student_data[uid]["posts"].append({"id": entry.get("id"), "message": msg})
        if "replies" in entry:
            bucket: List[Dict] = []
            collect_replies(entry["replies"], parent_message=msg, out=bucket)
            for r in bucket:
                ruid = r["user_id"]
                ensure(ruid)
                student_data[ruid]["replies"].append(r)

    return student_data


# ── main ───────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Test LLM reply quality checker on real Canvas data")
    parser.add_argument("--course", type=int, required=True, help="Canvas course ID")
    parser.add_argument("--topic", type=int, required=True, help="Canvas discussion topic ID")
    parser.add_argument("--min-words", type=int, default=40, help="Word count threshold (default 40)")
    args = parser.parse_args()

    base_url = os.getenv("CANVAS_BASE_URL", "https://cabrillo.instructure.com").rstrip("/")
    token = os.getenv("CANVAS_API_TOKEN")
    if not token:
        print("ERROR: CANVAS_API_TOKEN not set", file=sys.stderr)
        sys.exit(1)
    headers = {"Authorization": f"Bearer {token}"}

    print(f"\nFetching discussion topic {args.topic} in course {args.course}...")
    entries = fetch_entries(base_url, headers, args.course, args.topic)
    participants = fetch_participants(base_url, headers, args.course, args.topic)
    student_data = categorize(entries)

    checker = OllamaReplyChecker()

    total_replies = sum(len(d["replies"]) for d in student_data.values())
    above_threshold = sum(
        1 for d in student_data.values()
        for r in d["replies"] if count_words(r["message"]) >= args.min_words
    )

    print(f"\nTopic {args.topic} — {len(student_data)} students, "
          f"{total_replies} replies total, {above_threshold} above {args.min_words}-word threshold\n")
    print("=" * 70)

    pass_count = 0
    fail_count = 0
    skipped_count = 0

    for uid, data in sorted(student_data.items()):
        replies = data["replies"]
        if not replies:
            continue

        name = participants.get(uid, f"Student {uid}")
        student_header_printed = False

        for r in replies:
            wc = count_words(r["message"])
            if wc < args.min_words:
                skipped_count += 1
                continue

            result = checker.is_substantive(r["parent_message"], r["message"])

            if not student_header_printed:
                print(f"\n{name} (ID {uid}):")
                student_header_printed = True

            label = "PASS" if result else "FAIL — not substantive"
            print(f"  Reply {r['id']} ({wc} words): {label}")
            print(f"    {snippet(r['message'])}")

            if result:
                pass_count += 1
            else:
                fail_count += 1

    evaluated = pass_count + fail_count
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Evaluated : {evaluated} replies")
    print(f"  PASS      : {pass_count} ({pass_count/evaluated*100:.0f}%)" if evaluated else "  PASS: 0")
    print(f"  FAIL      : {fail_count} ({fail_count/evaluated*100:.0f}%)" if evaluated else "  FAIL: 0")
    print(f"  Skipped   : {skipped_count} (below {args.min_words}-word threshold)")
    print()


if __name__ == "__main__":
    main()
