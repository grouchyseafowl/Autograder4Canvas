# Pipeline Architecture Spec — Post-Testing Refinement

**Date**: 2026-03-28
**Source**: Test results A-N, experiment log, P1-P7 implementation session
**Status**: Ready for implementation. N×4 replication gate MET (100% stable).
Wait for P1-P7 pipeline re-run to finish before modifying engine.py.

---

## Overview

This spec describes the target pipeline architecture based on findings from
Tests A-N (2026-03-26 through 2026-03-28). The core change: replace binary
concern detection with a 4-axis wellbeing classifier running on raw
submissions alongside observations. This eliminates ~48 min of unreliable
LLM calls and fixes the two hardest equity failures (S029 neurodivergent
false-flag, S028 AAVE false-flag).

## Implementation order — TWO SEPARATE COMMITS

**Part 1** (this spec): Replace binary concern detector with 4-axis
classifier. Remove dead stages (deepening, guided synthesis). Rewire
feedback drafter. This is a direct replacement — same place in the
pipeline, different prompt and output schema.
- Gate: Test N replicated at n=3 (8/8, 0 FP, S029 ENGAGED). **MET.**
- Implement as one commit. Test independently before Part 2.

**Part 2** (future, NOT in this spec): Add a CHECK-IN pass for subtle
signals like S002 (burnout that presents as low engagement).
- Gate: Test O results show CHECK-IN fires on **ALL 17/17 students
  across all 3 runs.** It is completely non-discriminating. **GATE NOT
  MET.** The multi-axis approach (ENGAGED+CHECK-IN simultaneously) does
  not work — the model tags everyone for check-in.
- Test O also regressed on accuracy: Priya Sharma (control) and Yolanda
  Fuentes (lived experience) both get false CRISIS tags that Test N
  correctly avoids.
- **CHECK-IN needs redesign before it can be implemented.** Options:
  (a) Run CHECK-IN ONLY on ENGAGED students with specific signal
  patterns (short submissions, trailing off, apologies for quality) —
  narrower trigger. (b) Accept that S002-type subtle burnout requires
  longitudinal data (compare to prior submissions), not single-submission
  classification. See `project_longitudinal_trajectory.md`.
- Do NOT implement Part 2 until a working CHECK-IN design is validated.

**Critical constraint**: Don't modify the pipeline while it's running.
Wait for the current P1-P7 re-run to finish and produce output first.

---

## Target Pipeline (stages in order)

### Stage 1: Data Fetch
**Status**: Keep unchanged.

### Stage 2: Preprocessing (translation/transcription)
**Status**: Keep unchanged.

### Stage 3: Quick Analysis (non-LLM)
**Status**: Keep unchanged. Signal matrix, word counts, sentiment, clusters.
The signal matrix results are still used by theme generation and outlier
surfacing. They are no longer passed to concern detection (which is removed).

### Stage 3.5: Class Reading (synthesis-first)
**Status**: Keep unchanged. Produces class_reading text consumed by Stage 4
(coding) and Stage 5b (observations).

### Stage 4: Per-Submission Coding (reading-first)
**Status**: Keep. Now uses `code_submission_reading_first` (confirmed by
P1-P7 fixes). Produces `what_student_is_reaching_for`, `confusion_or_questions`,
`free_form_reading`, plus existing fields (theme_tags, notable_quotes,
emotional_register, etc.).

### ~~Stage 5: Concern Detection (binary)~~ → REMOVE
**Status**: REMOVE. 48 minutes of LLM calls producing unreliable output.
Test F (n=20): 100% false-flag on neurodivergent, 0% sensitivity on burnout.
Test M: production detector false-flags AAVE student, misses 3/8 burnout.

**What to do**: Delete the Stage 5 block from engine.py (lines ~911-1113).
Do NOT delete `concern_detector.py` yet — keep the file for reference during
transition. Remove the import and the loop.

