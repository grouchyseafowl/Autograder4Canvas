#!/bin/bash
# Autograder System Status Script
# Shows quick overview of automation health

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║          AUTOGRADER AUTOMATION STATUS                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Check services
echo "📋 Services:"
MAIN_SERVICE=$(launchctl list | grep com.autograder.automation | awk '{print $1}')
WATCHDOG_SERVICE=$(launchctl list | grep com.autograder.watchdog | awk '{print $1}')

if [ -n "$MAIN_SERVICE" ]; then
    echo "  ✅ Main automation: Loaded (PID: $MAIN_SERVICE)"
else
    echo "  ❌ Main automation: Not loaded"
fi

if [ -n "$WATCHDOG_SERVICE" ]; then
    echo "  ✅ Watchdog: Loaded (PID: $WATCHDOG_SERVICE)"
else
    echo "  ⚠️  Watchdog: Not loaded"
fi

echo ""

# Check for running processes
echo "🔄 Running Processes:"
RUNNING=$(ps aux | grep "run_automation.py" | grep -v grep | wc -l)
if [ "$RUNNING" -eq 0 ]; then
    echo "  ℹ️  No automation processes currently running"
else
    echo "  ⚠️  $RUNNING automation process(es) running:"
    ps aux | grep "run_automation.py" | grep -v grep | awk '{print "     PID " $2 " - Running for: " $10}'
fi

echo ""

# Check last successful run
echo "📅 Last Successful Run:"
LOG_FILE="/Users/june/Documents/Autograder Rationales/automation.log"
if [ -f "$LOG_FILE" ]; then
    LAST_COMPLETED=$(grep "AUTOMATION RUN COMPLETED" "$LOG_FILE" | tail -1 | awk '{print $1, $2}')
    if [ -n "$LAST_COMPLETED" ]; then
        LAST_RUN_EPOCH=$(date -j -f "%Y-%m-%d %H:%M:%S" "$LAST_COMPLETED" +%s 2>/dev/null)
        CURRENT_EPOCH=$(date +%s)
        HOURS_SINCE=$((($CURRENT_EPOCH - $LAST_RUN_EPOCH) / 3600))

        echo "  📝 $LAST_COMPLETED ($HOURS_SINCE hours ago)"

        if [ $HOURS_SINCE -gt 30 ]; then
            echo "  ⚠️  WARNING: Last run was over 30 hours ago!"
        else
            echo "  ✅ Status: Normal"
        fi

        # Show summary from last run
        STATS=$(grep -A 5 "📊 SUMMARY" "$LOG_FILE" | tail -6)
        if [ -n "$STATS" ]; then
            echo ""
            echo "  Last Run Statistics:"
            echo "$STATS" | grep "Courses processed" | sed 's/^/  /'
            echo "$STATS" | grep "Assignments graded" | sed 's/^/  /'
            echo "$STATS" | grep "Submissions graded" | sed 's/^/  /'
        fi
    else
        echo "  ⚠️  No completed runs found in log"
    fi
else
    echo "  ❌ Log file not found"
fi

echo ""

# Check for recent errors
echo "⚠️  Recent Errors:"
ERRORS=$(grep -i "error\|failed\|timeout" "$LOG_FILE" 2>/dev/null | tail -5)
if [ -z "$ERRORS" ]; then
    echo "  ✅ No recent errors"
else
    echo "  Last 5 error messages:"
    echo "$ERRORS" | sed 's/^/  /'
fi

echo ""

# Next scheduled run
echo "⏰ Next Scheduled Run:"
echo "  📅 Daily at 2:00 AM (system time: $(date '+%Y-%m-%d %H:%M:%S'))"
NEXT_RUN=$(date -v+1d -v2H -v0M -v0S '+%Y-%m-%d %H:%M:%S' 2>/dev/null)
if [ $? -eq 0 ]; then
    echo "  ⏭️  Next run: $NEXT_RUN"
fi

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "For detailed logs: tail -f '$LOG_FILE'"
echo "For troubleshooting: see MONITORING.md"
echo "════════════════════════════════════════════════════════════════"
