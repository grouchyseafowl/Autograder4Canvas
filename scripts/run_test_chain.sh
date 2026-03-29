#!/usr/bin/env bash
# Chain runner: polls until a PID exits, then checks log for errors and runs next command.
# Uses polling (kill -0) so it works for any PID, not just child processes of this shell.
# Usage: run_test_chain.sh <pid> <log_file> <next_command...>
set -euo pipefail

PID=$1; shift
LOG=$1; shift
NEXT_CMD=("$@")

echo "[chain] Polling PID $PID (checking every 30s)..."
while kill -0 "$PID" 2>/dev/null; do
    sleep 30
done

# PID is gone — check whether the log ends with an error signature
echo "[chain] PID $PID no longer running. Checking log for errors..."
TAIL=$(tail -5 "$LOG")
if echo "$TAIL" | grep -qiE "traceback|error:|exception:|aborting|crash"; then
    echo "[chain] Detected error in $LOG:"
    tail -40 "$LOG"
    echo "[chain] Aborting chain — fix the crash before re-running."
    exit 1
fi

echo "[chain] Log looks clean. Running next: ${NEXT_CMD[*]}"
"${NEXT_CMD[@]}"
