# Learning Through Use — Adaptive Calibration System

> Supplement to `docs/engagement_reframe_spec.md` — replaces the Implementation Priorities, What We're Not Building, and Open Questions sections.

The DAIGT test corpus gives us formal competition essays from strong writers. It tells us nothing about normal classroom variation, ESL patterns, neurodivergent writing, first-gen patterns. The system must calibrate from actual classroom data. This document specifies the concrete mechanisms.

---

## Mechanism 1: Cohort calibration (build first — highest impact)

**Status: ❌ NOT BUILT** — This is the highest-impact remaining gap. All AIC thresholds are currently absolute, not class-relative. Infrastructure exists (WeightComposer for education-level defaults, AIC_MODE_WEIGHT_PRESETS for assignment-type priors) but no distribution computation or percentile-based thresholds.

**What exists that supports this**:
- `WeightComposer` (`src/modules/weight_composer.py`) — education-level defaults per institution type (high_school, community_college, four_year, university, online). Provides the `type_mean` source for cold-start priors.
- `AIC_MODE_WEIGHT_PRESETS` — per-mode (discussion, essay, lab, etc.) weight profiles. Provides assignment-type priors.
- `RunStore.get_cohort()` — returns flat student lists but no aggregated statistics.
- QuickAnalyzer already computes per-submission statistics (word count, sentiment, TF-IDF terms) that could feed distribution computation.
- AIC computes per-submission signal values (sentence_variance, starter_diversity, comma_density, avg_word_length, hp_confidence) that are the natural inputs for distribution tracking.

**What needs building**:
- ClassBaseline table in RunStore (schema below)
- Distribution computation after each run (mean, stdev, percentiles from AIC + QA signals)
- Percentile-based threshold replacement in AIC convergence channels
- Bayesian cold-start blending logic
- EMA baseline evolution across runs
- UI to show "relative to this class" context

---

After processing a class, compute per-signal distributions as the baseline for THAT class. Future analyses compare each student against THEIR CLASS, not against absolute thresholds or DAIGT baselines.

**What to compute per signal** (sentence variance, starter diversity, comma density, HP confidence, authenticity, etc.): mean, median, stdev, percentile boundaries (P10, P25, P75, P90), IQR for outlier detection.

**How percentiles translate to engagement signals**:
- Below class P10 → "Conversation opportunity" (engagement notably below classmates)
- Below class P25 → "Worth monitoring"
- P25-P75 → Typical for this class
- Above P75 → "Strong engagement"

This automatically adapts to the population. In a community college ESL class where average HP is 3%, a student with HP=1% is notable. In a university seminar where average HP is 25%, a student with HP=5% is notable. Same signal, different classroom.

**Cold start (first run, no prior data)**: Bayesian blending of education-level defaults (from WeightComposer) and assignment-type priors (from AIC_MODE_WEIGHT_PRESETS):
```
effective_baseline = (n × class_mean + prior_weight × type_mean) / (n + prior_weight)
where prior_weight = max(10, 25 - n)
```
A class of 5 students uses `prior_weight=20` (heavy reliance on priors); a class of 25 uses `prior_weight=10` (mostly observed data). As the system processes more classes of each type, assignment-type priors themselves improve.

**Baseline evolution**: Each new run updates via exponential moving average:
```
updated_mean = 0.3 × new_class_mean + 0.7 × previous_baseline_mean
```
Recent data weighted 30%, history 70%. Smooths noise while allowing drift. System tracks whether baseline shifts come from student growth, assignment type changes, or population changes.

**Storage** (RunStore extension):
```
ClassBaseline:
  run_id, course_id, assignment_mode, education_level, n_students
  signals: {signal_name: {mean, median, stdev, p10, p25, p75, p90, iqr}}
  assignment_type_prior_used: bool
  prior_weight_used: float
```

**Open design question**: Which signals go into the baseline? AIC computes one set (sentence_variance, starter_diversity, comma_density, avg_word_length, hp_confidence, authenticity). Insights QuickAnalyzer computes overlapping signals (TF-IDF, embedding clusters, sentiment). Should the ClassBaseline store AIC signals only (simpler, faster), Insights signals only (richer, requires LLM run), or a merged superset (most complete, most complex)?

---

## Mechanism 2: Assignment context awareness

**Status: ⚠️ PARTIALLY BUILT** — Foundation exists but structured extraction is missing.

