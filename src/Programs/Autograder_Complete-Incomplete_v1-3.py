import os
import platform
import requests
import time
import json
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime
from pathlib import Path
import csv

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

# Thresholds for grading (not AI detection)
MIN_FILE_SIZE = 1024  # 1KB

def get_config_dir() -> Path:
    """Get the configuration directory for storing settings."""
    system = platform.system()
    
    if system == "Windows":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        config_dir = base / "CanvasAutograder"
    elif system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support" / "CanvasAutograder"
    else:
        config_dir = Path.home() / ".config" / "CanvasAutograder"
    
    return config_dir


def get_output_base_dir() -> Path:
    """Get base output directory in a cross-platform way."""
    system = platform.system()
    
    # Check for /output directory first (container/deployment environment)
    if os.path.isdir("/output"):
        return Path("/output")
    
    # Check for custom output directory in JSON config (matches autograder_utils.py)
    config_file = get_config_dir() / "settings.json"
    if config_file.exists():
        try:
            import json
            with open(config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
                if "output_directory" in config:
                    custom_dir = Path(config["output_directory"])
                    if custom_dir.exists() or custom_dir.parent.exists():
                        custom_dir.mkdir(parents=True, exist_ok=True)
                        return custom_dir
        except Exception:
            pass  # Fall through to default
    
    # Default location
    if system == "Windows":
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
    else:
        documents = Path.home() / "Documents"
    
    return documents / "Autograder Rationales"


def count_words(text: str) -> int:
    """Count words in text."""
    if not text:
        return 0
    return len(text.split())

def has_pdf_annotations(submission: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Check if submission has PDF annotations.
    Canvas uses 'student_annotation' type when students annotate instructor-provided PDFs.
    For student-uploaded PDFs, it uses 'online_upload' with canvadoc_document_id.
    Returns: (has_annotations, debug_info)
    """
    submission_type = submission.get("submission_type")
    user_id = submission.get("user_id")
    
    # CRITICAL: Canvas uses "student_annotation" type when students annotate 
    # a PDF that the instructor provided in the assignment
    if submission_type == "student_annotation":
        print(f"   📝 Found student_annotation submission for user {user_id}")
        return True, "student_annotation type"
    
    # Check if this is an online_upload submission with annotations
    if submission_type == "online_upload":
        attachments = submission.get("attachments", [])
        
        if not attachments:
            return False, "No attachments"
        
        for attachment in attachments:
            # Check if it's a PDF
            content_type = attachment.get("content-type", "")
            filename = attachment.get("filename", "")
            is_pdf = content_type.startswith("application/pdf") or filename.lower().endswith(".pdf")
            
            if is_pdf:
                # Check for canvadoc_document_id - this indicates the PDF was viewed/annotated in Canvas
                if attachment.get("canvadoc_document_id"):
                    print(f"   📝 Found annotated PDF for user {user_id} (canvadoc ID: {attachment.get('canvadoc_document_id')})")
                    return True, f"Has canvadoc_document_id"
                
                # Also check if there's a preview_url which indicates Canvas processed the document
                if attachment.get("preview_url"):
                    print(f"   📝 Found PDF with preview for user {user_id}")
                    return True, f"Has preview_url"
    
    return False, f"Not annotation type (type: {submission_type})"

def evaluate_submission(submission: Dict[str, Any], all_submissions: List[Dict[str, Any]], min_word_count: int) -> Tuple[bool, List[str]]:
    """
    Determine if submission shows good faith effort.
    Returns: (is_complete, list_of_flags)
    """
    flags = []
    has_content = False
    
    submission_type = submission.get("submission_type")
    user_id = submission.get("user_id")
    
    # First, check if this is a PDF submission with annotations
    # If it has annotations, we consider it valid and complete
    has_annotations, debug_info = has_pdf_annotations(submission)
    if has_annotations:
        print(f"   ✅ User {user_id}: PDF with annotations detected - marking complete")
        return True, flags  # PDF with annotations is automatically valid
    
    # Check text body
    body = submission.get("body", "")
    if body:
        has_content = True
        word_count = count_words(body)
        
        # Short text check
        if word_count > 0 and word_count < min_word_count:
            flags.append(f"Very short text ({word_count} words)")
    
    # Check attachments (non-PDF or PDF without annotations)
    attachments = submission.get("attachments", [])
    if attachments:
        has_content = True
        for file in attachments:
            file_size = file.get("size", 0)
            file_name = file.get("filename", "unknown")
            content_type = file.get("content-type", "")
            
            # Check if it's a PDF (these would have been caught above if annotated)
            is_pdf = content_type.startswith("application/pdf") or file_name.lower().endswith(".pdf")
            
            # If it's a PDF without annotations, flag it
            if is_pdf and not file.get("canvadoc_document_id") and not file.get("preview_url"):
                flags.append(f"PDF '{file_name}' uploaded without annotations - may need manual review")
            
            # Small file check (but not for PDFs)
            if not is_pdf and file_size > 0 and file_size < MIN_FILE_SIZE:
                flags.append(f"Small file '{file_name}' ({file_size} bytes)")
    
    # Check URL submissions
    url = submission.get("url")
    if url:
        has_content = True
        if not body and not attachments:
            flags.append("URL with no description")
    
    # Determine if it's a valid submission
    is_submitted = submission_type and submission_type not in ["not_submitted", "none", "on_paper"]
    
    is_complete = has_content and is_submitted
    
    print(f"   🔍 User {user_id}: type={submission_type}, has_content={has_content}, is_submitted={is_submitted}, complete={is_complete}")
    
    return is_complete, flags

def get_active_students(course_id: int) -> List[Dict]:
    print("📥 Fetching active student enrollments...")
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/enrollments"
    params = {"type": ["StudentEnrollment"], "state": ["active"], "per_page": 100}
    response = requests.get(url, headers=HEADERS, params=params)

    if not response.headers.get('Content-Type', '').startswith('application/json'):
        print("⚠️ Received non-JSON response (likely redirected to login):")
        print(response.text[:300])
        return []

    if response.status_code != 200:
        print(f"❌ Failed to fetch enrollments: {response.text}")
        return []

    data = response.json()
    return data if isinstance(data, list) else []

def get_all_assignments(course_id: int) -> List[Dict]:
    """Fetch all assignments in the course."""
    print("📚 Fetching all assignments...")
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments"
    params = {"per_page": 100}
    response = requests.get(url, headers=HEADERS, params=params)

    if response.status_code != 200:
        print(f"❌ Failed to fetch assignments: {response.text}")
        return []

    data = response.json()
    return data if isinstance(data, list) else []

def filter_complete_incomplete_assignments(assignments: List[Dict], include_no_deadline: bool = False, grade_future_submitted: bool = False) -> List[Dict]:
    """
    Filter assignments to only those using complete/incomplete grading with passed deadlines.
    Canvas indicates this with grading_type = "pass_fail"
    
    Args:
        assignments: List of assignment dictionaries
        include_no_deadline: Whether to include assignments without due dates
        grade_future_submitted: Whether to include future assignments that have submissions
    
    Returns:
        List of filtered assignments
    """
    from datetime import datetime
    import pytz
    
    filtered = []
    now = datetime.now(pytz.UTC)
    
    for assignment in assignments:
        grading_type = assignment.get("grading_type", "")
        if grading_type != "pass_fail":
            continue
        
        # Check due date
        due_at = assignment.get("due_at")
        
        # If no due date, check user preference
        if not due_at:
            if include_no_deadline:
                print(f"   ℹ️  Including '{assignment.get('name')}' (no due date set)")
                filtered.append(assignment)
            else:
                print(f"   ⏭️  Skipping '{assignment.get('name')}' (no due date set)")
            continue
        
        # Parse due date and compare with current time
        try:
            from dateutil import parser as date_parser
            due_date = date_parser.isoparse(due_at)
            # Ensure due_date is timezone-aware
            if due_date.tzinfo is None:
                due_date = pytz.UTC.localize(due_date)
            
            if now >= due_date:
                # Deadline has passed - always include
                filtered.append(assignment)
            elif grade_future_submitted:
                # Future deadline, but user wants to grade submitted work
                time_remaining = due_date - now
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                print(f"   ⚠️  Including '{assignment.get('name')}' (due in {days}d {hours}h)")
                print(f"       Will only grade students who already submitted")
                filtered.append(assignment)
            else:
                # Future deadline, skip
                time_remaining = due_date - now
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                print(f"   ⏭️  Skipping '{assignment.get('name')}' (due in {days}d {hours}h)")
        except Exception as e:
            print(f"   ⚠️  Could not parse due date for '{assignment.get('name')}': {e}")
            print(f"       Skipping to be safe (cannot verify deadline has passed)")
    
    return filtered

def filter_by_deadline(assignments: List[Dict], include_no_deadline: bool = False, grade_future_submitted: bool = False) -> List[Dict]:
    """
    Filter assignments to only those with passed deadlines.
    
    Args:
        assignments: List of assignment dictionaries
        include_no_deadline: Whether to include assignments without due dates
        grade_future_submitted: Whether to include future assignments that have submissions
    
    Returns:
        List of assignments with passed deadlines
    """
    from datetime import datetime
    import pytz
    
    filtered = []
    now = datetime.now(pytz.UTC)
    
    for assignment in assignments:
        due_at = assignment.get("due_at")
        
        # If no due date, check user preference
        if not due_at:
            if include_no_deadline:
                print(f"   ℹ️  Including '{assignment.get('name')}' (no due date set)")
                filtered.append(assignment)
            else:
                print(f"   ⏭️  Skipping '{assignment.get('name')}' (no due date set)")
            continue
        
        # Parse due date and compare with current time
        try:
            from dateutil import parser as date_parser
            due_date = date_parser.isoparse(due_at)
            # Ensure due_date is timezone-aware
            if due_date.tzinfo is None:
                due_date = pytz.UTC.localize(due_date)
            
            if now >= due_date:
                # Deadline has passed - always include
                filtered.append(assignment)
            elif grade_future_submitted:
                # Future deadline, but user wants to grade submitted work
                time_remaining = due_date - now
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                print(f"   ⚠️  Including '{assignment.get('name')}' (due in {days}d {hours}h)")
                print(f"       Will only grade students who already submitted")
                filtered.append(assignment)
            else:
                # Future deadline, skip
                time_remaining = due_date - now
                days = time_remaining.days
                hours = time_remaining.seconds // 3600
                print(f"   ⏭️  Skipping '{assignment.get('name')}' (due in {days}d {hours}h)")
        except Exception as e:
            print(f"   ⚠️  Could not parse due date for '{assignment.get('name')}': {e}")
            print(f"       Skipping to be safe (cannot verify deadline has passed)")
    
    return filtered

def get_submissions(course_id: int, assignment_id: int) -> Dict[int, Dict]:
    print(f"📤 Fetching submissions for assignment {assignment_id}...")
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions"
    params = {"include": ["attachments", "user"], "per_page": 100}

    all_submissions = []
    page_count = 0

    while url:
        response = requests.get(url, headers=HEADERS, params=params)
        page_count += 1

        if not response.headers.get('Content-Type', '').startswith('application/json'):
            print("⚠️ Received non-JSON response (likely redirected to login):")
            print(response.text[:300])
            return {}

        if response.status_code != 200:
            print(f"❌ Failed to fetch submissions: {response.text}")
            return {}

        data = response.json()
        if not isinstance(data, list):
            print("❌ Unexpected submission format")
            return {}

        all_submissions.extend(data)

        # Check for next page in Link header
        link_header = response.headers.get('Link', '')
        url = None
        params = None  # Clear params for subsequent pages (they're in the URL)

        if link_header:
            # Parse Link header for 'next' relation
            for link in link_header.split(','):
                if 'rel="next"' in link:
                    # Extract URL from <URL>
                    url = link[link.find('<')+1:link.find('>')]
                    break

    if page_count > 1:
        print(f"   📄 Fetched {len(all_submissions)} submissions across {page_count} pages")

    return {sub.get("user_id"): sub for sub in all_submissions if sub.get("user_id")}

def get_assignment_name(course_id: int, assignment_id: int) -> str:
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}"
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code == 200:
        try:
            return resp.json().get("name", f"Assignment {assignment_id}")
        except:
            pass
    return f"Assignment {assignment_id}"

def grade_assignment(course_id: int, assignment_id: int, students: List[Dict], 
                     submissions: Dict[int, Dict], min_word_count: int, 
                     regrade_mode: bool = False) -> List[Dict]:
    """
    Grade assignment and return list of flagged submissions.
    
    Args:
        regrade_mode: If True, only grade "incomplete" submissions (don't change "complete" to "incomplete")
    
    Returns: List of dicts with 'name', 'user_id', 'flags'
    """
    grade_data = {}
    marked_complete = 0
    marked_incomplete = 0
    skipped_already_complete = 0
    flagged_submissions = []
    
    # Convert submissions dict to list for duplicate checking
    all_submissions_list = list(submissions.values())

    for enrollment in students:
        user_id = enrollment.get("user_id")
        if not user_id:
            continue

        submission = submissions.get(user_id)

        if submission and submission.get("workflow_state") != "unsubmitted":
            # Check current grade if in regrade mode
            current_grade = submission.get("grade")
            
            # In regrade mode, skip students who already have "complete"
            if regrade_mode and current_grade == "complete":
                print(f"   ⏭️  User {user_id}: Already complete, skipping")
                skipped_already_complete += 1
                continue
            
            is_complete, flags = evaluate_submission(submission, all_submissions_list, min_word_count)
            
            if is_complete:
                grade = "complete"
                marked_complete += 1
                
                # If flagged, still grade as complete but record for review
                if flags:
                    user_info = submission.get("user", {})
                    student_name = user_info.get("name", f"User {user_id}")
                    flagged_submissions.append({
                        "name": student_name,
                        "user_id": user_id,
                        "flags": flags
                    })
            else:
                grade = "incomplete"
                marked_incomplete += 1
        else:
            # In regrade mode, check if they already have a grade
            if regrade_mode and submission:
                current_grade = submission.get("grade")
                if current_grade == "complete":
                    print(f"   ⏭️  User {user_id}: Already complete (no submission), skipping")
                    skipped_already_complete += 1
                    continue
            
            grade = "incomplete"
            marked_incomplete += 1
        
        grade_data[str(user_id)] = {"posted_grade": grade}

    if not grade_data:
        print("⚠️ No students to grade for this assignment.")
        if regrade_mode and skipped_already_complete > 0:
            print(f"   (All {skipped_already_complete} students already marked complete)")
        return flagged_submissions

    payload = {"grade_data": grade_data}
    url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}/assignments/{assignment_id}/submissions/update_grades"

    print(f"\n✅ Submitting grades for assignment {assignment_id} ({len(grade_data)} students)...")
    print(f"   ✔ Complete: {marked_complete} | ✘ Incomplete: {marked_incomplete}")
    if regrade_mode and skipped_already_complete > 0:
        print(f"   ⏭️  Skipped (already complete): {skipped_already_complete}")
    if flagged_submissions:
        print(f"   ⚠️  Flagged for review: {len(flagged_submissions)}")

    response = requests.post(url, headers=HEADERS, json=payload)

    if response.status_code not in (200, 201):
        print(f"❌ Assignment {assignment_id}: Failed to submit grades ({response.status_code})")
        print(response.text[:500])
        return flagged_submissions

    # Poll job progress
    try:
        progress_data = response.json()
        job_id = progress_data.get("id")
        if not job_id:
            print("⚠️ No job ID — assuming immediate success.")
            return flagged_submissions
    except Exception:
        print("⚠️ Could not parse job ID.")
        return flagged_submissions

    print(f"⏳ Waiting for grade job {job_id} to finish...")
    progress_url = f"{CANVAS_BASE_URL}/api/v1/progress/{job_id}"
    while True:
        prog_resp = requests.get(progress_url, headers=HEADERS)
        if prog_resp.status_code != 200:
            print(f"⚠️ Could not check job status (HTTP {prog_resp.status_code})")
            break

        try:
            status = prog_resp.json()
            state = status.get("workflow_state", "unknown")
            if state == "completed":
                print("✅ Grade update completed!")
                break
            elif state == "failed":
                msg = status.get("message", "Unknown error")
                print(f"❌ Job failed: {msg}")
                break
            else:
                time.sleep(3)
        except Exception as e:
            print(f"⚠️ Error reading progress: {e}")
            break

    print(f"✅ Assignment {assignment_id}: Grades processed!")
    return flagged_submissions

def export_rationale(course_id: int, assignment_id: int, assignment_name: str, rationale_rows: List[Dict]):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in assignment_name)
    filename = f"complete_incomplete_rationale_{course_id}_{safe_name}_{timestamp}.csv"

    # Cross-platform output base
    BASE_DIR = get_output_base_dir()

    OUTPUT_DIR = BASE_DIR / "Complete-Incomplete Assignments"
    
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"❌ Failed to create output directory: {e}")
        return
        
    output_path = OUTPUT_DIR / filename

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=[
                "Student Name", "User ID", "Grade", "Reason"
            ])
            writer.writeheader()
            for row in rationale_rows:
                writer.writerow({
                    "Student Name": row["name"],
                    "User ID": row["user_id"],
                    "Grade": row["grade"],
                    "Reason": row["reason"]
                })
        print(f"✅ Rationale exported: {output_path.name}")
            
    except Exception as e:
        print(f"❌ Error creating CSV file: {e}")

def main():
    print("🎓 Canvas Auto-Grader: Complete/Incomplete with PDF Annotation Support")
    print("Make sure CANVAS_API_TOKEN is set in your environment.\n")

    print("="*70)
    print("📌 HOW TO FIND YOUR COURSE ID")
    print("="*70)
    print("1. Open your course in Canvas")
    print("2. Look at the URL in your browser's address bar")
    print("3. Find the number after '/courses/' in the URL")
    print()
    print("   Example: https://cabrillo.instructure.com/courses/12345")
    print("            The Course ID is: 12345")
    print("="*70)
    print()

    try:
        course_id = int(input("Enter Course ID: ").strip())
    except ValueError:
        print("❌ Invalid course ID. Please enter only the numeric ID.")
        return

    # Verify API access
    print("🔍 Verifying Canvas API access...")
    test_url = f"{CANVAS_BASE_URL}/api/v1/courses/{course_id}"
    test_resp = requests.get(test_url, headers=HEADERS)
    if not test_resp.headers.get('Content-Type', '').startswith('application/json'):
        print("❌ CRITICAL: Received HTML (e.g., OpenCCC login page).")
        print("   Check your token, URL, and internet connection.")
        print("   Response preview:", repr(test_resp.text[:200]))
        return

    # Session-wide deadline settings (default to safe mode, can be toggled in menu)
    include_no_deadline = False
    grade_future_submitted = False

    # Selection mode with deadline toggles
    while True:
        print("\n📋 Assignment Selection:")
        print("   [1] Grade specific assignments by ID")
        print("   [2] Grade ALL complete/incomplete assignments (auto-detect)")
        print("   [3] Grade assignments filtered by keyword")
        print()
        print("   Deadline Settings:")
        no_deadline_status = "ON" if include_no_deadline else "OFF"
        future_status = "ON" if grade_future_submitted else "OFF"
        print(f"   [N] Include no-deadline assignments: {no_deadline_status}")
        print(f"   [F] Grade submitted work for future deadlines: {future_status}")
        if grade_future_submitted:
            print(f"       ⚠️  Only grades students who already submitted")
        print()
        
        selection_input = input("Choose option (1/2/3, N, F): ").strip().upper()
        
        # Handle toggle options
        if selection_input == 'N':
            include_no_deadline = not include_no_deadline
            status = "ON" if include_no_deadline else "OFF"
            print(f"\n✅ No-deadline assignments: {status}")
            continue
        elif selection_input == 'F':
            grade_future_submitted = not grade_future_submitted
            status = "ON" if grade_future_submitted else "OFF"
            print(f"\n✅ Future deadline grading: {status}")
            if grade_future_submitted:
                print("   ⚠️  Will only grade students who already submitted")
                print("      Students without submissions will remain ungraded")
            continue
        elif selection_input in ['1', '2', '3']:
            selection_mode = selection_input
            break
        else:
            print("❌ Invalid choice. Please enter 1, 2, 3, N, or F")
            continue

    if selection_mode == "2":
        # Auto-detect complete/incomplete assignments
        print("\n🔍 Scanning for complete/incomplete assignments...")
        all_assignments = get_all_assignments(course_id)
        
        if not all_assignments:
            print("❌ No assignments found in course.")
            return
        
        print("\n🕒 Filtering by grading type and deadline...")
        complete_incomplete_assignments = filter_complete_incomplete_assignments(
            all_assignments, 
            include_no_deadline=include_no_deadline,
            grade_future_submitted=grade_future_submitted
        )
        
        if not complete_incomplete_assignments:
            print("❌ No complete/incomplete assignments found matching your deadline settings.")
            return
        
        print(f"\n✅ Found {len(complete_incomplete_assignments)} complete/incomplete assignments:")
        for idx, assignment in enumerate(complete_incomplete_assignments, 1):
            print(f"   {idx}. {assignment.get('name')} (ID: {assignment.get('id')})")
        
        # Ask about regrade mode
        print("\n⚙️ Grading Mode:")
        print("   [1] Grade all students (may change 'complete' to 'incomplete')")
        print("   [2] Regrade only 'incomplete' students (preserve existing 'complete' grades)")
        regrade_choice = input("\nChoose mode (1/2, default=2): ").strip() or "2"
        regrade_mode = (regrade_choice == "2")
        
        if regrade_mode:
            print("✅ Regrade mode: Will only update 'incomplete' submissions")
        else:
            print("⚠️  Full grade mode: May change 'complete' to 'incomplete' if criteria not met")
        
        assignment_ids = [a.get("id") for a in complete_incomplete_assignments]
        
    elif selection_mode == "3":
        # Filter by keyword
        print("\n🔍 Fetching all assignments...")
        all_assignments = get_all_assignments(course_id)
        
        if not all_assignments:
            print("❌ No assignments found in course.")
            return
        
        filter_keyword = input("\nEnter keyword to filter assignments (e.g., 'essay', 'quiz', 'homework'): ").strip().lower()
        if not filter_keyword:
            print("❌ No keyword provided.")
            return
        
        # First filter by keyword
        keyword_matched = [a for a in all_assignments if filter_keyword in a.get("name", "").lower()]
        
        if not keyword_matched:
            print(f"❌ No assignments found containing '{filter_keyword}'")
            return
        
        # Then filter by deadline using session settings
        print(f"\n🕒 Filtering {len(keyword_matched)} assignments by deadline...")
        filtered_assignments = filter_by_deadline(
            keyword_matched, 
            include_no_deadline=include_no_deadline,
            grade_future_submitted=grade_future_submitted
        )
        
        if not filtered_assignments:
            print(f"\n❌ No assignments containing '{filter_keyword}' match your deadline settings")
            return
        
        print(f"\n✅ Found {len(filtered_assignments)} assignments with '{filter_keyword}':")
        for idx, assignment in enumerate(filtered_assignments, 1):
            grading_type = assignment.get("grading_type", "points")
            print(f"   {idx}. {assignment.get('name')} (ID: {assignment.get('id')}) [{grading_type}]")
        
        # Ask about regrade mode
        print("\n⚙️ Grading Mode:")
        print("   [1] Grade all students (may change existing grades)")
        print("   [2] Regrade only 'incomplete' students (preserve existing 'complete' grades)")
        regrade_choice = input("\nChoose mode (1/2, default=2): ").strip() or "2"
        regrade_mode = (regrade_choice == "2")
        
        if regrade_mode:
            print("✅ Regrade mode: Will only update 'incomplete' submissions")
        else:
            print("⚠️  Full grade mode: May change existing grades if criteria not met")
        
        assignment_ids = [a.get("id") for a in filtered_assignments]
        
    else:
        # Manual assignment ID entry
        print("\n" + "="*70)
        print("📌 HOW TO FIND ASSIGNMENT IDs")
        print("="*70)
        print("1. Go to the Assignments page in Canvas")
        print("2. Click on an assignment to open it")
        print("3. Look at the URL in your browser's address bar")
        print("4. Find the number after '/assignments/' in the URL")
        print()
        print("   Example: https://cabrillo.instructure.com/courses/12345/assignments/67890")
        print("            The Assignment ID is: 67890")
        print()
        print("   TIP: You can enter multiple IDs separated by spaces")
        print("        Example: 67890 67891 67892")
        print("="*70)
        print()
        assignment_input = input("Enter Assignment ID(s) (space-separated): ").strip()
        try:
            assignment_ids = [int(x) for x in assignment_input.split()]
        except ValueError:
            print("❌ Invalid assignment ID(s).")
            return
        
        # Default to regrade mode for manual entry
        regrade_mode = True
        print("✅ Using regrade mode: Will only update 'incomplete' submissions")

    # Get minimum word count from user
    try:
        min_word_count_input = input("\nEnter minimum word count for complete submissions (default=50): ").strip()
        if min_word_count_input == "":
            MIN_WORD_COUNT = 50
        else:
            MIN_WORD_COUNT = int(min_word_count_input)
        print(f"✅ Using minimum word count: {MIN_WORD_COUNT}")
    except ValueError:
        print("⚠️ Invalid input. Using default minimum word count of 50.")
        MIN_WORD_COUNT = 50

    students = get_active_students(course_id)
    if not students:
        print("🛑 No active students found. Exiting.")
        return
    
    print(f"✅ Found {len(students)} active students\n")
    
    all_flagged = {}
    for idx, aid in enumerate(assignment_ids, 1):
        print(f"\n{'='*70}")
        print(f"Processing assignment {idx}/{len(assignment_ids)}")
        print(f"{'='*70}")
        
        assignment_name = get_assignment_name(course_id, aid)
        submissions = get_submissions(course_id, aid)
        flagged = grade_assignment(course_id, aid, students, submissions, MIN_WORD_COUNT, regrade_mode)
        if flagged:
            all_flagged[aid] = flagged

        # Build rationale rows for THIS assignment
        rationale_rows = []
        for enrollment in students:
            user_id = enrollment.get("user_id")
            if not user_id:
                continue
            submission = submissions.get(user_id)
            student_name = enrollment.get("user", {}).get("name", f"User {user_id}")

            # Check if skipped due to regrade mode
            if regrade_mode and submission:
                current_grade = submission.get("grade")
                if current_grade == "complete":
                    rationale_rows.append({
                        "name": student_name,
                        "user_id": user_id,
                        "grade": "complete",
                        "reason": "Already complete (not regraded)"
                    })
                    continue

            if submission and submission.get("workflow_state") != "unsubmitted":
                is_complete, flags = evaluate_submission(submission, list(submissions.values()), MIN_WORD_COUNT)
                grade = "complete" if is_complete else "incomplete"
                reason = "; ".join(flags) if flags else "Meets requirements" if is_complete else "Incomplete submission"
            else:
                grade = "incomplete"
                reason = "No submission"

            rationale_rows.append({
                "name": student_name,
                "user_id": user_id,
                "grade": grade,
                "reason": reason
            })

        export_rationale(course_id, aid, assignment_name, rationale_rows)
        print()

    print("\n" + "="*70)
    print("🏁 All assignments processed.")
    print("="*70)
    
    # Print flagged submissions summary
    if all_flagged:
        print("\n" + "="*70)
        print("⚠️  FLAGGED SUBMISSIONS FOR REVIEW")
        print("="*70)
        for assignment_id, flagged_list in all_flagged.items():
            assignment_name = get_assignment_name(course_id, assignment_id)
            print(f"\n📋 {assignment_name} (ID: {assignment_id}): {len(flagged_list)} flagged")
            print("-" * 70)
            for item in flagged_list:
                print(f"\n👤 {item['name']} (ID: {item['user_id']})")
                for flag in item['flags']:
                    print(f"   • {flag}")
        print("\n" + "="*70)
    else:
        print("\n✅ No submissions flagged for review.")


if __name__ == "__main__":
    main()