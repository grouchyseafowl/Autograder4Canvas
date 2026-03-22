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

| Signal | What it catches | Source |
|---|---|---|
| **Smoking gun** | Raw chatbot HTML/markdown paste artifacts | `_detect_raw_ai_artifacts()` |
| **Unicode manipulation** | Zero-width characters, homoglyph insertion | Preprocessing (to build) |
| **Teacher-test detection** | "Does anyone read these?" messages | `patterns.py` TEACHER_NOTE |
| **Incoherence gate** | Keyboard mash, Lorem ipsum, random characters | `analyze_text()` pre-check (to build) |

These work because they detect **gaming behavior** — active attempts to circumvent rather than engage. No ambiguity, no population sensitivity.

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

**Newly identified signals (promising, need validation with larger corpus):**

Testing identified three unmeasured signals with very large effect sizes (d > 1.8), though n=4 for AI means these are hypotheses, not confirmed:

| Signal | AI (n=4) | Human (n=295) | d | Stability basis | Bias risk |
|---|---|---|---|---|---|
| **Sentence-starter diversity** | 1.000 (all perfect — no repeated first words) | 0.759 mean (13.6% also perfect) | 2.13 | HIGH — transformer repetition penalties are architectural, not model-version-specific | LOW — humans across all populations repeat starters naturally |
| **Comma density** (per 100 words) | 5.69 | 2.80 | 1.85 | MODERATE — AI constructs complex sentences with subordinate clauses, but varies by prompt | MEDIUM — formal academic ESL writing may also have high comma density |
| **Average word length** | 5.13 chars | 4.28 chars | 2.17 | MODERATE — continuous version of "inflated vocab," but decreases with casual-style prompts | MEDIUM — correlates with education level and reading exposure |

Starter diversity has the strongest theoretical stability claim because it stems from transformer architecture (repetition penalties, attention mechanisms) rather than training data or prompt style. If validated on a larger corpus (20+ AI essays across models), it would be a strong convergence channel. Comma density and average word length serve as **corroboration signals** that can be downplayed in population settings where they risk false positives (e.g., ESL populations with naturally higher formal comma usage).

**Validation path**: Multiple approaches available:
- **Claude Code subagents** — can generate Anthropic model responses directly (no API key needed, fastest path for Claude-generated test essays)
- **OpenRouter API** (available in `GitHub/Reframe` project directory) — route prompts to multiple providers (GPT-4o, Gemini, Llama, Mistral). Preference for free tier where available.
- **Direct model access** — Gemini Pro and Claude Sonnet/Opus available directly.
- **Target**: 20+ essays across 5+ models, in both discussion (200 word) and essay (500-1000 word) formats, with naive/roleplay/adversarial prompt variants.

**Key finding**: Structural signals are **model-dependent for rhythm** (sentence uniformity) but potentially **model-stable for repetition avoidance** (starter diversity). ChatGPT tends rhythmic; Gemini Pro and Claude produce human-like rhythm but MAY still show the starter diversity and comma density patterns. Expanded testing is the next priority — need to confirm these patterns before building detectors around them.

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
| **Source depth** | Specific quotes, page references vs. generic "the reading says" | New detector (to build) + `citation_checker.py` | "Did this student engage with the actual readings?" |
| **Hedging presence** | Natural epistemic uncertainty in discussion context | New detector (to build, mode-sensitive) | "Is this student expressing genuine uncertainty?" |

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
| **Similarity clusters** | Multiple students saying the same thing the same way | QuickAnalyzer embeddings (to build pairwise) | "Several students submitted very similar responses — is the assignment eliciting diverse thinking?" |
| **Theme convergence** | Class gravitating toward specific ideas | Insights pipeline (existing) | "Here's what the class is most engaged with" |
| **Engagement outliers** | Students whose engagement pattern differs significantly from class | QuickAnalyzer clusters (existing) | "These students may need a conversation" |
| **Concern patterns** | Essentializing, tone-policing, structural misunderstandings | Insights pipeline (existing) | "Watch for these patterns in class discussion" |
| **Longitudinal voice** | How a student's engagement changes over time | To build (requires multiple assignments) | "This student's engagement shifted — here's how" |
| **Class trajectory** | How the class's engagement evolves across assignments — both quantitative (signal trends) AND qualitative (how the engagement changes, not just that it does) | To build; qualitative dimension can use 8B LLM (Ollama) for narrative description, with potential to scale to larger models | "The class started with surface-level engagement with intersectionality but by Assignment 4, students are connecting course concepts to their own experiences and citing specific passages" |

