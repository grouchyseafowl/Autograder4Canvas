#!/usr/bin/env bash
# Resilient test queue — runs tests sequentially, each in its own process.
# If one deadlocks (timeout), kills it and moves to the next.
# Results accumulate across runs (each saves its own dated JSON).
#
# Usage:
#   caffeinate -i ./scripts/run_test_queue.sh
#
# Queue:
#   1. Test F (n=5) x4 batches = 20 total runs for rate stability
#   2. Test I: Tier 2 wellbeing classification (observation→alert)

set -uo pipefail
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="data/research/raw_outputs/test_queue_${TIMESTAMP}.log"
mkdir -p data/research/raw_outputs

echo "═══════════════════════════════════════════════" | tee "$LOG"
echo "  Test Queue — $TIMESTAMP" | tee -a "$LOG"
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

# --- Test F batches (n=5 each, 4 batches = 20 total) ---
for batch in 1 2 3 4; do
    run_test "F batch $batch/4 (n=5)" 2400 \
        scripts/run_alt_hypothesis_tests.py --tests F --runs 5 --no-subprocess
    # Brief pause for Metal recovery between batches
    sleep 10
done

# --- Test I: Tier 2 wellbeing classification on observations ---
# This tests whether classifying OBSERVATIONS (not raw submissions)
# correctly identifies wellbeing signals without false-flagging engaged students.
run_test "I: Tier 2 wellbeing classification" 1800 \
    scripts/run_tier2_wellbeing_test.py

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Queue complete. Log: $LOG" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
