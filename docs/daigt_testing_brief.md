# DAIGT Data Collection + System Testing Brief

> Context for a new conversation/agent. This brief covers everything needed to:
> 1. Obtain and filter the DAIGT dataset
> 2. Run it through AIC and InsightsEngine to verify system behavior
> 3. Select essays for the demo corpus
> 4. Assemble the final demo corpus (real + hand-crafted + AI-generated)
> 5. Generate baked Insights JSON for the demo

## What this feeds into

See `docs/demo_expansion_plan.md` for the full demo expansion plan. This work produces the **data layer** that the demo UI consumes. The outputs are:
- `src/demo_assets/insights_ethnic_studies.json`
- `src/demo_assets/insights_biology.json`
- Timing measurements for the demo guide's `[TBD]` fields

---

## Step 1: Obtain and Filter DAIGT Data

### The Dataset

**DAIGT (Detect AI-Generated Text)** — Kaggle competition dataset. Contains real student essays (from the ASAP/ETS corpus) and AI-generated essays. The real student essays are what we want.

- Kaggle: `thedrcat/daigt-v2-train-dataset` (or search "DAIGT")
- The dataset has a `label` column: `0` = human-written, `1` = AI-generated
- It also has a `source` column identifying the original corpus (e.g., `persuade_corpus`)
- Essays span multiple prompt types (persuasive, narrative, informational)

### Filtering Criteria

Write `scripts/assemble_demo_corpus.py` (first stage) to:

1. Load the DAIGT CSV
2. Filter to `label == 0` (human-written only)
3. Filter to word count 80–350 (matches our assignment contexts — discussion posts, not full essays)
4. Prefer persuasive/reflective register (these map best to Ethnic Studies discussions and Biology lab reflections)
5. Output `data/demo_source/daigt_filtered.json` with structure:
```json
[
  {
    "source_id": "daigt_00142",
    "text": "The essay text...",
    "word_count": 187,
    "source": "persuade_corpus",
    "prompt_id": "3"
  }
]
```

**Target:** ~100 filtered essays to choose from. We'll use ~15 for normal students after topic adaptation, plus 4 shortened for exhaustion_spike students.

---

## Step 2: Run AIC on Filtered Essays

### Purpose

Verify that real student writing scores LOW on our AI detection. This is a calibration check — if real essays trigger high suspicion, our system has a problem.

### How to Run

```python
from Academic_Dishonesty_Check_v2 import DishonestyAnalyzer

analyzer = DishonestyAnalyzer(
    profile_id="standard",
    context_profile="high_school",  # matches demo context
)

results = []
for essay in filtered_essays:
    result = analyzer.analyze_text(
        text=essay["text"],
        student_id=essay["source_id"],
        student_name=f"DAIGT-{essay['source_id']}",
    )
    results.append(result)
```

### What to Check

- **Suspicious scores**: Real essays should mostly score < 30. If any score > 50, investigate why.
- **Smoking gun detection**: Should be `False` for all real essays. Any `True` is a false positive to investigate.
- **Human presence detection**: Real essays should show `human_presence_confidence > 0.5` in most cases.
- **Marker distributions**: What markers fire on real student writing? This tells us our baseline.

### What to Record

Save results to `data/demo_source/daigt_aic_results.json`:
```json
[
  {
    "source_id": "daigt_00142",
    "suspicious_score": 12.3,
    "authenticity_score": 78.5,
    "concern_level": "low",
    "smoking_gun": false,
    "human_presence_confidence": 0.72,
    "human_presence_level": "moderate",
    "markers_found": {"hedging_language": ["I think", "maybe"]},
    "marker_counts": {"hedging_language": 2}
  }
]
```

### Success Criteria

- ≥90% of real essays score `concern_level: "low"`
- 0 false-positive smoking guns
- Human presence detector fires on ≥80% of essays

---

## Step 3: Run QuickAnalyzer on Filtered Essays

### Purpose

See what statistical/NLP patterns emerge from real student writing. This tells us what "normal" looks like before we run the LLM pipeline.

### How to Run

