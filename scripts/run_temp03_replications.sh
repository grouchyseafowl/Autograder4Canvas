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
echo "  Temperature 0.3 Replications — $TIMESTAMP" | tee -a "$LOG"
echo "  5 runs each of N and O at temp 0.3" | tee -a "$LOG"
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

# Set temperature for all tests in this queue
export TEST_TEMPERATURE=0.3

# N at temp 0.3 — 5 runs to see variation
for rep in 1 2 3 4 5; do
    run_test "N temp0.3 rep $rep/5" \
        scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess
    sleep 10
done

# O at temp 0.3 — 5 runs
for rep in 1 2 3 4 5; do
    run_test "O temp0.3 rep $rep/5" \
        scripts/run_alt_hypothesis_tests.py --tests O --no-subprocess
    sleep 10
done

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Temp 0.3 replications complete. Log: $LOG" | tee -a "$LOG"
echo "  KEY: Do results vary across runs? If S029/S002 flip" | tee -a "$LOG"
echo "  on some runs, the finding is sampling-dependent." | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
