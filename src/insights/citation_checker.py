"""
Citation extraction and class-level source analysis.

Extracts citations from student submissions (URLs, DOIs, author-year
references, reading references, quoted titles) and builds a class-level
"sources cited" view showing what the class is reading and engaging with.

Design principles:
  - Only produces output when citations are actually found
  - Verification runs automatically but asynchronously (non-blocking)
  - Verification only checks URL/DOI existence via HEAD request — it never
    judges whether a source "supports the claim"
  - Paywalled, non-indexed, and non-English sources will appear as
    unverified even if they are real — teachers should know this
  - The "sources cited" view is pedagogical: it shows the teacher what
    the class is engaging with, NOT a policing tool
  - Toggleable by assignment template (research papers vs discussion posts)

Equity note on verification:
  A citation marked "unverified" means the URL/DOI didn't respond with
  a success code — NOT that the source is fake.  Community newspapers,
  local publications, non-English sources, paywalled journals, and oral
  sources cited via secondary reference will all appear unverified.
  This information is for teacher awareness only; it must never be used
  to penalize or flag a student automatically.
"""

import logging
import re
import threading
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Citation patterns
# ---------------------------------------------------------------------------

# URLs (http/https)
_URL_PATTERN = re.compile(r"https?://[^\s<>\")\]]+")

# DOIs (10.NNNN/...)
_DOI_PATTERN = re.compile(r"\b(10\.\d{4,}/[^\s<>\")\],;]+)")

# APA-style parenthetical: (Author, 2024) or (Author & Author, 2024)
_APA_CITE = re.compile(
    r"\(([A-Z][a-z]+(?:\s+(?:&|and|et\s+al\.?)\s+[A-Z][a-z]+)*)"
    r",?\s+(\d{4})\)"
)

# Inline author reference: Author (2024) argues...
_INLINE_AUTHOR = re.compile(
    r"([A-Z][a-z]{2,}(?:\s+(?:&|and)\s+[A-Z][a-z]{2,})?)\s+\((\d{4})\)"
)

# "According to [source]..." patterns
_ACCORDING_TO = re.compile(
    r"(?:according\s+to|as\s+(?:\w+\s+){0,2}"
    r"(?:argues?|states?|claims?|writes?|notes?|explains?|describes?))"
    r"\s+(.{3,60}?)(?:[,.]|\s+that\b)",
    re.IGNORECASE,
)

# Generic reading reference: "the reading says..."
_READING_REF = re.compile(
    r"(?:the\s+)?(?:reading|text|article|book|chapter|author|source|document)"
    r"\s+(?:says?|states?|argues?|mentions?|discusses?|explains?|describes?"
    r"|shows?|points?\s+out)",
    re.IGNORECASE,
)

# Quoted titles: "Title of Work" or \u201cTitle of Work\u201d
# Three separate patterns for straight quotes, left/right smart quotes,
# and single quotes — prevents cross-boundary matching.
_QUOTED_TITLE = re.compile(
    r'"([^"]{5,80})"|'                            # straight double quotes
    r"\u201c([^\u201c\u201d]{5,80})\u201d|"       # smart double quotes (left…right)
    r"\u2018([^\u2018\u2019]{5,80})\u2019"        # smart single quotes (left…right)
)

# Canvas/LMS URLs to skip (these are submission infrastructure, not citations)
_SKIP_DOMAINS_EXACT = frozenset({
    "localhost",
    "127.0.0.1",
})

