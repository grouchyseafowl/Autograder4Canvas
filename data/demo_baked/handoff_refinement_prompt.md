# HANDOFF: Pipeline vs Opus Baseline Comparison & Refinement Planning

## Who You Are Working For
An Ethnic Studies professor is building a tool (Autograder4Canvas) to help teachers analyze student work at scale. The tool runs locally on Apple Silicon (FERPA-safe — no student data leaves the machine). The professor is pitching this to a K-12 principal.

## System Philosophy
This part of the system (insights generation) is NOT a grading tool or an AI detector. It is an **engagement analysis system** that helps teachers understand what their class is thinking, who needs support, and what to teach next. Every output is a "conversation starter, not a verdict." Read `src/docs/ADC_README.md` for full philosophy.

**Engagement reframe context**: The system recently pivoted from an AI-detection frame to an engagement-analysis frame (see `docs/engagement_reframe_spec.md`). This is a **both/and** reorientation, not a total replacement:
- **Primary product**: Engagement signals — personal connection, intellectual work, course engagement, real-time processing
- **Retained detection**: Integrity signals (smoking gun paste artifacts, unicode manipulation, teacher-test patterns, incoherence) stay as explicit flags for clear gaming behavior
- **Structural indicators**: Sentence uniformity, starter diversity, etc. surface as supplementary context ("unusually uniform structure"), not as "AI detected"
- **The privileged disengaged student**: Zero engagement across all dimensions is detectable and surfaceable without needing to determine whether AI was involved. A student phoning it in on an Ethnic Studies assignment for political reasons shows up as absence across every engagement dimension — the system catches that.
- **Key shift**: From "Did the student cheat?" to "How did the student engage with the material?" — but the system still surfaces clear gaming, near-identical submissions, and total disengagement. Teachers make the final call.

Read `docs/engagement_reframe_spec.md` and `docs/engagement_reframe_learning.md` for the full spec.

## Methodological Caveats (READ BEFORE ANALYZING)

**Caveat 1 — Incomplete pipeline run.** The synthesis stage partially failed (3/9 sections populated due to JSON parse errors in the 8B model output). Before attributing gaps to the pipeline's design, check whether missing data is simply an artifact of that incomplete run. We could rerun the remaining stages to get a more complete baseline — but we want to use what we have first to illuminate what revisions we can, and to assess the proof of concept. **Seriously — is an 8B model worth pursuing for this pipeline? If not, for which components? Account for methodological artifacts when answering this.**

**Caveat 2 — "Off-topic" submissions may be a testing artifact.** The demo corpus was assembled from prefab data and retooled for an intersectionality assignment. Before concluding that 19 students are "off-topic," go back and examine:
- `scripts/assemble_demo_corpus.py` — how was the corpus constructed?
- `data/demo_corpus/ethnic_studies.json` — read the actual submissions; is there a link between the driving content and intersectionality, or is this a data construction issue?
- If it IS a data artifact, note that — it changes the evaluation significantly. The pipeline can't be blamed for not detecting a mismatch that exists in our test data, not in real student behavior.
- If the data genuinely has 19 off-topic submissions by design, then the pipeline should catch it.

**Critical equity constraints** (non-negotiable):
- ESL students, neurodivergent writers, students from oral traditions, and first-gen students must not be disproportionately flagged
- Righteous anger about structural injustice is APPROPRIATE engagement, not a concern
- The system surfaces patterns for teacher review — it never auto-penalizes
- "Complete/incomplete" grading is engagement-focused pedagogy, not hoop-jumping
- Never recommend singling out individual students to share — create structural opportunities instead
- Cultural knowledge (family stories, community experience, transnational perspectives) is an ASSET, not "anecdotal evidence"

## What Happened in the Previous Session

### Built Today (already committed)
1. **Gibberish gate** (`src/insights/gibberish_gate.py`) — keyboard mash, Lorem Ipsum, repetition spam detection
2. **Citation checker** (`src/insights/citation_checker.py`) — URL/DOI/author-year extraction, class-level "sources cited" view, async auto-verification with equity note
3. **Reader-test patterns** (`src/insights/patterns.py`) — 23+ regex patterns for "are you reading this?" plus semantic embedding-based detection
4. **MLX fixes** (`src/insights/llm_backend.py`) — serialization lock, per-call max_tokens, `_clean_llm_json()` for double-brace and invalid-escape artifacts
5. **Theme gen limits** (`src/insights/theme_generator.py`) — 1200 token cap for lightweight tier (was 4096, causing 2-hour runaway)
6. **AIC improvements** (`src/Academic_Dishonesty_Check_v2.py`, `src/modules/human_presence_detector.py`) — HP bridge scoring, convergence multiplier, cognitive diversity fix

