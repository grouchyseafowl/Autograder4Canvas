"""
Organizational Analyzer Module

Algorithmic detection of AI-specific organizational patterns that don't overlap
with neurodivergent writing styles.

Key distinctions:
- AI: Excessive headers, perfect balance, uniform structure
- Neurodivergent: May use headers as scaffolding, but with UNEVEN depth (hyperfocus)
"""

import re
import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class OrganizationalAnalysis:
    """Results of organizational pattern analysis."""
    excessive_headers: bool
    excessive_headers_score: float
    hierarchical_headers: bool
    hierarchical_headers_score: float
    balanced_sections: bool
    balanced_sections_score: float
    uniform_paragraphs: bool
    uniform_paragraphs_score: float
    uniform_sentences: bool
    uniform_sentences_score: float

    # Engagement reframe signals (Phase A)
    # Sentence-starter diversity: AI=1.0, Human=0.759 (d=2.13)
    # Strongest theoretical stability — transformer repetition penalties are architectural
    starter_diversity_score: float = 0.0

    # Comma density per 100 words: AI=5.69, Human=2.80 (d=1.85)
    # AI constructs complex sentences with subordinate clauses
    # Bias note: formal academic ESL writing may also have high comma density
    comma_density_score: float = 0.0

    # Average word length: AI=5.13, Human=4.28 (d=2.17)
    # Continuous version of "inflated vocab"
    # Bias note: correlates with education level and reading exposure
    avg_word_length_score: float = 0.0

    total_ai_organizational_score: float = 0.0
    details: Dict[str, any] = None


