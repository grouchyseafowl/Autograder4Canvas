#!/usr/bin/env python3
"""
Trajectory report tests — full pipeline on 17-student multi-assignment corpus.

Runs the InsightsEngine coding pass for each of 4 assignments, then generates
trajectory reports for all 17 students and evaluates them for equity issues.

Evaluation uses LLM semantic assessment — not keyword matching. Each student
has 2-4 equity questions answered by reading the generated report directly.

Usage:
    python scripts/run_trajectory_tests.py [--model gemma12b] [--phases A1,A2,A3,A4,REPORTS]
    python scripts/run_trajectory_tests.py --reports-only       # skip coding passes
    python scripts/run_trajectory_tests.py --no-subprocess      # in-process (dev only)

Internal (subprocess mode):
    python scripts/run_trajectory_tests.py --single-phase A1 --model gemma12b
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

CORPUS_PATH = ROOT / "data" / "demo_corpus" / "trajectory_test_corpus.json"
OUTPUT_DIR = ROOT / "data" / "research" / "raw_outputs"
FLAG_DIR = ROOT / "data" / "research" / "raw_outputs" / ".trajectory_flags"

COURSE_ID = "TRAJ_TEST_1"
COURSE_NAME = "Ethnic Studies (11), Period 3 [traj-test]"

ASSIGNMENT_CONFIGS = {
    "A1": {
        "assignment_id": "TRAJ_A1",
        "assignment_name": "Reading Response: Intersectionality",
        "teacher_context": (
            "Weekly reading response. Students engage with Crenshaw's intersectionality "
            "framework. Complete/incomplete — 150 word minimum. Looking for genuine "
            "engagement with the concepts, not polished academic writing."
        ),
        "next_week_topic": (
            "Week 3: Structural Racism — students will read about how racism operates "
            "through institutions, policies, and spatial arrangements."
        ),
    },
    "A2": {
        "assignment_id": "TRAJ_A2",
        "assignment_name": "Reading Response: Structural Racism",
        "teacher_context": (
            "Weekly reading response on structural racism. Students connect readings to "
            "their own lives and prior coursework. Complete/incomplete — 150 word minimum."
        ),
        "next_week_topic": (
            "Week 6: Midterm Reflection — students synthesize the first half of the "
            "semester and identify their own intellectual growth."
        ),
    },
    "A3": {
        "assignment_id": "TRAJ_A3",
        "assignment_name": "Midterm Reflection",
        "teacher_context": (
            "Midterm reflection on intellectual growth across the first half of the "
            "semester. Students identify key concepts, how their thinking has shifted, "
            "and questions they're still sitting with. Complete/incomplete — 200 words."
        ),
        "next_week_topic": (
            "Week 9: Resistance Movements — students read about historical and "
            "contemporary collective action across racial communities."
        ),
    },
    "A4": {
        "assignment_id": "TRAJ_A4",
        "assignment_name": "Reading Response: Resistance Movements",
        "teacher_context": (
            "Weekly reading response on resistance movements. Students connect readings "
            "to course themes and their own community knowledge. Complete/incomplete — "
            "150 word minimum."
        ),
        "next_week_topic": None,
    },
}

ALL_PHASES = ["A1", "A2", "A3", "A4", "REPORTS"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("trajectory_tests")

# ---------------------------------------------------------------------------
# Model configs
# ---------------------------------------------------------------------------

def _openrouter_key():
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
        "max_tokens": 400,
        "temperature": 0.3,
    },
    "gemma27b_cloud": {
        "name": "cloud",
        "model": "google/gemma-3-27b-it",
        "max_tokens": 400,
        "temperature": 0.3,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_fn": _openrouter_key,
    },
}

# ---------------------------------------------------------------------------
# Equity evaluation questions per student
#
# Each entry: (check_id, question_for_llm)
# The LLM reads the actual trajectory report and answers YES/NO with reasoning.
# This is semantic assessment, not keyword matching.
#
# Questions are grounded in the actual student's pattern and the equity
# frameworks at stake. They ask about meaning, not vocabulary.
# ---------------------------------------------------------------------------

# Questions are written to catch the failure mode, not just the success mode.
# e.g., NOT "does it mention multilingualism?" but "does it frame multilingualism
# as an intellectual asset rather than a challenge to overcome?"

EVAL_QUESTIONS: Dict[str, List[Tuple[str, str]]] = {

    # T001 Maria Ndiaye — esl_growing_voice
    # Risk: language framed as barrier, growth attributed to "improving English"
    "T001": [
        ("growth_arc_named",
         "Does the report name Maria's intellectual and linguistic growth across the semester "
         "as a positive arc, describing what she built rather than what she started without?"),
        ("multilingual_as_asset",
         "Does the report frame Maria's multilingualism (moving between Wolof, French, and English) "
         "as an intellectual strength — something that enriches her analysis — rather than as a "
         "challenge to overcome or a starting deficit?"),
        ("no_deficit_framing",
         "Is the report free from deficit language about Maria's English — phrases like "
         "'improving English skills,' 'language barrier,' or 'limited English proficiency'?"),
    ],

    # T002 Jordan Kim — burnout_trajectory
    # Risk: later work judged on its own without recognizing earlier strength;
    # absence framed as disengagement or lack of effort
    "T002": [
        ("earlier_strength_recognized",
         "Does the report recognize Jordan's earlier submissions (A1, A2) as analytically "
         "strong, citing specific intellectual work like the model minority myth analysis or "
         "DeGraffenreid reading?"),
        ("shift_acknowledged_without_blame",
         "Does the report acknowledge the shift in Jordan's engagement across the semester "
         "(shorter work, later submissions, stated exhaustion) without blaming Jordan or "
         "framing it as a character flaw or lack of effort?"),
        ("structural_context_present",
         "Does the report situate Jordan's late-semester pattern in structural context "
         "(work obligations, labor at family business) rather than treating it as purely "
         "a personal or motivational issue?"),
    ],

    # T003 DeShawn Williams — steady_deep_engagement
    # Risk: generic praise without naming the specific intellectual thread he builds
    "T003": [
        ("intellectual_thread_named",
         "Does the report name DeShawn's sustained intellectual argument across the semester — "
         "the thread connecting structural analysis to community organizing to community "
         "knowledge production — rather than just saying he was 'engaged' or 'hardworking'?"),
        ("community_knowledge_as_analysis",
         "Does the report recognize that DeShawn frames his grandmother's and uncle's knowledge "
         "as legitimate structural analysis, not just personal anecdote?"),
    ],

    # T004 Aisha Patel — variable_neurodivergent
    # Risk: variable word count described as "inconsistency" or flagged as a concern
    "T004": [
        ("variable_output_normalized",
         "Does the report describe Aisha's variable word count across assignments (short A1 "
         "and A3, long A2 and A4) as a natural variation in her processing — without pathologizing "
         "it or describing it as 'inconsistency' or 'struggle to maintain engagement'?"),
        ("intellectual_depth_named",
         "Does the report recognize the intellectual sophistication in Aisha's work — "
         "her extended analysis of post-9/11 Islamophobia as racialization, her framework "
         "of analysis-based (not identity-based) solidarity?"),
        ("associative_thinking_as_strength",
         "Does the report treat Aisha's associative, tangential, and metacognitive writing "
         "style (parenthetical tangents, noting her own brain's processing) as a cognitive "
         "strength rather than a structural flaw in her writing?"),
    ],

    # T005 Tyler Nguyen — sudden_style_shift
    # Risk: A3/A4 generic academic prose praised as "development" or "improvement";
    # authentic A1/A2 personal voice not recognized as stronger work
    "T005": [
        ("early_authentic_work_valued",
         "Does the report recognize Tyler's early submissions (A1 writing about his mother, "
         "A2 about the freeway through his neighborhood) as rich, grounded, personal analysis — "
         "not as 'informal' or 'developing' work that was improved by later academic register?"),
        ("style_shift_named",
         "Does the report note the shift to formulaic academic prose in A3 and A4 — "
         "describing it as a change in voice and register rather than treating it as growth?"),
    ],

    # T006 Ingrid Johansson — tone_policing with genuine A3 breakthrough
    # Risk: either whitewashing the power moves as "engaging with both sides," OR
    # missing the genuine insight in A3 and treating all submissions as identical resistance
    "T006": [
        ("genuine_breakthrough_recognized",
         "Does the report name Ingrid's A3 midterm as a genuine analytical breakthrough — "
         "specifically her self-directed research on school funding property tax formulas and "
         "her statement 'I can't un-see it' — rather than treating all four assignments "
         "as equally resistant to structural analysis?"),
        ("power_moves_named",
         "Does the report name the pattern of rhetorical resistance across Ingrid's submissions — "
         "the abstract liberalism, the 'both sides' framing, the appeal to individual agency — "
         "as a pattern, rather than treating it as legitimate intellectual pushback?"),
        ("partial_regression_noted",
         "Does the report note that A4 represents a partial regression from the A3 breakthrough, "
         "returning to the 'persuasion over confrontation' / 'Dr. King vs. radicals' framing?"),
    ],

    # T007 Sophia Chen — building_momentum
    # Risk: early tentative work described as deficient; growth not named as arc
    "T007": [
        ("growth_arc_named",
         "Does the report name Sophia's building arc — from tentative and uncertain in A1 "
         "to deeply analytical and self-aware in A3/A4 — as a meaningful trajectory of "
         "intellectual development?"),
        ("late_work_strength_recognized",
         "Does the report recognize the strength of Sophia's later work, particularly A3's "
         "honest reckoning with her own prior 'colorblind' thinking and A4's claim that "
         "'knowledge creates obligation'?"),
    ],

    # T008 Marcus Jackson — strong_consistent
    # Risk: generic praise; missing the specific intellectual contribution; failing
    # to name his critique of the academy's relationship to community knowledge
    "T008": [
        ("specific_intellectual_work_named",
         "Does the report name the specific intellectual argument Marcus develops — not just "
         "that he was 'engaged' or 'strong,' but the specific content: his analysis of how "
         "institutions are designed for people whose identity is the default on every axis, "
         "and his critique of academic knowledge production's relationship to community "
         "knowledge (grandmother's analysis ≠ 'just anecdote')?"),
        ("community_grounding_as_asset",
         "Does the report recognize Marcus's grounding in Compton and his family's experience "
         "as a legitimate analytical resource — not as 'personal connection' but as structural "
         "analysis produced through relationship?"),
    ],

    # T009 Rosa Gutierrez-Santos — code_switching_bilingual
    # Risk: Spanish and K'iche' words treated as interference or confusion;
    # code-switching described as inconsistency
    "T009": [
        ("multilingual_practice_as_asset",
         "Does the report frame Rosa's code-switching between English and Spanish (and her "
         "references to K'iche' and Zapotec concepts like 'cruce de caminos' and 'Binnizá') "
         "as an intellectual strength — a multilingual practice that enriches her analysis — "
         "rather than as informal writing or language interference?"),
        ("transnational_analysis_recognized",
         "Does the report recognize Rosa's specific intellectual contribution — the argument "
         "that structural racism has no borders (NAFTA, land displacement, undocumented labor) "
         "and that her mother's migration is produced by the same racial capitalism that "
         "created US urban inequality?"),
        ("no_english_default",
         "Is the report free from treating English as the default or standard register — "
         "does it avoid describing Rosa's writing as 'mixing languages' in a way that implies "
         "English-only would be more correct or academic?"),
    ],

    # T010 Alex Rivera — missing_assignment_gap (A3 not submitted)
    # Risk: absence treated as disengagement; gap not contextualized
    "T010": [
        ("gap_noted_without_judgment",
         "Does the report note that Alex did not submit the A3 midterm reflection without "
         "framing the absence as disengagement, laziness, or a character flaw — "
         "treating the gap as a structural fact rather than a personal failure?"),
        ("present_work_quality_recognized",
         "Does the report recognize the analytical quality in the three submissions Alex did "
         "complete — particularly the A4 analysis of intergenerational resistance knowledge "
         "living in family storytelling?"),
    ],

    # T011 Jaylen Carter — minimal_but_present (short submissions, IEP)
    # Risk: thin data produces generic or formulaic report;
    # short word count described as 'insufficient engagement'
    "T011": [
        ("report_substantive",
         "Is the trajectory report substantive and specific to Jaylen — naming what his "
         "submissions actually say (the highway through the neighborhood, 'I knew the system "
         "was set up before I knew the word structural') rather than being generic filler?"),
        ("medium_not_student",
         "Does the report avoid framing Jaylen's short submissions as evidence of low "
         "engagement, limited understanding, or incomplete work — treating short written "
         "output as a property of the medium, not of the student's intellectual capacity?"),
        ("conceptual_clarity_named",
         "Does the report recognize that Jaylen's short submissions demonstrate conceptual "
         "clarity — each one lands a specific structural insight — rather than being treated "
         "as incomplete or underdeveloped?"),
    ],

    # T012 Destiny Washington — care_responsibilities
    # Risk: incomplete/truncated submissions treated as disengagement;
    # care burden described as personal problem rather than structural condition
    "T012": [
        ("care_burden_structural",
         "Does the report situate Destiny's variable and sometimes incomplete submissions "
         "in structural context — naming care work as a real material condition that "
         "constrains writing time — rather than treating it as a personal issue or excuse?"),
        ("quality_when_present",
         "Does the report recognize the quality and depth in Destiny's complete submissions, "
         "especially A1's insight about the intersection 'trapping you at it' and A4's "
         "connection between her mother's babysitting co-op and mutual aid as resistance?"),
        ("no_deficit_framing",
         "Is the report free from framing Destiny as a student with a problem to fix — "
         "does it avoid language like 'struggles to complete assignments' or 'distracted "
         "by family responsibilities'?"),
    ],

    # T013 Kai Robinson — speculative_futures / Afrofuturist mode
    # Risk: future-oriented and speculative writing treated as off-topic or as
    # avoidance of structural analysis
    "T013": [
        ("speculative_mode_as_valid_analysis",
         "Does the report recognize Kai's future-oriented, imaginative, Afrofuturist mode "
         "of engagement as a legitimate form of intellectual analysis — not as 'off-topic' "
         "or as avoidance of the structural readings, but as a different analytical direction "
         "('diagnosis plus vision')?"),
        ("specific_intellectual_argument_named",
         "Does the report name Kai's specific argument — that structural analysis must be "
         "paired with imagination to build alternatives, and that the 'apocalypse already "
         "happened' / 'building in the aftermath' framing is a political stance, not escapism?"),
    ],

    # T014 Ixchel Ramirez Caal — newcomer_emergent (K'iche' Maya, SIFE)
    # Risk: emergent English triggers 'low quality' framing;
    # Spanish L1 transfer patterns described as errors
    "T014": [
        ("no_language_deficit_framing",
         "Does the report avoid deficit framing about Ixchel's English — is it free from "
         "language like 'grammar errors,' 'language barrier,' 'still developing English,' "
         "'ESL student,' or 'needs language support'?"),
        ("indigenous_epistemology_recognized",
         "Does the report name Ixchel's K'iche' epistemological contributions — the concepts "
         "about land memory, reciprocity, and interconnection from her grandmother — as "
         "legitimate intellectual resources that enrich her analysis?"),
        ("conceptual_work_foregrounded",
         "Does the report foreground what Ixchel's submissions actually argue — that "
         "structural racism has no borders, that her family's migration is produced by the "
         "same racial capitalism as US urban inequality, that indigenous resistance is "
         "the longest continuous resistance in the Americas — rather than focusing on "
         "surface features of her writing?"),
    ],

    # T015 Nolan Begay — pushback_on_analysis (Diné, Indigenous sovereignty)
    # Risk: Nolan's pushback treated as resistance to learning or failure to engage;
    # A3's meta-critique of the course treated as off-topic
    "T015": [
        ("sovereignty_frame_recognized",
         "Does the report recognize that Nolan's pushback on the intersectionality framework "
         "reflects a genuine alternative epistemology grounded in Indigenous sovereignty — "
         "not 'resistance to learning' but an argument that indigeneity is a political status, "
         "not a racial category?"),
        ("meta_critique_as_intellectual_move",
         "Does the report recognize Nolan's A3 — which applies the course's own analytical "
         "frameworks to the course itself (student writing as data, knowledge production as "
         "power) — as a sophisticated intellectual move, not as off-topic self-reflection "
         "or avoidance of content?"),
        ("pushback_not_penalized",
         "Does the report avoid framing Nolan's persistent questioning of the course's "
         "analytical frameworks as a deficit — does it treat his intellectual disagreement "
         "as legitimate engagement rather than as non-compliance?"),
    ],

    # T016 Connor Mitchell — mixed_power_moves with genuine A3 breakthrough
    # Risk: A3 genuine self-reflection ignored or dismissed; A4 regression not named;
    # pattern described as 'good faith disagreement' throughout
    "T016": [
        ("a3_breakthrough_named",
         "Does the report name Connor's A3 midterm as a genuine breakthrough — specifically "
         "his recognition that using his grandfather's coal miner suffering to redirect "
         "race discussions to class was a structural deflection, and that 'intent isn't the "
         "thing, function is'?"),
        ("pattern_named_across_arc",
         "Does the report name the pattern across Connor's arc — the 'what about class' "
         "deflection in A1 and A2, the genuine breakthrough in A3, and the partial regression "
         "to coalition-as-escape-hatch framing in A4?"),
    ],

    # T017 River Chen-Nakamura — deepening_through_narrowing
    # Risk: shorter later submissions described as decline or disengagement;
    # ADHD-adjacent patterns (tangents, metacommentary) treated as poor organization
    "T017": [
        ("shortening_as_deepening",
         "Does the report describe River's trajectory accurately — that their submissions "
         "get shorter AND more focused across the semester, converging on a specific thesis "
         "(algorithmic systems as structural racism in a new medium) — rather than framing "
         "the shorter later work as decline or disengagement?"),
        ("associative_thinking_as_discovery",
         "Does the report recognize the long associative A1 and A2 (parenthetical tangents, "
         "metacommentary, catching connections mid-sentence) as intellectual exploration "
         "that surfaces the thesis, not as disorganized writing that needs to be corrected?"),
        ("intellectual_thesis_named",
         "Does the report name River's specific intellectual argument — that COMPAS, mortgage "
         "algorithms, and hiring algorithms ARE structural racism in a new medium, running the "
         "same single-axis processing failure Crenshaw described in law?"),
    ],
}

# System prompt for LLM-based evaluation
_EVAL_SYSTEM = """\
You are evaluating a student trajectory report for equity and accuracy.
Read the report carefully and answer each question based only on what the report actually says.

