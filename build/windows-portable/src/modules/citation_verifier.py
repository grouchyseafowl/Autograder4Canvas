"""
Citation Verification Module
Verifies that citations in student work actually exist.
AI frequently fabricates plausible-sounding but non-existent sources.
"""

import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

# Network requests are optional
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


@dataclass
class CitationInfo:
    """Information extracted from a citation."""
    raw_text: str
    citation_type: str  # apa, mla, chicago, unknown
    
    # Extracted components (may be None)
    authors: List[str]
    year: Optional[str]
    title: Optional[str]
    source: Optional[str]  # Journal, book, website
    page_numbers: Optional[str]
    doi: Optional[str]
    url: Optional[str]
    
    # Position in text
    position: int


@dataclass
class VerificationResult:
    """Result of verifying a single citation."""
    citation: CitationInfo
    
    # Verification status
    verified: bool
    verification_method: str  # doi, crossref, google_scholar, manual, not_checked
    
    # Confidence
    confidence: str  # high, medium, low, unknown
    
    # Issues found
    issues: List[str]
    
    # What was found (if anything)
    found_title: Optional[str] = None
    found_authors: Optional[List[str]] = None
    found_source: Optional[str] = None


@dataclass
class CitationAnalysis:
    """Complete citation analysis for a submission."""
    total_citations: int
    citations_checked: int
    citations_verified: int
    citations_suspicious: int
    
    # Individual results
    results: List[VerificationResult]
    
    # Summary
    concern_level: str
    summary: str
    recommendations: List[str]


class CitationExtractor:
    """Extracts citations from text."""
    
    def __init__(self):
        # Patterns for different citation styles
        self.patterns = {
            'apa_parenthetical': re.compile(
                r'\(([A-Z][a-zA-Z\-\']+(?:\s+(?:&|and)\s+[A-Z][a-zA-Z\-\']+)*'
                r'(?:\s+et\s+al\.?)?),?\s*(\d{4}[a-z]?)\)',
                re.IGNORECASE
            ),
            'apa_narrative': re.compile(
                r'([A-Z][a-zA-Z\-\']+(?:\s+(?:&|and)\s+[A-Z][a-zA-Z\-\']+)*'
                r'(?:\s+et\s+al\.?)?)\s*\((\d{4}[a-z]?)\)',
                re.IGNORECASE
            ),
            'mla_parenthetical': re.compile(
                r'\(([A-Z][a-zA-Z\-\']+)\s+(\d+(?:-\d+)?)\)',
                re.IGNORECASE
            ),
            'page_reference': re.compile(
                r'(?:p\.|pp\.)\s*(\d+(?:\s*-\s*\d+)?)',
                re.IGNORECASE
            ),
            'doi': re.compile(
                r'(?:doi:?\s*|https?://doi\.org/)?(10\.\d{4,}/[^\s\]>]+)',
                re.IGNORECASE
            ),
            'url': re.compile(
                r'https?://[^\s\]>]+',
                re.IGNORECASE
            ),
        }
        
        # Common journal name patterns (for detection)
        self.journal_patterns = [
            re.compile(r'Journal of [A-Z][a-zA-Z\s]+', re.IGNORECASE),
            re.compile(r'[A-Z][a-zA-Z]+ Review', re.IGNORECASE),
            re.compile(r'[A-Z][a-zA-Z]+ Quarterly', re.IGNORECASE),
            re.compile(r'American [A-Z][a-zA-Z\s]+', re.IGNORECASE),
            re.compile(r'International [A-Z][a-zA-Z\s]+', re.IGNORECASE),
        ]
    
    def extract_citations(self, text: str) -> List[CitationInfo]:
        """Extract all citations from text."""
        citations = []
        
        # Find APA parenthetical citations
        for match in self.patterns['apa_parenthetical'].finditer(text):
            citations.append(CitationInfo(
                raw_text=match.group(0),
                citation_type='apa',
                authors=self._parse_authors(match.group(1)),
                year=match.group(2),
                title=None,
                source=None,
                page_numbers=None,
                doi=None,
                url=None,
                position=match.start()
            ))
        
        # Find APA narrative citations
        for match in self.patterns['apa_narrative'].finditer(text):
            # Avoid duplicates with parenthetical
            if not any(c.position == match.start() for c in citations):
                citations.append(CitationInfo(
                    raw_text=match.group(0),
                    citation_type='apa',
                    authors=self._parse_authors(match.group(1)),
                    year=match.group(2),
                    title=None,
                    source=None,
                    page_numbers=None,
                    doi=None,
                    url=None,
                    position=match.start()
                ))
        
        # Find DOIs
        for match in self.patterns['doi'].finditer(text):
            # Check if this DOI is associated with an existing citation
            doi = match.group(1)
            associated = False
            for c in citations:
                if abs(c.position - match.start()) < 200:  # Within 200 chars
                    c.doi = doi
                    associated = True
                    break
            
            if not associated:
                citations.append(CitationInfo(
                    raw_text=match.group(0),
                    citation_type='doi',
                    authors=[],
                    year=None,
                    title=None,
                    source=None,
                    page_numbers=None,
                    doi=doi,
                    url=None,
                    position=match.start()
                ))
        
        # Find URLs
        for match in self.patterns['url'].finditer(text):
            url = match.group(0)
            # Skip DOI URLs (already captured)
            if 'doi.org' in url:
                continue
            
            # Check if associated with existing citation
            associated = False
            for c in citations:
                if abs(c.position - match.start()) < 200:
                    c.url = url
                    associated = True
                    break
            
            if not associated:
                citations.append(CitationInfo(
                    raw_text=url,
                    citation_type='url',
                    authors=[],
                    year=None,
                    title=None,
                    source=None,
                    page_numbers=None,
                    doi=None,
                    url=url,
                    position=match.start()
                ))
        
        return citations
    
    def _parse_authors(self, author_string: str) -> List[str]:
        """Parse author names from citation string."""
        # Handle "et al."
        if 'et al' in author_string.lower():
            base = re.sub(r'\s+et\s+al\.?', '', author_string, flags=re.IGNORECASE)
            return [base.strip(), 'et al.']
        
        # Split on & or and
        parts = re.split(r'\s*(?:&|and)\s*', author_string)
        return [p.strip() for p in parts if p.strip()]


