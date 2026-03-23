# Testing Plan: Next Steps

Based on Round 2 testing session (2026-03-22).

---

## Priority 1: Validate synthesis-first refinement (relational moves)

**What changed:** Connection reader prompt now includes specific relational move examples
(tone policing, essentializing in context, colorblind erasure, gatekeeping).

**Test:** Run `scripts/prototype_synthesis_first.py` on MLX Llama 3.1 8B with the
refined prompt. Check:
- Does the class reading surface the Aiden/Destiny tension explicitly?
- Does per-student coding of S025 Aiden now catch tone policing?
- Does per-student coding still catch S018 Connor (colorblind)?
- Does S029 Jordan remain clean?

**Success criteria:** S025 caught AND S029 clean. If S025 is caught, combined multi-pass
(standard + synthesis-first) would reach 3/3, 0 FP on Llama 8B.

**Script:** Ready to run. `python3 scripts/prototype_synthesis_first.py`
(requires MLX free — no concurrent MLX inference).

## Priority 2: Replication runs

Run each configuration 3x to check if results are stable:
- Llama 8B standard pipeline (3 runs)
- Llama 8B synthesis-first (3 runs, with refined prompt)
- Qwen 7B standard pipeline (1 additional run for confirmation)

**What we're checking:** Is the complementary attention pattern reliable or stochastic?

## Priority 3: 27B and 70B synthesis-first (OpenRouter)

When rate limits clear, run:
- `google/gemma-3-27b-it:free` synthesis-first
- `meta-llama/llama-3.3-70b-instruct:free` synthesis-first

**What we're checking:** At what scale does the architecture contribution plateau?
If 70B synthesis-first matches Gemini handoff quality, architecture + moderate scale
may be sufficient. If 8B synthesis-first matches 27B standard, architecture can
substitute for scale.

## Priority 4: Cloud enhancement test

Wire OpenRouter credentials into `_run_cloud_enhancement()` in synthesizer.py.
Run on the Llama 8B synthesis output (4/4 calls, 5 highlights, 2 tensions).

**What we're checking:** Does anonymized-pattern cloud enhancement add richness
comparable to the Gemini handoff, while keeping all student data local?

## Priority 5: Build actual combined pipeline

Currently "combined" = theoretical union of two separate runs. Build a real
multi-pass system:
1. Standard concern detection pass (catches S015)
2. Synthesis-first class reading + per-student coding (catches S018, S025 with refined prompt)
3. Union of concern flags with deduplication
4. Per-student coding uses synthesis-first tags (richer)

**What we're checking:** Does the real combined system behave as predicted,
or does the synthesis-first context suppress standard detection?

## Priority 6: Second corpus (AP Biology or Pre-Calc)

Create a 20-30 student corpus for a STEM subject with equity-critical patterns:
- Student using home/cultural knowledge for science concepts
- Neurodivergent lab report writing
- ESL student with strong concepts, non-standard expression
- Student making sophisticated observations in non-academic register

**What we're checking:** Do the universal readers (asset, threshold, connection)
produce useful output outside humanities?

## Priority 7: Teacher evaluation

Have 2-3 teachers independently evaluate:
- Standard pipeline output vs. synthesis-first output
- Which `what_student_is_reaching_for` descriptions are pedagogically useful?
- Do teachers prefer the Gemini handoff or the pipeline output?

## Parking lot (not blocking)

- Adversarial critic pass prototype
- Reader-not-judge per-student coding
- Ablation: structured vs. unstructured class reading
- Immanent critique prompting in feedback generation
- Synthesis-only chatbot export mode test
