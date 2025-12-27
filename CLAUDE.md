# CLAUDE.md - AI Assistant Guide for Autograder4Canvas

## Project Overview

**Autograder4Canvas** is a cross-platform desktop application for automating grading workflows in Canvas LMS (Learning Management System). It provides three main tools for instructors:

1. **Academic Dishonesty Detection** - AI-generated content detection using linguistic pattern analysis
2. **Complete/Incomplete Assignment Grading** - Automated evaluation of submission completeness
3. **Discussion Forum Grading** - Batch grading of Canvas discussion posts

**Version:** 1.3
**License:** GNU GPL v2
**Target Platforms:** macOS, Windows, Linux
**Primary Language:** Python 3.7+

---

## Codebase Structure

```
Autograder4Canvas/
├── src/                                    # Source code (primary development location)
│   ├── run_autograder_v1-3.py             # Main launcher (entry point)
│   ├── autograder_utils.py                # Shared utilities (file ops, config)
│   ├── ai_detection_markers.py            # AI detection module
│   ├── ai_detection_markers.json          # Detection patterns database
│   ├── requirements.txt                    # Python dependencies
│   └── Programs/                           # Grading tool implementations
│       ├── Academic_Dishonesty_Check_v1-3.py
│       ├── Autograder_Complete-Incomplete_v1-3.py
│       └── Autograder_Discussion_Forum_v1-3.py
│
├── build/                                  # Platform-specific builds
│   ├── mac/Autograder4Canvas.app/         # macOS app bundle
│   ├── windows/Autograder4Canvas/         # Windows distribution
│   └── linux/Autograder4Canvas/           # Linux distribution
│
├── Autograder4Canvas.app/                 # Root-level macOS app (legacy?)
├── run_autograder.sh                      # Unix launcher script
├── run_autograder.bat                     # Windows launcher script
├── README.md                              # User documentation
├── README.txt                             # Detailed user guide
└── LICENSE                                # GPL v2 license

```

### Key Directories

- **`src/`** - Primary development location. All code changes should be made here first.
- **`src/Programs/`** - Individual grading tool implementations (self-contained scripts).
- **`build/`** - Contains platform-specific distribution packages. These are build artifacts.
- **Build artifacts** replicate `src/` contents across platforms, suggesting a build process copies files.

---

## Architecture

### Design Pattern

The application follows a **launcher + plugin** architecture:

1. **Launcher** (`run_autograder_v1-3.py`)
   - Entry point for the application
   - Manages Python virtual environment setup
   - Handles dependency installation
   - Provides interactive menu for tool selection
   - Manages settings (output location, auto-open, cleanup)
   - Handles Canvas API token configuration

2. **Utilities Module** (`autograder_utils.py`)
   - Cross-platform file operations (trash, archive, open folder)
   - Configuration management (JSON-based settings)
   - Output directory management with user preferences
   - Platform detection and path handling

3. **Grading Tools** (`src/Programs/*.py`)
   - Self-contained scripts that can run independently
   - Each script handles its own Canvas API interaction
   - All scripts follow the same configuration pattern
   - Generate CSV/Excel output files

4. **AI Detection Module** (`ai_detection_markers.py`)
   - Reusable module for AI-generated content detection
   - JSON-driven pattern database
   - Provides analysis utilities and scoring algorithms

### Data Flow

```
User Input → Launcher → Tool Selection → Canvas API → Data Processing → CSV/Excel Output
                ↓
         Settings/Config
         (JSON storage)
```

### Configuration Storage

- **Location (cross-platform):**
  - Windows: `%LOCALAPPDATA%\CanvasAutograder\settings.json`
  - macOS: `~/Library/Application Support/CanvasAutograder/settings.json`
  - Linux: `~/.config/CanvasAutograder/settings.json`

- **Legacy location:** `~/.canvas_autograder_settings` (text-based, deprecated)

- **Settings managed:**
  - Custom output directory path
  - Auto-open folder after grading
  - Automatic cleanup mode (none/archive/trash)
  - Cleanup threshold (days)
  - Cleanup targets (file types)

### Output Structure

Default output location: `~/Documents/Autograder Rationales/`

```
Autograder Rationales/
├── Academic Dishonesty Reports/
│   ├── csv/                    # CSV reports
│   └── excel/                  # Excel reports
├── Discussion Forums/          # Discussion grading CSV
├── Complete-Incomplete Assignments/  # Completeness grading CSV
└── Archived Reports/           # Optional archive location
    ├── Academic Dishonesty/
    ├── Discussions/
    └── Assignments/
```

