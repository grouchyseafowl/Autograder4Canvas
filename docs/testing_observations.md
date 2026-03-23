# Testing Observations — AIC & Insights Pipeline

> Generated from DAIGT testing brief execution (2026-03-20).
> Updated 2026-03-22 with methodology audit findings and Claude Sonnet validation data.
> This document captures empirical findings that should drive system refinement.
> Each observation includes the gap identified, proposed fix, and validation criteria.
>
> **2026-03-22 Update**: A methodology audit (`docs/comparison_analysis.md`) revealed that
> the demo corpus's 19 "off-topic" submissions are a data construction artifact — DAIGT
> essays with light keyword swaps, not genuinely off-topic student work. Findings
> conditioned on this artifact are marked below. Additionally, 5 Claude Sonnet test
> essays (`data/demo_source/claude_test_essays.json`) were added to calibration,
> and the biology pipeline crash (SynthesisReport sections dict coercion) was fixed.

---

## Methodology Limits

**What we CAN test with current data:**
- Detection accuracy on well-written AI text (the hard case) — now includes Claude Sonnet essays (5 styles: naive, personal, formal, lab, adversarial)
- False positive rates on competent human writing (DAIGT essays, n=295)
- Pipeline stage timing and reliability on local 8B models
- Concern detector behavior on specific discourse patterns (10 hand-crafted students)
- Structural indicator validation (starter diversity, comma density, avg word length) — calibrated against DAIGT + 13 AI essays across 4 models

**What the methodology audit revealed we CANNOT validly test:**
- Topic-mismatch detection (current corpus has DAIGT-adapted essays, not genuinely off-topic work)
- Theme quality on a coherent single-topic corpus (current corpus mixes driving + intersectionality)
- Pairwise similarity validation (Ethan Liu / Nadia Petrov match is a construction artifact — same DAIGT source)
- Engagement absence detection on realistic disengaged students (Tyler/Jaylen are AI-generated, not disengaged humans)

**What we CANNOT test without real classroom data:**
- Detection on truly minimal-effort submissions
- Detection on writing from students with learning disabilities
- Detection on dictated submissions (speech-to-text artifacts)
- Detection on translanguaging / multilingual submissions (beyond our 1 ESL student)
- False positive rates across the full range of student writing ability
- Longitudinal trajectory analysis (single-assignment snapshot only)
- Population-level cross-submission similarity (corpus is hand-assembled, not organic)

**What we need to get right before real classroom testing:**
- Every improvement below should be validated on our synthetic data first
- But the synthetic data validation is necessary, not sufficient
- Real classroom pilot (with teacher consent) is the only way to validate the full system

---

## AIC Observations

### OBS-AIC-01: Human presence score is advisory-only

**Data:** All 4 AI-generated essays (ChatGPT x2, Gemini Pro, Gemini Thinking) scored 0.0-10.3% human presence. The system flags "Very low overall human presence score" in the concerns text but does NOT increase the suspicious_score.

**Gap:** Human presence analysis generates informational text but has no path to influence the suspicious score. A submission with 0% human presence across 5 categories gets the same suspicious score as one with 80%.

**Location:** `src/Academic_Dishonesty_Check_v2.py` — the `suspicious_score` calculation and the `human_presence_details` are computed independently.

**Proposed fix:** Implement inverse weighting — if human_presence_confidence < threshold (e.g., 15%), add a scaled contribution to suspicious_score. E.g., `absence_signal = max(0, (15 - human_presence_confidence)) * weight_factor`. This makes the *absence* of human markers a positive signal for AI, rather than just a note.

**Priority:** CRITICAL — this is the primary reason clean AI text is invisible to the system.

**Validation:** After fix, ChatGPT #1 and Gemini Thinking #4 (both 0-2.7% human presence) should score ≥30 suspicious. Gemini Pro #3 (which fakes human markers) may still evade — that's a separate issue (OBS-AIC-04).

---

### OBS-AIC-02: Sentence uniformity threshold too narrow

**Data:** ChatGPT #1 has variance_coefficient=0.211 → detected as "AI signature (rhythmic)". ChatGPT #2 has variance_coefficient=0.285 → classified as "Human variation". Both are AI.

**Gap:** The uniformity threshold is a hard cutoff (~0.25). Real AI text has enough variance to evade — ChatGPT #2 just varies sentence length enough to pass. Binary classification (uniform vs not) loses the gradient.