class OrganizationalAnalyzer:
    """
    Analyzes text for AI-specific organizational patterns.

    These patterns are AI signatures that don't overlap with neurodivergent
    writing styles, so they should NOT receive cognitive diversity protection.
    """

    def __init__(self):
        self.header_patterns = {
            'h1': re.compile(r'^# (.+)$', re.MULTILINE),
            'h2': re.compile(r'^## (.+)$', re.MULTILINE),
            'h3': re.compile(r'^### (.+)$', re.MULTILINE),
            'h4': re.compile(r'^#### (.+)$', re.MULTILINE),
        }

    def analyze(self, text: str) -> OrganizationalAnalysis:
        """
        Perform complete organizational analysis.

        Returns:
            OrganizationalAnalysis with all detected patterns
        """
        word_count = len(text.split())

        # Analyze headers
        header_analysis = self._analyze_headers(text, word_count)

        # Analyze section balance (if headers present)
        section_analysis = self._analyze_section_balance(text, header_analysis['headers'])

        # Analyze paragraph uniformity
        paragraph_analysis = self._analyze_paragraph_uniformity(text)

        # Analyze sentence uniformity (also computes starter diversity,
        # comma density, and avg word length signals)
        sentence_analysis = self._analyze_sentence_uniformity(text)

        # Calculate total score — includes starter diversity but NOT
        # comma_density or avg_word_length, which are corroboration-only
        # signals that participate through convergence, not standalone scoring.
        # (#LANGUAGE_JUSTICE: comma density risks false positives on ESL formal
        # writing; avg word length correlates with education level. These
        # signals should only amplify when multiple independent channels agree.)
        total_score = (
            header_analysis.get('excessive_score', 0) +
            header_analysis.get('hierarchical_score', 0) +
            section_analysis.get('balance_score', 0) +
            paragraph_analysis.get('uniformity_score', 0) +
            sentence_analysis.get('uniformity_score', 0) +
            sentence_analysis.get('starter_diversity_score', 0)
        )

        return OrganizationalAnalysis(
            excessive_headers=header_analysis.get('excessive', False),
            excessive_headers_score=header_analysis.get('excessive_score', 0),
            hierarchical_headers=header_analysis.get('hierarchical', False),
            hierarchical_headers_score=header_analysis.get('hierarchical_score', 0),
            balanced_sections=section_analysis.get('balanced', False),
            balanced_sections_score=section_analysis.get('balance_score', 0),
            uniform_paragraphs=paragraph_analysis.get('uniform', False),
            uniform_paragraphs_score=paragraph_analysis.get('uniformity_score', 0),
            uniform_sentences=sentence_analysis.get('uniform', False),
            uniform_sentences_score=sentence_analysis.get('uniformity_score', 0),
            starter_diversity_score=sentence_analysis.get('starter_diversity_score', 0),
            comma_density_score=sentence_analysis.get('comma_density_score', 0),
            avg_word_length_score=sentence_analysis.get('avg_word_length_score', 0),
            total_ai_organizational_score=round(total_score, 2),
            details={
                'header_analysis': header_analysis,
                'section_analysis': section_analysis,
                'paragraph_analysis': paragraph_analysis,
                'sentence_analysis': sentence_analysis
            }
        )

    def _analyze_headers(self, text: str, word_count: int) -> Dict[str, any]:
        """
        Analyze header usage patterns.

        AI signatures:
        - Too many headers for word count
        - Too many levels of hierarchy

        Neurodivergent difference:
        - May use headers as scaffolding, but more sparingly
        - Usually 1-2 levels max
        """
        headers = []
        header_levels = {}

        # Extract headers at each level
        for level, pattern in self.header_patterns.items():
            matches = pattern.findall(text)
            for match in matches:
                headers.append({'level': level, 'text': match})
                header_levels[level] = header_levels.get(level, 0) + 1

        total_headers = len(headers)
        deepest_level = max([int(h['level'][1]) for h in headers]) if headers else 0

        # Check for excessive headers
        excessive = False
        excessive_score = 0.0

        if word_count < 500 and total_headers > 2:
            excessive = True
            excessive_score = 1.5
        elif 500 <= word_count < 1000 and total_headers > 4:
            excessive = True
            excessive_score = 1.2
        elif 1000 <= word_count < 2000 and total_headers > 6:
            excessive = True
            excessive_score = 1.0

        # Check for hierarchical depth
        hierarchical = False
        hierarchical_score = 0.0

        if deepest_level >= 3 and word_count < 2000:
            hierarchical = True
            hierarchical_score = 1.3
        elif deepest_level >= 4:
            hierarchical = True
            hierarchical_score = 1.5

        return {
            'headers': headers,
            'total_count': total_headers,
            'deepest_level': deepest_level,
            'level_distribution': header_levels,
            'excessive': excessive,
            'excessive_score': excessive_score,
            'hierarchical': hierarchical,
            'hierarchical_score': hierarchical_score
        }

    def _analyze_section_balance(self, text: str, headers: List[Dict]) -> Dict[str, any]:
        """
        Analyze balance of content under headers.

        AI signature: Sections are suspiciously uniform in length
        Neurodivergent: Sections vary widely (hyperfocus on interesting parts)

        This is KEY: Headers + uniform depth = AI
                     Headers + uneven depth = scaffolding
        """
        if len(headers) < 2:
            return {'balanced': False, 'balance_score': 0.0}

        # Split text by headers to get sections
        sections = self._extract_sections(text, headers)

        if len(sections) < 2:
            return {'balanced': False, 'balance_score': 0.0}

        # Calculate section lengths (in words)
        section_lengths = [len(section.split()) for section in sections]

        if not section_lengths or max(section_lengths) == 0:
            return {'balanced': False, 'balance_score': 0.0}

        # Calculate variance
        mean_length = np.mean(section_lengths)
        std_length = np.std(section_lengths)
        variance_coef = std_length / mean_length if mean_length > 0 else 0

        # AI signature: variance coefficient < 0.25 (very uniform)
        balanced = variance_coef < 0.25
        balance_score = 1.4 if balanced else 0.0

        return {
            'section_count': len(sections),
            'section_lengths': section_lengths,
            'mean_length': round(mean_length, 1),
            'variance_coefficient': round(variance_coef, 3),
            'balanced': balanced,
            'balance_score': balance_score,
            'interpretation': 'AI signature (uniform sections)' if balanced else 'Human variation (uneven depth)'
        }

    def _extract_sections(self, text: str, headers: List[Dict]) -> List[str]:
        """
        Extract text sections divided by headers.

        Simple approach: Split by header patterns and return content chunks.
        """
        # Create a pattern that matches any header
        header_pattern = re.compile(r'^#{1,6} .+$', re.MULTILINE)

        # Split by headers
        sections = header_pattern.split(text)

        # Filter out empty sections
        sections = [s.strip() for s in sections if s.strip()]

        return sections

    def _analyze_paragraph_uniformity(self, text: str) -> Dict[str, any]:
        """
        Analyze paragraph length uniformity.

        AI signature: Low variance in paragraph lengths
        Neurodivergent: High variance (hyperfocus creates uneven depth)
        """
        # Split by double newlines (paragraph breaks)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]

        if len(paragraphs) < 3:
            return {'uniform': False, 'uniformity_score': 0.0}

        # Calculate paragraph lengths
        para_lengths = [len(p.split()) for p in paragraphs]

        mean_length = np.mean(para_lengths)
        std_length = np.std(para_lengths)
        variance_coef = std_length / mean_length if mean_length > 0 else 0

        # AI signature: variance coefficient < 0.20 (very uniform)
        uniform = variance_coef < 0.20
        uniformity_score = 1.2 if uniform else 0.0

        # Neurodivergent positive: High variance (> 0.40)
        high_variance = variance_coef > 0.40

        return {
            'paragraph_count': len(paragraphs),
            'paragraph_lengths': para_lengths,
            'mean_length': round(mean_length, 1),
            'variance_coefficient': round(variance_coef, 3),
            'uniform': uniform,
            'uniformity_score': uniformity_score,
            'high_variance': high_variance,
            'interpretation': 'AI signature (uniform)' if uniform else 'Neurodivergent positive (uneven)' if high_variance else 'Normal variation'
        }

    def _analyze_sentence_uniformity(self, text: str) -> Dict[str, any]:
        """
        Analyze sentence length uniformity.

        AI signature: Rhythmically similar sentences
        Human: More variation in complexity and length
        """
        # Split into sentences (basic approach)
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 2]

        if len(sentences) < 5:
            return {
                'uniform': False, 'uniformity_score': 0.0,
                'sentence_count': len(sentences),
                'mean_length': 0, 'variance_coefficient': 0,
                'interpretation': 'Too few sentences for analysis',
                'starter_diversity': 0.0, 'starter_diversity_score': 0.0,
                'comma_density': 0.0, 'comma_density_score': 0.0,
                'avg_word_length': 0.0, 'avg_word_length_score': 0.0,
            }

        # Calculate sentence lengths
        sent_lengths = [len(s.split()) for s in sentences]

        mean_length = np.mean(sent_lengths)
        std_length = np.std(sent_lengths)
        variance_coef = std_length / mean_length if mean_length > 0 else 0

        # Gradient scoring: 0.15-0.40 range based on calibration data
        # (AI mean VC=0.336, Human mean VC=0.458, d=0.99)
        # Below 0.15: maximum score (extremely rhythmic)
        # 0.15-0.40: linear gradient
        # Above 0.40: zero (human-typical variation)
        if variance_coef < 0.15:
            uniformity_score = 0.8
        elif variance_coef < 0.40:
            uniformity_score = 0.8 * (0.40 - variance_coef) / (0.40 - 0.15)
        else:
            uniformity_score = 0.0

        uniform = uniformity_score > 0.4  # For backward compat boolean

        if uniformity_score > 0.5:
            interpretation = 'Low variation (rhythmic pattern)'
        elif uniformity_score > 0.1:
            interpretation = 'Moderate uniformity'
        else:
            interpretation = 'Typical variation'

        # Sentence-starter diversity: unique first words / total sentences
        # AI tends toward perfect diversity (d=2.13) due to transformer
        # repetition penalties; humans naturally repeat starters.
        starters = [s.split()[0].lower() for s in sentences if s.split()]
        starter_diversity = len(set(starters)) / len(starters) if starters else 0

        # Gradient scoring for starter diversity:
        # 1.0 = perfect (all unique) → max score 0.6
        # 0.95-1.0 = very high → gradient
        # Below 0.85 = human-typical → zero
        # Note: 13.6% of humans also achieve 1.0, so this is corroborative
        #
        # MINIMUM SAMPLE: Requires 8+ sentences. With fewer, random chance
        # produces high diversity (5 sentences → 5/5=1.0 is common for humans).
        # The d=2.13 effect size was measured on texts with sufficient length.
        if len(sentences) >= 8 and starter_diversity >= 1.0:
            starter_diversity_score = 0.6
        elif len(sentences) >= 8 and starter_diversity >= 0.85:
            starter_diversity_score = 0.6 * (starter_diversity - 0.85) / (1.0 - 0.85)
        else:
            starter_diversity_score = 0.0

        # Comma density: commas per 100 words
        # AI mean 5.69, Human mean 2.80 (d=1.85) — AI constructs
        # complex sentences with subordinate clauses.
        words = text.split()
        comma_count = text.count(',')
        comma_density = (comma_count / len(words) * 100) if words else 0

        # Gradient scoring for comma density:
        # Above 5.0 per 100 words → max score 0.4
        # 3.5-5.0 → gradient
        # Below 3.5 → zero (human-typical range)
        # Bias caveat: ESL formal writing may produce high comma density —
        # this signal should be downweighted when ESL context is detected
        if comma_density >= 5.0:
            comma_density_score = 0.4
        elif comma_density >= 3.5:
            comma_density_score = 0.4 * (comma_density - 3.5) / (5.0 - 3.5)
        else:
            comma_density_score = 0.0

        # Average word length: continuous version of "inflated vocab"
        # AI mean 5.13 chars, Human mean 4.28 chars (d=2.17)
        all_words = re.findall(r'[a-zA-Z]+', text)
        avg_word_length = (sum(len(w) for w in all_words) / len(all_words)) if all_words else 0

        # Gradient scoring for avg word length:
        # Above 5.0 chars → max score 0.4
        # 4.5-5.0 → gradient
        # Below 4.5 → zero (human-typical range)
        # Bias caveat: correlates with education level and reading exposure
        if avg_word_length >= 5.0:
            avg_word_length_score = 0.4
        elif avg_word_length >= 4.5:
            avg_word_length_score = 0.4 * (avg_word_length - 4.5) / (5.0 - 4.5)
        else:
            avg_word_length_score = 0.0

        return {
            'sentence_count': len(sentences),
            'mean_length': round(mean_length, 1),
            'variance_coefficient': round(variance_coef, 3),
            'uniform': uniform,
            'uniformity_score': round(uniformity_score, 3),
            'interpretation': interpretation,
            'starter_diversity': round(starter_diversity, 3),
            'starter_diversity_score': round(starter_diversity_score, 3),
            'comma_density': round(comma_density, 2),
            'comma_density_score': round(comma_density_score, 3),
            'avg_word_length': round(avg_word_length, 2),
            'avg_word_length_score': round(avg_word_length_score, 3),
        }

    def verify_circular_references(self, text: str) -> Dict[str, any]:
        """
        Detect circular signposting - references to content that doesn't exist.

        AI hallucination: "As previously mentioned" when nothing was mentioned
        Human: Refers to actual prior content
        """
        circular_phrases = [
            r"as previously mentioned",
            r"as stated above",
            r"as discussed earlier",
            r"returning to our earlier point",
            r"as we saw",
            r"as noted before"
        ]

        violations = []

        for phrase_pattern in circular_phrases:
            matches = list(re.finditer(phrase_pattern, text, re.IGNORECASE))

            for match in matches:
                # Get position of the phrase
                position = match.start()
                phrase = match.group()

                # Extract preceding text
                preceding_text = text[:position]

                # Try to identify what's being referenced
                # This is a simplified check - could be more sophisticated
                # Look for key nouns/concepts in the sentence containing the phrase
                sentence_start = text.rfind('.', 0, position) + 1
                sentence = text[sentence_start:position + len(phrase) + 100]

                # Extract potential topic words (simplified)
                topic_words = self._extract_topic_words(sentence)

                # Check if these topics appear in preceding text
                topics_found = sum(1 for word in topic_words if word.lower() in preceding_text.lower())

                if topics_found == 0:
                    # Possible hallucination - phrase refers to nothing
                    violations.append({
                        'phrase': phrase,
                        'position': position,
                        'context': sentence[:200],
                        'likely_hallucination': True
                    })

        return {
            'circular_references_found': len(violations),
            'violations': violations,
            'score': min(len(violations) * 0.6, 2.0)  # Cap at 2.0
        }

    def _extract_topic_words(self, text: str) -> List[str]:
        """
        Extract likely topic words from text (simplified).

        Real implementation would use NLP, but this is basic approach.
        """
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
                       'of', 'as', 'by', 'this', 'that', 'these', 'those', 'is', 'are', 'was',
                       'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did',
                       'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can',
                       'it', 'its', 'they', 'their', 'them', 'we', 'our', 'us', 'you', 'your'}

        words = re.findall(r'\b[a-z]+\b', text.lower())
        topic_words = [w for w in words if w not in common_words and len(w) > 3]

        return topic_words


def analyze_organizational_patterns(text: str) -> OrganizationalAnalysis:
    """
    Convenience function to analyze organizational patterns.

    Returns:
        OrganizationalAnalysis with AI-specific pattern detection
    """
    analyzer = OrganizationalAnalyzer()
    return analyzer.analyze(text)
