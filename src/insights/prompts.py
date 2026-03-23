"""
Prompt templates for the Insights Engine LLM pipeline.

THIS IS THE MOST IMPORTANT FILE IN PHASE 2.

Design principles (from spec Section XV):
  1. Teacher-oriented framing in every prompt
  2. Few-shot examples, not abstract instructions
  3. Decompose by cognitive skill for Lightweight tier
  4. Output as JSON matching the Pydantic models
  5. Student names, verbatim quotes, preserve tensions
  6. Political urgency about injustice is appropriate engagement, not a concern
  7. Course content ≠ student wellbeing: students discussing violence, trauma,
     or injustice AS COURSE MATERIAL are doing the assignment, not in distress

Every prompt instructs the model to:
  - Use student names (never "Student 1")
  - Include verbatim quotes (not paraphrases)
  - Preserve tensions and contradictions (not smooth them)
"""

# ---------------------------------------------------------------------------
# System prompt (shared across all calls)
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = (
    "You are helping a teacher understand what their students learned this "
    "week. The teacher needs to know: what are students actually saying? "
    "What concepts are they grappling with? What is surprising or notable? "
    "What might need the teacher's attention?\n\n"
    "Always use student names. Always include verbatim quotes. "
    "Preserve tensions and contradictions — they are pedagogically productive, "
    "not problems to smooth away. Political urgency about injustice is "
    "appropriate academic engagement, not a concern.\n\n"
    "IMPORTANT: Many courses study difficult topics — violence, genocide, "
    "sexual assault, colonialism, slavery, trauma. Students writing about "
    "these topics are engaging with course material, not expressing personal "
    "distress. Never confuse disturbing SUBJECT MATTER with student WELLBEING "
    "concerns.\n\n"
    "Respond ONLY with valid JSON matching the requested schema."
)

# ---------------------------------------------------------------------------
# Pass 1a: Comprehension (Lightweight tier, call 1)
# ---------------------------------------------------------------------------

COMPREHENSION_PROMPT = """\
Read this student submission carefully. Your job is reading comprehension — \
understand what the student is saying.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}

NON-LLM ANALYSIS (grounding context — verify against the text):
- Emotional register signal: {vader_compound} ({vader_polarity}){top_emotions} ⚠ Signal misreads AAVE, ESL writing,
  and righteous anger — treat as rough signal only, not ground truth.
- Keyword hits: {keyword_hits}
- Embedding cluster: {cluster_id}
{signal_matrix_context}
SUBMISSION TEXT:
---
{submission_text}
---
{profile_fragment}
Respond with JSON:
{{
  "student_name": "{student_name}",
  "readings_referenced": ["specific texts or authors the student mentions"],
  "concepts_applied": ["course concepts the student uses or engages with"],
  "personal_connections": ["how the student connects to personal experience"],
  "current_events_referenced": ["external events the student references"],
  "notable_quotes": [
    {{
      "text": "exact verbatim quote from the student",
      "significance": "why this quote matters (one sentence)"
    }}
  ]
}}

Select 1-2 verbatim quotes that best capture the student's thinking. \
If the student doesn't reference readings or make personal connections, \
return empty lists — don't guess.

EXAMPLE (for a different student and assignment):
{{
  "student_name": "Maria Santos",
  "readings_referenced": ["Omi and Winant's Racial Formations"],
  "concepts_applied": ["racial formation", "racialization"],
  "personal_connections": ["grandmother's experience immigrating from Mexico"],
  "current_events_referenced": ["Watsonville ICE raids"],
  "notable_quotes": [
    {{
      "text": "When Omi and Winant talk about racial projects, I think about how my abuela describes becoming 'Mexican' only after crossing the border",
      "significance": "Connects abstract theory to lived family experience"
    }}
  ]
}}"""

# ---------------------------------------------------------------------------
# Pass 1b: Interpretation (Lightweight tier, call 2)
# ---------------------------------------------------------------------------

INTERPRETATION_PROMPT = """\
You already read {student_name}'s submission. Here is what you found:

COMPREHENSION RESULTS:
{comprehension_json}

ASSIGNMENT PROMPT: {assignment_prompt}
{teacher_interests}
SUBMISSION TEXT:
---
{submission_text}
---

{profile_fragment}
Now assess the student's engagement. Respond with JSON:
{{
  "theme_tags": ["1-5 open-vocabulary theme labels for this submission"],
  "theme_confidence": {{"theme_label": 0.8}},
  "emotional_register": "one of: analytical, passionate, personal, urgent, reflective, disengaged",
  "emotional_notes": "brief explanation of why you chose this register"
}}

Theme tags should be specific and descriptive ("connecting theory to family \
history", "confusion about racial projects") not generic ("engagement", \
"response"). If unsure about a theme, give it lower confidence (0.3-0.5).
{lens_fragment}
EXAMPLE:
{{
  "theme_tags": ["connecting theory to family history", "racialization as process"],
  "theme_confidence": {{"connecting theory to family history": 0.9, "racialization as process": 0.7}},
  "emotional_register": "personal",
  "emotional_notes": "Student writes from deep personal connection to grandmother's story, emotional but analytically grounded"
}}"""

# ---------------------------------------------------------------------------
# Pass 1 combined: Coding (Medium/Deep tier, single call)
# ---------------------------------------------------------------------------

