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

During QC, we discovered that suppressing the sentiment score alone was insufficient.
The signal matrix — which classifies submissions into categories like "POSSIBLE CONCERN"
or "LOW ENGAGEMENT" — was computed from the **same biased compound score** before the
suppression layer ran. So a student writing in AAVE might have their sentiment score
suppressed, but the signal matrix context still told the LLM "LOW ENGAGEMENT: perfunctory
response."

This is a concrete example of how bias leaks through indirect channels even after the
direct channel is blocked. The fix: when suppression fires, the signal matrix context
is also caveated with a reliability note. But the broader finding is methodological:
**auditing for bias requires tracing all downstream consumers of a biased signal, not
just the primary display path.**

**Framework connection (#ALGORITHMIC_JUSTICE):** This is exactly what Virginia Eubanks
describes in *Automating Inequality* — the harm doesn't come from any single decision
point but from the system of interlocking automated judgments. Fixing one node (sentiment
display) while leaving another node (signal matrix) consuming the same biased input
reproduces the harm through a different path.

### Observation 6: The teacher correction problem

Standard ML practice would treat teacher corrections as ground truth for active learning:
teacher dismisses a false positive → system learns → fewer false positives. We built this
mechanism, then removed it.

**Why:** A teacher who unconsciously reads AAVE writing as less serious will dismiss AAVE
asset chips. If the system learns from those dismissals, it learns the teacher's bias. The
system becomes *less* protective for the students who most need protection, because of
the teacher who most needs the system's intervention. The sensitivity floor for protected
categories (AAVE, ESL, communal voice) would be eroded by the very biases the system
exists to counteract.

**The alternative:** Detection sensitivity is driven by **cohort-relative baselines** —
computed from the class's own linguistic profile via exponential moving average across
runs. The class data itself teaches the system what's normal for this population. This
is structural observation from the data, not filtered through teacher judgment.

Teacher corrections are still stored — for audit, institutional accountability, and a
future "bias mirror" feature that could show teachers their own correction patterns
relative to student linguistic profiles. But they do not feed back into detection.

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
threat. A more interdependent design might surface the teacher's correction patterns
back to them as reflection data rather than silently overriding their judgment. (The
"bias mirror" feature is designed for this but not yet built.)

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
creates the category it claims to detect — "AAVE features" is a linguistic classification
imposed on text, not a self-identification by the writer. The asset label ("authentic
voice") is the system's framing, not the student's.

**Framework connection (#FEMINIST_TECHNOSCIENCE):** Haraway's "view from nowhere" applies
here. The detection module claims to observe linguistic features objectively, but the
features it looks for (zero copula, habitual be, negative concord) are categories defined
by sociolinguistic research — they are themselves situated knowledge. The module encodes
a particular scholarly tradition's way of categorizing Black language, then applies that
categorization to student text. This is a situated view presented as detection.

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
engagement detection.** A student writing about slavery might score `grief: 0.35 +
admiration: 0.28` — grief about the content, admiration for the people who survived it.
VADER reads this as slightly negative. GoEmotions reads it as complex engagement. The
`complex_emotional_engagement` feature in `linguistic_features.py` detects these
co-occurring affect pairs and surfaces them as an asset: "Complex emotional engagement
with course material."

This is the community cultural wealth framework operationalized at the affect level.
Righteous anger about injustice, grief mixed with admiration, fear mixed with optimism —
these are not "negative sentiment." They are evidence of deep engagement with course
material that happens to be about painful subjects. The asset framing converts what
VADER reads as a concern signal into what it actually is: a student bringing their full
emotional intelligence to the material.

**The enrichment only reaches the LLM when the score is reliable.** For suppressed
submissions (AAVE, ESL, short), neither the compound score nor the named emotions are
shown — the LLM reads tone from text. This prevents the richer GoEmotions signal from
becoming a more sophisticated bias vector.

### New Limitation

11. **Linguistic feature detection creates the categories it claims to detect.** The AAVE
regex encodes sociolinguistic categories (zero copula, habitual be) that are themselves
scholarly constructions. A student's writing is not "AAVE" or "ESL" — those are
classifications the system imposes. The feature-based (vs. population-based) architecture
partially mitigates this but does not eliminate it. The system's view of linguistic
diversity is bounded by which features the developers chose to detect.

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
9. Can the "bias mirror" feature (showing teachers their own correction patterns
   relative to student linguistic profiles) be designed without itself becoming a
   punitive instrument?

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
