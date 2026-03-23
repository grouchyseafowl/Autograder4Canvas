#!/usr/bin/env python3
"""
Prototype: Pairwise Relational Concern Check

Tests whether an 8B model can detect tone policing when explicitly shown
the pairing — Aiden's civility request alongside Destiny's urgent anger.

The hypothesis: the model can evaluate the relational dynamic when forced
to see both sides, even though it can't identify the dynamic on its own.

Uses MLX Llama 3.1 8B.
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

SYSTEM = (
    "You are a perceptive reader of student work. You notice what students "
    "are reaching for, not just what they produce. Non-standard English, "
    "AAVE, multilingual syntax, and neurodivergent writing styles are valid "
    "academic registers — they are assets, not deficits."
)

# Load corpus
with open(ROOT / "data" / "demo_corpus" / "ethnic_studies.json") as f:
    corpus = json.load(f)
by_id = {s["student_id"]: s for s in corpus}

# ──────────────────────────────────────────────────────────
# Step 1: Standard concern check (baseline — no pairing)
# ──────────────────────────────────────────────────────────

STANDARD_CONCERN_PROMPT = """\
Review this student submission for passages that might need the teacher's attention.

STUDENT: {student_name}
SUBMISSION:
---
{submission_text}
---

Flag concerns ONLY for:
(a) Essentializing language — attributing traits to entire groups, including positive
    stereotypes ("they always...", "[group] is so resilient")
(b) Colorblind/post-racial claims ("I don't see race", "treat everyone the same")
(c) Tone policing — dismissing others' emotional responses, calling for "civility"
    in ways that silence urgency about injustice ("too emotional", "not productive",
    "without getting heated", "respectful conversation")
(d) Acute personal distress unrelated to course material

Do NOT flag: anger about injustice, students using their own identity as the
analytical subject, non-standard writing styles.

Respond with JSON:
{{"concerns": [{{"flagged_passage": "exact text", "why_flagged": "explanation", "confidence": 0.0-1.0}}]}}
If no concerns: {{"concerns": []}}
"""

# ──────────────────────────────────────────────────────────
# Step 2: Pairwise relational concern check
# ──────────────────────────────────────────────────────────

PAIRWISE_CONCERN_PROMPT = """\
Read these two student submissions together. They are from the same class,
responding to the same assignment about intersectionality.

STUDENT A: {student_a_name}
---
{student_a_text}
---

STUDENT B: {student_b_name}
---
{student_b_text}
---

Now evaluate Student B's submission in light of Student A's.

Student A has expressed {student_a_register} about {student_a_topic}.
Student B calls for {student_b_framing}.

THE QUESTION: Does Student B's call for {student_b_framing} function as
tone policing — does it delegitimize or silence Student A's way of engaging
with the material? Or is it a genuinely independent reflection?

Consider: If Student A reads Student B's words, does it tell them their
emotional response was wrong? Does it create pressure to suppress their
authentic engagement in future class discussions?

