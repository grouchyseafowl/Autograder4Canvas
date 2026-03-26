#!/usr/bin/env python3
"""
Alternative hypothesis tests for the observation architecture paper.

Reconstructed from docs/research/experiment_log.md methodology.
Saves all raw outputs to data/research/raw_outputs/ (persistent, not /tmp).

Tests:
  A: Temperature/consistency (5 runs × 2 students on observation prompt)
  B: Best possible concern prompt (7 key students)
  C: Length effect (7 key students, 100-150 word assessments)
  D: Structural power moves detection (2 corpus + 5 synthetic)
  E: Cross-model replication (Test A on Qwen 7B)

Usage:
    python scripts/run_alt_hypothesis_tests.py [--tests A,B,C,D,E] [--model gemma12b]
    python scripts/run_alt_hypothesis_tests.py --tests A,E  # just temperature + cross-model
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
CLASS_READING_PATH = ROOT / "data" / "demo_baked" / "checkpoints" / "ethnic_studies_gemma12b_mlx_class_reading.json"
OUTPUT_DIR = ROOT / "data" / "research" / "raw_outputs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alt_hypothesis_tests")


# ---------------------------------------------------------------------------
# Model configs
# ---------------------------------------------------------------------------

def _openrouter_key():
    """Load OpenRouter API key from Reframe .env."""
    env_path = Path.home() / "Documents" / "GitHub" / "Reframe" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REFRAME_SHARED_OPENROUTER_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REFRAME_SHARED_OPENROUTER_KEY", "")


MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "qwen7b": {
        "name": "mlx",
        "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "gemma27b_cloud": {
        "name": "cloud",
        "model": "google/gemma-3-27b-it",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
    "mistral_large_cloud": {
        "name": "cloud",
        "model": "mistralai/mistral-large-2411",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
}


# ---------------------------------------------------------------------------
# Prompts (from src/insights/prompts.py + experiment log methodology)
# ---------------------------------------------------------------------------

from insights.prompts import OBSERVATION_SYSTEM_PROMPT, OBSERVATION_PROMPT

BEST_CONCERN_SYSTEM = (
    "You are assessing whether a student's submission raises genuine wellbeing "
    "concerns that the teacher should be aware of.\n\n"
    "CRITICAL EQUITY PROTECTIONS — These are NOT concerns:\n"
    "- Righteous anger about injustice = ENGAGEMENT, not distress\n"
    "- Lived experience of racism, poverty, immigration, disability, "
    "or gender violence described AS COURSE MATERIAL = doing the assignment\n"
    "- AAVE, multilingual mixing, nonstandard English = VALID ACADEMIC REGISTER\n"
    "- Neurodivergent writing patterns (fragmented, nonlinear, associative) = "
    "COGNITIVE STYLE, not confusion\n"
    "- Passionate, emotional, or confrontational engagement with difficult "
    "material = INTELLECTUAL ENGAGEMENT\n\n"
    "Genuine wellbeing concerns include: signs of burnout/exhaustion, "
    "expressions of hopelessness about personal situation (not course material), "
    "mentions of self-harm, or requests for help."
)

BEST_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Respond with JSON only: {{"concern": true/false, "explanation": "..."}}"""

LENGTH_CONCERN_SYSTEM = BEST_CONCERN_SYSTEM

LENGTH_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

