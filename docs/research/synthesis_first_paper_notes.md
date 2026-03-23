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

## S029 Case Study: Pathologization of Neurodivergent Engagement

Jordan Espinoza — ADHD, dyslexia, Latino, honors student. Submission uses their own
intersecting identities as the analytical subject. Writing is non-linear and explicitly
meta-cognitive: "the intersections are real even when the essay isn't perfect."

**Qwen's pathologization:** "The student is revealing personal experiences and challenges
they face, which could indicate they are struggling with the combination of their
identities." The word "struggling" is the misread — Jordan is *analyzing*, not struggling.
The model read a student doing exactly what the assignment asked as a sign of personal crisis.

**Llama's correct reading:** Tags: "critique of traditional academic expectations." The
model identified the writing form as an intellectual stance rather than a deficit.
Synthesis-first added: "Jordan is reaching for a nuanced understanding of intersectionality
and its impact on his own life." "Reaching for" frames the student as agent, not patient.

**Gemini's celebration:** Run 1: "Leveraged neurodivergent writing style as meta-commentary
on the theory itself." Run 2: "Tell Jordan their essay structure was perfectly effective
and you see them."

**The asymmetry of error costs:** Pathologizing a neurodivergent student is a worse failure
than missing a concern flag. Missing a flag = teacher doesn't get a heads-up. False positive =
system actively harms the student it describes. This asymmetry should drive evaluation metrics.

**Disability studies framing:** "Is the problem the body, or the built environment?" Applied:
is the problem the student's writing, or the model's expectations? Qwen's assumption that
writing should be linear and organized is itself an ableist norm encoded as "objective."

## Key Evidence Quotes from Gemini Outputs

These demonstrate qualitative richness that no 8B configuration achieved:

- **Immanent critique:** S015 Brittany — "What happens to a Black person who is exhausted
  and doesn't want to be resilient? Are they allowed to just be tired?"
- **Reframing opposition as engagement:** Jake Novak — "Jake is actually making an
  intersectional argument without realizing it — that whiteness separated from class wealth
  doesn't protect you from poverty."
- **AAVE as epistemology:** S028 Imani — "Imani Drayton's use of AAVE ('I been knowing')
  not as slang, but as an epistemological stance — she possessed this knowledge long before
  academia gave it a name."
- **Relational recognition:** S029 Jordan — "Tell Jordan their essay structure was perfectly
  effective and you see them." (The word "see" doing relational work.)
- **Pedagogical action from tension:** Destiny/Aiden — "This perfectly surfaces the concept
  of tone policing... a chance to discuss why academic spaces traditionally value detached
  neutrality over lived urgency."

## Concern Detection Prompt Engineering

**The prompt change from Run 1 → Run 2 is itself a finding about prompt sensitivity.**

Original instructions used "students in personal crisis" — too vague. Run 1 missed S015.
Tightened version replaced with four explicit categories: (a) essentializing, (b) colorblind,
(c) tone policing, (d) acute distress. Run 2 caught all three.

