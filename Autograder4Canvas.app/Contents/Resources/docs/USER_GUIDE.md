# Academic Dishonesty Check v2.0 - User Guide

## Philosophy: What This Tool Does (and Doesn't Do)

### This tool is a CONVERSATION STARTER, not a verdict.

It identifies patterns that MAY indicate academic dishonesty, but:
- It cannot prove AI use
- It cannot prove plagiarism
- It cannot determine intent
- It should NEVER be the sole basis for academic action

### What "Academic Dishonesty" Means Here

We use "academic dishonesty" rather than "AI detection" because:

1. **The pedagogical concern isn't AI itself** - it's whether students are the primary intellectual source of their work
2. **The same AI use can be legitimate or dishonest** depending on:
   - Assignment requirements
   - Disclosed vs. undisclosed use
   - Whether learning objectives were met
3. **Other forms of dishonesty matter too** - contract cheating, heavy peer assistance, copying from sources

### Core Values

1. **Learning over products** - The goal is student intellectual engagement, not polished output
2. **Context determines meaning** - Same patterns mean different things in different contexts
3. **Equity and inclusion** - Avoid false positives for ESL, first-gen, neurodivergent students
4. **Instructor judgment is final** - This tool supports, never replaces, human judgment

---

## Quick Start

### 1. Run the Tool

```bash
python Academic_Dishonesty_Check_v2.py
```

### 2. Choose Analysis Mode

The interactive menu offers:

1. **Analyze Canvas Assignment** - Batch analyze all submissions for an assignment
2. **Analyze Single Text** - Paste text for individual analysis
3. **View Assignment Profiles** - See available profiles and their settings
4. **About This Tool** - Philosophy and guidance

### 3. Select Assignment Profile

Choose the profile that matches your assignment type:

| Profile | Use For | Key Focus |
|---------|---------|-----------|
| `personal_reflection` | Journals, reflections, narratives | Missing personal voice |
| `analytical_essay` | Literary analysis, arguments | Missing textual engagement |
| `discussion_post` | Forum posts | Missing engagement with readings/classmates |
| `rough_draft` | First drafts | Excessive polish |
| `research_paper` | Cited research | Citation verification |
| `standard` | General/other | Balanced detection |

### 4. Review Results

Results are categorized by concern level:
- **HIGH** - Multiple strong indicators; conversation recommended
- **ELEVATED** - Notable patterns; worth attention
- **MODERATE** - Some indicators; monitor
- **LOW** - Minor patterns; likely authentic
- **NONE** - No concerning patterns detected

---

## Understanding the Analysis

### Two Score Types

1. **Suspicious Score** - Points for concerning patterns found
   - AI transition phrases ("It is important to note...")
   - Generic phrases ("Throughout history...")
   - Inflated vocabulary ("utilize" instead of "use")
   - Hedge phrases ("One might argue...")

2. **Authenticity Score** - Points for positive patterns found
   - Personal voice ("I remember when...")
   - Specific details (names, places, sensory language)
   - Emotional language ("I felt...")
   - Intellectual uncertainty ("I'm not sure if...")

### The Combination Matters

| Suspicious | Authenticity | Interpretation |
|------------|--------------|----------------|
| High | Low | **Most concerning** - AI markers without human voice |
| High | High | **Mixed** - May indicate partial AI use with genuine engagement |
| Low | High | **Likely authentic** - Strong personal voice |
| Low | Low | **Needs attention** - May be disengaged but not AI |

### Peer Comparison

When analyzing a full assignment, the tool compares each submission to the class:
- Identifies **statistical outliers** (top 5-10%)
- Adapts to the class's writing patterns
- Same score might be "high" in one class, "moderate" in another

---

## Having the Conversation

### Do NOT Say

❌ "The AI detector flagged your paper"
❌ "This looks like ChatGPT wrote it"
❌ "You need to prove you wrote this"

### DO Say

✅ "I'd like to understand your writing process better"
✅ "Can you walk me through how you developed this argument?"
✅ "I noticed some patterns I wanted to ask you about"

### Suggested Conversation Starters

**For personal reflections:**
- "Can you tell me more about this experience?"
- "What details do you remember most vividly?"
- "How did this experience affect you?"

**For analytical essays:**
- "Which passage in the text led you to this interpretation?"
- "Can you show me where you found this evidence?"
- "What other interpretations did you consider?"

**For research papers:**
- "Can you show me this source?"
- "How did you find this research?"
- "What database did you use?"

### Process Questions

These are hard to answer if work isn't authentic:
- "What was hardest about writing this?"
- "Did your thesis change as you wrote?"
- "What did you cut from earlier drafts?"
- "What would you change if you had more time?"

---

## Context Adjustments

### Why Context Matters

The same patterns mean different things for different students:

| Pattern | Standard Interpretation | ESL Student | First-Gen Student |
|---------|------------------------|-------------|-------------------|
| "Furthermore" | AI transition marker | Taught in grammar class | Taught in dev English |
| Formal vocabulary | May be inflated | Language learning | Following models |
| Perfect grammar | Unusual for drafts | May use intensive editing | May use Grammarly |
| Formulaic structure | Lacks originality | Following learned models | Following templates |