**Signal matrix concern signals**: The non-LLM signal matrix
(`signal_matrix_classify`) in quick_analysis still produces keyword-based
concern signals. These should be KEPT as a non-LLM fallback layer —
they're fast, don't use the GPU, and provide a baseline signal. But they
no longer feed into an LLM concern detection call. Instead, they're
available to the wellbeing classifier and the feedback drafter as context.

### NEW Stage 5: Wellbeing Classifier (4-axis, sequential with 5b)
**Status**: NEW. Replaces binary concern detection.
**Gating**: Test N replicated at n=4 with 100% stability — every student
classifies identically across all 4 runs. Gate is MET. Proceed.

**Architecture**: Reads RAW SUBMISSION TEXT (not observations) with the
4-axis schema: CRISIS / BURNOUT / ENGAGED / NONE. Runs sequentially with
Stage 5b observations (MLX can only run one inference at a time on 16GB).
Both read raw submissions independently — neither reads the other's output.
Order doesn't matter; suggested: wellbeing first (shorter per-student),
then observations.

**Why raw text, not observations**: Test L showed that classifying
observations absorbs genuine signals into ENGAGED because the observation
text is already asset-framed. Test N showed 8/8, 0 FP on raw text. The
student's own words carry the signal directly: "I was watching the street
from my window" reads as CRISIS without interpretive framing.

**Exact prompt** (from `FOUR_AXIS_SUBMISSION_SYSTEM` in
`scripts/run_alt_hypothesis_tests.py`, line 2197 — the Test N prompt that
produced 8/8, 0 FP). Copy this verbatim into `src/insights/prompts.py`:

```python
WELLBEING_CLASSIFIER_SYSTEM = (
    "You are assessing a student's submission for their teacher.\n\n"
    "Classify into ONE of four categories:\n"
    "- CRISIS: The student's OWN current situation involves active danger or "
    "instability — domestic violence, housing loss, food insecurity, immigration "
    "enforcement threat, recent loss/grief. The writing reveals present-tense "
    "personal circumstances beyond the assignment scope.\n"
    "- BURNOUT: The student is depleted — exhaustion, overwork, caregiving burden, "
    "sleep deprivation. They're functioning but running on empty. Metacommentary "
    "about fatigue, trailing off, apologies for quality.\n"
    "- ENGAGED: The student is doing the assignment. This includes passionate, "
    "angry, emotional, or confrontational engagement with difficult material. "
    "Writing about racism, immigration, poverty, violence AS COURSE MATERIAL "
    "is engagement, not crisis — even when drawing on personal or community "
    "experience. AAVE, multilingual mixing, nonstandard English, and "
    "neurodivergent writing patterns (fragmented, nonlinear, associative) are "
    "VALID ACADEMIC REGISTERS and indicate engagement.\n"
    "- NONE: Insufficient text or off-topic.\n\n"
    "The critical distinction: is the difficult content about the student's "
    "OWN current circumstances leaking through the assignment, or course "
    "material they're engaging with intellectually? The former is CRISIS/BURNOUT; "
    "the latter is ENGAGED.\n\n"
    "Respond with JSON only: {\"axis\": \"CRISIS\"|\"BURNOUT\"|\"ENGAGED\"|\"NONE\", "
    "\"signal\": \"brief description\", \"confidence\": 0.0-1.0}"
)

WELLBEING_CLASSIFIER_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Classify this submission. Respond with JSON only."""
```

**Implementation** — add to `src/insights/submission_coder.py`:

