# Integration Guide: Academic Dishonesty Check v2.0

This guide explains how to integrate the v2.0 Academic Dishonesty Check with
the existing Canvas Autograder launcher system.

## Quick Integration

### Option 1: Replace v1.3 (Recommended for Testing)

1. Rename the existing script:
   ```
   mv Academic_Dishonesty_Check_v1-3.py Academic_Dishonesty_Check_v1-3.py.backup
   ```

2. Copy v2.0 to the same location:
   ```
   cp academic_dishonesty_v2/Academic_Dishonesty_Check_v2.py Academic_Dishonesty_Check_v2.py
   ```

3. The run_autograder.py will automatically detect it (pattern: `*Academic*Dishonesty*.py`)

### Option 2: Run Both Versions

1. Keep both files in the Programs/ directory:
   - `Academic_Dishonesty_Check_v1-3.py`
   - `Academic_Dishonesty_Check_v2.py`

2. The launcher will find the first match. To control which runs:
   - Temporarily rename the one you don't want to use (add `.disabled`)

### Option 3: Modify run_autograder.py

Add v2 as a separate menu option by modifying `get_script_type_info()`:

```python
def get_script_type_info():
    return {
        "Academic_Dishonesty": {
            "display": "Academic Dishonesty Check (v1.3)",
            "pattern": "*Academic*Dishonesty*v1*.py",
            "subdir": SUBDIRS.get("Academic_Dishonesty", "Academic Dishonesty Reports"),
            "subdir_key": "Academic_Dishonesty"
        },
        "Academic_Dishonesty_v2": {
            "display": "Academic Dishonesty Check (v2.0) ✨",
            "pattern": "*Academic*Dishonesty*v2*.py",
            "subdir": SUBDIRS.get("Academic_Dishonesty", "Academic Dishonesty Reports"),
            "subdir_key": "Academic_Dishonesty"
        },
        # ... other scripts
    }
```

## Directory Structure

After integration, your project should look like:

```
your_project/
├── run_autograder_v1-3.py           # Main launcher
├── autograder_utils.py              # Utilities
├── Academic_Dishonesty_Check_v1-3.py    # v1.3 (can keep as backup)
├── Academic_Dishonesty_Check_v2.py      # v2.0 (main script)
├── config/                              # v2.0 configuration
│   ├── dishonesty_markers/
│   │   ├── core/
│   │   │   ├── ai_transitions.yaml
│   │   │   ├── balance_markers.yaml
│   │   │   └── ... (other markers)
│   │   └── custom/
│   ├── profiles/
│   │   ├── personal_reflection.yaml
│   │   └── ... (other profiles)
│   └── context_profiles/
│       └── community_college.yaml
├── modules/                             # v2.0 Python modules
│   ├── __init__.py
│   ├── marker_loader.py
│   ├── peer_comparison.py
│   ├── context_analyzer.py
│   ├── draft_comparison.py
│   ├── citation_verifier.py
│   ├── consent_system.py
│   ├── update_checker.py
│   └── report_generator.py
├── docs/
│   └── USER_GUIDE.md
├── Autograder_Complete-Incomplete_v1-3.py
├── Autograder_Discussion_Forum_v1-3.py
└── ... (other existing files)
```

## First Run

When v2.0 runs for the first time, it will:

1. **Prompt for consent** - User must acknowledge tool limitations
2. **Check for config directory** - Creates if missing
3. **Use built-in defaults** - Works without YAML files (they're optional)

## Configuration Paths

v2.0 looks for configuration in these locations (in order):

1. **Same directory as script**: `./config/`
2. **User config directory**:
   - Windows: `%LOCALAPPDATA%\CanvasAutograder\`
   - macOS: `~/Library/Application Support/CanvasAutograder/`
   - Linux: `~/.config/CanvasAutograder/`

If no YAML files are found, the script uses built-in default patterns.

## Dependencies

v2.0 has minimal dependencies:

**Required:**
- Python 3.7+
- `requests` (for Canvas API - same as v1.3)

**Optional:**
- `pyyaml` (for YAML config loading - uses built-in defaults without it)

Install with:
```bash
pip install requests pyyaml
```

Or add to requirements.txt:
```
requests>=2.25.0
PyYAML>=5.4
```

## Environment Variables

Same as v1.3:
- `CANVAS_API_TOKEN` - Canvas API token
- `CANVAS_BASE_URL` - Canvas instance URL (default: https://cabrillo.instructure.com)

## Output Compatibility

v2.0 outputs are compatible with the existing file structure:
- Reports go to the same `Academic Dishonesty Reports/` subdirectory
- CSV and Excel formats supported
- File naming follows existing conventions

## Key Differences from v1.3

| Feature | v1.3 | v2.0 |
|---------|------|------|
| Pattern detection | Hardcoded | YAML configurable |
| Assignment profiles | None | 7 profiles (reflection, essay, etc.) |
| Context awareness | None | Community college adjustments |
| Peer comparison | None | Statistical outlier detection |
| Draft comparison | None | Compares draft to final |
| Citation checking | None | Verifies citations exist |
| First-run consent | None | Required acknowledgments |

## Rollback

If issues arise, simply rename files:
```bash
mv Academic_Dishonesty_Check_v2.py Academic_Dishonesty_Check_v2.py.disabled
mv Academic_Dishonesty_Check_v1-3.py.backup Academic_Dishonesty_Check_v1-3.py
```

## Support

See `docs/USER_GUIDE.md` for detailed usage instructions.
