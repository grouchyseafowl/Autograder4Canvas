#!/usr/bin/env bash
# Resilient test queue — runs tests sequentially, each in its own process.
# If one deadlocks (timeout), kills it and moves to the next.
# Results accumulate across runs (each saves its own dated JSON).
#
# Usage:
#   caffeinate -i ./scripts/run_test_queue.sh
#   caffeinate -i ./scripts/run_test_queue.sh --timeout-scale 2.0  # double all timeouts
#   PIPELINE_TIMEOUT=21600 caffeinate -i ./scripts/run_test_queue.sh
#
# Timeout configuration:
#   --timeout-scale <factor>   Multiply all timeouts by this factor (default 1.0)
#   PIPELINE_TIMEOUT env var   Override pipeline timeout (default 18000s / 5h)
#   TEST_TIMEOUT env var       Override per-test timeout (default 3600s / 1h)
#   F_BATCH_TIMEOUT env var    Override F batch timeout (default 2400s / 40m)
#
# Queue:
#   1. Full pipeline re-run (with all prompt fixes applied)
#   2. Test J: Pipeline validation (structural naming, anti-spotlighting,
#      what_reaching_for, confusion field, preamble stripping)
#   3. Test K: Enhancement model comparison (free OpenRouter models)
#   4. Test F (n=5) x4 batches = 20 total runs for rate stability
#   5. Test I: Tier 2 wellbeing classification (observation→alert)

set -uo pipefail
cd "$(dirname "$0")/.."

# Parse timeout scale factor
TIMEOUT_SCALE=1.0
for arg in "$@"; do
    case $arg in
        --timeout-scale=*) TIMEOUT_SCALE="${arg#*=}" ;;
        --timeout-scale) shift; TIMEOUT_SCALE="${1:-1.0}" ;;
    esac
done

# Configurable timeouts (env vars override defaults, scale factor applies)
_scale() { echo "$1 * $TIMEOUT_SCALE" | bc | cut -d. -f1; }
PIPELINE_T=$(_scale "${PIPELINE_TIMEOUT:-18000}")
TEST_T=$(_scale "${TEST_TIMEOUT:-3600}")
F_BATCH_T=$(_scale "${F_BATCH_TIMEOUT:-2400}")

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="data/research/raw_outputs/test_queue_${TIMESTAMP}.log"
mkdir -p data/research/raw_outputs

echo "═══════════════════════════════════════════════" | tee "$LOG"
echo "  Test Queue — $TIMESTAMP" | tee -a "$LOG"
echo "  Timeouts: pipeline=${PIPELINE_T}s test=${TEST_T}s F_batch=${F_BATCH_T}s (scale=${TIMEOUT_SCALE})" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"

# Metal warmup
echo "  Metal warmup..." | tee -a "$LOG"
python3 -c "
from mlx_lm import load, generate
m,t = load('mlx-community/gemma-3-12b-it-4bit')
print('Metal OK:', generate(m, t, prompt='Hi', max_tokens=3, verbose=False))
" >> "$LOG" 2>&1

if [ $? -ne 0 ]; then
    echo "  Metal warmup FAILED — aborting" | tee -a "$LOG"
    exit 1
fi

run_test() {
    local name="$1"
    local timeout_s="$2"
    shift 2
    echo "" | tee -a "$LOG"
    echo "  [$name] Starting (timeout ${timeout_s}s)..." | tee -a "$LOG"
    # macOS doesn't have `timeout`; use a background process + wait
    python3 "$@" >> "$LOG" 2>&1 &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge "$timeout_s" ]; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            echo "  [$name] TIMEOUT (${timeout_s}s) — likely Metal deadlock" | tee -a "$LOG"
            return 124
        fi
    done
    wait "$pid"
    local rc=$?
    if [ $rc -eq 0 ]; then
        echo "  [$name] DONE" | tee -a "$LOG"
    else
        echo "  [$name] FAILED (exit $rc)" | tee -a "$LOG"
    fi
    return $rc
}

