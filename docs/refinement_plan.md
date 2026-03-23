# Insights Pipeline Refinement Plan

> **Date:** 2026-03-22
> **Methodology gate:** `docs/comparison_analysis.md` (Phase 0 audit completed)
> **Status:** Code changes implemented; this document records what, why, and equity checks.

---

## Implemented Changes (This Session)

### R1: Assignment Connection Detection (P0)
- **What**: `src/insights/quick_analyzer.py` — new `_assignment_connection()` method + `assignment_description` parameter on `analyze()`
- **Why**: The pipeline had no mechanism to surface when a submission's vocabulary doesn't connect to the assignment. In real deployment, this catches wrong-portal submissions and helps teachers see engagement patterns. (Gap 3 in comparison analysis)
- **How**: TF-IDF cosine similarity between assignment description and each submission, with per-student scores and class-level observation.
- **Equity check** (#ALGORITHMIC_JUSTICE, #COMMUNITY_CULTURAL_WEALTH): Vocabulary overlap cannot assess experiential engagement. Maria Ndiaye's grandmother in Dakar IS intersectionality regardless of vocabulary match. Observation text frames low scores as "the student may be approaching differently," never "off-topic." Translation note added for `was_translated` submissions (#LANGUAGE_JUSTICE). Class-level observation surfaces portal issues without singling out individuals.
- **Priority**: P0 — most actionable engagement signal the pipeline was missing

### R2: Feedback-Concern Content Validation (P0)
- **What**: `src/insights/feedback_drafter.py` — rewritten `_build_concern_context()`
- **Why**: The broken mycorrhizal link: Stage 5 (concerns) correctly flags Connor Walsh's colorblind framing, but Stage 8 (feedback) validates it because it only received tone guidance, not content. (Gap 1 in comparison analysis)
- **How**: Pass concern content summaries (`why_flagged`, `flagged_passage`) to the feedback prompt. LLM told to avoid validating flagged behavior and find a different strength to highlight.
- **Equity check** (#TRANSFORMATIVE_JUSTICE): Steering feedback away from validating dismissive framing is transformative — it addresses potential harm without replicating it. Righteous anger (Destiny Williams) is protected: the concern detector correctly does NOT flag it, so the feedback drafter receives no avoidance guidance. (#ETHNIC_STUDIES)
- **Priority**: P0 — pipeline's most damaging self-contradiction

### R3: Individual Pair Surfacing (P0)
- **What**: `src/insights/quick_analyzer.py` — `_pairwise_similarity()` updated to surface pairs >= 0.90
- **Why**: Near-verbatim matches are factual information teachers need. Class-level stats alone don't tell the teacher WHICH submissions matched. (Gap 4 in comparison analysis)
- **How**: Added `HighSimilarityPair` model, `meta` parameter to `_pairwise_similarity()`, pair identification at >= 0.90 threshold only.
- **Equity check** (#INTERDEPENDENCE, #COMMUNITY_CULTURAL_WEALTH): Even at 0.90, observation text includes collaborative learning as a possible interpretation. Below 0.90, no individual pairs surfaced — moderate similarity can reflect community, collaboration, or shared cultural knowledge. Document-level 0.90 is near-verbatim territory; future work should explore paragraph-level analysis for finer grain.
- **Priority**: P0

### R4: Coding Hallucination Guard (P0)
- **What**: `src/insights/submission_coder.py` — new `_validate_concepts()` function
- **Why**: The 8B model attributed "intersectionality in practice" at 0.8 confidence to a driving essay. Misrepresenting a student's engagement is harmful — it could lead a teacher to assume understanding that isn't there. (Gap 2 in comparison analysis)
- **How**: Post-validate each `concepts_applied` entry against submission text using substring match, token overlap (>= 50%), and stem overlap. Remove concepts with no vocabulary support.
- **Equity check** (#TRANSFORMATIVE_JUSTICE): Prevents misrepresentation. The guard uses generous matching (stem overlap catches "intersectional" for "intersectionality") to avoid over-stripping legitimate connections.
- **Priority**: P0

### R5: Inter-Stage Data Flow (P0)
- **What**: `src/insights/engine.py` — wire assignment description to QuickAnalyzer, inject assignment connection notes into coding prompts
- **Why**: The mycorrhizal fix: broken information flow between stages is the single structural problem that causes multiple quality gaps. (Gap 5 in comparison analysis)
- **How**: Fetch assignment description before Quick Analysis (via `DataFetcher.fetch_assignment_info()`), pass to `analyze()`. When vocabulary overlap < 0.3, inject a note into the coding prompt telling the 8B to code what the student ACTUALLY wrote, not what the assignment asked for.
- **Equity check**: The injected note explicitly says "If the student is engaging through personal experience rather than academic vocabulary, that engagement is valid — capture it."
- **Priority**: P0 — architectural fix that addresses multiple gaps

### R6: Data Model Extensions (P0)
- **What**: `src/insights/models.py` — new `AssignmentConnectionScore`, `HighSimilarityPair` models; extended `PerSubmissionSummary`, `PairwiseSimilarityStats`, `QuickAnalysisResult`
- **Why**: Data models for R1, R3, R5
- **How**: Pydantic models with equity-conscious docstrings
- **Priority**: P0 — required by all other changes

---

## Not Implemented (Future Work)

### F1: Engagement Absence Detection (P1)
- **Gap**: Tyler Nguyen and Jaylen Carter (AI-generated, zero personal engagement) get clean codings. The pipeline doesn't surface engagement absence.
- **Fix**: Wire AIC engagement dimensions (personal_connection, intellectual_work, etc.) into pipeline records. Non-LLM — the signals already exist in AIC.
- **Why deferred**: Requires AIC-pipeline integration that crosses module boundaries. The engagement signals are computed in `Academic_Dishonesty_Check_v2.py`, which runs separately from the Insights pipeline.

### F2: Theme Tag / Concern Self-Contradiction (P1)
- **Gap**: Brittany's record has "celebrating cultural diversity" (theme tag) alongside "essentializing language" (concern). Theme tags can validate what concerns flag.
- **Fix**: Post-validation pass: if a concern is flagged, check whether theme tags validate the flagged behavior.
- **Why deferred**: Requires defining which theme-tag / concern-type combinations are contradictory. Design work needed.

### F3: Incomplete Submission Detection (P1)
- **Gap**: Jordan Kim's truncated submission ("Idk I had more to say but its late and") not surfaced.
- **Fix**: Non-LLM heuristic: last sentence lacks terminal punctuation + word count below class P25 + trailing conjunction → flag as "possibly incomplete."
- **Why deferred**: Simple to implement but needs threshold calibration against real classroom data.

### F4: Paragraph-Level Similarity Analysis (P2)
- **Gap**: Document-level 0.90 cosine catches verbatim matches. AI-assisted work produces moderate similarity with different wording — semantically similar paragraphs across submissions.
- **Fix**: Sentence-cluster or paragraph-level pairwise analysis at lower thresholds. Surface as "several students structured their argument similarly in paragraph N."
- **Why deferred**: Significant architectural work. Current document-level approach is the foundation.

### F5: Cross-Student Tension Surfacing (P2)
- **Gap**: Opus spontaneously identifies that Connor's colorblindness contradicts Destiny's structural analysis. The 8B pipeline doesn't surface cross-student tensions.
- **Fix**: Multi-pass synthesis: targeted prompts asking the 8B to compare specific pairs of student positions. Mycorrhizal approach — orchestration creates depth that single calls can't.
- **Why deferred**: Requires synthesis stage redesign. Current synthesis partially failed (3/9 sections, JSON parse errors).

---

## Cross-Model Testing Fixes (From 2026-03-22 Multi-Model Comparison)

> These fixes were identified by running the pipeline on DeepSeek 671B, Qwen3-32B, and Llama 70B
> via OpenRouter, plus a Gemini Pro browser handoff. See `docs/comparison_analysis.md` Sections 6-7.

### X1: Synthesis Silent JSON Fallback (P0 — Blocks All API Backends)

- **Gap**: Synthesis returns 0/9 sections on DeepSeek, Qwen3, and 70B. All sections show "(Insufficient data for this section.)" — the demo script placeholder.
- **Root cause**: `synthesizer.py:292` — `parsed.get("sections", {})` silently returns empty dict when the model returns unexpected JSON structure. No logging. Same 4096 `max_tokens` for all models may cause truncated JSON on the 9-section single-shot prompt.
- **Fix (3 parts)**:
  1. **Log the raw response** when sections key is missing — `log.warning(f"Synthesis response missing 'sections' key. Raw: {raw[:500]}")` at line 292.
  2. **Increase max_tokens for synthesis** on API backends — 4096 is tight for 9 analytical sections. Set to 8192 for cloud backends.
  3. **Consider multi-pass synthesis for API backends** — the 3-pass approach (3 sections per call) already exists for 8B reliability (`_synthesize_lightweight`). API models may benefit from the same approach despite having more capacity, because the JSON structure requirement is easier to satisfy with fewer sections per call.
- **Location**: `src/insights/synthesizer.py` lines 277-298; `src/insights/llm_backend.py` max_tokens config
- **Validation**: Re-run synthesis stage on DeepSeek with logging. Inspect raw response to determine whether it's truncation, wrong JSON structure, or parse error. Then apply the appropriate fix.
- **Priority**: **P0** — this blocks the most valuable teacher-facing output (synthesis report) on every API backend. The pipeline currently produces themes, concerns, coding, and feedback on API backends, but not the synthesis narrative that ties them together.

### X2: Theme Quote Fabrication Prompt (P0 — Affects All Models)

- **Gap**: Theme generator asks for "2-4 supporting quotes per theme (verbatim from the records)" but only provides 1 quote per student (max 200 chars) via `_records_to_compact_json()`. Models fill the gap by fabricating. Qwen3 fabricated student names AND quotes. DeepSeek stayed within actual material (4/5 verbatim, 1/5 truncated). 70B and 8B untested for this specific issue.
- **Root cause**: `theme_generator.py:128-152` truncates to 1 quote × 200 chars. `prompts.py:506-507` asks for 2-4. The mismatch invites fabrication.
- **Fix (choose one)**:
  - **Option A (conservative)**: Change prompt to "For each theme, select the single most representative quote from the records provided. Do not generate or paraphrase — use only the exact text from the 'quote' field in each student's record." This eliminates the fabrication gap entirely.
  - **Option B (richer)**: Pass more quote material to theme generation — increase from 1 to 3 quotes per student, increase character limit from 200 to 400. Then ask for "1-3 supporting quotes per theme (verbatim from the records provided — do not fabricate or paraphrase)." This gives the model more material to work with while constraining fabrication.
  - **Option C (post-validation)**: Keep the current prompt but add post-validation: check that every supporting quote in the theme output appears as a substring of some student's quote in the coding records. Strip any quote that fails the check. This catches fabrication after the fact.
- **Recommendation**: Option A for immediate fix (simplest, eliminates the problem). Option B for later (richer output, still safe). Option C as defense-in-depth regardless.
- **Location**: `src/insights/theme_generator.py` lines 128-152 (compact JSON), `src/insights/prompts.py` lines 459-525 (THEME_GENERATION_PROMPT)
- **Priority**: **P0** — fabricated quotes attributed to real (or nonexistent) students is the highest-harm failure mode. A teacher reading "Amina Patel said X" and trying to follow up is acting on fiction. (#ALGORITHMIC_JUSTICE, #TRANSFORMATIVE_JUSTICE)

### X3: Qwen3 Concern Detection Investigation (P1)

- **Gap**: Qwen3 flags Connor Walsh (colorblind, 0.85) but misses Brittany Okafor (essentializing) and Aiden Brooks (tone policing). 8B, DeepSeek, and 70B all catch all three.
- **Root cause**: Unknown — could be model capacity, prompt sensitivity, or parsing. Needs investigation.
- **Investigation steps**:
  1. Run concern detector on just S015 (Brittany) and S025 (Aiden) with Qwen3 backend, with full logging of the raw LLM response.
  2. Check: did Qwen3 return a response that identified the concern but the parser missed it? Or did Qwen3 genuinely not recognize the pattern?
  3. If parsing: fix parser. If recognition: test whether prompt modifications (more examples, more explicit pattern descriptions) help Qwen3 recognize essentializing and tone policing.
- **Location**: `src/insights/submission_coder.py` (concern detection is part of coding)
- **Priority**: P1 — Qwen3 may not be viable as a backend regardless (quote fabrication is the bigger issue), but understanding why it misses concerns informs whether prompt design can compensate for model capacity.

---

## Methodology Notes

All implemented changes were filtered through the Phase 0 methodology audit (`docs/comparison_analysis.md`). Changes marked with methodology status:

- R1 (Assignment connection): Valid capability, but cannot validate against current corpus (DAIGT adaptation artifact)
- R2 (Feedback-concern): ✅ Valid — found on hand-crafted data (Connor Walsh)
- R3 (Pair surfacing): ⚠️ Ethan Liu / Nadia Petrov match is a DAIGT artifact (both from daigt_00011) — need real pair to validate
- R4 (Hallucination guard): ⚠️ Provoked by test data but good engineering regardless
- R5 (Inter-stage flow): ✅ Valid — architectural gap independent of data
- R6 (Models): ✅ Infrastructure — not data-dependent

The SynthesisReport biology pipeline crash (numeric value in sections dict) is already fixed by a `field_validator` in `models.py` (lines 322-340).