CODING_FULL_PROMPT = """\
Read this student submission and produce a structured coding record. \
You are helping a teacher understand what this student is thinking.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}
{teacher_interests}
PRE-COMPUTED SIGNALS (floor — your analysis should go beyond these):
- Emotional register signal: {vader_compound} ({vader_polarity}){top_emotions} ⚠ Signal misreads AAVE, ESL writing,
  and righteous anger. Your emotional_register judgment supersedes this score.
- Keyword hits: {keyword_hits}
- Embedding cluster: {cluster_id}
{signal_matrix_context}
SUBMISSION TEXT:
---
{submission_text}
---

Respond with JSON:
{{
  "student_name": "{student_name}",
  "theme_tags": ["1-5 specific theme labels"],
  "theme_confidence": {{"tag": 0.0-1.0}},
  "notable_quotes": [
    {{"text": "verbatim quote", "significance": "why it matters"}}
  ],
  "emotional_register": "analytical|passionate|personal|urgent|reflective|disengaged",
  "emotional_notes": "brief explanation",
  "readings_referenced": ["specific texts/authors"],
  "concepts_applied": ["course concepts used"],
  "personal_connections": ["connections to lived experience"],
  "current_events_referenced": ["external events referenced"]
}}

{profile_fragment}
RULES:
- Use {student_name}'s actual name, never "the student" or "Student 1"
- Quotes must be VERBATIM from the submission — do not paraphrase
- Theme tags should be specific ("confusion about racial projects") not \
generic ("engagement")
- If unsure, leave fields as empty lists — don't invent content
- Select up to 3 notable quotes that best capture their thinking
- The pre-computed signals are a floor. Surface patterns, tensions, and insights \
the keyword taxonomy and sentiment scores cannot capture — unexpected connections, \
rhetorical moves, cultural knowledge, structural critique
- Emotional register signal is a rough baseline only. Your reading of the text supersedes it
{lens_fragment}
EXAMPLE (different student and assignment):
{{
  "student_name": "David Kim",
  "theme_tags": ["interrogating colorblindness", "personal reckoning with privilege"],
  "theme_confidence": {{"interrogating colorblindness": 0.85, "personal reckoning with privilege": 0.7}},
  "notable_quotes": [
    {{
      "text": "I used to think not seeing race was progressive until this reading made me realize it was just comfortable",
      "significance": "Shows genuine intellectual shift — student confronting previous assumptions"
    }}
  ],
  "emotional_register": "reflective",
  "emotional_notes": "Thoughtful self-examination, vulnerability about prior beliefs",
  "readings_referenced": ["Bonilla-Silva's color-blind racism framework"],
  "concepts_applied": ["color-blind racism", "racial privilege"],
  "personal_connections": ["growing up in predominantly white suburb"],
  "current_events_referenced": []
}}"""

# ---------------------------------------------------------------------------
# Concern detection (ALWAYS separate, any tier)
# ---------------------------------------------------------------------------

CONCERN_PROMPT = """\
Review this student submission for passages that might need the teacher's \
attention. You are looking for signs of STUDENT WELLBEING issues or \
language that essentializes or dismisses groups.

STUDENT: {student_name}
ASSIGNMENT PROMPT: {assignment_prompt}

NON-LLM SIGNAL MATRIX RESULT:
{signal_matrix_result}

SUBMISSION TEXT:
---
{submission_text}
---

CRITICAL INSTRUCTIONS — READ VERY CAREFULLY:

THE MOST IMPORTANT DISTINCTION: You must distinguish between COURSE CONTENT \
and STUDENT WELLBEING. Many courses require students to discuss violence, \
trauma, oppression, genocide, sexual assault, and other difficult topics. \
A student writing ABOUT these topics is doing the assignment, not expressing \
personal distress. Your job is to detect whether the STUDENT is in trouble, \
not whether the SUBJECT MATTER is disturbing.

COURSE CONTENT vs. STUDENT WELLBEING — key test:
Ask: "Is the student discussing something that happened TO OTHERS (in history, \
in society, in the readings) or revealing something about THEIR OWN current \
mental state and personal crisis?"

Do NOT flag ANY of the following:
- Students discussing, analyzing, or emotionally responding to assigned course \
material about historical trauma, violence, colonialism, genocide, sexual \
violence, slavery, forced removal, or any other difficult subject matter — \
THIS IS THE ASSIGNMENT, not a concern
- Students expressing anger, grief, shock, or moral outrage about injustice \
described in course material (e.g. "It's crazy that this happened", "this \
makes me sick", "I can't believe this was legal")
- Students using words like "triggered", "overwhelming", or "hard to read" \
when describing their emotional response to difficult course material — this \
is emotional engagement with the assignment, not clinical distress
- Students expressing anger about racism, structural violence, or injustice \
(this is appropriate academic engagement)
- Students describing their own experiences with discrimination
- Students critiquing institutional racism, policing, or immigration enforcement
- Students using urgent or passionate language about justice issues
- Students whose writing style differs from academic English conventions
- Students using colloquial intensifiers like "crazy", "insane", "wild" when \
reacting to course content

DO flag:
- Language that essentializes racial or ethnic groups ("all X people...", \
"they always...", "those people")
- Colorblind claims ("I don't see race", "not about race", "reverse racism")
- Dismissal of other students' lived experiences
- Tone policing ("too angry", "too emotional", "calm down")
- Student revealing PERSONAL crisis: expressions of hopelessness about their \
OWN life, self-harm ideation, feeling unable to continue, requests for help \
that go beyond the academic context
- Student language that shifts from discussing course material to discussing \
their own inability to cope as a PERSON (not just "this reading was hard" \
but "I don't know how to keep going")

HOW TO TELL THE DIFFERENCE — examples:
- "This makes me angry" about historical injustice → ENGAGEMENT, not a concern
- "I can't do this anymore" about their own life → POTENTIAL CONCERN
- "This passage about rape was triggering" → emotional engagement with material
- "I feel like nobody would care if I disappeared" → POTENTIAL CONCERN
- "It's crazy how they treated Native women" → discussing course content
- "Reading about this violence was really heavy" → processing difficult material
- "I haven't been able to get out of bed and I don't see the point" → CONCERN

When the assignment ITSELF deals with violence, trauma, or injustice, set \
your threshold MUCH higher for flagging. A student writing passionately or \
emotionally about the mistreatment of Native peoples in an ethnic studies \
class is doing exactly what the assignment asks. Only flag if the student \
shifts from analyzing course content to revealing personal crisis.

The non-LLM analysis classified this submission as shown above. Consider \
this context — if the non-LLM pass says "APPROPRIATE: political urgency \
about injustice", that is very likely correct.
{profile_fragment}

Respond with JSON:
{{
  "concerns": [
    {{
      "flagged_passage": "exact text from the submission",
      "surrounding_context": "2-3 sentences around the flagged passage",
      "why_flagged": "brief explanation",
      "confidence": 0.0-1.0
    }}
  ]
}}

If no concerns, return: {{"concerns": []}}

EXAMPLE of what IS a concern (essentializing language):
{{
  "concerns": [
    {{
      "flagged_passage": "I don't see why we keep talking about race, everyone is equal now",
      "surrounding_context": "The student was responding to the Omi and Winant reading. They wrote: 'I don't see why we keep talking about race, everyone is equal now. My family worked hard and succeeded without any special treatment.'",
      "why_flagged": "Colorblind ideology — dismisses structural racism. Teacher may want to engage this student with specific evidence.",
      "confidence": 0.75
    }}
  ]
}}

EXAMPLE of what IS a concern (student wellbeing):
{{
  "concerns": [
    {{
      "flagged_passage": "I honestly don't know why I'm still doing any of this",
      "surrounding_context": "After a paragraph analyzing the reading, the student wrote: 'I honestly don't know why I'm still doing any of this. Nothing feels like it matters anymore. I'm just going through the motions.'",
      "why_flagged": "Student shifts from course analysis to expressing personal hopelessness. May indicate wellbeing issue beyond the assignment. Teacher should check in.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what is NOT a concern (engaging with difficult material):
A student in an ethnic studies class writes: "Reading about the rape and \
murder of Native women made me feel sick. It's crazy that this is still \
happening and nobody talks about it. This passage was really triggering \
but I'm glad we're learning about it." — This is a student processing \
difficult course material with appropriate emotional engagement. Do NOT \
flag this.

EXAMPLE of what is NOT a concern (passionate engagement):
"The system of white supremacy in this country makes me furious. How can \
we read about redlining and NOT be angry?" — This is appropriate engagement. \
Do NOT flag this.

EXAMPLE of what IS a concern (scientific-sounding essentialism):
{{
  "concerns": [
    {{
      "flagged_passage": "certain populations are just genetically predisposed to these health outcomes",
      "surrounding_context": "In a reflection on health disparities, the student wrote: 'I think certain populations are just genetically predisposed to these health outcomes. It's not really about access or racism, it's biology.'",
      "why_flagged": "Biological essentialism — attributes health disparities to genetics rather than engaging with structural determinants (housing, pollution, food access, insurance, provider bias). Teacher may want to direct student to evidence on social determinants.",
      "confidence": 0.8
    }}
  ]
}}

EXAMPLE of what IS a concern (pathologizing cultural practices):
{{
  "concerns": [
    {{
      "flagged_passage": "that kind of parenting would be considered neglect in our culture",
      "surrounding_context": "Responding to a case study on child development, the student wrote: 'The family's approach to discipline seems really unhealthy. That kind of parenting would be considered neglect in our culture. I think the child clearly has attachment issues because of it.'",
      "why_flagged": "Pathologizes a cultural parenting practice using Western diagnostic frameworks as universal norm. Student also diagnoses a child from surface description. Teacher may want to discuss cultural context in developmental assessment.",
      "confidence": 0.7
    }}
  ]
}}

EXAMPLE of what is NOT a concern (community health knowledge):
A nursing student writes: "My grandmother always used teas and remedios for \
everything, and honestly some of the pharmacology we're learning makes me \
think she wasn't wrong. My family doesn't trust hospitals because of how \
they treated my tío." — This student is integrating community health knowledge \
with clinical learning and naming a rational response to medical mistreatment. \
Do NOT flag this.

EXAMPLE of what is NOT a concern (lived expertise in a studied context):
A psychology student writes: "As someone who is autistic, I find it really \
frustrating that the textbook frames ASD as a list of deficits. My brain \
works differently, not worse." — This student is contributing expertise from \
lived experience and challenging the medical model. Do NOT flag this."""

