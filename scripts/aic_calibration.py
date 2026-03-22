#!/usr/bin/env python3
"""
AIC Calibration Script — Before/After Measurement Tool

Runs DishonestyAnalyzer on test corpora in both discussion and essay modes,
then reports score distributions, separation metrics, and differential impact.

Usage:
    python scripts/aic_calibration.py                   # Full run, print report
    python scripts/aic_calibration.py --save baseline   # Save results as named snapshot
    python scripts/aic_calibration.py --diff baseline   # Compare current to saved snapshot
    python scripts/aic_calibration.py --sample 100      # Limit DAIGT sample size
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Add src/ to path so we can import project modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from Academic_Dishonesty_Check_v2 import DishonestyAnalyzer, AnalysisResult
from assignment_templates import aic_config_from_mode

# ── Data paths ──────────────────────────────────────────────────────────────

AI_ESSAYS_PATH = PROJECT_ROOT / "data" / "demo_source" / "ai_essay_aic_results.json"
CLAUDE_ESSAYS_PATH = PROJECT_ROOT / "data" / "demo_source" / "claude_test_essays.json"
DAIGT_PATH = PROJECT_ROOT / "data" / "demo_source" / "daigt_filtered.json"
SNAPSHOTS_DIR = PROJECT_ROOT / "data" / "calibration_snapshots"


# ── Helpers ─────────────────────────────────────────────────────────────────

def git_commit_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, text=True,
        ).strip()
    except Exception:
        return "unknown"


def _load_essays_from(path: Path) -> list[dict]:
    """Load AI essay texts from a JSON file."""
    if not path.exists():
        return []
    with open(path) as f:
        data = json.load(f)
    essays = data.get("essays", data) if isinstance(data, dict) else data
    result = []
    for e in essays:
        text = e.get("text", "")
        if not text:
            continue
        result.append({
            "id": e.get("label", "unknown"),
            "source": e.get("source", "unknown"),
            "text": text,
            "group": "ai",
        })
    return result


def load_ai_essays() -> list[dict]:
    """Load AI essay texts from all sources."""
    result = _load_essays_from(AI_ESSAYS_PATH)
    result += _load_essays_from(CLAUDE_ESSAYS_PATH)
    return result


def load_daigt_essays(sample_size: int | None = None) -> list[dict]:
    """Load human DAIGT essays (sample if specified)."""
    with open(DAIGT_PATH) as f:
        data = json.load(f)
    if not isinstance(data, list):
        print(f"  Warning: DAIGT data is not a list, type={type(data)}")
        return []

    # Take a deterministic sample if requested
    if sample_size and sample_size < len(data):
        # Use every Nth entry for deterministic sampling
        step = len(data) // sample_size
        data = data[::step][:sample_size]

    result = []
    for entry in data:
        text = entry.get("text", "")
        if not text or len(text.split()) < 20:
            continue
        result.append({
            "id": entry.get("source_id", "unknown"),
            "source": entry.get("source", "daigt"),
            "text": text,
            "group": "human",
        })
    return result


def run_aic(essays: list[dict], mode: str) -> list[dict]:
    """Run AIC on all essays in the given mode. Returns list of result dicts."""
    aic_config = aic_config_from_mode(mode)
    analyzer = DishonestyAnalyzer(
        context_profile="standard",
        aic_config=aic_config,
    )

    results = []
    for essay in essays:
        try:
            result = analyzer.analyze_text(
                text=essay["text"],
                student_id=essay["id"],
                student_name=essay["id"],
            )
            # Extract structural signals from organizational analysis
            org = result.organizational_analysis or {}
            sent = org.get("sentence_analysis", {})
            entry = {
                "id": essay["id"],
                "source": essay["source"],
                "group": essay["group"],
                "mode": mode,
                "suspicious_score": result.suspicious_score,
                "adjusted_suspicious_score": result.adjusted_suspicious_score,
                "authenticity_score": result.authenticity_score,
                "concern_level": result.concern_level,
                "adjusted_concern_level": result.adjusted_concern_level,
                "human_presence_confidence": result.human_presence_confidence,
                "human_presence_level": result.human_presence_level,
                "ai_organizational_score": result.ai_organizational_score,
                "marker_counts": result.marker_counts,
                "word_count": result.word_count,
                "context_adjustments": result.context_adjustments_applied,
                # Structural engagement signals
                "sentence_vc": sent.get("variance_coefficient"),
                "starter_diversity": sent.get("starter_diversity"),
                "comma_density": sent.get("comma_density"),
                "avg_word_length": sent.get("avg_word_length"),
            }
            results.append(entry)
        except Exception as e:
            print(f"  Error on {essay['id']}: {e}")
            continue
    return results


# ── Analysis ────────────────────────────────────────────────────────────────

def compute_stats(values: list[float]) -> dict:
    """Compute basic statistics for a list of values."""
    if not values:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "stdev": 0}
    return {
        "count": len(values),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "stdev": round(statistics.stdev(values), 3) if len(values) > 1 else 0,
    }


def separation_metric(ai_scores: list[float], human_scores: list[float]) -> float:
    """Cohen's d-like separation: (mean_ai - mean_human) / pooled_std."""
    if not ai_scores or not human_scores:
        return 0.0
    mean_ai = statistics.mean(ai_scores)
    mean_human = statistics.mean(human_scores)
    var_ai = statistics.variance(ai_scores) if len(ai_scores) > 1 else 0
    var_human = statistics.variance(human_scores) if len(human_scores) > 1 else 0
    pooled_std = ((var_ai + var_human) / 2) ** 0.5
    if pooled_std == 0:
        return float("inf") if mean_ai != mean_human else 0.0
    return round((mean_ai - mean_human) / pooled_std, 3)


