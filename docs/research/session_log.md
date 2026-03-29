# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-29)

### Pipeline status

| Process | Status | Notes |
|---------|--------|-------|
| `generate_demo_insights.py --course ethnic_studies` | **RUNNING** (PID 15264) | 32/32 codings done (run `0cb5b7e8`), awaiting synthesis/report stages. ~80+ min elapsed. |
| Trajectory tests | Waiting | Launch after pipeline completes |

### InsightsStore

| Run | Status | Course | Codings | Notes |
|-----|--------|--------|---------|-------|
| `0cb5b7e8` | INCOMPLETE | 90003 (ethnic_studies) | 32 | ONLY incomplete — auto-resume will land here |
| `1fabfb04` | INCOMPLETE | TRAJ_TEST_1 | 0 | Safe to ignore — preprocessing only, no codings |

4 junk runs from 2026-03-28 marked complete directly in SQLite to fix auto-resume.

---

## Completed tests (this sprint)

| Test | File | Summary |
|------|------|---------|
| N@0.3 × 9 | `test_n_4axis_submissions_gemma12b_2026-03-28_1*.json` | 9/9 identical. S029 ENGAGED all 9. Deterministic at temp 0.3. |
| P@0.3 × 4 | `test_p_two_pass_gemma12b_2026-03-28_1*.json` | 4/4 identical v3 prompt. 2/6 corpus CHECK-INs (S002+S029 only). |
| Phase 1 (long-form) | `insights_phase1_long_form_gemma12b_mlx.json` | 7 students, 86 min. LF02 BURNOUT correct. LF06/LF03 issues — fixed by prompts. |
| Phase 2 (biology) | `insights_phase2_biology_gemma12b_mlx.json` | 11 students, 76 min. Zero FPs on 7 equity-critical students. |
| Phase 3 (translated) | `insights_phase3_translated_gemma12b_mlx.json` | Crashed on TR01 (list coercion bug, fixed). Re-run complete. 6/6 correct. |
| Qwen 7B N-test | `test_n_4axis_submissions_qwen7b_2026-03-28_2338.json` | S029 ENGAGED ✅. S023 false CRISIS (abuela narrative misread). |
| Gemma 27B N-test | `test_n_4axis_submissions_gemma27b_cloud_2026-03-29_0907.json` | Run complete. Log findings to experiment_log. |
| Test Q (27B probes) | `test_q_27b_probes_2026-03-29_1111.json` | 4 probes. Q3 key finding: disability vocab mediates BURNOUT trigger, not non-linear structure. |
| Test K (enhancement) | `test_k_enhancement_comparison_multi_model_2026-03-29_1113.json` | step_flash_free (StepFun 196B) ranked #1. Venice quota status: check file. |

---

## Queue

### Now
- **Pipeline watching**: PID 15264 running. When it finishes, verify all stages complete.

### After pipeline completes

| Priority | Test | Command | Notes |
|----------|------|---------|-------|
| 1 (MLX) | Trajectory reports | `caffeinate -i python scripts/run_trajectory_tests.py --model gemma12b` | 4-6 hrs. Resume via phase flags. |
| 1 (cloud, parallel) | Test K retry if needed | `python3 scripts/run_alt_hypothesis_tests.py --tests K --no-subprocess` | Check 2026-03-29 K file first — may already be done. |

### Pending (no blocker)
- Log Test Q findings to `docs/research/experiment_log.md` — verified numbers needed
- Log Test K findings to experiment log
- Investigate TR04 hallucination (observation references "prior submission" that doesn't exist)

---

## Bugs fixed this sprint

| Bug | Fix | Commit |
|-----|-----|--------|
| LF06 DV under-classified as BURNOUT | CRISIS supersedes ENGAGED in classifier | 900e3ae |
| LF03 emotional engagement → false BURNOUT | BURNOUT anchored to material conditions | 6b009b5 |
| Observation preamble "Okay, here's what I'm noticing" | Extended regex in submission_coder.py | 900e3ae |
| Phase 3 crash: emotional_register as list | `_coerce_str()` in submission_coder.py | d677560 |
| `send_text()` arg order in Metal warmup | Fixed call signature in all 3 scripts | (uncommitted) |
| `_build_provenance()` NameError in Test Q | Changed to `_git_provenance()` | (uncommitted) |

---

## Active issues

### TR04 hallucination (INVESTIGATE)
Phase 1 observation for TR04-style student references "a prior submission" that doesn't exist.
Likely cause: class reading synthesizes all submissions; model infers longitudinal data.
May require prompt guard for trajectory context. Priority: investigate before trajectory tests launch.
See handoff doc for full notes.

### Phase 2 pre-fix prompts
Phase 2 ran on pre-fix prompts (launched before CRISIS supersedes commit). BIO-WB04 (brother's arrest) classified BURNOUT instead of CRISIS — expected to be fixed. Re-run optional, not blocking.

---

## Key findings for paper

1. **Format > model**: 4-axis format eliminates disparate impact on neurodivergent writers (S029: 25/25 FP binary → 9/9 correct 4-axis). Format change alone, no model change.
2. **Cross-domain equity transfer**: Phase 2 zero FPs on equity-critical STEM students — protections transfer without domain-specific prompt changes.
3. **Two-pass reduces FPs**: 6/7 corpus → 2/7 while maintaining sensitivity.
4. **Disability vocab mediates BURNOUT trigger** (Test Q, Q3): neurotypical student with identical structure + "exhausting to explain" = ENGAGED; disability vocab added = BURNOUT. Structural explanation ruled out.
5. **Qwen 7B limitation**: S023 false CRISIS (intergenerational narrative misread as student's own crisis). Model comprehension ceiling, not prompt issue. Document as lower-tier deployment limitation.
6. **step_flash_free (StepFun 196B MoE) > Gemma 27B free** for enhancement quality (Test K).

---

## For next agent

- Pipeline (PID 15264) may have finished by the time you read this. Check `ps aux` first.
- If pipeline done: verify run `0cb5b7e8` moved to DONE in InsightsStore, check all 11 stages completed.
- Then launch trajectory tests with caffeinate.
- Test Q and K findings still need to be logged to experiment_log.md.
- TR04 hallucination issue still open.
