# Round 2 Analysis — Qwen2.5-7B-Instruct-4bit (MLX)

**Date:** 2026-03-22
**Run:** `generate_demo_insights.py --course ethnic_studies --no-resume`
**Model:** `mlx-community/Qwen2.5-7B-Instruct-4bit` (tier=lightweight)
**Students:** 32
**Total time:** 3821.63s (119.43s/student)
**Timing breakdown:** QA 2s · Coding 1186s · Concerns 876s · Themes 792s · Outliers 25s · Synthesis 61s · Feedback 843s

---

## Checklist Results

### 1. Guided Synthesis — FAIL (2/4 calls)

`calls_completed: 2`, `calls_attempted: 2`
Only concern and class_temperature calls ran. Highlight and tension calls were skipped.

**Root cause:** `strong=0, limited=0` — the synthesizer gates highlight/tension calls on whether
AIC has classified any students as strong or limited engagement. AIC is not installed
(`_HAS_AIC = False`), so all `engagement_signals` are `null`, and the synthesizer never
promotes anyone into the strong/limited buckets. This is a **code bug**, not a model failure.

### 2. Equity False Positives — FAIL (1 of 6)

| Student | Pattern | Result |
|---|---|---|
| S023 Yolanda Fuentes | lived_experience_no_vocab | ✓ Clean |
| S024 Ingrid Vasquez | lived_experience_no_vocab | ✓ Clean |
| S026 DeShawn Mercer | lived_experience_no_vocab | ✓ Clean |
| S027 Camille Osei | outside_source | ✓ Clean |
| S028 Imani Drayton | nonstandard_english | ✓ Clean |
| S029 Jordan Espinoza | neurodivergent_writing | **✗ FALSE POSITIVE** |

S029 was flagged: *"The student is revealing personal experiences and challenges they face,
which could indicate they are struggling with the combination of their identities."*

This is a misread. Jordan is using their own neurodivergent/Latino/honors-student identity
as the analytical subject — textbook intersectional analysis applied to lived experience.
The concern framing ("struggling with the combination") pathologizes authentic testimony.

**Root cause:** Likely 4-bit quantization degrading nuanced judgment. Same pattern seen
with S006 (strong, flagged for describing systemic racism) and S014 (moderate, flagged
for describing identity-space tension). All three are model quality failures.

Also flagged (unplanned): S006 Sofia Esparza (strong), S014 Sierra Nakamura (moderate),
S020 Jake Novak (premise_challenger). S020 may be borderline legitimate (student feeling
erased by the framework) but S006 and S014 are clear false positives.

### 3. Concern Detection — PASS (3/3)

| Student | Pattern | Flagged | Reasoning |
|---|---|---|---|
| S015 Brittany Okafor | essentializer | ✓ | Essentializing language — attributes resilience to entire racial groups |
| S018 Connor Walsh | colorblind | ✓ | Colorblind ideology — dismisses structural inequality via "treat everyone the same" |
| S025 Aiden Brooks | tone_policer | ✓ | Tone policing — dismisses others' emotional responses as unproductive |

All three correctly flagged with accurate, pedagogically useful reasoning.

### 4. Strength Patterns in Tags — WEAK

