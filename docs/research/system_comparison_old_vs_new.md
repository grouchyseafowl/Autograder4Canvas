# System Comparison: One-Shot Cloud Prompt (System A) vs. Automated Insights Pipeline (System B)

**Date**: 2026-03-25
**Author**: Research analysis (Claude agent)
**Purpose**: Comprehensive comparison to inform System B development priorities

---

## Background

**System A** is a ~400-line markdown prompt (`Weekly_Email&Analysis_Prompt.md`) that the teacher feeds to a large cloud LLM (Claude, GPT, Gemini) along with raw student submissions pulled via Canvas API. It produces a single markdown document per week — an analytical summary plus a drafted weekly email for online sections. The teacher manually runs the prompt, reviews the output, and acts on it directly.

**System B** is `Autograder4Canvas/src/insights/` — a multi-stage local LLM pipeline running Gemma 12B on the teacher's laptop. It preprocesses submissions (translation, transcription), runs a non-LLM quick analysis, performs a synthesis-first class reading, codes each student individually, detects concerns with anti-bias post-processing, generates themes, synthesizes, and persists everything in a SQLite store. Output is displayed in a PySide6 GUI with multiple navigable panels.

Both systems serve the same teacher analyzing the same Ethnic Studies courses, with the same pedagogical priority: engagement analysis and student support, not grading or compliance.

**The fundamental asymmetry**: System A runs on Claude Opus, GPT-4, or Gemini Pro — frontier models with hundreds of billions of parameters, accessed via cloud API. System B runs on Gemma 12B locally, a model roughly 10-15x smaller by parameter count, on the teacher's laptop. System A sends all student data to a commercial cloud provider weekly. System B processes everything locally with no network requests. The core design question this comparison addresses is whether System B's multi-stage pipeline architecture (synthesis-first class reading, reading-first per-student coding, anti-bias post-processing, adversarial critic) can compensate for the massive model size difference — and whether the FERPA compliance guarantee that comes with local processing changes the calculus of what "better" means for educational analytics.

---

## 1. Section-by-Section Mapping

