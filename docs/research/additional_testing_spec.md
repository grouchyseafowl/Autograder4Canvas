# Additional Testing Specification: Pipeline Validation Phases 1-4

**Status**: Revised 2026-03-28 (post-QC). Spec complete, not yet implemented.
**Date**: 2026-03-28
**Revision**: v2 — updated to reflect observation architecture, 4-axis
wellbeing classifier (Test N), reading-first coding, and pipeline
architecture changes from 2026-03-22 through 2026-03-28 experiment sessions.
**Depends on**: Observation architecture (validated 32/32), Test N 4-axis
results (8/8, 0 FP, n=4 at temp 0.1), Gemma 12B MLX as reference model,
synthesis-first pipeline (engine.py + class_reader.py), per-student
checkpointing (implemented).
**Pending**: Temp 0.3 replication results for Tests N and P. If results
are unstable at temp 0.3, Phase 4 cross-model design may need adjustment.

---

## Baseline: What Has Been Validated

The pipeline has been validated on a 32-student ethnic studies corpus
(discussion posts, 45-280 words, intersectionality prompt). Key findings
from the experiment log (2026-03-22 through 2026-03-28):

- **Observation architecture**: 32/32 students produced asset-framed
  observations; 8/8 wellbeing signals surfaced (Test G); 0 classification-
  induced false positives; consistent across 3 model families (Test E:
  16/16 ASSET across Gemma 12B, Qwen 7B, Gemma 27B)
- **4-axis wellbeing classification (Test N)**: CRISIS/BURNOUT/ENGAGED/NONE
  on raw submissions = 8/8 wellbeing signals caught, 0/2 false positives,
  S029 correctly ENGAGED, S028 correctly ENGAGED. Replicated at n=4 (temp
  0.1, deterministic). S002 burnout still classified ENGAGED (too subtle for
  single-submission classification at 12B — only generative observation
  catches the fatigue signal)
- **Binary concern detection superseded**: Binary FLAG/CLEAR produced
  systematic disparate impact — S029 false-flagged 25/25 runs (simplified),
  S028 false-flagged by production detector. Replaced by 4-axis classifier
  + observation architecture (see pipeline_architecture_spec.md)
