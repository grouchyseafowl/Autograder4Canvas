# Test Monitor Handoff — 2026-03-28 evening

## Your role

You are monitoring tests, debugging failures, reading raw output qualitatively,
logging results in the experiment log, and relaunching the pipeline from a
checkpoint. You are NOT editing pipeline source code — another agent handles that.

## Currently running

**Test P** (two-pass architecture: 4-axis classification then targeted CHECK-IN
on ENGAGED students only). Background task — check output at:
```
tail -30 /private/tmp/claude-501/-Users-june-Documents-GitHub-Autograder4Canvas/574cc6c3-b3cb-450c-ab51-72de8d2fa49c/tasks/b6jg6gtnm.output
```
Should complete in ~20 min from launch (~15:30 PDT).

## Queue after Test P completes

### 1. Temp 0.3 replications (~1.5 hours)
```
caffeinate -i ./scripts/run_temp03_replications.sh
```
Runs: P at temp 0.1 (already done if P completed above — skip duplicate),
then N×5 at temp 0.3, then P×3 at temp 0.3.

Tests whether the 4-axis (N) and two-pass (P) results hold under sampling
variation. At temp 0.1 everything is deterministic. At temp 0.3 we'll see
if results vary.

### 2. Pipeline resume from checkpoint (~80 min)
Run 0cb5b7e8 in the InsightsStore has 32/32 students coded (P1+P2 complete).
Resume skips coding and runs: wellbeing classification → observations →
themes → outliers → synthesis → feedback.

To resume:
```
caffeinate -i python3 scripts/generate_demo_insights.py --course ethnic_studies --resume-run 0cb5b7e8
```
(If that flag doesn't exist, check how the demo generator handles resume —
the engine's `resume_run()` method takes a run_id. The other agent may have
wired this differently.)

**Alternative**: The other agent building the 4-axis system may launch this
themselves. Coordinate — don't both launch it.

### 3. Test K retry (late evening when Venice quotas reset)
```
python3 scripts/run_alt_hypothesis_tests.py --tests K --no-subprocess
```
Enhancement model comparison — 9 models, corrected list, no GPT. Free
OpenRouter models have rate limits that reset overnight.

## What to look for in results

### Test P (THE KEY IMPLEMENTATION TEST)
- **S002 Jordan Kim**: Does it get CHECK-IN? The two-pass should catch the
  "Idk I had more to say but its late" signal. Test O caught it (ENGAGED +
  CHECK-IN) but also tagged 7/7 corpus students. P should be more targeted.
- **How many corpus students get CHECK-IN?** O had 7/7. If P also has 7/7,
  the targeted prompt isn't more selective. If P has 1-3, it's working.
- **WB09 Priya (control)**: Does the false positive return? O had it. P
  shouldn't, since CHECK-IN runs only on ENGAGED students (Priya should be
  classified ENGAGED by pass 1, so she DOES get the CHECK-IN pass — but the
  CHECK-IN prompt is narrower than O's multi-axis prompt).
- **CHECK-IN reasoning quality**: Read the `pass2_reasoning` for any
  CHECK-IN flagged students. Does the model surface competing interpretations
  ("this could be X OR Y") or just label?

### Temp 0.3 replications
- Do results VARY across runs? At temp 0.1, all N runs were word-for-word
  identical. At 0.3, we expect variation. The question: does S029 ever flip
  from ENGAGED to something else? Does S002 ever get caught by N alone?
- If S029 flips on ANY run: the 4-axis result is sampling-dependent, which
  weakens the paper claim. Document the flip rate.
- If N results are stable at 0.3: strong evidence for the paper.

### Pipeline resume (P1-P7 verification)
Check the baked output against this checklist (from memory file
`project_pipeline_rerun_followup.md`):
- [ ] `what_student_is_reaching_for` populated (was 0/32, should be >25/32)
- [ ] `confusion_or_questions` populated where applicable
- [ ] Observation preambles stripped (no "Okay, here's what I'm noticing")
- [ ] Anti-spotlighting: no "ask [student] to share" in synthesis
- [ ] Multiplicity + pedagogical wins sections in synthesis
- [ ] Forward-looking section in synthesis
- [ ] Structural naming in observations (Connor: "colorblind erasure", etc.)
- [ ] P7 insight ranking: do Exceptional Contributions highlight the most
      analytically interesting students? (Check _insight_score() effect)
- [ ] Observation synthesis saved to raw_outputs

### Test K (enhancement models)
- Rank models by total_score AND per-dimension
- **Language justice** is the hardest dimension — models scoring 0 there are
  disqualified regardless of total
- Report top 2-3 free models with scores
- If ALL models score <5 total, enhancement tier may need a paid model

## Critical conventions

### MLX testing
- **Always warmup Metal** before launching tests:
  ```python
  python3 -c "from mlx_lm import load, generate; m,t = load('mlx-community/gemma-3-12b-it-4bit'); print(generate(m, t, prompt='Hi', max_tokens=3, verbose=False))"
  ```
- **Use `caffeinate -i`** to prevent system sleep during runs
- If Metal deadlocks (0% CPU after model load), kill the process, warmup
  again, relaunch
- **Post-sleep deadlock**: Metal inference launched right after laptop wake
  deadlocks. Wait 30s after wake, do a warmup, then launch tests.

### Evaluating results
- **READ RAW OUTPUT QUALITATIVELY** — do not rely on keyword matching. The
  keyword evaluator (`WELLBEING_KEYWORDS`) has been wrong multiple times
  (flagged "eat" inside "great", classified asset-framed observations as
  MIXED because "distress" appeared in a negation). Read what the model
  actually SAID about each student.
- Every test output file now includes `provenance.git_commit` — verify the
  commit matches what you expect.

### Logging results
- Add findings to `docs/research/experiment_log.md`
- Include: what was tested, the raw numbers, qualitative reading of key
  outputs, what this means for the paper/system
- **Always verify claims against data as a separate step** — check every
  number you write against the actual JSON file
- Note codepath (test harness vs production) for any classification test
- Commit frequently with descriptive messages

## Files you need

| File | What it is |
|---|---|
| `scripts/run_alt_hypothesis_tests.py` | All tests (A-P) |
| `scripts/run_temp03_replications.sh` | Temp 0.3 queue |
| `scripts/generate_demo_insights.py` | Demo pipeline |
| `docs/research/experiment_log.md` | Research log |
| `memory/project_pipeline_refinement_plan.md` | Decision tree |
| `memory/project_pipeline_rerun_followup.md` | P1-P7 checklist |
| `data/research/raw_outputs/` | All test results |
| `CLAUDE.md` | MLX conventions |

## Decision tree (abbreviated)

**If P catches S002 with CHECK-IN AND corpus CHECK-INs < 4/7**:
→ Two-pass architecture validated. Tell the implementation agent to add
  CHECK-IN pass to pipeline (Part 2 of refinement plan).

**If P has same 7/7 over-firing as O**:
→ Targeted CHECK-IN prompt isn't more selective. Need prompt refinement
  or accept that CHECK-IN requires longitudinal data.

**If temp 0.3 N results are stable (S029 stays ENGAGED across 5 runs)**:
→ 4-axis finding is robust. Ready for paper.

**If temp 0.3 N results vary**:
→ Document the flip rate. If S029 flips >1/5 times, the finding needs
  a confidence interval, not an absolute claim.

## What another agent is doing

The implementation agent is building the 4-axis wellbeing classifier into
the production pipeline (replacing Stage 5 binary concern detector). They
have the per-student checkpointing. They may also launch the pipeline
resume — **coordinate with them so you don't both launch it**.
