# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-30, early morning)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **INCOMPLETE** | Themes may have crashed mid-run. Retry after ee5386e2 finishes. |
| ee5386e2 | 90005 (Chicano Studies, 25 subs) | **RUNNING** | Currently in observations stage (1/25). |

Pipeline background task `bgcfq9jb1` is still running. Notification will fire when done.

### What was done this session (evening into early morning)

1. Q4/Q5 probes, guard-v2, Test O 27B — all logged.
2. WB06 minimized-disclosure probe — W0 BURNOUT, W1 CRISIS, W2 CRISIS. Mechanism confirmed. Guard added.
3. Signal framing fix: "despite attempts to minimize" → prompt tells model to name material conditions directly without characterizing disclosure style. Updated all three prompts.
4. Pipeline launched — resumed 0cb5b7e8 (themes may have stalled), then auto-started ee5386e2 (90005 corpus fresh run). ee5386e2 currently in observations.

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
| Disability vocab → BURNOUT (S029, 27B) | FIXED — guard-v2 | Shipped |
| Metacommentary burnout suppressed (S002) | FIXED — guard-v2 revision | Shipped |
| Community resilience → BURNOUT underclass (WB06) | FIXED — minimized-disclosure guard | Shipped. Re-run Test N 27B to confirm |
| Signal text "attempts to minimize" framing | FIXED — prompt signal guidance | Shipped |
| CHECK-IN surveillance on neurodivergent identity disclosure (S029) | OPEN | Definition fix needed |
| Immigration/racial identity ablation on 27B | OPEN | Design needed |

---

## Key findings (complete, 2026-03-30)

1. **4-axis + format** (12B): Eliminates neurodivergent false-flags. Production path.
2. **Guard-v2**: Fixes disability-vocab trigger without over-suppressing metacommentary burnout.
3. **Minimized-disclosure guard**: Community resilience framing suppresses CRISIS; prompt-level fix restores it. Parallel mechanism to disability guard.
4. **Multi-axis vs single-axis**: Multi-axis wins on ENGAGED+CRISIS co-occurrence (WB06). Single-axis wins on S029 (no CHECK-IN surveillance). Neither is clearly dominant — depends on use case.
5. **Evidence-extraction fails (Q5)**: Bias activates before task structure kicks in.

---

## For next agent

- Monitor pipeline notification (`bgcfq9jb1`). On completion → launch equity trajectory tests immediately.
- Do NOT wait to read equity test output before launching — it's caffeinate MLX, will run for hours.
- After equity tests launch, run Test N 27B cloud to validate minimized-disclosure guard: `python3 scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess --model gemma27b_cloud`
- All current findings committed. Signal framing fix committed.