# Suffix matches: any domain ending with these is skipped
# (catches myschool.instructure.com, canvas.instructure.com, etc.)
_SKIP_DOMAIN_SUFFIXES = (
    ".instructure.com",
    "instructure.com",
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    """A single extracted citation."""

    citation_type: str
    # "url", "doi", "author_year", "reading_reference",
    # "quoted_title", "generic_reference"
    raw_text: str  # the matched text
    normalized: str  # cleaned/normalized form
    student_id: str = ""
    student_name: str = ""
    # Verification (only populated if verify_citations() is called)
    verified: Optional[bool] = None  # None = not checked
    verification_note: str = ""


@dataclass
class SourceSummary:
    """One source referenced by the class."""

    source: str  # normalized source identifier
    citation_type: str
    student_ids: List[str] = field(default_factory=list)
    student_names: List[str] = field(default_factory=list)
    count: int = 0  # total references across all students


@dataclass
class CitationReport:
    """Full citation analysis for one class.

    When has_citations is False, the rest of the fields are empty —
    the system produces no output when there's nothing to report.
    """

    citations: List[Citation] = field(default_factory=list)
    has_citations: bool = False
    source_count: int = 0  # unique sources

    # Class-level aggregation
    sources_summary: List[SourceSummary] = field(default_factory=list)
    most_cited: List[Tuple[str, int]] = field(default_factory=list)
    students_with_citations: int = 0
    students_without_citations: int = 0

    # Generic reading references (not specific enough to aggregate,
    # but useful to know how many students cite "the reading" generically
    # vs. by name)
    generic_reading_ref_count: int = 0
    specific_source_count: int = 0


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def extract_citations(
    text: str,
    *,
    student_id: str = "",
    student_name: str = "",
) -> List[Citation]:
    """Extract all citations from a single submission.

    Returns empty list if no citations found.
    """
    citations: List[Citation] = []
    seen_normalized: set = set()  # dedup within one submission

    def _add(ctype: str, raw: str, normalized: str) -> None:
        key = (ctype, normalized.lower().strip())
        if key not in seen_normalized:
            seen_normalized.add(key)
            citations.append(Citation(
                citation_type=ctype,
                raw_text=raw,
                normalized=normalized,
                student_id=student_id,
                student_name=student_name,
            ))

    # --- URLs ---
    for m in _URL_PATTERN.finditer(text):
        url = m.group().rstrip(".,;:!?)")
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain in _SKIP_DOMAINS_EXACT:
                continue
            if any(domain.endswith(s) for s in _SKIP_DOMAIN_SUFFIXES):
                continue
        except Exception:
            pass
        _add("url", m.group(), url)

    # --- DOIs ---
    for m in _DOI_PATTERN.finditer(text):
        doi = m.group(1).rstrip(".,;:!?)")
        _add("doi", m.group(), f"https://doi.org/{doi}")

    # --- APA-style (Author, Year) ---
    for m in _APA_CITE.finditer(text):
        author, year = m.group(1), m.group(2)
        _add("author_year", m.group(), f"{author} ({year})")

    # --- Inline author: Author (Year) ---
    for m in _INLINE_AUTHOR.finditer(text):
        author, year = m.group(1), m.group(2)
        norm = f"{author} ({year})"
        _add("author_year", m.group(), norm)

    # --- "According to..." ---
    for m in _ACCORDING_TO.finditer(text):
        ref_text = m.group(1).strip()
        if len(ref_text) > 3:
            _add("generic_reference", m.group(), ref_text)

    # --- Generic reading references ---
    for m in _READING_REF.finditer(text):
        _add("reading_reference", m.group(), "[course reading]")

    # --- Quoted titles ---
    for m in _QUOTED_TITLE.finditer(text):
        # Multiple capture groups — take the first non-None match
        title = next((g for g in m.groups() if g is not None), None)
        if title is None:
            continue
        title = title.strip()
        # Filter out dialog/speech: must be >10 chars, start with uppercase
        if len(title) > 10 and title[0].isupper():
            _add("quoted_title", m.group(), title)

    return citations


# ---------------------------------------------------------------------------
# Class-level analysis
# ---------------------------------------------------------------------------

def analyze_class_citations(
    texts: Dict[str, str],
    meta: Dict[str, Dict],
) -> CitationReport:
    """Extract citations across all submissions and build class-level summary.

    Parameters
    ----------
    texts : dict of student_id → body text
    meta : dict of student_id → metadata (must have student_name)

    Returns
    -------
    CitationReport with class-level aggregation.
    Returns report with has_citations=False if no citations found.
    """
    all_citations: List[Citation] = []
    students_with: set = set()
    generic_count = 0

    for sid, text in texts.items():
        name = meta.get(sid, {}).get("student_name", f"Student {sid}")
        cites = extract_citations(text, student_id=sid, student_name=name)
        if cites:
            students_with.add(sid)
            all_citations.extend(cites)

    if not all_citations:
        return CitationReport(
            has_citations=False,
            students_without_citations=len(texts),
        )

    # Separate generic reading refs from specific sources
    specific = []
    for cite in all_citations:
        if cite.citation_type == "reading_reference":
            generic_count += 1
        else:
            specific.append(cite)

    # Build source summary: group by normalized source
    source_map: Dict[str, SourceSummary] = {}
    for cite in specific:
        key = cite.normalized.lower().strip()
        if key not in source_map:
            source_map[key] = SourceSummary(
                source=cite.normalized,
                citation_type=cite.citation_type,
            )
        summary = source_map[key]
        summary.count += 1
        if cite.student_id not in summary.student_ids:
            summary.student_ids.append(cite.student_id)
            summary.student_names.append(cite.student_name)

    # Sort by frequency
    sorted_sources = sorted(
        source_map.values(), key=lambda s: s.count, reverse=True
    )
    most_cited = [(s.source, s.count) for s in sorted_sources[:10]]

    return CitationReport(
        citations=all_citations,
        has_citations=True,
        source_count=len(source_map),
        sources_summary=sorted_sources,
        most_cited=most_cited,
        students_with_citations=len(students_with),
        students_without_citations=len(texts) - len(students_with),
        generic_reading_ref_count=generic_count,
        specific_source_count=len(specific),
    )


# ---------------------------------------------------------------------------
# Verification (network requests — runs automatically but async/non-blocking)
# ---------------------------------------------------------------------------

def _check_one_url(cite: "Citation", timeout: float) -> None:
    """HEAD-request a single URL or DOI and update cite.verified in place."""
    import urllib.request
    url = cite.normalized
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "Autograder4Canvas/1.0 (citation-check)")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            cite.verified = resp.status < 400
            cite.verification_note = f"HTTP {resp.status}"
    except Exception as e:
        cite.verified = False
        cite.verification_note = str(e)[:100]


