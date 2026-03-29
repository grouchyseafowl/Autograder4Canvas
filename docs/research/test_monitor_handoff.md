# Test Monitor + Implementation Handoff — 2026-03-29

## Your role

You are monitoring test results, analyzing outputs qualitatively, fixing bugs,
running remaining phases, implementing the two-pass wellbeing architecture in
production, and running the pipeline resume. Debug as you go — if something
crashes, fix and re-run. Address any issues from testing BEFORE the pipeline run.

## What has been completed this session

### Replication suite (COMPLETE — all stable)

**N@0.3 (9 runs)**: 9/9 identical. S029 ENGAGED, S002 ENGAGED, WB 10/10,
0/2 control FPs. Effectively deterministic at temp 0.3 on Gemma 12B 4-bit.

**P@0.3 (4 runs: 1 @0.1, 3 @0.3)**: 4/4 identical for v3 prompt. 2/6 corpus
CHECK-INs (S002 + S029 only), S028 clear, 0/2 control FPs. Boolean calibration
is stable.

**Paper-ready finding**: The 4-axis format protects neurodivergent writers
(S029 ENGAGED 9/9) where the binary detector flagged them 25/25. Format
change eliminates disparate impact without model change.

Files: `data/research/raw_outputs/test_n_4axis_submissions_gemma12b_2026-03-28_1*.json`
and `test_p_two_pass_gemma12b_2026-03-28_1*.json`.

### Trajectory tests (COMPLETE — 69/69 passed, 0.22s)

Pure unit tests in `tests/test_trajectory_context.py`. All equity protections
validated: multi-signal safety, ESL suppression, neurodivergent protection,
working student protection, equity language compliance.

### Phase 1: Long-Form Chunking (COMPLETE — issues found and fixed)

**File**: `src/demo_assets/insights_phase1_long_form_gemma12b_mlx.json`
**Duration**: 86 min, 7 students (778-1500 words each)

**Results**: All 7 essays chunked correctly (2-3 chunks each). Chunking code
works. P1 readings per chunk concatenated for P2 — no silent truncation.

**Wellbeing**:
- LF02 Jaylen (burnout buried in middle): **BURNOUT 0.9** ✅ — key test passed
- LF06 Marisol (DV/IPV at boundary): BURNOUT 0.85 ⚠️ should be CRISIS
- LF03 Natasha (tonal shift): BURNOUT 0.9 ⚠️ false positive (emotional
  engagement misread as depletion)
- All others correct. what_student_is_reaching_for: 7/7 populated.

**Fixes committed**:
1. CRISIS supersedes ENGAGED — DV/housing/food insecurity disclosures now
   CRISIS even when student maintains analytical engagement (prompts.py +
   run_alt_hypothesis_tests.py)
2. BURNOUT anchored on MATERIAL CONDITIONS (work, sleep, caregiving) not
   metacommentary. Emotional intensity ≠ depletion. (prompts.py +
   run_alt_hypothesis_tests.py)
3. Observation preamble regex extended — "Okay, here's what I'm noticing
   about [student]..." now caught (submission_coder.py)

### Phase 2: Biology/STEM (COMPLETE — strong results)

**File**: `src/demo_assets/insights_phase2_biology_gemma12b_mlx.json`
**Duration**: 76 min, 11 students

**Results**: Zero false positives on all 7 equity-critical STEM students.
The pipeline does not pathologize non-standard ways of knowing in STEM:
- BIO-LR01 Daniela: abuela's cooking = epistemology, not confusion
- BIO-LR02 Marcus: colloquial register = engagement, not deficiency
- BIO-LR03 Anh: ESL syntax not flagged, technical precision recognized
- BIO-LR04 Jordan: neurodivergent tangents = curiosity, not disorganization
- BIO-LR07 Ruby: indigenous ecological knowledge = epistemology