# ---------------------------------------------------------------------------
# Deepening pass (Stage 4b — flagged students only, experimental)
# ---------------------------------------------------------------------------
# Runs ONLY when a concern was flagged in Stage 5. Asks the 8B to:
#   1. Name the rhetorical strategy precisely (not just repeat the concern category)
#   2. Reconsider emotional register given the concern context
#   3. Surface theme tags that may be in tension with the concern
#
# Design constraints:
#   - Righteous anger about injustice must NOT be reframed as "defensive" or "uncomfortable"
#     The concern detector already protects this — if no concern was flagged, this pass
#     never runs for that student.
#   - "Passionate" for Destiny Williams is correct — she has no concern flag.
#   - Analysis is for the teacher, not a verdict on the student.
#   - Only revise register with specific textual evidence.

DEEPENING_PROMPT = """\
You have already analyzed {student_name}'s submission. A concern was flagged. \
Now reconsider the coding in light of that concern.

ORIGINAL CODING (what you found in Stage 1):
{coding_summary}

CONCERN FLAGGED:
Passage: "{flagged_passage}"
Why flagged: {why_flagged}

SUBMISSION TEXT:
---
{submission_text}
---

Three questions:

1. RHETORICAL STRATEGY — What is this student doing with language?
   Name the move precisely. Not just the concern category ("colorblind framing"), \
but the specific rhetorical move the student is making.
   Examples of named moves:
   - "invokes personal respect for all people to sidestep structural analysis"
   - "celebrates cultural diversity while assigning fixed traits to groups"
   - "acknowledges historical injustice then frames it as resolved to avoid present analysis"
   - "uses open-mindedness language ('I don't see race') to resist a structural lens"
   - "tone-polices by reframing structural anger as unproductive emotion"
   - "challenges the framework's scope without dismissing it entirely"

2. EMOTIONAL REGISTER — Is "{current_register}" accurate given the concern?
   Smaller models sometimes assign "analytical" or "passionate" when the concern \
context suggests a more precise register.
   Available registers: analytical, passionate, personal, urgent, reflective, \
disengaged, defensive, confused, uncomfortable
   Only revise if you can point to specific language in the submission \
that supports the change. Many registers are correct even with a concern — \
"defensive" and "analytical" are very different, and getting it wrong \
misrepresents the student.

3. THEME TENSIONS — Are any of these theme tags in tension with the flagged concern?
   Current theme tags: {theme_tags_str}
   A tension exists when a theme tag appears to celebrate or validate the same \
behavior the concern flagged — for example, "celebrating cultural diversity" as \
a theme tag alongside a concern about essentializing language.

Respond with JSON:
{{
  "rhetorical_strategy": "one precise sentence describing the student's rhetorical move",
  "revised_register": "{current_register}",
  "register_change_reason": "",
  "theme_tensions": []
}}

RULES:
- If "{current_register}" is still accurate, keep it — do not change just because \
a concern was flagged. Concerned students can still be "analytical."
- If you revise the register, register_change_reason must contain the specific \
language from the submission that supports the change.
- theme_tensions contains only the exact theme tag strings from the list above \
that validate the flagged behavior. Empty list if none do.
- No moralistic language. This analysis is for the teacher's professional judgment."""

# ---------------------------------------------------------------------------
# Theme generation
# ---------------------------------------------------------------------------