---

## Key Components

### 1. Main Launcher (`run_autograder_v1-3.py`)

**Purpose:** Application entry point and orchestrator

**Key Functions:**
- `main()` - Entry point, runs setup and menu loop
- `create_virtual_environment()` - Sets up Python venv
- `install_dependencies()` - Installs packages from requirements.txt
- `select_script()` - Interactive menu for tool/settings selection
- `run_script()` - Executes selected grading tool
- `get_canvas_token()` - Retrieves/prompts for Canvas API token
- `cleanup_old_files()` - Automatic file cleanup based on settings
- `load_settings()` / `save_settings()` - Settings persistence

**Important Patterns:**
- Virtual environment location varies:
  - Inside app bundle: `~/.canvas_autograder_venv`
  - From source: `<repo>/.venv`
- Settings are managed through both legacy (text) and new (JSON) formats
- Menu loop allows returning to menu after running tools or changing settings

### 2. Utilities Module (`autograder_utils.py`)

**Purpose:** Cross-platform file and configuration utilities

**Key Functions:**
- `get_output_base_dir()` - Determines output directory (respects user preference)
- `get_output_dir(subdir_key)` - Gets specific output subdirectory
- `open_folder(path)` - Opens folder in system file browser
- `move_to_trash(file_path)` - Cross-platform trash/recycle bin operation
- `archive_old_files()` / `trash_old_files()` - Bulk file cleanup operations
- `load_config()` / `save_config()` - JSON-based settings management
- `run_first_time_setup()` - Interactive first-run configuration

**Cross-Platform Implementations:**
- **Trash/Recycle Bin:**
  - macOS: Uses AppleScript via osascript
  - Windows: PowerShell with Microsoft.VisualBasic.FileIO
  - Linux: `gio trash` command, fallback to `~/.local/share/Trash/files`

- **Open Folder:**
  - macOS: `open` command
  - Windows: `explorer` command
  - Linux: `xdg-open` command

**Important Constants:**
```python
SUBDIRS = {
    "Academic_Dishonesty": "Academic Dishonesty Reports",
    "Discussion_Forum": "Discussion Forums",
    "Complete-Incomplete": "Complete-Incomplete Assignments",
    "Archived": "Archived Reports"
}
```

### 3. Academic Dishonesty Checker (`Academic_Dishonesty_Check_v1-3.py`)

**Purpose:** Detect AI-generated student submissions using linguistic analysis

**Architecture:**
- Assignment type profiles (notes, drafts, reflections, analytical essays, etc.)
- Multi-level detection (linguistic, structural, authenticity markers)
- Configurable thresholds per assignment type
- Support for citation verification (CrossRef/OpenLibrary APIs)

**Key Features:**
- **Assignment Profiles:** Contextual detection rules based on assignment type
  - `notes_brainstorm` - Inverted checks (flags polished content)
  - `rough_draft` - Higher tolerance for errors
  - `personal_reflection` - Requires personal voice markers
  - `analytical_essay` - Balanced formal analysis
  - `research_paper` - Citation verification enabled

- **Detection Categories:**
  - Linguistic patterns (AI transition phrases, hedge phrases, inflated vocabulary)
  - Structural patterns (paragraph uniformity, sentence patterns)
  - Authenticity markers (personal voice, emotional language)
  - Technical patterns (copy-paste detection, cross-submission checks)

**Output Files:**
- CSV reports: `academic_dishonesty_YYYYMMDD_HHMMSS.csv`
- Excel reports: `academic_dishonesty_YYYYMMDD_HHMMSS.xlsx` (with formatting)

**Configuration:**
```python
CANVAS_BASE_URL = "https://cabrillo.instructure.com"  # Hardcoded institution
MIN_WORD_COUNT = 50
DUPLICATE_SIMILARITY_THRESHOLD = 0.85
```

### 4. Complete/Incomplete Grader (`Autograder_Complete-Incomplete_v1-3.py`)

**Purpose:** Evaluate student submissions for good-faith effort

**Evaluation Criteria:**
- Text body word count (configurable minimum)
- File attachment size and type
- PDF annotation detection (Canvas-specific)
- URL submissions with descriptions

