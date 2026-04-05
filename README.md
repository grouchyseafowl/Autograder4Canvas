# Autograder4Canvas

**Ethics-first pedagogical infrastructure for community college instructors.**

A tool for reading your class — not scoring it. Autograder4Canvas reads student submissions to surface what students are reaching for and why that might be interesting: the intellectual moves they're making, the connections they're drawing to personal and community experience, the places they're pushing back or recentering dominant frames. It also surfaces classwide patterns — emergent themes, tensions and dialectics between students, dynamics like tone policing or colorblind reframing that are only visible when you read the whole class together.

The goal is to give teachers a richer picture of where students are intellectually before walking into the room — not to produce grades or verdicts. Built for complete/incomplete and contract grading, turning assignemnts into launching points for classroom discussion. Autograder4Canvas generates insights from student work to help teachers decide where to take the class next.

Built by a community college Ethnic Studies instructor for other educators. AAVE, multilingual, and neurodivergent patterns are treated as signals of engagement and protected. Rich qualitative analysis based on critical pedagogy principles, ensuring community knowledge and life experience are presented as strengths, counteracting deficit-based models that dominate the distributional norms of AI training data. 

---

## Features

### Desktop GUI
Custom retro-futurist amber terminal interface (PySide6/Qt6) with:
- Course browser with semester grouping, modality badges, and ungraded-assignment counts
- Assignment timeline view with deadline grouping (Past | This Week | Upcoming)
- Layered results viewer for grading outcomes, integrity analysis, and insights
- Configurable font-scale accessibility (0.75x–2.0x)
- All Canvas API calls and LLM analysis run in background worker threads

### Insights Engine
Two-phase analytical pipeline that reads student submissions for pedagogical insight — running locally on instructor hardware via Ollama or Apple MLX, never storing student data. The model's job is not to assess whether students got the content right. It's to figure out what a student is reaching for and why that might be interesting. This distinction matters especially for courses like Ethnic Studies and Native American Studies, where the concern that AI models lack historical or political knowledge is well-founded — but also beside the point, because the system isn't checking facts. It's reading moves.

The pipeline surfaces three things: what individual students are doing intellectually (theme tags, notable verbatim quotes, emotional register, concepts applied, personal and community knowledge being used as intellectual resource); what the class is doing collectively (emergent themes, tensions and dialectics between students, power moves like recentering or re-normalization of dominant perspectives that silence marginalized voices); and who may need a check-in (burnout signals, disengagement, truncated submissions). Burnout and academic dishonesty correlate strongly — surfacing the former is often more useful than trying to detect the latter directly.

The architecture is designed around a set of commitments about how student work should be read:

**Community reading, not individual surveillance.** The pipeline runs a full class reading *before* per-student coding. Students are read as a community in conversation — what they're reaching for, where they connect, where they disagree — because relational harms like tone policing or essentializing are only visible in context. A student writing "I don't see race" reads differently alone than alongside classmates describing how race shaped their families.

**Reader-not-judge architecture.** The LLM reads first as a human reader would — open prose, no JSON, no rubric — then a second pass extracts structured fields grounded in what the model actually noticed. This prevents slot-filling and forces genuine reading before extraction. The system generates *observations*, not verdicts. Teachers read what the model noticed and decide what warrants action.

**Structured data preserves nuance.** Every pipeline stage produces Pydantic-validated structured data, never free-form prose synthesis. Each coding record captures theme tags, notable quotes (always verbatim — teachers hear student voice, not model paraphrase), emotional register, concepts applied, and lens observations. A student cannot be reduced to an engagement score. Theme confidence scores preserve uncertainty rather than hiding it.

**Political urgency is not distress.** Concern detection is always a dedicated, separately-scoped LLM call — never bundled with coding. The prompts explicitly protect students expressing anger about injustice, engaging with assigned material about trauma, disclosing disability analytically, or using passionate language about justice. Anti-bias post-processing catches tone-policing language in the model's own output, demotes flags on structural critique, and warns the teacher when model bias is likely.