**Location:** `src/Academic_Dishonesty_Check_v2.py` — `organizational_analysis.sentence_analysis`

**Proposed fix:** Replace binary threshold with gradient scoring. Variance coefficient 0.15-0.35 is a "suspicious range" with proportional scoring, not a cliff at 0.25. Also consider: sentence length variance COMBINED with other signals (low human presence + moderate uniformity = more suspicious than either alone).

**Priority:** HIGH — affects detection of ~50% of AI text that has moderate uniformity.

**Validation:** ChatGPT #2 (0.285 variance) should get a non-zero AI organizational score after fix.

---

### OBS-AIC-03: No formulaic conclusion detection

**Data:** Both ChatGPT essays open their final paragraph with "Overall, ...". This is one of the strongest AI fingerprints in short-form writing — real students almost never start a concluding sentence with "Overall" in a discussion post.

**Gap:** No detector for formulaic conclusion patterns.

**Location:** Would be a new detector in `src/Academic_Dishonesty_Check_v2.py` or `src/modules/human_presence_detector.py`

**Proposed fix:** Add a conclusion pattern detector that checks for:
- "Overall, ..." as paragraph opener
- "In conclusion, ..."
- "To sum up, ..."
- "In summary, ..."
- Final paragraph restating the thesis of the first paragraph (semantic similarity check)
These patterns in a discussion post context (not a formal essay) are strong AI signals.

**Priority:** MEDIUM — common in ChatGPT output specifically. Less common in Gemini/Claude output. But ChatGPT is the dominant student tool.

**Validation:** Both ChatGPT essays should trigger this detector.

---

### OBS-AIC-04: Gemini Pro fakes human markers convincingly

**Data:** Gemini Pro #3 scored 10.3% human presence — highest of all 4 AI essays — because it uses first person ("I can definitely see this in my own life"), personal anecdotes ("As a first-generation Latina from a working-class neighborhood"), and informal language ("super interesting", "Hey everyone"). It also evades sentence uniformity (variance=0.436, well above threshold).

**Gap:** The human presence detector counts surface markers (first-person pronouns, informal language, personal references) without validating their *authenticity*. A well-prompted AI can produce all these markers.

**Location:** `src/modules/human_presence_detector.py`

**Proposed fix:** This is the hardest problem. Possible approaches:
1. **Specificity depth analysis**: Real personal anecdotes name specific people, places, times. AI anecdotes are vivid but generic ("a working-class neighborhood" — which one? "a part-time job" — doing what?). Measure specificity gradient.
2. **Register shift analysis**: Real students shift register within a post (formal when referencing reading, informal when personal). AI maintains consistent register even in "informal" mode.
3. **Hedging pattern analysis**: Real students hedge differently — "I think", "kind of", "maybe", "idk" — and hedge inconsistently. AI either hedges uniformly or not at all.
4. **Cross-submission comparison**: If we have prior submissions from this student, compare voice consistency. This is the strongest signal but requires longitudinal data.

**Priority:** HIGH but HARD — this is the fundamental adversarial problem. No single-text detector may fully solve it. Population-level signals (cross-submission) are more reliable.

**Validation:** Difficult to validate without a broader corpus. Gemini Pro #3 should at minimum have its human presence score tempered by the absence of high-specificity details.

---

### OBS-AIC-05: No generic source attribution detection

**Data:** AI essays reference readings generically: "the reading emphasized", "Crenshaw's idea helps us understand", "the reading on intersectionality". Real students who engage with the material quote or paraphrase specific passages, or reference specific concepts by name.

**Gap:** No detector for generic vs. specific source attribution. In a discussion post context, generic attribution ("the reading says") combined with no specific quotes or paraphrases is a moderate AI signal.

**Proposed fix:** Add a source attribution analyzer:
- Count specific quotes (quotation marks with attributed content)
- Count specific concept references (names a concept from the reading vs. generic "intersectionality")
- Count specific page/passage references
- Generic attribution phrases without specifics → moderate AI signal

**Priority:** MEDIUM — this only applies to assignments that reference readings. But it's a strong signal when applicable.

**Validation:** ChatGPT #1/#2 and Gemini Thinking #4 should trigger (generic attribution). Gemini Pro #3 at least references "Kimberlé Crenshaw" and "the traffic intersection metaphor" — more specific.

---

### OBS-AIC-06: Hedging absence not detected

