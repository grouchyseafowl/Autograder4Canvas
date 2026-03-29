# Development Reference

This file contains reference docs that don't need to load every session.
See `CLAUDE.md` for active session instructions.

## MLX Testing Conventions

MLX (Metal GPU) inference on macOS has specific constraints on 16 GB machines.
All future testing with MLX should follow these practices:

### Process isolation
- **Each test must run in its own subprocess.** Metal GPU memory is not fully
  reclaimed in-process; only process exit guarantees memory release. Use
  `--single-test` flag + `subprocess.run()` (see `run_alt_hypothesis_tests.py`).
- **Pause 5s between subprocesses** to let Metal driver reclaim memory.

### Sleep resilience
- Metal inference deadlocks if launched immediately after laptop wake from sleep.
- **Always run a Metal warmup** before launching test suites (load model, generate
  5 tokens, discard).
- Use `caffeinate -i` to prevent system sleep during active runs.
- Subprocess timeouts should be set (default 900s, 3600s for long tests) so stuck
  processes don't block the suite.

### Data preservation
- **All raw outputs go to `data/research/raw_outputs/`** with date-stamped filenames.
  Never use `/tmp/` for test data — prior results were lost to system crashes.
- Checkpoints go to `data/demo_baked/checkpoints/` and enable resume on crash.

### Memory management
- Call `unload_mlx_model()` between pipeline stages (not just between tests).
- The improved unload does: explicit `del` model/tokenizer → `gc.collect()` →
  `mx.clear_cache()` → `set_cache_limit(0)` then restore → `gc.collect()`.
- Within a test, the 20s throttle + `mx.clear_cache()` after each call helps
  but doesn't prevent gradual memory pressure over 30+ calls.

### Default backend
- Test scripts default to `mlx-gemma` (Gemma 12B 4-bit via MLX).
- Production code uses `auto_detect_backend()` which respects user config.

## Unit Test Suite

Run before and after any significant change:

```bash
python3 -m pytest tests/ -v --tb=short
# Expected: ~614 tests, ~2min, 0 failures
```

### What's covered (pure unit tests — no LLM, no MLX, no Canvas)

| File | Covers |
|---|---|
| `test_models.py` | Pydantic validators, `vader_sentiment` migration, `SynthesisReport` numeric-section filter, `Theme.sub_themes` dict coercion |
| `test_insights_store.py` | SQLite run lifecycle, stage completion (idempotent), codings upsert, profile/template round-trips, resume persistence |
| `test_teacher_profile.py` | Wellbeing floor enforcement, concern sensitivity, prompt fragment builders, template save/fork |
| `test_prompts.py` | All prompt constants exist, required `{placeholders}` present, equity-critical content guards |
| `test_submission_coder.py` | `_chunk_text`, `_validate_concepts` (hallucination guard), `_coerce_str`, format helpers |
| `test_feedback_drafter.py` | Data-sufficiency check, wellbeing context builder (CRISIS/BURNOUT never leak to student), preprocessing fragment |
| `test_linguistic_features.py` | AAVE feature detection, multilingual tier suppression, `_derive_tier`, `detect_features` output shape, two-tier short-submission thresholds by assignment type |
| `test_human_presence_detector.py` | `_normalize_score` math, `HumanPresenceDetector.analyze` output contract, empty/short text edge cases |
| `test_quick_analyzer.py` | `_strip_html`, `_tokenize`, `_deduplicate_names`, `_detect_engagement_type`, `match_submission_references`, stats computation, truncation detection, word frequency, `analyze()` contract |

### What is NOT here (by design)

- **LLM calls** — mock them and you're testing your mocks, not the system.
  Use the empirical integration tests in `tests/test_wellbeing_classifier.py`
  and `scripts/run_trajectory_tests.py` for that.
- **MLX/Metal** — process-isolation constraint; see MLX Testing Conventions above.
- **GUI panels** — PySide6 widget tests require `pytest-qt` and are not installed.
- **Canvas API** — live API; would need `requests` mocking infra not yet built.

### Constraints for new tests

- **No real student data** — all fixtures must be synthetic (FERPA).
- **No MLX** — unit tests must mock `send_text` / `call_llm` entirely.
- Integration tests must be marked `@pytest.mark.integration` and kept separate.
- Use `tmp_path` for any database; never a fixed path that could collide.

## .gitignore Recommendations

```
.reframe/session/
.reframe-active
```
