# Autograder Monitoring & Troubleshooting Guide

## Health Monitoring

### Quick Health Check
```bash
./scripts/health_check.sh
```

This checks if the automation has run successfully in the last 30 hours.

### View Recent Activity
```bash
# Last 50 lines of automation log
tail -50 "/Users/june/Documents/Autograder Rationales/automation.log"

# Check for errors
grep -i "error\|failed\|timeout" "/Users/june/Documents/Autograder Rationales/automation.log" | tail -20

# See last successful run
grep "AUTOMATION RUN COMPLETED" "/Users/june/Documents/Autograder Rationales/automation.log" | tail -1
```

### Check for Hung Processes
```bash
ps aux | grep run_automation.py | grep -v grep
```

If a process has been running for more than 2 hours, it's likely hung.

## Scheduled Tasks

### Main Automation
- **Schedule**: Daily at 2:00 AM
- **Service**: `com.autograder.automation`
- **Logs**:
  - Main: `/Users/june/Documents/Autograder Rationales/automation.log`
  - stdout: `/Users/june/autograder_logs/launchd_stdout.log`
  - stderr: `/Users/june/autograder_logs/launchd_stderr.log`

### Watchdog (Hung Process Killer)
- **Schedule**: Every hour at :30
- **Service**: `com.autograder.watchdog`
- **Logs**: `/Users/june/autograder_logs/watchdog.log`
- **Action**: Kills processes running > 2 hours

## Manual Operations

### Run Manually (Dry Run)
```bash
cd /Users/june/Documents/GitHub/Autograder4Canvas
export CANVAS_BASE_URL="https://cabrillo.instructure.com"
export CANVAS_API_TOKEN="<your-token>"
python3 src/run_automation.py --dry-run
```

### Run for Single Course
```bash
python3 src/run_automation.py --dry-run --course 44853
```

### Restart Services
```bash
# Restart main automation
launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist

# Restart watchdog
launchctl unload ~/Library/LaunchAgents/com.autograder.watchdog.plist
launchctl load ~/Library/LaunchAgents/com.autograder.watchdog.plist
```

### Check Service Status
```bash
launchctl list | grep autograder
```

## Troubleshooting

### Problem: No runs in 24+ hours

**Check:**
1. Is the service loaded?
   ```bash
   launchctl list | grep com.autograder.automation
   ```

2. Any hung processes?
   ```bash
   ps aux | grep run_automation.py | grep -v grep
   ```

3. Check error logs:
   ```bash
   tail -50 /Users/june/autograder_logs/launchd_stderr.log
   ```

**Fix:**
```bash
# Kill hung processes
pkill -f run_automation.py

# Restart service
launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist
```

### Problem: Process hangs during execution

**Signs:**
- Process running > 2 hours
- No new log entries
- Stuck in middle of grading

**Automatic Fix:**
The watchdog will automatically kill it within 1 hour.

**Manual Fix:**
```bash
# Find and kill the process
ps aux | grep run_automation.py | grep -v grep
kill <PID>

# If it doesn't die, force kill
kill -9 <PID>
```

### Problem: Canvas API timeouts

**Signs in logs:**
- "Timeout fetching assignment groups"
- "Connection error"
- Long gaps between log entries

**Response:**
- Timeouts now have automatic retry with exponential backoff (3 attempts)
- Each API call has 30-second timeout
- Process will continue with other courses if one fails

### Problem: n8n notifications failing

**Signs in logs:**
```
Failed to send notification email: HTTPConnectionPool(host='localhost', port=5678)
```

**Fix:**
1. **Start n8n** (if you want notifications):
   ```bash
   # Start n8n service if you have it configured
   ```

2. **Or disable notifications** (edit config):
   ```bash
   # Edit .autograder_config/course_configs.json
   # Set "n8n_webhook_url" to null or empty string
   ```

This is **not critical** - automation will continue without notifications.

## Performance Metrics

### Normal Execution Time
- **Small course** (20-30 students, 5 assignments): 1-2 minutes
- **Medium course** (40-50 students, 10 assignments): 3-5 minutes
- **All courses combined**: 5-15 minutes

### Warning Signs
- Single course taking > 10 minutes
- Total execution > 30 minutes
- These indicate Canvas API slowness

## Log Maintenance

### Log Rotation
Logs automatically rotate when they exceed 10MB. You can manually trigger:
```bash
./scripts/rotate_logs.sh
```

### View Rotated Logs
```bash
# List archived logs
ls -lh "/Users/june/Documents/Autograder Rationales"/*.log.*.gz

# View archived log
zcat "/Users/june/Documents/Autograder Rationales/automation.log.20260213_150000.gz" | less
```

## Safety Features

1. **Request Timeouts**: All Canvas API requests have 30s timeout
2. **Job Polling Timeout**: Grade submission jobs timeout after 5 minutes
3. **Retry Logic**: Failed requests retry 3 times with exponential backoff
4. **Process Watchdog**: Kills processes running > 2 hours
5. **Error Isolation**: Course failures don't stop other courses from processing
6. **Dry-run Testing**: Test without submitting grades

## Emergency Procedures

### Stop All Automation
```bash
# Unload services
launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
launchctl unload ~/Library/LaunchAgents/com.autograder.watchdog.plist

# Kill any running processes
pkill -f run_automation.py
```

### Re-enable After Emergency Stop
```bash
launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist
launchctl load ~/Library/LaunchAgents/com.autograder.watchdog.plist
```

## Contact & Escalation

If automation is down for > 48 hours or you see critical errors:
1. Check this guide first
2. Review error logs
3. Try manual dry-run to identify issue
4. Contact system administrator if Canvas API is down

## Change History

- **2026-02-13**: Added timeout fixes, retry logic, and watchdog service
- **2026-01-27**: Initial automation deployment