**Data:** AI essays use confident declarative statements: "intersectionality shows how these identities interact", "It pushes us to think more critically". Real student discussion posts are full of hedging: "I think", "kind of", "maybe", "I guess", "I'm not sure but". The absence of hedging in a discussion post (not a formal essay) is a moderate AI signal.

**Gap:** The system counts hedging markers as human presence indicators but doesn't flag their *absence* as suspicious.

**Location:** `src/modules/human_presence_detector.py` — cognitive_struggle category includes hedging markers.

**Proposed fix:** In discussion post context, compute a hedging ratio (hedging markers per 100 words). If the ratio is well below the class median AND other signals are present (low human presence, moderate uniformity), increase suspicion. Context matters: a formal essay has low hedging naturally. A discussion post with no hedging is unusual.

**Priority:** MEDIUM — strongest when combined with assignment type context.

**Validation:** All 4 AI essays should show below-median hedging ratios.

---

### OBS-AIC-07: Transition word density not analyzed

**Data:** ChatGPT essays use smooth, evenly-distributed transitions: "Rather than", "For example", "This made me reflect", "It encourages us", "Instead of". Real student discussion posts have rougher transitions or none at all — they jump between ideas.

**Gap:** No detector for transition word density or distribution.

**Proposed fix:** Measure transition word/phrase frequency per sentence. High density of formal transitions in a discussion post context is a moderate AI signal. Consider: which transitions are used. AI favors "academic" transitions (Furthermore, Moreover, Additionally). Students use "and", "but", "like", "so".

**Priority:** LOW-MEDIUM — supplementary signal, not primary.

---

### OBS-AIC-08: Score composition doesn't combine weak signals

**Data:** ChatGPT #1 has: low human presence (2.7%), sentence uniformity (0.211), AI org score (0.8), zero cognitive struggle, zero productive messiness, zero authentic voice — but still only scores 0.8/100 suspicious. Each individual signal is below its threshold for concern. The *combination* of 5+ weak signals is what makes this text obviously AI to a human reader.

**Gap:** The scoring model is additive (each marker independently contributes) but doesn't have a "multi-signal convergence" escalation. When 5+ categories all point the same direction, the confidence should be higher than the sum of parts.

**Location:** `src/Academic_Dishonesty_Check_v2.py` — final score computation.

**Proposed fix:** Implement a convergence multiplier. When N independent signal categories all indicate AI (even weakly), apply a multiplier: `convergence_bonus = base_score * (1 + 0.15 * (converging_signals - 2))`. This means 3 weak signals in agreement amplify each other.

**Priority:** CRITICAL — this is the second major architectural gap (after OBS-AIC-01). The system detects many weak signals but can't synthesize them into a meaningful conclusion.

**Validation:** ChatGPT #1 (which has weak signals across 5+ categories) should score significantly higher than an essay with one strong signal.

---

### OBS-AIC-09: cognitive_diversity markers not scored in human presence (BUG)

**Data:** Claude Sonnet B (biology lab) contains "now that I think about it" — correctly detected as a `cognitive_diversity` marker. But the human presence score is 0.0% across all 5 categories. The marker appears in `markers_found` but is never credited to `cognitive_struggle` or any HP category.

**Gap:** The `cognitive_diversity` marker detection pipeline is disconnected from the human presence scoring pipeline. Markers are found but not weighted.

**Location:** `src/modules/human_presence_detector.py` — the mapping from `cognitive_diversity` markers to HP category scores.

**Proposed fix:** Map `cognitive_diversity` markers → `cognitive_struggle` category in HP scoring. These markers ("I think", "now that I think about it", "I'm not sure") are strong human presence indicators.

**Priority:** HIGH — this is a scoring bug. The system already detects the right markers but throws away the signal before scoring.

**Validation:** Claude Sonnet B should get a non-zero cognitive_struggle score after fix.

---

### OBS-AIC-10: Dual-register pattern (academic → messy) undetected

**Data:** Gemini Thinking C simulates a tired student: formal academic first half ("provides a crucial critique of 'single-axis' frameworks that often dominate social justice discourse"), then degrades into typos and trailing ellipsis ("anyway identity is messy and we cant just check boxes especially when the boxes are..."). A real tired student would not START at that academic register.

**Gap:** No detector for within-text register shifts. The system analyzes the text holistically — it doesn't notice that the first half and second half have dramatically different registers.

**Proposed fix:** Split text at midpoint (or by paragraph). Compute register metrics (sentence length variance, vocabulary sophistication, hedging density) for each half. Large register shift between halves is a moderate AI signal — especially when the first half is MORE formal than the second (tired student pattern would be the reverse or uniform).

