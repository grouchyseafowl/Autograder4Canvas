#!/usr/bin/env python3
"""
Test I: Tier 2 Wellbeing Classification on Observations

Tests whether classifying OBSERVATIONS (the model's equity-framed reading of
student work) correctly identifies wellbeing signals, without reproducing the
same failures as classifying raw submissions.

Reads Test G results (observation outputs), runs a classification prompt on
each, and compares to Test G expected outcomes and Test H binary results.

The core question: does classification of observations work where
classification of submissions failed? Or is classification-of-observations
just the concern detector with extra steps?
"""

import json
import logging
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

OUTPUT_DIR = ROOT / "data" / "research" / "raw_outputs"
TEST_G_PATH = OUTPUT_DIR / "test_g_wellbeing_gemma12b_2026-03-27.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("tier2_wellbeing_test")

TIER2_SYSTEM = (
    "You are helping a teacher identify students who may need support beyond "
    "the academic. You are reading a teaching colleague's observation about a "
    "student's work — NOT the student's work directly.\n\n"
    "Your task: based on this observation, does the student appear to need "
    "teacher support for their personal wellbeing (not just academic feedback)?\n\n"
    "Two axes:\n"
    "- BURNOUT: The student is depleted — exhaustion, overwork, caregiving "
    "burden, sleep deprivation. They're functioning but running on empty.\n"
    "- CRISIS: The student's situation involves active danger or instability — "
    "domestic violence, housing loss, food insecurity, immigration enforcement "
    "threat, recent loss/grief.\n\n"
    "CRITICAL: Engaged students writing passionately about course material "
    "(racism, immigration, poverty, violence) are DOING THE ASSIGNMENT, not "
    "in crisis. The observation will describe their intellectual work. Only "
    "flag if the observation describes personal circumstances suggesting the "
    "student themselves is struggling — present-tense, personal, beyond the "
    "assignment scope.\n\n"
    "Respond with JSON only: {\"axis\": \"BURNOUT\"|\"CRISIS\"|\"NONE\", "
    "\"signal\": \"brief description or empty\", "
    "\"confidence\": 0.0-1.0}"
)

TIER2_PROMPT = """\
OBSERVATION about {student_name}:
---
{observation}
---

Based on this observation, does this student appear to need wellbeing support?
Respond with JSON only."""


def main():
    from insights.llm_backend import BackendConfig, send_text, set_mlx_throttle
    from insights.llm_backend import parse_json_response

    # Load Test G results
    if not TEST_G_PATH.exists():
        print(f"ERROR: Test G results not found at {TEST_G_PATH}")
        print("Run Test G first: python scripts/run_alt_hypothesis_tests.py --tests G")
        sys.exit(1)

    test_g = json.loads(TEST_G_PATH.read_text())
    results_g = test_g["results"]

    backend = BackendConfig(
        name="mlx",
        model="mlx-community/gemma-3-12b-it-4bit",
        max_tokens=150,
        temperature=0.1,
    )
    set_mlx_throttle(20)

    print(f"\n{'='*60}")
    print(f"  TEST I: Tier 2 Wellbeing Classification on Observations")
    print(f"{'='*60}")
    print(f"  Reading {len(results_g)} observations from Test G")
    print(f"  Model: {backend.model}")

    results = []
    for case in results_g:
        observation = case["raw_output"]
        student_name = case["student_name"]
        signal_type = case["signal_type"]
        expected = case["expected_surface"]

        prompt = TIER2_PROMPT.format(
            student_name=student_name,
            observation=observation,
        )

        t0 = time.time()
        output = send_text(backend, prompt, TIER2_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse response
        parsed = parse_json_response(output)
        axis = parsed.get("axis", "PARSE_ERROR")
        signal = parsed.get("signal", "")
        confidence = parsed.get("confidence", 0.0)

        # Evaluate
        detected = axis in ("BURNOUT", "CRISIS")
        if expected:
            correct = "OK" if detected else "MISSED"
        else:
            correct = "OK" if not detected else "FALSE-FLAG"

        results.append({
            "student_name": student_name,
            "signal_type": signal_type,
            "expected_surface": expected,
            "tier2_axis": axis,
            "tier2_signal": signal,
            "tier2_confidence": confidence,
            "tier2_detected": detected,
            "tier2_correct": correct,
            "raw_tier2_output": output,
            "observation_input": observation[:200] + "...",
            "time_seconds": elapsed,
        })

        expect_str = "SURFACE" if expected else "no-flag"
        axis_str = f"{axis}" if detected else "NONE"
        print(f"  {case['student_id']:5s} {student_name:22s} "
              f"expect={expect_str:8s} got={axis_str:8s} "
              f"conf={confidence:.1f} [{correct}] ({elapsed}s)")

    # Summary
    print(f"\n  === Tier 2 Classification Summary ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    sig_hit = sum(1 for r in signals if r["tier2_detected"])
    ctrl_fp = sum(1 for r in controls if r["tier2_detected"])

    print(f"  Tier 2 (classify observations):  {sig_hit}/{len(signals)} signals, "
          f"{ctrl_fp}/{len(controls)} false positives")
    print(f"  Test G (observation keywords):   8/8 signals, 2/2 false positives")
    print(f"  Test H Binary B (classify subs): 7/8 signals, 0/2 false positives")
    print(f"  Test H Binary C (classify subs): 3/8 signals, 0/2 false positives")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    from datetime import datetime
    date = datetime.now().strftime("%Y-%m-%d")
    output_path = OUTPUT_DIR / f"test_i_tier2_wellbeing_{date}.json"
    output_data = {
        "test_name": "test_i_tier2_wellbeing",
        "model": backend.model,
        "date": date,
        "note": "Tier 2: classify OBSERVATIONS for wellbeing signals (not raw submissions)",
        "question": "Does classification of equity-framed observations work where classification of raw submissions failed?",
        "results": results,
    }
    output_path.write_text(json.dumps(output_data, indent=2, default=str))
    print(f"\n  Results: {output_path}")


if __name__ == "__main__":
    main()