- **Reading-first coding**: P1 (free-form reading) + P2 (structured extraction)
  produces what_student_is_reaching_for 7/7, prevents slot-filling hallucination.
  Asset framing where standard coding produces deficit framing (Tyler: "lacks
  personal connection" → "prioritizing clarity over performative elaboration")
- **Synthesis-first class reading**: Class context required for relational harm
  detection (tone policing invisible without it, even on 27B). Sublinear
  scaling: 2x students → 1.4x time
- **Chunking**: `_chunk_text` in `submission_coder.py` splits at 3000 chars
  with 400-char overlap, preferring paragraph > sentence > hard-cut breaks.
  Never tested on submissions that actually trigger chunking (all corpus
  entries are under 3000 chars)
- **Per-student checkpointing**: Implemented. Each student's coding record
  saves to SQLite store immediately on completion. Pipeline crash recovery
  resumes from last completed student, not from scratch.

### Current Pipeline Stage Order

1. Data Fetch (from Canvas)
2. Preprocessing (translation/transcription)
3. Quick Analysis (non-LLM: signal matrix, word counts, sentiment)
4. Class Reading (synthesis-first, reads class as community)
5. Per-Submission Coding (reading-first: P1 free-form per chunk → P2 extraction)
6. Wellbeing Classification (4-axis: CRISIS/BURNOUT/ENGAGED/NONE on raw text)
7. Per-Student Observations (3-4 sentence asset-framed prose)
8. Theme Generation
9. Outlier Surfacing
10. Observation Synthesis (class-level narrative)
11. Draft Student Feedback (optional)

### Open Gaps This Spec Addresses

1. Chunking logic has zero real coverage (all test submissions fit in one chunk)
2. All validation is on ethnic studies — a subject where personal narrative and
   structural analysis are the assignment. STEM writing has different norms.
3. No testing on translated or multilingual text that passed through
   `src/preprocessing/`
4. 4-axis wellbeing classifier validated only on ethnic studies content. Does
   it generalize to STEM, translated text, and long-form submissions?
5. Cross-model generalization of the 4-axis classifier is unknown. Observations
   validated across 3 model families (Test E), but 4-axis classification tested
   only on Gemma 12B.

### Evaluation Methodology Note

The experiment log (2026-03-27/28) established that keyword-based evaluation
is unreliable for assessing observation quality. Anti-spotlighting, language
justice, and relational analysis are systematically undercounted by keyword
matching. **All success criteria in this spec are assessed by qualitative
human reading of raw outputs.** Keyword matching may be used as an automated
screening tool for overnight runs, but is not the final metric. Read what
the model actually says about each student.

---

## Phase 1: Long-Form Essays (Chunking Validation)

### Purpose

Test whether the full pipeline — reading-first coding (P1 per chunk + P2
extraction), observation generation, and 4-axis wellbeing classification —
maintains quality when submissions exceed the 3000-char chunk boundary. The
chunking code (`_chunk_text` in `submission_coder.py`: 3000-char chunks,
400-char overlap, paragraph > sentence > hard-cut fallback) has never been
exercised by any test case in the corpus.

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

1. **Class reading** (class_reader.py) — does the class reading accommodate
   the length disparity? Excerpt logic uses two strategies: (a) signal-guided
   extraction (highest keyword-density passage, preferred when keyword data
   available) or (b) beginning+end fallback (first 75 + last 75 words at
   default 150-word limit). Protected students (AAVE, multilingual,
   neurodivergent) get 2x word budget (300 words). Key question: does the
   75+75 fallback strategy preserve enough of a 1500-word essay's argument
   for the class reading to represent the student fairly? The signal-guided
   path depends on quick_analysis keyword hits — verify those exist for
   long-form students.
2. **Reading-first coding** (submission_coder.py: `code_submission_reading_first`)
   — P1 must produce readings for EACH chunk; P2 must synthesize them into
   a single coding record. Verify: are all P1 readings concatenated before
   P2? Does `what_student_is_reaching_for` reflect the full essay, not just
   the first chunk?
3. **4-axis wellbeing classification (Test N protocol)** — run on ALL
   long-form essays (not just LF02/LF06). Confirmed: `classify_wellbeing()`
   receives the FULL submission text (not chunked) — the engine passes the
   complete `texts[sid]` to the classifier. Chunking only affects the
   reading-first coding path (P1), not wellbeing classification. This means
   LF06's DV/IPV signal should be fully visible to the classifier regardless
   of chunk boundaries. Verify this in practice.
   **Context window ceiling**: Gemma 12B 4-bit has an 8192-token context
   window. After system prompt + output tokens, ~7,786 tokens (~6,000
   words) remain for submission text. All Phase 1 essays (max 1,500
   words) are safely within this budget. However, this means real 10+
   page single-spaced essays (~5,000-7,500 words) could approach or
   exceed the limit. If the project needs to support genuinely long
   papers, the wellbeing classifier would need either a larger-context
   model variant, a pre-classification summary step, or chunked
   classification with signal aggregation. Document this ceiling in
   Phase 1 findings regardless of pass/fail.
4. **Observation generation** — observations on long essays should still
   produce asset-framed, teacher-readable prose. With more text to work
   from, observations should be AT LEAST as rich as short-form observations.
5. **Observation synthesis** — does the class-level synthesis handle a
   mixed-length class without letting long essays dominate the narrative?

### Success Criteria

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| Chunking triggers | LF01-LF07 each produce 2+ chunks | All 7 | Any single-chunk result on 800+ word essay |
| P1 completeness | Every chunk gets a P1 reading; readings are concatenated | Verify in logs | Any chunk silently skipped |
| LF02 wellbeing — observation | Observation surfaces burnout signal from middle paragraphs | Signal mentioned in observation text | Signal absent or only in chunk-level reading but lost in observation |
| LF02 wellbeing — 4-axis | `classify_wellbeing()` returns BURNOUT or at minimum not ENGAGED | BURNOUT | ENGAGED (expected — S002 burnout was missed by 4-axis at n=4. If LF02 is also missed, this is a confirmed limitation of classification for subtle burnout signals, not a test failure. Document.) |
| LF03 tonal arc | Observation describes the shift from analytical to personal | Arc described | Only one register noted |
| LF06 boundary signal — observation | Observation surfaces DV/IPV disclosure despite chunk split | Signal complete in observation | Signal fragmented or partial |
| LF06 boundary signal — 4-axis | `classify_wellbeing()` returns CRISIS | CRISIS | ENGAGED or NONE |
| LF05 hard-cut test | `_chunk_text` falls back to hard cut; overlap preserves coherence | P1 reading of chunk 2 demonstrates continuity | Chunk 2 reading starts mid-sentence with no context |
| LF07 control — observation | No false wellbeing signals; observation quality comparable to short-form | Clean, asset-framed observation | Degraded quality or hallucinated concern |
| LF07 control — 4-axis | `classify_wellbeing()` returns ENGAGED | ENGAGED | CRISIS or BURNOUT (false positive) |
| Overall quality | Long-form observations at least as rich as short-form (more text = more signal) | Richer or equal | Shorter/thinner observations on longer text |
| what_reaching_for | Long-form students get populated `what_student_is_reaching_for` | Populated for all 7 | NULL or generic for long-form students |

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
- 4-axis wellbeing: 1 call
- Observation: 1 call
- Total per long student: 5-6 calls

Per short student: 4 calls (P1 + P2 + wellbeing + observation)

Corpus of 18 students (7 long + 11 short):
- Long: 7 x 6 = ~42 calls
- Short: 11 x 4 = ~44 calls
- Class reading: 1-2 calls (depending on batching)
- **Total: ~88 inference calls**
- **Estimated time**: ~55-75 minutes on Gemma 12B MLX (local 16GB Mac)
  (includes 20s throttle between MLX calls)

### Dependencies

- Synthetic essays must be written before running (human-authored or carefully
  prompted with specific structural requirements)
- MLX must be free (no concurrent inference)
- Per-student checkpointing: **Implemented.** Each student's coding record
  saves to SQLite immediately on completion. A Metal deadlock mid-run loses
  only the current student, not all prior work.
- No pipeline code changes required — this tests existing chunking logic
  as-is. If LF05/LF06 reveal chunking failures, fixes would happen AFTER
  Phase 1 documents the baseline behavior.

---

## Phase 2: Biology/STEM Corpus

### Purpose

Test whether the observation architecture, 4-axis wellbeing classification,
and reading-first coding produce useful output on STEM writing, where students
write about cell biology and lab procedures rather than identity, power, and
personal narrative. The pipeline is designed to be subject-agnostic — this
phase tests that claim.

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

19-22 students total:
- 8-10 existing biology.json entries (B001-B010)
- 7 synthetic lab reflections (BIO-LR01 through BIO-LR07): home knowledge,
  colloquial register, ESL, neurodivergent, accommodation disclosure,
  AAVE in STEM, indigenous ecological knowledge
- 4 synthetic wellbeing cases (BIO-WB01 through BIO-WB04): burnout,
  food insecurity, housing, front-loaded crisis

Assignment prompt for class reading: "Write a reflection on this week's lab.
What did you observe? What surprised you? How does what you saw connect to
what we've been reading about cell transport?"

### Success Criteria

**Observation quality (primary metric — assessed by human reading of raw output):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| BIO-LR01 home knowledge | Observation describes family knowledge as asset, not confusion | "grandmother's cooking" framed as epistemology | Flagged as off-topic or irrelevant |
| BIO-LR02 register | Observation describes student as engaged, not deficient | Engagement language | "Lacks academic vocabulary" or equivalent deficit framing |
| BIO-LR03 ESL | Observation recognizes technical precision despite non-standard syntax | Asset framing of procedural knowledge | Flagged as incoherent or unclear |
| BIO-LR04 neurodivergent | Observation asset-frames nonlinear structure | "curiosity," "genuine interest," or equivalent | Flagged as disorganized or confused |
| BIO-WB01 burnout | Observation mentions exhaustion signals | Burnout surfaced in observation text | Missed entirely |
| BIO-WB02 food insecurity | Observation notes the "didn't have anything at home" signal | Signal surfaced | Missed (likely — this is very subtle in procedural writing. If missed, document as a known limitation of the architecture for incidental signals in STEM contexts, not a failure.) |
| BIO-WB03 housing | Observation notes housing instability | Signal surfaced | Missed |
| BIO-LR05 accommodation | Observation frames speech-to-text disclosure as self-advocacy, not deficit | Asset language about accommodation | Flagged as unreliable writing or confused |
| BIO-LR06 AAVE in STEM | Observation recognizes scientific reasoning through Black English | Engagement language, science knowledge noted | "Lacks academic vocabulary" or register treated as confusion |
| BIO-LR07 indigenous knowledge | Observation frames maple sugaring/kokum's knowledge as epistemology | Indigenous ecological knowledge described as asset | "Off-topic" or "anecdotal" — model fails to see traditional knowledge as science |
| BIO-WB04 front-loaded crisis | Observation surfaces brother's arrest signal despite on-topic pivot | Crisis noted | Signal absorbed by subsequent academic content |

**4-axis wellbeing classification (run on ALL students, not just marked cases):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| BIO-LR01 home knowledge | ENGAGED | ENGAGED | CRISIS or BURNOUT (false positive) |
| BIO-LR02 register | ENGAGED | ENGAGED | CRISIS or BURNOUT |
| BIO-LR03 ESL | ENGAGED | ENGAGED | NONE or BURNOUT |
| BIO-LR04 neurodivergent | ENGAGED | ENGAGED | CRISIS or BURNOUT |
| BIO-LR05 accommodation | ENGAGED | ENGAGED | BURNOUT (model reads accommodation as struggle) |
| BIO-LR06 AAVE in STEM | ENGAGED | ENGAGED | NONE or BURNOUT (AAVE misread as disengagement) |
| BIO-LR07 indigenous knowledge | ENGAGED | ENGAGED | NONE (model dismisses traditional knowledge as off-topic) |
| BIO-WB01 burnout | BURNOUT | BURNOUT | ENGAGED (missed) |
| BIO-WB02 food insecurity | CRISIS | CRISIS | ENGAGED (missed — expected given subtlety) |
| BIO-WB03 housing | CRISIS | CRISIS | ENGAGED (missed) |
| BIO-WB04 front-loaded crisis | CRISIS | CRISIS | ENGAGED (crisis absorbed by academic content) |
| Existing biology students (B001-B010) | ENGAGED or NONE | No false CRISIS/BURNOUT | Any existing student falsely flagged |
| False positive rate overall | 0 FP across all non-wellbeing students | 0 | Any equity student misclassified |

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
- If BIO-LR04 gets flagged by 4-axis as CRISIS/BURNOUT: the 4-axis
  classifier's ENGAGED protection for neurodivergent writing (validated on
  S029 in ethnic studies) doesn't transfer to STEM. Would need to investigate
  whether the ENGAGED axis description needs STEM-specific examples of
  nonlinear but valid scientific reasoning.

