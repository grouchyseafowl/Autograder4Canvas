# Test Monitor + Implementation Handoff — 2026-03-28

## Your role

You are monitoring running tests, analyzing results, implementing the two-pass
wellbeing architecture in production code, running the pipeline resume, and
launching Phase 1-4 testing. You own the full loop: monitor → analyze → implement
→ test.

## Currently running (background)

**Temp 0.3 replication suite** — launched via `run_temp03_replications.sh`.
The script runs sequentially: P@0.1 → N×5@0.3 → P×3@0.3.

Check progress:
```bash
ls -lt data/research/raw_outputs/test_p_two_pass_gemma12b_2026-03-28_17*.json data/research/raw_outputs/test_n_*2026-03-28_17*.json data/research/raw_outputs/test_n_*2026-03-28_18*.json 2>/dev/null
```

**P@0.1 is already complete** — results: 2/7 corpus CHECK-INs, 0/2 control FPs,
8/8 WB signals, S002+S029 caught. This is the best result of the iteration.
File: `test_p_two_pass_gemma12b_2026-03-28_1719.json`.

Note: the JSON metadata says temperature 0.3 but the actual inference was 0.1
(controlled by `TEST_TEMPERATURE` env var; the JSON reads from the MODELS config
dict instead — metadata bug, does not affect results).

Remaining in the suite: N×5@0.3 (~70 min), P×3@0.3 (~42 min). Do NOT re-launch
the suite — it's already running in the background. Just monitor the output files.

## What happened before this session

### Test P prompt iteration (4 runs)

The two-pass architecture works: Pass 1 classifies all students on a 4-axis
schema (CRISIS/BURNOUT/ENGAGED/NONE), then Pass 2 runs a targeted CHECK-IN
prompt only on ENGAGED students. Pass 1 was perfect from the start (17/17).
The iteration was all about the Pass 2 CHECK-IN prompt.

| Run | Prompt ver | Corpus CHK-INs | Control FPs | S028 FP | S002 | S029 |
|-----|-----------|----------------|-------------|---------|------|------|
| 1456 | v1 (original) | 6/7 | 2/2 | yes | yes | yes |
| 1521 | v2 (self-ref + equity) | 3/7 | 0/2 | yes | yes | yes |
| 1546 | v2 (same prompt rerun) | 3/7 | 0/2 | yes | yes | yes |
| 1719 | v3 (boolean calibration) | **2/7** | **0/2** | **no** | yes | yes |

**v1 problem**: "Is there anything subtle?" was a yes-biased question. Model
found "abrupt endings" in 8/8 ENGAGED students because student writing normally
ends without formal conclusions.

**v2 fixes** (lines 2583-2618 in `run_alt_hypothesis_tests.py`):
1. Flipped default: "Most engaged students need no further attention"
2. Required quotable self-reference about OWN STATE (not course material)
3. Required REGISTER SHIFT as a strong indicator
4. Four equity protections (register-neutral, not dialect-specific):
   - No formal conclusion = normal, not a signal
   - Personal/community experience as course material ≠ self-disclosure
   - Rhetorical expressions about material ≠ self-disclosure
   - Approach metacommentary ("I'm just gonna be real") ≠ state disclosure
5. Boolean calibration: "Set check_in to true ONLY when the competing
   interpretations are genuinely balanced"

**Why S028 kept flagging in v2**: "Ok so I'm just gonna be real with this one"
— the model quoted this as potential self-disclosure but its own reasoning said
"it's crucial not to overinterpret this; it's likely a strategic choice."
Boolean/reasoning misalignment. The v3 calibration sentence fixed it by telling
the model: if your analysis leans toward "nothing to note," check_in is false.

### Decision tree result: GO

P catches S002 ✅ AND corpus CHECK-INs = 2/7 (< 4/7) ✅.
**Two-pass architecture is validated. Implement in production.**

Full iteration history is logged in `docs/research/experiment_log.md` starting
at the entry "## 2026-03-28 15:30 — Test P Results".

## Queue (in priority order)

### 1. Monitor replication results (ongoing, ~2 hours total)

Results will appear as files in `data/research/raw_outputs/`. Key questions:

**N@0.3 (5 runs)**: Does S029 stay ENGAGED? Does S002 stay ENGAGED (not BURNOUT)?
Do all WB signals stay correct? If S029 flips on any run, document the flip rate.
Stable results = strong paper evidence. Variable results = need confidence intervals.