**PDF Annotation Detection:**
```python
# Canvas uses "student_annotation" submission type for annotated PDFs
# Also checks for canvadoc_document_id and preview_url indicators
```

**Special Cases:**
- PDF with annotations → automatically complete
- PDF without annotations → flagged for manual review
- Very short text (< min_word_count) → flagged
- Small files (< 1KB) → flagged

**Output:** CSV with student names, completion status, and flag details

### 5. Discussion Forum Grader (`Autograder_Discussion_Forum_v1-3.py`)

**Purpose:** Batch grade Canvas discussion forum posts

**Features:**
- Fetches discussion entries via Canvas API
- Word count validation
- Reply count tracking
- Generates grading reports

**Output:** CSV with student names, post word counts, reply counts

### 6. AI Detection Markers Module (`ai_detection_markers.py`)

**Purpose:** Reusable AI detection engine with JSON-driven pattern database

**Class: `AIDetectionMarkers`**

Key Methods:
```python
get_markers(category, marker_type)  # Retrieve specific marker set
analyze_text(text, detection_level)  # Full text analysis
count_phrase_occurrences(text, phrases)  # Pattern matching
calculate_suspicion_score(results)  # Aggregate scoring
get_assignment_markers(assignment_type)  # Type-specific markers
get_detection_strategy(user_level)  # Sophistication-aware detection
```

**Detection Levels:**
- `naive` - Basic AI use (obvious patterns)
- `intermediate` - Some editing applied
- `advanced` - Sophisticated prompt engineering
- `very_advanced` - Heavily edited AI content

**Marker Categories:**
- `linguistic_patterns` - Transition phrases, hedge phrases, vocabulary
- `structural_patterns` - Sentence uniformity, paragraph organization
- `authenticity_markers` - Personal voice, emotional vulnerability
- `assignment_type_specific` - Context-based markers

**Database:** `ai_detection_markers.json` (not analyzed in detail, but referenced throughout)

---

## Dependencies

From `requirements.txt`:

```
requests>=2.31.0       # Canvas API HTTP requests
python-dateutil>=2.8.2 # Date/time parsing
pytz>=2023.3           # Timezone handling
openpyxl>=3.1.0        # Excel file generation
```

**Rationale:**
- **requests** - Canvas REST API communication
- **python-dateutil** - Parsing Canvas timestamp formats
- **pytz** - Timezone-aware datetime operations
- **openpyxl** - Creating formatted Excel reports (academic dishonesty tool)

**No external dependencies for:**
- GUI frameworks (uses terminal/CLI interface)
- Database systems (file-based storage only)
- AI/ML libraries (rule-based detection only)

---

## Canvas API Integration

### Authentication

Uses Canvas API tokens stored in environment variable:
```bash
export CANVAS_API_TOKEN="your_token_here"
```

The launcher prompts for token if not set and offers to save it permanently.

### API Endpoint Pattern

```python
CANVAS_BASE_URL = "https://cabrillo.instructure.com"  # Institution-specific
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Example endpoints used:
# GET /api/v1/courses/{course_id}/enrollments
# GET /api/v1/courses/{course_id}/assignments
# GET /api/v1/courses/{course_id}/assignments/{assignment_id}/submissions
# GET /api/v1/courses/{course_id}/discussion_topics/{topic_id}/entries
```

### Pagination Handling

Canvas API uses pagination. Code handles this via:
```python
params = {"per_page": 100}
# Follow 'next' links in response headers if needed
```

### Rate Limiting

No explicit rate limiting implemented. Canvas has built-in rate limits that the API respects.

---

## Development Workflows

### Initial Setup

```bash
# Clone the repository
cd Autograder4Canvas

# The launcher handles Python environment setup automatically
python3 src/run_autograder_v1-3.py

# Or use platform-specific launchers
./run_autograder.sh          # macOS/Linux
run_autograder.bat           # Windows
```

### Making Changes to Grading Tools

1. **Edit source files in `src/` directory** (NOT in `build/`)
2. Test changes by running the launcher:
   ```bash
   python3 src/run_autograder_v1-3.py
   ```
3. Select the tool you modified from the menu
4. Verify output in the configured output directory

### Adding a New Grading Tool

1. Create new script in `src/Programs/`:
   ```python
   # Follow naming pattern: ToolName_v1-3.py
   ```

