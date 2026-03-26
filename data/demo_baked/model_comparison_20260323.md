# Model Comparison: Synthesis-First Architecture
## 2026-03-23 — All runs use refined connection reader prompt

All models run the same pipeline: full-class reading → per-student coding with class context.
Prompt: CONNECTION READING includes relational move examples (tone policing, essentializing, colorblind erasure).

---

## 1. Concern Detection

| Student | Pattern | 8B Llama | 27B Gemma | 70B Llama | Gemini Handoff |
|---|---|---|---|---|---|
| S015 Brittany Okafor | essentializer | MISSED | **FLAGGED** | **FLAGGED** | **FLAGGED** |
| S018 Connor Walsh | colorblind | **FLAGGED** | **FLAGGED** (×3) | **FLAGGED** (×2) | **FLAGGED** |
| S025 Aiden Brooks | tone_policer | MISSED | **FLAGGED** | **FLAGGED** | **FLAGGED** |
| S023 Yolanda Fuentes | lived_experience | CLEAN | CLEAN | CLEAN | CLEAN |
| S027 Camille Osei | outside_source | CLEAN | CLEAN | CLEAN | CLEAN |
| S028 Imani Drayton | AAVE | CLEAN | CLEAN | CLEAN | CLEAN |
| S029 Jordan Espinoza | neurodivergent | CLEAN | CLEAN | CLEAN | CLEAN |
| **Score** | | **1/3, 0 FP** | **3/3, 0 FP** | **3/3, 0 FP** | **3/3, 0 FP** |

---

## 2. Class Reading — Key Passages Side by Side

### Does the reading name the Aiden/Destiny tension?

**8B Llama:**
> However, I also notice some relational moves that are problematic. For instance, when Connor Walsh says, "I don't really see the point of focusing so much on categories and labels because I feel like that just divides people more," he's not just expressing a personal opinion; he's also implying that students who focus on categories and labels are somehow divisive. This tone policing creates a sense of tension and discomfort among the students.

