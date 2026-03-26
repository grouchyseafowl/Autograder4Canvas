# Session Handoff — 2026-03-23

## TL;DR

Built the integrated synthesis-first pipeline. Gemma 12B + class reading appears
to be **100% reliable** on concern detection (5/5 runs, 3/3, 0 FP). The architecture
compensates for model size. Replication study and 12B MLX full pipeline still running.

---

## When You Pick Up

### Step 1: Check what finished overnight

```bash
# Replication study (THE most important result)
cat /tmp/replication_study.log
# or the saved JSON:
cat data/demo_baked/replication_study_20260323.json | python3 -m json.tool

# 12B MLX full pipeline
tail -30 /tmp/round3_gemma12b_final.log
# Results (if completed):
ls -la src/demo_assets/insights_ethnic_studies_gemma12b_mlx.json
```

### Step 2: Read the replication numbers

The study ran 5 concern checks per student on 3 configs. What you're looking for:

| Config | What it tests | Good result |
|---|---|---|
| A: Gemma 12B + context | **The deployment target** | 3/3, 0 FP on ≥80% of runs |
| B: Gemma 27B + context | Quality ceiling | 3/3, 0 FP on ≥80% of runs |
| C: Gemma 27B, no context | **Control** — does class reading actually help? | Should be worse than B |

**FINAL DATA (2026-03-23):**

| Student | Expected | A: 12B+ctx | B: 27B+ctx | C: 27B no ctx |
|---|---|---|---|---|
| S015 Brittany | FLAG | **100%** | **100%** | **0%** |
| S018 Connor | FLAG | **100%** | 80% | **100%** |
| S025 Aiden | FLAG | **100%** | 80% | 100% |
| S023 Yolanda | CLEAN | **0%** | 0% | 0% |
| S027 Camille | CLEAN | **0%** | 0% | 0% |
| S028 Imani | CLEAN | **0%** | 0% | 0% |
| S029 Jordan | CLEAN | **0%** | 0% | 0% |

**Config A (Gemma 12B + class context): PERFECT. 100% on all flags, 0% on all equity, 5/5 runs.**

Key insight: Config C shows S015 Brittany drops to 0% WITHOUT class context.
Class reading helps essentializing detection too, not just tone policing.
12B outperforms 27B on reliability. The architecture IS the intelligence.

### Step 3: Decide what to do based on the data

**Everything is ≥ 100% on the synthetic corpus. Architecture validated on test cases.**

**CAVEAT: This is synthetic data we designed.** Real student writing will be messier,
more ambiguous, and include patterns we haven't anticipated. The 100% tells us the
architecture works on the known patterns — not that it generalizes to all real-world
cases. The adversarial critic and immanent critique remain valuable for ambiguous
real-world cases even though they're not needed for the test corpus.

**Next session priorities:**

### 1. Commit + clean up
- Commit all working tree changes (new files + modifications)
- Merge branches if needed
- Verify the build is clean

### 2. Setup UX (Phase 8) — the big one
Walk non-technical users through configuration. The system needs to assess what
the teacher has access to and recommend a path:

**Routes to support:**
- **A: Light tier (local only)** — Gemma 12B on teacher's machine. 16GB needed.
  No cloud, no API. Full FERPA safety. 3/3 concern detection, good quality.
- **B: Light + enhanced analysis (browser handoff)** — A + system generates a
  ready-to-paste anonymized prompt (~400 words). Teacher pastes into ANY chatbot
  they have access to (institutional Gemini, free ChatGPT, Copilot, Claude,
  OpenRouter playground). Zero setup. Teacher controls what leaves their machine.
- **C: Light + enhanced analysis (API)** — A + automated cloud call. Three sub-options:
  - Institutional API (best): Institution provides API endpoint + key + privacy
    agreement. Can handle FULL non-redacted data (not just anonymized). Could even
    run the entire pipeline on a large cloud model if the privacy agreement covers
    student data. The system should detect this and offer: "Your institution's API
    can handle the full analysis. Run everything through [model], or run locally
    first and enhance with cloud?" Teacher chooses.
  - Free: Teacher creates OpenRouter account, uses free-tier model. Small anonymized
    payload only. One call per assignment, within free limits.
  - Paid: OpenRouter with Gemma 27B paid (~$0.01/assignment). Anonymized only.
- **E: Institutional server (medium tier)** — Gemma 27B on school infrastructure.
  Full pipeline, no cloud needed. 32GB+.
- **F: Institutional API as primary** — If the institution provides access to a
  powerful model (Sonnet, GPT-4, etc) with a privacy agreement, consider whether
  the local pipeline adds value or whether a single-pass handoff is better.
  The pipeline adds value when: the institutional model isn't always available,
  the teacher wants to review locally first, or the institutional model doesn't
  have the equity framing in its prompts. The handoff is better when: the
  institutional model is high-quality and always available.

**Setup wizard should:**
- Auto-detect hardware (RAM, Apple Silicon, GPU)
- Recommend a route based on what's available
- Handle model download (one-click Ollama or MLX)
- Test the model works
- Configure cloud enhancement if chosen
- Show a sample run so the teacher sees the output before committing