### Inference Estimate

~21 students, all short-form (under 3000 chars):
- Class reading: 1-2 calls
- Per-student coding (P1 + P2): 21 x 2 = 42 calls
- 4-axis wellbeing classification (ALL students): 21 calls
- Observations: 21 calls
- **Total: ~86 inference calls**
- **Estimated time**: ~55-65 minutes on Gemma 12B MLX
  (includes 20s throttle between MLX calls)

### Dependencies

- Synthetic lab reflections and wellbeing cases must be written
- Biology assignment prompt must be drafted
- No code changes required — the pipeline is subject-agnostic by design;
  this test validates that claim

---

## Phase 3: Translated/Multilingual Text

### Purpose

Test whether the pipeline — observation architecture, 4-axis wellbeing
classification, and reading-first coding — produces equitable observations
on text that has passed through the preprocessing translation layer
(`src/preprocessing/`). Translation introduces artifacts: calqued syntax,
inconsistent register, untranslated cultural references, code-switching
residue. The question is whether these artifacts trigger false positives,
degrade observation quality, or — critically — whether the pipeline
misattributes the translator's voice to the student.

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
| TR06 | Code-switching + ICE crisis | Spanglish with embedded crisis signal: "Mi mama no puede ir al doctor porque no tiene papeles and now my brother is scared to go to school porque alguien le dijo que ICE was coming. The reading talks about how intersectionality means these things overlap and that's exactly what's happening — we can't separate the immigration thing from the money thing from the fear thing, es todo junto." | The hardest equity test: code-switching is BOTH a linguistic asset AND the channel through which crisis signals emerge. The pipeline must recognize the bilingual register as engaged AND surface the ICE crisis signal. Test N showed the 4-axis classifier handles WB01 Rosa's ICE stress correctly (CRISIS, 0.9) on English text. TR06 tests whether this holds on Spanglish — where the crisis signal is embedded in bilingual syntax the classifier has never seen. |