```python
def classify_wellbeing(
    backend: BackendConfig,
    student_name: str,
    submission_text: str,
    *,
    max_tokens: int = 150,
) -> dict:
    """Classify a student's submission on the 4-axis wellbeing schema.

    Returns dict with keys: axis, signal, confidence.
    Returns {"axis": "NONE", "signal": "", "confidence": 0.0} on failure.
    """
    from insights.prompts import (
        WELLBEING_CLASSIFIER_SYSTEM, WELLBEING_CLASSIFIER_PROMPT
    )

    wc = len(submission_text.split())
    if wc < 15:
        return {"axis": "NONE", "signal": "Too brief", "confidence": 0.0}

    prompt = WELLBEING_CLASSIFIER_PROMPT.format(
        student_name=student_name,
        submission_text=submission_text,
    )

    try:
        raw = send_text(backend, prompt, WELLBEING_CLASSIFIER_SYSTEM,
                        max_tokens=max_tokens)
        parsed = _parse_response(raw, student_name, "wellbeing")

        axis = parsed.get("axis", "NONE")
        if axis not in ("CRISIS", "BURNOUT", "ENGAGED", "NONE"):
            log.warning("Unexpected wellbeing axis '%s' for %s", axis, student_name)
            axis = "NONE"

        return {
            "axis": axis,
            "signal": parsed.get("signal", ""),
            "confidence": float(parsed.get("confidence", 0.0)),
        }
    except Exception as exc:
        log.warning("Wellbeing classification failed for %s: %s", student_name, exc)
        return {"axis": "NONE", "signal": "", "confidence": 0.0}
```

**Output fields** — add to `SubmissionCodingRecord` in `models.py`:
```python
# Wellbeing classifier (4-axis, reads raw submission)
wellbeing_axis: Optional[str] = None       # "CRISIS"|"BURNOUT"|"ENGAGED"|"NONE"
wellbeing_signal: Optional[str] = None     # brief LLM description
wellbeing_confidence: float = 0.0          # 0.0-1.0
```

**Store compatibility**: The `InsightsStore.save_coding()` already
serializes the full `SubmissionCodingRecord` as JSON. New fields are
`Optional` with defaults — backward compatible with existing stored runs.
No schema migration needed.

**Teacher-facing behavior**:
- CRISIS (confidence ≥ 0.7): Surface as alert banner in student detail view.
  Teacher sees the observation (rich prose) + the alert (structured signal).
- BURNOUT (confidence ≥ 0.7): Surface as softer notice (not a banner —
  more like a margin note). Burnout warrants accommodation, not alarm.
- ENGAGED / NONE: No alert. The observation speaks for itself.

**Timing estimate**: ~30s per student × 32 = ~16 min. Faster than old
concern detection (~48 min) because the prompt is simpler (single JSON
response, no multi-pass).

**Verification after implementation** (OPUS-level review recommended):
1. Run `classify_wellbeing()` on S029 (neurodivergent) → must return ENGAGED
2. Run on S028 (AAVE) → must return ENGAGED
3. Run on WB01 Rosa (ICE stress) → must return CRISIS or BURNOUT
4. Run on WB09 Priya Sharma (control) → must return ENGAGED
5. Run on WB10 DeAndre (control) → must return ENGAGED or NONE
6. If ANY of checks 1-2 return CRISIS/BURNOUT, STOP — the prompt needs
   revision before proceeding. These are the students who bear the cost
   of misclassification.
7. Run full pipeline and spot-check 5 random students' wellbeing_axis
   against their observation text — do they align qualitatively?

### ~~Stage 4b: Deepening Pass~~ → REMOVE
**Status**: REMOVE. Depends entirely on Stage 5 concern flags. With
concerns removed, there are no flagged students to deepen. The deepening
pass's functions (rhetorical strategy naming, register reconsideration)
are now handled by:
- Observations (Stage 5b): describe rhetorical strategies in prose
- Structural naming in observation prompt: names mechanisms directly
- The wellbeing classifier handles the "is this engagement or distress"
  question that deepening was trying to answer

**What to do**: Delete the Stage 4b block from engine.py (lines ~1173-1300).
Delete `code_deepening` function from submission_coder.py if it exists.

### Stage 5b: Per-Student Observations
**Status**: Keep. Validated 32/32. Now includes P1-P7 prompt fixes
(structural naming, preamble stripping, anti-spotlighting).

Runs sequentially with new Stage 5 (wellbeing classifier). Both read raw
submissions independently. The observation produces teacher-facing prose;
the classifier produces structured signals.

### Stage 6: Theme Generation
**Status**: Keep unchanged.

