# Pipeline Evaluation: Ethnic Studies — Intersectionality in Practice

> **Run date:** 2026-03-08
> **Evaluation date:** 2026-03-21
> **Model:** mlx-community/Qwen2.5-7B-Instruct-4bit (local, lightweight tier)
> **Corpus:** 29 students, "Week 6 Discussion: Intersectionality in Practice"
> **Total runtime:** 6,612 seconds (~110 min), 228 seconds/student
> **Evaluator:** Pipeline quality audit (automated analysis of output vs. raw submissions)

---

## Executive Summary

The pipeline produced genuinely useful output for the 10 on-topic intersectionality submissions (S001, S002, S003, S010, S011, S015, S018, S020, S022, S025). Coding accuracy is strong for this subset, concern detection correctly identified the three most pedagogically important patterns (essentializing, colorblindness, tone policing), and feedback is personalized with specific references to student content.

However, the corpus contains a critical structural problem that the pipeline failed to surface: **19 of 29 submissions (66%) are about phones and driving, not intersectionality.** These are DAIGT-adapted essays on a completely different topic, placed into an Ethnic Studies class corpus. The pipeline coded them, themed them, and generated feedback for them as if they were legitimate responses to the assignment prompt — never flagging that two-thirds of the class appears to have submitted work for a different assignment entirely. This is the single most important finding of this evaluation.

---

## 1. Coding Accuracy

**Rating: Adequate (on-topic) / Critical Gap (off-topic)**

### On-topic submissions (10 students): Strong

Detailed comparison of 8 raw submissions against their codings:

**Maria Ndiaye (S001, ESL pattern):** Coding accurately captures "connecting theory to family history" and "intersectionality in multiple contexts." Personal connections correctly identified (grandmother in Senegal, mother in America). The emotional register "personal" is accurate. Notable quotes are well-selected — both capture the strongest moments of her writing. Concepts_applied correctly lists "intersectionality." **Accurate.**