THEME_GENERATION_PROMPT = """\
You are helping a teacher understand what their class said this week. Below \
are structured coding records for {n_records} student submissions. Identify \
the themes that emerge.

ASSIGNMENT: {assignment_name}
{teacher_interests}
CODING RECORDS (JSON):
{records_json}

Respond with JSON:
{{
  "themes": [
    {{
      "name": "specific, descriptive theme name",
      "description": "2-3 sentences describing this theme",
      "frequency": 0,
      "student_ids": ["id1", "id2"],
      "supporting_quotes": [
        {{"text": "verbatim quote", "significance": "why it matters"}}
      ],
      "confidence": 0.0-1.0,
      "sub_themes": ["optional sub-theme names if this theme has meaningful subdivisions"]
    }}
  ],
  "contradictions": [
    {{
      "description": "what the tension is",
      "side_a": "one position",
      "side_a_students": ["ids"],
      "side_b": "opposing position",
      "side_b_students": ["ids"],
      "pedagogical_significance": "why this tension matters for teaching"
    }}
  ]
}}

{profile_fragment}
RULES:
- Generate 3-8 themes. Specific names, not generic ("confusion about racial \
projects" not "confusion")
- Use student names in descriptions and quotes — never "Student 1" or \
"some students"
- Contradictions are FIRST-CLASS output. When students disagree, that is \
pedagogically important. Surface it. "Some students found the reading \
transformative while others found it alienating" — name who, and preserve \
both sides.
- Include 2-4 supporting quotes per theme (verbatim from the records)
- Themes should cover most submissions. If a submission doesn't fit any \
theme, that's fine — the outlier pass will handle it.
- Frequency = how many students, not how many mentions
{lens_fragment}
EXAMPLE theme:
{{
  "name": "connecting racial formation to family immigration",
  "description": "Multiple students connected Omi and Winant's framework to their families' experiences of racialization through immigration. Students described how family members were categorized differently before and after crossing borders.",
  "frequency": 8,
  "student_ids": ["101", "105", "112", "118", "122", "131", "138", "144"],
  "supporting_quotes": [
    {{
      "text": "My abuela says she didn't become 'Mexican' until she came to California",
      "significance": "Illustrates racialization as a process, not an identity"
    }}
  ],
  "confidence": 0.9,
  "sub_themes": ["maternal family narratives", "border as racial boundary"]
}}"""

# ---------------------------------------------------------------------------
# Theme meta-synthesis (for hierarchical grouping in Lightweight tier)
# ---------------------------------------------------------------------------

THEME_META_SYNTHESIS_PROMPT = """\
You are merging theme analyses from {n_groups} groups of student submissions \
into a single unified theme set. Some themes may appear across groups — \
merge them. Some may be unique to one group — preserve them.

ASSIGNMENT: {assignment_name}
{teacher_interests}
THEME SETS TO MERGE:
{theme_sets_json}

Respond with the same JSON format as the theme generation prompt — a single \
unified theme set with merged themes and contradictions.

{profile_fragment}
RULES:
- Merge similar themes across groups (combine student lists, quotes, frequencies)
- NEVER drop a theme just because it appeared in only one group — unique themes \
are often the most important findings
- Within a merged theme, preserve DIVERSITY — if students approach the same theme \
through different entry points (personal experience vs academic analysis vs current \
events), note that range, don't flatten it into one description
- Contradictions from different groups about the SAME topic should be merged
- Contradictions about DIFFERENT topics should both be preserved
- NEW contradictions may emerge when groups are combined — if Group 1's dominant \
theme conflicts with Group 3's dominant theme, that's a finding, not a merge error
- After merging, re-evaluate confidence based on how consistent the theme is \
across groups (appears in all groups = high confidence)
- Student names and verbatim quotes must be preserved through the merge
- If a theme has sub-themes or notable variation within it, use the sub_themes \
field to capture that variation rather than collapsing it"""

# ---------------------------------------------------------------------------
# Outlier analysis
# ---------------------------------------------------------------------------

OUTLIER_ANALYSIS_PROMPT = """\
These student submissions did not fit neatly into the themes identified \
for this assignment. For each, explain why it is notable and how it relates \
to (or challenges) the themes.

ASSIGNMENT: {assignment_name}

IDENTIFIED THEMES:
{themes_summary}

OUTLIER SUBMISSIONS:
{outliers_json}

Respond with JSON:
{{
  "outliers": [
    {{
      "student_id": "id",
      "student_name": "name",
      "why_notable": "what this submission says that nobody else said",
      "relationship_to_themes": "how it relates to or challenges the identified themes",
      "notable_quote": {{
        "text": "verbatim quote",
        "significance": "why it matters"
      }},
      "teacher_recommendation": "check in, highlight in class, worth discussing, etc."
    }}
  ]
}}

Remember: outliers are often the most pedagogically important findings. \
A student who sees something nobody else sees may be ahead of the class, \
or may need support. Use the student's actual name and their own words."""

# ---------------------------------------------------------------------------
# Synthesis — tier-differentiated
# ---------------------------------------------------------------------------

_SYNTHESIS_SECTIONS = """\
Generate a JSON report with these section keys:
{{
  "sections": {{
    "what_students_said": "Executive summary — the most important patterns, \
primary concern, biggest win. Use student names and quotes.",
    "emergent_themes": "From the theme set, with supporting quotes and \
student counts.",
    "tensions_and_contradictions": "From the contradictions — explicitly \
preserved, named as pedagogically productive.",
    "surprises": "From the outlier report — submissions that don't fit \
the themes. Use student names and their actual words.",
    "focus_areas": "Teacher-directed analysis against their stated interests \
and analysis lens.",
    "concerns": "Aggregated from concern flags, with flagged passages and \
suggested responses. Each concern requires individual teacher review.",
    "divergent_approaches": "How students entered the material differently \
— by format, emotional register, personal vs analytical.",
    "looking_ahead": "What this tells the teacher about readiness for next \
week.",
    "students_to_check_in_with": "Aggregated from concern flags + outlier \
flags. Student names with specific reasons."
  }},
  "confidence": 0.0-1.0
}}"""

# ---------------------------------------------------------------------------
# 3-pass synthesis sections (for Lightweight tier on small models)
# ---------------------------------------------------------------------------
# Each pass asks for 3 sections, which an 8B model can handle reliably.

_SYNTH_PASS_1 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "what_students_said": "Executive summary — most important patterns, \
primary concern, biggest win.",
    "emergent_themes": "From the theme set, with supporting quotes and \
student counts.",
    "tensions_and_contradictions": "From the contradictions — explicitly \
preserved, named as pedagogically productive."
  }},
  "confidence": 0.0-1.0
}}"""

_SYNTH_PASS_2 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "surprises": "Submissions that don't fit the themes. Use student \
names and their actual words.",
    "focus_areas": "Teacher-directed analysis against their stated interests \
and analysis lens.",
    "concerns": "Aggregated from concern flags, with flagged passages and \
suggested responses. Each concern requires individual teacher review."
  }},
  "confidence": 0.0-1.0
}}"""

