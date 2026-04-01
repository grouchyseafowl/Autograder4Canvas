# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-04-01, ~12:45)

### Pipeline status

| Run | Course | Status | Notes |
|-----|--------|--------|-------|
| 0cb5b7e8 | 90003 (Ethnic Studies, 32 subs) | **DONE** | All stages complete. |
| ee5386e2 | 90005 (Biology, 25 subs) | **DONE** | Complete. |
| d3e2011c | 90005 (Biology fresh re-run) | **DONE** | Full pipeline re-run. |

### Active background tasks

| Task ID | Test | Phase | Progress | Notes |
|---------|------|-------|----------|-------|
| bps52a800 | P3 equity trajectory (16 students, `--run-id P3`) | A1 | 12/16 codings done | MLX Gemma 12B. caffeinate running. Expected ~4-6h total. |

**P3 InsightsStore state**: run `361411a0`, course `EQ_TEST_P3`, INCOMPLETE, 12 codings, 3 stages.

### Equity flags (`.equity_flags/`)
Empty — A1 still running.

### Trajectory flags (`.trajectory_flags/`)
A1.done, A2.done, A3.done, A4.done, REPORTS.done — from prior Test Q run. **Must `--reset-flags` before Q3 runs.**

---

## What was done this session (2026-04-01)

### Code changes (all committed)

1. **Isolation fix** (`run_equity_trajectory_tests.py`): `--run-id` arg sets unique `COURSE_ID = "EQ_TEST_<run_id>"` per run, passed through to subprocesses. Prevents `get_student_history()` bleeding prior run observations into current run. Test P2's 95% result was confounded by this — P2 had access to Test P's observations. P3 is the first clean replication.

2. **Linguistic transfer framing** (`src/insights/prompts.py`): Observation prompt now explicitly names L1 syntactic patterns as "evidence of INTELLECTUAL STRETCHING" and "epistemological resource, not just 'not a deficit.'" Targets E002 (Jin-Young, ESL transfer-not-as-stretch failure in Test P/P2).

3. **Continuity/return framing** (`src/insights/prompts.py`): Observation prompt instructs model to name return-to-baseline after a dip as continuity, not surprising recovery. Targets E010 (Tanya Reyes, a4_return_not_anomalous failure).

4. **CHECK-IN scope fix** (`src/insights/prompts.py`): `TARGETED_CHECKIN_SYSTEM` explicitly excludes identity-navigation fatigue ("exhausting to explain my identity") from CHECK-IN trigger. This was re-routing S029-type surveillance through a softer label.

5. **E013–E016 equity corpus** (`scripts/run_equity_trajectory_tests.py`): Four new students added — Fatima Al-Hassan (Arabic rhetorical transfer), Wei Chen (Mandarin conceptual compression), Lucía Mendoza (Spanish epistemic hedging), Reyna Santos (Tagalog relational framing). Tests the gap between "not penalizing multilingualism" and "recognizing multilingualism as epistemological resource." Full EVAL_QUESTIONS written for each.

6. **Evaluator hardening** (`run_equity_trajectory_tests.py`): Explicit check_id list in eval prompt, adaptive max_tokens (120/check), phantom-ID filtering.

7. **Q3 Teacher Notes fix** (`src/insights/prompts.py`): `TRAJECTORY_REPORT_PROMPT` Teacher Notes section now explicitly instructs LLM to surface lens_observations power move patterns and equity concerns — even when the student's intellectual work is strong. Targets T006 (Ingrid Johansson, tone policing missed).

8. **WB11–WB14 corpus** (`scripts/run_alt_hypothesis_tests.py`): Four new wellbeing cases testing community resilience guard across distinct community contexts: WB11 (Kaya Runningwater, Indigenous/tribal distribution), WB12 (Jasmine Rollins, Black church food pantry), WB13 (Amara Osei, Ghanaian susu rotating credit), WB14 (Marcus Tran, control — analytical writing about community wealth, no personal crisis). All stay in resilience register without meta-awareness; no bypass stress signals.

---

## Queue — IN ORDER (MLX serial constraint applies)

### 1. P3 — RUNNING (background bps52a800)

