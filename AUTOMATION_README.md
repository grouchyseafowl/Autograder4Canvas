# Canvas Autograder - Automation System

## Overview

This automation system extends the Canvas Autograder to run **completely unattended**, automatically grading assignments across all your courses while you sleep.

## Key Features

✅ **Non-interactive execution** - Runs completely unattended
✅ **Smart course detection** - Uses Canvas term API for current semester only
✅ **Intelligent skipping** - No submissions, already graded, future deadlines
✅ **Multi-type grading** - Assignments, discussions, replies with different rules
✅ **Flexible configuration** - Per-course, per-assignment-type rules
✅ **User-friendly setup** - Interactive wizard pulls Canvas data
✅ **Academic dishonesty integration** - Runs ADC on graded submissions
✅ **Two-tier flag logging** - Summary + Details sheets in Excel
✅ **Auto-wake scheduling** - Built-in pmset configuration for macOS

## Quick Start

### Prerequisites

1. **macOS** (this automation uses macOS-specific scheduling)
2. **Python 3.8+**
3. **Canvas API Token** - Set as environment variable:
   ```bash
   export CANVAS_API_TOKEN='your_token_here'
   ```
   Add to `~/.zshrc` or `~/.bash_profile` to make permanent:
   ```bash
   echo "export CANVAS_API_TOKEN='your_token_here'" >> ~/.zshrc
   ```

### One-Command Setup

```bash
cd /Users/june/Documents/GitHub/Autograder4Canvas
./setup_automation.sh
```

This script will:
1. Configure macOS to wake your computer automatically
2. Create a scheduled task (launchd) to run grading
3. Install Python dependencies
4. Run the interactive configuration wizard
5. Test the setup with a dry-run

### What the Wizard Does

The setup wizard uses a **course-by-course workflow**:

1. **Detect Current Semester** - Fetches active terms from Canvas
2. **Select Your Courses** - Shows courses where you're the instructor
3. **Configure Each Course** - One course at a time:
   - Lists all assignment groups in THIS course
   - You select which groups to auto-grade
   - For EACH selected group, configure:
     - Type (Complete/Incomplete or Discussion)
     - Word count minimums
     - Academic dishonesty check (yes/no)
   - Shows summary of THIS course's configuration
   - Prompts to continue to next course
4. **Final Summary** - Shows all courses and their configured groups
5. **Save Configuration** - Creates `.autograder_config/course_configs.json`

This workflow ensures you configure **all assignment groups for one course** before moving to the next, making it easier to focus on one class at a time.

## Configuration Example

After setup, you'll have a configuration like this:

```json
{
  "version": "1.0",
  "global_settings": {
    "current_semester_term_ids": [789],
    "skip_future_assignments": true,
    "skip_no_submissions": true,
    "log_file_path": "~/Documents/Autograder Rationales/automation.log",
    "flag_excel_path": "./autograder_flags.xlsx"
  },
  "courses": {
    "123456": {
      "course_name": "ETHN-1-02",
      "enabled": true,
      "assignment_rules": [
        {
          "rule_id": "weekly_reflections",
          "assignment_group_name": "Weekly Reflections",
          "assignment_type": "complete_incomplete",
          "min_word_count": 200,
          "run_adc": true,
          "preserve_existing_grades": true
        }
      ]
    }
  }
}
```

## Manual Usage

### Run Grading Manually

```bash
# Dry-run (preview only, no changes)
python3 src/run_automation.py --dry-run

# Actually run grading
python3 src/run_automation.py

# Grade specific course only
python3 src/run_automation.py --course 123456
```

### Update Configuration

```bash
# Check for new courses/assignment groups
python3 src/run_automation.py --update-config

# Re-run full setup wizard
python3 src/run_automation.py --setup
```

## Scheduled Execution

After running `setup_automation.sh`, your system will:

1. **Wake automatically** - 5 minutes before run time (default: 2:55 AM)
2. **Run grading** - At configured time (default: 3:00 AM)
3. **Log results** - To `~/Documents/Autograder Rationales/automation.log`

### Check Schedule Status

```bash
# View launchd schedule
launchctl list | grep autograder

# View pmset wake schedule
pmset -g sched
```

### Modify Schedule

Edit the launchd plist:
```bash
nano ~/Library/LaunchAgents/com.autograder.automation.plist
```

Then reload:
```bash
launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist
```

## How It Works

### Intelligent Skipping

The system automatically skips:

1. **Future assignments** - Assignments with deadlines in the future
2. **No submissions** - Assignments with zero student submissions
3. **Already graded** - Submissions that already have grades

This ensures you're only grading what needs grading.

### Grade Preservation

The system **never** overwrites existing grades. It checks:

- `workflow_state` - Must be "submitted" or "pending_review"
- `score` - Must be `null` (no existing grade)

This protects against accidentally overwriting manual grades.

### Academic Dishonesty Checking

If enabled (`run_adc: true`), the system:

1. Runs academic dishonesty detection on graded submissions
2. Logs flags to `autograder_flags.xlsx` with two sheets:
   - **Summary** - Student totals, sorted by flag count
   - **Details** - Individual flag records with markers and scores

### Logging

All activity is logged to `~/Documents/Autograder Rationales/automation.log`:

