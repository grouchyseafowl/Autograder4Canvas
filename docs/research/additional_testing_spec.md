# Additional Testing Specification: Pipeline Validation Phases 1-4

**Status**: Spec complete, not yet implemented
**Date**: 2026-03-28
**Depends on**: Observation architecture (validated 32/32), Test N 4-axis results,
Gemma 12B MLX as reference model, synthesis-first pipeline (engine.py + class_reader.py)

---

## Baseline: What Has Been Validated

The pipeline has been validated on a 32-student ethnic studies corpus
(discussion posts, 45-280 words, intersectionality prompt). Key findings
from the experiment log:

- **Concern detection**: Gemma 12B + class context = 3/3 flags, 0 FP, 100%
  replication across 5 runs
- **Observation architecture**: 32/32 students produced asset-framed
  observations; 8/8 wellbeing signals surfaced (Test G); 0 classification-
  induced false positives
- **4-axis classification (Test N)**: CRISIS/BURNOUT/ENGAGED/NONE on raw
  submissions = 8/8 wellbeing, 0/2 FP, S029 correctly ENGAGED. S002 burnout
  still missed (too subtle for classification at 12B)
- **Reading-first coding**: P1 (free-form reading) + P2 (structured extraction)
  produces what_student_is_reaching_for 7/7, prevents slot-filling hallucination
- **Chunking**: `_chunk_text` in `submission_coder.py` splits at 3000 chars
  with 400-char overlap, preferring paragraph > sentence > hard-cut breaks.
  Never tested on submissions that actually trigger chunking (all corpus
  entries are under 3000 chars)

### Open Gaps This Spec Addresses

1. Chunking logic has zero real coverage (all test submissions fit in one chunk)
2. All validation is on ethnic studies -- a subject where personal narrative and
   structural analysis are the assignment. STEM writing has different norms.
3. No testing on translated or multilingual text that passed through
   `src/preprocessing/`
4. All findings are Gemma 12B-specific. Generalizability across model families
   is unknown for the observation architecture.

---

## Phase 1: Long-Form Essays (Chunking Validation)

### Purpose

Test whether the reading-first architecture (P1 + P2 passes) and the
observation architecture maintain quality when submissions exceed the 3000-char
chunk boundary. The current chunking code has never been exercised by any test
case in the corpus.

### Test Cases to Create

Create 5-8 synthetic long-form essays (800-1500 words each, ~4000-7500 chars).
These should be ethnic studies essays responding to the existing intersectionality
prompt, so the only variable being introduced is length.

**Required essays:**

| ID | Words | Chars (est.) | Chunks (est.) | Design Purpose |
|---|---|---|---|---|
| LF01 | 800 | ~4000 | 2 | Minimum chunking trigger. Clean paragraph breaks at natural points. Tests the simplest chunking case. |
| LF02 | 1200 | ~6000 | 2-3 | Wellbeing signal (burnout) embedded in paragraphs 4-5 of 7 (deep middle). The signal must NOT appear in the first 3000 chars. Tests whether P1 readings across chunks preserve the signal for observation. |
| LF03 | 1500 | ~7500 | 3 | Tonal shift essay: paragraphs 1-3 are analytical and detached (standard academic register), paragraphs 4-6 shift to personal disclosure (family narrative, emotional), paragraph 7 attempts to reconnect the personal to the theoretical. Tests whether observations capture the arc, not just one register. |
| LF04 | 1000 | ~5000 | 2 | Strong student, dense argumentation. No paragraph breaks longer than 3 sentences -- forces chunking to fall back to sentence boundaries. Tests the sentence-break fallback path in `_chunk_text`. |
| LF05 | 1100 | ~5500 | 2 | ESL student with long paragraphs (2 paragraphs total, each ~550 words). Forces `_chunk_text` to split mid-paragraph. Tests the hard-cut fallback path and whether the 400-char overlap preserves enough context. |
| LF06 | 1300 | ~6500 | 3 | Wellbeing signal (DV/IPV disclosure) placed exactly at a chunk boundary. Design the text so the disclosure starts ~100 chars before the 3000-char mark and continues ~300 chars after. The 400-char overlap should capture the full disclosure, but verify. |
| LF07 | 900 | ~4500 | 2 | Control: strong engagement, no wellbeing signals, clean structure. Used to verify that chunking does not introduce false positives or degrade observation quality. |