### Stage 7: Outlier Surfacing
**Status**: Keep unchanged.

### ~~Stage 8: Guided Synthesis (concern-based)~~ → REMOVE
**Status**: REMOVE. Reads concern flags that no longer exist. The 4 calls:
1. Concern Pattern Analysis → reads `r.concerns` → dead
2. Engagement Highlights → reads strong engagers → partially alive
3. Tension Surfacing → reads concern + engagement data → dead input
4. Class Temperature → reads flagged_count, etc. → dead input

Stage 8b (observation-based synthesis) replaces this entirely. It produces
all 9 sections (class temperature, threads, exceptional contributions,
check-ins, multiplicity, pedagogical wins, moments, structural moves,
forward-looking) from observation data.

**What to do**: Remove the Stage 8 block from engine.py (lines ~1372-1401).
Keep `synthesizer.py` functions for reference but they should not be called.
The `guided_synthesis()` function can be deprecated.

**Cloud enhancement rewiring**: `_run_cloud_enhancement()` in
`synthesizer.py` (line ~695) currently takes a `GuidedSynthesisResult`
and extracts `concern_patterns`, `engagement_highlights`, `tensions`,
`class_temperature` to build the anonymized payload. With guided
synthesis removed, the enhancement should read the observation synthesis
text (markdown) instead. The simplest approach:

1. Parse the observation synthesis markdown for section headers
   (Class Temperature, Exceptional Contributions, Structural Power
   Moves, etc.)
2. Build the anonymized payload from these sections — the observation
   synthesis already uses student names, so `_validate_no_student_data()`
   must scan and strip them before sending.
3. Alternatively: generate a NEW anonymized summary from coding records
   (aggregate engagement patterns, wellbeing axis distribution, theme
   tags) and send that. This avoids parsing markdown.

**Recommendation**: Option 3 is more robust. Build a
`_build_enhancement_payload(coding_records, obs_synthesis_text)` function
that produces the same anonymized pattern format Test K validated on.
The `_validate_no_student_data()` check still runs before any cloud call.

**This is OPUS-level work** — the anonymization boundary is a FERPA
compliance point. The implementing agent should verify: no student names,
IDs, or verbatim quotes cross the wire. Test by printing the payload
and scanning for any name from the corpus.

### Stage 8b: Observation-Based Synthesis → rename to Stage 8
**Status**: Keep. Becomes the only synthesis stage. Already includes P2-P7
additions (multiplicity, pedagogical wins, forward-looking, elevated
insights ranking, anti-spotlighting).

### Stage 9: Draft Feedback
**Status**: Keep, with rewiring.

