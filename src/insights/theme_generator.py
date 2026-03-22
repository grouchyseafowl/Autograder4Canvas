"""
Theme generation and outlier surfacing for the Insights Engine.

Tier logic for theme generation:
  Lightweight: hierarchical — groups of 10-15 records -> theme sets -> meta-synthesis merge
  Medium: groups of 20-25
  Deep: all records in one call (if context allows, else groups of 30+)

Groups formed by embedding cluster (from Quick Analysis), not arbitrarily.
Contradictions are first-class data, not an afterthought.
"""

import json
import logging
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, List, Optional

from insights.llm_backend import BackendConfig, parse_json_response, send_text
from insights.models import (
    Contradiction,
    OutlierRecord,
    OutlierReport,
    QuoteRecord,
    SubmissionCodingRecord,
    Theme,
    ThemeSet,
)
from insights.prompts import (
    ANALYSIS_LENS_PROMPT_FRAGMENT,
    INTEREST_AREAS_FRAGMENT,
    OUTLIER_ANALYSIS_PROMPT,
    SYSTEM_PROMPT,
    THEME_GENERATION_PROMPT,
    THEME_META_SYNTHESIS_PROMPT,
)

log = logging.getLogger(__name__)

# Group size limits by tier
_GROUP_SIZES = {
    "lightweight": 5,   # Tiny groups for 8B — larger batches timeout on 20+ students
    "medium": 15,
    "deep_thinking": 30,
}

# Per-call timeout (seconds). If the LLM hasn't responded in this window,
# we fall back to a non-LLM result so the pipeline doesn't stall.
_LLM_CALL_TIMEOUT = 300  # 5 minutes

# Max tokens per stage — tight limits prevent MLX from running away.
# These are well above what a correct response needs; they guard against
# the model looping or generating until context exhaustion.
_MAX_TOKENS_THEME = {
    "lightweight":   1200,  # JSON theme set for 5 students: ~600–900 tokens
    "medium":        2000,
    "deep_thinking": 3000,
}
_MAX_TOKENS_META = {
    "lightweight":   1500,  # Merge 8 theme groups: ~900–1200 tokens
    "medium":        2500,
    "deep_thinking": 4096,
}


def _fallback_theme_set_from_records(
    records: List["SubmissionCodingRecord"],
) -> "ThemeSet":
    """Build a ThemeSet without LLM, from tag frequency in the records.

    Used when an LLM call times out so the pipeline can continue.
    """
    tag_counter: Counter = Counter()
    tag_students: Dict[str, List[str]] = {}
    for r in records:
        for tag in r.theme_tags:
            tag_counter[tag] += 1
            tag_students.setdefault(tag, []).append(r.student_id)

    themes = []
    for tag, count in tag_counter.most_common(10):
        if tag in ("insufficient text for analysis",
                    "file upload — text not extracted",
                    "blank submission"):
            continue  # Skip infrastructure tags
        themes.append(Theme(
            name=tag,
            description=f"Auto-grouped from coding tag '{tag}' (LLM timed out)",
            frequency=count,
            student_ids=tag_students.get(tag, []),
            supporting_quotes=[],
            confidence=0.3,
        ))

    if not themes and records:
        # No tags at all — create a single placeholder theme
        themes.append(Theme(
            name="(theme generation timed out)",
            description=(
                f"LLM theme generation timed out for {len(records)} records. "
                f"Try resuming the run or reducing the number of submissions."
            ),
            frequency=len(records),
            student_ids=[r.student_id for r in records],
            supporting_quotes=[],
            confidence=0.1,
        ))

    return ThemeSet(themes=themes, contradictions=[])


def _build_interests_fragment(teacher_interests: list) -> str:
    if not teacher_interests:
        return ""
    summary = ", ".join(f"({i+1}) {interest}" for i, interest in enumerate(teacher_interests[:3]))
    return INTEREST_AREAS_FRAGMENT.format(interests_summary=summary)