_SYNTH_PASS_3 = """\
Generate JSON with EXACTLY these 3 section keys. Write 2-4 sentences per section.
Use student names and direct quotes.
{{
  "sections": {{
    "divergent_approaches": "How students entered the material differently \
— by format, emotional register, personal vs analytical.",
    "looking_ahead": "What this tells the teacher about readiness for \
next week.",
    "students_to_check_in_with": "Aggregated from concern flags + outlier \
flags. Student names with specific reasons. Do NOT recommend singling out \
students to share or present — suggest structural opportunities instead."
  }},
  "confidence": 0.0-1.0
}}"""

SYNTHESIS_PROMPT_LIGHTWEIGHT = """\
Write an analytical report for a teacher based on the structured analysis \
below. The teacher needs key information fast — they are reviewing this \
before class.

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
THEME SET (summarized):
{themes_summary}

OUTLIER REPORT:
{outliers_summary}

CONCERN FLAGS:
{concerns_summary}

QUICK ANALYSIS HIGHLIGHTS:
{quick_analysis_summary}
{teacher_interests}
{profile_fragment}
{_SYNTHESIS_SECTIONS}

Write clearly and concisely. Use student names. Include verbatim quotes. \
Mark each section as HIGH, MEDIUM, or LOW confidence based on evidence strength."""

SYNTHESIS_PROMPT_MEDIUM = """\
Write an analytical report for a teacher based on the full structured \
analysis below. Connect themes to each other. Notice secondary patterns. \
The teacher needs this to prepare for class.

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
ALL CODING RECORDS (structured JSON):
{records_summary}

THEME SET:
{themes_json}

OUTLIER REPORT:
{outliers_json}

CONCERN FLAGS:
{concerns_summary}

QUICK ANALYSIS:
{quick_analysis_summary}
{teacher_interests}
{profile_fragment}
{_SYNTHESIS_SECTIONS}

Write for a tired teacher who needs key info fast but also wants genuine \
analytical depth. Use student names throughout. Include verbatim quotes. \
Surface connections between themes. Mark confidence per section."""

SYNTHESIS_PROMPT_DEEP = """\
Write a genuinely insightful analytical report for a teacher. You have full \
context — all student submissions as structured records, the complete theme \
analysis, outlier report, and teacher's pedagogical priorities.

Your task is not just to organize findings — it is to do interpretive work. \
Notice students circling the same unspoken tension from different angles. \
Identify where surface agreement masks fundamental disagreement. Find the \
student whose quiet observation nobody else noticed. Write the kind of \
analysis that makes a teacher say "I wouldn't have seen that."

ASSIGNMENT: {assignment_name}
COURSE: {course_name}
TOTAL SUBMISSIONS: {total_submissions}
{teacher_context}
PEDAGOGICAL FRAMEWORK:
Student work is knowledge production. Multiplicity is generative. Tensions \
are productive. Political urgency is appropriate. Honor multiple entry points.

ALL CODING RECORDS:
{records_json}

THEME SET:
{themes_json}

OUTLIER REPORT:
{outliers_json}

ALL CONCERN FLAGS:
{concerns_json}

QUICK ANALYSIS:
{quick_analysis_json}
{teacher_interests}
{profile_fragment}
{_SYNTHESIS_SECTIONS}

Write for a teacher who cares deeply about their students and wants to \
understand what their class is thinking. Use student names. Quote their \
actual words. Preserve complexity. Mark confidence per section."""

# ---------------------------------------------------------------------------
# Prompt fragments (injected when teacher provides optional context)
# ---------------------------------------------------------------------------

ANALYSIS_LENS_PROMPT_FRAGMENT = """\

ANALYSIS LENS (teacher's focus):
{lens_criteria}
For each lens criterion, note how this student's work engages with it. \
These are observations, not scores — "Student connected racial formation \
to grandmother's experience" not "B+"."""

INTEREST_AREAS_FRAGMENT = """\

TEACHER'S PRIORITIES: {interests_summary}"""

PROFILE_FRAGMENT = """\
{profile_fragment}"""

# ---------------------------------------------------------------------------
# Guided Synthesis Chain (A6) — 4 scoped calls, each answering ONE question
#
# Design principles:
#   - ONE question per call — not open-ended synthesis
#   - Student names in LOCAL calls only — NEVER in cloud calls
#   - Do NOT suggest exercises or teaching strategies — the teacher designs response
#   - Surface tensions as productive, not as problems
#   - Partial results are valid (#CRIP_TIME)
#   - Righteous anger about injustice is APPROPRIATE engagement, not a concern
# ---------------------------------------------------------------------------

SYNTHESIS_CONCERN_PROMPT = """\
These students were flagged for teacher attention after an engagement analysis:

{flagged_students_block}

What patterns do you see among these concerns? Note BOTH commonalities AND \
important differences — do NOT force them into one category if the distinctions \
are pedagogically meaningful. Jake's class-based critique is NOT the same \
pattern as Connor's colorblindness even if both "challenge the framework."

Do NOT suggest teaching strategies or exercises — the teacher designs the \
pedagogical response. Your job is to describe the diagnostic picture.

Respond with JSON:
{{
  "patterns": [
    {{
      "description": "What this group of students has in common (be specific)",
      "student_names": ["name1", "name2"]
    }}
  ],
  "key_differences": [
    "Important distinction between students that should NOT be collapsed into one pattern"
  ]
}}

If all students share one pattern with no meaningful differences, \
key_differences may be an empty list. But preserve real distinctions.

EXAMPLE:
{{
  "patterns": [
    {{
      "description": "Both students resist engaging with a structural lens, \
though through different moves — one uses colorblind framing, one uses \
meritocracy framing",
      "student_names": ["Connor Walsh", "Aiden Park"]
    }}
  ],
  "key_differences": [
    "Connor's colorblindness ('I don't see race') and Aiden's meritocracy framing \
('everyone can succeed') look similar but the teacher should engage them differently — \
Connor is denying race exists, Aiden accepts it exists but denies its structural effects"
  ]
}}"""