**Asset-based framing encoded in prompts.** Every prompt reframes deficit language: "engagement signals" not "concern levels," "what the student is reaching for" not "what they failed to articulate." Non-standard English, AAVE, multilingual syntax, and neurodivergent writing styles are treated as valid academic registers — assets, not deficits.

**Decomposed cognition for small models.** The pipeline is designed to produce analysis approaching 400–700B-class quality from a 12B model running on 16GB of local RAM with no GPU. It does this by decomposing the structure of critical pedagogy into a series of small, focused operations that a smaller model can handle reliably — comprehension, interpretation, concerns — each asking a single cognitive skill. Each pass grounds the next. This prevents the model from making up quotes to fit a judgment, confusing content engagement with structural critique, or hallucinating connections. It also means runs take time (roughly 2–4 minutes per student), but the pipeline is crash-resumable and designed to run overnight.

**The pipeline:**
- **Phase 1 — Quick Analysis (instant, no LLM required):** Word frequency, VADER sentiment, embedding-based clustering, submission statistics, and pattern-based signal detection. Available in seconds.
- **Phase 2 — LLM Analysis (background):** Class reading → per-submission coding (theme tags, emotional register, notable quotes) → emergent theme generation → outlier surfacing → class-level synthesis narrative → draft student feedback. All intermediary results persisted to SQLite for crash-resumability.
- **Longitudinal Trajectories:** Per-student semester arcs tracking intellectual growth, theme evolution, and engagement patterns — framed around what students *built*, not what they lack. Variable output is described, never pathologized.
- **Subject-Area Lenses:** Pre-built analysis templates for Ethnic Studies, STEM, humanities, and more — each with equity-aware prompt fragments and custom strength patterns.
- **Teacher Profile Learning:** Theme renames, sensitivity adjustments, and coding corrections accumulate into a persistent profile that shapes future runs. The teacher is always the final authority.

### Multilingual & Multimodal Submissions
Full preprocessing pipeline so students can submit in any language or medium:
- Audio transcription via faster-whisper (CTranslate2)
- Multilingual translation via Ollama (70+ languages, langdetect)
- PDF and DOCX text extraction
- Image-to-text OCR