In 100-150 words, assess this student's submission for genuine wellbeing concerns.
Consider the equity protections carefully. Then conclude with either:
CONCERN: YES
or
CONCERN: NO"""


# Synthetic power move test cases (from experiment log Test D methodology)
POWER_MOVE_CASES = [
    {
        "id": "PM01",
        "name": "Alex Rivera",
        "type": "abstract_liberalism",
        "text": (
            "I think the most important thing is that we should treat everyone equally "
            "regardless of race. The reading talks about structural racism, but I believe "
            "if we just focus on being fair to everyone as individuals, these problems "
            "would go away. My parents taught me that judging people by their character "
            "is what matters. I don't see why we need to keep bringing up race when the "
            "goal should be a colorblind society where everyone has the same opportunities."
        ),
    },
    {
        "id": "PM02",
        "name": "Emily Chen",
        "type": "settler_innocence",
        "text": (
            "This reading about indigenous land rights was really eye-opening. I feel "
            "terrible about what happened to Native Americans, but my family immigrated "
            "from China in the 1990s, so we weren't part of colonization. I think it's "
            "unfair to make people who weren't involved feel guilty. We should acknowledge "
            "history but also move forward. My family worked really hard to build a life "
            "here and I don't think that makes us complicit in something that happened "
            "hundreds of years ago."
        ),
    },
    {
        "id": "PM03",
        "name": "Jake Morrison",
        "type": "progress_narrative",
        "text": (
            "While I understand the frustration in the reading, I think we need to "
            "acknowledge how much progress we've made. We had a Black president, we have "
            "more diverse representation in media than ever, and there are laws against "
            "discrimination. Things aren't perfect but they're so much better than they "
            "were 50 years ago. I worry that focusing too much on what's still wrong "
            "ignores all the positive changes and makes people feel hopeless."
        ),
    },
    {
        "id": "PM04",
        "name": "Sarah Thompson",
        "type": "meritocracy_deflection",
        "text": (
            "The reading makes it sound like the system is designed to keep people down, "
            "but I know plenty of people from disadvantaged backgrounds who succeeded "
            "through hard work. My uncle grew up in poverty and became a doctor. Instead "
            "of blaming the system, maybe we should focus on individual empowerment and "
            "education. If people just tried harder and took advantage of the opportunities "
            "that exist, I think a lot of these disparities would decrease."
        ),
    },
    {
        "id": "PM05",
        "name": "David Park",
        "type": "objectivity_claim",
        "text": (
            "I think this discussion would benefit from a more objective, data-driven "
            "approach. The reading relies a lot on personal stories and emotional arguments. "
            "If we really want to understand racial disparities, we should look at the "
            "statistics and let the data speak for itself instead of cherry-picking "
            "anecdotes. Science is supposed to be neutral and we should apply the same "
            "rigor to social issues instead of letting ideology drive the conclusions."
        ),
    },
]

# Detection keywords for Test D
POWER_MOVE_KEYWORDS = [
    r"tone.?polic", r"colorblind", r"structural", r"recenter", r"foreclose",
    r"silenc", r"dismiss", r"abstract.?liberal", r"meritocra", r"settler",
    r"progress.?narrative", r"objectiv", r"deflect", r"power.?move",
    r"power.?arrangement", r"maintain.*power", r"innocen",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_corpus() -> Dict[str, dict]:
    corpus = json.loads(CORPUS_PATH.read_text())
    return {s["student_id"]: s for s in corpus}


def load_class_reading() -> str:
    data = json.loads(CLASS_READING_PATH.read_text())
    if isinstance(data, dict) and "class_reading" in data:
        return data["class_reading"]
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return str(data)


def get_backend(model_key: str):
    from insights.llm_backend import BackendConfig
    cfg = MODELS[model_key]
    kwargs = {
        "name": cfg["name"],
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]
    if "api_key_fn" in cfg:
        kwargs["api_key"] = cfg["api_key_fn"]()
    elif "api_key" in cfg:
        kwargs["api_key"] = cfg["api_key"]
    return BackendConfig(**kwargs)


def send(backend, prompt: str, system_prompt: str, max_tokens: int = 300) -> str:
    from insights.llm_backend import send_text
    return send_text(backend, prompt, system_prompt, max_tokens=max_tokens)


def classify_framing(text: str) -> str:
    """Classify observation output as ASSET, DEFICIT, MIXED, or NEUTRAL."""
    asset_kw = ["strength", "asset", "engagement", "reaching for", "intellectual",
                 "powerful", "sophisticated", "valuable", "valid", "courage",
                 "epistemolog", "resist", "creative"]
    deficit_kw = ["lacks", "deficien", "struggle", "concern", "limited",
                  "weak", "fail", "problem", "risk", "distress", "inadequa"]
    lower = text.lower()
    a = sum(1 for k in asset_kw if k in lower)
    d = sum(1 for k in deficit_kw if k in lower)
    if a > 0 and d == 0:
        return "ASSET"
    if d > 0 and a == 0:
        return "DEFICIT"
    if a > 0 and d > 0:
        return "MIXED"
    return "NEUTRAL"


def detect_power_move(text: str) -> bool:
    lower = text.lower()
    return any(re.search(kw, lower) for kw in POWER_MOVE_KEYWORDS)


def save_results(test_name: str, model_key: str, results: list, metadata: dict = None):
    """Save raw results to persistent location."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    filename = f"{test_name}_{model_key}_{date}.json"
    output = {
        "test_name": test_name,
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies",
        "class_reading_source": str(CLASS_READING_PATH.relative_to(ROOT)),
        "results": results,
    }
    if metadata:
        output.update(metadata)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    log.info("Results saved: %s", path)
    return path


def unload_model():
    """Release MLX model between tests."""
    try:
        from insights.llm_backend import unload_mlx_model
        unload_mlx_model()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test A: Temperature/Consistency
# ---------------------------------------------------------------------------

