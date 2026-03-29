#!/usr/bin/env bash
# Run Phase 2 → 3 → 4 sequentially with Metal warmup between each.
# Phase 2 is assumed already running — this script runs Phase 3 and 4.
#
# Usage:
#   caffeinate -i ./scripts/run_phase_tests.sh

set -uo pipefail
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG="data/research/raw_outputs/phase_tests_${TIMESTAMP}.log"

warmup() {
    echo "  [warmup] Metal warmup..." | tee -a "$LOG"
    python3 -c "
from mlx_lm import load, generate
m,t = load('mlx-community/gemma-3-12b-it-4bit')
print('Metal OK:', generate(m, t, prompt='Hi', max_tokens=3, verbose=False))
" >> "$LOG" 2>&1
    sleep 5
}

echo "═══════════════════════════════════════════════" | tee "$LOG"
echo "  Phase Tests — $TIMESTAMP" | tee -a "$LOG"
echo "  Phase 3: Translated/multilingual" | tee -a "$LOG"
echo "  Phase 4: Cross-model (Qwen 7B)" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"

# --- Phase 3: Translated/multilingual ---
warmup
echo "" | tee -a "$LOG"
echo "  [Phase 3] Starting translated/multilingual pipeline..." | tee -a "$LOG"
python3 scripts/generate_demo_insights.py --course phase3_translated >> "$LOG" 2>&1
rc=$?
[ $rc -eq 0 ] && echo "  [Phase 3] DONE" | tee -a "$LOG" || echo "  [Phase 3] FAILED ($rc)" | tee -a "$LOG"
sleep 10

# --- Phase 4: Cross-model (Qwen 7B on the ethnic studies corpus via test harness) ---
warmup
echo "" | tee -a "$LOG"
echo "  [Phase 4] Starting cross-model Test N on Qwen 7B..." | tee -a "$LOG"
python3 scripts/run_alt_hypothesis_tests.py --tests N --model qwen7b --no-subprocess >> "$LOG" 2>&1
rc=$?
[ $rc -eq 0 ] && echo "  [Phase 4 N-qwen] DONE" | tee -a "$LOG" || echo "  [Phase 4 N-qwen] FAILED ($rc)" | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
echo "  Phase tests complete. Log: $LOG" | tee -a "$LOG"
echo "═══════════════════════════════════════════════" | tee -a "$LOG"