2. Implement these standard patterns:
   ```python
   import os
   CANVAS_BASE_URL = "https://cabrillo.instructure.com"
   API_TOKEN = os.getenv("CANVAS_API_TOKEN")

   def get_output_base_dir() -> Path:
       # Use same pattern as other tools
   ```

3. Add tool detection pattern in `run_autograder_v1-3.py`:
   ```python
   def get_script_type_info():
       return {
           "Your_Tool_Key": {
               "display": "Your Tool Name",
               "pattern": "*YourTool*.py",
               "subdir": "Your Tool Output Folder",
               "subdir_key": "Your_Tool_Key"
           }
       }
   ```

4. Add subdirectory mapping in `autograder_utils.py`:
   ```python
   SUBDIRS = {
       "Your_Tool_Key": "Your Tool Output Folder"
   }
   ```

### Building for Distribution

**Note:** Build process is not fully documented in the repository. Based on the structure:

1. Source files in `src/` are copied to `build/{platform}/`
2. Platform-specific packaging:
   - macOS: `.app` bundle created
   - Windows: Executable wrapper likely used (installer references)
   - Linux: Shell script launcher with tar.gz distribution

**Recommended:** Create a build script that:
```bash
# Pseudocode
copy src/* to build/mac/Autograder4Canvas.app/Contents/Resources/
copy src/* to build/windows/Autograder4Canvas/src/
copy src/* to build/linux/Autograder4Canvas/src/
```

### Testing

**Current state:** No automated tests found in repository.

**Recommended testing approach:**
1. Manual testing via launcher
2. Test with Canvas sandbox/test courses
3. Verify cross-platform file operations
4. Validate output file formats (CSV/Excel)

**Test checklist:**
- [ ] Virtual environment creation
- [ ] Dependency installation
- [ ] Canvas API authentication
- [ ] Each grading tool execution
- [ ] Output file generation
- [ ] Settings persistence
- [ ] Cleanup operations (archive/trash)
- [ ] Cross-platform compatibility

---

## Coding Conventions

### File Naming

- Source files: `descriptive_name_v1-3.py` (version suffix for tracking)
- Output files: `tool_type_YYYYMMDD_HHMMSS.csv` (timestamp for uniqueness)
- Config files: `settings.json` (JSON format preferred over legacy text)

### Code Style

Based on analysis of existing code:

1. **Type hints:** Used in utilities module, recommended for new code
   ```python
   def function_name(param: Type) -> ReturnType:
   ```

2. **Docstrings:** Present in utilities, should be added to all public functions
   ```python
   def function_name(param):
       """
       Brief description.

       Args:
           param: Description

       Returns:
           Description
       """
   ```

3. **Constants:** UPPER_CASE with module-level scope
   ```python
   CANVAS_BASE_URL = "https://cabrillo.instructure.com"
   MIN_WORD_COUNT = 50
   ```

4. **Error handling:** Use try-except with user-friendly messages
   ```python
   try:
       # operation
   except SomeError as e:
       print(f"❌ Friendly error message: {e}")
   ```

5. **Unicode emoji:** Used extensively for user feedback
   - ✅ Success
   - ❌ Error
   - ⚠️ Warning
   - 📁 File/folder operations
   - 📥 Downloading
   - 📤 Uploading
   - 🔍 Searching/analyzing

### Platform Compatibility

Always check platform when using OS-specific features:

```python
import platform

system = platform.system()  # "Darwin", "Windows", "Linux"

if system == "Darwin":
    # macOS-specific code
elif system == "Windows":
    # Windows-specific code
else:
    # Linux/Unix-specific code
```

### Path Handling

Use `pathlib.Path` for all file operations:

```python
from pathlib import Path

# Good
config_dir = Path.home() / ".config" / "app"

# Avoid
config_dir = os.path.join(os.path.expanduser("~"), ".config", "app")
```

### Configuration Management

New code should use JSON config (via `autograder_utils.py`):

```python
from autograder_utils import load_config, save_config, get_output_base_dir

config = load_config()
output_dir = get_output_base_dir()  # Respects user preference
```

---

## AI Assistant Guidelines

### When Modifying Code

1. **Always edit `src/` directory first**, never edit `build/` directories directly
2. **Test changes** by running the launcher before committing
3. **Preserve cross-platform compatibility** - test changes on target platforms if possible
4. **Follow existing patterns** - look at similar code before implementing new features
5. **Update version numbers** if making significant changes (currently v1-3)

### Common Pitfalls to Avoid

