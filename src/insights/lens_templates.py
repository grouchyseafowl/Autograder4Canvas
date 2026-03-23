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
    # Subject-specific concern framing: adjusts which default patterns are
    # relevant and adds subject-appropriate patterns.  Empty string = use
    # the hardcoded defaults unmodified.
    concern_framing_fragment: str = ""
    # Default strength patterns — surfaced when teacher has not defined custom ones.
    # These represent community cultural wealth and non-dominant forms of engagement
    # that the pipeline should actively look for.
    default_strength_patterns: List[str] = field(default_factory=list)
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
        concern_framing_fragment=(
            "CONCERN FRAMING (Ethnic Studies):\n"
            "All default concern patterns apply with full weight.\n"
            "ESPECIALLY flag: essentializing language about racial/ethnic groups, "
            "colorblind claims, tone policing of anger about structural injustice, "
            "dismissal of lived experience as 'just personal opinion.'\n"
            "Do NOT flag passion, anger, or grief about injustice — these are "
            "appropriate engagement, not behavioral concerns."
        ),
        default_strength_patterns=[
            "student connects course material to community or family knowledge",
            "student demonstrates translanguaging or multilingual thinking",
            "student brings outside sources or cross-disciplinary connections",
            "student challenges or extends the assigned framework's scope",
            "student shows meta-awareness of their own knowledge-making process",
            "student's writing demonstrates rhetorical sophistication in any register",
        ],
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
        concern_framing_fragment=(
            "CONCERN FRAMING (Social Science):\n"
            "Default patterns apply. Also flag:\n"
            "- Student presents a demographic correlation as a causal explanation "
            "('Group X does Y because they are naturally Z')\n"
            "- Student treats anecdote or single case as proof of a general claim\n"
            "- Student attributes social behavior to biology or genetics without "
            "scientific evidence\n"
            "Essentializing and colorblind framing remain relevant in social "
            "science contexts — patterns about group behavior, structural "
            "inequality, and identity deserve scrutiny."
        ),
        default_strength_patterns=[
            "student applies theoretical frameworks to their own lived experience as evidence",
            "student questions whose experiences are treated as data vs. anecdote",
            "student brings cross-disciplinary frameworks into analysis",
            "student demonstrates methodological awareness in evaluating sources",
            "student surfaces structural explanations rather than individual deficit framing",
        ],
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
        concern_framing_fragment=(
            "CONCERN FRAMING (Humanities):\n"
            "Default patterns apply. Also flag:\n"
            "- Student presents a single interpretation as the only possible "
            "reading ('the author definitely meant...', 'this obviously shows...')\n"
            "- Student dismisses other students' interpretations from their "
            "cultural or personal perspective as 'wrong' rather than different\n"
            "Essentializing and colorblind framing apply when students discuss "
            "characters, authors, or historical figures by identity categories."
        ),
        default_strength_patterns=[
            "student brings their own cultural or religious interpretive tradition to the text",
            "student connects the text to family knowledge, proverbs, or community wisdom",
            "student challenges 'universal' claims and names whose experience they represent",
            "student surfaces non-Western or Indigenous intellectual traditions",
            "student develops an original interpretive claim not present in course materials",
        ],
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
        concern_framing_fragment=(
            "CONCERN FRAMING (English/Writing):\n"
            "Default patterns apply. IMPORTANT: Non-standard English, dialect "
            "features, or code-switching are NOT concerns — they are rhetorical "
            "choices with deep cultural roots. Only flag language that harms "
            "other students or essentializes groups, not language that differs "
            "from dominant academic conventions.\n"
            "Also flag: student dismisses another writer's voice or style as "
            "'incorrect' rather than engaging with its choices."
        ),
        default_strength_patterns=[
            "student demonstrates code-switching with intentionality across registers",
            "student draws on home language or community rhetorical traditions as strength",
            "student's voice is distinct and consistent with their own linguistic identity",
            "student takes structural or formal risks in their writing",
            "student writes with passion or specificity about community or lived experience",
        ],
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
        concern_framing_fragment=(
            "CONCERN FRAMING (History):\n"
            "Default patterns apply. Also flag:\n"
            "- Historical inevitability framing ('it was bound to happen', "
            "'there was no alternative') — this removes human agency and often "
            "naturalizes conquest, slavery, or genocide\n"
            "- 'Both sides' framing that treats perpetrators and victims as "
            "morally equivalent\n"
            "- Student treats a single source's perspective as objective fact "
            "without noting whose perspective it represents"
        ),
        default_strength_patterns=[
            "student connects historical events to their own family or community history",
            "student surfaces whose testimony and archives are missing from the record",
            "student applies historical thinking to question whose perspective dominates",
            "student connects historical causes to present structural conditions",
            "student centers the experience of communities not in the textbook narrative",
        ],
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
            "data about the social context of science, not expressing ignorance.\n"
            "When students bring community knowledge traditions — agricultural "
            "knowledge, ecological observation, traditional navigation, food "
            "science practices — into dialogue with Western scientific frameworks, "
            "this is integrative thinking, not anecdote."
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
        concern_framing_fragment=(
            "CONCERN FRAMING (Science):\n"
            "The humanities-specific default patterns (colorblind claims, "
            "tone policing) are LESS relevant for lab/science work. De-weight "
            "them unless the assignment explicitly engages with social dimensions "
            "of science.\n"
            "INSTEAD, prioritize flagging:\n"
            "- Student attributes a group's behavior, ability, or outcome to "
            "biology or genetics without scientific evidence ('women are "
            "naturally worse at spatial reasoning', 'some races are more "
            "athletic') — this is scientific-sounding essentialism\n"
            "- Student presents a correlation from data as direct causation "
            "without acknowledging confounding factors\n"
            "- Student claims a result 'proves' a hypothesis rather than "
            "'supports' or 'is consistent with' it (misuse of scientific language)\n"
            "- Student dismisses a counterexample or outlier without explanation\n"
            "Wellbeing signals always apply regardless of subject."
        ),
        default_strength_patterns=[
            "student connects scientific concepts to community or environmental health context",
            "student brings community ecological or traditional knowledge into dialogue with course concepts",
            "student questions whose communities are studied and who benefits from research",
            "student demonstrates sophisticated data reasoning that goes beyond surface patterns",
            "student surfaces structural context for health, environmental, or social outcomes",
        ],
    ),

    "psychology": LensTemplate(
        key="psychology",
        display_name="Psychology",
        description=(
            "Human behavior, research methods, case analysis, "
            "clinical awareness, developmental and social dimensions"
        ),
        analysis_lens=[
            "Application of psychological concepts to human behavior",
            "Research methodology critique and evaluation",
            "Integration of multiple theoretical perspectives",
            "Awareness of cultural context in psychological claims",
            "Distinguishing description from diagnosis",
        ],
        default_interests=[
            "How students apply psychological frameworks to real situations",
            "Whether students interrogate research design and sample limitations",
            "How students handle the line between understanding and pathologizing",
        ],
        equity_attention_framing=(
            "Whose behavior is studied and whose is 'normal'? Which communities "
            "are research subjects vs. researchers? Is 'disorder' located in the "
            "person or in the mismatch between the person and a world built for "
            "one way of being? Whose cultural practices get pathologized?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Psychology):\n"
            "Notice when students from communities historically pathologized by "
            "psychology — Black, Indigenous, disabled, queer, neurodivergent — "
            "bring that knowledge into coursework. A student who says 'my community "
            "doesn't trust therapists' is describing a rational response to historical "
            "harm, not expressing stigma about mental health.\n"
            "Surface when students question whose behavior counts as 'normal' and "
            "whose gets a diagnosis. This is critical thinking about the discipline "
            "itself, not resistance to learning.\n"
            "Note when students recognize that most foundational research used "
            "WEIRD samples (Western, Educated, Industrialized, Rich, Democratic) — "
            "questioning generalizability is methodological sophistication.\n"
            "A student describing neurodivergent experience, disability, or mental "
            "health from the inside is contributing expertise, not oversharing. "
            "Their relationship to the material is different from someone studying "
            "it from the outside — both are valid, but the labor is not equal.\n"
            "When students use culturally specific vocabulary for psychological "
            "experiences — 'susto,' 'nervios,' 'hikikomori,' concepts that don't "
            "map cleanly to DSM categories — this is cultural knowledge, not "
            "imprecise language."
        ),
        assignment_variants={
            "case_study": [
                "Application of theoretical frameworks to the case",
                "Consideration of cultural and structural context",
                "Awareness of diagnostic limitations and power",
            ],
            "research_critique": [
                "Methodology evaluation (sample, design, generalizability)",
                "Identification of researcher assumptions",
                "Alternative interpretations of findings",
            ],
            "reflection": [
                "Personal connection to psychological concepts",
                "Integration of course material with lived observation",
                "Critical self-awareness about positionality",
            ],
        },
        concern_framing_fragment=(
            "CONCERN FRAMING (Psychology):\n"
            "Default patterns apply. Also flag:\n"
            "- Student pathologizes a cultural practice, communication style, or "
            "community norm as a psychological disorder\n"
            "- Student attributes a group's behavior to inherent psychological "
            "traits rather than structural conditions ('people in poverty have "
            "lower impulse control' without examining systemic context)\n"
            "- Student diagnoses a real person (peer, family member, public figure) "
            "based on surface behavior — diagnosis requires clinical assessment, "
            "not pattern-matching from a textbook\n"
            "- Student treats Western psychological frameworks as universal without "
            "acknowledging cultural specificity\n"
            "Neurodivergent self-description is NOT a concern — it is expertise. "
            "Wellbeing signals always apply."
        ),
        default_strength_patterns=[
            "student identifies cultural specificity in psychological research and its limits",
            "student applies psychological concepts to structural rather than individual explanations",
            "student brings lived experience of neurodivergence, disability, or mental health as expertise",
            "student critiques WEIRD sampling or universality assumptions in foundational research",
            "student uses culturally specific vocabulary for psychological experience with precision",
        ],
    ),

    "government_civics": LensTemplate(
        key="government_civics",
        display_name="Government / Civics",
        description=(
            "Democratic participation, institutional analysis, policy reasoning, "
            "constitutional interpretation, civic engagement"
        ),
        analysis_lens=[
            "Understanding of institutional structures and processes",
            "Policy analysis and evidence-based reasoning",
            "Multiple perspectives on governance and power",
            "Connection between civic structures and lived experience",
            "Constitutional and legal reasoning",
        ],
        default_interests=[
            "How students connect institutional structures to their own civic lives",
            "Whether students see governance as something done TO them or BY them",
            "How students reason about policy tradeoffs and competing rights",
        ],
        equity_attention_framing=(
            "Whose citizenship is conditional? Who participates in democracy "
            "and who is subject to it? Which students can discuss 'the system' "
            "abstractly and which are navigating it for survival? Who has been "
            "criminalized by the institutions being studied?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Government/Civics):\n"
            "Notice when students whose communities face policing, immigration "
            "enforcement, voter suppression, or incarceration bring that experience "
            "into coursework — they are not being 'political,' they are describing "
            "how governance operates on their bodies and families. This is primary "
            "source knowledge about the subject matter.\n"
            "Surface when students distinguish between formal rights and actual "
            "access — 'everyone can vote' vs. who actually can, practically. "
            "This is sophisticated institutional analysis.\n"
            "A student who expresses distrust of government institutions is "
            "describing a relationship to power, not demonstrating ignorance "
            "about how government works. A student whose family has been deported, "
            "detained, or disenfranchised has a different relationship to 'civic "
            "participation' than one who assumes access.\n"
            "Note when students from communities that built mutual aid, "
            "sanctuary networks, or parallel governance structures describe "
            "this as civic engagement — it is, even when it isn't recognized "
            "by the formal system being studied."
        ),
        assignment_variants={
            "policy_analysis": [
                "Evidence-based reasoning about policy effects",
                "Consideration of differential impact across communities",
                "Institutional and structural analysis",
            ],
            "discussion": [
                "Engagement with competing civic perspectives",
                "Connection to current events and lived experience",
                "Reasoning about rights, access, and power",
            ],
            "essay": [
                "Constitutional or legal argument development",
                "Multiple perspectives on governance questions",
                "Integration of historical and contemporary evidence",
            ],
        },
        concern_framing_fragment=(
            "CONCERN FRAMING (Government/Civics):\n"
            "Default patterns apply. Also flag:\n"
            "- Student frames criminalization or incarceration as proof of "
            "individual moral failure rather than examining institutional "
            "structures and incentives\n"
            "- Student treats formal legal equality as proof that structural "
            "inequality doesn't exist ('everyone has the same rights now')\n"
            "- Student dismisses community-based governance, mutual aid, or "
            "protest as 'not real' civic participation\n"
            "- Student attributes a community's political conditions to that "
            "community's culture rather than to policy and institutional design\n"
            "Do NOT flag passionate civic engagement, including anger about "
            "injustice — this is the course working as intended."
        ),
        default_strength_patterns=[
            "student brings lived experience of navigating government systems as primary source knowledge",
            "student distinguishes between formal rights and actual community access",
            "student surfaces community-based governance, mutual aid, or resistance as civic practice",
            "student demonstrates sophisticated structural analysis of how policy operates on bodies",
            "student connects historical civic struggles to present conditions",
        ],
    ),

    "health_sciences": LensTemplate(
        key="health_sciences",
        display_name="Health Sciences",
        description=(
            "Health equity, clinical reasoning, patient-centered care, "
            "community health, body and wellness across contexts"
        ),
        analysis_lens=[
            "Understanding of health within structural and social context",
            "Patient/client-centered reasoning",
            "Evidence-based practice and critical appraisal",
            "Awareness of health disparities and their causes",
            "Ethical reasoning in care and research",
        ],
        default_interests=[
            "How students reason about health disparities — structural vs. individual framing",
            "Whether students center the patient/client perspective or the provider/system perspective",
            "How students handle the intersection of clinical evidence and lived experience",
        ],
        equity_attention_framing=(
            "Whose body is 'normal'? Whose pain is believed? Whose health "
            "knowledge — community, Indigenous, ancestral — is dismissed as "
            "'folk medicine'? Who is a research subject and who is a researcher? "
            "Which students are studying health systems that have harmed their "
            "own communities?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Health Sciences):\n"
            "Notice when students from communities with histories of medical "
            "racism — Black, Indigenous, disabled, incarcerated, queer — bring "
            "that knowledge into health coursework. A student who describes their "
            "family's distrust of hospitals is describing a rational response to "
            "Tuskegee, forced sterilization, and ongoing disparities in pain "
            "management. This is health literacy, not health ignorance.\n"
            "Surface when students bring community health knowledge, traditional "
            "medicine, or ancestral healing practices into dialogue with clinical "
            "frameworks — this is integrative thinking, not 'unscientific.'\n"
            "Note when disability is framed as a problem to fix rather than a "
            "way of being in a world built for particular bodies. A student who "
            "challenges the medical model of disability is doing critical work "
            "in the discipline.\n"
            "A student who references their own chronic illness, disability, "
            "caregiving responsibilities, or navigation of healthcare systems "
            "is contributing expertise about the subject matter, not digressing."
        ),
        assignment_variants={
            "case_study": [
                "Clinical reasoning and differential analysis",
                "Patient/client context and social determinants",
                "Ethical considerations and provider positionality",
            ],
            "reflection": [
                "Personal connection to health concepts and systems",
                "Awareness of structural determinants of health",
                "Provider identity development and self-awareness",
            ],
            "discussion": [
                "Evidence-based reasoning about health interventions",
                "Community health perspectives and local knowledge",
                "Ethical reasoning about care, consent, and access",
            ],
        },
        concern_framing_fragment=(
            "CONCERN FRAMING (Health Sciences):\n"
            "Default patterns apply. Also flag:\n"
            "- Student attributes a community's health outcomes to cultural "
            "or behavioral deficits rather than structural determinants "
            "(housing, pollution, food access, insurance, provider bias)\n"
            "- Student dismisses patient/community health knowledge as "
            "'non-compliant' or 'uneducated' rather than understanding it "
            "as a rational response to context\n"
            "- Student frames disability as inherently negative or as a "
            "problem requiring correction, rather than considering the social "
            "model and built environment\n"
            "- Student uses biological essentialism to explain health "
            "disparities across racial groups without engaging with the "
            "evidence on structural causation\n"
            "Wellbeing signals apply with heightened attention — students "
            "in health fields may disclose personal health experiences in "
            "the course of doing the work."
        ),
        default_strength_patterns=[
            "student centers the patient or community perspective rather than the provider or system",
            "student brings community health knowledge or traditional healing practices as valid expertise",
            "student surfaces structural determinants of health disparities",
            "student demonstrates awareness of medical racism or historical harm in health institutions",
            "student applies disability justice or social model frameworks to clinical questions",
        ],
    ),

    "arts": LensTemplate(
        key="arts",
        display_name="Arts",
        description=(
            "Creative practice, aesthetic analysis, cultural tradition, "
            "artistic voice, critique and interpretation"
        ),
        analysis_lens=[
            "Articulation of creative intent and process",
            "Engagement with aesthetic traditions and cultural context",
            "Critical interpretation of artistic works",
            "Development of artistic voice and perspective",
            "Willingness to take creative risks",
        ],
        default_interests=[
            "How students articulate their creative choices and influences",
            "Whether students engage with diverse aesthetic traditions or default to one canon",
            "How students give and receive critique — what power dynamics surface",
        ],
        equity_attention_framing=(
            "Whose aesthetics are 'fine art' and whose are 'craft' or "
            "'folk art'? Whose traditions are studied in survey courses and "
            "whose are electives? Which students are asked to explain their "
            "cultural references and which can assume theirs are universal? "
            "Who has had access to formal training and who brings self-taught, "
            "community-taught, or ancestral knowledge?"
        ),
        equity_prompt_fragment=(
            "EQUITY ATTENTION (Arts):\n"
            "Notice when students draw on cultural, community, or family "
            "artistic traditions — beadwork, muralism, spoken word, textile "
            "arts, hip-hop production, ceremonial design — and whether these "
            "are recognized as artistic practice or marginalized as 'other.' "
            "A student whose artistic lineage is community-based rather than "
            "institution-based is not less trained; they are differently trained.\n"
            "Surface when students challenge what counts as art, whose work "
            "hangs in galleries, or whose aesthetic vocabulary is treated as "
            "the default. This is critical engagement with the discipline.\n"
            "A student who creates work about their community's experience — "
            "migration, displacement, resistance, joy — is doing artistic and "
            "intellectual work simultaneously. Do not separate the political "
            "content from the aesthetic achievement.\n"
            "Note that access to materials, studio space, instruments, and "
            "training is structurally unequal. A student's artistic sophistication "
            "is not measured by their access to resources."
        ),
        assignment_variants={
            "artist_statement": [
                "Articulation of creative intent and influences",
                "Connection between personal/cultural context and artistic choices",
                "Situating work within broader artistic conversations",
            ],
            "critique": [
                "Engagement with the work on its own terms",
                "Awareness of aesthetic traditions informing the work",
                "Constructive dialogue that respects creative risk",
            ],
            "reflection": [
                "Process documentation and creative reasoning",
                "Growth and experimentation over time",
                "Connection between artistic practice and lived experience",
            ],
        },
        concern_framing_fragment=(
            "CONCERN FRAMING (Arts):\n"
            "The humanities-specific default patterns (colorblind claims, "
            "tone policing) apply when students write about art's cultural "
            "and social dimensions. De-weight them for purely formal or "
            "technical analysis unless it becomes a way to avoid engaging "
            "with cultural content.\n"
            "Also flag:\n"
            "- Student dismisses another student's cultural artistic tradition "
            "as 'not real art' or 'primitive' or 'folk'\n"
            "- Student uses another culture's sacred or ceremonial artistic "
            "forms without acknowledgment of origin or significance\n"
            "- Student frames access to formal training, materials, or "
            "institutional spaces as proof of artistic merit\n"
            "Do NOT flag art that expresses pain, rage, grief, or political "
            "conviction — this is what art does."
        ),
        default_strength_patterns=[
            "student articulates connections between their cultural tradition and artistic choices",
            "student brings community or ancestral artistic lineage into the work",
            "student takes creative risks that challenge expected forms or conventions",
            "student demonstrates critical engagement with whose aesthetics are centered",
            "student's artistic voice is distinct and rooted in specific cultural knowledge",
        ],
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
        concern_framing_fragment=(
            "CONCERN FRAMING (General):\n"
            "All default patterns apply. Use judgment about which patterns "
            "are most relevant given the assignment topic."
        ),
        default_strength_patterns=[
            "student makes cross-disciplinary connections",
            "student brings lived experience or community knowledge as evidence",
            "student demonstrates metacognitive awareness of their own thinking",
            "student challenges or extends the scope of the course material",
            "student's engagement reflects care for their community or subject matter",
        ],
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


def get_concern_framing_fragment(subject_key: str) -> str:
    """Return the subject-specific concern framing for a subject area.

    Empty string for general/unknown — the hardcoded defaults apply unmodified.
    """
    t = LENS_TEMPLATES.get(subject_key, LENS_TEMPLATES["general"])
    return t.concern_framing_fragment


def get_default_strength_patterns(subject_key: str) -> List[str]:
    """Return default strength patterns for a subject area.

    Used when a teacher has not defined custom strength patterns.
    Always returns something — falls back to general if key unknown.
    These patterns represent community cultural wealth and non-dominant
    forms of engagement that the pipeline should actively surface.
    """
    t = LENS_TEMPLATES.get(subject_key, LENS_TEMPLATES["general"])
    return list(t.default_strength_patterns)
