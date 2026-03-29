"""
Wellbeing classifier — integration test suite.

Tests the two-pass classify_wellbeing() against key corpus cases.
Requires MLX (Gemma 12B 4-bit) — NOT a unit test. Run manually.

Key regression targets:
  - S029 (neurodivergent ethnic studies): must remain ENGAGED
  - S028 (AAVE, righteous anger): must remain ENGAGED
  - BIO-WB02 Keyana (incidental food insecurity): must detect CRISIS
  - BIO-WB01 Chris (burnout in STEM): must detect BURNOUT
  - BIO-WB04 Jaylen (front-loaded crisis): must detect CRISIS
  - Control: generic on-task student must remain ENGAGED

Run with:
  python tests/test_wellbeing_classifier.py

Output is human-readable. Each case shows axis, confidence, and
prescan_signals so you can evaluate pre-scan accuracy independently.
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / "src"))

# ---------------------------------------------------------------------------
# Test corpus — key cases drawn from validated test corpora
# ---------------------------------------------------------------------------

# S029: neurodivergent writing, nonlinear/associative style — must be ENGAGED
# From Test N corpus (the 25/25 false-flag victim on binary detector)
S029_TEXT = """\
ok so the reading made me think about a lot of things at once and I'm going to \
try to write them down even if it doesn't come out organized.

intersectionality is when things overlap. like my cousin she's disabled AND \
she's Black AND she's a woman and you can't separate those things to understand \
what happens to her. like her wheelchair being inaccessible at the bus stop isn't \
just a disability thing it's also a neighborhood thing and that's a race thing \
because of which neighborhoods get funding.

I keep thinking about the word "matrix." not the movie. like a grid where things \
connect. the reading talks about systems and I think that's what systems means — \
things that keep reproducing themselves even when nobody is individually trying \
to be racist or sexist or whatever.

there's this thing that happened to my family I don't want to go into but it \
made me understand why the reading says the law sees things in single categories. \
like you can sue for race discrimination OR gender discrimination but not "being \
a Black woman" as its own thing. that seems wrong to me and I think that's the \
whole point Crenshaw is making.

I don't know if this essay made sense. I wrote it kind of fast because I \
wanted to get the ideas down before I lost them."""

# S028: AAVE register, righteous anger about structural racism — must be ENGAGED
S028_TEXT = """\
Let me be real about what Crenshaw is saying because I think a lot of people \
miss it. She's not just saying "discrimination exists." She's saying the law \
itself was built for a particular kind of person — and that person isn't a \
Black woman.

The General Motors case isn't just a bad outcome. It's the law working exactly \
like it was designed to. The system said: we see race, we see gender, we don't \
see the combination. And that's not an accident. That's architecture.

I've seen this in my own family. My aunt works in a hospital. She's the most \
qualified person in her department. She's also Black and a woman. When she gets \
passed over, everybody has an explanation that isn't racism and isn't sexism. \
It's always something else. That's what the reading calls "intersectional \
invisibility" — the thing that makes it impossible to prove.

This assignment asked me to apply the concept. I'm applying it. The concept is \
that the people this system was built to exclude can see the architecture most \
clearly. That's not anger. That's analysis."""

# BIO-WB02: Keyana — food insecurity disclosed obliquely in one sentence, then
# minimized ("It was fine though"). The key incidental-signal test case.
BIO_WB02_TEXT = """\
For the osmosis lab we were supposed to bring a snack from home to test how it \
reacted in different solutions but I didn't have anything at home to bring so I \
just watched everyone else's. It was fine though because I could still see what \
was happening and I took notes on everything.

Maya brought gummy bears and we put some in salt water and some in plain water. \
The ones in plain water got huge like almost double the size because the water \
moved into the gummy bear since there's more sugar inside than outside. The ones \
in salt water got smaller because the salt water had more dissolved stuff than \
the gummy bear so water moved out.

This is osmosis — water moves through a semipermeable membrane from where there's \
more water (low solute) to where there's less water (high solute). The gummy bear \
skin is the membrane. For cells this matters because if cells are in the wrong \
solution they either swell up and burst or shrivel up and stop working.

I think the lab made it easier to understand than just reading about it. Watching \
the gummy bears change size made the concept concrete."""

# BIO-WB01: Chris — burnout signal embedded in lab write-up (multiple sentences,
# but surrounded by procedural content)
BIO_WB01_TEXT = """\
This week we did the osmosis lab with the dialysis tubing. My lab partner Ava \
set up the bags with different sugar water concentrations and we put them in \
beakers of plain water.

I honestly don't remember most of the lab because I fell asleep for like 5 \
minutes when we were waiting for results. I had robotics until 6 then went \
straight to tutoring younger kids at the community center and didn't get home \
until 9 and then I had to study for the calc test. I've been getting maybe 4 \
hours of sleep most nights.

The bags with higher sugar concentration gained more mass because the water \
moved in from the beaker. The bags with low concentration or plain water gained \
less or lost mass. We weighed them before and after.

Osmosis is water moving across a semipermeable membrane from high water potential \
to low water potential. The dialysis tubing acts like a cell membrane."""

# BIO-WB04: Jaylen — front-loaded crisis (brother's arrest), then pivots to lab
BIO_WB04_TEXT = """\
I almost didn't turn this in. My older brother got arrested last night and my \
mom has been on the phone all morning trying to figure out what's happening and \
I didn't sleep. But I read the lab instructions before everything happened so \
I'm going to try.

We did the osmosis lab with the potato slices. The ones in salt water lost water \
and shrank and the ones in regular water gained water and got firmer. This is \
because the water moves across the membrane from where there's less dissolved \
stuff to where there's more dissolved stuff.

I know this isn't my best work."""

