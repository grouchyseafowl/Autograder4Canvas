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
  6. VADER sentiment per submission
  7. Embedding-based clustering (sentence-transformers + k-means/HDBSCAN)
  8. Cross-submission shared reference detection
  9. VADER+keyword signal matrix concern pre-screening

Each component degrades gracefully if its library is unavailable.
"""

import logging
import re
import statistics
from collections import Counter
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple

from insights.models import (
    ConcernSignal,
    ContradictionSignal,
    EmbeddingCluster,
    KeywordHit,
    PerSubmissionSummary,
    QuickAnalysisResult,
    SharedReference,
    SubmissionStats,
    TermFrequency,
    TermScore,
)
from insights.patterns import (
    INSIGHT_PATTERNS,
    KEYWORD_CATEGORIES,
    classify_vader_polarity,
    match_all_patterns,
    signal_matrix_classify,
)

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Common English stopwords (avoids NLTK dependency)
# ---------------------------------------------------------------------------
_STOPWORDS = frozenset(
    "a an the and or but is are was were be been being have has had do does did "
    "will would shall should may might can could i me my we our you your he she "
    "it they them their his her its this that these those am not no nor so if "
    "then than too very just about also how all each every both few more most "
    "other some such only own same than through during before after above below "
    "to from up down in out on off over under again further of at by for with "
    "as into between because until while during where when which who whom what "
    "there here why how much many any no dont didnt cant wont im ive hed shed "
    "well get got one two still even really like think know want make way much "
    "many thing things going went said says doesnt thats theres heres".split()
)


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", " ", text)


def _tokenize(text: str) -> List[str]:
    """Simple word tokenization: lowercase, alpha-only, no stopwords."""
    text = _strip_html(text)
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return [w for w in words if w not in _STOPWORDS]


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

        self._progress("Computing sentiment...")
        result.sentiments, result.sentiment_distribution = self._vader_sentiment(texts)

        self._progress("Clustering submissions...")
        result.clusters, result.embedding_outlier_ids = self._embedding_clusters(texts, meta)

        self._progress("Detecting shared references...")
        result.shared_references = self._shared_references(texts)

        self._progress("Running signal matrix...")
        median_wc = result.stats.word_count_median
        result.concern_signals = self._signal_matrix(texts, meta, result.sentiments, median_wc)

        self._progress("Detecting contradictions...")
        result.contradictions = self._detect_contradictions(
            texts, meta, result.sentiments, result.shared_references
        )

        # Build per-submission summaries
        for sid, body in texts.items():
            wc = len(body.split())
            sub_meta = meta.get(sid, {})
            cluster_id = None
            for cl in result.clusters:
                if sid in cl.student_ids:
                    cluster_id = cl.cluster_id
                    break
            vader_compound = result.sentiments.get(sid, {}).get("compound", 0.0)
            kw_hits = match_all_patterns(body)
            result.per_submission[sid] = PerSubmissionSummary(
                student_id=sid,
                student_name=sub_meta.get("student_name", f"Student {sid}"),
                word_count=wc,
                submission_type=sub_meta.get("submission_type") or "unknown",
                vader_compound=vader_compound,
                keyword_hits=kw_hits,
                cluster_id=cluster_id,
                was_translated=sub_meta.get("was_translated", False),
                was_transcribed=sub_meta.get("was_transcribed", False),
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
    # 6. VADER sentiment
    # ------------------------------------------------------------------

    def _vader_sentiment(
        self, texts: Dict[str, str]
    ) -> Tuple[Dict[str, Dict[str, float]], Dict[str, int]]:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        except ImportError:
            log.info("vaderSentiment not available — skipping sentiment")
            return {}, {}

        analyzer = SentimentIntensityAnalyzer()
        sentiments: Dict[str, Dict[str, float]] = {}
        register_counts: Dict[str, int] = Counter()

        for sid, body in texts.items():
            scores = analyzer.polarity_scores(body)
            sentiments[sid] = {
                "pos": scores["pos"],
                "neg": scores["neg"],
                "neu": scores["neu"],
                "compound": scores["compound"],
            }
            # Classify emotional register
            compound = scores["compound"]
            wc = len(body.split())
            if wc < 50 and abs(compound) < 0.2:
                register = "perfunctory"
            elif compound >= 0.3 and scores["pos"] > 0.15:
                register = "passionate"
            elif compound <= -0.3:
                register = "urgent"
            elif abs(compound) < 0.15 and scores["neu"] > 0.7:
                register = "analytical"
            elif scores["pos"] > 0.1 and "my " in body.lower():
                register = "personal"
            else:
                register = "reflective"
            register_counts[register] += 1

        return sentiments, dict(register_counts)

    # ------------------------------------------------------------------
    # 7. Embedding-based clustering
    # ------------------------------------------------------------------

    def _embedding_clusters(
        self, texts: Dict[str, str], meta: Dict[str, Dict]
    ) -> Tuple[List[EmbeddingCluster], List[str]]:
        try:
            from sentence_transformers import SentenceTransformer
            from sklearn.cluster import KMeans
            import numpy as np
        except ImportError:
            log.info("sentence-transformers/sklearn not available — skipping clustering")
            return [], []

        sids = list(texts.keys())
        docs = [texts[sid] for sid in sids]

        if len(docs) < 4:
            return [], []

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

                clusters.append(EmbeddingCluster(
                    cluster_id=cid,
                    size=len(c_sids),
                    student_ids=c_sids,
                    student_names=c_names,
                    top_terms=[t for t, _ in top],
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

            return clusters, outlier_ids

        except Exception as e:
            log.warning("Embedding clustering failed: %s", e)
            return [], []

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
            compound = sentiments.get(sid, {}).get("compound", 0.0)
            wc = len(body.split())
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
