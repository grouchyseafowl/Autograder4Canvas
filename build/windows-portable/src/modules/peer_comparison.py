"""
Peer Comparison Module
Statistical outlier detection for academic dishonesty analysis.
Identifies submissions that are unusual compared to their cohort.
"""

import statistics
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class SubmissionMetrics:
    """Metrics for a single submission."""
    student_id: str
    student_name: str
    
    # Core scores
    suspicious_score: float
    authenticity_score: float
    word_count: int
    
    # Calculated metrics (filled in by analyzer)
    suspicious_percentile: Optional[float] = None
    authenticity_percentile: Optional[float] = None
    suspicious_zscore: Optional[float] = None
    authenticity_zscore: Optional[float] = None
    
    # Outlier status
    is_outlier: bool = False
    outlier_reasons: List[str] = field(default_factory=list)


@dataclass
class PeerComparisonResult:
    """Result of peer comparison analysis."""
    # Cohort statistics
    total_submissions: int
    
    suspicious_mean: float
    suspicious_stdev: float
    suspicious_median: float
    suspicious_iqr: float
    
    authenticity_mean: float
    authenticity_stdev: float
    authenticity_median: float
    authenticity_iqr: float
    
    # Thresholds used
    suspicious_threshold: float
    authenticity_threshold: float
    
    # Outliers
    outlier_count: int
    outliers: List[SubmissionMetrics]
    
    # All metrics (updated with percentiles)
    all_metrics: List[SubmissionMetrics]