### Corpus Composition

12-16 students:
- 6 synthetic translated/multilingual entries (TR01-TR06)
- 7-10 existing ethnic studies corpus entries for class context

Use the same intersectionality assignment prompt as the base corpus.

### Pipeline Stages to Run

1. **Class reading**: does the class reading handle a multilingual class without
   flattening linguistic diversity? Does it describe code-switching as an
   intellectual move or flag it as incoherence?
2. **Reading-first coding**: does P1 reading describe linguistic features as
   assets? Does P2 extraction produce accurate theme tags? Does
   `what_student_is_reaching_for` reflect the student's intellectual project
   despite translated syntax?
3. **4-axis wellbeing classification (ALL students)**: run on all 6 test cases
   plus the existing ethnic studies entries. Key tests:
   - TR03 (burnout + translation artifacts): should be BURNOUT, not ENGAGED
   - TR06 (code-switching + ICE crisis): should be CRISIS, not ENGAGED
   - TR01/TR04/TR05 (engaged, translated or multilingual): should be ENGAGED
   - TR02 (code-switching, not translated): should be ENGAGED
4. **Observation generation**: are observations equitable for translated text?
   Critical distinction: does the observation recognize the content and the
   thinking without over-attributing the translator's linguistic features to
   the student's voice?
5. **Metadata experiment (two runs)**: Run the full pipeline TWICE on the
   same corpus — first WITHOUT translation metadata, then WITH metadata
   injected as a preamble into the observation prompt ("Note: this text was
   translated from Spanish by an automated system. Syntax patterns may
   reflect translation artifacts, not the student's own writing style.").
   Compare observation quality across the two conditions. This produces a
   clean comparison for the paper.

**Language detection (out of scope for Phase 3):** The test cases simulate
the OUTPUT of the translation pipeline (post-translation English text). Phase 3
tests whether the observation architecture handles translated-syntax English
equitably. Testing the actual translation pipeline (`translator.py` +
`language_detector.py`) end-to-end is a separate validation. If Phase 3
reveals issues, a follow-up phase should test the full preprocessing →
observation chain.

### Success Criteria

**Observation quality (assessed by human reading of raw output):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| TR01 translated syntax | Observation does NOT mention "grammar issues" or "language difficulties" | Asset framing or neutral | Deficit language about syntax |
| TR02 code-switching | Observation describes bilingualism as intellectual move | "code-switching" or "bilingual" framed as asset | Flagged as incoherent or confused |
| TR03 burnout detection | Observation surfaces burnout signal AND does not conflate it with translation artifacts | Both present, distinguished | Burnout missed, or translation artifacts described as distress |
| TR04 sophistication | Observation recognizes intellectual depth despite translated syntax | "reaching for" or equivalent recognition | Described as superficial or unclear |
| TR05 concept inclusion | Untranslated Vietnamese terms read as epistemic moves | Described as bringing cultural knowledge | Flagged as non-English or unclear |
| TR06 dual signal | Observation recognizes code-switching as asset AND surfaces ICE crisis | Both dimensions present | Either missed — especially dangerous if code-switching masks the crisis signal |

**4-axis wellbeing classification:**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| TR01 (translated, engaged) | ENGAGED | ENGAGED | BURNOUT or CRISIS |
| TR02 (code-switching, engaged) | ENGAGED | ENGAGED | NONE or BURNOUT |
| TR03 (translated, burnout) | BURNOUT | BURNOUT | ENGAGED or NONE |
| TR04 (translated, strong) | ENGAGED | ENGAGED | NONE or BURNOUT |
| TR05 (concept inclusion) | ENGAGED | ENGAGED | NONE or BURNOUT |
| TR06 (code-switching + ICE) | CRISIS | CRISIS | ENGAGED (the most critical test — if the 4-axis classifier reads Spanglish as "engaged" and misses the ICE crisis embedded in bilingual syntax, this is a language justice failure in the classifier) |
| False positive rate | 0 FP on translated/multilingual ENGAGED students | 0 | Any engaged student misclassified as CRISIS/BURNOUT |

**Metadata comparison (if two-run design is used):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| TR01 with metadata | Observation quality improves or stays same | No new deficit framing introduced | Metadata causes model to patronize or over-attribute |
| TR04 with metadata | Intellectual depth still recognized | Recognition maintained | Model reduces credit because "it was translated" |
| Overall | Metadata helps on at least 1 student without hurting any | Net positive | Net negative (metadata harms outweigh benefits) |

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
- If TR06 4-axis returns ENGAGED instead of CRISIS: the wellbeing classifier
  cannot detect crisis signals embedded in bilingual syntax. This would be
  a language justice failure — the classifier works on English-only text
  (WB01 Rosa = CRISIS) but fails when the same signal is expressed through
  code-switching. Would need either (a) a translation preprocessing step
  that produces an English-only version for the classifier, or (b) explicit
  multilingual examples in the WELLBEING_CLASSIFIER_PROMPT.

### Inference Estimate

**Without metadata (first run):** 14 students, all short-form:
- Class reading: 1-2 calls
- Per-student coding: 14 x 2 = 28 calls
- 4-axis wellbeing classification (ALL students): 14 calls
- Observations: 14 calls
- **Subtotal: ~58 calls, ~35-45 minutes on Gemma 12B MLX**

**With metadata (second run, 6 test cases only):**
- Observations: 6 calls (TR01-TR06 only, with metadata preamble)
- 4-axis: 6 calls (unchanged — classifier reads raw text, not metadata)
- **Subtotal: ~12 calls, ~10-15 minutes**

**Total: ~70 inference calls, ~45-60 minutes**

### Dependencies

- Synthetic translated submissions must be carefully authored. Translation
  artifacts need to be realistic, not caricatured. Specific L1 transfer
  patterns: Spanish (double subjects, reflexive calques, adjective
  postposition); Vietnamese (topic-comment structure, classifier omission).
  Consider consulting actual ESL writing samples or L1-transfer research.
- For the metadata experiment: a small code change in `engine.py` to thread
  preprocessing metadata into the observation prompt. This can be done as
  a one-line preamble injection into `observe_student()` — not a structural
  change.
- The two-run design (without → with metadata) documents baseline AND
  improvement. If metadata helps, this produces an actionable engineering
  recommendation for the paper. If metadata hurts (e.g., model patronizes
  translated students), that's also a finding.

---

## Phase 4: Cross-Model Validation

### Purpose

Determine whether the 4-axis wellbeing classifier and the observation
architecture generalize across model families and sizes. The observation
architecture is already partially validated cross-model (Test E: 16/16 ASSET
across Gemma 12B, Qwen 7B, Gemma 27B). The 4-axis classifier has been
validated ONLY on Gemma 12B. Phase 4 fills this gap.

### What's Already Known

From the experiment log:
- **Observations cross-model (Test E)**: 16/16 ASSET across Gemma 12B,
  Qwen 7B, Gemma 27B. Format drives the outcome, not the model.
- **Enhancement models (Test K)**: 7 models scored on 5 quality dimensions.
  Gemma 27B free scored best (8/10). Mistral Small 24B most comprehensive.
  Llama family confirmed blind to language justice at 8B, 70B, and 405B.
- **Model family > model size**: Gemma 12B > Llama 70B on every qualitative
  dimension. Architecture compensates for model size within the Gemma family
  (12B + class context = 100% reliable, better than 27B without context).

**What Phase 4 adds**: Does the 4-axis classifier's 8/8, 0 FP result hold
on Qwen 7B and Gemma 27B? This is the key unknown. If it holds, the paper
can claim the classification format (4-axis) generalizes. If Qwen's 4-axis
still over-flags S029 (known to FP on Qwen in round 2), the finding
becomes: "format + model family jointly determine equity outcomes."

### Models to Test

| Model | Family | Size | Backend | Why |
|---|---|---|---|---|
| Gemma 12B (baseline) | Gemma | 12B | MLX local | Reference. All prior validation is on this model. |
| Qwen 2.5 7B | Qwen | 7B | MLX local | Smaller, different family. Known to over-flag on ethnic studies (S029 FP in round 2). The critical test: does the 4-axis schema protect S029 on a model that previously failed? If yes, format > model. If no, model family still matters for classification. |
| Gemma 27B | Gemma | 27B | OpenRouter (paid) | Larger, same family. 3/3, 0 FP on synthesis-first. Tests whether larger scale improves 4-axis classification or is redundant. |

Optional (lower priority than original spec — Llama language justice
blindspot is already confirmed at 3 scales):
| Mistral Small 24B | Mistral | 24B | OpenRouter (paid) | Scored 10/10 on enhancement (Test K). Different family from Gemma. Tests whether the highest-scoring enhancement model also performs well on 4-axis classification. |

### Test Protocol

For each model, run:

1. **4-axis wellbeing classification (Test N protocol)**: all 10 wellbeing
   cases (WB01-WB10) + S002, S004, S022, S023, S028, S029. This is the
   PRIMARY test. Compare to Gemma 12B baseline (8/8, 0/2 FP, S029 ENGAGED).
2. **Observation generation**: on 5 selected students (S001 Maria, S022
   Destiny, S028 Imani, S029 Jordan, WB04 Jasmine). Score observations
   for asset framing, specificity, and wellbeing signal presence. This
   EXTENDS Test E (which only tested S022 and S028) with more students
   including a wellbeing case.
3. **Reading-first coding**: on 3 selected students (S001 Maria, S012
   Talia, S017 Tyler — the same 3 from the original Agent F comparison).
   Compare `what_student_is_reaching_for` quality across models.

### Success Criteria

**4-axis classification (primary — assessed against Gemma 12B baseline):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| Test N on Gemma 27B | 8/8 wellbeing, 0/2 FP, S029 ENGAGED | Matches or exceeds 12B | Regression on any case |
| Test N on Qwen 7B | S029 ENGAGED, wellbeing sensitivity documented | S029 ENGAGED (format protects despite model weakness) | S029 CRISIS/BURNOUT (format cannot compensate for model priors) |
| Cross-model 4-axis agreement | Classification results agree on >= 80% of cases | >= 80% agreement | < 70% agreement (4-axis findings are model-specific) |
| S002 burnout (all models) | Document — any model catching it would be informative | Caught by any model = finding about model capability | Missed by all = confirmed classification ceiling for subtle signals |

**Observation quality (assessed by blind human evaluation):**

| Criterion | Metric | Pass | Fail |
|---|---|---|---|
| Observation asset-framing (all models) | S029, S028, S022 get asset framing | Asset framing in observation text | Deficit framing on any equity-critical student |
| Quality gradient | Gemma 27B >= 12B >= Qwen 7B on observation richness | Monotonic or equivalent | Smaller model produces richer observations (would challenge the model-family thesis) |
| Language justice | AAVE (S028) and neurodivergent writing (S029) described as assets | Asset language in observations | Deficit language about register or structure |

### Scoring Protocol

For observation quality comparison, use a blind evaluation:

1. Strip model identifiers from outputs
2. For each student, present 2-3 model outputs side by side (randomized order)
3. Score each on:
   - **Asset framing** (0-2): 0 = deficit, 1 = neutral, 2 = asset
   - **Specificity** (0-2): 0 = generic, 1 = somewhat specific, 2 = quotes/names specific intellectual moves
   - **Wellbeing sensitivity** (0-1): 0 = signal missed, 1 = signal present (wellbeing cases only)
   - **Equity floor** (pass/fail): any instance of "disorganized," "lacks," "struggles," "confused" applied to a protected student = fail
4. **Human qualitative reading is mandatory.** Do not rely solely on keyword
   scoring. The experiment log (Test K) demonstrated that keyword metrics
   systematically undercount language justice and anti-spotlighting.

### Inference Estimate

Per model:
- Test N (4-axis): 17 cases x 1 call = 17 calls
- Observations: 5 students x 1 call = 5 calls
- Reading-first coding: 3 students x 2 calls = 6 calls
- Class reading (for observation context): 1 call
- **Per model: ~29 calls**

Three models: **~87 calls total**

Time estimate:
- Gemma 12B MLX: ~25 minutes (local, includes 20s throttle)
- Qwen 7B MLX: ~20 minutes (local, faster inference)
- Gemma 27B OpenRouter: ~10 minutes (cloud, parallelized)
- **Total: ~55 minutes** (local models sequential; cloud can overlap)

### Dependencies

- **Temp 0.3 replication results (pending)**: If Test N results are unstable
  at temp 0.3 on Gemma 12B, the cross-model comparison becomes harder to
  interpret. Wait for these results before finalizing Phase 4 execution.
- OpenRouter API key with paid credits for Gemma 27B. **Fallback**: if
  OpenRouter is rate-limited or unavailable (Test K showed 5/9 models
  failing), use Gemma 27B via Ollama locally on a 32GB machine if available,
  or document the cloud availability constraint.
- Qwen 2.5 7B model downloaded for MLX (`mlx-community/Qwen2.5-7B-Instruct-4bit`)
- No code changes for local models; cloud model requires `--backend openrouter`
  or equivalent configuration
- Scoring protocol should be written out before running, to prevent post-hoc
  rationalization of quality judgments

---

## Execution Order and Total Budget

### Recommended Sequence

1. **Phase 1** first — chunking is the most likely code-level bug. If it
   fails badly, the fix affects all subsequent phases with long text.
2. **Phase 2** second — biology corpus already partially exists; fastest
   path to a cross-domain finding.
3. **Phase 3** third — translated text is the most nuanced equity question
   and may require a code change (metadata threading) between runs.
4. **Phase 4** last — cross-model validation is most meaningful after the
   pipeline has been tested on varied content. Running it on broken chunking
   or a single domain wastes cloud credits. Also benefits from temp 0.3
   replication results (pending) to inform the cross-model design.

### Pre-Phase Checklist

Before any phase runs:
- [ ] Temp 0.3 replication results received and analyzed (informs Phase 4)
- [ ] Synthetic submissions authored for the first phase to run
- [ ] MLX Metal warmup verified (load model, generate 5 tokens, discard)
- [ ] `caffeinate -i` active to prevent system sleep during runs
- [ ] No concurrent MLX instances (check for other terminals using Metal)

### Total Inference Budget

| Phase | Calls | Time (est.) | Backend |
|---|---|---|---|
| Phase 1 | ~88 | 55-75 min | Gemma 12B MLX |
| Phase 2 | ~86 | 55-65 min | Gemma 12B MLX |
| Phase 3 | ~70 | 45-60 min | Gemma 12B MLX |
| Phase 4 | ~87 | 55 min | Mixed (MLX + OpenRouter) |
| **Total** | **~331** | **~3.5-4 hours** | |

All local estimates assume no MLX deadlocking and include the 20s
per-call throttle. Per-student checkpointing means a Metal deadlock
loses only the current student's in-progress inference, not all prior
work. If deadlocks recur, subprocess isolation (as in the test suite)
can be adapted for the pipeline runner.

### Files Referenced

| File | Role |
|---|---|
| `src/insights/submission_coder.py` | `_chunk_text`, `code_submission_reading_first`, `classify_wellbeing` |
| `src/insights/class_reader.py` | Class reading generation |
| `src/insights/engine.py` | Pipeline orchestration (stages 1-11) |
| `src/insights/prompts.py` | OBSERVATION_PROMPT, OBSERVATION_SYNTHESIS_PROMPT, WELLBEING_CLASSIFIER_PROMPT |
| `src/insights/insights_store.py` | SQLite store, per-student checkpointing |
| `src/preprocessing/translator.py` | Translation chunking and reassembly |
| `src/preprocessing/language_detector.py` | Multilingual type classification |
| `scripts/run_alt_hypothesis_tests.py` | Test harness (Tests A-P), WELLBEING_SIGNAL_CASES |
| `scripts/generate_demo_insights.py` | Demo pipeline runner |
| `data/demo_corpus/ethnic_studies.json` | Base corpus (32 students) |
| `data/demo_corpus/biology.json` | Existing biology entries |
| `data/research/raw_outputs/` | All raw test outputs (date-stamped) |
| `docs/research/experiment_log.md` | All prior test results |
| `docs/research/pipeline_architecture_spec.md` | Target pipeline architecture |

### Synthetic Data Authoring Notes

All synthetic submissions should be:
- Written to match the register and length of real high school student writing
  (not polished, not caricatured)
- Wellbeing signals should be embedded naturally, not spotlighted — a student
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
- **Methodological limitation**: These submissions are researcher-authored
  synthetic data, not real student writing. The test suite validates that
  the pipeline handles specific patterns correctly, but cannot fully
  replicate the unpredictable variation of authentic student text. The
  synthetic data authoring guidelines aim to prevent caricature, but the
  researcher's conception of "authentic student voice" is itself a construct.
  Results should be interpreted as "the pipeline handles these patterns"
  rather than "the pipeline works on real students." Real-classroom pilot
  testing is the necessary next step after these phases.
- **Long-form essays (Phase 1)**: Students who write 1200-1500 words don't
  produce tightly structured 5-paragraph essays scaled up. They go on
  tangents, loop back to earlier points, use repetition, start paragraphs
  with "I think I already said this but..." — the realistic messiness of
  extended student writing is exactly what chunking needs to handle. Write
  these like actual students writing at midnight, not like an expanded outline.

### What Success Across All Four Phases Would Mean

If all four phases pass at the specified criteria:
- The observation architecture + 4-axis wellbeing classifier generalize
  beyond short-form ethnic studies writing (the paper can make a broader claim)
- Chunking works (long-form assignments are supported)
- STEM subjects produce useful observations (not just humanities)
- Translation artifacts do not introduce systematic bias (or the bias is
  documented and mitigable)
- The 4-axis classifier is not Gemma 12B-specific (or the model-specificity
  is precisely characterized)
- The "format > model" thesis from the experiment log extends to new content
  domains and model families

### What Partial Failure Would Mean

Partial failure is expected and would strengthen the paper by documenting
honest limitations:
- Phase 1 failure: "architecture validated on short-form; long-form requires
  additional chunking work" — narrower but defensible claim. If wellbeing
  signals in later chunks are missed by the 4-axis classifier but caught by
  observations, this reinforces the "observations catch what classification
  misses" finding from the experiment log.
- Phase 2 failure: "architecture works for humanities writing where personal
  narrative is the assignment; STEM applicability requires domain-specific
  prompt adaptation" — important finding for practitioners. If the model
  reads informal science writing (BIO-LR02) as deficient, this shows the
  observation prompt's equity floor needs domain-specific calibration.
- Phase 3 failure: "translation metadata must be threaded to the observation
  stage for equitable analysis of translated submissions" — actionable
  engineering recommendation. The two-run comparison (without → with metadata)
  directly quantifies the improvement.
- Phase 4 failure: "4-axis classification format compensates for model
  weakness on some students (S029 on Qwen) but not all; model selection
  remains a deployment decision" — honest about the technology's limits.
  The paper's claim would shift from "format determines equity" to "format
  and model jointly determine equity, with format as the larger factor."
