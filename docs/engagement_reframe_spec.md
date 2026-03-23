# Engagement Analysis Reframe — System Specification

> From "Did the student cheat?" to "How did the student engage with the material?"

## Why this reframe

The AIC was designed to detect AI-generated text. Testing with 8 AI essays across 4 models showed the fundamental limit: **0/8 scored above 1.0 suspicious.** Architectural fixes (HP bridge + convergence) improved the scoring pipeline but can't overcome the detection frame's core problems:

1. **Arms race**: Keyword-based detection (AI transitions, generic phrases, inflated vocab) breaks with each model release. ChatGPT doesn't use "delving into" anymore.
2. **Cultural encoding**: The system's definition of "human writing" is neurotypical, Anglo-American academic English. ESL students, neurodivergent writers, and students from oral traditions trigger false positives.
3. **Adversarial fragility**: Gemini Pro faked human presence markers (10.3% HP) with a basic prompt. Sophisticated prompting defeats individual-text detection.
4. **Wrong question**: "Did AI write this?" assumes individual written text is the correct form of academic engagement. It isn't always.

The signals the system already collects — human presence categories, organizational structure, pattern analysis — actually measure **engagement**, not AI use. The reframe makes this explicit.

---

## Signal taxonomy

### Tier 1: Integrity signals (clear gaming behavior)

These are binary, non-negotiable flags. No cultural bias risk. Keep as explicit flags in the UI.

| Signal | What it catches | Source | Status |
|---|---|---|---|
| **Smoking gun** | Raw chatbot HTML/markdown paste artifacts | `_detect_raw_ai_artifacts()` | ✅ Built. Forces concern_level='high'. |
| **Unicode manipulation** | Zero-width characters, homoglyph insertion | `Academic_Dishonesty_Check_v2.py` | ✅ Detection built (count + details). Normalization/stripping not yet implemented. |
| **Teacher-test detection** | "Does anyone read these?" messages | `patterns.py` TEACHER_NOTE | ✅ Built. 70+ regex variants + semantic detection in QuickAnalyzer. Surfaced as relationship marker, not concern. |
| **Incoherence gate** | Keyboard mash, Lorem ipsum, random characters | `gibberish_gate.py` | ✅ Built. Conservative gate (confidence ≥0.7 to skip LLM). Equity safeguards: does NOT flag poor grammar, AAVE, slang, non-English, short-but-genuine. Translated text bypasses all checks. |

These work because they detect **gaming behavior** — active attempts to circumvent rather than engage. No ambiguity, no population sensitivity.

All four Tier 1 signals are implemented and wired into both the AIC pathway (`Academic_Dishonesty_Check_v2.py`) and the Insights pipeline (`quick_analyzer.py`). Integrity flags are tracked in `marker_counts` and `markers_found` dicts, added to `context_applied` notes with ⚠ prefix.

### Tier 2: Structural indicators — what the data actually shows

Early versions of this spec claimed 6 structural signals were "stable across AI generations." Calibration testing (8 AI essays, 200 human essays) showed this was overstated. Here's what the data supports:

**Measured and partially discriminating:**

| Signal | Data | Discrimination | Model-dependency |
|---|---|---|---|
| **Sentence length uniformity** | AI mean VC=0.336, Human mean VC=0.458 (d=0.99). 4/8 AI essays below human P10. | MODERATE — catches ~50% of AI output | HIGH — ChatGPT (0.226, 0.303) and Gemini Thinking D (0.189) are distinctively low; Gemini Pro (0.458) and Claude (0.434, 0.437) produce variance AT the human mean |
| **Absence of very short sentences** | ChatGPT has 0% sentences <8 words; humans have 6.5% mean | WEAK — only ChatGPT-specific | HIGH — Gemini Pro produces short sentences |
| **Max/min sentence ratio** | AI mean 3.2, Human mean 5.68 — AI avoids extremes | WEAK — high overlap | MODERATE — more consistent across models |

**NOT measured — theoretical only (do not claim as validated):**

