#!/usr/bin/env python3
"""
Assemble Demo Corpus — Steps 1-5 of the DAIGT Testing Brief.

Stage 1: Download and filter DAIGT data from HuggingFace
Stage 2: Run AIC on filtered essays (calibration check)
Stage 3: Run QuickAnalyzer on a class-sized batch
Stage 4: Select essays for demo corpus + hand-craft key students
Stage 5: Output assembled corpus files

Usage:
    python scripts/assemble_demo_corpus.py [--stage N] [--all]

NOTE: Stage 4 previously used DAIGT-adapted essays for the 19 "normal" corpus
slots. Those produced off-topic essays with thin keyword substitutions (see
docs/comparison_analysis.md §1.2). They have been replaced with authentic
hand-authored replacement submissions loaded from
data/demo_corpus/replacement_students.json via _build_replacement_students().
The old DAIGT adaptation functions are retained below but marked deprecated.
"""

import json
import os
import sys
import time
from pathlib import Path

# Add src/ to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

DATA_DIR = ROOT / "data" / "demo_source"
CORPUS_DIR = ROOT / "data" / "demo_corpus"
ASSETS_DIR = ROOT / "src" / "demo_assets"


# ──────────────────────────────────────────────────────────────
# Stage 1: Download and Filter DAIGT
# ──────────────────────────────────────────────────────────────

def stage1_filter_daigt():
    """Download DAIGT from HuggingFace and filter to human-written essays."""
    print("\n═══ Stage 1: Download + Filter DAIGT ═══")

    from datasets import load_dataset

    print("Loading ramensoft/daigt_v3 from HuggingFace...")
    ds = load_dataset("ramensoft/daigt_v3", split="train")
    print(f"  Total rows: {len(ds)}")

    # Filter: label == 0 (human-written), word count 80-350
    filtered = []
    label_counts = {0: 0, 1: 0}
    for row in ds:
        label = row.get("label", -1)
        label_counts[label] = label_counts.get(label, 0) + 1

        if label != 0:
            continue

        text = row.get("text", "")
        wc = len(text.split())
        if wc < 80 or wc > 350:
            continue

        source = row.get("source", "unknown")
        prompt_name = row.get("prompt_name", "")

        filtered.append({
            "source_id": f"daigt_{len(filtered):05d}",
            "text": text,
            "word_count": wc,
            "source": source,
            "prompt_name": prompt_name,
        })

    print(f"  Label distribution: {label_counts}")
    print(f"  After filtering (human + 80-350 words): {len(filtered)}")

    # Source distribution
    sources = {}
    for e in filtered:
        s = e["source"]
        sources[s] = sources.get(s, 0) + 1
    print(f"  Source distribution: {sources}")

    # Word count stats
    wcs = [e["word_count"] for e in filtered]
    print(f"  Word count: min={min(wcs)}, max={max(wcs)}, "
          f"median={sorted(wcs)[len(wcs)//2]}, mean={sum(wcs)/len(wcs):.0f}")

    out_path = DATA_DIR / "daigt_filtered.json"
    out_path.write_text(json.dumps(filtered, indent=2))
    print(f"  Saved {len(filtered)} essays to {out_path}")

    return filtered


# ──────────────────────────────────────────────────────────────
# Stage 2: Run AIC on Filtered Essays
# ──────────────────────────────────────────────────────────────