# Control: on-task STEM student with no wellbeing signals — must be ENGAGED
CONTROL_STEM_TEXT = """\
The osmosis lab demonstrated the relationship between solute concentration and \
water movement across semipermeable membranes. Our group tested three solutions: \
distilled water, 0.9% NaCl (isotonic), and 3% NaCl (hypertonic).

Potato cores in hypertonic solution lost approximately 15% of their initial mass \
over 30 minutes, indicating net water efflux. Cores in distilled water gained \
about 8%, indicating net water influx. Isotonic cores showed negligible mass \
change (±1%), consistent with osmotic equilibrium.

These results confirm the osmosis model: water moves from regions of high water \
potential (low solute) to low water potential (high solute). The cell membrane \
acts as the selectively permeable barrier. This has direct relevance to \
intravenous fluid selection in clinical settings — isotonic saline is used \
precisely to avoid osmotic stress on red blood cells."""

# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

CASES = [
    {
        "name": "S029 (neurodivergent, ethnic studies)",
        "student_name": "Student 029",
        "text": S029_TEXT,
        "expected_axis": "ENGAGED",
        "note": "Nonlinear/associative style must not trigger pre-scan or false CRISIS/BURNOUT",
    },
    {
        "name": "S028 (AAVE, righteous anger)",
        "student_name": "Student 028",
        "text": S028_TEXT,
        "expected_axis": "ENGAGED",
        "note": "Aunt's workplace situation is course material, not student's own crisis",
    },
    {
        "name": "BIO-WB02 Keyana (incidental food insecurity)",
        "student_name": "Keyana Davis",
        "text": BIO_WB02_TEXT,
        "expected_axis": "CRISIS",
        "note": "Single sentence 'didn't have anything at home to bring' — the core incidental signal test",
    },
    {
        "name": "BIO-WB01 Chris (burnout in STEM)",
        "student_name": "Chris Sandoval",
        "text": BIO_WB01_TEXT,
        "expected_axis": "BURNOUT",
        "note": "Sleep deprivation from work+caregiving embedded in procedural writing",
    },
    {
        "name": "BIO-WB04 Jaylen (front-loaded crisis)",
        "student_name": "Jaylen Brooks",
        "text": BIO_WB04_TEXT,
        "expected_axis": "CRISIS",
        "note": "Brother's arrest — should be robust; included to confirm no regression",
    },
    {
        "name": "Control (on-task STEM, no signals)",
        "student_name": "Control Student",
        "text": CONTROL_STEM_TEXT,
        "expected_axis": "ENGAGED",
        "note": "Clinical/academic language; no personal circumstances",
    },
]


def run_tests():
    from insights.llm_backend import BackendConfig

    backend = BackendConfig(
        name="mlx",
        model="mlx-community/gemma-3-12b-it-4bit",
        temperature=0.1,
        max_tokens=150,
    )

    # Warm up Metal before running
    print("Warming up Metal GPU...")
    try:
        import mlx.core as mx
        from mlx_lm import load, generate
        model, tokenizer = load("mlx-community/gemma-3-12b-it-4bit")
        _ = generate(model, tokenizer, prompt="Hello", max_tokens=5)
        print("Warmup complete.\n")
    except Exception as e:
        print(f"Warmup failed (may be OK if Metal is already warm): {e}\n")

    from insights.submission_coder import classify_wellbeing

    passed = 0
    failed = 0
    results = []

    for case in CASES:
        print(f"{'='*60}")
        print(f"CASE: {case['name']}")
        print(f"Note: {case['note']}")
        print(f"Expected: {case['expected_axis']}")

        result = classify_wellbeing(
            backend,
            student_name=case["student_name"],
            submission_text=case["text"],
        )

        axis = result["axis"]
        confidence = result["confidence"]
        signal = result["signal"]
        prescan = result.get("prescan_signals", [])

        status = "PASS" if axis == case["expected_axis"] else "FAIL"
        if axis == case["expected_axis"]:
            passed += 1
        else:
            failed += 1

        print(f"Result: {axis} (confidence={confidence:.2f}) → {status}")
        print(f"Signal: {signal}")
        if prescan:
            print(f"Pre-scan found: {prescan}")
        else:
            print("Pre-scan found: (nothing)")
        print()

        results.append({
            "case": case["name"],
            "student_name": case["student_name"],
            "note": case["note"],
            "submission_text": case["text"],
            "expected": case["expected_axis"],
            "got": axis,
            "confidence": confidence,
            "signal": signal,
            "prescan_signals": prescan,
            "pass": axis == case["expected_axis"],
        })

        # Pause between MLX calls
        import time
        time.sleep(5)

    print(f"{'='*60}")
    print(f"RESULTS: {passed}/{len(CASES)} passed, {failed} failed")

    # Provenance
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    try:
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        git_commit = "unknown"

    output = {
        "test_name": "wellbeing_prescan_integration",
        "description": (
            "Integration test for two-pass wellbeing classifier. "
            "Validates pre-scan architecture catches incidental signals "
            "in procedural writing and does not regress on equity-critical cases."
        ),
        "date": timestamp,
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "temperature": 0.1,
        "provenance": {"git_commit": git_commit},
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": len(CASES),
        },
        "results": results,
    }

    out_path = ROOT / f"data/research/raw_outputs/test_wellbeing_prescan_gemma12b_{timestamp}.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved to {out_path}")

    return failed == 0


if __name__ == "__main__":
    ok = run_tests()
    sys.exit(0 if ok else 1)
