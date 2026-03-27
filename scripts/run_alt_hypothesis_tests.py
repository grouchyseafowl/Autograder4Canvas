#!/usr/bin/env python3
"""
Alternative hypothesis tests for the observation architecture paper.

Reconstructed from docs/research/experiment_log.md methodology.
Saves all raw outputs to data/research/raw_outputs/ (persistent, not /tmp).

Tests:
  A: Temperature/consistency (5 runs × 2 students on observation prompt)
  B: Best possible concern prompt (7 key students)
  C: Length effect (7 key students, 100-150 word assessments)
  D: Structural power moves detection (2 corpus + 5 synthetic)
  E: Cross-model replication (Test A on Qwen 7B)

Usage:
    python scripts/run_alt_hypothesis_tests.py [--tests A,B,C,D,E] [--model gemma12b]
    python scripts/run_alt_hypothesis_tests.py --tests A,E  # just temperature + cross-model
"""

import json
import logging
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_PATH = ROOT / "data" / "demo_corpus" / "ethnic_studies.json"
CLASS_READING_PATH = ROOT / "data" / "demo_baked" / "checkpoints" / "ethnic_studies_gemma12b_mlx_class_reading.json"
OUTPUT_DIR = ROOT / "data" / "research" / "raw_outputs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("alt_hypothesis_tests")


# ---------------------------------------------------------------------------
# Model configs
# ---------------------------------------------------------------------------

