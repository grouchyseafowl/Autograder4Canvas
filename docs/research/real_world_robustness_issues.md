# Real-World Robustness Issues

Identified 2026-03-23 from fragility analysis. These are risks that the synthetic
test corpus can't surface — they need either real data testing, architectural
solutions, or both.

---

## Moderate Risk (need attention before launch)

### 1. Different concern types beyond our test set — DONE
**Problem:** We've tested essentializing, colorblind, and tone policing. Real
classes surface: deficit framing of poverty, savior narratives ("those poor
people need our help"), exoticizing ("their culture is so beautiful and
spiritual"), "model minority" stereotypes, gender essentialism.

**Fixed:** Added savior narrative, exoticizing, model minority, and deficit
framing of poverty to CONCERN_PROMPT — both in the DO-flag list (with
descriptions of relational harm) and as few-shot examples with realistic
student text, context, why_flagged, and confidence scores.

### 2. Brief-but-substantive voices in class reading — DONE
**Problem:** Marcus Bell writes "thats basically it" in 30 words. This IS valid
engagement (naming the core concept, acknowledging limits of articulation). But
in a class reading prompt with 32 students, 30 words gets drowned out.

**Fixed:** Two changes: (1) CLASS_READING_PROMPT now instructs the model to
"pay special attention to students who wrote BRIEFLY but SUBSTANTIVELY" with
framing about concision, self-protection, and variable capacity. (2)
`_build_submissions_block` in class_reader.py annotates 10-60 word submissions
with `[NOTE: Brief submission — read carefully, do not overlook]`.

### 3. Class size scaling (50+ students) — IN PROGRESS
**Problem:** Hierarchical group reading is designed but untested above 32.
Large classes (50-100) would produce 10-20 groups, each needing an LLM call,
plus merge passes.

**Current state:** Adaptive group sizing is built in class_reader.py. 60-student
synthetic corpus created. Scaling test script ready at /tmp/test_scaling_60.py.
Awaiting LLM run.

**Fix:** Test with a synthetic 60-student corpus. May need to cap group count
and merge hierarchically (groups of groups).

**Priority:** Medium — most classes are 25-35.

### 3b. Full pipeline concern detection false positives — FIXED
**Problem:** Isolated concern detection is 100% reliable (replication study),
but the full pipeline produces false positives. 12B MLX full pipeline: 9 flagged
students (6 strengths flagged as concerns, 1 protected student flagged). S015
Brittany (essentializer) missed entirely.

**Root cause:** Two factors:
1. max_tokens=4096 (backend default) lets the 12B model generate verbose
   "analysis" that gets formatted as concern JSON, filling the response with
   strength descriptions labeled as flags.
2. APPROPRIATE signal matrix results ("Sophisticated analysis — student engaging
   well") were being passed to the concern prompt, confusing the model into
   analyzing those strengths.

**Fixed:** concern_detector.py now:
- Caps max_tokens=800 for concern detection calls
- Filters out APPROPRIATE signals before passing to the prompt
- Both ConcernSignal and tuple format paths filter APPROPRIATE signals

**Status:** Code fix applied, unit tests pass. Needs full pipeline re-test.

### 4. Non-discussion assignments
**Problem:** Lab reports, problem sets, coding assignments don't have relational
voice. The class reading would produce generic output.

**Current state:** No assignment type detection for the class reading stage.

**Fix:** The class reading should be conditional — skip it for assignment types
where students aren't writing reflectively. Use the assignment prompt analysis
(already in Quick Analysis) to determine if a class reading is appropriate.
When skipped, fall back to the stats-based class context (existing behavior).

**Priority:** Medium — most insights users will be humanities/social science
initially. But this matters for scaling.

## Higher Risk (need architecture decisions)

### 5. Mixed language submissions — DONE (classification + pipeline threading)
**Problem:** A student writes half in Spanish, half in English. Or includes
Yoruba concepts in an anthropology essay. The model reads through English-
dominant lens.

**Fixed:** Three-way multilingual classification added to language_detector.py:
- `monolingual_english` — no non-English detected
- `concept_inclusion` — isolated non-English terms/phrases (don't translate)
- `code_switching` — bilingual fluency across sentences (don't translate — asset)
- `primary_other_language` — written primarily in another language (translate, preserve original)

Classification uses per-sentence langdetect on English-dominant texts. Threaded
through: LanguageResult → PreprocessedSubmission → engine.py submission metadata.

**Verified safe:** Code-switching and concept inclusion NEVER trigger translation.
Yoruba concepts in English essays classified as monolingual_english (correct).
Full Spanish correctly triggers translation.

**Remaining:** AIC and insights pipeline don't yet consume `multilingual_type`
for per-student handling — they rely on `linguistic_features.py` code_mixing
detection (which runs independently). Future: merge these two detection paths.

**Design decision (2026-03-23): No parenthetical glosses for code-switched text.**

Considered and rejected adding inline translations like "mi mamá siempre dice
que hay que echarle ganas [my mom always says you have to give it your all]"
for monolingual teachers. Reasons:

1. **Never modify the student's text.** The code-switched submission enters the
   class reading and coding prompts exactly as written. The student chose those
   words in that language because the English didn't say it.

2. **Translation flattens.** "Echarle ganas" → "try hard" strips cultural
   weight. An 8B model's gloss of culturally dense phrases will be poor. A bad
   gloss is worse than no gloss — it becomes the teacher's reading and the
   original becomes decoration.

3. **Glosses reproduce monolingualism as the default.** They position English
   as the language of comprehension and everything else as needing explanation.
   The system should not be the arbiter of what the student "really meant" in
   English.

4. **The class reading already provides access.** The LLM reads the multilingual
   text and explains what the student is reaching for — the teacher gets meaning
   through the LLM's interpretive reading, not through mechanical glossing. If
   the teacher needs more, the handoff prompt lets them ask their own questions
   of an institutional chatbot.

5. **Teacher-facing metadata notes the asset.** The processing summary and
   linguistic context note flag multilingual use as a communicative resource:
   "This student writes across English and Spanish — bilingual fluency." This
   tells the teacher what's happening without flattening the content.

The principle: trust the student's language choices. Help the teacher engage
with them rather than routing around them.

### 6. AI-generated submissions
**Problem:** A student submits ChatGPT output. The class reading reads it as
the student's voice. The pipeline may surface "strengths" that aren't the
student's. Worse: the essay may be perfectly written in standard English,
making it look like the strongest submission — and now the class reading
centers an AI voice while marginalizing authentic student voices.

**Current state:** AIC detects likely AI-generated text. But the class reading
and concern detection don't receive this flag.

**Fix:** When AIC flags a submission as likely AI-generated:
- Class reading should either exclude it or mark it: "[Note: this submission
  shows signals consistent with AI generation. Read with awareness that this
  may not represent the student's authentic voice.]"
- Concern detection should NOT flag AI submissions for essentializing etc. —
  the concern is with the student's choice to submit AI text, which is an
  AIC issue, not an insights issue.
- The class reading should not let a polished AI essay set the standard
  against which authentic but non-standard voices are measured.

**Priority:** High — AI submission rates are significant in most classrooms.

### 7. Very small classes (under 8) — DONE
**Problem:** The class reading looks for relational dynamics that may not exist
in a 5-person class. "Tensions between groups" doesn't apply.

**Fixed:** Added `CLASS_READING_SMALL_PROMPT` in prompts.py — focuses on
individual depth, avoids "groups"/"factions" language, notes that every voice
carries significant weight. class_reader.py selects this prompt automatically
when `len(submissions) < 8`.

---

## Already handled (confirmed)

- **Essay length variation (2-4x):** Signal-guided extraction + beginning/end
  fallback handles this. Short submissions in full, long ones excerpted.
- **AAVE variation:** Linguistic feature detector covers multiple AAVE features.
  Sentiment suppression protects across variants.
- **Neurodivergent writing:** Disability self-advocacy protection in CONCERN_PROMPT.
  Flat-affect detection in linguistic features.
- **Multilingual syntax (within English):** Detected and protected. LLM context
  note injected into concern detection.

---

## Process

For a third agent to work on these:
- Items 1, 2, 7 are prompt engineering tasks (modify prompts.py)
- Item 3 is a testing task (create synthetic 60-student corpus, run pipeline)
- Item 4 is a conditional logic task (add assignment type check before class reading)
- Item 5 is a preprocessing integration task (check src/preprocessing/ → class_reader)
- Item 6 is an AIC integration task (pass AI-detection flag to class_reader + concern_detector)