**P@0.3 (3 runs)**: What's the CHECK-IN range? Does S028 stay clear with the
v3 prompt? Ideal: 2/7 consistently. Acceptable: 2-3/7 range.

Log all results to experiment_log.md. Read qualitatively — don't rely on keyword
matching (WELLBEING_KEYWORDS has been wrong before, see experiment log).

### 2. Implement two-pass wellbeing in production pipeline

The validated architecture needs to move from the test script into the production
pipeline. The prompts are in `scripts/run_alt_hypothesis_tests.py`:
- **Pass 1** (4-axis): `FOUR_AXIS_SUBMISSION_SYSTEM` at line ~2197
- **Pass 2** (CHECK-IN): `TARGETED_CHECKIN_SYSTEM` at line ~2583

Production pipeline files to modify:
- `src/insights/engine.py` — the main pipeline. Currently has a binary concern
  detector (Stage 5) that needs replacing with the two-pass architecture.
- `src/insights/synthesizer.py` — downstream synthesis reads concern flags;
  needs to read the new 4-axis + CHECK-IN results instead.

Key implementation decisions:
- Pass 1 replaces Stage 5 entirely (no more binary concern_flag)
- Pass 2 runs only on ENGAGED students (the gating logic)
- Results stored per-student: `wellbeing_axis` (CRISIS/BURNOUT/ENGAGED/NONE),
  `wellbeing_confidence`, `checkin_flag` (bool), `checkin_reasoning` (string)
- Temperature: 0.1 for pass 1 (classification), 0.3 for pass 2 (generative)
- Use `unload_mlx_model()` between pipeline stages per CLAUDE.md

### 3. Phase 1-4 additional testing suite (BEFORE pipeline resume)

Run these BEFORE the pipeline resume. They validate the wellbeing prompts on
new domains using the test harness. If the prompts fail on STEM or multilingual
submissions, you want to know before baking a full 32-student production run.

24 synthetic submissions across 3 corpus files:

**Spec**: `docs/research/additional_testing_spec.md` (824 lines, full success
criteria for each test case)

**Corpus files**:
- `data/demo_corpus/phase1_long_form.json` — 7 long-form essays (chunking)
- `data/demo_corpus/phase2_biology.json` — 11 biology submissions (STEM equity
  + wellbeing): home epistemology, colloquial register, ESL, neurodivergent,
  accommodation disclosure, AAVE in STEM, indigenous knowledge, burnout,
  food insecurity, housing instability, front-loaded crisis
- `data/demo_corpus/phase3_translated.json` — 6 translated/code-switching
  submissions: Spanish L1 transfer, Spanglish code-switching, Vietnamese
  concept inclusion, burnout through translation, ICE stress in Spanglish

**Execution order**: Phase 1 → 2 → 3 → 4. Phase 4 waits for temp 0.3 results.
Follow MLX conventions from CLAUDE.md (warmup, caffeinate, subprocess isolation).

Read the spec carefully before running — it has specific success criteria per
test case, not just pass/fail.

### 4. Pipeline resume from checkpoint (~80 min)

Run `0cb5b7e8` in the InsightsStore has 32/32 students coded (P1+P2 complete).
Resume skips coding and runs: wellbeing classification → observations →
themes → outliers → synthesis → feedback.

**WARNING**: There are 5 runs in the store (query with
`PYTHONPATH=src python3 -c "from insights.insights_store import InsightsStore; ..."`):
- `0cb5b7e8` — 32 codings, no downstream stages. **THIS IS THE ONE WE WANT.**
- `6a5ff72f` — 4 codings (quick_analysis)
- `48dc3560` — 0 codings
- `10d8fd07` — 4 codings
- `4b7d2caf` — 22 codings

The auto-resume (`_find_incomplete_run()` at line 94 of generate_demo_insights.py)
picks the most recent incomplete run, NOT 0cb5b7e8. You need to either:
1. Check if a `--resume-run <id>` flag exists
2. Or delete/mark the newer incomplete runs so auto-resume finds 0cb5b7e8
3. Or manually call `engine.resume_run(run_id="0cb5b7e8...")` in a script

To launch (once resume target is confirmed):
```bash
caffeinate -i python3 scripts/generate_demo_insights.py --course ethnic_studies
```