**What exists**:
- `DataFetcher.fetch_assignment_info()` (`src/insights/data_fetcher.py:155-172`) — fetches assignment metadata from Canvas API (description, rubric)
- `AssignmentConnectionScore` model (`src/insights/models.py:214-235`) — measures vocabulary overlap between submission and assignment description via TF-IDF
- QuickAnalyzer computes `assignment_connection_observation` — surfaced in synthesis Call 4
- `citation_checker.py` distinguishes specific citations (author-year, URL, DOI, quoted title) from generic references ("the reading says...")
- spaCy `en_core_web_sm` is already a project dependency (used in QuickAnalyzer for NER on submissions)

**What needs building**:
- Named reference extraction FROM the assignment description (apply spaCy NER + TF-IDF to the assignment text itself, not just submissions)
- Engagement expectation matrix (what signal levels are expected for THIS assignment type)
- Reading list extraction from Canvas modules API (`GET /courses/:id/modules`)
- Comparison: did student cite assigned readings vs. just the topic?

---

Before analyzing submissions, analyze the ASSIGNMENT ITSELF to set engagement expectations.

**Assignment fingerprinting** (automatic, from Canvas API or teacher input):

1. **Named reference extraction**: Parse assignment description for author names, work titles, key concepts.
   - "After reading Chapter 3 of Crenshaw's *Mapping the Margins*..." → Crenshaw, Mapping the Margins, traffic intersection metaphor, single-axis frameworks

2. **Engagement type detection**: Does the prompt ask for personal reflection? Analysis? Summary?
   - "Share your personal reaction..." → personal voice expected
   - "Analyze the author's argument..." → source depth expected

3. **Specificity targets**: Named entities from the assignment become the "engagement vocabulary." Check whether submissions reference these specifically ("Crenshaw argues in *Mapping the Margins* that...") or only generically ("intersectionality shows how identities interact...").

**Why this targets READINGS, not the assignment prompt**: A student who feeds the assignment prompt into ChatGPT will produce text about intersectionality — the concept is in ChatGPT's training data. What they WON'T produce is specific references to the assigned READING — the specific arguments, examples, and framings that Crenshaw uses. The engagement check is: did the student engage with the READING, not just the TOPIC.

**Canvas API integration**:
- `GET /courses/:id/assignments/:id` → description, rubric
- `GET /courses/:id/modules` → linked materials, reading titles
- Extract reading titles, author names, key concepts from metadata
- No LLM needed — TF-IDF keyword extraction + named entity recognition
- Result: "This student referenced 3/5 named concepts from the assigned reading"

**Engagement expectation matrix** (generated per assignment):
```
Assignment: "Respond to Crenshaw's Mapping the Margins"
  Expected engagement:
    Source depth: HIGH (should reference specific arguments)
    Personal connection: MODERATE (asked for reaction)
    Course connection: HIGH (builds on class discussion)
  Named reference targets:
    - Crenshaw, Mapping the Margins, traffic intersection, single-axis
  Mode: discussion (auto-detected from prompt structure)
```

---

## Mechanism 3: Teacher feedback loop (granular, not binary)

**Status: ⚠️ PARTIALLY BUILT** — Profile persistence and concern sensitivity exist. Granular signal corrections, threshold adjustment, per-student annotations, and correction pattern recognition do not.

**What exists**:
- `TeacherProfileManager` (`src/insights/teacher_profile.py`) — records theme renames, theme splits/merges, concern actions, tag edits, custom concern patterns, custom strength patterns, disabled default patterns
- Concern sensitivity calibration: ±0.1 per teacher acknowledge/dismiss action (stored per concern text)
- `get_full_profile_fragment()` generates prompt injection from accumulated edits
- `InsightsStore.teacher_profiles` table persists profiles; `course_profile_templates` table enables reusable snapshots
- `InsightsStore.prompt_calibration` table exists (stores teacher corrections: original_coding → corrected_coding) but **nothing reads from it yet**
- Course profile dialog (GUI) for profile management with template fork/save