```
2026-01-27 03:00:15 - INFO - ====================================
2026-01-27 03:00:15 - INFO - AUTOMATION RUN STARTED
2026-01-27 03:00:15 - INFO - ====================================
2026-01-27 03:00:16 - INFO - 📚 Processing course: ETHN-1-02 (123456)
2026-01-27 03:00:16 - INFO -   📁 Group: Weekly Reflections (8 assignments)
2026-01-27 03:00:17 - INFO -     📝 Grading: Reflection Week 5
2026-01-27 03:00:18 - INFO -       ✅ Graded 23 submission(s)
```

## File Structure

```
Autograder4Canvas/
├── src/
│   ├── automation/                      # Automation system
│   │   ├── __init__.py
│   │   ├── automation_engine.py         # Main orchestration
│   │   ├── canvas_helpers.py            # Canvas API wrappers
│   │   ├── config_wizard.py             # Interactive setup
│   │   ├── course_config.py             # Configuration schema
│   │   ├── flag_aggregator.py           # Excel flag logging
│   │   └── grade_checker.py             # Grade preservation
│   ├── run_automation.py                # CLI entry point
│   └── [existing autograder files]
├── .autograder_config/
│   └── course_configs.json              # Your configuration
├── autograder_flags.xlsx                # Persistent flag log
└── setup_automation.sh                  # One-command setup
```

## Testing & Debugging

### Debug Script

Use the included debug script to test automation:

```bash
./test_automation_schedule.sh
```

This provides 6 testing options:

1. **Create test run in 2 minutes** - Schedules a test to verify scheduling works
2. **Run automation manually NOW** - Test script logic immediately (dry-run)
3. **Check dependencies** - Verify Python, Canvas token, config, etc.
4. **View automation log** - See last 50 lines of execution log
5. **View error log** - See any errors that occurred
6. **Exit**

**Key Features:**
- ✅ Separates scheduling issues from script issues
- ✅ Creates marker files to prove execution
- ✅ Safe (uses dry-run mode)
- ✅ Quick (2-minute test option)
- ✅ Comprehensive diagnostics

**Example Use Case:**

If automation doesn't run overnight:
```bash
# Test if script works
./test_automation_schedule.sh
# Select option 2 (manual run)

# If that works, test if scheduling works
./test_automation_schedule.sh
# Select option 1 (test in 2 minutes)
# Wait 2 minutes, check for marker file
```

See **[TESTING_AND_DEBUGGING.md](TESTING_AND_DEBUGGING.md)** for complete guide.

## Troubleshooting

### Quick Diagnostics

```bash
# Run full diagnostic
./test_automation_schedule.sh

# Option 3: Check all dependencies
# Option 2: Test script manually
# Option 1: Test scheduling (2 min wait)
```

### Automation Not Running

1. Check launchd status:
   ```bash
   launchctl list | grep autograder
   ```

2. Check logs:
   ```bash
   tail -50 ~/Documents/Autograder\ Rationales/automation.log
   tail -50 ~/Documents/Autograder\ Rationales/automation_error.log
   ```

3. Verify pmset schedule:
   ```bash
   pmset -g sched
   ```

### Computer Not Waking

1. Check System Settings > Battery > Options
   - Enable "Wake for network access"

2. Verify pmset schedule:
   ```bash
   sudo pmset repeat wakeorpoweron MTWRFSU 02:55:00
   ```

### Configuration Errors

Run validation:
```bash
python3 -c "
import sys; sys.path.insert(0, 'src')
from pathlib import Path
from automation.course_config import AutomationConfig, ConfigValidator

config = AutomationConfig.load(Path('.autograder_config/course_configs.json'))
errors = ConfigValidator.validate_config(config)

if errors:
    print('Configuration errors:')
    for error in errors:
        print(f'  - {error}')
else:
    print('✅ Configuration valid')
"
```

## Uninstalling

To remove automation:

```bash
# Remove launchd service
launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
rm ~/Library/LaunchAgents/com.autograder.automation.plist

# Remove pmset wake schedule
sudo pmset repeat cancel

# Remove configuration (optional)
rm -rf .autograder_config
rm autograder_flags.xlsx
```

## Advanced Configuration

### Custom Assignment Rules

Edit `.autograder_config/course_configs.json` to:

- Change word count thresholds
- Enable/disable ADC per assignment group
- Toggle grade preservation
- Enable/disable specific courses

### Multiple Terms

The system supports grading across multiple terms simultaneously:

```json
"global_settings": {
  "current_semester_term_ids": [789, 790]
}
```

### Discussion Forum Settings

For discussion forums:

```json
{
  "assignment_type": "discussion_forum",
  "post_min_words": 200,
  "reply_min_words": 50,
  "reply_points": 0.5,
  "run_adc": true
}
```

## Support

For issues or questions:

1. Check logs: `~/Documents/Autograder Rationales/automation.log`
2. Run dry-run to test: `python3 src/run_automation.py --dry-run`
3. Validate configuration (see Troubleshooting section)

## Safety Features

The automation system includes multiple safety mechanisms:

1. **Dry-run mode** - Test without making changes
2. **Grade preservation** - Never overwrites existing grades
3. **Intelligent skipping** - Avoids unnecessary work
4. **Error isolation** - One failed course doesn't crash entire run
5. **Comprehensive logging** - Full audit trail of all actions
6. **Configuration validation** - Checks for conflicts before running

## What Gets Automated

✅ **Automated:**
- Complete/Incomplete grading based on word count
- PDF annotation detection
- Academic dishonesty checking
- Grade submission to Canvas
- Flag aggregation and reporting

❌ **Not Automated (requires manual review):**
- Discussion forum grading (partial - needs enhancement)
- Manual grade adjustments
- Student communication
- Flag review and action