Check the baked output against the P1-P7 checklist (from memory file
`project_pipeline_rerun_followup.md`):
- [ ] `what_student_is_reaching_for` populated (was 0/32, should be >25/32)
- [ ] `confusion_or_questions` populated where applicable
- [ ] Observation preambles stripped (no "Okay, here's what I'm noticing")
- [ ] Anti-spotlighting: no "ask [student] to share" in synthesis
- [ ] Multiplicity + pedagogical wins sections in synthesis
- [ ] Forward-looking section in synthesis
- [ ] Structural naming in observations (Connor: "colorblind erasure", etc.)
- [ ] P7 insight ranking: Exceptional Contributions highlight analytically
      interesting students (check `_insight_score()` effect)
- [ ] Observation synthesis saved to raw_outputs

### 5. Test K retry (when Venice quotas reset)
```bash
python3 scripts/run_alt_hypothesis_tests.py --tests K --no-subprocess
```
Enhancement model comparison — 9 models, corrected list, no GPT. Free
OpenRouter models have rate limits. Best run late evening or overnight.

## Critical conventions

### MLX testing
- **Always warmup Metal** before launching tests:
  ```python
  python3 -c "from mlx_lm import load, generate; m,t = load('mlx-community/gemma-3-12b-it-4bit'); print(generate(m, t, prompt='Hi', max_tokens=3, verbose=False))"
  ```
- **Use `caffeinate -i`** to prevent system sleep during runs
- If Metal deadlocks (0% CPU after model load), kill the process, warmup again
- **Post-sleep deadlock**: Metal inference launched right after laptop wake
  deadlocks. Wait 30s after wake, warmup, then launch.
- **Pause 5s between subprocesses** for Metal memory reclamation
- Call `unload_mlx_model()` between pipeline stages

### Evaluating results
- **READ RAW OUTPUT QUALITATIVELY** — the keyword evaluator has been wrong
  multiple times. Read what the model actually SAID about each student.
- Every test output file includes `provenance.git_commit` — verify it.
- pass2_reasoning fields may have JSON escaping issues (backslash-truncated
  in the stored `pass2_reasoning` field). Read the `prompt_pass2` field instead
  for the full raw model output.

### Logging
- Add findings to `docs/research/experiment_log.md`
- Include: what was tested, raw numbers, qualitative reading, implications
- **Verify every number against the actual JSON** before writing
- Note codepath (test harness vs production) for classification tests

## Files you need

| File | What it is |
|---|---|
| `scripts/run_alt_hypothesis_tests.py` | All tests (A-P), including v3 prompts |
| `scripts/run_temp03_replications.sh` | Currently running replication suite |
| `scripts/generate_demo_insights.py` | Demo pipeline + resume logic |
| `src/insights/engine.py` | Production pipeline (needs two-pass impl) |
| `src/insights/synthesizer.py` | Synthesis (reads concern flags) |
| `docs/research/experiment_log.md` | Research log |
| `docs/research/additional_testing_spec.md` | Phase 1-4 test spec |
| `data/demo_corpus/phase{1,2,3}*.json` | New test corpus files |
| `data/demo_corpus/ethnic_studies.json` | Existing corpus (mix with new) |
| `memory/project_pipeline_refinement_plan.md` | Decision tree |
| `memory/project_pipeline_rerun_followup.md` | P1-P7 checklist |
| `data/research/raw_outputs/` | All test results |
| `CLAUDE.md` | MLX conventions |

## Decision tree (updated)

**Two-pass architecture: GO** (validated across 4 P runs, best result 2/7 corpus
CHECK-INs with 0/2 control FPs). Implement in production.

**Temp 0.3 N replications** (pending):
- If stable (S029 stays ENGAGED 5/5): 4-axis finding is robust. Ready for paper.
- If S029 flips >1/5: need confidence interval, not absolute claim.

**Temp 0.3 P replications** (pending):
- If S028 stays clear 3/3: boolean calibration is stable.
- If S028 flips: it's a borderline case sensitive to sampling. Acceptable if
  the reasoning is self-correcting (teacher would dismiss it).

**Pipeline resume**: Verify P1-P7 fixes against checklist. If synthesis still
truncates at 2000 tokens, may need to split into two calls.

**Phase 1-4 tests**: Follow spec. These test new domains (STEM, multilingual)
that the ethnic studies corpus doesn't cover. Results inform whether the
wellbeing prompts generalize beyond the development corpus.
