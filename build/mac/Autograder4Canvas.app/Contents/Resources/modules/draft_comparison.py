"""
Draft Comparison Module
Compares draft and final submissions to detect suspicious revision patterns.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from difflib import SequenceMatcher


@dataclass
class RevisionAnalysis:
    """Results of comparing draft to final submission."""
    
    # Similarity metrics
    overall_similarity: float  # 0-1, where 1 = identical
    structural_similarity: float  # Paragraph structure similarity
    content_overlap: float  # % of draft content preserved
    
    # Revision metrics
    words_added: int
    words_removed: int
    words_changed: int
    paragraphs_added: int
    paragraphs_removed: int
    
    # Concern indicators
    concern_level: str  # none, low, moderate, elevated, high
    concern_reasons: List[str]
    
    # Positive indicators
    authentic_revision_signs: List[str]
    
    # Detailed changes
    major_changes: List[str]
    
    # Interpretation
    interpretation: str
    conversation_starters: List[str]


class DraftComparisonAnalyzer:
    """
    Analyzes the relationship between draft and final submissions.
    
    Philosophy:
    Authentic revision shows specific patterns:
    - Ideas develop and refine
    - Structure may change but core content persists
    - Errors get fixed, not everything gets replaced
    - Writing voice remains consistent
    
    Concerning patterns:
    - Complete replacement (draft content mostly gone)
    - "Draft" is already perfect (no room for improvement)
    - Final has completely different voice/style
    - Sophistication jumps dramatically
    """
    
    def __init__(self):
        self.min_draft_length = 100  # Minimum words for meaningful comparison
    
    def compare_submissions(self, 
                            draft_text: str, 
                            final_text: str,
                            student_name: str = "Student") -> RevisionAnalysis:
        """
        Compare draft and final submissions.
        
        Args:
            draft_text: The rough draft submission
            final_text: The final submission
            student_name: For reporting
            
        Returns:
            RevisionAnalysis with detailed comparison
        """
        # Clean and normalize texts
        draft_clean = self._normalize_text(draft_text)
        final_clean = self._normalize_text(final_text)
        
        # Word-level analysis
        draft_words = draft_clean.split()
        final_words = final_clean.split()
        
        # Calculate similarity
        overall_sim = self._calculate_similarity(draft_clean, final_clean)
        
        # Paragraph analysis
        draft_paragraphs = self._get_paragraphs(draft_text)
        final_paragraphs = self._get_paragraphs(final_text)
        structural_sim = self._calculate_structural_similarity(
            draft_paragraphs, final_paragraphs
        )
        
        # Content overlap
        content_overlap = self._calculate_content_overlap(draft_words, final_words)
        
        # Count changes
        added, removed, changed = self._count_word_changes(draft_words, final_words)
        para_added, para_removed = self._count_paragraph_changes(
            draft_paragraphs, final_paragraphs
        )
        
        # Identify major changes
        major_changes = self._identify_major_changes(
            draft_paragraphs, final_paragraphs
        )
        
        # Assess concern level
        concern_level, concern_reasons = self._assess_concern(
            overall_sim, structural_sim, content_overlap,
            len(draft_words), len(final_words),
            draft_text, final_text
        )
        
        # Find authentic revision signs
        authentic_signs = self._find_authentic_revision_signs(
            draft_text, final_text, draft_paragraphs, final_paragraphs
        )
        
        # Generate interpretation
        interpretation = self._generate_interpretation(
            concern_level, concern_reasons, authentic_signs,
            overall_sim, content_overlap
        )
        
        # Generate conversation starters
        conversation_starters = self._generate_conversation_starters(
            concern_level, concern_reasons
        )
        
        return RevisionAnalysis(
            overall_similarity=round(overall_sim, 2),
            structural_similarity=round(structural_sim, 2),
            content_overlap=round(content_overlap, 2),
            words_added=added,
            words_removed=removed,
            words_changed=changed,
            paragraphs_added=para_added,
            paragraphs_removed=para_removed,
            concern_level=concern_level,
            concern_reasons=concern_reasons,
            authentic_revision_signs=authentic_signs,
            major_changes=major_changes[:5],  # Top 5
            interpretation=interpretation,
            conversation_starters=conversation_starters
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison."""
        # Lowercase
        text = text.lower()
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation for word comparison
        text = re.sub(r'[^\w\s]', '', text)
        return text.strip()
    
    def _get_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines or single newlines with blank lines
        paragraphs = re.split(r'\n\s*\n|\n{2,}', text)
        # Clean and filter empty
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate overall text similarity using SequenceMatcher."""
        return SequenceMatcher(None, text1, text2).ratio()
    
    def _calculate_structural_similarity(self, 
                                          paras1: List[str], 
                                          paras2: List[str]) -> float:
        """Calculate structural similarity based on paragraph patterns."""
        if not paras1 or not paras2:
            return 0.0
        
        # Compare paragraph count
        count_sim = 1 - abs(len(paras1) - len(paras2)) / max(len(paras1), len(paras2))
        
        # Compare paragraph lengths (normalized)
        lengths1 = [len(p.split()) for p in paras1]
        lengths2 = [len(p.split()) for p in paras2]
        
        # Pad shorter list
        max_len = max(len(lengths1), len(lengths2))
        lengths1 += [0] * (max_len - len(lengths1))
        lengths2 += [0] * (max_len - len(lengths2))
        
        # Calculate length pattern similarity
        max_total = max(sum(lengths1), sum(lengths2), 1)
        length_diff = sum(abs(a - b) for a, b in zip(lengths1, lengths2))
        length_sim = 1 - (length_diff / (2 * max_total))
        
        return (count_sim + length_sim) / 2
    
    def _calculate_content_overlap(self, 
                                    words1: List[str], 
                                    words2: List[str]) -> float:
        """Calculate what percentage of draft content appears in final."""
        if not words1:
            return 0.0
        
        set1 = set(words1)
        set2 = set(words2)
        
        overlap = len(set1 & set2)
        return overlap / len(set1)
    
    def _count_word_changes(self, 
                            words1: List[str], 
                            words2: List[str]) -> Tuple[int, int, int]:
        """Count words added, removed, and changed."""
        set1 = set(words1)
        set2 = set(words2)
        
        added = len(set2 - set1)
        removed = len(set1 - set2)
        
        # Estimate changed (words in similar positions that differ)
        matcher = SequenceMatcher(None, words1, words2)
        changed = 0
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == 'replace':
                changed += max(i2 - i1, j2 - j1)
        
        return added, removed, changed
    
    def _count_paragraph_changes(self,
                                  paras1: List[str],
                                  paras2: List[str]) -> Tuple[int, int]:
        """Count paragraphs added and removed."""
        # Simple heuristic based on count difference
        diff = len(paras2) - len(paras1)
        if diff > 0:
            return diff, 0
        else:
            return 0, abs(diff)
    
    def _identify_major_changes(self,
                                 paras1: List[str],
                                 paras2: List[str]) -> List[str]:
        """Identify major structural or content changes."""
        changes = []
        
        # Compare each draft paragraph to final
        for i, p1 in enumerate(paras1):
            best_match = 0
            for p2 in paras2:
                sim = SequenceMatcher(None, p1.lower(), p2.lower()).ratio()
                best_match = max(best_match, sim)
            
            if best_match < 0.3:
                preview = p1[:50] + "..." if len(p1) > 50 else p1
                changes.append(f"Draft paragraph {i+1} removed or heavily rewritten: '{preview}'")
        
        # Check for new paragraphs
        for i, p2 in enumerate(paras2):
            best_match = 0
            for p1 in paras1:
                sim = SequenceMatcher(None, p1.lower(), p2.lower()).ratio()
                best_match = max(best_match, sim)
            
            if best_match < 0.3:
                preview = p2[:50] + "..." if len(p2) > 50 else p2
                changes.append(f"New paragraph {i+1} in final: '{preview}'")
        
        return changes
    
    def _assess_concern(self,
                        overall_sim: float,
                        structural_sim: float,
                        content_overlap: float,
                        draft_words: int,
                        final_words: int,
                        draft_text: str,
                        final_text: str) -> Tuple[str, List[str]]:
        """Assess concern level based on comparison metrics."""
        concerns = []
        
        # Check for complete replacement
        if content_overlap < 0.3 and overall_sim < 0.3:
            concerns.append("Draft content mostly replaced (< 30% preserved)")
        
        # Check for "draft" that's already perfect
        if overall_sim > 0.95:
            concerns.append("Draft and final nearly identical (> 95% similar)")
        
        # Check for dramatic length change
        if draft_words > 0:
            length_ratio = final_words / draft_words
            if length_ratio > 3:
                concerns.append(f"Final is {length_ratio:.1f}x longer than draft")
            elif length_ratio < 0.3:
                concerns.append(f"Final is much shorter than draft ({length_ratio:.1f}x)")
        
        # Check for sophistication jump (crude heuristic)
        draft_avg_word_len = sum(len(w) for w in draft_text.split()) / max(len(draft_text.split()), 1)
        final_avg_word_len = sum(len(w) for w in final_text.split()) / max(len(final_text.split()), 1)
        
        if final_avg_word_len > draft_avg_word_len + 1.5:
            concerns.append("Vocabulary sophistication increased significantly")
        
        # Determine concern level
        if len(concerns) >= 2 or (content_overlap < 0.2 and overall_sim < 0.2):
            level = "high"
        elif len(concerns) >= 1:
            level = "elevated"
        elif content_overlap < 0.5 or overall_sim < 0.4:
            level = "moderate"
        elif overall_sim > 0.9:
            level = "low"  # Too similar might indicate no real revision
        else:
            level = "none"
        
        return level, concerns
    
    def _find_authentic_revision_signs(self,
                                        draft: str,
                                        final: str,
                                        draft_paras: List[str],
                                        final_paras: List[str]) -> List[str]:
        """Find signs of authentic revision process."""
        signs = []
        
        # Check for error corrections (draft has errors, final doesn't)
        draft_errors = self._count_basic_errors(draft)
        final_errors = self._count_basic_errors(final)
        if draft_errors > final_errors and draft_errors > 0:
            signs.append(f"Errors reduced from {draft_errors} to {final_errors}")
        
        # Check for paragraph reorganization (not replacement)
        if len(draft_paras) != len(final_paras) and abs(len(draft_paras) - len(final_paras)) <= 2:
            signs.append("Paragraph structure refined (not completely changed)")
        
        # Check for expansion of ideas (sentences added within paragraphs)
        draft_sentences = len(re.findall(r'[.!?]+', draft))
        final_sentences = len(re.findall(r'[.!?]+', final))
        if 1.2 < final_sentences / max(draft_sentences, 1) < 2.0:
            signs.append("Ideas expanded (moderate sentence increase)")
        
        # Check for consistent voice (I/my usage patterns)
        draft_first_person = len(re.findall(r'\b(I|my|me)\b', draft, re.I))
        final_first_person = len(re.findall(r'\b(I|my|me)\b', final, re.I))
        if draft_first_person > 0 and final_first_person > 0:
            ratio = final_first_person / draft_first_person
            if 0.5 < ratio < 2.0:
                signs.append("Consistent personal voice maintained")
        
        return signs
    
    def _count_basic_errors(self, text: str) -> int:
        """Count basic errors (typos, spacing issues)."""
        errors = 0
        
        # Double spaces
        errors += len(re.findall(r'  +', text))
        
        # Missing space after punctuation
        errors += len(re.findall(r'[.!?,][A-Za-z]', text))
        
        # Common typos (very basic)
        common_typos = ['teh', 'hte', 'adn', 'taht', 'wiht']
        for typo in common_typos:
            errors += len(re.findall(rf'\b{typo}\b', text, re.I))
        
        return errors
    
    def _generate_interpretation(self,
                                  concern_level: str,
                                  concerns: List[str],
                                  authentic_signs: List[str],
                                  similarity: float,
                                  overlap: float) -> str:
        """Generate human-readable interpretation."""
        if concern_level == "none":
            return ("The revision pattern appears normal. Draft content was preserved "
                    "and refined, suggesting authentic revision work.")
        
        elif concern_level == "low":
            if similarity > 0.9:
                return ("Draft and final are very similar. This may indicate the 'draft' "
                        "was already quite polished, or minimal revision occurred. "
                        "Consider whether the draft requirement was meaningful.")
            return "Minor revision concerns, but generally appears authentic."
        
        elif concern_level == "moderate":
            return ("Some revision patterns are unusual. Significant portions changed, "
                    "but some continuity remains. May warrant a brief conversation "
                    "about the revision process.")
        
        elif concern_level == "elevated":
            concerns_str = "; ".join(concerns)
            return (f"Notable concerns: {concerns_str}. The relationship between "
                    "draft and final is unusual. A conversation about the revision "
                    "process is recommended.")
        
        else:  # high
            concerns_str = "; ".join(concerns)
            return (f"Significant concerns: {concerns_str}. The final submission "
                    "appears largely disconnected from the draft. This may indicate "
                    "the final was produced through a different process. "
                    "A detailed conversation is strongly recommended.")
    
    def _generate_conversation_starters(self,
                                         concern_level: str,
                                         concerns: List[str]) -> List[str]:
        """Generate appropriate conversation starters."""
        starters = []
        
        if concern_level in ["elevated", "high"]:
            starters.append("Can you walk me through your revision process?")
            starters.append("What changed most between your draft and final?")
            starters.append("What feedback or ideas led to these revisions?")
            
            if "replaced" in str(concerns).lower():
                starters.append("I noticed the final is quite different from the draft. "
                               "What prompted such significant changes?")
            
            if "identical" in str(concerns).lower():
                starters.append("Your draft and final are very similar. Did you feel "
                               "the draft didn't need much revision?")
        
        elif concern_level == "moderate":
            starters.append("What was your revision process like?")
            starters.append("What improvements did you focus on?")
        
        return starters


def compare_draft_to_final(draft_text: str, 
                           final_text: str,
                           student_name: str = "Student") -> RevisionAnalysis:
    """
    Convenience function to compare draft and final submissions.
    
    Args:
        draft_text: The rough draft
        final_text: The final submission
        student_name: For reporting
        
    Returns:
        RevisionAnalysis with comparison results
    """
    analyzer = DraftComparisonAnalyzer()
    return analyzer.compare_submissions(draft_text, final_text, student_name)
