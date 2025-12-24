import os
import platform
import requests
import time
from typing import List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
import csv
from dateutil import parser
import pytz

# ======================
# CONFIGURATION
# ======================
CANVAS_BASE_URL = "https://cabrillo.instructure.com"
API_TOKEN = os.getenv("CANVAS_API_TOKEN")

if not API_TOKEN:
    raise ValueError("❌ Missing CANVAS_API_TOKEN environment variable")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Grading thresholds
MIN_WORD_COUNT = 50

def get_output_base_dir() -> Path:
    """Get base output directory in a cross-platform way."""
    system = platform.system()
    
    if os.path.isdir("/output"):
        return Path("/output")
    
    if system == "Windows":
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        documents = Path.home() / "Documents"
    
    return documents / "Grading_Rationales"


def count_words(text: str) -> int:
    """Count words in text, handling HTML."""
    if not text:
        return 0
    # Basic HTML tag removal
    import re
    text = re.sub(r'<[^>]+>', '', text)
    return len(text.split())


def get_active_students(course_id: int) -> List[Dict]:
    """Fetch active student enrollments."""
    print("📥 Fetching active student enrollments...")
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/enrollments"
    params = {"type": ["StudentEnrollment"], "state": ["active"], "per_page": 100}
    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"❌ Failed to fetch enrollments: {response.text}")
        return []

    data = response.json()
    return data if isinstance(data, list) else []


def get_all_discussion_topics(course_id: int) -> List[Dict]:
    """Fetch all discussion topics in the course."""
    print("📚 Fetching all discussion topics...")
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/discussion_topics"
    params = {"per_page": 100}
    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"❌ Failed to fetch discussion topics: {response.text}")
        return []

    data = response.json()
    return data if isinstance(data, list) else []


def filter_graded_discussions(discussions: List[Dict], grading_filter: str = "all") -> List[Dict]:
    """
    Filter discussions to only graded ones where the due date has passed.
    
    Args:
        grading_filter: "complete_incomplete", "letter_grade", or "all"
    """
    filtered = []
    now = datetime.now(pytz.UTC)
    
    for discussion in discussions:
        # Check if it's a graded discussion (has assignment)
        assignment = discussion.get("assignment")
        if not assignment:
            continue
        
        # Filter by grading type
        grading_type = assignment.get("grading_type", "")
        if grading_filter == "complete_incomplete" and grading_type != "pass_fail":
            continue
        elif grading_filter == "letter_grade" and grading_type not in ["points", "letter_grade", "gpa_scale", "percent"]:
            continue
        # "all" includes both
        
        # Check due date
        due_at = assignment.get("due_at")
        
        # If no due date, include it (treat as always available to grade)
        if not due_at:
            print(f"   ⚠️  '{discussion.get('title')}' has no due date - including")
            filtered.append(discussion)
            continue
        
        # Parse due date and compare with current time
        try:
            due_date = parser.isoparse(due_at)
            # Ensure due_date is timezone-aware
            if due_date.tzinfo is None:
                due_date = pytz.UTC.localize(due_date)
            
            if now >= due_date:
                filtered.append(discussion)
            else:
                # Calculate time remaining
                time_remaining = due_date - now
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                print(f"   ⏭️  Skipping '{discussion.get('title')}' - due in {days}d {hours}h")
        except Exception as e:
            print(f"   ⚠️  Could not parse due date for '{discussion.get('title')}': {e}")
            print(f"       Including discussion to be safe")
            filtered.append(discussion)
    
    return filtered


def fetch_discussion_entries(course_id: int, topic_id: int) -> List[Dict]:
    """Fetch all entries (including replies) for a discussion topic."""
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/discussion_topics/{topic_id}/view"
    resp = requests.get(url, headers=HEADERS)
    
    if resp.status_code != 200:
        print(f"⚠️  Failed to fetch discussion {topic_id} (HTTP {resp.status_code})")
        return []
    
    try:
        data = resp.json()
        entries = data.get("view", [])
    except Exception as e:
        print(f"   ❌ JSON decode error: {e}")
        return []
    
    return entries


