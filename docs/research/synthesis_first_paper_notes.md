# Research Notes: Synthesis-First Architecture for Equity-Aware Educational Analytics

**Working title:** "Reading the Community: How Critical Pedagogy Architecture Improves Small Language Model Performance in Educational Analytics"

**Date:** 2026-03-22
**Researchers:** June (teacher-researcher, system designer), Claude (AI collaborator)
**Status:** Active experimentation, pre-draft

---

## Research Question

Can critical pedagogy frameworks, applied as architectural design principles (not just evaluation criteria), enable small (8B parameter) language models to produce educational analytics approaching the quality of much larger models — specifically on equity-critical tasks like protecting non-dominant student engagement from pathologization?

## Core Thesis

The "intelligence" producing rich educational analytics is partially located in the *structure of the inquiry*, not solely in the model's parameter count. A pipeline architecture grounded in Freire's critique of the banking model — reading student work as community dialogue rather than atomizing it into individual classifications — produces measurably different (and in key respects, better) outputs from the same small model.

## Theoretical Framework

### Primary frameworks applied as design principles

1. **Critical Pedagogy (Freire)** — The banking model critique maps directly onto pipeline architecture. Current pipeline: atomize student work → classify each submission → aggregate classifications → synthesize. This IS the banking model — "deposits" of coded data aggregated by an authoritative synthesizer. The alternative: read the community of learners as a dialogue, surface emergent tensions, then annotate individuals within that communal frame.

2. **Community Cultural Wealth (Yosso)** — Operationalized as the "asset reader" orientation. Rather than asking "what did this student produce?" ask "what is this student bringing?" This reframes non-standard writing, multilingual syntax, and neurodivergent form as assets to be named rather than deficits to be classified.

3. **Language Justice** — Operationalized as a protective constraint: AAVE, multilingual mixing, and neurodivergent writing are valid academic registers. The system must not pathologize non-dominant language use as a concern or deficit. This produces concrete design decisions in prompt engineering and concern detection.

4. **Disability Studies** — "Is the problem the body, or the built environment?" Applied to pipeline design: if a student's writing doesn't fit the expected form, is the problem the student or the system's expectations? Operationalized as the protective meta-check: "If this student is engaging differently from the expected form, am I about to misread them?"

5. **Interdependence** — "Does this assume independence as the goal, or design for mutual reliance?" The standard pipeline assumes each student's work is independently analyzable. The synthesis-first architecture assumes students are in dialogue — their work is interdependent, and meaning emerges from the relationships between submissions.

### Framework lineage
- Freire, P. (1970). *Pedagogy of the Oppressed*
- Yosso, T. J. (2005). "Whose culture has capital?"
- Crenshaw, K. (1989). "Demarginalizing the Intersection of Race and Sex"
- Baker-Bell, A. (2020). *Linguistic Justice*
- Kafer, A. (2013). *Feminist, Queer, Crip*

## Methodology

### Test corpus
32 synthetic student submissions for a high school Ethnic Studies assignment on intersectionality. Each student has a known "pattern" encoding specific characteristics:

**Equity-critical students (must NOT be flagged as concerns):**
- S023 Yolanda Fuentes — lived experience without academic vocabulary
- S024 Ingrid Vasquez — first-generation, material conditions
- S026 DeShawn Mercer — intersectional identity, discipline disparities
- S027 Camille Osei — outside source integration
- S028 Imani Drayton — AAVE as academic register
- S029 Jordan Espinoza — neurodivergent writing style, ADHD, dyslexia, Latino, honors

**Concern-detection students (MUST be flagged):**
- S015 Brittany Okafor — essentializing language (positive stereotyping)
- S018 Connor Walsh — colorblind ideology
- S025 Aiden Brooks — tone policing

**Additional patterns:** sustained AI-generated text (S010, S011), burnout/truncation (S002), premise challenger (S020), righteous anger (S022), etc.

### Models tested
| Model | Parameters | Quantization | Engine | Source |
|---|---|---|---|---|
| Qwen 2.5 7B Instruct | 7B | 4-bit | MLX | Local |
| Llama 3.1 8B Instruct | 8B | 4-bit | MLX | Local |
| Nemotron Nano 9B v2 | 9B | — | Cloud | OpenRouter free |
| Gemma 3 27B IT | 27B | — | Cloud | OpenRouter free |
| Llama 3.3 70B Instruct | 70B | — | Cloud | OpenRouter free |
| Gemini Pro | ~unknown | — | Cloud | Browser chatbot |

### Architecture variants tested
1. **Standard pipeline** — per-student coding → concern detection → theme generation → synthesis
2. **Chatbot handoff** — all 32 submissions in one prompt, single-pass full analysis
3. **Synthesis-first** — full-class free-form reading → inject as context → per-student coding