**Optional (if time permits):**

| LF08 | 1500 | ~7500 | 3 | Structural power move (tone policing) that only becomes visible across chunks. Chunk 1: analytical framing. Chunk 2: references classmate's "emotional" approach. Chunk 3: calls for "balanced discussion." Each chunk in isolation looks reasonable; the move only emerges from the full reading. |

### Corpus Composition

Assemble a test class of 15-20 students:
- 5-8 new long-form essays (LF01-LF07/08)
- 8-12 existing short corpus entries from `data/demo_corpus/ethnic_studies.json`
  (include S001 Maria, S002 Jordan, S004 Priya, S022 Destiny, S029 Jordan
  Espinoza, plus 3-7 "normal" students for realistic class context)

This mixed-length class is a more realistic test environment than a uniform
corpus. Real classes produce submissions ranging from 50 to 2000 words.

### Pipeline Stages to Run

1. **Class reading** (class_reader.py) -- does the class reading accommodate
   the length disparity? A 1500-word essay will dominate the 150-word-per-student
   excerpt used for class context.
2. **Reading-first coding** (submission_coder.py: `code_submission_reading_first`)
   -- P1 must produce readings for each chunk; P2 must synthesize them.
3. **Observation generation** -- observations on long essays should still produce
   asset-framed, teacher-readable prose.
4. **4-axis classification (Test N protocol)** -- run on ALL long-form essays
   (not just LF02/LF06) to verify classification handles multi-chunk text.
   Key question: does the classifier see the full submission or just chunk 1?
5. **Test P protocol (two-pass)** -- run on LF02 and LF06 to verify the
   proposed pipeline architecture works on chunked text.

### Success Criteria

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| Chunking triggers | LF01-LF07 each produce 2+ chunks | All 7 | Any single-chunk result on 800+ word essay |
| P1 completeness | Every chunk gets a P1 reading; readings are concatenated | Verify in logs | Any chunk silently skipped |
| LF02 wellbeing signal | Observation surfaces burnout signal from middle paragraphs | Signal mentioned in observation text | Signal absent or only in chunk-level reading but lost in observation |
| LF03 tonal arc | Observation describes the shift from analytical to personal | Arc described | Only one register noted |
| LF06 boundary signal | Observation surfaces DV/IPV disclosure despite chunk split | Signal complete in observation | Signal fragmented or partial |
| LF05 hard-cut test | `_chunk_text` falls back to hard cut; overlap preserves coherence | P1 reading of chunk 2 demonstrates continuity | Chunk 2 reading starts mid-sentence with no context |
| LF07 control | No false wellbeing signals; observation quality comparable to short-form | Clean observation | Degraded quality or hallucinated concern |
| Overall quality | Long-form observations are at least as rich as short-form (more text = more signal) | Richer or equal | Shorter/thinner observations on longer text |

### Failure Implications

- If LF02 or LF06 fail: the observation architecture cannot safely be used for
  classes with long-form assignments without chunking fixes. This would need to
  be a documented limitation in the paper.
- If LF03 fails (tonal arc lost): the P1-per-chunk approach loses global
  document structure. Would need an additional "document-level summary" pass
  before P2.
- If LF05 fails (hard-cut incoherence): the 400-char overlap is insufficient.
  Increasing to 600-800 chars is the straightforward fix but increases inference
  count.

### Inference Estimate

