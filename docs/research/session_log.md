# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-29, evening session)

### Pipeline status

| Process | Status | Notes |
|---------|--------|-------|
| ethnic_studies pipeline (0cb5b7e8) | **Resuming** | Crashed after observations (7/11 stages). Fixed: added 5s sleep to `unload_mlx_model()` for Metal reclaim. Relaunched — check `ps aux` and store on startup. |
| Trajectory tests | Waiting | Launch after pipeline completes |

### What was done this session

1. **Test-monitor skill created** (`~/.claude/skills/test-monitor/SKILL.md`) — global skill for multi-agent research sessions. Includes session log protocol, commit-on-exit, context management. Reviewed by Opus, trimmed 30%.
2. **Mycelial model doc** (`~/.claude/skills/test-monitor/mycelial_model.md`) — distributed intelligence architecture reference.
3. **Test Q logged** to experiment log — 27B probes confirm disability vocab + "exhausting" are both necessary for BURNOUT. Neither alone triggers it.
4. **Test K logged** to experiment log — then **revised** after qualitative read of actual outputs. Anti-spotlighting keyword rubric was methodologically invalid (prompt told models not to suggest activities; rubric scored for activity suggestions). Rewritten with qualitative findings.
5. **TR04 hallucination diagnosed and fixed** — `OBSERVATION_SYSTEM_PROMPT` now guards against inventing prior submissions. Conditional on trajectory context presence.
6. **Pipeline crash root cause found** — `unload_mlx_model()` had no sleep after Metal cleanup; driver reclaim is async. Added 5s sleep. This was the recurring crash cause.
7. **Identity-disclosure guard implemented** — generalized guard added to `WELLBEING_CLASSIFIER_SYSTEM` in prompts.py. Covers all identity axes. Material conditions = only valid wellbeing evidence.
8. **Evidence-extraction classifier designed** — `WELLBEING_EVIDENCE_EXTRACTION_SYSTEM` added to prompts.py. Two-step: extract material evidence → derive axis. Alternative to guard approach.
9. **Q4/Q5 probes added** to `test_q_27b_probes()` — head-to-head comparison of guard vs evidence-extraction on same S029 text with 27B.

---

## Queue

### Immediate (cloud, ~3 min)
```bash
python3 scripts/run_alt_hypothesis_tests.py --tests Q --no-subprocess
```
Runs Q0-Q5: baseline + 3 ablations + guard test + evidence-extraction test. All on 27B via OpenRouter.

### After pipeline completes (MLX, 4-6 hrs)
```bash
caffeinate -i python scripts/run_trajectory_tests.py --model gemma12b
```

### Pending design work (pass to other agents)
- Longitudinal equity tests: `docs/research/longitudinal_test_design_prompt.md` — 4 risk areas (normative development, variable output, silence-after-disclosure, working student patterns)
- Binary vs 4-axis GUI comparison: feature-flagged research mode (another agent implementing)
- Identity vocabulary probes: immigration + racial identity ablations on 27B (design needed, similar to Q methodology)
- Test K anti-spotlighting redesign: replace keyword rubric with qualitative framing assessment

---

## Active issues

### TR04 hallucination — FIXED
Fixed in `OBSERVATION_SYSTEM_PROMPT` (prompts.py). Conditional on trajectory context: when no prior submissions, guard fires. When trajectory context present, longitudinal language allowed.

### Pipeline crash — FIXED
Root cause: `unload_mlx_model()` had no async reclaim pause. Added 5s sleep. Pipeline relaunched.

### Phase 2 pre-fix prompts
Phase 2 ran before CRISIS-supersedes commit. BIO-WB04 may be fixed now. Re-run optional.

---

## Key findings (updated)

1. **Format > model (12B)**: 4-axis eliminates disparate impact on neurodivergent writers (25/25 FP binary → 9/9 correct 4-axis). But does NOT fix 27B.
2. **Disability vocab mediates 27B trigger** (Test Q): both disability vocabulary AND "exhausting" needed. Neither alone sufficient. Interaction effect.
3. **Guard vs evidence-extraction**: two competing fixes implemented, not yet tested. Guard = suppress wrong inference. Evidence-extraction = restructure task so wrong inference can't form. Q4/Q5 probes ready to run.
4. **Anti-spotlighting keyword rubric invalid** (Test K): prompt told models not to suggest activities; rubric scored for activity language. Real finding from qualitative read: step_flash frames class-level, arcee drifts individual. Spotlighting risk is upstream (synthesis layer input), not in enhancement model.
5. **All test corpora are fabricated** — findings speak to pipeline capability, not to real student populations. Binary vs 4-axis on real anonymized data is the ecological validity test (pending GUI research mode).

---

## For next agent

- Check `ps aux` — pipeline may have completed or crashed again.
- If completed: run Q4/Q5 probes immediately (cloud, ~3 min) — this is the most important open test.
- Read Q4/Q5 output QUALITATIVELY (skill rule: always read raw output before logging).
- If Q5 works and Q4 doesn't: the evidence-extraction architecture is the recommended production classifier. This is a significant finding.
- Then launch trajectory tests with caffeinate.
- Experiment log entries for Q4/Q5 results need to be written after the run.
- `docs/research/longitudinal_test_design_prompt.md` is ready for the design agent.
