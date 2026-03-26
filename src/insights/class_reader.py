"""
Class Reading — Synthesis-First Architecture.

Reads the class as a community BEFORE individual student evaluation.
This makes relational harms (tone policing, essentializing in context)
visible — they are invisible when students are read in isolation.

The class reading is injected into per-student coding and concern
detection prompts, giving the model the relational context it needs
to see how one student's framing affects how other students' voices land.

Design principle: atomized evaluation reproduces the isolation that makes
relational harms invisible. The system must read the class as an
interdependent community, not a collection of individual performances.
"""

import logging
import re
from typing import Dict, List, Optional, Set, Tuple

from insights.llm_backend import BackendConfig, send_text
from insights.prompts import (
    CLASS_READING_MERGE_PROMPT,
    CLASS_READING_PROMPT,
    CLASS_READING_SMALL_PROMPT,
    CLASS_READING_SYSTEM_ADDENDUM,
    SYSTEM_PROMPT,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Assignment type detection — determines if class reading is appropriate
# ---------------------------------------------------------------------------

# Keywords in assignment name/description that indicate NON-reflective work
# where students aren't writing in their own voice.
_NON_REFLECTIVE_PATTERNS = re.compile(
    r"\b(lab\s*report|problem\s*set|p\s*-?\s*set|homework\s*\d|"
    r"worksheet|quiz|exam|test\s*\d|midterm|final\s*exam|"
    r"multiple\s*choice|fill[\s-]*in[\s-]*the[\s-]*blank|"
    r"coding\s*(assignment|project|exercise|lab)|"
    r"programming\s*(assignment|project|exercise|lab)|"
    r"math\s*homework|calculation|compute|solve\b.*equation|"
    r"data\s*analysis\s*report|technical\s*report|"
    r"circuit\s*diagram|proof|derivation)\b",
    re.IGNORECASE,
)

# Keywords that indicate REFLECTIVE work — override non-reflective signals
# if both are present (e.g., "lab report with reflection section")
_REFLECTIVE_PATTERNS = re.compile(
    r"\b(reflect|reflection|response\s*paper|personal\s*essay|"
    r"journal|free[\s-]*write|discussion\s*(post|board|response)|"
    r"your\s*(thoughts|opinion|perspective|experience|reaction)|"
    r"what\s*do\s*you\s*think|how\s*did\s*(this|you)|"
    r"in\s*your\s*own\s*words|share\s*your|"
    r"reading\s*response|critical\s*response|"
    r"narrative|memoir|personal\s*narrative|"
    r"identity|community|culture|lived\s*experience)\b",
    re.IGNORECASE,
)


def is_reflective_assignment(
    assignment_name: str, assignment_description: str = ""
) -> bool:
    """Determine if an assignment involves reflective/personal student writing.

    Returns True if the class reading is appropriate (reflective, discussion,
    personal writing). Returns False for lab reports, problem sets, coding
    assignments, etc. where students aren't writing in their own voice.

    When in doubt, defaults to True — it's better to generate a class reading
    that turns out generic than to skip one that would have surfaced relational
    dynamics.
    """
    combined = f"{assignment_name} {assignment_description}"

    has_reflective = bool(_REFLECTIVE_PATTERNS.search(combined))
    has_non_reflective = bool(_NON_REFLECTIVE_PATTERNS.search(combined))

    # Reflective signals override non-reflective (e.g., "lab report reflection")
    if has_reflective:
        return True

    # Clear non-reflective signal with no reflective override
    if has_non_reflective:
        return False

    # Default: assume reflective — better to read than to miss
    return True

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_class_reading(
    *,
    submissions: Dict[str, str],
    submission_names: Dict[str, str],
    assignment_prompt: str,
    course_name: str = "",
    backend: BackendConfig,
    max_words_per_submission: int = 150,
    teacher_context: str = "",
    cluster_assignments: Optional[Dict[str, int]] = None,
    quick_summaries: Optional[Dict[str, object]] = None,
    ai_flagged_ids: Optional[Set[str]] = None,
) -> str:
    """Generate a class-level reading from all student submissions.

    Args:
        submissions: Mapping of student_id → submission text.
        submission_names: Mapping of student_id → student name.
        assignment_prompt: The assignment description.
        course_name: Course name for context.
        backend: LLM backend to use.
        max_words_per_submission: Max words to include per essay.
            Short submissions (under this limit) are included in full.
        teacher_context: Optional teacher notes about the assignment.
        cluster_assignments: Optional mapping of student_id → cluster_id
            from Quick Analysis embedding clusters.  Used for hierarchical
            group reading when the class is large.
        quick_summaries: Optional mapping of student_id → PerSubmissionSummary
            from Quick Analysis.  When present, keyword_hits are used to guide
            excerpt selection for long submissions.
        ai_flagged_ids: Optional set of student_ids whose submissions are
            likely AI-generated (from AIC).  These are annotated in the
            submissions block so the class reading doesn't center AI voice
            over authentic student voices.

    Returns:
        Free-text class reading (asset / threshold / connection).
        Empty string on failure (caller should fall back to stats context).
    """
    if not submissions:
        return ""

    n = len(submissions)
    system = SYSTEM_PROMPT.rstrip("\n") + "\n\n" + CLASS_READING_SYSTEM_ADDENDUM

    # Build quick_analysis_data: student_id → per-submission dict
    # Includes keyword_hits for signal-guided extraction AND
    # protected flag for linguistic justice excerpt boosting
    quick_analysis_data: Optional[Dict[str, dict]] = None
    if quick_summaries:
        quick_analysis_data = {}
        for sid, summary in quick_summaries.items():
            entry: dict = {}
            # Keyword hits for signal-guided extraction
            if hasattr(summary, "keyword_hits"):
                entry["keyword_hits"] = summary.keyword_hits
            elif isinstance(summary, dict) and "keyword_hits" in summary:
                entry["keyword_hits"] = summary["keyword_hits"]
            # Linguistic repertoire: boost word budget for protected students
            # (AAVE, multilingual, neurodivergent, communal voice)
            _rep = getattr(summary, "linguistic_repertoire", None)
            if _rep:
                features = getattr(_rep, "features", [])
                entry["has_protected_features"] = any(
                    getattr(f, "protected", False) for f in features
                ) if features else False
            quick_analysis_data[sid] = entry

    _ai_flags = ai_flagged_ids or set()

    # For small classes (<=20), do a single-pass reading.
    # For larger classes, use hierarchical group reading if clusters available.
    if n <= 20 or cluster_assignments is None:
        return _single_pass_reading(
            submissions=submissions,
            submission_names=submission_names,
            assignment_prompt=assignment_prompt,
            course_name=course_name,
            backend=backend,
            max_words=max_words_per_submission,
            teacher_context=teacher_context,
            system=system,
            quick_analysis_data=quick_analysis_data,
            ai_flagged_ids=_ai_flags,
        )

    return _hierarchical_reading(
        submissions=submissions,
        submission_names=submission_names,
        assignment_prompt=assignment_prompt,
        course_name=course_name,
        backend=backend,
        max_words=max_words_per_submission,
        teacher_context=teacher_context,
        system=system,
        cluster_assignments=cluster_assignments,
        quick_analysis_data=quick_analysis_data,
        ai_flagged_ids=_ai_flags,
    )


# ---------------------------------------------------------------------------
# Single-pass reading (small classes or fallback)
# ---------------------------------------------------------------------------


def _single_pass_reading(
    *,
    submissions: Dict[str, str],
    submission_names: Dict[str, str],
    assignment_prompt: str,
    course_name: str,
    backend: BackendConfig,
    max_words: int,
    teacher_context: str,
    system: str,
    quick_analysis_data: Optional[Dict[str, dict]] = None,
    ai_flagged_ids: Optional[Set[str]] = None,
) -> str:
    """Read all submissions in one LLM call."""
    block = _build_submissions_block(
        submissions, submission_names, max_words, quick_analysis_data,
        ai_flagged_ids=ai_flagged_ids,
    )

    tc_line = f"Teacher's context: {teacher_context}" if teacher_context else ""

    # Use small-class prompt for classes under 8 students —
    # focuses on individual depth rather than group dynamics
    template = CLASS_READING_SMALL_PROMPT if len(submissions) < 8 else CLASS_READING_PROMPT
    prompt = template.format(
        assignment_prompt=assignment_prompt,
        course_name=course_name,
        teacher_context=tc_line,
        submissions_block=block,
    )

    word_count = len(prompt.split())
    log.info(
        "Class reading: %d students, ~%d prompt words, single pass",
        len(submissions),
        word_count,
    )

    try:
        reading = send_text(backend, prompt, system, max_tokens=1200)
        log.info("Class reading complete: %d words", len(reading.split()))
        return reading.strip()
    except Exception as e:
        log.warning("Class reading failed (non-fatal): %s", e)
        return ""


# ---------------------------------------------------------------------------
# Hierarchical group reading (large classes)
# ---------------------------------------------------------------------------


def _hierarchical_reading(
    *,
    submissions: Dict[str, str],
    submission_names: Dict[str, str],
    assignment_prompt: str,
    course_name: str,
    backend: BackendConfig,
    max_words: int,
    teacher_context: str,
    system: str,
    cluster_assignments: Dict[str, int],
    quick_analysis_data: Optional[Dict[str, dict]] = None,
    ai_flagged_ids: Optional[Set[str]] = None,
) -> str:
    """Read class in groups (by embedding cluster), then merge."""
    groups = _group_by_cluster(
        submissions, submission_names, cluster_assignments
    )
    log.info(
        "Hierarchical reading: %d students in %d groups",
        len(submissions),
        len(groups),
    )

    # If clustering produced only 1 group, just do single-pass
    if len(groups) <= 1:
        return _single_pass_reading(
            submissions=submissions,
            submission_names=submission_names,
            assignment_prompt=assignment_prompt,
            course_name=course_name,
            backend=backend,
            max_words=max_words,
            teacher_context=teacher_context,
            system=system,
            quick_analysis_data=quick_analysis_data,
            ai_flagged_ids=ai_flagged_ids,
        )

    # Read each group — use more words per student since groups are smaller
    group_max_words = min(300, max_words * 2)
    group_readings: List[str] = []

    for i, (cluster_id, members) in enumerate(groups):
        group_subs = {sid: submissions[sid] for sid, _ in members}
        group_names = {sid: name for sid, name in members}
        block = _build_submissions_block(
            group_subs, group_names, group_max_words, quick_analysis_data,
            ai_flagged_ids=ai_flagged_ids,
        )

        tc_line = f"Teacher's context: {teacher_context}" if teacher_context else ""
        prompt = CLASS_READING_PROMPT.format(
            assignment_prompt=assignment_prompt,
            course_name=course_name,
            teacher_context=tc_line,
            submissions_block=block,
        )

        try:
            reading = send_text(backend, prompt, system, max_tokens=800)
            group_readings.append(
                f"--- Group {i + 1} ({len(members)} students) ---\n{reading.strip()}"
            )
            log.info(
                "  Group %d/%d (%d students): %d words",
                i + 1,
                len(groups),
                len(members),
                len(reading.split()),
            )
        except Exception as e:
            log.warning("Group %d reading failed: %s", i + 1, e)

    if not group_readings:
        log.warning("All group readings failed, falling back to single pass")
        return _single_pass_reading(
            submissions=submissions,
            submission_names=submission_names,
            assignment_prompt=assignment_prompt,
            course_name=course_name,
            backend=backend,
            max_words=max_words,
            teacher_context=teacher_context,
            system=system,
            quick_analysis_data=quick_analysis_data,
            ai_flagged_ids=ai_flagged_ids,
        )

    # Merge group readings into unified class reading
    merge_prompt = CLASS_READING_MERGE_PROMPT.format(
        group_readings="\n\n".join(group_readings)
    )
    try:
        merged = send_text(backend, merge_prompt, system, max_tokens=1200)
        log.info("Merged class reading: %d words", len(merged.split()))
        return merged.strip()
    except Exception as e:
        log.warning("Merge failed, concatenating group readings: %s", e)
        return "\n\n".join(group_readings)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_submissions_block(
    submissions: Dict[str, str],
    names: Dict[str, str],
    max_words: int,
    quick_analysis_data: Optional[Dict[str, dict]] = None,
    ai_flagged_ids: Optional[Set[str]] = None,
) -> str:
    """Build the submissions block for the class reading prompt.

    Short submissions are included in full.  Longer submissions are
    excerpted to *max_words* using one of two strategies:

    - Signal-guided (preferred): when quick_analysis_data is available for
      a student and their keyword_hits are non-empty, the passage with the
      highest keyword concentration is found and max_words of text are
      extracted centered on that passage.
    - Beginning + end (fallback): first half + last half of the word budget,
      so the student's conclusion and strongest points aren't lost.

    AI-flagged submissions are annotated so the class reading doesn't
    center AI-generated voice over authentic student voices.
    """
    _ai_flags = ai_flagged_ids or set()
    parts: List[str] = []
    for sid, text in submissions.items():
        name = names.get(sid, f"Student {sid}")
        # Strip HTML tags for cleaner reading
        clean = _strip_html(text)
        words = clean.split()
        word_count = len(words)

        # Boost word budget for students with protected linguistic features
        # (AAVE, multilingual, neurodivergent) — their voice deserves full
        # representation in the class reading, not truncated excerpts
        effective_max = max_words
        if quick_analysis_data and sid in quick_analysis_data:
            if quick_analysis_data[sid].get("has_protected_features"):
                effective_max = min(word_count, int(max_words * 2))

        if word_count <= effective_max:
            # Short submission or protected student — include in full
            excerpt = clean
        else:
            # Try signal-guided extraction first
            excerpt = ""
            if quick_analysis_data and sid in quick_analysis_data:
                kw_hits = quick_analysis_data[sid].get("keyword_hits", {})
                excerpt = _find_highest_signal_passage(clean, kw_hits, effective_max)

            if not excerpt:
                # Beginning + end fallback: take first half and last half
                # of the budget, so conclusions aren't lost
                half = effective_max // 2
                beginning = " ".join(words[:half])
                ending = " ".join(words[-half:])
                excerpt = f"{beginning} [...] {ending}"

        # Flag brief-but-present submissions so the LLM doesn't overlook them
        brief_note = ""
        if 10 <= word_count <= 60:
            brief_note = " [NOTE: Brief submission — read carefully, do not overlook]"

        # Flag AI-generated submissions so the class reading doesn't center
        # AI voice over authentic student voices
        ai_note = ""
        if sid in _ai_flags:
            ai_note = (
                " [NOTE: This submission shows signals consistent with AI "
                "generation. Read with awareness that this may not represent "
                "the student's authentic voice. Do not let its polish set "
                "the standard against which other voices are measured.]"
            )

        parts.append(f"### {name} ({word_count} words){brief_note}{ai_note}")
        parts.append(excerpt)
        parts.append("")

    return "\n".join(parts)


def _find_highest_signal_passage(
    text: str, keyword_hits: dict, max_words: int
) -> str:
    """Find the passage centered on the highest concentration of keyword hits.

    Splits the text into rough sentences on '.', scores each sentence by how
    many unique keywords appear in it, then extracts max_words of text centered
    on the highest-scoring sentence.  Adjacent sentences are pulled in
    (earlier and later alternately) until the word budget is reached.

    Returns an empty string if keyword_hits is empty or no keywords are found
    in the text (caller should fall back to beginning+end strategy).
    """
    if not keyword_hits:
        return ""

    keywords = {k.lower() for k in keyword_hits.keys()}
    sentences = text.split(".")

    best_idx = 0
    best_score = 0
    for i, sent in enumerate(sentences):
        words = set(sent.lower().split())
        score = len(words & keywords)
        if score > best_score:
            best_score = score
            best_idx = i

    if best_score == 0:
        return ""  # no keywords found anywhere — fall back

    # Expand outward from best_idx until we reach the word budget
    included = [best_idx]
    lo = best_idx - 1
    hi = best_idx + 1
    word_count = len(sentences[best_idx].split())

    while word_count < max_words and (lo >= 0 or hi < len(sentences)):
        # Alternate: try the earlier sentence first, then the later one
        added = False
        if lo >= 0:
            candidate = sentences[lo].split()
            if word_count + len(candidate) <= max_words:
                included.insert(0, lo)
                word_count += len(candidate)
                lo -= 1
                added = True
        if hi < len(sentences):
            candidate = sentences[hi].split()
            if word_count + len(candidate) <= max_words:
                included.append(hi)
                word_count += len(candidate)
                hi += 1
                added = True
        if not added:
            break  # neither neighbor fits within budget — stop

    # Re-join in original document order, restoring the '.' separator
    passage = ".".join(sentences[i] for i in sorted(included)).strip()

    # Annotate with ellipsis markers if we didn't start / end the document
    prefix = "[...] " if sorted(included)[0] > 0 else ""
    suffix = " [...]" if sorted(included)[-1] < len(sentences) - 1 else ""
    return f"{prefix}{passage}{suffix}"


def _strip_html(text: str) -> str:
    """Remove HTML tags from submission text."""
    import re

    return re.sub(r"<[^>]+>", " ", text).strip()


def _group_by_cluster(
    submissions: Dict[str, str],
    names: Dict[str, str],
    cluster_assignments: Dict[str, int],
    max_group_size: int = 8,
) -> List[Tuple[int, List[Tuple[str, str]]]]:
    """Group students by embedding cluster for hierarchical reading.

    Returns list of (cluster_id, [(sid, name), ...]) tuples.
    Groups larger than max_group_size are split.
    Students without cluster assignments go in cluster -1.
    """
    clusters: Dict[int, List[Tuple[str, str]]] = {}
    for sid in submissions:
        cid = cluster_assignments.get(sid, -1)
        name = names.get(sid, f"Student {sid}")
        clusters.setdefault(cid, []).append((sid, name))

    # Split oversized groups
    result: List[Tuple[int, List[Tuple[str, str]]]] = []
    for cid, members in sorted(clusters.items()):
        for i in range(0, len(members), max_group_size):
            result.append((cid, members[i : i + max_group_size]))

    return result