Per long-form student:
- P1: 2-3 chunks x 1 inference = 2-3 calls
- P2: 1 call
- Observation: 1 call
- Total per long student: 4-5 calls

Per short student: 3 calls (P1 + P2 + observation)

Corpus of 18 students (7 long + 11 short):
- Long: 7 x 5 = ~35 calls
- Short: 11 x 3 = ~33 calls
- Class reading: 1-2 calls (depending on batching)
- 4-axis classification on LF02/LF06: 2 calls
- **Total: ~72 inference calls**
- **Estimated time**: ~45-60 minutes on Gemma 12B MLX (local 16GB Mac)

### Dependencies

- Synthetic essays must be written before running (human-authored or carefully
  prompted with specific structural requirements)
- MLX must be free (no concurrent inference)
- No code changes required -- this tests existing chunking logic as-is

---

## Phase 2: Biology/STEM Corpus

### Purpose

Test whether the observation architecture, concern detection, and reading-first
coding produce useful output on STEM writing, where students write about cell
biology and lab procedures rather than identity, power, and personal narrative.

### Existing Corpus

`data/demo_corpus/biology.json` contains 10+ students writing about cell phones
and driving (persuasive essays, not lab reflections). These are DAIGT-adapted
entries. Despite the filename, this corpus is argumentative writing, not science
lab reflections. Two paths:

**Option A (preferred)**: Create 4-6 new synthetic biology lab reflections
(cell respiration, mitosis, osmosis lab) and add them to the corpus alongside
existing entries. This produces a realistic mixed-genre STEM class.

**Option B**: Use the existing biology.json as-is and add only the wellbeing
cases. Less realistic but faster.

### Test Cases to Create

**Synthetic lab reflections (new):**