**What P3 tests**: Clean equity replication with:
- Isolation fix (EQ_TEST_P3 course_id, no history bleed)
- Linguistic transfer framing in observation prompt
- Continuity/return framing for E010
- 16 students: E001–E012 (original) + E013–E016 (linguistic transfer spectrum)

**When P3 finishes**: New monitor should read raw output JSON from `data/research/raw_outputs/equity_trajectory_*.json`. Look for:
- E002 (Jin-Young): does `esl_as_intellectual_stretch` check now pass? (stable fail in P and P2)
- E010 (Tanya): does `a4_return_not_anomalous` check pass? (was evaluator hallucination confound in P2)
- E013–E016: do the linguistic transfer checks pass? (first run — no prior data)
- E005 (Naomi Lee, disability): was unstable P→P2; check if clean run stabilizes
- Overall pass rate vs P (35/42, 83%) and P2 (53/56, 95% confounded)

Log results as **Test P3** in experiment log. Note isolation is clean (no prior run history).

### 2. Q3 — Trajectory report test (after P3, MLX)

**Before running**: `python3 scripts/run_trajectory_tests.py --model gemma12b --reset-flags`

Wait — need to reset trajectory flags first:
```bash
# Check/reset flags before running
ls data/research/raw_outputs/.trajectory_flags/
caffeinate -i python3 scripts/run_trajectory_tests.py --model gemma12b --reset-flags
```

**What Q3 tests**: Trajectory reports with Teacher Notes now explicitly using lens_observations. Targets T006 (tone policing for Ingrid Johansson). Also re-tests T002 (Jordan Kim specificity) and T008 since the linguistic transfer framing in observations may improve report specificity.

Log results as **Test Q3** in experiment log. Compare to Test Q (33/48, 69%).

### 3. Test N extension — cloud (can run ANYTIME, independent of MLX)

No MLX needed — runs on 27B via OpenRouter cloud.

```bash
python3 scripts/run_alt_hypothesis_tests.py --tests N --no-subprocess
```

**What it tests**: WB11–WB14 against community resilience guard. Expected: WB11/12/13 = CRISIS or BURNOUT (classifier sees through resilience framing); WB14 = ENGAGED (no false positive on analytical writing).

**Key question**: Does the guard generalize beyond Somali/mosque (WB06) to Indigenous tribal distribution, Black church pantry, and West African susu? If WB14 false-positive, the guard is over-firing on analytical writing about these topics.

Log as **Test N extension** in experiment log under Test N entry.

---

## Stable research findings (replicated, as of 2026-04-01)

| Finding | Test | Stability |
|---------|------|-----------|
| Silence-after-disclosure: 9/9 | P + P2 | **Replicated** — 3 disclosure types (deportation, racial violence, disability) |
| ESL transfer-not-as-stretch (E002) | P + P2 | **Replicated failure** — prompt fix in P3, awaiting clean test |
| AAVE/code-switching: solid | P + P2 | Replicated |
| Multilingual (Arabic/Mandarin/Spanish/Tagalog) | P2 | New — tested in P3 for first time with prompt fix |
| Disability/chronic illness | P vs P2 | Unstable — E005 pass→fail; P2 confounded, P3 will clarify |
| Working student timestamps: infra present | P3 | Infrastructure confirmed present (corpus has timestamps, trajectory context processes them) |
| Tone policing missed by trajectory report (T006) | Q | Single run — Q3 prompt fix applied |
| Community resilience guard (WB06) | Q4/Q5 | Single test — extensions WB11-14 pending |

---

## Key infrastructure notes for new monitor

- **MLX serial constraint**: Do NOT run two MLX tasks simultaneously. P3 must finish before Q3 starts.
- **Test N extension is cloud-safe**: Can run in parallel with P3 right now. Use `--no-subprocess`.
- **Trajectory flags are stale**: `.trajectory_flags/` has all phases done from prior Test Q run. Always `--reset-flags` before Q3.
- **Commit before leaving**: `git add docs/research/session_log.md docs/research/experiment_log.md src/ scripts/ && git commit -m "Research session $(date +%Y-%m-%d): [summary]"`
- **P2 confound documented**: Test P2's 95% rate is not reliable — `get_student_history()` pulled Test P's observations in. P3 is the clean baseline.
