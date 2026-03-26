"""
Export analysis packages for use with external chatbots.

Teachers with institutional chatbot access (Gemini, ChatGPT, Claude, Copilot)
but no API key can export a structured prompt + student submissions as a
markdown file, paste it into their chatbot, and get the same analytical
report the local pipeline would produce.

Two export modes:
  1. "Full Analysis" — raw submissions + analysis prompt. The chatbot does
     everything: coding, theme generation, outlier surfacing, synthesis.
     Best when the local pipeline hasn't run or you want a fresh perspective.

  2. "Synthesis Only" — pre-coded records from a completed local run +
     synthesis prompt. The chatbot does interpretive synthesis on top of
     the local pipeline's coding. Best when coding is done but synthesis
     timed out, or you want a deeper model's interpretation.

FERPA: These exports contain student names and submission text. The teacher
must ensure their institutional chatbot use is FERPA-compliant before
pasting student data into it.
"""

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# FERPA warning (prominently placed at top of every export)
# ---------------------------------------------------------------------------

_FERPA_HEADER = """\
# ⚠️  FERPA WARNING — READ BEFORE PASTING

**This document contains student names and their actual coursework.**

Before pasting this into ANY chatbot or AI tool, you must verify:

1. **Your institution has a Data Processing Agreement (DPA)** with the
   chatbot provider (Google for Gemini, OpenAI for ChatGPT, Anthropic
   for Claude, Microsoft for Copilot).
2. **Your use is authorized** under your institution's acceptable use
   policy for AI tools with student data.
3. **The chatbot is NOT using your data for training.** Most enterprise/
   education plans disable training on inputs — verify this for your plan.

If you are unsure about ANY of these, **do not paste this document.**
Instead, run the analysis locally using the Insights Engine — local
processing with Ollama keeps all student data on your computer.

---

"""

_ANONYMIZATION_NOTE = """\
> **Student names are included** because the analysis requires them to
> produce actionable insights ("check in with Maria" vs "check in with
> Student #7"). If your institutional policy requires anonymization,
> use find-and-replace to substitute names before pasting.

---

"""


# ---------------------------------------------------------------------------
# Export: Full Analysis (raw submissions → chatbot does everything)
# ---------------------------------------------------------------------------

def export_full_analysis(
    *,
    course_name: str,
    assignment_name: str,
    submissions: List[Dict],
    teacher_context: str = "",
    teacher_interests: Optional[List[str]] = None,
    analysis_lens: Optional[Dict] = None,
    quick_analysis_summary: str = "",
) -> str:
    """Generate a markdown export for full chatbot analysis.

    Args:
        submissions: list of dicts with student_name, body (text), word_count
        teacher_context: teacher's week context / notes
        teacher_interests: teacher's focus areas
        analysis_lens: analysis lens criteria dict

    Returns:
        Markdown string ready to paste into a chatbot.
    """
    parts = [_FERPA_HEADER, _ANONYMIZATION_NOTE]

    # Title
    parts.append(f"# Assignment Analysis: {assignment_name}\n")
    parts.append(f"**Course:** {course_name}  \n")
    parts.append(f"**Submissions:** {len(submissions)}  \n")
    parts.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n\n")

    # Instructions for the chatbot
    parts.append("## Instructions for AI\n\n")
    parts.append(_FULL_ANALYSIS_PROMPT.format(
        assignment_name=assignment_name,
        course_name=course_name,
        total_submissions=len(submissions),
        teacher_context=_format_teacher_context(teacher_context),
        teacher_interests=_format_interests(teacher_interests),
        lens_criteria=_format_lens(analysis_lens),
    ))
    parts.append("\n\n---\n\n")

    # Quick analysis summary (if available)
    if quick_analysis_summary:
        parts.append("## Quick Analysis (Non-AI Statistical Summary)\n\n")
        parts.append(quick_analysis_summary)
        parts.append("\n\n---\n\n")

    # Student submissions
    parts.append("## Student Submissions\n\n")
    for i, sub in enumerate(submissions, 1):
        name = sub.get("student_name", f"Student {i}")
        body = sub.get("body", sub.get("text", ""))
        wc = sub.get("word_count", len(body.split()) if body else 0)

        # Clean HTML
        body = re.sub(r"<[^>]+>", " ", body or "").strip()

        if not body or wc < 15:
            parts.append(f"### {name} ({wc} words)\n\n")
            parts.append("*[No text submitted or text extraction failed]*\n\n")
        else:
            parts.append(f"### {name} ({wc} words)\n\n")
            parts.append(f"{body}\n\n")

    parts.append("---\n\n")
    parts.append(
        "*End of submissions. Please produce the analysis report "
        "following the instructions above.*\n"
    )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Export: Synthesis Only (coded records → chatbot does synthesis)