### Testing Completed
1. **MLX pipeline run**: 29 Ethnic Studies students, Qwen2.5-7B-Instruct-4bit, 1h50m total (228s/student)
2. **Opus baseline**: Same 29 submissions analyzed by claude-opus-4-6[1m] in one shot
3. **Pipeline evaluation**: Refinement agent assessed output across 7 dimensions

### The Core Finding (with caveat)
The Opus baseline immediately identified that **19 of 29 students submitted essays about phones and driving** — seemingly off-topic for an intersectionality assignment. The pipeline processed all 29 without flagging this.

**BUT**: Before treating this as a pipeline gap, investigate whether this is a testing data artifact. The demo corpus was assembled from prefab data. Check `scripts/assemble_demo_corpus.py` and the raw submissions to determine: did we construct the data in a way that created this mismatch? If so, this finding tells us about our methodology, not the pipeline. If the data is genuinely off-topic by design (simulating students who submitted the wrong assignment), then the pipeline should catch it and this IS a real gap.

## Architectural Model: Distributed Intelligence (Mycorrhizal Network)

The pipeline uses a **distributed intelligence model** — multiple networked 8B LLM calls with careful orchestration, aiming to approach the analytical depth of a single large-model pass (Opus). The architectural inspiration comes from the Reframe project's mycorrhizal network implementation, where intelligence emerges from networked lightweight calls rather than single powerful ones.

**Key principles from the mycorrhizal architecture:**

1. **Scoped call history** — each pipeline stage should reference previous stages' outputs. Currently the pipeline's biggest structural flaw is that stages operate in sequence but don't share information well. Quick Analysis identifies clusters but coding ignores them. Coding flags concerns but feedback ignores the flags. Fix this and quality improves more than any single-stage improvement.

2. **Anti-flattening** — the synthesis stage must preserve tensions and contradictions, not smooth them into consensus. When Connor Walsh's colorblindness contradicts Destiny Williams's structural analysis, that tension is the pedagogy. The Reframe engine uses tension injection to prevent this; the Insights pipeline needs an equivalent mechanism.

3. **Coalition without assimilation** — theme generation should preserve distinct analytical stances. The current 30-theme output with 5+ near-identical driving themes is assimilation (everything averaged together). The target is: distinct theme clusters that maintain their specificity, with cross-cluster tensions preserved.

4. **Iterative deepening** — each successive stage should build on accumulated intelligence from previous stages, not start fresh. The feedback drafter receiving concern flags from the concern detector is a mycorrhizal link that's currently broken.

**What this means concretely for the refinement plan**: Many of the pipeline's gaps (feedback-concern contradiction, synthesis weighting by majority, theme deduplication failure) trace to the same root cause — broken information flow between stages. The refinement plan should prioritize inter-stage data flow as a structural fix, not just patch individual stages.

## Key Files to Read

### START HERE — Comparison Outputs
1. `data/demo_baked/baseline_claudcode_opus.md` — **Opus one-shot analysis** (the quality bar)
2. `docs/pipeline_evaluation.md` — **Refinement agent's evaluation** (7 dimensions, 16 recommendations)
3. `data/demo_baked/pipeline_evaluation_summary.json` — Compact pipeline output summary

### Raw Data & Test Apparatus
4. `data/demo_corpus/ethnic_studies.json` — The 29 raw student submissions
5. `src/demo_assets/insights_ethnic_studies.json` — Full pipeline output (164 KB — parse nested JSON strings in `themes.theme_set` and `themes.synthesis_report`)
6. `scripts/assemble_demo_corpus.py` — **How the test data was constructed** (critical for Caveat 2)

### Pipeline Architecture (read as needed for root cause analysis)
7. `src/insights/prompts.py` — All LLM prompt templates (likely where many fixes will go)
8. `src/insights/submission_coder.py` — Per-student LLM coding stage
9. `src/insights/concern_detector.py` — LLM concern detection stage
10. `src/insights/feedback_drafter.py` — Per-student feedback generation
11. `src/insights/theme_generator.py` — Theme generation from coded records
12. `src/insights/synthesizer.py` — Multi-pass narrative synthesis
13. `src/insights/quick_analyzer.py` — Non-LLM analysis (VADER, embeddings, signal matrix, citations, gibberish)
14. `src/insights/patterns.py` — Keyword patterns and signal matrix
15. `src/insights/llm_backend.py` — Backend dispatch with JSON cleanup
16. `src/insights/engine.py` — Pipeline orchestration