def analyze_group(results: list[dict], group: str, mode: str) -> dict:
    """Analyze results for a specific group+mode combination."""
    filtered = [r for r in results if r["group"] == group and r["mode"] == mode]
    if not filtered:
        return {"count": 0}

    sus_scores = [r["suspicious_score"] for r in filtered]
    auth_scores = [r["authenticity_score"] for r in filtered]
    hp_scores = [r["human_presence_confidence"] for r in filtered
                 if r["human_presence_confidence"] is not None]
    org_scores = [r["ai_organizational_score"] for r in filtered]
    concern_dist = Counter(r["concern_level"] for r in filtered)

    return {
        "count": len(filtered),
        "suspicious": compute_stats(sus_scores),
        "authenticity": compute_stats(auth_scores),
        "human_presence": compute_stats(hp_scores),
        "ai_org": compute_stats(org_scores),
        "concern_levels": dict(concern_dist),
    }


def print_report(all_results: list[dict], ai_essays: list[dict]):
    """Print a formatted calibration report."""
    modes = ["discussion", "essay"]

    print("=" * 72)
    print("AIC CALIBRATION REPORT")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"  Git:  {git_commit_hash()}")
    print("=" * 72)

    for mode in modes:
        print(f"\n{'─' * 72}")
        print(f"MODE: {mode.upper()}")
        print(f"{'─' * 72}")

        for group, label in [("ai", "AI Essays"), ("human", "DAIGT Human Essays")]:
            stats = analyze_group(all_results, group, mode)
            if stats["count"] == 0:
                continue
            print(f"\n  {label} (n={stats['count']}):")
            print(f"    Suspicious:  {_fmt_stats(stats['suspicious'])}")
            print(f"    Authenticity:{_fmt_stats(stats['authenticity'])}")
            print(f"    HP Conf:     {_fmt_stats(stats['human_presence'])}")
            print(f"    AI Org:      {_fmt_stats(stats['ai_org'])}")
            print(f"    Concern:     {stats['concern_levels']}")

        # Separation metric
        ai_sus = [r["suspicious_score"] for r in all_results
                  if r["group"] == "ai" and r["mode"] == mode]
        human_sus = [r["suspicious_score"] for r in all_results
                     if r["group"] == "human" and r["mode"] == mode]
        sep = separation_metric(ai_sus, human_sus)
        print(f"\n  Separation (Cohen's d): {sep}")

    # Per-AI-essay detail
    print(f"\n{'─' * 72}")
    print("PER-AI-ESSAY BREAKDOWN")
    print(f"{'─' * 72}")
    for mode in modes:
        print(f"\n  Mode: {mode}")
        mode_results = [r for r in all_results if r["group"] == "ai" and r["mode"] == mode]
        for r in mode_results:
            print(f"    {r['source']} ({r['id']}): "
                  f"sus={r['suspicious_score']:.2f}, "
                  f"auth={r['authenticity_score']:.2f}, "
                  f"hp={r['human_presence_confidence'] or 0:.1f}%, "
                  f"org={r['ai_organizational_score']:.2f}, "
                  f"concern={r['concern_level']}")
            # Structural signals
            vc = r.get("sentence_vc")
            sd = r.get("starter_diversity")
            cd = r.get("comma_density")
            awl = r.get("avg_word_length")
            parts = []
            if vc is not None: parts.append(f"sent_vc={vc:.3f}")
            if sd is not None: parts.append(f"starter_div={sd:.3f}")
            if cd is not None: parts.append(f"comma_den={cd:.2f}")
            if awl is not None: parts.append(f"avg_wl={awl:.2f}")
            if parts:
                print(f"      signals: {', '.join(parts)}")
            # Show convergence or hp_absence if present
            ctx = [a for a in r.get("context_adjustments", [])
                   if "convergence" in a.lower() or "hp_absence" in a.lower()
                   or "human presence" in a.lower()]
            for c in ctx:
                print(f"      → {c}")

    # False positive summary
    print(f"\n{'─' * 72}")
    print("FALSE POSITIVE ANALYSIS (DAIGT)")
    print(f"{'─' * 72}")
    for mode in modes:
        human_results = [r for r in all_results
                         if r["group"] == "human" and r["mode"] == mode]
        if not human_results:
            continue
        total = len(human_results)
        elevated_plus = sum(1 for r in human_results
                           if r["concern_level"] in ("elevated", "high"))
        moderate_plus = sum(1 for r in human_results
                           if r["concern_level"] in ("moderate", "elevated", "high"))
        print(f"\n  Mode: {mode} (n={total})")
        print(f"    Elevated+:  {elevated_plus}/{total} = {elevated_plus/total*100:.1f}%")
        print(f"    Moderate+:  {moderate_plus}/{total} = {moderate_plus/total*100:.1f}%")

    print(f"\n{'=' * 72}")