Respond with JSON:
{{
  "is_tone_policing": true or false,
  "reasoning": "your analysis of the relational dynamic",
  "what_it_costs": "if tone policing, what does it cost Student A?",
  "confidence": 0.0-1.0
}}
"""

# ──────────────────────────────────────────────────────────
# Run tests
# ──────────────────────────────────────────────────────────

print("=" * 60)
print("PAIRWISE RELATIONAL CONCERN CHECK PROTOTYPE")
print("Model: Llama 3.1 8B MLX")
print("=" * 60)

# Test 1: Standard check on S025 Aiden (baseline — expect miss)
aiden = by_id["S025"]
print(f"\n── Test 1: Standard concern check on S025 Aiden Brooks ──")
t0 = time.time()
prompt = STANDARD_CONCERN_PROMPT.format(
    student_name=aiden["student_name"],
    submission_text=aiden["text"],
)
raw = send_text(BACKEND, prompt, SYSTEM, max_tokens=400)
print(f"  Time: {time.time()-t0:.1f}s")
try:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    parsed = json.loads(raw[start:end]) if start >= 0 else {"_raw": raw}
except:
    parsed = {"_raw": raw[:300]}
concerns = parsed.get("concerns", [])
print(f"  Result: {'FLAGGED' if concerns else 'MISSED'} ({len(concerns)} concerns)")
for c in concerns:
    if isinstance(c, dict):
        print(f"    why: {c.get('why_flagged','')[:80]}")

# Test 2: Pairwise check — Aiden in light of Destiny
destiny = by_id["S022"]
print(f"\n── Test 2: Pairwise check — Aiden in light of Destiny Williams ──")
t0 = time.time()
prompt = PAIRWISE_CONCERN_PROMPT.format(
    student_a_name=destiny["student_name"],
    student_a_text=destiny["text"],
    student_b_name=aiden["student_name"],
    student_b_text=aiden["text"],
    student_a_register="urgent anger",
    student_a_topic="redlining and how intersectionality describes her family's dispossession",
    student_b_framing="calm, respectful, non-emotional discussion",
)
raw = send_text(BACKEND, prompt, SYSTEM, max_tokens=400)
print(f"  Time: {time.time()-t0:.1f}s")
try:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    parsed = json.loads(raw[start:end]) if start >= 0 else {"_raw": raw}
except:
    parsed = {"_raw": raw[:500]}
print(f"  is_tone_policing: {parsed.get('is_tone_policing', '(parse failed)')}")
print(f"  confidence: {parsed.get('confidence', '?')}")
print(f"  reasoning: {parsed.get('reasoning', parsed.get('_raw',''))[:200]}")
print(f"  what_it_costs: {parsed.get('what_it_costs', '')[:200]}")

# Test 3: Pairwise check — Aiden in light of Rashida (different urgent voice)
rashida = by_id["S007"]
print(f"\n── Test 3: Pairwise check — Aiden in light of Rashida Thompson ──")
t0 = time.time()
prompt = PAIRWISE_CONCERN_PROMPT.format(
    student_a_name=rashida["student_name"],
    student_a_text=rashida["text"],
    student_b_name=aiden["student_name"],
    student_b_text=aiden["text"],
    student_a_register="passionate urgency",
    student_a_topic="how Black girls are disproportionately disciplined in schools",
    student_b_framing="calm, respectful, non-emotional discussion",
)
raw = send_text(BACKEND, prompt, SYSTEM, max_tokens=400)
print(f"  Time: {time.time()-t0:.1f}s")
try:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    parsed = json.loads(raw[start:end]) if start >= 0 else {"_raw": raw}
except:
    parsed = {"_raw": raw[:500]}
print(f"  is_tone_policing: {parsed.get('is_tone_policing', '(parse failed)')}")
print(f"  confidence: {parsed.get('confidence', '?')}")
print(f"  reasoning: {parsed.get('reasoning', parsed.get('_raw',''))[:200]}")
print(f"  what_it_costs: {parsed.get('what_it_costs', '')[:200]}")

# Test 4: Control — pair Aiden with a calm analytical student (should NOT flag)
alex = by_id["S003"]
print(f"\n── Test 4: Control — Aiden paired with Alex Hernandez (calm, analytical) ──")
t0 = time.time()
prompt = PAIRWISE_CONCERN_PROMPT.format(
    student_a_name=alex["student_name"],
    student_a_text=alex["text"],
    student_b_name=aiden["student_name"],
    student_b_text=aiden["text"],
    student_a_register="calm analytical summary",
    student_a_topic="defining intersectionality as a theoretical framework",
    student_b_framing="calm, respectful, non-emotional discussion",
)
raw = send_text(BACKEND, prompt, SYSTEM, max_tokens=400)
print(f"  Time: {time.time()-t0:.1f}s")
try:
    start = raw.find("{")
    end = raw.rfind("}") + 1
    parsed = json.loads(raw[start:end]) if start >= 0 else {"_raw": raw}
except:
    parsed = {"_raw": raw[:500]}
print(f"  is_tone_policing: {parsed.get('is_tone_policing', '(parse failed)')}")
print(f"  confidence: {parsed.get('confidence', '?')}")
print(f"  reasoning: {parsed.get('reasoning', parsed.get('_raw',''))[:200]}")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("If Test 1 = MISSED and Tests 2-3 = tone_policing:true,")
print("  the pairwise approach detects what isolation cannot.")
print("If Test 4 = tone_policing:false,")
print("  the approach correctly distinguishes relational from non-relational contexts.")