# ---------------------------------------------------------------------------

def export_synthesis_only(
    *,
    course_name: str,
    assignment_name: str,
    coding_records: List[Dict],
    quick_analysis_summary: str = "",
    teacher_context: str = "",
    teacher_interests: Optional[List[str]] = None,
    analysis_lens: Optional[Dict] = None,
) -> str:
    """Generate a markdown export for chatbot synthesis from coded records.

    Use this when the local pipeline completed coding but synthesis
    timed out or you want a more capable model's interpretation.

    Args:
        coding_records: list of coding record dicts (from insights_store)

    Returns:
        Markdown string ready to paste into a chatbot.
    """
    parts = [_FERPA_HEADER, _ANONYMIZATION_NOTE]

    # Title
    parts.append(f"# Synthesis Request: {assignment_name}\n")
    parts.append(f"**Course:** {course_name}  \n")
    parts.append(f"**Coded Records:** {len(coding_records)}  \n")
    parts.append(f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n\n")

    # Instructions
    parts.append("## Instructions for AI\n\n")
    parts.append(_SYNTHESIS_PROMPT.format(
        assignment_name=assignment_name,
        course_name=course_name,
        total_submissions=len(coding_records),
        teacher_context=_format_teacher_context(teacher_context),
        teacher_interests=_format_interests(teacher_interests),
    ))
    parts.append("\n\n---\n\n")

    # Quick analysis
    if quick_analysis_summary:
        parts.append("## Statistical Summary\n\n")
        parts.append(quick_analysis_summary)
        parts.append("\n\n---\n\n")

    # Coded records
    parts.append("## Coded Student Records\n\n")
    parts.append(
        "Each record below was produced by a local AI model (llama3.1:8b) "
        "reading the student's submission. Your job is to synthesize these "
        "into a coherent analytical report.\n\n"
    )

    for rec in coding_records:
        name = rec.get("student_name", "Unknown")
        tags = rec.get("theme_tags", [])
        register = rec.get("emotional_register", "")
        quotes = rec.get("notable_quotes", [])
        concerns = rec.get("concerns", [])
        readings = rec.get("readings_referenced", [])
        concepts = rec.get("concepts_applied", [])
        connections = rec.get("personal_connections", [])
        wc = rec.get("word_count", 0)

        parts.append(f"### {name}")
        if register:
            parts.append(f" · {register}")
        if wc:
            parts.append(f" · {wc} words")
        parts.append("\n\n")

        if tags:
            parts.append(f"**Themes:** {', '.join(tags)}  \n")
        if readings:
            parts.append(f"**Readings:** {', '.join(readings)}  \n")
        if concepts:
            parts.append(f"**Concepts:** {', '.join(concepts)}  \n")
        if connections:
            parts.append(f"**Personal connections:** {', '.join(connections)}  \n")

        for q in quotes[:2]:
            text = q.get("text", "") if isinstance(q, dict) else str(q)
            sig = q.get("significance", "") if isinstance(q, dict) else ""
            if text:
                parts.append(f'\n> "{text}"')
                if sig:
                    parts.append(f"  \n> *{sig}*")
                parts.append("\n")

        if concerns:
            for c in concerns:
                passage = c.get("flagged_passage", "")[:100] if isinstance(c, dict) else ""
                why = c.get("why_flagged", "") if isinstance(c, dict) else ""
                if passage:
                    parts.append(f"\n⚠ **Concern:** {why} — \"{passage}\"  \n")

        parts.append("\n")

    parts.append("---\n\n")
    parts.append(
        "*End of coded records. Please produce the synthesis report "
        "following the instructions above.*\n"
    )

    return "".join(parts)


# ---------------------------------------------------------------------------
# Format quick analysis for export
# ---------------------------------------------------------------------------

def format_quick_analysis_for_export(qa_json: str) -> str:
    """Convert QuickAnalysisResult JSON into readable markdown summary."""
    try:
        qa = json.loads(qa_json)
    except (json.JSONDecodeError, TypeError):
        return ""

    stats = qa.get("stats", {})
    parts = []

    # Submission stats
    n = stats.get("total_submissions", 0)
    wc_mean = stats.get("word_count_mean", 0)
    wc_median = stats.get("word_count_median", 0)
    wc_min = stats.get("word_count_min", 0)
    wc_max = stats.get("word_count_max", 0)
    parts.append(
        f"- **{n} submissions**, word count: "
        f"avg {wc_mean:.0f}, median {wc_median:.0f}, "
        f"range {wc_min}–{wc_max}"
    )

    # Timing
    timing = stats.get("timing", {})
    if timing:
        timing_parts = [f"{v} {k.replace('_', ' ')}" for k, v in timing.items() if v]
        if timing_parts:
            parts.append(f"- **Timing:** {', '.join(timing_parts)}")

    # Sentiment
    sentiment = qa.get("sentiment_distribution", {})
    if sentiment:
        sent_parts = [f"{k}: {v}" for k, v in sorted(sentiment.items(), key=lambda x: -x[1])]
        parts.append(f"- **Sentiment distribution:** {', '.join(sent_parts)}")

    # Top terms
    tfidf = qa.get("tfidf_terms", [])
    if tfidf:
        terms = [t.get("term", "") for t in tfidf[:10] if t.get("term")]
        if terms:
            parts.append(f"- **Distinctive terms (TF-IDF):** {', '.join(terms)}")

    # Keyword patterns
    keyword_hits = qa.get("keyword_hits", {})
    if keyword_hits:
        hits = []
        for name, hit in sorted(keyword_hits.items(), key=lambda x: -x[1].get("count", 0)):
            count = hit.get("count", 0) if isinstance(hit, dict) else 0
            n_students = len(hit.get("student_ids", [])) if isinstance(hit, dict) else 0
            display = name.replace("_", " ").title()
            hits.append(f"{display} ({count} hits, {n_students} students)")
        parts.append(f"- **Keyword patterns:** {'; '.join(hits[:5])}")

    # Concern signals
    concerns = qa.get("concern_signals", [])
    if concerns:
        by_type = {}
        for sig in concerns:
            st = sig.get("signal_type", "")
            by_type.setdefault(st, []).append(sig.get("student_name", ""))
        for st, names in by_type.items():
            parts.append(f"- **{st}:** {', '.join(names[:5])}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt templates for export
# ---------------------------------------------------------------------------

_FULL_ANALYSIS_PROMPT = """\
You are helping a teacher understand what their students said this week.
Below are all student submissions for one assignment. Please analyze them
and produce a structured analytical report.

**Assignment:** {assignment_name}
**Course:** {course_name}
**Total submissions:** {total_submissions}
{teacher_context}
{teacher_interests}
{lens_criteria}

**PEDAGOGICAL FRAMEWORK:**
Student work is knowledge production. Multiplicity is generative. Tensions
are productive. Political urgency about injustice is appropriate academic
engagement, not a concern. Honor multiple entry points.

Non-standard English, AAVE, multilingual mixing, and neurodivergent writing
styles are valid academic registers — do not treat them as deficits or
flag them as concerns. A student using their own identity as the analytical
subject is demonstrating engagement, not crisis.

**YOUR TASK:**
1. Read each submission carefully
2. For each student, identify: theme tags, notable quotes, emotional register
   (analytical/passionate/personal/urgent/reflective/disengaged), readings
   referenced, concepts applied, personal connections
3. Generate 3-8 emergent themes with student names and supporting quotes
4. Surface contradictions — when students disagree, that is pedagogically
   important. Name who and preserve both sides.
5. Identify outliers — submissions that don't fit the themes are often the
   most important findings
6. Flag concerns ONLY for:
   (a) Essentializing language — attributing fixed traits to entire racial/ethnic
       groups, including positive stereotypes. Watch for patterns like "all X
       people are...", "they always...", "[group] just naturally..." — celebratory
       stereotypes ("they have this amazing resilience") are as much a concern as
       negative ones, because they flatten individuals into group traits.
   (b) Colorblind/post-racial claims that dismiss structural inequality
       ("I don't see race", "treat everyone the same", "we don't need labels").
   (c) Tone policing — dismissing others' emotional responses as unproductive
       or calling for "civility" in ways that silence urgency about injustice.
   (d) Explicit signs of acute personal distress unrelated to the material
       (e.g., "I can't stop crying", safety concerns).
   Do NOT flag: anger about injustice, students describing their own
   marginalization, non-standard writing styles, or short/incomplete submissions.

**OUTPUT FORMAT:**
Produce a report with these sections:
- **What Your Students Said** — executive summary, key patterns, biggest win
- **Emergent Themes** — 3-8 themes with student names and quotes
- **Tensions & Contradictions** — explicitly preserved, named as productive
- **Surprises** — outlier submissions with student names and their words
- **Your Focus Areas** — analysis against stated interests/lens
- **What Your Students Need You to See** — concern flags with suggested responses
- **Students to Check In With** — names with specific reasons

Use student names throughout. Include verbatim quotes. Preserve complexity.
"""

_SYNTHESIS_PROMPT = """\
You are helping a teacher understand what their class said this week.
Below are structured coding records produced by a local AI model for
each student submission. Your job is interpretive synthesis — connect
the individual codings into a coherent analytical report.

**Assignment:** {assignment_name}
**Course:** {course_name}
**Total submissions:** {total_submissions}
{teacher_context}
{teacher_interests}

**YOUR TASK:**
Don't just organize findings — do interpretive work. Notice students
circling the same unspoken tension from different angles. Identify where
surface agreement masks fundamental disagreement. Find the student whose
quiet observation nobody else noticed.

**OUTPUT FORMAT:**
Produce a report with these sections:
- **What Your Students Said** — executive summary with names and quotes
- **Emergent Themes** — synthesized from the coded theme tags
- **Tensions & Contradictions** — opposing views, named as productive
- **Surprises** — submissions that don't fit, unique voices
- **Your Focus Areas** — analysis against teacher's stated interests
- **What Your Students Need You to See** — aggregated concern flags
- **How Students Entered the Material** — format, register, personal vs analytical
- **Looking Ahead** — what this tells you about readiness for next week
- **Students to Check In With** — names with specific reasons

Write for a teacher who cares deeply about their students and wants to
understand what their class is thinking. Use student names. Quote their
actual words. Preserve complexity.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_teacher_context(context: str) -> str:
    if not context:
        return ""
    return f"\n**Teacher's context:** {context}\n"


def _format_interests(interests: Optional[List[str]]) -> str:
    if not interests:
        return ""
    items = ", ".join(f"({i+1}) {x}" for i, x in enumerate(interests[:5]))
    return f"\n**Teacher's priorities:** {items}\n"


def _format_lens(lens: Optional[Dict]) -> str:
    if not lens:
        return ""
    criteria = "\n".join(f"- {k}: {v}" for k, v in lens.items())
    return f"\n**Analysis lens:**\n{criteria}\n"


# ---------------------------------------------------------------------------
# Export: Handoff Prompt (anonymized patterns → institutional chatbot)
# ---------------------------------------------------------------------------

_FERPA_ANONYMIZED_NOTICE = """\
> **FERPA notice:** This prompt contains anonymized class-level patterns.
> No student names or identifying information are included.

---

"""

_HANDOFF_INSTRUCTIONS = """\
Provide a richer pedagogical analysis of these class-level patterns.

What do these patterns suggest about where the class is right now?
What tensions are most productive to bring into the room?
What should the teacher notice about HOW students are engaging with the material —
not just what they said, but the register, energy, and entry points they used?

Do NOT suggest singling out individual students to share or present.
Instead, suggest structural teaching opportunities: discussion formats,
follow-up prompts, grouping strategies, or writing moves the whole class
could benefit from.

Consider:
- What unspoken questions are underneath the surface patterns?
- Where is surface agreement masking real disagreement worth surfacing?
- What concerns deserve a structural response rather than an individual one?
- What does the class temperature suggest about where students are emotionally?
"""

_HANDOFF_PROMPT = """\
You are helping a teacher plan next steps after reading their class's submissions.
Below are anonymized class-level patterns — no individual students are identified.

**Course:** {course_name}
**Assignment:** {assignment_name}
**Total submissions:** {total_submissions}
{teacher_context}
## Class Reading

{class_reading}

## Pattern Summary

{pattern_summary}

---

## Your Task

{instructions}
"""


def export_handoff_prompt(
    *,
    course_name: str,
    assignment_name: str,
    class_reading: str,
    synthesis_data: dict,
    total_submissions: int,
    student_names: list,
    teacher_context: str = "",
) -> str:
    """Generate an anonymized prompt for pasting into an institutional chatbot.

    FERPA-safe: all student names are replaced with anonymous labels.
    No direct quotes that could identify students are included.
    The teacher reviews the prompt before pasting.

    Returns markdown text ready to copy-paste.
    """
    name_map = _build_name_map(student_names)

    # Anonymize the free-text class reading
    anon_reading = _anonymize_text(class_reading, name_map)

    # Extract and anonymize pattern fields from synthesis_data
    pattern_summary = _format_pattern_summary(synthesis_data, name_map)

    # Format teacher context
    ctx_block = _format_teacher_context(teacher_context)

    body = _HANDOFF_PROMPT.format(
        course_name=course_name,
        assignment_name=assignment_name,
        total_submissions=total_submissions,
        teacher_context=ctx_block,
        class_reading=anon_reading,
        pattern_summary=pattern_summary,
        instructions=_HANDOFF_INSTRUCTIONS,
    )

    parts = [
        f"# Handoff Prompt: {assignment_name}\n",
        f"**Exported:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  \n\n",
        _FERPA_ANONYMIZED_NOTICE,
        body,
    ]
    return "".join(parts)


def _anonymize_text(text: str, name_map: dict) -> str:
    """Replace student names with anonymous labels."""
    result = text
    for name, label in name_map.items():
        result = result.replace(name, label)
    return result


def _build_name_map(student_names: list) -> dict:
    """Build name → anonymous label mapping, longest names first."""
    # Sort longest first to avoid partial replacement issues
    sorted_names = sorted(set(student_names), key=len, reverse=True)
    labels = []
    for i in range(len(sorted_names)):
        if i < 26:
            labels.append(f"Student {chr(65 + i)}")
        else:
            labels.append(f"Student {i + 1}")
    return dict(zip(sorted_names, labels))


def _format_pattern_summary(synthesis_data: dict, name_map: dict) -> str:
    """Extract and anonymize pattern fields from synthesis_data."""
    parts = []

    concern_patterns = synthesis_data.get("concern_patterns", [])
    if concern_patterns:
        parts.append("**Concern patterns:**")
        if isinstance(concern_patterns, list):
            for item in concern_patterns:
                text = item if isinstance(item, str) else str(item)
                parts.append(f"- {_anonymize_text(text, name_map)}")
        else:
            parts.append(_anonymize_text(str(concern_patterns), name_map))

    engagement_highlights = synthesis_data.get("engagement_highlights", [])
    if engagement_highlights:
        parts.append("\n**Engagement highlights:**")
        if isinstance(engagement_highlights, list):
            for item in engagement_highlights:
                text = item if isinstance(item, str) else str(item)
                parts.append(f"- {_anonymize_text(text, name_map)}")
        else:
            parts.append(_anonymize_text(str(engagement_highlights), name_map))

    tensions = synthesis_data.get("tensions", [])
    if tensions:
        parts.append("\n**Tensions:**")
        if isinstance(tensions, list):
            for item in tensions:
                text = item if isinstance(item, str) else str(item)
                parts.append(f"- {_anonymize_text(text, name_map)}")
        else:
            parts.append(_anonymize_text(str(tensions), name_map))

    class_temperature = synthesis_data.get("class_temperature", "")
    if class_temperature:
        anon_temp = _anonymize_text(str(class_temperature), name_map)
        parts.append(f"\n**Class temperature:** {anon_temp}")

    return "\n".join(parts) if parts else "(No pattern data available.)"


# ---------------------------------------------------------------------------
# File saving helper
# ---------------------------------------------------------------------------

def save_export(content: str, output_dir: str, filename: str) -> Path:
    """Save export content to a markdown file. Returns the file path."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / filename
    path.write_text(content, encoding="utf-8")
    return path