def test_a_temperature(model_key: str = "gemma12b", n_runs: int = 5):
    print(f"\n{'='*60}")
    print(f"  TEST A: Temperature/Consistency ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    test_students = ["S022", "S028"]  # Destiny (righteous anger), Imani (AAVE)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []
    for sid in test_students:
        student = corpus[sid]
        print(f"\n  {sid} {student['student_name']}:")
        for run in range(1, n_runs + 1):
            prompt = OBSERVATION_PROMPT.format(
                class_context=class_reading,
                assignment=assignment,
                student_name=student["student_name"],
                submission_text=student["text"],
                teacher_lens="",
            )
            t0 = time.time()
            output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
            elapsed = round(time.time() - t0, 1)
            classification = classify_framing(output)
            results.append({
                "student_id": sid,
                "student_name": student["student_name"],
                "run": run,
                "prompt": prompt,
                "system_prompt": OBSERVATION_SYSTEM_PROMPT,
                "raw_output": output,
                "classification": classification,
                "time_seconds": elapsed,
            })
            print(f"    Run {run}: {classification} ({elapsed}s)")

    path = save_results("test_a_temperature", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test B: Best Possible Concern Prompt
# ---------------------------------------------------------------------------

def test_b_best_concern(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST B: Best Possible Concern Prompt ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    # Override temperature to 0.1 for classification
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = BEST_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, BEST_CONCERN_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse result
        lower = output.lower()
        if '"concern": true' in lower or '"concern":true' in lower:
            result = "FLAG"
        elif '"concern": false' in lower or '"concern":false' in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "prompt": prompt,
            "system_prompt": BEST_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_b_best_concern", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test C: Length Effect
# ---------------------------------------------------------------------------

def test_c_length(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST C: Length Effect ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = LENGTH_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, LENGTH_CONCERN_SYSTEM, max_tokens=500)
        elapsed = round(time.time() - t0, 1)

        lower = output.lower()
        if "concern: yes" in lower:
            result = "FLAG"
        elif "concern: no" in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "prompt": prompt,
            "system_prompt": LENGTH_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_c_length", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test D: Structural Power Moves Detection
# ---------------------------------------------------------------------------

def test_d_power_moves(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST D: Structural Power Moves ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    # Combine corpus students + synthetic cases
    test_cases = []
    for sid in ["S018", "S025"]:
        s = corpus[sid]
        test_cases.append({
            "id": sid,
            "name": s["student_name"],
            "type": "corpus_" + ("colorblind" if sid == "S018" else "tone_policing"),
            "text": s["text"],
        })
    test_cases.extend(POWER_MOVE_CASES)

    results = []
    for case in test_cases:
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=case["name"],
            submission_text=case["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
        elapsed = round(time.time() - t0, 1)

        detected = detect_power_move(output)
        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "power_move_type": case["type"],
            "detected": detected,
            "prompt": prompt,
            "system_prompt": OBSERVATION_SYSTEM_PROMPT,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        status = "DETECTED" if detected else "MISSED"
        print(f"  {case['id']:5s} {case['name']:20s} ({case['type']:25s}) {status} ({elapsed}s)")

    path = save_results("test_d_power_moves", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test E: Cross-model replication (Test A on different model)
# ---------------------------------------------------------------------------

def test_e_cross_model(model_key: str = "qwen7b", n_runs: int = 3):
    print(f"\n{'='*60}")
    print(f"  TEST E: Cross-model Replication ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    # Same as Test A but on a different model
    results = test_a_temperature(model_key=model_key, n_runs=n_runs)

    # Re-save under test_e name
    path = save_results("test_e_cross_model", model_key, results, {
        "note": "Cross-model replication of Test A (temperature/consistency)",
        "reference_model": "gemma-3-12b-it-4bit",
    })
    print(f"\n  Cross-model results: {path}")
    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alternative hypothesis tests")
    parser.add_argument("--tests", default="A,B,C,D",
                        help="Comma-separated list of tests to run (A,B,C,D,E)")
    parser.add_argument("--model", default="gemma12b",
                        help="Model key (gemma12b, qwen7b)")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs for Test A/E (default 5)")
    args = parser.parse_args()

    tests = [t.strip().upper() for t in args.tests.split(",")]
    model = args.model

    print(f"\nTests to run: {tests}")
    print(f"Model: {MODELS.get(model, {}).get('model', model)}")
    print(f"Output: {OUTPUT_DIR}")

    total_t0 = time.time()
    all_results = {}

    if "A" in tests:
        all_results["A"] = test_a_temperature(model, n_runs=args.runs)
        unload_model()

    if "B" in tests:
        all_results["B"] = test_b_best_concern(model)
        unload_model()

    if "C" in tests:
        all_results["C"] = test_c_length(model)
        unload_model()

    if "D" in tests:
        all_results["D"] = test_d_power_moves(model)
        unload_model()

    if "E" in tests:
        # Run cross-model on Qwen 7B (local) first
        if model != "qwen7b":
            all_results["E_qwen7b"] = test_e_cross_model("qwen7b", n_runs=min(args.runs, 3))
            unload_model()

        # Then try Gemma 27B cloud (if key available)
        key = _openrouter_key()
        if key:
            try:
                all_results["E_gemma27b"] = test_e_cross_model("gemma27b_cloud", n_runs=min(args.runs, 3))
            except Exception as e:
                log.warning("Cloud cross-model test failed: %s", e)
                print(f"  Cloud test skipped: {e}")
        else:
            print("  Cloud cross-model test skipped (no OpenRouter key)")

    total_time = round(time.time() - total_t0, 1)

    # Summary
    print(f"\n{'='*60}")
    print(f"  ALL TESTS COMPLETE — {total_time}s total")
    print(f"{'='*60}")
    for test_id, results in all_results.items():
        print(f"  Test {test_id}: {len(results)} results")
    print(f"  Raw outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
