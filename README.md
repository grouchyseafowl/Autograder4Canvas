# Autograder4Canvas

A Canvas LMS integration tool for community college instructors to streamline grading workflows with ethics-first design principles.

## Features

- **Academic Dishonesty Detection** - Linguistic pattern analysis to support learning conversations (not surveillance)
- **Complete/Incomplete Grading** - Automated evaluation of submission completeness
- **Discussion Forum Grading** - Batch grading of Canvas discussion posts
- **Automation Engine** - Schedule and automate grading workflows

## Download

**No Python or technical setup required.** Just download and run.

**[Download the latest release](https://github.com/grouchyseafowl/Autograder4Canvas/releases/latest)**

| Platform | File |
|----------|------|
| macOS    | `Autograder4Canvas-Mac.dmg` |
| Windows  | `Autograder4Canvas-Windows.zip` |
| Linux    | `Autograder4Canvas-Linux.tar.gz` |

### Installation

**macOS:**
1. Download `Autograder4Canvas-Mac.dmg`
2. Open the DMG and drag the app to your Applications folder
3. Right-click the app and select "Open" (first time only, to bypass Gatekeeper)

**Windows:**
1. Download `Autograder4Canvas-Windows.zip` and extract it
2. Run `Autograder4Canvas.exe`
3. If Windows SmartScreen appears, click "More info" → "Run anyway" (the app is not code-signed)

**Linux:**
1. Download `Autograder4Canvas-Linux.tar.gz`
2. Extract: `tar -xzf Autograder4Canvas-Linux.tar.gz`
3. Run the `Autograder4Canvas` executable inside

## Quick Start

1. **Get your Canvas API token:**
   - Log into Canvas → Account → Settings → New Access Token

2. **Launch Autograder4Canvas**

3. **Enter your Canvas API token** when prompted

4. **Select your grading tool:**
   - Academic Dishonesty Check
   - Complete/Incomplete Grading
   - Discussion Forum Grading
   - Automation Setup

5. **Follow the on-screen prompts** to select your course and assignment

## Documentation

- [User Guide](src/docs/USER_GUIDE.md) - Detailed usage instructions
- [Automation Guide](AUTOMATION_README.md) - Set up automated grading workflows
- [Academic Dishonesty Check README](Academic_Dishonety_check_README.txt) - Ethical considerations and usage

## Core Values

This tool is designed with **ethics-first principles**:

- ✅ **Student dignity & agency** - Students are knowledge creators, not potential cheaters
- ✅ **Educational equity** - Accounts for ELLs, first-gen students, neurodivergent learners
- ✅ **Data sovereignty** - Processes locally only, never stores student work
- ✅ **Transparency** - Human judgment over algorithmic "accuracy"
- ✅ **Bias awareness** - Makes detection biases visible

**The Academic Dishonesty Check is a conversation starter, not a verdict.**

## Requirements

- Canvas LMS account with API access
- Internet connection for Canvas API calls
- Python 3.7+ (bundled in pre-built apps)

## Building from Source

See [Development Guide](docs/INTEGRATION_GUIDE.md) for build instructions.

## Support

For questions or issues, please [open an issue](https://github.com/grouchyseafowl/Autograder4Canvas/issues) on GitHub.

## License

GNU GPL v3 - See LICENSE file for details

## Credits

Built by a community college instructor for educators teaching humanities and social sciences.