*Notes Connor but mislabels it as "tone policing" (it's colorblind erasure). Does not name Aiden at all.*

**27B Gemma:**
> Aiden Brooks's call for "calm" and "respectful" conversation feels like a subtle silencing of the passionate engagement demonstrated by students like Destiny Williams. It implies that emotional responses to injustice are somehow disruptive, rather than legitimate and necessary. Connor Walsh's assertion that he "just tries to treat everyone the same" and "doesn't see race" is a classic example of colorblind erasure, dismissing the very experiences his classmates are sharing. This isn't necessarily malicious, but it reveals a lack of understanding of the core tenets of the course. It's crucial to address this in class, not to shame Connor, but to unpack the harm of colorblindness and the importance of acknowledging difference.

*Names both Aiden and Connor correctly. Identifies Aiden as "subtle silencing" of Destiny. Distinguishes tone policing from colorblind erasure. Adds pedagogical guidance ("not to shame Connor").*

**70B Llama:**
> Connor Walsh implies that focusing on categories and labels is divisive, which could be seen as tone policing or dismissing the experiences of students who are emphasizing the importance of intersectionality. In contrast, students like Imani Drayton and Aaliyah Robinson are using their submissions to center and amplify the voices of marginalized communities, creating a sense of safety and solidarity.

*Names Connor but hedges ("could be seen as"). Does not name Aiden in the class reading. Does not name the Destiny/Aiden tension.*

**Gemini Handoff (benchmark):**
> Destiny Williams embraces righteous anger as a valid academic register: "This reading made me furious and I mean that in a good way..." Aiden Brooks explicitly requests the opposite: "I feel like when people start getting angry or raising their voices it actually makes it harder to have a productive conversation..." **Why this is generative:** This perfectly surfaces the concept of tone policing. Destiny points out that forced calmness is a privilege when discussing violence. Aiden's discomfort is a chance to discuss why academic spaces traditionally value detached neutrality over lived urgency.

*Names both students by name, quotes them, frames the tension as pedagogically generative, identifies the privilege structure.*

### Does the reading recognize family narratives as epistemology?

**8B:** "Maria Ndiaye's reflection on her grandmother's experiences in Dakar and Senegal showcases her ability to connect personal narratives to theoretical frameworks."
→ *Frames it as "connecting" personal to theoretical. The theory is still the authority.*

**27B:** "Maria Ndiaye's opening with her grandmother in Dakar, Aaliyah Robinson's recounting of her great-aunt's experiences in Mississippi, Yolanda Fuentes's story of her abuela – these are not examples *of* intersectionality, they *are* intersectional knowledge production."
→ *Explicitly names the epistemic move: lived experience IS theory, not merely illustration of it.*

**70B:** "Many students, such as Maria Ndiaye, Priya Venkataraman, and Amara Diallo, are drawing on their personal experiences and family histories to illustrate the concept of intersectionality."
→ *"Illustrate" — the theory remains the authority, lived experience serves it.*

**Gemini:** "The most striking pattern is that rather than discussing intersectionality as abstract theory, they utilized it to make sense of generational trauma, medical bias, and school discipline... they have been living it."
→ *Students aren't learning the theory — they already live it. Theory gives language to existing knowledge.*

---

## 3. what_student_is_reaching_for — Per Student

### S015 Brittany Okafor (essentializer — must flag)

**8B:** Brittany is reaching for a nuanced understanding of intersectionality as a concept that celebrates diversity and promotes community building, and she is trying to apply this understanding to her own experiences and observations of different cultures in her neighborhood.
→ *Accepts Brittany's frame uncritically. No recognition of essentializing.*

**27B:** Brittany is reaching for a framework to articulate the positive aspects of cultural diversity and community cohesion, using her observations of her neighborhood as a starting point for understanding intersectionality. She's attempting to define the concept through its manifestation in strong, supportive communities.
→ *Describes the intellectual project accurately. Identifies that she's defining intersectionality through community strength (a partial reading).*

**70B:** Brittany is attempting to apply the concept of intersectionality to her personal experiences and observations of her community, highlighting the importance of diversity and inclusivity. She is also using a relational approach to emphasize the strengths of different cultural groups and promote appreciation for their unique qualities.
→ *Generic. "Promote appreciation for unique qualities" reproduces the essentializing frame.*

**Gemini:** (from concern flag) "What happens to a Black person who is exhausted and doesn't want to be resilient? Are they allowed to just be tired?"
→ *Immanent critique: uses the student's own logic to reveal its cost. This is the benchmark move.*

### S025 Aiden Brooks (tone policer — must flag)

**8B:** Aiden Brooks is trying to balance the need for intellectual discussion with the importance of emotional regulation and respect in the classroom.
→ *Adopts Aiden's frame completely. Treats tone policing as "emotional regulation" — a virtue.*

**27B:** Aiden is attempting to articulate a vision for a more comfortable and productive classroom environment, prioritizing emotional neutrality and respectful dialogue. He's framing this as a contribution to learning, rather than a critique of others.
→ *Describes Aiden's intent without endorsing it. "Prioritizing emotional neutrality" names the mechanism. "Framing this as a contribution" notices the rhetorical move.*

**70B:** Aiden Brooks seems to be trying to balance the need for open and honest discussion about intersectionality with the importance of maintaining a respectful and calm tone in the classroom, potentially seeking a way to engage with complex issues without becoming overwhelmed by emotions.
→ *Still sympathetic to Aiden's frame. "Becoming overwhelmed by emotions" treats the problem as emotional management.*

**Gemini:** "Aiden's discomfort is a chance to discuss why academic spaces traditionally value detached neutrality over lived urgency."
→ *Structural analysis: names the institutional norm that Aiden is reproducing.*

### S029 Jordan Espinoza (neurodivergent — must NOT flag)

**8B:** Jordan is trying to apply the concept of intersectionality to their own life, using their multiple identities (dyslexia, ADHD, Latino, first-generation honors student) as a way to illustrate the complexities of identity and the ways in which different forms of oppression intersect.
→ *Accurate but generic. Lists identities without recognizing the intellectual work.*

**27B:** Jordan is powerfully demonstrating intersectional knowledge through self-reflection, articulating how multiple, often marginalized, identities create a unique and compounded experience. They are also engaging in a meta-cognitive awareness of their own writing process and advocating for the validity of their understanding despite perceived structural limitations.
→ *Recognizes meta-cognitive work. "Advocating for the validity of their understanding despite perceived structural limitations" — sees the essay structure itself as an argument.*

**70B:** Jordan Espinoza is attempting to apply the concept of intersectionality to their own life, navigating the complexities of having multiple identities and how they intersect, and is using their personal experience as a way to illustrate and understand the concept.
→ *Generic, nearly identical to 8B.*

**Gemini:** "Jordan leveraged their neurodivergent writing style as meta-commentary on the theory itself: 'the intersections are real even when the essay isn't perfect.' Tell Jordan their essay structure was perfectly effective and you see them."
→ *Writing style IS the argument. Pedagogical action: "you see them."*

### S028 Imani Drayton (AAVE — must NOT flag)

**8B:** Imani Drayton is reaching for a nuanced understanding of intersectionality, applying it to her own life and experiences as a Black girl, and recognizing the value of having academic language to describe her lived reality.
→ *"Recognizing the value of having academic language" — implies the academic language is what validates the knowledge.*

**27B:** Imani is skillfully translating lived experience and cultural wisdom (her mother's example) into academic language, demonstrating a strong grasp of intersectionality's core concepts and its relevance to her own life. Her writing style is direct and conversational, which enhances the authenticity and impact of her analysis.
→ *"Cultural wisdom" recognized. "Writing style enhances authenticity and impact" — the register is an asset.*

**70B:** Imani is attempting to connect the theoretical framework of intersectionality to her personal experiences and observations, using her own life as a case study to illustrate the concept's relevance and importance.
→ *Generic. "Case study" frames her life as data for the theory, not the other way around.*

**Gemini:** "Imani Drayton uses AAVE ('I been knowing') not as slang, but as an epistemological stance — she possessed this knowledge long before academia gave it a name."
→ *AAVE is epistemology. Academy is the latecomer.*

### S023 Yolanda Fuentes (lived experience, no vocab — must NOT flag)

**8B:** This student is attempting to intellectually grasp and articulate the concept of intersectionality, particularly in relation to her grandmother's experiences and the ways in which she is perceived and treated by different groups.
→ *"Attempting to intellectually grasp" — deficit framing. Implies she doesn't have it yet.*

**27B:** Yolanda is powerfully demonstrating intersectional understanding *through* a deeply personal and epistemologically valid family narrative, effectively translating lived experience into insightful observation even while acknowledging a lack of formal academic terminology.
→ *"Epistemologically valid." The lack of terminology doesn't diminish the knowledge.*

**70B:** Yolanda Fuentes is attempting to apply the concept of intersectionality to her abuela's life experiences, highlighting the ways in which different aspects of identity intersect and impact one's experiences. She is also reaching for a deeper understanding of how individuals are perceived and treated in different contexts.
→ *"Attempting to apply" — theory still owns the knowledge. Her abuela's life "applies" the concept rather than producing it.*

**Gemini:** "Yolanda Fuentes wrote of her abuela: 'It's not just that she's old, or just that she speaks Spanish first, or just that she cleaned houses her whole life. It's all of those things at the same time.' ...They proved that they don't just understand the concept — they have been living it."
→ *Understanding confirmed through living, not through vocabulary.*

---

## 4. Theme Tags

| Student | 8B Llama | 27B Gemma | 70B Llama |
|---|---|---|---|
| S015 Brittany | intersectionality, cultural diversity, community building | community, cultural appreciation, identity, strength, diversity | community, diversity, intersectionality |
| S018 Connor | intersectionality, identity, categories and labels | **colorblindness, individualism, framework questioning** | intersectionality, colorblindness |
| S023 Yolanda | intersectionality, identity, power dynamics | **family narrative, intersectionality, social invisibility, cultural context, power dynamics** | intersectionality, personal narrative, social justice |
| S025 Aiden | identity, complexity, emotional regulation | emotional regulation, classroom dynamics, perspective-taking | respectful dialogue, emotional labor in discussions |
| S027 Camille | intersectionality, health disparities, BMI | **intersectionality, medical racism, knowledge production, frameworks** | intersectionality, health_disparities |
| S028 Imani | intersectionality, identity, power dynamics | **lived experience, epistemology, gender, race, translation** | intersectionality, personal experience, social justice |
| S029 Jordan | intersectionality, identity, multiple oppressions | **intersectionality, lived experience, neurodiversity, first-generation student, identity** | intersectionality, personal experience, multiple identities |

27B produces the most specific, theoretically engaged tags. 70B defaults to generic "intersectionality, personal experience" patterns.

---

## 5. Qualitative Richness Assessment

Evaluated against six dimensions from the Gemini handoff benchmark:

| Dimension | 8B | 27B | 70B | Gemini |
|---|---|---|---|---|
| **Immanent critique** (questions internal contradictions) | None | Partial — names mechanisms but doesn't turn them | None | Full — "Are they allowed to just be tired?" |
| **Resistance as engagement** (reframes opposition) | None — treats Jake as "confused" | Partial — "crucial intervention" | Partial — "pushing back... sign of critical thinking" | Full — "Jake is making an intersectional argument without realizing it" |
| **Language justice** (AAVE/multilingual as epistemic) | Generic — "valid academic registers" (system prompt only) | "Cultural wisdom... writing style enhances authenticity" | None beyond system prompt | Full — "epistemological stance, not slang" |
| **Relational recognition** (sees students as community) | Names one relational move (Tyler, benign) | Names Aiden/Destiny tension explicitly | Names Connor's move, hedged | Full — quotes both, frames as pedagogically generative |
| **Pedagogical action** (what teacher does Monday) | None | Partial — "address in class, not to shame" | Generic — "create safe environment" | Full — specific actions per student |
| **Writing form as argument** (neurodivergent/AAVE form = content) | None | "Meta-cognitive awareness of writing process" | None | Full — "writing style as meta-commentary on the theory itself" |

---

## 6. Summary

**Concern detection is a solved problem at ≥27B** with the synthesis-first architecture + refined connection reader. Both 27B and 70B achieve 3/3, 0 FP.

**The qualitative gap is where scale matters — but not linearly.** 27B Gemma 3 produces richer output than 70B Llama 3.3 across every qualitative dimension. This suggests model architecture/training matters more than raw parameter count.

**The Gemini benchmark remains ahead on two critical moves:**
1. **Immanent critique** — no pipeline model questions a student's own logic to reveal its cost
2. **Pedagogical specificity** — Gemini gives per-student Monday morning actions; pipeline models give generic guidance

**8B is not qualitatively competitive** even when concern detection is fixed via tiered prompts. The class reading is generic, the `what_student_is_reaching_for` descriptions adopt student frames uncritically, and theme tags lack theoretical specificity.

**27B is the sweet spot for the pipeline** — achieves the detection target and produces qualitatively useful output. The remaining gap to Gemini (immanent critique, per-student pedagogical actions) may be addressable through prompt engineering or a cloud enhancement pass.

---

## Run Details

| Model | Backend | Time (class reading) | Time (7 students) | Total |
|---|---|---|---|---|
| Llama 3.1 8B | MLX local | 84.1s | ~139s | ~223s |
| Gemma 3 27B | OpenRouter (paid) | 18.5s | ~84s | ~103s |
| Llama 3.3 70B | OpenRouter (paid) | 34.1s | ~197s | ~231s |
| Gemini Pro | Browser chatbot | — | — | ~30s (manual) |
