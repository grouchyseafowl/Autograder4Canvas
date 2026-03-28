# Insights Pipeline — UX Gaps

**Date**: 2026-03-28
**Source**: Codebase audit comparing `src/insights/engine.py` against
`src/gui/panels/insights_panel.py` and `src/gui/panels/settings_panel.py`.
Cross-referenced with `docs/research/experiment_log.md` findings.

**Problem**: Multiple pipeline features developed through research iterations
are functional in the backend but invisible or disconnected in the GUI. The
teacher can't see, configure, or benefit from them.

---

## Issue 1: `insights_teacher_lens` — No UI control

**Severity**: Critical
**Files**: `engine.py:1126`, `submission_coder.py` (observe_student)

The engine reads `insights_teacher_lens` from settings and injects it into
per-student observation prompts as "TEACHER'S OBSERVATION PRIORITIES" and into
the observation synthesis prompt. This is the mechanism for teachers to tell
the pipeline *what kinds of things to notice* when reading student work.

No UI control writes to this setting. The existing "Analysis Lens" text field
in the insights panel writes to a different parameter (`analysis_lens` dict)
which flows into coding and theme generation — a separate stage with separate
prompts. The observation stage gets nothing from the teacher.

**What the teacher loses**: The ability to say "I'm particularly interested in
how students connect course readings to their family histories" and have that
shape what the pipeline notices in each student's work. Without this, the
observation stage uses only its default priorities.

**Fix options**:
- (a) Add a dedicated "Observation Priorities" field in the teacher input
  section, mapped to `insights_teacher_lens`
- (b) Wire the existing "Analysis Lens" field to write BOTH `analysis_lens`
  and `insights_teacher_lens` (simpler, but conflates two stages)
- (c) Rename the existing "Analysis Lens" field to something broader and feed
  it to both parameters

**Recommendation**: Option (c). Teachers shouldn't need to understand pipeline
stage boundaries. One input field, fed to both coding and observation prompts.
The label "What kinds of thinking are you listening for?" already works for
both purposes.

---

## Issue 2: `insights_next_week_topic` — UI field exists but doesn't connect

**Severity**: Critical
**Files**: `insights_panel.py:759`, `engine.py:1468`

The "Next Week" text field exists in the insights panel. When the teacher types
"Next week we're discussing medical racism in the Tuskegee context," that text
gets appended to `teacher_context` (the general context string passed to the
class reading stage). But the engine ALSO reads a separate
`insights_next_week_topic` setting for the `OBSERVATION_SYNTHESIS_FORWARD_LOOKING`
template — the part of the synthesis that says "given what you observed this
week, and knowing next week covers X, here's what to watch for."

Nobody writes to `insights_next_week_topic`. The forward-looking synthesis
section is always empty.

This is particularly frustrating because the teacher *is* providing the
information — they can see the field and type in it — but it routes to general
context instead of the specialized forward-looking prompt where it would
produce the most actionable output.

**What the teacher loses**: The "What This Tells Us for Week X+1" section that
`pipeline_gaps_plan.md` Priority 3 identifies as "among the most actionable"
outputs. The UI asks for the input; the engine has the prompt; the wiring
between them is broken.

**Fix**: In `_start_run()`, pass the "Next Week" field text as a separate
parameter to the engine (or write it to `insights_next_week_topic` in
settings before launching the run). Small fix, high impact.

---

## Issue 3: `insights_deepening_pass` — No UI control

**Severity**: Moderate
**Files**: `engine.py:1179-1181`

The deepening pass (Stage 4b) re-examines students who were flagged for
concerns. It asks the model to name the rhetorical strategy precisely,
reconsider emotional register, and surface theme tags that are in tension
with the concern. This is the mechanism that catches false positives —
it's the pipeline's second look before surfacing a concern to the teacher.

Defaults to `True`. No toggle exists anywhere in the GUI.

**What the teacher loses**: The ability to toggle this off if it's adding
processing time they don't need, or to know it exists when interpreting
how concerns were refined. Also relevant for debugging: if a concern was
demoted, the teacher has no way to know the deepening pass did that.

