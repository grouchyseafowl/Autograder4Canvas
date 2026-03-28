#!/usr/bin/env bash
# Replication queue — runs after main queue to confirm key findings.
#
# Usage:
#   caffeinate -i ./scripts/run_replication_queue.sh
#
# Queue:
#   1. Test M × 3 replications (production concern detector consistency)
#   2. Test N × 3 replications (4-axis classification consistency)
#   3. Test O — Multi-axis classification (ENGAGED + CRISIS simultaneously)
#      Also tests CHECK-IN axis for subtle signals like S002

set -uo pipefail
cd "$(dirname "$0")/.."

TIMEOUT_SCALE=${TIMEOUT_SCALE:-1.0}
_scale() { echo "$1 * $TIMEOUT_SCALE" | bc | cut -d. -f1; }
TEST_T=$(_scale "${TEST_TIMEOUT:-3600}")

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="data/research/raw_outputs/replication_queue_${TIMESTAMP}.log"
mkdir -p data/research/raw_outputs

echo "═══════════════════════════════════════════════" | tee "$LOG"
echo "  Replication Queue — $TIMESTAMP" | tee -a "$LOG"
echo "  Test timeout: ${TEST_T}s (scale=${TIMEOUT_SCALE})" | tee -a "$LOG"
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
    python3 "$@" >> "$LOG" 2>&1 &
    local pid=$!
    local elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        sleep 5
        elapsed=$((elapsed + 5))
        if [ $elapsed -ge "$timeout_s" ]; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null
            echo "  [$name] TIMEOUT (${timeout_s}s)" | tee -a "$LOG"
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

# --- Test N replications (4-axis on submissions — best classification result) ---
# Refine first, then replicate. N achieved 8/8 + 0 FP at n=1.
# Need n=4 total (1 existing + 3 new) to confirm stability.
for rep in 1 2 3; do
    run_test "N replication $rep/3" "$TEST_T" \
        scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess
    sleep 10
done

# --- Test O replications (multi-axis with CHECK-IN reasoning) ---
# Tests whether multi-axis catches S002 and dual-tags wellbeing cases.
# CHECK-IN prompt now asks model to surface competing interpretations.
for rep in 1 2 3; do
    run_test "O replication $rep/3" "$TEST_T" \
        scripts/run_alt_hypothesis_tests.py --tests O --no-subprocess
    sleep 10
done

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Replication queue complete. Log: $LOG" | tee -a "$LOG"
echo "" | tee -a "$LOG"
echo "  KEY QUESTIONS:" | tee -a "$LOG"
echo "  N replications: Does 8/8 + 0/2 FP hold across 3 runs?" | tee -a "$LOG"
echo "    If it degrades, the 4-axis result was a fluke." | tee -a "$LOG"
echo "    S029 should stay ENGAGED. S002 will likely stay ENGAGED." | tee -a "$LOG"
echo "  O replications: Does S002 get CHECK-IN tag?" | tee -a "$LOG"
echo "    Does the multi-axis format catch what single-axis misses?" | tee -a "$LOG"
echo "    Are wellbeing cases dual-tagged (ENGAGED + CRISIS)?" | tee -a "$LOG"
echo "    CHECK-IN reasoning: does the model surface competing" | tee -a "$LOG"
echo "    interpretations (not just a label)?" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
