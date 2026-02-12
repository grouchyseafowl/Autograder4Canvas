#!/usr/bin/env python3
"""
Canvas Autograder - Automation Runner
Non-interactive execution for scheduled grading.
"""

import argparse
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from automation.automation_engine import AutomationEngine
from automation.config_wizard import ConfigWizard


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Canvas Autograder - Automated Grading System",
        epilog="For first-time setup, run: python run_automation.py --setup",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        '--setup',
        action='store_true',
        help='Run interactive configuration wizard'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Preview what would be graded without making changes'
    )

    parser.add_argument(
        '--config',
        type=str,
        default='.autograder_config/course_configs.json',
        help='Path to configuration file (default: .autograder_config/course_configs.json)'
    )

    parser.add_argument(
        '--update-config',
        action='store_true',
        help='Check for new courses/assignments and update configuration'
    )

    parser.add_argument(
        '--edit-config',
        action='store_true',
        help='Edit existing configuration (change word counts, add/delete groups, etc.)'
    )

    parser.add_argument(
        '--course',
        type=int,
        help='Grade only specific course ID (for testing)'
    )

    args = parser.parse_args()

    try:
        if args.setup:
            # Run interactive setup wizard
            print()
            wizard = ConfigWizard()
            wizard.run()

        elif args.update_config:
            # Update existing config with new courses/assignments
            print()
            wizard = ConfigWizard(update_mode=True)
            wizard.check_for_updates()

        elif args.edit_config:
            # Edit existing configuration
            print()
            wizard = ConfigWizard()
            wizard.edit_configuration()

        else:
            # Run automation
            print()

            # Validate config exists
            config_path = Path(args.config)
            if not config_path.exists():
                print(f"❌ Configuration file not found: {config_path}")
                print()
                print("Run setup first:")
                print("  python src/run_automation.py --setup")
                print()
                sys.exit(1)

            # Create and run engine
            engine = AutomationEngine(
                config_path=str(config_path),
                dry_run=args.dry_run,
                course_filter=args.course
            )
            engine.run()

    except KeyboardInterrupt:
        print()
        print()
        print("⏹️  Interrupted by user. Exiting...")
        sys.exit(0)

    except Exception as e:
        print()
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