```python
from insights.quick_analyzer import QuickAnalyzer

analyzer = QuickAnalyzer()
qa_result = analyzer.analyze(
    submissions=[
        {
            "student_id": essay["source_id"],
            "student_name": f"DAIGT-{essay['source_id']}",
            "body": essay["text"],
            "submission_type": "online_text_entry",
            "word_count": essay["word_count"],
            "submitted_at": "2026-03-08T22:00:00Z",  # dummy
            "due_at": "2026-03-08T23:59:00Z",         # dummy
        }
        for essay in filtered_essays[:30]  # use a class-sized batch
    ],
    assignment_id="test-001",
    assignment_name="Test Analysis",
    course_id="test-course",
    course_name="Test Course",
)
```

### What to Check

- **Sentiment distribution**: What's the natural spread? (analytical/passionate/personal/etc.)
- **Clustering**: Do real essays cluster meaningfully? How many clusters emerge for ~30 essays?
- **Keyword hits**: What patterns from `src/insights/patterns.py` fire on real writing?
- **Concern signals**: The signal matrix pre-screening — what does it flag in real student writing?
- **Embedding outliers**: Which essays are genuinely unusual? These might be good "charting new ground" candidates.

### What to Record

Save the full `QuickAnalysisResult` (serialized) to `data/demo_source/daigt_quick_analysis.json`. This is reference data for calibrating expectations.

---

## Step 4: Run LLM Pipeline on a Small Batch

### Purpose