## Empirical Results (2026-03-22)

### Table 1: Concern Detection Across Configurations

| Configuration | S015 essentializing | S018 colorblind | S025 tone policing | S029 equity | Total |
|---|---|---|---|---|---|
| Qwen 7B standard | ✓ | ✓ | ✓ | ✗ FALSE POS | 3/3 but 1 FP |
| Llama 8B standard | ✓ | ✗ | ✗ | ✓ clean | 1/3, 0 FP |
| Llama 8B synthesis-first | ✗ | ✓ | ✗ | ✓ clean | 1/3, 0 FP |
| Llama 8B combined (both) | ✓ | ✓ | ✗ | ✓ clean | 2/3, 0 FP |
| Nemotron 9B synthesis-first | ✗ | ✗ | ✗ | ✓ clean | 0/3, 0 FP |
| Gemini Pro handoff Run 1 | ✗ | ✓ | ✓ | ✓ clean | 2/3, 0 FP |
| Gemini Pro handoff Run 2 | ✓ | ✓ | ✓ | ✓ clean | 3/3, 0 FP |

### Table 2: Qualitative Richness

| Configuration | Theme tags | what_student_is_reaching_for | Theme count | Synthesis calls |
|---|---|---|---|---|
| Qwen 7B standard | Generic | Not present | 16 (fragmented) | 2/4 |
| Llama 8B standard | Specific (e.g., "code-switching as survival strategy") | Not present | TBD | 4/4 |
| Llama 8B synthesis-first | Moderate | 7/7 populated | N/A (prototype) | N/A |
| Gemini Pro handoff | Exceptional | Implicit throughout | 4 (coherent) | N/A |

### Observation 1: Architecture appears to shift attention pattern

In our single run of each configuration, standard Llama caught essentializing (S015) but missed colorblind (S018). Synthesis-first Llama caught colorblind (S018) but missed essentializing (S015). This suggests the class reading may function as an attention mechanism that highlights certain patterns while de-emphasizing others.

**Caveat:** This is N=1 per configuration. LLMs are stochastic — the same model may produce different results on re-run. The "combined" 2/3 result is a theoretical union of two separate runs, not an actual combined pipeline. A real combined system might behave differently (e.g., synthesis-first context could suppress the standard detection). This observation needs replication before it can be called a finding.

**If it holds:** Multi-pass architecture with different attention orientations would be more robust than any single pass. This would connect to Haraway's situated knowledges — but we should earn that connection through replicated results, not claim it from a single observation.

### Observation 2: S029 equity protection appears model-dependent

Jordan Espinoza was correctly NOT flagged in all Llama configurations tested (standard, synthesis-first). The false positive only occurred with Qwen 2.5 7B. This suggests Llama's training handles the neurodivergent/engagement distinction better than Qwen's.

**Caveat:** Only two base models tested. We don't know if this is a general Llama property, something specific to 3.1 vs. 2.5 training, or stochastic variation. More models and multiple runs needed.

### Observation 3: Synthesis-first produces observation-type outputs

The `what_student_is_reaching_for` field was populated for 7/7 students in the synthesis-first prototype. This is a qualitatively different output from classification-type outputs like theme tags — it describes what the student seems to be intellectually reaching for rather than categorizing what they produced.

**Caveat:** "Reaching for" observations are not a new concept in education — this is what good teachers already do. The contribution (if any) is that the architecture elicits this from a small model. The quality of these observations compared to human teacher readings has not been evaluated.

### Observation 4: Model size and architecture are confounded in our comparison

Gemini Pro (very large model, single-pass architecture) produced the richest output. Llama 8B with synthesis-first produced useful but less eloquent observations. We cannot separate the contributions of model size vs. architecture from this comparison — Gemini's advantages may come entirely from scale, entirely from seeing all students at once, or from some combination.

**Needed:** Same architecture tested at multiple model sizes (8B, 27B, 70B synthesis-first) to isolate the architecture contribution. Pending — blocked by OpenRouter rate limits.

## Limitations

1. **N=1 per configuration.** Every result is from a single run. LLMs are stochastic — re-running the same configuration may produce different concern detection patterns. No reliability metrics exist for any finding.

2. **Single synthetic corpus.** All testing used one fabricated 32-student Ethnic Studies corpus. Real student writing is messier, more ambiguous, and may not conform to the clean patterns encoded in the test data. Generalizability to real classrooms is undemonstrated.

3. **Single subject area.** All results are from Ethnic Studies. The universal readers (asset, threshold, connection) are theoretically generalizable but have not been tested on STEM, arts, or other disciplines.

