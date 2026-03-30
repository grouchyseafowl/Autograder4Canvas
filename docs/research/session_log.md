# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-30, ~13:00)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **RUNNING** | Resumed ~13:00. Bug fixed: `run_partial()` now calls `complete_stage()`. Will run themes→outliers→synthesis→feedback. bj80omqw8. |
| ee5386e2 | 90005 (Chicano Studies/Biology, 25 subs) | **DONE** | All stages complete. 25/25 feedback drafted. Demo corpus content mismatch (biology.json uses placeholder phone/driving submissions). |

### Active background tasks

| Task | Status | Notes |
|------|--------|-------|
| `bj80omqw8` | **RUNNING** | 0cb5b7e8 resume via generate_demo_insights.py. On completion → trajectory tests. |

### What was done this session (morning)

1. Equity trajectory tests (b2yl0yqw4) COMPLETE — all 5 phases (A1–A4 + OBSERVATIONS).
2. Test P logged: 35/42 checks (83%), 7/12 students all-pass. Silence-after-disclosure: 9/9 ✓.
3. 0cb5b7e8 pipeline resumed (bj80omqw8). Fixed `run_partial()` bug last session.

---

## Queue — IN ORDER, DO NOT SKIP

### 1. WHEN bj80omqw8 NOTIFICATION FIRES — launch trajectory tests

```bash
caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b
```

Existing trajectory report corpus. Tests trajectory report generator (separate from equity tests).

### 2. Cloud tests available any time (no MLX needed)

- CHECK-IN definition fix for S029 (design needed — low priority)
- Immigration/racial identity vocabulary probes on 27B (design needed)
- Test P follow-up probes: P2 (timestamp in trajectory ctx), P3 (linguistic transfer framing), P4 (cross-phase observation synthesis)

---

## Test P key findings (2026-03-30)

**Equity trajectory tests — first end-to-end run. 35/42 checks (83%), 7/12 all-pass.**

| Risk area | Result | Note |
|-----------|--------|------|
| Silence-after-disclosure | **9/9** ✓ | Strongest area. All 3 disclosure types pass. |
| Linguistic voice development | 9/10 | Miss: ESL transfer not framed as intellectual stretch (E002) |
| Disability/variable output | 7/8 | 1 check: JSON parse failure (evaluator infra) |
| Working student patterns | 6/9 | 2 real gaps (see below) |
| Control | 4/6 | 2 unanswered evaluator checks (infra) |

**Two confirmed infrastructure gaps:**
1. **No timestamp data in trajectory context** — submission times not passed to observation prompt. `trajectory_ctx_*` checks cannot pass until fixed.
2. **No cross-phase observation synthesis** — A4 observation doesn't know A1/A2 baseline; can't contextualize return to quality.

**Evaluator reliability issue:** LLM evaluator confuses which observation belongs to which assignment when all 4 are presented simultaneously. E010 A4 explanation hallucinated A3 framing.

---

## Active findings requiring follow-up (for paper)

| Finding | Status | Next action |
|---------|--------|-------------|
| Silence-after-disclosure handling | **VALIDATED** Test P 9/9 | No action needed |
| ESL linguistic transfer not as intellectual stretch | OPEN | Add to observation prompt framing |
| Submission timestamp not in trajectory ctx | OPEN | Infrastructure fix needed |
| Cross-phase observation synthesis absent | OPEN | Design needed |
| CHECK-IN surveillance on neurodivergent identity (S029) | OPEN | Definition fix needed |
| Immigration/racial identity ablation on 27B | OPEN | Design needed |

---

## Key findings (complete, 2026-03-30)

1. **4-axis + format** (12B): Eliminates neurodivergent false-flags. Production path.
2. **Guard-v2**: Fixes disability-vocab trigger without over-suppressing metacommentary burnout.
3. **Minimized-disclosure guard**: Community resilience framing suppresses CRISIS; prompt-level fix restores it.
4. **Multi-axis vs single-axis**: Multi-axis wins on ENGAGED+CRISIS co-occurrence. Single-axis wins on S029.
5. **Evidence-extraction fails (Q5)**: Bias activates before task structure kicks in.
6. **Silence-after-disclosure solid**: 9/9 across deportation fear, racial violence, disability disclosure.
7. **Working student equity gap**: Two infrastructure fixes needed (timestamps, cross-phase context).

---

## For next agent

- **bj80omqw8 RUNNING**: 0cb5b7e8 resume. On completion → `caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b`
- **Equity tests DONE** (Test P logged). Key gaps: timestamp in trajectory ctx, cross-phase synthesis, ESL transfer framing.
- MLX queue is serial. Do not run two MLX tasks at once.
- **Test P raw output**: `data/research/raw_outputs/equity_observations_gemma12b_2026-03-30_1255.json`