def flatten_entries(entries: List[Dict]) -> List[Dict]:
    """Flatten nested discussion entries (replies)."""
    all_entries = []
    
    def process_entry(entry):
        all_entries.append(entry)
        if "replies" in entry:
            for reply in entry["replies"]:
                process_entry(reply)
    
    for entry in entries:
        process_entry(entry)
    
    return all_entries


def evaluate_discussion_post(posts: List[str], grading_criteria: Dict[str, Any], 
                           grading_type: str) -> Tuple[str, List[str], int, int, int]:
    """
    Evaluate discussion posts based on word count and reply criteria.
    
    Args:
        posts: List of all post/reply texts from student
        grading_criteria: Dict with thresholds and reply requirements
        grading_type: "pass_fail" or letter grade type
    
    Returns: (grade, flags, total_word_count, num_posts, avg_words_per_post)
    """
    flags = []
    num_posts = len(posts)
    
    if num_posts == 0:
        if grading_type == "pass_fail":
            return "incomplete", ["No posts"], 0, 0, 0
        else:
            return "F", ["No posts"], 0, 0, 0
    
    # Calculate word counts
    word_counts = [count_words(post) for post in posts]
    total_word_count = sum(word_counts)
    avg_words_per_post = total_word_count / num_posts if num_posts > 0 else 0
    
    # For complete/incomplete
    if grading_type == "pass_fail":
        criteria = grading_criteria.get("complete", {})
        min_total_words = criteria.get("total_words", 50)
        min_replies = criteria.get("min_replies", 0)
        min_avg_words = criteria.get("avg_words", 0)
        
        # Check all criteria
        if total_word_count < min_total_words:
            flags.append(f"Total words too low ({total_word_count}/{min_total_words})")
        
        if min_replies > 0 and num_posts < min_replies:
            flags.append(f"Not enough posts/replies ({num_posts}/{min_replies})")
        
        if min_avg_words > 0 and avg_words_per_post < min_avg_words:
            flags.append(f"Average words per post too low ({avg_words_per_post:.0f}/{min_avg_words})")
        
        if flags:
            return "incomplete", flags, total_word_count, num_posts, int(avg_words_per_post)
        return "complete", flags, total_word_count, num_posts, int(avg_words_per_post)
    
    # For letter grades
    else:
        grade_order = ['A', 'B', 'C', 'D']
        
        for grade in grade_order:
            criteria = grading_criteria.get(grade)
            if not criteria:
                continue
            
            min_total_words = criteria.get("total_words", 0)
            min_replies = criteria.get("min_replies", 0)
            min_avg_words = criteria.get("avg_words", 0)
            
            # Check if meets all criteria for this grade
            meets_total = total_word_count >= min_total_words
            meets_replies = num_posts >= min_replies if min_replies > 0 else True
            meets_avg = avg_words_per_post >= min_avg_words if min_avg_words > 0 else True
            
            if meets_total and meets_replies and meets_avg:
                return grade, flags, total_word_count, num_posts, int(avg_words_per_post)
        
        # If below all thresholds, return F with reasons
        flags.append(f"Did not meet minimum criteria")
        return "F", flags, total_word_count, num_posts, int(avg_words_per_post)


