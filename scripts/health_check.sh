#!/bin/bash
# Autograder Health Check Script
# Checks if automation has run successfully recently

LOG_FILE="/Users/june/Documents/Autograder Rationales/automation.log"
MAX_HOURS_SINCE_RUN=30  # Alert if no successful run in 30 hours

# Check if log file exists
if [ ! -f "$LOG_FILE" ]; then
    echo "ERROR: Log file not found at $LOG_FILE"
    exit 1
fi

# Find the last "AUTOMATION RUN COMPLETED" timestamp
LAST_COMPLETED=$(grep "AUTOMATION RUN COMPLETED" "$LOG_FILE" | tail -1 | awk '{print $1, $2}')

if [ -z "$LAST_COMPLETED" ]; then
    echo "WARNING: No completed runs found in log file"
    exit 1
fi

# Convert to epoch time (works on macOS)
LAST_RUN_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_COMPLETED" +%s 2>/dev/null)
if [ $? -ne 0 ]; then
    echo "ERROR: Could not parse last run timestamp: $LAST_COMPLETED"
    exit 1
fi

CURRENT_EPOCH=$(date +%s)
HOURS_SINCE=$((($CURRENT_EPOCH - $LAST_RUN_EPOCH) / 3600))

echo "Last successful run: $LAST_COMPLETED ($HOURS_SINCE hours ago)"

if [ $HOURS_SINCE -gt $MAX_HOURS_SINCE_RUN ]; then
    echo "WARNING: Last successful run was $HOURS_SINCE hours ago (threshold: $MAX_HOURS_SINCE_RUN hours)"

    # Check for hung processes
    HUNG_PROCESSES=$(ps aux | grep "run_automation.py" | grep -v grep | wc -l)
    if [ $HUNG_PROCESSES -gt 0 ]; then
        echo "ERROR: Found $HUNG_PROCESSES hung autograder process(es)"
        ps aux | grep "run_automation.py" | grep -v grep
    fi

    exit 1
else
    echo "OK: Automation is running normally"
    exit 0
fi