1. **Hardcoded paths:** Always use `Path.home()` or platform detection
2. **Assuming platform:** Don't assume Unix-like system - check `platform.system()`
3. **Breaking virtual environment:** Don't change `requirements.txt` without testing
4. **Ignoring Canvas API pagination:** Large courses may require pagination handling
5. **File system encoding:** Always use `encoding='utf-8'` when reading/writing files

### When Adding Features

1. **Check if utilities exist:** `autograder_utils.py` has many reusable functions
2. **Maintain settings compatibility:** Don't break existing user settings
3. **Add to settings menu:** New settings should be accessible via launcher menu
4. **Document in README:** User-facing changes need documentation updates
5. **Consider all three tools:** Does the feature apply to other grading tools?

### Security Considerations

1. **API tokens:** Never log or expose Canvas API tokens
2. **Student data:** Handle student information securely (PII in CSV outputs)
3. **File operations:** Validate paths to prevent directory traversal
4. **External APIs:** Handle failures gracefully (citation verification, etc.)

### Performance Considerations

1. **Canvas API calls:** Minimize requests, use pagination efficiently
2. **Large submissions:** Handle large text submissions without memory issues
3. **File cleanup:** Archive/trash operations should batch efficiently
4. **Caching:** Consider caching Canvas data for repeated operations

---

## Common Tasks

### Changing the Canvas Institution

Edit the `CANVAS_BASE_URL` in all grading tool files:

```python
# In src/Programs/*.py files
CANVAS_BASE_URL = "https://your-institution.instructure.com"
```

**Note:** This is currently hardcoded. Consider making it a configurable setting.

### Adding New AI Detection Patterns

1. Edit `src/ai_detection_markers.json` to add patterns
2. Or use `AIDetectionMarkers` class programmatically:
   ```python
   from ai_detection_markers import AIDetectionMarkers
   markers = AIDetectionMarkers()
   # Access and modify marker data
   ```

### Modifying Output Format

Each tool generates its own output. To change format:

1. Locate CSV writing code in the tool (e.g., `Academic_Dishonesty_Check_v1-3.py`)
2. Modify CSV structure or add Excel formatting (openpyxl)
3. Ensure headers and data rows match

### Adding New Settings

1. Add setting to `load_settings()` defaults in `run_autograder_v1-3.py`:
   ```python
   defaults = {
       "your_new_setting": default_value
   }
   ```

2. Add menu option in `select_script()`:
   ```python
   print(f"  [X] Your Setting Name")
   # Handle in choice logic
   ```

3. Implement setting toggle/configuration function
4. Use setting in relevant code sections

### Debugging Canvas API Issues

Enable verbose logging:

```python
# Add to start of script
import logging
logging.basicConfig(level=logging.DEBUG)

# Or print API responses
response = requests.get(url, headers=HEADERS)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:500]}")  # First 500 chars
```

### Handling New Canvas Submission Types

Canvas may add new submission types. To handle:

1. Check Canvas API documentation for new `submission_type` values
2. Update evaluation logic in relevant tool:
   ```python
   submission_type = submission.get("submission_type")
   if submission_type == "new_type":
       # Handle new type
   ```

---

## Important Files Reference

### Configuration Files

| File | Purpose | Format |
|------|---------|--------|
| `~/.canvas_autograder_settings` | Legacy settings (deprecated) | Text key=value |
| `{config_dir}/settings.json` | Current settings | JSON |
| `src/ai_detection_markers.json` | AI detection patterns | JSON |

### Output Files

| Pattern | Tool | Location |
|---------|------|----------|
| `academic_dishonesty_*.csv` | Academic Dishonesty | `{output}/Academic Dishonesty Reports/csv/` |
| `academic_dishonesty_*.xlsx` | Academic Dishonesty | `{output}/Academic Dishonesty Reports/excel/` |
| `complete_incomplete_*.csv` | Complete/Incomplete | `{output}/Complete-Incomplete Assignments/` |
| `discussion_forum_*.csv` | Discussion Forum | `{output}/Discussion Forums/` |

### Launcher Scripts

| File | Platform | Purpose |
|------|----------|---------|
| `run_autograder.sh` | macOS/Linux | Shell launcher |
| `run_autograder.bat` | Windows | Batch launcher |
| `src/run_autograder_v1-3.py` | All | Python launcher (primary) |

---

## Architecture Decisions

### Why Virtual Environment?

