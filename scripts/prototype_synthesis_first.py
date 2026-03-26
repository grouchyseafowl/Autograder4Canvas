#!/usr/bin/env python3
"""
Prototype: Synthesis-First Architecture

Tests the hypothesis that running a free-form full-class reading BEFORE
per-student coding produces richer, more accurate outputs from an 8B model.

Architecture:
  1. Load all 32 submissions
  2. Run a free-form class reading (all submissions, one prompt)
  3. Inject that reading as context into per-student coding prompts
  4. Compare results on equity-critical students (S023-S029)
     and concern-detection students (S015, S018, S025)

Uses Ollama llama3.1:8b to avoid MLX lock conflict with the running comparison.
"""

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from insights.llm_backend import BackendConfig, send_text

BACKEND = BackendConfig(
    name="mlx",
    model="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
)

# ──────────────────────────────────────────────────────────
# Step 1: Load corpus
# ──────────────────────────────────────────────────────────

with open(ROOT / "data" / "demo_corpus" / "ethnic_studies.json") as f:
    corpus = json.load(f)

by_id = {s["student_id"]: s for s in corpus}
print(f"Loaded {len(corpus)} submissions")

# ──────────────────────────────────────────────────────────
# Step 2: Full-class free-form reading
# ──────────────────────────────────────────────────────────

CLASS_READING_PROMPT = """\
You are helping a teacher understand what their students said this week.
Below are all student submissions for one assignment. Read them as a
community in conversation — notice what they're reaching for, where
they connect, where they disagree, where they surprise you.

Assignment: Week 6 Discussion: Intersectionality in Practice
Course: Ethnic Studies (11), Period 3
Teacher's context: Studying Kimberlé Crenshaw and intersectionality
frameworks. Next week: structural racism and policing.

SUBMISSIONS:
{submissions_block}

---

Produce a free-form reading of this class. You are not classifying or
grading — you are noticing. Address these three orientations:

1. ASSET READING: What knowledge, skills, and capacities are students
   bringing to this material? Where is unexpected competence? Where are
   students doing intellectual work that doesn't look like the expected
   format but IS rigorous thinking?

2. THRESHOLD READING: Where are students encountering productive
   difficulty? Where is confusion actually a sign of deep engagement
   with a hard concept? What questions are students circling that they
   haven't quite articulated yet?

3. CONNECTION READING: What connections are students making — to each
   other, to outside knowledge, to their own lives? Where are productive
   tensions between different students' understandings? Who is in
   unspoken dialogue with whom?

   Pay special attention to RELATIONAL MOVES — moments where one student's
   framing affects how other students' voices land. Examples:
   - A student calling for "calm" or "civility" in a class where others
     are expressing urgent anger about injustice (tone policing)
   - A student attributing traits to an entire group in a class where
     members of that group are writing as individuals (essentializing)
   - A student saying "I don't see race" in a class where others just
     described how race shaped their family's life (colorblind erasure)
   - A student implying certain writing styles aren't "academic enough"
     in a class where those styles are doing rigorous intellectual work
   These are only visible when you read the class as a community — name
   them when you see them, because they matter for who feels safe to speak.

Use student names. Quote their actual words. Notice what's quiet as
much as what's loud. Write 400-600 words.
"""

SYSTEM = (
    "You are a perceptive reader of student work. You notice what students "
    "are reaching for, not just what they produce. Non-standard English, "
    "AAVE, multilingual syntax, and neurodivergent writing styles are valid "
    "academic registers — they are assets, not deficits."
)


def build_submissions_block(max_words_per=150):
    parts = []
    for s in corpus:
        text = s["text"]
        words = text.split()
        if len(words) > max_words_per:
            text = " ".join(words[:max_words_per]) + "..."
        parts.append(f"### {s['student_name']} ({s['word_count']} words)")
        parts.append(text)
        parts.append("")
    return "\n".join(parts)


def send_with_retry(backend, prompt, system, max_tokens, max_retries=5):
    """Send with exponential backoff for rate limits."""
    for attempt in range(max_retries):
        try:
            return send_text(backend, prompt, system, max_tokens=max_tokens)
        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 30 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s (attempt {attempt+1}/{max_retries})...")
                time.sleep(wait)
            else:
                raise


print("\n── Step 2: Full-class free-form reading ──")
t0 = time.time()
submissions_block = build_submissions_block()
prompt = CLASS_READING_PROMPT.format(submissions_block=submissions_block)
print(f"  Prompt: {len(prompt.split())} words (~{len(prompt)//4} tokens)")

class_reading = send_with_retry(BACKEND, prompt, SYSTEM, max_tokens=1200)
elapsed = time.time() - t0
print(f"  Done: {elapsed:.1f}s")
print(f"  Output: {len(class_reading.split())} words")
print()
print("── CLASS READING ──")
print(class_reading)
print("── END ──")

# ──────────────────────────────────────────────────────────
# Step 3: Per-student coding WITH class context
# ──────────────────────────────────────────────────────────