def _build_lens_fragment(analysis_lens: Optional[Dict]) -> str:
    if not analysis_lens:
        return ""
    criteria = [f"- {name}: {desc}" for name, desc in analysis_lens.items()]
    if not criteria:
        return ""
    return ANALYSIS_LENS_PROMPT_FRAGMENT.format(lens_criteria="\n".join(criteria))


def _records_to_compact_json(records: List[SubmissionCodingRecord]) -> str:
    """Convert coding records to compact JSON for prompt injection.

    Includes only the fields the theme generator needs, to conserve context.
    Stripped to the minimum viable set: tags, confidence, register, quote.
    readings/concepts/connections removed — they bloat context on 8B models
    and themes are primarily driven by the four retained fields.
    """
    compact = []
    for r in records:
        best_quote = ""
        if r.notable_quotes:
            best_quote = r.notable_quotes[0].text[:200]
        entry = {
            "name": r.student_name,
            "id": r.student_id,
            "tags": r.theme_tags[:5],
            "confidence": {
                t: c for t, c in list(r.theme_confidence.items())[:5]
            } if r.theme_confidence else {},
            "register": r.emotional_register,
            "quote": best_quote,
        }
        compact.append(entry)
    return json.dumps(compact, separators=(",", ":"))


def _group_by_cluster(
    records: List[SubmissionCodingRecord], group_size: int
) -> List[List[SubmissionCodingRecord]]:
    """Group records by embedding cluster, then split into batches of group_size.

    Records without a cluster ID go into an "ungrouped" pool.
    """
    clusters: Dict[int, List[SubmissionCodingRecord]] = {}
    ungrouped: List[SubmissionCodingRecord] = []

    for r in records:
        if r.cluster_id is not None:
            clusters.setdefault(r.cluster_id, []).append(r)
        else:
            ungrouped.append(r)

    # Build groups: keep cluster members together, fill with ungrouped
    groups: List[List[SubmissionCodingRecord]] = []
    current: List[SubmissionCodingRecord] = []

    for cid in sorted(clusters.keys()):
        cluster_records = clusters[cid]
        if len(current) + len(cluster_records) <= group_size:
            current.extend(cluster_records)
        else:
            if current:
                groups.append(current)
            # If cluster is bigger than group_size, split it
            if len(cluster_records) > group_size:
                for i in range(0, len(cluster_records), group_size):
                    groups.append(cluster_records[i: i + group_size])
                current = []
            else:
                current = cluster_records

    # Add ungrouped records
    for r in ungrouped:
        if len(current) >= group_size:
            groups.append(current)
            current = []
        current.append(r)

    if current:
        groups.append(current)

    return groups


def _parse_theme_set(parsed: dict) -> ThemeSet:
    """Convert parsed JSON to a ThemeSet model."""
    themes = []
    for t in parsed.get("themes", []):
        if not isinstance(t, dict):
            continue
        quotes = []
        for q in t.get("supporting_quotes", [])[:4]:
            if isinstance(q, dict) and q.get("text"):
                quotes.append(QuoteRecord(text=q["text"], significance=q.get("significance", "")))
        themes.append(Theme(
            name=t.get("name", ""),
            description=t.get("description", ""),
            frequency=int(t.get("frequency", 0)),
            student_ids=t.get("student_ids", []),
            supporting_quotes=quotes,
            confidence=float(t.get("confidence", 0.5)),
            sub_themes=t.get("sub_themes"),
        ))

    contradictions = []
    for c in parsed.get("contradictions", []):
        if not isinstance(c, dict):
            continue
        contradictions.append(Contradiction(
            description=c.get("description", ""),
            side_a=c.get("side_a", ""),
            side_a_students=c.get("side_a_students", []),
            side_b=c.get("side_b", ""),
            side_b_students=c.get("side_b_students", []),
            pedagogical_significance=c.get("pedagogical_significance", ""),
        ))

    return ThemeSet(themes=themes, contradictions=contradictions)