# --- Step 1: Test J — Pipeline validation ---
# Tests whether the prompt changes actually work at 12B:
# structural naming quality, anti-spotlighting, what_reaching_for,
# preamble stripping. See test docstring for interpretation guide.
run_test "J: Pipeline validation" "$TEST_T" \
    scripts/run_alt_hypothesis_tests.py --tests J --no-subprocess

sleep 10

# --- Step 2: Test K — Enhancement model comparison (cloud, no MLX) ---
# Tests anonymized enhancement prompt against free OpenRouter models.
# NO MLX required — all calls go to cloud. Safe to run after Metal tests.
# Scores models on: structural naming, language justice, relational
# analysis, pedagogical depth, anti-spotlighting.
run_test "K: Enhancement model comparison" "$TEST_T" \
    scripts/run_alt_hypothesis_tests.py --tests K --no-subprocess

# --- Step 3: Test M — Production concern detector (MSOT validation) ---
# Runs the ACTUAL production concern_detector.detect_concerns() on test
# students + wellbeing cases. Answers: does the production system (with
# anti-bias post-processing, confidence thresholding, signal matrix)
# reproduce the same S029/S002 failures as the simplified test prompt?
# This is the most methodologically important test in the queue.
run_test "M: Production concern detector" "$TEST_T" \
    scripts/run_alt_hypothesis_tests.py --tests M --no-subprocess

sleep 10

# --- Step 4: Test L — Expanded wellbeing classifier (4-axis) ---
# Tests CRISIS/BURNOUT/ENGAGED/NONE schema. Should fix Test I's
# false positive on Priya (analytical engagement misread as burnout).
# Runs on MLX — needs observations from Test G.
run_test "L: Expanded wellbeing classifier" "$TEST_T" \
    scripts/run_alt_hypothesis_tests.py --tests L --no-subprocess

sleep 10

# --- Step 5: Test N — 4-axis classification on raw submissions ---
# Tests the CRISIS/BURNOUT/ENGAGED/NONE schema directly on student
# writing (not observations). This answers: does a richer classification
# schema fix the S029 false-flag and S002 miss when applied directly to
# submissions? Comparison to Test M (production binary) and Test L
# (4-axis on observations).
run_test "N: 4-axis classification on submissions" "$TEST_T" \
    scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess

sleep 10

# --- Step 6: Test I — Original Tier 2 for comparison baseline ---
run_test "I: Tier 2 wellbeing (3-axis baseline)" "$TEST_T" \
    scripts/run_tier2_wellbeing_test.py

sleep 15

# --- Step 7: Pipeline re-run (last — longest, checkpointed) ---
# Runs after all tests so Metal has clean state for the 5h pipeline.
# Resumes from class_reading checkpoint (skips Stages 1 + 1.5).
run_test "Pipeline re-run (all fixes)" "$PIPELINE_T" \
    scripts/generate_demo_insights.py --course ethnic_studies

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Queue complete. Log: $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "  RESULTS INTERPRETATION GUIDE:" | tee -a "$LOG"
echo "  Test M: THE CRITICAL TEST. Does the production concern detector" | tee -a "$LOG"
echo "    reproduce S029 false-flag and S002 miss? If production system" | tee -a "$LOG"
echo "    handles S029 correctly, the n=25 finding is specific to the" | tee -a "$LOG"
echo "    simplified binary prompt, not a general classification failure." | tee -a "$LOG"
echo "  Test J: structural_naming_score, violation_count," | tee -a "$LOG"
echo "    reaching_for count. J2 uses ~10 students, no P7 ranking." | tee -a "$LOG"
echo "  Test K: Rank models by total score AND per-dimension." | tee -a "$LOG"
echo "    Language justice dimension hardest — flag 0-scorers." | tee -a "$LOG"
echo "  Test L vs I: Compare false positive rates. L should have" | tee -a "$LOG"
echo "    0/2 FP (vs I's 1/2). If ENGAGED absorbed BURNOUT cases," | tee -a "$LOG"
echo "    the prompt needs refinement." | tee -a "$LOG"
echo "  Pipeline: Check what_student_is_reaching_for populated (was 0/32)." | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
