"""
Demo mode: self-contained mock data for principal pitch.
All student names and data are fictional. No real student data.

Two profiles:
  "cc"  — Community College (ETHN-1-02, HIST-27, CIS-101, ENGL-1A)
  "hs"  — High School (AP US History, 11th Grade English, Ethnic Studies, Digital Literacy)

Narrative (same for both profiles):
  Act 1 — Time Recovered: 80+ ungraded discussion posts, run autograder, done.
  Act 2 — The Whole Student: ESL adjustment, burnout signal, smoking gun (rarest case).
"""
import random
import time
from typing import List, Dict, Callable

# ── Reproducible RNG ──────────────────────────────────────────────────────────
_rng = random.Random(42)

# ── Term IDs ──────────────────────────────────────────────────────────────────
SPRING_2026 = 301
FALL_2025   = 300

# =============================================================================
# COMMUNITY COLLEGE profile
# =============================================================================

_CC_SPRING_COURSES = [
    {"id": 80001, "name": "ETHN-1-02: Introduction to Ethnic Studies",
     "course_code": "ETHN-1-02", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 80002, "name": "HIST-27: History of the Americas",
     "course_code": "HIST-27", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 80003, "name": "CIS-101-03: Introduction to Computer Information Systems",
     "course_code": "CIS-101-03", "workflow_state": "available", "course_format": "hybrid"},
    {"id": 80004, "name": "ENGL-1A-04: Composition and Reading",
     "course_code": "ENGL-1A-04", "workflow_state": "available", "course_format": "on_campus"},
]

_CC_FALL_COURSES = [
    {"id": 70001, "name": "ETHN-1-01: Introduction to Ethnic Studies",
     "course_code": "ETHN-1-01", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 70002, "name": "ENGL-1A-02: Composition and Reading",
     "course_code": "ENGL-1A-02", "workflow_state": "available", "course_format": "online"},
]

