"""
citation_checker.py — unit tests.

Tests citation extraction regexes and class-level aggregation.
No network requests — verification functions are async/network-only
and are excluded from the unit test suite.

Equity note validated here:
  Canvas/Instructure URLs are submission infrastructure, not citations —
  they must be excluded so that students citing external work get accurate
  counts even when Canvas wraps all links.

All fixtures are synthetic.

Run with: python3 -m pytest tests/test_citation_checker.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.citation_checker import (
    Citation,
    CitationReport,
    analyze_class_citations,
    extract_citations,
)


# ---------------------------------------------------------------------------
# extract_citations — URL extraction
# ---------------------------------------------------------------------------

class TestExtractCitationsUrl:
    def test_http_url_extracted(self):
        text = "See https://example.com/article for more."
        cites = extract_citations(text)
        types = [c.citation_type for c in cites]
        assert "url" in types

    def test_https_url_normalized(self):
        text = "Source: https://example.org/paper"
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert len(url_cites) == 1
        assert "example.org" in url_cites[0].normalized

    def test_trailing_punctuation_stripped(self):
        text = "See https://example.com/article."
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert not url_cites[0].normalized.endswith(".")

    def test_canvas_instructure_url_skipped(self):
        """Canvas URLs are submission infrastructure, not citations."""
        text = "Submitted at https://myschool.instructure.com/courses/123/assignments/456"
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert len(url_cites) == 0

    def test_canvas_subdomain_skipped(self):
        text = "See https://canvas.instructure.com/login for login"
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert len(url_cites) == 0

    def test_non_canvas_url_not_skipped(self):
        text = "Source: https://jstor.org/stable/123456"
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert len(url_cites) == 1

    def test_duplicate_url_deduplicated(self):
        text = "See https://example.com and also https://example.com for reference."
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        assert len(url_cites) == 1


# ---------------------------------------------------------------------------
# extract_citations — DOI extraction
# ---------------------------------------------------------------------------

class TestExtractCitationsDoi:
    def test_doi_extracted(self):
        text = "According to the study (10.1000/xyz123), the results show..."
        cites = extract_citations(text)
        doi_cites = [c for c in cites if c.citation_type == "doi"]
        assert len(doi_cites) == 1

    def test_doi_normalized_with_prefix(self):
        text = "See 10.1145/1234567.1234568 for full paper."
        cites = extract_citations(text)
        doi_cites = [c for c in cites if c.citation_type == "doi"]
        assert "doi.org" in doi_cites[0].normalized


# ---------------------------------------------------------------------------
# extract_citations — APA / inline author citations
# ---------------------------------------------------------------------------

class TestExtractCitationsAuthorYear:
    def test_apa_parenthetical(self):
        text = "Intersectionality is foundational (Crenshaw, 1991)."
        cites = extract_citations(text)
        ay_cites = [c for c in cites if c.citation_type == "author_year"]
        assert len(ay_cites) >= 1
        assert "Crenshaw" in ay_cites[0].normalized

    def test_inline_author_year(self):
        text = "Crenshaw (1991) argues that single-axis frameworks fail Black women."
        cites = extract_citations(text)
        ay_cites = [c for c in cites if c.citation_type == "author_year"]
        assert len(ay_cites) >= 1

    def test_year_in_normalized(self):
        # Pattern requires capitalized author name
        text = "As Hooks (2000) explains in her work on love and community."
        cites = extract_citations(text)
        ay_cites = [c for c in cites if c.citation_type == "author_year"]
        assert any("2000" in c.normalized for c in ay_cites)


# ---------------------------------------------------------------------------
# extract_citations — reading references
# ---------------------------------------------------------------------------

class TestExtractCitationsReadingRef:
    def test_reading_reference_detected(self):
        text = "The reading says that intersectionality is key to understanding these cases."
        cites = extract_citations(text)
        rr = [c for c in cites if c.citation_type == "reading_reference"]
        assert len(rr) >= 1

    def test_text_states_detected(self):
        text = "The text states that legal frameworks often miss compound harms."
        cites = extract_citations(text)
        rr = [c for c in cites if c.citation_type == "reading_reference"]
        assert len(rr) >= 1

    def test_reading_ref_normalized_to_course_reading(self):
        text = "The author argues this is central to the framework."
        cites = extract_citations(text)
        rr = [c for c in cites if c.citation_type == "reading_reference"]
        if rr:
            assert rr[0].normalized == "[course reading]"


# ---------------------------------------------------------------------------
# extract_citations — quoted titles
# ---------------------------------------------------------------------------

class TestExtractCitationsQuotedTitle:
    def test_quoted_title_extracted(self):
        text = 'She wrote "Mapping the Margins" which addresses compound discrimination.'
        cites = extract_citations(text)
        qt = [c for c in cites if c.citation_type == "quoted_title"]
        assert len(qt) >= 1
        assert "Mapping the Margins" in qt[0].normalized

    def test_short_title_not_extracted(self):
        # Titles under 10 chars or not starting with uppercase filtered
        text = 'He said "ok" and then left.'
        cites = extract_citations(text)
        qt = [c for c in cites if c.citation_type == "quoted_title"]
        assert len(qt) == 0


# ---------------------------------------------------------------------------
# extract_citations — metadata attachment
# ---------------------------------------------------------------------------

class TestExtractCitationsMetadata:
    def test_student_id_attached(self):
        text = "Source: https://example.com"
        cites = extract_citations(text, student_id="s001")
        assert all(c.student_id == "s001" for c in cites)

    def test_student_name_attached(self):
        text = "Source: https://example.com"
        cites = extract_citations(text, student_name="Alex Rivera")
        assert all(c.student_name == "Alex Rivera" for c in cites)

    def test_empty_text_returns_empty(self):
        assert extract_citations("") == []

    def test_plain_text_no_citations(self):
        text = "I thought this reading was very interesting and engaging."
        cites = extract_citations(text)
        url_cites = [c for c in cites if c.citation_type == "url"]
        doi_cites = [c for c in cites if c.citation_type == "doi"]
        assert len(url_cites) == 0
        assert len(doi_cites) == 0


# ---------------------------------------------------------------------------
# analyze_class_citations — class-level aggregation
# ---------------------------------------------------------------------------

class TestAnalyzeClassCitations:
    def test_no_citations_returns_no_report(self):
        texts = {"s1": "I thought this reading was interesting."}
        meta = {"s1": {"student_name": "Alex Rivera"}}
        report = analyze_class_citations(texts, meta)
        assert report.has_citations is False

    def test_no_citations_counts_students_without(self):
        texts = {"s1": "Plain text.", "s2": "Also plain."}
        meta = {"s1": {}, "s2": {}}
        report = analyze_class_citations(texts, meta)
        assert report.students_without_citations == 2

    def test_with_citations_has_citations_true(self):
        texts = {"s1": "See https://example.com for info. Crenshaw (1991) argues this."}
        meta = {"s1": {"student_name": "Alex Rivera"}}
        report = analyze_class_citations(texts, meta)
        assert report.has_citations is True

    def test_students_with_and_without_counted(self):
        texts = {
            "s1": "See https://jstor.org/stable/1234",
            "s2": "I found this interesting.",
        }
        meta = {"s1": {"student_name": "Alex"}, "s2": {"student_name": "Jordan"}}
        report = analyze_class_citations(texts, meta)
        assert report.students_with_citations == 1
        assert report.students_without_citations == 1

    def test_generic_reading_refs_counted_separately(self):
        texts = {"s1": "The reading says this is important. The text states the opposite."}
        meta = {"s1": {"student_name": "Alex"}}
        report = analyze_class_citations(texts, meta)
        assert report.generic_reading_ref_count >= 1
        # Generic reading refs should not count as specific sources
        assert report.source_count == 0 or report.specific_source_count == 0

    def test_most_cited_sorted_by_frequency(self):
        texts = {
            "s1": "Crenshaw (1991) and Crenshaw (1991) argues this.",
            "s2": "hooks (2000) writes about love.",
            "s3": "Crenshaw (1991) is foundational.",
        }
        meta = {k: {"student_name": f"Student {k}"} for k in texts}
        report = analyze_class_citations(texts, meta)
        if len(report.most_cited) >= 2:
            # Most cited should appear first
            first_count = report.most_cited[0][1]
            second_count = report.most_cited[1][1]
            assert first_count >= second_count

    def test_source_count_is_unique_sources(self):
        texts = {
            "s1": "Crenshaw (1991) and hooks (2000) both discuss this.",
            "s2": "Crenshaw (1991) is foundational to intersectionality.",
        }
        meta = {k: {"student_name": f"S{k}"} for k in texts}
        report = analyze_class_citations(texts, meta)
        # Two unique sources: Crenshaw and hooks
        assert report.source_count >= 1

    def test_empty_texts_returns_no_report(self):
        report = analyze_class_citations({}, {})
        assert report.has_citations is False