**Fix**: Add a toggle in Settings > Insights & AI > Advanced, or in the
insights panel's analysis options section. Label it something like
"Re-examine flagged students (refines concern accuracy, adds ~30s per
flagged student)." Default on.

---

## Issue 4: Per-student observations not displayed

**Severity**: Critical
**Files**: `engine.py:1120-1155`, `insights_panel.py` (no references)

The observation architecture is the core research finding (see
`pipeline_gaps_plan.md` Priority 1, validated 32/32). Per-student
observations are 3-4 sentence generative descriptions of each student's
intellectual reach, emotional engagement, and structural power moves. They
replace binary concern flags with teacher-readable narrative.

The engine generates these and stores them on `record.observation`. The
"Student Work" layer in the review view displays coding records (themes,
engagement type, concern flags, sentiment) but contains zero references to
`observation` anywhere in `insights_panel.py`.

**What the teacher loses**: The single most important output of the pipeline.
The whole point of the observation architecture is that teachers see
observations, not flags. Right now they see flags (the old system) because
observations aren't rendered.

**Fix**: Add an observation section to each student card in the "Student Work"
layer. This should be the *first* thing visible on the card — above themes,
above concern chips, above sentiment. It's what the teacher should read. The
structured data (themes, etc.) is supporting detail.

---

## Issue 5: Observation synthesis not displayed

**Severity**: Critical
**Files**: `engine.py:1430-1490`, `insights_panel.py` (no references)

The engine generates a class-level observation synthesis: a narrative built
from all per-student observations, structured as class temperature, thematic
threads, exceptional contributions, students to check in with, and a class
conversation starter. This is stored in the database.

The "Report" layer shows the traditional guided synthesis (4-call architecture:
concerns, highlights, tensions, temperature) but has no reference to
`obs_synthesis` or `observation_synthesis`.

**What the teacher loses**: The class-level narrative that answers "what did my
students say this week?" This is the executive summary the teacher opens
Monday morning. Without it, they get the older structured synthesis which is
less narrative and less actionable.