def generate_themes(
    coding_records: List[SubmissionCodingRecord],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
    analysis_lens: Optional[Dict] = None,
    teacher_interests: Optional[list] = None,
    profile_fragment: str = "",
) -> ThemeSet:
    """Generate themes from coding records.

    Returns a ThemeSet with themes and contradictions.
    """
    if not coding_records:
        return ThemeSet()

    group_size = _GROUP_SIZES.get(tier, 12)
    interests_text = _build_interests_fragment(teacher_interests)
    lens_fragment = _build_lens_fragment(analysis_lens)

    # If all records fit in one group, single call
    if len(coding_records) <= group_size:
        return _generate_single(
            coding_records, assignment_name, interests_text, lens_fragment,
            backend, profile_fragment, tier=tier,
        )

    # Hierarchical: group -> theme sets -> meta-synthesis
    groups = _group_by_cluster(coding_records, group_size)
    log.info("Theme generation: %d records in %d groups (tier=%s, group_size=%d)",
             len(coding_records), len(groups), tier, group_size)

    group_theme_sets = []
    for i, group in enumerate(groups):
        log.info("  Generating themes for group %d/%d (%d records)", i + 1, len(groups), len(group))
        ts = _generate_single(
            group, assignment_name, interests_text, lens_fragment,
            backend, profile_fragment, tier=tier,
        )
        group_theme_sets.append(ts)

    if len(group_theme_sets) == 1:
        return group_theme_sets[0]

    # Meta-synthesis: merge group theme sets
    return _meta_synthesize(
        group_theme_sets, assignment_name, interests_text, backend,
        profile_fragment, tier=tier,
    )


def _generate_single(
    records: List[SubmissionCodingRecord],
    assignment_name: str,
    interests_text: str,
    lens_fragment: str,
    backend: BackendConfig,
    profile_fragment: str = "",
    tier: str = "lightweight",
) -> ThemeSet:
    """Generate themes from a single group of records.

    Wrapped with a timeout — if the LLM call exceeds _LLM_CALL_TIMEOUT
    seconds, returns a fallback ThemeSet built from tag frequencies so the
    pipeline doesn't stall on slow 8B models.
    """
    _max_tok = _MAX_TOKENS_THEME.get(tier, 1200)

    def _inner() -> ThemeSet:
        prompt = THEME_GENERATION_PROMPT.format(
            n_records=len(records),
            assignment_name=assignment_name,
            teacher_interests=interests_text,
            records_json=_records_to_compact_json(records),
            lens_fragment=lens_fragment,
            profile_fragment=profile_fragment,
        )

        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=_max_tok)
        parsed = parse_json_response(raw)

        if "_parse_error" in parsed:
            log.warning("Theme generation JSON parse failed, retrying")
            from insights.prompts import JSON_REPAIR_PROMPT
            repair = JSON_REPAIR_PROMPT.format(
                raw_response=raw[:2000],
                expected_format='{"themes": [...], "contradictions": [...]}',
            )
            raw2 = send_text(backend, repair, SYSTEM_PROMPT, max_tokens=_max_tok)
            parsed2 = parse_json_response(raw2)
            return _parse_theme_set(parsed2)

        return _parse_theme_set(parsed)

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_inner)
        return future.result(timeout=_LLM_CALL_TIMEOUT)
    except FuturesTimeoutError:
        log.warning(
            "Theme generation timed out after %ds for %d records — "
            "falling back to tag-frequency themes",
            _LLM_CALL_TIMEOUT, len(records),
        )
        # Don't wait for the orphaned thread — let it finish on its own
        pool.shutdown(wait=False, cancel_futures=True)
        return _fallback_theme_set_from_records(records)
    except Exception as exc:
        log.warning(
            "Theme generation failed (%s) for %d records — "
            "falling back to tag-frequency themes",
            exc, len(records),
        )
        return _fallback_theme_set_from_records(records)
    finally:
        pool.shutdown(wait=False)