class PeerComparisonAnalyzer:
    """
    Analyzes submissions through peer comparison.
    
    Philosophy:
    Instead of absolute thresholds, this identifies STATISTICAL OUTLIERS
    within the class cohort. A score of 5 might be "high" in one class
    but "moderate" in another where the mean is 3.5.
    
    This adapts to:
    - Different disciplines and writing styles
    - Varying assignment expectations
    - Class-specific patterns
    
    Methods:
    - Percentile ranking: Where does this submission fall?
    - Z-score: How many standard deviations from mean?
    - IQR-based outliers: Robust outlier detection
    """
    
    def __init__(self, 
                 outlier_percentile: float = 90.0,
                 zscore_threshold: float = 2.0,
                 use_iqr: bool = True):
        """
        Initialize the peer comparison analyzer.
        
        Args:
            outlier_percentile: Percentile above which to flag as outlier
                               (95 for community college, 90 for standard)
            zscore_threshold: Z-score above which to flag as outlier
            use_iqr: Whether to use IQR-based outlier detection
        """
        self.outlier_percentile = outlier_percentile
        self.zscore_threshold = zscore_threshold
        self.use_iqr = use_iqr
    
    def analyze_cohort(self, metrics: List[SubmissionMetrics]) -> PeerComparisonResult:
        """
        Analyze a cohort of submissions.
        
        Args:
            metrics: List of SubmissionMetrics for all submissions
            
        Returns:
            PeerComparisonResult with statistics and outlier identification
        """
        if len(metrics) < 3:
            # Not enough data for meaningful comparison
            return self._insufficient_data_result(metrics)
        
        # Extract score lists
        suspicious_scores = [m.suspicious_score for m in metrics]
        authenticity_scores = [m.authenticity_score for m in metrics]
        
        # Calculate statistics
        sus_stats = self._calculate_stats(suspicious_scores)
        auth_stats = self._calculate_stats(authenticity_scores)
        
        # Calculate thresholds
        sus_threshold = self._calculate_threshold(suspicious_scores, sus_stats)
        auth_threshold = self._calculate_threshold(authenticity_scores, auth_stats, lower=True)
        
        # Calculate percentiles and z-scores for each submission
        outliers = []
        for m in metrics:
            # Suspicious percentile (higher = more concerning)
            m.suspicious_percentile = self._calculate_percentile(
                m.suspicious_score, suspicious_scores
            )
            
            # Authenticity percentile (lower = more concerning)
            m.authenticity_percentile = self._calculate_percentile(
                m.authenticity_score, authenticity_scores
            )
            
            # Z-scores
            if sus_stats['stdev'] > 0:
                m.suspicious_zscore = (m.suspicious_score - sus_stats['mean']) / sus_stats['stdev']
            else:
                m.suspicious_zscore = 0.0
                
            if auth_stats['stdev'] > 0:
                m.authenticity_zscore = (m.authenticity_score - auth_stats['mean']) / auth_stats['stdev']
            else:
                m.authenticity_zscore = 0.0
            
            # Check if outlier
            outlier_reasons = self._check_outlier(m, sus_stats, auth_stats, sus_threshold)
            if outlier_reasons:
                m.is_outlier = True
                m.outlier_reasons = outlier_reasons
                outliers.append(m)
        
        return PeerComparisonResult(
            total_submissions=len(metrics),
            suspicious_mean=round(sus_stats['mean'], 2),
            suspicious_stdev=round(sus_stats['stdev'], 2),
            suspicious_median=round(sus_stats['median'], 2),
            suspicious_iqr=round(sus_stats['iqr'], 2),
            authenticity_mean=round(auth_stats['mean'], 2),
            authenticity_stdev=round(auth_stats['stdev'], 2),
            authenticity_median=round(auth_stats['median'], 2),
            authenticity_iqr=round(auth_stats['iqr'], 2),
            suspicious_threshold=round(sus_threshold, 2),
            authenticity_threshold=round(auth_threshold, 2),
            outlier_count=len(outliers),
            outliers=outliers,
            all_metrics=metrics
        )
    
    def _calculate_stats(self, scores: List[float]) -> Dict[str, float]:
        """Calculate statistical measures for a list of scores."""
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        
        mean = statistics.mean(scores)
        stdev = statistics.stdev(scores) if n > 1 else 0.0
        median = statistics.median(scores)
        
        # IQR calculation
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        q1 = sorted_scores[q1_idx]
        q3 = sorted_scores[q3_idx]
        iqr = q3 - q1
        
        return {
            'mean': mean,
            'stdev': stdev,
            'median': median,
            'q1': q1,
            'q3': q3,
            'iqr': iqr,
            'min': sorted_scores[0],
            'max': sorted_scores[-1]
        }
    
    def _calculate_threshold(self, 
                              scores: List[float], 
                              stats: Dict[str, float],
                              lower: bool = False) -> float:
        """Calculate outlier threshold."""
        sorted_scores = sorted(scores)
        n = len(sorted_scores)
        
        if lower:
            # For authenticity, we flag LOW scores
            percentile_idx = int(n * (100 - self.outlier_percentile) / 100)
            return sorted_scores[max(0, percentile_idx)]
        else:
            # For suspicious, we flag HIGH scores
            percentile_idx = int(n * self.outlier_percentile / 100)
            return sorted_scores[min(percentile_idx, n - 1)]
    
    def _calculate_percentile(self, score: float, all_scores: List[float]) -> float:
        """Calculate percentile rank of a score."""
        below_count = sum(1 for s in all_scores if s < score)
        return round(100 * below_count / len(all_scores), 1)
    
    def _check_outlier(self, 
                       m: SubmissionMetrics,
                       sus_stats: Dict,
                       auth_stats: Dict,
                       sus_threshold: float) -> List[str]:
        """Check if a submission is an outlier and return reasons."""
        reasons = []
        
        # Percentile-based check
        if m.suspicious_percentile >= self.outlier_percentile:
            reasons.append(f"Suspicious score in top {100 - self.outlier_percentile:.0f}% of class")
        
        # Z-score check
        if m.suspicious_zscore and m.suspicious_zscore > self.zscore_threshold:
            reasons.append(f"Z-score {m.suspicious_zscore:.1f} (>{self.zscore_threshold} std dev)")
        
        # Low authenticity check
        if m.authenticity_zscore and m.authenticity_zscore < -1.5:
            reasons.append("Authenticity significantly below class average")
        
        # IQR-based check
        if self.use_iqr:
            upper_fence = sus_stats['q3'] + 1.5 * sus_stats['iqr']
            if m.suspicious_score > upper_fence:
                reasons.append(f"Beyond IQR upper fence ({upper_fence:.1f})")
        
        # Combined check: high suspicious AND low authenticity
        if (m.suspicious_percentile >= 75 and 
            m.authenticity_percentile <= 25):
            if "high suspicious AND low authenticity" not in reasons:
                reasons.append("High suspicious AND low authenticity relative to peers")
        
        return reasons
    
    def _insufficient_data_result(self, metrics: List[SubmissionMetrics]) -> PeerComparisonResult:
        """Return result when there's insufficient data for comparison."""
        return PeerComparisonResult(
            total_submissions=len(metrics),
            suspicious_mean=0.0,
            suspicious_stdev=0.0,
            suspicious_median=0.0,
            suspicious_iqr=0.0,
            authenticity_mean=0.0,
            authenticity_stdev=0.0,
            authenticity_median=0.0,
            authenticity_iqr=0.0,
            suspicious_threshold=0.0,
            authenticity_threshold=0.0,
            outlier_count=0,
            outliers=[],
            all_metrics=metrics
        )
    
    def generate_cohort_summary(self, result: PeerComparisonResult) -> str:
        """Generate a human-readable cohort summary."""
        lines = []
        
        lines.append(f"Submissions Analyzed: {result.total_submissions}")
        lines.append("")
        lines.append("Suspicious Score Distribution:")
        lines.append(f"  Mean: {result.suspicious_mean}, Median: {result.suspicious_median}")
        lines.append(f"  Std Dev: {result.suspicious_stdev}, IQR: {result.suspicious_iqr}")
        lines.append(f"  Outlier Threshold: {result.suspicious_threshold}")
        lines.append("")
        lines.append("Authenticity Score Distribution:")
        lines.append(f"  Mean: {result.authenticity_mean}, Median: {result.authenticity_median}")
        lines.append(f"  Std Dev: {result.authenticity_stdev}, IQR: {result.authenticity_iqr}")
        lines.append("")
        lines.append(f"Outliers Identified: {result.outlier_count}")
        
        if result.outliers:
            lines.append("")
            lines.append("Outlier Summary:")
            for o in result.outliers:
                lines.append(f"  - {o.student_name}: {', '.join(o.outlier_reasons)}")
        
        return "\n".join(lines)


def create_submission_metrics(student_id: str,
                              student_name: str,
                              suspicious_score: float,
                              authenticity_score: float,
                              word_count: int) -> SubmissionMetrics:
    """Convenience function to create SubmissionMetrics."""
    return SubmissionMetrics(
        student_id=student_id,
        student_name=student_name,
        suspicious_score=suspicious_score,
        authenticity_score=authenticity_score,
        word_count=word_count
    )
