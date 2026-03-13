# Academic Dishonesty Check v2.0

**Adaptive, Data-Driven Academic Integrity Analysis System**

## Important: What This Tool Is (And Isn't)

### ✓ What This Tool IS:
- A **conversation starter** for discussing student work
- An **outlier detector** using peer comparison within a class
- A **pedagogical support** for upholding learning objectives
- **Context-aware** for ESL, first-generation, and community college students

### ✗ What This Tool IS NOT:
- A verdict or proof of cheating
- An "AI detector" (it detects *dishonest use*, not all AI use)
- Infallible (false positives occur, especially for diverse populations)
- A replacement for instructor judgment

## Philosophy

This tool centers on **academic dishonesty** rather than **AI detection**. The key question is not "Did the student use AI?" but rather "Did the student engage with the learning objectives?"

### Key Principles:

1. **Authorship is central**: Students must be the primary intellectual source of their work
2. **Context determines dishonesty**: The same AI use can be legitimate or dishonest depending on the assignment
3. **Learning over products**: The process matters more than the polish
4. **Equity focus**: Avoid false positives for ESL and first-generation students
5. **Conversation, not accusation**: All flags are starting points for dialogue

## Features

### Peer Comparison
Instead of absolute thresholds, the tool identifies statistical outliers *within each class cohort*. This adapts to:
- Different disciplines and writing styles
- Varying assignment expectations
- Class-specific patterns

### Context-Aware Adjustments
Reduces false positives by adjusting thresholds for:
- **ESL students**: Formal transitions may be taught structures
- **First-generation students**: Formulaic writing may reflect developmental English instruction
- **Community college contexts**: Higher thresholds account for population diversity

### Assignment Profiles
Different detection approaches for different assignment types:
- **Personal Reflection**: Focus on *absence* of personal voice
- **Analytical Essay**: Focus on *presence* of generic content
- **Rough Draft**: Flag *over-polish* as suspicious
- **Discussion Post**: Check for course material engagement

### Pedagogical Reporting
Reports include:
- Conversation starters (not accusations)
- Verification questions for instructors
- Revision guidance tied to learning objectives
- Context notes explaining adjustments applied

## Installation

### Requirements
- Python 3.8+
- `requests` library (for Canvas integration)
- `pyyaml` (optional, for YAML configuration)

### Setup
```bash
# Install dependencies
pip install requests pyyaml

# Set Canvas API token
export CANVAS_API_TOKEN="your_token_here"
export CANVAS_BASE_URL="https://your.instructure.com"

# Run the tool
python Academic_Dishonesty_Check_v2.py
```

## Usage

### Interactive Mode
```bash
python Academic_Dishonesty_Check_v2.py
```

This presents a menu to:
1. Analyze a Canvas assignment (batch processing)
2. Analyze pasted text (single submission)
3. View assignment profiles
4. Learn about the tool

### Command Line
```bash
python Academic_Dishonesty_Check_v2.py --help
python Academic_Dishonesty_Check_v2.py --version
```

## Directory Structure

```
academic_dishonesty_v2/
├── Academic_Dishonesty_Check_v2.py  # Main script
├── modules/                          # Python modules
│   └── __init__.py
├── config/
│   ├── dishonesty_markers/
│   │   ├── core/                     # Built-in marker definitions
│   │   │   ├── ai_transitions.yaml
│   │   │   ├── personal_voice_markers.yaml
│   │   │   └── generic_phrases.yaml
│   │   └── custom/                   # User-added markers
│   ├── profiles/                     # Assignment type profiles
│   │   └── personal_reflection.yaml
│   ├── context_profiles/             # Population adjustments
│   │   └── community_college.yaml
│   └── institution_profiles/         # Institution demographics
└── docs/
```

## Configuration

### YAML Marker Files
Markers are defined in YAML files with:
- Pattern definitions (string or regex)
- Confidence weights
- Context adjustments (ESL, assignment type)
- Pedagogical notes

### Assignment Profiles
Each profile specifies:
- Detection approach (presence vs. absence)
- Weight multipliers for different markers
- Learning objectives
- Instructor guidance

### Context Profiles
Population-specific adjustments:
- Marker weight multipliers
- Threshold adjustments
- Rationale for each adjustment

## Understanding Reports

### Concern Levels
- **HIGH**: Recommend structured conversation with student
- **ELEVATED**: Recommend brief check-in
- **MODERATE**: Note for pattern tracking across assignments
- **LOW**: Provide feedback only if desired
- **NONE**: No concerns identified

### Scores
- **Suspicious Score**: Sum of concerning markers found
- **Authenticity Score**: Sum of authentic voice markers found
- **Percentile**: Position within class distribution

### Outlier Detection
Students flagged as outliers based on:
- Score above class threshold (90th or 95th percentile)
- Z-score > 2 standard deviations from mean
- Low authenticity compared to peers

## Best Practices

### Before Flagging a Student
1. Review the submission yourself
2. Consider the student's background (ESL, first-gen)
3. Check for ESL error patterns (these indicate human authorship)
4. Compare against the student's previous work

### Having the Conversation
1. Lead with curiosity, not accusation
2. Use the conversation starters provided
3. Ask about their process and specific details
4. Offer revision opportunity before formal action

### Interpreting Results
1. Multiple high-concern students may indicate assignment design issues
2. Context adjustments explain why thresholds differ
3. Peer comparison reveals class patterns
4. Low authenticity alone is not proof of dishonesty

## Contributing

This tool is designed to be:
- **Adaptable**: Add custom markers via YAML files
- **Transparent**: All detection logic is visible
- **Updatable**: Marker files can be versioned and updated

### Adding Custom Markers
1. Create a YAML file in `config/dishonesty_markers/custom/`
2. Follow the schema in existing marker files
3. Restart the tool to load new markers

### Reporting Issues
If you encounter false positives:
1. Note the student context (ESL, first-gen, etc.)
2. Identify which markers triggered the flag
3. Consider whether those markers need context adjustment

## Version History

### v2.0.0 (2025-12-26)
- Complete architectural redesign
- YAML-based externalized markers
- Peer comparison instead of absolute thresholds
- Context-aware adjustments for diverse populations
- Pedagogically-framed reporting

### v1.3 (Previous)
- Hardcoded detection patterns
- Fixed thresholds
- Limited context awareness

## License

Educational use. Designed for community college contexts.

## Contact

For questions about this tool or its pedagogical approach, consult your institution's academic integrity office.

---

*Remember: This tool supports instructor judgment. It does not replace it.*