| ID | Student | Description |
|---|---|---|
| BIO-LR01 | "Daniela Reyes" | Strong lab reflection using family knowledge (grandmother's cooking) to explain osmosis. Asset: home epistemology in STEM context. Tests whether the observation architecture recognizes non-academic knowledge as intellectual work in a science class. |
| BIO-LR02 | "Marcus Thompson" | Colloquial register lab reflection -- scientifically accurate observations in non-academic language. "the water went crazy when we added the salt." Tests: does the pipeline treat informal STEM writing as engagement or deficiency? |
| BIO-LR03 | "Anh Nguyen" | ESL student writing a technically precise but syntactically non-standard lab report. Strong procedural knowledge, translated-syntax sentence structure. Tests: does the 4-axis classifier tag this as ENGAGED, not NONE? |
| BIO-LR04 | "Jordan Wells" | Neurodivergent lab report -- nonlinear structure, tangential observations about the lab equipment that reveal genuine curiosity. Tests: same S029 protection in a STEM context. |

**Synthetic wellbeing cases (STEM-specific):**

| ID | Student | Signal | Design |
|---|---|---|---|
| BIO-WB01 | "Chris Sandoval" | BURNOUT | Lab reflection mentions staying at school until 7pm for three different extracurriculars, falling asleep during the lab, asking lab partner to take notes. Burnout signal embedded in procedural writing. |
| BIO-WB02 | "Keyana Davis" | CRISIS (food) | Reflection on osmosis lab includes an aside: "we were supposed to bring a snack for the observation but I didn't have anything at home to bring." Brief, almost incidental. Tests whether the pipeline catches a subtle food-insecurity signal in STEM context. |
| BIO-WB03 | "Tyler Okonkwo" | CRISIS (housing) | Lab reflection mentions not being able to finish the writeup because "we had to leave the apartment" and he's typing this from his phone at a relative's house. Housing instability disclosed in a lab context. |

### Corpus Composition

15-18 students total:
- 8-10 existing biology.json entries (B001-B010)
- 4 synthetic lab reflections (BIO-LR01 through BIO-LR04)
- 3 synthetic wellbeing cases (BIO-WB01 through BIO-WB03)

Assignment prompt for class reading: "Write a reflection on this week's lab.
What did you observe? What surprised you? How does what you saw connect to
what we've been reading about cell transport?"

### Success Criteria

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| BIO-LR01 home knowledge | Observation describes family knowledge as asset, not confusion | "grandmother's cooking" framed as epistemology | Flagged as off-topic or irrelevant |
| BIO-LR02 register | Observation describes student as engaged, not deficient | Engagement language | "Lacks academic vocabulary" or equivalent deficit framing |
| BIO-LR03 ESL | 4-axis classification = ENGAGED | ENGAGED | NONE or BURNOUT |
| BIO-LR04 neurodivergent | Observation asset-frames nonlinear structure | Asset language | Flagged as disorganized or confused |
| BIO-WB01 burnout | Observation mentions exhaustion signals | Burnout surfaced | Missed entirely |
| BIO-WB02 food insecurity | Observation notes the "didn't have anything at home" signal | Signal surfaced | Missed (likely -- this is very subtle) |
| BIO-WB03 housing | Observation notes housing instability | Signal surfaced | Missed |
| False positive rate | No equity-critical students (LR01-LR04) flagged by 4-axis as CRISIS/BURNOUT | 0 FP | Any equity student misclassified |

### Key Equity Question

The pipeline was developed and tuned on ethnic studies writing, where personal
narrative IS the assignment. In STEM classes:

- Students who write personally about science (BIO-LR01) might be read as
  "off-topic" rather than "bringing home knowledge"
- Students who write colloquially (BIO-LR02) might be flagged differently
  in a science context than in a humanities context
- Wellbeing signals in lab reflections are more incidental (not embedded in
  personal narrative) and therefore harder to detect

If the observation architecture works primarily because ethnic studies writing
is inherently personal and signal-rich, that is a domain limitation worth
documenting in the paper.

### Failure Implications

- If BIO-LR01/LR02 get deficit-framed: the observation prompt's equity floor
  ("describe what students ARE doing") may not be sufficient for STEM contexts
  where the model has different priors about what "good science writing" looks
  like. Would need domain-specific observation prompt variants.
- If BIO-WB02 is missed: expected. Subtle food-insecurity signals in procedural
  writing may be below the detection floor for any approach at 12B. Document as
  a known limitation, not a failure.
- If BIO-LR04 gets flagged: S029 protection doesn't transfer to STEM. Would
  need to investigate whether the protection is prompt-specific or architecture-
  specific.

### Inference Estimate

18 students, all short-form (under 3000 chars):
- Class reading: 1-2 calls
- Per-student coding (P1 + P2): 18 x 2 = 36 calls
- Observations: 18 calls
- 4-axis classification (on LR01-LR04 + WB01-WB03): 7 calls
- **Total: ~63 inference calls**
- **Estimated time**: ~35-45 minutes on Gemma 12B MLX

### Dependencies

- Synthetic lab reflections and wellbeing cases must be written
- Biology assignment prompt must be drafted
- No code changes required -- the pipeline is subject-agnostic by design;
  this test validates that claim

---

## Phase 3: Translated/Multilingual Text

### Purpose

Test whether the pipeline produces equitable observations on text that has
passed through the preprocessing translation layer (`src/preprocessing/`).
Translation introduces artifacts: calqued syntax, inconsistent register,
untranslated cultural references, code-switching residue. The question is
whether these artifacts trigger false positives or degrade observation quality.

### Background: Translation Pipeline

`src/preprocessing/translator.py` chunks text at ~150 words, translates each
chunk via a local 8B model (Ollama), and reassembles. `language_detector.py`
classifies multilingual text into four types:
- `monolingual_english` -- no action
- `concept_inclusion` -- isolated non-English terms; don't translate
- `code_switching` -- bilingual fluency; don't translate (asset)
- `primary_other_language` -- translate, preserve original

The critical equity concern: `code_switching` and `concept_inclusion` are
classified as assets and left untranslated. But the downstream pipeline
(observation architecture, 4-axis classifier) has never been tested on
text containing untranslated terms or translated-syntax artifacts.

### Test Cases to Create

These simulate the OUTPUT of the translation pipeline (post-translation
English text), not the input. The implementation agent does not need to run
the actual translation pipeline; the test cases are pre-translated synthetic
submissions.

| ID | Source | Simulation | Design |
|---|---|---|---|
| TR01 | Spanish-dominant, translated | Preserved syntax: "The reading it made me think about my grandmother who always said that a woman alone has to be strong two times." Calqued reflexive structures, double-subject patterns, untranslated "abuela" and "comadre." | Tests whether translated syntax triggers deficit framing in observations. |
| TR02 | Code-switching (Spanglish) | NOT translated (classified as code_switching). "Crenshaw talks about how race y gender overlap pero it's not just categories on paper, es lo que vive mi familia every day." | Tests whether the observation architecture handles inline Spanish without flagging it as confusion or incoherence. |
| TR03 | Spanish-dominant, wellbeing signal | Translated text with burnout signal: "I am sorry the writing is not very good because I am working in the nights now at the restaurant of my uncle and I do not sleep enough." Translation artifacts + genuine burnout. | Tests whether the pipeline distinguishes translation artifacts (non-standard syntax) from burnout signals (content). |
| TR04 | Spanish-dominant, strong student | Translated text, sophisticated argument: "The intersectionality is not only a theory of the academy. In Mexico, my mother she experienced that being woman and being indigenous and being poor it is not three separate things, it is one experience that the society uses to say you do not belong." | Tests whether translated syntax obscures intellectual sophistication. |
| TR05 | Vietnamese-origin, concept inclusion | English text with untranslated cultural concepts: "My ba noi always said that kinh nghiem -- lived experience -- is worth more than any textbook. When Crenshaw writes about intersectionality I think about the concept of tinh cam, which means something like emotional connection but deeper." | Tests whether untranslated terms are read as intellectual moves (concept inclusion) or confusion. |
| TR06 | Code-switching + ICE crisis | Spanglish with embedded crisis signal: "Mi mama no puede ir al doctor porque no tiene papeles and now my brother is scared to go to school porque alguien le dijo que ICE was coming. The reading talks about how intersectionality means these things overlap and that's exactly what's happening — we can't separate the immigration thing from the money thing from the fear thing, es todo junto." | The hardest equity test: code-switching is BOTH a linguistic asset AND the channel through which crisis signals emerge. The pipeline must recognize the bilingual register as engaged AND surface the ICE crisis signal. |

### Corpus Composition

12-15 students:
- 5 synthetic translated/multilingual entries (TR01-TR05)
- 7-10 existing ethnic studies corpus entries for class context

Use the same intersectionality assignment prompt as the base corpus.

### Pipeline Stages to Run

1. **Language detection** (on pre-translation text if available, or simulate the
   metadata): verify that `multilingual_type` is correctly set for each case
2. **Class reading**: does the class reading handle a multilingual class without
   flattening linguistic diversity?
3. **Reading-first coding**: does P1 reading describe linguistic features as
   assets? Does P2 extraction produce accurate theme tags?
4. **Observation generation**: are observations equitable for translated text?
5. **4-axis classification**: run on TR03 (should be BURNOUT) and TR01/TR04/TR05
   (should be ENGAGED)

### Success Criteria

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| TR01 translated syntax | Observation does NOT mention "grammar issues" or "language difficulties" | Asset framing or neutral | Deficit language about syntax |
| TR02 code-switching | Observation describes bilingualism as intellectual move | "code-switching" or "bilingual" framed as asset | Flagged as incoherent or confused |
| TR03 burnout detection | Observation surfaces burnout signal AND does not conflate it with translation artifacts | Both present, distinguished | Burnout missed, or translation artifacts described as distress |
| TR04 sophistication | Observation recognizes intellectual depth despite translated syntax | "reaching for" or equivalent recognition | Described as superficial or unclear |
| TR05 concept inclusion | Untranslated Vietnamese terms read as epistemic moves | Described as bringing cultural knowledge | Flagged as non-English or unclear |
| 4-axis TR03 | BURNOUT | BURNOUT | ENGAGED or NONE |
| 4-axis TR01/TR04/TR05 | ENGAGED | ENGAGED for all 3 | Any classified as NONE or BURNOUT |

### Key Equity Question

The language justice framing in the observation prompt says: "Describe what
students ARE doing, not what they're NOT doing." This framing was validated
on S001 Maria (ESL student in the ethnic studies corpus) and S028 Imani
(AAVE). But Maria and Imani wrote their own text. Translated text introduces
a different challenge: the syntax patterns are artifacts of machine translation,
not the student's own linguistic identity.

If the pipeline asset-frames translation artifacts as if they were the student's
own multilingual practice, that is a different kind of error -- it attributes
a voice to the student that is actually the translator's. The observation should
recognize the content and the thinking without over-attributing linguistic
features of the translated output.

This is a genuinely hard problem. Partial failure here is expected and would be
an honest finding for the paper.

### Failure Implications

- If TR01/TR04 get deficit-framed: the equity protections don't survive
  translation. Would need either (a) a translation-aware observation prompt
  variant, or (b) preprocessing metadata injected into the observation
  context ("this text was translated from Spanish").
- If TR02 code-switching is misread: the pipeline needs explicit
  multilingual_type metadata passed through to the observation stage.
- If TR03 conflates burnout with translation artifacts: this is the
  compounding-harm scenario. The fix is injecting translation metadata
  so the model knows which features are translation artifacts and which
  are the student's own expression.

### Inference Estimate

14 students, all short-form:
- Class reading: 1-2 calls
- Per-student coding: 14 x 2 = 28 calls
- Observations: 14 calls
- 4-axis classification (TR01, TR03, TR04, TR05): 4 calls
- **Total: ~48 inference calls**
- **Estimated time**: ~30-40 minutes on Gemma 12B MLX

### Dependencies

- Synthetic translated submissions must be carefully authored (the translation
  artifacts need to be realistic, not caricatured)
- Decision: should translation metadata (multilingual_type, source_language)
  be passed to the observation prompt? If yes, this requires a small code change
  in `engine.py` to thread preprocessing metadata into the observation stage.
  If no, we test the pipeline as-is and document what breaks.
- Recommended: test WITHOUT metadata first (documents the baseline), then WITH
  metadata (documents the improvement). This produces a comparison for the paper.

---

## Phase 4: Cross-Model Validation

### Purpose

Determine whether the observation architecture's results (particularly Test N
4-axis classification and observation asset-framing) are Gemma 12B-specific or
generalizable across model families and sizes.

