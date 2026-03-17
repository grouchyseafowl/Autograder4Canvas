"""
Analysis lens templates and equity attention framing by subject area.

Templates provide starting configurations for the analysis lens and
teacher interests. Teachers pick a subject template, then customize.
The profile learns from there.

Equity attention dimensions are woven into every subject — not as an
add-on, but as what it means to teach that subject with integrity.
The power analysis always runs at full depth. What shifts is how it's
APPLIED to the subject matter and how findings are framed.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class LensTemplate:
    """A starting configuration for a subject area."""
    key: str
    display_name: str
    description: str
    # What the analysis listens for (becomes the analysis lens)
    analysis_lens: List[str]
    # Default ranked interests
    default_interests: List[str]
    # How the power analysis is framed for this subject
    equity_attention_framing: str
    # Equity-aware prompt fragment (injected into concern + synthesis prompts)
    equity_prompt_fragment: str
    # Assignment type sub-templates
    assignment_variants: Dict[str, List[str]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Subject templates
# ---------------------------------------------------------------------------

LENS_TEMPLATES: Dict[str, LensTemplate] = {

    "ethnic_studies": LensTemplate(
        key="ethnic_studies",
        display_name="Ethnic Studies",
        description=(
            "Critical engagement, lived experience, structural analysis, "
            "multiplicity, current events, solidarity"
        ),
        analysis_lens=[
            "Critical engagement with course concepts",
            "Connection to lived experience and personal history",
            "Structural analysis (not just individual)",
            "Multiplicity — honoring different entry points",
            "Current events connections",
        ],
        default_interests=[
            "How students connect readings to lived experience",
            "Whether structural analysis or individual framing dominates",
            "Current events connections",
        ],
        equity_attention_framing=(
            "Who's doing emotional labor? Who can stay safely analytical "
            "while others analyze their own oppression? How is the classroom "
            "reproducing or interrupting the dynamics in the readings?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Ethnic Studies):\n"
            "Look for which students are doing the emotional labor of explaining "
            "racism, colonialism, or discrimination from their own experience — "
            "while other students analyze the same topics from a comfortable "
            "academic distance. This labor gap IS the classroom dynamic.\n"
            "A student expressing anger about injustice is doing appropriate "
            "intellectual work. A student who keeps things safely theoretical "
            "while the material demands personal engagement may be avoiding "
            "the harder work the course asks for.\n"
            "Surface references to material conditions: work, family obligations, "
            "immigration status, community crises. These aren't tangential — "
            "they're the structural context of the learning."
        ),
        assignment_variants={
            "discussion": [
                "Peer engagement and dialogue",
                "Critical response to others' ideas",
                "Solidarity and coalition-building in discussion",
            ],
            "reflection": [
                "Personal connection to course concepts",
                "Structural analysis of lived experience",
                "Multiplicity of entry points",
            ],
        },
    ),

    "social_science": LensTemplate(
        key="social_science",
        display_name="Social Science",
        description=(
            "Framework application, evidence-based reasoning, connecting "
            "theory to observation, methodological thinking"
        ),
        analysis_lens=[
            "Applying theoretical frameworks to observations",
            "Evidence-based reasoning",
            "Connecting theory to real-world phenomena",
            "Methodological awareness",
            "Distinguishing correlation from causation",
        ],
        default_interests=[
            "How students apply theory to evidence",
            "Common methodological misconceptions",
            "Whether students see structural vs individual explanations",
        ],
        equity_attention_framing=(
            "Whose lived experience is treated as 'anecdotal' vs whose is "
            "'data'? Which students can theorize from distance and which "
            "are theorizing from inside? Are structural explanations or "
            "individual ones being privileged?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Social Science):\n"
            "Notice when students from marginalized communities offer lived "
            "experience as evidence — is it being integrated as valid data "
            "or dismissed as 'just personal'? Meanwhile, students who can "
            "theorize from distance have a different relationship to the material.\n"
            "Surface when students challenge the methodology or framing of "
            "published research — this is critical thinking, not being "
            "'anti-science.' A student questioning whose communities are studied "
            "and who benefits from the research is doing sophisticated work.\n"
            "Note references to material conditions that shape how students "
            "engage: work schedules, family responsibilities, community contexts."
        ),
        assignment_variants={
            "research": [
                "Source evaluation and methodology",
                "Evidence quality and reasoning",
                "Theory application",
            ],
            "discussion": [
                "Framework application in dialogue",
                "Engaging with peers' theoretical claims",
                "Connecting theory to current events",
            ],
        },
    ),

    "humanities": LensTemplate(
        key="humanities",
        display_name="Humanities",
        description=(
            "Interpretive depth, textual engagement, ambiguity, "
            "cross-text connections, original argument"
        ),
        analysis_lens=[
            "Interpretive depth and close reading",
            "Engaging with ambiguity and complexity",
            "Cross-text connections",
            "Original interpretive argument",
            "Multiple interpretive traditions",
        ],
        default_interests=[
            "How students handle ambiguity in texts",
            "Whether students develop original interpretations",
            "Connections across different readings/traditions",
        ],
        equity_attention_framing=(
            "Whose texts are 'canonical'? Whose interpretive traditions "
            "are centered? Is 'universal human experience' being claimed "
            "without examining whose experience it actually describes?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Humanities):\n"
            "Notice whose interpretive traditions students draw on. A student "
            "reading a text through their cultural or religious tradition is "
            "doing interpretive work, not 'missing the point.' A student who "
            "connects a philosophical text to their grandmother's proverbs is "
            "demonstrating cross-traditional thinking.\n"
            "Surface when students resist or complicate 'universal' claims — "
            "this is sophisticated critique, not failure to understand.\n"
            "Note when students bring non-Western, Indigenous, or marginalized "
            "intellectual traditions into dialogue with canonical texts — this "
            "enriches the class even when it doesn't match expected frameworks."
        ),
        assignment_variants={
            "essay": [
                "Thesis development and argumentation",
                "Textual evidence and close reading",
                "Interpretive originality",
            ],
            "discussion": [
                "Engaging with others' interpretations",
                "Textual references in dialogue",
                "Productive disagreement",
            ],
        },
    ),

    "english": LensTemplate(
        key="english",
        display_name="English / Writing",
        description=(
            "Argument structure, evidence use, thesis clarity, "
            "writing craft, source integration, voice development"
        ),
        analysis_lens=[
            "Argument structure and thesis clarity",
            "Evidence use and source integration",
            "Writing craft and voice development",
            "Revision and growth over time",
            "Rhetorical awareness",
        ],
        default_interests=[
            "How students develop arguments with evidence",
            "Voice development and authenticity",
            "Common structural weaknesses",
        ],
        equity_attention_framing=(
            "Whose language is 'standard'? Whose rhetorical traditions "
            "are valued? Is 'clarity' being defined by a single cultural "
            "norm? Who's code-switching and what does that labor look like?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (English/Writing):\n"
            "Notice code-switching — students whose voice shifts between "
            "personal and academic register are doing labor. That labor "
            "should be visible, not just evaluated as 'inconsistent voice.'\n"
            "A student whose writing doesn't match 'standard academic English' "
            "may be drawing on rich rhetorical traditions from their home "
            "language or community. Surface this as strength, not deficit.\n"
            "When a student writes with passion about injustice, evaluate "
            "the argument, don't police the tone. 'Too emotional' is not "
            "a writing critique — it's a cultural norm being imposed."
        ),
        assignment_variants={
            "essay": [
                "Thesis and argument structure",
                "Evidence integration",
                "Voice and craft",
            ],
            "creative": [
                "Voice authenticity",
                "Risk-taking and experimentation",
                "Cultural and personal grounding",
            ],
        },
    ),

    "history": LensTemplate(
        key="history",
        display_name="History",
        description=(
            "Source analysis, multiple perspectives, chronological "
            "reasoning, cause/effect, historical empathy"
        ),
        analysis_lens=[
            "Source analysis and evaluation",
            "Multiple perspectives on events",
            "Chronological reasoning and causation",
            "Historical empathy and context",
            "Connecting past to present",
        ],
        default_interests=[
            "How students handle primary sources",
            "Whether students see multiple perspectives",
            "Connections between historical events and present",
        ],
        equity_attention_framing=(
            "Whose archives survive? Whose testimony counts as evidence? "
            "Is 'objectivity' masking a particular standpoint? Whose "
            "ancestors are 'historical subjects' and whose are family?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (History):\n"
            "Notice when students connect historical events to their own "
            "family histories — a student whose grandparents lived through "
            "the events being studied has a different relationship to the "
            "material than one studying it from the outside.\n"
            "Surface when students question whose perspective dominates the "
            "historical record — this is historiographical thinking, not "
            "conspiracy theory. 'The textbook doesn't mention...' may be the "
            "most important observation in the class.\n"
            "Note when studying violence done to specific communities requires "
            "members of those communities to sit with their own people's "
            "suffering as coursework. That's a cost the course imposes unevenly."
        ),
        assignment_variants={
            "source_analysis": [
                "Source evaluation and contextualization",
                "Perspective identification",
                "Evidentiary reasoning",
            ],
            "essay": [
                "Historical argument development",
                "Multiple causation",
                "Connection to present",
            ],
        },
    ),

    "science": LensTemplate(
        key="science",
        display_name="Science",
        description=(
            "Conceptual accuracy, common misconceptions, methodology, "
            "data reasoning, scientific literacy"
        ),
        analysis_lens=[
            "Conceptual accuracy and understanding",
            "Common misconceptions identified",
            "Methodology and experimental reasoning",
            "Data interpretation and evidence-based conclusions",
            "Scientific literacy and communication",
        ],
        default_interests=[
            "Which concepts students struggle with",
            "Common misconceptions across the class",
            "How students reason from data to conclusions",
        ],
        equity_attention_framing=(
            "Whose bodies/communities are researched vs doing research? "
            "Which knowledge traditions are treated as 'pre-scientific'? "
            "Are 'neutral' findings shaped by who funds or designs the study? "
            "Who sees themselves in the scientific enterprise and who feels excluded?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Science):\n"
            "Notice when students from communities impacted by environmental "
            "racism, medical racism, or extractive research bring that experience "
            "into science coursework — this is not 'being political,' it's "
            "connecting science to its material consequences.\n"
            "Surface when students question the neutrality of scientific "
            "practice — who funds research, whose communities are studied, "
            "whose health outcomes are treated as default. This is sophisticated "
            "scientific thinking.\n"
            "A student who says 'my community doesn't trust doctors' is providing "
            "data about the social context of science, not expressing ignorance."
        ),
        assignment_variants={
            "lab_report": [
                "Methodology and procedure",
                "Data analysis and interpretation",
                "Conclusions and limitations",
            ],
            "reflection": [
                "Conceptual understanding",
                "Application to real-world contexts",
                "Scientific literacy",
            ],
        },
    ),

    "general": LensTemplate(
        key="general",
        display_name="General",
        description="Balanced across all dimensions",
        analysis_lens=[
            "Engagement with course material",
            "Critical thinking and analysis",
            "Connections to experience or current events",
            "Evidence use and reasoning",
            "Originality and depth",
        ],
        default_interests=[
            "Overall engagement patterns",
            "Common confusions or misconceptions",
            "Diversity of approaches",
        ],
        equity_attention_framing=(
            "How are structural inequalities showing up in who submits, "
            "how they submit, what they say, and what they don't say?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION:\n"
            "Surface patterns that reveal structural conditions: who's "
            "exhausted, who's code-switching, who's doing invisible labor, "
            "who's gone quiet. These aren't individual deficits — they're "
            "signals about how the course and its context are working for "
            "different students.\n"
            "When students reference material conditions (work, family, "
            "health, housing), note this as context, not distraction."
        ),
        assignment_variants={},
    ),
}


def get_template(key: str) -> Optional[LensTemplate]:
    """Look up a lens template by key."""
    return LENS_TEMPLATES.get(key)


def get_template_choices() -> List[tuple]:
    """Return (key, display_name) pairs for GUI picker."""
    return [(t.key, t.display_name) for t in LENS_TEMPLATES.values()]


def get_equity_fragment(subject_key: str) -> str:
    """Return the equity attention prompt fragment for a subject area.

    Always returns something — falls back to general if key unknown.
    """
    t = LENS_TEMPLATES.get(subject_key, LENS_TEMPLATES["general"])
    return t.equity_prompt_fragment