4. **Designed ground truth.** The "correct" concern flags are built into the corpus by the researcher, not established through independent human coding. The evaluation criteria embed specific theoretical commitments about what counts as a concern vs. engagement. Different educators might disagree about some cases.

5. **No human evaluation.** No teachers have evaluated the outputs for pedagogical usefulness. "Better" is currently measured against our designed benchmarks, not teacher judgment.

6. **Confounded comparisons.** Gemini Pro vs. Llama 8B differs in both model size AND architecture (single-pass vs. pipeline). The Qwen vs. Llama comparison differs in base model AND training data. Clean isolation of variables is incomplete.

7. **"Combined" results are theoretical.** The multi-pass combined detection (standard union synthesis-first = 2/3) was computed from the union of separate runs, not from an actual combined pipeline. A real implementation might produce different results.

8. **Incomplete model range.** 27B and 70B synthesis-first results are pending (OpenRouter rate limits). The critical test — same architecture at different scales — is unfinished.

9. **No prompt sensitivity analysis.** We don't know how much the results depend on specific prompt wording. The chatbot handoff improved from 2/3 to 3/3 with prompt changes, suggesting high sensitivity.

10. **Researcher reflexivity.** The corpus designer, pipeline designer, prompt engineer, and evaluator are the same research team. The research question and the evaluation criteria co-evolved during the session rather than being pre-registered.

## Gaps to Fill Before This Is a Paper

### Required (blocking)
- [ ] **Replication:** Run each configuration 3x minimum to check if results are stable
- [ ] **Actual combined pipeline:** Build and test standard + synthesis-first as a real multi-pass system, not a theoretical union
- [ ] **Complete model range:** Get 27B and 70B synthesis-first results for scale isolation
- [ ] **Second corpus:** Create an AP Biology or Pre-Calc corpus with equity-critical patterns to test generalizability

### Important (strengthening)
- [ ] **Teacher evaluation:** Have 2-3 teachers independently evaluate outputs for usefulness — do they prefer synthesis-first outputs?
- [ ] **Inter-rater reliability on ground truth:** Have other educators evaluate whether S015/S018/S025 should be flagged and S029 shouldn't, independent of our design
- [ ] **Cloud enhancement test:** The anonymized-patterns-to-cloud-model pipeline is built but untested
- [ ] **Adversarial critic pass:** Proposed but not prototyped
- [ ] **Prompt sensitivity:** Run same architecture with varied prompts to measure stability

### Nice to have (enriching)
- [ ] Real classroom data comparison (FERPA-compliant, teacher does privately)
- [ ] Ablation study: class reading without structured orientations, vs. with
- [ ] Longitudinal: does synthesis-first quality hold across multiple assignments?
- [ ] Cost/time analysis: synthesis-first adds one full-class pass — what's the overhead?

## Open Questions

1. Is the complementary attention pattern (standard catches X, synthesis-first catches Y) reliable or was it stochastic variation in a single run?
2. At what model size does the architecture contribution become negligible — do 70B models produce equivalent results regardless of pipeline structure?
3. Does the asset/threshold/connection framing genuinely help the class reading, or would an unstructured "read and notice" prompt work as well?
4. Can the adversarial critic pass close the remaining gap on S025 (tone policing)?
5. How does the system perform with real (not synthetic) student work?

## Venue Considerations

- **LAK (Learning Analytics & Knowledge)** — natural fit for educational AI with equity focus
- **AIED (AI in Education)** — applied educational AI research
- **FAccT (Fairness, Accountability, Transparency)** — equity-first AI design
- **ACL/EMNLP** — if framed as architecture/prompting contribution
- **CHI/CSCW** — if framed as teacher-centered design research

## Conversation Artifacts

The research emerged through an extended collaborative conversation tracked by the Reframe Philosophy Engine (hooks logging framework application, drift detection, temporal reflections). Conversation state may be recoverable from:
- `.reframe/session/` — per-session framework application data
- Claude Code conversation history
- Git commit history on the `ux/review-insights-merge` branch

## Files

- Prototype: `scripts/prototype_synthesis_first.py`
- Test corpus: `data/demo_corpus/ethnic_studies.json`
- Qwen results: `src/demo_assets/insights_ethnic_studies.json`
- Llama results: `src/demo_assets/insights_ethnic_studies_llama8b_mlx.json` (when written)
- Synthesis-first results: `data/demo_baked/synthesis_first_prototype_mlx_llama.json`
- Gemini handoff outputs: `data/demo_baked/Gemini_handoff_output.md`, `Gemini_handoff_output_t2.md`
- Analysis report: `data/demo_baked/round2_8b_analysis.md`
- Chatbot export: `data/demo_baked/chatbot_export_ethnic_studies_full.md`
- Architecture memory: `memory/project_synthesis_first_architecture.md`