**Priority:** MEDIUM — this is an advanced adversarial technique. Worth detecting but not as impactful as OBS-AIC-01/08.

---

### OBS-AIC-11: Cumulative AIC test results (8 essays, 4 models)

**Data (all 8 AI-generated essays):**

| Essay | Model | Suspicious | Human Presence | Detected Signal |
|-------|-------|-----------|---------------|-----------------|
| ChatGPT #1 | ChatGPT | 0.8 | 2.7% | Sentence rhythm |
| ChatGPT #2 | ChatGPT | 0.0 | 8.5% | Nothing |
| Gemini Pro #3 | Gemini Pro | 0.0 | 10.3% | Fakes human markers |
| Gemini Thinking #4 | Gemini Thinking | 0.0 | 0.0% | Nothing |
| Claude Sonnet A | Claude Sonnet | 0.0 | 6.6% | Fakes personal anecdote |
| Claude Sonnet B | Claude Sonnet | 0.0 | 0.0% | BUG: markers found but not scored |
| Gemini Thinking C | Gemini Thinking | 0.0 | 2.4% | Register shift undetected |
| Gemini Thinking D | Gemini Thinking | 0.8 | 8.6% | Sentence rhythm (anti-detection backfired) |

**Summary:** 8/8 essays score < 1.0 suspicious. 0/8 trigger smoking gun. The system cannot detect clean AI text at the individual level. Every signal that COULD help (low human presence, cognitive diversity absence, register analysis) is either not implemented or not weighted into the score.

**Implication:** Individual-text AIC needs the architectural fixes in OBS-AIC-01 and OBS-AIC-08 as minimum. Population-level detection (cross-submission similarity) may ultimately be more reliable than individual-text analysis for catching sophisticated AI use.

---

## Pipeline Observations

### OBS-PIPE-01: SSR timing on local 8B

**Data:** Short Sub Review takes 93-136s per review (avg 118s) on Ollama llama3.1:8b.

**Implication for demo:** Scene 2 says "each review takes roughly [TBD] seconds". On local 8B: ~2 minutes. On cloud API (Sonnet): likely 5-15 seconds.

---

### OBS-PIPE-02: Per-student coding timing

**Data (3-student pilot):** ~91.5s per student on Ollama llama3.1:8b.

**Extrapolation for 29 students:** ~44 min for coding stage alone.

---

### OBS-PIPE-03: 3-pass synthesis for 8B reliability

**Data:** Single-pass synthesis on 8B produced 4/9 sections. 3-pass approach (3 sections each) resolved this.

**Status:** Fix implemented and deployed in current pipeline run.

---

## Concern Detector Observations