SYNTHESIS_HIGHLIGHT_PROMPT = """\
These students showed strong engagement with the material in this assignment:

{strong_students_block}

What do these students demonstrate? What specific analytical moves or \
connections are they making? Be specific — "strong engagement" is not \
enough. Name the intellectual work.

Do NOT suggest how the teacher should use these students' work — do NOT \
recommend singling out students to share or present. Your job is to \
describe what these students are doing intellectually so the teacher \
can design structural opportunities.

Respond with JSON:
{{
  "highlights": [
    {{
      "description": "What specific intellectual move or connection this student is making",
      "student_names": ["name1"]
    }}
  ]
}}

Group students together only if they are genuinely making the same move. \
Different entries from the same discipline area may look similar but be \
meaningfully distinct.

EXAMPLE:
{{
  "highlights": [
    {{
      "description": "Maria Ndiaye is applying transnational framing — \
connecting the course concepts to her own cross-border family experience \
in a way that extends the theoretical framework beyond US-centric examples",
      "student_names": ["Maria Ndiaye"]
    }},
    {{
      "description": "Destiny Williams and Jake Novak are both using \
structural analysis but from opposite directions — Destiny centers lived \
geography, Jake interrogates framework scope",
      "student_names": ["Destiny Williams", "Jake Novak"]
    }}
  ]
}}"""

SYNTHESIS_TENSION_PROMPT = """\
An engagement analysis found these patterns in a class assignment:

CONCERN PATTERNS:
{concern_patterns_block}

ENGAGEMENT HIGHLIGHTS:
{highlight_patterns_block}

What tensions or contrasts do you see between these groups? Where do \
students' perspectives diverge in ways the teacher should be aware of?

IMPORTANT: These tensions may be productive — disagreement and divergence \
in a classroom are often where learning happens. "The tension is the \
pedagogy." Do NOT frame divergence as a problem to resolve. Surface it \
as something worth the teacher's attention.

Do NOT suggest exercises, discussion designs, or teaching strategies — \
the teacher decides how to respond. Your job is to name the tension clearly.

Respond with JSON:
{{
  "tensions": [
    {{
      "description": "What the tension is — name it precisely",
      "between": ["group or student description A", "group or student description B"]
    }}
  ]
}}

If no meaningful tension exists between the groups (e.g., all students \
showed strong engagement with no concern flags), return an empty list.

EXAMPLE:
{{
  "tensions": [
    {{
      "description": "The class contains students actively applying structural \
analysis (Destiny, Maria, Jake) alongside students resisting it through \
colorblind or meritocracy framing (Connor, Aiden). This is not a gap in \
understanding — it is an ideological tension that often exists in real \
classrooms. The teacher should be aware that these students are working \
from fundamentally different frameworks, not just different depths of \
engagement.",
      "between": [
        "Students applying structural analysis to intersecting oppressions",
        "Students resisting structural analysis through colorblind or \
meritocracy framing"
      ]
    }}
  ]
}}"""

SYNTHESIS_TEMPERATURE_PROMPT = """\
Here is the class summary data for one assignment:

- Total students: {total_students}
- Concern flags: {flagged_count} student(s) — concern types: {concern_types}
- Strong engagement: {strong_count} student(s)
- Limited/minimal engagement: {limited_count} student(s)
- Middle range (moderate engagement, no concerns): {middle_count} student(s)
- Assignment connection: {connection_summary}
- Pairwise similarity: {similarity_summary}

Write a 3-4 sentence "class temperature" summary for the teacher. \
Focus on: what the class is thinking, where they're struggling, and \
what the teacher should pay attention to going into the next class.

Do NOT suggest exercises or teaching strategies — the teacher designs \
the response. Do NOT use "the students" — describe the class as a whole \
with concrete numbers and patterns.

If a large proportion of students were flagged for concerns, note this \
directly: it may indicate the assignment prompt or reading needs \
reframing, not just individual student issues.

Respond with JSON:
{{
  "class_temperature": "3-4 sentence summary of where this class is",
  "attention_areas": [
    "Specific pattern or student group the teacher should watch in next class"
  ]
}}

EXAMPLE:
{{
  "class_temperature": "Most of the class (18 of 24 students) engaged \
with the intersectionality framework at a surface level, reproducing the \
traffic intersection metaphor without extending it. A cluster of 4 students \
showed strong engagement through lived experience and transnational framing. \
3 students were flagged for colorblind or meritocracy framing that resists \
structural analysis — these students are not confused, they are working \
from a different ideological starting point.",
  "attention_areas": [
    "The 3 flagged students (Connor, Aiden, Brittany) need individual \
engagement — they are not all making the same move and should not be \
grouped together in a class response",
    "The gap between surface-level engagement and the 4 strong engagers \
suggests the assignment may need a bridge — something connecting the \
abstract framework to students' own starting points"
  ]
}}"""


# ---------------------------------------------------------------------------
# JSON repair prompt (used on parse failure)
# ---------------------------------------------------------------------------

JSON_REPAIR_PROMPT = """\
Your previous response was not valid JSON. Here is what you returned:

{raw_response}

Please fix the JSON so it is valid. Return ONLY the corrected JSON, \
nothing else. The expected format is:

{expected_format}"""

# ---------------------------------------------------------------------------
# Draft student feedback (Phase 4)
# ---------------------------------------------------------------------------

FEEDBACK_SYSTEM_PROMPT = """\
You are helping a teacher write a brief, constructive response to a \
student's work. The student will read this comment on their assignment \
in Canvas.

Your job is to:
1. Show the student their thinking was heard (reference something specific \
they said)
2. Name one strength (grounded in their actual work, not generic praise)
3. Offer one area for growth or a question that invites deeper thinking
4. Keep the tone {feedback_style} and the length {feedback_length}

NEVER include: grades, scores, comparison to other students, concern flags, \
engagement ratings, or any analytical metadata. The student should feel \
SEEN, not ASSESSED.

Respond ONLY with valid JSON matching the requested schema."""

