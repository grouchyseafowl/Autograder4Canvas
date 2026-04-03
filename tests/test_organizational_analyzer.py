"""
organizational_analyzer.py — unit tests.

Tests OrganizationalAnalyzer pure math: header detection, section balance,
paragraph uniformity, sentence uniformity, Phase A engagement signals
(starter_diversity, comma_density, avg_word_length), and circular reference
detection.

Design equity principle validated here:
  #LANGUAGE_JUSTICE: comma_density and avg_word_length are corroboration-only.
  They must NOT be included in total_ai_organizational_score because:
  - High comma density can reflect formal ESL academic writing style.
  - High avg word length correlates with education level and reading exposure.
  Penalizing these signals standalone would harm specific student populations.

  #ALGORITHMIC_JUSTICE: The neurodivergent-aware distinction is headers +
  UNIFORM section depth (AI signature) versus headers + UNEVEN section depth
  (scaffolding). Tests verify this distinction is correctly encoded.

All fixtures are synthetic. No LLM, no MLX, no Canvas.

Implementation note: _analyze_section_balance and _analyze_paragraph_uniformity
return numpy booleans (result of numpy comparison operators). Tests use truthiness
checks rather than `is True/False` identity checks to handle both cases.

Run with: python3 -m pytest tests/test_organizational_analyzer.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from modules.organizational_analyzer import (
    OrganizationalAnalysis,
    OrganizationalAnalyzer,
    analyze_organizational_patterns,
)


# ---------------------------------------------------------------------------
# Synthetic text corpus
# ---------------------------------------------------------------------------

# Short text (< 500 words) with 3 markdown headers — triggers excessive_headers
EXCESSIVE_HEADERS_TEXT = (
    "# Introduction\n"
    "This section introduces the topic with some brief words about the subject matter.\n\n"
    "# Method\n"
    "Here we describe the method used in this analysis of the given material and context.\n\n"
    "# Conclusion\n"
    "Finally, we conclude with a summary of what was discussed in the previous two sections.\n"
)

# Text with h3 depth (depth 3, < 2000 words) — triggers hierarchical_headers
HIERARCHICAL_HEADERS_TEXT = (
    "# Main Section\n"
    "Some content here to establish context for the analysis.\n\n"
    "## Subsection\n"
    "More content going into detail about a specific aspect.\n\n"
    "### Sub-subsection\n"
    "Even deeper content here, reaching the third level of hierarchy.\n"
)

# Two headers with roughly equal-length sections — triggers balanced_sections
UNIFORM_SECTIONS_TEXT = (
    "# First Section\n"
    "The quick brown fox jumps over the lazy dog and the cat sat on the mat.\n"
    "These sentences have a similar number of words arranged in a balanced way.\n\n"
    "# Second Section\n"
    "A different set of words arranged in a similarly balanced and uniform pattern.\n"
    "The content is varied but the length of each section is approximately equal.\n"
)

# Two headers with very different section lengths — hyperfocus on one section
NONUNIFORM_SECTIONS_TEXT = (
    "# Brief Note\n"
    "Just two words.\n\n"
    "# Deep Analysis\n"
    "This section goes into extensive detail about the topic because I find it fascinating.\n"
    "There are so many interesting aspects to explore here, from the historical context\n"
    "to the contemporary applications, and I want to make sure I cover all of them\n"
    "thoroughly. The nuance in this area is remarkable and deserves careful attention.\n"
    "The implications for practice are significant and often overlooked in standard\n"
    "treatments of the subject. I could write about this for hours because it connects\n"
    "to so many things I care about deeply. The intersections with other fields are\n"
    "particularly rich territory for exploration and discovery and deserve more attention.\n"
)

# Plain prose, no headers — baseline neutral text
PLAIN_PROSE = (
    "Intersectionality is a framework developed by Kimberlé Crenshaw to describe\n"
    "how multiple social identities overlap and interact in ways that produce\n"
    "compounded forms of discrimination. The legal system often fails to account\n"
    "for the ways in which race and gender combine to create unique vulnerabilities.\n\n"
    "I found this reading challenging but important. The case studies made abstract\n"
    "theory concrete. It changed how I think about fairness in legal systems.\n"
)

# 9 sentences with all unique first words — triggers starter_diversity_score
HIGH_STARTER_DIVERSITY_TEXT = (
    "Actually, this is an important point worth considering carefully.\n"
    "Because intersectionality matters, we should pay close attention here.\n"
    "Critically, the legal framework fails in this specific context.\n"
    "Despite appearances, the situation is considerably more complex than presented.\n"
    "Even within communities, there are important divisions worth examining.\n"
    "Finally, we must acknowledge the structural factors at play.\n"
    "Generally speaking, the research broadly supports this analytical view.\n"
    "However, there are several important exceptions that deserve careful note.\n"
    "Indeed, the evidence is quite compelling when examined more carefully.\n"
)

# 5 sentences with high comma density (> 5.0 per 100 words).
# Needed because comma_density is only computed when sentence_count >= 5.
HIGH_COMMA_DENSITY_5SENT = (
    "Intersectionality, as Crenshaw argues, operates across legal, social, and economic dimensions. "
    "The legal framework, which was designed for single-axis analysis, fails compound harms entirely. "
    "Race and gender, when combined, produce unique, compounded, and invisible forms of discrimination. "
    "Black women, for instance, fall through both race law and gender law simultaneously. "
    "A framework, however well-intentioned, cannot address harms it was, by default, designed to ignore."
)

# 5 sentences with high average word length (> 5 chars per word).
# Needed because avg_word_length is only computed when sentence_count >= 5.
HIGH_AVG_WORD_LENGTH_5SENT = (
    "Intersectionality demonstrates multidimensional understanding of discrimination systematically. "
    "Institutional frameworks undermine representation and recognition in contemporary jurisprudence. "
    "Methodological considerations fundamentally determine interpretive possibilities for practitioners. "
    "Structural conditions generate differential opportunities for historically marginalized populations. "
    "Interdisciplinary perspectives illuminate intersectional vulnerabilities within established frameworks."
)

# Uniform sentences — all approx 9 words each
UNIFORM_SENTENCES_TEXT = (
    "This sentence has exactly nine words in total here.\n"
    "Another sentence also has approximately nine words in it.\n"
    "The third sentence continues with nine similar words here.\n"
    "Fourth sentence maintains this consistent pattern of nine words.\n"
    "Fifth sentence has the same rhythm and nine words.\n"
    "Sixth sentence follows this established pattern of nine words.\n"
    "Seventh sentence also maintains approximately nine words per line.\n"
    "Eighth sentence concludes this uniform pattern of nine words.\n"
)


# ---------------------------------------------------------------------------
# analyze() — output contract
# ---------------------------------------------------------------------------

class TestAnalyzeContract:
    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_returns_organizational_analysis(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        assert isinstance(result, OrganizationalAnalysis)

    def test_all_fields_present(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        for field in ("excessive_headers", "excessive_headers_score",
                      "hierarchical_headers", "hierarchical_headers_score",
                      "balanced_sections", "balanced_sections_score",
                      "uniform_paragraphs", "uniform_paragraphs_score",
                      "uniform_sentences", "uniform_sentences_score",
                      "starter_diversity_score", "comma_density_score",
                      "avg_word_length_score", "total_ai_organizational_score"):
            assert hasattr(result, field), f"Missing field: {field}"

    def test_total_score_nonnegative(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        assert result.total_ai_organizational_score >= 0.0

    def test_empty_text_returns_result(self, analyzer):
        result = analyzer.analyze("")
        assert isinstance(result, OrganizationalAnalysis)
        assert result.total_ai_organizational_score == 0.0

    def test_details_dict_present(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        assert isinstance(result.details, dict)

    def test_convenience_function_matches_analyzer(self, analyzer):
        direct = analyzer.analyze(PLAIN_PROSE)
        via_func = analyze_organizational_patterns(PLAIN_PROSE)
        assert via_func.total_ai_organizational_score == direct.total_ai_organizational_score
        assert via_func.excessive_headers == direct.excessive_headers


# ---------------------------------------------------------------------------
# Header detection
# ---------------------------------------------------------------------------

class TestHeaderDetection:
    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_excessive_headers_detected(self, analyzer):
        """3 headers in < 500 words → excessive (threshold is > 2)."""
        result = analyzer.analyze(EXCESSIVE_HEADERS_TEXT)
        assert result.excessive_headers
        assert result.excessive_headers_score > 0

    def test_no_headers_not_excessive(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        assert not result.excessive_headers
        assert result.excessive_headers_score == 0.0

    def test_two_headers_in_short_text_not_excessive(self, analyzer):
        """2 headers is at threshold (> 2 required) — not excessive."""
        text = "# H1\nSome content here for testing purposes.\n\n# H2\nMore content here.\n"
        result = analyzer.analyze(text)
        assert not result.excessive_headers

    def test_three_headers_in_short_text_excessive(self, analyzer):
        text = "# H1\nShort text.\n\n# H2\nShort text.\n\n# H3\nShort text.\n"
        result = analyzer.analyze(text)
        assert result.excessive_headers

    def test_hierarchical_headers_detected(self, analyzer):
        """H3 (depth 3) in < 2000 words → hierarchical."""
        result = analyzer.analyze(HIERARCHICAL_HEADERS_TEXT)
        assert result.hierarchical_headers
        assert result.hierarchical_headers_score > 0

    def test_h2_only_not_hierarchical(self, analyzer):
        """H1 + H2 only (depth 2) → not hierarchical."""
        text = "# Section\nContent here.\n\n## Subsection\nMore content.\n"
        result = analyzer.analyze(text)
        assert not result.hierarchical_headers
        assert result.hierarchical_headers_score == 0.0


# ---------------------------------------------------------------------------
# Section balance — neurodivergent-aware distinction
# ---------------------------------------------------------------------------

class TestSectionBalance:
    """
    #ALGORITHMIC_JUSTICE: The AI signature is headers + UNIFORM section depth.
    Headers + UNEVEN section depth is a neurodivergent scaffolding pattern
    (hyperfocus creates imbalance). The balanced_sections flag must only fire
    on uniformity, not on header presence alone.
    """

    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_uniform_sections_flagged(self, analyzer):
        result = analyzer.analyze(UNIFORM_SECTIONS_TEXT)
        assert result.balanced_sections  # truthy — handles both bool and np.bool_
        assert result.balanced_sections_score > 0

    def test_nonuniform_sections_not_flagged(self, analyzer):
        """Hyperfocus creates uneven section depth — this is NOT an AI signal."""
        result = analyzer.analyze(NONUNIFORM_SECTIONS_TEXT)
        assert not result.balanced_sections
        assert result.balanced_sections_score == 0.0

    def test_no_headers_no_section_score(self, analyzer):
        result = analyzer.analyze(PLAIN_PROSE)
        assert not result.balanced_sections
        assert result.balanced_sections_score == 0.0

    def test_single_header_no_section_score(self, analyzer):
        """Section balance requires at least 2 sections."""
        text = "# Only Header\nAll the content is here with no sections to compare to."
        result = analyzer.analyze(text)
        assert result.balanced_sections_score == 0.0


# ---------------------------------------------------------------------------
# Paragraph uniformity
# ---------------------------------------------------------------------------

class TestParagraphUniformity:
    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_highly_uniform_paragraphs_flagged(self, analyzer):
        """4 paragraphs of equal length → low variance coef → uniform."""
        para = "word " * 20
        text = f"{para}\n\n{para}\n\n{para}\n\n{para}"
        result = analyzer.analyze(text)
        assert result.uniform_paragraphs
        assert result.uniform_paragraphs_score > 0

    def test_varied_paragraphs_not_flagged(self, analyzer):
        """Short para + long para → high variance → not uniform."""
        short = "Just three words."
        long = ("This paragraph is much longer than the short one. " * 5).strip()
        text = f"{short}\n\n{long}\n\n{short}\n\n{long}"
        result = analyzer.analyze(text)
        assert not result.uniform_paragraphs
        assert result.uniform_paragraphs_score == 0.0

    def test_fewer_than_3_paragraphs_not_flagged(self, analyzer):
        text = "First paragraph here.\n\nSecond paragraph here."
        result = analyzer.analyze(text)
        assert not result.uniform_paragraphs
        assert result.uniform_paragraphs_score == 0.0


# ---------------------------------------------------------------------------
# Sentence uniformity + starter diversity
# ---------------------------------------------------------------------------

class TestSentenceAnalysis:
    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_uniform_sentences_score_positive(self, analyzer):
        """All sentences ~9 words → near-zero variance coef → positive score."""
        result = analyzer.analyze(UNIFORM_SENTENCES_TEXT)
        assert result.uniform_sentences_score > 0

    def test_few_sentences_no_scores(self, analyzer):
        """Fewer than 5 sentences → sentence analysis skipped entirely."""
        text = "First sentence. Second sentence. Third sentence."
        result = analyzer.analyze(text)
        assert result.uniform_sentences_score == 0.0
        assert result.starter_diversity_score == 0.0

    def test_starter_diversity_zero_for_under_8_sentences(self, analyzer):
        """Fewer than 8 sentences → starter_diversity_score always 0 (sample too small)."""
        text = "He went. She stayed. They argued. We left. I watched."
        result = analyzer.analyze(text)
        assert result.starter_diversity_score == 0.0

    def test_high_starter_diversity_fires_for_9_sentences(self, analyzer):
        """9 sentences with all-unique starters → starter_diversity = 1.0 → score > 0."""
        result = analyzer.analyze(HIGH_STARTER_DIVERSITY_TEXT)
        assert result.starter_diversity_score > 0.0

    def test_starter_diversity_score_bounded(self, analyzer):
        result = analyzer.analyze(HIGH_STARTER_DIVERSITY_TEXT)
        assert 0.0 <= result.starter_diversity_score <= 0.6


# ---------------------------------------------------------------------------
# Phase A corroboration signals — equity-critical
# ---------------------------------------------------------------------------

class TestPhaseACorroborationSignals:
    """
    #LANGUAGE_JUSTICE: comma_density and avg_word_length are corroboration-only.
    They must NOT appear in total_ai_organizational_score.

    Failing these tests means we are penalizing ESL students (high comma density
    from formal academic register) and students with broad vocabulary (high avg
    word length) — standalone penalties with no equity justification.

    Note: these signals are only computed when sentence_count >= 5 (the early-
    return gate for sentence analysis). Tests use 5-sentence fixtures accordingly.
    """

    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_high_comma_density_populates_field(self, analyzer):
        result = analyzer.analyze(HIGH_COMMA_DENSITY_5SENT)
        assert result.comma_density_score > 0.0

    def test_high_avg_word_length_populates_field(self, analyzer):
        result = analyzer.analyze(HIGH_AVG_WORD_LENGTH_5SENT)
        assert result.avg_word_length_score > 0.0

    def test_total_equals_structural_component_sum(self, analyzer):
        """
        Definitive equity check: total = header_scores + section_score +
        para_score + sentence_uniformity + starter_diversity.
        NOT including comma_density_score or avg_word_length_score.

        Uses the comma-dense fixture because it has high comma_density_score.
        If comma_density were improperly included in total, total > structural_sum.
        """
        result = analyzer.analyze(HIGH_COMMA_DENSITY_5SENT)
        structural_sum = (
            result.excessive_headers_score +
            result.hierarchical_headers_score +
            result.balanced_sections_score +
            result.uniform_paragraphs_score +
            result.uniform_sentences_score +
            result.starter_diversity_score
        )
        assert result.total_ai_organizational_score == pytest.approx(structural_sum, abs=0.01)

    def test_avg_word_length_excluded_from_total(self, analyzer):
        """Same decomposition check on the long-word fixture."""
        result = analyzer.analyze(HIGH_AVG_WORD_LENGTH_5SENT)
        structural_sum = (
            result.excessive_headers_score +
            result.hierarchical_headers_score +
            result.balanced_sections_score +
            result.uniform_paragraphs_score +
            result.uniform_sentences_score +
            result.starter_diversity_score
        )
        assert result.total_ai_organizational_score == pytest.approx(structural_sum, abs=0.01)

    def test_comma_density_score_bounded(self, analyzer):
        result = analyzer.analyze(HIGH_COMMA_DENSITY_5SENT)
        assert 0.0 <= result.comma_density_score <= 0.4

    def test_avg_word_length_score_bounded(self, analyzer):
        result = analyzer.analyze(HIGH_AVG_WORD_LENGTH_5SENT)
        assert 0.0 <= result.avg_word_length_score <= 0.4


# ---------------------------------------------------------------------------
# Gradient scoring — sentence uniformity
# ---------------------------------------------------------------------------

class TestSentenceUniformityGradient:
    """
    Gradient: VC < 0.15 → max 0.8; 0.15–0.40 → linear; > 0.40 → 0.
    High human variation (VC > 0.40) should score 0.
    """

    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_highly_variable_sentences_score_zero(self, analyzer):
        """Text with very mixed sentence lengths should score 0 on sentence uniformity."""
        text = (
            "Yes.\n"
            "This sentence is a bit longer and has more structure to it.\n"
            "Short.\n"
            "This is an extremely long sentence that goes on and on and on and really should "
            "break any uniformity signal because human writers naturally vary their sentence "
            "length when they are thinking through ideas rather than generating text.\n"
            "OK.\n"
            "Another medium-length sentence here for variety in the corpus.\n"
        )
        result = analyzer.analyze(text)
        assert result.uniform_sentences_score == 0.0


# ---------------------------------------------------------------------------
# Circular reference detection
# ---------------------------------------------------------------------------

class TestCircularReferenceDetection:
    @pytest.fixture
    def analyzer(self):
        return OrganizationalAnalyzer()

    def test_hallucination_phrase_detected(self, analyzer):
        text = ("As previously mentioned, the framework is central to our analysis. "
                "But nothing was actually mentioned before this sentence.")
        result = analyzer.verify_circular_references(text)
        assert result["circular_references_found"] >= 1

    def test_as_stated_above_detected(self, analyzer):
        text = "As stated above, the analysis is complete. (Nothing was stated above.)"
        result = analyzer.verify_circular_references(text)
        assert result["circular_references_found"] >= 1

    def test_clean_text_no_violations(self, analyzer):
        result = analyzer.verify_circular_references(PLAIN_PROSE)
        assert result["circular_references_found"] == 0
        assert result["score"] == 0.0

    def test_score_capped_at_2(self, analyzer):
        """Many circular phrases should not push score above 2.0."""
        text = (
            "As previously mentioned, the point. "
            "As stated above, more content. "
            "As discussed earlier, another point. "
            "Returning to our earlier point, we note. "
            "As we saw, this is true. "
            "As noted before, the issue persists."
        )
        result = analyzer.verify_circular_references(text)
        assert result["score"] <= 2.0

    def test_returns_required_keys(self, analyzer):
        result = analyzer.verify_circular_references(PLAIN_PROSE)
        assert "circular_references_found" in result
        assert "violations" in result
        assert "score" in result

    def test_violations_is_list(self, analyzer):
        result = analyzer.verify_circular_references(PLAIN_PROSE)
        assert isinstance(result["violations"], list)
