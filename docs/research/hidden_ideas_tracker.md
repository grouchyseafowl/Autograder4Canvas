# Hidden Ideas Tracker

These ideas were surfaced across sessions and kept getting deferred. This file
tracks their status so they don't fall off the edge.

---

## Ready to wire in (prompt/code written, waiting on test data)

### Adversarial Critic Pass
- **What:** After a concern flag, argue AGAINST it. Confirm only if critic can't counter.
- **Why:** Reduces false positives (S029 pathologization) AND stochastic flags.
- **Status:** `CONCERN_CRITIC_PROMPT` written in `prompts.py`. NOT wired into detection flow.
- **Waiting on:** Replication study frequency data. If FP rate is low without it, may not need it. If stochastic, wire it in.
- **Cost:** 1 additional LLM call per flagged student (cheap — only runs on flags).

### Immanent Critique Prompting
- **What:** "What does this framing cost the people it describes?"
- **Why:** Produces pedagogically sophisticated concern descriptions.
- **Status:** WIRED IN. Appended to every concern detection call via `+ CONCERN_IMMANENT_CRITIQUE_ADDENDUM` in `concern_detector.py`. Covers both main and resume paths.
- **Cost:** Zero additional calls — just enriches existing concern descriptions.

### Attention Directives
- **What:** Class reading produces explicit "look for X" instructions for per-student coding.
- **Why:** Focuses the model's attention on patterns the class reading surfaced.
- **Status:** NOT built. Would be an enhancement to `class_reader.py` output format.
- **Waiting on:** Decision on whether class reading is reliably useful (replication data).
- **Cost:** Zero additional calls — restructures existing class reading output.

## Tested, didn't work as designed

### Pairwise Relational Concern Check
- **What:** Show model two students side-by-side to detect relational harms.
- **Why:** Tone policing is relational — visible only in contrast.
- **Status:** Tested 2026-03-22. Control pairing also flagged — approach can't distinguish relational from non-relational context.
- **Outcome:** Class reading approach works better. Pairwise is retired.

## Built and working

### Cloud Enhancement (anonymized patterns → cloud model)
- **What:** Send anonymized patterns to a cloud model for richer synthesis.
- **Status:** `_run_cloud_enhancement()` in `synthesizer.py`. Tested 2026-03-23 — produced Gemini-level output.
- **Deployed:** Yes, triggers when `insights_cloud_url` + `insights_cloud_key` are set.

### Handoff Prompt Generator
- **What:** Generate anonymized prompt for teacher to paste into institutional chatbot.
- **Status:** `export_handoff_prompt()` in `chatbot_export.py`. Built 2026-03-23.
- **Deployed:** Yes.

### Disability Self-Advocacy Protection
- **What:** CONCERN_PROMPT explicitly protects disability disclosure as intellectual work.
- **Status:** Added to CONCERN_PROMPT 2026-03-23. Tested on Gemma 12B — S029 goes from FLAGGED to CLEAN.
- **Deployed:** Yes.

### Linguistic Note Injection in Concern Detection
- **What:** AAVE/multilingual/neurodivergent context notes flow into concern detection (not just coding).
- **Status:** Built in `engine.py` concern detection loop 2026-03-23.
- **Deployed:** Yes.

### Sentiment Suppression in Concern Detection
- **What:** When VADER is unreliable (AAVE/multilingual), mark signal matrix as unreliable in concern prompt.
- **Status:** Built in `engine.py` 2026-03-23. Tested — S028 Imani stays clean.
- **Deployed:** Yes.

## Not yet started (future)

### Absence Detection
- **What:** If material warrants anger and no student expresses it, flag the absence.
- **Why:** Counter to tone policing invisibility — the absence of expected emotion is itself a signal.
- **Status:** Idea only. Needs experiment design.

### Reader-Not-Judge Pipeline-Wide
- **What:** Free-form observation first, JSON extraction second — for ALL pipeline stages.
- **Why:** "The schema kills emergence." JSON-first prompts constrain what the model can notice.
- **Status:** Partially done (class reading IS free-form). Full version would restructure coding and concern detection.

### Cohort Calibration (Mechanism 1)
- **What:** Class-relative baselines via EMA. Sensitivity adapts to the cohort's linguistic profile.
- **Status:** Designed in AIC. Not implemented in insights pipeline.

### Bias Mirror
- **What:** Show teachers their own correction patterns relative to student linguistic profiles.
- **Status:** Designed. Not surfaced as a feature.

---

## Process Note

These ideas kept getting deferred because each session focused on infrastructure
and testing rather than feature building. To prevent this:
1. Check this file at session start
2. Pick ONE hidden idea to implement per session
3. Don't defer something twice without a documented reason