def _fmt_stats(s: dict) -> str:
    if s["count"] == 0:
        return " (no data)"
    return (f" min={s['min']:.2f}  max={s['max']:.2f}  "
            f"mean={s['mean']:.2f}  median={s['median']:.2f}  "
            f"stdev={s['stdev']:.2f}")


def diff_snapshots(current: list[dict], baseline: list[dict]):
    """Compare current results to a baseline snapshot."""
    print(f"\n{'─' * 72}")
    print("DIFFERENTIAL IMPACT (vs baseline)")
    print(f"{'─' * 72}")

    # Index baseline by (id, mode)
    base_idx = {}
    for r in baseline:
        base_idx[(r["id"], r["mode"])] = r

    CONCERN_ORDER = {"none": 0, "low": 1, "moderate": 2, "elevated": 3, "high": 4}
    worsened = []

    for r in current:
        key = (r["id"], r["mode"])
        if key not in base_idx:
            continue
        b = base_idx[key]
        cur_level = CONCERN_ORDER.get(r["concern_level"], 0)
        base_level = CONCERN_ORDER.get(b["concern_level"], 0)
        if cur_level > base_level and r["group"] == "human":
            worsened.append({
                "id": r["id"],
                "mode": r["mode"],
                "baseline_concern": b["concern_level"],
                "current_concern": r["concern_level"],
                "baseline_sus": b["suspicious_score"],
                "current_sus": r["suspicious_score"],
            })

    if worsened:
        print(f"\n  DAIGT essays with WORSENED concern level: {len(worsened)}")
        for w in worsened[:20]:
            print(f"    {w['id']} ({w['mode']}): "
                  f"{w['baseline_concern']} → {w['current_concern']} "
                  f"(sus: {w['baseline_sus']:.2f} → {w['current_sus']:.2f})")
        if len(worsened) > 20:
            print(f"    ... and {len(worsened) - 20} more")
    else:
        print("\n  No DAIGT essays worsened in concern level.")


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AIC Calibration Tool")
    parser.add_argument("--save", type=str, help="Save results as named snapshot")
    parser.add_argument("--diff", type=str, help="Compare to named snapshot")
    parser.add_argument("--sample", type=int, default=200,
                        help="DAIGT sample size (default: 200)")
    args = parser.parse_args()

    print("Loading test data...")
    ai_essays = load_ai_essays()
    daigt_essays = load_daigt_essays(sample_size=args.sample)
    all_essays = ai_essays + daigt_essays
    print(f"  AI essays: {len(ai_essays)}")
    print(f"  DAIGT essays: {len(daigt_essays)}")

    print("\nRunning AIC in discussion mode...")
    discussion_results = run_aic(all_essays, "discussion")
    print(f"  Scored {len(discussion_results)} essays")

    print("Running AIC in essay mode...")
    essay_results = run_aic(all_essays, "essay")
    print(f"  Scored {len(essay_results)} essays")

    all_results = discussion_results + essay_results

    # Print report
    print_report(all_results, ai_essays)

    # Save snapshot if requested
    if args.save:
        SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "git_commit": git_commit_hash(),
            "ai_count": len(ai_essays),
            "daigt_count": len(daigt_essays),
            "results": all_results,
        }
        path = SNAPSHOTS_DIR / f"{args.save}.json"
        with open(path, "w") as f:
            json.dump(snapshot, f, indent=2)
        print(f"\nSnapshot saved: {path}")

    # Diff against baseline if requested
    if args.diff:
        path = SNAPSHOTS_DIR / f"{args.diff}.json"
        if not path.exists():
            print(f"\nError: snapshot '{args.diff}' not found at {path}")
            return
        with open(path) as f:
            baseline = json.load(f)
        diff_snapshots(all_results, baseline["results"])


if __name__ == "__main__":
    main()
