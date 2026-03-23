"""
QuickAnalyzer — Non-LLM analysis pass.  THE ANALYTICAL FOUNDATION.

This is not a fallback.  It is the backbone of the system.  Given 8B
limitations, the non-LLM pass provides the most *reliable* analytical
signal.  It runs in seconds, requires no model, and is always available.

Components:
  1. Submission statistics (count, word count distribution, timing, format)
  2. Word frequency (stopword-filtered, top N per prompt/question)
  3. TF-IDF distinctive terms (scikit-learn)
  4. Named entity extraction (spaCy en_core_web_sm)
  5. Keyword pattern matching (INSIGHT_PATTERNS)
  6. Emotional register scoring (GoEmotions; falls back to VADER)
  7. Embedding-based clustering (sentence-transformers + k-means/HDBSCAN)
  8. Cross-submission shared reference detection
  9. Emotional register + keyword signal matrix concern pre-screening

Each component degrades gracefully if its library is unavailable.
"""

import logging
import re
import statistics
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from insights.models import (
    AssignmentConnectionScore,
    AssignmentFingerprint,
    ConcernSignal,
    ContradictionSignal,
    EmbeddingCluster,
    HighSimilarityPair,
    KeywordHit,
    PairwiseSimilarityStats,
    PerSubmissionSummary,
    QuickAnalysisResult,
    ReferenceMatchScore,
    SharedReference,
    SubmissionStats,
    TermFrequency,
    TermScore,
)
from insights.citation_checker import analyze_class_citations, verify_citations_async
from insights.gibberish_gate import check_gibberish
from insights.patterns import (
    INSIGHT_PATTERNS,
    KEYWORD_CATEGORIES,
    classify_vader_polarity,
    has_critical_keywords,
    match_all_patterns,
    signal_matrix_classify,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common English stopwords (avoids NLTK dependency)
# ---------------------------------------------------------------------------
_STOPWORDS = frozenset(
    # ---- Core English function words (NLTK-style) ----
    "a an the and or but is are was were be been being have has had do does did "
    "will would shall should may might can could i me my we our you your he she "
    "it they them their his her its this that these those am not no nor so if "
    "then than too very just about also how all each every both few more most "
    "other some such only own same through during before after above below "
    "to from up down in out on off over under again further of at by for with "
    "as into between because until while where when which who whom what "
    "there here why how much many any dont didnt cant wont im ive hed shed "
    "doesnt thats theres heres theyre youre were theyd youd wed "
    "ill youll hell shell theyll well weve youve theyve "
    "isnt arent wasnt werent hasnt havent hadnt shouldnt wouldnt couldnt "
    "mustnt must neednt shant lets thats whats hows whos whys having "
    # ---- Common verbs / verb forms (no analytical signal) ----
    "get got gets getting give gave gives giving given go goes going gone went "
    "make makes making made come comes coming came become becomes becoming became "
    "take takes taking took taken put puts putting set sets setting run runs "
    "running ran say says said saying tell tells telling told talk talks talking "
    "talked think thinks thinking thought know knows knowing knew known "
    "see sees seeing saw seen find finds finding found show shows showing showed "
    "shown want wants wanting wanted need needs needing needed keep keeps keeping "
    "kept let letting seem seems seemed seeming try tries trying tried "
    "help helps helping helped start starts starting started use uses using used "
    "look looks looking looked turn turns turning turned call calls calling called "
    "ask asks asking asked work works working worked move moves moving moved "
    "live lives living lived believe believes believed feel feels feeling felt "
    "bring brings bringing brought hold holds holding held stand stands standing "
    "stood happen happens happening happened leave leaves leaving left "
    "begin begins beginning began begun mean means meaning meant "
    # ---- Generic adverbs / adjectives / fillers ----
    "really actually already always never ever still even back away "
    "just quite rather often however instead also yet ago soon enough "
    "maybe perhaps sometimes usually generally probably certainly definitely "
    "simply basically essentially merely nearly almost truly indeed "
    "well lot lots kind sort able like "
    "now right around already since without within along upon onto toward "
    "towards across behind beyond beside besides among throughout against "
    "big small great good bad new old long short high low different "
    "important large little young certain sure whole real "
    # ---- Generic nouns / pronouns (no analytical signal) ----
    "people person thing things something anything nothing everything "
    "someone anyone everyone nobody somebody everybody "
    "way ways part parts place places time times day days year years "
    "world life man men woman women idea ideas point fact "
    "number case end side hand example reason area state "
    "one two three four five six seven eight nine ten "
    # ---- Conjunctions / prepositions / determiners ----
    "although though whether either neither nor yet thus hence therefore "
    "moreover furthermore meanwhile nonetheless nevertheless "
    "else another per via ought dare etc "
    # ---- HTML entities that leak through ----
    "nbsp amp quot lt gt ndash mdash hellip rsquo lsquo rdquo ldquo "
    # ---- Common academic filler (no analytical signal) ----
    "week reading readings assignment class course professor teacher students "
    "student wrote write writing essay paper paragraph page pages chapter "
    "question questions answer topic discussion response reflection submission "
    "canvas homework grade point points due today yesterday last next first "
    "second third new also another".split()
)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def _tokenize(text: str) -> List[str]:
    """Simple word tokenization: lowercase, alpha-only, no stopwords."""
    text = _strip_html(text)
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


# ---------------------------------------------------------------------------
# Assignment fingerprint extraction (Mechanism 2 — Assignment Context Awareness)
# ---------------------------------------------------------------------------

# Engagement type detection keywords.  Order matters — first match wins,
# except when multiple categories match → "mixed".
_ENGAGEMENT_PATTERNS: Dict[str, List[re.Pattern]] = {
    "personal_reflection": [
        re.compile(r"\b(?:share\s+your\s+personal|reflect\s+on|your\s+experience|your\s+own|personal\s+narrative|how\s+(?:has|have|do|does|did)\s+(?:this|these|the)\b)", re.I),
        re.compile(r"\b(?:what\s+does\s+this\s+mean\s+to\s+you|connect\s+to\s+your\s+(?:life|experience)|in\s+your\s+(?:life|experience))\b", re.I),
    ],
    "analysis": [
        re.compile(r"\b(?:analyze|evaluate|argue|critique|critical(?:ly)?|assess|examine|interpret|compare\s+and\s+contrast)\b", re.I),
    ],
    "summary": [
        re.compile(r"\b(?:summarize|describe|explain|outline|identify\s+the\s+(?:main|key))\b", re.I),
    ],
    "discussion": [
        re.compile(r"\b(?:discuss|respond\s+to|what\s+do\s+you\s+think|do\s+you\s+agree|your\s+(?:thoughts|opinion|response)|react\s+to)\b", re.I),
    ],
}


def extract_assignment_fingerprint(
    assignment_description: str,
) -> Optional[AssignmentFingerprint]:
    """Extract named references from an assignment description using NLP.

    Pure NLP — no LLM required.  Uses spaCy NER for author names and work
    titles, regex for quoted/italicized titles, and TF-IDF for key concepts.

    Returns None if spaCy is unavailable or the description is empty.
    """
    desc = _strip_html(assignment_description).strip()
    if not desc or len(desc) < 20:
        return None

    # ----- Named entity extraction (spaCy) -----
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except (ImportError, OSError):
        log.info("spaCy/en_core_web_sm not available — skipping assignment fingerprint")
        return None

    doc = nlp(desc)

    # PERSON entities → author names
    raw_persons = []
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            name = ent.text.strip()
            if len(name) >= 2:
                raw_persons.append(name)

    # WORK_OF_ART entities → titles
    raw_works = []
    for ent in doc.ents:
        if ent.label_ == "WORK_OF_ART":
            title = ent.text.strip()
            if len(title) >= 3:
                raw_works.append(title)

    # All entities for raw_named_entities (deduplicated)
    raw_entities = list(dict.fromkeys(
        ent.text.strip() for ent in doc.ents if len(ent.text.strip()) >= 2
    ))

    # ----- Regex for quoted / italicized titles -----
    # Quoted text: "Title Here" or 'Title Here'
    for m in re.finditer(r'["\u201c]([^"\u201d]{3,80})["\u201d]', desc):
        candidate = m.group(1).strip()
        # Skip if it looks like an instruction phrase, not a title
        if not re.match(r'^(?:for example|such as|e\.g\.|i\.e\.)', candidate, re.I):
            if candidate not in raw_works:
                raw_works.append(candidate)

    # Italic markers in HTML-stripped text (from <em> or <i> tags — we get
    # the text but lose the tags).  Look for *text* or _text_ in markdown-style.
    for m in re.finditer(r'[*_]([^*_]{3,80})[*_]', desc):
        candidate = m.group(1).strip()
        if candidate not in raw_works:
            raw_works.append(candidate)

    # Deduplicate author names (keep longest form, case-insensitive)
    author_names = _deduplicate_names(raw_persons)

    # Deduplicate work titles
    work_titles = list(dict.fromkeys(raw_works))

    # ----- Key concept extraction (TF-IDF on the description) -----
    key_concepts = _extract_key_concepts(desc)

    # ----- Engagement type detection -----
    engagement_type = _detect_engagement_type(desc)

    return AssignmentFingerprint(
        author_names=author_names,
        work_titles=work_titles,
        key_concepts=key_concepts,
        engagement_type=engagement_type,
        raw_named_entities=raw_entities,
    )


def _deduplicate_names(names: List[str]) -> List[str]:
    """Deduplicate person names: keep the longest form per last-name.

    E.g., ["Kimberle Crenshaw", "Crenshaw"] → ["Kimberle Crenshaw"]
    """
    if not names:
        return []
    # Sort longest first so we keep the fullest form
    sorted_names = sorted(set(names), key=len, reverse=True)
    result = []
    seen_lower = set()
    for name in sorted_names:
        name_lower = name.lower()
        # Check if this name is a substring of an already-kept name
        if any(name_lower in kept for kept in seen_lower):
            continue
        result.append(name)
        seen_lower.add(name_lower)
    return result


def _extract_key_concepts(description: str, top_n: int = 10) -> List[str]:
    """Extract distinctive terms from the assignment description using TF-IDF.

    Since we only have one document (the assignment description), we use
    single-document TF-IDF against a pseudo-corpus of individual sentences
    to surface terms that are distinctive within the description itself.
    Falls back to simple frequency-based extraction if sklearn is unavailable.
    """
    # Tokenize into content words
    tokens = _tokenize(description)
    if not tokens:
        return []

    # Split description into sentences as pseudo-documents for TF-IDF
    sentences = [s.strip() for s in re.split(r'[.!?]+', description) if len(s.strip()) > 10]

    if len(sentences) >= 2:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            vec = TfidfVectorizer(
                stop_words="english",
                max_features=200,
                min_df=1,
                token_pattern=r"[a-zA-Z]{3,}",
            )
            tfidf = vec.fit_transform(sentences)
            feature_names = vec.get_feature_names_out()
            # Average TF-IDF across sentences
            avg_scores = tfidf.mean(axis=0).A1
            top_indices = avg_scores.argsort()[-top_n:][::-1]
            concepts = [
                feature_names[i] for i in top_indices
                if avg_scores[i] > 0 and feature_names[i] not in _STOPWORDS
            ]
            return concepts[:top_n]
        except (ImportError, ValueError):
            pass

    # Fallback: frequency-based (most common non-stopword tokens)
    counter = Counter(tokens)
    return [term for term, _ in counter.most_common(top_n)]


def _detect_engagement_type(description: str) -> str:
    """Detect what type of engagement the assignment asks for.

    Returns one of: personal_reflection, analysis, summary, discussion, mixed.
    Forgiving — defaults to "mixed" when unclear.
    """
    matched_types = []
    for eng_type, patterns in _ENGAGEMENT_PATTERNS.items():
        for pat in patterns:
            if pat.search(description):
                matched_types.append(eng_type)
                break  # one match per type is enough

    if len(matched_types) == 0:
        return "mixed"
    elif len(matched_types) == 1:
        return matched_types[0]
    else:
        return "mixed"


def match_submission_references(
    submission_text: str,
    fingerprint: AssignmentFingerprint,
) -> ReferenceMatchScore:
    """Match a single submission against the assignment fingerprint.

    Checks which author names, work titles, and key concepts from the
    assignment description appear in the student's submission text.

    Case-insensitive matching.  For author names, matches on last name
    alone (e.g., "Crenshaw" matches "Kimberle Crenshaw" in the fingerprint).
    """
    text_lower = submission_text.lower()

    # Match author names (case-insensitive, last-name match)
    authors_found = []
    for author in fingerprint.author_names:
        # Try full name first, then last name
        if author.lower() in text_lower:
            authors_found.append(author)
        else:
            # Try last name only (last word of the name)
            parts = author.split()
            if len(parts) > 1 and parts[-1].lower() in text_lower:
                # Verify it's a word boundary match, not a substring
                last = parts[-1].lower()
                if re.search(r'\b' + re.escape(last) + r'\b', text_lower):
                    authors_found.append(author)

    # Match work titles (case-insensitive, allow partial for long titles)
    titles_found = []
    for title in fingerprint.work_titles:
        title_lower = title.lower()
        if title_lower in text_lower:
            titles_found.append(title)
        elif len(title.split()) > 3:
            # For long titles, check if significant portion appears
            title_words = [w for w in title_lower.split() if w not in _STOPWORDS and len(w) > 2]
            if title_words:
                found_count = sum(1 for w in title_words if re.search(r'\b' + re.escape(w) + r'\b', text_lower))
                if found_count / len(title_words) >= 0.6:
                    titles_found.append(title)

    # Match key concepts (word-boundary match)
    concepts_found = []
    for concept in fingerprint.key_concepts:
        concept_lower = concept.lower()
        if re.search(r'\b' + re.escape(concept_lower) + r'\b', text_lower):
            concepts_found.append(concept)

    # Compute overall match ratio
    total_refs = len(fingerprint.author_names) + len(fingerprint.work_titles) + len(fingerprint.key_concepts)
    found_count = len(authors_found) + len(titles_found) + len(concepts_found)
    match_ratio = found_count / max(total_refs, 1)

    # Build observation
    observation = _build_reference_observation(
        authors_found, len(fingerprint.author_names),
        titles_found, len(fingerprint.work_titles),
        concepts_found, len(fingerprint.key_concepts),
    )

    return ReferenceMatchScore(
        authors_found=authors_found,
        authors_total=len(fingerprint.author_names),
        titles_found=titles_found,
        titles_total=len(fingerprint.work_titles),
        concepts_found=concepts_found,
        concepts_total=len(fingerprint.key_concepts),
        match_ratio=round(match_ratio, 4),
        observation=observation,
    )


def _build_reference_observation(
    authors_found: List[str], authors_total: int,
    titles_found: List[str], titles_total: int,
    concepts_found: List[str], concepts_total: int,
) -> str:
    """Build a human-readable observation about reference matching."""
    parts = []
    total_refs = authors_total + titles_total + concepts_total
    if total_refs == 0:
        return ""

    found_total = len(authors_found) + len(titles_found) + len(concepts_found)

    if authors_total > 0:
        parts.append(f"{len(authors_found)}/{authors_total} named authors")
    if titles_total > 0:
        parts.append(f"{len(titles_found)}/{titles_total} work titles")
    if concepts_total > 0:
        parts.append(f"{len(concepts_found)}/{concepts_total} key concepts")

    detail = ", ".join(parts)

    if found_total == 0:
        return (
            f"No named references from the assignment detected ({detail}). "
            f"The student may be engaging through personal experience, "
            f"paraphrase, or non-academic vocabulary."
        )
    elif found_total < total_refs * 0.3:
        return f"Few named references from the assignment ({detail})."
    elif found_total >= total_refs * 0.7:
        return f"Strong reference to assigned material ({detail})."
    else:
        return f"Some references to assigned material ({detail})."


class QuickAnalyzer:
    """Non-LLM analysis pass — the analytical foundation."""

    def __init__(self, progress_callback: Optional[Callable] = None):
        self._progress = progress_callback or (lambda *a: None)

    def analyze(
        self,
        submissions: List[Dict[str, Any]],
        *,
        assignment_id: str,
        assignment_name: str = "",
        assignment_description: str = "",
        course_id: str = "",
        course_name: str = "",
    ) -> QuickAnalysisResult:
        """Run the full non-LLM analysis pass.

        Parameters
        ----------
        submissions : list of dicts, each with at least:
            - student_id, student_name, body (text), submission_type,
              word_count (optional), submitted_at (optional)

        Returns QuickAnalysisResult with all components populated.
        """
        result = QuickAnalysisResult(
            assignment_id=str(assignment_id),
            assignment_name=assignment_name,
            course_id=str(course_id),
            course_name=course_name,
            analyzed_at=datetime.utcnow().isoformat(),
        )

        if not submissions:
            result.analysis_notes.append("No submissions to analyze.")
            return result

        # Extract text bodies
        texts: Dict[str, str] = {}
        meta: Dict[str, Dict] = {}
        for sub in submissions:
            sid = str(sub.get("student_id", sub.get("user_id", "")))
            body = sub.get("body") or sub.get("text") or ""
            body = _strip_html(body)
            texts[sid] = body
            meta[sid] = sub

        # Pre-analysis gate: flag gibberish before any expensive analysis
        self._progress("Running gibberish gate...")
        gibberish_results: Dict[str, Any] = {}  # sid → GibberishResult
        for sid, body in texts.items():
            was_translated = meta.get(sid, {}).get("was_translated", False)
            gib = check_gibberish(body, was_translated=was_translated)
            gibberish_results[sid] = gib
            if gib.is_gibberish:
                result.gibberish_ids.append(sid)
                name = meta.get(sid, {}).get("student_name", f"Student {sid}")
                result.analysis_notes.append(
                    f"Gibberish gate flagged {name}: {gib.detail}"
                )

        self._progress("Computing submission statistics...")
        result.stats = self._compute_stats(texts, meta)

        self._progress("Analyzing word frequency...")
        result.top_terms = self._word_frequency(texts)

        self._progress("Computing TF-IDF terms...")
        result.tfidf_terms = self._tfidf_terms(texts)

        self._progress("Extracting named entities...")
        result.named_entities = self._named_entities(texts)

        self._progress("Matching keyword patterns...")
        result.keyword_hits = self._keyword_hits(texts, meta)

        self._progress("Computing emotional register...")
        result.sentiments, result.sentiment_distribution = self._compute_emotional_register(texts, meta)

        self._progress("Clustering submissions...")
        result.clusters, result.embedding_outlier_ids, _embeddings, _embed_sids = (
            self._embedding_clusters(texts, meta)
        )

        self._progress("Computing pairwise similarity...")
        result.pairwise_similarity = self._pairwise_similarity(
            _embeddings, _embed_sids, meta
        )

        # Assignment connection (vocabulary overlap with assignment description)
        _connection_scores: Dict[str, "AssignmentConnectionScore"] = {}
        if assignment_description.strip():
            self._progress("Computing assignment connection...")
            _connection_scores = self._assignment_connection(
                texts, meta, assignment_description
            )
            result.assignment_description = assignment_description
            # Class-level observation
            low_count = sum(
                1 for s in _connection_scores.values()
                if s.vocabulary_overlap < 0.1
            )
            total = len(_connection_scores)
            if total > 0 and low_count / total > 0.3:
                result.assignment_connection_observation = (
                    f"An unusually high proportion of submissions "
                    f"({low_count} of {total}) have low vocabulary "
                    f"connection to the assignment keywords. Possible "
                    f"interpretations: submission portal issue, "
                    f"assignment prompt may need clearer framing, or "
                    f"students are approaching the material through "
                    f"different entry points."
                )
            elif total > 0 and low_count / total > 0.1:
                result.assignment_connection_observation = (
                    f"Some submissions ({low_count} of {total}) have "
                    f"low vocabulary connection to the assignment keywords."
                )

        # Assignment fingerprint (named reference extraction)
        _fingerprint: Optional[AssignmentFingerprint] = None
        _reference_scores: Dict[str, ReferenceMatchScore] = {}
        if assignment_description.strip():
            self._progress("Extracting assignment fingerprint...")
            _fingerprint = extract_assignment_fingerprint(assignment_description)
            if _fingerprint:
                result.assignment_fingerprint = _fingerprint
                has_refs = (
                    _fingerprint.author_names
                    or _fingerprint.work_titles
                    or _fingerprint.key_concepts
                )
                if has_refs:
                    for sid, body in texts.items():
                        _reference_scores[sid] = match_submission_references(
                            body, _fingerprint
                        )
                    # Class-level note
                    ref_parts = []
                    if _fingerprint.author_names:
                        ref_parts.append(
                            f"{len(_fingerprint.author_names)} author(s): "
                            + ", ".join(_fingerprint.author_names[:5])
                        )
                    if _fingerprint.work_titles:
                        ref_parts.append(
                            f"{len(_fingerprint.work_titles)} title(s): "
                            + ", ".join(_fingerprint.work_titles[:3])
                        )
                    if _fingerprint.key_concepts:
                        ref_parts.append(
                            f"{len(_fingerprint.key_concepts)} key concept(s)"
                        )
                    result.analysis_notes.append(
                        f"Assignment fingerprint: {'; '.join(ref_parts)} "
                        f"(engagement type: {_fingerprint.engagement_type})"
                    )

        self._progress("Detecting shared references...")
        result.shared_references = self._shared_references(texts)

        self._progress("Running signal matrix...")
        median_wc = result.stats.word_count_median
        result.concern_signals = self._signal_matrix(texts, meta, result.sentiments, median_wc)

        # Semantic reader-test detection — catches natural variations the regex
        # can't anticipate ("has anyone actually looked at these?" etc.)
        # Runs only when sentence-transformers is available (already loaded for clustering).
        semantic_signals = self._semantic_teacher_test(texts, meta)
        result.concern_signals.extend(semantic_signals)

        self._progress("Detecting contradictions...")
        result.contradictions = self._detect_contradictions(
            texts, meta, result.sentiments, result.shared_references
        )

        # Citation analysis — only produces output when citations exist.
        # URL/DOI verification runs async in the background (non-blocking).
        # Equity note: unverified ≠ fake — paywalled, non-English, non-indexed,
        # and community sources will appear unverified even when real.
        self._progress("Extracting citations...")
        try:
            cite_report = analyze_class_citations(texts, meta)
            if cite_report.has_citations:
                # Start async verification — updates citations in place as
                # each HEAD request completes.  The result dict below captures
                # a reference to cite_report.citations so it reflects updates.
                _verify_thread = verify_citations_async(cite_report.citations)

                result.citation_report = {
                    "has_citations": True,
                    "source_count": cite_report.source_count,
                    "students_with_citations": cite_report.students_with_citations,
                    "students_without_citations": cite_report.students_without_citations,
                    "generic_reading_ref_count": cite_report.generic_reading_ref_count,
                    "specific_source_count": cite_report.specific_source_count,
                    "most_cited": cite_report.most_cited,
                    "verification_note": (
                        "URL/DOI existence is checked automatically. "
                        "Unverified ≠ fake — paywalled, non-English, and "
                        "community sources will appear unverified."
                    ),
                    "sources_summary": [
                        {
                            "source": s.source,
                            "citation_type": s.citation_type,
                            "student_names": s.student_names,
                            "count": s.count,
                        }
                        for s in cite_report.sources_summary
                    ],
                    # Live reference — verification status fills in as
                    # background thread completes.
                    "_citations_live": cite_report.citations,
                }
                result.analysis_notes.append(
                    f"Citations found: {cite_report.source_count} unique sources "
                    f"across {cite_report.students_with_citations} students "
                    f"(URL/DOI verification running in background)"
                )
        except Exception as e:
            log.warning("Citation analysis failed: %s", e)

        # Build per-submission summaries
        # Compute class median word count for truncation detection
        _all_wcs = [len(body.split()) for body in texts.values()]
        _class_median_wc = statistics.median(_all_wcs) if _all_wcs else 0.0

        for sid, body in texts.items():
            wc = len(body.split())
            sub_meta = meta.get(sid, {})
            cluster_id = None
            for cl in result.clusters:
                if sid in cl.student_ids:
                    cluster_id = cl.cluster_id
                    break
            _sentiment_data = result.sentiments.get(sid, {})
            vader_compound = _sentiment_data.get("compound", 0.0)
            _emotions = _sentiment_data.get("emotions", {})
            _sentiment_backend = _sentiment_data.get("reliability", "")
            kw_hits = match_all_patterns(body)
            # Reuse gibberish result from the early gate pass
            gib = gibberish_results.get(sid)

            # Truncation detection (non-LLM heuristic)
            _is_trunc, _trunc_note = self._is_possibly_truncated(body, wc, _class_median_wc)

            result.per_submission[sid] = PerSubmissionSummary(
                student_id=sid,
                student_name=sub_meta.get("student_name", f"Student {sid}"),
                word_count=wc,
                submission_type=sub_meta.get("submission_type") or "unknown",
                vader_compound=vader_compound,
                emotions=_emotions,
                sentiment_backend=_sentiment_backend,
                keyword_hits=kw_hits,
                cluster_id=cluster_id,
                was_translated=sub_meta.get("was_translated", False),
                was_transcribed=sub_meta.get("was_transcribed", False),
                is_gibberish=gib.is_gibberish if gib else False,
                gibberish_reason=gib.reason if gib else "",
                gibberish_detail=gib.detail if gib else "",
                assignment_connection=_connection_scores.get(sid),
                reference_match=_reference_scores.get(sid),
                is_possibly_truncated=_is_trunc,
                truncation_note=_trunc_note,
            )

        return result

    # ------------------------------------------------------------------
    # 1. Submission statistics
    # ------------------------------------------------------------------

    def _compute_stats(
        self, texts: Dict[str, str], meta: Dict[str, Dict]
    ) -> SubmissionStats:
        word_counts = [len(t.split()) for t in texts.values()]
        format_counts: Dict[str, int] = Counter()
        timing_counts: Dict[str, int] = Counter()

        for sid, m in meta.items():
            fmt = m.get("submission_type", "unknown") or "unknown"
            format_counts[fmt] += 1

            sub_at = m.get("submitted_at")
            due_at = m.get("due_at")
            if sub_at and due_at:
                try:
                    sub_dt = datetime.fromisoformat(sub_at.replace("Z", "+00:00"))
                    due_dt = datetime.fromisoformat(due_at.replace("Z", "+00:00"))
                    diff = (sub_dt - due_dt).total_seconds()
                    if diff <= 0:
                        timing_counts["on_time"] += 1
                    elif diff <= 86400:
                        timing_counts["late"] += 1
                    else:
                        timing_counts["very_late"] += 1
                except (ValueError, TypeError):
                    pass
            elif sub_at:
                timing_counts["on_time"] += 1

        return SubmissionStats(
            total_submissions=len(texts),
            word_count_mean=statistics.mean(word_counts) if word_counts else 0,
            word_count_median=statistics.median(word_counts) if word_counts else 0,
            word_count_min=min(word_counts) if word_counts else 0,
            word_count_max=max(word_counts) if word_counts else 0,
            word_counts=word_counts,
            format_breakdown=dict(format_counts),
            timing=dict(timing_counts),
        )

    # ------------------------------------------------------------------
    # Truncation detection (non-LLM heuristic)
    # ------------------------------------------------------------------

    def _is_possibly_truncated(self, text: str, word_count: int, class_median_words: float) -> tuple[bool, str]:
        """Non-LLM heuristic: detect submissions that may have been cut off mid-thought.

        Equity note: frames as care ("consider checking in"), never as failure.
        ESL students and neurodivergent writers may have non-standard endings —
        require multiple signals, not just missing terminal punctuation.
        """
        stripped = text.strip()
        if not stripped:
            return False, ""

        signals = []

        # Signal 1: ends without terminal punctuation
        last_chars = stripped[-3:] if len(stripped) >= 3 else stripped
        if not re.search(r'[.?!"\')\]]', last_chars):
            signals.append("no_terminal_punct")

        # Signal 2: ends with trailing conjunction/preposition
        last_word = stripped.split()[-1].lower().rstrip('.,;:') if stripped.split() else ""
        trailing_words = {"and", "but", "that", "because", "with", "or", "so", "when", "if", "the", "a", "an"}
        if last_word in trailing_words:
            signals.append("trailing_conjunction")

        # Signal 3: explicit acknowledgment of incompleteness
        incomplete_phrases = ["i had more", "ran out of", "didn't finish", "will finish later", "more to say"]
        text_lower = stripped.lower()
        if any(phrase in text_lower for phrase in incomplete_phrases):
            signals.append("explicit_incomplete")

        # Signal 4: significantly shorter than class median
        below_median = class_median_words > 0 and word_count < (class_median_words * 0.5)
        if below_median:
            signals.append("below_median")

        # Require: explicit_incomplete OR (no_terminal_punct AND one other signal)
        is_truncated = (
            "explicit_incomplete" in signals
            or ("no_terminal_punct" in signals and "trailing_conjunction" in signals)
            or ("no_terminal_punct" in signals and "below_median" in signals)
        )

        if is_truncated:
            note = ("This submission may be incomplete — it ends without finishing the last thought"
                    + (", and is shorter than most submissions in this class" if below_median else "")
                    + ". Consider checking in with this student.")
            return True, note

        return False, ""

    # ------------------------------------------------------------------
    # 2. Word frequency
    # ------------------------------------------------------------------

    def _word_frequency(
        self, texts: Dict[str, str], top_n: int = 30
    ) -> List[TermFrequency]:
        counter: Counter = Counter()
        for body in texts.values():
            counter.update(_tokenize(body))
        return [
            TermFrequency(term=t, count=c)
            for t, c in counter.most_common(top_n)
        ]

    # ------------------------------------------------------------------
    # 3. TF-IDF distinctive terms
    # ------------------------------------------------------------------

    def _tfidf_terms(
        self, texts: Dict[str, str], top_n: int = 20
    ) -> List[TermScore]:
        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
        except ImportError:
            log.info("scikit-learn not available — skipping TF-IDF")
            return []

        docs = list(texts.values())
        if len(docs) < 2:
            return []

        try:
            vec = TfidfVectorizer(
                max_features=500,
                stop_words="english",
                min_df=2,
                max_df=0.9,
                token_pattern=r"[a-zA-Z]{3,}",
            )
            tfidf = vec.fit_transform(docs)
            feature_names = vec.get_feature_names_out()

            # Average TF-IDF score across documents for each term
            avg_scores = tfidf.mean(axis=0).A1
            top_indices = avg_scores.argsort()[-top_n:][::-1]
            return [
                TermScore(term=feature_names[i], score=round(avg_scores[i], 4))
                for i in top_indices
                if avg_scores[i] > 0
            ]
        except Exception as e:
            log.warning("TF-IDF analysis failed: %s", e)
            return []

    # ------------------------------------------------------------------
    # 4. Named entity extraction
    # ------------------------------------------------------------------

    def _named_entities(
        self, texts: Dict[str, str]
    ) -> Dict[str, List[str]]:
        try:
            import spacy
            nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
        except (ImportError, OSError):
            log.info("spaCy/en_core_web_sm not available — skipping NER")
            return {}

        entities: Dict[str, Counter] = {}
        combined = " ".join(texts.values())
        # Process in chunks to avoid memory issues
        chunk_size = 100000
        for i in range(0, len(combined), chunk_size):
            doc = nlp(combined[i:i + chunk_size])
            for ent in doc.ents:
                if ent.label_ not in entities:
                    entities[ent.label_] = Counter()
                entities[ent.label_][ent.text.strip()] += 1

        # Return top entities per type
        result = {}
        for label, counter in entities.items():
            top = [text for text, _ in counter.most_common(10)]
            if top:
                result[label] = top
        return result

    # ------------------------------------------------------------------
    # 5. Keyword pattern matching
    # ------------------------------------------------------------------

    def _keyword_hits(
        self, texts: Dict[str, str], meta: Dict[str, Dict]
    ) -> Dict[str, KeywordHit]:
        hits: Dict[str, Dict] = {}

        for sid, body in texts.items():
            for pname, pattern in INSIGHT_PATTERNS.items():
                matches = pattern.findall(body)
                if not matches:
                    continue
                if pname not in hits:
                    hits[pname] = {
                        "pattern_name": pname,
                        "count": 0,
                        "student_ids": [],
                        "examples": [],
                    }
                hits[pname]["count"] += len(matches)
                hits[pname]["student_ids"].append(sid)
                # Keep first example per student (up to 5 total)
                if len(hits[pname]["examples"]) < 5:
                    # Find the match in context (±30 chars)
                    m = pattern.search(body)
                    if m:
                        start = max(0, m.start() - 30)
                        end = min(len(body), m.end() + 30)
                        hits[pname]["examples"].append(
                            "…" + body[start:end].strip() + "…"
                        )

        return {
            name: KeywordHit(**data) for name, data in hits.items()
        }

    # ------------------------------------------------------------------
    # 6. Emotional register scoring (GoEmotions, falls back to VADER)
    # ------------------------------------------------------------------

    # Submission types where word_count=0 means "unreadable file", not
    # "empty submission".  These must never be labelled perfunctory /
    # disengaged — the student DID submit; the pipeline just can't
    # extract text from their file.
    _FILE_SUBMISSION_TYPES = frozenset({"online_upload", "media_recording"})

    # GoEmotions label groupings (Demszky et al., 2020).
    # Used to derive a VADER-compatible compound score and pos/neg/neu floats.
    _GE_POSITIVE = frozenset({
        "admiration", "amusement", "approval", "caring", "desire",
        "excitement", "gratitude", "joy", "love", "optimism", "pride", "relief",
    })
    _GE_NEGATIVE = frozenset({
        "anger", "annoyance", "disappointment", "disapproval", "disgust",
        "embarrassment", "fear", "grief", "nervousness", "remorse", "sadness",
    })
    # Remaining labels (confusion, curiosity, neutral, realization, surprise) → neutral

    # Token budget: RoBERTa-base max is 512 tokens (~400 words).
    # Truncate to keep the most informative part (first + last thirds).
    _GE_MAX_CHARS = 1200

    def _ge_truncate(self, text: str) -> str:
        """Truncate text to fit GoEmotions token budget."""
        if len(text) <= self._GE_MAX_CHARS:
            return text
        half = self._GE_MAX_CHARS // 2
        return text[:half] + " … " + text[-half:]

    def _compute_emotional_register(
        self, texts: Dict[str, str], meta: Dict[str, Dict]
    ) -> Tuple[Dict[str, Dict[str, float]], Dict[str, int]]:
        """Compute emotional register scores using GoEmotions.

        Primary backend: SamLowe/roberta-base-go_emotions via HuggingFace
        transformers.  Falls back to vaderSentiment if transformers is
        unavailable or the model cannot be loaded.

        Output per submission (all downstream .get("compound") calls work):
          compound   : float [-1, 1]  positive_mass − negative_mass
          pos        : float  sum of positive-valence emotion probabilities
          neg        : float  sum of negative-valence emotion probabilities
          neu        : float  sum of neutral/ambiguous emotion probabilities
          emotions   : dict[str, float]  full GoEmotions label→score map
          reliability: str  "go_emotions" | "vader" | "none"
        """
        sentiments: Dict[str, Dict[str, float]] = {}
        register_counts: Dict[str, int] = Counter()

        score_fn = self._build_emotion_scorer()

        for sid, body in texts.items():
            scores = score_fn(body)
            sentiments[sid] = scores

            wc = len(body.split())
            sub_type = (meta.get(sid, {}).get("submission_type") or "").lower()

            # File uploads / media recordings with no extractable text:
            # exclude from register distribution entirely.
            if wc == 0 and sub_type in self._FILE_SUBMISSION_TYPES:
                continue

            compound = scores["compound"]
            pos = scores["pos"]
            neu = scores["neu"]

            # Classify emotional register — same logic as before so
            # downstream consumers see no behavioural change.
            if wc < 50 and abs(compound) < 0.2:
                register = "perfunctory"
            elif compound >= 0.3 and pos > 0.15:
                register = "passionate"
            elif compound <= -0.3:
                # Negative score may be topic-driven (colonialism, racism,
                # genocide) rather than personal distress.  Check engagement.
                _engagement_patterns = (
                    "critical_analysis",
                    "conceptual_connection",
                    "evidence_use",
                    "personal_reflection",
                )
                has_engagement = any(
                    INSIGHT_PATTERNS[p].search(body)
                    for p in _engagement_patterns
                    if p in INSIGHT_PATTERNS
                )
                if has_engagement or has_critical_keywords(body):
                    register = "passionate"
                else:
                    register = "urgent"
            elif abs(compound) < 0.15 and neu > 0.7:
                register = "analytical"
            elif pos > 0.1 and "my " in body.lower():
                register = "personal"
            else:
                register = "reflective"
            register_counts[register] += 1

        return sentiments, dict(register_counts)

    def _build_emotion_scorer(self):
        """Return a callable text → scores dict.

        Tries GoEmotions first; falls back to VADER on any failure.
        Result is cached on the instance so the model loads only once.
        """
        if hasattr(self, "_emotion_scorer_cache"):
            return self._emotion_scorer_cache

        scorer = self._try_go_emotions_scorer()
        if scorer is None:
            scorer = self._try_vader_scorer()
        if scorer is None:
            scorer = self._null_scorer

        self._emotion_scorer_cache = scorer
        return scorer

    def _try_go_emotions_scorer(self):
        """Build a GoEmotions scorer; return None on any import/load failure."""
        try:
            from transformers import pipeline as hf_pipeline
        except ImportError:
            log.info("transformers not available — GoEmotions scorer unavailable")
            return None

        try:
            pipe = hf_pipeline(
                "text-classification",
                model="SamLowe/roberta-base-go_emotions",
                top_k=None,
                truncation=True,
                max_length=512,
            )
            log.info("GoEmotions scorer loaded (SamLowe/roberta-base-go_emotions)")
        except Exception as e:
            log.info("GoEmotions model load failed (%s) — falling back to VADER", e)
            return None

        pos_labels = self._GE_POSITIVE
        neg_labels = self._GE_NEGATIVE

        def _score(text: str) -> Dict[str, float]:
            truncated = self._ge_truncate(text)
            try:
                raw = pipe(truncated)
            except Exception as exc:
                log.debug("GoEmotions inference failed: %s", exc)
                return self._null_scorer(text)
            # raw is [[{label, score}, ...]] (top_k=None gives all labels)
            label_scores = raw[0] if raw else []
            emotions: Dict[str, float] = {
                item["label"]: round(item["score"], 4) for item in label_scores
            }
            pos = sum(v for k, v in emotions.items() if k in pos_labels)
            neg_mass = sum(v for k, v in emotions.items() if k in neg_labels)
            neu_mass = sum(v for k, v in emotions.items() if k not in pos_labels and k not in neg_labels)
            compound = max(-1.0, min(1.0, pos - neg_mass))
            return {
                "compound": round(compound, 4),
                "pos": round(pos, 4),
                "neg": round(neg_mass, 4),
                "neu": round(neu_mass, 4),
                "emotions": emotions,
                "reliability": "go_emotions",
            }

        return _score

    def _try_vader_scorer(self):
        """Build a VADER scorer; return None on import failure."""
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError:
            log.info("vaderSentiment not available — sentiment scoring disabled")
            return None

        analyzer = SentimentIntensityAnalyzer()
        log.info("Emotional register: using VADER fallback (GoEmotions unavailable)")

        def _score(text: str) -> Dict[str, float]:
            s = analyzer.polarity_scores(text)
            return {
                "compound": s["compound"],
                "pos": s["pos"],
                "neg": s["neg"],
                "neu": s["neu"],
                "emotions": {},
                "reliability": "vader",
            }

        return _score

    @staticmethod
    def _null_scorer(text: str) -> Dict[str, float]:  # noqa: ARG004
        """Zero scores when no backend is available."""
        return {
            "compound": 0.0,
            "pos": 0.0,
            "neg": 0.0,
            "neu": 1.0,
            "emotions": {},
            "reliability": "none",
        }

    # ------------------------------------------------------------------
    # 7. Embedding-based clustering
    # ------------------------------------------------------------------

    def _embedding_clusters(
        self, texts: Dict[str, str], meta: Dict[str, Dict]
    ) -> Tuple[List[EmbeddingCluster], List[str], Optional[Any], Optional[List[str]]]:
        """Run K-means clustering on sentence embeddings.

        Returns
        -------
        clusters : List[EmbeddingCluster]
        outlier_ids : List[str]
        embeddings : numpy ndarray or None
            Raw embedding matrix (n_submissions x embedding_dim).
            Returned so callers can pass it to _pairwise_similarity()
            without a second encode pass.
        embed_sids : List[str] or None
            Student IDs in the same row order as `embeddings`.
        """
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.cluster import KMeans
            import numpy as np
        except ImportError:
            log.info("sentence-transformers/sklearn not available — skipping clustering")
            return [], [], None, None

        sids = list(texts.keys())
        docs = [texts[sid] for sid in sids]

        if len(docs) < 4:
            return [], [], None, None

        try:
            model = SentenceTransformer("all-MiniLM-L6-v2")
            embeddings = model.encode(docs, show_progress_bar=False)

            # Choose k: sqrt(n) capped at 8
            n = len(docs)
            k = max(2, min(8, int(n ** 0.5)))

            km = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = km.fit_predict(embeddings)

            # Build clusters
            cluster_map: Dict[int, List[int]] = {}
            for idx, label in enumerate(labels):
                cluster_map.setdefault(int(label), []).append(idx)

            clusters = []
            outlier_ids = []

            for cid, indices in sorted(cluster_map.items()):
                c_sids = [sids[i] for i in indices]
                c_names = [meta.get(sid, {}).get("student_name", f"Student {sid}")
                           for sid in c_sids]

                # Top terms for this cluster
                cluster_text = " ".join(texts[sid] for sid in c_sids)
                top = Counter(_tokenize(cluster_text)).most_common(5)

                # Find submission closest to cluster centroid
                centroid = km.cluster_centers_[cid]
                best_idx = min(indices, key=lambda idx: np.linalg.norm(embeddings[idx] - centroid))
                centroid_snippet = texts[sids[best_idx]][:150].strip()

                clusters.append(EmbeddingCluster(
                    cluster_id=cid,
                    size=len(c_sids),
                    student_ids=c_sids,
                    student_names=c_names,
                    top_terms=[t for t, _ in top],
                    centroid_text=centroid_snippet,
                ))

            # Outlier detection: submissions far from their cluster center
            distances = km.transform(embeddings)
            for idx in range(n):
                label = labels[idx]
                dist = distances[idx][label]
                # Outlier if distance > 2 standard deviations from cluster mean
                cluster_dists = [distances[j][label]
                                 for j in range(n) if labels[j] == label]
                if len(cluster_dists) > 2:
                    mean_d = statistics.mean(cluster_dists)
                    std_d = statistics.stdev(cluster_dists)
                    if std_d > 0 and dist > mean_d + 2 * std_d:
                        outlier_ids.append(sids[idx])

            return clusters, outlier_ids, embeddings, sids

        except Exception as e:
            log.warning("Embedding clustering failed: %s", e)
            return [], [], None, None

    # ------------------------------------------------------------------
    # 7b. Pairwise cosine similarity (class-level aggregate)
    # ------------------------------------------------------------------

    def _pairwise_similarity(
        self,
        embeddings: Optional[Any],
        sids: Optional[List[str]],
        meta: Optional[Dict[str, Dict]] = None,
    ) -> Optional[PairwiseSimilarityStats]:
        """Compute class-level pairwise cosine similarity statistics.

        Takes the embeddings already produced by _embedding_clusters() —
        no second encode pass.

        Returns aggregate statistics plus individual pairs at extreme
        thresholds (>=0.90).  At this level the match is near-verbatim.
        Even so, the observation is factual — the system does not
        determine cause.  Below 0.90, high similarity can indicate
        community, shared cultural knowledge, or collaborative learning.
        The first question for the teacher is always: "Is the assignment
        designed to produce diverse responses?"
        """
        if embeddings is None or sids is None or len(sids) < 2:
            return None

        try:
            from sklearn.metrics.pairwise import cosine_similarity
            import numpy as np
        except ImportError:
            log.info("scikit-learn not available — skipping pairwise similarity")
            return None

        try:
            n = len(sids)
            sim_matrix = cosine_similarity(embeddings)  # (n, n) symmetric

            # Collect upper-triangle values (exclude self-similarity on diagonal)
            upper = [
                float(sim_matrix[i, j])
                for i in range(n)
                for j in range(i + 1, n)
            ]

            if not upper:
                return None

            total_pairs = len(upper)
            mean_sim = float(np.mean(upper))
            max_sim = float(np.max(upper))
            pairs_085 = int(sum(1 for v in upper if v >= 0.85))
            pairs_070 = int(sum(1 for v in upper if v >= 0.70))

            # Build a class-level observation note — no student names or pair IDs
            if mean_sim >= 0.80:
                level = "very high"
            elif mean_sim >= 0.65:
                level = "high"
            elif mean_sim >= 0.50:
                level = "moderate"
            else:
                level = "low"

            parts = [
                f"This assignment had {level} submission similarity "
                f"(mean={mean_sim:.2f}, max={max_sim:.2f}, "
                f"{total_pairs} pairs total)."
            ]
            if pairs_085 > 0:
                parts.append(
                    f"{pairs_085} pair{'s' if pairs_085 != 1 else ''} "
                    f"above 0.85 (high similarity)."
                )
            if pairs_070 > 0:
                parts.append(
                    f"{pairs_070} pair{'s' if pairs_070 != 1 else ''} "
                    f"above 0.70 (moderate similarity)."
                )
            parts.append(
                "Consider first: is the assignment designed to produce diverse "
                "responses? Similarity can reflect community, shared cultural "
                "knowledge, or collaborative learning — not only copying."
            )

            observation = " ".join(parts)

            # Individual pairs at extreme threshold (>= 0.90)
            high_pairs: List[HighSimilarityPair] = []
            INDIVIDUAL_THRESHOLD = 0.90
            if meta is not None:
                for i in range(n):
                    for j in range(i + 1, n):
                        sim = float(sim_matrix[i, j])
                        if sim >= INDIVIDUAL_THRESHOLD:
                            name_a = meta.get(
                                sids[i], {}
                            ).get("student_name", f"Student {sids[i]}")
                            name_b = meta.get(
                                sids[j], {}
                            ).get("student_name", f"Student {sids[j]}")
                            high_pairs.append(HighSimilarityPair(
                                student_id_a=sids[i],
                                student_name_a=name_a,
                                student_id_b=sids[j],
                                student_name_b=name_b,
                                cosine_similarity=round(sim, 4),
                                observation=(
                                    f"These two submissions share "
                                    f"{sim:.0%} vocabulary overlap. "
                                    f"This is a factual observation — "
                                    f"the system does not determine "
                                    f"cause. Possible interpretations "
                                    f"include shared source material, "
                                    f"collaborative learning, or "
                                    f"identical content."
                                ),
                            ))

            return PairwiseSimilarityStats(
                mean_similarity=round(mean_sim, 4),
                max_similarity=round(max_sim, 4),
                pairs_above_085=pairs_085,
                pairs_above_070=pairs_070,
                total_pairs=total_pairs,
                observation=observation,
                high_similarity_pairs=high_pairs,
            )

        except Exception as e:
            log.warning("Pairwise similarity computation failed: %s", e)
            return None

    # ------------------------------------------------------------------
    # 7c. Assignment connection (vocabulary overlap)
    # ------------------------------------------------------------------

    def _assignment_connection(
        self,
        texts: Dict[str, str],
        meta: Dict[str, Dict],
        assignment_description: str,
    ) -> Dict[str, AssignmentConnectionScore]:
        """Compute vocabulary overlap between each submission and the
        assignment description using TF-IDF cosine similarity.

        This measures VOCABULARY OVERLAP only — it cannot assess whether
        a student is engaging with the material through lived experience,
        personal narrative, or non-standard approaches.
        """
        if not assignment_description.strip():
            return {}

        try:
            from sklearn.feature_extraction.text import TfidfVectorizer
            from sklearn.metrics.pairwise import cosine_similarity as cos_sim
        except ImportError:
            log.info("scikit-learn not available — skipping assignment connection")
            return {}

        sids = list(texts.keys())
        if not sids:
            return {}

        # Vectorize assignment description alongside all submissions.
        # The assignment description is document 0; submissions follow.
        all_docs = [assignment_description] + [texts[s] for s in sids]

        try:
            vectorizer = TfidfVectorizer(
                stop_words="english",
                max_features=5000,
                min_df=1,
            )
            tfidf_matrix = vectorizer.fit_transform(all_docs)
        except ValueError:
            # Empty vocabulary (all stopwords, etc.)
            return {}

        # Cosine similarity of each submission against the assignment desc
        assignment_vec = tfidf_matrix[0:1]
        submission_vecs = tfidf_matrix[1:]
        similarities = cos_sim(assignment_vec, submission_vecs).flatten()

        # Extract top content terms from the assignment description
        feature_names = vectorizer.get_feature_names_out()
        assignment_tfidf = tfidf_matrix[0].toarray().flatten()
        top_indices = assignment_tfidf.argsort()[-20:][::-1]
        assignment_keywords = [
            feature_names[i] for i in top_indices
            if assignment_tfidf[i] > 0
        ]

        scores: Dict[str, AssignmentConnectionScore] = {}
        for idx, sid in enumerate(sids):
            overlap = float(similarities[idx])
            was_translated = meta.get(sid, {}).get("was_translated", False)

            # Count keyword overlap
            sub_lower = texts[sid].lower()
            kw_found = sum(1 for kw in assignment_keywords if kw in sub_lower)
            kw_ratio = kw_found / max(len(assignment_keywords), 1)

            # Build observation
            obs_parts: List[str] = []
            if overlap < 0.1:
                obs_parts.append(
                    "This submission's vocabulary does not closely match "
                    "the assignment keywords. Consider: the student may "
                    "have submitted work for a different assignment, may "
                    "need support connecting their ideas to the prompt, "
                    "or may be engaging with the material in ways this "
                    "vocabulary check cannot capture."
                )
            elif overlap < 0.3:
                obs_parts.append(
                    "This submission's vocabulary partially overlaps the "
                    "assignment keywords. The student may be approaching "
                    "the material through personal experience or a "
                    "different entry point."
                )
            # >= 0.3: no observation needed

            if was_translated and obs_parts:
                obs_parts.append(
                    "Vocabulary overlap is measured against translated "
                    "text; engagement in the original language may not "
                    "be fully reflected."
                )

            scores[sid] = AssignmentConnectionScore(
                vocabulary_overlap=round(overlap, 4),
                keyword_overlap_count=kw_found,
                keyword_overlap_ratio=round(kw_ratio, 4),
                observation=" ".join(obs_parts),
            )

        return scores

    # ------------------------------------------------------------------
    # 8. Shared reference detection
    # ------------------------------------------------------------------

    def _shared_references(
        self, texts: Dict[str, str]
    ) -> List[SharedReference]:
        """Detect shared references: proper nouns, quoted titles, key phrases
        mentioned by multiple students."""
        # Extract capitalized multi-word phrases (likely proper nouns / titles)
        ref_counter: Dict[str, List[str]] = {}
        phrase_pat = re.compile(r"\b([A-Z][a-z]+(?:\s+(?:and|&|of|the|in)\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")

        for sid, body in texts.items():
            # Proper noun phrases
            found = set()
            for m in phrase_pat.finditer(body):
                phrase = m.group(1).strip()
                if len(phrase) > 4 and phrase not in found:
                    found.add(phrase)
            # Quoted text (book titles, etc.)
            for m in re.finditer(r'"([^"]{4,60})"', body):
                found.add(m.group(1))

            for ref in found:
                if ref not in ref_counter:
                    ref_counter[ref] = []
                ref_counter[ref].append(sid)

        # Only keep references mentioned by 2+ students
        refs = []
        for ref, sids in ref_counter.items():
            if len(sids) >= 2:
                refs.append(SharedReference(
                    reference=ref,
                    student_ids=sids,
                    count=len(sids),
                ))
        refs.sort(key=lambda r: r.count, reverse=True)
        return refs[:20]  # top 20

    # ------------------------------------------------------------------
    # 9. Contradiction detection
    # ------------------------------------------------------------------

    def _detect_contradictions(
        self,
        texts: Dict[str, str],
        meta: Dict[str, Dict],
        sentiments: Dict[str, Dict[str, float]],
        shared_refs: List[SharedReference],
    ) -> List[ContradictionSignal]:
        """Detect contradictions: shared reference + opposing sentiment."""
        contradictions = []
        for ref in shared_refs:
            if ref.count < 3:
                continue
            pos_students = []
            neg_students = []
            for sid in ref.student_ids:
                compound = sentiments.get(sid, {}).get("compound", 0.0)
                # Check sentiment in the sentence containing the reference
                body = texts.get(sid, "")
                ref_lower = ref.reference.lower()
                for sentence in re.split(r'[.!?]+', body):
                    if ref_lower in sentence.lower():
                        try:
                            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
                            sa = SentimentIntensityAnalyzer()
                            sent_score = sa.polarity_scores(sentence)["compound"]
                            if sent_score >= 0.2:
                                pos_students.append(sid)
                            elif sent_score <= -0.2:
                                neg_students.append(sid)
                        except ImportError:
                            if compound >= 0.1:
                                pos_students.append(sid)
                            elif compound <= -0.1:
                                neg_students.append(sid)
                        break

            if pos_students and neg_students:
                contradictions.append(ContradictionSignal(
                    reference=ref.reference,
                    positive_students=pos_students,
                    negative_students=neg_students,
                    description=(
                        f"Opposing views on '{ref.reference}': "
                        f"{len(pos_students)} positive, {len(neg_students)} negative"
                    ),
                ))

        return contradictions

    # ------------------------------------------------------------------
    # Signal matrix pre-screening
    # ------------------------------------------------------------------

    def _signal_matrix(
        self,
        texts: Dict[str, str],
        meta: Dict[str, Dict],
        sentiments: Dict[str, Dict[str, float]],
        median_wc: float,
    ) -> List[ConcernSignal]:
        signals = []
        for sid, body in texts.items():
            wc = len(body.split())
            sub_type = (meta.get(sid, {}).get("submission_type") or "").lower()

            # Skip signal matrix for file uploads / media recordings whose
            # text could not be extracted.  word_count=0 here means the
            # pipeline can't read the file, NOT that the student was
            # disengaged.  Running the matrix would produce a false
            # "PERFUNCTORY" / disengagement signal.
            if wc == 0 and sub_type in self._FILE_SUBMISSION_TYPES:
                continue

            compound = sentiments.get(sid, {}).get("compound", 0.0)
            classifications = signal_matrix_classify(
                body, compound, wc, median_wc
            )
            name = meta.get(sid, {}).get("student_name", f"Student {sid}")
            for signal_type, cat, polarity, interpretation in classifications:
                # Find the matched text excerpt using only the category's patterns
                matched = ""
                cat_patterns = KEYWORD_CATEGORIES.get(cat, [])
                for pname in cat_patterns:
                    pat = INSIGHT_PATTERNS.get(pname)
                    if pat:
                        m = pat.search(body)
                        if m:
                            start = max(0, m.start() - 20)
                            end = min(len(body), m.end() + 20)
                            matched = body[start:end].strip()
                            break

                signals.append(ConcernSignal(
                    student_id=sid,
                    student_name=name,
                    signal_type=signal_type,
                    keyword_category=cat,
                    vader_polarity=polarity,
                    matched_text=matched,
                    interpretation=interpretation,
                ))
        return signals

    # Reference phrases for semantic reader-test detection.
    # Covers the semantic space of "student checking if teacher reads their work."
    _READER_TEST_REFERENCES = [
        "are you actually reading this?",
        "does anyone read these submissions?",
        "I wonder if my teacher will see this",
        "I bet you don't even read these",
        "does the teacher actually grade these",
        "is anyone going to read this?",
        "nobody reads these anyway",
        "testing to see if you read this",
        "I could write anything here and no one would notice",
        "has anyone actually looked at these?",
    ]
    _READER_TEST_THRESHOLD = 0.68  # cosine similarity — empirically tuned

    def _semantic_teacher_test(
        self,
        texts: Dict[str, str],
        meta: Dict[str, Dict],
    ) -> List[ConcernSignal]:
        """Semantic reader-test detection using sentence embeddings.

        Catches natural variations the regex can't anticipate
        ("has anyone actually looked at these?", etc.).
        Only runs when sentence-transformers is available.
        Complements, does not replace, the regex teacher_test pattern —
        regex hits are skipped to avoid duplicate signals.

        #LANGUAGE_JUSTICE: works across phrasings and registers, not just
        standard English formulations of "are you reading this?"
        """
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
        except ImportError:
            return []

        try:
            model = SentenceTransformer("all-MiniLM-L6-v2")
            ref_embeddings = model.encode(
                self._READER_TEST_REFERENCES, show_progress_bar=False,
                normalize_embeddings=True,
            )
        except Exception as e:
            log.debug("Semantic teacher-test init failed: %s", e)
            return []

        signals = []
        teacher_test_pat = INSIGHT_PATTERNS.get("teacher_test")

        for sid, body in texts.items():
            # Split into sentences — rough but sufficient
            sentences = [s.strip() for s in re.split(r"[.!?]+", body)
                         if len(s.strip()) > 15]
            if not sentences:
                continue

            try:
                sent_embeddings = model.encode(
                    sentences, show_progress_bar=False,
                    normalize_embeddings=True,
                )
            except Exception:
                continue

            # Cosine similarity: dot product of normalized vectors
            sim_matrix = sent_embeddings @ ref_embeddings.T  # (n_sents, n_refs)
            max_sims = sim_matrix.max(axis=1)

            for sentence, sim in zip(sentences, max_sims):
                if sim < self._READER_TEST_THRESHOLD:
                    continue
                # Skip if the regex already caught this sentence — no duplicates
                if teacher_test_pat and teacher_test_pat.search(sentence):
                    continue
                name = meta.get(sid, {}).get("student_name", f"Student {sid}")
                signals.append(ConcernSignal(
                    student_id=sid,
                    student_name=name,
                    signal_type="TEACHER NOTE",
                    keyword_category="semantic_direct_address",
                    vader_polarity="neutral",
                    matched_text=sentence[:120],
                    interpretation=(
                        f"Semantically similar to a reader-test phrase "
                        f"(similarity {sim:.2f}) — student may be checking "
                        f"if teacher reads submissions. Respond to build trust."
                    ),
                ))

        return signals
