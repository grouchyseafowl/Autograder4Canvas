# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-31, ~10:30)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **DONE** | All stages complete. Manually called complete_run(). Demo JSON baked 14:18 yesterday. |
| ee5386e2 | 90005 (Biology, 25 subs) | **DONE** | Complete. Demo corpus content mismatch (placeholder submissions). |
| d3e2011c | 90005 (Biology fresh re-run) | **DONE** | Full pipeline re-run with fixed run_partial(). |

### Active background tasks

None running.

### What was done this session (2026-03-30 evening – 2026-03-31 morning)

1. Equity trajectory tests (b2yl0yqw4) **COMPLETE** — Test P logged (35/42, 83%).
2. 0cb5b7e8 pipeline resumed (bj80omqw8) — all stages done, but missing `complete_run()`. Fixed + manually marked DONE.
3. Bug fixed: `run_partial()` now calls `complete_run()` at end.
4. Trajectory tests first attempt timed out (1800s) — fixed timeout (7200s) + `stop_after=observations`.
5. Trajectory tests **COMPLETE** (bc7sa5700) — Test Q logged (33/48, 69%).
6. Equity replication (blh0qcwtr) **COMPLETE** — Test P2 logged (53/56, 95%, expanded 16-student corpus).

---

## Queue — IN ORDER, DO NOT SKIP

### 1. Clean isolation replication (important methodological fix)

Before running another equity test, clear prior EQ_TEST_1 runs from store OR use a new course_id. P2 was confounded by P's history. Command TBD — need to either:
- Delete prior EQ_TEST_1 runs from InsightsStore before each run, OR
- Add `--isolation` flag to equity test script that uses a unique course_id per run

### 2. Cloud tests available any time (no MLX needed)

- CHECK-IN definition fix for S029 (design needed — low priority)
- Test Q2: Pass key quotes + assignment labels to report generator → rerun T002, T006, T008
- Test Q3: Add lens_observations power move flags to report generator → rerun T006

---

## Stable research findings (replicated, as of 2026-03-31)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 | **Replicated** — identical results in 2 independent coding runs |
| ESL transfer-not-as-stretch (E002) | P + P2 | **Replicated** — same failure, same explanation both runs |
| AAVE/code-switching: solid | P + P2 | Replicated |
| Multilingual (Arabic/Mandarin/Spanish/Tagalog): solid | P2 | New — needs cross-run validation |
| Disability/chronic illness: near-boundary | P vs P2 | Unstable — E005 pass→fail |
| Working student timestamps: infra gap | P | Confounded in P2 |
| Tone policing missed by trajectory report (T006) | Q | Single run |

## Key infrastructure bugs fixed this session

1. `run_partial()` never called `complete_run()` → completed_at never set
2. `run_trajectory_tests.py`: 1800s timeout too short → 7200s; missing `stop_after=observations`
3. `python` vs `python3` in queue command

---

## For next agent

- All tests done. No background tasks running.
- **Methodological issue**: P2 was confounded — `get_student_history()` pulled Test P's observations into P2 runs. Fix needed before clean replication.
- **Test Q trajectory reports** (33/48): three failure modes logged — specificity loss, structural context in wrong section, asset framing misses tone policing.
- **Test P/P2 stable findings**: silence-after-disclosure (9/9, replicated), ESL transfer gap (replicated), multilingual diversity strong.
- MLX serial constraint still applies. Do not run two MLX tasks at once.