Test the full InsightsEngine pipeline on ~10 real essays to verify:
- Submission coder produces meaningful codings
- Concern detector behaves correctly (doesn't over-flag)
- Theme generator finds real themes
- Synthesizer produces a coherent report
- Measure wall-clock time per essay

### How to Run

This requires an LLM backend. Two options:

**Option A — Anthropic API (Sonnet):**
```python
from insights.engine import InsightsEngine
from insights.insights_store import InsightsStore

store = InsightsStore()  # Uses default SQLite path
engine = InsightsEngine(api=None, store=store, settings={
    "insights_model_tier": "medium",
    "insights_backend": "anthropic",
    "anthropic_api_key": os.environ["ANTHROPIC_API_KEY"],
    "anthropic_model": "claude-sonnet-4-20250514",
})

run_id = engine.run_analysis(
    course_id="test-001",
    course_name="Test Course",
    assignment_id="test-assign-001",
    assignment_name="Test Analysis",
    model_tier="medium",
    teacher_context="Testing pipeline with real student essays from DAIGT dataset",
    progress_callback=lambda stage, pct: print(f"{stage}: {pct}%"),
)
```

**Option B — Local Ollama (8B):**
```python
engine = InsightsEngine(api=None, store=store, settings={
    "insights_model_tier": "lightweight",
    "insights_backend": "ollama",
    "ollama_model": "llama3.1:8b",
    "ollama_base_url": "http://localhost:11434",
})
```

### What to Check

- **Coding quality**: Do theme_tags make sense? Are notable_quotes actually notable?
- **Emotional register**: Does the classification match a human read?
- **Concerns**: Are any flagged? If so, are they legitimate? Check that the anti-tone-policing post-processing works (see `src/insights/concern_detector.py` lines 83-124).
- **Themes**: With only 10 essays, themes will be thin. That's fine — we're checking format and sanity.
- **Timing**: Record wall-clock time per essay and total. This goes into the demo guide.

### What to Record

- Wall-clock times: per-essay coding, total pipeline, broken down by stage
- Save the full InsightsStore output for this test run (it's in SQLite)
- Note any failures, timeouts, or unexpected outputs

### Known Issues from Prior Testing

From `memory/project_insights_testing_findings.md` and `memory/project_insights_fine_tuning.md`:
- Theme generation can timeout on the 8B model (300s limit, falls back to tag-frequency themes)
- Concern detector had over-flagging issues — threshold was raised
- Stopwords needed filtering in top_terms
- Resume logic exists for interrupted runs (`engine.run_partial()`)

---

## Step 5: Select Essays for Demo Corpus

### Student Roster (from `src/demo_data.py`)

The demo has 35 students across courses. For Insights, we need ~29 for Ethnic Studies and ~25 for Biology. The key students with specific narrative roles:

| Student | ID | Pattern | What Their Submission Must Show |
|---------|-----|---------|-------------------------------|
| **Maria Ndiaye** | S001 | esl | Transnational family voice. Non-native English patterns (article drops, tense shifts, preposition choices). Rich personal connections to intersectionality through family experience. Must trigger ESL adjustment in AIC (40% suspicion reduction). |
| **Jordan Kim** | S002 | burnout | Exactly ~97 words. Genuine but fatigued. Submitted at 2am. One clear connection to the reading, then runs out of steam. Triggers Short Sub Review → TEACHER_REVIEW. |
| **Alex Hernandez** | S003 | smoking_gun | Raw HTML/markdown artifacts. Angle brackets, div tags, chatbot formatting bones. The text itself may be coherent — the giveaway is the physical artifacts of copy-paste from a chatbot. |
| **Tyler Nguyen** | S010 | sustained_cheat | AI-generated. Correct but hollow. Uses the right vocabulary but zero personal connections, zero quotes from readings, no emotional register. Looks "too clean." |
| **Jaylen Carter** | S011 | sustained_cheat | Same as Tyler — AI-generated, topically correct, personally empty. |
| **4 exhaustion_spike students** | S030-S033 | exhaustion_spike | First-time pattern change at Week 6. Normally 200+ words, now 100-140. Genuine voice but rushed. Some may have AI markers — not because they're dishonest, but because exhaustion looks like disengagement. |
| **~19 normal students** | various | normal | Real student voice. Mix of engagement levels. Some analytical, some personal, some passionate. Adapted from DAIGT with topic changes. |

### What DAIGT Can and Cannot Provide

**DAIGT gives us:** Authentic student voice patterns — hedging, messiness, personal anecdotes, cognitive struggle, sentence-level fingerprints of real adolescent writing. Also: *rhetorical moves* that may map to the discourse patterns we need. A student arguing passionately about school uniforms uses the same structural moves as a student arguing passionately about redlining — exclamation marks, first person conviction, strong verbs. A student who says "everyone deserves to express themselves" about dress codes might use the same flattening move as a student essentializing about culture.

**DAIGT does NOT give us:** The specific *content* — intersectionality, identity, race, colorblindness, tone policing. These are discourse patterns tied to identity-focused classroom discussion. A school uniform essay won't contain "I don't see color" or "Latino families always value community."

**What this means:** DAIGT essays are *voice scaffolding* — we borrow the writing style and, where possible, the rhetorical moves. For students who need specific discourse patterns (essentializing, colorblind claims, tone policing), the approach is hybrid: find a DAIGT essay with a structurally similar move, then adapt the content while preserving the voice. Where no analog exists, hand-craft using a DAIGT essay's voice register (sentence length, hedging style, paragraph structure) as a template.

### Critical Pedagogy Students (Hand-Craft or Hybrid)

In addition to the key students above, the following "normal" students must exhibit specific discourse patterns that Scenes 9-11 depend on. The concern detector and theme generator need these inputs to produce the outputs the demo showcases.

**Avoiding strawmen:** These students must read as real teenagers, not pedagogical examples. The essentializer doesn't think they're essentializing — they think they're being supportive. The tone policer isn't being malicious — they're uncomfortable and reaching for "civility" as a shield. Write the *student*, not the *pattern*. One approach: find a DAIGT essay with a similar rhetorical *move* (group-level claim, appeal to fairness, passionate argument) and adapt it into the Ethnic Studies context, preserving voice while shifting content.

| Student | ID | What They Write | Why It Matters to the Demo | Source Strategy |
|---------|-----|-----------------|---------------------------|----------------|
| **Essentializer** | e.g. S015 | Well-intentioned but essentializing: admires a culture but flattens it. "In my neighborhood the Mexican families are always so close and they really support each other, I think that's what intersectionality is about." Positive sentiment, problematic framing. ~180 words. | Scene 10: essentializing concern flagged even with positive sentiment. | Look for DAIGT essays that make group-level claims ("people who X always Y") and adapt the topic. If none found, hand-craft using a real student voice register from DAIGT as scaffolding. |
| **Colorblind Claimant** | e.g. S018 | Makes a colorblind claim inside an otherwise engaged post: "I think intersectionality is interesting but honestly at the end of the day I just treat everyone the same, I don't really see the point of focusing so much on categories." ~200 words. | Scene 10: colorblind claim flagged. Tests keyword + neutral sentiment → CONCERN. | Hand-craft. This is a specific discourse move unlikely to appear in DAIGT. Use a DAIGT essay's voice register (hedging style, sentence length) as scaffolding. |
| **Righteous Anger** | e.g. S022 | Passionate, angry engagement with systemic injustice: "This makes me furious — how can we read about redlining and act like it's ancient history when my neighborhood still looks exactly like the map from 1940?" ~220 words. | Scene 10: anger NOT flagged. Signal matrix codes (negative VADER + critical keywords) as APPROPRIATE. This is the critical pedagogy showcase. | Look for DAIGT essays with passionate/urgent register (exclamation marks, strong verbs, first person conviction). Adapt the passion to this topic. |
| **Tone Policer** | e.g. S025 | Uncomfortable with classmate intensity, reaches for civility: "I get that this is important to people but I feel like we should be able to have these conversations without getting so heated about it, like we're all here to learn right?" ~170 words. | Tests that concern detector catches tone policing via anti-bias post-processing. | Look for DAIGT essays that use "respectful disagreement" framing or appeals to neutrality. Adapt. |
| **Premise Challenger** | e.g. S020 | Genuine intellectual pushback: "OK but the reading acts like intersectionality covers everything and it doesn't. My family is white and poor and nobody in this framework talks about us. That's its own kind of erasure." ~190 words. | Scene 11 "Charting New Ground" — outlier report. Genuine dissent, not hostility. | Hand-craft. This is a specific intellectual move. Use DAIGT voice scaffolding for register. |

**Total hand-crafted/hybrid students:** 5 key + 5 critical pedagogy = 10, plus 4 exhaustion_spike adapted from DAIGT = 14 special students. The remaining ~15 normal students are adapted from DAIGT with topic changes.

### Selection Criteria for DAIGT Adaptation

From Step 2/3 results, select essays (~15 normal + 4 to shorten for exhaustion_spike) that:
1. Scored low on AIC (< 20 suspicious score)
2. Have clear human presence markers
3. Show a range of emotional registers (not all analytical)
4. Include some that the QuickAnalyzer embedding model identified as cluster outliers (for additional "charting new ground" candidates)
5. Vary in word count (100–350 range, centered around 180–220)

### Topic Adaptation Strategy

The DAIGT essays won't be about intersectionality or cell respiration. The adaptation process:

**Assignment contexts:**
- **Ethnic Studies**: "Week 6 Discussion: Intersectionality in Practice" — students respond to a reading about intersectionality theory applied to everyday life
- **Biology**: "Lab Reflection: Cell Respiration" — students reflect on a lab where they measured CO2 output under different conditions

**How to adapt (preserving voice):**
1. Read the DAIGT essay and identify its *structure*: Does it open with a personal anecdote? Make a claim then support it? Use hedging? Reference authority?
2. Rewrite the *content* to match the assignment topic while preserving that structural fingerprint
3. Keep the original's: sentence length variation, hedging patterns ("I think", "maybe"), punctuation habits, paragraph structure, emotional register
4. Change the original's: topic references, cited sources, specific claims
5. **Do NOT** clean up grammar, fix run-ons, or "improve" the writing. The messiness is the authenticity signal.

**Example:** A DAIGT essay that argues "I think school uniforms are not a good idea because they take away our identity..." becomes "I think intersectionality is really important because it shows how identity is not just one thing..." — same hedging, same structure, different topic.

For **Biology**, the adaptation is different — lab reflections are more structured. Look for DAIGT essays with a more analytical/reporting register and adapt those.

---

## Step 6: Hand-Craft Key Students

These cannot come from DAIGT — they need specific characteristics.

### Maria Ndiaye (S001) — ESL / Transnational Voice

Write ~210 words about intersectionality through the lens of her Senegalese-American family. Must include:
- Article drops ("In my family we always talked about identity" not "In my family, we have always talked about identity")
- Tense shifts (switching between present and past when describing ongoing family dynamics)
- Preposition choices that reflect French/Wolof transfer ("I am thinking on this" vs "I am thinking about this")
- Rich personal content — her grandmother's experience, navigating two cultural contexts
- A genuinely insightful point about intersectionality that goes beyond the reading

**Verification**: Run through AIC. Must trigger ESL context adjustment. Final adjusted score should be low.

### Jordan Kim (S002) — Burnout / Short Sub Review

Write exactly ~97 words. Must include:
- One clear connection to the reading (names a concept or quotes a passage)
- A personal moment that shows genuine engagement
- Then trails off — last sentence is incomplete or minimal
- Voice should match a student who's been writing 200+ word posts for weeks

**Verification**: Must be below the word count threshold. Run through Short Sub Review prompts to verify TEACHER_REVIEW verdict.

### Alex Hernandez (S003) — Smoking Gun

Generate with an LLM, then deliberately leave artifacts:
- Raw `<div>` or `<p>` tags in the text
- Maybe a `**bold**` markdown fragment
- The content should be topically correct (about intersectionality) but with zero personal voice
- Should NOT have ESL patterns, hedging, or personal connections

**Verification**: Run through AIC. Must trigger `smoking_gun: True`. The `smoking_gun_details` should cite the HTML/markdown artifacts.

### Tyler Nguyen & Jaylen Carter (S010, S011) — Sustained Cheaters

These simulate "good" cheaters — students who paste ChatGPT output but clean up formatting. The generation process is a **calibration loop** against our own AIC system:

**Generation approach (realistic student cheating):**
1. Write a student-style prompt: "write a discussion post about intersectionality for my ethnic studies class, around 200 words" — this is literally what students do
2. Run the raw output through ChatGPT (or Sonnet/Haiku with a generic system prompt)
3. Light cleanup: remove any obvious AI phrasing the student would catch

**Humanization loop (calibrate against AIC):**
1. Run the generated text through `DishonestyAnalyzer.analyze_text()`
2. Check the score. Raw ChatGPT output will likely score **too high** (70+) — it'll have perfect paragraph structure, no hedging, organizational markers
3. If score > 60: humanize one step at a time, re-testing after each:
   - Add 1-2 hedging phrases ("I think", "kind of")
   - Break one long sentence into two choppy ones
   - Add a minor typo or autocorrect artifact
   - Shorten one paragraph, lengthen another
   - Drop a transition word ("Furthermore" → just start the sentence)
4. Re-run AIC after each change. Stop when score lands in 40-60 range
5. Record the humanization steps and which markers each step affected

**This loop is itself valuable system testing.** It maps our detection boundary. If AI text needs 10 edits to reach 40-60, our system is sensitive. If 2 edits get it there, we may have a gap. Document the findings either way.

**Key constraints:**
- Zero personal connections (the text should be *about* intersectionality in general, never "in my experience" or "my family")
- Zero readings referenced by name (or generic: "the reading mentioned" not "Crenshaw argues")
- No emotional register beyond "analytical" — this is the hallmark of AI: correct but hollow
- Slightly different from each other (different source prompts or temperature)
- Must NOT trigger smoking gun (no HTML artifacts, no markdown)

**Verification**: Final AIC score 40-60, `smoking_gun: False`, `human_presence_confidence < 0.3`. The signal is statistical, not physical.

### 4 Exhaustion Spike Students (S030-S033)

Adapt from DAIGT essays but shorten to 100-140 words. These should feel:
- Genuine but rushed
- Like a student who usually writes more but didn't have time this week
- Some may accidentally trip AI markers because brevity + surface-level engagement looks like AI patterns

**Verification**: Run through AIC. Scores should be variable — some low, some borderline. The point is that the *cluster* is the signal, not any individual score.

---

## Step 7: Generate Demo Insights JSON

### Script: `scripts/generate_demo_insights.py`

Once the corpus is assembled, run the full InsightsEngine pipeline to produce the baked JSON files.

**For Ethnic Studies:**
```python
from preprocessing.pipeline import PreprocessedSubmission
from insights.engine import InsightsEngine
from insights.insights_store import InsightsStore

# Build PreprocessedSubmission objects from corpus
submissions = []
for student in ethnic_studies_corpus:
    sub = PreprocessedSubmission(
        submission_id=int(student["student_id"].replace("S", "")),
        user_id=int(student["student_id"].replace("S", "")),
        assignment_id=113002,  # from demo_data.py
        text=student["text"],
        was_translated=False,
        was_transcribed=False,
        was_image_transcribed=False,
        original_language=None,
        original_language_name=None,
        original_text=None,
        transcription_results=[],
        image_transcription_results=[],
        translation_result=None,
        teacher_comment=None,
    )
    submissions.append(sub)

# For Maria Ndiaye — mark as translated to trigger ESL awareness
maria_sub = PreprocessedSubmission(
    ...,
    was_translated=False,  # She wrote in English
    original_language="wo",  # Wolof detected
    original_language_name="Wolof",
    # The system uses original_language presence as an ESL signal
)
```

### Pipeline Execution

```python
import time

store = InsightsStore()
engine = InsightsEngine(api=None, store=store, settings={
    "insights_model_tier": "medium",
    "insights_backend": "anthropic",
    "anthropic_api_key": os.environ["ANTHROPIC_API_KEY"],
    "anthropic_model": "claude-sonnet-4-20250514",
})

t0 = time.time()

run_id = engine.run_analysis(
    course_id="90003",
    course_name="Ethnic Studies (11), Period 3",
    assignment_id="113002",
    assignment_name="Week 6 Discussion: Intersectionality in Practice",
    model_tier="medium",
    teacher_context=(
        "This is a weekly discussion board. Students respond to a reading about "
        "intersectionality theory applied to everyday life. Complete/incomplete grading — "
        "150 word minimum. I'm looking for genuine engagement with the concepts, not "
        "polished academic writing."
    ),
    progress_callback=lambda stage, pct: print(f"  {stage}: {pct}%"),
)

elapsed = time.time() - t0
print(f"\nTotal pipeline time: {elapsed:.1f}s ({elapsed/29:.1f}s per student)")
```

### Extracting Baked JSON

After the pipeline completes, extract from InsightsStore into the demo JSON format:

```python
import json

run = store.get_run(run_id)
# run["stages_completed"] must be a list (InsightsStore._decode_run handles this)
# run["quick_analysis"] stays as JSON string

codings = store.get_codings(run_id)
# Each coding has "coding_record" as a dict (already decoded by InsightsStore)

themes = store.get_themes(run_id)
# themes["theme_set"] and themes["outlier_report"] and themes["synthesis_report"]
# are JSON strings — keep them as strings in the baked file

feedback = store.get_feedback(run_id)

demo_json = {
    "run": run,
    "codings": codings,
    "themes": themes,
    "feedback": feedback,
}

output_path = Path("src/demo_assets/insights_ethnic_studies.json")
output_path.parent.mkdir(parents=True, exist_ok=True)
output_path.write_text(json.dumps(demo_json, indent=2, default=str))
```

### Critical Format Requirements

The demo UI (`src/gui/panels/insights_panel.py`) expects:

1. **`run["stages_completed"]`** — must be a Python list, NOT a JSON string. The real InsightsStore decodes this from SQLite. DemoInsightsStore loads it already decoded from JSON.

2. **`coding["coding_record"]`** — must be a Python dict, NOT a JSON string. Fields required (from `src/insights/models.py` SubmissionCodingRecord):
   - `theme_tags`: list of strings (1-5)
   - `theme_confidence`: dict of tag → float
   - `notable_quotes`: list of dicts with `text` and `significance`
   - `emotional_register`: one of analytical|passionate|personal|urgent|reflective|disengaged
   - `readings_referenced`: list of strings
   - `concepts_applied`: list of strings
   - `personal_connections`: list of strings
   - `concerns`: list of ConcernRecord dicts (`flagged_passage`, `surrounding_context`, `why_flagged`, `confidence`)
   - `word_count`: int
   - `cluster_id`: int or null
   - `vader_sentiment`: float
   - `keyword_hits`: dict
   - `draft_feedback`: string or null

3. **`themes["theme_set"]`** — JSON string. When parsed, must be a list of theme objects with `contradictions` field.

4. **`themes["outlier_report"]`** — JSON string. When parsed, must be a list with `why_notable`, `relationship_to_themes`, `teacher_recommendation` per outlier.

5. **`themes["synthesis_report"]`** — JSON string. When parsed, must have a `"sections"` dict with exactly these 9 keys:
   - `what_students_said`
   - `emergent_themes`
   - `tensions_and_contradictions`
   - `surprises`
   - `focus_areas`
   - `concerns`
   - `divergent_approaches`
   - `looking_ahead`
   - `students_to_check_in_with`

6. **Feedback rows** — each must have: `run_id`, `student_id`, `student_name`, `draft_text`, `approved_text` (null), `status` ("pending"), `confidence` (float), `posted_at` (null).

### Timing to Record

Record and report:
- Total pipeline time for Ethnic Studies (~29 students) via Sonnet
- Total pipeline time for Biology (~25 students) via Sonnet
- Per-student coding time average
- If you also run via local 8B: total time for comparison

These numbers fill in the `[TBD]` placeholders in the demo guide script (Scenes 2 and 8 in `docs/demo_expansion_plan.md`).

---

## Step 8: Verify Demo-Critical Behaviors

After generating the JSON, verify these specific behaviors that the demo narrative depends on:

### Concern Detection Verification

In the Ethnic Studies codings:
- [ ] The Essentializer student (~S015) has a concern flagged for essentializing language, even though VADER sentiment is positive
- [ ] The Colorblind Claimant (~S018) has a concern flagged for the colorblind claim
- [ ] The Righteous Anger student (~S022) is NOT flagged as a concern — the signal matrix must code (negative VADER + critical keywords) as APPROPRIATE
- [ ] The Tone Policer (~S025) has a concern flagged — the anti-bias post-processing catches tone policing (see `concern_detector.py` lines 83-124)
- [ ] The signal matrix in QuickAnalysis coded political critique keywords (from `patterns.py` CRITICAL_KEYWORDS) as APPROPRIATE, not concerns
- [ ] No student writing passionately about oppression, injustice, or systemic racism is flagged as a concern

### Outlier/"Charting New Ground" Verification

- [ ] Maria Ndiaye appears in the outlier report (transnational family framing = unique perspective)
- [ ] The Premise Challenger (~S020) appears in the outlier report (class-based critique of intersectionality framing)
- [ ] Outlier recommendations are STRUCTURAL (discussion prompts, small groups, reading pairings) — NOT "invite Maria to share" or "ask S020 to present their argument"
- [ ] At least 2-3 students appear as outliers total (Maria + Premise Challenger + possibly one adapted from DAIGT)

### Synthesis Report Verification

- [ ] All 9 section keys present
- [ ] `students_to_check_in_with` section does NOT recommend spotlighting
- [ ] `tensions_and_contradictions` captures the individual-vs-systemic framing of intersectionality
- [ ] `concerns` section distinguishes content concerns from wellbeing concerns

### Biology Differences

- [ ] Themes are about scientific reasoning (data interpretation, lab methodology), not identity
- [ ] Concerns are about disengagement from scientific process, not political content
- [ ] Different emotional register distribution (more analytical, less passionate)

---

## File Outputs Summary

| File | What | When |
|------|------|------|
| `data/demo_source/daigt_filtered.json` | Filtered DAIGT essays | Step 1 |
| `data/demo_source/daigt_aic_results.json` | AIC calibration results | Step 2 |
| `data/demo_source/daigt_quick_analysis.json` | QuickAnalyzer calibration | Step 3 |
| `data/demo_corpus/ethnic_studies.json` | Final assembled corpus | Steps 5-6 |
| `data/demo_corpus/biology.json` | Final assembled corpus | Steps 5-6 |
| `src/demo_assets/insights_ethnic_studies.json` | Baked Insights for demo UI | Step 7 |
| `src/demo_assets/insights_biology.json` | Baked Insights for demo UI | Step 7 |

The `data/` files are working artifacts. The `src/demo_assets/` files are committed to the repo and consumed by the demo.

---

## Architecture Quick Reference

Key files and their roles, for orientation:

| System | Entry Point | Key Classes/Functions |
|--------|------------|----------------------|
| AIC | `src/Academic_Dishonesty_Check_v2.py` | `DishonestyAnalyzer.analyze_text()` → `AnalysisResult` |
| QuickAnalyzer | `src/insights/quick_analyzer.py` | `QuickAnalyzer.analyze()` → `QuickAnalysisResult` |
| Full Pipeline | `src/insights/engine.py` | `InsightsEngine.run_analysis()` → run_id |
| Submission Coder | `src/insights/submission_coder.py` | `code_submission()` → `SubmissionCodingRecord` |
| Concern Detector | `src/insights/concern_detector.py` | `detect_concerns()` → `List[ConcernRecord]` |
| Theme Generator | `src/insights/theme_generator.py` | `generate_themes()`, `surface_outliers()` |
| Signal Matrix | `src/insights/patterns.py` | `SIGNAL_MATRIX`, `CRITICAL_KEYWORDS` |
| Prompts | `src/insights/prompts.py` | All LLM prompt templates |
| Models | `src/insights/models.py` | `SubmissionCodingRecord`, `QuickAnalysisResult`, `ConcernRecord` |
| Preprocessing | `src/preprocessing/pipeline.py` | `PreprocessedSubmission` dataclass |
| Store | `src/insights/insights_store.py` | `InsightsStore` — SQLite persistence |
| Demo Data | `src/demo_data.py` | Student roster, course data, `simulate_grading_run()` |
| Demo Store | `src/automation/demo_store.py` | `DemoRunStore` (will get `DemoInsightsStore` after demo expansion) |