*(Pending — will be populated after full pipeline completes and we can examine which students were/weren't flagged)*

### OBS-CONC-01: [Placeholder — essentializer flagging]
### OBS-CONC-02: [Placeholder — colorblind claim flagging]
### OBS-CONC-03: [Placeholder — righteous anger NOT flagged]
### OBS-CONC-04: [Placeholder — tone policing flagging]

---

## Theme Generator Observations

*(Pending — will be populated after full pipeline completes)*

---

## What We Still Need to Test & How

### Testing gap 1: Writing diversity beyond competent essays

**The problem:** DAIGT essays are competition-quality writing. Real classrooms include students who struggle with writing, dictate answers, write in multiple languages, have learning disabilities, or submit minimal-effort work. Our false-positive rate is only validated on competent writing.

**What this risks:** If AIC refinements (like OBS-AIC-01, raising suspicion when human presence is low) are tuned on competent writing, they may systematically flag students who write differently — not because they used AI, but because their writing doesn't match the "human markers" the system expects. This is the core #ALGORITHMIC_JUSTICE concern: optimization on one population harms another.

**Approaches to test:**
1. **Generate synthetic low-ability submissions**: Use LLMs to generate text *in the style of* struggling writers (short sentences, limited vocabulary, spelling errors, incomplete thoughts). Run through AIC. Check: does the system correctly identify these as human despite lack of "sophisticated" human markers?
2. **Dictation simulation**: Generate text with speech-to-text artifacts (no capitalization, run-on sentences, "like" and "um" fragments). Run through AIC. Check: does the system handle these as human?
3. **Multilingual simulation**: Generate submissions with translanguaging patterns (code-switching, loan words, L1 grammatical transfer for several languages). Run through AIC. Check: false positive rates by language background.
4. **Real pilot with consenting teacher**: The only way to validate across the full spectrum. Requires IRB-like consent process and de-identification. This is the gold standard — synthetic testing is a prerequisite, not a substitute.

### Testing gap 2: Adversarial prompting (students who try to evade)

**The problem:** Our AI-generated test essays used basic prompts. Real students will:
- Ask ChatGPT to "write like a high school student"
- Ask it to "add personal examples" or "make it sound casual"
- Run their AI output through paraphrasers
- Mix AI paragraphs with their own writing

**What this risks:** If we only test naive AI output, our improvements may not catch sophisticated evasion. Gemini Pro #3 already shows this — it fakes human markers with a basic prompt.

**Approaches to test:**
1. **Prompt escalation ladder**: Test a series of increasingly sophisticated prompts:
   - Level 0: "Write about intersectionality" (our current tests)
   - Level 1: "Write like a high school student discussing intersectionality"
   - Level 2: "Include a personal anecdote and informal language"
   - Level 3: "Include spelling mistakes, run-on sentences, and hedging like 'I think'"
   - Level 4: "Write the first paragraph yourself, ask AI to continue in your style"
2. **Run each level through AIC before and after refinements**: Map the detection boundary at each level. Document where the boundary is and what we can/cannot catch.
3. **Acknowledge the boundary**: At some point, sufficiently sophisticated evasion becomes indistinguishable from human writing. The system should be honest about this — the goal is to catch lazy/naive AI use and surface patterns at the population level, not to be an arms race against determined evasion.

### Testing gap 3: Population-level signals

**The problem:** Individual-text AIC analysis will always have limits (see Gemini Pro #3). The strongest AI detection signals may be at the population level: multiple students submitting structurally similar text, sudden class-wide register shifts, vocabulary clustering.

**What this risks:** Over-investment in single-text detection when the real power is in cross-submission analysis.

**Approaches to test:**
1. **Inject 2-3 AI essays into the corpus and test cross-submission similarity**: If multiple students use the same AI, their submissions will cluster. Measure: does our embedding similarity in QuickAnalyzer catch this?
2. **Test departure-from-baseline**: If we had prior submissions from each student, would a sudden shift in voice/register/complexity flag AI use? This requires longitudinal test data we don't have yet.
3. **Design the population-level detector**: This may be a new module, not an AIC enhancement. It would live in the Insights pipeline (which already does class-level analysis) rather than the individual AIC.

### Testing gap 4: Feedback loop / teacher interaction

**The problem:** We're testing algorithms in isolation. In real use, the teacher sees the output and makes decisions. We haven't tested whether teachers can effectively interpret AIC scores, concern flags, and synthesis reports.

**Approaches to test:**
1. **Demo walkthrough with real teachers** (this is the demo itself)
2. **Measure: does the teacher make better decisions with the tool than without?** This is an impact evaluation, not a software test. But it's the test that ultimately matters.

---

## Timing Data (Accumulated)

### Local 8B (Ollama llama3.1:8b)

**From 3-student pilot (reliable per-unit rates):**
| Stage | Total (3 students) | Per student |
|-------|--------------------|-------------|
| Quick Analysis | <1s | — |
| Coding | 276s | ~92s |
| Concerns | 312s | ~104s |
| Themes | 168s | — (class-level) |
| Outliers | <1s | — |
| Synthesis | 157s | — (class-level) |
| Feedback | 235s | ~78s |
| **Total** | **1,240s** (~21 min) | ~413s/student |

**Extrapolation for 29 students:**
- Per-student stages: (92+104+78) * 29 = 7,946s ≈ 132 min
- Class-level stages: ~168 + ~157 = 325s (will be ~975s with 3-pass) ≈ 16 min
- **Estimated total: ~150 min (~2.5 hours)**
- Full 29-student run in progress — will update with actuals.

**Short Sub Review (SSR):** 93-136s per review (avg ~118s, ~2 min)

### Cloud API (Sonnet) — Pending

Requires ANTHROPIC_API_KEY to be configured. Not yet run.

---

## Common Cheating Methods Coverage Audit

> Cross-referenced with prior research in `devo/Dishonesty markers v 1-3 Raw/Academic_Dishonesty_Limitations_and_Markers_Expanded.md` (Dec 2025).
>
> **Framing note:** This matrix maps what the system can and can't surface. Many "gaps" are intentional — the system is a *conversation starter for teachers*, not a surveillance dragnet. Not every gap should be closed. Each potential addition must be evaluated for: (1) does it help the teacher understand their students better, or just catch more people? (2) who bears the false-positive cost? (3) does the behavior being "detected" always indicate dishonesty, or could it indicate something else the teacher needs to know?

### Coverage Matrix

| # | Submission Pattern | Surfaced? | Where | Notes |
|---|-------------------|-----------|-------|-------|
| 1 | **Raw AI copy-paste (with artifacts)** | ✅ YES | `_detect_raw_ai_artifacts()` | HTML headers, markdown bold, encoded tags → smoking gun. Strongest detector we have. |
| 2 | **Clean AI copy-paste (no artifacts)** | ❌ NO | — | 8/8 AI essays score < 1.0. OBS-AIC-01 + OBS-AIC-08 are the path to fixing this. |
| 3 | **Edited/polished AI text** | ❌ NO | — | Research doc Section 1. Seam detection, register shift analysis needed. |
| 4 | **Incoherent / nonsense submission** | ⚠️ PARTIAL | SSR only | `placeholder` category in SSR catches short incoherent text. No check for longer incoherent submissions. **Caution:** incoherent submissions are more often signals of crisis, confusion, or tech failure than "cheating" — see OBS-CHEAT-01. |
| 5 | **Copy of assignment prompt** | ❌ NO | — | Would need prompt text → submission similarity. **Caution:** ESL students legitimately scaffold off prompt language — see OBS-CHEAT-03. |
| 6 | **Copy from internet (plagiarism)** | ❌ NO (intentional) | — | Not a Turnitin clone by design. External plagiarism checking is a separate institutional tool. |
| 7 | **High cross-student similarity** | ⚠️ PARTIAL | `peer_comparison.py`, `quick_analyzer.py` | Peer comparison detects statistical outliers. QuickAnalyzer computes embeddings + clusters. But no pairwise content-similarity. **Caution:** similarity can indicate collaboration, shared cultural knowledge, or study groups — not only copying. See OBS-CHEAT-04. |
| 8 | **Paraphrasing tools (QuillBot etc.)** | ❌ NO | — | Research doc Section 7. Would need semantic similarity — high effort, uncertain reliability. |
| 9 | **Contract cheating (essay mills)** | ❌ NO (by design) | — | Research doc Section 4. Requires longitudinal baseline — draft comparison is the closest mechanism. Individual-text detection is unreliable for human-written contract work. |
| 10 | **Self-plagiarism (resubmit old work)** | ❌ NO | — | Would need cross-assignment comparison. Canvas API has history. |
| 11 | **File manipulation (wrong file, corrupted)** | ❌ NO | — | Research doc Section 5. Metadata, creation dates not analyzed. |
| 12 | **Invisible character tricks** | ❌ NO | — | Zero-width characters, whitespace inflation. See OBS-CHEAT-02 for what's safe to fix vs. what has bias risk. |
| 13 | **Submission timing patterns** | ❌ NO | — | Research doc marker #14. Canvas timestamps available but not analyzed. Least bias-prone of the unbuilt features. |
| 14 | **Minimal effort / partial work** | ✅ YES | SSR + signal matrix | Short Sub Reviewer + PERFUNCTORY/DISENGAGEMENT patterns in `patterns.py`. |
| 15 | **Hybrid AI/human writing** | ❌ NO | — | Paragraph-level stylometric analysis needed. Research doc Section 1 (seam detection). |

### Prior Research — Quick Wins Equity Check

The Dec 2025 research doc identified 5 "Phase 1: Quick Wins" (low effort, good detection value). However, the concurrent refinement agent correctly deferred Phases 3-5 (formulaic conclusions, hedging absence, transition density) due to cultural and linguistic bias risks. **Three of the five Quick Wins have the same risks:**

| Quick Win | Status | Equity Risk |
|-----------|--------|-------------|
| Sentence length variance | ⚠️ PARTIAL (OBS-AIC-02) | **LOW** — Sentence variance is structural, not cultural. Gradient scoring is safe. |
| Type-Token Ratio (vocab diversity) | ❌ NOT BUILT | **⚠️ HIGH** — ESL students, students with limited English vocabulary, students from oral traditions will have naturally lower TTR. Flagging low TTR differentially impacts these populations. **Same risk category as deferred Phases 3-5.** |
| Contractions analysis | ❌ NOT BUILT | **⚠️ HIGH** — ESL students are explicitly taught "do not use contractions in academic writing." Flagging absence of contractions in discussion posts would differentially flag ESL students following what they were taught. **Same risk category as deferred Phases 3-5.** |
| Filler words / discourse markers | ❌ NOT BUILT | **⚠️ HIGH** — "well", "actually", "I mean", "kind of" are culturally and linguistically variable. Students from more formal academic traditions, international students, students from non-English oral traditions don't use these specific English discourse markers. **This IS the "hedging absence" detector that the refinement agent already correctly deferred.** |
| Submission timing patterns | ❌ NOT BUILT | **LOW** — Temporal patterns are structural, not linguistic. Students with accommodations may have different windows, but that's addressable. Least bias-prone of the unbuilt features. |

**Conclusion:** Only 2 of 5 Quick Wins (sentence variance, submission timing) are safe to build without the cultural/linguistic bias research the refinement agent correctly flagged. The other 3 (TTR, contractions, discourse markers) need the same caution.

### OBS-CHEAT-01: No pre-analysis coherence gate

**Data:** The SSR handles short submissions below a word count threshold, but there is no coherence gate before full analysis. A student could submit 500 words of keyboard mash, pasted Lorem Ipsum, or random characters and the system would run the full AIC pipeline on it — wasting compute and producing meaningless scores. This is a technical efficiency problem: the system should short-circuit on non-analyzable text rather than generating a human presence report on "asdfghjkl."

**Gap:** No pre-analysis check that the text is actually natural language before running the full pipeline.

**Proposed fix:** Add a lightweight coherence gate at the top of `analyze_text()`:
1. **Dictionary word ratio**: Tokenize, check against a basic English word set. Below 40% recognizable words → short-circuit
2. **Lorem ipsum / placeholder detection**: Literal string match for known placeholder text
3. **Repeated content**: If any 10+ word sequence repeats 3+ times, short-circuit (copy-paste padding)
4. **Character entropy**: Keyboard mash has distinct character distribution from natural language — simple statistical check

When the gate triggers, return an `AnalysisResult` with a clear status: `"submission_not_analyzable"` — skip all marker detection, HP scoring, organizational analysis. The teacher sees "This submission does not contain analyzable text" and can follow up as appropriate (could be system-testing, tech failure, crisis — that's the teacher's judgment call, not the algorithm's).

**Priority:** LOW-MEDIUM — this is a robustness fix. It prevents the system from producing confident-sounding nonsense about nonsense.

**Location:** Top of `analyze_text()` in `Academic_Dishonesty_Check_v2.py`, before any marker detection runs.

---

### OBS-CHEAT-02: No invisible character / text manipulation detection

**Data:** No detection exists for: zero-width characters (U+200B, U+FEFF), non-breaking spaces used to inflate word count, or mixed-script character substitution.

**Gap:** Text manipulation tricks that inflate word count or evade plagiarism detection are invisible to the system.

**What's safe to fix vs. what has bias risk:**

| Fix | Bias Risk | Recommendation |
|-----|-----------|----------------|
| **Strip zero-width characters** (U+200B, U+FEFF, U+200C, etc.) | **NONE** — silent preprocessing, no flag | ✅ Implement as preprocessing. Count stripped chars silently for diagnostics. |
| **Normalize whitespace** (non-breaking spaces → regular spaces) | **NONE** — silent preprocessing | ✅ Implement as preprocessing. |
| **Flag high zero-width char count** | **LOW** — deliberate insertion of dozens of invisible characters is not a natural writing behavior in any language | ✅ Flag for teacher attention if count is high (>10) |
| **Homoglyph detection** (Cyrillic/Greek chars mixed with Latin) | **⚠️ MEDIUM** — Students who write in multiple scripts (Russian, Ukrainian, Greek, Serbian students writing in English) naturally produce mixed-script text from keyboard switching. Copy-paste from multilingual sources introduces non-Latin characters. **Flagging mixed scripts encodes Latin as default (#LANGUAGE_JUSTICE).** | ⚠️ Do NOT flag as suspicious. Silently normalize to Latin equivalents for analysis accuracy, but don't treat as evidence of manipulation. |

**Priority:** The safe fixes (zero-width stripping, whitespace normalization) are pure preprocessing improvements that make the analyzer more accurate without surveillance implications. Do those. Homoglyph *detection* (as distinct from normalization) needs more thought.

**Location:** Pre-processing step in `Academic_Dishonesty_Check_v2.py`.

---

### OBS-CHEAT-03: No prompt-copying detection

**Data:** The system does not compare submission text against the assignment prompt.

**Gap:** No mechanism to access or compare against the assignment prompt text.

**Equity consideration:** ESL students frequently scaffold off prompt language — echoing the prompt's vocabulary and sentence structures as a foundation for their response. This is a legitimate and well-documented ESL writing strategy (#LANGUAGE_JUSTICE). High prompt-submission similarity is NOT a reliable dishonesty signal for multilingual learners.

**Proposed fix (if built):** Accept assignment prompt text as optional input. Compute overlap. But route the output as *informational* ("submission closely follows prompt language"), not as a suspicious_score contribution. For short submissions that are *entirely* prompt text, the SSR already handles this (low engagement, placeholder classification).

**Priority:** LOW — The SSR handles the important case (short submissions). The remaining case (long submissions that heavily echo the prompt) is more likely scaffolding than dishonesty. Building a detector that flags this risks penalizing ESL strategies.

---

### OBS-CHEAT-04: Cross-student content similarity

**Data:** QuickAnalyzer already computes submission embeddings and clusters them. Peer comparison does statistical outlier detection. But neither computes pairwise content similarity between submissions.

**Gap:** The infrastructure exists (embeddings in QuickAnalyzer) but pairwise similarity isn't computed.

**Equity concerns — this is the highest-risk detector in this section:**
- **#COMMUNITY_CULTURAL_WEALTH:** Collaborative knowledge construction — studying together, family discussion, community knowledge-sharing — naturally produces similar language. In many cultures, learning is *inherently* collective. Similarity is evidence of strong community, not dishonesty.
- **#INTERDEPENDENCE:** Flagging similar submissions assumes independence is the default expectation. In many learning contexts, interdependent work is how learning happens. The system shouldn't encode an individualist learning model as neutral.
- **#ETHNIC_STUDIES:** Research on plagiarism detection tools (including Turnitin) shows disproportionate flagging of students of color. Cross-student similarity detection carries this same risk.
- **#CRITICAL_PEDAGOGY:** If students are producing similar work, the first question should be "is the assignment designed to produce diverse responses?" not "who copied from whom?" A prompt that has one right answer will produce convergent submissions regardless of copying.

**Proposed approach (if built):** Surface as a *class-level pattern* in the Insights pipeline, not as individual student flags. "This assignment produced unusually high cross-submission similarity" is useful pedagogical information (maybe the prompt needs revision). "Student A and Student B have similar submissions" is surveillance that the teacher may act on punitively, and the similarity may be legitimate.

**Priority:** MEDIUM for the class-level pattern version. **DO NOT BUILD** the individual-pair flagging version without extensive equity testing and teacher guidance about interpretation.

**Location:** `src/insights/quick_analyzer.py` — class-level similarity distribution metric, not pairwise flags.

---

## Next Steps

1. Complete full pipeline run (ethnic_studies + biology) — Ollama 8B in progress
2. Populate concern/theme/outlier observations from pipeline output
3. Configure ANTHROPIC_API_KEY and run Sonnet comparison
4. **Refinement session (in progress — separate agent)**:
   - Phase 0: Calibration script (`scripts/aic_calibration.py`) — before/after measurement
   - Phase 0.5: Fix OBS-AIC-09 bug (HPD pattern gap)
   - Phase 1: HP bridge (OBS-AIC-01) — low HP → suspicious_score contribution
   - Phase 2: Signal convergence (OBS-AIC-08) — multi-channel amplification
   - Phases 3-5 deferred pending cultural/linguistic bias research
5. **Quick wins (equity-vetted)**: Only sentence variance gradient (OBS-AIC-02) and submission timing are safe to build. TTR, contractions, and discourse markers have the same cultural/linguistic bias risks as deferred Phases 3-5 — need research first.
6. **Safe preprocessing**: Unicode normalization (zero-width stripping, whitespace normalization) — no bias risk, improves analyzer accuracy. Do this first.
7. **Common cheating coverage**: OBS-CHEAT-01 (coherence check → teacher check-in, not suspicious_score), OBS-CHEAT-04 (class-level similarity distribution, NOT pairwise student flags)
7. Run prompt escalation ladder (Testing gap 2) through AIC before and after refinements
8. Expand AI essay corpus with more models/prompts
9. Re-run full test suite after refinements to verify improvements
10. Design population-level detection module (Testing gap 3)