class CitationVerifier:
    """Verifies citations exist using various methods."""
    
    def __init__(self, enable_network: bool = True):
        """
        Initialize verifier.
        
        Args:
            enable_network: Whether to make network requests for verification
        """
        self.enable_network = enable_network and HAS_REQUESTS
        self.crossref_api = "https://api.crossref.org/works"
        self.doi_resolver = "https://doi.org"
    
    def verify_citation(self, citation: CitationInfo) -> VerificationResult:
        """Verify a single citation."""
        issues = []
        
        # If we have a DOI, verify it
        if citation.doi:
            return self._verify_doi(citation)
        
        # If we have a URL, check it
        if citation.url:
            return self._verify_url(citation)
        
        # Otherwise, do heuristic checks
        return self._heuristic_check(citation)
    
    def _verify_doi(self, citation: CitationInfo) -> VerificationResult:
        """Verify a DOI resolves."""
        if not self.enable_network:
            return VerificationResult(
                citation=citation,
                verified=False,
                verification_method='not_checked',
                confidence='unknown',
                issues=['Network verification disabled']
            )
        
        try:
            # Try to resolve DOI
            url = f"{self.doi_resolver}/{citation.doi}"
            response = requests.head(url, allow_redirects=True, timeout=5)
            
            if response.status_code == 200:
                return VerificationResult(
                    citation=citation,
                    verified=True,
                    verification_method='doi',
                    confidence='high',
                    issues=[]
                )
            else:
                return VerificationResult(
                    citation=citation,
                    verified=False,
                    verification_method='doi',
                    confidence='high',
                    issues=[f'DOI does not resolve (status {response.status_code})']
                )
        except Exception as e:
            return VerificationResult(
                citation=citation,
                verified=False,
                verification_method='doi',
                confidence='medium',
                issues=[f'Could not verify DOI: {str(e)}']
            )
    
    def _verify_url(self, citation: CitationInfo) -> VerificationResult:
        """Verify a URL is accessible."""
        if not self.enable_network:
            return VerificationResult(
                citation=citation,
                verified=False,
                verification_method='not_checked',
                confidence='unknown',
                issues=['Network verification disabled']
            )
        
        try:
            response = requests.head(
                citation.url, 
                allow_redirects=True, 
                timeout=5,
                headers={'User-Agent': 'Mozilla/5.0 (Academic Citation Checker)'}
            )
            
            if response.status_code == 200:
                return VerificationResult(
                    citation=citation,
                    verified=True,
                    verification_method='url',
                    confidence='medium',  # URL exists but content not verified
                    issues=[]
                )
            else:
                return VerificationResult(
                    citation=citation,
                    verified=False,
                    verification_method='url',
                    confidence='medium',
                    issues=[f'URL returned status {response.status_code}']
                )
        except Exception as e:
            return VerificationResult(
                citation=citation,
                verified=False,
                verification_method='url',
                confidence='low',
                issues=[f'Could not access URL: {str(e)}']
            )
    
    def _heuristic_check(self, citation: CitationInfo) -> VerificationResult:
        """Check citation using heuristics (no network)."""
        issues = []
        
        # Check for suspicious patterns
        
        # Very generic author names
        if citation.authors:
            for author in citation.authors:
                if author.lower() in ['smith', 'jones', 'johnson', 'williams']:
                    issues.append(f"Very common author name: {author}")
        
        # Year in suspicious range (AI often uses recent but not too recent)
        if citation.year:
            try:
                year = int(citation.year[:4])
                if 2018 <= year <= 2022:
                    issues.append("Year in common AI fabrication range (2018-2022)")
            except ValueError:
                issues.append(f"Invalid year format: {citation.year}")
        
        # Missing components
        if not citation.authors:
            issues.append("No authors identified")
        if not citation.year:
            issues.append("No year identified")
        
        # Determine confidence based on issues
        if len(issues) >= 2:
            confidence = 'low'
        elif len(issues) == 1:
            confidence = 'medium'
        else:
            confidence = 'medium'  # Can't verify without network
        
        return VerificationResult(
            citation=citation,
            verified=False,  # Can't verify without network
            verification_method='heuristic',
            confidence=confidence,
            issues=issues if issues else ['Cannot verify without network access']
        )


