# Demo Mode Expansion: Insights + Short Sub Review + Tutorial Guide

> Stable reference. Approved 2026-03-20. Implementation deferred until after DAIGT data collection + system testing.

## Context

The demo has grading, AIC, and student trajectories but no Insights data and no guided narrative. The three acts in `demo_data.py` comments are unrealized. This work:

- Assembles a **hybrid demo corpus** from DAIGT real student essays + hand-crafted key students + deliberately AI-generated cheating submissions
- Generates **pre-baked Insights results** for two classes (Ethnic Studies + Biology) by running InsightsEngine on that corpus
- Integrates **Short Sub Review** into the demo run (Jordan Kim's 97-word post reviewed and escalated)
- Builds a **floating tutorial guide** (13 scenes across 3 acts)
- Renames **"Outliers" → "Charting New Ground"** with anti-spotlighting design
- Adds a **timing banner** communicating production processing times
- Showcases **critical pedagogy** — microaggression detection, colorblind claim flagging, protection of legitimate anger

---

## Phase 0: Demo Corpus Assembly + Data Generation

### Step 1: Source and filter DAIGT data

**Script: `scripts/assemble_demo_corpus.py`**

- Downloads/filters real student essays from the DAIGT dataset
- Filters for appropriate length (80-350 words), reflective/persuasive register
- Outputs `data/demo_source/daigt_filtered.json` — **kept separate** from created data (also used for system verification/calibration)

### Step 2: Analyze DAIGT data with our system

Run AIC + QuickAnalyzer on filtered DAIGT essays to see what patterns emerge naturally. Select essays that work for each student role.

### Step 3: Assemble the demo corpus

Second stage of `scripts/assemble_demo_corpus.py`:

| Student | Source | Why |
|---------|--------|-----|
| Maria Ndiaye (esl) | Hand-craft | Need transnational family voice with non-native English patterns |
| Jordan Kim (burnout) | Hand-craft | Exactly ~97 words, genuine but fatigued, 2am submission |
| Alex Hernandez (smoking_gun) | AI-generated with raw HTML | He cheated — the submission IS AI output |
| Tyler Nguyen / Jaylen Carter | AI-generated | Correct but hollow — zero personal connections |
| 4 exhaustion_spike students | Adapt from DAIGT | Short-ish (100-140 words), genuine but clearly not their normal output |
| Essentializer (~S015) | Hand-craft | Well-intentioned essentializing: "Latino families always value community." Positive sentiment, problematic framing. Concern detector must catch this. |
| Colorblind Claimant (~S018) | Hand-craft | "I don't see color, I just see people" embedded in a thoughtful post. Must be flagged. |
| Righteous Anger (~S022) | Hand-craft | Furious about redlining/systemic violence. Must NOT be flagged — this is the critical pedagogy showcase. |
| Tone Policer (~S025) | Hand-craft | "We should keep this respectful and not get too emotional." Must be flagged for tone policing. |
| Premise Challenger (~S020) | Hand-craft | Challenges the assignment's intersectionality framing from a class-based lens. Appears in "Charting New Ground." |
| ~15 normal students | Adapt from DAIGT | Real student voice; change topic references to match assignment prompts |

Output: `data/demo_corpus/ethnic_studies.json` and `data/demo_corpus/biology.json`

### Step 4: Generate Insights results

**Script: `scripts/generate_demo_insights.py`**

1. Constructs `PreprocessedSubmission` objects from the assembled corpus
2. Calls InsightsEngine pipeline: QuickAnalyzer → SubmissionCoder → ConcernDetector → ThemeGenerator → Synthesizer → FeedbackDrafter
3. Uses Sonnet via `ANTHROPIC_API_KEY` for high-quality codings
4. **Times the run** — record wall-clock time for both Sonnet and local 8B. Use real numbers in the demo guide.
5. Outputs to `src/demo_assets/insights_ethnic_studies.json` and `src/demo_assets/insights_biology.json`

### Step 5: Add Biology course to demo data

Add to `_HS_SPRING_COURSES` in `src/demo_data.py`:
```python
{"id": 90005, "name": "Biology, Period 6",
 "course_code": "BIO-P6", "workflow_state": "available", "course_format": "on_campus"}
```
CC: `{"id": 50005, "name": "BIOL 101 - Intro to Biology", ...}`

Add assignment group + lab reflection assignment to `_HS_ASSIGNMENTS[90005]`.

---

## Demo Guide Widget

### New file: `src/gui/widgets/demo_guide.py`

**`DemoGuide(QFrame)`** — floating amber narration widget, bottom-right of `centralWidget()`. 320px wide. Non-blocking.

**Positioning:** Installs itself as `eventFilter` on parent. In `eventFilter`, checks for `QEvent.Resize` and calls `_reposition()`. Implementation:
```python
def __init__(self, parent):
    super().__init__(parent)
    parent.installEventFilter(self)
    ...

def eventFilter(self, obj, event):
    if obj is self.parent() and event.type() == QEvent.Resize:
        self._reposition()
    return super().eventFilter(obj, event)

def _reposition(self):
    p = self.parent()
    if p:
        self.move(p.width() - self.width() - 12, p.height() - self.height() - 12)
```

**Visual:** `QFrame#demoGuide` with:
- `border-top: 2px solid {BORDER_AMBER}`, dark background (PANE_BG_GRADIENT), `border-radius: 8px`
- Act label: dim amber, 10px, bold, letter-spaced
- Title: hot amber, 13px bold
- Body: mid amber, 11px, word-wrapped
- Hint: italic amber, 10px
- Nav: `< Back` | `4 / 13` | `Next >` — small amber buttons
- `Hide Guide` flat link → hides frame, shows `▶ Demo Guide` restore button at parent bottom-right

**Signals:** `scene_changed(int)` — for optional auto-advance.

**Methods:** `advance_if_at(scene_idx)` — advance by 1 only if currently at that index.

---

## Demo Script (13 scenes)

### ACT 1: THE PRACTICE

**Scene 1 — "A different kind of grading."**
> Complete/incomplete grading treats assignments as jumping-off points, not final products. The word count isn't a hoop — it's a proxy for good-faith engagement. Students write to engage. Teachers read to understand.
>
> The autograder handles the counting. The AIC flags anything that doesn't look like the student's own work. And for submissions below the word count, Short Sub Review gives a second look.
>
> *→ Select 'AP US History, Period 2' from the sidebar.*

**Scene 2 — "The safety net."**
> Short Sub Review is on. When a submission falls below the word count, the LLM reads it — not to judge quality, but to check for engagement. It can only upgrade or escalate. Never condemn.
>
> On a local device, each review takes roughly [TBD] seconds. Some teachers set the word count deliberately high and use the LLM as a first-pass engagement filter they then review themselves.
>
> *→ Toggle Short Sub Review on. Select the Week 6 discussion. Click Run.*

**Scene 3 — "Here's what happened."**
> [N] complete. [M] incomplete. One submission tripped a smoking gun. And Jordan Kim — 97 words, submitted at 2am — was reviewed by Short Sub Review. The LLM found a genuine connection to the reading. Verdict: TEACHER_REVIEW. Not failed. Not dismissed. Flagged for your attention.
>
> *→ Click Review in the nav bar.*

### ACT 2: THREE SIGNALS

**Scene 4 — "The smoking gun."**
> Alex Hernandez's submission contains raw HTML — angle brackets, div tags, the formatting bones of a chatbot response pasted without cleaning. This isn't algorithmic suspicion. It's physical evidence. The system shows exactly what it found and provides conversation starters — not accusations.
>
> The teacher decides what this means and how to approach the conversation.
>
> *→ In Academic Integrity, click Alex Hernandez.*

**Scene 5 — "The flag that wasn't one."**
> Maria Ndiaye's integrity score is elevated. But look at the context: the system detected second-language writing patterns — article usage, tense shifts, preposition choices that AI models virtually never produce. These are what careful English looks like when you think in another language first.
>
> The system reduced her suspicion score by 40%. She's not flagged. She's protected.
>
> *→ Click Maria Ndiaye in the scatter plot.*

**Scene 6 — "The trajectory."**
> Jordan Kim's Short Sub Review found real engagement in 97 words — he connected the reading to something from his own life. But the trajectory tells a bigger story. Four weeks of 200+ word posts. Two weeks of decline. This week: 97 words at 2am.
>
> The system surfaces this so you can check in. That's a teaching decision, not a grading one.
>
> *→ Click Jordan Kim. Scroll to the trajectory chart.*

**Scene 7 — "It's not just Jordan."**
> Look at the scatter plot. Four other students show a first-time pattern change at Week 6. Their earlier work was clean. This week, quality dropped and AI markers spiked — not because they became dishonest, but because something shifted.
>
> When AI use appears as a cluster at the same point in the semester, it's a systemic signal. End-of-term exhaustion, competing deadlines, burnout. The system surfaces the pattern so you can address the cause, not the symptom.
>
> *→ Notice the cluster in the scatter plot. Click any of them to see the same trajectory shape.*

### ACT 3: CLASS VOICE

**Scene 8 — "What did your class actually say?"**
> The Insights tab runs a different kind of analysis. Not integrity signals — themes. Voices. What your students were actually thinking when they wrote about intersectionality.
>
> This analysis takes time. On a local device, expect [TBD — use measured time] for a class of 30. With an institutional API, [TBD]. Either way, it runs unattended — start it before you leave and it's waiting in the morning.
>
> *→ Click the 'Insights' segment in the Review tab.*

**Scene 9 — "Three themes. One productive tension."**
> [N] students wrote about identity as something plural and irreducible. [N] connected categories to structural power. [N] said the framework gave language to something they already knew but couldn't name.
>
> And running through the class is a real intellectual tension: some students think intersectionality is about personal recognition, others think it's a tool for systemic analysis. Most lean toward the individualizing frame — that's typical. The disagreement maps onto a genuine debate in the field. It's your next discussion.
>
> *→ Click Themes in the layer tabs.*

**Scene 10 — "What the system catches that a grade can't."**
> The system flags essentializing language — "all X people," "those people always" — even when wrapped in positive sentiment. It flags colorblind claims. It flags tone policing.
>
> It does NOT flag anger about injustice. A student who writes "this makes me furious" about historical violence is engaging with the material. The system knows the difference — and the demo walks you through why that distinction matters.
>
> *→ Look at flagged concerns. Notice what IS and ISN'T flagged.*

**Scene 11 — "Charting new ground."**
> Several students took the discussion somewhere the themes didn't capture. One connected intersectionality to transnational family experience — a framing absent from the reading. Another challenged the assignment's premises.
>
> The system doesn't recommend singling these students out. Instead, it suggests ways to create space — discussion prompts, small group structures, reading pairings — so these perspectives can enter the conversation without putting anyone on the spot.
>
> *→ Click 'Charting New Ground' in the layer tabs.*

**Scene 12 — "Same tool. Different class."**
> The analysis also ran on your Biology class — the cell respiration lab reflection. Completely different register. Completely different patterns. The Themes layer shows who connected data to prior readings and who just reported numbers. Different concerns surface here — disengagement from scientific reasoning looks different from identity politics.
>
> The tool adapts to the subject. You set the lens.
>
> *→ Use the course selector to switch to Biology.*

**Scene 13 — "This is the whole picture."**
> You automated the completion grading. You caught a cheating case with physical evidence. You identified a student burning out before he disappeared. You saw a class-wide exhaustion pattern. You heard what your students were actually thinking. You found contributions that chart new ground. And you know which students need a check-in — and which need to be left alone.
>
> The autograder didn't do any of that teaching. It cleared the noise so your judgment could land where it matters.
>
> *→ That's the demo. Questions?*

---

## Implementation: Files to Create

### `scripts/assemble_demo_corpus.py`
Data curation script. See Phase 0 above.

### `scripts/generate_demo_insights.py`
Runs InsightsEngine on the assembled corpus. Outputs baked JSON to `src/demo_assets/`.

### `src/demo_assets/insights_ethnic_studies.json` and `insights_biology.json`

Generated by script, committed to repo. Structure:
```json
{
  "run": {
    "run_id": "demo-insights-run-eth-studies-000000000001",
    "course_id": "90003",
    "course_name": "Ethnic Studies (11), Period 3",
    "assignment_id": "113002",
    "assignment_name": "Week 6 Discussion: Intersectionality in Practice",
    "started_at": "2026-03-08T16:45:00+00:00",
    "completed_at": "2026-03-08T17:12:00+00:00",
    "model_tier": "lightweight",
    "model_name": "demo-data",
    "total_submissions": 29,
    "stages_completed": ["data_fetch","preprocessing","quick_analysis","coding","concerns","themes","outliers","synthesis"],
    "pipeline_confidence": {"overall": 0.82},
    "teacher_context": "...",
    "analysis_lens_config": {"lens": "equity_attention"},
    "quick_analysis": "<JSON string — QuickAnalysisResult>"
  },
  "codings": [
    {
      "run_id": "...",
      "student_id": "S001",
      "student_name": "Maria Ndiaye",
      "coding_record": { "...SubmissionCodingRecord as dict, NOT JSON string..." : "..." },
      "submission_text": "In my family we always talked about...",
      "teacher_edited": 0,
      "teacher_edits": null,
      "teacher_notes": null
    }
  ],
  "themes": {
    "theme_set": "<JSON string — themes list with contradictions>",
    "outlier_report": "<JSON string — charting-new-ground entries>",
    "synthesis_report": "<JSON string with 'sections' dict — 9 keys: what_students_said, emergent_themes, tensions_and_contradictions, surprises, focus_areas, concerns, divergent_approaches, looking_ahead, students_to_check_in_with>"
  },
  "feedback": [
    {
      "run_id": "...",
      "student_id": "S001",
      "student_name": "Maria Ndiaye",
      "draft_text": "Maria — your post stood out for...",
      "approved_text": null,
      "status": "pending",
      "confidence": 0.91,
      "posted_at": null
    }
  ]
}
```

### `src/gui/widgets/demo_guide.py`
`DemoGuide(QFrame)` — see Widget section above. Contains `GUIDE_SCRIPT` list (13 scene dicts).

---

## Implementation: Files to Modify

### `src/demo_data.py`

**Add constants:**
```python
DEMO_INSIGHTS_RUN_ID_ES  = "demo-insights-run-eth-studies-000000000001"
DEMO_INSIGHTS_RUN_ID_BIO = "demo-insights-run-bio-lab-0000000000001"
```

**Add Biology course** to `_HS_SPRING_COURSES` (id 90005) and `_HS_ASSIGNMENTS[90005]`.

**Modify `simulate_grading_run()`** — after the student loop, check for Jordan Kim in the results. Add pre-baked SSR review to a new `"short_sub_reviews"` dict in the return value:
```python
results["short_sub_reviews"] = {
    f"{assignment['id']}:{student['id']}": {
        "student_name": "Jordan Kim",
        "submission_text": "...(his 97-word submission)...",
        "assignment_id": assignment["id"],
        "assignment_name": assignment["name"],
        "course_id": course_id,
        "course_name": course_name,
        "user_id": student["id"],
        "review": {
            "verdict": "TEACHER_REVIEW",
            "brevity_category": "partial_attempt",
            "rationale": "Submission shows real engagement...",
            "engagement_evidence": ["connected the reading to a specific personal moment"],
            "confidence": 0.48,
            "teacher_note": "Consider a low-stakes check-in...",
            "bias_warning": None,
            "thread_context": None,
        }
    }
}
```
Also add log line: `"  Jordan Kim  [97 words]  SHORT_SUB_REVIEW → TEACHER_REVIEW"`

### `src/automation/demo_store.py`

**Add `DemoInsightsStore` class** after `DemoRunStore`. Full implementation including:
- JSON loading from `src/demo_assets/` via `Path(__file__).resolve().parent.parent / "demo_assets"`
- `get_run()`, `get_runs()`, `get_completed_runs()`, `get_codings()`, `get_coding_record()`, `get_themes()`, `get_feedback()`, `get_approved_feedback()`
- In-memory override dicts for `update_coding_tags()` and `update_feedback_status()`
- All other write methods as silent no-ops
- See plan file for full method signatures

### `src/gui/main_window.py`

1. Split InsightsStore creation — demo uses `DemoInsightsStore`, non-demo uses `InsightsStore`
2. Create DemoGuide after `self._stack.setCurrentIndex(0)` when in demo mode
3. Add `resizeEvent` override as backup for DemoGuide repositioning

### `src/gui/panels/insights_panel.py`

1. Rename "Outliers" → "Charting New Ground" (3 user-visible strings; internal key stays `"outliers"`)
2. Demo pre-load: `QTimer.singleShot(0, lambda: self.show_review(DEMO_INSIGHTS_RUN_ID_ES))`
3. Timing banner at top of review view (visible only in demo mode)
4. Guard `_on_resume_run()` — return early in demo mode

### `src/gui/workers.py`

Add `short_sub_reviews_ready = Signal(dict)` to `DemoRunWorker`. Emit it from `run()` after `simulate_grading_run()` returns.

### `src/gui/dialogs/run_dialog.py`

Pass `demo_mode=self._demo_mode` to `ShortSubReviewDialog` constructor.

### `src/gui/dialogs/short_sub_review_dialog.py`

1. Add `demo_mode: bool = False` parameter to constructor
2. In `_on_accept()` and `_on_post_all_high_confidence()`: skip Canvas POST in demo mode, always succeed

### `src/insights/prompts.py`

Add anti-spotlighting instruction to synthesis and outlier prompt sections:
- Do NOT recommend inviting specific students to share/present
- Recommend STRUCTURAL opportunities (discussion prompts, small groups, reading pairings, writing prompts)
- Frame recommendations around what the TEACHER can do with the CLASS

---

## Key Design Principles

1. **No unsourced claims.** Time the actual run. Use real numbers.
2. **Anti-spotlighting.** Never recommend singling out a student. Create structural opportunities.
3. **Complete/incomplete is a pedagogy.** Engagement-focused. Assignments as jumping-off points.
4. **AI use as symptom.** Cluster = systemic signal, not individual dishonesty.
5. **Critical pedagogy is a feature.** Scene 10 is a selling point.
6. **Source data ≠ demo data.** DAIGT in `data/demo_source/`. Created data in `data/demo_corpus/`. Baked results in `src/demo_assets/`.
7. **Build on existing demo mechanics.** DemoRunStore, DemoRunWorker, demo courses, setup dialog buttons — all preserved and extended.

---

## Verification

**Data pipeline:**
1. `scripts/assemble_demo_corpus.py` produces corpus with expected student count/patterns
2. `scripts/generate_demo_insights.py` runs successfully, times the run, outputs valid JSON
3. JSON files contain all 9 synthesis section keys; `stages_completed` is a list; `coding_record` is a dict

**Demo guide:**
4. DemoGuide appears bottom-right; 13 scenes navigate; repositions on resize
5. Dismiss/restore works

**Run + Short Sub Review:**
6. `simulate_grading_run()` returns `short_sub_reviews` dict for Jordan Kim
7. DemoRunWorker emits `short_sub_reviews_ready` signal
8. RunDialog shows "Review Short Submissions (1)" button
9. ShortSubReviewDialog opens with Jordan's review; Accept works (no API call in demo)

**Insights:**
10. Review > Insights pre-loads Ethnic Studies run in Results state
11. Timing banner visible; "Charting New Ground" tab label present; "Outliers" label gone
12. All 7 layers populate: Patterns, Student Work, Themes, Charting New Ground, Report, Feedback, Semester
13. Concern flags: essentializing/colorblind flagged; anger about injustice NOT flagged
14. "Charting New Ground" shows multiple students with structural recommendations (no spotlighting)
15. Biology run loads when switching course selector

**Integration:**
16. Tag edits persist in DemoInsightsStore overrides
17. Resume button does not launch workers
18. All write methods are silent no-ops