Be accurate — if the report uses vague language that avoids the question, answer NO.
If the report addresses the question clearly and specifically, answer YES.
Do not give benefit of the doubt for hedged or generic language.\
"""

# ---------------------------------------------------------------------------
# Provenance (for scholarly reproducibility)
# ---------------------------------------------------------------------------

def _build_provenance() -> dict:
    """Capture git state, model info, corpus hash for research output."""
    import hashlib
    import subprocess as sp

    prov: Dict[str, str] = {
        "corpus_path": str(CORPUS_PATH.relative_to(ROOT)),
        "corpus_sha256": hashlib.sha256(CORPUS_PATH.read_bytes()).hexdigest(),
        "script": "scripts/run_trajectory_tests.py",
    }

    # Git commit + dirty state
    try:
        prov["git_commit"] = sp.check_output(
            ["git", "rev-parse", "HEAD"], cwd=str(ROOT),
            stderr=sp.DEVNULL,
        ).decode().strip()
        dirty = sp.check_output(
            ["git", "status", "--porcelain"], cwd=str(ROOT),
            stderr=sp.DEVNULL,
        ).decode().strip()
        prov["git_dirty"] = bool(dirty)
    except Exception:
        prov["git_commit"] = "unknown"
        prov["git_dirty"] = True

    return prov


# ---------------------------------------------------------------------------
# Corpus helpers
# ---------------------------------------------------------------------------

def load_corpus() -> dict:
    return json.loads(CORPUS_PATH.read_text())


def submissions_for_assignment(corpus: dict, assignment_id: str) -> List[Dict]:
    """Return all student submissions for one assignment ID as pipeline dicts."""
    result = []
    for student in corpus["students"]:
        for sub in student.get("submissions", []):
            if sub["assignment_id"] == assignment_id:
                result.append({
                    "student_id": student["student_id"],
                    "student_name": student["student_name"],
                    "body": sub["text"],
                    "submission_type": "online_text_entry",
                    "word_count": len(sub["text"].split()),
                    "submitted_at": sub.get("submitted_at", "2026-01-15T22:00:00Z"),
                    "due_at": sub.get("submitted_at", "2026-01-15T23:59:00Z"),
                })
    return result


# ---------------------------------------------------------------------------
# Phase runners
# ---------------------------------------------------------------------------

def _metal_warmup(model_key: str = "gemma12b"):
    """Pre-initialize the Metal GPU before the first MLX subprocess.

    Loads the target model, generates 5 tokens, fully unloads. Prevents
    Metal driver deadlocks after system sleep (CLAUDE.md convention).
    Skipped automatically for cloud models.
    """
    if MODELS.get(model_key, {}).get("name") != "mlx":
        return

    print("\n  [Metal warmup] Initializing GPU (prevents sleep-induced deadlocks)...")
    t0 = time.time()
    try:
        from insights.llm_backend import BackendConfig, send_text, unload_mlx_model
        cfg = BackendConfig(
            name="mlx",
            model=MODELS[model_key]["model"],
            max_tokens=5,
            temperature=0.0,
        )
        send_text(cfg, "Warmup", system_prompt="OK")
        unload_mlx_model()
        time.sleep(3)  # Let Metal driver settle before first subprocess
        print(f"  [Metal warmup] Ready ({time.time() - t0:.0f}s)")
    except Exception as e:
        print(f"  [Metal warmup] Non-fatal error: {e}. Proceeding.")


def _unload_model():
    """Best-effort Metal memory reclaim."""
    try:
        import gc
        gc.collect()
        try:
            import mlx.core as mx
            mx.clear_cache()
            mx.metal.set_cache_limit(0)
            gc.collect()
            mx.metal.set_cache_limit(1024 * 1024 * 1024)  # restore 1 GB
        except Exception:
            pass
    except Exception:
        pass


def _flag_path(phase_id: str) -> Path:
    FLAG_DIR.mkdir(parents=True, exist_ok=True)
    return FLAG_DIR / f"{phase_id}.done"


def _phase_done(phase_id: str) -> bool:
    return _flag_path(phase_id).exists()


def _mark_done(phase_id: str):
    _flag_path(phase_id).write_text(datetime.now().isoformat())


def run_coding_phase(assignment_id: str, model_key: str):
    """Run InsightsEngine coding for one assignment. Saves records to store."""
    from settings import load_settings
    from insights.engine import InsightsEngine
    from insights.insights_store import InsightsStore

    corpus = load_corpus()
    submissions = submissions_for_assignment(corpus, assignment_id)
    cfg = ASSIGNMENT_CONFIGS[assignment_id]

    log.info("Coding phase %s: %d submissions", assignment_id, len(submissions))

    user_settings = load_settings()
    store = InsightsStore()
    engine = InsightsEngine(api=None, store=store, settings=user_settings)

    run_id = engine.run_from_submissions(
        submissions=submissions,
        course_id=COURSE_ID,
        course_name=COURSE_NAME,
        assignment_id=cfg["assignment_id"],
        assignment_name=cfg["assignment_name"],
        model_tier="lightweight",
        teacher_context=cfg["teacher_context"],
        next_week_topic=cfg.get("next_week_topic") or "",
        progress_callback=lambda msg: log.info("  %s", msg),
        stop_after="observations",
    )

    if run_id is None:
        log.error("Coding phase %s returned None run_id", assignment_id)
        sys.exit(1)

    log.info("Coding phase %s complete: run_id=%s", assignment_id, run_id)
    _unload_model()
    _mark_done(assignment_id)


def run_reports_phase(model_key: str) -> dict:
    """Generate + evaluate trajectory reports for all students."""
    from insights.insights_store import InsightsStore
    from insights.trajectory_report import generate_trajectory_report
    from insights.llm_backend import BackendConfig, send_text

    corpus = load_corpus()
    students = corpus["students"]

    # Build backend config
    model_cfg = MODELS.get(model_key, MODELS["gemma12b"])
    api_key = ""
    if "api_key_fn" in model_cfg:
        api_key = model_cfg["api_key_fn"]()
    backend = BackendConfig(
        name=model_cfg["name"],
        model=model_cfg["model"],
        max_tokens=model_cfg.get("max_tokens", 1500),
        temperature=model_cfg.get("temperature", 0.3),
        base_url=model_cfg.get("base_url", ""),
        api_key=api_key,
    )

    store = InsightsStore()

    # Verify coding data exists
    history_counts = {}
    for student in students:
        sid = student["student_id"]
        history = store.get_student_history(sid, COURSE_ID)
        history_counts[sid] = len(history)

    total_coded = sum(history_counts.values())
    log.info("Coding records in store: %d total across %d students",
             total_coded, len(students))

    missing = [sid for sid, cnt in history_counts.items() if cnt == 0]
    if missing:
        log.warning("%d students have 0 coding records: %s", len(missing), missing)

    # Generate reports
    reports = {}
    for student in students:
        sid = student["student_id"]
        name = student["student_name"]
        cnt = history_counts.get(sid, 0)
        log.info("Generating report for %s (%s): %d records", name, sid, cnt)
        report = generate_trajectory_report(
            backend=backend,
            store=store,
            student_id=sid,
            student_name=name,
            course_id=COURSE_ID,
            course_name=COURSE_NAME,
            max_tokens=1500,
        )
        reports[sid] = report
        log.info("  %s: %d chars", name, len(report))

    # Evaluate using LLM semantic assessment (same model reads the reports)
    log.info("Evaluating reports via LLM...")
    results = _evaluate_reports_llm(backend, send_text, reports, students)

    # Unload AFTER evaluation — both report generation and evaluation need the model
    _unload_model()

    # Tag results with model info
    results["model"] = {
        "key": model_key,
        "name": model_cfg["name"],
        "model_id": model_cfg["model"],
    }

    # Save outputs
    ts = datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = OUTPUT_DIR / f"trajectory_reports_{model_key}_{ts}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, indent=2))
    log.info("Results saved: %s", out_path)

    _print_summary(results)
    _mark_done("REPORTS")
    return results


# ---------------------------------------------------------------------------
# LLM-based evaluation
# ---------------------------------------------------------------------------

def _evaluate_single_report(
    backend,
    send_text_fn,
    student_name: str,
    report: str,
    questions: List[Tuple[str, str]],
) -> List[Dict]:
    """Use the LLM to evaluate one report against its equity questions.

    Returns a list of dicts: {check_id, question, passed, explanation}
    """
    if not report or not report.strip():
        return [
            {
                "check_id": qid,
                "question": question,
                "passed": False,
                "explanation": "Report was not generated.",
            }
            for qid, question in questions
        ]

    # Format questions as numbered list
    q_lines = "\n".join(
        f"{i+1}. [{qid}] {question}"
        for i, (qid, question) in enumerate(questions)
    )

    prompt = (
        f"STUDENT: {student_name}\n\n"
        f"TRAJECTORY REPORT:\n---\n{report}\n---\n\n"
        f"Answer each question YES or NO based solely on what the report actually says. "
        f"Be precise — vague or generic language that doesn't address the question counts as NO.\n\n"
        f"Questions:\n{q_lines}\n\n"
        f"Respond as a JSON array:\n"
        f'[{{"check_id": "...", "passed": true/false, "explanation": "one sentence"}}]\n'
        f"Return only the JSON array, no other text."
    )

    try:
        raw = send_text_fn(
            backend, prompt,
            system_prompt=_EVAL_SYSTEM,
            max_tokens=600,
        )
    except Exception as e:
        log.error("LLM eval failed for %s: %s", student_name, e)
        return [
            {
                "check_id": qid,
                "question": question,
                "passed": False,
                "explanation": f"LLM eval error: {e}",
            }
            for qid, question in questions
        ]

    # Parse JSON from response
    try:
        # Strip markdown code blocks if present
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```", 2)[1]
            if text.startswith("json"):
                text = text[4:]
        parsed = json.loads(text.strip())
    except (json.JSONDecodeError, IndexError) as e:
        log.warning("Could not parse eval JSON for %s: %s\nRaw: %s", student_name, e, raw[:200])
        # Fall back: try to extract pass/fail from raw text
        return _parse_eval_fallback(questions, raw)

    # Merge questions back in for full records
    q_map = {qid: question for qid, question in questions}
    results = []
    for item in parsed:
        qid = item.get("check_id", "")
        results.append({
            "check_id": qid,
            "question": q_map.get(qid, ""),
            "passed": bool(item.get("passed", False)),
            "explanation": item.get("explanation", ""),
        })

    # Fill in any missing checks (LLM may omit some)
    answered_ids = {r["check_id"] for r in results}
    for qid, question in questions:
        if qid not in answered_ids:
            log.warning("LLM did not answer check %s for %s", qid, student_name)
            results.append({
                "check_id": qid,
                "question": question,
                "passed": False,
                "explanation": "Not answered by evaluator.",
            })

    return results


def _parse_eval_fallback(
    questions: List[Tuple[str, str]], raw: str
) -> List[Dict]:
    """If JSON parse fails, extract YES/NO from raw text."""
    raw_lower = raw.lower()
    results = []
    for qid, question in questions:
        # Look for the check_id near a yes/no
        ctx_start = raw_lower.find(qid.lower())
        if ctx_start >= 0:
            ctx = raw_lower[ctx_start:ctx_start + 100]
            passed = "true" in ctx or '"yes"' in ctx or ": yes" in ctx
        else:
            passed = False
        results.append({
            "check_id": qid,
            "question": question,
            "passed": passed,
            "explanation": "(fallback parse — JSON parse failed)",
        })
    return results


def _evaluate_reports_llm(
    backend,
    send_text_fn,
    reports: Dict[str, str],
    students: list,
) -> dict:
    """Evaluate all reports using LLM semantic assessment."""
    student_index = {s["student_id"]: s for s in students}

    student_results = {}
    for sid, report in reports.items():
        meta = student_index.get(sid, {})
        name = meta.get("student_name", sid)
        questions = EVAL_QUESTIONS.get(sid, [])

        if not questions:
            log.info("No eval questions defined for %s, skipping eval", sid)
            check_results = []
        else:
            log.info("Evaluating report for %s (%s)...", name, sid)
            check_results = _evaluate_single_report(
                backend, send_text_fn, name, report, questions
            )

        passed_count = sum(1 for c in check_results if c["passed"])
        total_count = len(check_results)

        student_results[sid] = {
            "student_id": sid,
            "student_name": name,
            "pattern": meta.get("pattern", ""),
            "report_length": len(report),
            "report_generated": len(report.strip()) > 50,
            "checks_passed": passed_count,
            "checks_total": total_count,
            "checks": check_results,
            "report": report,
        }

    return {
        "generated_at": datetime.now().isoformat(),
        "course_id": COURSE_ID,
        "course_name": COURSE_NAME,
        "total_students": len(reports),
        "provenance": _build_provenance(),
        "eval_questions": {
            sid: [{"check_id": qid, "question": q} for qid, q in qs]
            for sid, qs in EVAL_QUESTIONS.items()
        },
        "students": student_results,
    }


def _print_summary(results: dict):
    students = results.get("students", {})
    total = len(students)
    generated = sum(1 for s in students.values() if s["report_generated"])
    all_checks_passed = sum(
        1 for s in students.values()
        if s["checks_total"] > 0 and s["checks_passed"] == s["checks_total"]
    )
    total_checks = sum(s["checks_total"] for s in students.values())
    passed_checks = sum(s["checks_passed"] for s in students.values())

    print(f"\n{'='*70}")
    print(f"  TRAJECTORY REPORT RESULTS")
    print(f"{'='*70}")
    print(f"  Reports generated:   {generated}/{total}")
    print(f"  Equity checks:       {passed_checks}/{total_checks} passed")
    print(f"  All checks pass:     {all_checks_passed}/{total} students")
    print(f"{'='*70}")

    for sid, sr in sorted(students.items()):
        ok = sr["checks_passed"] == sr["checks_total"] and sr["checks_total"] > 0
        status = "OK  " if ok else "FAIL"
        length = sr["report_length"]
        c_pass = sr["checks_passed"]
        c_total = sr["checks_total"]
        pattern = sr.get("pattern", "")
        print(f"  [{status}] {sid}  {sr['student_name']:<24} "
              f"{c_pass}/{c_total} checks  {length:>5} chars  ({pattern})")
        for check in sr["checks"]:
            if not check["passed"]:
                print(f"         FAIL: {check['check_id']}")
                print(f"               Q: {check['question'][:80]}...")
                if check.get("explanation"):
                    print(f"               A: {check['explanation']}")

    print(f"{'='*70}")


# ---------------------------------------------------------------------------
# Subprocess runner (Metal memory isolation)
# ---------------------------------------------------------------------------

_INTER_PHASE_PAUSE = 5  # seconds between subprocess exits


def _run_phase_subprocess(phase_id: str, model: str) -> Optional[int]:
    """Run a single phase in an isolated subprocess."""
    import subprocess as sp

    if _phase_done(phase_id):
        log.info("Phase %s already done (flag file exists), skipping.", phase_id)
        return 0

    cmd = [
        sys.executable, __file__,
        "--single-phase", phase_id,
        "--model", model,
    ]
    log.info("Subprocess for phase %s: %s", phase_id, " ".join(cmd))
    timeout = 7200 if phase_id == "REPORTS" else 7200
    result = sp.run(cmd, timeout=timeout)
    return result.returncode


def _run_single_phase(phase_id: str, model: str):
    """Execute one phase in the current process (called from subprocess)."""
    if phase_id in ASSIGNMENT_CONFIGS:
        run_coding_phase(phase_id, model)
    elif phase_id == "REPORTS":
        run_reports_phase(model)
    else:
        log.error("Unknown phase: %s", phase_id)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Trajectory report tests")
    parser.add_argument("--phases", default=",".join(ALL_PHASES),
                        help=f"Comma-separated phases: {','.join(ALL_PHASES)}")
    parser.add_argument("--model", default="gemma12b",
                        help="Model key: gemma12b, gemma27b_cloud")
    parser.add_argument("--reports-only", action="store_true",
                        help="Skip coding passes, generate reports only")
    parser.add_argument("--no-subprocess", action="store_true",
                        help="Run all phases in-process (dev/debug only)")
    parser.add_argument("--reset-flags", action="store_true",
                        help="Clear done-flags and re-run all phases from scratch")
    parser.add_argument("--single-phase", default=None,
                        help="(internal) Run a single phase in this process")
    args = parser.parse_args()

    # --- Single-phase mode: called from subprocess ---
    if args.single_phase:
        _run_single_phase(args.single_phase, args.model)
        return

    if args.reset_flags:
        for phase in ALL_PHASES:
            flag = _flag_path(phase)
            if flag.exists():
                flag.unlink()
                log.info("Reset flag: %s", phase)

    if args.reports_only:
        phases = ["REPORTS"]
    else:
        phases = [p.strip().upper() for p in args.phases.split(",")]
        for p in phases:
            if p not in ALL_PHASES:
                log.error("Unknown phase: %s (valid: %s)", p, ALL_PHASES)
                sys.exit(1)

    model = args.model
    model_display = MODELS.get(model, {}).get("model", model)

    print(f"\n{'═'*70}")
    print(f"  Trajectory Report Tests")
    print(f"  Course: {COURSE_NAME}")
    print(f"  Corpus: {CORPUS_PATH.name}")
    print(f"  Model:  {model_display}")
    print(f"  Phases: {phases}")
    print(f"  Output: {OUTPUT_DIR}")
    if not args.no_subprocess:
        print(f"  Mode:   subprocess isolation (Metal memory reclaimed per phase)")
    if MODELS.get(model, {}).get("name") == "mlx":
        print(f"  NOTE:   Run with 'caffeinate -i' to prevent Metal deadlocks on sleep:")
        print(f"          caffeinate -i python scripts/run_trajectory_tests.py --model {model}")
    print(f"{'═'*70}")

    if not args.no_subprocess:
        _metal_warmup(model)

    phase_results = {}

    for phase_id in phases:
        if args.no_subprocess:
            _run_single_phase(phase_id, model)
            phase_results[phase_id] = "done"
        else:
            try:
                rc = _run_phase_subprocess(phase_id, model)
                phase_results[phase_id] = "OK" if rc == 0 else f"exit {rc}"
            except Exception as e:
                log.error("Phase %s subprocess failed: %s", phase_id, e)
                phase_results[phase_id] = f"FAILED: {e}"

            if phase_id != phases[-1]:
                log.info("Pausing %ds for Metal memory reclamation...",
                         _INTER_PHASE_PAUSE)
                time.sleep(_INTER_PHASE_PAUSE)

    print(f"\n{'='*70}")
    print(f"  ALL PHASES COMPLETE")
    print(f"{'='*70}")
    for phase_id, status in phase_results.items():
        print(f"  Phase {phase_id}: {status}")
    print(f"  Flag dir: {FLAG_DIR}")
    print(f"  Outputs:  {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