def _meta_synthesize(
    theme_sets: List[ThemeSet],
    assignment_name: str,
    interests_text: str,
    backend: BackendConfig,
    profile_fragment: str = "",
    tier: str = "lightweight",
) -> ThemeSet:
    """Merge multiple ThemeSets into one via meta-synthesis LLM call.

    Wrapped with a timeout — falls back to _manual_merge if the LLM
    exceeds _LLM_CALL_TIMEOUT seconds.
    """
    _max_tok = _MAX_TOKENS_META.get(tier, 1500)

    def _inner() -> ThemeSet:
        sets_json = []
        for i, ts in enumerate(theme_sets):
            sets_json.append({
                "group": i + 1,
                "themes": [
                    {
                        "name": t.name,
                        "description": t.description,
                        "frequency": t.frequency,
                        "student_ids": t.student_ids,
                        "confidence": t.confidence,
                        "supporting_quotes": [
                            {"text": q.text, "significance": q.significance}
                            for q in t.supporting_quotes[:2]
                        ],
                    }
                    for t in ts.themes
                ],
                "contradictions": [
                    {
                        "description": c.description,
                        "side_a": c.side_a,
                        "side_a_students": c.side_a_students,
                        "side_b": c.side_b,
                        "side_b_students": c.side_b_students,
                    }
                    for c in ts.contradictions
                ],
            })

        prompt = THEME_META_SYNTHESIS_PROMPT.format(
            n_groups=len(theme_sets),
            assignment_name=assignment_name,
            teacher_interests=interests_text,
            theme_sets_json=json.dumps(sets_json, indent=1),
            profile_fragment=profile_fragment,
        )

        raw = send_text(backend, prompt, SYSTEM_PROMPT, max_tokens=_max_tok)
        parsed = parse_json_response(raw)

        if "_parse_error" in parsed:
            log.warning("Meta-synthesis parse failed — combining theme sets manually")
            return _manual_merge(theme_sets)

        return _parse_theme_set(parsed)

    pool = ThreadPoolExecutor(max_workers=1)
    try:
        future = pool.submit(_inner)
        return future.result(timeout=_LLM_CALL_TIMEOUT)
    except FuturesTimeoutError:
        log.warning(
            "Meta-synthesis timed out after %ds for %d theme sets — "
            "falling back to manual merge",
            _LLM_CALL_TIMEOUT, len(theme_sets),
        )
        pool.shutdown(wait=False, cancel_futures=True)
        return _manual_merge(theme_sets)
    finally:
        pool.shutdown(wait=False)


def _manual_merge(theme_sets: List[ThemeSet]) -> ThemeSet:
    """Fallback: combine theme sets without LLM synthesis."""
    all_themes = []
    all_contradictions = []
    for ts in theme_sets:
        all_themes.extend(ts.themes)
        all_contradictions.extend(ts.contradictions)
    return ThemeSet(themes=all_themes, contradictions=all_contradictions)


# ---------------------------------------------------------------------------
# Outlier surfacing
# ---------------------------------------------------------------------------