### Engagement Reframe & Design Docs
17. `docs/engagement_reframe_spec.md` — **The engagement reframe specification** (signal taxonomy, UI framing, both/and model, system limits). Read this to understand what the pipeline should be producing.
18. `docs/engagement_reframe_learning.md` — **Adaptive calibration system** (6 mechanisms: cohort calibration, assignment context awareness, teacher feedback loop, voice fingerprinting, class culture modeling, predictive engagement). The assignment context awareness mechanism (Mechanism 2) is directly relevant to the topic-mismatch gap.

### Testing Documentation
19. `docs/testing_observations.md` — Prior AIC gaps and cheating coverage audit
20. `data/demo_baked/original_analysis_prompt.md` — Teacher's original manual analysis prompt (what this pipeline automates)

### Memory Files (architectural context)
21. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/project_engagement_reframe.md` — Strategic pivot from AI detection to engagement analysis
22. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/project_equity_attention.md` — Equity attention framework
23. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/project_insights_testing_findings.md` — Prior testing results
24. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/feedback_anti_spotlighting.md` — Anti-spotlighting principle
25. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/feedback_complete_incomplete_pedagogy.md` — C/I grading philosophy
26. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/user_context.md` — User context (HS teacher, K-12 principal pitch)
27. `~/.claude/projects/-Users-june-Documents-GitHub-Autograder4Canvas/memory/research_distributed_llm_analysis.md` — Research report on distributed LLM analysis for educational analytics (8B feasibility, nuance preservation, DeTAILS prior art, mitigation strategies)