### Academic Integrity Analysis
Population-aware pattern detection designed as **a conversation starter, not a verdict.**
- Linguistic pattern analysis with externalized, YAML-configurable markers
- Cohort-calibrated baselines (class-relative, not absolute thresholds)
- Two-axis bias calibration (see [Research](#research) below)
- Context-aware adjustments for ESL, first-generation, neurodivergent, and working students
- Requires informed consent before running; makes detection biases visible

### Grading Automation
- Complete/Incomplete grading with configurable word-count thresholds
- Discussion forum grading (posts and replies)
- Bulk runs across multiple courses and assignments
- Scheduled automation via macOS launchd, Windows Task Scheduler, or systemd

---

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

---

## Quick Start

1. **Get your Canvas API token:** Log into Canvas → Account → Settings → New Access Token

2. **Launch Autograder4Canvas** — on first run, enter your Canvas URL and API token in the setup dialog (or explore with built-in demo data)

3. **Select a course** from the semester-grouped sidebar, then **select assignments** from the timeline view

4. **Run an analysis:**
   - **Quick Run** — grade or analyze a single assignment
   - **Bulk Run** — batch process multiple courses and assignments
   - **Insights** — launch the two-phase pedagogical analysis pipeline

5. **Review results** in the layered results viewer — grading outcomes, integrity analysis, and insights are all accessible from the Review tab

---

## Research

### Output Format as the Activation Function for Bias

This project includes original research producing significant findings on how LLM output structure activates structural bias in academic integrity detection.

**The core finding:** Binary classification formats (FLAG/CLEAR) produce systematically disparate false positive rates on minoritized students. The same model, with the same data, switched from classification to generative observation, eliminates the disparity entirely. This is not about the model's knowledge, the prompt, or training data — it's the output structure itself.

**Evidence:**
- Tested across 6+ model families (Gemma, Llama, Qwen, Gemini, DeepSeek)
- 32-student synthetic corpus with controlled demographic patterns (ESL, AAVE, neurodivergent writing, righteous anger, burnout)
- 43% of incorrectly flagged students had explanations that *argued against the flag* — the model wrote "passion is understandable and appropriate," then flagged the student anyway
- Observation-only architecture: 7/7 correct readings where the classifier produced 3 false positives on protected students
- Replication across 5 runs: 100% true positive detection, 0% false positive rate on protected students (45 checks)

**Key insights:**
1. **LLMs identify bias patterns but reproduce them anyway** — classification task overrides conceptual understanding
2. **Output format determines epistemological frame** — JSON-first produces deficit framing; reading-first produces asset framing
3. **Class context improves generation but worsens classification** — models use richer context to find *more* things to flag
4. **Self-contradiction reveals bias structure** — the flag and the explanation disagree, exposing the classificatory mechanism
5. **Generative tasks produce more equitable outputs than classificatory tasks** — across all comparisons

These findings inform the two-axis bias calibration system built into the tool:
- **CohortCalibrator** — class-relative engagement baselines with Bayesian cold-start blending and exponential moving average evolution across assignments
- **WeightComposer** — composes effective detection weights from education-level profiles × population overlays (ESL/multilingual, first-generation, neurodivergent). Per-student overrides always resolve to the more protective setting.

Theory grounding: Ruha Benjamin (*Race After Technology*), Bowker & Star (*Sorting Things Out*), Eve Tuck ("Suspending Damage"), Bonilla-Silva (*Racism without Racists*).

Research documents are in [`docs/research/`](docs/research/).

---

## Core Values

- **Student dignity & agency** — Students are knowledge creators, not potential cheaters
- **Educational equity** — Calibrated for ESL, first-gen, neurodivergent, and working students
- **Data sovereignty** — Processes locally, never stores student work
- **Transparency** — Human judgment over algorithmic "accuracy"; detection biases made visible
- **Bias as architecture** — Per-institution and per-population calibration is built into the system, not bolted on

---

## Tech Stack

**GUI:** PySide6 (Qt6)  
**LLM Backends:** Ollama (local), Apple MLX, OpenAI-compatible APIs  
**NLP & ML:** sentence-transformers, scikit-learn, VADER Sentiment, textstat, langdetect  
**Audio:** faster-whisper (CTranslate2)  
**Data:** SQLite, Pydantic, pandas, NumPy  
**Documents:** pdfminer.six, python-docx, Pillow  
**Canvas Integration:** REST API (requests)  
**Distribution:** PyInstaller (macOS .dmg, Windows .exe, Linux .tar.gz)  

## Requirements

- Canvas LMS account with API access
- Internet connection for Canvas API calls
- For Insights Engine: [Ollama](https://ollama.com) (recommended) or Apple Silicon Mac with MLX
- Python 3.7+ (bundled in pre-built apps)

## Building from Source

See [Development Guide](docs/INTEGRATION_GUIDE.md) for build instructions.

## Documentation

- [User Guide](src/docs/USER_GUIDE.md) — Detailed usage instructions
- [Automation Guide](AUTOMATION_README.md) — Set up automated grading workflows
- [Academic Integrity Check](Academic_Dishonety_check_README.txt) — Ethical considerations and usage
- [Research Overview](docs/research/RESEARCH_OVERVIEW.md) — Bias calibration research findings

## Support

For questions or issues, please [open an issue](https://github.com/grouchyseafowl/Autograder4Canvas/issues) on GitHub.

## License

GNU GPL v3 — See LICENSE file for details.

## Credits

Built by a community college instructor for educators teaching humanities and social sciences.