_CC_ASSIGNMENTS: Dict[int, List[Dict]] = {
    80001: [
        {"id": 20001, "name": "Weekly Discussions",
         "assignments": [
             {"id": 101001, "name": "Week 1 Discussion: Who Tells Our Stories?",
              "due_at": "2026-01-31T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 101002, "name": "Week 2 Discussion: Land & Belonging",
              "due_at": "2026-02-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 101003, "name": "Week 4 Discussion: Cultural Memory",
              "due_at": "2026-02-21T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 101004, "name": "Week 6 Discussion: Resistance & Identity",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 28},
         ]},
        {"id": 20002, "name": "Written Assignments",
         "assignments": [
             {"id": 101010, "name": "Reading Response 1",
              "due_at": "2026-02-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_upload"],
              "needs_grading_count": 0},
             {"id": 101011, "name": "Midterm Essay",
              "due_at": "2026-03-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_upload"],
              "needs_grading_count": 3},
         ]},
    ],
    80002: [
        {"id": 20010, "name": "Weekly Discussions",
         "assignments": [
             {"id": 102001, "name": "Week 2: Colonial Encounters",
              "due_at": "2026-02-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 102002, "name": "Week 4: Revolution & Independence",
              "due_at": "2026-02-21T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 102003, "name": "Week 6: Immigration Waves",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 31},
         ]},
    ],
    80003: [
        {"id": 20020, "name": "Reflections",
         "assignments": [
             {"id": 103001, "name": "Module 1 Reflection",
              "due_at": "2026-02-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_text_entry"],
              "needs_grading_count": 0},
             {"id": 103002, "name": "Module 3 Reflection",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_text_entry"],
              "needs_grading_count": 14},
         ]},
    ],
    80004: [
        {"id": 20030, "name": "Weekly Discussions",
         "assignments": [
             {"id": 104001, "name": "Discussion: The Unreliable Narrator",
              "due_at": "2026-02-28T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 104002, "name": "Discussion: Argument & Evidence",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 11},
         ]},
    ],
    70001: [
        {"id": 20040, "name": "Weekly Discussions",
         "assignments": [
             {"id": 701001, "name": "Week 10 Discussion: Solidarity",
              "due_at": "2025-11-08T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
         ]},
    ],
    70002: [
        {"id": 20050, "name": "Weekly Discussions",
         "assignments": [
             {"id": 702001, "name": "Final Discussion: Reflection",
              "due_at": "2025-12-06T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
         ]},
    ],
}

_CC_AIC_RUNS = [
    {
        "course_id": "80001",
        "course_name": "ETHN-1-02",
        "assignment_id": "101004",
        "assignment_name": "Week 6 Discussion: Resistance & Identity",
        "last_run": "2026-03-10T14:22:00",
        "analyzed_count": 35,
        "smoking_gun_count": 1,
    },
    {
        "course_id": "80002",
        "course_name": "HIST-27",
        "assignment_id": "102003",
        "assignment_name": "Week 6: Immigration Waves",
        "last_run": "2026-03-09T09:15:00",
        "analyzed_count": 33,
        "smoking_gun_count": 0,
    },
    {
        "course_id": "80004",
        "course_name": "ENGL-1A-04",
        "assignment_id": "104002",
        "assignment_name": "Discussion: Argument & Evidence",
        "last_run": "2026-03-08T16:45:00",
        "analyzed_count": 29,
        "smoking_gun_count": 2,
    },
]

# Trajectory assignment labels (CC)
_CC_TRAJECTORY_ASSIGNMENTS = [
    ("101001", "Week 1 Discussion", "2026-01-31T23:59:00Z"),
    ("101002", "Week 2 Discussion", "2026-02-07T23:59:00Z"),
    ("101003", "Week 4 Discussion", "2026-02-21T23:59:00Z"),
    ("101004", "Week 6 Discussion", "2026-03-07T23:59:00Z"),
]

# Student detail context labels (CC)
_CC_DETAIL_CONTEXT = {
    "assignment_name": "Week 6 Discussion: Resistance & Identity",
    "course_id":       "80001",
}

# =============================================================================
# HIGH SCHOOL profile
# =============================================================================

_HS_SPRING_COURSES = [
    {"id": 90001, "name": "AP US History, Period 2",
     "course_code": "AP-US-HIST-P2", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 90002, "name": "11th Grade English B, Period 5",
     "course_code": "ENG-11B-P5", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 90003, "name": "Ethnic Studies (11), Period 3",
     "course_code": "ETH-11-P3", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 90004, "name": "Digital Literacy (9), Period 4",
     "course_code": "DL-9-P4", "workflow_state": "available", "course_format": "blended"},
]

_HS_FALL_COURSES = [
    {"id": 71001, "name": "AP US History, Period 2",
     "course_code": "AP-US-HIST-P2", "workflow_state": "available", "course_format": "on_campus"},
    {"id": 71002, "name": "10th Grade English, Period 1",
     "course_code": "ENG-10-P1", "workflow_state": "available", "course_format": "online"},
]

_HS_ASSIGNMENTS: Dict[int, List[Dict]] = {
    90001: [
        {"id": 20100, "name": "Weekly Discussions",
         "assignments": [
             {"id": 111001, "name": "Week 1 Discussion: Primary Sources & Perspective",
              "due_at": "2026-01-31T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 111002, "name": "Week 2 Discussion: Colonialism & Resistance",
              "due_at": "2026-02-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 111003, "name": "Week 4 Discussion: Reconstruction Era",
              "due_at": "2026-02-21T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 111004, "name": "Week 6 Discussion: Civil Rights Era",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 28},
         ]},
        {"id": 20101, "name": "Written Work",
         "assignments": [
             {"id": 111010, "name": "Document Analysis 1",
              "due_at": "2026-02-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_upload"],
              "needs_grading_count": 0},
             {"id": 111011, "name": "Midterm Essay",
              "due_at": "2026-03-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_upload"],
              "needs_grading_count": 3},
         ]},
    ],
    90002: [
        {"id": 20110, "name": "Weekly Discussions",
         "assignments": [
             {"id": 112001, "name": "Discussion: Setting & Atmosphere",
              "due_at": "2026-02-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 112002, "name": "Discussion: Character Motivation",
              "due_at": "2026-02-21T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 112003, "name": "Discussion: The Great Gatsby — Illusion vs Reality",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 31},
         ]},
    ],
    90003: [
        {"id": 20120, "name": "Weekly Discussions",
         "assignments": [
             {"id": 113001, "name": "Week 3 Discussion: Identity & Representation",
              "due_at": "2026-02-14T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_text_entry"],
              "needs_grading_count": 0},
             {"id": 113002, "name": "Week 6 Discussion: Intersectionality in Practice",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["online_text_entry"],
              "needs_grading_count": 14},
         ]},
    ],
    90004: [
        {"id": 20130, "name": "Check-ins",
         "assignments": [
             {"id": 114001, "name": "Module 5 Reflection: Digital Footprints",
              "due_at": "2026-02-28T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
             {"id": 114002, "name": "Module 6 Reflection: Online Safety",
              "due_at": "2026-03-07T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 11},
         ]},
    ],
    71001: [
        {"id": 20140, "name": "Weekly Discussions",
         "assignments": [
             {"id": 711001, "name": "Week 14 Discussion: Legacy of the Civil War",
              "due_at": "2025-11-08T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
         ]},
    ],
    71002: [
        {"id": 20150, "name": "Weekly Discussions",
         "assignments": [
             {"id": 712001, "name": "Final Discussion: Year in Review",
              "due_at": "2025-12-06T23:59:00Z",
              "grading_type": "pass_fail", "submission_types": ["discussion_topic"],
              "needs_grading_count": 0},
         ]},
    ],
}

_HS_AIC_RUNS = [
    {
        "course_id": "90001",
        "course_name": "AP US History, Per. 2",
        "assignment_id": "111004",
        "assignment_name": "Week 6: Civil Rights Era",
        "last_run": "2026-03-10T14:22:00",
        "analyzed_count": 35,
        "smoking_gun_count": 1,
    },
    {
        "course_id": "90002",
        "course_name": "11th Grade English B",
        "assignment_id": "112003",
        "assignment_name": "Discussion: The Great Gatsby",
        "last_run": "2026-03-09T09:15:00",
        "analyzed_count": 33,
        "smoking_gun_count": 0,
    },
    {
        "course_id": "90003",
        "course_name": "Ethnic Studies (11)",
        "assignment_id": "113002",
        "assignment_name": "Week 6: Intersectionality",
        "last_run": "2026-03-08T16:45:00",
        "analyzed_count": 29,
        "smoking_gun_count": 2,
    },
]

# Trajectory assignment labels (HS)
_HS_TRAJECTORY_ASSIGNMENTS = [
    ("111001", "Week 1: Primary Sources", "2026-01-31T23:59:00Z"),
    ("111002", "Week 2: Colonialism", "2026-02-07T23:59:00Z"),
    ("111003", "Week 4: Reconstruction", "2026-02-21T23:59:00Z"),
    ("111004", "Week 6: Civil Rights Era", "2026-03-07T23:59:00Z"),
]

# Student detail context labels (HS)
_HS_DETAIL_CONTEXT = {
    "assignment_name": "Week 6 Discussion: Civil Rights Era",
    "course_id":       "90001",
}

# ── Profile routing helpers ────────────────────────────────────────────────────

def _spring_courses(profile: str) -> List[Dict]:
    return list(_HS_SPRING_COURSES if profile == "hs" else _CC_SPRING_COURSES)

def _fall_courses(profile: str) -> List[Dict]:
    return list(_HS_FALL_COURSES if profile == "hs" else _CC_FALL_COURSES)

def _assignments_map(profile: str) -> Dict[int, List[Dict]]:
    return _HS_ASSIGNMENTS if profile == "hs" else _CC_ASSIGNMENTS

def _aic_runs(profile: str) -> List[Dict]:
    return list(_HS_AIC_RUNS if profile == "hs" else _CC_AIC_RUNS)

def _trajectory_assignments(profile: str) -> List[tuple]:
    return (_HS_TRAJECTORY_ASSIGNMENTS if profile == "hs"
            else _CC_TRAJECTORY_ASSIGNMENTS)

def _detail_context(profile: str) -> Dict:
    return _HS_DETAIL_CONTEXT if profile == "hs" else _CC_DETAIL_CONTEXT

# =============================================================================
# Student roster (shared across both profiles)
# =============================================================================

_KEY_STUDENTS = [
    {"id": "S001", "name": "Maria Ndiaye",  "pattern": "esl"},
    {"id": "S002", "name": "Jordan Kim",    "pattern": "burnout"},        # severe individual case
    {"id": "S003", "name": "Alex Hernandez","pattern": "smoking_gun"},
]

# 7 students in the Week-6 cohort burnout cluster — a class-wide pattern,
# distinct from Jordan Kim's more severe individual case.
_NORMAL_NAMES_AND_PATTERNS = [
    ("Amara Osei",         "normal"),
    ("Priya Subramaniam",  "normal"),
    ("DeShawn Williams",   "normal"),
    ("Sophie Laurent",     "normal"),
    ("Kai Nakamura",       "normal"),
    ("Chloe Reyes",        "normal"),
    ("Marcus Webb",        "normal"),
    ("Fatima Al-Rashid",   "normal"),
    ("Tyler Nguyen",       "sustained_cheat"),  # ← elevated all semester
    ("Isabela Ferreira",   "normal"),
    ("Sam Kowalski",       "normal"),
    ("Aaliyah Brooks",     "exhaustion_spike"), # ← clean until Week 6
    ("Ethan Park",         "normal"),
    ("Lena Muller",        "normal"),
    ("Jaylen Carter",      "sustained_cheat"),  # ← elevated all semester
    ("Nadia Petrov",       "normal"),
    ("Diego Morales",      "normal"),
    ("Yuki Tanaka",        "normal"),
    ("Brianna Hughes",     "exhaustion_spike"), # ← clean until Week 6
    ("Connor Sullivan",    "normal"),
    ("Zara Ahmed",         "normal"),
    ("Malik Johnson",      "normal"),
    ("Elena Vasquez",      "exhaustion_spike"), # ← clean until Week 6
    ("Patrick O'Brien",    "normal"),
    ("Mei Huang",          "normal"),
    ("Devon Marshall",     "exhaustion_spike"), # ← clean until Week 6
    ("Anita Sharma",       "normal"),
    ("Lucas Blanc",        "normal"),
    ("Kayla Robinson",     "normal"),
    ("Omar Sheikh",        "normal"),
    ("Tiana Foster",       "normal"),
    ("Ryan Fitzgerald",    "normal"),
]

_ALL_STUDENTS = _KEY_STUDENTS + [
    {"id": f"S{100 + i}", "name": name, "pattern": pattern}
    for i, (name, pattern) in enumerate(_NORMAL_NAMES_AND_PATTERNS)
]  # 35 total


# =============================================================================
# Public API
# =============================================================================

def get_demo_terms(profile: str = "cc") -> List[tuple]:
    """Returns [(term_id, term_name, is_current), ...]"""
    if profile == "hs":
        return [
            (SPRING_2026, "Spring Semester 2026", True),
            (FALL_2025,   "Fall Semester 2025",   False),
        ]
    return [
        (SPRING_2026, "Spring 2026", True),
        (FALL_2025,   "Fall 2025",   False),
    ]


def get_demo_courses(term_id: int, profile: str = "cc") -> List[Dict]:
    if term_id == SPRING_2026:
        return _spring_courses(profile)
    if term_id == FALL_2025:
        return _fall_courses(profile)
    return []


def get_demo_assignment_groups(course_id: int, profile: str = "cc") -> List[Dict]:
    """Returns assignment group dicts with nested 'assignments' list."""
    return list(_assignments_map(profile).get(course_id, []))


def simulate_grading_run(
    selected: List[Dict],
    callback: Callable[[str, int, int], None],
    cancel_check: Callable[[], bool],
) -> Dict:
    """
    Simulate grading ~35 students across all selected assignments.
    callback(log_line, done, total) is called for each student.
    cancel_check() returns True if the user clicked Stop.
    Returns {"graded": n, "complete": n, "incomplete": n, "flagged": n}
    """
    rng = random.Random(7)
    students = list(_ALL_STUDENTS)
    total = len(students) * len(selected)
    done  = 0
    results = {"graded": 0, "complete": 0, "incomplete": 0, "flagged": 0}

    for assignment in selected:
        for student in students:
            if cancel_check():
                return results

            pattern = student["pattern"]
            sname   = student["name"]

            if   pattern == "burnout":          wc = rng.randint(45, 110)
            elif pattern == "sustained_cheat":  wc = rng.randint(235, 310)  # AI writes enough
            elif pattern == "exhaustion_spike": wc = rng.randint(70, 148)   # short despite AI
            elif pattern == "smoking_gun":      wc = rng.randint(210, 270)
            elif pattern == "esl":              wc = rng.randint(165, 290)
            else:                               wc = rng.randint(155, 385)

            min_wc = 200
            if pattern == "smoking_gun":
                results["flagged"] += 1
                results["graded"]  += 1
                log = f"  {sname}  [{wc} words]  >> FLAGGED (structural anomaly)"
            elif wc < min_wc:
                results["incomplete"] += 1
                results["graded"]     += 1
                log = f"  {sname}  [{wc} words]  Incomplete"
            else:
                results["complete"] += 1
                results["graded"]   += 1
                log = f"  {sname}  [{wc} words]  Complete"

            done += 1
            callback(log, done, total)
            time.sleep(rng.uniform(0.04, 0.12))

    return results


def get_demo_aic_runs(profile: str = "cc") -> List[Dict]:
    """Run summary dicts for RunBrowserSidebar."""
    return _aic_runs(profile)


def get_demo_cohort(course_id: str, assignment_id: str) -> List[Dict]:
    """Scatter-plot cohort data. Returns ~35 student dicts.
    Profile-agnostic: the RNG seed from the IDs gives consistent scatter per run."""
    rng = random.Random(
        int(str(course_id or "80001")[-4:]) + int(str(assignment_id or "101004")[-4:])
    )
    cohort = []

    for student in _ALL_STUDENTS:
        pattern = student["pattern"]

        if pattern == "esl":
            raw  = round(rng.uniform(3.8, 5.2), 2)
            adj  = round(raw * 0.35, 2)
            hp   = round(rng.uniform(58, 72), 1)
            wc   = rng.randint(210, 290)
            concern = "low"
            sg   = False

        elif pattern == "burnout":
            raw  = round(rng.uniform(1.8, 2.8), 2)
            adj  = raw
            hp   = round(rng.uniform(62, 78), 1)
            wc   = rng.randint(85, 130)
            concern = "medium"
            sg   = False

        elif pattern == "sustained_cheat":
            # AI use all semester — word count stays NORMAL because AI writes enough.
            # Suspicious score high but with natural variation (not a flat line).
            raw  = round(rng.uniform(3.5, 5.5), 2)
            adj  = raw
            hp   = round(rng.uniform(32, 52), 1)
            wc   = rng.randint(260, 320)   # normal — AI produces sufficient text
            concern = "medium"
            sg   = False

        elif pattern == "exhaustion_spike":
            # Hit a wall at Week 6 — first-time AI use AND short post.
            # Word count drops alongside the suspicion spike.
            raw  = round(rng.uniform(2.2, 3.8), 2)
            adj  = raw
            hp   = round(rng.uniform(50, 68), 1)
            wc   = rng.randint(95, 148)   # short — overwhelmed, didn't write enough
            concern = "medium"
            sg   = False

        elif pattern == "smoking_gun":
            raw  = round(rng.uniform(8.5, 10.0), 2)
            adj  = raw
            hp   = round(rng.uniform(18, 32), 1)
            wc   = rng.randint(220, 310)
            concern = "high"
            sg   = True

        else:
            raw  = round(rng.uniform(0.2, 2.1), 2)
            adj  = raw
            hp   = round(rng.uniform(68, 95), 1)
            wc   = rng.randint(200, 420)
            concern = "none"
            sg   = False

        cohort.append({
            "student_id":                student["id"],
            "student_name":              student["name"],
            "human_presence_confidence": hp,
            "suspicious_score":          raw,
            "adjusted_suspicious_score": adj,
            "concern_level":             concern,
            "smoking_gun":               sg,
            "word_count":                wc,
        })

    return cohort


def get_demo_student_detail(student_id: str, assignment_id: str,
                             profile: str = "cc") -> Dict:
    """Full detail dict for StudentDetailView.load()."""
    student = next((s for s in _ALL_STUDENTS if s["id"] == student_id), None)
    if not student:
        return {}

    pattern = student["pattern"]
    sname   = student["name"]
    ctx     = _detail_context(profile)
    base = {
        "student_id":     student_id,
        "student_name":   sname,
        "assignment_id":  assignment_id,
        "assignment_name": ctx["assignment_name"],
        "course_id":      ctx["course_id"],
    }

    if pattern == "esl":
        return {**base,
            "submitted_at":          "2026-03-07T21:34:00",
            "last_analyzed_at":      "2026-03-10T14:22:00",
            "concern_level":         "low",
            "suspicious_score":      4.6,
            "adjusted_suspicious_score": 1.6,
            "authenticity_score":    3.2,
            "human_presence_confidence": 64.5,
            "word_count":            247,
            "smoking_gun":           False,
            "smoking_gun_details":   [],
            "marker_counts": {
                "inflated_vocabulary":          3,
                "ai_transitions":               2,
                "passive_construction_density": 4,
                "missing_personal_voice":       1,
                "structural_uniformity":        2,
            },
            "context_adjustments": [
                "ESL pattern detected — suspicious score reduced 65%",
                "Passive construction rate consistent with second-language writing",
                "Vocabulary choices reflect translation patterns, not AI generation",
            ],
            "conversation_starters": [
                "Your post shows real engagement with the material. Can you say more "
                "about what this topic means to you personally?",
                "I noticed some interesting word choices — were you translating from "
                "another language as you wrote?",
            ],
            "verification_questions": [
                "What part of this week's reading connected most to your own experience?",
                "How would you explain the main idea to someone who hasn't read this?",
            ],
        }

    if pattern == "sustained_cheat":
        _s_rng = random.Random(hash(student_id) & 0xFFFFFFFF)
        wc  = _s_rng.randint(265, 320)   # normal — AI produces sufficient length
        raw = round(_s_rng.uniform(3.5, 5.5), 2)
        return {**base,
            "submitted_at":          "2026-03-07T20:44:00",   # reasonable time — no burnout
            "last_analyzed_at":      "2026-03-10T14:22:00",
            "concern_level":         "medium",
            "suspicious_score":      raw,
            "adjusted_suspicious_score": raw,
            "authenticity_score":    round(_s_rng.uniform(2.0, 3.5), 1),
            "human_presence_confidence": round(_s_rng.uniform(32.0, 52.0), 1),
            "word_count":            wc,
            "smoking_gun":           False,
            "smoking_gun_details":   [],
            "marker_counts": {
                "inflated_vocabulary":          _s_rng.randint(4, 6),
                "ai_transitions":               _s_rng.randint(3, 5),
                "passive_construction_density": _s_rng.randint(4, 6),
                "missing_personal_voice":       _s_rng.randint(5, 7),
                "structural_uniformity":        _s_rng.randint(4, 6),
            },
            "context_adjustments": [
                "AI-assistance markers elevated across all 4 submissions — consistent pattern, "
                "not a stress response",
                f"Word count is normal ({wc} words) and submitted at a reasonable time — "
                "this student isn't struggling, they're outsourcing",
                "Suspicious score varies week to week but never drops below elevated range",
            ],
            "conversation_starters": [
                "I want to talk about how you've been approaching these discussions. "
                "Your posts are consistently well-structured — can you walk me through your process?",
                "I'm not trying to catch you out. I just want to understand whether the work "
                "reflects your thinking, because I'd like to know what you actually understand.",
            ],
            "verification_questions": [
                "Can you tell me about one specific idea from this week's reading in your own words?",
                "What would you add to this post if you were writing it right now, in front of me?",
                "What part of this topic do you find genuinely interesting or confusing?",
            ],
        }

    if pattern == "exhaustion_spike":
        _s_rng = random.Random(hash(student_id) & 0xFFFFFFFF)
        wc  = _s_rng.randint(95, 148)
        raw = round(_s_rng.uniform(2.2, 3.8), 2)
        return {**base,
            "submitted_at":          "2026-03-08T01:55:00",
            "last_analyzed_at":      "2026-03-10T14:22:00",
            "concern_level":         "medium",
            "suspicious_score":      raw,
            "adjusted_suspicious_score": raw,
            "authenticity_score":    round(_s_rng.uniform(3.5, 5.5), 1),
            "human_presence_confidence": round(_s_rng.uniform(50.0, 68.0), 1),
            "word_count":            wc,
            "smoking_gun":           False,
            "smoking_gun_details":   [],
            "marker_counts": {
                "inflated_vocabulary":          _s_rng.randint(2, 4),
                "ai_transitions":               _s_rng.randint(1, 3),
                "passive_construction_density": _s_rng.randint(2, 4),
                "missing_personal_voice":       _s_rng.randint(3, 5),
                "structural_uniformity":        _s_rng.randint(2, 3),
            },
            "context_adjustments": [
                "Integrity markers spiked at Week 6 — this student's earlier work was clean",
                "Burnout and first-time academic integrity concerns often co-occur: "
                "students who hit a wall sometimes reach for a shortcut they've never used before",
                f"Short submission ({wc} words), submitted after midnight — 4 other students "
                "show the same first-time spike this week",
            ],
            "conversation_starters": [
                "Your earlier posts this semester were really strong — and this week felt "
                "different. What's been going on?",
                "I'm not here to get anyone in trouble. I just want to check in. "
                "It looks like Week 6 was hard for a lot of people.",
                "This post reads a little differently from your usual voice. "
                "Can you talk me through how you wrote it?",
            ],
            "verification_questions": [
                "What part of this week's topic genuinely interested you?",
                "What would you add to this post if you had more time?",
                "Is there anything going on that's made it harder to focus lately?",
            ],
        }

    if pattern == "burnout":
        return {**base,
            "submitted_at":          "2026-03-08T02:17:00",
            "last_analyzed_at":      "2026-03-10T14:22:00",
            "concern_level":         "medium",
            "suspicious_score":      2.3,
            "adjusted_suspicious_score": 2.3,
            "authenticity_score":    4.8,
            "human_presence_confidence": 71.2,
            "word_count":            97,
            "smoking_gun":           False,
            "smoking_gun_details":   [],
            "marker_counts": {
                "inflated_vocabulary":          0,
                "ai_transitions":               0,
                "passive_construction_density": 1,
                "missing_personal_voice":       2,
                "structural_uniformity":        1,
            },
            "context_adjustments": [
                "Possible burnout signal: word count declining across last 4 submissions",
                "Submission time: 3 of last 4 posts submitted after midnight",
                "Authenticity score is HIGH — writing reads as genuinely personal, but brief",
            ],
            "conversation_starters": [
                "I noticed your posts have been shorter lately, and this one came in at 2am. "
                "How are you doing this semester?",
                "Your writing sounds like you had something to say but ran out of energy. "
                "Is there anything I can do to help?",
            ],
            "verification_questions": [
                "What's been taking up most of your energy lately?",
                "Is there anything I can adjust to make this class more manageable?",
            ],
        }

    if pattern == "smoking_gun":
        return {**base,
            "submitted_at":          "2026-03-07T19:55:00",
            "last_analyzed_at":      "2026-03-10T14:22:00",
            "concern_level":         "high",
            "suspicious_score":      9.1,
            "adjusted_suspicious_score": 9.1,
            "authenticity_score":    0.4,
            "human_presence_confidence": 23.8,
            "word_count":            264,
            "smoking_gun":           True,
            "smoking_gun_details": [
                "Raw HTML tags in submission body (<br>, <p>, <span style=>)",
                "Clipboard paste artifact: 246-word block with no paragraph breaks",
                "Zero post-submission edits — typical paste-and-submit pattern",
                "No Canvas activity in the 10 minutes before submission",
            ],
            "marker_counts": {
                "inflated_vocabulary":          6,
                "ai_transitions":               5,
                "passive_construction_density": 7,
                "missing_personal_voice":       8,
                "structural_uniformity":        7,
                "raw_html_paste":               1,
            },
            "context_adjustments": [],
            "conversation_starters": [
                "I'd like to talk about your most recent post. Can you walk me through how "
                "you approached this assignment?",
                "What were you thinking about when you wrote this?",
                "What sources or ideas did you draw on?",
            ],
            "verification_questions": [
                "Can you explain in your own words what the author argues?",
                "What part of this topic did you find most challenging?",
                "If you were explaining this to a friend, what would you say?",
            ],
        }

    # Generic student — low/no concern
    rng = random.Random(hash(student_id) & 0xFFFFFFFF)
    wc  = rng.randint(200, 400)
    return {**base,
        "submitted_at":          "2026-03-07T18:30:00",
        "last_analyzed_at":      "2026-03-10T14:22:00",
        "concern_level":         "none",
        "suspicious_score":      round(rng.uniform(0.1, 1.5), 2),
        "adjusted_suspicious_score": round(rng.uniform(0.1, 1.5), 2),
        "authenticity_score":    round(rng.uniform(5.0, 9.5), 1),
        "human_presence_confidence": round(rng.uniform(72.0, 95.0), 1),
        "word_count":            wc,
        "smoking_gun":           False,
        "smoking_gun_details":   [],
        "marker_counts": {
            "inflated_vocabulary":          rng.randint(0, 1),
            "ai_transitions":               0,
            "passive_construction_density": rng.randint(0, 1),
            "missing_personal_voice":       0,
            "structural_uniformity":        0,
        },
        "context_adjustments": [],
        "conversation_starters": [
            "Nice work on this week's discussion. "
            "What aspect of the reading resonated most with you?"
        ],
        "verification_questions": [],
    }


def get_demo_trajectory(student_id: str, course_id: str,
                         profile: str = "cc") -> List[Dict]:
    """Per-assignment sparkline data over the semester."""
    student = next((s for s in _ALL_STUDENTS if s["id"] == student_id), None)
    if not student:
        return []

    pattern      = student["pattern"]
    rng          = random.Random(hash(student_id) & 0xFFFFFFFF)
    assignments  = _trajectory_assignments(profile)
    submit_times = [
        "2026-01-31T20:15:00", "2026-02-07T22:48:00",
        "2026-02-21T01:32:00", "2026-03-08T02:17:00",
    ]

    rows = []
    for i, (aid, aname, due) in enumerate(assignments):
        if pattern == "burnout":
            # Severe individual case — steep continuous decline
            wc    = [280, 210, 145, 97][i]
            susp  = [1.2, 1.8, 2.1, 2.3][i]
            auth  = [7.2, 6.1, 5.4, 4.8][i]
            hp    = [84.0, 78.0, 74.0, 71.2][i]
            subm  = submit_times[i]
            level = "medium"
            adj   = susp

        elif pattern == "sustained_cheat":
            # AI use all semester — word count stays normal because AI writes enough.
            # Suspicion score varies (not a flat line) but never drops below elevated range.
            # Submission times are unremarkable — no burnout signal, just outsourcing.
            wc    = [288, 302, 275, 294][i]   # stable, healthy word count all semester
            susp  = [3.8, 3.1, 4.3, 3.9][i]  # varies but stays consistently elevated
            auth  = [2.8, 3.2, 2.5, 2.9][i]
            hp    = [44.0, 48.0, 40.0, 46.0][i]
            subm  = [
                "2026-01-31T18:55:00",   # reasonable times — no fatigue signal
                "2026-02-07T19:30:00",
                "2026-02-21T20:10:00",
                "2026-03-07T20:44:00",
            ][i]
            level = "medium"   # concern all semester, not just at Week 6
            adj   = susp

        elif pattern == "exhaustion_spike":
            # Clean work all semester, then hockey-stick at Week 6 — first-time shortcut.
            # Suspicious score low → low → low → sharp jump. That's the visual.
            wc    = [270, 255, 230, 118][i]
            susp  = [0.6, 0.8, 1.1, 3.5][i]
            auth  = [8.4, 8.1, 7.6, 4.2][i]
            hp    = [89.0, 87.0, 85.0, 57.0][i]
            subm  = [
                "2026-01-31T19:45:00",
                "2026-02-07T20:30:00",
                "2026-02-21T21:50:00",
                "2026-03-08T01:55:00",   # late AND first-time spike
            ][i]
            level = "none" if i < 3 else "medium"   # clean until Week 6
            adj   = susp

        elif pattern == "esl":
            wc    = rng.randint(220, 290)
            susp  = round(rng.uniform(3.5, 5.2), 2)
            adj   = round(susp * 0.35, 2)
            auth  = round(rng.uniform(3.0, 4.0), 1)
            hp    = round(rng.uniform(60, 70), 1)
            level = "low"
            subm  = f"2026-{['01-31','02-07','02-21','03-07'][i]}T21:30:00"

        elif pattern == "smoking_gun":
            wc    = rng.randint(200, 310)
            susp  = round(rng.uniform(7.0, 10.0), 2)
            adj   = susp
            auth  = round(rng.uniform(0.2, 1.5), 1)
            hp    = round(rng.uniform(18, 35), 1)
            level = "high"
            subm  = f"2026-{['01-31','02-07','02-21','03-07'][i]}T19:55:00"

        else:
            wc    = rng.randint(200, 400)
            susp  = round(rng.uniform(0.1, 1.5), 2)
            adj   = susp
            auth  = round(rng.uniform(6.0, 9.5), 1)
            hp    = round(rng.uniform(75, 95), 1)
            level = "none"
            subm  = f"2026-{['01-31','02-07','02-21','03-07'][i]}T18:00:00"

        rows.append({
            "assignment_id":             aid,
            "assignment_name":           aname,
            "due_at":                    due,
            "submitted_at":              subm,
            "suspicious_score":          susp,
            "adjusted_suspicious_score": adj,
            "authenticity_score":        auth,
            "human_presence_confidence": hp,
            "word_count":                wc,
            "concern_level":             level,
        })

    return rows