**Fix**: Display the observation synthesis in the "Report" layer. If both
traditional and observation synthesis exist for a run, the observation
synthesis should be primary (it's the newer, validated architecture). The
traditional synthesis can be secondary or collapsed.

---

## Issue 6: Model family guidance missing from setup

**Severity**: Moderate
**Files**: `insights_wizard.py`, `settings_panel.py`

Research conclusively shows Gemma outperforms Llama at every tested size for
this task: 3/3 concern detection on Gemma 4B/12B/27B vs 1/3 on Llama 8B.
More importantly, Gemma produces qualitatively richer observations — it
recognizes non-standard writing as epistemologically valid rather than
deficient (experiment_log.md, 2026-03-23 findings).

The setup wizard detects hardware but doesn't recommend model families. The
settings panel allows arbitrary model name entry with no guidance. A teacher
could install Llama 8B (the Ollama default) and get a pipeline that misses
relational harms and produces generic theme tags — with no indication that a
different model would perform dramatically better.

**What the teacher loses**: The pipeline's validated performance. A teacher
using Llama 8B gets a qualitatively different (worse) experience than Gemma
12B, and has no way to know this.

**Fix options**:
- Update default models in `llm_backend.py` to Gemma family
- Add recommended model badges/labels in the setup wizard
- Show a brief note in the settings panel: "Gemma models are recommended for
  this pipeline. Tested: gemma-3-12b-it (local, 16GB), gemma-3-27b-it
  (server/cloud)"
- For Ollama users: recommend `gemma3:12b` instead of `llama3.1:8b`

---

## Issue 7: Synthesis-first architecture not explained to teacher

**Severity**: Low-moderate
**Files**: `insights_panel.py` (running view)

The pipeline reads all student work as a class community *before* evaluating
any individual student. This is structurally necessary — tone policing is a
relational harm visible only in context of other students' urgency. Standard
per-student evaluation misses it even on 27B models (experiment_log.md:
296-319).

The running view shows stage progress ("Generating class reading...") but
nothing explains why this happens or what it enables. The teacher sees a
loading bar, not a pedagogical choice.

**What the teacher loses**: Understanding of what makes this tool different
from other AI grading tools. The class-as-community reading is a deliberate
pedagogical stance, not a technical implementation detail. Teachers who
understand it will trust the output more and interpret observations better.

**Fix**: Add a brief tooltip or info line in the running view: "Reading all
submissions together first — some patterns are only visible when student work
is read as a conversation, not in isolation." Or add a sentence to the setup
wizard explaining the approach.

---

## Issue 8: Chatbot handoff not explained in wizard

**Severity**: Low-moderate
**Files**: `insights_wizard.py`, `insights_panel.py` (export exists)

The Tier 2 deployment model (local analysis + paste anonymized patterns into
institutional chatbot for qualitative enhancement) is a key accessibility
feature: it gives teachers without cloud API access the benefit of larger
models through a workflow they already have (their school's AI chatbot).

The review view has an "Export" button and "Copy for Chatbot" button that
work. But the setup wizard doesn't mention this workflow. A teacher who
selects "Keep data on my computer" in the wizard and has no API key may not
discover that they can still get enhanced analysis through manual handoff.

**What the teacher loses**: Access to qualitative enhancement that
experiment_log.md shows produces "Gemini-level" analysis on anonymized data.

**Fix**: In the wizard's "Keep data on my computer" path, add a note:
"After analysis completes, you can copy anonymized patterns to your school's
AI chatbot for deeper qualitative insights. No student names or text leave
your computer." This frames the handoff as a feature of the local-first
design, not a workaround.

---

## Issue 9: `insights_model_tier` — orphaned setting

**Severity**: Low (cleanup)
**Files**: `settings.py`

Defined in settings defaults as `"auto"` but never read by the engine. The
engine receives `model_tier` as a run parameter from the insights panel's
depth toggle. The setting in `settings.py` is dead code.

**Fix**: Either remove from defaults, or use it as a persistent default for
the depth toggle (so the teacher's last-used tier is remembered across
sessions). The latter would be a small UX improvement.

---

## Issue 10: `insights_low_priority` — orphaned setting

**Severity**: Low (cleanup)
**Files**: `settings.py`

Defined in settings defaults as `True` but never read by the engine or GUI.
Presumably intended to control process priority (nice level) during analysis
to keep the computer responsive.

**Fix**: Either remove, or implement — set process nice level when True. The
`insights_throttle_delay` setting partially serves this purpose already (pause
between prompts to keep the system responsive), so this may be redundant.

---

## Issue 11: `insights_cloud_privacy` — orphaned setting

**Severity**: Low (cleanup)
**Files**: `settings.py`

Defined in settings defaults as `""` but never read. Likely intended to store
whether the teacher has acknowledged the FERPA implications of cloud API use,
or to record their institution's privacy agreement status.

**Fix**: Either remove, or wire it into the cloud configuration flow. When a
teacher enters cloud API credentials, prompt them to acknowledge the privacy
implications and store the acknowledgment here. This would strengthen the
FERPA compliance posture — right now the settings panel shows a FERPA warning
label but doesn't gate cloud use on acknowledgment.

---

## Issue 12: AI-flagged student handling not teacher-configurable

**Severity**: Moderate-high
**Files**: `engine.py:441-477`, `class_reader.py:426-434`, `submission_coder.py:707-766`

The AIC pre-scan runs automatically before the class reading. Students flagged
as likely AI-generated (elevated/high concern or smoking gun) are:
- Annotated in the class reading with: "[NOTE: This submission shows signals
  consistent with AI generation. Read with awareness that this may not
  represent the student's authentic voice. Do not let its polish set the
  standard against which other voices are measured.]"
- Still observed, but observations are prefixed with: "[NOTE: This submission
  was flagged as likely AI-generated by the engagement analysis system. The
  observation below describes what was submitted, regardless of authorship.]"