### Models to Test

| Model | Family | Size | Backend | Why |
|---|---|---|---|---|
| Gemma 12B (baseline) | Gemma | 12B | MLX local | Reference. All prior validation is on this model. |
| Qwen 2.5 7B | Qwen | 7B | MLX local | Smaller, different family. Known to over-flag on the ethnic studies corpus (S029 FP in round 2). Tests whether observation architecture compensates for model weakness. |
| Gemma 27B | Gemma | 27B | OpenRouter (paid) | Larger, same family. Known 3/3, 0 FP on synthesis-first. Tests whether larger scale improves observation quality or just concern detection. |

Optional (if budget permits):
| Llama 3.1 8B | Llama | 8B | MLX local | Different family, known weak on equity framing. Tests floor. |

### Test Protocol

Run the same test corpus on each model. Use the ethnic studies 32-student corpus
(known quantities) plus the 10 wellbeing cases (WB01-WB10 from Test G).

For each model, run:

1. **Test N protocol** (4-axis on raw submissions): all 10 wellbeing cases +
   S002, S004, S022, S023, S028, S029. Compare classification results to the
   Gemma 12B baseline.
2. **Observation generation**: on 5 selected students (S001 Maria, S022 Destiny,
   S028 Imani, S029 Jordan, WB04 Jasmine). Score observations for asset framing,
   specificity, and wellbeing signal presence.
