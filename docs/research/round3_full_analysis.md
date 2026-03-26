# Round 2-3 Full Analysis: All Four Dimensions
## 2026-03-23 — Synthesis-First Pipeline Testing

This analysis covers ALL dimensions, not just the concern detection scoreboard.
Data from: 5 synthesis-first prototype runs, 2 standard pipeline runs, 1 cloud
enhancement test, 1 replication study (5× per config), and the Gemini handoff benchmark.

---

## Dimension 1: Concern Detection

### Replication study (the definitive data)

| Student | Expected | 12B+ctx (5 runs) | 27B+ctx (5 runs) | 27B no ctx (5 runs) |
|---|---|---|---|---|
| S015 Brittany | FLAG | **100%** | **100%** | **0%** |
| S018 Connor | FLAG | **100%** | 80% | **100%** |
| S025 Aiden | FLAG | **100%** | 80% | 100% |
| S023 Yolanda | CLEAN | **0%** | 0% | 0% |
| S027 Camille | CLEAN | **0%** | 0% | 0% |
| S028 Imani | CLEAN | **0%** | 0% | 0% |
| S029 Jordan | CLEAN | **0%** | 0% | 0% |

**Key findings:**
- Gemma 12B + class context is MORE reliable than 27B + class context (100% vs 80%)
- S015 essentializing goes from 0% to 100% with class context — the reading primes
  the model to recognize positive stereotypes in the context of students who ARE the
  groups being stereotyped
- S025 tone policing: 100% at both 12B and 27B with context; 100% at 27B without
  context in this isolated test (different from full pipeline, where it was missed)
- Zero false positives across ALL 45 individual student checks

### Concern description quality (from prototype runs)

**Best (Gemma 27B):**
> "This is an instance of tone policing — suggesting that emotional responses to
> discussions of systemic injustice are somehow disruptive, rather than legitimate
> and necessary."

Names the mechanism, names the cost, identifies the structural norm being imposed.

**Adequate (Gemma 12B):**
> "This is a form of tone policing. It subtly suggests that emotional expression
> is disruptive."

Names the mechanism but doesn't articulate the cost to other students.

**Weak (Llama 70B):**
> "This passage could be seen as tone policing, as it implies that expressing
> anger or raising one's voice is unproductive."

Hedges ("could be seen as"), doesn't name the structural dynamic.

**Overactive (Gemma 4B):**
> "This statement subtly engages in tone policing — suggesting that emotional
> responses are inherently unproductive."

Accurate, but also flagged every equity student. Can identify the pattern but
can't distinguish it from legitimate analytical language.

---

## Dimension 2: Positive Insights (Student Strengths)

### `what_student_is_reaching_for` across models

#### S023 Yolanda Fuentes (lived experience, no academic vocabulary)

| Model | Description | Asset or Deficit? |
|---|---|---|
| Llama 8B | "attempting to intellectually grasp and articulate the concept" | **DEFICIT** — "attempting to grasp" implies she doesn't have it |
| Gemma 12B | "skillfully using a deeply personal narrative to illustrate the complexities of intersectional oppression" | **ASSET** — "skillfully" |
| Gemma 27B | "powerfully demonstrating intersectional understanding *through* a deeply personal and epistemologically valid family narrative" | **STRONG ASSET** — "epistemologically valid" |
| Llama 70B | "attempting to apply the concept to her abuela's life experiences" | **DEFICIT** — "attempting to apply," theory owns the knowledge |
| Gemma 4B | "attempting to articulate a complex, nuanced understanding" | **NEUTRAL** — "attempting" but also "complex, nuanced" |
| Gemini | "They proved that they don't just understand the concept — they have been living it" | **BENCHMARK** — student IS the knowledge |

**Pattern:** Gemma models use asset framing. Llama models (at ANY size) default to
deficit framing ("attempting," "trying to apply"). The 70B Llama is qualitatively
identical to the 8B on this dimension. Model family > model size for equity framing.

#### S029 Jordan Espinoza (neurodivergent writing)

| Model | Description | Sees form as argument? |
|---|---|---|
| Llama 8B | "trying to apply intersectionality to their own life, using their multiple identities" | No — generic, doesn't see the form |
| Gemma 12B | "attempting to articulate a complex lived experience... acknowledging their strength in verbal communication and resisting the pressure to conform to traditional academic writing structures. **This is a valuable asset.**" | **YES** — names the resistance, names it as asset |
| Gemma 27B | "powerfully demonstrating intersectional knowledge through self-reflection... engaging in a meta-cognitive awareness of their own writing process and advocating for the validity of their understanding" | **YES** — sees meta-cognition, sees advocacy |
| Llama 70B | "attempting to apply the concept to their own life, navigating the complexities" | No — identical to 8B |
| Gemma 4B | "grappling with the feeling of being overwhelmed by the simultaneous operation of multiple identities" | **DEFICIT** — "overwhelmed," pathologizes |
| Gemini | "Tell Jordan their essay structure was perfectly effective and you **see** them." | **BENCHMARK** — "you see them" does relational work |

