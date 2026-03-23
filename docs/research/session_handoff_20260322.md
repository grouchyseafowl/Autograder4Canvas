# Session Handoff — 2026-03-22

## Where We Are

We have a working system with a clear path to 3/3 concern detection, 0 false positives.

Llama 3.1 8B on MLX runs the full pipeline in ~80 min for 32 students:
- 0 equity false positives (S029 neurodivergent student protected)
- 1/3 concern detection in current pipeline (essentializing only)
- **BUT: confirmed that a focused/shorter concern prompt catches all 3 on the same model**
- 4/4 synthesis calls (5 highlights, 2 tensions, class temperature)
- Richer theme tags than Qwen ("code-switching as survival strategy")
- Truncation detection working (S002)

**The path to 3/3:** The full CONCERN_PROMPT (517 words) is too long for 8B — model
loses tone policing in the noise. Focused prompt (276 words) catches it. Fix: tier-
differentiated concern prompt (short for 8B, full for larger models).

The chatbot handoff (Gemini Pro) achieves 3/3, 0 FP with the tightened prompt.

## What's Committed

5 commits on main tonight:
1. `79b8bf4` — Code fixes: MLX default → Llama, truncation, synthesis fallback,
   meta-synthesis retry, handoff hardening, backend handlers
2. `e045fd1` — Research: paper notes, experiment log, prototype script
3. `21422bc` — Research: session audit, limitations, case study, evidence
4. `44b6d1f` — Llama as primary demo asset, v2 results, testing plan
5. `3eab1c7` — Tone policing findings, pairwise fix proposal, invisibility paradox

## What's Running (check results when you return)

1. **70B synthesis-first** (`/tmp/proto_70b_final.log`) — may have completed or
   exhausted retries on OpenRouter rate limit
2. **27B synthesis-first** (`/tmp/proto_27b_final.log`) — same
3. **Pairwise concern check** (`/tmp/pairwise_results.log`) — MLX Llama prototype
   testing whether showing Aiden alongside Destiny catches tone policing

## The Big Questions

### 1. Can we reach 3/3 concern detection on 8B?

**SOLVED (late night finding).** Root cause: prompt length. The full CONCERN_PROMPT
(517 words) buries tone policing in examples and "do NOT flag" instructions. A focused
prompt (276 words) catches S025 correctly on the same 8B model.

Fix: tier-differentiated concern prompt — short for lightweight (8B), full for medium/deep.
Not yet implemented. This is the Priority 1 code change for next session.

### 2. Can synthesis-first produce Gemini-level richness on 8B?

**Partially.** `what_student_is_reaching_for` descriptions are pedagogically useful.
But the class reading is generic compared to Gemini's output. Theme tags are richer in
standard Llama than in synthesis-first Llama. The architecture adds a new output type
(relational observations) rather than replacing the standard pipeline's outputs.

**Recommendation:** Multi-pass — standard for structured coding, synthesis-first for
relational observations. Not either/or but both.

### 3. What about theme fragmentation?

32 themes on Llama (worse than Qwen's 16). Meta-synthesis JSON fails on both 8B models.
**Not yet fixed.** Options: hierarchical merge (pairs of groups), reduced group count,
or cloud model for theme synthesis only (anonymized, FERPA-safe).

### 4. Is this a paper?

Yes. Core contribution: critical pedagogy frameworks applied as architectural design
principles produce measurably different results from the same small model. The tone
policing invisibility paradox is the theoretical centerpiece. The S029 case study
(pathologization → celebration across model configs) is the empirical centerpiece.

See `docs/research/synthesis_first_paper_notes.md` (500+ lines).

## Hidden Ideas Inventory

Tucked away across conversations, memory, and notes:

### In the architecture (not yet built)
- **Adversarial critic pass:** After concern flag, argue AGAINST flagging. Confirm only
  if critic can't counter. Would catch S029-type false positives. (memory file)
- **Reader-not-judge pipeline-wide:** Free-form observation first, JSON extraction second.
  The schema kills emergence. (memory file + paper notes)
- **Immanent critique prompting:** "What does this framing cost the people it describes?"
  Produces pedagogically sophisticated responses. (memory file)
- **Pairwise relational concern check:** Force model to evaluate student pairs, not
  individuals. Running tonight. (paper notes + prototype)
- **Attention directives:** Class reading produces explicit "look for X" instructions
  that modify per-student coding prompts. (parked — depends on pairwise results)
- **Absence detection:** If material warrants anger and no student expresses it, flag the
  absence. Counter to tone policing invisibility. (paper notes)

### In the pipeline (built, untested)
- **Cloud enhancement** (`_run_cloud_enhancement` in synthesizer.py): Anonymized
  patterns → larger cloud model for interpretive synthesis. FERPA-safe. Has OpenRouter
  credentials now.
- **Synthesis-only chatbot export** (`export_synthesis_only` in chatbot_export.py):
  Pre-coded records → chatbot does interpretive synthesis. Second handoff mode.
- **Cohort calibration** (Mechanism 1): Class-relative baselines via EMA. Designed,
  not implemented. Highest-impact gap for AIC.

### In the research (testing plan)
- **Replication runs** (3x each config) — is the complementary attention pattern reliable?
- **Second corpus** (AP Bio or Pre-Calc) — do universal readers generalize?
- **Teacher evaluation** — do teachers prefer synthesis-first outputs?
- **Prompt sensitivity analysis** — how fragile are the results to wording changes?
- **Scale isolation** — same architecture at 8B, 27B, 70B to separate contributions

### In the broader design
- **Bias mirror:** Show teachers their own correction patterns relative to student
  linguistic profiles. Built for audit, not yet surfaced as a feature. (paper notes,
  session 2026-03-22b)
- **Signal layer as equity infrastructure:** The VADER/GoEmotions suppression layer
  is itself an architectural intervention — documented in paper notes session b.
- **Teacher corrections don't feed back into detection.** Design decision: cohort
  baselines drive sensitivity, not teacher judgment. Prevents teacher bias from
  eroding protections. (paper notes, session b)

## Files to Check

| File | What's in it |
|---|---|
| `/tmp/pairwise_results.log` | Pairwise concern check results |
| `/tmp/proto_70b_final.log` | 70B synthesis-first (may be rate-limited) |
| `/tmp/proto_27b_final.log` | 27B synthesis-first (may be rate-limited) |
| `docs/research/synthesis_first_paper_notes.md` | Full paper notes (500+ lines) |
| `docs/research/experiment_log.md` | Chronological experiment record |
| `docs/research/testing_plan_next.md` | Prioritized next steps |
| `data/demo_baked/round2_8b_analysis.md` | Full analysis report with merge status |
| `memory/project_synthesis_first_architecture.md` | Architecture design + implementation path |
| `data/demo_baked/synthesis_first_*.json` | All prototype result files |