def grade_discussion_topic(course_id: int, topic_id: int, topic_name: str, 
                          students: List[Dict], min_word_count: int,
                          grading_type: str, regrade_mode: bool = False) -> Tuple[List[Dict], Dict]:
    """
    Grade a discussion topic.
    
    Args:
        grading_type: "pass_fail" or "points"/"letter_grade" etc.
        regrade_mode: If True, don't lower existing grades
    
    Returns: (flagged_submissions, student_grades_dict)
    """
    print(f"\n📝 Grading: {topic_name}")
    
    # Fetch all discussion entries
    entries = fetch_discussion_entries(course_id, topic_id)
    if not entries:
        print(f"   ⚠️  No entries found for this discussion")
        return [], {}
    
    all_entries = flatten_entries(entries)
    
    # Create mapping of user_id to their posts
    student_posts = {}
    for entry in all_entries:
        user_id = entry.get("user_id")
        message = entry.get("message", "")
        
        if user_id:
            if user_id not in student_posts:
                student_posts[user_id] = []
            student_posts[user_id].append(message)
    
    # Prepare to grade
    student_ids = {s.get("user_id") for s in students}
    grade_data = {}
    flagged_submissions = []
    student_grades = {}
    
    marked_complete = 0
    marked_incomplete = 0
    skipped_no_downgrade = 0
    
    # Get assignment ID for fetching current grades
    assignment = None
    topics_data = get_all_discussion_topics(course_id)
    for t in topics_data:
        if t.get("id") == topic_id:
            assignment = t.get("assignment")
            break
    
    assignment_id = assignment.get("id") if assignment else None
    
    # Fetch current submissions if in regrade mode
    current_submissions = {}
    if regrade_mode and assignment_id:
        submissions_url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
        params = {"per_page": 100}
        resp = requests.get(submissions_url, headers=HEADERS, params=params)
        if resp.status_code == 200:
            subs = resp.json()
            current_submissions = {s.get("user_id"): s for s in subs if isinstance(subs, list)}
    
    for student in students:
        user_id = student.get("user_id")
        if not user_id or user_id not in student_ids:
            continue
        
        student_name = student.get("user", {}).get("name", f"User {user_id}")
        
        # Check current grade if in regrade mode
        if regrade_mode and user_id in current_submissions:
            current_sub = current_submissions[user_id]
            current_grade = current_sub.get("grade")
            current_score = current_sub.get("score")
            
            # For complete/incomplete, check if already complete
            if grading_type == "pass_fail" and current_grade == "complete":
                print(f"   ⏭️  {student_name}: Already complete, skipping")
                skipped_no_downgrade += 1
                student_grades[user_id] = {"grade": "complete", "reason": "Already complete (not regraded)"}
                continue
            
            # For letter grades, check if they have a passing score
            # We'll consider any score > 0 as "don't downgrade"
            if grading_type != "pass_fail" and current_score and current_score > 0:
                print(f"   ⏭️  {student_name}: Has existing score ({current_score}), skipping")
                skipped_no_downgrade += 1
                student_grades[user_id] = {"grade": current_grade or str(current_score), 
                                          "reason": f"Already graded ({current_score} points)"}
                continue
        
        # Evaluate posts
        if user_id in student_posts:
            # Combine all messages for word count
            combined_message = " ".join(student_posts[user_id])
            status, flags, word_count = evaluate_discussion_post(combined_message, min_word_count)
            
            if status == "complete":
                if grading_type == "pass_fail":
                    grade = "complete"
                else:
                    # For letter grades, use full points
                    max_points = assignment.get("points_possible", 10) if assignment else 10
                    grade = str(max_points)
                marked_complete += 1
                
                # Record flags if any
                if flags:
                    flagged_submissions.append({
                        "name": student_name,
                        "user_id": user_id,
                        "flags": flags,
                        "word_count": word_count
                    })
                
                student_grades[user_id] = {"grade": grade, "reason": "Meets requirements"}
            else:
                if grading_type == "pass_fail":
                    grade = "incomplete"
                else:
                    grade = "0"
                marked_incomplete += 1
                
                reason = "; ".join(flags) if flags else "Does not meet requirements"
                student_grades[user_id] = {"grade": grade, "reason": reason}
                
                flagged_submissions.append({
                    "name": student_name,
                    "user_id": user_id,
                    "flags": flags,
                    "word_count": word_count
                })
        else:
            # No post found
            if grading_type == "pass_fail":
                grade = "incomplete"
            else:
                grade = "0"
            marked_incomplete += 1
            
            student_grades[user_id] = {"grade": grade, "reason": "No post found"}
            flagged_submissions.append({
                "name": student_name,
                "user_id": user_id,
                "flags": ["No post"],
                "word_count": 0
            })
        
        grade_data[str(user_id)] = {"posted_grade": student_grades[user_id]["grade"]}
    
    # Submit grades if we have any
    if not grade_data:
        print("   ⚠️  No students to grade")
        if skipped_no_downgrade > 0:
            print(f"   (All {skipped_no_downgrade} students already graded)")
        return flagged_submissions, student_grades
    
    if not assignment_id:
        print("   ❌ No assignment ID found - cannot submit grades")
        return flagged_submissions, student_grades
    
    print(f"   ✔ Complete/Full points: {marked_complete} | ✘ Incomplete/Zero: {marked_incomplete}")
    if skipped_no_downgrade > 0:
        print(f"   ⏭️  Skipped (already graded): {skipped_no_downgrade}")
    
    # Submit grades
    payload = {"grade_data": grade_data}
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/update_grades"
    
    response = requests.post(url, headers=HEADERS, json=payload)
    
    if response.status_code not in (200, 201):
        print(f"   ❌ Failed to submit grades ({response.status_code})")
        print(f"   {response.text[:300]}")
        return flagged_submissions, student_grades
    
    # Poll job progress
    try:
        progress_data = response.json()
        job_id = progress_data.get("id")
        if job_id:
            print(f"   ⏳ Waiting for grade job to complete...")
            progress_url = f"{CANVAS_BASE_URL}/api/v1/progress/{job_id}"
            while True:
                prog_resp = requests.get(progress_url, headers=HEADERS)
                if prog_resp.status_code == 200:
                    status = prog_resp.json()
                    state = status.get("workflow_state", "unknown")
                    if state == "completed":
                        print(f"   ✅ Grades submitted successfully!")
                        break
                    elif state == "failed":
                        print(f"   ❌ Job failed: {status.get('message', 'Unknown error')}")
                        break
                    time.sleep(2)
                else:
                    break
    except Exception as e:
        print(f"   ⚠️  Could not track job progress: {e}")
    
    return flagged_submissions, student_grades