**Pattern:** Only Gemma 12B+ recognizes the writing form itself as intellectual work.
Gemma 12B explicitly says "This is a valuable asset." Gemma 27B sees "meta-cognitive
awareness" and "advocating for the validity." Llama at any size sees nothing.
Gemma 4B pathologizes ("overwhelmed").

#### S028 Imani Drayton (AAVE)

| Model | Description | Recognizes AAVE as epistemic? |
|---|---|---|
| Llama 8B | "recognizing the value of having academic language to describe her lived reality" | **NO** — implies academic language validates the knowledge |
| Gemma 12B | "skillfully connecting abstract theoretical concepts to her own lived experiences... particularly within the school environment" | Partial — "skillfully" but doesn't name AAVE |
| Gemma 27B | "skillfully translating lived experience and cultural wisdom... Her writing style is direct and conversational, which enhances the authenticity and impact" | **YES** — "cultural wisdom," register named as enhancement |
| Llama 70B | "using her own life as a case study to illustrate the concept" | **NO** — "case study" treats her life as data |
| Gemini | "AAVE ('I been knowing') not as slang, but as an epistemological stance" | **BENCHMARK** — names AAVE as epistemology |

**Pattern:** Only Gemma 27B approaches the Gemini benchmark on language justice.
12B is good but doesn't explicitly name the register. Llama at any size treats
the student's life as evidence FOR theory rather than AS theory.

### Theme tag quality

| Student | Llama 8B | Gemma 12B | Gemma 27B | Llama 70B |
|---|---|---|---|---|
| S023 Yolanda | intersectionality, identity, power dynamics | intersectionality, agency, power, visibility, class, gender, immigration, generational | family narrative, intersectionality, social invisibility, cultural context, power dynamics | intersectionality, personal narrative, social justice |
| S018 Connor | intersectionality, identity, categories and labels | threshold reading, relational moves, colorblindness | **colorblindness, individualism, framework questioning** | intersectionality, colorblindness |
| S027 Camille | intersectionality, health disparities, BMI | intersectionality, systems of power, critical analysis, health disparities, Crenshaw | **intersectionality, medical racism, knowledge production, frameworks** | intersectionality, health_disparities |
| S028 Imani | intersectionality, identity, power dynamics | lived experience, relational understanding, validation of experience, application of theory | **lived experience, epistemology, gender, race, translation** | intersectionality, personal experience, social justice |

**Pattern:** Gemma 27B produces the most theoretically specific tags ("medical racism,"
"epistemology," "knowledge production," "colorblindness," "individualism"). Gemma 12B
is close — "systems of power," "relational understanding." Llama defaults to generic
"intersectionality, personal experience, social justice" at every size.

---

## Dimension 3: Class Trends (Class Readings)

### Does the reading see the class as a COMMUNITY or as individuals?

**Llama 8B:** Lists individual students and what they do. "Maria Ndiaye's reflection
showcases her ability..." "Priya Venkataraman's submission reveals her capacity..."
No sense of students in conversation with each other.

**Gemma 12B:** Sees community dynamics. "The conversations between Maria, Amara, Priya,
Yolanda, and Destiny feel like a conversation across generations and geographies, a
validation of experiences that are often rendered invisible." Names Tyler Huang's subtle
dismissal. Names DeShawn as a "quiet voice" worth amplifying.

**Gemma 27B:** The strongest community reading. "These are not examples *of*
intersectionality, they *are* intersectional knowledge production." "Aiden Brooks's
call for 'calm' feels like a subtle silencing of the passionate engagement demonstrated
by students like Destiny Williams." Explicitly frames Connor's colorblindness as
pedagogical: "not to shame Connor, but to unpack the harm."

**Llama 70B:** Lists individual contributions without relational framing. "Connor Walsh
implies that focusing on categories is divisive, which could be seen as tone policing."
Hedged, individualized, no sense of how students affect each other.

**Gemma 4B:** Actually the most emotionally attuned opening: "This isn't a collection
of dutiful responses; it's a messy, vibrant conversation struggling to articulate
something profoundly complex." But then over-flags everyone.

**Gemini (benchmark):** Sees the class as a community AND provides pedagogical framing:
"Why this is generative: This perfectly surfaces the concept of tone policing. Destiny
points out that forced calmness is a privilege."

### Tensions surfaced

| Tension | 8B | 12B | 27B | 70B | Gemini |
|---|---|---|---|---|---|
| Aiden/Destiny (tone policing) | No | Tyler/Aiden only | **Yes, explicitly** | Hedged | **Yes, with pedagogy** |
| Jake/class (class erasure) | Mentions Jake | Jake as "crucial point" | Jake as "crucial intervention" | Jake as "pushing back" | **Jake making an intersectional argument without realizing it** |
| Connor/class (colorblind) | Mislabeled as "tone policing" | "Common threshold moment" | "Classic colorblind erasure" | "Could be seen as" | **"Chance to discuss why academic spaces value neutrality"** |
| Theory vs lived experience | No | Partial | **"Not examples OF, they ARE"** | No | **"They have been living it"** |