Students are NOT excluded — they're annotated. This is a defensible default,
but the teacher has no control over or visibility into the policy, and AI
policies vary enormously across assignments and institutions:
- Some teachers prohibit AI entirely
- Some allow AI for brainstorming but not final drafts
- Some assignments explicitly encourage AI collaboration
- Some students use AI tools as disability accommodations

The current one-size annotation doesn't distinguish these cases.

**What the teacher loses**: Agency over how AI-flagged students are handled.
A teacher who designed an AI-collaborative assignment gets every student
annotated with a warning. A teacher who prohibits AI gets a soft annotation
when they might want the submission excluded from class context entirely.

**Fix — two layers**:

*Layer 1 (per-assignment AI policy selector)*: Add to the analysis setup
view, alongside the existing toggles. Options:
- "AI use not expected" (default — current annotation behavior)
- "AI prohibited" (exclude flagged subs from class reading context entirely;
  observation still runs but more prominent flag)
- "AI allowed / encouraged" (suppress AI annotations; treat all submissions
  as authentic voice)

*Layer 2 (future — "how I used AI" recognition)*: Some teachers ask students
to disclose AI use. The pipeline could surface self-reported AI use
statements (e.g., "I used ChatGPT to help me outline..."). This is worth
designing carefully — fuzzy keyword matching could work but risks students
falling through the cracks if they don't follow instructions precisely. A
lightweight approach: if the teacher provides a label phrase (e.g., "AI
Disclosure:"), the pipeline looks for it. If absent, no flag — don't penalize
students for not following a format. This is a future feature, not immediate.

---

## Issue 13: No runtime estimate shown before or during analysis

**Severity**: Moderate
**Files**: `insights_panel.py:4167-4186`

The setup summary shows "4 assignments across 2 courses · ~32 students ·
local 12B model" but does NOT estimate how long the run will take. The
running view shows a progress bar and stage labels, but no estimated time
remaining or total. Teachers launching their first run may expect results in
minutes, not hours.

**What the teacher loses**: Ability to plan. A teacher who starts a run at
3pm expecting 15-minute results will close the app and lose progress (or
think it's frozen). A teacher who knows it'll take a while will start it
before leaving for the day.

**Actual measured runtimes** (Apple Silicon, 16 GB RAM, MLX backend):

| Model | Students | Total | Per-student | Notes |
|-------|----------|-------|-------------|-------|
| Gemma 12B 4-bit MLX | 7 | ~13 min | ~2 min | Synthesis-first prototype |
| Qwen 7B 4-bit MLX | 32 | 64 min | 119s | Full pipeline |
| Llama 8B 4-bit MLX | 32 | 79 min | 147s | Full pipeline |
| Gemma 12B 4-bit MLX | 32 | 11 hours | — | Theme generation timed out on all groups (outlier) |
| Gemma 12B (core stages only) | 32 | ~2h | ~104s coding + ~113s concerns | Class reading 8 min, themes excluded |

Per-student coding averages ~104s on 12B MLX. Reading-first two-pass coding
is ~2 min/student. These numbers are from a 2020 M1 MacBook Air 16 GB — newer
hardware will be faster.

**Fix**: Add an estimate to the setup summary based on tier and student count.
Use measured data, not formulas. Display as e.g. "Estimated time: ~2 hours
(based on Apple Silicon with 16 GB RAM running MLX)." Note that estimates are
approximate — actual time depends on submission length, hardware, and whether
other apps are running. In the running view, show elapsed time and stage
progress rather than a countdown (countdowns that are wrong erode trust more
than elapsed timers).

---

## Issue 14: Teacher concern calibration not visible

**Severity**: Low-moderate
**Files**: `teacher_profile.py:125-165`, `teacher_profile.py:325-345`

The teacher profile's `concern_sensitivity` learn loop works: when a teacher
acknowledges or dismisses a concern, sensitivity adjusts by ±0.1, and the
`get_concern_sensitivity_fragment()` injects the calibration state into future
prompts so the LLM knows which concern patterns the teacher has validated.
Protected wellbeing concerns have a floor of 0.3 — they can't be fully
suppressed.

But the teacher has no visibility into their own calibration state. After
dismissing several tone-policing flags across runs, a teacher can't see that
their sensitivity for that pattern is now 0.2 (effectively suppressed) vs.
0.8 for wellbeing signals (elevated). They also can't see the floor
protection — that wellbeing signals will always surface regardless of how
many times they dismiss them.

**What the teacher loses**: Understanding of how their past actions shape
future results. If a new semester starts and concern patterns shift, the
teacher has no way to know their profile is carrying calibration from last
semester (note: `export_template()` correctly strips `concern_sensitivity`,
but only if the teacher explicitly creates a new template).

**Fix**: Add a "Your Calibration" section to the course profile view. Show
each concern pattern with its current sensitivity level (bar or number).
Highlight protected patterns with a note: "Wellbeing signals always surface
(floor: 0.3)." Add a "Reset calibration" button that zeroes
`concern_sensitivity` without affecting other profile settings.

---

## Issue 15: Enhancement tier UX

**Severity**: Critical
**Files**: `synthesizer.py:686-796`, `insights_wizard.py:1051-1149`,
`insights_panel.py:3324-3336`, `settings_panel.py`

### What enhancement does

After the local pipeline runs (Gemma 12B on the teacher's laptop), it
produces per-student observations and a class synthesis. The enhancement tier
sends *only anonymized class-level patterns* (no student names, no quotes, no
identifiable data) to a cloud model for richer pedagogical analysis. The
teacher gets back a narrative that adds: deeper structural framing, productive
tension analysis, language justice recognition, and pedagogical significance
that the 12B model can't fully produce. FERPA validation
(`_validate_no_student_data()`) blocks any payload containing student names or
IDs.

The enhancement should feel like a second opinion from a more experienced
colleague, not a replacement for the local analysis. The local synthesis has
the student-level detail (names, observations, check-ins). The enhancement
has the class-level pedagogical framing. Both are visible together.

### What currently works in code

- Enhancement trigger in `synthesizer.py` (runs after guided synthesis if
  cloud credentials are configured)
- FERPA-safe anonymized payload construction
- Display in review view ("DEEPER ANALYSIS" section)
- Graceful degradation (if cloud fails, local synthesis still shows)
- Wizard has a toggle, API key field, and model override

### Enhancement is separate from institutional cloud API

Important distinction: the enhancement tier is specifically for the local 12B
pipeline. It sends anonymized patterns to a cloud model for qualitative
enrichment. This is different from the "institutional cloud API" option, where
a teacher with an institutional privacy agreement (DPA) runs the *entire
pipeline* through a cloud model (e.g., institutional Claude or GPT-4). That's
a separate deployment tier, not an enhancement layer.

### UX: Four options, framed by what the teacher values

The wizard should present these choices in teacher language, not model names.
No model names, parameter counts, architecture types, or benchmark numbers
in the teacher-facing UX.

**Option 1: "Keep everything on my computer"** (Tier 1, local only)
No cloud call. The local 12B synthesis is the final output. For teachers who
can't or won't send any data externally, or who are in restrictive
institutional environments.

**Option 2: "Enhance with a free service"** (Tier 2 — Gemma 27B via
OpenRouter)
One button. Sends anonymized patterns to Google's free Gemma 27B. Returns
richer analysis in ~20 seconds. Teacher sees the anonymized prompt before it
sends and can cancel.

Trade-offs to surface (brief, non-technical):
- "This sends a summary of class patterns (no student names or writing) to
  Google's servers"
- "Free, but Google may use this data to improve their products"
- "Works most of the time, but occasionally unavailable"

Requires a free OpenRouter account. The wizard should walk the teacher through
creating one: link to signup, where to find the API key, paste it here.

**Option 3: "Enhance with a privacy-focused service"** (Tier 2 alt — Mistral
Small via Venice)
Same flow, different provider. Venice advertises no-logging,
no-training-on-inputs. Requires the teacher to have an OpenRouter account
with a small balance (~$0.01 per use).

Trade-offs to surface:
- "This sends a summary of class patterns to Venice.ai, a privacy-first
  provider that doesn't log or train on your data"
- "Costs about 1 cent per use"
- "More private than Option 2"

**Option 4: "Paste into my school's AI tool"** (Tier 2 browser handoff)
The system generates an anonymized prompt the teacher can copy-paste into
whatever chatbot their school provides (Google Gemini, Microsoft Copilot,
institutional Claude, etc.). No API, no account, no cost. The teacher
controls where the data goes. This is FERPA-compliant because only anonymized
class patterns leave the machine, and the teacher chooses the destination.

This should always be visible as an option, not hidden behind settings. For
teachers at schools that already have an approved AI tool, this is the path
of least resistance and maximum institutional alignment. It's also the most
future-proof — when better models appear, the teacher just pastes into a
different chatbot. No code change needed.

### Data flow the UX should make visible

```
Teacher clicks "Enhance"
    ↓
System shows anonymized prompt preview
    ↓
Teacher reviews — "This is what will be sent. No student names."
    ↓
Teacher confirms (or cancels, or copies to clipboard for Option 4)
    ↓
API call to selected provider (free / privacy / paste-your-own)
    ↓
Response appears as "Enhanced Analysis" panel alongside local synthesis
    ↓
Both visible — teacher sees local analysis AND enhancement together
```

### Model selection rationale (internal — NOT shown to teachers)

Enhancement was tested against 7 models on 2026-03-28. Two were selected:

| Default | Model | Provider | Cost | Why chosen |
|---------|-------|----------|------|------------|
| Yes | Gemma 3 27B | OpenRouter (free) | $0.00 | Best overall quality + accessibility, free, reliable |
| Privacy alt | Mistral Small 3.1 24B | Venice via OpenRouter | ~$0.01 | No-logging provider, strongest on comprehensiveness, explicit anti-spotlighting |

Other models tested had specific strengths but aren't defaults:
- StepFun 196B: strongest on questioning assessment norms ("the evaluation
  system is the problem, not the student") — valuable for critical pedagogy
  but provider less familiar to US educators, privacy posture less clear
- Nemotron 120B: sharpest analytical precision (content/form axis for
  structural mechanisms) — valuable for teachers planning differentiated
  responses but not enough edge over Gemma to justify as default

Model performance will change with updates. The system defaults to the tested
models but should document: "Enhancement tested 2026-03-28 against Gemma 3
27B and Mistral Small 3.1 24B. Model performance may change with updates."

Technical users can override the model in advanced settings or use a paid API.

### What's missing in the current UX

1. **API key setup walkthrough** — The wizard needs to guide the teacher
   through creating an OpenRouter account, finding their API key, and pasting
   it. Step-by-step with screenshots or a link to a setup guide. Teachers
   shouldn't need to understand what an API key is — just "create an account
   here, copy this code, paste it here."

2. **Prompt preview before sending** — The teacher should see the anonymized
   payload before it leaves the machine and be able to cancel. This is
   essential for trust and FERPA compliance transparency. Currently the
   enhancement runs automatically with no preview.

3. **Per-run toggle** — Enhancement runs automatically if configured. The
   teacher can't skip it on a specific run (for speed, cost, or when the
   free tier is down). Add a toggle to the run setup view.

4. **Silent failure messaging** — If the cloud API fails (rate limit, auth
   error, model unavailable — free tier has volatile availability), the
   teacher gets local synthesis with no indication enhancement was attempted
   and failed. Show: "Cloud enhancement unavailable — showing local analysis
   only. You can retry or paste the prompt into your school's AI tool."

5. **Enhancement not offered in the "keep data local" wizard path** — A
   teacher who selects "Keep data on my computer" never learns that
   enhancement exists and is privacy-safe (only anonymized patterns leave
   the machine). It should be offered as an optional add-on in ALL wizard
   paths, since no student data leaves the machine.

6. **Browser handoff not presented as a first-class option** — The "Copy for
   Chatbot" button exists in the review view but isn't presented as an
   enhancement path during setup. It should appear alongside Options 2 and 3,
   framed as: "No account needed — paste into whatever AI tool your school
   uses."

7. **Enhancement status in settings panel** — The wizard configures
   enhancement, but the settings panel doesn't show whether it's active or
   which provider is selected. A teacher who configured it weeks ago can't
   tell from settings whether it's on.

---

## Issue 16: Wellbeing classification (4-axis) needs UX

**Severity**: Critical (pending implementation)
**Files**: `concern_detector.py`, `insights_panel.py` (review view)

Testing confirms the 4-axis wellbeing classification schema works and is
being refined before implementation:

| Classification | What it means | Teacher response |
|----------------|---------------|------------------|
| **CRISIS** | Active danger: ICE stress, domestic violence, housing insecurity, grief, food insecurity | Counselor referral, mandated reporting consideration, immediate structural support |
| **BURNOUT** | Depletion: exhaustion from assigned work, caregiving load, running low on steam | Flexible deadlines, reduced load, check-in about workload — NOT counselor referral |
| **ENGAGED** | Drawing on community knowledge / lived experience that looks like distress to a naive classifier | No intervention needed — this is intellectual work. Acknowledge the asset. |
| **NONE** | No wellbeing signal detected | Standard observation |

The 4-axis schema solves a critical false-positive pattern: students writing
analytically about topics from their communities (ICE policy, housing, police
violence) were misclassified as BURNOUT under the old 3-axis schema
(BURNOUT/CRISIS/NONE) because the model had no category for "engaged via
community knowledge." The ENGAGED axis gives the model a way to say "this
student is doing intellectual work that draws on lived experience — this is
an asset, not a distress signal."

**What the UX needs**:

1. **Distinct visual treatment per classification** — CRISIS and BURNOUT
   should look different in the review view (different colors, icons,
   suggested actions). ENGAGED should not look like a concern at all — it
   should be celebrated as a strength.

2. **Suggested teacher actions per type** — CRISIS: "Consider connecting
   this student with your school counselor." BURNOUT: "Consider flexible
   timing or a check-in about workload." ENGAGED: "This student is drawing
   on community knowledge — consider creating space for this in class
   discussion (without singling them out)."

3. **Confidence scores visible** — Testing shows genuine signals at 0.8-0.95,
   false positives at 0.6. Teachers should see confidence levels to
   calibrate trust: "BURNOUT (high confidence)" vs "BURNOUT (moderate —
   review suggested)."

4. **The false-positive pattern explained** — Brief help text: "Students
   writing about topics that affect their communities may show linguistic
   patterns similar to personal distress. This system distinguishes
   analytical engagement from burnout or crisis."

**Status**: Currently in test scripts only (Test L), not yet in production
pipeline. Implementation expected soon. UX design can proceed in parallel.

---

## Implementation priority

**Do first** (highest teacher impact, unblocks the observation architecture):
- Issue 4: Display per-student observations in Student Work layer
- Issue 5: Display observation synthesis in Report layer
- Issue 2: Wire "Next Week" field to `insights_next_week_topic`
- Issue 15: Enhancement tier UX (API key walkthrough, prompt preview,
  browser handoff as first-class option)

**Do second** (completes the teacher input → pipeline flow):
- Issue 1: Wire "Analysis Lens" to also feed observation stage
- Issue 3: Add deepening pass toggle
- Issue 13: Runtime estimate (use measured data, not formulas)
- Issue 12: AI policy selector per assignment
- Issue 16: Wellbeing classification UX (ready for design now, implement
  when 4-axis pipeline code lands)

**Do third** (setup & transparency):
- Issue 6: Model family guidance
- Issue 7: Synthesis-first explanation
- Issue 8: Chatbot handoff in wizard (partially covered by Issue 15 Option 4)
- Issue 14: Concern calibration visibility

**Cleanup when convenient**:
- Issues 9-11: Orphaned settings