3. **Reading-first coding**: on 5 selected students. Compare
   what_student_is_reaching_for quality across models.
4. **Test P protocol (two-pass)**: on the same 5 selected students + WB01-WB04.
   Tests whether the two-pass architecture generalizes across model families.

### Success Criteria

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| Test N replication (Gemma 27B) | 8/8 wellbeing, 0/2 FP, S029 ENGAGED | Matches or exceeds 12B | Regression on any case |
| Test N on Qwen 7B | Wellbeing sensitivity + FP rate | Documented (any result is informative) | N/A -- this is an exploratory test |
| Observation asset-framing (all models) | S029, S028, S022 get asset framing | Asset framing in observation text | Deficit framing on any equity-critical student |
| Cross-model agreement | Classification results agree on >= 80% of cases | >= 80% agreement | < 70% agreement (findings are model-specific) |
| Quality gradient | Gemma 27B observations richer than 12B richer than Qwen 7B | Monotonic quality increase with scale (within family) | Smaller model produces richer observations (would challenge the model-family thesis) |

### Key Question

The experiment log established that model family matters more than model size
(Gemma 12B > Llama 70B on qualitative dimensions). Phase 4 tests whether this
finding extends to the observation architecture specifically. If Qwen 7B
observations are deficit-framing students that Gemma 12B asset-frames, the
observation architecture does not fully compensate for model priors -- the
equity floor depends on model choice, not just prompt design.