### Community College Settings

The default profile (`community_college`) adjusts for:
- **45% ESL** - Reduces weight of formal transitions
- **60% First-Gen** - Reduces weight of formulaic structure
- **75% Working Students** - Context notes about time constraints

### ESL Positive Indicators

These errors suggest human authorship (AI doesn't make them):
- Article errors ("a" before vowels, missing articles)
- Preposition errors ("depend of," "arrive to")
- Word form errors ("importancy," "educative")
- L1 transfer patterns

If you see formal vocabulary WITH these errors, it's likely an ESL student using a thesaurus, not AI.

### Creating Custom Profiles

Copy `INSTITUTION_TEMPLATE.yaml` and customize:
- Demographics for your institution
- Marker weight adjustments
- Threshold settings
- Institution-specific notes

---

## Assignment Profiles in Detail

### Personal Reflection

**Detection approach:** Look for what's MISSING

Key indicators of concern:
- No first-person voice
- No specific details (names, places, times)
- No emotional language
- Generic statements that could apply to anyone

A personal reflection without personal elements has failed to meet the assignment's learning objectives, regardless of how it was produced.

### Analytical Essay

**Detection approach:** Look for engagement with texts

Key indicators of concern:
- No direct quotes or page references
- Analysis that could apply to any text
- No specific textual evidence
- Generic literary analysis language

Verify by asking: "Can you show me the passage you're analyzing here?"

### Discussion Post

**Detection approach:** Look for engagement with class

Key indicators of concern:
- Could be posted to any discussion anywhere
- No reference to specific reading content
- No reference to classmates
- Reads like a formal essay, not a post

Discussion posts should sound like posts, not essays.

### Rough Draft

**Detection approach:** Look for excessive polish

Key indicators of concern:
- "Draft" reads as polished final product
- Perfect grammar throughout
- Fully formed structure
- No revision markers or rough sections

Real drafts have rough edges. Too-perfect drafts may not be authentic drafts.

### Research Paper

**Detection approach:** Verify citations

Key actions:
- Spot-check 2-3 citations
- Verify at least one quote matches source
- Check that authors and journals exist
- Ask student to produce the actual source

AI frequently fabricates citations - this is strong evidence if found.

---

## Report Interpretation

### Concern Level Meanings

**HIGH CONCERN**
- Multiple strong indicators
- Recommended action: Have a conversation
- Do not assume dishonesty - investigate

**ELEVATED CONCERN**
- Notable patterns present
- Recommended action: Pay attention, may warrant conversation
- Consider assignment type and student context

**MODERATE CONCERN**
- Some indicators present
- Recommended action: Monitor, note for patterns across work
- May not warrant immediate action

**LOW/NONE**
- Few or no concerning patterns
- No action needed
- Note: Absence of flags doesn't prove authenticity

### Report Sections

1. **Summary Statistics** - Class overview, outlier count
2. **High Concern Submissions** - Detailed analysis, conversation starters
3. **Peer Comparison** - Where each submission falls relative to class
4. **Context Notes** - Adjustments applied, ESL indicators found

---

## Best Practices

### Before the Assignment

1. **Be clear about AI policy** in syllabus and assignment
2. **Design for authenticity** - assignments requiring specific personal knowledge
3. **Use scaffolded assignments** - drafts, outlines, reflections
4. **Consider process documentation** - notes, sources, revision history

### During Analysis

1. **Use appropriate profile** for assignment type
2. **Consider student context** - ESL, first-gen, etc.
3. **Look at patterns across work** - one flag isn't definitive
4. **Trust your knowledge** of the student

### After Analysis

1. **Start with conversation**, not accusation
2. **Ask process questions** - hard to answer if not authentic
3. **Consider explanations** - there may be legitimate ones
4. **Document carefully** if pursuing academic integrity process
5. **Reflect on assignment design** - how can future assignments encourage authenticity?

---

## Limitations

This tool CANNOT:
- Prove AI use definitively
- Detect all forms of AI assistance
- Account for legitimate AI use that was disclosed
- Replace instructor judgment
- Distinguish between AI use and contract cheating
- Detect AI use that has been heavily edited

False positives are possible for:
- ESL students
- Students who learned formulaic writing
- Neurodivergent students
- Students using grammar tools
- Strong writers who happen to write formally

False negatives are possible for:
- AI output that has been edited
- AI output in student's natural voice (via prompting)
- Selective AI use (some sections only)

---

## Ethical Considerations

1. **Presumption of innocence** - Flags are not verdicts
2. **Equity** - Ensure diverse students aren't disproportionately flagged
3. **Transparency** - Be clear with students about how work is evaluated
4. **Proportionality** - Response should match severity
5. **Learning focus** - Goal is education, not punishment

---

## Getting Help

- **Documentation issues:** Check README.md
- **Technical problems:** Verify Python and dependencies
- **Interpretation questions:** Focus on conversation, not accusation
- **False positive concerns:** Adjust context profile or thresholds

---

*This tool supports academic integrity; it does not replace the judgment of educators who know their students and context.*