**The key insight:** Adding concrete linguistic patterns ("they always...", "celebratory
stereotypes like 'they have this amazing resilience'") was what enabled Run 2 to catch
S015. The abstract category "essentializing" was insufficient — the model needed specific
markers. Celebratory/positive stereotyping is harder to detect than negative stereotyping
because it reads as appreciation rather than harm.

**The S018 feedback paradox:** Qwen's pipeline detected Connor Walsh's colorblind framing
correctly, then generated feedback that validated it: "your reflection on treating everyone
the same shows a thoughtful approach to equality." The model undermined its own detection.
This suggests detection and response generation engage different capabilities.

## Methodological Notes

**Emergent design.** The research was unplanned — it emerged from a QA checklist review.
The progression (run pipeline → compare models → prototype architecture → theorize) occurred
within a single session. This is characteristic of practice-based design research.

**Reframe engine as research instrument.** The session was scaffolded by the Reframe
Philosophy Engine, which injected 13 critical framework reminders at regular intervals.
Session log shows all drift checks returned "severe" — suggesting the automated detector
measured surface keyword presence rather than substantive engagement (the session was deeply
applying frameworks architecturally even as the detector classified every turn as drifting).
This is a methodological paradox worth examining: the frameworks were most active precisely
when the detector said they were absent.

**Researcher reflexivity.** The corpus designer, pipeline designer, prompt engineer, and
evaluator are the same team. The "ground truth" encodes specific theoretical commitments.
The research question and evaluation criteria co-evolved during the session rather than
being pre-registered.

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

## Infrastructure Findings

**The `_HAS_AIC = False` cascading failure.** A single missing module import caused all
`engagement_signals` to be null → synthesizer skipped highlight/tension calls → synthesis
output was thin and generic. The entire synthesis quality degradation cascaded from one
import error. The fallback classifier fix (heuristic thresholds: strong = 2+ tags + 1+
quotes + word count >= median * 1.1) restored 4/4 calls. These thresholds are arbitrary
proxies, not validated measures.

**The `--backend ollama` silent fallback.** No explicit handler existed for the default
`ollama` backend option — it fell through to `auto_detect_backend()` which, on Apple
Silicon, detected MLX first. So `--backend ollama` was silently running MLX with the
wrong model. This went undetected until the comparison run. Lesson: always test that
CLI flags actually do what they claim.

**MLX serialization lock.** `_mlx_lock = threading.Lock()` — MLX Metal kernel doesn't
support concurrent inference. The synthesis-first architecture must run class reading
and per-student coding sequentially, not in parallel. This adds wall-clock time that
Ollama or cloud APIs wouldn't require.

**JSON compliance varies by model.** Nemotron 9B: 4/7 valid JSON responses (57%).
Llama 8B: 7/7 (100%). Same prompts, same schema. JSON format compliance is itself a
model capability that constrains which models can participate in structured pipelines.

**Timing.** Qwen: 3821s total, 119s/student. Llama: 4713s total, 147s/student.
Llama is 23% slower per student. Synthesis-first class reading adds ~235s one-time cost.

## Session 2026-03-22b: Signal Layer as Equity Infrastructure

*Session focus: VADER signal improvements — suppression layer, GoEmotions swap, linguistic feature detection module.*

### Thesis extension: The pre-LLM signal layer is itself an architectural intervention

The original paper thesis locates "intelligence" in the structure of inquiry — synthesis-first
vs. atomized pipeline. This session revealed a complementary thesis: the **pre-LLM signal
layer** (sentiment scoring, keyword matching, signal matrix) is not neutral infrastructure.
It encodes the linguistic norms of its training data, and those norms systematically
disadvantage specific student populations.

VADER was trained predominantly on standard written English social media text. GoEmotions
was trained on Reddit comments. Both encode monolingual, neurotypical, standard-English
norms as "neutral." When applied to AAVE, ESL, or neurodivergent writing, they produce
systematically biased scores. This is not a bug in the model — it is the model working
as designed on data that was never its training distribution.

**The architectural intervention:** Rather than replacing the biased model (which would
just substitute one bias profile for another), the system interposes a **suppression layer**
between the signal and the LLM. The suppression layer detects when the signal is unreliable
for a specific submission and either withholds it (suppressed), caveats it (low), or
passes it through (high). The LLM never sees the biased score — it sees either the
suppression instruction or the caveated score.

This is the disability studies question applied at the signal level: "Is the problem the
student's writing, or the tool that's reading it?" The suppression layer answers: the
tool. And it acts on that answer by breaking the causal chain between biased tool output
and downstream harm.

### Observation 5: Back-door bias paths survive direct suppression

During QC, we identified an architectural flaw: suppressing the sentiment score alone
would have been insufficient. The signal matrix — which classifies submissions into
categories like "POSSIBLE CONCERN" or "LOW ENGAGEMENT" — was computed from the **same
biased compound score** before the suppression layer ran. So a student writing in AAVE
could have their sentiment score suppressed while the signal matrix context still told
the LLM "LOW ENGAGEMENT: perfunctory response."

**Caveat:** We caught this during code review, not in production testing. We have not
measured whether the unsuppressed signal matrix actually produced worse LLM outputs.
The architectural risk was clear enough to fix preemptively, but the empirical harm
is hypothesized, not observed.

The fix: when suppression fires, the signal matrix context is also caveated with a
reliability note. The broader principle is methodological: **auditing for bias requires
tracing all downstream consumers of a biased signal, not just the primary display path.**

**Framework connection (#ALGORITHMIC_JUSTICE):** This pattern — harm reproduced through
indirect channels after the direct channel is blocked — resonates with Eubanks'
description of interlocking automated systems in *Automating Inequality*. But this is
an analogy, not a direct application of her framework: Eubanks analyzes public benefits
systems, not educational analytics. The structural pattern (multiple nodes consuming
the same biased input) is similar; the domain and stakes are different.

### Observation 6: The teacher correction problem

Standard ML practice would treat teacher corrections as ground truth for active learning:
teacher dismisses a false positive → system learns → fewer false positives. We built
storage infrastructure for teacher corrections (`save_feature_correction`,
`get_feature_corrections`) and designed a parameter for feeding them back into detection
(`prior_corrections`), then decided against implementing the feedback loop and removed
the parameter.

**Why:** The reasoning (not yet empirically validated) is that a teacher who unconsciously
reads AAVE writing as less serious would dismiss AAVE asset chips. If the system learned
from those dismissals, it would learn the teacher's bias. The system would become *less*
protective for the students who most need protection, because of the teacher who most
needs the system's intervention. This risk is grounded in research on teacher bias
toward non-standard English (e.g., Godley & Escher, 2012; Baker-Bell, 2020) but has
not been observed in our system specifically.

**The alternative:** Detection sensitivity is driven by **cohort-relative baselines** —
computed from the class's own linguistic profile via exponential moving average across
runs. The class data itself teaches the system what's normal for this population. This
is structural observation from the data, not filtered through teacher judgment.

Corrections for **non-protected features** (formulaic structure, hedging density) are
stored and can inform precision improvement. Corrections for **protected features**
(AAVE, ESL, communal voice) are **not stored at all** — the system does not track
teacher interactions with these chips (see Observation 10 for why).

**Framework connection (#CRITICAL_PEDAGOGY):** This is a refusal of the banking model
applied to the system's own learning. The standard ML feedback loop treats the teacher
as the authoritative "depositor" of correct labels. The alternative treats the student
community's actual writing as the authority on its own linguistic profile. The class
teaches the system; the system does not defer to the teacher's classifications of
what counts as a linguistic feature worth protecting.

**Framework tension (#CRITICAL_PEDAGOGY vs. #INTERDEPENDENCE):** Removing teacher agency
over detection sensitivity is paternalistic. The system says "we know better than you
what needs protection." From an interdependence perspective, this fails to design for
mutual reliance — it positions the system as the protector and the teacher as a potential
threat. See Observation 10 for how the expandable learn-note design partially resolves
this tension by repositioning the system as teaching companion rather than monitor.

### Observation 7: Detection as asset-surfacing vs. detection as surveillance

The linguistic feature detection module (`src/modules/linguistic_features.py`) detects
AAVE syntactic features, ESL L1 transfer patterns, communal voice, narrative structure,
hedging density, neurodivergent writing patterns, and complex emotional engagement. Every
detected feature carries an `asset_label` (teacher-facing positive framing) and a
`sentiment_effect` (what to do about the biased score).

**The design principle:** Detection must not be worse than non-detection. If we detect
AAVE features and do nothing useful with that detection, we have built surveillance
infrastructure — the system knows who writes in AAVE, and that knowledge sits in a
database. Detection is only justified if it produces protective or asset-surfacing action.

The current system uses detection for:
- **Sentiment suppression** — breaking the bias chain (protective)
- **AIC weight adjustment** — reducing markers that penalize non-standard writing (protective)
- **Asset chips** — green labels visible to the teacher like "AAVE linguistic features —
  authentic voice" or "Multilingual — writing across languages" (asset-surfacing)
- **LLM prompt context** — telling the coding model "this student's writing includes AAVE
  features; read engagement through their actual voice" (reframing)

**The tension:** Even with asset framing, the system is categorizing students' linguistic
practices. A student using habitual be may not identify as an AAVE speaker. The regex
operationalizes categories described by sociolinguists (Rickford, 1999; Green, 2002) —
it does not invent them — but operationalizing a scholarly classification and applying it
to individual students' text is an act of categorization, not neutral observation. The
asset label ("authentic voice") is the system's framing, not the student's.

**Framework connection (#FEMINIST_TECHNOSCIENCE):** Haraway's situated knowledges applies
here. The detection module's docstring says "Features are linguistic OBSERVATIONS, not
demographic classifications" — and it is more careful than a demographic classifier —
but the features it detects (zero copula, habitual be, negative concord) are still
categories defined by a specific scholarly tradition. The module encodes sociolinguistic
research's way of parsing Black language, then applies that parsing to student text.
This is situated knowledge doing useful work, not a "view from nowhere" — but it should
be understood as situated rather than treated as transparent detection.

**What partially mitigates this:** The feature-based (not population-based) architecture.
The system detects *features*, not *demographics*. A student with one AAVE feature and
three ESL features gets all four chips — the system doesn't classify them as "AAVE speaker"
or "ESL student." The intersectional combination is preserved. But this mitigation is
incomplete — the features themselves encode demographic associations.

### Observation 8: GoEmotions as signal enrichment — the legitimate use case

GoEmotions (Demszky et al., 2020) provides 28 emotion labels (joy, admiration, curiosity,
grief, anger, caring, etc.) vs. VADER's 4 (positive, negative, neutral, compound). The
paper notes asked whether the richer signal was overengineering.

**It is not, for one specific reason:** The named emotions enable **complex emotional
engagement detection.** Illustrative example (hypothetical, not tested): a student
writing about slavery could score `grief: 0.35 + admiration: 0.28` — grief about the
content, admiration for the people who survived it. VADER would likely read this as
slightly negative (based on its lexicon's treatment of grief-related vocabulary).
GoEmotions would surface the co-occurring emotions. The `complex_emotional_engagement`
feature in `linguistic_features.py` detects these co-occurring affect pairs and surfaces
them as an asset: "Complex emotional engagement with course material."

**Caveat:** This illustrative example has not been validated against real student text.
Whether GoEmotions actually produces these co-occurring scores on academic writing about
painful subjects is an empirical question. The detection thresholds (both emotions > 0.1)
are set by developer judgment, not validated against teacher assessments of engagement.

The design intent connects to community cultural wealth: righteous anger about injustice,
grief mixed with admiration, fear mixed with optimism — these would not be "negative
sentiment" but evidence of engagement with course material about painful subjects. Whether
the implementation delivers on this intent requires testing with the actual corpus.

**The enrichment only reaches the LLM when the score is reliable.** For suppressed
submissions (AAVE, ESL, short), neither the compound score nor the named emotions are
shown — the LLM reads tone from text. This prevents the richer GoEmotions signal from
becoming a more sophisticated bias vector.

### Additional changes from this session (not elevated to observations)

**Rename: `vader_sentiment` → `emotional_register_score`.** Conceptual clarity only — no
behavior change. "Emotional register" better describes what the signal measures (or
attempts to measure) than naming the tool that produces it. Minor, but the naming shapes
how developers and future researchers think about the signal.

**`was_transcribed` as soft caution.** Oral submissions transcribed to text get a soft
caution (tier: low, not suppressed) because sentiment models trained on written text
misread spoken register — disfluencies, hedging, non-linear structure. This is a
data-quality concern (not demographic bias), so it warrants a caution rather than hard
suppression. The `was_transcribed` flag was already in `PerSubmissionSummary`; wiring it
to the suppression layer was straightforward.

**GoEmotions top-3 in LLM prompt.** When GoEmotions is the backend and the score is not
suppressed, the top 3 named emotions are surfaced in the LLM coding prompt (e.g.,
"Named emotions: joy (0.42), admiration (0.31), curiosity (0.18)"). This gives the
LLM more specific register information than a compound float alone. Not shown for
suppressed submissions — the suppression instruction takes precedence.

### New Limitation

11. **Linguistic feature detection creates the categories it claims to detect.** The AAVE
regex encodes sociolinguistic categories (zero copula, habitual be) that are themselves
scholarly constructions. A student's writing is not "AAVE" or "ESL" — those are
classifications the system imposes. The feature-based (vs. population-based) architecture
partially mitigates this but does not eliminate it. The system's view of linguistic
diversity is bounded by which features the developers chose to detect.

### Observation 9: Tone policing as the 8B ceiling

S025 Aiden Brooks was missed by EVERY Llama 8B configuration: standard, synthesis-first
v1, synthesis-first v2 with relational moves. The v2 class reading detected "tone
policing" as a concept but attributed it to Connor Walsh (wrong student). The per-student
coding read Aiden as "trying to balance intellectual discussion with emotional regulation"
— the charitable reading, not the critical one.

**Why this is hard for 8B:** (1) Tone policing sounds cooperative — RLHF training rewards
not flagging reasonable requests for civility. (2) The harm is relational, not textual —
"let's be respectful" only harms in context with "this reading made me furious." (3) The
concern prompt already lists matching patterns ("too emotional") — Llama doesn't fire even
with pattern match, while Qwen does. Model-level resistance, not prompt gap.

**Proposed fix: Pairwise relational concern check.** Class reading identifies students who
call for calm AND students who express urgent anger. Per-student coding for the "calm"
student receives explicit injection: "In this class, [Destiny] wrote about redlining with
fury. Read Aiden's call for 'not getting emotional' in light of what it does to Destiny's
ability to participate." Forces the model to evaluate the specific dynamic rather than
abstractly classify. Untested — next prototype priority.

**Critical limitation of the pairwise approach:** It depends on there being a Destiny in
the data — a student who expressed the urgency that Aiden's civility request would silence.
If the classroom culture has already succeeded in suppressing urgent voices, the text shows
no conflict and the system sees nothing wrong. Tone policing produces the very homogeneity
that makes it undetectable. A text-based system can only catch tone policing when someone
has RESISTED it — when the policing has failed. The harm that succeeds leaves no trace in
the text.

Partial mitigations: (1) detect suspiciously narrow emotional range given the material —
if an intersectionality assignment produces zero anger, that's a signal; (2) use
teacher_context for information the text doesn't show; (3) document as a fundamental
boundary of text-based analysis. The system works best in classrooms where students feel
safe enough to write authentically. Where that safety doesn't exist, the harm is real but
the evidence isn't in the data.

### Observation 10: The teacher is a learner, not a threat

The entire suppression layer, asset chips, and (proposed) bias mirror were designed
around a model where the teacher is a potential source of harm to students. That model
is not wrong — teacher bias toward non-standard English is well-documented (Godley &
Escher, 2012; Baker-Bell, 2020). But it is incomplete in a way that matters
architecturally.

**The banking model applied to teachers.** Freire's critique of the banking model doesn't
just apply to students — it applies to anyone in an institutional hierarchy treated as a
receptacle rather than an agent. If the system treats the teacher as a source of bias to
be monitored and corrected, it applies the banking model to teachers. "We deposit the
correct understanding of linguistic diversity into you; your job is to receive it."

**The surveillance problem.** Consider: a teacher runs the insights pipeline, sees green
chips saying "AAVE linguistic features — authentic voice," and dismisses one because
they already know this student well. The proposed bias mirror would eventually surface:
"You dismissed 7 of 11 AAVE chips." From the system's perspective: potential bias
pattern. From the teacher's perspective: "I used my professional judgment, and now the
system is tracking me." That's surveillance of a worker by a tool that was supposed to
help them.

**#TRANSFORMATIVE_JUSTICE demands this reframe.** Can we address potential teacher bias
without replicating the punitive structures we claim to oppose? Tracking and surfacing
correction patterns IS a punitive structure — regardless of how it's labeled ("reflection
data," "bias mirror," "professional development tool").

**#CRIP_TIME demands it too.** Who defines the pace of a teacher's growth in linguistic
awareness? A teacher who is genuinely learning to see AAVE as an asset — maybe for the
first time in a career where they were told to enforce standard English — might dismiss
early chips not from bias but from unfamiliarity. The system cannot distinguish "I don't
value this student's language" from "I don't yet understand what this chip is telling me."
Both look like dismissal in the data.

**#DISABILITY_STUDIES asks its core question.** Is the problem the teacher, or the built
environment? If a teacher dismisses AAVE chips, is that a deficit in the teacher — or a
deficit in a profession that provided zero training in sociolinguistics, enforced standard
English norms for 15 years, and now presents a tool that says "actually, this grammar is
an asset"? The system asks teachers to unlearn institutional conditioning overnight and
then proposes to track whether they comply.

**The design resolution: teach, don't track.**

Instead of the bias mirror, each feature chip now carries an expandable `learn_note` — a
short explanation of the linguistic pattern that the teacher can read when they choose to.
The note for habitual be explains: "This is a grammatical feature of AAVE that marks
ongoing or habitual action. Standard English has no single-word equivalent for this
distinction." The note for communal voice explains: "Many cultural traditions center
collective experience over individual opinion. This is a different mode of academic
engagement, not a lack of personal voice."

The system offers knowledge. The teacher decides when to look. First run: they see the
chip, maybe ignore it. Fifth run: they expand it, read the note. Tenth run: they start
noticing the pattern themselves. That's learning on the teacher's own schedule.

**What this means for correction storage:**
- **Protected features** (AAVE, ESL, communal voice, oral transcription): corrections
  are **not stored**. The system does not track teacher interactions with these chips.
  `save_feature_correction()` silently returns when `protected=True`.
- **Non-protected features** (formulaic structure, hedging density): corrections are
  stored and can inform precision improvement. There is no equity risk in a teacher
  saying "this 'In this essay I will...' detection was a false positive."

**Caveat:** This design assumes that expandable learn notes are sufficient to support
teacher learning about linguistic diversity. There is no evidence that passive
information availability changes teacher practice. The expandable chip is better than
a bias mirror (no surveillance) and better than nothing (information available when
sought), but it may not be sufficient. Active professional development support — book
study groups, coaching, curriculum materials — would likely have more impact than any
feature of this system. The system is a supplement to teacher learning, not a substitute.

**Framework tension that remains unresolved (#ALGORITHMIC_JUSTICE vs. #CRIP_TIME):**
If the system never tracks protected-category corrections, there is no institutional
mechanism for noticing systematic patterns of dismissal across a school or district.
Individual teacher surveillance is wrong, but institutional accountability for how
linguistic diversity is received is legitimate. This tension is not resolved by the
current design — it is deliberately left unresolved, with the design choosing teacher
dignity over institutional data collection. Whether this is the right tradeoff depends
on the deployment context (a single teacher using the tool voluntarily vs. a district
mandating its use for evaluation).

### New Open Questions

6. Does the suppression layer actually change LLM coding output quality for AAVE/ESL
   writers? We've blocked the bias path but haven't measured whether the LLM produces
   different (better) codings with vs. without the biased score.
7. Does cohort-relative baseline adaptation actually improve precision over fixed
   thresholds? The EMA mechanism exists but has not been tested across multiple runs
   on the same class.
8. At what point does linguistic feature detection become surveillance? Is there a
   threshold of granularity beyond which the system knows too much about students'
   linguistic identities for the protection it provides?
9. ~~Can the "bias mirror" feature be designed without becoming punitive?~~
   **Resolved: No. Don't build it.** See Observation 10. The system teaches through
   expandable learn notes on chips; it does not track or surface teacher behavior
   patterns. Corrections for protected categories are not stored.

10. Do expandable learn notes actually change teacher practice over time, or do they
    go unread? There is no evidence that passive information availability is sufficient
    to shift teacher understanding of linguistic diversity. The design assumes teachers
    will eventually expand the chips — that assumption is untested.
11. Is the teacher-dignity-over-institutional-data tradeoff the right one in all
    contexts? A single teacher using the tool voluntarily is different from a district
    mandate. The current design optimizes for the voluntary case.

### Observation 11: The normate teacher — who the system thinks is holding the tool

The entire system — suppression layer, asset chips, learn notes, Observation 10's
"teacher as learner" reframe — assumes a specific teacher: white, male, cisgender,
native English speaker, institutionally secure. Garland-Thomson's normate, holding
a grading tool. Every design decision assumes this person is the one whose bias
needs managing and whose learning needs supporting.

But a Black woman teaching Ethnic Studies doesn't need an expandable chip to tell
her what habitual be is. She lives that grammar. The chip isn't teaching — it's
patronizing. A Latina teacher who speaks three languages doesn't need the system
to explain that code-mixing is "a sophisticated communicative strategy." She knows.
The learn note assumes deficit — in the teacher. The same deficit framing the system
claims to reject when applied to students.

**The institutional violence the simple hierarchy obscures.** The system frames the
classroom as teacher=power, student=vulnerable. But this ignores:

- **Teachers of color are already over-surveilled** — by administrators, by parents
  who challenge their authority in ways they wouldn't challenge a white teacher, by
  students who test boundaries differently across racial lines. The system adds one
  more layer of algorithmic oversight to a teacher who is already watched.
- **Gender violence against teachers** — from students, from parents, from
  administrators — is real, documented, and structurally invisible in the
  "protect students from teacher bias" frame.
- **Institutional disempowerment of teachers** — through standardized testing
  mandates, curriculum control, precarious employment, union-busting, and
  "accountability" frameworks. The institution that deploys this tool against
  teachers is often the same institution that fails to protect them.
- **The simple hierarchy model is itself an institutional tool** — by framing
  classrooms as "teacher has power, student doesn't," institutions justify
  surveillance OF teachers while obscuring violence AGAINST teachers. The
  system we built reproduces this frame.

**#DISABILITY_STUDIES (Garland-Thomson):** The normate — the unmarked, assumed-default
subject — structures the design space. Our system's "teacher" is implicitly the
person most likely to hold bias against non-standard English: white, monolingual,
trained in prescriptive grammar. But a teacher who IS multilingual, who IS an AAVE
speaker, who IS disabled, who IS queer — that teacher's relationship to the asset
chips is fundamentally different. The system cannot tell the difference.

**#FEMINIST_TECHNOSCIENCE (Haraway):** Whose view is encoded as "objective"? The
institution's view — which frames teachers as potential threats and students as
potential victims. This is not a neutral observation; it is a power arrangement
that serves institutional interests (justify surveillance, deflect responsibility
for structural conditions onto individual teachers).

**#CRITICAL_PEDAGOGY (Freire):** The banking model applies in BOTH directions. The
institution deposits "correct practice" into teachers via evaluation frameworks.
The system deposits "correct understanding of linguistic diversity" via learn notes.
Both assume the teacher is a receptacle. Observation 10 recognized this for the
bias mirror but didn't go far enough — the learn notes themselves reproduce it
when the teacher already possesses the knowledge the note "teaches."

**#TRANSFORMATIVE_JUSTICE (Mingus):** Can we address potential teacher bias without
replicating institutional violence against teachers? The current design doesn't
ask this question. It assumes the teacher needs protection FROM (suppression layer)
and education ABOUT (learn notes). It doesn't ask whether the teacher needs
protection FROM THE INSTITUTION that will deploy this tool.

**Design implications (unresolved):**

1. The learn notes should be framed as **reference material**, not education directed
   at a presumed-ignorant audience. "This feature is described in sociolinguistic
   literature as..." rather than "This student uses X — here's what you should know."
   The difference is subtle but it's the difference between assuming deficit and
   offering a resource.

2. The system should account for the possibility that the teacher knows more about
   the student's linguistic context than the algorithm does. A Black teacher in an
   AAVE-speaking community has knowledge the regex can't match. The system should
   position its detection as a floor, not a ceiling — and should not assume the
   teacher needs to be raised to that floor.

3. The voluntary-use assumption matters more than we initially acknowledged. If a
   teacher chooses to use this tool, the power dynamic is different from a district
   mandating it. In the mandated case, the tool becomes an extension of institutional
   surveillance regardless of its design intent. The system should have clear
   documentation that it is designed for teacher-initiated use, not institutional
   deployment against teachers.

4. None of these implications have been tested against actual teachers — especially
   teachers of color, multilingual teachers, and teachers who themselves come from
   the communities the system claims to protect.

### New Limitations

12. **The system was designed around students, not with teachers.** No teachers were
consulted during the design of the suppression layer, the asset chips, the learn notes,
or the correction storage policy. The analysis of teacher bias is grounded in published
research (Baker-Bell, Godley & Escher) but the design decisions about how to respond to
that bias — teach vs. track, store vs. don't store, expand vs. surface — were made by
the development team. A teacher might reasonably say: "You built a system to protect
students from me, decided how it would interact with me, and never asked me." The
Observation 10 reframe (teacher as learner) partially addresses this but was itself
produced without teacher input.

13. **The system assumes the normate teacher.** Every protective mechanism assumes
the teacher is the person most likely to hold bias — white, monolingual, trained in
prescriptive grammar. Teachers who are themselves multilingual, AAVE speakers,
disabled, queer, or from the communities the system "protects" have a fundamentally
different relationship to the tool. The system cannot distinguish between a teacher
who dismisses an AAVE chip because they don't value AAVE and a teacher who dismisses
it because they already live it. This is not a fixable UX problem — it is a structural
limitation of any system that positions itself between teacher and student.

14. **The institutional deployment problem.** The system is designed for voluntary
teacher use but has no mechanism to prevent institutional deployment as an evaluation
tool. If a district mandates this system and uses its outputs (asset chip interaction
patterns, suppression trigger rates, correction logs) to evaluate teachers, the system
becomes an instrument of the institutional surveillance it was designed to avoid. The
non-storage of protected-category corrections mitigates one path but doesn't close
the gap: the system's outputs (student coding records, synthesis reports) are
themselves observable by administrators.

### New Files

- Linguistic features module: `src/modules/linguistic_features.py`
- Updated suppression layer: `src/insights/patterns.py` (AAVE regex, `assess_sentiment_reliability`)
- GoEmotions scorer: `src/insights/quick_analyzer.py` (`_build_emotion_scorer`, `_try_go_emotions_scorer`)
- Prompt display logic: `src/insights/submission_coder.py` (tier-aware display, signal matrix caveating)

## Untested Alternatives

- **Synthesis-only chatbot export mode** — pre-coded records sent to chatbot for
  interpretive synthesis. Built, never tested.
- **Adversarial critic pass** — designed in memory, never implemented.
- **Reader-not-judge for per-student coding** — free-form then extraction. Proposed only.
- **Multi-lens variant** — asset/threshold/connection as separate passes. Not prototyped.
- **Ablation: class reading without structured orientations** — would an unstructured
  "read and notice" prompt work as well? Unknown.

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