**Current behavior**: `_build_concern_context()` in feedback_drafter.py
reads `record.concerns` to:
1. Adjust tone (warmer for flagged students)
2. Avoid praising flagged behavior (e.g., don't validate colorblind framing)
3. Steer toward growth in flagged area

**Rewiring needed**: Replace concern data with wellbeing + observation data:
1. **Tone adjustment**: Read `wellbeing_axis`. If CRISIS or BURNOUT, draft
   with extra warmth and no performance pressure (same intent as current
   concern-aware drafting).
2. **Avoid praising harmful behavior**: Read `observation` text. If the
   observation names a structural power move (tone policing, colorblind
   erasure), the feedback drafter should not validate that behavior.
   The observation already contains this information in prose.
3. **Steer toward growth**: The `what_student_is_reaching_for` field
   (now populated by reading-first coding) tells the drafter what the
   student IS doing well and where they're heading — use this as the
   growth direction.

**Implementation**: Rewrite `_build_concern_context()` to `_build_wellbeing_context()`.
Pass the full observation text to the feedback LLM — it can read the
observation for structural moves rather than relying on fragile string
matching. The LLM is better at detecting "the observation noted tone
policing" than regex.

```python
def _build_wellbeing_context(record: dict) -> str:
    """Build context for wellbeing-aware and observation-aware feedback drafting.

    Replaces _build_concern_context(). Reads wellbeing classifier output
    + observation prose instead of binary concern flags.
    """
    axis = record.get("wellbeing_axis", "NONE")
    observation = record.get("observation", "")
    reaching_for = record.get("what_student_is_reaching_for", "")

    parts = []

    # Wellbeing-aware tone
    if axis in ("CRISIS", "BURNOUT"):
        parts.append(
            "WELLBEING-AWARE DRAFTING: This student shows signs of "
            f"{axis.lower()}. Write with extra warmth. Do NOT add "
            "performance pressure. Do NOT reference the wellbeing "
            "signal — the student should see only a supportive comment."
        )

    # Pass observation for structural move awareness
    # The LLM reads the observation to know if tone policing, colorblind
    # erasure, or other structural moves were identified — and avoids
    # validating them in the feedback.
    if observation:
        parts.append(
            f"OBSERVATION CONTEXT (for your awareness, NOT for the student):\n"
            f"{observation}\n\n"
            "If this observation identifies a structural power move (tone "
            "policing, colorblind erasure, etc.), do NOT validate or praise "
            "that framing in your feedback. Redirect gently toward deeper "
            "engagement with the structural analysis."
        )

    # Growth direction from reading-first coding
    if reaching_for:
        parts.append(f"GROWTH DIRECTION: {reaching_for}")

    return "\n\n".join(parts) if parts else ""
```

**Callers to update**: In `feedback_drafter.py`, find every call to
`_build_concern_context(record_dict)` and replace with
`_build_wellbeing_context(record_dict)`. Also update the import in
`engine.py` Stage 9 if it imports this function directly.

**Verification**: After implementation, generate feedback for:
1. S018 Connor (colorblind) → feedback should NOT say "great point about
   treating everyone equally." Should redirect toward structural analysis.
2. S025 Aiden (tone policing) → feedback should NOT validate "keeping
   discussion calm." Should acknowledge engagement while redirecting.
3. WB01 Rosa (CRISIS) → feedback should be warm, no performance pressure.
4. S004 Priya (ENGAGED, strong) → feedback should be substantive, reference
   specific intellectual moves from reaching_for.
5. S029 Jordan (neurodivergent, ENGAGED) → feedback should NOT reference
   writing style as a problem. Should affirm intellectual work.

---

## Files to modify

| File | Change | Effort |
|------|--------|--------|
| `src/insights/engine.py` | Remove Stage 5 (concern detection), Stage 4b (deepening), Stage 8 (guided synthesis). Add new Stage 5 (wellbeing classifier). Rename 8b → 8. Rewire cloud enhancement. | Large |
| `src/insights/models.py` | Add `wellbeing_axis`, `wellbeing_signal`, `wellbeing_confidence` to SubmissionCodingRecord | Small |
| `src/insights/prompts.py` | Add WELLBEING_CLASSIFIER_SYSTEM and WELLBEING_CLASSIFIER_PROMPT (from Test N) | Small |
| `src/insights/feedback_drafter.py` | Rewrite `_build_concern_context()` → `_build_wellbeing_context()` | Medium |
| `src/insights/synthesizer.py` | Deprecate `guided_synthesis()`. Rewire `_run_cloud_enhancement()` to read observation synthesis. | Medium |
| `src/insights/concern_detector.py` | Do not delete yet. Mark as deprecated. Remove imports from engine.py. | Small |
| `src/insights/submission_coder.py` | Add `classify_wellbeing()` function (the 4-axis classifier). Parallels `observe_student()`. | Medium |

---

## What NOT to change yet

- **Theme generation (Stage 6)**: Still reads coding records. Works fine.
- **Outlier surfacing (Stage 7)**: Same — reads coding records.
- **Chatbot export**: The handoff prompt system works independently. The
  enhancement UX (Gemma 27B / Mistral Small / browser) is a separate spec.
- **AIC integration**: Not affected by this change.
- **Signal matrix**: Kept as non-LLM fallback. Just no longer feeds into
  a dedicated LLM concern call.

## GUI impact — what the implementing agent needs to know

The GUI reads `record.concerns` (a list of `ConcernRecord` objects) to
display concern cards in the student detail view. After this change,
`record.concerns` will always be an empty list for new runs.

**What to do**:
- The student detail view should display `wellbeing_axis` and
  `wellbeing_signal` instead of concern cards. CRISIS/BURNOUT get
  visual prominence; ENGAGED/NONE do not.
- Old runs in the store still have `concerns` data — the GUI should
  gracefully handle both old (concerns) and new (wellbeing) formats.
  Check: if `wellbeing_axis` is present, show wellbeing UI. If only
  `concerns` is present, show legacy concern cards.
- The observation text (`record.observation`) is the primary teacher-
  facing content. The wellbeing signal supplements it with a structured
  routing indicator, not a replacement.

**This is a separate task from the pipeline refactor.** The pipeline
can ship without the GUI update — the data will be in the store, the
GUI just won't display the new fields until updated.

## Stage numbering note

The engine.py code comments use "Stage 5" for concern detection and
"Stage 5b" for observations. This spec follows that numbering. The
other agent's notes may reference "Stage 3" for concern detection —
that refers to the engine's `complete_stage(run_id, "concerns")` call
which uses a string label, not the comment number. Both refer to the
same code block (~lines 911-1113 in engine.py).

---

## Validation checklist (after implementation)

1. Run full pipeline with 4-axis classifier on ethnic_studies corpus
2. Verify all 32 students get wellbeing_axis classification
3. Check S029 (neurodivergent) → should be ENGAGED, not CRISIS/BURNOUT
4. Check S028 (AAVE) → should be ENGAGED
5. Verify feedback drafts for CRISIS/BURNOUT students have warmer tone
6. Verify feedback drafts for structural-move students don't validate
   the flagged behavior
7. Verify observation synthesis still produces all 9 sections
8. Verify cloud enhancement works with observation synthesis data
9. Compare total pipeline time — should be ~48 min faster (concern
   detection removed, wellbeing ~16 min, net savings ~32 min)

---

## Timing impact estimate

| Stage | Old time | New time | Change |
|-------|----------|----------|--------|
| Stage 5 (concerns) | ~48 min | 0 | **Removed** |
| Stage 4b (deepening) | ~5 min | 0 | **Removed** |
| Stage 8 (guided synthesis) | ~5 min | 0 | **Removed** |
| NEW Stage 5 (wellbeing) | 0 | ~16 min | **Added** |
| **Net change** | | | **~42 min saved** |

Total pipeline estimate: ~80 min coding + ~16 min wellbeing + ~35 min
observations + ~22 min themes + ~7 min outliers + ~5 min synthesis +
~25 min feedback = **~190 min** (was ~270 min). Significant improvement.

---

## Test evidence summary

| Test | Finding | Implication |
|------|---------|-------------|
| F (n=20) | Binary 100% FP on S029, 0% on S002 | Binary must go |
| M | Production detector: 5/8 signals, 2 FP (Imani, DeAndre) | Production detector also broken |
| I | 3-axis on observations: 8/8, 1 FP (Priya) | Observations good but 3-axis FPs |
| L | 4-axis on observations: 4/8, 0 FP | ENGAGED absorbs signals — don't classify observations |
| **N (n=4)** | **4-axis on raw submissions: 8/8, 0 FP, 100% stable** | **Ship this. Gate met.** |
| O (n=3) | Multi-axis CHECK-IN: fires 17/17 students, 100% over-fire | CHECK-IN needs redesign. Gate NOT met. |
| J | P1-P7 fixes validated at 12B | Prompt changes work |
| K | Gemma 27B best enhancement, Mistral Small best privacy | Enhancement tier validated |

### Test N replication detail (the gate for Part 1)

4 runs, temperature 0.3, all 17 students. **Every classification
identical across all 4 runs.** Zero variance.

| Student | Type | N run 1 | N run 2 | N run 3 | N run 4 |
|---------|------|---------|---------|---------|---------|
| S029 Jordan E. | neurodivergent | ENGAGED | ENGAGED | ENGAGED | ENGAGED |
| S028 Imani D. | AAVE | ENGAGED | ENGAGED | ENGAGED | ENGAGED |
| Rosa Gutierrez | ICE stress | CRISIS | CRISIS | CRISIS | CRISIS |
| Keisha Williams | caregiving | BURNOUT | BURNOUT | BURNOUT | BURNOUT |
| Priya Sharma | control | ENGAGED | ENGAGED | ENGAGED | ENGAGED |
| DeAndre Washington | control | ENGAGED | ENGAGED | ENGAGED | ENGAGED |

(All 17 students stable — table shows equity-critical subset.)

**Notable: Marcus Bell (minimal_effort) classifies as BURNOUT** across
all 4 runs. The classifier reads his brevity as depletion rather than
disengagement. This is arguably a better default than "lazy" — a teacher
checking in about capacity is a more appropriate response than assuming
disengagement. The observation carries the qualitative detail for the
teacher to judge. Not a bug; worth noting for the paper.

**N×4 replication gate: MET.** Proceed with Part 1.

---

## Implementation sequence — with model switches

### Phase 1: Mechanical changes (Sonnet)

These are deletions, additions, and copies. No judgment calls.

1. Add `wellbeing_axis`, `wellbeing_signal`, `wellbeing_confidence` fields
   to `SubmissionCodingRecord` in `src/insights/models.py`
2. Add `WELLBEING_CLASSIFIER_SYSTEM` and `WELLBEING_CLASSIFIER_PROMPT` to
   `src/insights/prompts.py` (copy verbatim from this spec)
3. Add `classify_wellbeing()` function to `src/insights/submission_coder.py`
   (copy from this spec, follows `observe_student()` pattern)
4. In `src/insights/engine.py`:
   a. Remove Stage 5 block (concern detection, lines ~911-1113)
   b. Remove Stage 4b block (deepening pass, lines ~1173-1300)
   c. Remove Stage 8 block (guided synthesis, lines ~1372-1401)
   d. Add new Stage 5 (wellbeing classifier loop — follows observation
      stage pattern: loop over students, call `classify_wellbeing()`,
      store results on record)
   e. Rename Stage 8b comment to Stage 8
5. Run syntax verification:
   ```
   python -c "from insights.engine import InsightsEngine"
   python -c "from insights.submission_coder import classify_wellbeing"
   python -c "from insights.models import SubmissionCodingRecord; r = SubmissionCodingRecord(student_id='t', student_name='t', wellbeing_axis='ENGAGED')"
   ```

**After Phase 1, STOP.**

Tell the user:
> Phase 1 complete — mechanical changes done. Stage removals and additions
> are in place. Syntax verified. Before proceeding to Phase 2 (equity-
> critical rewiring), switch to Opus: type `/model opus` or start a new
> session with Opus. Phase 2 requires judgment about feedback framing,
> FERPA compliance, and equity verification.

### Phase 2: Equity-critical rewiring (Opus)

These require understanding WHY each decision was made.

6. Rewrite `_build_concern_context()` → `_build_wellbeing_context()` in
   `feedback_drafter.py` using the implementation in this spec. Key: the
   observation text is passed as context so the LLM can read it for
   structural power moves — no fragile string matching.
7. Update all callers of `_build_concern_context()` in feedback_drafter.py
   and engine.py Stage 9.
8. Rewire cloud enhancement (`_run_cloud_enhancement()` in synthesizer.py)
   to read observation synthesis data instead of guided synthesis. Build
   new anonymized payload. **FERPA boundary — verify no student names
   cross the wire.** Print the payload and scan.
9. Deprecate `guided_synthesis()` (add docstring warning, don't delete).
10. Run behavioral verification:
    - Classify S029 (neurodivergent) → must be ENGAGED
    - Classify S028 (AAVE) → must be ENGAGED
    - Classify WB01 Rosa → must be CRISIS or BURNOUT
    - Generate feedback for S018 Connor → must NOT validate colorblind framing
    - Generate feedback for WB01 Rosa → warm tone, no performance pressure
    - If S029 or S028 return CRISIS/BURNOUT: **STOP. Do not proceed.**
11. Run full pipeline on ethnic_studies corpus. Spot-check 5 random students.
12. Verify baked JSON compatibility with existing GUI panels.
13. Commit as: "Replace concern detection with 4-axis wellbeing classifier"

## Task difficulty and agent assignment

| Task | Difficulty | Agent | Why |
|------|-----------|-------|-----|
| Add model fields (models.py) | Easy | Sonnet | Mechanical — add 3 Optional fields |
| Add prompts (prompts.py) | Easy | Sonnet | Copy from spec verbatim |
| Add `classify_wellbeing()` (submission_coder.py) | Medium | Sonnet | Follows `observe_student()` pattern, code provided in spec |
| Remove Stage 5 from engine.py | Medium | Sonnet | Delete block, but verify nothing else references it |
| Remove Stage 4b from engine.py | Easy | Sonnet | Delete block, standalone |
| Remove Stage 8 from engine.py | Medium | Sonnet | Must verify Stage 8b still runs and is renamed |
| Add new Stage 5 to engine.py | Medium | Sonnet | Follows observation stage pattern — loop over students, call function, store results |
| Rewire feedback drafter | Medium | **Opus** | Equity-critical: must not validate structural moves, must not reveal wellbeing signals to students. The observation-as-context approach needs careful prompt crafting. |
| Rewire cloud enhancement | Hard | **Opus** | FERPA compliance boundary. Anonymization must be verified. Building the new payload from obs synthesis or coding records needs architectural judgment. |
| Verify S029/S028 safety | Critical | **Opus** | These are the students who bear the cost of misclassification. The checks in the verification section must pass before any deployment. |
| Integration testing | Hard | **Opus** | Full pipeline run, spot-check outputs, verify timing, check store compatibility |

---

## QC checklist — run BEFORE considering this done

**Syntax/import verification** (Sonnet can do):
- [ ] `python -c "from insights.engine import InsightsEngine"` succeeds
- [ ] `python -c "from insights.submission_coder import classify_wellbeing"` succeeds
- [ ] `python -c "from insights.models import SubmissionCodingRecord; r = SubmissionCodingRecord(student_id='t', student_name='t', wellbeing_axis='ENGAGED')"` succeeds
- [ ] `python -c "from insights.prompts import WELLBEING_CLASSIFIER_SYSTEM"` succeeds

**Behavioral verification** (Opus should review):
- [ ] S029 (neurodivergent) classifies as ENGAGED — not CRISIS or BURNOUT
- [ ] S028 (AAVE) classifies as ENGAGED — not CRISIS or BURNOUT
- [ ] WB01 Rosa (ICE stress) classifies as CRISIS or BURNOUT
- [ ] WB09 Priya Sharma (analytical control) classifies as ENGAGED
- [ ] Feedback for Connor (colorblind) does NOT validate "treating everyone the same"
- [ ] Feedback for Rosa (CRISIS) has warm tone, no performance pressure
- [ ] Cloud enhancement payload contains NO student names (print and scan)

**Regression checks**:
- [ ] Observation synthesis still produces all 9 sections
- [ ] Theme generation still works (reads coding records, not concerns)
- [ ] Outlier surfacing still works
- [ ] Pipeline completes without error on ethnic_studies corpus
- [ ] Baked JSON structure compatible with GUI (check existing panels)

**Dead code verification**:
- [ ] No remaining imports of `detect_concerns` in engine.py
- [ ] No remaining imports of `code_deepening` in engine.py
- [ ] No remaining calls to `guided_synthesis()` in engine.py
- [ ] `concern_detector.py` still exists (not deleted) but is not imported
- [ ] `synthesizer.py` `guided_synthesis()` still exists but is not called