**Key design question:** Should we hardcode Gemma as the recommended model, or
let the teacher choose? Recommendation: hardcode Gemma 12B as default, let
advanced users override in settings. The setup wizard should never mention
"MLX" or "4-bit quantization."

### 3. Test on real data
Even one real anonymized assignment. The synthetic corpus proves the architecture
but can't prove generalization.

### 4. Wire in immanent critique
Zero cost, enriches concern descriptions. Prompt is written.

### 5. Free-tier cloud test (re-run)
Free-tier quota was exhausted today. Re-run `/tmp/free_tier_cloud_test.py`
tomorrow to confirm free-tier models handle the small anonymized payload.

### 6. Hidden ideas tracker
Check `docs/research/hidden_ideas_tracker.md`. Pick ONE to implement.

### 7. Real-world robustness issues
See `docs/research/real_world_robustness_issues.md` — 7 identified risks with
fixes specified. A third agent could work on items 1, 4, 5, 6 (prompt engineering
+ integration tasks) while testing agent handles real data evaluation.

Key issue for multilingual: code-switching ≠ concept inclusion ≠ primary other-language.
The preprocessing pipeline needs to distinguish these and pass the distinction through
to AIC and insights. Don't translate code-switching (it's an asset). Don't translate
embedded concepts (they're the point). Do translate primary other-language (but preserve
original alongside).

### Step 4: Check the hidden ideas tracker

`docs/research/hidden_ideas_tracker.md` — these keep getting deferred. Pick ONE:
- **Adversarial critic** (prompt written, not wired in) — highest value if FP exist
- **Immanent critique** (prompt written, not wired in) — highest value for qualitative richness
- **Attention directives** (not built) — highest value for coding quality

---

## What Was Built Today (uncommitted)

### New files:
- `src/insights/class_reader.py` — synthesis-first class reading with hierarchical grouping, signal-guided excerpts, protected-feature word budget boost
- `docs/research/hidden_ideas_tracker.md` — tracks all hidden ideas with status

### Modified files:
| File | What changed |
|---|---|
| `src/insights/prompts.py` | CLASS_READING_PROMPT, MERGE_PROMPT, disability protection in CONCERN_PROMPT, {class_context} in CONCERN_PROMPT, CONCERN_CRITIC_PROMPT, IMMANENT_CRITIQUE_ADDENDUM |
| `src/insights/engine.py` | Stage 3.5 class reading, class_context + linguistic note + sentiment suppression in concern detection |
| `src/insights/concern_detector.py` | class_context parameter, TODO for adversarial critic |
| `src/insights/insights_store.py` | Migration v6, save/get class_reading |
| `src/insights/llm_backend.py` | Gemma 12B/27B defaults |
| `src/insights/chatbot_export.py` | export_handoff_prompt() with anonymization |
| `scripts/generate_demo_insights.py` | Stage 1.5 class reading, class_context in coding + concerns, Gemma backend options |

### Prompts written but NOT wired in:
- `CONCERN_CRITIC_PROMPT` — adversarial critic pass
- `CONCERN_IMMANENT_CRITIQUE_ADDENDUM` — "what does this framing cost?"

---

## Architecture (settled)

1. **Synthesis-first required** — tone policing invisible without class context
2. **Gemma model family** — 3/3 at every size; Llama 8B can't
3. **AIC linguistic justice** — sentiment suppression, protected excerpts, disability protection
4. **Cloud enhancement optional** — anonymized handoff for institutional chatbots

Pipeline flow:
```
Quick Analysis (non-LLM) → Class Reading (synthesis-first) →
Per-student Coding (with class context) → Concern Detection (with class context +
linguistic note + sentiment suppression) → Themes → Synthesis → Feedback
```

---

## Key Findings

1. **Gemma 12B + class reading may be 100% reliable** (5/5 runs, 3/3, 0 FP). Pending full replication data.
2. **Lightweight > medium for relational harm detection**. Decomposed prompts keep signals sharp.
3. **Disability self-advocacy protection works.** "Is the problem the body or the built environment?" centered in the prompt. S029 clean everywhere.
4. **12B outperforms 27B on reliability with class context.** Architecture compensates for scale.
5. **Class reading may suppress essentializing detection** (S015 regression). Needs investigation.

---

## Files to Check

| File | What |
|---|---|
| `/tmp/replication_study.log` | **Most important** — frequency data |
| `data/demo_baked/replication_study_20260323.json` | Machine-readable results |
| `/tmp/round3_gemma12b_final.log` | 12B MLX full pipeline |
| `src/demo_assets/insights_ethnic_studies_gemma12b_mlx.json` | 12B results if done |
| `docs/research/hidden_ideas_tracker.md` | Hidden ideas — check at session start |
| `docs/research/experiment_log.md` | Full chronological record |
| `data/demo_baked/model_comparison_20260323.md` | Round 2 side-by-side comparison |
