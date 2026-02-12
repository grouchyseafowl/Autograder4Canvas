"""
Canvas Autograder - Command Reference Generator
Creates a handy reference file with all automation commands.
"""

from pathlib import Path
from datetime import datetime


def generate_command_reference(output_path: Path = None):
    """
    Generate command reference file.

    Args:
        output_path: Path to save reference file (default: COMMAND_REFERENCE.txt in repo root)
    """
    if output_path is None:
        output_path = Path(__file__).parent.parent.parent / "COMMAND_REFERENCE.txt"

    reference = f"""
╔══════════════════════════════════════════════════════════════════════════╗
║                                                                          ║
║              CANVAS AUTOGRADER - COMMAND REFERENCE                       ║
║                                                                          ║
║              Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                               ║
║                                                                          ║
╚══════════════════════════════════════════════════════════════════════════╝


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SETUP & CONFIGURATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

First-Time Setup
────────────────────────────────────────────────────────────────────────────
Run the integrated setup script (configures everything):

    ./setup_automation.sh

This will:
  • Install Python dependencies
  • Configure macOS wake schedule (pmset)
  • Create automated task (launchd)
  • Run configuration wizard
  • Test the setup


Configure Courses & Assignments (Initial Setup)
────────────────────────────────────────────────────────────────────────────
Run the interactive configuration wizard:

    python3 src/run_automation.py --setup

This walks you through configuring each course and assignment group.


Edit Existing Configuration
────────────────────────────────────────────────────────────────────────────
Change word counts, add/delete groups, toggle courses on/off:

    python3 src/run_automation.py --edit-config

Options:
  • Edit specific course details (change word counts, ADC settings)
  • Add new assignment groups to a course
  • Delete assignment groups from a course
  • Enable/disable entire courses
  • Save or discard changes


Check for New Assignments
────────────────────────────────────────────────────────────────────────────
Check if Canvas has new assignment groups you haven't configured:

    python3 src/run_automation.py --update-config

Checks each course for new groups and lets you configure them.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  RUNNING AUTOMATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Run Automation Manually (Safe Test Mode)
────────────────────────────────────────────────────────────────────────────
Test without actually submitting grades:

    python3 src/run_automation.py --dry-run

Use this to verify everything works before running for real.


Run Automation Manually (Real Grading)
────────────────────────────────────────────────────────────────────────────
Actually grade and submit to Canvas:

    python3 src/run_automation.py

⚠️  This WILL submit grades to Canvas!


Run Single Course Only (Testing)
────────────────────────────────────────────────────────────────────────────
Test automation on just one course:

    python3 src/run_automation.py --course COURSE_ID

Replace COURSE_ID with the Canvas course ID number.


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TESTING & DEBUGGING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Debug Automation Schedule
────────────────────────────────────────────────────────────────────────────
Test if automation runs on schedule:

    ./test_automation_schedule.sh

Options:
  [1] Create test run in 2 minutes - Verify scheduling works
  [2] Run automation manually NOW - Test script immediately
  [3] Check dependencies - Verify Python, Canvas token, etc.
  [4] View automation log - See execution history
  [5] View error log - See any errors
  [6] Exit

Use Option 1 to verify scheduling, Option 2 to test script logic.


Monitor Logs in Real-Time
────────────────────────────────────────────────────────────────────────────
Watch automation as it runs:

    tail -f ~/Documents/Autograder\\ Rationales/automation.log


View Recent Log Entries
────────────────────────────────────────────────────────────────────────────
See last 50 lines of automation log:

    tail -50 ~/Documents/Autograder\\ Rationales/automation.log


View Error Log
────────────────────────────────────────────────────────────────────────────
See any errors that occurred:

    tail -50 ~/Documents/Autograder\\ Rationales/automation_error.log


Check Last Run
────────────────────────────────────────────────────────────────────────────
When did automation last run?

    grep "AUTOMATION RUN STARTED" ~/Documents/Autograder\\ Rationales/automation.log | tail -1


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  SCHEDULE MANAGEMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Check Scheduled Tasks
────────────────────────────────────────────────────────────────────────────
Verify launchd service is running:

    launchctl list | grep autograder

Should show: com.autograder.automation


Check Wake Schedule
────────────────────────────────────────────────────────────────────────────
Verify computer will wake automatically:

    pmset -g sched

Should show daily wake time.


Temporarily Disable Automation
────────────────────────────────────────────────────────────────────────────
Stop scheduled runs without removing:

    launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist


Re-Enable Automation
────────────────────────────────────────────────────────────────────────────
Resume scheduled runs:

    launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist


Change Scheduled Time
────────────────────────────────────────────────────────────────────────────
1. Edit the plist file:

    nano ~/Library/LaunchAgents/com.autograder.automation.plist

2. Find <key>Hour</key> and <key>Minute</key> sections
3. Change the <integer> values
4. Save and reload:

    launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist
    launchctl load ~/Library/LaunchAgents/com.autograder.automation.plist


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  CONFIGURATION FILES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View Current Configuration
────────────────────────────────────────────────────────────────────────────
See your configuration in JSON format:

    cat .autograder_config/course_configs.json | python3 -m json.tool


View Scheduled Task Configuration
────────────────────────────────────────────────────────────────────────────
See launchd configuration:

    cat ~/Library/LaunchAgents/com.autograder.automation.plist


Backup Configuration
────────────────────────────────────────────────────────────────────────────
Save a copy before making changes:

    cp .autograder_config/course_configs.json .autograder_config/backup_$(date +%Y%m%d).json


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ACADEMIC DISHONESTY FLAGS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

View Flag Summary
────────────────────────────────────────────────────────────────────────────
Open Excel file with student flag summaries:

    open autograder_flags.xlsx

Two sheets:
  • Summary - Student totals sorted by flag count
  • Details - Individual flag records


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Automation Didn't Run
────────────────────────────────────────────────────────────────────────────
1. Run debug script:
   ./test_automation_schedule.sh

2. Select Option 2 (manual run) - Does it work?
   • Yes → Script OK, check scheduling
   • No → Fix script errors (check logs)

3. Select Option 1 (test in 2 min) - Does marker file appear?
   • Yes → Scheduling works
   • No → Check launchd and pmset


Python Import Errors
────────────────────────────────────────────────────────────────────────────
Reinstall dependencies:

    pip3 install -r src/requirements.txt


Canvas API Errors
────────────────────────────────────────────────────────────────────────────
Check if API token is set:

    echo $CANVAS_API_TOKEN

If empty, set it:

    export CANVAS_API_TOKEN='your_token_here'

Add to ~/.zshrc for persistence:

    echo "export CANVAS_API_TOKEN='your_token_here'" >> ~/.zshrc


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  UNINSTALL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Remove Automation Completely
────────────────────────────────────────────────────────────────────────────
1. Unload launchd service:
   launchctl unload ~/Library/LaunchAgents/com.autograder.automation.plist

2. Remove plist file:
   rm ~/Library/LaunchAgents/com.autograder.automation.plist

3. Remove wake schedule:
   sudo pmset repeat cancel

4. (Optional) Remove configuration:
   rm -rf .autograder_config
   rm autograder_flags.xlsx


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  DOCUMENTATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Read Main Documentation
────────────────────────────────────────────────────────────────────────────
    cat AUTOMATION_README.md


Read Testing Guide
────────────────────────────────────────────────────────────────────────────
    cat TESTING_AND_DEBUGGING.md


Read Change Log
────────────────────────────────────────────────────────────────────────────
    cat CHANGELOG_IMPROVEMENTS.md


View This Reference Again
────────────────────────────────────────────────────────────────────────────
    cat COMMAND_REFERENCE.txt


━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  QUICK REFERENCE SUMMARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Most Common Commands:

    Setup (first time):              ./setup_automation.sh
    Edit configuration:              python3 src/run_automation.py --edit-config
    Test automation:                 ./test_automation_schedule.sh
    Run dry-run:                     python3 src/run_automation.py --dry-run
    Run for real:                    python3 src/run_automation.py
    View logs:                       tail -50 ~/Documents/Autograder\\ Rationales/automation.log
    Check schedule:                  launchctl list | grep autograder

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For help: Read AUTOMATION_README.md or TESTING_AND_DEBUGGING.md
Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""

    # Write to file
    output_path.write_text(reference)

    return output_path


def print_command_reference():
    """Print the command reference to console."""
    reference_file = Path(__file__).parent.parent.parent / "COMMAND_REFERENCE.txt"

    if reference_file.exists():
        print(reference_file.read_text())
    else:
        print("⚠️  Command reference file not found. Run setup first.")


if __name__ == "__main__":
    output_path = generate_command_reference()
    print(f"✅ Command reference generated: {output_path}")