CODING_WITH_CONTEXT_PROMPT = """\
You are coding one student's submission for a teacher's review.

CLASS CONTEXT (from reading the full set of 32 submissions):
---
{class_reading}
---

Now code this individual student within that class context.

STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Respond with JSON:
{{
  "theme_tags": ["tag1", "tag2"],
  "notable_quotes": [
    {{"text": "exact quote", "significance": "why it matters"}}
  ],
  "emotional_register": "analytical|passionate|personal|urgent|reflective",
  "what_student_is_reaching_for": "1-2 sentence observation about what this student seems to be trying to do intellectually",
  "concerns": [
    {{
      "flagged_passage": "exact text",
      "why_flagged": "brief explanation",
      "confidence": 0.0-1.0
    }}
  ]
}}

CONCERN GUIDELINES:
Flag ONLY: (a) language that essentializes groups (including positive
stereotypes like "they always...", "[group] is so resilient"), (b) colorblind
claims, (c) tone policing, (d) acute personal distress.
Do NOT flag: anger about injustice, students using their own identity as the
analytical subject, non-standard writing styles, or short submissions.

If a student is doing intellectual work in a non-standard form, name that
as an asset in what_student_is_reaching_for, not a concern.

If no concerns, return empty list: "concerns": []
"""

# Test students: equity-critical + concern-detection
TEST_STUDENTS = [
    "S015",  # Brittany Okafor — essentializer (must flag)
    "S018",  # Connor Walsh — colorblind (must flag)
    "S025",  # Aiden Brooks — tone policer (must flag)
    "S023",  # Yolanda Fuentes — lived experience, no vocab (must NOT flag)
    "S027",  # Camille Osei — outside source (must NOT flag)
    "S028",  # Imani Drayton — AAVE (must NOT flag)
    "S029",  # Jordan Espinoza — neurodivergent writing (must NOT flag)
]

print(f"\n── Step 3: Coding {len(TEST_STUDENTS)} test students with class context ──")

results = {}
for sid in TEST_STUDENTS:
    s = by_id[sid]
    print(f"\n  [{sid}] {s['student_name']}...", end="", flush=True)
    t0 = time.time()

    prompt = CODING_WITH_CONTEXT_PROMPT.format(
        class_reading=class_reading,
        student_name=s["student_name"],
        submission_text=s["text"],
    )

    raw = send_with_retry(BACKEND, prompt, SYSTEM, max_tokens=600)
    elapsed = time.time() - t0
    print(f" {elapsed:.1f}s")

    # Parse JSON from response
    try:
        # Find JSON in the response
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            parsed = json.loads(raw[start:end])
        else:
            parsed = {"_raw": raw, "_parse_error": "no JSON found"}
    except json.JSONDecodeError as e:
        parsed = {"_raw": raw[:500], "_parse_error": str(e)}

    results[sid] = {
        "student_name": s["student_name"],
        "pattern": s["pattern"],
        "coding": parsed,
    }

# ──────────────────────────────────────────────────────────
# Step 4: Evaluate
# ──────────────────────────────────────────────────────────

print("\n\n" + "=" * 60)
print("SYNTHESIS-FIRST PROTOTYPE RESULTS")
print("=" * 60)

equity_ids = {"S023", "S027", "S028", "S029"}
concern_ids = {"S015", "S018", "S025"}

print("\n── Concern Detection (must flag) ──")
for sid in sorted(concern_ids):
    r = results.get(sid, {})
    coding = r.get("coding", {})
    concerns = coding.get("concerns", [])
    name = r.get("student_name", "?")
    pattern = r.get("pattern", "?")
    flagged = len(concerns) > 0 and not coding.get("_parse_error")
    print(f"  {sid} {name} ({pattern}): {'FLAGGED' if flagged else 'MISSED'}")
    for c in concerns:
        if isinstance(c, dict):
            print(f"    why: {c.get('why_flagged', '')[:80]}")

print("\n── Equity-Critical (must NOT flag) ──")
for sid in sorted(equity_ids):
    r = results.get(sid, {})
    coding = r.get("coding", {})
    concerns = coding.get("concerns", [])
    name = r.get("student_name", "?")
    pattern = r.get("pattern", "?")
    clean = len(concerns) == 0 or coding.get("_parse_error")
    print(f"  {sid} {name} ({pattern}): {'CLEAN' if clean else 'FALSE POSITIVE'}")
    if not clean:
        for c in concerns:
            if isinstance(c, dict):
                print(f"    why: {c.get('why_flagged', '')[:80]}")

print("\n── Qualitative: what_student_is_reaching_for ──")
for sid in sorted(results.keys()):
    r = results[sid]
    coding = r.get("coding", {})
    reaching = coding.get("what_student_is_reaching_for", "(none)")
    print(f"  {sid} {r['student_name']}: {reaching}")

print("\n── Qualitative: theme_tags ──")
for sid in sorted(results.keys()):
    r = results[sid]
    coding = r.get("coding", {})
    tags = coding.get("theme_tags", [])
    print(f"  {sid} {r['student_name']}: {tags}")

# Save full results
output_path = ROOT / "data" / "demo_baked" / "synthesis_first_mlx_llama_v3.json"
with open(output_path, "w") as f:
    json.dump({
        "class_reading": class_reading,
        "results": results,
    }, f, indent=2)
print(f"\nFull results saved to: {output_path}")