def stage2_run_aic(filtered_essays):
    """Run DishonestyAnalyzer on filtered essays as a calibration check."""
    print("\n═══ Stage 2: AIC Calibration ═══")

    from Academic_Dishonesty_Check_v2 import DishonestyAnalyzer

    analyzer = DishonestyAnalyzer(
        profile_id="standard",
        context_profile="high_school",
    )

    results = []
    t0 = time.time()

    # Run on first 100 (or all if fewer)
    batch = filtered_essays[:100]
    print(f"  Running AIC on {len(batch)} essays...")

    for i, essay in enumerate(batch):
        result = analyzer.analyze_text(
            text=essay["text"],
            student_id=essay["source_id"],
            student_name=f"DAIGT-{essay['source_id']}",
        )

        results.append({
            "source_id": essay["source_id"],
            "word_count": essay["word_count"],
            "suspicious_score": result.suspicious_score,
            "authenticity_score": result.authenticity_score,
            "concern_level": result.concern_level,
            "smoking_gun": result.smoking_gun,
            "human_presence_confidence": result.human_presence_confidence,
            "human_presence_level": result.human_presence_level,
            "markers_found": result.markers_found,
            "marker_counts": result.marker_counts,
        })

        if (i + 1) % 25 == 0:
            print(f"    Processed {i + 1}/{len(batch)}...")

    elapsed = time.time() - t0
    print(f"  AIC complete: {elapsed:.1f}s ({elapsed/len(batch):.2f}s/essay)")

    # Success criteria
    low_concern = sum(1 for r in results if r["concern_level"] == "low")
    smoking_guns = sum(1 for r in results if r["smoking_gun"])
    hp_detected = sum(1 for r in results
                      if r["human_presence_confidence"] and r["human_presence_confidence"] > 0.5)

    print(f"\n  ── Success Criteria ──")
    print(f"  Low concern: {low_concern}/{len(results)} "
          f"({100*low_concern/len(results):.0f}%) — target ≥90%: "
          f"{'✓' if low_concern >= 0.9 * len(results) else '✗'}")
    print(f"  Smoking guns: {smoking_guns} — target 0: "
          f"{'✓' if smoking_guns == 0 else '✗'}")
    print(f"  Human presence detected: {hp_detected}/{len(results)} "
          f"({100*hp_detected/len(results):.0f}%) — target ≥80%: "
          f"{'✓' if hp_detected >= 0.8 * len(results) else '✗'}")

    # Score distribution
    scores = [r["suspicious_score"] for r in results]
    print(f"\n  Suspicious score distribution:")
    for bucket, lo, hi in [("<10", 0, 10), ("10-20", 10, 20), ("20-30", 20, 30),
                            ("30-50", 30, 50), ("50+", 50, 100)]:
        n = sum(1 for s in scores if lo <= s < hi)
        print(f"    {bucket}: {n} ({100*n/len(scores):.0f}%)")

    # Concern level distribution
    concern_dist = {}
    for r in results:
        cl = r["concern_level"]
        concern_dist[cl] = concern_dist.get(cl, 0) + 1
    print(f"  Concern levels: {concern_dist}")

    out_path = DATA_DIR / "daigt_aic_results.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"  Saved AIC results to {out_path}")

    return results


# ──────────────────────────────────────────────────────────────
# Stage 3: Run QuickAnalyzer
# ──────────────────────────────────────────────────────────────

def stage3_quick_analysis(filtered_essays):
    """Run QuickAnalyzer on a class-sized batch (~30 essays)."""
    print("\n═══ Stage 3: QuickAnalyzer ═══")

    from insights.quick_analyzer import QuickAnalyzer

    batch = filtered_essays[:30]
    submissions = []
    for essay in batch:
        submissions.append({
            "student_id": essay["source_id"],
            "student_name": f"DAIGT-{essay['source_id']}",
            "body": essay["text"],
            "submission_type": "online_text_entry",
            "word_count": essay["word_count"],
            "submitted_at": "2026-03-08T22:00:00Z",
            "due_at": "2026-03-08T23:59:00Z",
        })

    analyzer = QuickAnalyzer()
    t0 = time.time()
    qa_result = analyzer.analyze(
        submissions,
        assignment_id="test-001",
        assignment_name="Test Analysis",
        course_id="test-course",
        course_name="Test Course",
    )
    elapsed = time.time() - t0
    print(f"  QuickAnalyzer complete: {elapsed:.1f}s")

    # Summarize results
    print(f"\n  ── QuickAnalysis Summary ──")
    print(f"  Submissions analyzed: {qa_result.stats.total_submissions}")
    print(f"  Clusters found: {len(qa_result.clusters)}")
    print(f"  Embedding outliers: {qa_result.embedding_outlier_ids}")
    print(f"  Sentiment distribution: {qa_result.sentiment_distribution}")
    print(f"  Concern signals: {len(qa_result.concern_signals)}")
    print(f"  Top terms: {[t.term for t in qa_result.top_terms[:10]]}")

    # Save full result
    out_path = DATA_DIR / "daigt_quick_analysis.json"
    out_path.write_text(qa_result.model_dump_json(indent=2))
    print(f"  Saved QuickAnalysis to {out_path}")

    return qa_result


# ──────────────────────────────────────────────────────────────
# Stage 4: Select essays for demo corpus + hand-craft key students
# ──────────────────────────────────────────────────────────────

