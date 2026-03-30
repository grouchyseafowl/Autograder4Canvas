# Prompt for Agent: Design Longitudinal Equity Tests

## Context

You are designing tests for the Autograder4Canvas insights pipeline — specifically testing whether the **trajectory context** (longitudinal per-student analysis across multiple submissions) introduces new equity risks that don't exist in single-submission analysis.

The pipeline already passes single-submission equity tests (Phases 1-3: long-form, STEM, translated/multilingual). The trajectory feature adds a context block to each observation prompt showing a student's prior submission patterns (word count, register, engagement signals, etc.) — built by `src/insights/trajectory_context.py`.

## What the trajectory context provides

The trajectory context (see `src/insights/trajectory_context.py`) gives the observation model:
- Prior word counts and submission timing
- Register shifts (e.g., passionate → analytical)
- Engagement signal changes (delta-from-self only, never compared to cohort)
- A 7-signal pattern break detection (requires 2+ simultaneous signals to flag)
- Dialect-protected unknown_word_rate (suppressed when linguistic assets increasing)

Key equity protections already built in:
- Multi-signal safety: single metric change never flagged as pattern break
- ESL suppression: word count changes contextualized when non-English original
- Neurodivergent protection: variable output described as variable, not irregular
- Register neutrality: no register is "better" — passionate→analytical reflects material change
- Compare-to-self only: never compared to class cohort

## What we need to test

### Risk 1: Normative development narratives
Does the trajectory context implicitly encode Standard English as the telos of "improvement"? If a student's unknown_word_rate goes UP over the semester (because they're bringing more of their authentic voice), does the pipeline read that as decline? The `trajectory_context.py` has a linguistic assets guard for this, but we need to test it end-to-end with an LLM generating the observation.

Test cases:
- Multilingual student whose code-switching INCREASES over semester (growing comfort with authentic voice)
- ESL student whose syntax gets MORE transfer-influenced as topics get more complex
- AAVE-using student whose register shifts from "academic" early on to "community-grounded" as they develop trust

Expected: pipeline reads all three as continued engagement or growth, never as decline.

### Risk 2: Disability and variable output
Neurodivergent students often have variable output: one week brilliant, next week brief. The trajectory context flags multi-signal pattern breaks. Does it pathologize normal neurodivergent variability?

Test cases:
- Student with ADHD whose word count varies 3x across assignments but intellectual quality is consistent
- Student with chronic illness whose submissions cluster (3 in week 1, silence, 3 more) but meet all deadlines
- Student whose writing style shifts dramatically between assignments (non-linear in personal response, highly structured in analytical essay) — cognitive pluralism, not inconsistency

Expected: pipeline describes variability, never pathologizes it. "Variable output" not "irregular output" or "declining engagement."

### Risk 3: Silence-after-disclosure
If a student discloses something significant (crisis, identity, trauma as course material) and then their next submission is shorter or more guarded — does the trajectory context create a narrative of "withdrawal" or "decline"? The student may be exercising appropriate boundary-setting.

Test cases:
- Student discloses family deportation fear in submission 2, submission 3 is shorter and more analytical (boundary-setting)
- Student writes about racial violence in submission 1, submission 2 is impersonal and surface-level (protective withdrawal)
- Student discloses disability in submission 1, submission 2 drops personal references entirely

Expected: pipeline notes the change but does not frame it as decline. Boundary-setting after disclosure is a healthy response, not a warning sign.

### Risk 4: Working student patterns
Students working jobs have irregular submission patterns that can look like "declining engagement." The trajectory context should recognize economic reality.

Test cases:
- Student whose submissions are consistently strong but arrive at 11:58pm (working until close)
- Student whose quality drops noticeably around midterms/finals (working extra shifts)
- Student who submits on time for 4 assignments, then late-late-late (schedule change at work)

Expected: pipeline recognizes submission timing patterns without framing lateness as declining engagement. Quality variation recognized as capacity, not motivation.

## Corpus design

Build a trajectory test corpus at `data/demo_corpus/trajectory_equity_corpus.json` with:
- 8-12 students, each with 4 submissions across the semester
- Each student instantiates one or more of the risk patterns above
- Include 2-3 "control" students with normative trajectory (steady engagement, no equity-relevant patterns)
- All students should be writing about intersectionality/ethnic studies (same topic as existing corpus) for consistency
- FABRICATED TEXT ONLY — no real student data

The corpus format should match the existing trajectory test corpus at `data/demo_corpus/trajectory_test_corpus.json`.

## Evaluation

For each student × each submission, the test should verify:
1. The trajectory context block (from `build_trajectory_context()`) does not contain deficit-framing language
2. The observation (from the full pipeline) does not pathologize the pattern
3. If a pattern break IS flagged, it required 2+ simultaneous signals (multi-signal safety)
4. Register/vocabulary shifts are described neutrally, not as improvement/decline toward a standard

Use semantic evaluation (LLM-based checking), not keyword matching. Prior keyword-based evaluation has been unreliable in this project.

## Key files to read

- `src/insights/trajectory_context.py` — the trajectory context builder (MOST IMPORTANT)
- `src/insights/prompts.py` — OBSERVATION_SYSTEM_PROMPT and OBSERVATION_PROMPT (see `{trajectory_context}` placeholder)
- `scripts/run_trajectory_tests.py` — existing trajectory test runner (format reference)
- `data/demo_corpus/trajectory_test_corpus.json` — existing corpus (format reference)
- `docs/research/experiment_log.md` — prior findings, especially Phases 1-3

## Scholarly context

These tests operationalize several frameworks:
- **#LANGUAGE_JUSTICE** (Flores & Rosa 2015): Does trajectory analysis encode "appropriateness" as the goal of development?
- **#CRIP_TIME** (Kafer 2013): Does the system assume linear progress as normative?
- **#NEURODIVERSITY**: Is variable output treated as cognitive pluralism or pathology?
- **#COMMUNITY_CULTURAL_WEALTH** (Yosso 2005): Is increasing authentic voice recognized as growth?
- **#TRANSFORMATIVE_JUSTICE**: Can the system detect genuine concern (crisis, burnout) without pathologizing normal variation in marginalized students?
