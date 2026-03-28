# MSOT Fix: Align Test Infrastructure with Production Concern Detector

## Problem

Tests B, C, F measure a **simplified binary prompt** (`BEST_CONCERN_SYSTEM` +
`BEST_CONCERN_PROMPT` in `scripts/run_alt_hypothesis_tests.py`) that asks
"concern: true/false." The production concern detector (`src/insights/concern_detector.py`)
is a significantly more nuanced system with:

1. **Confidence scoring** (0.0-1.0) with a 0.7 surfacing threshold
2. **Anti-bias post-processing** (`_check_bias_in_output()`) that catches when
   the LLM itself tone-polices a student and demotes the flag
3. **Course-content disambiguation** (`_CONTENT_FLAG_MARKERS`) that detects when
   the LLM confuses subject matter with student distress
4. **Signal matrix cross-validation** — non-LLM keyword/sentiment layer that
   catches what the LLM misses and vice versa
5. **A richer prompt** (`CONCERN_PROMPT` in `src/insights/prompts.py`) with
   detailed examples of what IS and ISN'T a concern

Our n=25 finding (S029 false-flagged 100%, S002 missed 100%) is based on the
simplified test prompt. We don't know whether the production concern detector
produces the same results. This is a methodological gap that would not survive
peer review.

## What needs to happen

### 1. New test: run production concern detector on test corpus

Add a test (e.g., Test M) that calls the **actual production codepath**:

```python
from insights.concern_detector import detect_concerns
from insights.llm_backend import BackendConfig

backend = BackendConfig(name="mlx", model="mlx-community/gemma-3-12b-it-4bit")

# For each test student (S002, S004, S022, S023, S028, S029, S031):
concerns = detect_concerns(
    student_id=sid,
    student_name=name,
    submission_text=text,
    backend=backend,
    # Include signal matrix results if the production path uses them
)
```

Record for each student:
- Number of concerns returned
- Each concern's `confidence`, `flagged_passage`, `why_flagged`
- Whether the anti-bias post-processing fired (check for demotion markers)
- Whether course-content disambiguation fired

Run this 5x (like Test F) to check consistency.

### 2. Also run production detector on wellbeing cases (WB01-WB10)

Direct comparison to Test G (observation) and Test H (simplified binary).

### 3. Document which codepath each test uses

Every test result file should include a field like:
```json
"codepath": "test_harness_binary"  // or "production_concern_detector"
```

This makes it explicit when we're testing a simplified variant vs the real system.

### 4. Assess the gap

Compare results:
- Does the production detector also false-flag S029? (If the anti-bias
  post-processing catches "exhausting to explain" as identity-based fatigue
  rather than personal crisis, the n=25 finding is specific to the simplified
  prompt, not a general classification failure.)
- Does the production detector catch S002? (If the signal matrix flags the
  trailing-off pattern even when the LLM misses it, the combined system
  works where the LLM-only test doesn't.)

### 5. Design Test L against the right baseline

Test L (multi-option schema: concern/notable/engaged/exceptional) should be
compared against BOTH the simplified binary AND the production detector.
Otherwise we're comparing a new idea against a strawman.

## Files to modify

- `scripts/run_alt_hypothesis_tests.py` — add Test M (production detector),
  add `codepath` field to all existing test result records
- `src/insights/concern_detector.py` — may need a thin wrapper function that
  accepts the same inputs as the test harness for easy comparison
- `docs/research/experiment_log.md` — document which tests used which codepath
  (retroactively annotate existing results)

## Key architectural note

The production concern detector in `concern_detector.py` uses `detect_concerns()`
which expects specific inputs. Check the function signature carefully — it may
need signal matrix results from `patterns.py:signal_matrix_classify()` as input,
which means the test needs to run the signal matrix too (not just the LLM call).

The observation tests (G, I) are NOT affected by this MSOT issue — they import
the observation prompt directly from `src/insights/prompts.py` and use the same
`send_text()` codepath the production pipeline uses. The MSOT is specifically
about the concern detection path.

## What this means for existing findings

If the production detector handles S029 correctly (anti-bias catches it):
- Tests B/C/F measured a simplified system, not the production system
- The n=25 finding still demonstrates that naive binary classification fails,
  but the production system may have already solved it
- The paper claim needs to be "binary classification without post-processing
  fails" not "binary classification fails"

If the production detector also fails on S029:
- The anti-bias post-processing isn't sufficient
- The n=25 finding generalizes to the production system
- The observation architecture argument is strengthened

Either outcome is publishable — but they're different claims.