class CitationAnalyzer:
    """
    Complete citation analysis for academic dishonesty detection.
    
    This analyzer:
    1. Extracts citations from text
    2. Verifies they exist (if network enabled)
    3. Identifies suspicious patterns
    4. Generates recommendations
    """
    
    def __init__(self, enable_network: bool = False):
        """
        Initialize analyzer.
        
        Args:
            enable_network: Whether to verify citations via network
                           Default False to avoid slow analysis
        """
        self.extractor = CitationExtractor()
        self.verifier = CitationVerifier(enable_network)
    
    def analyze(self, text: str, check_limit: int = 5) -> CitationAnalysis:
        """
        Analyze citations in text.
        
        Args:
            text: The submission text
            check_limit: Maximum citations to verify via network
            
        Returns:
            CitationAnalysis with results
        """
        # Extract citations
        citations = self.extractor.extract_citations(text)
        
        # Verify citations (up to limit)
        results = []
        for i, citation in enumerate(citations):
            if i < check_limit:
                result = self.verifier.verify_citation(citation)
            else:
                result = VerificationResult(
                    citation=citation,
                    verified=False,
                    verification_method='not_checked',
                    confidence='unknown',
                    issues=['Exceeded check limit']
                )
            results.append(result)
        
        # Count results
        verified = sum(1 for r in results if r.verified)
        suspicious = sum(1 for r in results if r.issues and 'fabrication' in str(r.issues).lower())
        
        # Check for vague attribution patterns
        vague_patterns = self._find_vague_attribution(text)
        
        # Determine concern level
        concern_level = self._determine_concern(
            len(citations), verified, suspicious, len(vague_patterns)
        )
        
        # Generate summary and recommendations
        summary = self._generate_summary(
            len(citations), verified, suspicious, vague_patterns, results
        )
        recommendations = self._generate_recommendations(
            concern_level, results, vague_patterns
        )
        
        return CitationAnalysis(
            total_citations=len(citations),
            citations_checked=min(len(citations), check_limit),
            citations_verified=verified,
            citations_suspicious=suspicious,
            results=results,
            concern_level=concern_level,
            summary=summary,
            recommendations=recommendations
        )
    
    def _find_vague_attribution(self, text: str) -> List[str]:
        """Find vague attribution that should be cited."""
        vague_patterns = [
            (r'studies\s+(?:show|have\s+shown|indicate|suggest)', 'Studies show/indicate'),
            (r'research\s+(?:shows|indicates|suggests)', 'Research shows'),
            (r'(?:experts?|scientists?|researchers?)\s+(?:say|believe|argue)', 'Experts say'),
            (r'according\s+to\s+(?:experts?|research|studies)', 'According to experts'),
            (r'it\s+(?:has\s+been|is\s+widely)\s+(?:proven|established|accepted)', 'It has been proven'),
        ]
        
        found = []
        for pattern, description in vague_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(description)
        
        return found
    
    def _determine_concern(self, total: int, verified: int, 
                           suspicious: int, vague_count: int) -> str:
        """Determine overall concern level."""
        if suspicious > 0:
            return 'high'
        
        if vague_count >= 3:
            return 'elevated'
        
        if total == 0 and vague_count > 0:
            return 'elevated'  # Claims without citations
        
        if vague_count >= 1:
            return 'moderate'
        
        return 'low'
    
    def _generate_summary(self, total: int, verified: int, suspicious: int,
                          vague: List[str], results: List[VerificationResult]) -> str:
        """Generate human-readable summary."""
        parts = []
        
        parts.append(f"Found {total} citation(s) in text.")
        
        if verified > 0:
            parts.append(f"{verified} verified successfully.")
        
        if suspicious > 0:
            parts.append(f"{suspicious} appear suspicious.")
        
        if vague:
            parts.append(f"Found {len(vague)} vague attribution(s) without citations.")
        
        # Note any unverifiable citations
        unverified = [r for r in results if not r.verified and r.verification_method != 'not_checked']
        if unverified:
            parts.append(f"{len(unverified)} could not be verified.")
        
        return " ".join(parts)
    
    def _generate_recommendations(self, concern_level: str,
                                   results: List[VerificationResult],
                                   vague: List[str]) -> List[str]:
        """Generate actionable recommendations."""
        recs = []
        
        if concern_level in ['high', 'elevated']:
            recs.append("Request student provide PDF or link for key sources")
            recs.append("Manually verify 2-3 citations via Google Scholar")
        
        # Specific to unverified DOIs
        failed_dois = [r for r in results if r.citation.doi and not r.verified]
        if failed_dois:
            recs.append(f"Check DOI(s) manually: {', '.join(r.citation.doi for r in failed_dois)}")
        
        # Specific to vague attribution
        if vague:
            recs.append(f"Ask student to cite specific sources for: {', '.join(vague[:3])}")
        
        # General
        if concern_level != 'low':
            recs.append("Ask: 'Can you show me the article/study you're referencing here?'")
        
        return recs


def analyze_citations(text: str, enable_network: bool = False) -> CitationAnalysis:
    """
    Convenience function to analyze citations in text.
    
    Args:
        text: The submission text
        enable_network: Whether to verify via network (slower but more thorough)
        
    Returns:
        CitationAnalysis with results
    """
    analyzer = CitationAnalyzer(enable_network)
    return analyzer.analyze(text)