### Chatbot Export Comparison
28. `data/demo_baked/chatbot_export_ethnic_studies_full.md` — The system-generated prompt+submissions package for pasting into institutional chatbots. Compare this against the original manual prompt (#20) to see what the pipeline's own export captures vs. misses — this reveals what the system thinks is important to send to a large model.

## Your Task

### Phase 0: Methodology Audit (DO THIS FIRST — write to `docs/comparison_analysis.md` as opening section)

Before any comparison analysis, critically examine how the testing apparatus shaped the data. The goal is to ensure we are refining the pipeline based on real gaps, not methodological artifacts.

1. **Read `scripts/assemble_demo_corpus.py`** — How was the demo corpus constructed? Were submissions written for this assignment, or adapted from other sources? What transformations were applied?
2. **Read `data/demo_corpus/ethnic_studies.json`** — Read the actual 29 submissions. For the 19 about phones/driving: is there ANY connection to intersectionality in the text, or are they purely off-topic?
3. **Check the assignment prompt in the corpus** — Does the assignment description match what students were actually responding to? Is "Intersectionality in Practice" the prompt they were given, or was it retrofitted onto existing data?
4. **Read the Opus baseline prompt** (`data/demo_baked/original_analysis_prompt.md`) — Did the Opus prompt correctly describe the assignment? Could the "off-topic" finding be partly an artifact of how we framed the task to Opus?
5. **Assess the incomplete synthesis** — Which of the findings in `docs/pipeline_evaluation.md` are invalidated or weakened by the fact that synthesis only partially completed?
6. **Surface any other methodology issues** you discover. We don't know what we don't know — that's what fresh eyes are for.

**Output**: A methodology assessment section that explicitly states which findings from the prior evaluation are:
- ✅ Valid regardless of methodology (e.g., feedback-concern contradiction)
- ⚠️ Potentially affected by methodology and need reinterpretation
- ❌ Likely artifacts of test data construction or incomplete pipeline run

**This assessment gates everything else.** Phase 1's comparison analysis should be filtered through these findings. Don't analyze gaps that are actually methodology artifacts.

### Phase 1: Three-Way Comparison Analysis (continues in `docs/comparison_analysis.md`)

Compare pipeline vs Opus. LLMs are stochastic — don't expect identical outputs. Focus on **structural** differences in analytical capability — what patterns does each surface, miss, or mischaracterize?

**Important**: Verify every claim below against the actual data before accepting it. The previous session's analysis was done with full context — you have fresh eyes. Double-check characterizations against the raw submissions in `data/demo_corpus/ethnic_studies.json`. **Filter all findings through your Phase 0 methodology assessment** — if the "off-topic" issue is a data artifact, the comparison looks very different.

| Category | What to Compare |
|---|---|
| **Topic mismatch** | Opus caught 19 off-topic immediately. Pipeline didn't. BUT: is this a real gap or a test data artifact? Check `assemble_demo_corpus.py`. |
| **Student characterization** | Compare coding of on-topic students (Maria Ndiaye, Destiny Williams, Jake Novak, Connor Walsh, Aiden Brooks, Brittany Okafor, Jordan Kim, Alex Hernandez, Tyler Nguyen, Jaylen Carter) |
| **Concern signals** | What each flagged + what each correctly did NOT flag (Destiny's anger = appropriate) |
| **Theme quality** | Opus: 7 clear themes. Pipeline: 30 (many redundant). Which are pedagogically useful? |
| **Synthesis narrative** | What would each help the teacher DO on Monday? |
| **Feedback-concern contradiction** | Pipeline feedback for Connor Walsh validates the colorblind framing that concern signals flagged |
| **Equity** | How each handles ESL (Maria), righteous anger (Destiny), non-standard grammar |

### Phase 2: Root Cause Analysis (add to comparison doc)

For each gap, trace to architectural cause:
- **Prompt problem?** → Fix template in `prompts.py`. Check whether prompts use engagement-frame language or detection-frame language — the 8B model's output quality is heavily shaped by prompt framing. A prompt that says "surface what the teacher needs to see about this student's engagement" produces different output than one that says "identify concerns."
- **Pipeline structure problem?** → Missing stage, wrong stage order, missing data flow
- **Broken mycorrhizal link?** → Stage N produces valuable signal but Stage N+1 doesn't receive it. The feedback-concern contradiction is the clearest example: concerns correctly flag colorblindness, but feedback (running later, without concern data) validates it. Map ALL inter-stage data flows and identify which links are broken.
- **8B model limitation?** → Too small to surface nuance in engagement patterns; consider what can be done non-LLM or through multi-pass strategies
- **Data flow problem?** → E.g., Quick Analysis clusters not passed to coding; concern signals not passed to feedback drafter
- **Methodology problem?** → Test data construction, incomplete pipeline run, stochastic variation
- **Framing problem?** → The engagement reframe is a both/and: engagement signals as primary product, detection capabilities retained for clear gaming. If a pipeline output uses pure detection language where engagement language would be more useful to the teacher, that's a framing fix.

**You have explicit permission to conclude that 8B is insufficient** — either for the whole pipeline or for specific components. If specific stages need a larger model, say so. If the distributed multi-call architecture can compensate, explain how. If there are hard limits, name them. The professor wants realistic assessment, not optimism.

### Phase 3: Refinement Plan (write to `docs/refinement_plan.md`)

Prioritized list of concrete changes. For each:
- **What**: Specific file + function to change
- **Why**: Which comparison gap it addresses (cite evidence)
- **How**: Implementation sketch (not full code, but enough to act on)
- **Equity check**: Who could this harm? How to mitigate?
- **Priority**: P0 = blocks demo, P1 = significant quality gap, P2 = nice to have

**Likely P0 items** (based on what we already know):
1. Assignment engagement detection — the pipeline must surface when students' work doesn't connect to the assignment's expected content area. This is the single most useful engagement signal the pipeline currently misses. (Non-LLM approach: TF-IDF overlap between submission and assignment prompt, wired into the Assignment Context Awareness mechanism described in `docs/engagement_reframe_learning.md`)
2. Feedback-concern consistency (broken mycorrhizal link) — the feedback drafter must receive concern signals from the concern detector. Currently these stages don't share data, so feedback validates the exact behavior concerns flagged. This is the pipeline's most damaging contradiction.
3. Cross-student similarity — surface both class-level patterns (embedding clusters already detected by QuickAnalyzer) AND near-duplicate pairs (>90% cosine similarity, e.g. Ethan Liu / Nadia Petrov verbatim match). Class-level surfaced as "this assignment had unusually high similarity — is the prompt eliciting diverse thinking?" Individual pairs surfaced only at very high thresholds, framed as factual observation, never verdict. Equity note: moderate similarity can reflect community cultural wealth, collaborative learning, or shared cultural knowledge — only surface individual pairs when the match is unmistakably copy/paste level.
4. Coding fidelity — don't attribute concepts the student never mentioned. When the pipeline codes David Park's phones-and-driving essay with "intersectionality in practice" at 0.8 confidence, that's a hallucination that misrepresents the student's engagement. Post-validate concepts_applied against actual submission text.
5. Inter-stage data flow (architectural) — wire Quick Analysis outputs (clusters, keyword hits, embedding position, sentiment) into coding prompts. Wire concern flags into feedback drafting. Wire cluster structure into theme generation. This is the mycorrhizal fix — the single structural change that addresses multiple quality gaps simultaneously.

### Phase 4: Update Documentation
- Update `docs/testing_observations.md` with comparison findings
- Update `docs/demo_expansion_plan.md` timing TBDs if they exist

## Critical Framing

**The 8B pipeline will NEVER match Opus on interpretive depth.** That's expected and acceptable. The pipeline's advantages are:
- Runs locally (FERPA-safe, no student data leaves the machine)
- Processes at scale (batch a whole class, not one paste at a time)
- Produces structured data the GUI can render (not just markdown)
- Runs overnight without API costs

**We want a specific assessment of interpretive depth differences.** Don't just say "8B can't match Opus" — characterize the gap precisely:
- What specific interpretive moves does Opus make that 8B doesn't?
- Which of those moves could be approximated through better prompting, multi-pass strategies, or non-LLM augmentation?
- Which are genuinely beyond 8B's capability?
- Where you're unsure, say so — surface the uncertainty so we can investigate together.

**When you hit a wall — surface it, don't mark it "uncertain."** This is a collaborative project. If you encounter something you can't resolve — a technical limit you're unsure about, a design tension between equity and detection, a question about whether an 8B behavior is fixable or inherent — don't just write "UNCERTAIN" and move on. Write up what you know, what you don't, what the tradeoffs look like, and surface it as a conversation for us to work through together. The professor has the pedagogical expertise and the Reframe Engine frameworks; you have the technical knowledge. Neither of us has the full picture alone. The best outcomes come from working the hard problems together, especially at the edges of an experimental system.

**The question is NOT "does it match Opus?" but "does it catch the structural patterns that help a teacher know what to do Monday morning?"** A teacher needs to know:
1. 19 students submitted the wrong assignment (topic mismatch) — *if this is real and not a data artifact*
2. Maria Ndiaye's work is exceptional (surface exemplary work)
3. Connor and Aiden are resisting the framework (concern signals)
4. Brittany is misreading intersectionality as diversity-celebration (pedagogical gap)
5. Jordan Kim may be struggling (check-in signal)
6. Multiple students produced near-identical or low-engagement responses (class-level similarity + individual near-duplicate surfacing for very high matches)
7. Some submissions show zero personal connection and generic academic register — disengaged regardless of whether AI was involved (Tyler Nguyen, Jaylen Carter, Alex Hernandez)

If the 8B pipeline catches these 7 things — even without Opus's eloquent prose — it's done its job. That's the optimization target.

**Both/and on detection**: The engagement frame is the primary lens, but detection capabilities are retained for clear gaming: smoking gun paste artifacts, near-identical submissions (pairwise at >90% similarity), and total disengagement across all dimensions. The student who pastes ChatGPT output into an Ethnic Studies discussion because they don't want to engage with the material should show up in the analysis — not because the system detected AI, but because the system detected zero engagement. If the smoking gun is also present (HTML tags, markdown formatting), flag that too. Teachers need both kinds of information.

**The experimental dimension**: This project is exploring whether a distributed intelligence model — a mycorrhizal network of networked 8B calls with careful orchestration — can approach the analytical depth of a single large model pass. The biological metaphor: fungi connect trees through underground networks, transferring nutrients and signals; each hyphal thread does small, local work, but the network produces forest-scale intelligence that no single organism possesses. The pipeline's per-student coding calls are the hyphal threads; the theme generation and synthesis are the emergent network intelligence. We're genuinely curious to what extent we can close the gap with Opus. When you identify limitations, think creatively about whether architectural solutions (inter-stage data flow, multi-pass strategies, chain-of-thought, non-LLM pre-processing, embedding-based augmentation) could compensate — especially the inter-stage data flow, which is the most direct mycorrhizal fix. But if there are hard technical limits, be realistic and name them. The professor would rather know the truth than hear optimism.

## Pipeline Timing Reference

| Stage | Time | % of Total |
|---|---|---|
| Quick Analysis (non-LLM) | 20s | <1% |
| Coding (29 students) | 2136s (36 min) | 32% |
| Concerns | 1310s (22 min) | 20% |
| Themes | 1673s (28 min) | 25% |
| Outliers | 91s | 1% |
| Synthesis | 409s (7 min) | 6% |
| Feedback | 901s (15 min) | 14% |
| **Total** | **6612s (1h50m)** | **228s/student** |
