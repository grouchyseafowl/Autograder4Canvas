# Autograder4Canvas

**Ethics-first pedagogical infrastructure for community college instructors.**

A tool for reading your class — not scoring it. Autograder4Canvas reads student submissions to surface what students are reaching for and why that might be interesting: the intellectual moves they're making, the connections they're drawing to personal and community experience, the places they're pushing back or recentering dominant frames. It also surfaces classwide patterns — emergent themes, tensions and dialectics between students, dynamics like tone policing or colorblind reframing that are only visible when you read the whole class together.

The goal is to give teachers a richer picture of where students are intellectually before walking into the room — not to produce grades or verdicts. Built for complete/incomplete and contract grading, turning assignments into launching points for classroom discussion. Runs locally on instructor hardware, FERPA-compliant by design — no student data leaves the machine.

---

## Why This Exists

I built Autograder4Canvas while teaching as one of two full-time Ethnic Studies faculty at a California community college, carrying 175–200 students per semester — with enrollment climbing toward 250 as the state's Ethnic Studies transfer requirement (AB 1460) drove every CSU-bound student through our department. A few additional instructors taught sections from other departments, but the scale relative to staffing was significant.

The requirement changed what it meant to teach the course. Where enrollment had been self-selecting — students who chose Ethnic Studies and arrived committed — the mandate meant every transfer-track student came through regardless of starting point. In the current political climate, that means students who are actively hostile toward marginalized communities sit in the same room as the students those views target — and are told to discuss race, identity, and power as a condition of graduating. As a transgender professor of Ethnic Studies, I was not outside these dynamics — I was in them alongside my students, navigating the same hostility the course material was designed to examine. I built Autograder4Canvas to solve real problems that emerged from teaching in these conditions at this scale.

The tool grew in stages:

**Stage 1 — Automation.** A script that pulled assignments from Canvas and assessed word counts — a limited proxy for engagement, but defensible when set conservatively: low enough to mean more than bare compliance, high enough that students who didn't engage meaningfully didn't receive credit. This freed hours per week from administrative grading.

**Stage 2 — Integrity analysis.** I added academic integrity detection, but almost immediately ran into a tension I couldn't engineer around: as an Ethnic Studies professor with abolitionist commitments, I was building a surveillance tool for the very students my discipline exists to advocate for. I didn't want to police students in an Ethnic Studies course. But I also couldn't ignore students who were genuinely abusing the system — submitting AI-generated text or recycled work while classmates put in real intellectual effort. That ambivalence drove the design: the tool had to surface patterns for teacher review without acting as judge, and it had to do so without reproducing the demographic biases I was discovering in the signals — ESL students, AAVE speakers, neurodivergent writers, and first-generation students triggered false positives at rates that made the tool a liability unless bias was addressed structurally.

**Stage 3 — Design infrastructure.** The tension between abolitionism and accountability forced a deeper question: how do you build detection tools that don't reproduce the sorting systems Ethnic Studies exists to critique? I designed a system that used an LLM to simulate an assembly of specialists across critical theory — critical race theory, disability studies, abolitionist pedagogy, feminist technoscience — to pressure-test every design decision. One of those assembled voices was an abolitionist, and it became clear almost immediately that the framework I'd built was far too powerful to spend on catching cheating. That system became [Reframe](https://github.com/grouchyseafowl/Reframe), a general-purpose critical theory engine that now shapes the design of everything in this project.

**Stage 4 — Insights.** The system I'd built to detect disengagement patterns became the seed for something more ambitious: qualitative insight generation at scale. The design problem is significant — how do you get a local model running on an instructor's laptop to produce the kind of layered, contextual reading of student work that a human reader would, across 200 submissions per assignment? The answer required both architectural innovation and engineering discipline. The pipeline decomposes the cognitive work into 10+ discrete stages: a full-class reading pass that sees students as a community in conversation before any individual analysis; per-student coding for themes, quotes, and emotional register; a separate wellbeing assessment on raw text; generative observations that describe what the model notices rather than classify what it judges; theme generation; outlier surfacing; and a class-level synthesis narrative. Each stage asks the model a single focused question, grounding the next pass and preventing the hallucination and nuance-flattening that plague multi-step LLM pipelines. The entire pipeline runs on a 12B parameter model (Gemma) on a 16GB MacBook — no cloud, no GPU cluster, no institutional server. An early version of this system detected a patterned uptick in disengagement across all my regular-semester sections in Week 6. In the spring 2026 political climate, I was paying close attention to student wellbeing, and the system identified the pattern as burnout rather than cheating. I gave the class a week off with instructions to focus on self-care and community connection, then assigned readings from the Ethnic Studies literature on collective care.

### What this enables

The engineering makes possible a pedagogical reversal. In the traditional model, assignments are endpoints: students submit, the instructor grades, everyone moves on. Here, the flow runs the other direction — assignments become inputs to a feedback loop. Students submit; the system reads the class as a whole; the instructor sees what students are thinking through, where they're struggling, what themes are emerging across the room; and the next class session or assignment responds to where students actually are. The assignment is a stepping stone for conversation, not a product to be scored. The grade is a byproduct, not the point.

This changes what's possible for both sides. Pressure lifts from students because the process — what they're reaching for, what they're working through — matters more than the output. Pressure lifts from instructors because the system surfaces qualitative patterns across an entire class: we no longer have to approximate a student's intellectual trajectory with a quantitative figure. The teacher becomes a reader of student thinking, not a grader of student products.

These aren't separate concerns. The critical pedagogy — reading students as knowledge creators, refusing deficit framing — requires the engineering that makes qualitative analysis work on a small model. The engineering constraint — running locally on a teacher's own laptop — is itself an accessibility commitment: the instructor with no IT department and no budget gets the same tool as the one with a GPU cluster. And the algorithmic justice work — structurally protecting ESL students, AAVE speakers, neurodivergent writers from false positives — is what makes the tool safe to use at the scale where it's needed. The accessibility, the justice work, the pedagogy, and the engineering are entangled by design. They have to be, because the problems they address are entangled too.

### Coming next

**Agent-assisted inbox.** An agentic Canvas message responder — not just a draft generator, but a command center for instructor communication at scale. The backend (`src/inbox/`) already handles Canvas conversations, SQLite persistence, context assembly with temporal decay, and TF-IDF learning from prior responses. Early use revealed the tool needs to do more than draft replies: it needs to diagnose Canvas issues (unpublished modules, broken submissions), execute bulk admin actions, post course-wide announcements, and group similar messages for systematic response. The design uses a fixed action menu with deterministic execution — the LLM suggests, the instructor approves, Python acts.

**Overnight grading automation.** Scheduled runs that grade while the instructor sleeps — the system pulls new submissions from Canvas overnight, applies Complete/Incomplete grading with configurable thresholds, and has results waiting by morning. Supports macOS launchd, Windows Task Scheduler, and systemd.

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

Built by a community college Ethnic Studies instructor for educators teaching humanities and social sciences, particularly at Hispanic Serving Institutions.