def export_rationale(course_id: int, topic_id: int, topic_name: str, 
                    student_grades: Dict, students: List[Dict]):
    """Export grading rationale to CSV."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in topic_name)
    filename = f"discussion_rationale_{course_id}_{safe_name}_{timestamp}.csv"
    
    # Determine output directory (cross-platform)
    BASE_DIR = get_output_base_dir()
    
    OUTPUT_DIR = BASE_DIR / "Discussion Forums"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    
    # Create student name mapping
    student_names = {s.get("user_id"): s.get("user", {}).get("name", f"User {s.get('user_id')}") 
                     for s in students}
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Student Name", "User ID", "Grade", "Reason"
        ])
        writer.writeheader()
        
        for user_id, grade_info in student_grades.items():
            writer.writerow({
                "Student Name": student_names.get(user_id, f"User {user_id}"),
                "User ID": user_id,
                "Grade": grade_info["grade"],
                "Reason": grade_info["reason"]
            })
    
    print(f"   ✅ Rationale exported: {output_path.name}")


def main():
    print("🎓 Canvas Discussion Forum Auto-Grader")
    print("Supports Complete/Incomplete and Letter Grade discussions\n")
    
    try:
        course_id = int(input("Enter Course ID: ").strip())
    except ValueError:
        print("❌ Invalid course ID.")
        return
    
    # Verify API access
    print("🔍 Verifying Canvas API access...")
    test_url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}"
    test_resp = requests.get(test_url, headers=HEADERS)
    if not test_resp.headers.get('Content-Type', '').startswith('application/json'):
        print("❌ CRITICAL: Received HTML response.")
        print("   Check your token, URL, and internet connection.")
        return
    
    if test_resp.status_code != 200:
        print(f"❌ Could not access course: {test_resp.text}")
        return
    
    course_data = test_resp.json()
    course_name = course_data.get("name", f"Course {course_id}")
    print(f"✅ Connected to: {course_name}\n")
    
    # Selection mode
    print("📋 Discussion Selection:")
    print("   [1] Grade specific discussions by ID")
    print("   [2] Grade ALL graded discussions (auto-detect)")
    selection_mode = input("\nChoose option (1/2, default=1): ").strip() or "1"
    
    if selection_mode == "2":
        # Auto-detect graded discussions
        print("\n🔍 Scanning for graded discussion forums...")
        all_discussions = get_all_discussion_topics(course_id)
        
        if not all_discussions:
            print("❌ No discussion topics found in course.")
            return
        
        # Ask which grading type to filter
        print("\n📊 Which grading type to include?")
        print("   [1] Complete/Incomplete only")
        print("   [2] Letter grade only")
        print("   [3] Both (all graded discussions)")
        grading_filter_choice = input("\nChoose (1/2/3, default=3): ").strip() or "3"
        
        grading_filter = "all"
        if grading_filter_choice == "1":
            grading_filter = "complete_incomplete"
        elif grading_filter_choice == "2":
            grading_filter = "letter_grade"
        
        graded_discussions = filter_graded_discussions(all_discussions, grading_filter)
        
        if not graded_discussions:
            print(f"❌ No {grading_filter.replace('_', '/')} discussions with passed due dates found.")
            return
        
        print(f"\n✅ Found {len(graded_discussions)} graded discussions with passed due dates:")
        for idx, discussion in enumerate(graded_discussions, 1):
            assignment = discussion.get("assignment", {})
            grading_type = assignment.get("grading_type", "")
            grade_type_display = "Complete/Incomplete" if grading_type == "pass_fail" else "Letter Grade"
            
            due_at = assignment.get("due_at")
            due_date_str = ""
            if due_at:
                try:
                    due_date = parser.isoparse(due_at)
                    due_date_str = f" - Due: {due_date.strftime('%b %d, %Y')}"
                except:
                    pass
            
            print(f"   {idx}. {discussion.get('title')} (ID: {discussion.get('id')}) [{grade_type_display}]{due_date_str}")
        
        # Ask about regrade mode
        print("\n⚙️ Grading Mode:")
        print("   [1] Grade all students (may lower existing grades)")
        print("   [2] Protect existing grades (don't lower scores)")
        regrade_choice = input("\nChoose mode (1/2, default=2): ").strip() or "2"
        regrade_mode = (regrade_choice == "2")
        
        if regrade_mode:
            print("✅ Grade protection ON: Will not lower existing grades")
        else:
            print("⚠️  Grade protection OFF: May lower existing grades")
        
        topic_ids = [(d.get("id"), d.get("title"), d.get("assignment", {}).get("grading_type", "")) 
                     for d in graded_discussions]
    else:
        # Manual topic ID entry
        topic_input = input("\nEnter Discussion Topic ID(s) (space-separated): ").strip()
        try:
            raw_ids = [int(x) for x in topic_input.split()]
        except ValueError:
            print("❌ Invalid discussion topic ID(s).")
            return
        
        # Fetch names and grading types
        all_discussions = get_all_discussion_topics(course_id)
        topic_ids = []
        for tid in raw_ids:
            for d in all_discussions:
                if d.get("id") == tid:
                    assignment = d.get("assignment", {})
                    topic_ids.append((tid, d.get("title", f"Discussion {tid}"), 
                                    assignment.get("grading_type", "")))
                    break
            else:
                topic_ids.append((tid, f"Discussion {tid}", ""))
        
        # Default to regrade mode
        regrade_mode = True
        print("✅ Grade protection ON: Will not lower existing grades")
    
    # Get students
    students = get_active_students(course_id)
    if not students:
        print("🛑 No active students found. Exiting.")
        return
    
    print(f"✅ Found {len(students)} active students\n")
    
    # Determine grading criteria based on first discussion's type
    # (assuming all selected discussions use same grading type)
    first_grading_type = topic_ids[0][2] if topic_ids else ""
    
    grading_criteria = {}
    
    if first_grading_type == "pass_fail":
        # Complete/Incomplete grading
        print("📏 Grading Criteria for Complete/Incomplete:")
        print("   (Leave blank to skip a requirement)")
        
        try:
            total_words = input("   Minimum TOTAL words across all posts (default=50): ").strip()
            min_replies = input("   Minimum number of posts/replies (default=1): ").strip()
            avg_words = input("   Minimum AVERAGE words per post (optional): ").strip()
            
            grading_criteria["complete"] = {
                "total_words": int(total_words) if total_words else 50,
                "min_replies": int(min_replies) if min_replies else 1,
                "avg_words": int(avg_words) if avg_words else 0
            }
            
            print(f"\n   ✅ Complete criteria:")
            print(f"      • Total words: {grading_criteria['complete']['total_words']}+")
            print(f"      • Minimum posts/replies: {grading_criteria['complete']['min_replies']}")
            if grading_criteria['complete']['avg_words'] > 0:
                print(f"      • Average words per post: {grading_criteria['complete']['avg_words']}+")
                
        except ValueError:
            print("   ⚠️  Invalid input. Using defaults")
            grading_criteria["complete"] = {"total_words": 50, "min_replies": 1, "avg_words": 0}
    else:
        # Letter grade grading
        print("📏 Grading Criteria for Letter Grades:")
        print("   For each grade, set: total words, min posts/replies, and avg words per post")
        print("   (Leave entire grade blank to skip - all lower grades will receive F/0)\n")
        
        for grade in ['A', 'B', 'C', 'D']:
            print(f"   --- {grade} Grade ---")
            
            # Set defaults based on grade
            default_total = {'A': 200, 'B': 150, 'C': 100, 'D': 50}
            default_replies = {'A': 2, 'B': 2, 'C': 1, 'D': 1}
            
            try:
                total_words = input(f"   Total words for {grade} (default: {default_total[grade]}, or press Enter to skip {grade} and below): ").strip()
                
                # If user skips this grade, don't ask for lower grades
                if not total_words and grade != 'A':
                    print(f"   ⏭️  Skipping {grade} and all lower grades")
                    break
                
                # If it's A grade and user pressed enter, use default
                if grade == 'A' and not total_words:
                    total_words = str(default_total['A'])
                
                min_replies = input(f"   Min posts/replies for {grade} (default: {default_replies[grade]}): ").strip()
                avg_words = input(f"   Avg words/post for {grade} (optional): ").strip()
                
                grading_criteria[grade] = {
                    "total_words": int(total_words) if total_words else default_total[grade],
                    "min_replies": int(min_replies) if min_replies else default_replies[grade],
                    "avg_words": int(avg_words) if avg_words else 0
                }
            except ValueError:
                print(f"   ⚠️  Invalid input for {grade}. Using defaults")
                grading_criteria[grade] = {
                    "total_words": default_total[grade],
                    "min_replies": default_replies[grade],
                    "avg_words": 0
                }
        
        # Ensure we have at least A grade
        if 'A' not in grading_criteria:
            print(f"   ⚠️  No A grade defined. Using default: 200 words, 2 posts")
            grading_criteria['A'] = {"total_words": 200, "min_replies": 2, "avg_words": 0}
        
        print(f"\n   ✅ Grading Scale:")
        for grade in ['A', 'B', 'C', 'D']:
            if grade in grading_criteria:
                criteria = grading_criteria[grade]
                print(f"      {grade}: {criteria['total_words']}+ total words, {criteria['min_replies']}+ posts", end="")
                if criteria['avg_words'] > 0:
                    print(f", {criteria['avg_words']}+ avg words/post")
                else:
                    print()
        print(f"      F: Below minimum")
    
    # Grade each discussion
    all_flagged = {}
    for idx, (topic_id, topic_name, grading_type) in enumerate(topic_ids, 1):
        print(f"\n{'='*70}")
        print(f"Processing discussion {idx}/{len(topic_ids)}")
        print(f"{'='*70}")
        
        # Get max points for this discussion
        max_points = 10  # default
        for d in all_discussions if 'all_discussions' in locals() else []:
            if d.get("id") == topic_id:
                assignment = d.get("assignment", {})
                max_points = assignment.get("points_possible", 10)
                break
        
        flagged, student_grades = grade_discussion_topic(
            course_id, topic_id, topic_name, students, 
            grading_criteria, grading_type, max_points, regrade_mode
        )
        
        if flagged:
            all_flagged[topic_id] = {"name": topic_name, "flagged": flagged}
        
        # Export rationale
        export_rationale(course_id, topic_id, topic_name, student_grades, students)
    
    print("\n" + "="*70)
    print("🏁 All discussions processed.")
    print("="*70)
    
    # Print flagged submissions summary
    if all_flagged:
        print("\n" + "="*70)
        print("⚠️  FLAGGED SUBMISSIONS FOR REVIEW")
        print("="*70)
        for topic_id, data in all_flagged.items():
            print(f"\n💬 {data['name']} (ID: {topic_id}): {len(data['flagged'])} flagged")
            print("-" * 70)
            for item in data['flagged']:
                grade_display = item.get('grade', 'N/A')
                print(f"\n👤 {item['name']} (ID: {item['user_id']}) - Grade: {grade_display}")
                print(f"   📊 Stats: {item['word_count']} total words, {item['num_posts']} posts, {item['avg_words']} avg words/post")
                for flag in item['flags']:
                    print(f"   • {flag}")
        print("\n" + "="*70)
    else:
        print("\n✅ No submissions flagged for review.")



if __name__ == "__main__":
    main()