def stage4_assemble_corpus(filtered_essays, aic_results, qa_result):
    """Select DAIGT essays and hand-craft key students for the demo corpus."""
    print("\n═══ Stage 4: Assemble Demo Corpus ═══")

    # Index AIC results by source_id
    aic_by_id = {r["source_id"]: r for r in aic_results}

    # Select ~15 normal essays: low AIC score, good human presence, varied register
    candidates = []
    for essay in filtered_essays[:100]:
        aic = aic_by_id.get(essay["source_id"])
        if not aic:
            continue
        if aic["suspicious_score"] > 20:
            continue
        if aic["human_presence_confidence"] and aic["human_presence_confidence"] < 0.5:
            continue
        candidates.append({**essay, "aic": aic})

    # Sort by a diversity score (mix of word counts and scores)
    candidates.sort(key=lambda c: c["word_count"])

    # Pick 15 spread across word count range
    normal_picks = []
    step = max(1, len(candidates) // 15)
    for i in range(0, len(candidates), step):
        if len(normal_picks) >= 15:
            break
        normal_picks.append(candidates[i])

    print(f"  Selected {len(normal_picks)} normal essays from DAIGT")

    # Pick 4 for exhaustion_spike (shorten to 100-140 words)
    exhaust_picks = []
    for c in candidates:
        if c["word_count"] >= 180 and len(exhaust_picks) < 4:
            # Truncate to 100-140 words
            words = c["text"].split()
            target = 120  # middle of 100-140
            shortened = " ".join(words[:target])
            exhaust_picks.append({**c, "text": shortened, "word_count": target})

    print(f"  Selected {len(exhaust_picks)} exhaustion_spike essays")

    # ── Hand-crafted students ──
    hand_crafted = _build_hand_crafted_students()
    print(f"  Hand-crafted {len(hand_crafted)} key students")

    # ── Replacement students (authentic submissions) ──
    replacement = _build_replacement_students()
    print(f"  Loaded {len(replacement)} replacement students from replacement_students.json")

    # ── Assemble Ethnic Studies corpus ──
    # Order: hand-crafted first, then replacement students (already carry their
    # own student_ids so no counter arithmetic is needed).
    ethnic_studies = []
    for hc in hand_crafted:
        if hc.get("course") == "ethnic_studies":
            ethnic_studies.append(hc)
    ethnic_studies.extend(replacement)

    print(f"  Ethnic Studies corpus: {len(ethnic_studies)} students")

    # ── Assemble Biology corpus ──
    biology = []
    bio_counter = 1
    # Use remaining normal picks for biology
    remaining = candidates[len(normal_picks):]
    for i, pick in enumerate(remaining[:25]):
        sid = f"B{bio_counter:03d}"
        bio_counter += 1
        biology.append({
            "student_id": sid,
            "student_name": _BIO_NAMES[i % len(_BIO_NAMES)],
            "pattern": "normal",
            "text": _adapt_topic_biology(pick["text"]),
            "word_count": len(_adapt_topic_biology(pick["text"]).split()),
            "source": f"daigt_adapted:{pick['source_id']}",
            "course": "biology",
        })

    print(f"  Biology corpus: {len(biology)} students")

    # Save corpora
    es_path = CORPUS_DIR / "ethnic_studies.json"
    es_path.write_text(json.dumps(ethnic_studies, indent=2))
    print(f"  Saved Ethnic Studies corpus to {es_path}")

    bio_path = CORPUS_DIR / "biology.json"
    bio_path.write_text(json.dumps(biology, indent=2))
    print(f"  Saved Biology corpus to {bio_path}")

    return ethnic_studies, biology


# ──────────────────────────────────────────────────────────────
# Hand-crafted students + replacement students
# ──────────────────────────────────────────────────────────────

def _build_hand_crafted_students():
    """Build the hand-crafted key students per the testing brief."""
    students = []

    # Maria Ndiaye (S001) — ESL / Transnational Voice
    students.append({
        "student_id": "S001",
        "student_name": "Maria Ndiaye",
        "pattern": "esl",
        "course": "ethnic_studies",
        "text": (
            "When I first read about intersectionality I was thinking on my grandmother "
            "in Dakar. She is a woman, she is Wolof, she is old now and she don't have "
            "much money. In Senegal people don't use this word intersectionality but "
            "everybody know that life is harder when you are many things at once that "
            "society don't value. My grandmother she always say that being woman in "
            "Senegal is one thing but being poor woman who is also from village that is "
            "another thing completely.\n\n"
            "When my family come to America I see same thing but different. My mother "
            "she is Black woman here but also immigrant and also Muslim and each of "
            "these things it add up. The reading talk about how categories overlap and "
            "I think this is true but it is not just categories on paper. It is real "
            "life every day, like when my mother go to the school meeting and people "
            "treat her different because she have accent and she wear hijab. "
            "Intersectionality for me it is not theory it is just what my family live "
            "through and I think the reading could be stronger if it include voices "
            "from outside America because this experience it is everywhere not just here."
        ),
    })

    # Jordan Kim (S002) — Burnout
    students.append({
        "student_id": "S002",
        "student_name": "Jordan Kim",
        "pattern": "burnout",
        "course": "ethnic_studies",
        "text": (
            "The reading about intersectionality made me think about how Crenshaw "
            "talks about the ways that race and gender overlap to create unique "
            "experiences that you cant really understand by just looking at one thing "
            "at a time. Like my mom is Korean and a woman and her experience is "
            "different from my dads even though theyre in the same family. I think "
            "this connects to what we talked about last week about how identity is "
            "not just one thing. Idk I had more to say but its late and"
        ),
    })

    # Alex Hernandez (S003) — Smoking Gun
    # Must trigger smoking_gun=True. The detector looks for:
    #   - ≥2 HTML headers (<h2>/<h3>), or
    #   - ≥3 markdown bold (**text**), or
    #   - markdown headers (## text), or
    #   - ≥3 markdown bullets (- item)
    students.append({
        "student_id": "S003",
        "student_name": "Alex Hernandez",
        "pattern": "smoking_gun",
        "course": "ethnic_studies",
        "text": (
            "<h2>Understanding Intersectionality</h2>\n\n"
            "<p>Intersectionality is a theoretical framework that examines how "
            "various social categorizations such as race, class, and gender interact "
            "on multiple levels to create overlapping systems of discrimination or "
            "disadvantage.</p>\n\n"
            "<h3>Key Aspects</h3>\n\n"
            "<p>The concept was first coined by **Kimberlé Crenshaw** in 1989 to "
            "address the marginalization of Black women within both feminist and "
            "anti-racist discourse. It recognizes that individuals possess multiple, "
            "layered identities that shape their lived experiences in profound "
            "ways.</p>\n\n"
            "<h3>Why It Matters</h3>\n\n"
            "<p>Furthermore, intersectionality provides a **critical lens** through "
            "which we can analyze **systemic inequality**. It demonstrates that "
            "social categories are not independent but rather interconnected, "
            "creating **complex systems** of privilege and oppression that affect "
            "individuals differently based on their unique combination of "
            "identities.</p>"
        ),
    })

    # Tyler Nguyen (S010) — Sustained Cheater
    # Generated by Ollama llama3.1:8b — real AI output, not hand-crafted
    students.append({
        "student_id": "S010",
        "student_name": "Tyler Nguyen",
        "pattern": "sustained_cheat",
        "course": "ethnic_studies",
        "text": (
            "The reading on intersectionality highlights the complexities of identity "
            "and how different aspects of it interact to create unique experiences of "
            "privilege and oppression. The author argues that simply being a woman of "
            "color, for example, does not automatically mean that one experiences "
            "oppression. Rather, it is the intersection of factors such as race, class, "
            "and sexuality that determines one's positionality. This idea is "
            "particularly relevant in understanding the experiences of marginalized "
            "communities, as it emphasizes the need to consider multiple axes of "
            "identity.\n\n"
            "I found it striking that the author uses the example of the \"triple "
            "jeopardy\" faced by black women in the Civil Rights Movement. Despite "
            "being a key figure in the movement, black women like Sojourner Truth and "
            "Ida B. Wells faced both racism and sexism. This intersection of "
            "oppressions highlights the ways in which different forms of oppression "
            "can intersect and exacerbate one another.\n\n"
            "What struck me most about this reading was the emphasis on the need for "
            "a more nuanced understanding of identity and power dynamics. Simply being "
            "a member of a marginalized group is not enough to guarantee solidarity or "
            "shared experiences. Rather, we need to consider the specific ways in which "
            "different individuals intersect with multiple forms of oppression."
        ),
    })

    # Jaylen Carter (S011) — Sustained Cheater
    # Generated by Ollama llama3.1:8b — real AI output, not hand-crafted
    students.append({
        "student_id": "S011",
        "student_name": "Jaylen Carter",
        "pattern": "sustained_cheat",
        "course": "ethnic_studies",
        "text": (
            "Intersectionality is a crucial concept in ethnic studies that helps us "
            "comprehend the complexities of discrimination. Developed by Kimberlé "
            "Crenshaw, intersectionality acknowledges that individuals have multiple "
            "identities that intersect and overlap, creating unique experiences of "
            "marginalization. For example, a woman of color may face both sexism and "
            "racism, which cannot be addressed separately. Intersectionality recognizes "
            "that these forms of oppression are not mutually exclusive, but rather "
            "interconnected, leading to a more nuanced understanding of the ways in "
            "which social inequalities intersect.\n\n"
            "By considering multiple identities and experiences, intersectionality "
            "sheds light on the ways in which dominant groups maintain power and "
            "privilege. It highlights the need to address the systemic inequalities "
            "that result from the intersections of racism, sexism, homophobia, and "
            "other forms of oppression. Intersectionality encourages us to move beyond "
            "a simplistic, additive approach to understanding identity and instead, to "
            "consider the complex ways in which multiple forms of oppression are "
            "experienced simultaneously. By doing so, we can develop more effective "
            "strategies for promoting social justice and challenging the status quo. "
            "Ultimately, intersectionality offers a powerful framework for analyzing "
            "and addressing the complexities of oppression in our society."
        ),
    })

    # Essentializer (~S015)
    students.append({
        "student_id": "S015",
        "student_name": "Brittany Okafor",
        "pattern": "essentializer",
        "course": "ethnic_studies",
        "text": (
            "I really liked the reading about intersectionality because it made me "
            "think about the different cultures in my neighborhood. Like in my "
            "neighborhood the Mexican families are always so close and they really "
            "support each other and I think thats what intersectionality is about, "
            "like how different backgrounds come together and make communities "
            "stronger. And the Black families on my street they have this amazing "
            "resilience and they always look out for each other too. I think all "
            "cultures have something beautiful about them and if we could just "
            "appreciate what makes each group special instead of discriminating "
            "then we would be so much better off.\n\n"
            "The reading talked about how identity is layered and I see that with "
            "my friend Rosa who is Latina and also queer and shes like the strongest "
            "person I know because of all she has been through. I think intersectionality "
            "shows us that diversity is our greatest strength and we should celebrate "
            "all the things that make each culture unique."
        ),
    })

    # Colorblind Claimant (~S018)
    students.append({
        "student_id": "S018",
        "student_name": "Connor Walsh",
        "pattern": "colorblind",
        "course": "ethnic_studies",
        "text": (
            "I thought the reading on intersectionality was interesting and I can "
            "see why people study it. The idea that different parts of your identity "
            "affect how you experience the world makes sense to me. Like I understand "
            "that someone who is a woman and also Black might face challenges that "
            "are different from someone who is just one of those things.\n\n"
            "But honestly at the end of the day I just try to treat everyone the same "
            "regardless of what they look like or where they come from. I dont really "
            "see the point of focusing so much on categories and labels because I feel "
            "like that just divides people more. When I meet someone I dont think "
            "about their race or gender I just see a person. I think if more people "
            "had that attitude we wouldnt need frameworks like intersectionality "
            "because we would just respect each other as individuals.\n\n"
            "I know some people might disagree with me on this but I think focusing "
            "too much on differences can actually make things worse sometimes."
        ),
    })

    # Premise Challenger (~S020)
    students.append({
        "student_id": "S020",
        "student_name": "Jake Novak",
        "pattern": "premise_challenger",
        "course": "ethnic_studies",
        "text": (
            "Ok so I read the piece on intersectionality and I have some real "
            "questions about it. The framework talks about how race gender class "
            "all these categories overlap to create different experiences of "
            "oppression and I get that. But the reading acts like intersectionality "
            "covers everything and it doesnt.\n\n"
            "My family is white and poor. Like actually poor, not just middle class "
            "complaining about money. My dad works two jobs and my mom is disabled "
            "and nobody in this framework really talks about us. When the reading "
            "says that privilege operates along axes of race and gender I want to "
            "ask where does my dad's privilege come in? He cant pay the electric "
            "bill half the time. Thats its own kind of erasure.\n\n"
            "Im not saying racism isnt real because obviously it is. Im saying "
            "that this framework has a blind spot for class when its separated "
            "from race and I think thats worth talking about instead of just "
            "accepting the reading as gospel."
        ),
    })

    # Righteous Anger (~S022)
    students.append({
        "student_id": "S022",
        "student_name": "Destiny Williams",
        "pattern": "righteous_anger",
        "course": "ethnic_studies",
        "text": (
            "This reading made me furious and I mean that in a good way. How can "
            "we sit here and read about redlining and act like its ancient history "
            "when my neighborhood still looks exactly like the map from 1940?? The "
            "same blocks that were red-lined are the same blocks with no grocery "
            "stores no good schools no investment. That is intersectionality in "
            "PRACTICE not just theory.\n\n"
            "And it makes me angry when people act like talking about race is "
            "divisive. You know whats divisive? Literal lines drawn on a map that "
            "decided which neighborhoods got resources and which ones didnt and "
            "then telling the people who got nothing that they should just work "
            "harder. The reading talks about overlapping systems and YES thats "
            "exactly it — my grandmother was Black AND poor AND a woman AND living "
            "in a neighborhood the government decided wasnt worth investing in.\n\n"
            "Intersectionality isnt just an academic concept. Its the story of "
            "my family and millions of families like mine and Im tired of "
            "pretending we can discuss it calmly like it doesnt affect real people "
            "right now."
        ),
    })

    # Tone Policer (~S025)
    students.append({
        "student_id": "S025",
        "student_name": "Aiden Brooks",
        "pattern": "tone_policer",
        "course": "ethnic_studies",
        "text": (
            "I read the piece on intersectionality and I think it raises some "
            "good points about how identity is complex. The idea that peoples "
            "experiences are shaped by multiple factors at once is something I "
            "can agree with.\n\n"
            "I do want to say though that I feel like in class discussions about "
            "this stuff people get really heated and I think we should be able "
            "to have these conversations without getting so emotional about it. "
            "Like were all here to learn right? I get that this is important to "
            "people but I feel like when people start getting angry or raising "
            "their voices it actually makes it harder to have a productive "
            "conversation and some people just shut down.\n\n"
            "I think we can talk about intersectionality and systemic issues "
            "in a way thats respectful to everyone in the room. We should "
            "focus on understanding each others perspectives instead of trying "
            "to win arguments. Just my two cents."
        ),
    })

    # Set word counts
    for s in students:
        s["word_count"] = len(s["text"].split())

    return students


def _build_replacement_students():
    """Load the 19 authentic replacement students from replacement_students.json.

    These replace the old DAIGT-adapted essays that produced off-topic text
    with thin keyword substitutions.  See docs/comparison_analysis.md §1.2.

    Returns a list of student dicts in the same format as
    _build_hand_crafted_students():
        student_id, student_name, pattern, course, text, word_count
    """
    src = CORPUS_DIR / "replacement_students.json"
    raw = json.loads(src.read_text())
    students = []
    for s in raw["students"]:
        # Use test_pattern when present, otherwise engagement_category
        pattern = s.get("test_pattern") or s.get("engagement_category", "normal")
        students.append({
            "student_id": s["student_id"],
            "student_name": s["student_name"],
            "pattern": pattern,
            "course": "ethnic_studies",
            "text": s["submission_text"],
            "word_count": s.get("word_count", len(s["submission_text"].split())),
        })
    return students


# ──────────────────────────────────────────────────────────────
# --- DEPRECATED: Historical DAIGT adaptation ---
# These functions were used in the original corpus construction but produced
# off-topic essays with thin keyword swaps. See docs/comparison_analysis.md
# Section 1.2 for the methodology audit that identified this problem.
# Replaced by _build_replacement_students() which loads authentic submissions.
# ──────────────────────────────────────────────────────────────

def _adapt_topic_ethnic_studies(text):
    """Minimal topic adaptation: keeps voice, swaps some references.

    The DAIGT essays are about various school topics. We do light
    keyword swaps to make them read as responses to an Ethnic Studies
    intersectionality discussion. We intentionally don't over-rewrite —
    these are the "normal" students whose specific topic engagement
    is less important than their authentic voice patterns.
    """
    # Light substitutions that preserve sentence structure
    replacements = [
        ("school uniforms", "intersectionality"),
        ("uniforms", "identity categories"),
        ("dress code", "social categories"),
        ("cell phone", "social media"),
        ("cell phones", "social media"),
        ("electoral college", "systemic inequality"),
        ("should be required", "is important to understand"),
        ("should not be required", "can be complicated"),
        ("the government", "society"),
        ("students should", "people should"),
        ("in school", "in our communities"),
        ("in schools", "in society"),
        ("our school", "our community"),
        ("the school", "the system"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
        # Also try title case
        result = result.replace(old.title(), new.title())
    return result


def _adapt_topic_biology(text):
    """Adapt DAIGT essays to sound like biology lab reflections."""
    replacements = [
        ("school uniforms", "cell respiration"),
        ("uniforms", "the lab results"),
        ("dress code", "experimental procedure"),
        ("electoral college", "cellular processes"),
        ("the government", "the data"),
        ("students should", "our group found that"),
        ("in school", "in the lab"),
        ("in schools", "in our experiments"),
        ("our school", "our lab group"),
        ("I think", "Based on what we observed, I think"),
        ("I believe", "The data suggests"),
    ]
    result = text
    for old, new in replacements:
        result = result.replace(old, new)
        result = result.replace(old.title(), new.title())
    return result


# ──────────────────────────────────────────────────────────────
# Name lists
# ──────────────────────────────────────────────────────────────

_NORMAL_NAMES = [
    "Sophia Ramirez", "Ethan Liu", "Aaliyah Johnson", "David Park",
    "Maya Patel", "Isaiah Thomas", "Olivia Chen", "Jamal Washington",
    "Emma Gonzalez", "Kai Tanaka", "Zoe Abrams", "Marcus Rivera",
    "Ava Kowalski", "Darius Hayes", "Lily Chang", "Noah Peters",
    "Priya Sharma", "Carlos Mendez", "Amara Osei",
]

_EXHAUSTION_NAMES = [
    "Ryan Mitchell", "Jasmine Lee", "Brandon Torres", "Nadia Petrov",
]

_BIO_NAMES = [
    "Sarah Kim", "James Cooper", "Alicia Moreno", "Derek Chang",
    "Nicole Rivera", "Kevin O'Brien", "Fatima Al-Hassan", "Chris Nakamura",
    "Hannah Jacobs", "Luis Fernandez", "Tanya Patel", "Matt Stevenson",
    "Diana Okafor", "Andre Williams", "Grace Lin", "Daniel Murphy",
    "Samantha Cruz", "Tyler Brown", "Aisha Mohammed", "Ryan Kowalski",
    "Jessica Nguyen", "Michael Sato", "Brittany Hall", "Omar Diaz",
    "Emily Watson",
]


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, default=0,
                        help="Run only this stage (1-4). 0 = all.")
    args = parser.parse_args()

    # Stage 1
    daigt_path = DATA_DIR / "daigt_filtered.json"
    if args.stage in (0, 1):
        filtered = stage1_filter_daigt()
    elif daigt_path.exists():
        filtered = json.loads(daigt_path.read_text())
        print(f"Loaded {len(filtered)} filtered essays from cache")
    else:
        print("ERROR: Run stage 1 first to download DAIGT data")
        sys.exit(1)

    # Stage 2
    aic_path = DATA_DIR / "daigt_aic_results.json"
    if args.stage in (0, 2):
        aic_results = stage2_run_aic(filtered)
    elif aic_path.exists():
        aic_results = json.loads(aic_path.read_text())
        print(f"Loaded {len(aic_results)} AIC results from cache")
    else:
        print("ERROR: Run stage 2 first for AIC results")
        sys.exit(1)

    # Stage 3
    qa_path = DATA_DIR / "daigt_quick_analysis.json"
    if args.stage in (0, 3):
        qa_result = stage3_quick_analysis(filtered)
    elif qa_path.exists():
        from insights.models import QuickAnalysisResult
        qa_result = QuickAnalysisResult.model_validate_json(qa_path.read_text())
        print("Loaded QuickAnalysis from cache")
    else:
        print("ERROR: Run stage 3 first for QuickAnalysis")
        sys.exit(1)

    # Stage 4
    if args.stage in (0, 4):
        ethnic_studies, biology = stage4_assemble_corpus(
            filtered, aic_results, qa_result
        )

    print("\n═══ Corpus assembly complete ═══")


if __name__ == "__main__":
    main()
