#!/usr/bin/env bash
# Full pipeline + alt hypothesis test queue.
# Runs the observation-enabled pipeline, then tests A-D+E automatically.
#
# Usage:
#   ./scripts/run_full_queue.sh [--skip-pipeline] [--tests A,B,C,D,E]
#
# Logs go to data/research/raw_outputs/queue_*.log

set -euo pipefail
cd "$(dirname "$0")/.."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="data/research/raw_outputs"
mkdir -p "$LOG_DIR"

SKIP_PIPELINE=false
TESTS="A,B,C,D,E"

for arg in "$@"; do
    case $arg in
        --skip-pipeline) SKIP_PIPELINE=true ;;
        --tests=*) TESTS="${arg#*=}" ;;
    esac
done

echo "═══════════════════════════════════════════════════════"
echo "  Full Queue: Pipeline + Alt Hypothesis Tests"
echo "  Timestamp: $TIMESTAMP"
echo "  Skip pipeline: $SKIP_PIPELINE"
echo "  Tests: $TESTS"
echo "═══════════════════════════════════════════════════════"

# Ensure plugged in (MLX deadlocks on battery)
BATTERY=$(pmset -g batt 2>/dev/null | grep -o "'.*'" | tr -d "'" || echo "unknown")
if [[ "$BATTERY" == *"Battery"* ]]; then
    echo ""
    echo "  WARNING: Running on battery power."
    echo "  MLX inference can deadlock on battery. Plug in for reliability."
    echo ""
    read -p "  Continue anyway? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1
fi

# Step 1: Pipeline (with observations)
if [ "$SKIP_PIPELINE" = false ]; then
    PIPELINE_LOG="$LOG_DIR/pipeline_${TIMESTAMP}.log"
    echo ""
    echo "Step 1: Running pipeline with observations..."
    echo "  Log: $PIPELINE_LOG"
    echo ""
    python3 scripts/generate_demo_insights.py \
        --course ethnic_studies 2>&1 | tee "$PIPELINE_LOG"
    echo ""
    echo "Pipeline complete. Log: $PIPELINE_LOG"
else
    echo ""
    echo "Step 1: Pipeline SKIPPED (--skip-pipeline)"
fi

# Step 2: Alt hypothesis tests
TEST_LOG="$LOG_DIR/alt_hypothesis_${TIMESTAMP}.log"
echo ""
echo "Step 2: Running alt hypothesis tests ($TESTS)..."
echo "  Log: $TEST_LOG"
echo ""
python3 scripts/run_alt_hypothesis_tests.py \
    --tests "$TESTS" --model gemma12b 2>&1 | tee "$TEST_LOG"

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  Queue complete."
echo "  Pipeline log: $LOG_DIR/pipeline_${TIMESTAMP}.log"
echo "  Test log:     $TEST_LOG"
echo "  Raw outputs:  $LOG_DIR/"
echo "═══════════════════════════════════════════════════════"
