# Experiment Log — 2026-03-22

Chronological record of experiments, decisions, and findings.

---

## 19:49 — Qwen 2.5 7B full pipeline started
- `--course ethnic_studies --no-resume`
- Model: `mlx-community/Qwen2.5-7B-Instruct-4bit` via MLX
- 32 students, full pipeline

## 20:09 — Qwen coding checkpoint
- 32 codings complete
- First look: all concern_flag=False in coding records (separate from concern detection stage)

## 20:23 — Qwen concerns checkpoint
- S015 ✓, S018 ✓, S025 ✓ (3/3 concern detection)
- S029 ✗ FALSE POSITIVE — "personal stress/difficulty" for neurodivergent writing
- S006, S014 also false positives (strong writers)
- Total flagged: 7 students

## 20:38 — Qwen synthesis
- calls_completed: 2/4 (only concern + temperature)
- strong=0, limited=0 — AIC not installed, no engagement signals
- **Identified code bug:** synthesis gating requires AIC engagement signals

## 20:40 — Chatbot handoff generated
- `chatbot_export_ethnic_studies_full.md` — 38.5KB, ~9600 tokens
- Original concern instructions had "students in personal crisis" — too vague

## 20:52 — Qwen full pipeline complete
- 3821.63s total, 119.43s/student
- S002 truncation NOT propagated (code bug)
- S018 feedback validates colorblind framing before redirecting (quality issue)
- 16 fragmented themes (meta-synthesis JSON parse failed)

## ~20:55 — Gemini handoff Run 1
- Pasted into Gemini Pro browser chatbot
- 2/3 concerns (missed S015 Brittany essentializing)
- 0 false positives, S029 CELEBRATED
- Theme quality exceptional (4 coherent themes)
- Jordan Espinoza: "leveraged neurodivergent writing style as meta-commentary"
- Imani Drayton: "AAVE as epistemological stance"

## 20:57 — Three code fixes implemented
1. Truncation propagation (generate_demo_insights.py)
2. Synthesis call fallback classifier (synthesizer.py)
3. Meta-synthesis JSON retry (theme_generator.py)

## 21:00 — Chatbot export prompt tightened
- Added AAVE/neurodivergent/multilingual protection
- Added essentializing linguistic patterns ("they always...", celebratory stereotypes)
- Replaced vague "personal crisis" with explicit 4-category concern list

## ~21:05 — Gemini handoff Run 2 (with tightened prompt)
- **3/3 concerns** — S015 NOW CAUGHT with excellent suggested response
- "What happens to a Black person who is exhausted and doesn't want to be resilient?"
- 0 false positives
- **Finding:** Linguistic pattern examples ("they always...") were the key missing element

## 21:15 — Backend bug found
- `--backend ollama` had no explicit handler, fell through to auto_detect → MLX
- Fixed: added explicit `ollama` and `mlx-llama` backend handlers

## 21:20 — Llama 3.1 8B MLX full pipeline started
- `--backend mlx-llama --no-resume`
- Model: `mlx-community/Meta-Llama-3.1-8B-Instruct-4bit`
- Same 32 students, same prompts, different base model

## 21:20 — MLX default changed
- `llm_backend.py` default: Qwen 2.5 7B → Llama 3.1 8B
- Based on early coding checkpoint showing richer theme tags

## 21:41 — Llama coding checkpoint analyzed
- S029 tags: "critique of traditional academic expectations" — model NOTICED the form
- S028 tags: "code-switching as survival strategy" — genuine engagement
- S027 tags: "critiquing neutrality in science" — specific, not generic
- Clear quality improvement over Qwen across all equity-critical students

## 22:06 — Llama concerns checkpoint
- S015 ✓ caught (essentializing)
- S018 ✗ missed (colorblind)
- S025 ✗ missed (tone policing)
- S029 ✓ CLEAN — no false positive
- **Finding:** Different failure profile from Qwen. Llama is conservative (0 FP, 1/3 detection)

## 22:09 — Synthesis-first prototype launched (Nemotron 9B via OpenRouter)
- Full-class reading pass → inject into per-student coding
- Class reading: 219 words (truncated by free tier), noticed Maria's multilingual syntax
- Concern detection: 0/3 (model too weak for structured JSON)
- Equity: 4/4 clean
- `what_student_is_reaching_for`: 3/7 populated (when model succeeded, descriptions were good)
- **Finding:** Architecture is directionally right, model insufficient for proof-of-concept

## 22:23 — Llama synthesis complete
- **4/4 calls succeeded** (first time)
- 5 highlights, 2 tensions, class temperature
- Synthesis fallback classifier working (9 strong students identified)

## 22:30 — Synthesis-first theory session
- Identified three universal oriented readers (asset, threshold, connection)
- Protective meta-check for equity
- Generalizability model across disciplines
- Adversarial critic pass, reader-not-judge, immanent critique as mechanisms

## 22:41 — Llama MLX full pipeline complete
- 4713.8s total, 147.31s/student

## 22:50 — Synthesis-first prototype on MLX Llama
- Class reading: 234.8s, rich observations
- Per-student coding: ~45s each, all 7 students
- **S015: MISSED** (was caught in standard Llama)
- **S018: CAUGHT** (was missed in standard Llama)
- S025: missed (both)
- S029: CLEAN (both)
- `what_student_is_reaching_for`: 7/7 populated

**KEY FINDING: Architecture shifts attention pattern, doesn't uniformly improve it.**
Standard + synthesis-first combined: 2/3 detection, 0 FP.
This is the complementary attention pattern — different architectures see different things.

## 22:55 — 70B and 27B prototype runs attempted (OpenRouter)
- Rate limited on free tier across all providers
- Retry logic added, runs pending
- These test whether model size or architecture is the primary driver

## Pending
- 70B/27B synthesis-first results (waiting for rate limit reset)
- Cloud enhancement test (anonymized patterns → larger cloud model)
- Full comparison report across all configurations