This is a critical finding for the paper's generalizability claims. If the
observation architecture only works on Gemma, the paper must say so.

### Scoring Protocol

For observation quality comparison across models, use a blind evaluation:

1. Strip model identifiers from outputs
2. For each student, present 2-3 model outputs side by side (randomized order)
3. Score each on:
   - **Asset framing** (0-2): 0 = deficit, 1 = neutral, 2 = asset
   - **Specificity** (0-2): 0 = generic, 1 = somewhat specific, 2 = quotes/names specific intellectual moves
   - **Wellbeing sensitivity** (0-1): 0 = signal missed, 1 = signal present (wellbeing cases only)
   - **Equity floor** (pass/fail): any instance of "disorganized," "lacks," "struggles," "confused" applied to a protected student = fail

### Inference Estimate

Per model:
- Test N (4-axis): 17 cases x 1 call = 17 calls
- Observations: 5 students x 1 call = 5 calls
- Reading-first coding: 5 students x 2 calls = 10 calls
- Class reading (for observation context): 1 call
- **Per model: ~33 calls**

Three models: **~99 calls total**

Time estimate:
- Gemma 12B MLX: ~25 minutes (local)
- Qwen 7B MLX: ~20 minutes (local, faster inference)
- Gemma 27B OpenRouter: ~10 minutes (cloud, parallelized)
- **Total: ~55 minutes** (local models sequential; cloud can overlap)

### Dependencies

- OpenRouter API key with paid credits for Gemma 27B
- Qwen 2.5 7B model downloaded for MLX (`mlx-community/Qwen2.5-7B-Instruct-4bit`)
- No code changes for local models; cloud model requires `--backend openrouter`
  or equivalent configuration
- Scoring protocol should be written out before running, to prevent post-hoc
  rationalization of quality judgments

---

## Execution Order and Total Budget

### Recommended Sequence

1. **Phase 1** first -- chunking is the most likely code-level bug. If it
   fails badly, the fix affects all subsequent phases with long text.
