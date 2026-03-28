#!/usr/bin/env bash
# Temperature 0.3 replication studies for N and O.
# Tests whether results hold under sampling variation (not just deterministic decoding).
#
# Usage:
#   caffeinate -i ./scripts/run_temp03_replications.sh

set -uo pipefail
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="data/research/raw_outputs/temp03_replications_${TIMESTAMP}.log"
mkdir -p data/research/raw_outputs

echo "═══════════════════════════════════════════════" | tee "$LOG"
echo "  Test P + Temperature 0.3 Replications — $TIMESTAMP" | tee -a "$LOG"
echo "  1. Test P (two-pass architecture) at temp 0.1" | tee -a "$LOG"
echo "  2. N × 5 at temp 0.3" | tee -a "$LOG"
echo "  3. P × 3 at temp 0.3" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"

# Metal warmup
python3 -c "
from mlx_lm import load, generate
m,t = load('mlx-community/gemma-3-12b-it-4bit')
print('Metal OK:', generate(m, t, prompt='Hi', max_tokens=3, verbose=False))
" >> "$LOG" 2>&1

run_test() {
    local name="$1"; shift
    echo "" | tee -a "$LOG"
    echo "  [$name] Starting..." | tee -a "$LOG"
    python3 "$@" >> "$LOG" 2>&1 &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge 3600 ]; then
            kill "$pid" 2>/dev/null; wait "$pid" 2>/dev/null
            echo "  [$name] TIMEOUT" | tee -a "$LOG"
            return 124
        fi
    done
    wait "$pid"
    local rc=$?
    [ $rc -eq 0 ] && echo "  [$name] DONE" | tee -a "$LOG" || echo "  [$name] FAILED ($rc)" | tee -a "$LOG"
    return $rc
}

# --- Step 1: Test P at temp 0.1 (the proposed pipeline architecture) ---
# This tests N-then-CHECK-IN before we vary temperature.
# Results determine whether to implement the two-pass approach.
export TEST_TEMPERATURE=0.1
run_test "P: Two-pass (temp 0.1)" \
    scripts/run_alt_hypothesis_tests.py --tests P --no-subprocess
sleep 10

# --- Step 2: N at temp 0.3 — 5 runs to see variation ---
export TEST_TEMPERATURE=0.3
for rep in 1 2 3 4 5; do
    run_test "N temp0.3 rep $rep/5" \
        scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess
    sleep 10
done

# --- Step 3: P at temp 0.3 — 3 runs ---
for rep in 1 2 3; do
    run_test "P temp0.3 rep $rep/3" \
        scripts/run_alt_hypothesis_tests.py --tests P --no-subprocess
    sleep 10
done

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Queue complete. Log: $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "  KEY QUESTIONS:" | tee -a "$LOG"
echo "  P (temp 0.1): Does S002 get CHECK-IN? How many corpus" | tee -a "$LOG"
echo "    students get CHECK-IN? (O had 7/7 — P should be fewer" | tee -a "$LOG"
echo "    since CHECK-IN only runs on ENGAGED students)" | tee -a "$LOG"
echo "  N (temp 0.3): Do S029/S002/wellbeing results vary?" | tee -a "$LOG"
echo "  P (temp 0.3): Is the two-pass stable under sampling?" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