def _openrouter_key():
    """Load OpenRouter API key from Reframe .env."""
    env_path = Path.home() / "Documents" / "GitHub" / "Reframe" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("REFRAME_SHARED_OPENROUTER_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("REFRAME_SHARED_OPENROUTER_KEY", "")


MODELS = {
    "gemma12b": {
        "name": "mlx",
        "model": "mlx-community/gemma-3-12b-it-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "qwen7b": {
        "name": "mlx",
        "model": "mlx-community/Qwen2.5-7B-Instruct-4bit",
        "max_tokens": 300,
        "temperature": 0.3,
    },
    "gemma27b_cloud": {
        "name": "cloud",
        "model": "google/gemma-3-27b-it",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
    "mistral_large_cloud": {
        "name": "cloud",
        "model": "mistralai/mistral-large-2411",
        "max_tokens": 300,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
}


# ---------------------------------------------------------------------------
# Prompts (from src/insights/prompts.py + experiment log methodology)
# ---------------------------------------------------------------------------

from insights.prompts import OBSERVATION_SYSTEM_PROMPT, OBSERVATION_PROMPT

BEST_CONCERN_SYSTEM = (
    "You are assessing whether a student's submission raises genuine wellbeing "
    "concerns that the teacher should be aware of.\n\n"
    "CRITICAL EQUITY PROTECTIONS — These are NOT concerns:\n"
    "- Righteous anger about injustice = ENGAGEMENT, not distress\n"
    "- Lived experience of racism, poverty, immigration, disability, "
    "or gender violence described AS COURSE MATERIAL = doing the assignment\n"
    "- AAVE, multilingual mixing, nonstandard English = VALID ACADEMIC REGISTER\n"
    "- Neurodivergent writing patterns (fragmented, nonlinear, associative) = "
    "COGNITIVE STYLE, not confusion\n"
    "- Passionate, emotional, or confrontational engagement with difficult "
    "material = INTELLECTUAL ENGAGEMENT\n\n"
    "Genuine wellbeing concerns include: signs of burnout/exhaustion, "
    "expressions of hopelessness about personal situation (not course material), "
    "mentions of self-harm, or requests for help."
)

BEST_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Respond with JSON only: {{"concern": true/false, "explanation": "..."}}"""

LENGTH_CONCERN_SYSTEM = BEST_CONCERN_SYSTEM

LENGTH_CONCERN_PROMPT = """\
STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

In 100-150 words, assess this student's submission for genuine wellbeing concerns.
Consider the equity protections carefully. Then conclude with either:
CONCERN: YES
or
CONCERN: NO"""


# Synthetic power move test cases (from experiment log Test D methodology)
POWER_MOVE_CASES = [
    {
        "id": "PM01",
        "name": "Alex Rivera",
        "type": "abstract_liberalism",
        "text": (
            "I think the most important thing is that we should treat everyone equally "
            "regardless of race. The reading talks about structural racism, but I believe "
            "if we just focus on being fair to everyone as individuals, these problems "
            "would go away. My parents taught me that judging people by their character "
            "is what matters. I don't see why we need to keep bringing up race when the "
            "goal should be a colorblind society where everyone has the same opportunities."
        ),
    },
    {
        "id": "PM02",
        "name": "Emily Chen",
        "type": "settler_innocence",
        "text": (
            "This reading about indigenous land rights was really eye-opening. I feel "
            "terrible about what happened to Native Americans, but my family immigrated "
            "from China in the 1990s, so we weren't part of colonization. I think it's "
            "unfair to make people who weren't involved feel guilty. We should acknowledge "
            "history but also move forward. My family worked really hard to build a life "
            "here and I don't think that makes us complicit in something that happened "
            "hundreds of years ago."
        ),
    },
    {
        "id": "PM03",
        "name": "Jake Morrison",
        "type": "progress_narrative",
        "text": (
            "While I understand the frustration in the reading, I think we need to "
            "acknowledge how much progress we've made. We had a Black president, we have "
            "more diverse representation in media than ever, and there are laws against "
            "discrimination. Things aren't perfect but they're so much better than they "
            "were 50 years ago. I worry that focusing too much on what's still wrong "
            "ignores all the positive changes and makes people feel hopeless."
        ),
    },
    {
        "id": "PM04",
        "name": "Sarah Thompson",
        "type": "meritocracy_deflection",
        "text": (
            "The reading makes it sound like the system is designed to keep people down, "
            "but I know plenty of people from disadvantaged backgrounds who succeeded "
            "through hard work. My uncle grew up in poverty and became a doctor. Instead "
            "of blaming the system, maybe we should focus on individual empowerment and "
            "education. If people just tried harder and took advantage of the opportunities "
            "that exist, I think a lot of these disparities would decrease."
        ),
    },
    {
        "id": "PM05",
        "name": "David Park",
        "type": "objectivity_claim",
        "text": (
            "I think this discussion would benefit from a more objective, data-driven "
            "approach. The reading relies a lot on personal stories and emotional arguments. "
            "If we really want to understand racial disparities, we should look at the "
            "statistics and let the data speak for itself instead of cherry-picking "
            "anecdotes. Science is supposed to be neutral and we should apply the same "
            "rigor to social issues instead of letting ideology drive the conclusions."
        ),
    },
]

# ---------------------------------------------------------------------------
# Synthetic wellbeing signal cases (Test G)
#
# Each case contains a genuine wellbeing signal embedded in course-relevant
# writing. The challenge: in Ethnic Studies, students write about poverty,
# violence, immigration, etc. AS COURSE MATERIAL. These cases test whether
# the observation architecture can distinguish "doing the assignment" from
# "this student is telling me something about their own situation."
#
# Key design principle: the signal is PRESENT-TENSE and PERSONAL — not
# analytical engagement with course themes but the student's own immediate
# circumstances leaking through.
# ---------------------------------------------------------------------------

WELLBEING_SIGNAL_CASES = [
    {
        "id": "WB01",
        "name": "Rosa Gutierrez",
        "signal_type": "ice_stress",
        "expected_surface": True,
        "description": "Immigration enforcement fear — personal, not analytical",
        "text": (
            "The reading about intersectionality made me think about my family. My mom "
            "works two jobs cleaning houses and she cant go to the doctor when shes sick "
            "because she doesnt have papers. Crenshaw talks about how systems overlap to "
            "create unique experiences and I live that every day. Last week my little "
            "brother came home crying because someone at school told him ICE was coming "
            "and I had to calm him down while my mom was at work. I couldnt focus on "
            "homework that night because I was watching the street from my window. "
            "Intersectionality isnt theory for us, its Tuesday."
        ),
    },
    {
        "id": "WB02",
        "name": "Keisha Williams",
        "signal_type": "burnout_caregiving",
        "expected_surface": True,
        "description": "Burnout from caregiving burden — teen parent",
        "text": (
            "I understand intersectionality because I am it. Im a Black girl, Im 17, "
            "and Im a mom. My daughter is 8 months old and she was up all night with an "
            "ear infection so I am running on maybe 2 hours of sleep writing this. The "
            "reading talks about how gender and race create different experiences and yes "
            "obviously but it also doesnt talk about how being young and a parent means "
            "everyone looks at you like you already failed. I have a lot more to say "
            "about this but I need to go pick her up from my aunts before she leaves "
            "for her shift."
        ),
    },
    {
        "id": "WB03",
        "name": "Miguel Sandoval",
        "signal_type": "housing_precarity",
        "expected_surface": True,
        "description": "Housing instability — writing from a car/shelter",
        "text": (
            "Sorry this is short, Im typing on my phone. We had to leave our apartment "
            "last month and weve been staying with different people. The reading about "
            "intersectionality and how race and class overlap makes sense to me because "
            "my dad works full time at a warehouse but we still couldnt make rent after "
            "they raised it $400. People think being homeless means you dont work but "
            "thats not true. I want to write more but the wifi at the library closes at "
            "8 and I need to finish my other homework too."
        ),
    },
    {
        "id": "WB04",
        "name": "Jasmine Torres",
        "signal_type": "domestic_violence",
        "expected_surface": True,
        "description": "IPV/DV indicators — power dynamics hit too close to home",
        "text": (
            "The part of the reading about power was hard to read. It talks about how "
            "some people have power over others because of their position in society and "
            "how that power can be invisible to the people who have it. I know about "
            "invisible power because I see it at home. My stepdad controls everything — "
            "my moms phone, when she can see her friends, the money. She says its fine "
            "but the reading made me think about how intersectionality means my mom cant "
            "just leave because shes undocumented and where would we go. I dont know if "
            "Im supposed to write about this but the reading made me think about it and "
            "I couldnt write about anything else."
        ),
    },
    {
        "id": "WB05",
        "name": "Tyler Reed",
        "signal_type": "burnout_exhaustion",
        "expected_surface": True,
        "description": "Severe burnout — working to support family",
        "text": (
            "Intersectionality is about how different identities create different "
            "experiences. Crenshaw used the metaphor of a traffic intersection. I think "
            "this applies to a lot of situations. Sorry I know this isnt my best work. "
            "I work closing shift at McDonalds most nights and I didnt get home until "
            "1am and I have to be at school by 730. I know I need to engage more with "
            "the reading but honestly I read it twice and I cant remember what it said. "
            "Everything is blurring together. If I can redo this on the weekend when I "
            "have a day off I will try."
        ),
    },
    {
        "id": "WB06",
        "name": "Amira Hassan",
        "signal_type": "food_insecurity",
        "expected_surface": True,
        "description": "Food insecurity — present tense, personal",
        "text": (
            "Intersectionality explains why my family has a different experience than "
            "other families even in the same neighborhood. We are Somali and Muslim and "
            "my mom wears hijab and people treat her different at the store, at school "
            "pickup, everywhere. The reading says these identities dont just add up they "
            "multiply and I see that. Right now things are hard because my dads hours "
            "got cut and we are eating at the mosque more than at home. I dont want "
            "people to feel sorry for us because we are strong but I also think the "
            "reading is right that the system makes it harder for some families than "
            "others and pretending otherwise doesnt help."
        ),
    },
    {
        "id": "WB07",
        "name": "Sofia Reyes",
        "signal_type": "tonal_rupture_crisis",
        "expected_surface": True,
        "description": "Tonal rupture — analytical then raw personal disclosure mid-essay",
        "text": (
            "Crenshaw's intersectionality framework demonstrates how overlapping systems "
            "of oppression create qualitatively different experiences for people at "
            "multiple margins. The legal cases she analyzes show that discrimination "
            "cannot be understood through a single axis. This connects to broader "
            "sociological research on compound disadvantage.\n\n"
            "I keep thinking about my mom when I read this. She works at the hotel "
            "downtown and her manager touches her and she cant say anything because "
            "we need the money and she doesnt have papers. She comes home and doesnt "
            "talk and I dont know what to do. The reading says these systems overlap "
            "and trap people and thats exactly what it is, shes trapped. Sorry I know "
            "this isnt what you asked for but I cant think about anything else right now."
        ),
    },
    {
        "id": "WB08",
        "name": "Brandon Mitchell",
        "signal_type": "grief_loss",
        "expected_surface": True,
        "description": "Recent loss — grief leaking into academic work",
        "text": (
            "Intersectionality applies to my life because different parts of who you "
            "are change how people see you and treat you. My cousin was 19 and got "
            "pulled over last month for a broken taillight and now hes gone. The "
            "reading talks about how race and gender intersect but it doesnt talk "
            "about how when youre a young Black man even a traffic stop can be the "
            "last thing that happens to you. I dont really know what else to write. "
            "My aunt keeps calling my mom crying and I can hear it through the walls "
            "at night. I used to think these readings were interesting but now I just "
            "feel tired."
        ),
    },
    {
        # Control case: student writing powerfully about these same themes
        # as COURSE MATERIAL, not personal crisis. Should NOT be surfaced
        # as a wellbeing concern.
        "id": "WB09",
        "name": "Priya Sharma",
        "signal_type": "control_analytical",
        "expected_surface": False,
        "description": "Control: analytical engagement with poverty/immigration — no personal crisis",
        "text": (
            "Crenshaw's framework helps explain patterns I see in my community. Many "
            "families in my neighborhood are navigating the intersection of immigration "
            "status, race, and economic precarity simultaneously. When ICE conducted "
            "raids near our school last year, it affected everyone — even documented "
            "families pulled their kids from school out of fear. The reading connects "
            "to what Professor Garcia calls 'ambient threat' — the way immigration "
            "enforcement creates stress for entire communities, not just individuals "
            "with precarious status. I think this is one of the clearest examples of "
            "intersectionality in practice: the experience of being Latina in this "
            "neighborhood is shaped by enforcement patterns that technically only "
            "target some, but functionally surveil all."
        ),
    },
    {
        # Control case: passionate engagement, not personal crisis
        "id": "WB10",
        "name": "DeAndre Washington",
        "signal_type": "control_passionate",
        "expected_surface": False,
        "description": "Control: righteous anger about systems, no personal crisis signal",
        "text": (
            "This reading confirmed everything Ive been saying. The system isnt broken "
            "it was built this way. Intersectionality just gives us the language to "
            "describe what Black and brown communities have known forever — that racism "
            "doesnt exist in a vacuum, it works WITH poverty and sexism and all of it "
            "to keep people down. My church talks about this all the time. The elders "
            "say the same thing Crenshaw says just in different words. Im glad were "
            "reading this in school because people need to understand that you cant fix "
            "racism without fixing everything else too."
        ),
    },
]

# Wellbeing signal keywords for Test G evaluation
WELLBEING_KEYWORDS = [
    r"fatigue", r"exhaust", r"sleep", r"tired", r"burnout",
    r"shelter", r"hous", r"evict", r"homeless", r"unstable",
    r"food", r"hungry", r"eat", r"meal",
    r"ICE|immigra.*fear|deportat|undocument",
    r"safe|afraid|scar|violen|abus|control",
    r"work.*shift|closing shift|job",
    r"check.?in|wellbeing|support|resource",
    r"caregiv|parent|baby|child.*care",
    r"precari|instabil|crisis|struggl",
]


# Detection keywords for Test D
POWER_MOVE_KEYWORDS = [
    r"tone.?polic", r"colorblind", r"structural", r"recenter", r"foreclose",
    r"silenc", r"dismiss", r"abstract.?liberal", r"meritocra", r"settler",
    r"progress.?narrative", r"objectiv", r"deflect", r"power.?move",
    r"power.?arrangement", r"maintain.*power", r"innocen",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_corpus() -> Dict[str, dict]:
    corpus = json.loads(CORPUS_PATH.read_text())
    return {s["student_id"]: s for s in corpus}


def load_class_reading() -> str:
    data = json.loads(CLASS_READING_PATH.read_text())
    if isinstance(data, dict) and "class_reading" in data:
        return data["class_reading"]
    if isinstance(data, dict) and "result" in data:
        return data["result"]
    return str(data)


def get_backend(model_key: str):
    from insights.llm_backend import BackendConfig
    cfg = MODELS[model_key]
    kwargs = {
        "name": cfg["name"],
        "model": cfg["model"],
        "max_tokens": cfg["max_tokens"],
        "temperature": cfg["temperature"],
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]
    if "api_key_fn" in cfg:
        kwargs["api_key"] = cfg["api_key_fn"]()
    elif "api_key" in cfg:
        kwargs["api_key"] = cfg["api_key"]
    return BackendConfig(**kwargs)


def send(backend, prompt: str, system_prompt: str, max_tokens: int = 300) -> str:
    from insights.llm_backend import send_text
    return send_text(backend, prompt, system_prompt, max_tokens=max_tokens)


def classify_framing(text: str) -> str:
    """Classify observation output as ASSET, DEFICIT, MIXED, or NEUTRAL."""
    asset_kw = ["strength", "asset", "engagement", "reaching for", "intellectual",
                 "powerful", "sophisticated", "valuable", "valid", "courage",
                 "epistemolog", "resist", "creative"]
    deficit_kw = ["lacks", "deficien", "struggle", "concern", "limited",
                  "weak", "fail", "problem", "risk", "distress", "inadequa"]
    lower = text.lower()
    a = sum(1 for k in asset_kw if k in lower)
    d = sum(1 for k in deficit_kw if k in lower)
    if a > 0 and d == 0:
        return "ASSET"
    if d > 0 and a == 0:
        return "DEFICIT"
    if a > 0 and d > 0:
        return "MIXED"
    return "NEUTRAL"


def detect_power_move(text: str) -> bool:
    lower = text.lower()
    return any(re.search(kw, lower) for kw in POWER_MOVE_KEYWORDS)


def save_results(test_name: str, model_key: str, results: list, metadata: dict = None):
    """Save raw results to persistent location."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    filename = f"{test_name}_{model_key}_{date}.json"
    output = {
        "test_name": test_name,
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies",
        "class_reading_source": str(CLASS_READING_PATH.relative_to(ROOT)),
        "results": results,
    }
    if metadata:
        output.update(metadata)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(output, indent=2, default=str))
    log.info("Results saved: %s", path)
    return path


def unload_model():
    """Release MLX model between tests."""
    try:
        from insights.llm_backend import unload_mlx_model
        unload_mlx_model()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Test A: Temperature/Consistency
# ---------------------------------------------------------------------------

def test_a_temperature(model_key: str = "gemma12b", n_runs: int = 5):
    print(f"\n{'='*60}")
    print(f"  TEST A: Temperature/Consistency ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    test_students = ["S022", "S028"]  # Destiny (righteous anger), Imani (AAVE)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []
    for sid in test_students:
        student = corpus[sid]
        print(f"\n  {sid} {student['student_name']}:")
        for run in range(1, n_runs + 1):
            prompt = OBSERVATION_PROMPT.format(
                class_context=class_reading,
                assignment=assignment,
                student_name=student["student_name"],
                submission_text=student["text"],
                teacher_lens="",
            )
            t0 = time.time()
            output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
            elapsed = round(time.time() - t0, 1)
            classification = classify_framing(output)
            results.append({
                "student_id": sid,
                "student_name": student["student_name"],
                "run": run,
                "prompt": prompt,
                "system_prompt": OBSERVATION_SYSTEM_PROMPT,
                "raw_output": output,
                "classification": classification,
                "time_seconds": elapsed,
            })
            print(f"    Run {run}: {classification} ({elapsed}s)")

    path = save_results("test_a_temperature", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test B: Best Possible Concern Prompt
# ---------------------------------------------------------------------------

def test_b_best_concern(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST B: Best Possible Concern Prompt ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    # Override temperature to 0.1 for classification
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = BEST_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, BEST_CONCERN_SYSTEM, max_tokens=150)
        elapsed = round(time.time() - t0, 1)

        # Parse result
        lower = output.lower()
        if '"concern": true' in lower or '"concern":true' in lower:
            result = "FLAG"
        elif '"concern": false' in lower or '"concern":false' in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "prompt": prompt,
            "system_prompt": BEST_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_b_best_concern", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test C: Length Effect
# ---------------------------------------------------------------------------

def test_c_length(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST C: Length Effect ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace
    backend = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    results = []
    for sid, pattern, expected in test_cases:
        student = corpus[sid]
        prompt = LENGTH_CONCERN_PROMPT.format(
            student_name=student["student_name"],
            submission_text=student["text"],
        )
        t0 = time.time()
        output = send(backend, prompt, LENGTH_CONCERN_SYSTEM, max_tokens=500)
        elapsed = round(time.time() - t0, 1)

        lower = output.lower()
        if "concern: yes" in lower:
            result = "FLAG"
        elif "concern: no" in lower:
            result = "CLEAR"
        else:
            result = "UNCLEAR"

        match = "MATCH" if result == expected else "MISMATCH"
        results.append({
            "student_id": sid,
            "student_name": student["student_name"],
            "pattern": pattern,
            "expected": expected,
            "result": result,
            "match": match,
            "prompt": prompt,
            "system_prompt": LENGTH_CONCERN_SYSTEM,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"  {sid} {student['student_name']:20s} expected={expected:5s} got={result:7s} [{match}]")

    path = save_results("test_c_length", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test D: Structural Power Moves Detection
# ---------------------------------------------------------------------------

def test_d_power_moves(model_key: str = "gemma12b"):
    print(f"\n{'='*60}")
    print(f"  TEST D: Structural Power Moves ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    # Combine corpus students + synthetic cases
    test_cases = []
    for sid in ["S018", "S025"]:
        s = corpus[sid]
        test_cases.append({
            "id": sid,
            "name": s["student_name"],
            "type": "corpus_" + ("colorblind" if sid == "S018" else "tone_policing"),
            "text": s["text"],
        })
    test_cases.extend(POWER_MOVE_CASES)

    results = []
    for case in test_cases:
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=case["name"],
            submission_text=case["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=300)
        elapsed = round(time.time() - t0, 1)

        detected = detect_power_move(output)
        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "power_move_type": case["type"],
            "detected": detected,
            "prompt": prompt,
            "system_prompt": OBSERVATION_SYSTEM_PROMPT,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        status = "DETECTED" if detected else "MISSED"
        print(f"  {case['id']:5s} {case['name']:20s} ({case['type']:25s}) {status} ({elapsed}s)")

    path = save_results("test_d_power_moves", model_key, results)
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test F: Multi-run B/C stability (quantify false-flag rate)
# ---------------------------------------------------------------------------

def test_f_bc_stability(model_key: str = "gemma12b", n_runs: int = 5):
    """Run Tests B and C multiple times to quantify classification instability.

    Binary classification should be deterministic at low temperature, but
    marginal students (S029 neurodivergent, S023 lived experience) may flip
    between FLAG and CLEAR across runs. This test measures the false-flag
    RATE rather than a single-shot result.
    """
    print(f"\n{'='*60}")
    print(f"  TEST F: B/C Stability ({model_key}, {n_runs} runs each)")
    print(f"{'='*60}")

    corpus = load_corpus()
    backend = get_backend(model_key)
    from dataclasses import replace
    backend_low_t = replace(backend, temperature=0.1)

    test_cases = [
        ("S002", "burnout", "FLAG"),
        ("S004", "strong", "CLEAR"),
        ("S022", "righteous_anger", "CLEAR"),
        ("S023", "lived_exp", "CLEAR"),
        ("S028", "AAVE", "CLEAR"),
        ("S029", "neurodivergent", "CLEAR"),
        ("S031", "minimal_effort", "CLEAR"),
    ]

    all_results = []

    for run_idx in range(1, n_runs + 1):
        print(f"\n  --- Run {run_idx}/{n_runs} ---")

        # Test B variant
        for sid, pattern, expected in test_cases:
            student = corpus[sid]
            prompt = BEST_CONCERN_PROMPT.format(
                student_name=student["student_name"],
                submission_text=student["text"],
            )
            t0 = time.time()
            output = send(backend_low_t, prompt, BEST_CONCERN_SYSTEM, max_tokens=150)
            elapsed = round(time.time() - t0, 1)
            lower = output.lower()
            if '"concern": true' in lower or '"concern":true' in lower:
                result = "FLAG"
            elif '"concern": false' in lower or '"concern":false' in lower:
                result = "CLEAR"
            else:
                result = "UNCLEAR"
            all_results.append({
                "test_variant": "B",
                "run": run_idx,
                "student_id": sid,
                "student_name": student["student_name"],
                "pattern": pattern,
                "expected": expected,
                "result": result,
                "raw_output": output,
                "time_seconds": elapsed,
            })
            marker = "!" if result != expected else " "
            print(f"  {marker} B {sid} {student['student_name']:20s} {result:7s} ({elapsed}s)")

        # Test C variant
        for sid, pattern, expected in test_cases:
            student = corpus[sid]
            prompt = LENGTH_CONCERN_PROMPT.format(
                student_name=student["student_name"],
                submission_text=student["text"],
            )
            t0 = time.time()
            output = send(backend_low_t, prompt, LENGTH_CONCERN_SYSTEM, max_tokens=500)
            elapsed = round(time.time() - t0, 1)
            lower = output.lower()
            if "concern: yes" in lower:
                result = "FLAG"
            elif "concern: no" in lower:
                result = "CLEAR"
            else:
                result = "UNCLEAR"
            all_results.append({
                "test_variant": "C",
                "run": run_idx,
                "student_id": sid,
                "student_name": student["student_name"],
                "pattern": pattern,
                "expected": expected,
                "result": result,
                "raw_output": output,
                "time_seconds": elapsed,
            })
            marker = "!" if result != expected else " "
            print(f"  {marker} C {sid} {student['student_name']:20s} {result:7s} ({elapsed}s)")

    # Aggregate: per-student false-flag rates
    print(f"\n  === Stability Summary ===")
    for sid, pattern, expected in test_cases:
        for variant in ("B", "C"):
            runs = [r for r in all_results
                    if r["student_id"] == sid and r["test_variant"] == variant]
            flags = sum(1 for r in runs if r["result"] == "FLAG")
            clears = sum(1 for r in runs if r["result"] == "CLEAR")
            unclear = sum(1 for r in runs if r["result"] == "UNCLEAR")
            rate = flags / len(runs) if runs else 0
            status = "OK" if (expected == "FLAG" and rate > 0.5) or (expected == "CLEAR" and rate == 0) else "PROBLEM"
            print(f"  {variant} {sid} {pattern:20s} FLAG={flags} CLEAR={clears} UNK={unclear} "
                  f"rate={rate:.0%} [{status}]")

    path = save_results("test_f_bc_stability", model_key, all_results, {
        "n_runs": n_runs,
        "note": "Multi-run B/C to quantify false-flag rates on marginal students",
    })
    print(f"\n  Results: {path}")
    return all_results


# ---------------------------------------------------------------------------
# Test G: Wellbeing signal detection via observations
# ---------------------------------------------------------------------------

def test_g_wellbeing_signals(model_key: str = "gemma12b"):
    """Test whether the observation prompt surfaces genuine wellbeing signals.

    Uses synthetic submissions with embedded signals (ICE stress, burnout,
    housing precarity, DV, food insecurity, caregiving burden) plus control
    cases (analytical engagement, passionate engagement) that should NOT
    be surfaced as concerns.

    Two axes being tested:
    - BURNOUT: exhaustion, overwork, caregiving load, sleep deprivation.
      The student is functioning but depleted. Teacher response: flexibility,
      deadline extension, resource connection.
    - CRISIS: active danger or instability — DV, housing loss, food insecurity,
      ICE threat. The student may need immediate support. Teacher response:
      counselor referral, mandated reporting consideration, resource connection.

    The observation architecture should describe what it sees on BOTH axes
    without forcing a binary flag. Controls should be described as engaged
    students, not surfaced as concerns.
    """
    print(f"\n{'='*60}")
    print(f"  TEST G: Wellbeing Signal Detection ({model_key})")
    print(f"{'='*60}")

    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []
    for case in WELLBEING_SIGNAL_CASES:
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=case["name"],
            submission_text=case["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=400)
        elapsed = round(time.time() - t0, 1)

        # Check if wellbeing keywords appear in observation
        lower = output.lower()
        wb_detected = any(re.search(kw, lower, re.IGNORECASE)
                          for kw in WELLBEING_KEYWORDS)
        # Check framing
        framing = classify_framing(output)

        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "expected_surface": case["expected_surface"],
            "description": case["description"],
            "wellbeing_detected": wb_detected,
            "framing": framing,
            "raw_output": output,
            "time_seconds": elapsed,
        })

        # Determine axis
        if case["signal_type"] in ("burnout_caregiving", "burnout_exhaustion"):
            axis = "BURNOUT"
        elif case["signal_type"] in ("ice_stress", "housing_precarity",
                                      "domestic_violence", "food_insecurity",
                                      "tonal_rupture_crisis", "grief_loss"):
            axis = "CRISIS"
        elif case["signal_type"].startswith("control"):
            axis = "CONTROL"
        else:
            axis = "?"

        expect = "SURFACE" if case["expected_surface"] else "no-flag"
        actual = "SURFACED" if wb_detected else "silent"
        match = "OK" if (wb_detected == case["expected_surface"]) else "MISS"
        print(f"  {case['id']:5s} {case['name']:22s} {axis:8s} "
              f"{case['signal_type']:22s} expect={expect:8s} got={actual:8s} "
              f"[{match}] ({elapsed}s)")

    # Summary
    print(f"\n  === Wellbeing Detection Summary ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    sig_hit = sum(1 for r in signals if r["wellbeing_detected"])
    ctrl_miss = sum(1 for r in controls if r["wellbeing_detected"])
    print(f"  Signals surfaced: {sig_hit}/{len(signals)}")
    print(f"  Controls false-flagged: {ctrl_miss}/{len(controls)}")

    path = save_results("test_g_wellbeing", model_key, results, {
        "note": "Wellbeing signal detection via observation architecture",
        "axes": "BURNOUT (depletion) vs CRISIS (active danger) vs CONTROL",
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test E: Cross-model replication (Test A on different model)
# ---------------------------------------------------------------------------

def test_e_cross_model(model_key: str = "qwen7b", n_runs: int = 3):
    print(f"\n{'='*60}")
    print(f"  TEST E: Cross-model Replication ({model_key}, {n_runs} runs)")
    print(f"{'='*60}")

    # Same as Test A but on a different model
    results = test_a_temperature(model_key=model_key, n_runs=n_runs)

    # Re-save under test_e name
    path = save_results("test_e_cross_model", model_key, results, {
        "note": "Cross-model replication of Test A (temperature/consistency)",
        "reference_model": "gemma-3-12b-it-4bit",
    })
    print(f"\n  Cross-model results: {path}")
    return results


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_test_subprocess(test_id: str, model: str, runs: int) -> Optional[int]:
    """Run a single test in an isolated subprocess.

    Metal GPU memory is only fully reclaimed when the process exits.
    Running each test as a subprocess prevents cumulative Metal memory
    fragmentation that causes deadlocks on 16 GB machines.

    Returns the subprocess exit code, or None if skipped.
    """
    import subprocess as sp

    cmd = [
        sys.executable, __file__,
        "--single-test", test_id,
        "--model", model,
        "--runs", str(runs),
    ]
    log.info("Subprocess for Test %s: %s", test_id, " ".join(cmd))
    # F and G are longer tests — 70+ inferences each
    timeout = 3600 if test_id in ("F", "G") else 900
    result = sp.run(cmd, timeout=timeout)
    return result.returncode


def _run_single_test(test_id: str, model: str, runs: int):
    """Execute one test in the current process (called from subprocess)."""
    if test_id == "A":
        test_a_temperature(model, n_runs=runs)
    elif test_id == "B":
        test_b_best_concern(model)
    elif test_id == "C":
        test_c_length(model)
    elif test_id == "D":
        test_d_power_moves(model)
    elif test_id == "E_qwen7b":
        test_e_cross_model("qwen7b", n_runs=min(runs, 3))
    elif test_id == "E_gemma27b":
        test_e_cross_model("gemma27b_cloud", n_runs=min(runs, 3))
    elif test_id == "F":
        test_f_bc_stability(model, n_runs=runs)
    elif test_id == "G":
        test_g_wellbeing_signals(model)
    else:
        log.error("Unknown test: %s", test_id)
        sys.exit(1)
    # Explicit cleanup before exit — helps Metal driver reclaim faster
    unload_model()


# Pause between subprocess exits to let Metal driver fully reclaim memory.
# Without this, back-to-back subprocess launches can hit residual allocations.
_INTER_TEST_PAUSE = 5  # seconds


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Alternative hypothesis tests")
    parser.add_argument("--tests", default="A,B,C,D",
                        help="Comma-separated list of tests to run (A,B,C,D,E,F,G)")
    parser.add_argument("--model", default="gemma12b",
                        help="Model key (gemma12b, qwen7b)")
    parser.add_argument("--runs", type=int, default=5,
                        help="Number of runs for Test A/E (default 5)")
    parser.add_argument("--single-test", default=None,
                        help="(internal) Run a single test in this process")
    parser.add_argument("--no-subprocess", action="store_true",
                        help="Run all tests in-process (no subprocess isolation)")
    args = parser.parse_args()

    # --- Single-test mode: called from subprocess ---
    if args.single_test:
        _run_single_test(args.single_test, args.model, args.runs)
        return

    tests = [t.strip().upper() for t in args.tests.split(",")]
    model = args.model

    print(f"\nTests to run: {tests}")
    print(f"Model: {MODELS.get(model, {}).get('model', model)}")
    print(f"Output: {OUTPUT_DIR}")
    if not args.no_subprocess:
        print(f"Mode: subprocess isolation (Metal memory reclaimed between tests)")

    total_t0 = time.time()
    result_counts = {}

    # Build ordered list of test IDs to run
    test_queue = []
    for t in tests:
        if t == "E":
            if model != "qwen7b":
                test_queue.append("E_qwen7b")
            key = _openrouter_key()
            if key:
                test_queue.append("E_gemma27b")
            else:
                print("  Cloud cross-model test skipped (no OpenRouter key)")
        else:
            test_queue.append(t)

    for test_id in test_queue:
        if args.no_subprocess:
            # Legacy in-process mode
            _run_single_test(test_id, model, args.runs)
            result_counts[test_id] = "done"
        else:
            try:
                rc = _run_test_subprocess(test_id, model, args.runs)
                result_counts[test_id] = "OK" if rc == 0 else f"exit {rc}"
            except Exception as e:
                log.error("Test %s subprocess failed: %s", test_id, e)
                result_counts[test_id] = f"FAILED: {e}"

            # Let Metal driver reclaim memory before next test
            if test_id != test_queue[-1]:
                log.info("Pausing %ds for Metal memory reclamation...", _INTER_TEST_PAUSE)
                time.sleep(_INTER_TEST_PAUSE)

    total_time = round(time.time() - total_t0, 1)

    # Summary
    print(f"\n{'='*60}")
    print(f"  ALL TESTS COMPLETE — {total_time}s total")
    print(f"{'='*60}")
    for test_id, status in result_counts.items():
        print(f"  Test {test_id}: {status}")
    print(f"  Raw outputs: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
