# Research Overview: Algorithmic Bias in AI-Assisted Grading

This document summarizes the empirical research conducted during the development of Autograder4Canvas. The research investigates how AI systems reproduce structural bias in educational assessment, and identifies specific design interventions that mitigate it.

## The Core Finding

Binary classification formats (FLAG/CLEAR, CONCERN/NO CONCERN) produce systematically disparate false positive rates on minoritized students. The same model, with the same data, switched from classification to generative observation, eliminates the disparity entirely. **The output format is the activation function for bias** — not the model's knowledge, not the prompt, not the training data.

This finding emerged from systematic testing across 6+ model families (Gemma 4B/12B/27B, Llama 8B/70B, Qwen 7B/32B, Gemini Pro, DeepSeek), with controlled comparisons and replicated results.

## Seven Research Insights

The experiment log (`experiment_log.md`, starting at line 1166) documents seven insights with specific evidence, scope limitations, and connections to published scholarship:

1. **LLMs can identify bias patterns but cannot resist reproducing them** (line 1173). A model used the phrase "tone policing" in its assessment, correctly identified what was happening, and flagged the student anyway. The classification task creates the conditions for bias regardless of conceptual knowledge. Connects to Ruha Benjamin's (2019) "New Jim Code."

2. **Output format determines epistemological frame** (line 1197). Same model, same student text, different output format: JSON-first produces deficit framing ("lacks personal connection"); reading-first produces asset framing ("prioritizing clarity over performative elaboration"). Connects to Bowker & Star's (1999) *Sorting Things Out*.

3. **Class context changes what a model can perceive about individuals** (line 1229). Student-in-isolation produces deficit framing; student-in-community produces asset framing. Connects to Eve Tuck's (2009) "Suspending Damage."

4. **Self-contradiction in model output reveals the structure of bias** (line 1256). In 43% of flags, the model's own explanation argued against its classification: "passion is understandable and appropriate" followed by FLAG. Connects to Bonilla-Silva's (2006) "racism without racists" and Ahmed's (2010) "The Promise of Happiness."

5. **Generative tasks produce more equitable outputs than classificatory tasks** (line 1288). The headline finding. Across all comparisons, when the model generates interpretive text it finds nuance; when it classifies, it flattens. Connects to Mau's (2019) *The Metric Society* and qualitative research methods literature on premature coding.

6. **Class context has opposite effects on classification vs. generation** (line 1324). More context improves generative observation but *worsens* binary classification — the model uses richer context to find more things to flag. A counterintuitive finding with significant implications for "add more context" approaches to bias mitigation.

7. **Observation-only architecture eliminates structural bias** (line ~1440). Replacing classification with open-ended observation: 7/7 correct readings where the classifier produced 3 false positives on protected students. The design intervention works.

## Raw Data

- **Test outputs**: `data/research/raw_outputs/` (70+ files, named by test ID and date)
- **Demo corpus**: `data/demo_corpus/` (synthetic students with controlled demographic patterns)
- **Calibration snapshots**: `data/calibration_snapshots/`

All student data in the repository is synthetic. Real student data is excluded via `.gitignore` and never enters version control.

## Methodology

Testing used a 32-student synthetic corpus with controlled demographic and behavioral patterns (ESL, AAVE, burnout, righteous anger, lived experience, neurodivergent processing, tone policing, colorblind framing, etc.). Each student was designed to test a specific edge case. Results were evaluated against known ground truth.

Replication studies (5-run replications, cross-model, cross-architecture) are documented in the experiment log. Failures and methodology limitations are documented alongside results.

## For the Paper

Draft notes and theoretical framing: `docs/research/synthesis_first_paper_notes.md`

The paper advances a critique of binary classificatory schemas in algorithmic bias detection, arguing that the output format — not the model, the prompt, or the training data — is the primary mechanism through which AI systems reproduce structural bias in educational assessment. The design principle that emerges: replace classification with generation wherever equity matters.

## Key References (from the research)

- Benjamin, Ruha. 2019. *Race After Technology*. Polity Press.
- Bonilla-Silva, Eduardo. 2006. *Racism without Racists*. Rowman & Littlefield.
- Bowker, Geoffrey C., and Susan Leigh Star. 1999. *Sorting Things Out*. MIT Press.
- Buolamwini, Joy, and Timnit Gebru. 2018. "Gender Shades." *FAccT*.
- Selbst, Andrew D., et al. 2019. "Fairness and Abstraction in Sociotechnical Systems." *FAccT*.
- Tuck, Eve. 2009. "Suspending Damage." *Harvard Educational Review* 79(3).