FEEDBACK_DRAFT_PROMPT = """\
Write draft feedback for this student based on the structured analysis of \
their submission. The teacher will review and edit before posting.

STUDENT: {student_name}
ASSIGNMENT: {assignment_prompt}
{lens_fragment}
{preprocessing_fragment}
ANALYSIS OF THIS STUDENT'S WORK:
- Theme tags: {theme_tags}
- Emotional register: {emotional_register}
- Notable quotes: {notable_quotes}
- Concepts applied: {concepts_applied}
- Personal connections: {personal_connections}
- Readings referenced: {readings_referenced}
{concern_context}
{profile_fragment}

Respond with JSON:
{{
  "feedback_text": "The full feedback comment the student will read",
  "strengths_noted": ["1-2 specific strengths from their work"],
  "areas_for_growth": ["1 area for development or deeper thinking"],
  "question_for_student": "A genuine question inviting further thought",
  "confidence": 0.0-1.0
}}

RULES:
- Use {student_name}'s actual name
- Reference something SPECIFIC they said (not generic praise)
- NEVER mention concern flags, engagement ratings, theme tags, or any \
analytical metadata in the feedback text. The student sees ONLY a human \
comment from their teacher.
- If the student's emotional register suggests exhaustion or disengagement, \
write with extra warmth — no performance pressure
- If the student did emotional labor (sharing personal marginalization, \
explaining lived experience), acknowledge that labor explicitly
{style_fragment}
{length_fragment}

EXAMPLES:

Example 1 (warm style, student with personal connections):
Student: Maria Garcia
Themes: racial formation, family history
Quote: "My grandmother always said race was something done to us, not \
something we are — now I have language for that"
Response:
{{
  "feedback_text": "Maria, your connection between your grandmother's \
insight and Omi & Winant's framework is exactly the kind of thinking this \
course is built for. You're not just learning a theory — you're recognizing \
wisdom your family has always held. For next week, I'm curious: how does \
your grandmother's understanding challenge or extend what the authors \
describe?",
  "strengths_noted": ["personal connection to theory", "family knowledge \
as resource"],
  "areas_for_growth": ["extend framework beyond personal experience"],
  "question_for_student": "How does your grandmother's understanding \
challenge or extend what the authors describe?",
  "confidence": 0.9
}}

Example 2 (care-oriented, student showing exhaustion signals):
Student: James Thompson
Themes: [minimal]
Quote: [none — 62 words, significantly shorter than previous weeks]
Emotional register: disengaged
Response:
{{
  "feedback_text": "James, I wanted to check in. I noticed this week's \
reflection was shorter than your usual work, and I want you to know that's \
okay — weeks vary. If something's going on, my door is open. When you're \
ready, the questions from this week's reading will still be here. No \
pressure.",
  "strengths_noted": ["consistent participation in previous weeks"],
  "areas_for_growth": ["re-engage when ready"],
  "question_for_student": "",
  "confidence": 0.7
}}

Example 3 (multilingual acknowledgment):
Student: Ana Reyes
Preprocessing: translated from Spanish
Themes: personal_reflection, current_events
Response:
{{
  "feedback_text": "Ana, your reflection — written in Spanish and showing \
real depth — brought a perspective no one else in the class offered this \
week. Your connection between the course concepts and your personal \
experience is exactly the kind of multilingual thinking that enriches \
everyone's understanding. For next week: how might these ideas look \
different when you think about them in Spanish versus English?",
  "strengths_noted": ["multilingual depth", "unique perspective"],
  "areas_for_growth": ["explore how language shapes understanding"],
  "question_for_student": "How might these ideas look different when you \
think about them in Spanish versus English?",
  "confidence": 0.85
}}"""

# Style fragments injected based on teacher profile
FEEDBACK_STYLE_VARIANTS = {
    "warm": "Write with warmth and care. Acknowledge the student as a whole person.",
    "direct": "Be clear and specific. Name what works and what to develop.",
    "socratic": "End with a genuine question that invites deeper thinking.",
    "lens_focused": "Ground feedback in the analysis lens criteria: {lens_criteria}",
}

# Length fragments injected based on teacher profile
FEEDBACK_LENGTH_VARIANTS = {
    "brief": "2-3 sentences maximum.",
    "moderate": "4-6 sentences.",
    "detailed": "A short paragraph (6-8 sentences) with specific references "
                "to the student's work.",
}


# ---------------------------------------------------------------------------
# Short Submission Review prompts
# ---------------------------------------------------------------------------

SHORT_SUB_SYSTEM_PROMPT = (
    "You are helping a teacher decide whether a short student submission "
    "demonstrates engagement with the assignment. The submission fell below "
    "the word count threshold, but word count alone does not determine "
    "whether a student has engaged.\n\n"
    "Your job is NOT to judge writing quality, grammar, or sophistication. "
    "Your job is NOT to assess student effort or character. "
    "Your job IS to look at what the student actually wrote and determine "
    "whether it shows engagement with the assignment material.\n\n"
    "A submission can be short AND complete. Brevity is not a deficiency.\n\n"
    "IMPORTANT: Students who mix languages (e.g., English and Spanish, "
    "English and Tagalog) within a submission are demonstrating multilingual "
    "engagement — a sophisticated rhetorical practice. Count ALL languages "
    "when assessing engagement, not just English words. If the submission "
    "is entirely in a non-English language, verdict is TEACHER_REVIEW — "
    "the teacher can assess engagement; you cannot reliably assess a "
    "language you may not know well.\n\n"
    "IMPORTANT: Students using dictation or assistive technology may produce "
    "text with unusual formatting, run-on structures, or missing punctuation. "
    "This represents full engagement through oral expression.\n\n"
    "IMPORTANT: Variable capacity is real. A student may be dealing with "
    "chronic pain, executive function barriers, mental health, work "
    "schedules, family obligations, or other circumstances. Assess THIS "
    "submission on its own terms — never compare to an imagined 'normal' "
    "output level.\n\n"
    "IMPORTANT: Students may write briefly as a form of self-protection, "
    "particularly around identity (gender, sexuality, race, disability, "
    "immigration). Protective brevity is not disengagement.\n\n"
    "IMPORTANT: Multiple factors may compound. A multilingual student with "
    "variable capacity faces more than the sum of individual barriers. "
    "Give additional benefit of the doubt when multiple markers are present.\n\n"
    "If you are uncertain, the verdict is TEACHER_REVIEW. You may include "
    "a teacher_note suggesting a check-in if the brevity pattern suggests "
    "the student may need support — framed as care, not surveillance.\n\n"
    "Respond ONLY with valid JSON matching the requested schema."
)

_SHORT_SUB_DO_NOT = """\
IMPORTANT — DO NOT:
- Judge writing quality, grammar, or sophistication
- Compare this to other students or an imagined "ideal" submission
- Penalize non-standard English, code-switching, or multilingual writing
- Treat brevity itself as evidence of low engagement
- Make assumptions about student character, effort, or motivation
- Penalize bullet points, fragments, or informal structure
- Use words like "limited," "basic," "lacks," or "insufficient" about the writing
- Rate informal register (AAVE, colloquial, conversational) as lower confidence \
than academic register for the same engagement level

DO:
- Look for specific evidence of engagement with the assignment material
- Consider whether the format makes brevity appropriate
- Note any course concepts, personal connections, or substantive content
- Recognize translanguaging (language mixing) as sophisticated engagement
- Recognize that protective brevity (writing less around sensitive identity \
topics) is not disengagement
- Give the benefit of the doubt — if ambiguous, verdict is TEACHER_REVIEW
- If the submission is entirely in a non-English language, verdict is TEACHER_REVIEW
- If brevity may reflect circumstances beyond the assignment, include a \
teacher_note suggesting a check-in (framed as care)"""

