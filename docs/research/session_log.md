# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-29, late evening — second session)

### Pipeline status

| Process | Status | Notes |
|---------|--------|-------|
| Ethnic studies pipeline (0cb5b7e8) | **INCOMPLETE** | 32 codings, 7/11 stages. Waiting on MLX memory. |
| Q4/Q5 probes | DONE | Logged |
| Test N re-run (27B, no guard, 19:28) | DONE | Logged — temperature variability, not guard |
| Test N 12B post-guard (21:07) | DONE | Logged — S023 CRISIS is variability; S031 fixed |
| Test N 27B post-guard (21:09) | DONE | Logged — guard works on S029; side effects found |
| Trajectory equity tests | **Waiting on MLX** | Corpus + runner already built |

### What was done this session

1. **Guard added to FOUR_AXIS_SUBMISSION_SYSTEM and MULTI_AXIS_SYSTEM** in `scripts/run_alt_hypothesis_tests.py`. Both now have the identity-disclosure guard paragraph.
2. **Test N 12B post-guard run** — ran MLX incidentally (memory available for 12B). S031 BURNOUT→ENGAGED (correct), S023 ENGAGED→CRISIS (temperature variability). Logged.
3. **Test N 27B post-guard run** — S029 ENGAGED ✓ (systematic, guard working). **Guard scope problem identified**: guard also suppresses S002 metacommentary burnout (unintended) and WB06 food-insecurity-as-crisis (expected trade-off). Full qualitative analysis logged.
4. **Guard revision proposed** in experiment log — narrower wording that preserves S029 protection without over-suppressing metacommentary burnout signals.
5. **Equity trajectory corpus + runner already exist** (`data/demo_corpus/trajectory_equity_corpus.json`, `scripts/run_equity_trajectory_tests.py`) — ready to run, waiting on MLX memory.

---

## Queue

### Next cloud test (no MLX, ~3 min)

**Option A: Test guard revision on 27B (probe only)**
Update guard wording in WELLBEING_CLASSIFIER_SYSTEM (production) and FOUR_AXIS_SUBMISSION_SYSTEM. Re-run Q4 probe to confirm S029 still ENGAGED. Run S002 as a new probe to confirm metacommentary burnout restored. This is a targeted fix before full re-run.

**Option B: Test O on 27B (multi-axis + guard)**
MULTI_AXIS_SYSTEM now has the guard. Run: `python3 scripts/run_alt_hypothesis_tests.py --tests O --no-subprocess --model gemma27b_cloud`
Tests whether CRISIS/BURNOUT/CHECK-IN/ENGAGED multi-axis classifier works better on 27B than 12B.

### Next MLX tests (when memory available)

**Priority 1: Resume pipeline (0cb5b7e8)**
```bash
caffeinate -i python scripts/generate_demo_insights.py --resume
```
Stages remaining: themes, outliers, synthesis, feedback (~4 stages).

**Priority 2: Equity trajectory tests**
```bash
caffeinate -i python scripts/run_equity_trajectory_tests.py --model gemma12b
```
All 4 risk areas: language justice, disability variability, silence-after-disclosure, working students. LLM semantic evaluation (not keyword matching). Corpus: 12 students × 4 submissions.

**Priority 3: Trajectory tests (existing corpus)**
```bash
caffeinate -i python scripts/run_trajectory_tests.py --model gemma12b
```

---

## Active issues

### Guard scope problem (IMPORTANT — do not ship current guard wording)
The current guard in WELLBEING_CLASSIFIER_SYSTEM (production) may suppress metacommentary burnout signals. S002 (trailing off late at night) classified ENGAGED with guard. Proposed revision is in experiment log under "Test N: Guard Integration" entry. Before deploying 27B for any production use, revise and test.

Guard coverage status:
| Prompt | Guard present | Status |
|--------|-------------|--------|
| `WELLBEING_CLASSIFIER_SYSTEM` (production, 12B path) | YES | Needs revision (scope too broad) |
| `FOUR_AXIS_SUBMISSION_SYSTEM` (Test N) | YES (just added) | Same issue |
| `MULTI_AXIS_SYSTEM` (Test O/future) | YES (just added) | Same issue |

### Pipeline incomplete (0cb5b7e8)
Waiting on MLX memory.

---

## Key findings (updated 2026-03-29 evening)

1. **Format > model (12B)**: 4-axis eliminates neurodivergent false-flags. Binary → 4-axis = only confirmed fix.
2. **Guard works on 27B (S029 → ENGAGED, systematic)**. But scope is too broad — also suppresses metacommentary burnout and identity-discrimination crisis signals. Needs targeted revision.
3. **Evidence-extraction fails (Q5)**: Bias activates in Step 1 before task structure can prevent it.
4. **Guard scope problem**: Material-conditions-only requirement encodes a disclosure register that is not culturally neutral. Students trained to minimize hardship produce metacommentary, not explicit conditions.
5. **Equity trajectory corpus + runner ready**: 12 students × 4 submissions, 4 risk areas, LLM-semantic eval. Waiting on MLX.

---

## For next agent

- **If MLX memory available**: run equity trajectory tests (`scripts/run_equity_trajectory_tests.py`), then resume pipeline.
- **Before that OR while waiting**: revise guard wording per experiment log proposal, run Q4 probe + S002 probe to confirm fix doesn't regress.
- Test O on 27B is available as a quick cloud run (MULTI_AXIS_SYSTEM has guard now).
- `docs/research/longitudinal_test_design_prompt.md` — already implemented, no need to re-design.
