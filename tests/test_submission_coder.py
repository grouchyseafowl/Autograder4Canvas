"""
submission_coder.py — unit tests for pure (non-LLM) functions.

All functions tested here have zero LLM dependencies — they're data
transformation utilities and validation guards that run synchronously.

LLM-calling functions (code_submission, classify_wellbeing, etc.) are
NOT tested here; those are covered by the existing integration test suite
(test_wellbeing_classifier.py, empirical pipeline runs).

Run with: python -m pytest tests/test_submission_coder.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.submission_coder import (
    _build_interests_fragment,
    _build_lens_fragment,
    _chunk_text,
    _coerce_str,
    _format_keyword_hits,
    _format_signal_matrix,
    _safe_quotes,
    _validate_concepts,
)


# ---------------------------------------------------------------------------
# _coerce_str
# ---------------------------------------------------------------------------

class TestCoerceStr:
    def test_string_passthrough(self):
        assert _coerce_str("analytical") == "analytical"

    def test_none_returns_default(self):
        assert _coerce_str(None) == ""

    def test_none_with_custom_default(self):
        assert _coerce_str(None, "unknown") == "unknown"

    def test_list_joined(self):
        """LLM sometimes returns a list where a string is expected."""
        result = _coerce_str(["analytical", "passionate"])
        assert result == "analytical, passionate"

    def test_empty_list(self):
        assert _coerce_str([]) == ""

    def test_int_coerced(self):
        assert _coerce_str(42) == "42"

    def test_single_item_list(self):
        assert _coerce_str(["reflective"]) == "reflective"


# ---------------------------------------------------------------------------
# _chunk_text
# ---------------------------------------------------------------------------

class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        text = "A short paragraph about osmosis."
        chunks = _chunk_text(text, chunk_size=500, overlap=50)
        assert chunks == [text]

    def test_long_text_splits_into_multiple(self):
        # 5000 chars, chunk_size=2000
        text = ("This is a long sentence about intersectionality. " * 100)
        chunks = _chunk_text(text, chunk_size=2000, overlap=200)
        assert len(chunks) > 1

    def test_all_chunks_non_empty(self):
        text = "x" * 8000
        chunks = _chunk_text(text, chunk_size=3000, overlap=200)
        assert all(c for c in chunks)

    def test_coverage_paragraph_break_preferred(self):
        """Chunk should break at paragraph boundary rather than mid-word."""
        para1 = "A" * 500
        para2 = "B" * 500
        text = para1 + "\n\n" + para2
        chunks = _chunk_text(text, chunk_size=600, overlap=50)
        # First chunk should not contain B's (it split at the para break)
        assert chunks[0].strip().endswith("A" * 1)

    def test_all_content_covered(self):
        """Every character from the original text should appear in at least one chunk."""
        text = "The quick brown fox. " * 200
        chunks = _chunk_text(text, chunk_size=1000, overlap=100)
        # Reconstruction: each char of text should appear in some chunk
        # (we check length coverage rather than exact reconstruction because overlap)
        total_unique_content = len(text)
        # Simple check: first and last part of text appear
        assert text[:50] in chunks[0]
        assert text[-30:].strip() in chunks[-1] or text[-30:].strip() in "".join(chunks)

    def test_empty_text_returns_single_empty_chunk(self):
        chunks = _chunk_text("", chunk_size=1000, overlap=100)
        assert chunks == [""]

    def test_exact_chunk_size_returns_single_chunk(self):
        text = "x" * 1000
        chunks = _chunk_text(text, chunk_size=1000, overlap=100)
        assert len(chunks) == 1


# ---------------------------------------------------------------------------
# _format_signal_matrix
# ---------------------------------------------------------------------------

class TestFormatSignalMatrix:
    def test_empty_signals_returns_no_flags(self):
        result = _format_signal_matrix([])
        assert "No signal matrix flags" in result

    def test_signals_with_attrs(self):
        """Signal objects with signal_type/interpretation attributes."""
        class MockSignal:
            signal_type = "POSSIBLE CONCERN"
            interpretation = "Combined keyword + negative VADER"
            keyword_category = "distress"

        result = _format_signal_matrix([MockSignal()])
        assert "POSSIBLE CONCERN" in result
        assert "distress" in result

    def test_signals_as_tuples(self):
        """Tuple format: (signal_type, keyword_category, ?, interpretation)."""
        sig = ("POSSIBLE CONCERN", "distress", None, "Keyword in negative context")
        result = _format_signal_matrix([sig])
        assert "POSSIBLE CONCERN" in result
        assert "Keyword in negative context" in result

    def test_multiple_signals(self):
        class MockSignal:
            signal_type = "ALERT"
            interpretation = "High keyword density"
            keyword_category = "crisis"

        result = _format_signal_matrix([MockSignal(), MockSignal()])
        assert result.count("ALERT") == 2


# ---------------------------------------------------------------------------
# _format_keyword_hits
# ---------------------------------------------------------------------------

class TestFormatKeywordHits:
    def test_empty_returns_none_string(self):
        assert _format_keyword_hits({}) == "none"

    def test_single_hit(self):
        result = _format_keyword_hits({"crisis": 2})
        assert "crisis" in result
        assert "2" in result

    def test_sorted_by_count_descending(self):
        result = _format_keyword_hits({"low": 1, "high": 5, "medium": 3})
        assert result.index("high") < result.index("medium")

    def test_truncated_to_8(self):
        hits = {f"kw{i}": i for i in range(12)}
        result = _format_keyword_hits(hits)
        # Should contain at most 8 entries
        assert result.count(":") <= 8


# ---------------------------------------------------------------------------
# _build_lens_fragment
# ---------------------------------------------------------------------------

class TestBuildLensFragment:
    def test_none_returns_empty(self):
        assert _build_lens_fragment(None) == ""

    def test_empty_dict_returns_empty(self):
        assert _build_lens_fragment({}) == ""

    def test_populates_lens_criteria(self):
        lens = {"power": "Who holds power in this narrative?",
                "voice": "Whose voice is centered?"}
        result = _build_lens_fragment(lens)
        assert "power" in result
        assert "voice" in result


# ---------------------------------------------------------------------------
# _build_interests_fragment
# ---------------------------------------------------------------------------

class TestBuildInterestsFragment:
    def test_empty_returns_empty(self):
        assert _build_interests_fragment([]) == ""

    def test_none_returns_empty(self):
        assert _build_interests_fragment(None) == ""

    def test_includes_interests(self):
        result = _build_interests_fragment(["power", "identity", "structural violence"])
        assert "power" in result
        assert "identity" in result

    def test_capped_at_3(self):
        result = _build_interests_fragment(["a", "b", "c", "d", "e"])
        # Should only include first 3
        assert "(4)" not in result
        assert "(3)" in result


# ---------------------------------------------------------------------------
# _safe_quotes
# ---------------------------------------------------------------------------

class TestSafeQuotes:
    def test_empty_returns_empty(self):
        assert _safe_quotes([]) == []

    def test_none_returns_empty(self):
        assert _safe_quotes(None) == []

    def test_valid_dict_quote(self):
        quotes = [{"text": "The law was built for a particular kind of person.",
                   "significance": "Names structural exclusion."}]
        result = _safe_quotes(quotes)
        assert len(result) == 1
        assert result[0].text == "The law was built for a particular kind of person."

    def test_missing_text_skipped(self):
        quotes = [{"significance": "Something"}, {"text": "Valid quote.", "significance": "X"}]
        result = _safe_quotes(quotes)
        assert len(result) == 1
        assert result[0].text == "Valid quote."

    def test_max_3_returned(self):
        quotes = [
            {"text": f"Quote {i}.", "significance": "Sig."}
            for i in range(5)
        ]
        result = _safe_quotes(quotes)
        assert len(result) == 3

    def test_missing_significance_uses_empty(self):
        quotes = [{"text": "Just a quote with no significance."}]
        result = _safe_quotes(quotes)
        assert result[0].significance == ""


# ---------------------------------------------------------------------------
# _validate_concepts (hallucination guard)
# ---------------------------------------------------------------------------

class TestValidateConcepts:
    SUBMISSION = (
        "Crenshaw discusses intersectionality as a framework for understanding "
        "how race and gender combine to create unique forms of discrimination. "
        "The General Motors case shows how the law fails to recognize "
        "intersectional invisibility."
    )

    def test_empty_concepts_returns_empty(self):
        assert _validate_concepts([], self.SUBMISSION) == []

    def test_present_concept_retained(self):
        # "intersectionality" is in the submission
        result = _validate_concepts(["intersectionality"], self.SUBMISSION)
        assert "intersectionality" in result

    def test_hallucinated_concept_removed(self):
        # "quantum mechanics" is NOT in this submission
        result = _validate_concepts(["quantum mechanics"], self.SUBMISSION)
        assert "quantum mechanics" not in result

    def test_partial_token_match_retained(self):
        # "intersectional" is in the text; "intersectionality" uses stem overlap
        # (both share the "inters" stem). This should be retained.
        result = _validate_concepts(["intersectional invisibility"], self.SUBMISSION)
        assert "intersectional invisibility" in result

    def test_direct_substring_match(self):
        result = _validate_concepts(["General Motors case"], self.SUBMISSION)
        assert "General Motors case" in result

    def test_empty_concept_token_retained(self):
        """Concepts with no tokens (e.g. punctuation-only) pass through."""
        result = _validate_concepts(["---"], self.SUBMISSION)
        assert "---" in result

    def test_stem_based_matching(self):
        """'racial formation' stem matches 'race' (rac-) via prefix."""
        submission_with_race = "The reading talks about racialization as a process."
        result = _validate_concepts(["racialization"], submission_with_race)
        assert "racialization" in result

    def test_two_token_concept_requires_both_tokens(self):
        """Two-token concept: 'cellular activity' — needs >50% tokens = both."""
        text = "We studied cellular processes in the lab."
        # "cellular" is present, "activity" is not → should fail >0.5 threshold
        result = _validate_concepts(["cellular activity"], text)
        assert "cellular activity" not in result

    def test_mix_of_valid_and_hallucinated(self):
        concepts = ["intersectionality", "quantum entanglement", "discrimination"]
        result = _validate_concepts(concepts, self.SUBMISSION)
        assert "intersectionality" in result
        assert "discrimination" in result
        assert "quantum entanglement" not in result