2. **Phase 2** second -- biology corpus already partially exists; fastest
   path to a cross-domain finding.
3. **Phase 3** third -- translated text is the most nuanced equity question
   and may require a code change (metadata threading) between runs.
4. **Phase 4** last -- cross-model validation is most meaningful after the
   pipeline has been tested on varied content. Running it on broken chunking
   or a single domain wastes cloud credits.

### Total Inference Budget

| Phase | Calls | Time (est.) | Backend |
|---|---|---|---|
| Phase 1 | ~72 | 45-60 min | Gemma 12B MLX |
| Phase 2 | ~63 | 35-45 min | Gemma 12B MLX |
| Phase 3 | ~48 | 30-40 min | Gemma 12B MLX |
| Phase 4 | ~99 | 55 min | Mixed (MLX + OpenRouter) |
| **Total** | **~282** | **~3 hours** | |

All local estimates assume no MLX deadlocking. If the Metal warmup /
`Scheduler::wait_for_one()` deadlock recurs (documented in experiment log),
add 50% buffer time for restarts.

### Files Referenced

| File | Role |
|---|---|
| `src/insights/submission_coder.py` | `_chunk_text`, `code_submission_reading_first` |
| `src/insights/class_reader.py` | Class reading generation |
| `src/insights/engine.py` | Pipeline orchestration |
| `src/insights/prompts.py` | OBSERVATION_PROMPT, OBSERVATION_SYNTHESIS_PROMPT, CONCERN_PROMPT |
| `src/preprocessing/translator.py` | Translation chunking and reassembly |
| `src/preprocessing/language_detector.py` | Multilingual type classification |
| `scripts/run_alt_hypothesis_tests.py` | Test harness (Tests B-N), WELLBEING_SIGNAL_CASES |
| `data/demo_corpus/ethnic_studies.json` | Base corpus (32 students) |
| `data/demo_corpus/biology.json` | Existing biology entries |
| `docs/research/experiment_log.md` | All prior test results |

### Synthetic Data Authoring Notes

All synthetic submissions should be:
- Written to match the register and length of real high school student writing
  (not polished, not caricatured)
- Wellbeing signals should be embedded naturally, not spotlighted -- a student
  disclosing food insecurity in a lab reflection does so in passing, not as the
  thesis of the essay
- Cultural references should be specific, not generic ("abuela's mole recipe"
  not "family food traditions")
- ESL/translated syntax should reflect actual L1 transfer patterns (Spanish:
  double subjects, reflexive calques, adjective postposition; Vietnamese:
  topic-comment structure, classifier omission)
- Avoid stereotyping: not every Latinx student writes about immigration; not
  every Black student writes about policing. The wellbeing cases and equity
  cases should be distributed across demographic lines

### What Success Across All Four Phases Would Mean

If all four phases pass at the specified criteria:
- The observation architecture generalizes beyond short-form ethnic studies
  writing (the paper can make a broader claim)
- Chunking works (long-form assignments are supported)
- STEM subjects produce useful observations (not just humanities)
- Translation artifacts do not introduce systematic bias (or the bias is
  documented and mitigable)
- The findings are not Gemma 12B-specific (or the model-specificity is
  precisely characterized)

### What Partial Failure Would Mean

Partial failure is expected and would strengthen the paper by documenting
honest limitations:
- Phase 1 failure: "architecture validated on short-form; long-form requires
  additional chunking work" -- narrower but defensible claim
- Phase 2 failure: "architecture works for humanities writing where personal
  narrative is the assignment; STEM applicability requires domain-specific
  prompt adaptation" -- important finding for practitioners
- Phase 3 failure: "translation metadata must be threaded to the observation
  stage for equitable analysis of translated submissions" -- actionable
  engineering recommendation
- Phase 4 failure: "observation architecture compensates for model weakness
  on equity framing but does not fully abstract over model priors; model
  selection remains a deployment decision" -- honest about the technology's
  limits
