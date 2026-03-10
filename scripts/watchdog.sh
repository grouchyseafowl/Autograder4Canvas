#!/bin/bash
# Autograder Watchdog Script
# Kills autograder processes that have been running for more than 2 hours
# Run this periodically via cron to prevent hung processes

MAX_RUNTIME_SECONDS=7200  # 2 hours

# Find autograder processes
PROCESSES=$(ps aux | grep "run_automation.py" | grep -v grep | grep -v watchdog)

if [ -z "$PROCESSES" ]; then
    echo "$(date): No autograder processes running"
    exit 0
fi

echo "$PROCESSES" | while read -r line; do
    PID=$(echo "$line" | awk '{print $2}')
    # Get elapsed time in seconds (works on macOS)
    ELAPSED=$(ps -p "$PID" -o etime= | awk -F: '{if (NF==3) {print $1*3600 + $2*60 + $3} else if (NF==2) {print $1*60 + $2} else {print $1}}')

    if [ "$ELAPSED" -gt "$MAX_RUNTIME_SECONDS" ]; then
        echo "$(date): Killing hung autograder process $PID (runtime: ${ELAPSED}s)"
        kill "$PID"
        sleep 5
        # Force kill if still running
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$(date): Force killing process $PID"
            kill -9 "$PID"
        fi
    else
        echo "$(date): Autograder process $PID is running normally (runtime: ${ELAPSED}s)"
    fi
done
