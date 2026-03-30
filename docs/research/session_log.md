# Session Log — Autograder4Canvas Research Pipeline

**Dynamic state file.** Agents read this at startup. Write updates before leaving.
Old content gets archived to `docs/research/logs/` when > 200 lines.

---

## Current state (2026-03-29, late night)

### Pipeline status

| Process | Status | Notes |
|---------|--------|-------|
| Ethnic studies pipeline (0cb5b7e8) | **INCOMPLETE** | 32 codings, 7/11 stages. Waiting on MLX memory. |
| Test N guard-v2 (27B) | DONE | Logged |
| Test O 27B + guard-v2 | DONE | Logged |
| Trajectory equity tests | **Waiting on MLX** | Corpus + runner built, ready to launch |

### What was done this session (full evening)

1. Q4/Q5 probes: guard works, evidence-extraction fails. Logged.
2. Test N 27B post-guard-v1: S002 over-suppressed, WB06 downgraded. Guard scope problem identified.
3. Guard-v2 revision: changed "only material conditions" → explicit metacommentary list. Updated all three prompts (production + test script).
4. Test N 27B guard-v2: S029 ✓, S002 restored ✓, S031 fixed ✓. WB06 still BURNOUT — separate problem (minimized-disclosure + community resilience framing underclassification).
5. Test O 27B + guard-v2: 8/8 wellbeing caught, 0 FP. WB06 → CRISIS in multi-axis (multi-axis resolves single-axis BURNOUT failure). S029 ENGAGED + CHECK-IN (guard blocks BURNOUT, but CHECK-IN re-routes surveillance). Multi-axis vs single-axis tradeoff documented.
6. All runs logged with qualitative analysis.

---

## Queue

### MLX — when memory available

**Priority 1: Resume pipeline (0cb5b7e8)**
```bash
caffeinate -i python scripts/generate_demo_insights.py --resume
```
Remaining stages: themes, outliers, synthesis, feedback.

**Priority 2: Equity trajectory tests**
```bash
caffeinate -i python scripts/run_equity_trajectory_tests.py --model gemma12b
```
12 students × 4 submissions, 4 equity risk areas. LLM-semantic evaluation.

**Priority 3: Trajectory tests (existing corpus)**
```bash
caffeinate -i python scripts/run_trajectory_tests.py --model gemma12b
```

### Cloud — remaining design work

- **Minimized-disclosure probe**: Construct WB06 variant without resilience framing ("we are strong"). Confirm food insecurity alone → CRISIS. Then test prompt addition: "material conditions determine classification, not emotional register." n=1 ablation.
- **CHECK-IN disambiguation**: Define CHECK-IN to exclude identity-navigation exhaustion. Test with S029.
- **Identity vocabulary probes**: Immigration + racial identity ablations on 27B (design not written). Similar methodology to Test Q.

---

## Key findings (complete, 2026-03-29 evening)

1. **4-axis + format** eliminates neurodivergent false-flags on 12B. Root fix for production.
2. **Guard-v2** (targeted, not broad): fixes S029 disability-vocab trigger on 27B. Does not over-suppress metacommentary burnout. Shipped to all three prompts.
3. **Minimized-disclosure / community resilience underclassification**: WB06 food insecurity reads as BURNOUT in single-axis when student uses resilience framing. Multi-axis resolves this (WB06 → CRISIS). Independent from guard.
4. **Multi-axis wins on co-occurrence** (ENGAGED + CRISIS simultaneously). Loses on CHECK-IN over-surveillance of identity-navigating students (S029).
5. **CHECK-IN surveillance pathway**: Guard blocks BURNOUT for S029, but multi-axis adds CHECK-IN because "exhausting to explain" remains. Fix: exclude identity-navigation exhaustion from CHECK-IN trigger definition.
6. **Equity trajectory tests ready**: corpus and runner already built. 4 risk areas. MLX only.

---

## Unresolved equity issues (for paper + future tests)

| Issue | Mechanism | Tested | Fix direction |
|-------|-----------|--------|---------------|
| Disability vocab → BURNOUT (S029, 27B) | identity disclosure + emotional language | Test Q, guard-v2 | DONE — guard-v2 shipped |
| Metacommentary burnout suppressed (S002) | guard-v1 too broad | Test N guard comparison | DONE — guard-v2 fixed |
| Minimized-disclosure underclassification (WB06) | community resilience framing | Test N/O | Open — probe needed |
| CHECK-IN surveillance on identity disclosure (S029) | multi-axis bias toward CHECK-IN | Test O | Open — definition fix needed |
| Unknown: immigration/racial identity triggers | ablation not yet run | Not yet | Design needed |

---

## For next agent

- **MLX available**: run equity trajectory tests first (highest research value), then resume pipeline.
- **Cloud while waiting**: minimized-disclosure WB06 probe is fast (~3 min), high value.
- Guard-v2 is committed. All findings logged.
- `docs/research/longitudinal_test_design_prompt.md` is implemented — no need to re-design.