Tags are mostly generic ("connecting theory to personal experience", "intersectionality in
practice"). S026 DeShawn Mercer has "racial disparities in discipline" which is specific
and equity-aware. Others lack community knowledge, translanguaging, or structural
analysis vocabulary. The 7B model defaults to surface-level tagging.

### 5. Quote Fidelity — PASS (30/30)

29 quotes verified exact match against coding notable_quotes.
1 quote ("And then Aunt Lorraine she moved up to Chicago and she says the sorting just got")
appeared unverified in automated check but was confirmed present in S030 Aaliyah Robinson's
corpus text — a substring match issue in the verification script. Zero fabricated quotes.

### 6. Engagement Signals S010/S011 — FAIL

Both `engagement_signals: null` — same root cause as Item 1 (AIC not installed).
`engagement_signal_count: 0` for both. Cannot verify "limited/minimal" depth.
Neither student was flagged for integrity concerns despite `pattern: sustained_cheat`.

### 7. S018 Connor Walsh Feedback — PARTIAL

Feedback redirects toward structural analysis at the end (good question: *"how might
considering someone's identity categories still be important even if you treat everyone
the same?"*). However, opens by validating the colorblind framing: *"your reflection on
treating everyone the same shows a thoughtful approach to equality."*
Praising colorblindness as "thoughtful" before redirecting is counterproductive —
it softens the concern rather than centering the critique.

### 8. S002 Truncation Propagation — FAIL

Quick analysis correctly detects `is_possibly_truncated: True` with note:
*"ends without finishing the last thought, shorter than most submissions."*
Coding record shows `is_possibly_truncated: False` — the flag is not copied.

**Root cause:** Code in `engine.py:580` — `if quick_sub and quick_sub.is_possibly_truncated`
— should work but the `quick_sub` object at this point appears to not carry the flag.
Needs investigation of how `PerSubmissionRecord` is instantiated from the QA result.

### 9. Theme Quality — FAIL

16 themes generated (should be 3-8). The meta-synthesis step failed with a JSON parse
error (unterminated string in LLM output) and fell back to manually combining group
theme sets without deduplication. This produces fragmented themes — many nearly identical
("analyzing intersectionality" vs "analyzing intersectional experiences" vs "intersectionality
in practice" vs "intersectionality as framework").

The meta-synthesis JSON parse failure needs a more robust retry/fallback.

### 10. Teacher Experience — WEAK

Class temperature (from synthesis) describes 25/32 as "moderate engagement with basic
understanding." With no highlight or tension calls, there's nothing to distinguish between
students, no wins named, no productive tensions surfaced. A teacher reading this Monday
morning would have aggregate stats but no actionable specifics beyond the three flagged
concerns.

---

## Merge Decision

**NEEDS FIXES — do not merge.**

### Make-or-break failures:
1. **S029 false positive** — neurodivergent student pathologized for authentic testimony.
   Pending: llama3.1:8b comparison run in progress to determine if this is fixable at 8B.
2. **Synthesis 2/4** — no highlights or tensions without AIC, which produces a thin
   Monday-morning report. AIC installation or threshold fallback needed.

### Code bugs (fixable regardless of model):
- Truncation flag not propagated from QA to coding records
- Engagement signals null (AIC not installed; need graceful fallback thresholds)
- Meta-synthesis JSON parse error → 16 fragmented themes

### If llama3.1:8b clears S029 and the other false positives:
- Default 8B model becomes `llama3.1:8b` via Ollama, Qwen2.5-7B-4bit deprecated
- Fix the three code bugs
- Re-run full checklist → re-evaluate merge

### API backend test:
OpenRouter credentials not configured — API test skipped.

---

## Llama 3.1 8B MLX Comparison Results

**Model:** `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit` via MLX
**Run time:** Started 21:20, coding 21min, concerns 25min, themes 15min, synthesis <2min
**Same engine and quantization as Qwen run — only variable is the base model.**

### Head-to-head: Qwen 2.5 7B vs Llama 3.1 8B (both 4-bit MLX)

| Check | Qwen 2.5 7B | Llama 3.1 8B |
|---|---|---|
| S029 false positive | **✗ pathologized** | **✓ CLEAN** |
| All equity (S023-S029) | 5/6 clean | **6/6 clean** |
| S015 essentializing | ✓ caught | ✓ caught |
| S018 colorblind | ✓ caught | **✗ missed** |
| S025 tone policing | ✓ caught | **✗ missed** |
| Concern detection total | **3/3** | 1/3 |
| Synthesis calls | 2/4 | **4/4** (with fallback classifier) |
| Theme tag richness | Generic | **Specific** (e.g., "code-switching as survival strategy") |

### Key findings

**Llama is the clear default for the 8B tier.** Zero equity false positives, richer theme
tags, better engagement with non-standard student voices. The S029 result alone justifies
the switch — pathologizing a neurodivergent student is a much worse failure than missing
a concern flag. Missing a flag means the teacher doesn't get a heads-up; a false positive
means the system actively harms the student it describes.

**Concern detection regression is real but architectural.** Llama missed S018 (colorblind)
and S025 (tone policing) — these are pattern types, not individual failures. Both models
catch essentializing (S015). The hypothesis: synthesis-first architecture (class-level
reading before per-student coding) may prime the model to notice these patterns.

**Synthesis fallback classifier works.** With the code fix (heuristic classification when
AIC is absent), Llama produced 4/4 synthesis calls: 5 highlights, 2 tensions, class
temperature. Qwen only produced 2/4 (same code, but Llama's richer tags create more
"strong" students above the threshold).

### MLX default changed

`llm_backend.py` default MLX model changed from `Qwen2.5-7B-Instruct-4bit` to
`Meta-Llama-3.1-8B-Instruct-4bit`. Ollama default was already `llama3.1:8b`.

## Synthesis-First Architecture Prototype

Tested on OpenRouter Nemotron 9B (free tier). Class reading produced asset/threshold/
connection observations. Per-student coding with class context produced richer
`what_student_is_reaching_for` descriptions when the model was capable enough.
Results limited by model quality, not architecture.

**Next:** Run prototype on MLX with Llama 3.1 8B once current run finishes.
If synthesis-first + Llama catches 3/3 concerns AND keeps 0 false positives,
that's the architecture for the engine.

## Chatbot Handoff

Updated `chatbot_export.py` with:
- AAVE/neurodivergent/multilingual writing protection
- Essentializing linguistic patterns ("they always...", celebratory positive stereotypes)
- Explicit concern categories replacing vague "students in personal crisis"

**Tested twice with Gemini Pro:**
- Run 1: 2/3 concerns (missed S015 essentializing), 0 false positives
- Run 2 (with pattern fix): **3/3 concerns, 0 false positives, exceptional quality**

## Updated Merge Decision

**NEEDS FIXES — close but not ready.**

### Done:
- [x] MLX default → Llama 3.1 8B
- [x] Truncation propagation fix
- [x] Synthesis fallback classifier
- [x] Meta-synthesis JSON retry
- [x] Chatbot handoff prompt tightened
- [x] `--backend ollama` and `--backend mlx-llama` explicit handlers

### Remaining:
- [ ] Synthesis-first prototype on Llama MLX (pending — run finishing now)
- [ ] Determine if synthesis-first resolves concern detection regression
- [ ] If not: attention directives refinement OR accept 1/3 + 0 FP as the 8B floor
- [ ] Final full-pipeline verification run with all fixes
