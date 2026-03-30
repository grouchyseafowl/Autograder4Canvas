# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-30, ~01:30)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **INCOMPLETE** | Themes stage: groups 1-7 generated, but meta-synthesis timed out twice (compact retry also failed at 00:51). Stage not marked complete. Retry after equity tests finish. |
| ee5386e2 | 90005 (Chicano Studies/Biology, 25 subs) | **DONE** | All stages complete. 25/25 feedback drafted. |

### Active background tasks

| Task | Status | Notes |
|------|--------|-------|
| `bo63hw52i` | **RUNNING** | Equity trajectory tests — `caffeinate -i python3 scripts/run_equity_trajectory_tests.py --model gemma12b`. MLX, will take hours. |

### What was done this session (evening into early morning)

1. Q4/Q5 probes, guard-v2, Test O 27B — all logged.
2. WB06 minimized-disclosure probe — W0 BURNOUT, W1 CRISIS, W2 CRISIS. Mechanism confirmed. Guard added.
3. Signal framing fix: "despite attempts to minimize" → prompt tells model to name material conditions directly without characterizing disclosure style. Updated all three prompts.
4. Pipeline launched — resumed 0cb5b7e8 (themes ran via _manual_merge but complete_stage never called — bug), ee5386e2 COMPLETED (25 subs, all stages, 11638s).
5. Test N 27B validated — WB06 → CRISIS, all guards holding. Logged.
6. Equity trajectory tests launched (MLX, gemma12b). Phase A1 running.
7. **Bug fixed in engine.py `run_partial()`**: never called `complete_stage()` — stages appeared incomplete forever. Also: fake `stages_run.append("synthesis")` claimed synthesis done without running it. Fixed: added `complete_stage()` after each stage, implemented synthesis + feedback in run_partial(), added "feedback" check to resume_run().

---

## Queue — IN ORDER, DO NOT SKIP

### 1. WHEN PIPELINE NOTIFICATION FIRES — immediately launch equity trajectory tests

```bash
caffeinate -i python3 scripts/run_equity_trajectory_tests.py --model gemma12b
```

12 students × 4 submissions, 4 equity risk areas (#LANGUAGE_JUSTICE, #CRIP_TIME, silence-after-disclosure, working students). LLM-semantic eval (NOT keyword rubric).

### 2. AFTER equity trajectory tests complete — retry 0cb5b7e8

```bash
caffeinate -i python3 scripts/generate_demo_insights.py
```

Will auto-detect 0cb5b7e8 as incomplete and resume from themes. If it fails again, check theme_generator.py for crash on group 5-7 (likely a long LLM response or timeout).

### 3. AFTER 0cb5b7e8 complete (OR while it runs if cloud-only) — trajectory tests

```bash
caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b
```

Existing trajectory report corpus. Tests trajectory report generator (separate from equity tests).

### 4. Cloud tests available any time (no MLX needed)

- Minimized-disclosure guard validation: re-run Test N 27B with updated prompts — does WB06 now classify as CRISIS? (~3 min)
- CHECK-IN definition fix for S029 (design needed — low priority)
- Immigration/racial identity vocabulary probes on 27B (design needed)

---

## Active findings requiring follow-up (for paper)

| Finding | Status | Next action |
|---------|--------|-------------|
| Disability vocab → BURNOUT (S029, 27B) | FIXED — guard-v2 | Shipped + validated Test N 2026-03-30 00:34 |
| Metacommentary burnout suppressed (S002) | FIXED — guard-v2 revision | Shipped + validated |
| Community resilience → BURNOUT underclass (WB06) | FIXED — minimized-disclosure guard | **VALIDATED** Test N 00:34: CRISIS conf=0.9, signal text clean |
| Signal text "attempts to minimize" framing | FIXED — prompt signal guidance | **VALIDATED** — WB06 signal now names material conditions only |
| CHECK-IN surveillance on neurodivergent identity disclosure (S029) | OPEN | Definition fix needed |
| Immigration/racial identity ablation on 27B | OPEN | Design needed |
| S031 minimal-effort → NONE (expected ENGAGED) | OPEN design question | Is NONE correct for no-signal submissions? Not equity-sensitive. |

---

## Key findings (complete, 2026-03-30)

1. **4-axis + format** (12B): Eliminates neurodivergent false-flags. Production path.
2. **Guard-v2**: Fixes disability-vocab trigger without over-suppressing metacommentary burnout.
3. **Minimized-disclosure guard**: Community resilience framing suppresses CRISIS; prompt-level fix restores it. Parallel mechanism to disability guard.
4. **Multi-axis vs single-axis**: Multi-axis wins on ENGAGED+CRISIS co-occurrence (WB06). Single-axis wins on S029 (no CHECK-IN surveillance). Neither is clearly dominant — depends on use case.
5. **Evidence-extraction fails (Q5)**: Bias activates before task structure kicks in.

---

## For next agent

- **Test N 27B validation COMPLETE** (00:34). WB06 → CRISIS ✓. All guards validated. Logged.
- **ee5386e2 COMPLETE**. **0cb5b7e8 still INCOMPLETE** — themes groups generated, meta-synthesis timed out (twice). Will resume after equity tests finish.
- **Equity trajectory tests RUNNING** (task `bo63hw52i`). On completion → retry 0cb5b7e8: `caffeinate -i python3 scripts/generate_demo_insights.py`
- After 0cb5b7e8 complete → trajectory tests: `caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b`
- MLX queue is sequential (GPU contention). Do not run two MLX tasks at once.
- **0cb5b7e8 `run_partial()` bug FIXED** in `src/insights/engine.py`. Next resume will correctly run themes→outliers→synthesis→feedback and mark each complete. Retry after equity tests finish.
- **Meta-synthesis orphaned thread**: when 300s timeout fires, the background thread calling `send_text()` continues running (Python threads can't be killed mid-execution). This is why "phantom" JSON parse warnings appear ~14min after the timeout — they're from the orphaned thread, already irrelevant. Not a crash, not a new failure. The pipeline correctly used `_manual_merge()` result.