def verify_citations_async(
    citations: List["Citation"],
    *,
    timeout: float = 5.0,
    on_complete: Optional[callable] = None,
) -> threading.Thread:
    """Verify URL and DOI citations in a background thread.

    Non-blocking — returns immediately.  Citations are updated in-place
    as each check completes.  Call on_complete(citations) when all are done.

    Equity note: paywalled, non-English, non-indexed, and community sources
    will appear unverified.  This is informational only — never a verdict.

    Parameters
    ----------
    citations : list
        All citations from analyze_class_citations().
    timeout : float
        Per-URL request timeout in seconds.
    on_complete : callable, optional
        Called with citations list when all checks complete.

    Returns
    -------
    threading.Thread — already started.  Join if you need to wait.
    """
    to_check = [c for c in citations if c.citation_type in ("url", "doi")]

    def _run() -> None:
        threads = []
        for cite in to_check:
            t = threading.Thread(
                target=_check_one_url, args=(cite, timeout), daemon=True
            )
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        if on_complete:
            on_complete(citations)

    thread = threading.Thread(target=_run, daemon=True, name="citation-verify")
    thread.start()
    return thread


def verify_citations_sync(
    citations: List["Citation"],
    *,
    timeout: float = 5.0,
) -> List["Citation"]:
    """Verify URL and DOI citations synchronously (blocking).

    Use verify_citations_async() in pipelines to avoid blocking.
    This version is provided for tests and one-off checks.
    """
    t = verify_citations_async(citations, timeout=timeout)
    t.join()
    return citations