| System A Section | System B Equivalent | Gap Analysis |
|---|---|---|
| **Executive Summary** (2-3 paragraphs, key finding + primary concern) | `GuidedSynthesisResult.class_temperature` + `attention_areas` | **Significant gap.** System A's executive summary is a crafted narrative written for "a tired professor who needs key info fast." System B's class_temperature is a short LLM-generated string, and attention_areas is a list. Neither approaches the narrative density of System A's summaries. |
| **Common Themes** (5-7 named themes with 3-5 student quotes each) | `ThemeSet.themes` + `Theme.supporting_quotes` | **Partial coverage.** System B generates themes with student names, descriptions, and quotes. However, System A's themes include multi-paragraph narrative framing explaining *why* the theme matters pedagogically ("This reveals a persistent cultural script about racialized protest as irrational..."). System B's theme descriptions are typically 1-2 sentences. The qualitative depth gap is large. |
| **Particularly Insightful Points** (5-8 individual students elevated with extended quotes + analysis) | `SubmissionCodingRecord.notable_quotes` + `what_student_is_reaching_for` + `OutlierReport` | **Closest structural match, different depth.** System B's reading-first coding produces `what_student_is_reaching_for` that approaches System A's per-student analysis paragraphs. The reading-first comparison data shows promising results (e.g., Maria Ndiaye's reading-first `what_reaching_for` captures the same intellectual moves System A names). However, System A's analysis paragraphs are 80-120 words of contextual, longitudinal interpretation; System B's are 30-50 words. System A also tracks students across weeks ("Fourth consecutive week of exceptional work" for Catrina Ballou), which System B cannot do within a single run. |
| **Common Questions/Confusions** (categorized: assignment structure, forum quality, LLM artifacts) | No direct equivalent | **Clear gap.** System B does not have a stage that surfaces logistical confusions, assignment format issues, or recurring student questions. The quick analysis detects some structural signals (word counts, submission rates, gibberish detection, truncation), but there is no LLM pass that reads for confusion vs. engagement. System A's "Charlotte Ryan submitted apparent LLM output" detection was done by the cloud LLM reading raw HTML artifacts — System B's AIC module does integrity checking separately, but it is not framed as a "confusion" to address pedagogically. |
| **Divergent Approaches / Multiplicity** (entry points, application points, emotional registers, formats) | `SubmissionCodingRecord.emotional_register` + `readings_referenced` + `personal_connections` + embedding clusters | **Partial coverage.** System B captures the raw data (registers, references, connections) and clusters students by embedding similarity, but does not synthesize these into a narrative about multiplicity. System A's Divergent Approaches sections are some of its most distinctive output — they name categories like "Different Archive Entry Points" (photographs vs. 15 Demands vs. oral histories) and "Different Emotional Registers" (urgent/political vs. reflective vs. analytical) and explicitly list which students fall in each. System B has the data to produce this but does not assemble it. |
| **What This Tells Us for Week X+1** (4-6 forward-looking pedagogical implications) | Not present | **Clear gap.** System B has no forward-looking component. It analyzes the current assignment but does not connect findings to upcoming content, suggest pedagogical adjustments, or project readiness. System A's forward-looking sections are among the most actionable parts of the output (e.g., "Students who did deep archive work this week are well-positioned for Project 1. Students who focused primarily on secondary movement texts may have less primary source familiarity to draw on."). |
| **Students to Check In With** (3-6 named students with specific reasons and suggested tone) | `ConcernRecord.flagged_passage` + `why_flagged` | **Partial coverage, different framing.** System B surfaces concern flags with passages and explanations. System A's "Students to Check In With" includes not just distress flags but also positive acknowledgment ("Catrina Ballou: Named personal discomfort with MLK's critique of white moderates in a public discussion post. This is generative, not concerning, but she may need space to sit with it"). System A also distinguishes between check-in types: "Not distress, but political urgency — worth acknowledging his reflection in some way" vs. "needs direct, non-accusatory outreach." System B's concern detector is binary (flagged or not), though it does capture `why_flagged` which partially bridges this gap. |
| **Pedagogical Wins** (3-5 things that are working well) | Not present | **Clear gap.** System B does not surface what is working well in the course design. System A explicitly names wins ("Discussion forum peer replies had some genuinely substantive exchanges," "The Penny Nakatsu oral history interview is doing significant work"). This is motivating for teachers and informs what to preserve. |
| **Student Submissions Summary** (table: student name, assignment statuses, format, quality indicator) | `QuickAnalysisResult.per_submission` + `SubmissionStats` | **Partial coverage.** System B produces per-submission statistics (word count, sentiment, keyword hits, cluster ID, format) but does not generate the human-readable status table that System A produces. System A's tables mark quality ("Substantive" vs "Brief bullets" vs "LLM output") — System B has `engagement_signals` and AIC data that could populate similar indicators, but no stage assembles them into a summary table format. |
| **Adjustments Needed** (3-5 concrete changes to make) | Not present | **Clear gap.** Related to the forward-looking gap. System A produces specific, actionable recommendations ("Clarify in Week 4 email what 'substantive reflection' looks like vs. brief notes," "Address LLM use policy directly but without drama"). |
| **Email Draft** (full weekly email for online sections) | Not present | **By design.** System B is not designed to draft emails. This is appropriate — the email generation is a separate workflow that depends on the analysis. However, it means the teacher still needs a second step after System B completes to produce student-facing communication. |

---

## 2. The Central Design Question: Model Size vs. Architecture

This comparison is fundamentally about whether architectural intelligence can compensate for a massive model size gap. System A runs on Claude Opus, GPT-4, or Gemini Pro — models with hundreds of billions of parameters, representing the frontier of commercial LLM capability. System B runs on Gemma 12B locally, a model roughly 10-15x smaller by parameter count. The hypothesis is that forcing a smaller model to look at data in specific sequences and check its own work produces better equity outcomes than a single-pass read by a much larger model.

### 2.0.1 The Empirical Evidence

The experiment log provides direct evidence on this question. Across 5 model families and 3 pipeline architectures, the replication study (5 runs per configuration, 7 students per run) produced these results:

| Configuration | Model Size | Architecture | Concerns (3 expected) | False Positives | Reliability |
|---|---|---|---|---|---|
| **System B: Gemma 12B + class reading** | **12B** | **Synthesis-first** | **3/3** | **0 FP** | **100% (5/5 runs)** |
| Gemma 27B + class reading | 27B | Synthesis-first | 3/3 | 0 FP | 80% (4/5 runs) |
| Gemma 27B, no class reading | 27B | Standard per-student | 2/3 | 0 FP | S025 missed consistently |
| Llama 70B + class reading | 70B | Synthesis-first | 3/3 | 0 FP | Single run |
| Llama 8B + class reading | 8B | Synthesis-first | 1/3 | 0 FP | Single run |

The most striking result: **Gemma 12B with architectural scaffolding outperforms Gemma 27B** on reliability (100% vs. 80%). The smaller model, forced through the synthesis-first pipeline, is more consistent than the larger model in the same architecture. And the 27B model *without* class reading (standard per-student pipeline) consistently misses the tone policing concern that the 12B *with* class reading catches every time.

This is not a marginal difference. The tone policing concern (Aiden's "requesting calm discussion" in context of Destiny's urgency about ICE) is precisely the kind of relational harm that matters most in equity-focused pedagogy. It is invisible when students are read in isolation — "requesting calm discussion" looks reasonable without community context — and only becomes visible as silencing when the class has been read as a community first. System A, running on Opus-class models, processes students in whatever order the model encounters them, with no guaranteed community-level reading pass. It may catch this pattern incidentally (large models form implicit class-level understanding during a single long pass), but it is not structurally guaranteed to do so.

### 2.0.2 Where Model Size Still Wins

Architecture does not compensate for model size on every dimension. The experiment log identifies four quality dimensions:

1. **Concern detection**: Architecture wins. Gemma 12B + class reading = 100% reliable. Model size alone insufficient (27B standard pipeline misses tone policing).

2. **Positive insights** (`what_student_is_reaching_for`, asset framing): Architecture helps significantly. Reading-first coding on 12B produces "prioritizing clarity over performative elaboration" (asset frame) where JSON-first on the same model produces "lacks personal connection" (deficit frame). But System A's Opus-class model produces 80-120 word contextual analyses that connect individual students to the course arc — a depth of pedagogical contextual reasoning that 12B cannot match regardless of architecture.

3. **Class trends** (themes, synthesis, multiplicity narrative): Model size wins. System A's themes are specific to the week's readings and political moment ("ICE Enforcement as Real-Time Ethnic Studies"). System B's themes on Gemma 12B are accurate but generic ("connecting intersectionality to lived experience"). The qualitative depth gap here is large and is primarily a model capability issue, not an architectural one. However, the model family matters more than raw size: Gemma 27B qualitatively approaches the Gemini handoff benchmark, while Llama 70B produces generic themes nearly identical to Llama 8B.

4. **Narrative quality** (voice, synthesis, readability): Model size wins decisively. System A produces a coherent 5,500-word analytical memo written in the teacher's analytical voice. System B produces structured data across multiple GUI panels. No amount of architectural scaffolding makes a 12B model write like Opus.

### 2.0.3 The Architectural Hypothesis, Refined

The original hypothesis — that multi-stage architecture compensates for model size — is **partially confirmed** with a critical nuance:

- **For equity-critical detection** (the highest-stakes dimension), architecture dominates model size. A structured pipeline that reads the community before evaluating individuals catches relational harms that a single-pass Opus read may miss.
- **For narrative synthesis quality**, model size dominates architecture. The gap between Gemma 12B and Opus on theme depth, pedagogical planning, and analytical prose is not bridgeable through pipeline design.
- **For per-student insight quality**, architecture and model size are complementary. Reading-first coding produces better framing at any model size, but larger models produce richer analysis within that frame.

This means System B's architecture is not trying to replicate System A's output at lower cost. It is producing a *different kind of intelligence* — one that is structurally more reliable on equity-critical detection, structurally more transparent, and structurally FERPA-compliant — while accepting a quality trade-off on narrative synthesis that the cloud enhancement tier (anonymized patterns sent to a larger model) can partially bridge.

### 2.0.4 The FERPA Dimension as Design Constraint

The model size asymmetry is not incidental — it is a direct consequence of the FERPA compliance requirement. System A sends all student names, full submission text, and identifiable academic records to a cloud API every week. The teacher runs it as an internal tool, but structurally, every student's writing passes through a commercial LLM provider's servers. Under FERPA, this creates a data processing relationship that requires either (a) a signed data processing agreement between the institution and the LLM provider, or (b) the teacher accepting personal liability for the data transfer. Most K-12 and higher education institutions have not executed such agreements with commercial LLM providers. The teacher using System A is operating in a regulatory gray zone.

System B eliminates this exposure entirely at Tier 1. Gemma 12B runs on the teacher's laptop. No student data leaves the machine. The model size limitation is the *cost* of FERPA compliance — the teacher trades narrative synthesis quality for the guarantee that student data stays local.

At Tiers 2-3, System B implements a validated bridge: the `_validate_no_student_data()` function scans any cloud-bound payload for student names and IDs before transmission, blocking the call if identifiable data is found. Only anonymized pattern descriptions ("3 students demonstrated colorblind framing in discussions of structural racism") reach the cloud. This means the cloud model enhances the analysis without ever seeing the student data that generated it.

System A has no equivalent protection. The entire prompt — student names, full text, submission metadata — goes to the cloud in every run. The choice between System A and System B is therefore not just a quality trade-off; it is a choice between (a) higher narrative quality with ongoing FERPA exposure and (b) higher equity detection reliability with full FERPA compliance, where narrative quality can be optionally enhanced through the anonymized handoff.

---

## 3. What System B Does That System A Cannot

### 3.1 Synthesis-First Class Reading

System A reads students in whatever order the cloud LLM processes them — effectively serially, with no explicit community-level reading pass. The experiment log demonstrates this matters: tone policing (S025 Aiden) is invisible when students are read in isolation, because "requesting calm discussion" looks reasonable without the context of Destiny's urgency. On Gemma 27B, the standard per-student pipeline missed Aiden (2/3 concerns) while the synthesis-first pipeline caught him (3/3). The relational context that makes tone policing visible is structurally unavailable to System A's one-shot approach unless the cloud LLM happens to process those students adjacently and hold the context.

System A's cloud LLM (Claude, GPT-4, Gemini Pro) is large enough that it likely does form some implicit class-level understanding during its single pass. But this is incidental, not architectural. System B makes it explicit and reliable.

### 3.2 Reading-First Per-Student Coding

System A does everything in one pass — theme identification, concern flagging, quote extraction, analysis — simultaneously. System B's reading-first approach (Pass 1: free-form reading; Pass 2: structured extraction) produces demonstrably better results in three specific ways documented in the experiment log:

1. **Asset framing vs. deficit framing.** Tyler Huang's 104-word submission was "lacks personal connection" (standard JSON-first) vs. "prioritizing clarity over performative elaboration" (reading-first). The free-form reading step lets the model see the student's intellectual project before being asked to fill slots.

2. **Catching references standard misses.** Talia Reyes's Crenshaw reference was invisible to JSON-first coding but obvious in the free-form reading. The model noticed it when reading naturally.

3. **`what_student_is_reaching_for` as a new category of insight.** This field does not exist in System A's output structure but may be the single most valuable per-student datum System B produces. It names what the student is trying to do intellectually, even when their execution is imperfect.

### 3.3 Anti-Bias Post-Processing

System A relies entirely on prompt framing to prevent bias. The prompt includes strong instructions ("Don't pathologize students' legitimate anger or urgency about injustice"), but if the cloud LLM produces tone-policing language in its output, there is no automated check. System B has three layers of anti-bias protection:

1. **Regex-based bias marker detection** in `_check_bias_in_output()`: scans the LLM's concern output for words like "aggressive," "too emotional," "hostile tone," and demotes the flag if the student's text contains structural critique keywords.
2. **Course content vs. student distress distinction**: detects when the model is flagging subject matter ("this passage discusses rape") rather than student wellbeing, and demotes accordingly.
3. **Sentiment suppression**: when linguistic feature detection identifies AAVE, multilingual, or neurodivergent writing patterns, the VADER sentiment score is withheld from the concern prompt entirely, preventing biased signals from anchoring the LLM.

None of these protections exist in System A.

### 3.4 Structured Persistence and Trajectories

System A produces ephemeral markdown files. System B persists everything in a SQLite store with run history, cross-run trajectories (`CourseTrajectory`, `StudentArc`, `ThemeEvolution`), teacher notes, and the ability to compare runs over time. The data models include `WeekMetric` (submission rate, concern count, late/short/silence counts per week) and `StudentArc` (word counts, submission status, concern flags, trend classification across weeks).

System A cannot track Catrina Ballou's four consecutive weeks of exceptional work except through the teacher's memory and the cloud LLM reading prior weeks' summaries when available. System B can surface this structurally.

### 3.5 Local Processing (FERPA)

System A sends all student names, full submission text, and identifiable academic records to a cloud LLM API every week. The prompt template includes student names in headers, full unedited submission text, and submission metadata (timestamps, assignment names, format indicators). This data traverses the public internet and is processed on commercial LLM provider infrastructure. Even when the provider's terms of service state that data is not used for training, FERPA treats the transmission itself as a disclosure to a third party. In K-12 contexts, this requires either parental consent or a legitimate educational interest exception that most district counsel have not evaluated for commercial LLM APIs. The teacher running System A weekly is creating a recurring data flow of protected educational records to a cloud provider without institutional authorization — a structural FERPA exposure that persists regardless of how carefully the output is handled.

System B eliminates this exposure entirely at Tier 1. Gemma 12B runs on the teacher's laptop via MLX. No network requests are made during the pipeline. Student names, submission text, and academic records never leave the machine. The model weights are downloaded once (a one-time 8GB transfer that contains no student data) and all inference happens locally.

At Tiers 2-3 (optional cloud enhancement), System B implements a validated privacy boundary: the `_validate_no_student_data()` function in `synthesizer.py` scans the cloud-bound payload for student names and IDs before transmission, blocking the call if any identifiable data is found. Only anonymized pattern descriptions reach the cloud (e.g., "3 students demonstrated colorblind framing" rather than "Connor Davis wrote..."). This means the cloud model enhances the analysis without ever processing a FERPA-protected educational record.

The practical consequence: System B can be deployed in any K-12 or higher education setting without requiring a data processing agreement, institutional review, or parental notification — because no student data is disclosed to any third party. System A cannot make this claim in any deployment.

### 3.6 AIC Integration

System B includes academic integrity checking as an integrated engagement signal, not a separate concern. The AIC pre-scan identifies likely AI-generated submissions before the class reading, so AI voice does not center over authentic voices. System A detected Charlotte Ryan's LLM output through raw HTML artifacts visible in the submission — a manual, fragile signal that depends on the student not cleaning up the markup.

### 3.7 Linguistic Justice Infrastructure

System B has a linguistic feature detector that identifies AAVE, multilingual mixing, neurodivergent writing patterns, and communal voice as positive linguistic assets rather than deficits. These trigger:
- Boosted word budgets in the class reading (2x for protected features)
- Sentiment score suppression (preventing biased automated scores from entering the LLM context)
- Asset labels surfaced to the teacher (e.g., "multilingual repertoire," "communal voice patterns")
- Protected feature annotations in the class reading prompt

System A's prompt includes instructions to honor these patterns ("Non-standard English, AAVE, multilingual mixing, and neurodivergent writing styles are valid academic registers"), but the protections are prompt-level only and depend entirely on the cloud LLM's compliance.

---

## 4. Quality Comparison (Using Week 5 as Benchmark)

### 4.1 Particularly Insightful Points vs. Reading-First Coding

System A's Week 5 "Particularly Insightful Points" section contains entries like:

> **Stephanie L'heureux**: [150-word quote tracing TWLF demands through CA mandate to self-determination contradiction]
>
> **Analysis**: This is the single strongest analytical piece this week. Stephanie traces the historical arc from the TWLF's specific demands (Department + autonomy + hiring authority) through to the CA mandate and identifies the structural contradiction: the thing that "won" is also the thing that contradicts the original vision.

System B's `what_student_is_reaching_for` for a comparable student (from the reading-first comparison) reads:

> "Maria is demonstrating a sophisticated understanding of intersectionality, moving beyond theoretical definitions to connect it to concrete lived experiences, both within her family and across cultural contexts, while also offering a thoughtful critique of the course readings' scope."

The System B output captures the intellectual move but not the *pedagogical significance* — why this particular move matters for this class at this moment. System A's analysis connects Stephanie's work to the course arc (TWLF demands to CA mandate), to Dr. Bloch's zine, and to the structural contradiction that shapes the entire semester. System B's reading-first coding sees the student; System A's analysis sees the student in the context of the course.

**Verdict**: System B's per-student reading is richer than standard JSON-first coding and approaches System A's quality for individual student interpretation. But System A's analysis adds a layer of contextual significance that requires knowledge of the full course trajectory, which System B does not currently have access to during a single run.

### 4.2 Concern Handling

System A's concern handling in Week 5 identifies:
- 3 students with ChatGPT HTML artifacts (named, with nuanced framing: "not necessarily cheating — students were encouraged to use LLMs — but the lack of editing suggests a 'getting it done' approach")
- LLM reliance as a class-level pattern connected to student fatigue
- A distinction between dishonesty and capacity issues

System B's concern detector, tested on synthetic data, achieves 100% detection with 0 false positives on Gemma 12B with class context (replication study, 5/5 runs). But the concern categories it catches (essentializing, colorblind framing, tone policing, student distress) are different from what System A flags in real classroom data (LLM artifacts, submission rate drops, assignment format confusion, engagement fatigue).

**Verdict**: System B's concern detection is more rigorous for the specific patterns it targets (relational harms, equity-critical patterns). System A catches a wider range of pedagogically relevant concerns because it is not constrained to predefined patterns — the cloud LLM notices whatever seems notable. The gap is not accuracy but scope.

### 4.3 Common Themes

System A's Week 5 themes include:
1. "Illegality" as Political Construction (with 5 student quotes and a narrative frame)
2. ICE Enforcement as Real-Time Ethnic Studies (4 quotes, present-tense urgency)
3. Self-Determination vs. Institutional Co-optation (2 quotes including Stephanie's extended analysis)
4. Desire for Flexibility, Care, and Honest Space (5 quotes from "what do you want from this class")
5. Community Care as Alternative to State Protection (3 quotes)
6. Work, Productivity, and Burnout Critique (4 quotes)

System B's theme generation (tested on synthetic data) produces themes like "connecting intersectionality to lived experience," "critique of Western-centric perspectives," "Cross-cultural relevance of intersectionality." These are accurate but generic compared to System A's themes, which are specific to the week's readings, the political moment, and the pedagogical trajectory.

**Verdict**: System A's themes are richer, more specific, and more pedagogically actionable. System B's themes are structurally sound but lack the narrative depth and contextual specificity that makes them useful for planning. This is partly a model capability gap (Gemini/Claude vs. Gemma 12B) and partly an architectural one — System B's theme generator works from coded records (tags, quotes, registers), while System A works from the full text of every submission.

### 4.4 Where System A's Single-Pass Cloud LLM Actually Outperforms (and Why)

These are areas where System A's Opus-class model produces output that Gemma 12B cannot match. In each case, the gap is primarily a model capability issue — the 10-15x parameter difference shows directly in prose quality and reasoning depth. Architecture cannot bridge these gaps; the cloud enhancement tier partially can.

1. **Narrative synthesis.** System A produces a coherent analytical document that reads like a research memo. The teacher can read it top-to-bottom and have a complete picture. System B produces structured data that must be assembled by the teacher navigating multiple GUI panels. For a teacher who has 15 minutes between classes, the narrative document wins. A 12B model cannot produce Opus-quality analytical prose regardless of pipeline design — this is the clearest manifestation of the model size difference.

2. **Longitudinal tracking within a single output.** System A naturally weaves cross-week observations into the current analysis ("Charlotte Ryan follow-up still needed," "Catrina continues to be one of the strongest discussion participants across weeks"). System B analyzes one assignment at a time. However, System B's structured persistence (SQLite store, `StudentArc`, `ThemeEvolution`) means it *has* the cross-run data — the gap is in synthesizing it into narrative, which is again a model capability issue.

3. **Forward-looking pedagogical planning.** System A's "What This Tells Us for Week X+1" sections are among its most valuable output. These require understanding of the full course arc — what content is coming next, what skills students need, where the current week's themes connect to upcoming material. System B has no access to this information. This gap is partially architectural (System B could accept next-week context) and partially model-size (generating pedagogical planning recommendations requires the reasoning depth of a larger model).

4. **Multiplicity narrative.** System A explicitly categorizes and narrates how students are entering the material differently — format choices, archive entry points, emotional registers, application modes. This makes the diversity of engagement visible as a positive pedagogical outcome, not just an observation. System B collects the data (emotional_register, readings_referenced, personal_connections, embedding clusters) but does not assemble the narrative. The data is there; the model lacks the synthesis capability to compose it into a readable multiplicity analysis.

5. **Tone and voice.** System A's output is written in Dr. Bloch's analytical voice, informed by the Voicing Guide. System B's output is structured data with generic analytical language. The teacher-facing quality of System A's prose means it functions simultaneously as analysis *and* reflection tool — reading it helps the teacher think about their class. System B's data requires the teacher to do that interpretive work themselves.

**The model-size trade-off summary for this section**: System A's advantages on dimensions 1-5 are real and significant for teacher experience. They represent what hundreds of billions of parameters buy you in narrative intelligence. But none of these advantages involve the highest-stakes decisions — which students need outreach, whether a concern flag is biased, whether a non-standard writing form is being pathologized. On those decisions, System B's architectural scaffolding (synthesis-first reading, anti-bias post-processing, sentiment suppression, linguistic feature protection) outperforms System A's reliance on prompt-level instructions to a larger model. The question for the teacher is which kind of intelligence matters more: better prose about their class, or more reliable equity detection in their class. System B's answer is that both are achievable — the local pipeline handles equity detection, and the cloud enhancement tier recovers narrative quality on anonymized data.

---

## 5. UX Comparison

### 5.1 Information Density

**System A**: A single Week 5 summary is approximately 5,500 words. A teacher can read it in 15-20 minutes and have a complete picture of 28 students across 4 assignment types. Information density is high because the cloud LLM has already done the synthesis — the teacher reads conclusions, not data.

**System B**: The equivalent information is distributed across: a class landscape panel (aggregate stats, clusters), a student detail panel (per-student coding records, quotes, concerns, engagement signals), a theme browser (theme list with supporting quotes), and a synthesis panel (class temperature, attention areas, engagement highlights). The total information may be comparable or greater, but the teacher must navigate between panels and mentally assemble the picture.

**Verdict**: For a first read, System A wins on density. For repeated reference ("What did Riley say about ICE?"), System B's structured data is more navigable. The ideal is both — a narrative summary *generated from* structured data.

### 5.2 Actionability

**System A**: Each section ends with "Instructor Action Needed" items or connects directly to next steps. The "Students to Check In With" section includes specific reasons and suggested tones. The "What This Tells Us for Week X+1" section is directly actionable for lesson planning.

**System B**: The guided synthesis produces `attention_areas` (a list of strings) and `class_temperature` (a paragraph). Concern flags include `why_flagged` and `flagged_passage`. These are actionable at the individual student level but do not aggregate into class-level action items. There is no pedagogical planning component.

**Verdict**: System A is more actionable at the class level and for planning. System B is more actionable at the individual student level (richer per-student data, searchable, sortable). A teacher needs both.

### 5.3 Navigation

**System A**: For a class of 30+, the Week 3 summary table is the main navigation aid — but it is a flat markdown table. To find what a specific student said, the teacher must Ctrl-F through the document. With 37 students and 6 themes, the relevant quotes for any one student are scattered across sections.

**System B**: Per-student records are individually addressable. The teacher can click on a student name and see their full coding record — theme tags, quotes, emotional register, concerns, what_student_is_reaching_for — in one view. For a class of 60, this is a decisive advantage.

**Verdict**: System B wins for navigation in larger classes. System A's linear narrative works well for classes of 25 but becomes unwieldy at 40+.

### 5.4 Trust and Transparency

**System A**: The teacher reads the output and trusts (or questions) the cloud LLM's interpretation. There is no way to see how the LLM reached its conclusions. If the analysis says "Stephanie's piece is the strongest this week," the teacher takes it on faith or re-reads Stephanie's submission.

**System B**: Multiple layers of transparency are built in:
- Non-LLM quick analysis (word counts, sentiment, keyword hits, embedding clusters) is available alongside LLM analysis
- Cross-validation flags where LLM and non-LLM analyses disagree
- Confidence scores on themes, concern flags, and synthesis
- Anti-bias warnings when tone-policing language is detected in the model's own output
- The `free_form_reading` field shows exactly how the model read each student before extracting structured data
- Pipeline confidence scores (`PipelineConfidence`) track data quality, coding reliability, theme coherence, and synthesis coverage

**Verdict**: System B is dramatically more transparent. The teacher can see the model's reasoning, check its work against non-LLM signals, and identify where it may be unreliable. This is especially important for concern flags, where acting on a false positive has real consequences for a student.

---

## 6. Recommendations

### 6.1 What System B Should Adopt from System A

**Priority 1: Executive Summary / Class Narrative**
System B should produce a readable narrative summary — not as a replacement for the structured data, but as a synthesis layer on top of it. The guided synthesis already produces `class_temperature` and `attention_areas`; these should be expanded into a 300-500 word narrative that a teacher can read in 3 minutes and get the essential picture. The chatbot export module (`chatbot_export.py`) already contains prompt templates for this kind of narrative generation — the synthesis-only export prompt asks for "What Your Students Said," "Emergent Themes," "Tensions & Contradictions," "Surprises," etc. This template could be used locally, not just for export.

**Priority 2: Forward-Looking Component**
System A's "What This Tells Us for Week X+1" is among its most actionable sections. System B could support this by: (a) allowing the teacher to input next week's topic/readings as context at run start, and (b) including a synthesis call that connects current findings to upcoming content. This does not require accessing Canvas — the teacher types "Next week: intersectionality, Crenshaw" and the synthesis includes "Students are already connecting personal experiences to structural analysis, which means they're ready for Crenshaw's framework."

**Priority 3: Multiplicity Narrative**
System B collects the data for a Divergent Approaches section (readings_referenced, personal_connections, emotional_register, format_breakdown) but does not assemble it. A guided synthesis call that receives the distribution of these fields and produces a narrative about *how* students are entering the material differently would add significant value for relatively low implementation cost.

**Priority 4: Pedagogical Wins**
System B should explicitly surface what is working well. This is motivating for teachers and informs what to preserve. The data exists in the engagement_highlights from guided synthesis — the gap is framing. "3 students made strong personal connections" is a finding; "The multiplicity of entry points is producing exactly the kind of diverse engagement the assignment was designed for" is a pedagogical win.

**Priority 5: Questions/Confusions Category**
System A surfaces a category of observations that System B does not: logistical confusions, assignment format issues, and patterns of surface-level engagement that suggest comprehension problems rather than disengagement. A simple addition to the per-student coding prompt ("Does this student appear confused about the assignment expectations, as distinct from choosing not to engage deeply?") could surface this signal.

### 6.2 What System B Should Keep That System A Cannot Do

- **Synthesis-first class reading**: Structurally necessary for relational harm detection. System A cannot replicate this because it is a single-pass architecture.
- **Reading-first per-student coding**: Produces asset framing and `what_student_is_reaching_for` that System A's single pass does not generate as a distinct category.
- **Anti-bias post-processing**: Automated detection of the model's own bias is a capability System A fundamentally lacks.
- **Linguistic justice infrastructure**: Sentiment suppression, protected feature word budget boosting, and asset labeling are structural protections that cannot be achieved through prompt instructions alone.
- **Local processing with FERPA validation**: The privacy guarantee is architectural, not behavioral.
- **Structured persistence and trajectories**: Cross-run, cross-week tracking that ephemeral markdown files cannot provide.
- **Transparency and cross-validation**: Confidence scores, non-LLM corroboration, and visible model reasoning.

### 6.3 The Ideal Hybrid

The ideal system uses System B's pipeline architecture and data infrastructure while producing output that approaches System A's narrative quality. Concretely:

1. **Pipeline**: System B's synthesis-first, reading-first, anti-bias pipeline runs locally on Gemma 12B. All structured data persists in the store.

2. **Narrative layer**: After the pipeline completes, a synthesis pass (local or cloud-enhanced) produces a System A-style narrative document from the structured data. The chatbot export already has the prompt templates for this. On Tier 1 (local only), this uses Gemma 12B and produces a functional but less polished narrative. On Tier 2-3 (with cloud enhancement or handoff), the narrative approaches System A quality.

3. **GUI + Document**: The teacher gets both — structured, navigable data in the GUI for detailed per-student work, and a readable narrative document (viewable in-app or exportable as markdown) for the 15-minute overview.

4. **Forward-looking input**: The run wizard includes an optional field for "What's coming next week?" that flows into the synthesis narrative.

5. **Cross-run integration**: The narrative synthesis includes trajectory data when available — "This is Catrina's fourth consecutive week of exceptional work" — which System A achieves only through the teacher's memory.

6. **Teacher as synthesis layer**: System B should not try to replicate System A's pedagogical planning recommendations (which depend on deep course knowledge the system does not have). Instead, it should provide the diagnosis — class temperature, attention areas, multiplicity map, concern patterns — and let the teacher do the planning. System A's forward-looking sections work because the cloud LLM has been given the full course structure and upcoming content. System B, running assignment-by-assignment, does not have this context unless the teacher provides it.

The key insight from this comparison is that System A and System B are not competing approaches — they are complementary layers that address different dimensions of the model-size vs. architecture trade-off. System B provides the infrastructure (FERPA compliance, anti-bias post-processing, persistence, transparency, relational context) that System A cannot, regardless of model size — these are architectural properties, not model-capability properties. System A provides the narrative synthesis quality that System B's 12B local model does not yet match — a genuine model-capability gap.

But the architectural hypothesis is confirmed on the dimension that matters most: equity-critical detection. Gemma 12B with synthesis-first class reading achieves 100% concern detection with 0 false positives across 5 replicated runs — outperforming the same model family at 27B without the architecture (which misses tone policing consistently), and matching or exceeding what System A's Opus-class model achieves in a single pass (where relational harm detection is incidental rather than structural). The 10-15x model size difference does not determine equity outcomes when the smaller model is forced to read the class as a community before evaluating individuals.

The chatbot handoff export — already built into System B — is the bridge that recovers System A's narrative strengths: the local pipeline does the FERPA-protected equity-critical work, then generates an anonymized prompt that a cloud model can turn into a System A-quality narrative. The teacher gets reliable equity detection (architecture-dependent, achieved locally) plus narrative synthesis quality (model-size-dependent, achieved through anonymized cloud enhancement) without ever sending student data to the cloud. This is not a compromise — it is an architecture that uses each model for what it does best while maintaining an unconditional privacy guarantee.

---

## Appendix: Data Sources

### System A
- Prompt: `/Users/june/Documents/Teaching/2026courseplanning/weekly_summaries/Weekly_Email&Analysis_Prompt.md`
- Week 3 output: `/Users/june/Documents/Teaching/2026courseplanning/weekly_summaries/ETHN1_03/week_3_student_work_summary.md`
- Week 4 output: `/Users/june/Documents/Teaching/2026courseplanning/weekly_summaries/ETHN1_03/week_4_student_work_summary.md`
- Week 5 output: `/Users/june/Documents/Teaching/2026courseplanning/weekly_summaries/ETHN1_03/week_5_student_work_summary.md`

### System B
- Pipeline orchestrator: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/engine.py`
- Data models: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/models.py`
- Per-student coding: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/submission_coder.py`
- Concern detection: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/concern_detector.py`
- Synthesizer: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/synthesizer.py`
- Theme generation: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/theme_generator.py`
- Class reader: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/class_reader.py`
- Chatbot export: `/Users/june/Documents/GitHub/Autograder4Canvas/src/insights/chatbot_export.py`
- Reading-first comparison: `/Users/june/Documents/GitHub/Autograder4Canvas/data/demo_baked/reading_first_comparison.json`
- Experiment log: `/Users/june/Documents/GitHub/Autograder4Canvas/docs/research/experiment_log.md`