- Isolates dependencies from system Python
- Allows specific version pinning
- Prevents conflicts with other Python applications
- Location varies to avoid issues with macOS app bundle signing

### Why JSON Config?

- Structured data (vs. text key=value)
- Easy to extend with nested settings
- Better error handling (vs. parsing text)
- Cross-platform compatibility

### Why Separate Tool Scripts?

- Modular design - tools can run independently
- Easier to maintain and test individual tools
- Users can run specific tools without the launcher
- Allows different update cycles per tool

### Why CSV + Excel Output?

- **CSV:** Universal compatibility, easy to import to LMS
- **Excel:** Better formatting, color coding, formulas
- Academic dishonesty tool provides both for flexibility

---

## Future Considerations

### Potential Improvements

1. **Configuration:**
   - Make Canvas URL configurable (currently hardcoded)
   - Add per-course settings (different thresholds)
   - Support multiple Canvas instances

2. **Testing:**
   - Add unit tests for utilities module
   - Integration tests with Canvas sandbox
   - Automated build verification

3. **Build Process:**
   - Automate platform-specific builds
   - Create proper installers (DMG, MSI, DEB)
   - Code signing for macOS/Windows

4. **Features:**
   - GUI option (in addition to CLI)
   - Batch processing multiple assignments
   - Historical analytics (track AI detection over time)
   - Integration with other LMS platforms (Moodle, Blackboard)

5. **AI Detection:**
   - Machine learning-based detection (supplement rules)
   - Integration with commercial AI detectors
   - Continuous pattern database updates

### Known Limitations

1. **Institution-specific:** Canvas URL is hardcoded to Cabrillo
2. **No GUI:** Terminal/CLI only (may be barrier for some users)
3. **Manual updates:** No auto-update mechanism
4. **Single-threaded:** API calls are sequential (could be parallelized)
5. **Limited error recovery:** Canvas API failures may require restart

---

## Getting Help

### Documentation Locations

- **User Guide:** `README.md` and `README.txt` in repository root
- **License:** `LICENSE` (GNU GPL v2)
- **This Guide:** `CLAUDE.md` (for AI assistants and developers)

### Code Examples

Look at existing tools for patterns:
- Cross-platform code: `autograder_utils.py`
- Canvas API usage: Any `src/Programs/*.py` file
- Settings management: `run_autograder_v1-3.py`
- Pattern matching: `ai_detection_markers.py`

### Canvas API Documentation

Official Canvas LMS REST API documentation:
https://canvas.instructure.com/doc/api/

### Support

- Repository: Check for issues/discussions on GitHub
- Canvas Community: https://community.canvaslms.com/

---

## Version History

- **v1.3 (Current):** Cross-platform support, JSON config, cleanup features
- **v1.2:** Earlier version (referenced in README)
- **v1.1 and earlier:** Not documented in current repository

### File Versioning

Python files use `_v1-3` suffix to indicate version. When making breaking changes:
1. Increment version number in filename
2. Update references in launcher
3. Consider migration path for existing users

---

## Summary for AI Assistants

**Key Principles:**

1. ✅ **Edit `src/` first** - Never modify `build/` directly
2. ✅ **Cross-platform always** - Test on macOS, Windows, Linux
3. ✅ **Use existing utilities** - Check `autograder_utils.py` first
4. ✅ **Preserve user settings** - Maintain backward compatibility
5. ✅ **Follow patterns** - Look at existing code before implementing new features
6. ✅ **Security first** - Handle API tokens and student data carefully
7. ✅ **User-friendly** - CLI uses emoji and clear messages
8. ✅ **Document changes** - Update README for user-facing changes

**Quick Reference:**

- **Main entry point:** `src/run_autograder_v1-3.py`
- **Utilities:** `src/autograder_utils.py`
- **Grading tools:** `src/Programs/`
- **Config location:** Platform-specific JSON file (see Configuration Storage section)
- **Output location:** `~/Documents/Autograder Rationales/` (customizable)
- **Dependencies:** requests, python-dateutil, pytz, openpyxl
- **Python version:** 3.7+ required

**When in doubt:**
1. Check how existing code handles the situation
2. Maintain cross-platform compatibility
3. Test before committing
4. Ask for clarification if requirements are unclear

---

*This guide was created to help AI assistants understand and work effectively with the Autograder4Canvas codebase. Last updated: 2025-12-27*
