# Pipeline Gaps: System A → System B Parity Plan

**Date**: 2026-03-25
**Source**: `system_comparison_old_vs_new.md` + session findings
**Baseline**: Gemma 12B MLX, synthesis-first architecture

---

## Priority 1: Observation-Only Concern Architecture (VALIDATED)

**Status**: Validated 2026-03-25. 32/32 correct readings, zero deficit framing
on protected students. Synthesis pass produces teacher-usable summary (817 words,
class temperature + threads + exceptional contributions + check-ins + class
conversation). Ready for pipeline integration.
**Problem**: Binary FLAG/CLEAR is structurally unsalvageable on 12B. 3 FP without
context, 6 FP + lost true positive with context. Students of color writing about
lived experience bear the cost.

**Design**: Hybrid — narrow crisis check (binary, high threshold, no context) +
open observation (generative, every student, with class context). Teacher sees
observations, not flags. Classification stays with the human.

**Validates**: Insight 5 (generative > classificatory)

---

## Priority 2: Executive Summary Narrative

**Status**: Partially addressed by synthesis pass. Class temperature section
works. Needs: more specific student examples pulled through (the per-student
observations have the specificity; synthesis compresses it too much). Also needs
pedagogical significance framing ("why this matters for this class at this
moment"). Prompt iteration, not architecture change.
**Problem**: System A produces 2-3 paragraphs for "a tired professor." System B
produces `class_temperature` (1 sentence) + `attention_areas` (list).

**Approach**: Expand guided synthesis to produce 300-500 word narrative. Chatbot
export prompt templates (`chatbot_export.py`) already have the structure — reuse
for local synthesis-only output. Sections: What your students said, emergent
themes, tensions & contradictions, surprises.

**Effort**: Small — prompt exists, just needs a local-only codepath

---

## Priority 3: Forward-Looking Component

**Status**: Not started
**Problem**: System A's "What This Tells Us for Week X+1" is among its most
actionable sections. System B has nothing forward-looking.

**Approach**: Add optional "What's coming next week?" text field to run wizard.
Flows into synthesis prompt: "Given these findings, and knowing that next week
covers [teacher input], what should the teacher be aware of?" On Tier 1 (local),
12B produces functional but basic planning. On Tier 2-3, cloud enhancement
produces richer pedagogical recommendations.

**Effort**: Medium — wizard UI change + synthesis prompt modification

---

## Priority 4: Multiplicity Narrative

**Status**: Not started
**Problem**: System A categorizes HOW students enter the material differently
(format choices, archive entry points, emotional registers, application modes)
and narrates it as a positive pedagogical outcome. System B has the data
(emotional_register, readings_referenced, personal_connections, embedding
clusters) but doesn't assemble it.

**Approach**: After coding stage, add a synthesis call that receives the
distribution of these fields and produces a narrative: "Students entered through
X different registers this week — [list]. The strongest analytical work came
from students who [pattern]."

**Effort**: Small-medium — data exists, needs aggregation + prompt

---

## Priority 5: Pedagogical Wins

**Status**: Not started
**Problem**: System A explicitly names what's working ("the multiplicity is
producing exactly the kind of diverse engagement the assignment was designed
for"). System B doesn't surface positives.

**Approach**: Reframe existing `engagement_highlights` from guided synthesis
as wins. Add framing prompt: "Based on these patterns, what is working well
in this assignment's design?" Include in executive summary narrative (P2).

**Effort**: Small — mostly a prompt framing change within P2

---

## Priority 6: Questions/Confusions Category

**Status**: Not started
**Problem**: System A surfaces logistical issues (assignment format confusion,
submission problems, LLM artifact patterns). System B has no equivalent.

**Approach**: Add to per-student coding prompt: "Does this student appear
confused about the assignment expectations, as distinct from choosing not to
engage deeply? Note any logistical or format issues." Aggregate in synthesis.

**Effort**: Small — prompt addition to coding stage

---

## Priority 7: Elevated Individual Insights

**Status**: Partially covered
**Problem**: System A's "Particularly Insightful Points" elevates 5-8 students
with extended quotes + pedagogical analysis. System B has `notable_quotes` +
`what_student_is_reaching_for` but doesn't elevate them to teacher attention.

**Approach**: After coding, rank students by a composite of: quote richness,
`what_reaching_for` depth, emotional register diversity, concept application.
Surface top 5-8 in the executive summary narrative. This is the observation-only
architecture's positive counterpart — "what I noticed" for exceptional work.

**Effort**: Medium — depends on P1 (observation architecture) and P2 (narrative)

---

## Additional testing needed

### Subtle recentering moves (Tuck & Yang, DiAngelo, Bonilla-Silva)
Add test students to corpus with patterns that recenter whiteness/masculinity/
heteronormativity through reasonable-sounding language:
- Abstract liberalism ("everyone should be treated equally")
- Settler innocence ("my family wasn't involved in that")
- Move to innocence ("let's focus on solutions, not blame")
- Progress narrative ("things have gotten a lot better")
- Tone policing (already tested via S025 Aiden Brooks)
- Colorblind ideology (already tested via S018 Connor Walsh)

These should be surfaced as pedagogical moments in observations, not flagged
as concerns. The teacher needs the MECHANISM articulated — why does this
reasonable-sounding statement enact harm? Tested: 12B CAN produce this
explanation when prompted specifically (see tone policing test, session notes).

### Alternative hypothesis tests (queued, /tmp/alt_hypothesis_tests.py)
- Test A: Temperature/consistency (5 runs × 2 students)
- Test B: Best possible concern prompt (does classification STILL fail?)
- Test C: Length effect (does 100-word justification still show disparate impact?)

Run AFTER full pipeline integration.

---

## Technical debt: dual pipeline implementation

**Status**: Known issue, not yet fixed
**Problem**: `scripts/generate_demo_insights.py` reimplements the pipeline
independently of `src/insights/engine.py`. Both have their own stage ordering,
backend selection, concern detection wiring, and now observation stages. This
creates a multiple-sources-of-truth problem: changes to the engine don't
automatically apply to the demo generator and vice versa.

**Impact**: May explain quality degradation between isolated tests (which run
through the demo generator) and integrated tests (which run through the engine).
Round 2 → integration quality drops could be partly caused by this divergence.

**Fix**: Refactor demo generator to call `engine.py` methods directly, passing
pre-loaded texts instead of going through the data fetcher. Engine needs a
`run_from_texts()` method that accepts a dict of {student_id: text} rather than
fetching from Canvas API.

**Effort**: Medium-large — engine is tightly coupled to the data fetcher. But
this is critical infrastructure for testing reliability.

---

## Not a gap (System B advantages to preserve)

- Synthesis-first class reading
- Reading-first per-student coding + `what_student_is_reaching_for`
- Anti-bias post-processing (3 layers)
- Linguistic justice infrastructure (sentiment suppression, word budget boost)
- FERPA compliance (architectural, not behavioral)
- Structured persistence + cross-run trajectories
- Transparency (confidence scores, cross-validation, visible reasoning)
- AIC integration as engagement signal
