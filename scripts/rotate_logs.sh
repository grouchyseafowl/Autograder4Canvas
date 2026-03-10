#!/bin/bash
# Autograder Log Rotation Script
# Rotates logs when they exceed 10MB and keeps last 5 archives

LOG_DIR="/Users/june/autograder_logs"
AUTOMATION_LOG="/Users/june/Documents/Autograder Rationales/automation.log"
MAX_SIZE_MB=10
MAX_ARCHIVES=5

# Function to rotate a log file
rotate_log() {
    local log_file="$1"
    local base_name=$(basename "$log_file")
    local log_dir=$(dirname "$log_file")

    # Check if file exists and size
    if [ ! -f "$log_file" ]; then
        return
    fi

    # Get file size in MB
    local size_mb=$(du -m "$log_file" | awk '{print $1}')

    if [ "$size_mb" -ge "$MAX_SIZE_MB" ]; then
        echo "$(date): Rotating $log_file (size: ${size_mb}MB)"

        # Create archive name with timestamp
        local timestamp=$(date +%Y%m%d_%H%M%S)
        local archive="${log_dir}/${base_name}.${timestamp}"

        # Move current log to archive
        mv "$log_file" "$archive"

        # Compress archive
        gzip "$archive"

        # Create new empty log
        touch "$log_file"

        # Remove old archives, keeping only MAX_ARCHIVES
        ls -t "${log_dir}/${base_name}".*.gz 2>/dev/null | tail -n +$((MAX_ARCHIVES + 1)) | xargs rm -f

        echo "$(date): Log rotated to ${archive}.gz"
    fi
}

# Rotate main logs
rotate_log "$AUTOMATION_LOG"
rotate_log "$LOG_DIR/launchd_stdout.log"
rotate_log "$LOG_DIR/launchd_stderr.log"
rotate_log "$LOG_DIR/watchdog.log"

echo "$(date): Log rotation check complete"