**Jordan Kim (S002, burnout pattern):** Tags "connecting theory to personal experience" and "intersectionality in family context" are accurate. Personal connections captured (mom Korean and a woman, dad's experience). The coding correctly notes Crenshaw as a reading reference. However, the coding misses that this is a truncated submission ("Idk I had more to say but its late and") — the burnout signal is visible but not coded. **Mostly accurate, missed burnout signal.**

**Alex Hernandez (S003, smoking gun pattern):** Coded as "explaining complex concepts" and "historical context of intersectionality" — both accurate for the content. However, this submission contains raw HTML tags (`<h2>`, `<p>`, `<h3>`) and markdown bold (`**`), which are AI copy-paste artifacts. The coding treats it as a legitimate student submission. The pipeline did not flag the smoking gun. **Content coding accurate; missed the most important signal about this submission.**

**Connor Walsh (S018, colorblind pattern):** Tags "intersectionality as framework" and "individualism vs. collective identity" are accurate and well-chosen. The concern correctly identifies the colorblind claim with appropriate surrounding context and a clear explanation for the teacher. Emotional register "reflective" is accurate. **Strong.**

**Jake Novak (S020, premise challenger):** Tags "critiquing intersectionality framework" and "class-based experiences" are excellent — they capture exactly what this student is doing. Personal connection to family socioeconomic status is correctly identified. The LLM correctly noted this as analytical rather than hostile. **Strong.**

**Destiny Williams (S022, righteous anger):** Tags capture the three key dimensions: "connecting theory to personal experience," "intersectionality in practice," and "historical impact on current conditions." Emotional register "passionate" is accurate. Personal connections correctly identify grandmother's experience and neighborhood history. Current events reference to redlining is correctly captured. **Strong.**

**Brittany Okafor (S015, essentializer):** Tags are appropriate. The concern flag for essentializing language is correctly identified with good context. However, the coding also includes "celebrating cultural diversity" as a theme tag, which may inadvertently validate the essentializing framing. **Mostly accurate; theme tag choice could reinforce the problem.**

**Aiden Brooks (S025, tone policer):** Tags "desire for respectful discussions" and "acknowledging emotional complexity" are accurate for what the student wrote, though the second tag is generous — the student is not so much acknowledging emotional complexity as requesting its suppression. The concern for tone policing is correctly identified. Emotional register coded as "analytical" is questionable — this reads more as "defensive" or "uncomfortable." **Adequate; emotional register slightly mischaracterized.**

### Off-topic submissions (19 students): Critical Gap

**Sophia Ramirez (S004):** Wrote about phones and driving — zero connection to intersectionality, the course reading, or ethnic studies. Pipeline coded it with tags "importance of safety" and "public awareness," which accurately describe the content but completely miss that this is off-topic.

**David Park (S007):** Wrote about distracted driving. Pipeline coded it with theme tag "intersectionality in practice" at 0.8 confidence. The submission contains zero mentions of intersectionality. This is a hallucinated theme assignment — the LLM forced the assignment topic onto unrelated content.

**Ryan Mitchell (S030):** Wrote about phones and driving. Coded with "practical application of intersectionality" at 0.6 confidence. Again, zero connection to intersectionality in the actual text.

**Marcus Rivera (S019):** Wrote about texting and driving with statistics. Pipeline coded concepts_applied as including "intersectionality" — this word does not appear in the submission. **This is a hallucination in the coding output.**

The pipeline has no mechanism to detect that a submission is off-topic relative to the assignment prompt. The teacher context explicitly states this is about "intersectionality theory applied to everyday life," but the LLM codes whatever content it receives without checking topical relevance.

### Recommendations

1. **CRITICAL: Add assignment-relevance check.** Before coding, compare submission content against the assignment prompt/teacher context. Flag submissions that share zero vocabulary overlap with the expected topic. This is not a surveillance feature — it tells the teacher "19 students appear to have submitted work for a different assignment," which is immediately actionable information.

2. **Fix hallucinated concept attribution.** The LLM should not add "intersectionality" to concepts_applied for a submission that never mentions the word. Add a post-processing validation step: concepts_applied entries must appear (or have clear synonyms) in the actual submission text.

3. **Surface truncated/incomplete submissions.** Jordan Kim's submission cuts off mid-sentence. The coding should note this as potentially incomplete rather than treating it as a finished response.

4. **Reconsider theme tag for essentializing submissions.** "Celebrating cultural diversity" as a tag for Brittany Okafor's submission may send the wrong signal to a teacher reviewing codings. The tag is factually descriptive but pedagogically misleading when the same submission is flagged for essentializing.

---

## 2. Theme Quality

**Rating: Needs Work**

### Overview

30 themes total: 18 LLM-generated (0.7-0.9 confidence), 12 tag-frequency fallbacks (0.3 confidence). The fallbacks are labeled "Auto-grouped from coding tag ... (LLM timed out)."

### Problems

**Two completely separate topic domains jammed together.** The theme list contains themes about distracted driving (risks, consequences, safety, statistics, blanket bans, technological solutions) and themes about intersectionality (connecting theory to experience, framework critique, cultural diversity). These are presented as if they are all themes from one class discussion about intersectionality. A teacher reading this theme list would be deeply confused.

**Massive redundancy among driving themes.** At least 5 themes overlap heavily:
- "risks and consequences of distracted driving" (freq 5, conf 0.9)
- "distracted driving risks" (freq 4, conf 0.85)
- "concern for safety" (freq 2, conf 0.9)
- "concern about public safety" (freq 3, conf 0.9)
- "public safety concerns" (freq 2, conf 0.75)

These are essentially the same theme described with slightly different wording. The LLM generated them in separate passes (the 3-pass synthesis approach for 8B reliability) and they were never deduplicated.

**The 12 fallback themes are all intersectionality-related.** This means the LLM theme generation timed out on the intersectionality submissions — the ones that actually matter for this assignment. The auto-grouped fallbacks have no descriptions, no supporting quotes, and 0.3 confidence. So the most pedagogically important themes (how students connected intersectionality to family, community, identity) are the least developed in the output.

**Missing themes that a teacher would care about:**
- No theme about **students bringing non-American perspectives** (Maria Ndiaye's Senegal connection is powerful and unique)
- No theme about **class/poverty as an axis of intersectionality** (Jake Novak's critique is a genuine intellectual contribution)
- No theme about **righteous anger as engagement** (Destiny Williams's submission is the most engaged in the class)
- No theme about **discomfort with the material** (Connor Walsh and Aiden Brooks both express resistance in different ways)
- No theme about **the gap between theory and lived experience** (multiple students address this)

### What works

The LLM-generated themes for the driving submissions are internally coherent, even if they are about the wrong topic. The contradiction detection found 6 tensions, several of which are genuine (personal responsibility vs. policy, blanket ban vs. nuanced approach). The theme "critiquing intersectionality framework" correctly isolated Jake Novak's submission as a distinct intellectual move.

### Recommendations

1. **CRITICAL: Deduplicate themes across passes.** After the 3-pass theme generation, run a consolidation step that merges themes with high semantic similarity. The current output has 5+ near-identical driving themes.

2. **CRITICAL: Separate themes by topic cluster when submissions diverge.** The quick_analysis already identified 5 clusters, with cluster 1 (intersectionality) clearly separate from clusters 0/3/4 (driving). Theme generation should respect these cluster boundaries and present separate theme groups, or at minimum label them.

3. **HIGH: Improve timeout handling for intersectionality themes.** The 12 fallback themes are all intersectionality-related, meaning the LLM choked specifically on the on-topic submissions. Investigate why — possibly because the intersectionality submissions require more nuanced theme extraction than "dangers of texting and driving."

4. **Add meta-theme about assignment engagement.** A teacher reading 30 themes wants to know: "How did my class engage with the assignment?" A top-level observation like "10 students engaged with the intersectionality reading; 19 submitted essays about phones and driving that appear unrelated to the assignment" would be the single most useful piece of information.

---

## 3. Synthesis Quality

**Rating: Critical Gap**

### Structure

Only 3 of 9 sections have content. The 6 empty sections ("surprises," "focus_areas," "concerns," "divergent_approaches," "looking_ahead," "students_to_check_in_with") all show "(Insufficient data for this section.)" This is the double-brace JSON error documented in OBS-PIPE-03 — the 3-pass approach resolved it partially but 6 sections still failed.

### Content of populated sections

**"what_students_said":** Leads with distracted driving content (Ethan Liu on safety, Jasmine Lee on parents). Mentions intersectionality only briefly. References Brittany Okafor's essentializing language, which is an odd choice for the opening synthesis section — this is a concern, not a representative example of what students said. The synthesis does not mention Maria Ndiaye, Destiny Williams, or Jake Novak — three of the most substantive submissions.

**"emergent_themes":** Again leads with driving content (Darius Hayes). Misattributes a quote to Connor Walsh about technology/steering wheel — Connor Walsh wrote about colorblindness, not driving. This appears to be a hallucinated attribution. Does mention Alex Hernandez/Crenshaw and Jake Novak's critique, but buries them after the driving content.

**"tensions_and_contradictions":** The tension described (personal responsibility vs. public awareness) is from the driving submissions, not the intersectionality discussion. The genuine tensions in this class — between colorblindness and structural analysis, between academic framing and lived experience, between celebrating diversity and essentializing it — are entirely absent.

### The core problem

The synthesis treats the corpus as if all 29 students wrote about the same topic. It weights the 19 driving submissions more heavily because they are the majority. From the teacher's perspective, the synthesis should focus on how students engaged with intersectionality and flag that a large group submitted off-topic work. Instead, the teacher gets a synthesis about phones and driving with some intersectionality content mixed in.

### Recommendations

1. **CRITICAL: Fix the 6 empty synthesis sections.** "students_to_check_in_with" is arguably the most valuable section for a teacher, and it contains no data. This section should flag: Jordan Kim (truncated, burnout signal), Connor Walsh (colorblind framing needs pedagogical follow-up), Aiden Brooks (tone policing needs follow-up), Alex Hernandez (possible AI submission), and the 19 off-topic students.

2. **CRITICAL: Synthesis should be cluster-aware.** When the class has clearly divergent response groups, the synthesis should acknowledge this structure rather than averaging across it. Lead with the on-topic group and treat the off-topic group as a separate finding.

3. **Fix attribution errors.** The Connor Walsh misattribution in "emergent_themes" is a factual error that would undermine teacher trust. Post-processing should verify that quoted text actually appears in the attributed student's submission.

4. **Prioritize the most engaged voices.** Maria Ndiaye, Destiny Williams, and Jake Novak wrote the most substantive on-topic submissions and none appear in the synthesis. The synthesis should surface students who did the most interesting intellectual work, not just quote whoever the LLM encountered first.

---

## 4. Feedback Quality

**Rating: Adequate (on-topic) / Needs Work (off-topic)**

### On-topic feedback: Genuinely personalized

**Maria Ndiaye (S001):** Feedback references her grandmother's experience in Senegal and asks how women in other parts of the world might inform understanding of intersectionality. This is specific, encouraging, and extends her thinking. The forward-looking question is well-matched to what she actually wrote about. **Strong.**

**Jordan Kim (S002):** References mom's Korean and female experiences, asks how these shape worldview. Specific to the submission. However, does not acknowledge the truncation or burnout signal ("its late and"). A teacher would want to know this student ran out of steam. **Adequate.**

**Jake Novak (S020):** Feedback validates his critique about class-based experiences and asks how we can better include class in intersectionality discussions. This is exactly the right move — it honors his intellectual contribution rather than dismissing his challenge. **Strong.**

**Destiny Williams (S022):** References redlining and community impact specifically. Asks about using historical context to advocate for change. Appropriate tone — meets her passion without dampening it. **Strong.**

**Connor Walsh (S018):** Feedback says "your reflection on treating everyone the same regardless of their background is a powerful statement. It shows a deep commitment to fairness and equality." This is problematic. The coding correctly flagged colorblind framing as a concern, but the feedback then validates that exact framing. A teacher using this draft would be reinforcing the colorblind ideology the concern flagged. The forward question ("how can intersectionality help us understand treating everyone fairly?") attempts a gentle redirect but the opening validation undercuts it. **Needs rework — feedback contradicts the concern flag.**

**Aiden Brooks (S025):** Feedback says "your thoughtful reflection on the emotional complexity of class discussions really stood out." This again validates the tone policing behavior that was correctly flagged as a concern. The coding and the feedback are working at cross purposes. **Needs rework — same contradiction pattern as Connor Walsh.**

**Brittany Okafor (S015):** Feedback highlights her "passion for discussing how different backgrounds come together" and asks about exploring resilience of other cultural groups. This reinforces the essentializing frame rather than gently challenging it. The coding flagged essentializing language, but the feedback does not redirect. **Needs rework.**

### Off-topic feedback: Formulaic and misleading

The feedback for off-topic driving submissions follows a pattern: praise the content, then awkwardly attempt to connect it to intersectionality. Examples:

- **David Park (S007):** "your analysis of distracted driving and its intersection with public safety concerns was clear and thorough" — uses "intersection" to vaguely gesture at the course topic, but the student wrote zero words about intersectionality.
- **Ryan Mitchell (S030):** "It shows a deep understanding of how intersectionality can apply to everyday situations" — Ryan wrote about phones and driving. This claim is false.
- **Olivia Chen (S012):** "how might you apply these safety risks to other areas of intersectionality you've explored in class?" — fabricates a connection that does not exist in the submission.

The feedback for off-topic submissions is not just unhelpful — it would actively mislead the teacher by suggesting these students engaged with the assignment.

### Structural patterns

All feedback follows the same template: [Name], [specific praise referencing content]. [Validation statement]. For next week, I'm curious: [forward-looking question]. This template is effective for on-topic submissions but becomes formulaic across 29 students. The "I'm curious" framing appears in every single piece of feedback.

### Recommendations

1. **CRITICAL: Feedback for concern-flagged students must align with the concern.** When the pipeline flags colorblind framing (Connor Walsh), essentializing (Brittany Okafor), or tone policing (Aiden Brooks), the feedback draft should incorporate a gentle pedagogical redirect, not validate the flagged behavior. This is the most important feedback fix — currently the concern system and the feedback system contradict each other.

2. **CRITICAL: Feedback for off-topic submissions should acknowledge the disconnect.** Instead of fabricating connections to intersectionality, the feedback for driving essays should note the topic mismatch. Something like "I noticed your post focused on distracted driving rather than the intersectionality reading — I want to make sure you saw the right prompt" is more useful than pretending the student engaged with the assignment.

3. **Vary the template.** The "I'm curious" forward question appears in all 29 feedback drafts. Add 3-4 alternative framings to reduce the template feeling.

4. **Surface burnout/incomplete signals in feedback.** Jordan Kim's feedback should acknowledge the truncation and check in, not just praise the partial content.

---

## 5. Concern Signals

**Rating: Adequate**

### What was correctly caught

**Brittany Okafor — Essentializing (POSSIBLE CONCERN, conf 0.8):** Correctly identified generalizing language about Black families and resilience. The flagged passage and explanation are appropriate. The signal type "POSSIBLE CONCERN" (not "DEFINITE") is calibrated well — this is a teachable moment, not a crisis. **Strong.**

**Connor Walsh — Colorblind claim (concern in coding, conf 0.85):** Correctly identified the "I don't see race" framing. The explanation is clear and actionable: "Teacher may want to engage this student with specific evidence of how race and gender intersect." **Strong.**

**Aiden Brooks — Tone policing (concern in coding, conf 0.8):** Correctly identified the request to suppress emotion in class discussions. The explanation appropriately frames this as a potential barrier to inclusive discussion. **Strong.**

### What was correctly NOT flagged

**Destiny Williams (S022):** Flagged as APPROPRIATE with interpretation "Political urgency about injustice — NOT a concern." This is exactly right. Her anger is appropriate engagement with the material, not a behavioral concern. **Strong.**

**Jake Novak (S020):** Flagged as APPROPRIATE despite critiquing the framework. The pipeline correctly distinguished legitimate intellectual challenge from dismissiveness. **Strong.**

### What was missed

**Jordan Kim (S002) — Burnout/disengagement signal:** The submission cuts off mid-sentence with "Idk I had more to say but its late and." This is a clear disengagement or exhaustion signal. The pipeline flagged it as APPROPRIATE with "Sophisticated analysis," which misses the point entirely. The concern system should have flagged a possible wellness check.

**Alex Hernandez (S003) — AI copy-paste artifacts:** The submission contains HTML tags and markdown formatting that are smoking-gun AI indicators. Neither the concern system nor the coding system flagged this. This is a detection gap, though it may be out of scope for the concern detector (which looks at discourse patterns, not formatting artifacts).

**19 off-topic submissions — No flags at all:** Not a single concern signal was raised about the fact that 19 students submitted work about phones and driving to an intersectionality discussion. The concern system only looks at discourse patterns within individual submissions, not at assignment relevance.

**S005 (Ethan Liu) and S033 (Nadia Petrov) — Near-identical text:** Nadia Petrov's submission is the first 120 words of Ethan Liu's submission, verbatim (both sourced from daigt_00011). In a real classroom, this would be a copy/plagiarism signal. The pipeline did not flag this, though it did cluster them together (cluster 4). The concern system does not do pairwise text comparison.

### Classification accuracy of the 12 signals

10 of 12 signals are classified APPROPRIATE — these are all from the keyword_category "critical" (meaning the student used critical analysis language). The interpretations are correct but generic: either "Sophisticated analysis — student engaging well" or "Political urgency about injustice — NOT a concern." These are true but not very informative.

The 2 non-APPROPRIATE signals (Brittany Okafor essentializing, Brittany Okafor APPROPRIATE) both apply to the same student, which is correct — she triggers both the "critical" pattern (engagement) and the "essentializing" pattern.

### Recommendations

1. **HIGH: Add burnout/disengagement detection.** Truncated submissions that end mid-sentence should trigger a "check in with this student" signal, not an "engaging well" signal. Look for: text that cuts off abruptly, phrases like "idk," "its late," "I'll finish later."

2. **HIGH: Add off-topic detection as a concern signal.** When a submission shares near-zero vocabulary with the assignment prompt, flag it. Frame for the teacher: "This submission may be for a different assignment."

3. **MEDIUM: Add pairwise near-duplicate detection.** Ethan Liu and Nadia Petrov submitted identical text. The pipeline should surface this. Frame it as informational, not accusatory (per the equity guidelines in testing_observations.md OBS-CHEAT-04).

4. **LOW: Enrich APPROPRIATE signal interpretations.** "Sophisticated analysis — student engaging well" is generic. The interpretation should reference what specific analytical move the student made.

---

## 6. Equity Audit

**Rating: Needs Work**

### Language Justice: ESL student treatment

**Maria Ndiaye (S001)** is the one ESL-patterned student. Her submission contains non-standard grammar throughout: "she don't have much money," "everybody know that," "my grandmother she always say," "being poor woman who is also from village," "my mother she is Black woman here," "each of these things it add up."

**Coding treatment:** The pipeline coded Maria's submission accurately and respectfully. Theme tags capture her intellectual contribution. Personal connections are well-identified. The emotional register "personal" is appropriate. The notable quotes selected are genuinely her strongest moments. The coding does not penalize or flag her grammar. **This passes the Language Justice test.**

**Feedback treatment:** The feedback is encouraging and specific: references her grandmother, asks a forward-looking question about global perspectives. Does not correct her grammar or suggest she needs writing improvement. Does not use qualifiers like "despite language barriers" or "good attempt." **This passes the Language Justice test.**

**However:** Maria is the only ESL student in the corpus. The testing_observations.md document correctly notes (Testing gap 1) that validation on one ESL student is insufficient. The system has not been tested on students with other L1 transfer patterns (Spanish, Mandarin, Arabic, Korean), on dictated/speech-to-text submissions, or on translanguaging.

### Community Cultural Wealth: Personal/cultural connections

Students making personal and cultural connections are generally well-served:

- **Maria Ndiaye:** Family and cultural connections coded as strengths
- **Destiny Williams:** Neighborhood history and grandmother coded as personal connections
- **Jake Novak:** Family poverty coded as personal connection, not dismissed
- **Brittany Okafor:** Neighborhood cultural knowledge coded as personal connections

None of these students had their personal knowledge dismissed as "off-topic" or "anecdotal." The coding system treated experiential knowledge as legitimate intellectual engagement. **This passes the Community Cultural Wealth test for coded students.**

**Gap:** The 19 off-topic students include Ava Kowalski (S021) who shares a personal anecdote about her mother texting and driving, and Darius Hayes (S023) who admits to texting and driving himself. These personal disclosures are coded as personal connections, which is correct. However, these students are writing about the wrong topic — they may be drawing on personal experience because they did not read the assignment. The pipeline treats personal connection as inherently positive, which is correct in isolation but misleading when the connection is to off-topic content.

### Algorithmic Justice: Concern signal distribution

Of the 12 concern signals:
- 10 are APPROPRIATE (benign), distributed across on-topic and off-topic students
- 1 is POSSIBLE CONCERN (Brittany Okafor — essentializing)
- 1 is APPROPRIATE (duplicate Brittany Okafor entry)

The flagged students by the LLM concern detector (in codings):
- Brittany Okafor (essentializing) — Black student
- Connor Walsh (colorblind) — apparent White student
- Aiden Brooks (tone policing) — apparent White student

The concern flags do not disproportionately target any racial group. The two White students flagged for colorblindness and tone policing are pedagogically appropriate flags — these are conceptual misunderstandings that Ethnic Studies curriculum is designed to address. The Black student flagged for essentializing is also appropriate — she is generalizing about racial groups in a way that flattens individual experience.

**However:** Concern signals from the quick_analysis keyword detector are entirely driven by the word "critical" (keyword_category: "critical"). This means any student who uses words associated with critical analysis triggers a signal — which is then classified as APPROPRIATE. This is technically correct but adds noise. A signal that is always APPROPRIATE is not a useful signal; it is a false-positive generator.

### Standard Academic English as default

The pipeline does not explicitly penalize non-standard English. Maria Ndiaye's grammar is not flagged. Emma Gonzalez (S014) uses "u" for "you," "mite" for "might," "there" for "their" consistently — her coding is accurate without grammar commentary. Isaiah Thomas (S009) uses "sum" for "some" and "was" for "were" — no penalty.

**However:** The emotional_register classification may encode a subtle bias. Every off-topic student who writes in non-standard English (Emma Gonzalez, Isaiah Thomas, Darius Hayes) gets classified as "analytical" or "passionate." Destiny Williams, who writes in non-standard English about a deeply personal topic with explicit anger, gets "passionate." Meanwhile, Tyler Nguyen (S010) and Jaylen Carter (S011), who write in polished academic English about intersectionality, both get "analytical." The register classification may be tracking formality/polish rather than actual emotional content.

### Recommendations

1. **HIGH: Remove the "critical" keyword APPROPRIATE signals.** They flag every student who uses critical analysis vocabulary, then classify all of them as benign. This is noise, not signal. The concern detector should focus on patterns that require teacher attention, not patterns that confirm engagement.

2. **HIGH: Test on more ESL patterns.** One ESL student is insufficient validation. Generate synthetic submissions with Spanish L1 transfer, Mandarin L1 transfer, and Arabic L1 transfer patterns. Verify coding accuracy does not degrade.

3. **MEDIUM: Audit emotional_register for formality bias.** Check whether "analytical" is being assigned to polished writing and "passionate"/"personal" to informal writing, independent of actual emotional content. A student can write analytically in non-standard English and passionately in formal English.

4. **MEDIUM: Do not validate concern-flagged behavior in feedback.** As noted in the Feedback section, Connor Walsh's feedback validates colorblind framing, Aiden Brooks's feedback validates tone policing, and Brittany Okafor's feedback reinforces essentializing. This is an equity failure — the system identifies a problem and then tells the student they are doing great. Fix the feedback-concern alignment.

---

## 7. Timing Analysis

**Rating: Adequate**

### Breakdown (6,612 seconds total)

| Stage | Seconds | % of total | Per-student |
|-------|---------|-----------|-------------|
| Quick analysis | 20 | 0.3% | <1s |
| Coding | 2,136 | 32.3% | 73.7s |
| Concerns | 1,310 | 19.8% | 45.2s |
| Themes | 1,673 | 25.3% | — (class-level) |
| Outliers | 91 | 1.4% | — |
| Synthesis | 409 | 6.2% | — |
| Feedback | 901 | 13.6% | 31.1s |

### Observations

**Coding dominates at 32%.** 73.7s per student is reasonable for a local 7B model generating structured JSON with theme tags, quotes, emotional register, and concepts. This is the stage that produces the most value per token spent.

**Concerns at 20% is expensive for what it produces.** 45.2s per student to generate 12 signals, 10 of which are APPROPRIATE (noise). The per-student time suggests the LLM is doing a full read + analysis pass for each student. If the keyword-based APPROPRIATE signals could be filtered pre-LLM (they are already detected by the quick_analyzer's keyword_hits), the concern stage could skip students who only have "critical" keyword matches and focus LLM time on students with actual discourse pattern concerns.

**Themes at 25% reflects the 3-pass approach.** 1,673 seconds for class-level theme generation is the cost of running 3 separate LLM passes to work around the 8B model's JSON reliability issues. This produced 18 LLM themes but failed on 12 (which fell back to tag-frequency grouping). A larger model or better JSON enforcement could reduce this to 1 pass.

**Feedback at 14% is efficient.** 31.1s per student for personalized draft feedback is good value. The template structure keeps generation focused.

**Synthesis at 6% produced 3/9 sections.** The cost is low but the output is incomplete. The remaining 6 sections failed, meaning ~60% of synthesis compute was wasted on failed generation attempts.

### Cost-quality tradeoff

At 228 seconds/student on a local M-series Mac, a class of 30 takes ~110 minutes. This is acceptable as an overnight or prep-period process. The teacher sets it running, comes back later.

The bottleneck for quality is not time but model capability. The 7B model struggles with:
- JSON structure at synthesis scale (6/9 sections failed)
- Theme deduplication across passes
- Assignment-relevance detection (zero capability)
- Feedback-concern alignment (contradicts its own flags)

Moving to a cloud API (Sonnet-class model) would likely reduce total time to 10-15 minutes and significantly improve synthesis completeness and theme quality. The tradeoff is cost (~$0.50-1.50 per run) and FERPA considerations for sending student text to a cloud endpoint.

### Recommendations

1. **MEDIUM: Pre-filter concern stage.** Skip LLM concern analysis for students whose only keyword_hits are "critical" (APPROPRIATE). Run LLM concern analysis only for students with essentializing, colorblind, or other pedagogically meaningful keyword patterns, plus students with unusual sentiment profiles. This could cut concern stage time by 50-70%.

2. **MEDIUM: Cache theme generation across passes.** The 3-pass approach generates overlapping themes. If pass 1 and pass 2 produce similar themes, pass 3 could focus on gaps rather than regenerating.

3. **LOW: Parallelize per-student stages.** Coding, concerns, and feedback are independent per student. If the MLX backend supports batching or the system moves to a cloud API with concurrent requests, these stages could run in parallel.

---

## Cross-cutting Findings

### The fundamental corpus problem

The single most important finding is not about the pipeline's algorithms — it is about the test corpus design. Placing 19 DAIGT essays about phones and driving into an Ethnic Studies intersectionality discussion creates a scenario that no real classroom would produce (19 students all submitting essays about the wrong topic). The pipeline's inability to detect this is a real gap, but the test corpus should also be redesigned to better simulate realistic classroom variation.

Realistic off-topic submissions in a discussion board would be:
- 1-2 students who misread the prompt
- 1 student who submitted to the wrong assignment
- 1 student who wrote about a related but different reading

Not 19 students all submitting essays about phones and driving. The current corpus tests the pipeline's ability to handle a scenario that would never actually occur, while missing scenarios that would (e.g., 2-3 students are off-topic, most are on-topic with varying depth).

### Pipeline stage dependencies

The pipeline's stages operate in sequence but do not share information well:
- Quick analysis identifies clusters but coding ignores them
- Coding flags concerns but feedback ignores the flags
- Themes are generated from codings but do not deduplicate across passes
- Synthesis receives all data but weights by majority, not relevance

Better information flow between stages would improve output quality more than any single-stage improvement.

---

## Summary of Recommendations by Priority

### Critical (must fix before demo)

| # | Finding | Stage | Fix |
|---|---------|-------|-----|
| 1 | No assignment-relevance detection | Coding/Quick | Add prompt-vs-submission topical overlap check |
| 2 | Feedback contradicts concern flags | Feedback | Align feedback draft with flagged concerns |
| 3 | Synthesis incomplete (6/9 empty) | Synthesis | Improve 8B JSON handling or add section retry |
| 4 | Hallucinated concept attribution | Coding | Post-validate concepts_applied against text |

### High (should fix before demo)

| # | Finding | Stage | Fix |
|---|---------|-------|-----|
| 5 | Theme deduplication absent | Themes | Merge semantically similar themes across passes |
| 6 | No burnout/disengagement detection | Concerns | Detect truncated submissions, exhaustion signals |
| 7 | Off-topic submissions generate misleading feedback | Feedback | Acknowledge topic mismatch instead of fabricating connection |
| 8 | Remove noisy APPROPRIATE signals | Concerns | Pre-filter "critical" keyword matches before LLM |
| 9 | Test on more ESL patterns | Testing | Synthetic submissions with varied L1 transfer |
| 10 | Connor Walsh misattribution in synthesis | Synthesis | Post-validate quoted text against source student |

### Medium (improve after demo)

| # | Finding | Stage | Fix |
|---|---------|-------|-----|
| 11 | Theme generation fails on intersectionality content | Themes | Investigate timeout on nuanced topics |
| 12 | Emotional register may track formality not emotion | Coding | Audit register classification against text features |
| 13 | Near-duplicate detection (S005/S033) | Quick/Concerns | Surface pairwise text identity as informational |
| 14 | Pre-filter concern stage for timing | Concerns | Skip LLM for keyword-only signals |
| 15 | Feedback template variation | Feedback | Add alternative forward-question framings |
| 16 | Cluster-aware synthesis | Synthesis | Separate theme groups by response cluster |

---

## Files Referenced

- `/Users/june/Documents/GitHub/Autograder4Canvas/data/demo_baked/pipeline_evaluation_summary.json`
- `/Users/june/Documents/GitHub/Autograder4Canvas/src/demo_assets/insights_ethnic_studies.json`
- `/Users/june/Documents/GitHub/Autograder4Canvas/data/demo_corpus/ethnic_studies.json`
- `/Users/june/Documents/GitHub/Autograder4Canvas/docs/testing_observations.md`