| Signal | Status | Why unmeasured |
|---|---|---|
| Paragraph length uniformity | MEASURED (after parsing fix): AI mean VC=0.393, Human mean VC=0.459, d=0.26. WEAK — high overlap, model-dependent. | Original claim of "unmeasurable" was a parsing bug (split on double-newline; text uses single-newline). Now corrected. AI essays have 3-7 paragraphs. Signal is too weak (d=0.26) to discriminate. Need broader testing with longer essays (5-paragraph, multi-page) to see if the signal strengthens at longer lengths. |
| Absence of typos/errors | NOT MEASURED | Requires spell-check integration. Also entangled with language background (#LANGUAGE_JUSTICE) — ESL errors are human markers, not a deficiency standard. |
| Register consistency | NOT MEASURED | Would require implementing register analysis. OBS-AIC-10 identified the concept but no detector exists. |
| Transition distribution | NOT MEASURED | Only counted as binary pattern presence, not distributional analysis. |

**Newly identified signals — validated as convergence contributors (2026-03-22):**

Testing identified three signals with large effect sizes. Initial measurement (n=4 AI, n=295 human) showed d > 1.8 for all three. Claude Sonnet validation (n=5 additional AI essays across naive, personal, formal, lab, and adversarial prompts) refined the picture:

| Signal | ChatGPT/Gemini | Claude Sonnet | Human (n=295) | Convergence role |
|---|---|---|---|---|
| **Sentence-starter diversity** | 1.000 (all 4 essays, all prompts) | 1.000 naive, 0.938 formal, 0.786 personal, 0.714 lab, 0.643 adversarial | 0.759 mean (13.6% also perfect) | **Strong for ChatGPT/Gemini, moderate for Claude.** Fires reliably on generic prompts; Claude evades on personal/casual text. Threshold ≥0.95 correctly separates. |
| **Comma density** (per 100 words) | 4.83–6.81 (all above human range) | 2.16–2.49 casual (human range!), 3.79 formal, 4.56 lab | 2.80 mean | **Strong for ChatGPT/Gemini, weak for Claude.** Claude's casual output is indistinguishable from human comma patterns. Threshold ≥4.5 catches only formal Claude + all ChatGPT/Gemini. |
| **Average word length** | 4.53–5.65 | 4.11–4.29 casual (human range), 4.80–5.88 formal/lab | 4.28 mean | **Model- and prompt-dependent.** Claude matches human range on casual text; formal/lab elevated. Threshold ≥4.8 avoids casual false positives. |

**Design principle: convergence, not standalone detection.** No single signal reliably identifies all AI output across all models and prompt styles. That is expected and acceptable. These signals are valuable as **convergence channels** — when starter diversity + comma density + sentence uniformity + organizational patterns all co-occur, the cumulative picture is meaningful even if any individual signal is ambiguous. The system's Phase 2 convergence architecture (multiplier at 3+ channels) is designed exactly for this.

A signal that catches ChatGPT/Gemini 80% of the time and Claude 40% of the time is doing real work in the pipeline. It doesn't need to catch everything — no single signal does. Under the engagement frame, these signals contribute to cohort-relative baselines (Mechanism 1): a class where most students write with natural starter repetition and moderate comma density will surface the submission with perfect diversity on all three as a statistical outlier *relative to that class*.

**Bias protections — who bears the cost of false signals (#ALGORITHMIC_JUSTICE):**

These signals carry differential risk across populations:

- **Comma density**: Formal academic ESL writing may produce elevated comma density through subordinate clause patterns learned in grammar-focused instruction. When ESL error patterns are detected, comma density scoring is zeroed — the signal is silenced rather than reduced, because formal comma usage in ESL writing is a *linguistic asset* (#COMMUNITY_CULTURAL_WEALTH), not an indicator of disengagement.
- **Avg word length**: Correlates with education level and reading exposure. Students from under-resourced schools may use shorter words not because they're disengaged but because they haven't had access to the vocabulary (#ETHNIC_STUDIES — the "word gap" is a resource gap, not a capacity gap). Cohort-relative measurement (Mechanism 1) mitigates this by comparing within-class, not against absolute thresholds.
- **Starter diversity**: Lowest bias risk. Humans across all populations naturally repeat sentence starters. The signal measures an architectural property of transformer models, not a cultural or educational pattern. However: students writing in a second language may produce high starter diversity through careful construction rather than AI use (#LANGUAGE_JUSTICE). The ESL context should moderate this signal too.

**Validation status**: 13 AI essays across 4 models (ChatGPT, Gemini Pro, Gemini Thinking, Claude Sonnet) + 200 DAIGT human essays. Signals implemented in `organizational_analyzer.py`, wired into convergence in `Academic_Dishonesty_Check_v2.py`. Calibration snapshot: `data/calibration_snapshots/claude_validation.json`. Further validation needed via OpenRouter (GPT-4o, Llama, Mistral) to characterize model-dependency more broadly.

**Implementation status (2026-03-22)**: All three Phase A signals are ✅ built with gradient scoring:
- Sentence-starter diversity: gradient at ≥0.95, max score 0.6 for perfect diversity with ≥8 sentences
- Comma density: gradient 3.5–5.0, max score 0.4 at ≥5.0 per 100 words
- Average word length: gradient 4.5–5.0, max score 0.4 at ≥5.0 chars

These participate in the **8-channel convergence system**: pattern_markers, organizational, hp_absence, authenticity_deficit, uniformity, starter_diversity, comma_density, avg_word_length. Multiplier formula: `1.0 + 0.2 × (converging - 2)` when 3+ channels agree. ESL protection: comma_density and avg_word_length are **completely zeroed** (not reduced) when ESL error patterns are detected.

**Reoriented signals** (not excluded — reframed from detection to engagement interpretation):

These signals were originally designed as AI detection markers. They're unreliable for detection (unstable across model versions, high cultural bias risk). But under the engagement frame, they have value as supplementary engagement context — IF reinterpreted:

| Signal | Detection frame (deprecated) | Engagement frame (reoriented) | Bias caveat |
|---|---|---|---|
| AI transitions ("Furthermore", "Moreover") | "AI wrote this" | "Formal register in an informal context — student may not be matching the assignment's expected register" | ESL students taught formal transitions; don't penalize |
| Generic phrases ("Throughout history") | "AI wrote this" | "Generic treatment — no discipline-specific depth visible" | Same |
| TTR / vocabulary diversity | "AI has lower TTR" | "Limited vocabulary range — student may not be using discipline-specific terms from the readings" | ESL/oral tradition students naturally have different TTR; must use cohort-relative, never absolute |
| Contractions analysis | "AI doesn't use contractions" | "Register signal — helps characterize the student's writing voice for longitudinal tracking" | ESL students taught "no contractions"; never flag absence |
| Filler words / discourse markers | "AI doesn't say 'like' or 'um'" | "Informality signal — presence indicates real-time thinking; useful for productive messiness scoring" | Culturally variable; only credit presence, never penalize absence |

Key principle: these signals can CREDIT human presence (filler words = evidence of real-time thinking) but should never PENALIZE absence (no filler words ≠ AI). Asymmetric interpretation.

### Tier 3: Engagement signals (the primary product)

These measure whether a human mind is at work — personal connection, intellectual effort, course engagement.

**Honest limitation**: AI CAN fake these signals. Gemini Pro scored 10.3% HP by generating fake personal stories and informal language. A well-prompted AI can produce text that looks "engaged." This means engagement signals are NOT reliable as AI detection. But they ARE reliable as engagement measurement — because the question shifts: even if an AI produced text with personal voice markers, did the STUDENT personally connect to the material? The teacher's conversation ("tell me more about that experience you described") will reveal whether the engagement was real. The signals are conversation starters, not verdicts.

**Design direction**: This system is deliberately NOT a conventional AI detector. We identify what we can identify (structural patterns, engagement dimensions, gaming behavior), but the emphasis is on helping teachers understand and support student engagement — not on catching AI use. This is a different product with different value.

**Engagement across disciplines**: Different disciplines produce different engagement patterns. The system must recognize this — engagement in an ethnic studies discussion post looks nothing like engagement in a biology lab report:

| Discipline context | What engagement looks like | Key HPD signals | What's different |
|---|---|---|---|
| **Ethnic Studies / Humanities** | Personal connection to ideas, cultural reference, position-taking, wrestling with power dynamics | Authentic voice, emotional stakes, cognitive struggle | Personal disclosure is expected; absence is notable |
| **Biology / Lab Sciences** | Precise methodology, data interpretation, connecting results to theory | Contextual grounding (lab procedure, data), source depth | Productive messiness looks different (hypothesis revision, not personal hedging). Personal voice is less expected |
| **Math / Quantitative** | Problem-solving process, showing work, identifying where understanding breaks down | Cognitive struggle (dominant), real-time processing | Engagement is visible through PROCESS documentation, not personal reflection |
| **English / Literature** | Close reading, textual evidence, interpretive risk-taking | Source depth (dominant), intellectual work | Quote specificity is the primary engagement marker |
| **History / Social Science** | Evidence-based argument, source evaluation, connecting past to present | Source depth, contextual grounding, intellectual work | Primary source engagement vs. textbook repetition |
| **CTE / Vocational** | Applied knowledge, practical examples, connecting theory to practice | Contextual grounding (workplace, hands-on experience) | Engagement shows through concrete application, not abstract analysis |

The 8 AIC modes (discussion, essay, lab, notes, personal, draft, outline, auto) partially capture this, but discipline-specific calibration would be stronger. Cohort calibration (Mechanism 1 in Learning Through Use) handles this automatically — the system learns what engagement looks like in THIS class by observing the actual distribution.

| Signal | What it measures | HPD category | Value to teacher |
|---|---|---|---|
| **Personal connection** | Student brings their own perspective, language, cultural references | Authentic Voice (15%) | "Is this student personally invested?" |
| **Intellectual work** | Evidence of thinking in real time — confusion, changed understanding, working through | Cognitive Struggle (20%) | "Is this student wrestling with the ideas?" |
| **Course engagement** | References to class, readings, discussions, assignment context | Contextual Grounding (35%) | "Is this student connected to the course?" |
| **Personal investment** | Stakes, care, emotional connection to the material | Emotional Stakes (20%) | "Does this matter to this student?" |
| **Real-time processing** | Self-correction, hedging, false starts, revision thinking | Productive Messiness (10%) | "Is this student thinking as they write?" |
| **Source depth** | Specific quotes, page references vs. generic "the reading says" | ✅ `citation_checker.py` integrated into AIC + Insights | "Did this student engage with the actual readings?" |
| **Hedging presence** | Natural epistemic uncertainty in discussion context | Partially covered by HPD productive_messiness markers (self-correction, hedging). No standalone mode-sensitive detector. | "Is this student expressing genuine uncertainty?" |

**Note on contextual grounding and citations**: The system currently uses GENERIC patterns ("In class when...", "The textbook on page...") for contextual grounding. Canvas API integration should target READING references (author names, work titles, specific concepts), not just the assignment prompt — a student who feeds the prompt into ChatGPT will produce on-topic text but WON'T reference the specific arguments from assigned readings.

The **citation checker** (`src/insights/citation_checker.py`) already handles significant parts of this:
- Extracts URLs, DOIs, author-year (APA), inline author references, quoted titles, and generic reading references
- Distinguishes **specific citations** (author-year, URL, DOI, quoted title) from **generic references** ("the reading says...") — tracked separately as `specific_source_count` vs `generic_reading_ref_count`
- Builds **class-level source aggregation**: most-cited sources, students with/without citations
- Has async URL/DOI verification (HEAD request — marks unverified, never penalizes)
- Excellent equity notes: paywalled, non-English, community sources will appear unverified — informational only

**What's built vs. what's needed**:
- Built: Citation extraction, class-level aggregation ("what sources did the class engage with most?"), specific vs. generic distinction, URL verification
- Needed: Matching citations against a **known course reading list** (Canvas integration — could surface whether cited sources are from assigned readings vs. outside research)
- Needed: **UX surfacing** — individual student citation patterns + class-wide source engagement patterns ("10 students cited Crenshaw; 3 cited sources outside the syllabus; 8 used only generic 'the reading says' references")
- Potential: Class-level source map showing WHICH readings got the most engagement and HOW students engaged with them (quoted specific passages? paraphrased arguments? mentioned by name only?)

### Tier 4: Population-level signals (class patterns)

These operate across submissions, not on individual text. They're the strongest signals for both engagement analysis and integrity.

| Signal | What it measures | Source | Value to teacher |
|---|---|---|---|
| **Similarity clusters** | Multiple students saying the same thing the same way | ✅ `quick_analyzer._pairwise_similarity()` | "Several students submitted very similar responses — is the assignment eliciting diverse thinking?" |
| **Theme convergence** | Class gravitating toward specific ideas | ✅ Insights pipeline (theme_generator + synthesizer) | "Here's what the class is most engaged with" |
| **Engagement outliers** | Students whose engagement pattern differs significantly from class | ✅ QuickAnalyzer clusters + outlier pass | "These students may need a conversation" |
| **Concern patterns** | Essentializing, tone-policing, structural misunderstandings | ✅ Concern detector + signal matrix + anti-bias post-processing | "Watch for these patterns in class discussion" |
| **Longitudinal voice** | How a student's engagement changes over time | ⚠️ Partial: `trajectory.py` StudentArc tracks word counts + submission status across runs. Missing: per-student signal vectors, Mahalanobis distance, drift detection. | "This student's engagement shifted — here's how" |
| **Class trajectory** | How the class's engagement evolves across assignments — both quantitative (signal trends) AND qualitative (how the engagement changes, not just that it does) | ⚠️ Partial: `trajectory.py` TrajectoryAnalyzer computes theme evolution (recurring/new/fading), engagement trends, concern trends, exhaustion trends, most-referenced readings. Missing: qualitative narrative via LLM. | "The class started with surface-level engagement with intersectionality but by Assignment 4, students are connecting course concepts to their own experiences and citing specific passages" |

**Equity framing for similarity**: Similarity can indicate strong community, collaborative learning, or shared cultural knowledge (#INTERDEPENDENCE, #COMMUNITY_CULTURAL_WEALTH) — not only copying. Surface as class-level pattern ("this assignment had unusually high similarity"), NOT as individual student flags. The first question is always: "Is the assignment designed to produce diverse responses?"

**Divergence-from-teacher-framing signal**: A particularly valuable pattern is when multiple students write similar things that **diverge from how the teacher taught the concept**. AI provides a GENERAL answer (from training data); the teacher taught a DISCIPLINE-SPECIFIC or COURSE-SPECIFIC answer. When several students all frame a concept the same way — and that framing doesn't match the course's approach — this is a strong signal. Examples:
- Teacher taught Crenshaw's traffic intersection metaphor; students all describe intersectionality using a "matrix of oppression" framing (a different scholarly tradition the AI trained on)
- Teacher emphasized a specific lab methodology; students all describe a generic textbook procedure
- Multiple students make the same factual error that reflects a common AI hallucination rather than a common student misunderstanding

This signal is ambiguous by design: it COULD indicate AI use, or it COULD indicate students collaborating, or consulting the same outside source. The system surfaces the pattern; the teacher interprets. The key innovation is comparing student framing against the TEACHER'S framing — which requires assignment context awareness (Mechanism 2).

**Longitudinal signals serve both student AND class**: Per-student voice tracking shows individual growth and consistency. Class trajectory shows whether the group is deepening, stagnating, or diverging across assignments. Cross-assignment data storage is partially built: `InsightsStore` persists per-run codings, and `TrajectoryAnalyzer` loads all completed runs for a course to compute semester-level patterns. What's missing: per-student engagement signal vectors (not just word counts) stored across runs, and statistical consistency analysis (Mahalanobis distance).

**Pairwise similarity implementation (2026-03-22)**: ✅ Built in `quick_analyzer._pairwise_similarity()`. Uses scikit-learn cosine similarity on TF-IDF vectors. Class-level stats (mean, max, pairs >0.85, >0.70). Individual pairs surfaced ONLY at ≥0.90 threshold (HighSimilarityPair records). Pedagogical framing built in — observation text notes collaborative/community interpretations, never blame. This matches the "What we're NOT building" exclusion of moderate-threshold pair flagging.

---

## System limits — what the engagement frame cannot see

The engagement frame is better than the detection frame, but it has its own blind spots. Naming these is essential (#FEMINIST_TECHNOSCIENCE — no view is neutral):

1. **Submission-based visibility**: The system analyzes what students submit — including audio (transcribed via whisper.cpp) and non-English text (translated via Ollama). It does NOT exclude oral submissions. But engagement happening OUTSIDE submissions — classroom discussion, group work, embodied practice — is not captured. The system should never be the SOLE measure of engagement; it's one input to the teacher's judgment. (#COMMUNITY_CULTURAL_WEALTH — embodied knowledge and relational learning that don't become submissions are assets this system cannot measure.)

2. **Communal voice — partially addressed, not fully**: The HPD already includes communal expression markers at high weights: "in my culture" (0.9), "my family/ancestors/elders/community believe/teach/say/told me" (0.9), "our community" (0.6), "in my/our neighborhood/community/town" (0.9). So the system does NOT simply privilege individualistic expression — communal voice IS recognized and weighted heavily. However, the specific manifestations of communal voice vary across cultural contexts (Indigenous knowledge sharing, Black church rhetorical traditions, Latinx familismo, Asian collectivist framing) and the pattern library's coverage of each is untested. Cohort calibration will further adapt to specific class populations. The remaining gap: communal voice expressed through RELATIONAL structures that don't match the current pattern templates may still be missed. (#INTERDEPENDENCE — the foundation is in place; coverage depth needs real-world validation.)

3. **English-centric analysis**: The preprocessing pipeline can translate non-English submissions (Ollama chunked translation) and transcribe audio (whisper.cpp), so non-English and oral submissions ARE supported. The HPD also has translanguaging markers ("I don't know the English word for", "This is hard to translate"). However, the engagement signals themselves (pattern matching, sentence structure analysis) operate on the English output of translation — nuance, register, and cultural expression that don't survive translation are lost. This is a structural limit of working through translation, not of the system's design intent. (#LANGUAGE_JUSTICE)

4. **Temporal snapshot**: Each analysis captures a single assignment. A student processing ideas slowly (#CRIP_TIME) may show low engagement on one assignment but deep engagement over a semester. Without longitudinal data, the system penalizes different processing speeds.

5. **Who controls this data**: Students currently have zero visibility into how their writing is analyzed. Under #INDIGENOUS_DATA_SOVEREIGNTY, the people described by data should have governance over it. The spec's "student visibility" open question is not optional — it's a design requirement that should be addressed before deployment.

6. **Sorting mechanism persists**: Even under engagement framing, the system still sorts students into categories (high/moderate/limited engagement). This sorting can become a self-fulfilling prophecy if teachers treat "limited engagement" as a fixed attribute rather than a situational observation. The system should explicitly frame each analysis as a SNAPSHOT, not a CHARACTER ASSESSMENT. (#TRANSFORMATIVE_JUSTICE)

---

## UI framing

### Current → Reframed

| Current | Reframed | Rationale |
|---|---|---|
| Suspicious score: 3.2 | Engagement depth: limited | Measures what the teacher actually needs |
| Concern level: moderate | Conversation opportunity: yes | Shifts from accusation to pedagogy |
| AI organizational patterns detected | Generic structure — no course-specific engagement visible | Describes what's absent, not what's suspected |
| Low human presence (2.7%) | Limited personal connection to material | Teacher can act on this |
| False positive on ESL student | Engagement signal unclear — teacher interpretation needed | Honest about system limits |
| Signal convergence: 4 channels | Multiple engagement dimensions absent | More useful than "probably AI" |

### What stays as explicit flags

Integrity signals (Tier 1) remain as distinct flags:
- "Chatbot paste artifacts detected" (smoking gun)
- "Text manipulation detected" (unicode gaming)
- "Student testing if submissions are read" (teacher-test — surface as trust opportunity)

Structural indicators (Tier 2) surface as supplementary context:
- "This submission has unusually uniform structure" — not "AI detected"

### Engagement summary format (per student)

**Design target** (from original spec):
```
Engagement Snapshot: [Student Name] — [Assignment Name]
  Course connection:    ████████░░  Strong (references class discussion, cites p.47)
  Personal investment:  ██████░░░░  Moderate (personal perspective present)
  Intellectual work:    ███░░░░░░░  Limited (no evidence of wrestling with ideas)
  Real-time thinking:   ██░░░░░░░░  Minimal (polished, no revision markers)

  Structural note: Uniform sentence rhythm (this pattern is common in
  ChatGPT output but also appears in some careful human writers)

  Suggested conversation: "I'd love to hear more about how you
  worked through the tension between [X] and [Y] in the reading."

  ⚠ This is a snapshot of one submission, not a measure of the student.
  Some engagement happens outside of text — conversation, participation,
  collaborative work — that this analysis cannot see.
```

**Current implementation (2026-03-22)**: ✅ Engagement snapshots are displayed in `insights_panel.py` as a chip row per student card:
- **Engagement depth**: color-coded chip (green=strong, amber=moderate, rose=limited/minimal)
- **Conversation opportunity**: 💬 "check in" chip (rose) when engagement limited/minimal
- **Register**: subject area code chip (amber) when applicable
- **Truncation warning**: rose chip when submission appears incomplete
- **Source depth**: specific citations, generic references, total count + interpretation

**Gap**: Bar chart visualization (the `████████░░` format above) is not implemented — display uses categorical chips only. This is a reasonable trade-off for 8B model reliability: 8B models can't judge engagement_depth gradients reliably, so the system surfaces evidence (quotes, concepts, connections) and lets the teacher judge. The chips are more honest than false-precision bar charts.

Note: "Engagement Snapshot" — not "Profile." The word "snapshot" frames it as situational and temporal; "profile" implies a fixed characterization.

---

## What this means for AIC vs Insights

**AIC** (fast, no LLM required):
- Computes engagement signals from text analysis alone (HPD → 5 engagement dimensions + source_depth)
- 8-channel convergence system with multiplier at 3+ channels
- Flags integrity signals (Tier 1: smoking gun, unicode, gibberish)
- Notes structural indicators (Tier 2: sentence uniformity, starter diversity, comma density, avg word length)
- ESL protections (error pattern detection → 40% score reduction + structural signal zeroing)
- Mode-adaptive thresholds via `weight_personal_voice` scaling
- Runs in seconds, works offline

**Insights pipeline** (deeper, requires LLM — ✅ substantially built):

The pipeline is tier-differentiated (lightweight/medium/deep) and stages are:
1. Data fetch (Canvas API)
2. Preprocessing (translation via Ollama + transcription via whisper.cpp)
3. Quick analysis (non-LLM: TF-IDF, embedding clustering, pairwise similarity, keyword patterns, VADER + GoEmotions, assignment connection scoring, gibberish gate, citation analysis)
4. Per-submission coding (LLM: themes, quotes, emotional register, lens observations, engagement signals — with concept validation hallucination guard)
5. Concern detection (always separate LLM call — with anti-bias post-processing: tone-policing protection, content-vs-distress classification)
6. Theme generation (embedding-cluster-grouped, with timeout fallback to tag-frequency themes)
7. Outlier surfacing
8. Guided synthesis (4-call scoped approach: concern patterns → engagement highlights → tensions → class temperature)
9. Short submission review (engagement-focused verdict: CREDIT or TEACHER_REVIEW, with 8 brevity categories and anti-bias post-processing)
10. Feedback drafting (per-student drafts with equity framing, multilingual acknowledgment)
11. Cross-validation (LLM vs. signal matrix comparison → ValidationFlag)

**Additional infrastructure built**:
- Resumable pipeline with stage checkpoints (recovery after crash/restart)
- Sleep prevention (caffeinate/powercfg/systemd-inhibit)
- Teacher profile system (TeacherProfileManager: theme renames/splits/merges, concern sensitivity, custom patterns, prompt fragment generation)
- Lens template system (subject-specific analysis framing: ethnic studies, social science, humanities, English/writing)
- Course profile dialog (GUI for profile management, template fork/save)
- Trajectory analysis (cross-run: theme evolution, engagement/concern/exhaustion trends, student arcs)
- Chatbot export (packages results for student-facing assistant)

**Relationship**: AIC is the fast pre-screen; Insights is the deep analysis. They complement, don't duplicate. AIC engagement signals feed into Insights `SubmissionCodingRecord.engagement_signals`. A teacher running AIC sees "this student may not be engaging deeply — here's a conversation starter." A teacher running Insights sees "here's what the whole class is thinking, where they're struggling, and which students need attention."

---

## AI literacy dimension

The engagement frame opens a path toward AI literacy coaching — helping students learn to use AI as a thinking tool rather than a thinking replacement.

The system can suggest (not determine) how AI might be involved based on engagement + structural patterns:

| | Structural indicators present | No structural indicators |
|---|---|---|
| **High engagement** | May be using AI as thinking partner — genuine engagement visible through the tool use. This is the emerging best practice. | Writing independently with strong engagement — the traditional ideal, but not the only valid approach. |
| **Low engagement** | May be outsourcing thinking — the tool did the work, the student didn't engage. This is where a conversation helps most. | Disengaged regardless of tools — also needs a conversation, about engagement not AI. |

**Important caveat**: The structural indicators are model-dependent (see Tier 2 data). The system cannot reliably detect AI use — it can only note structural patterns that are SOMETIMES associated with AI output. The teacher should never say "I can see you used AI" based on this data. Instead: "I noticed your submission doesn't show much engagement with the material — let's talk about your process."

The AI literacy coaching opportunity: when a teacher suspects AI use (from any source, not just this system), the engagement data tells them WHERE engagement is missing, which shapes the conversation: "Your response doesn't reference our class discussion — did you engage with the readings before writing?" This works whether or not AI was involved.

---

## Learning through use — adaptive calibration system

The DAIGT test corpus gives us formal competition essays from strong writers. It tells us nothing about normal classroom variation, ESL patterns, neurodivergent writing, first-gen patterns. The system must calibrate from actual classroom data. Full mechanism specs are in `docs/engagement_reframe_learning.md`. Summary:

### Six mechanisms

**Mechanism 1: Cohort calibration** — After processing a class, compute per-signal distributions (mean, stdev, P10/P25/P75/P90) as the baseline for THAT class. Student engagement is measured relative to classmates, not absolute thresholds. Bayesian cold-start blends education-level defaults with assignment-type priors. Baselines evolve via exponential moving average (α=0.3) across assignments.

**Mechanism 2: Assignment context awareness** — Parse assignment descriptions for named references (author names, work titles, key concepts from READINGS, not just the prompt). Check whether submissions reference these specifically ("Crenshaw argues in *Mapping the Margins*...") or generically ("intersectionality shows..."). Canvas API provides assignment metadata; no LLM needed — TF-IDF + named entity extraction.

**Mechanism 3: Teacher feedback loop** — Granular corrections (not just thumbs up/down): signal-level corrections ("this student engages orally"), threshold adjustments ("this engagement level is normal for my class"), signal weight overrides ("productive messiness doesn't apply to lab reports"), student annotations ("L1 transfer pattern, not a concern"). System surfaces patterns in corrections: "You've adjusted authentic_voice 8 times for communal expression — adjust the weight?"

**Mechanism 4: Voice fingerprinting** — Per-student signal vectors across assignments. Mahalanobis distance for consistency comparison (accounts for signal covariance). Growth tracking shows engagement trajectory: "contextual grounding and cognitive struggle trending up over 4 assignments." Drift alerts surface notable deviations from a student's own baseline.

**Mechanism 5: Class culture modeling** — Emerges from mechanisms 1-4. Not configured — observed. "Based on 4 assignments, your class tends toward formal analytical engagement with strong source references."

**Mechanism 6: Predictive engagement** — After 5+ assignments, system predicts expected engagement per student per assignment type. Actual submission significantly below expected → conversation opportunity with specific framing.

**Student visibility** (#INDIGENOUS_DATA_SOVEREIGNTY): Students can see their OWN engagement trajectory. Opt-in sharing with teacher. Default: student-private. Transforms system from surveillance to self-awareness.

---

## Implementation priorities — status as of 2026-03-22

### Phase A: Foundation + signals — ✅ COMPLETE (except corpus expansion)

1. ✅ Gradient sentence uniformity in `organizational_analyzer.py` — gradient scoring 0.15–0.40
2. ⚠️ Unicode preprocessing — detection built (count + details), stripping/normalization not yet implemented
3. ✅ Sentence-starter diversity — gradient scoring, d=2.13 effect size
4. ❌ Expanded AI test corpus via OpenRouter — not started
5. ✅ Wire `gibberish_gate.py` and `citation_checker.py` into AIC pathway — both integrated with graceful fallback
6. ✅ Comma density — gradient scoring, d=1.85 effect size
7. ✅ Average word length — gradient scoring, d=2.17 effect size
8. ✅ 8-channel convergence system — multiplier at 3+ channels
9. ✅ ESL protections — error pattern detection + structural signal zeroing

### Phase B: Calibration infrastructure — ❌ NOT STARTED

10. ❌ Cohort calibration (class-relative baselines) — highest-impact remaining gap
11. ⚠️ Assignment context extraction — Canvas API fetches assignment description; QA computes vocabulary overlap (AssignmentConnectionScore). Missing: named reference extraction, engagement expectation matrix, reading-vs-topic distinction
12. ❌ Cold-start Bayesian priors — WeightComposer provides education-level defaults but not wired into calibration

### Phase C: Engagement framing + population-level — ✅ MOSTLY COMPLETE

13. ✅ UI reframe — engagement depth chips (strong/moderate/limited/minimal), conversation opportunity, register chips. Integrity flags tracked separately. Bar chart visualization not implemented (chips are more honest for 8B reliability).
14. ✅ Class-level similarity — pairwise cosine in `quick_analyzer.py`, class-level stats, ≥0.90 pairs surfaced with pedagogical framing
15. ✅ Citation depth as engagement signal — specific vs generic distinction in `citation_checker.py`, mapped to source_depth in engagement signals
16. ⚠️ Reoriented signals — structural analysis exists; asymmetric "credit presence, never penalize absence" principle not explicitly enforced in code

### Phase D: Teacher feedback + longitudinal — ⚠️ PARTIAL

17. ⚠️ Teacher feedback loop — TeacherProfileManager built (theme renames/splits/merges, concern sensitivity ±0.1, custom patterns, strength patterns, disabled defaults). Missing: per-signal weight overrides, threshold adjustment, per-student annotations alongside signal data, correction pattern recognition surfacing.
18. ❌ Voice fingerprinting — StudentArc tracks word counts across runs but not signal vectors. No Mahalanobis distance, no drift detection.
19. ⚠️ Growth tracking — TrajectoryAnalyzer computes theme evolution, engagement/concern/exhaustion trends at class level. Per-student engagement signal growth not tracked.

### Phase E: Emergent intelligence — ❌ NOT STARTED

20. ❌ Class culture modeling (depends on B + D)
21. ❌ Predictive engagement (depends on D longitudinal data)
22. ❌ AI literacy coaching prompts

### Built beyond original spec (not in original phases)

These features were built during the Insights pipeline implementation and were not anticipated in the original spec:

- ✅ **Guided synthesis** — 4-call scoped approach replacing broken open-ended synthesis (concern patterns → engagement highlights → tensions → class temperature)
- ✅ **Cross-validation** — LLM vs. signal matrix comparison, ValidationFlag model
- ✅ **Short submission review** — 8 brevity categories (concise_complete, dense_engagement, format_appropriate, multilingual, partial_attempt, wrong_submission, placeholder, unclear), anti-bias post-processing, register bias detection
- ✅ **Feedback drafting** — per-student draft feedback with equity framing, multilingual acknowledgment, confidence thresholding
- ✅ **Trajectory analysis** — cross-run theme evolution (recurring/new/fading/one-time), engagement/concern/exhaustion trends, most-referenced readings, per-student word count arcs
- ✅ **Lens template system** — subject-specific analysis framing (ethnic studies, social science, humanities, English/writing) with equity attention, concern framing fragments, assignment variants
- ✅ **Course profile dialog** — GUI for profile management with template fork/save system
- ✅ **Chatbot export** — packages synthesis + codings for student-facing assistant
- ✅ **Embedding-based clustering** — sentence-transformers + k-means/HDBSCAN for theme grouping
- ✅ **Signal matrix** — VADER × keyword category pre-screening with critical keyword protection (structural critique ≠ concern)
- ✅ **Anti-bias post-processing** — tone-policing detection in concern flags, content-vs-distress classification, AAVE sentiment suppression, informal register bias detection
- ✅ **Resumable pipeline** — stage checkpoints for crash recovery
- ✅ **Concept validation** — hallucination guard rejecting concepts 8B attributes from prompt rather than submission text

---

## What we're NOT building

- **Plagiarism checker** — Turnitin's job
- **Perplexity/burstiness** — requires running an LLM, marginal benefit given engagement framing
- **Individual-pair similarity flagging at moderate thresholds** — equity risks too high; moderate similarity (30-80%) stays class-level only, since similar language can reflect community cultural wealth, collaborative learning, or shared cultural knowledge. **Exception**: near-duplicate pairs (>90% cosine similarity) ARE surfaced as informational observations ("these submissions share identical passages"), never as verdicts. Verbatim duplication is factual information teachers need.
- **Automated penalty/grading** — teacher is ALWAYS the decision-maker
- **Student-facing scores** — students see engagement TRAJECTORY (growth), never suspicion levels

---

## Open questions

### Resolved

- ~~**Integration with other agent's work**~~: ✅ `gibberish_gate.py`, `citation_checker.py`, expanded `patterns.py` all wired in. Citation depth = engagement signal. Hallucinated citation detection available via async URL/DOI verification (informational only).

### Still open

1. **Canvas API reading list integration**: Canvas API fetches assignment descriptions (✅ built). Still needed: `GET /courses/:id/modules` for linked materials/reading titles. Named reference extraction from assignment description (TF-IDF + spaCy NER) is infrastructure-ready but not built. This would power the reading-vs-topic distinction in Mechanism 2.
2. **Student visibility design** (#INDIGENOUS_DATA_SOVEREIGNTY): Opt-in trajectory sharing. Student-private by default. What does the teacher see without opt-in — aggregate class data only? This is a design requirement, not optional.
3. **RunStore schema extensions**: ClassBaseline (Mechanism 1), StudentSnapshot (Mechanism 4) tables not built. TeacherCalibration partially covered by `teacher_profiles` + `prompt_calibration` tables in InsightsStore. Need migration plan.
4. **Diverse testing corpus**: Partnership for real classroom data (with consent). Synthetic samples are prerequisite but not substitute. IRB-equivalent process for K-12/college.
5. **Dash patterns in current AI**: User observation that current models use many dashes. Our n=4 corpus showed 0-3 — likely outdated. OpenRouter testing with current model versions needed.
6. **The privileged disengaged student**: System detects zero engagement across all dimensions — conversation: "I noticed your response doesn't connect to our class work." We accept sophisticated AI use may not be catchable; engagement framing still surfaces the disengagement.

### New questions (emerged from implementation)

7. **AIC-Insights signal unification**: AIC computes engagement signals (HPD → 5 dimensions); Insights QuickAnalyzer computes overlapping but distinct signals (TF-IDF, embedding clusters, VADER, keyword patterns). No unified per-submission signal vector feeds both systems. Cohort calibration (Mechanism 1) needs to decide: which system's signals are the baseline? Both? A merged superset?
8. **Hardcoded threshold configurability**: Multiple thresholds are hardcoded across the pipeline (assignment connection: 30%/10%, pairwise similarity: 0.90/0.85/0.70, disengagement: median×0.4, concern confidence: 0.7, theme timeout: 300s, concern sensitivity adjustment: ±0.1). These should be surfaced as configurable parameters — but where? Teacher profile? Course profile? Global settings? Per-mechanism?
9. **Prompt calibration table usage**: `InsightsStore.prompt_calibration` table exists (stores teacher corrections: original_coding → corrected_coding), but nothing reads from it. How should corrections feed back into future prompts? Direct few-shot examples? Weight adjustment? This is the bridge between Mechanism 3 (teacher feedback) and actual prompt improvement.
10. **Integrity flags in Insights UI**: Tier 1 flags (unicode, gibberish, smoking gun) are tracked in AIC results but NOT displayed in the Insights panel Student Work cards. They appear only in `grading_results_panel.py`. Should be surfaced as warning chips or banner alerts in Insights too.
11. **Concern sensitivity calibration basis**: TeacherProfileManager adjusts concern sensitivity by ±0.1 per teacher action (acknowledge/dismiss). This is ad-hoc — no theoretical basis or validation. Does 10 dismissals = zero sensitivity? Should there be a floor? How does this interact with the signal matrix pre-screening?
