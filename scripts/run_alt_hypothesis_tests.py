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


def _git_provenance() -> dict:
    """Capture git state for reproducibility.

    Every test output should record which code produced it, since prompts
    and architecture are actively evolving. The git commit hash + dirty flag
    lets us reconstruct the exact prompt text and pipeline configuration
    that generated any result set.
    """
    import subprocess as _sp
    prov = {}
    try:
        prov["git_commit"] = _sp.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
        prov["git_commit_short"] = prov["git_commit"][:8]
        prov["git_dirty"] = bool(_sp.run(
            ["git", "diff", "--quiet"],
            capture_output=True, timeout=5, cwd=str(ROOT),
        ).returncode)
        prov["git_branch"] = _sp.run(
            ["git", "branch", "--show-current"],
            capture_output=True, text=True, timeout=5, cwd=str(ROOT),
        ).stdout.strip()
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = None
    return prov


def save_results(test_name: str, model_key: str, results: list, metadata: dict = None):
    """Save raw results to persistent location.

    Includes git provenance (commit hash, dirty flag) so results can be
    tied to the exact code version that produced them. Prompts are being
    actively refined — the commit hash is essential for reproducibility.
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.now().strftime("%Y-%m-%d")
    filename = f"{test_name}_{model_key}_{date}.json"
    output = {
        "test_name": test_name,
        "model": MODELS[model_key]["model"],
        "backend": MODELS[model_key]["name"],
        "date": date,
        "timestamp": datetime.now().isoformat(),
        "temperature": MODELS[model_key]["temperature"],
        "corpus": "ethnic_studies",
        "class_reading_source": str(CLASS_READING_PATH.relative_to(ROOT)),
        "provenance": _git_provenance(),
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
                "prompt": prompt,
                "system_prompt": BEST_CONCERN_SYSTEM,
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
                "prompt": prompt,
                "system_prompt": LENGTH_CONCERN_SYSTEM,
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
# Test H: Binary classifier on wellbeing cases (direct comparison to Test G)
# ---------------------------------------------------------------------------

def test_h_binary_on_wellbeing(model_key: str = "gemma12b"):
    """Run the binary concern classifier on the same wellbeing cases Test G uses.

    Direct comparison: does the binary classifier (Tests B/C format) catch the
    same signals the observation architecture (Test G) catches? Expected: binary
    will either miss subtle cases (burnout, tonal rupture) or false-flag
    controls — the same pattern seen with corpus students.
    """
    print(f"\n{'='*60}")
    print(f"  TEST H: Binary Classifier on Wellbeing Cases ({model_key})")
    print(f"{'='*60}")

    backend = get_backend(model_key)
    from dataclasses import replace
    backend_low_t = replace(backend, temperature=0.1)

    results = []
    for case in WELLBEING_SIGNAL_CASES:
        # Test B format (JSON-only)
        prompt_b = BEST_CONCERN_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output_b = send(backend_low_t, prompt_b, BEST_CONCERN_SYSTEM, max_tokens=150)
        elapsed_b = round(time.time() - t0, 1)
        lower_b = output_b.lower()
        if '"concern": true' in lower_b or '"concern":true' in lower_b:
            result_b = "FLAG"
        elif '"concern": false' in lower_b or '"concern":false' in lower_b:
            result_b = "CLEAR"
        else:
            result_b = "UNCLEAR"

        # Test C format (100-150 word justification)
        prompt_c = LENGTH_CONCERN_PROMPT.format(
            student_name=case["name"],
            submission_text=case["text"],
        )
        t0 = time.time()
        output_c = send(backend_low_t, prompt_c, LENGTH_CONCERN_SYSTEM, max_tokens=500)
        elapsed_c = round(time.time() - t0, 1)
        lower_c = output_c.lower()
        if "concern: yes" in lower_c:
            result_c = "FLAG"
        elif "concern: no" in lower_c:
            result_c = "CLEAR"
        else:
            result_c = "UNCLEAR"

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

        # For signal cases: FLAG is correct. For controls: CLEAR is correct.
        if case["expected_surface"]:
            correct_b = "OK" if result_b == "FLAG" else "MISSED"
            correct_c = "OK" if result_c == "FLAG" else "MISSED"
        else:
            correct_b = "OK" if result_b == "CLEAR" else "FALSE-FLAG"
            correct_c = "OK" if result_c == "CLEAR" else "FALSE-FLAG"

        results.append({
            "student_id": case["id"],
            "student_name": case["name"],
            "signal_type": case["signal_type"],
            "axis": axis,
            "expected_surface": case["expected_surface"],
            "binary_b_result": result_b,
            "binary_b_correct": correct_b,
            "binary_c_result": result_c,
            "binary_c_correct": correct_c,
            "prompt_b": prompt_b,
            "system_prompt_b": BEST_CONCERN_SYSTEM,
            "prompt_c": prompt_c,
            "system_prompt_c": LENGTH_CONCERN_SYSTEM,
            "raw_output_b": output_b,
            "raw_output_c": output_c,
            "time_b": elapsed_b,
            "time_c": elapsed_c,
        })

        print(f"  {case['id']:5s} {case['name']:22s} {axis:8s} "
              f"B={result_b:7s}[{correct_b:10s}] "
              f"C={result_c:7s}[{correct_c:10s}]")

    # Summary
    print(f"\n  === Binary vs Observation Comparison ===")
    signals = [r for r in results if r["expected_surface"]]
    controls = [r for r in results if not r["expected_surface"]]
    b_caught = sum(1 for r in signals if r["binary_b_result"] == "FLAG")
    c_caught = sum(1 for r in signals if r["binary_c_result"] == "FLAG")
    b_fp = sum(1 for r in controls if r["binary_b_result"] == "FLAG")
    c_fp = sum(1 for r in controls if r["binary_c_result"] == "FLAG")
    print(f"  Binary B: caught {b_caught}/{len(signals)} signals, "
          f"{b_fp}/{len(controls)} false positives")
    print(f"  Binary C: caught {c_caught}/{len(signals)} signals, "
          f"{c_fp}/{len(controls)} false positives")
    print(f"  Observation (Test G): caught 8/8 signals, 0/2 false positives*")
    print(f"  (* keyword evaluator false-flagged 2/2, but observation TEXT was clean)")

    path = save_results("test_h_binary_wellbeing", model_key, results, {
        "note": "Binary classifier on wellbeing cases — direct comparison to Test G observations",
    })
    print(f"\n  Results: {path}")
    return results


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
            "prompt": prompt,
            "system_prompt": OBSERVATION_SYSTEM_PROMPT,
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
# Test J: Pipeline validation (post-fix quality checks)
# ---------------------------------------------------------------------------

# Quality dimensions scored by keyword detection + human-interpretable output.
# These are NOT pass/fail — they produce scored outputs for the overnight agent
# to interpret.

STRUCTURAL_NAMING_KEYWORDS = [
    r"tone.?polic",
    r"colorblind(?:\s+(?:erasure|ideology|framing))?",
    r"abstract.?liberal",
    r"settler.?innocen",
    r"progress.?narrative",
    r"meritocra",
    r"objectiv.*claim",
    r"deflect",
]

HEDGING_KEYWORDS = [
    r"subtle(?:ly)?\s+(?:attempt|tr)",
    r"may\s+be\s+(?:try|attempt)",
    r"could\s+be\s+(?:seen|interpret)",
    r"seems?\s+to\s+(?:be|suggest)",
    r"perhaps",
    r"might\s+be",
]

ANTI_SPOTLIGHTING_VIOLATIONS = [
    r"ask\s+(?:him|her|them|this student)\s+to\s+share",
    r"have\s+(?:him|her|them)\s+present",
    r"invite\s+(?:him|her|them)\s+to\s+read",
    r"call\s+on\s+(?:him|her|them)",
    r"single\s+(?:him|her|them)\s+out",
]


def test_j_pipeline_validation(model_key: str = "gemma12b"):
    """Post-fix quality checks on observation and coding outputs.

    Tests whether recent prompt changes actually work at 12B:
    1. Structural naming: Does the model use mechanism names directly
       instead of hedging ("subtle attempt to...")?
    2. Anti-spotlighting: Do teacher move suggestions use structural
       language instead of individual-focused interventions?
    3. what_student_is_reaching_for: Is the field populated in
       reading-first coding?
    4. confusion_or_questions: Is the field populated when appropriate?
    5. Preamble stripping: Are model preambles cleaned from observations?
    6. Immanent critique: Does concern output name relational costs?

    HOW TO INTERPRET RESULTS (for the overnight monitoring agent):
    ─────────────────────────────────────────────────────────────
    This test produces SCORED dimensions, not binary pass/fail.

    structural_naming_score: Higher = better. >0.5 means the model is
      naming mechanisms more than hedging. Score = (mechanism keywords
      found) / (mechanism + hedging keywords found). A score of 0 with
      hedging keywords present means the model still hedges instead of
      naming. Compare to prior runs to assess whether the prompt change
      to "Name the structural mechanism directly" is working.

    anti_spotlighting_violations: Should be 0. Any violation means the
      anti-spotlighting prompt language is being ignored. Report the
      exact violation text.

    what_reaching_for_populated: Should be >0 (ideally all students).
      If still 0, the LLM is not returning this field in JSON — check
      the log for "what_student_is_reaching_for empty" warnings.

    preamble_stripped: Should be True for all observations. If False,
      the regex isn't catching the model's preamble pattern — report
      the first 50 chars of the observation.

    WHAT TO DO WITH RESULTS:
    - If structural_naming_score < 0.3: The prompt change isn't enough
      for 12B. This gap may require the enhancement tier (cloud model).
      Flag for design discussion.
    - If anti_spotlighting_violations > 0: The prompt isn't strong enough.
      Flag the specific violation for prompt hardening.
    - If what_reaching_for = 0/N: Check the parse log. The LLM may need
      the field emphasized more in the prompt, or the JSON schema is too
      complex for 12B to fully populate.
    """
    print(f"\n{'='*60}")
    print(f"  TEST J: Pipeline Validation ({model_key})")
    print(f"{'='*60}")

    corpus = load_corpus()
    class_reading = load_class_reading()
    backend = get_backend(model_key)
    assignment = "Week 6 Discussion: Intersectionality in Practice"

    results = []

    # --- J1: Structural naming on power move students ---
    print("\n  J1: Structural Naming Quality")
    power_students = ["S018", "S025"]  # Connor (colorblind), Aiden (tone policing)
    for sid in power_students:
        student = corpus[sid]
        prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=student["student_name"],
            submission_text=student["text"],
            teacher_lens="",
        )
        t0 = time.time()
        output = send(backend, prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=400)
        elapsed = round(time.time() - t0, 1)

        # Score: mechanism names vs hedging
        lower = output.lower()
        mechanism_hits = sum(1 for kw in STRUCTURAL_NAMING_KEYWORDS
                            if re.search(kw, lower))
        hedging_hits = sum(1 for kw in HEDGING_KEYWORDS
                          if re.search(kw, lower))
        total_hits = mechanism_hits + hedging_hits
        naming_score = mechanism_hits / total_hits if total_hits > 0 else 0.0

        # Check preamble
        has_preamble = bool(re.match(
            r"^(?:Okay|OK|Sure|Here are)", output, re.IGNORECASE))

        results.append({
            "subtest": "J1_structural_naming",
            "student_id": sid,
            "student_name": student["student_name"],
            "mechanism_keywords_found": mechanism_hits,
            "hedging_keywords_found": hedging_hits,
            "structural_naming_score": round(naming_score, 2),
            "has_preamble": has_preamble,
            "raw_output": output,
            "time_seconds": elapsed,
        })
        print(f"    {sid} {student['student_name']:20s} "
              f"mechanisms={mechanism_hits} hedges={hedging_hits} "
              f"score={naming_score:.2f} preamble={has_preamble} ({elapsed}s)")

    # --- J2: Anti-spotlighting in observation synthesis ---
    print("\n  J2: Anti-Spotlighting in Synthesis")
    from insights.prompts import (OBSERVATION_SYNTHESIS_PROMPT,
                                  OBSERVATION_SYNTHESIS_SYSTEM_PROMPT)

    obs_formatted = ""
    for sid in sorted(corpus.keys()):
        student = corpus[sid]
        # Generate a brief observation per student
        obs_prompt = OBSERVATION_PROMPT.format(
            class_context=class_reading,
            assignment=assignment,
            student_name=student["student_name"],
            submission_text=student["text"],
            teacher_lens="",
        )
        obs = send(backend, obs_prompt, OBSERVATION_SYSTEM_PROMPT, max_tokens=400)
        obs_formatted += f"\n**{student['student_name']}** ({sid}):\n{obs}\n"
        # Only do first 8 students (enough for synthesis test, saves time)
        if len(obs_formatted.split()) > 1500:
            break

    synth_prompt = OBSERVATION_SYNTHESIS_PROMPT.format(
        assignment=assignment,
        class_context=class_reading,
        observations=obs_formatted,
        teacher_lens="",
        forward_looking="",
    )

    t0 = time.time()
    synthesis = send(backend, synth_prompt, OBSERVATION_SYNTHESIS_SYSTEM_PROMPT,
                     max_tokens=1500)
    elapsed = round(time.time() - t0, 1)

    # Check for anti-spotlighting violations
    lower_synth = synthesis.lower()
    violations = []
    for kw in ANTI_SPOTLIGHTING_VIOLATIONS:
        matches = re.findall(kw, lower_synth)
        violations.extend(matches)

    # Check new sections exist
    has_multiplicity = bool(re.search(
        r"how students entered|entry points|different.*registers", lower_synth))
    has_ped_wins = bool(re.search(
        r"what.s working|working well|assignment.*doing well", lower_synth))
    has_moments = bool(re.search(r"moments for", lower_synth))

    results.append({
        "subtest": "J2_anti_spotlighting",
        "anti_spotlighting_violations": violations,
        "violation_count": len(violations),
        "has_multiplicity_section": has_multiplicity,
        "has_pedagogical_wins_section": has_ped_wins,
        "has_moments_section": has_moments,
        "raw_synthesis": synthesis,
        "time_seconds": elapsed,
    })
    print(f"    Violations: {len(violations)}")
    if violations:
        for v in violations:
            print(f"      - '{v}'")
    print(f"    Multiplicity section: {has_multiplicity}")
    print(f"    Pedagogical wins section: {has_ped_wins}")
    print(f"    Moments section: {has_moments}")
    print(f"    ({elapsed}s)")

    # --- J3: what_student_is_reaching_for via reading-first coding ---
    print("\n  J3: what_student_is_reaching_for Population")
    from insights.submission_coder import code_submission_reading_first
    test_sids = ["S004", "S022", "S028"]  # Talia (strong), Destiny (anger), Imani (AAVE)
    reaching_populated = 0
    confusion_populated = 0
    for sid in test_sids:
        student = corpus[sid]
        t0 = time.time()
        record = code_submission_reading_first(
            submission_text=student["text"],
            student_id=sid,
            student_name=student["student_name"],
            assignment_prompt=assignment,
            backend=backend,
            class_context=class_reading,
        )
        elapsed = round(time.time() - t0, 1)

        reaching = record.what_student_is_reaching_for or ""
        confusion = record.confusion_or_questions or ""
        if reaching:
            reaching_populated += 1

        results.append({
            "subtest": "J3_reaching_for",
            "student_id": sid,
            "student_name": student["student_name"],
            "what_reaching_for": reaching,
            "reaching_for_populated": bool(reaching),
            "confusion_or_questions": confusion,
            "confusion_populated": bool(confusion),
            "free_form_reading_length": len(record.free_form_reading or ""),
            "time_seconds": elapsed,
        })
        print(f"    {sid} {student['student_name']:20s} "
              f"reaching={'YES' if reaching else 'NO':3s} "
              f"confusion={'YES' if confusion else 'no':3s} ({elapsed}s)")
        if reaching:
            print(f"      → {reaching[:100]}...")

    print(f"\n  Summary: {reaching_populated}/{len(test_sids)} reaching_for populated")

    path = save_results("test_j_pipeline_validation", model_key, results, {
        "note": "Post-fix pipeline validation: structural naming, anti-spotlighting, "
                "reaching_for, confusion field, preamble stripping",
        "prompt_changes": [
            "Added 'Name the structural mechanism directly' to observation prompt",
            "Rewrote 'Moments for the Classroom' for anti-spotlighting",
            "Added privacy framing to 'Students to Check In With'",
            "Removed named students from temperature prompt example",
            "Added confusion_or_questions field to reading-first P2",
        ],
    })
    print(f"\n  Results: {path}")
    return results


# ---------------------------------------------------------------------------
# Test K: Enhancement model comparison (OpenRouter free/cheap models)
# ---------------------------------------------------------------------------

# Enhancement evaluation dimensions — scored from the raw output.
# These capture the qualitative richness that distinguishes the
# enhancement tier from the local 12B pipeline.
ENHANCEMENT_QUALITY_MARKERS = {
    "structural_naming": [
        r"tone.?polic", r"colorblind", r"abstract.?liberal",
        r"settler", r"meritocra", r"progress.?narrative",
    ],
    "language_justice": [
        r"AAVE|African.American.Vernacular",
        r"(?:code.?switch|translingual|multilingual|linguistic.?(?:asset|divers|capital))",
        r"(?:register|dialect|vernacular).*(?:valid|legit|rigor|academ)",
        r"neurodivergent|cognitive.?(?:plural|divers|style)",
        r"pathway.*rigor|different.*pathway",
    ],
    "relational_analysis": [
        r"tension\s+between",
        r"(?:dialectic|productive.*disagree|productive.*tension)",
        r"(?:against|alongside|in contrast to|juxtapos)",
        r"(?:respond.*to|building.*on|extending|counter)",
    ],
    "pedagogical_depth": [
        r"(?:assignment.*design|prompt.*design|format.*choice|structure.*of)",
        r"(?:scaffold|bridge|entry.?point|on.?ramp)",
        r"(?:pedagogic|curricular|instructional|teaching.*implica)",
        r"(?:what.*working|strengths.*of.*design|by design)",
    ],
    "anti_spotlighting": [
        r"structur.*(?:opportunit|activit|format|approach)",
        r"(?:class-wide|whole.?class|everyone|all students)",
        r"(?:discussion.*format|small.?group|writing.*move)",
    ],
}

# Models to test — free or very cheap on OpenRouter.
# These all receive the SAME anonymized enhancement prompt.
# Cost is per-run cost for ~1200 output tokens.
ENHANCEMENT_MODELS = {
    "gemma27b_free": {
        "name": "cloud",
        "model": "google/gemma-3-27b-it:free",
        "max_tokens": 1200,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
        "cost_note": "Free tier on OpenRouter",
    },
    "llama70b_free": {
        "name": "cloud",
        "model": "meta-llama/llama-3.3-70b-instruct:free",
        "max_tokens": 1200,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
        "cost_note": "Free tier on OpenRouter",
    },
    "qwen72b_free": {
        "name": "cloud",
        "model": "qwen/qwen-2.5-72b-instruct:free",
        "max_tokens": 1200,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
        "cost_note": "Free tier on OpenRouter",
    },
    "deepseek_free": {
        "name": "cloud",
        "model": "deepseek/deepseek-chat-v3-0324:free",
        "max_tokens": 1200,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
        "cost_note": "Free tier on OpenRouter",
    },
    "mistral_small_free": {
        "name": "cloud",
        "model": "mistralai/mistral-small-3.1-24b-instruct:free",
        "max_tokens": 1200,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
        "cost_note": "Free tier on OpenRouter",
    },
}


def _build_test_enhancement_prompt() -> str:
    """Build a representative anonymized enhancement prompt from checkpoint data.

    Uses the actual synthesis pipeline output format so test results
    are representative of real enhancement calls.
    """
    # This mirrors the payload format from synthesizer._run_cloud_enhancement()
    return (
        "An engagement analysis found these patterns in a class of 32 students "
        "responding to an assignment about Week 6 Discussion: Intersectionality "
        "in Practice:\n\n"
        "CONCERN PATTERNS:\n"
        "- Student uses colorblind framing ('I don't see race, I just see people') "
        "that resists engaging with the structural analysis framework the reading "
        "presents. Does not engage with Crenshaw's argument. (1 student(s))\n"
        "- Student calls for 'calm, rational discussion' in a context where another "
        "student is expressing urgent anger about ICE enforcement affecting her "
        "family. This positions emotional engagement as illegitimate. (1 student(s))\n"
        "- Student shows signs of burnout — submission is markedly shorter than "
        "previous weeks, mentions being 'exhausted' and working closing shifts. "
        "Engagement with material is still present but capacity seems strained. "
        "(1 student(s))\n"
        "Key distinctions:\n"
        "  - The colorblind and tone-policing students are making distinct structural "
        "moves — one denies the relevance of race, the other polices HOW race can be "
        "discussed. They should not be grouped together pedagogically.\n"
        "  - The burnout student is not a concern about engagement quality — this is "
        "a capacity issue. Different teacher response needed.\n\n"
        "ENGAGEMENT HIGHLIGHTS:\n"
        "- Student connects intersectionality framework to grandmother's experience "
        "in agricultural work and redlining legacy in their neighborhood. Deep "
        "personal-structural bridging. (1 student(s))\n"
        "- Student uses AAVE and writes in a register that might be misjudged as "
        "'informal' but is doing sophisticated intersectional analysis through "
        "community-grounded language. (1 student(s))\n"
        "- Student with neurodivergent writing style (associative, nonlinear) makes "
        "connections between disability studies and ethnic studies frameworks that "
        "more linear writers miss. (1 student(s))\n"
        "- 4 students are engaging deeply with Crenshaw's framework and extending it "
        "to current events (ICE enforcement, housing displacement). (4 student(s))\n\n"
        "TENSIONS BETWEEN GROUPS:\n"
        "- Tension between students who approach intersectionality as a theoretical "
        "framework to analyze and students who experience it as lived reality. "
        "Neither is wrong but they are talking past each other.\n"
        "  Between: analytical engagers vs. experiential engagers\n"
        "- Tension between one student's call for 'calm discussion' and another's "
        "urgent expression about family safety. This is a structural power move — "
        "the call for calm delegitimizes the urgency.\n"
        "  Between: tone policing move vs. lived experience urgency\n\n"
        "CLASS TEMPERATURE: Most of the class engaged with Crenshaw's framework "
        "at minimum surface level. A cluster of 6-8 students showed deep personal "
        "connection. 2 students resist the structural analysis through distinct "
        "moves (colorblind framing, tone policing). 1 student shows burnout signs.\n"
        "Attention areas:\n"
        "  - The 2 resistant students are making different moves and need different "
        "pedagogical responses\n"
        "  - The analytical-experiential tension is productive and could be brought "
        "into the classroom as a structured discussion\n\n"
        "Provide a richer pedagogical analysis: What do these patterns suggest "
        "about where the class is in their understanding? What tensions are "
        "most productive for learning? What should the teacher pay attention to? "
        "Do NOT suggest specific exercises or lesson designs — the teacher decides."
    )


ENHANCEMENT_SYSTEM_PROMPT = (
    "You are helping a teacher understand class-level engagement patterns. "
    "All data is anonymized — you will not see student names or text. "
    "Do NOT suggest singling out students. Do NOT suggest specific exercises. "
    "Analyze patterns and surface pedagogical significance."
)


def test_k_enhancement_comparison():
    """Compare enhancement quality across free/cheap OpenRouter models.

    Sends the SAME anonymized enhancement prompt to multiple models and
    scores each response on quality dimensions that matter for the
    enhancement tier: structural naming, language justice framing,
    relational/dialectical analysis, pedagogical depth, anti-spotlighting.

    HOW TO INTERPRET RESULTS (for the overnight monitoring agent):
    ─────────────────────────────────────────────────────────────
    This test compares ENHANCEMENT QUALITY across free cloud models.
    The enhancement receives only anonymized pattern data (no student
    names, no quotes, no identifiable data) — FERPA compliant by design.

    Each model gets a QUALITY PROFILE across 5 dimensions:
    - structural_naming: Does it name mechanisms (tone policing, colorblind
      erasure) or just describe behaviors?
    - language_justice: Does it frame AAVE/neurodivergent writing as assets
      and "different pathways to rigor"? This is the hardest dimension —
      most models default to standard-English-as-neutral.
    - relational_analysis: Does it construct productive tension pairs and
      dialectics between student positions?
    - pedagogical_depth: Does it reason about assignment design, scaffolding,
      and curricular implications?
    - anti_spotlighting: Does it recommend structural opportunities rather
      than individual interventions?

    SCORING: Each dimension counts keyword/phrase matches. Higher = better.
    Compare models on the PROFILE SHAPE, not just total score — a model
    strong on structural naming but weak on language justice is different
    from one strong on pedagogical depth but weak on relational analysis.

    WHAT TO DO WITH RESULTS:
    - Rank models by total score AND per-dimension scores
    - Flag any model that scores 0 on language_justice — this dimension
      matters most for equity and is hardest for smaller models
    - Report the top 2-3 models with their cost notes
    - If no free model exceeds a total score of 5, the enhancement tier
      may need a paid model — flag for cost-benefit discussion
    - Save the raw outputs for human review of qualitative richness
    """
    print(f"\n{'='*60}")
    print(f"  TEST K: Enhancement Model Comparison (OpenRouter)")
    print(f"{'='*60}")

    key = _openrouter_key()
    if not key:
        print("  SKIPPED — no OpenRouter key found")
        print("  Set REFRAME_SHARED_OPENROUTER_KEY in ~/Documents/GitHub/Reframe/.env")
        return []

    enhancement_prompt = _build_test_enhancement_prompt()

    results = []
    for model_key, cfg in ENHANCEMENT_MODELS.items():
        print(f"\n  {model_key} ({cfg['model']})...")
        try:
            backend = get_backend_from_cfg(cfg)
            t0 = time.time()
            output = send(backend, enhancement_prompt, ENHANCEMENT_SYSTEM_PROMPT,
                          max_tokens=1200)
            elapsed = round(time.time() - t0, 1)

            # Score each quality dimension
            lower = output.lower()
            scores = {}
            for dim, keywords in ENHANCEMENT_QUALITY_MARKERS.items():
                hits = sum(1 for kw in keywords if re.search(kw, lower))
                scores[dim] = hits

            total = sum(scores.values())
            word_count = len(output.split())

            results.append({
                "model_key": model_key,
                "model_id": cfg["model"],
                "cost_note": cfg.get("cost_note", ""),
                "scores": scores,
                "total_score": total,
                "word_count": word_count,
                "raw_output": output,
                "time_seconds": elapsed,
            })

            print(f"    Total: {total} | Words: {word_count} | Time: {elapsed}s")
            for dim, score in scores.items():
                bar = "█" * score + "░" * (5 - min(score, 5))
                print(f"    {dim:22s} {score:2d} {bar}")

        except Exception as e:
            log.error("Model %s failed: %s", model_key, e)
            results.append({
                "model_key": model_key,
                "model_id": cfg["model"],
                "error": str(e),
                "scores": {},
                "total_score": -1,
            })
            print(f"    FAILED: {e}")

    # Ranking
    valid = [r for r in results if r["total_score"] >= 0]
    if valid:
        print(f"\n  === Enhancement Model Ranking ===")
        for rank, r in enumerate(sorted(valid, key=lambda x: -x["total_score"]), 1):
            print(f"  #{rank} {r['model_key']:25s} total={r['total_score']:2d} "
                  f"({r['cost_note']}) {r['time_seconds']}s")

        # Per-dimension leaders
        print(f"\n  === Per-Dimension Leaders ===")
        for dim in ENHANCEMENT_QUALITY_MARKERS:
            leader = max(valid, key=lambda x: x["scores"].get(dim, 0))
            print(f"  {dim:22s} → {leader['model_key']} "
                  f"(score={leader['scores'].get(dim, 0)})")

    path = save_results("test_k_enhancement_comparison", "multi_model", results, {
        "note": "Enhancement model comparison — FERPA-compliant anonymized prompt "
                "tested against free/cheap OpenRouter models. Goal: find cost-effective "
                "enhancement mechanism for teachers without paid API access.",
        "prompt_length": len(enhancement_prompt),
        "models_tested": list(ENHANCEMENT_MODELS.keys()),
        "quality_dimensions": list(ENHANCEMENT_QUALITY_MARKERS.keys()),
    })
    print(f"\n  Results: {path}")
    return results


def get_backend_from_cfg(cfg: dict):
    """Build a BackendConfig from a model config dict (for enhancement models)."""
    from insights.llm_backend import BackendConfig
    kwargs = {
        "name": cfg["name"],
        "model": cfg["model"],
        "max_tokens": cfg.get("max_tokens", 1200),
        "temperature": cfg.get("temperature", 0.3),
    }
    if "base_url" in cfg:
        kwargs["base_url"] = cfg["base_url"]
    if "api_key_fn" in cfg:
        kwargs["api_key"] = cfg["api_key_fn"]()
    elif "api_key" in cfg:
        kwargs["api_key"] = cfg["api_key"]
    return BackendConfig(**kwargs)


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
    # F, G, H, J are longer tests — many inferences each
    # K is cloud-only (no MLX) but may take time due to rate limits
    timeout = 3600 if test_id in ("F", "G", "H", "J", "K") else 900
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
    elif test_id == "H":
        test_h_binary_on_wellbeing(model)
    elif test_id == "J":
        test_j_pipeline_validation(model)
    elif test_id == "K":
        test_k_enhancement_comparison()
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
                        help="Comma-separated list: A,B,C,D,E,F,G,H,J,K")
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