def surface_outliers(
    theme_set: ThemeSet,
    coding_records: List[SubmissionCodingRecord],
    embedding_outlier_ids: List[str],
    *,
    tier: str,
    backend: BackendConfig,
    assignment_name: str = "",
) -> OutlierReport:
    """Identify and explain outlier submissions.

    Outliers = records whose theme tags don't match any generated theme
    + records flagged as unique by embedding clustering.
    """
    if not theme_set.themes:
        return OutlierReport()

    theme_names = {t.name.lower() for t in theme_set.themes}
    theme_student_ids = set()
    for t in theme_set.themes:
        theme_student_ids.update(t.student_ids)

    # Find coding-based outliers: records with no theme tag matching a generated theme
    coding_outliers = []
    for r in coding_records:
        if r.student_id in theme_student_ids:
            continue
        # Also check if their tags match any theme name
        matched = any(tag.lower() in theme_names for tag in r.theme_tags)
        if not matched:
            coding_outliers.append(r)

    # Combine with embedding outliers
    outlier_ids = set(r.student_id for r in coding_outliers)
    outlier_ids.update(embedding_outlier_ids)

    outlier_records = [r for r in coding_records if r.student_id in outlier_ids]

    if not outlier_records:
        return OutlierReport()

    # Build themes summary for the prompt
    themes_summary = "\n".join(
        f"- {t.name} ({t.frequency} students): {t.description[:100]}"
        for t in theme_set.themes
    )

    # Build outlier data for the prompt
    outliers_data = []
    for r in outlier_records:
        quotes = [{"text": q.text, "significance": q.significance} for q in r.notable_quotes[:2]]
        outliers_data.append({
            "student_id": r.student_id,
            "student_name": r.student_name,
            "theme_tags": r.theme_tags,
            "emotional_register": r.emotional_register,
            "notable_quotes": quotes,
            "in_embedding_outliers": r.student_id in embedding_outlier_ids,
        })

    prompt = OUTLIER_ANALYSIS_PROMPT.format(
        assignment_name=assignment_name,
        themes_summary=themes_summary,
        outliers_json=json.dumps(outliers_data, indent=1),
    )

    try:
        raw = send_text(backend, prompt, SYSTEM_PROMPT)
        parsed = parse_json_response(raw)
    except Exception as exc:
        log.warning("Outlier analysis LLM call failed (%s) — using minimal report", exc)
        return _minimal_outlier_report(outlier_records, embedding_outlier_ids)

    if "_parse_error" in parsed:
        log.warning("Outlier analysis parse failed — using minimal report")
        return _minimal_outlier_report(outlier_records, embedding_outlier_ids)

    # Build OutlierReport
    outliers = []
    for item in parsed.get("outliers", []):
        if not isinstance(item, dict):
            continue
        quote_data = item.get("notable_quote")
        quote = None
        if isinstance(quote_data, dict) and quote_data.get("text"):
            quote = QuoteRecord(
                text=quote_data["text"],
                significance=quote_data.get("significance", ""),
            )
        outliers.append(OutlierRecord(
            student_id=item.get("student_id", ""),
            student_name=item.get("student_name", ""),
            why_notable=item.get("why_notable", ""),
            relationship_to_themes=item.get("relationship_to_themes", ""),
            notable_quote=quote,
            teacher_recommendation=item.get("teacher_recommendation", ""),
        ))

    # Cross-check: mark high confidence if both LLM and embedding agree
    for o in outliers:
        if o.student_id in embedding_outlier_ids:
            if not o.why_notable.endswith(" [confirmed by embedding analysis]"):
                o.why_notable += " [confirmed by embedding analysis]"

    return OutlierReport(outliers=outliers)


def _minimal_outlier_report(
    records: List[SubmissionCodingRecord],
    embedding_outlier_ids: List[str],
) -> OutlierReport:
    """Fallback outlier report when LLM parse fails."""
    outliers = []
    for r in records:
        quote = r.notable_quotes[0] if r.notable_quotes else None
        is_embedding = r.student_id in embedding_outlier_ids
        outliers.append(OutlierRecord(
            student_id=r.student_id,
            student_name=r.student_name,
            why_notable=f"Did not match identified themes. Tags: {', '.join(r.theme_tags)}"
                        + (" [also flagged by embedding analysis]" if is_embedding else ""),
            relationship_to_themes="Could not be determined (LLM analysis unavailable)",
            notable_quote=quote,
            teacher_recommendation="Review this submission — it may contain a unique perspective.",
        ))
    return OutlierReport(outliers=outliers)
