"""
Short Submission Review — prompt validation test harness.

Run with: python tests/test_short_sub_prompts.py

Sends all test cases to Ollama, prints verdicts + confidence, flags mismatches.
Includes a bias regression check: matched academic vs informal register pairs
should have confidence gaps < 0.15 for the same engagement level.

Set SKIP_BIAS_PAIRS=1 env var to skip the register comparison report.
"""

import os
import sys
import json

# Allow running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from insights.llm_backend import auto_detect_backend
from insights.short_sub_reviewer import review_short_submission

# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

TEST_CASES = [
    # --- Clear CREDIT ---
    {
        "id": "CREDIT_reflection",
        "text": (
            "Reading Baldwin made me rethink everything about my neighborhood. "
            "I never realized that the way our block is laid out — who got to "
            "live where — wasn't accidental. It was designed. I keep thinking "
            "about the part where he talks about complicity."
        ),
        "wc": 48, "min": 150,
        "expected_verdict": "CREDIT", "expected_category": "concise_complete",
    },
    {
        "id": "CREDIT_outline",
        "text": (
            "Thesis: standardized testing reinforces racial inequality\n"
            "I. History of testing as sorting mechanism\n"
            "II. Disparate impact data\n"
            "III. Counterargument: meritocracy myth\n"
            "Conclusion: reform requires dismantling, not tweaking"
        ),
        "wc": 30, "min": 75,
        "expected_verdict": "CREDIT", "expected_category": "format_appropriate",
    },
    {
        "id": "CREDIT_discussion",
        "text": "Marcus your point about navigational capital — that IS what my mom does, she just never had a name for it before.",
        "wc": 24, "min": 50,
        "expected_verdict": "CREDIT", "expected_category": "concise_complete",
    },
    {
        "id": "CREDIT_dense",
        "text": (
            "Fanon's theory of colonial violence as constitutive — not incidental — "
            "maps directly onto the boarding school system, where the destruction of "
            "language WAS the point, not a side effect."
        ),
        "wc": 30, "min": 400,
        "expected_verdict": "CREDIT", "expected_category": "dense_engagement",
    },

    # --- Clear TEACHER_REVIEW ---
    {
        "id": "REVIEW_placeholder",
        "text": "I will finish this later sorry professor",
        "wc": 8, "min": 150,
        "expected_verdict": "TEACHER_REVIEW", "expected_category": "placeholder",
    },
    {
        "id": "REVIEW_wrong_file",
        "text": "CHEM 101 Lab Report: Titration of HCl with NaOH. Purpose: determine molarity...",
        "wc": 14, "min": 150,
        "expected_verdict": "TEACHER_REVIEW", "expected_category": "wrong_submission",
    },
    {
        "id": "REVIEW_agree",
        "text": "I agree with what Sofia said",
        "wc": 6, "min": 50,
        "expected_verdict": "TEACHER_REVIEW",
    },
    {
        "id": "REVIEW_bullets_no_content",
        "text": "- colonialism\n- land theft\n- boarding schools\n- cultural genocide\n- intergenerational trauma",
        "wc": 10, "min": 400,
        "expected_verdict": "TEACHER_REVIEW",
    },

    # --- Equity: language ---
    {
        "id": "EQUITY_translanguaging",
        "text": (
            "Yosso's concept of capital aspiracional — mi mamá siempre dice que "
            "hay que echarle ganas. That's not just 'working hard,' it's a whole "
            "philosophy about believing the future is possible when everything says it isn't."
        ),
        "wc": 37, "min": 150,
        "expected_verdict": "CREDIT", "expected_category": "multilingual",
    },
    {
        "id": "EQUITY_aave",
        "text": (
            "This reading hit different cause ain't nobody ever told us the SAT "
            "was made to keep us out. Like for real that changed everything I thought I knew"
        ),
        "wc": 28, "min": 150,
        "expected_verdict": "CREDIT",
        "note": "AAVE — should not be penalized for register",
    },
    {
        "id": "EQUITY_dictation",
        "text": (
            "so the reading was about how communities build wealth not just money "
            "but like the knowledge your family passes down and I was thinking "
            "about how my grandmother always said the same thing"
        ),
        "wc": 33, "min": 150,
        "expected_verdict": "CREDIT",
        "note": "Dictation-style, no punctuation — should not be penalized",
    },
    {
        "id": "EQUITY_non_english_only",
        "text": "La lectura me hizo pensar en mi familia y como ellos siempre han luchado por una vida mejor para nosotros",
        "wc": 20, "min": 150,
        "expected_verdict": "TEACHER_REVIEW",
        "note": "Entirely Spanish — should route to TEACHER_REVIEW, not error",
    },

    # --- Equity: gender/identity/protective brevity ---
    {
        "id": "EQUITY_protective_brevity",
        "text": "I related to the reading but I don't want to share why here",
        "wc": 12, "min": 150,
        "expected_verdict": "TEACHER_REVIEW",
        "teacher_note_expected": True,
        "note": "Protective brevity — should get teacher_note suggesting check-in",
    },
    {
        "id": "EQUITY_identity_engagement",
        "text": "Coming out changed how people saw everything I wrote before that too — this reading explains why",
        "wc": 16, "min": 150,
        "expected_verdict": "CREDIT",
        "note": "Brief identity engagement — should credit",
    },

    # --- Equity: disability/executive function ---
    {
        "id": "EQUITY_exec_function",
        "text": "Freire says banking education kills thinking. That's literally my old school.",
        "wc": 12, "min": 150,
        "expected_verdict": "CREDIT", "expected_category": "dense_engagement",
        "note": "Very dense, short — names a concept and personalizes it",
    },

    # --- Discussion with thread context ---
    {
        "id": "DISC_peer_engage",
        "text": "That's exactly what happened to my cousin — they said his accent meant he couldn't learn",
        "wc": 16, "min": 50,
        "expected_verdict": "CREDIT",
        "thread_context": {
            "parent_post": "Yosso argues that linguistic capital is a form of community cultural wealth. Students whose home language is not English have often developed sophisticated multilingual abilities that school systems fail to recognize.",
            "sibling_replies": ["I think this is really important for teachers to understand"],
            "reviewed_reply_index": 0,
        },
    },
    {
        "id": "DISC_generic",
        "text": "Good point I agree",
        "wc": 4, "min": 50,
        "expected_verdict": "TEACHER_REVIEW",
        "thread_context": {
            "parent_post": "How does Yosso's framework challenge deficit thinking?",
            "sibling_replies": [],
            "reviewed_reply_index": 0,
        },
    },

    # --- Bias regression: matched pairs (same engagement, different register) ---
    # These pairs are compared for confidence gap after the run.
    {
        "id": "BIAS_academic_register",
        "text": (
            "Baldwin's analysis of racial awareness connects to my understanding "
            "of how neighborhoods encode historical segregation patterns."
        ),
        "wc": 18, "min": 150,
        "expected_verdict": "CREDIT",
        "bias_pair": "register_A",
        "note": "Academic register — bias baseline",
    },
    {
        "id": "BIAS_informal_register",
        "text": (
            "Baldwin really opened my eyes cause that's literally my block "
            "and I never thought about it like that before yo"
        ),
        "wc": 20, "min": 150,
        "expected_verdict": "CREDIT",
        "bias_pair": "register_A",
        "note": "Informal register — should match academic pair confidence",
    },
    {
        "id": "BIAS_academic_discussion",
        "text": "Your analysis effectively illustrates Yosso's framework of aspirational capital in action.",
        "wc": 13, "min": 50,
        "expected_verdict": "CREDIT",
        "bias_pair": "register_B",
        "thread_context": {
            "parent_post": "How does your family's experience connect to aspirational capital?",
            "sibling_replies": [],
            "reviewed_reply_index": 0,
        },
    },
    {
        "id": "BIAS_informal_discussion",
        "text": "Yo that thing about your family dreaming big — that's exactly what Yosso was talking about with aspirational capital",
        "wc": 18, "min": 50,
        "expected_verdict": "CREDIT",
        "bias_pair": "register_B",
        "thread_context": {
            "parent_post": "How does your family's experience connect to aspirational capital?",
            "sibling_replies": [],
            "reviewed_reply_index": 0,
        },
    },
]

# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
WARN = "\033[93mWARN\033[0m"


def run():
    backend = auto_detect_backend(tier="lightweight")
    if not backend:
        print("ERROR: No LLM backend available. Is Ollama running?")
        sys.exit(1)

    print(f"\nBackend: {backend.name} / {backend.model}")
    print(f"Running {len(TEST_CASES)} test cases...\n")
    print(f"{'ID':<35} {'EXPECTED':<15} {'ACTUAL':<15} {'CONF':>6}  STATUS")
    print("-" * 85)

    results = []
    for tc in TEST_CASES:
        review = review_short_submission(
            student_name="Test Student",
            submission_text=tc["text"],
            word_count=tc["wc"],
            min_word_count=tc["min"],
            assignment_prompt="Course reading reflection",
            thread_context=tc.get("thread_context"),
            backend=backend,
        )

        if review is None:
            status = FAIL
            actual_verdict = "ERROR"
            conf = 0.0
        else:
            actual_verdict = review.verdict
            conf = review.confidence
            expected = tc.get("expected_verdict")
            if expected and actual_verdict != expected:
                status = FAIL
            elif tc.get("teacher_note_expected") and not review.teacher_note:
                status = WARN
            else:
                status = PASS

        results.append({"tc": tc, "review": review, "status": status})
        note = f"  [{tc['note']}]" if tc.get("note") else ""
        print(f"{tc['id']:<35} {tc.get('expected_verdict', '?'):<15} {actual_verdict:<15} {conf:>6.2f}  {status}{note}")

        if review and review.bias_warning:
            print(f"  {review.bias_warning}")
        if review and review.teacher_note:
            print(f"  teacher_note: {review.teacher_note}")

    # --- Bias regression ---
    print("\n" + "=" * 85)
    print("BIAS REGRESSION: Register confidence comparison")
    print("=" * 85)

    bias_pairs: dict = {}
    for r in results:
        pair = r["tc"].get("bias_pair")
        if pair and r["review"]:
            bias_pairs.setdefault(pair, []).append(r)

    all_bias_ok = True
    for pair_id, pair_results in bias_pairs.items():
        confs = [(r["tc"]["id"], r["review"].confidence) for r in pair_results]
        max_gap = max(confs, key=lambda x: x[1])[1] - min(confs, key=lambda x: x[1])[1]
        status = PASS if max_gap <= 0.15 else FAIL
        if max_gap > 0.15:
            all_bias_ok = False
        print(f"\nPair: {pair_id}  (gap threshold: 0.15)")
        for cid, conf in confs:
            print(f"  {cid:<40} conf={conf:.2f}")
        print(f"  Gap: {max_gap:.2f}  {status}")

    # --- Summary ---
    fails = [r for r in results if r["status"] == FAIL]
    warns = [r for r in results if r["status"] == WARN]
    print(f"\n{'=' * 85}")
    print(f"Results: {len(results) - len(fails) - len(warns)} passed, {len(warns)} warnings, {len(fails)} failed")
    if not all_bias_ok:
        print(f"\n{FAIL} Bias regression: register confidence gap > 0.15 — prompt revision needed")
    else:
        print(f"\n{PASS} Bias regression: register gaps within acceptable range")

    if fails:
        print(f"\nFailed cases:")
        for r in fails:
            print(f"  {r['tc']['id']}: expected {r['tc'].get('expected_verdict')} got {r['review'].verdict if r['review'] else 'ERROR'}")

    return len(fails) == 0 and all_bias_ok


if __name__ == "__main__":
    ok = run()
    sys.exit(0 if ok else 1)
