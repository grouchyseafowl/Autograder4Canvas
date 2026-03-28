#!/usr/bin/env python3
"""
Generate Demo Insights — Steps 4+7 of the DAIGT Testing Brief.

Runs the full InsightsEngine pipeline via run_from_submissions() on the
assembled demo corpus. Captures wall-clock timing at each stage.
Outputs baked JSON files to src/demo_assets/.

Usage:
    python scripts/generate_demo_insights.py [--course ethnic_studies|biology|both]
                                              [--small-batch N]
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional

# Add src/ to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_DIR = ROOT / "data" / "demo_corpus"
ASSETS_DIR = ROOT / "src" / "demo_assets"
TIMING_PATH = ROOT / "data" / "demo_source" / "pipeline_timing.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("generate_demo_insights")


# ──────────────────────────────────────────────────────────────
# Configuration per course
# ──────────────────────────────────────────────────────────────

COURSES = {
    "ethnic_studies": {
        "course_id": "90003",
        "course_name": "Ethnic Studies (11), Period 3",
        "assignment_id": "113002",
        "assignment_name": "Week 6 Discussion: Intersectionality in Practice",
        "teacher_context": (
            "This is a weekly discussion board. Students respond to a reading about "
            "intersectionality theory applied to everyday life. Complete/incomplete grading — "
            "150 word minimum. I'm looking for genuine engagement with the concepts, not "
            "polished academic writing."
        ),
        "next_week_topic": (
            "Week 7: Racial Formation — Omi & Winant's framework. Students will read "
            "an excerpt on how race is socially constructed through political struggle "
            "and institutional practice."
        ),
        "corpus_file": "ethnic_studies.json",
        "output_file": "insights_ethnic_studies.json",
        "run_id": "demo-insights-run-eth-studies-000000000001",
    },
    "biology": {
        "course_id": "90005",
        "course_name": "Biology, Period 6",
        "assignment_id": "115001",
        "assignment_name": "Lab Reflection: Cell Respiration",
        "teacher_context": (
            "Lab reflection for the cell respiration experiment. Students measured "
            "CO2 output under different conditions and are asked to reflect on what "
            "the data showed them. Complete/incomplete, 100 word minimum."
        ),
        "corpus_file": "biology.json",
        "output_file": "insights_biology.json",
        "run_id": "demo-insights-run-bio-lab-0000000000001",
    },
}


# ──────────────────────────────────────────────────────────────
# Pipeline runner
# ──────────────────────────────────────────────────────────────

def run_pipeline(course_key: str, small_batch: int = 0,
                 backend_override=None, output_suffix: str = "",
                 tier_override: Optional[str] = None) -> dict:
    """Run the full Insights pipeline for one course via InsightsEngine.

    Args:
        backend_override: Optional BackendConfig to use instead of default.
        output_suffix: If set, appended to output filename (e.g., "_sonnet").
    """
    cfg = COURSES[course_key]
    timing: Dict = {}

    # ── Load corpus ──
    corpus_path = CORPUS_DIR / cfg["corpus_file"]
    corpus = json.loads(corpus_path.read_text())
    if small_batch > 0:
        corpus = corpus[:small_batch]
    total = len(corpus)

    print(f"\n{'═'*60}")
    print(f"  Pipeline: {cfg['course_name']}")
    print(f"  Students: {total}")
    print(f"{'═'*60}")

    # ── Build submission dicts (as QuickAnalyzer expects) ──
    submissions = []
    for s in corpus:
        submissions.append({
            "student_id": s["student_id"],
            "student_name": s["student_name"],
            "body": s["text"],
            "submission_type": "online_text_entry",
            "word_count": s.get("word_count", len(s["text"].split())),
            "submitted_at": "2026-03-08T22:00:00Z",
            "due_at": "2026-03-08T23:59:00Z",
        })

    # ── Build engine ──
    from settings import load_settings
    from insights.engine import InsightsEngine
    from insights.insights_store import InsightsStore

    user_settings = load_settings()
    store = InsightsStore()
    engine = InsightsEngine(api=None, store=store, settings=user_settings)

    # ── Determine tier ──
    if tier_override:
        tier = tier_override
    elif backend_override and backend_override.name == "cloud":
        if "sonnet" in backend_override.model:
            tier = "medium"
        elif "opus" in backend_override.model:
            tier = "deep_thinking"
        else:
            tier = "medium"
    else:
        tier = "lightweight"

    print(f"\n[LLM Backend] "
          f"{backend_override.name if backend_override else 'auto'} / "
          f"{backend_override.model if backend_override else 'auto-detect'} "
          f"(tier={tier})")

    # ── Timing capture ──
    def on_timing(stage_name, elapsed):
        timing[stage_name] = elapsed

    # ── Run the pipeline ──
    run_id = engine.run_from_submissions(
        submissions=submissions,
        course_id=cfg.get("course_id", "0"),
        course_name=cfg.get("course_name", ""),
        assignment_id=cfg.get("assignment_id", "0"),
        assignment_name=cfg.get("assignment_name", ""),
        model_tier=tier,
        teacher_context=cfg.get("teacher_context", ""),
        next_week_topic=cfg.get("next_week_topic", ""),
        progress_callback=lambda msg: print(f"  {msg}"),
        timing_callback=on_timing,
        backend_override=backend_override,
    )

    if run_id is None:
        raise RuntimeError("Pipeline returned None — check logs for errors")

    # ── Extract results from store ──
    run_data = store.get_run(run_id) or {}
    codings_rows = store.get_codings(run_id)
    themes_data = store.get_themes(run_id) or {}
    feedback_rows = store.get_feedback(run_id)

    # ── Assemble baked JSON ──
    # Preserve same structure as before for GUI compatibility.

    # Parse stages_completed from store (stored as JSON string)
    stages_str = run_data.get("stages_completed", "[]")
    if isinstance(stages_str, str):
        try:
            stages_completed = json.loads(stages_str)
        except (json.JSONDecodeError, TypeError):
            stages_completed = []
    else:
        stages_completed = stages_str or []

    # Parse pipeline_confidence
    conf_str = run_data.get("pipeline_confidence", "{}")
    if isinstance(conf_str, str):
        try:
            pipeline_confidence = json.loads(conf_str)
        except (json.JSONDecodeError, TypeError):
            pipeline_confidence = {}
    else:
        pipeline_confidence = conf_str or {}

    run_record = {
        "run_id": run_id,
        "course_id": cfg["course_id"],
        "course_name": cfg["course_name"],
        "assignment_id": cfg["assignment_id"],
        "assignment_name": cfg["assignment_name"],
        "started_at": run_data.get("started_at", ""),
        "completed_at": run_data.get("completed_at", ""),
        "model_tier": tier,
        "model_name": (backend_override.model if backend_override
                       else run_data.get("model_name", "")),
        "total_submissions": total,
        "stages_completed": stages_completed,
        "pipeline_confidence": pipeline_confidence,
        "teacher_context": cfg.get("teacher_context", ""),
        "analysis_lens_config": run_data.get("analysis_lens_config"),
        "quick_analysis": run_data.get("quick_analysis", ""),
    }

    # Build texts map for submission text in baked JSON
    texts = {str(s["student_id"]): s.get("body", s.get("text", ""))
             for s in corpus}

    codings_list = []
    for row in codings_rows:
        # coding_record may be a JSON string or dict depending on store
        cr = row.get("coding_record", {})
        if isinstance(cr, str):
            try:
                cr = json.loads(cr)
            except (json.JSONDecodeError, TypeError):
                cr = {}
        codings_list.append({
            "run_id": run_id,
            "student_id": row["student_id"],
            "student_name": row.get("student_name", ""),
            "coding_record": cr,
            "submission_text": row.get("submission_text",
                                       texts.get(row["student_id"], "")),
            "teacher_edited": 0,
            "teacher_edits": None,
            "teacher_notes": None,
        })

    themes_record = {}
    if themes_data:
        themes_record = {
            "theme_set": themes_data.get("theme_set", ""),
            "outlier_report": themes_data.get("outlier_report", ""),
            "synthesis_report": themes_data.get("synthesis_report", ""),
        }

    obs_synthesis = themes_data.get("observation_synthesis", "")

    # Build feedback rows in baked format
    baked_feedback = []
    for row in feedback_rows:
        baked_feedback.append({
            "run_id": run_id,
            "student_id": row.get("student_id", ""),
            "student_name": row.get("student_name", ""),
            "draft_text": row.get("draft_text", ""),
            "approved_text": row.get("approved_text"),
            "status": row.get("status", "pending"),
            "confidence": row.get("confidence", 0),
            "posted_at": row.get("posted_at"),
        })

    demo_json = {
        "run": run_record,
        "codings": codings_list,
        "themes": themes_record,
        "feedback": baked_feedback,
        "observation_synthesis": obs_synthesis,
    }

    # ── Save ──
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    out_name = cfg["output_file"]
    if output_suffix:
        out_name = out_name.replace(".json", f"{output_suffix}.json")
    out_path = ASSETS_DIR / out_name
    out_path.write_text(json.dumps(demo_json, indent=2, default=str))
    print(f"\n  Saved baked JSON: {out_path}")
    print(f"  File size: {out_path.stat().st_size / 1024:.0f} KB")

    # ── Timing summary ──
    timing["total"] = round(sum(
        v for v in timing.values() if isinstance(v, (int, float))), 2)
    timing["students"] = total
    timing["per_student_total"] = round(
        timing["total"] / max(total, 1), 2)

    print(f"\n{'─'*40}")
    print(f"  TOTAL: {timing['total']}s "
          f"({timing['per_student_total']}s/student)")
    for stage, t in timing.items():
        if stage not in ("total", "students", "per_student_total",
                         "coding_per_student_avg"):
            print(f"    {stage}: {t}s")
    print(f"{'─'*40}")

    return timing


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--course", default="both",
                        choices=["ethnic_studies", "biology", "both"])
    parser.add_argument("--small-batch", type=int, default=0,
                        help="Limit to N students (for quick testing)")
    parser.add_argument("--backend", default="mlx-gemma",
                        choices=["ollama", "mlx-llama", "mlx-gemma", "ollama-gemma", "sonnet", "opus", "qwen3-cloud",
                                 "deepseek-cloud", "openai-compat"],
                        help="LLM backend: ollama (gemma3:12b via Ollama), "
                             "mlx-llama (Meta-Llama-3.1-8B via MLX — faster, fairer vs Qwen MLX), "
                             "mlx-gemma (Gemma-3-12B via MLX), "
                             "ollama-gemma (Gemma-3-12B via Ollama), "
                             "sonnet, opus, "
                             "qwen3-cloud (480B via Ollama), deepseek-cloud (671B via Ollama), "
                             "openai-compat (any OpenAI-compatible API via env vars: "
                             "CLOUD_API_URL, CLOUD_API_KEY, CLOUD_MODEL)")
    parser.add_argument("--tier", default=None,
                        choices=["lightweight", "medium", "deep_thinking"],
                        help="Override prompt tier (default: auto-detect from backend)")
    parser.add_argument("--output-suffix", default="",
                        help="Suffix for output files (e.g., '_sonnet')")
    args = parser.parse_args()

    # Build backend config
    from insights.llm_backend import BackendConfig
    backend_override = None
    tier_override = args.tier
    output_suffix = args.output_suffix

    if args.backend == "ollama":
        backend_override = BackendConfig(
            name="ollama",
            model="llama3.1:8b",
            base_url="http://localhost:11434",
        )
        output_suffix = output_suffix or "_llama8b"
    elif args.backend == "mlx-llama":
        backend_override = BackendConfig(
            name="mlx",
            model="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        )
        output_suffix = output_suffix or "_llama8b_mlx"
    elif args.backend == "mlx-gemma":
        backend_override = BackendConfig(
            name="mlx",
            model="mlx-community/gemma-3-12b-it-4bit",
        )
        output_suffix = output_suffix or "_gemma12b_mlx"
    elif args.backend == "ollama-gemma":
        backend_override = BackendConfig(
            name="ollama",
            model="gemma3:12b",
            base_url="http://localhost:11434",
        )
        output_suffix = output_suffix or "_gemma12b"
    elif args.backend == "sonnet":
        backend_override = BackendConfig(
            name="cloud",
            model="claude-sonnet-4-20250514",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            api_format="anthropic",
        )
        output_suffix = output_suffix or "_sonnet"
        tier_override = tier_override or "medium"
    elif args.backend == "opus":
        backend_override = BackendConfig(
            name="cloud",
            model="claude-opus-4-20250514",
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            api_format="anthropic",
        )
        output_suffix = output_suffix or "_opus"
        tier_override = tier_override or "deep_thinking"
    elif args.backend == "qwen3-cloud":
        backend_override = BackendConfig(
            name="ollama",
            model="qwen3-coder:480b-cloud",
            base_url="http://localhost:11434",
        )
        output_suffix = output_suffix or "_qwen3"
        tier_override = tier_override or "medium"
    elif args.backend == "deepseek-cloud":
        backend_override = BackendConfig(
            name="ollama",
            model="deepseek-v3.1:671b-cloud",
            base_url="http://localhost:11434",
        )
        output_suffix = output_suffix or "_deepseek"
        tier_override = tier_override or "medium"
    elif args.backend == "openai-compat":
        cloud_url = os.environ.get("CLOUD_API_URL", "")
        cloud_key = os.environ.get("CLOUD_API_KEY", "")
        cloud_model = os.environ.get("CLOUD_MODEL", "")
        if not all([cloud_url, cloud_key, cloud_model]):
            print("ERROR: --backend openai-compat requires env vars: "
                  "CLOUD_API_URL, CLOUD_API_KEY, CLOUD_MODEL")
            sys.exit(1)
        backend_override = BackendConfig(
            name="cloud",
            model=cloud_model,
            base_url=cloud_url,
            api_key=cloud_key,
            api_format="openai",
        )
        model_slug = cloud_model.split("/")[-1].split(":")[0].lower()
        output_suffix = output_suffix or f"_{model_slug}"
        tier_override = tier_override or "medium"

    all_timing = {}

    courses = (["ethnic_studies", "biology"] if args.course == "both"
               else [args.course])

    for course_key in courses:
        try:
            timing = run_pipeline(
                course_key,
                small_batch=args.small_batch,
                backend_override=backend_override,
                output_suffix=output_suffix,
                tier_override=tier_override,
            )
            all_timing[course_key] = timing
        except Exception as e:
            log.exception(f"Pipeline failed for {course_key}: {e}")
            all_timing[course_key] = {"error": str(e)}

    # Save timing report
    timing_path = TIMING_PATH
    if output_suffix:
        timing_path = TIMING_PATH.with_name(
            TIMING_PATH.stem + output_suffix + TIMING_PATH.suffix
        )
    timing_path.parent.mkdir(parents=True, exist_ok=True)
    timing_path.write_text(json.dumps(all_timing, indent=2))
    print(f"\n{'═'*60}")
    print(f"  Timing saved to {timing_path}")
    print(f"{'═'*60}")

    # Summary
    for course, t in all_timing.items():
        if "error" in t:
            print(f"  {course}: FAILED — {t['error']}")
        else:
            print(f"  {course}: {t['total']}s total, "
                  f"{t['per_student_total']}s/student, "
                  f"{t['students']} students")


if __name__ == "__main__":
    main()
