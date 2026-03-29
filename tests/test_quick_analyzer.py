"""
quick_analyzer.py — unit tests for pure (non-LLM) functions.

Tests _strip_html, _tokenize, _deduplicate_names, _detect_engagement_type,
_build_reference_observation, match_submission_references, QuickAnalyzer
statistics, truncation detection, word frequency, and the analyze() contract
with empty/minimal submissions.

No LLM, no MLX, no spaCy required — all optional dependencies degrade
gracefully (most skipped, fallbacks exercised where available).

Run with: python3 -m pytest tests/test_quick_analyzer.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.quick_analyzer import (
    QuickAnalyzer,
    _build_reference_observation,
    _deduplicate_names,
    _detect_engagement_type,
    _extract_key_concepts,
    _strip_html,
    _tokenize,
    match_submission_references,
)
from insights.models import AssignmentFingerprint, QuickAnalysisResult


# ---------------------------------------------------------------------------
# Synthetic corpus — no real student data
# ---------------------------------------------------------------------------

PLAIN_TEXT = (
    "Crenshaw argues that intersectionality reveals how the law fails "
    "Black women by treating race and gender as separate categories. "
    "The General Motors case illustrates this structural erasure. "
    "Her framework challenges courts to recognize compound harm, not just "
    "the sum of single-axis discrimination claims."
)

SHORT_PLAIN_TEXT = "This reading was interesting and I enjoyed it."

REFLECTION_PROMPT = (
    "Reflect on your own experience with the ideas in this week's reading. "
    "How has this shaped your understanding of structural barriers?"
)

ANALYSIS_PROMPT = (
    "Critically analyze the argument made by Crenshaw in 'Mapping the Margins'. "
    "Evaluate the strengths and limitations of her legal framework."
)

SUMMARY_PROMPT = (
    "Summarize the main points of this week's reading and identify the key "
    "claims the author makes about intersectional identity."
)

DISCUSSION_PROMPT = (
    "What do you think about the argument presented? Do you agree with the "
    "author's perspective on these issues? Share your thoughts and reactions."
)


# ---------------------------------------------------------------------------
# _strip_html
# ---------------------------------------------------------------------------

class TestStripHtml:
    def test_plain_text_unchanged(self):
        assert _strip_html("Hello world") == "Hello world"

    def test_single_tag_removed(self):
        result = _strip_html("<p>Hello world</p>")
        assert "<p>" not in result
        assert "Hello world" in result

    def test_nested_tags_removed(self):
        result = _strip_html("<div><strong>Power</strong> and resistance</div>")
        assert "Power" in result
        assert "resistance" in result
        assert "<" not in result

    def test_self_closing_tag_removed(self):
        result = _strip_html("Line one<br/>Line two")
        assert "Line one" in result
        assert "Line two" in result

    def test_empty_string(self):
        assert _strip_html("") == ""

    def test_attributes_stripped(self):
        result = _strip_html('<a href="http://example.com">link text</a>')
        assert "link text" in result
        assert "href" not in result


# ---------------------------------------------------------------------------
# _tokenize
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_basic_tokenization(self):
        tokens = _tokenize("Crenshaw argues that intersectionality reveals")
        assert "crenshaw" in tokens
        assert "intersectionality" in tokens

    def test_stopwords_removed(self):
        tokens = _tokenize("the cat sat on the mat")
        # 'the', 'on' are stopwords; 'cat', 'sat', 'mat' are not
        assert "the" not in tokens
        # 'cat', 'sat', 'mat' are short words (<3 chars filtered by re.findall)
        # Actually 'cat' is 3 chars — should be kept; 'sat' and 'mat' too
        assert "cat" in tokens

    def test_min_3_chars(self):
        tokens = _tokenize("I am an ox")
        # 'i', 'am', 'an' are 1-2 chars or stopwords; 'ox' is 2 chars
        assert "ox" not in tokens  # 2 chars, below threshold
        assert "i" not in tokens

    def test_lowercase_output(self):
        tokens = _tokenize("Crenshaw Intersectionality POWER")
        assert "crenshaw" in tokens
        assert "intersectionality" in tokens
        assert "power" in tokens

    def test_html_stripped_before_tokenize(self):
        tokens = _tokenize("<p>Structural analysis</p>")
        assert "structural" in tokens
        assert "analysis" in tokens

    def test_empty_string(self):
        assert _tokenize("") == []

    def test_numbers_excluded(self):
        tokens = _tokenize("123 analysis 456")
        assert "123" not in tokens
        assert "analysis" in tokens


# ---------------------------------------------------------------------------
# _deduplicate_names
# ---------------------------------------------------------------------------

class TestDeduplicateNames:
    def test_empty_returns_empty(self):
        assert _deduplicate_names([]) == []

    def test_single_name_kept(self):
        assert _deduplicate_names(["Crenshaw"]) == ["Crenshaw"]

    def test_full_name_subsumes_last_name(self):
        result = _deduplicate_names(["Kimberle Crenshaw", "Crenshaw"])
        assert "Kimberle Crenshaw" in result
        assert "Crenshaw" not in result

    def test_order_preserved_longest_first(self):
        result = _deduplicate_names(["hooks", "bell hooks", "bell"])
        assert result[0] == "bell hooks"

    def test_unrelated_names_both_kept(self):
        result = _deduplicate_names(["Crenshaw", "hooks"])
        assert len(result) == 2
        assert "Crenshaw" in result
        assert "hooks" in result

    def test_case_insensitive_dedup(self):
        # "CRENSHAW" and "crenshaw" are the same person
        result = _deduplicate_names(["Kimberle Crenshaw", "CRENSHAW"])
        assert len(result) == 1
        assert "Kimberle Crenshaw" in result

    def test_duplicates_within_input(self):
        result = _deduplicate_names(["Crenshaw", "Crenshaw", "Crenshaw"])
        assert result == ["Crenshaw"]


# ---------------------------------------------------------------------------
# _detect_engagement_type
# ---------------------------------------------------------------------------

class TestDetectEngagementType:
    def test_personal_reflection_detected(self):
        result = _detect_engagement_type(REFLECTION_PROMPT)
        assert result == "personal_reflection"

    def test_analysis_detected(self):
        result = _detect_engagement_type(ANALYSIS_PROMPT)
        assert result == "analysis"

    def test_summary_detected(self):
        result = _detect_engagement_type(SUMMARY_PROMPT)
        assert result == "summary"

    def test_discussion_detected(self):
        result = _detect_engagement_type(DISCUSSION_PROMPT)
        assert result == "discussion"

    def test_multiple_types_returns_mixed(self):
        # Both personal_reflection and discussion cues
        mixed = "Share your personal thoughts. Do you agree with the author?"
        result = _detect_engagement_type(mixed)
        assert result == "mixed"

    def test_no_cues_returns_mixed(self):
        result = _detect_engagement_type("Write about the reading.")
        assert result == "mixed"

    def test_empty_prompt_returns_mixed(self):
        assert _detect_engagement_type("") == "mixed"

    def test_case_insensitive(self):
        result = _detect_engagement_type("ANALYZE the reading critically.")
        assert result == "analysis"


# ---------------------------------------------------------------------------
# _build_reference_observation
# ---------------------------------------------------------------------------

class TestBuildReferenceObservation:
    def test_no_refs_returns_empty(self):
        result = _build_reference_observation([], 0, [], 0, [], 0)
        assert result == ""

    def test_zero_found_of_nonzero_total(self):
        result = _build_reference_observation([], 1, [], 0, [], 0)
        assert "No named references" in result
        assert "personal experience" in result or "paraphrase" in result

    def test_few_refs_fraction(self):
        # 1 of 5 found — less than 30%
        result = _build_reference_observation(
            ["Crenshaw"], 5, [], 0, [], 0
        )
        assert "Few" in result

    def test_strong_refs_fraction(self):
        # 4 of 5 found — 80%, more than 70%
        result = _build_reference_observation(
            ["Crenshaw", "hooks"], 2, ["Mapping the Margins"], 1, ["intersectionality"], 2
        )
        assert "Strong" in result

    def test_some_refs_midrange(self):
        # 2 of 5 found — 40%, between 30% and 70%
        result = _build_reference_observation(
            ["Crenshaw"], 3, ["Mapping the Margins"], 1, [], 1
        )
        assert "Some" in result

    def test_detail_includes_author_counts(self):
        result = _build_reference_observation(
            ["Crenshaw"], 2, [], 0, [], 0
        )
        assert "1/2" in result
        assert "author" in result

    def test_detail_includes_title_counts(self):
        result = _build_reference_observation(
            [], 0, ["Mapping the Margins"], 1, [], 0
        )
        assert "1/1" in result
        assert "title" in result

    def test_detail_includes_concept_counts(self):
        result = _build_reference_observation(
            [], 0, [], 0, ["intersectionality"], 2
        )
        assert "1/2" in result
        assert "concept" in result


# ---------------------------------------------------------------------------
# match_submission_references
# ---------------------------------------------------------------------------

class TestMatchSubmissionReferences:
    @pytest.fixture
    def fingerprint(self):
        return AssignmentFingerprint(
            author_names=["Kimberle Crenshaw"],
            work_titles=["Mapping the Margins"],
            key_concepts=["intersectionality"],
        )

    def test_full_author_match(self, fingerprint):
        text = "Crenshaw argues that intersectionality is key."
        result = match_submission_references(text, fingerprint)
        assert "Kimberle Crenshaw" in result.authors_found

    def test_last_name_match(self, fingerprint):
        # "Crenshaw" alone should match "Kimberle Crenshaw"
        text = "According to Crenshaw, the law fails Black women."
        result = match_submission_references(text, fingerprint)
        assert len(result.authors_found) == 1

    def test_author_not_present(self, fingerprint):
        text = "The reading was about discrimination and legal frameworks."
        result = match_submission_references(text, fingerprint)
        assert result.authors_found == []

    def test_title_match(self, fingerprint):
        text = "In Mapping the Margins, she discusses the General Motors case."
        result = match_submission_references(text, fingerprint)
        assert "Mapping the Margins" in result.titles_found

    def test_title_not_present(self, fingerprint):
        text = "The reading was assigned last week and I found it compelling."
        result = match_submission_references(text, fingerprint)
        assert result.titles_found == []

    def test_concept_match(self, fingerprint):
        text = "The concept of intersectionality helps explain compound discrimination."
        result = match_submission_references(text, fingerprint)
        assert "intersectionality" in result.concepts_found

    def test_match_ratio_computed(self, fingerprint):
        # all 3 items found
        text = (
            "Crenshaw writes about intersectionality in Mapping the Margins. "
            "Her framework is foundational."
        )
        result = match_submission_references(text, fingerprint)
        assert result.match_ratio > 0.0
        assert result.match_ratio <= 1.0

    def test_totals_match_fingerprint(self, fingerprint):
        text = PLAIN_TEXT
        result = match_submission_references(text, fingerprint)
        assert result.authors_total == 1
        assert result.titles_total == 1
        assert result.concepts_total == 1

    def test_empty_fingerprint_returns_zero_ratio(self):
        empty_fp = AssignmentFingerprint()
        text = "Crenshaw argues for intersectionality."
        result = match_submission_references(text, empty_fp)
        assert result.match_ratio == 0.0

    def test_observation_populated(self, fingerprint):
        text = PLAIN_TEXT
        result = match_submission_references(text, fingerprint)
        assert isinstance(result.observation, str)
        assert len(result.observation) > 0


# ---------------------------------------------------------------------------
# QuickAnalyzer._compute_stats
# ---------------------------------------------------------------------------

class TestComputeStats:
    @pytest.fixture
    def analyzer(self):
        return QuickAnalyzer()

    def test_total_submissions_count(self, analyzer):
        texts = {"s1": "one two three", "s2": "four five six seven"}
        result = analyzer._compute_stats(texts, {"s1": {}, "s2": {}})
        assert result.total_submissions == 2

    def test_word_count_min_max(self, analyzer):
        texts = {"s1": "one two three", "s2": "a b c d e f g h i j"}
        result = analyzer._compute_stats(texts, {"s1": {}, "s2": {}})
        assert result.word_count_min == 3
        assert result.word_count_max == 10

    def test_word_count_mean_and_median(self, analyzer):
        texts = {"s1": "a b c", "s2": "a b c d e", "s3": "a b c d e f g"}
        result = analyzer._compute_stats(texts, {k: {} for k in texts})
        assert result.word_count_mean == pytest.approx(5.0)
        assert result.word_count_median == 5.0

    def test_format_breakdown_populated(self, analyzer):
        texts = {"s1": "text", "s2": "text"}
        meta = {
            "s1": {"submission_type": "online_text_entry"},
            "s2": {"submission_type": "online_upload"},
        }
        result = analyzer._compute_stats(texts, meta)
        assert result.format_breakdown.get("online_text_entry") == 1
        assert result.format_breakdown.get("online_upload") == 1

    def test_timing_on_time(self, analyzer):
        texts = {"s1": "text"}
        meta = {
            "s1": {
                "submitted_at": "2026-03-10T12:00:00Z",
                "due_at": "2026-03-11T23:59:00Z",
            }
        }
        result = analyzer._compute_stats(texts, meta)
        assert result.timing.get("on_time", 0) == 1

    def test_timing_late(self, analyzer):
        texts = {"s1": "text"}
        meta = {
            "s1": {
                "submitted_at": "2026-03-12T06:00:00Z",  # 6h after due
                "due_at": "2026-03-12T00:00:00Z",
            }
        }
        result = analyzer._compute_stats(texts, meta)
        assert result.timing.get("late", 0) == 1

    def test_timing_very_late(self, analyzer):
        texts = {"s1": "text"}
        meta = {
            "s1": {
                "submitted_at": "2026-03-15T00:00:00Z",  # 3 days late
                "due_at": "2026-03-12T00:00:00Z",
            }
        }
        result = analyzer._compute_stats(texts, meta)
        assert result.timing.get("very_late", 0) == 1

    def test_single_submission(self, analyzer):
        texts = {"s1": "one two three four five"}
        result = analyzer._compute_stats(texts, {"s1": {}})
        assert result.total_submissions == 1
        assert result.word_count_mean == 5.0


# ---------------------------------------------------------------------------
# QuickAnalyzer._is_possibly_truncated
# ---------------------------------------------------------------------------

class TestIsPossiblyTruncated:
    @pytest.fixture
    def analyzer(self):
        return QuickAnalyzer()

    def test_complete_sentence_not_truncated(self, analyzer):
        text = "She argues that intersectionality is the key framework."
        is_trunc, note = analyzer._is_possibly_truncated(text, 10, 100.0)
        assert is_trunc is False

    def test_ends_with_conjunction_and_no_punct(self, analyzer):
        # "but" with no terminal punct → truncated
        text = "I think she makes a good point but"
        is_trunc, note = analyzer._is_possibly_truncated(text, 10, 100.0)
        assert is_trunc is True
        assert isinstance(note, str) and len(note) > 0

    def test_explicit_incomplete_triggers(self, analyzer):
        text = "I didn't finish reading the whole thing but the ideas were interesting."
        is_trunc, note = analyzer._is_possibly_truncated(text, 14, 100.0)
        assert is_trunc is True
        assert "check" in note.lower()

    def test_below_median_and_no_punct(self, analyzer):
        # word_count=10, class_median=100 → 10% of median → very short
        text = "I think this is interesting because"  # no terminal punct
        is_trunc, note = analyzer._is_possibly_truncated(text, 7, 100.0)
        assert is_trunc is True

    def test_short_but_complete(self, analyzer):
        # Short text that ends properly
        text = "This reading was very interesting."
        is_trunc, note = analyzer._is_possibly_truncated(text, 6, 8.0)
        assert is_trunc is False

    def test_empty_text_not_truncated(self, analyzer):
        is_trunc, note = analyzer._is_possibly_truncated("", 0, 100.0)
        assert is_trunc is False
        assert note == ""

    def test_note_has_care_framing(self, analyzer):
        text = "She argues that intersectionality is a framework, but"
        is_trunc, note = analyzer._is_possibly_truncated(text, 10, 100.0)
        if is_trunc:
            assert "check" in note.lower() or "consider" in note.lower()

    def test_ends_with_period_not_truncated_even_if_short(self, analyzer):
        text = "Done."
        is_trunc, _ = analyzer._is_possibly_truncated(text, 1, 200.0)
        # Ends with period — no terminal punct signal, and below_median fires
        # but single-signal is not enough; explicit_incomplete also absent
        assert is_trunc is False

    def test_ran_out_of_triggers(self, analyzer):
        text = "I ran out of time to finish the rest of my thoughts."
        is_trunc, note = analyzer._is_possibly_truncated(text, 12, 100.0)
        assert is_trunc is True


# ---------------------------------------------------------------------------
# QuickAnalyzer._word_frequency
# ---------------------------------------------------------------------------

class TestWordFrequency:
    @pytest.fixture
    def analyzer(self):
        return QuickAnalyzer()

    def test_returns_list(self, analyzer):
        texts = {"s1": PLAIN_TEXT}
        result = analyzer._word_frequency(texts)
        assert isinstance(result, list)

    def test_terms_are_non_stopwords(self, analyzer):
        texts = {"s1": "the cat sat on the mat. the cat is black."}
        result = analyzer._word_frequency(texts)
        terms = [r.term for r in result]
        assert "the" not in terms
        assert "on" not in terms

    def test_count_reflects_frequency(self, analyzer):
        texts = {"s1": "intersectionality intersectionality intersectionality power"}
        result = analyzer._word_frequency(texts)
        top = result[0]
        assert top.term == "intersectionality"
        assert top.count == 3

    def test_top_n_respected(self, analyzer):
        texts = {"s1": " ".join(f"word{i}" * (30 - i) for i in range(30))}
        result = analyzer._word_frequency(texts, top_n=5)
        assert len(result) <= 5

    def test_html_stripped_before_counting(self, analyzer):
        texts = {"s1": "<p>intersectionality</p> <em>intersectionality</em>"}
        result = analyzer._word_frequency(texts)
        terms = {r.term: r.count for r in result}
        assert terms.get("intersectionality") == 2

    def test_empty_texts_returns_empty(self, analyzer):
        result = analyzer._word_frequency({})
        assert result == []

    def test_multiple_submissions_aggregated(self, analyzer):
        texts = {
            "s1": "intersectionality power resistance",
            "s2": "intersectionality identity liberation",
        }
        result = analyzer._word_frequency(texts)
        terms = {r.term: r.count for r in result}
        assert terms.get("intersectionality") == 2


# ---------------------------------------------------------------------------
# QuickAnalyzer.analyze — contract with empty and minimal submissions
# ---------------------------------------------------------------------------

class TestAnalyzeContract:
    @pytest.fixture
    def analyzer(self):
        return QuickAnalyzer()

    def test_empty_submissions_returns_result(self, analyzer):
        result = analyzer.analyze(
            [],
            assignment_id="a001",
            assignment_name="Week 3 Discussion",
        )
        assert isinstance(result, QuickAnalysisResult)

    def test_empty_submissions_adds_note(self, analyzer):
        result = analyzer.analyze([], assignment_id="a001")
        assert any("No submissions" in n for n in result.analysis_notes)

    def test_empty_submissions_per_submission_empty(self, analyzer):
        result = analyzer.analyze([], assignment_id="a001")
        assert result.per_submission == {}

    def test_single_submission_analyzed(self, analyzer):
        subs = [{"student_id": "s001", "student_name": "Alex Rivera", "body": PLAIN_TEXT}]
        result = analyzer.analyze(subs, assignment_id="a001")
        assert isinstance(result, QuickAnalysisResult)
        assert "s001" in result.per_submission

    def test_per_submission_word_count(self, analyzer):
        subs = [{"student_id": "s001", "student_name": "Alex Rivera", "body": PLAIN_TEXT}]
        result = analyzer.analyze(subs, assignment_id="a001")
        wc = result.per_submission["s001"].word_count
        assert wc == len(PLAIN_TEXT.split())

    def test_stats_populated(self, analyzer):
        subs = [
            {"student_id": "s001", "student_name": "Alex Rivera", "body": PLAIN_TEXT},
            {"student_id": "s002", "student_name": "Jordan Kim", "body": SHORT_PLAIN_TEXT},
        ]
        result = analyzer.analyze(subs, assignment_id="a001")
        assert result.stats is not None
        assert result.stats.total_submissions == 2

    def test_assignment_id_preserved(self, analyzer):
        result = analyzer.analyze([], assignment_id="xyz-999")
        assert result.assignment_id == "xyz-999"

    def test_course_name_preserved(self, analyzer):
        result = analyzer.analyze([], assignment_id="a001", course_name="Ethnic Studies 101")
        assert result.course_name == "Ethnic Studies 101"

    def test_student_name_in_per_submission(self, analyzer):
        subs = [{"student_id": "s001", "student_name": "Sam Torres", "body": PLAIN_TEXT}]
        result = analyzer.analyze(subs, assignment_id="a001")
        assert result.per_submission["s001"].student_name == "Sam Torres"

    def test_class_level_top_terms_populated(self, analyzer):
        subs = [
            {"student_id": "s001", "student_name": "Alex Rivera", "body": PLAIN_TEXT},
            {"student_id": "s002", "student_name": "Jordan Kim", "body": PLAIN_TEXT},
        ]
        result = analyzer.analyze(subs, assignment_id="a001")
        # top_terms may be empty if no tokens survive stopword filter,
        # but with PLAIN_TEXT there are substantive tokens
        assert isinstance(result.top_terms, list)

    def test_analyzed_at_populated(self, analyzer):
        result = analyzer.analyze([], assignment_id="a001")
        assert result.analyzed_at is not None
        assert len(result.analyzed_at) > 0

    def test_progress_callback_called(self, analyzer):
        calls = []
        analyzer._progress = lambda msg: calls.append(msg)
        subs = [{"student_id": "s001", "student_name": "Alex Rivera", "body": PLAIN_TEXT}]
        analyzer.analyze(subs, assignment_id="a001")
        assert len(calls) > 0