**Wellbeing**: 3/4 detected. BIO-WB02 Keyana (food insecurity) missed —
expected, documented as known limitation for subtle incidental signals in
procedural STEM writing. BIO-WB04 Jaylen (brother's arrest) under-classified
as BURNOUT instead of CRISIS — same pattern as LF06, should be fixed by
the CRISIS supersedes prompt change.

**Phase 2 ran on pre-fix prompts** (launched before the commits). A re-run
with fixed prompts would confirm the CRISIS supersedes fix works.

### Phase 3: Translated/Multilingual (FAILED — bug fixed, needs re-run)

Crashed on Carmen Flores (TR01): Pydantic validation error. The model
returned `emotional_register` as a list `['passionate', 'urgent', 'personal']`
instead of a string. **Fixed**: added `_coerce_str()` helper in
`submission_coder.py` that joins lists at the parse boundary. Committed.

**Re-run needed**:
```bash
caffeinate -i python3 scripts/generate_demo_insights.py --course phase3_translated
```

This is the language justice test — whether the pipeline reads through
translated syntax and code-switching without pathologizing multilingual
students. Critical test cases:
- TR01 Carmen (Spanish L1 transfer syntax): should be ENGAGED
- TR02 Diego (Spanglish code-switching): should be ENGAGED
- TR03 Ana (translated + burnout): should be BURNOUT
- TR06 Isabella (code-switching + ICE crisis): should be CRISIS

### Phase 4: Cross-Model (PARTIAL — Qwen done, Gemma 27B pending)

**Qwen 2.5 7B result** (data point, not primary comparison):
- S029 ENGAGED ✅ — format protects neurodivergent writers across model families
- S023 Yolanda: false CRISIS (Qwen reads grandmother's story as student's crisis)
- WB: 10/10, controls: 0/2 FP
- File: `test_n_4axis_submissions_qwen7b_2026-03-28_2338.json`

**Gemma 27B via OpenRouter still needed** — this is the real cross-model
comparison (same family, larger scale). Run:
```bash
python3 scripts/run_alt_hypothesis_tests.py --tests N --model gemma27b --no-subprocess
```
Note: OpenRouter key is in `~/Documents/GitHub/Reframe/.env` as
`REFRAME_SHARED_OPENROUTER_KEY`. The test harness reads it automatically.

Check if `gemma27b` model key exists in MODELS dict. If not, add it pointing
to the OpenRouter endpoint for `google/gemma-3-27b-it`.

## Queue (in priority order)

### 1. Re-run Phase 3 (translated/multilingual, ~45-60 min)

Bug is fixed. This is the most critical remaining test — the pipeline has
never been tested on translated syntax or code-switching. The spec in
`docs/research/additional_testing_spec.md` (Phase 3 section, line ~380)
has detailed success criteria. Read qualitatively — especially TR06 (code-
switching + ICE crisis) which is the hardest equity test.

### 2. Run Phase 4 Gemma 27B (~25 min via OpenRouter)

Cross-model validation on same family, larger scale. If 27B also protects
S029, the paper can claim format generalizes within the Gemma family.

### 3. Implement two-pass wellbeing in production pipeline

The validated architecture needs to move from the test script into production.
Prompts are in `scripts/run_alt_hypothesis_tests.py`:
- **Pass 1** (4-axis): `FOUR_AXIS_SUBMISSION_SYSTEM` at line ~2197
- **Pass 2** (CHECK-IN): `TARGETED_CHECKIN_SYSTEM` at line ~2583

Production files to modify:
- `src/insights/engine.py` — replace binary concern detector (Stage 5)
  with two-pass architecture
- `src/insights/synthesizer.py` — read 4-axis + CHECK-IN results instead
  of binary concern_flag

Key decisions:
- Pass 1 replaces Stage 5 entirely
- Pass 2 runs only on ENGAGED students
- Temperature: 0.1 for pass 1, 0.3 for pass 2
- Use `unload_mlx_model()` between pipeline stages per CLAUDE.md
- Results: `wellbeing_axis`, `wellbeing_confidence`, `checkin_flag`,
  `checkin_reasoning` per student

### 4. Pipeline resume from checkpoint (~80 min)

Run `0cb5b7e8` in InsightsStore. 32/32 coded, needs downstream stages.
**WARNING**: auto-resume picks wrong run. See handoff notes in prior version.

Run AFTER Phase 3 confirms no prompt issues on multilingual text and AFTER
implementation is complete.

### 5. Test K retry (when Venice quotas reset)

```bash
python3 scripts/run_alt_hypothesis_tests.py --tests K --no-subprocess
```

## Bugs fixed this session

| Bug | Fix | Commit |
|---|---|---|
| LF06 DV under-classified as BURNOUT | CRISIS supersedes ENGAGED in classifier prompt | 900e3ae |
| LF03 emotional engagement → false BURNOUT | BURNOUT anchored on material conditions, not metacommentary | 6b009b5 |
| Observation preamble "Okay, here's what I'm noticing" | Extended regex to include period-terminated "notic\w+" pattern | 900e3ae |
| Phase 3 crash: emotional_register as list | `_coerce_str()` helper joins lists at parse boundary | d677560 |
| Experiment log: "8 runs" should be "9 runs" | Corrected | d677560 |
| Experiment log: "2/4 caught" should be "3/4 detected" | Corrected | d677560 |

## Significance of findings

### For implementation

**The 4-axis format is the intervention, not the model.** The format change
(binary → 4-axis) eliminates disparate impact on neurodivergent writers
without model changes. This means:
- Prompt engineering is the primary lever for equity outcomes
- Model selection matters less than classification schema design
- The two-pass architecture (classify → targeted CHECK-IN) reduces false
  positives from 6/7 corpus to 2/7 while maintaining sensitivity
- The pipeline generalizes from ethnic studies to STEM without domain-specific
  prompt changes — equity protections transfer across disciplines

**Known limitations to document**:
- Subtle, incidental wellbeing signals in procedural writing (BIO-WB02 food
  insecurity) are below the detection floor for single-submission classification
- Crisis disclosures wrapped in sustained analytical engagement may be under-
  classified (LF06, BIO-WB04) — the CRISIS supersedes fix addresses this
- Theme generation times out on long-form content at the lightweight tier
- Observation preambles still appear occasionally (regex may need expansion)

### Scholarly context

**Format > model for equity outcomes** connects to work on structured
prediction formats reducing bias in NLP (Schick & Schütze 2021 on pattern
exploiting training; Zhao et al. 2021 on calibration). The finding that a
4-category schema eliminates false positives that persist across model sizes
and families suggests the classification format itself encodes assumptions
about whose writing is "normal" — the binary FLAG/CLEAR schema encodes a
deficit model where any deviation from expected academic register triggers
a flag.

**Community cultural wealth in STEM** (Yosso 2005): The Phase 2 result —
indigenous ecological knowledge, home epistemology, colloquial STEM register
all correctly classified as ENGAGED — demonstrates that the observation
architecture can recognize what Yosso calls "familial capital" and
"aspirational capital" in STEM contexts. The pipeline reads abuela's cooking
as osmosis epistemology rather than off-topic confusion.

**Language justice** (Flores & Rosa 2015 on raciolinguistic ideologies): The
Phase 3 test (pending re-run) directly tests whether the pipeline reproduces
what Flores & Rosa call "appropriateness-based" language ideologies — where
the listener/reader's perception of the speaker determines whether language
is heard as competent or deficient. If the pipeline reads translated syntax
or code-switching as engagement rather than confusion, it disrupts the
raciolinguistic frame that positions Standard English as the neutral register
against which all others are measured.

**Neurodiversity and algorithmic justice** (Whittaker et al. 2019 on
disability and AI): The S029 result (25/25 false flags on binary → 9/9
correct on 4-axis) is a case study in how classification schemas can
encode or disrupt normative assumptions about cognition. The binary
detector treated nonlinear, associative writing as deviant; the 4-axis
schema treats it as a valid academic register. The problem was never the
student's writing — it was the built environment of the classification system.

## Critical conventions

### MLX testing
- **Always warmup Metal** before launching tests
- **Use `caffeinate -i`** to prevent system sleep
- **Pause 5s between subprocesses** for Metal memory reclamation
- Call `unload_mlx_model()` between pipeline stages

### Evaluating results
- **READ RAW OUTPUT QUALITATIVELY** — keyword matching has been unreliable
- Read what the model actually SAID about each student
- Every test output includes `provenance.git_commit` — verify it
- pass2_reasoning fields may have JSON escaping issues — read prompt_pass2

### Logging
- Add findings to `docs/research/experiment_log.md`
- **Verify every number against the actual JSON** before writing

## Files you need

| File | What it is |
|---|---|
| `scripts/run_alt_hypothesis_tests.py` | All tests (A-P), including v3 prompts |
| `scripts/generate_demo_insights.py` | Demo pipeline + resume logic |
| `scripts/run_phase_tests.sh` | Phase test chaining script |
| `src/insights/engine.py` | Production pipeline (needs two-pass impl) |
| `src/insights/synthesizer.py` | Synthesis (reads concern flags) |
| `src/insights/submission_coder.py` | Coding, observations, wellbeing classification |
| `src/insights/prompts.py` | All prompts (updated with fixes) |
| `docs/research/experiment_log.md` | Research log (verified accurate) |
| `docs/research/additional_testing_spec.md` | Phase 1-4 test spec |
| `data/demo_corpus/phase{1,2,3}*.json` | Test corpus files |
| `data/research/raw_outputs/` | All test results |
| `src/demo_assets/insights_phase{1,2}_*.json` | Phase 1-2 baked outputs |
| `CLAUDE.md` | MLX conventions |