**What needs building**:
- Per-signal weight overrides (not just concern sensitivity — teacher should be able to say "productive_messiness doesn't apply to lab reports")
- Threshold adjustment mechanism (teacher-defined floor for conversation triggers, not fixed percentile)
- Per-student annotations alongside signal data ("this ESL student starts sentences with 'I' due to L1 transfer")
- Correction pattern recognition ("You've corrected authentic_voice 8 times for communal expression — adjust the weight?")
- Prompt calibration feedback loop (reading from prompt_calibration table to improve future prompts)
- Concern sensitivity calibration basis (±0.1 is ad-hoc; needs floor/ceiling and theoretical grounding)

---

Teachers provide corrections that teach the system about this specific educational context.

**Signal-level corrections**: Teacher sees "Course connection: Limited" but knows the student discussed the reading extensively in class. Teacher marks: "This student engages orally."
→ System adds per-student annotation. Future snapshots: "Note: This student has been marked as engaging through modalities this system doesn't fully capture."

**Threshold adjustment**: Teacher finds too many students flagged. Marks several as "this is normal for my class."
→ System shifts conversation threshold from P10 to teacher-defined floor for this class.

**Signal weight feedback**: Teacher notices productive_messiness over-weights for lab reports — they SHOULD be polished.
→ System stores per-class weight override: `productive_messiness_weight *= 0.5`.

**Student context annotations**: "This ESL student starts many sentences with 'I' due to L1 transfer — not a concern."
→ Per-student annotation stored alongside signal data. Signal computes normally; INTERPRETATION is contextualized: "Starter diversity: 0.65 (below class median; teacher note: L1 transfer pattern — not a concern)."

**Emergent pattern recognition**: System surfaces patterns in teacher corrections: "You've corrected authentic_voice assessments 8 times this semester for students expressing communal rather than individual voice — would you like to adjust how this signal is weighted for your classes?" The system learns from the teacher's VALUES, not just their corrections.

**Storage**:
```
TeacherCalibration:
  teacher_id, class_id
  threshold_floor: float
  weight_overrides: {signal_name: multiplier}
  student_annotations: {student_id: [{signal, note, date}]}
  correction_history: [{signal, original, teacher_correction, date}]
```

---

## Mechanism 4: Voice fingerprinting (longitudinal, per-student)

**Status: ❌ NOT BUILT** — Word count trajectory exists. Signal vector tracking, Mahalanobis distance, and drift detection do not.

**What exists**:
- `TrajectoryAnalyzer` (`src/insights/trajectory.py`) — cross-run analysis for course-level patterns
- `StudentArc` model (`src/insights/models.py:554-560`) — per-student weekly word counts, submission status, concern flags, trend (steady/improving/declining/irregular)
- `_compute_student_arcs()` in TrajectoryAnalyzer — computes per-student trajectory across runs
- `InsightsStore.insights_codings` table stores per-student per-run coding records (could be extended to store signal vectors)

**What needs building**:
- `StudentSnapshot` model — per-submission signal vector (sentence_variance, starter_diversity, comma_density, avg_word_length, hp_scores, authenticity, engagement_signals)
- Storage: signal vectors persisted per submission in InsightsStore (new table or column extension)
- Mahalanobis distance computation for voice consistency (after 3+ submissions)
- Growth tracking for engagement dimensions (not just word counts): is contextual_grounding increasing? is cognitive_struggle deepening?
- Drift alerts: signal vector shifts beyond 2σ from student's own baseline
- Student-visible engagement trajectory (opt-in, default student-private)

---

Across assignments, build each student's writing signature — for growth tracking and consistency comparison.

**Signal vector per submission**:
```
StudentSnapshot:
  student_id, assignment_id, timestamp
  signals: {sentence_variance, starter_diversity, comma_density,
            avg_word_length, hp_scores: {...}, authenticity, ...}
```

**Voice consistency** (after 3+ submissions): Compute student's typical signal range (mean ± 1σ per signal). New submissions compared against their OWN range using Mahalanobis distance (accounts for signal covariance — a student who always writes long complex sentences with lots of commas has correlated signals; deviating on BOTH is less surprising than deviating on just one).

Large distance = "This submission differs notably from this student's typical pattern." NOT "this student cheated." The teacher investigates.

**Growth tracking** (the most valuable teacher insight): Trend analysis across the semester:
- Is contextual_grounding increasing? (connecting more to course material)
- Is cognitive_struggle deepening? (wrestling with harder ideas)
- Is authentic_voice strengthening? (finding their voice)
- Is productive_messiness appearing? (taking more intellectual risks)

