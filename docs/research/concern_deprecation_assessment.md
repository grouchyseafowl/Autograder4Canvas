# Concern Detector Deprecation Assessment

Date: 2026-03-27
Status: **NOT YET READY TO DEPRECATE**

## Summary

The observation architecture (Stage 3b) outperforms binary concern detection
on equity metrics (Tests B/C/F/G/H), but the concern detector has capabilities
the observation system does not yet replicate. Both systems should run in
parallel during a transition period.

## What observations do better

- **Equity-sensitive framing**: Observations describe; concerns classify.
  Classification compresses away contextual nuance (Test F: 100% false-flag
  rate on S029 neurodivergent, 0% sensitivity on S002 burnout).
- **Wellbeing signal detection**: Observations caught 8/8 synthetic signals
  (Test G); binary caught 7/8 (B format) or 3/8 (C format).
- **Power move surfacing**: Observations naturally describe structural moves
  (Test D: 7/7) without binary flagging.
- **No false positives on engaged students**: Observation prose for controls
  (WB09, WB10) described intellectual engagement, not concern.

## Critical gaps — what concerns do that observations don't (yet)

### 1. Crisis urgency (CRITICAL)
The concern detector creates structured flags with confidence scores that
surface as banners in the teacher UI. A crisis signal needs to INTERRUPT
the teacher's workflow, not wait to be read in a prose observation. The
observation prompt has no explicit crisis detection instruction.

**Fix needed**: A wellbeing-signal post-pass that reads each observation,
checks for crisis indicators, and creates structured alerts.

### 2. Anti-bias post-processing (HIGH)
`_check_bias_in_output()` in concern_detector.py detects when the LLM
itself tone-polices a student (e.g., calling structural critique
"aggressive") and demotes the flag. The observation system has equity floor
language in the prompt but no verification that the LLM honored it.

**Fix needed**: Port `_check_bias_in_output()` logic to scan observation
text for bias markers and flag observations that violate the equity floor.

### 3. Non-LLM fallback (HIGH)
If MLX crashes, the signal matrix (VADER + keyword categories) still
produces keyword-based concerns. Observations have no fallback.

**Fix needed**: If LLM is unavailable, surface signal matrix results as
skeleton observations (or keep concerns as fallback layer).

### 4. Teacher customization (MEDIUM)
Custom concern patterns, per-pattern sensitivity, disabled defaults, and
calibration feedback loop are all wired into concerns. Observations accept
a generic `teacher_lens` parameter but lack the structured customization.

**Fix needed**: Port custom patterns and sensitivity tuning to observations.

### 5. Downstream consumers (MEDIUM)
Feedback drafting reads concerns to avoid praising flagged behavior.
Deepening pass runs only on flagged students. Cross-validator compares
LLM vs signal matrix. These need rewiring.

**Fix needed**: Rewrite consumers to read observations (some already do
for the feedback drafter; others need updates).

## Recommended transition path

1. Keep both systems running in parallel (current state)
2. Add wellbeing-signal post-pass on observations → structured alerts
3. Port anti-bias post-processing to observation output
4. Wire teacher customization into observations
5. Rewrite downstream consumers to prefer observations
6. Deprecate concern detector once all gaps closed
7. Remove concern detector code

## Evidence base

- Tests B, C: Binary classification equity failures (experiment_log.md)
- Test F: 0% sensitivity / 100% false-flag rate at n=5 (n=20 in progress)
- Test G: Observations surface 8/8 wellbeing signals
- Test H: Binary catches 7/8 (B) or 3/8 (C); observations catch 8/8
- Pipeline run: Concern detector produced Concerns=[] for S002 burnout;
  observation caught the fatigue signal