**Equity framing for similarity**: Similarity can indicate strong community, collaborative learning, or shared cultural knowledge (#INTERDEPENDENCE, #COMMUNITY_CULTURAL_WEALTH) — not only copying. Surface as class-level pattern ("this assignment had unusually high similarity"), NOT as individual student flags. The first question is always: "Is the assignment designed to produce diverse responses?"

**Divergence-from-teacher-framing signal**: A particularly valuable pattern is when multiple students write similar things that **diverge from how the teacher taught the concept**. AI provides a GENERAL answer (from training data); the teacher taught a DISCIPLINE-SPECIFIC or COURSE-SPECIFIC answer. When several students all frame a concept the same way — and that framing doesn't match the course's approach — this is a strong signal. Examples:
- Teacher taught Crenshaw's traffic intersection metaphor; students all describe intersectionality using a "matrix of oppression" framing (a different scholarly tradition the AI trained on)
- Teacher emphasized a specific lab methodology; students all describe a generic textbook procedure
- Multiple students make the same factual error that reflects a common AI hallucination rather than a common student misunderstanding

This signal is ambiguous by design: it COULD indicate AI use, or it COULD indicate students collaborating, or consulting the same outside source. The system surfaces the pattern; the teacher interprets. The key innovation is comparing student framing against the TEACHER'S framing — which requires assignment context awareness (Mechanism 2).

**Longitudinal signals serve both student AND class**: Per-student voice tracking shows individual growth and consistency. Class trajectory shows whether the group is deepening, stagnating, or diverging across assignments. Both require cross-assignment data storage (not yet built).

---

## System limits — what the engagement frame cannot see

The engagement frame is better than the detection frame, but it has its own blind spots. Naming these is essential (#FEMINIST_TECHNOSCIENCE — no view is neutral):

1. **Text-only visibility**: The system measures text-based engagement. Students who engage through oral contribution, visual work, physical practice, or collaborative activity outside the submission are invisible. The system should never be the SOLE measure of engagement — it's one input to the teacher's judgment. (#COMMUNITY_CULTURAL_WEALTH — oral traditions, embodied knowledge, relational learning are assets this system cannot measure.)

2. **Individual authorship assumption**: The HPD categories (authentic voice, personal investment, cognitive struggle) privilege individualistic expression. Community-oriented students may express engagement through collective reference ("our community believes"), relational language ("my grandmother taught me"), and cultural knowledge that the system may score lower on "personal voice" precisely because the voice is communal, not individual. This observation needs deeper analysis — the specific manifestations of communal voice vary significantly across cultural contexts (Indigenous knowledge sharing, Black church rhetorical traditions, Latinx familismo, Asian collectivist framing, etc.) and the system's ability to recognize each is untested. Cohort calibration partially addresses this (the system learns what engagement looks like in each specific class) but the HPD's pattern library may need expansion to recognize communal engagement markers alongside individual ones. (#INTERDEPENDENCE — this is an active design challenge, not a solved problem.)

3. **English-language analysis**: Every signal in the system operates on English text. Translanguaging, code-switching, and non-English expression are partially recognized (HPD has translanguaging markers) but the system's analytical power drops sharply outside monolingual English. This is a structural limit, not a bug to fix. (#LANGUAGE_JUSTICE)

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

Note: "Engagement Snapshot" — not "Profile." The word "snapshot" frames it as situational and temporal; "profile" implies a fixed characterization.

---

## What this means for AIC vs Insights

**AIC** (fast, no LLM required):
- Computes engagement signals from text analysis alone
- Provides per-student engagement profile
- Flags integrity signals (Tier 1)
- Notes structural indicators (Tier 2)
- Runs in seconds, works offline

**Insights pipeline** (deeper, requires LLM):
- Class-level themes, concerns, synthesis
- Nuanced engagement assessment (LLM-evaluated)
- Cross-student patterns
- Feedback generation
- Takes minutes-hours, needs Ollama or API

**Relationship**: AIC is the fast pre-screen; Insights is the deep analysis. They complement, don't duplicate. A teacher running AIC sees "this student may not be engaging deeply — here's a conversation starter." A teacher running Insights sees "here's what the whole class is thinking, where they're struggling, and which students need attention."

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

## Implementation priorities (revised)

### Phase A: Foundation + signals

1. Gradient sentence uniformity in `organizational_analyzer.py`
2. Unicode preprocessing (zero-width stripping, whitespace normalization)
3. Sentence-starter diversity (new signal, strongest theoretical stability)
4. Expanded AI test corpus via OpenRouter (`GitHub/Reframe` has the API; preference for free tier; also direct Gemini Pro/Claude access)
5. Wire `gibberish_gate.py` and `citation_checker.py` into AIC pathway

### Phase B: Calibration infrastructure

6. Cohort calibration (class-relative baselines in RunStore)
7. Assignment context extraction (named references from Canvas API — target readings, not prompts)
8. Cold-start Bayesian priors

### Phase C: Engagement framing + population-level

9. UI reframe (engagement snapshots, conversation starters, integrity flags separate)
10. Class-level similarity (pairwise cosine, surfaced as class pattern only)
11. Citation depth as engagement signal (specific vs generic references)
12. Reoriented signals (TTR as vocabulary range, AI transitions as register mismatch, etc. — credit presence, never penalize absence)

### Phase D: Teacher feedback + longitudinal

13. Teacher feedback loop (corrections, thresholds, annotations)
14. Voice fingerprinting (per-student signal vectors)
15. Growth tracking + drift detection

### Phase E: Emergent intelligence

16. Class culture modeling (emerges from B + D)
17. Predictive engagement (from D longitudinal data)
18. AI literacy coaching prompts

---

## What we're NOT building

- **Plagiarism checker** — Turnitin's job
- **Perplexity/burstiness** — requires running an LLM, marginal benefit given engagement framing
- **Individual-pair similarity flagging** — equity risks too high; class-level only
- **Automated penalty/grading** — teacher is ALWAYS the decision-maker
- **Student-facing scores** — students see engagement TRAJECTORY (growth), never suspicion levels

---

## Open questions

1. **Canvas API**: OAuth flow, scopes, offline caching. Can we pull module/page content for reading metadata, or just assignment descriptions?
2. **Student visibility design**: Opt-in trajectory sharing. Student-private by default. What does the teacher see without opt-in — aggregate class data only?
3. **RunStore schema**: ClassBaseline, TeacherCalibration, StudentSnapshot tables. Cross-run queries. Migration from current schema.
4. **Diverse testing corpus**: Partnership for real classroom data (with consent). Synthetic samples are prerequisite but not substitute. IRB-equivalent process for K-12/college.
5. **Integration with other agent's work**: `gibberish_gate.py`, `citation_checker.py`, expanded `patterns.py` teacher-test detection all wire into this framework. Citation depth = engagement signal. Hallucinated citations (404 URLs) = integrity signal.
6. **Dash patterns in current AI**: User observation that current models use many dashes. Our n=4 corpus showed 0-3 — likely outdated. OpenRouter testing with current model versions needed.
7. **The privileged disengaged student**: System detects zero engagement across all dimensions — conversation: "I noticed your response doesn't connect to our class work." We accept sophisticated AI use may not be catchable; engagement framing still surfaces the disengagement.