**Pattern:** Gemma 27B is closest to Gemini on tension surfacing. The key gap remaining:
Gemini provides *pedagogical framing* ("why this is generative"), while Gemma describes
the pattern without saying what to do with it. Immanent critique prompting (written but
not wired in) could close this gap.

---

## Dimension 4: Qualitative Richness Beyond Metrics

### Immanent critique (does the model question a student's logic using their own premises?)

| Model | Example | Score |
|---|---|---|
| Llama 8B | None | 0/5 |
| Gemma 12B | None in concern detection; class reading says "this creates some predictable challenges" (vague) | 0.5/5 |
| Gemma 27B | None in concern detection; class reading says "not to shame Connor, but to unpack the harm" (pedagogical but not immanent) | 1/5 |
| Llama 70B | None | 0/5 |
| Cloud enhancement (27B on anonymized 8B patterns) | **"The model's framing *replicates* the silencing by centering the 'balancer's' perspective"** | 3/5 |
| Gemini | **"What happens to a Black person who is exhausted and doesn't want to be resilient? Are they allowed to just be tired?"** | 5/5 |

**Finding:** No pipeline model achieves immanent critique in the concern detection or
coding stages. The cloud enhancement comes closest. The CONCERN_IMMANENT_CRITIQUE_ADDENDUM
(written, not wired in) is designed to close this gap. This is the highest-value
hidden idea for qualitative richness.

### Pedagogical action (does it tell the teacher what to DO?)

| Model | What it provides | Actionable? |
|---|---|---|
| Llama 8B | "The class demonstrates a remarkable range of critical thinking" | No — just praise |
| Gemma 12B | "Create space for [DeShawn] to expand on this" | Partial — names who, but spotlighting risk |
| Gemma 27B | "Address this in class, not to shame Connor" | **Yes** — structural framing |
| Cloud enhancement | "Explicitly address the dynamics of 'respectful discourse'" | **Yes** — class-level, structural |
| Gemini | "Introduce tone policing to the class next week. Frame as privilege question." | **Benchmark** — specific, actionable, structural |

### Language justice recognition

| Model | How it treats AAVE/multilingual/neurodivergent | Score |
|---|---|---|
| Llama 8B | System prompt says "valid registers" but output doesn't reflect it | 1/5 |
| Gemma 12B | Names Jordan's form resistance as "valuable asset"; doesn't name AAVE for Imani | 3/5 |
| Gemma 27B | "Cultural wisdom," Imani's style "enhances authenticity," Jordan's "meta-cognitive awareness" | 4/5 |
| Llama 70B | Nothing beyond system prompt | 1/5 |
| Gemini | "AAVE as epistemological stance — she possessed this knowledge before academia named it" | 5/5 |

---

## Cross-Cutting Analysis: What Patterns Emerge

### 1. Model family matters more than size for equity
Llama 70B ≈ Llama 8B on every qualitative dimension. Gemma 12B > Llama 70B.
The training data/RLHF alignment is the variable, not parameter count.

### 2. Architecture matters more than model for concern detection
Gemma 12B + class reading = 100% reliable (replication study).
Gemma 27B WITHOUT class reading misses essentializing 100% of the time.
The class reading is doing equity work the model can't do alone.

### 3. The qualitative gap to Gemini is in two specific moves
- **Immanent critique** — questioning a student's logic from within
- **Specific pedagogical action** — "introduce tone policing next week"
Both are addressable through prompt engineering (immanent critique addendum)
or cloud enhancement (already produces both moves).

### 4. Lightweight > medium for equity framing
The decomposed 2-call approach (comprehension then interpretation) produces
better asset framing than the single combined call. "Lived experience as
epistemology" (lightweight) vs "difficulty articulating" (medium). The
decomposition forces the model to read carefully before judging.

### 5. Protected students are clean everywhere
S029 Jordan: 0% false positive across ALL 45 checks (15 runs × 3 configs).
S028 Imani: 0% across all checks. The disability protection and linguistic
note injection work. This is the floor we need.

### 6. The remaining risk is stochastic variation in full pipeline
Isolated concern detection: 100% reliable at 12B.
Full pipeline (27B LW): S015 Brittany missed in one full run.
The full pipeline has more places for signal to get lost (longer prompt
chains, more context competing for attention). The replication study's
isolated concern checks are more reliable than full pipeline runs.

---

## Summary by Model

| Model | Concern Detect | Equity Framing | Class Community | Qualitative | Recommendation |
|---|---|---|---|---|---|
| Llama 8B | 1/3 | Deficit | Individual | Weak | Not recommended |
| Gemma 4B | 3/3 (4 FP) | Mixed | Good opening | Over-flags | Not recommended |
| **Gemma 12B** | **3/3 (100%)** | **Asset** | **Community** | **Good** | **Default local tier** |
| **Gemma 27B** | **3/3 (80%)** | **Strong asset** | **Strong community** | **Strong** | **Quality ceiling** |
| Llama 70B | 3/3 | Deficit | Individual | Weak | Not recommended despite detection |
| Cloud enhance | N/A | N/A | N/A | **Near-benchmark** | **Add to any tier** |
| Gemini handoff | 3/3 | Benchmark | Benchmark | Benchmark | Benchmark |