_SHORT_SUB_JSON_SCHEMA = """\
Respond with JSON:
{{
  "verdict": "CREDIT or TEACHER_REVIEW",
  "brevity_category": "one of: concise_complete, dense_engagement, \
format_appropriate, multilingual, partial_attempt, wrong_submission, \
placeholder, unclear",
  "rationale": "1-2 sentences for the teacher",
  "engagement_evidence": ["verbatim snippets showing engagement"],
  "confidence": 0.0-1.0,
  "teacher_note": "optional care-framed note if check-in may be warranted, or null"
}}"""

_SHORT_SUB_FEW_SHOT = """\
EXAMPLES:

Example 1 — CREDIT / concise_complete:
Submission (62 words): "Reading Baldwin made me rethink everything about my \
neighborhood. I never realized that the way our block is laid out — who got \
to live where — wasn't accidental. It was designed. I keep thinking about \
the part where he talks about complicity, because I wonder what that means \
for people who didn't choose to be here but benefit anyway. That's my block."
Response: {{"verdict": "CREDIT", "brevity_category": "concise_complete", \
"rationale": "Despite brevity, shows genuine personal connection to Baldwin and \
articulates a specific intellectual shift about complicity and place.", \
"engagement_evidence": ["that's my block", "I wonder what that means for people \
who didn't choose to be here"], "confidence": 0.88, "teacher_note": null}}

Example 2 — TEACHER_REVIEW / placeholder:
Submission (8 words): "I will finish this later sorry professor"
Response: {{"verdict": "TEACHER_REVIEW", "brevity_category": "placeholder", \
"rationale": "Student has not engaged with the material; this is a placeholder \
note, not a submission.", "engagement_evidence": [], "confidence": 0.95, \
"teacher_note": "Consider checking in — student may be navigating something."}}

Example 3 — CREDIT / format_appropriate:
Submission (43 words): "Thesis: standardized testing reinforces racial \
inequality\\nI. History of testing as sorting mechanism\\nII. Disparate \
impact data\\nIII. Counterargument: meritocracy myth\\nConclusion: reform \
requires dismantling, not tweaking"
Response: {{"verdict": "CREDIT", "brevity_category": "format_appropriate", \
"rationale": "Outline format is inherently concise; structure shows thesis, \
evidence plan, counterargument, and conclusion — complete academic thinking.", \
"engagement_evidence": ["meritocracy myth", "reform requires dismantling, not \
tweaking"], "confidence": 0.91, "teacher_note": null}}

Example 4 — CREDIT / multilingual:
Submission (45 words): "Yosso's concept of capital aspiracional — mi mamá \
siempre dice que hay que echarle ganas. That's not just 'working hard,' it's \
a whole philosophy about believing the future is possible when everything \
says it isn't. The reading finally gave me a word for what she taught me."
Response: {{"verdict": "CREDIT", "brevity_category": "multilingual", \
"rationale": "Translanguaging submission demonstrates sophisticated engagement: \
student connects Yosso's framework to embodied family knowledge across two \
languages.", "engagement_evidence": ["capital aspiracional", "The reading \
finally gave me a word for what she taught me"], "confidence": 0.93, \
"teacher_note": null}}

Example 5 — TEACHER_REVIEW / unclear (protective brevity):
Submission (14 words): "This reading connected to things I've been through \
but I can't really get into it here"
Response: {{"verdict": "TEACHER_REVIEW", "brevity_category": "unclear", \
"rationale": "Student signals personal connection but declines to elaborate — \
may be self-protecting around sensitive experience.", "engagement_evidence": \
["connected to things I've been through"], "confidence": 0.6, \
"teacher_note": "Consider a private check-in — student may have engaged deeply \
but not felt safe to write about it here. This is not disengagement."}}"""

SHORT_SUB_REVIEW_PROMPT = """\
A student submitted work below the word count threshold. \
Review whether this submission demonstrates engagement.

STUDENT: {student_name}
WORD COUNT: {word_count} words (threshold: {min_word_count})

ASSIGNMENT DESCRIPTION:
{assignment_prompt}

{review_guidance}

{equity_fragment}

SUBMISSION TEXT:
---
{submission_text}
---

""" + _SHORT_SUB_DO_NOT + """

""" + _SHORT_SUB_FEW_SHOT + """

""" + _SHORT_SUB_JSON_SCHEMA

SHORT_SUB_DISCUSSION_PROMPT = """\
A student's discussion reply fell below the word count threshold. \
Review whether this reply demonstrates engagement, considering the \
conversation context.

STUDENT: {student_name}
REPLY WORD COUNT: {word_count} words (threshold: {min_word_count})

DISCUSSION PROMPT:
{assignment_prompt}

THREAD CONTEXT:
{thread_context}

STUDENT'S REPLY:
---
{submission_text}
---

{review_guidance}

{equity_fragment}

A short reply that directly engages a peer's argument, applies a course \
concept, or adds a personal perspective can be more substantive than a \
long generic response. Evaluate this reply IN CONTEXT of what came before.

""" + _SHORT_SUB_DO_NOT + """

""" + _SHORT_SUB_FEW_SHOT + """

""" + _SHORT_SUB_JSON_SCHEMA

# Default per-genre guidance injected as {review_guidance} in Quick Run.
# Bulk Run pulls from the assignment template's short_sub_guidance field.
SHORT_SUB_TEMPLATE_GUIDANCE = {
    "personal": (
        "PERSONAL/REFLECTION: authentic engagement > length. A brief moment of "
        "genuine vulnerability or a single sharp connection to the reading "
        "constitutes complete work."
    ),
    "essay": (
        "FORMAL ESSAY: brevity is more concerning here, but a dense paragraph "
        "with thesis, evidence, and analysis can still demonstrate engagement."
    ),
    "notes": (
        "READING NOTES: inherently brief and fragmentary. Bullet points, "
        "keywords, page references are authentic note-taking. Do not expect prose."
    ),
    "outline": (
        "OUTLINE: hierarchical and concise by design. Look for structure and "
        "topic coverage, not word count."
    ),
    "discussion": (
        "DISCUSSION: a short, incisive response that directly engages a peer's "
        "argument or the reading can be more substantive than a long generic post."
    ),
    "draft": (
        "DRAFT: rough, incomplete, messy by nature. False starts and fragments "
        "are authentic drafting."
    ),
    "auto": "Look for evidence of engagement with the material regardless of format or register.",
}
