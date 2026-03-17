"""
CrossValidator — Compare LLM outputs against non-LLM signals.

When LLM and signal matrix agree, confidence is high.
When they disagree, surface it honestly — the teacher decides.

This is the self-improving quality layer. Cross-validation tells
the teacher (and us) how much to trust the analysis.
"""

import logging
from typing import Dict, List, Set

from insights.models import ValidationFlag

log = logging.getLogger(__name__)


class CrossValidator:
    """Compare LLM analysis results against non-LLM signal matrix output."""

    def validate_concerns(
        self,
        coding_records: list,
        concern_signals: list,
    ) -> List[ValidationFlag]:
        """Compare LLM concern flags against VADER+keyword signal matrix.

        Agreement = high confidence.
        LLM flags but matrix doesn't = possible LLM hallucination or bias.
        Matrix flags but LLM doesn't = LLM may have missed something.
        """
        flags = []

        # Build sets of flagged student IDs from each source
        llm_flagged: Dict[str, str] = {}  # student_id → summary
        for rec in coding_records:
            concerns = rec.get("concerns", [])
            if hasattr(rec, "concerns"):
                concerns = rec.concerns
            if hasattr(rec, "student_id"):
                sid = rec.student_id
                sname = rec.student_name
            else:
                sid = rec.get("student_id", "")
                sname = rec.get("student_name", "")

            concern_list = concerns if isinstance(concerns, list) else []
            if concern_list:
                reasons = []
                for c in concern_list:
                    if hasattr(c, "why_flagged"):
                        reasons.append(c.why_flagged)
                    elif isinstance(c, dict):
                        reasons.append(c.get("why_flagged", ""))
                llm_flagged[sid] = f"{sname}: {'; '.join(r for r in reasons if r)}"

        matrix_flagged: Dict[str, str] = {}  # student_id → summary
        for sig in concern_signals:
            if hasattr(sig, "student_id"):
                sid = sig.student_id
                sname = sig.student_name
                sig_type = sig.signal_type
                interp = sig.interpretation
            else:
                sid = sig.get("student_id", "")
                sname = sig.get("student_name", "")
                sig_type = sig.get("signal_type", "")
                interp = sig.get("interpretation", "")

            # Only count actual concerns, not APPROPRIATE
            if sig_type in ("APPROPRIATE",):
                continue
            matrix_flagged[sid] = f"{sname}: {sig_type} — {interp}"

        all_flagged = set(llm_flagged) | set(matrix_flagged)

        for sid in all_flagged:
            in_llm = sid in llm_flagged
            in_matrix = sid in matrix_flagged

            if in_llm and in_matrix:
                flags.append(ValidationFlag(
                    domain="concerns",
                    student_id=sid,
                    student_name=_extract_name(llm_flagged.get(sid, "")),
                    llm_says=llm_flagged.get(sid, ""),
                    matrix_says=matrix_flagged.get(sid, ""),
                    agreement="agree",
                    confidence_note="Both LLM and signal matrix flagged this student — high confidence.",
                ))
            elif in_llm:
                flags.append(ValidationFlag(
                    domain="concerns",
                    student_id=sid,
                    student_name=_extract_name(llm_flagged.get(sid, "")),
                    llm_says=llm_flagged.get(sid, ""),
                    matrix_says="(not flagged)",
                    agreement="llm_only",
                    confidence_note=(
                        "LLM flagged but signal matrix did not. "
                        "Could be a genuine nuance the matrix missed, "
                        "or possible LLM over-sensitivity."
                    ),
                ))
            else:
                flags.append(ValidationFlag(
                    domain="concerns",
                    student_id=sid,
                    student_name=_extract_name(matrix_flagged.get(sid, "")),
                    llm_says="(not flagged)",
                    matrix_says=matrix_flagged.get(sid, ""),
                    agreement="matrix_only",
                    confidence_note=(
                        "Signal matrix flagged but LLM did not. "
                        "The keyword/sentiment pattern is there — "
                        "the LLM may have interpreted context differently."
                    ),
                ))

        return flags

    def validate_themes(
        self,
        llm_themes: list,
        embedding_clusters: list,
    ) -> List[ValidationFlag]:
        """Compare LLM themes against embedding clusters.

        Do the LLM's theme groupings align with how embeddings cluster?
        Major misalignment = flag for review.
        """
        flags = []
        if not llm_themes or not embedding_clusters:
            return flags

        # Extract student sets from LLM themes
        llm_groups: Dict[str, Set[str]] = {}
        for theme in llm_themes:
            name = theme.get("name", "") if isinstance(theme, dict) else getattr(theme, "name", "")
            sids = theme.get("student_ids", []) if isinstance(theme, dict) else getattr(theme, "student_ids", [])
            if name and sids:
                llm_groups[name] = set(sids)

        # Extract student sets from embedding clusters
        cluster_groups: Dict[str, Set[str]] = {}
        for cluster in embedding_clusters:
            cid = cluster.get("cluster_id", 0) if isinstance(cluster, dict) else getattr(cluster, "cluster_id", 0)
            sids = cluster.get("student_ids", []) if isinstance(cluster, dict) else getattr(cluster, "student_ids", [])
            terms = cluster.get("top_terms", []) if isinstance(cluster, dict) else getattr(cluster, "top_terms", [])
            label = f"Cluster {cid} ({', '.join(terms[:3])})" if terms else f"Cluster {cid}"
            if sids:
                cluster_groups[label] = set(sids)

        if not llm_groups or not cluster_groups:
            return flags

        # Check alignment: for each LLM theme, find the best-matching cluster
        for theme_name, theme_sids in llm_groups.items():
            if not theme_sids:
                continue
            best_overlap = 0.0
            best_cluster = ""
            for c_name, c_sids in cluster_groups.items():
                if not c_sids:
                    continue
                overlap = len(theme_sids & c_sids) / len(theme_sids | c_sids)
                if overlap > best_overlap:
                    best_overlap = overlap
                    best_cluster = c_name

            if best_overlap < 0.2:
                flags.append(ValidationFlag(
                    domain="themes",
                    llm_says=f'Theme "{theme_name}" groups {len(theme_sids)} students',
                    matrix_says=f"No embedding cluster aligns well (best overlap: {best_overlap:.0%} with {best_cluster})",
                    agreement="llm_only",
                    confidence_note=(
                        "LLM theme grouping doesn't match embedding clusters. "
                        "The theme may be conceptually valid but not reflected in "
                        "vocabulary patterns — worth reviewing."
                    ),
                ))

        return flags

    def validate_outliers(
        self,
        llm_outliers: list,
        embedding_outlier_ids: List[str],
    ) -> List[ValidationFlag]:
        """Compare LLM outliers against embedding-based outliers.

        Both flagged same student = high confidence.
        Only one flagged = moderate confidence — still surface but note.
        """
        flags = []

        llm_ids: Dict[str, str] = {}
        for out in llm_outliers:
            if isinstance(out, dict):
                sid = out.get("student_id", "")
                sname = out.get("student_name", "")
                why = out.get("why_notable", "")
            else:
                sid = getattr(out, "student_id", "")
                sname = getattr(out, "student_name", "")
                why = getattr(out, "why_notable", "")
            if sid:
                llm_ids[sid] = f"{sname}: {why}"

        embed_set = set(embedding_outlier_ids)
        all_outlier_ids = set(llm_ids) | embed_set

        for sid in all_outlier_ids:
            in_llm = sid in llm_ids
            in_embed = sid in embed_set

            if in_llm and in_embed:
                flags.append(ValidationFlag(
                    domain="outliers",
                    student_id=sid,
                    student_name=_extract_name(llm_ids.get(sid, "")),
                    llm_says=llm_ids.get(sid, ""),
                    matrix_says="Embedding outlier (distant from all clusters)",
                    agreement="agree",
                    confidence_note="Both methods identify this student as distinctive — high confidence.",
                ))
            elif in_llm:
                flags.append(ValidationFlag(
                    domain="outliers",
                    student_id=sid,
                    student_name=_extract_name(llm_ids.get(sid, "")),
                    llm_says=llm_ids.get(sid, ""),
                    matrix_says="(not an embedding outlier)",
                    agreement="llm_only",
                    confidence_note="LLM found this notable but embedding analysis didn't flag it as distant.",
                ))
            else:
                flags.append(ValidationFlag(
                    domain="outliers",
                    student_id=sid,
                    llm_says="(not flagged by LLM)",
                    matrix_says="Embedding outlier",
                    agreement="matrix_only",
                    confidence_note="Embedding analysis flags this student as distant from peers, but LLM didn't surface them.",
                ))

        return flags


def _extract_name(summary: str) -> str:
    """Extract the student name from a 'Name: details' summary string."""
    if ":" in summary:
        return summary.split(":")[0].strip()
    return ""
