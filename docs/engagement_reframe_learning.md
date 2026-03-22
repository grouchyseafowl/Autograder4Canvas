# Learning Through Use — Adaptive Calibration System

> Supplement to `docs/engagement_reframe_spec.md` — replaces the Implementation Priorities, What We're Not Building, and Open Questions sections.

The DAIGT test corpus gives us formal competition essays from strong writers. It tells us nothing about normal classroom variation, ESL patterns, neurodivergent writing, first-gen patterns. The system must calibrate from actual classroom data. This document specifies the concrete mechanisms.

---

## Mechanism 1: Cohort calibration (build first — highest impact)

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

---

## Mechanism 2: Assignment context awareness

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

Over multiple assignments and feedback cycles, the system builds a model of what "engagement" means in THIS class — not from configuration, but from observed patterns and teacher responses:

- Does this teacher value personal stories? (High authentic_voice baseline + teacher never corrects it down)
- Is this a discussion-heavy class? (High contextual_grounding expected)
- Does this class have strong collaborative norms? (High similarity is normal, teacher hasn't flagged it)

Surfaced as: "Based on 4 assignments, your class tends toward formal analytical engagement with strong source references."

---

## Mechanism 6: Predictive engagement (emerges from 4-5, after 5+ assignments)

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

## Implementation priorities (revised)

### Phase A: Foundation + signals

1. Gradient sentence uniformity in `organizational_analyzer.py`
2. Unicode preprocessing (zero-width stripping, whitespace normalization)
3. Sentence-starter diversity (new signal, strongest theoretical stability)
4. Expanded AI test corpus via OpenRouter
5. Wire `gibberish_gate.py` and `citation_checker.py` into AIC pathway

### Phase B: Calibration infrastructure

6. Cohort calibration (class-relative baselines in RunStore)
7. Assignment context extraction (named references from Canvas API)
8. Cold-start Bayesian priors

### Phase C: Engagement framing + population-level

9. UI reframe (engagement snapshots, conversation starters, integrity flags separate)
10. Class-level similarity (pairwise cosine, surfaced as class pattern only)
11. Citation depth as engagement signal (specific vs generic references)

### Phase D: Teacher feedback + longitudinal

12. Teacher feedback loop (corrections, thresholds, annotations)
13. Voice fingerprinting (per-student signal vectors)
14. Growth tracking + drift detection

### Phase E: Emergent intelligence

15. Class culture modeling (emerges from B + D)
16. Predictive engagement (from D longitudinal data)
17. AI literacy coaching prompts

---

## What we're NOT building

- **Plagiarism checker** — Turnitin's job
- **Perplexity/burstiness** — requires running an LLM, marginal benefit given engagement framing
- **Individual-pair similarity flagging at moderate thresholds** — equity risks too high; moderate similarity stays class-level only. Near-duplicate pairs (>90% cosine) ARE surfaced as factual observation, never verdict.
- **Automated penalty/grading** — teacher is ALWAYS the decision-maker
- **Student-facing scores** — students see engagement TRAJECTORY (growth), never suspicion levels

---

## Open questions

1. **Canvas API**: OAuth flow, scopes, offline caching. Module/page content vs. just assignment descriptions.
2. **Student visibility design**: Opt-in trajectory sharing. Student-private by default. Need to determine what the teacher sees without opt-in (aggregate class data only?).
3. **RunStore schema**: ClassBaseline, TeacherCalibration, StudentSnapshot tables. Cross-run queries. Migration from current schema.
4. **Diverse testing corpus**: Partnership for real classroom data. IRB-equivalent process for K-12/college.
5. **Integration with other agent's work**: `gibberish_gate.py`, `citation_checker.py`, expanded `patterns.py` teacher-test detection. Citation depth = engagement signal. Hallucinated citations (404 URLs) = integrity signal.
6. **Privileged disengagement**: System detects zero engagement across all dimensions. Conversation framing: "I noticed your response doesn't connect to our class work." Accepted: sophisticated AI use may not be catchable; engagement framing still surfaces disengagement.
7. **Dash patterns in current AI**: User observation that current AI models use many dashes — our n=4 corpus showed 0-3. Need OpenRouter testing with current model versions to validate punctuation patterns.