Surfaced as: "This student's engagement with course material has deepened over the last 4 assignments — contextual grounding and cognitive struggle are both trending up."

**Drift alerts**: Signal vector shifts beyond 2σ from student's own baseline → "This submission's pattern differs notably from [Student]'s previous work." The teacher decides what it means.

**Student visibility** (#INDIGENOUS_DATA_SOVEREIGNTY): Students can see their OWN engagement trajectory: "Here's how your engagement has evolved this semester." This transforms the system from surveillance to self-awareness. Opt-in sharing with teacher — student controls whether the teacher sees their trajectory. Default: student-private.

**Minimum history**: Voice profiles need 3+ submissions. Below that: "Building voice profile — need more submissions for comparison." Use cohort baselines only.

---

## Mechanism 5: Class culture modeling (emerges from 1-4)

**Status: ❌ NOT BUILT** — Depends on Mechanisms 1, 3, 4. Some foundation exists in class-level observations.

**What exists**:
- Class-level similarity stats (PairwiseSimilarityStats observation field)
- TrajectoryAnalyzer computes theme_evolution, engagement_trend, concern_trend, exhaustion_trend at class level
- Class-level themes in Insights output (what the class is engaging with)
- Teacher profile accumulates preferences over time (theme vocabulary, concern calibration)

**What needs building**:
- Mechanism 1 (cohort calibration) provides the "what engagement looks like in this class" baseline
- Mechanism 3 (teacher feedback) provides the "what the teacher values" signal
- Mechanism 4 (voice fingerprinting) provides the "what individual trajectories look like" data
- Synthesis of all three into a class culture model ("your class tends toward formal analytical engagement with strong source references")

---

Over multiple assignments and feedback cycles, the system builds a model of what "engagement" means in THIS class — not from configuration, but from observed patterns and teacher responses:

- Does this teacher value personal stories? (High authentic_voice baseline + teacher never corrects it down)
- Is this a discussion-heavy class? (High contextual_grounding expected)
- Does this class have strong collaborative norms? (High similarity is normal, teacher hasn't flagged it)

Surfaced as: "Based on 4 assignments, your class tends toward formal analytical engagement with strong source references."

---

## Mechanism 6: Predictive engagement (emerges from 4-5, after 5+ assignments)

**Status: ❌ NOT BUILT** — Depends on Mechanisms 1, 4, 5. No predictive modeling infrastructure exists.

**What exists**:
- StudentArc tracks historical trend (steady/improving/declining/irregular) but doesn't predict
- Assignment mode awareness exists (8 AIC modes) but not used for prediction

---

Expected engagement per student per assignment type, based on their trajectory + class norms:

"Based on [Student]'s trajectory and this assignment type, expected engagement is: Course connection [strong], Personal investment [moderate], Intellectual work [moderate-strong]."

Actual submission significantly below expected → "This submission is below what we'd expect from [Student] — particularly in [specific dimension]. Worth a check-in."

This is the most powerful signal — personalized, longitudinal, independent of AI detection.

---

## Testing corpus expansion

n=4 AI essays with text is too small for confident claims. Need:

1. **Broader AI corpus** (OpenRouter): 20+ essays across GPT-4o, Claude, Gemini, Llama, Mistral. Varying prompts (naive, roleplay, adversarial). Both discussion posts (200 words) AND longer essays (500-1000 words) to validate paragraph-level signals.

2. **Diverse human corpus**: ESL writing (various L1), first-gen, neurodivergent, dictated/speech-to-text, collaborative. Synthetic first; real classroom data with consent as gold standard.

3. **Validation protocol**: For each signal, compute effect size on expanded corpus AND differential impact by population.

---

## Implementation priorities — status as of 2026-03-22

### Phase A: Foundation + signals — ✅ COMPLETE (except corpus expansion)

1. ✅ Gradient sentence uniformity in `organizational_analyzer.py`
2. ⚠️ Unicode detection built; stripping/normalization not yet implemented
3. ✅ Sentence-starter diversity
4. ❌ Expanded AI test corpus via OpenRouter
5. ✅ Wire `gibberish_gate.py` and `citation_checker.py` into AIC pathway

### Phase B: Calibration infrastructure — ❌ NEXT PRIORITY

6. ❌ **Cohort calibration** — highest-impact remaining gap (Mechanism 1)
7. ⚠️ Assignment context extraction — vocabulary overlap built, named reference extraction not
8. ❌ Cold-start Bayesian priors

### Phase C: Engagement framing + population-level — ✅ MOSTLY COMPLETE

9. ✅ UI reframe (engagement chips, conversation opportunity, register)
10. ✅ Class-level similarity (pairwise cosine, class-level stats, ≥0.90 pairs with pedagogical framing)
11. ✅ Citation depth (specific vs generic in citation_checker.py, mapped to source_depth)

### Phase D: Teacher feedback + longitudinal — ⚠️ PARTIAL

12. ⚠️ Teacher feedback loop — profile persistence built; per-signal overrides, threshold adjustment, per-student annotations, correction patterns not built
13. ❌ Voice fingerprinting — word count trajectory only, not signal vectors
14. ⚠️ Growth tracking — class-level trends built, per-student engagement signal growth not tracked

### Phase E: Emergent intelligence — ❌ NOT STARTED

15. ❌ Class culture modeling (depends on B + D)
16. ❌ Predictive engagement (depends on D longitudinal data)
17. ❌ AI literacy coaching prompts

### Recommended build order for remaining work

1. **Mechanism 1: Cohort calibration** — unblocks everything else. ClassBaseline table + distribution computation + percentile thresholds replacing absolute ones.
2. **Mechanism 2 completion: Named reference extraction** — apply spaCy NER to assignment description. Low effort, high value for reading-vs-topic distinction.
3. **Mechanism 3 completion: Per-signal weight overrides + prompt calibration loop** — teacher should be able to adjust engagement signal weights per class/assignment type, and prompt corrections should feed back into future runs.
4. **Mechanism 4: StudentSnapshot + signal vectors** — store per-submission engagement signal vectors across runs. Enables growth tracking and drift detection.
5. **Mechanisms 5-6** — emerge from 1-4 when sufficient longitudinal data exists.

---

## What we're NOT building

- **Plagiarism checker** — Turnitin's job
- **Perplexity/burstiness** — requires running an LLM, marginal benefit given engagement framing
- **Individual-pair similarity flagging at moderate thresholds** — equity risks too high; moderate similarity stays class-level only. Near-duplicate pairs (>90% cosine) ARE surfaced as factual observation, never verdict.
- **Automated penalty/grading** — teacher is ALWAYS the decision-maker
- **Student-facing scores** — students see engagement TRAJECTORY (growth), never suspicion levels

---

## Open questions

### Resolved

- ~~**Integration with other agent's work**~~: ✅ All wired in. `gibberish_gate.py`, `citation_checker.py`, expanded `patterns.py` teacher-test detection. Citation depth = engagement signal.

### Still open

1. **Canvas API reading list**: Module/page content for reading metadata — needed for Mechanism 2 completion.
2. **Student visibility design** (#INDIGENOUS_DATA_SOVEREIGNTY): Opt-in trajectory sharing. Student-private by default. What does the teacher see without opt-in?
3. **RunStore schema**: ClassBaseline table needed for Mechanism 1. StudentSnapshot table needed for Mechanism 4. Migration from current schema. TeacherCalibration partially covered by InsightsStore.teacher_profiles + prompt_calibration tables — consolidate or keep separate?
4. **Diverse testing corpus**: Partnership for real classroom data (with consent). IRB-equivalent process for K-12/college.
5. **Privileged disengagement**: Conversation framing works. Accepted: sophisticated AI use may not be catchable; engagement framing still surfaces disengagement.
6. **Dash patterns in current AI**: OpenRouter testing with current model versions needed.

### New questions (emerged from implementation)

7. **Signal vector scope for Mechanism 1**: Which signals constitute the ClassBaseline? AIC signals only (faster, simpler) or AIC + Insights QA signals (richer, requires Insights run)?
8. **Prompt calibration feedback loop**: `prompt_calibration` table stores corrections but nothing reads from them. Design needed: few-shot injection? Weight adjustment? Profile fragment extension?
9. **Concern sensitivity floor**: ±0.1 per action has no floor/ceiling. After 10 dismissals, concern is effectively silenced. Is that the right behavior? Should wellbeing signals be protected from full suppression?
10. **Integrity flags in Insights UI**: Tier 1 flags (unicode, gibberish, smoking gun) tracked in AIC but not displayed in Insights panel Student Work cards. Should be surfaced there too.
