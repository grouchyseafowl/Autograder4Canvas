"""
AICInfoDialog — "How does the Academic Integrity Check work?"

Explains markers, ethical framing, smoking gun detection, burnout signals,
and population profiles.  Opens from the Prior Runs panel and the run dialogs.
Read-only, scrollable — just close when done.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from gui.styles import (
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    ROSE_ACCENT, ROSE_DIM, TERM_GREEN, WARN_PINK,
    BG_VOID, BG_CARD, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    CARD_GRADIENT, MONO_FONT,
    make_secondary_button,
)


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
_SECTIONS = [
    {
        "heading": "What this tool does — and what it doesn't",
        "accent": PHOSPHOR_HOT,
        "body": (
            "The Academic Integrity Check (AIC) analyzes text submissions for "
            "patterns statistically associated with AI-generated writing. It does "
            "NOT prove cheating. It produces a suspicion score, an authenticity "
            "score, and a concern level — all of which are starting points for "
            "a conversation with the student, not verdicts.\n\n"
            "Every flag should be reviewed by the instructor before any action "
            "is taken. Context always matters more than scores."
        ),
    },
    {
        "heading": "Ethical framing — read this first",
        "accent": ROSE_ACCENT,
        "body": (
            "This tool was designed for community college populations that include "
            "ESL learners, first-generation students, neurodivergent writers, and "
            "non-traditional students returning after years away. Many writing "
            "patterns that superficially resemble AI output are also signatures of "
            "these student populations.\n\n"
            "The AIC applies automatic score reductions when ESL error patterns are "
            "detected (article errors, tense mixing) because AI models don't make "
            "those mistakes. Use the population profile selectors in the Prior Runs "
            "panel to recalibrate displayed scores for individual students.\n\n"
            "A high suspicion score means: have a curious conversation. It never "
            "means: take disciplinary action without further investigation."
        ),
    },
    {
        "heading": "Suspicion markers (raises score)",
        "accent": WARN_PINK,
        "body": (
            "These patterns appear more often in AI-generated text than in authentic "
            "student writing. Each match contributes to the suspicion score.\n\n"
            "  INFLATED VOCABULARY\n"
            "    Words and phrases that are technically correct but uncommon in spoken "
            "    academic discourse — 'furthermore', 'it is worth noting', 'in the "
            "    realm of'.\n\n"
            "  AI TRANSITION PHRASES\n"
            "    Connectives characteristic of ChatGPT-style output — 'In conclusion, "
            "    it is clear that', 'This essay has explored', 'Delving into'.\n\n"
            "  GENERIC SUMMARIZING PHRASES\n"
            "    Vague closers or openers with no specific content — 'This topic is "
            "    both complex and multifaceted', 'There are many perspectives'.\n\n"
            "  BALANCE MARKERS\n"
            "    Symmetric 'on one hand / on the other hand' framing when the "
            "    assignment calls for a position or personal reflection.\n\n"
            "  AI-SPECIFIC ORGANIZATION\n"
            "    Structurally uniform sections, excessive headings, perfectly balanced "
            "    paragraph lengths — document structures that emerge from AI generation "
            "    but are unusual in human prose."
        ),
    },
    {
        "heading": "Authenticity markers (lowers suspicion)",
        "accent": TERM_GREEN,
        "body": (
            "These patterns are strong signals of human authorship. Each match "
            "reduces or offsets the suspicion score.\n\n"
            "  PERSONAL VOICE\n"
            "    First-person references to specific lived experience, named people, "
            "    or places — 'My grandmother told me', 'When I worked at'.\n\n"
            "  COGNITIVE STRUGGLE\n"
            "    Visible thinking-in-progress: hedges, self-corrections, explicit "
            "    uncertainty — 'I'm not sure but', 'I keep going back to'.\n\n"
            "  CONTEXTUAL GROUNDING\n"
            "    References to specific class readings, discussions, or course "
            "    events — signals the student is responding to this class, not "
            "    generating a generic essay.\n\n"
            "  EMOTIONAL STAKES\n"
            "    Expressions of genuine feeling about the material — not performed "
            "    sentiment, but specific reactions tied to content.\n\n"
            "  PRODUCTIVE MESSINESS\n"
            "    Sentence fragments, run-ons, parenthetical asides, unusual "
            "    punctuation — the natural texture of a person thinking in writing.\n\n"
            "  ESL PATTERNS\n"
            "    Article errors ('I go to university'), tense mixing, or non-native "
            "    preposition use. AI models virtually never produce these. Their "
            "    presence is strong evidence of human authorship and triggers an "
            "    automatic 40% reduction in the suspicion score."
        ),
    },
    {
        "heading": "Smoking gun — chatbot paste artifacts",
        "accent": ROSE_ACCENT,
        "body": (
            "A 'smoking gun' is different from a high suspicion score. It means "
            "physical evidence of a chatbot copy-paste was found in the raw submission "
            "before HTML cleaning.\n\n"
            "THREE SCENARIOS ARE DETECTED:\n\n"
            "  1. STRUCTURAL HTML\n"
            "     Canvas submissions normally contain only <p> tags. If a submission "
            "     contains <h2>/<h3> section headers, <ul>/<li> bullet lists, or "
            "     <strong> tags used as section titles, the text was generated as a "
            "     document outside Canvas and pasted in.\n\n"
            "  2. RAW HTML SOURCE\n"
            "     Some students copy the raw HTML output from a chatbot. Canvas "
            "     stores this as HTML-encoded text (&lt;div&gt; appearing literally). "
            "     This is unambiguous — the student copied source code.\n\n"
            "  3. UNPROCESSED MARKDOWN\n"
            "     ChatGPT and similar tools often respond in Markdown. If the student "
            "     pastes that directly into Canvas, **bold** syntax, ## headers, and "
            "     - bullet lists appear as literal characters in the submission.\n\n"
            "A smoking gun forces the concern level to HIGH regardless of other "
            "scores. It is shown with a distinct rose-glow border in the Prior Runs "
            "panel — separate from 'high concern' submissions that only have elevated "
            "pattern scores."
        ),
    },
    {
        "heading": "Peer comparison and outlier detection",
        "accent": PHOSPHOR_MID,
        "body": (
            "After analyzing all submissions in a run, the AIC computes cohort "
            "statistics and identifies statistical outliers. A student who scores at "
            "the 95th percentile or above within their own class is flagged as an "
            "outlier — even if their absolute suspicious score is low.\n\n"
            "This is intentional: a class where everyone writes authentically may "
            "still have one student who stands out. Peer comparison catches that "
            "without setting arbitrary global thresholds that disadvantage students "
            "at schools where authentic writing is the norm."
        ),
    },
    {
        "heading": "Population profiles and score re-weighting",
        "accent": PHOSPHOR_MID,
        "body": (
            "In the Prior Runs panel, you can apply a population profile to a "
            "student. This recalculates their displayed scores using standardized "
            "multipliers — it does NOT re-run the analysis or change the stored data.\n\n"
            "Available profiles:\n\n"
            "  COMMUNITY COLLEGE  — default; 30% more lenient across the board\n"
            "  ESL                — stronger reduction on vocabulary and organization "
            "markers (patterns ESL writers share with AI output)\n"
            "  NEURODIVERGENT     — reduces weight on organizational uniformity and "
            "structure-based markers\n"
            "  FIRST-GEN          — moderate reduction; first-gen writers often use "
            "formal register to code-switch into academic voice\n"
            "  STANDARD           — no adjustment\n\n"
            "When a profile override is active, the panel displays 'Scores "
            "recalculated with [Profile] profile' prominently. This transparency "
            "protects both the teacher and the student if the analysis is ever "
            "reviewed."
        ),
    },
    {
        "heading": "Burnout signals — not suspicion",
        "accent": WARN_PINK,
        "body": (
            "The student trajectory view shows patterns over the semester. Some "
            "patterns that look suspicious in isolation are actually burnout signals:\n\n"
            "  DECLINING WORD COUNT\n"
            "    A student who submitted 600 words in Week 2 and 180 words in "
            "    Week 10 may be overwhelmed, not cheating. Prompt a check-in "
            "    conversation — not an integrity conversation.\n\n"
            "  LATE-NIGHT SUBMISSION TIMING\n"
            "    Submissions timestamped after midnight, clustered near deadlines. "
            "    Students working multiple jobs submit when they can. The trajectory "
            "    panel labels these as 'submission timing' data, not a red flag.\n\n"
            "If you see a student's suspicion score rise while their word count "
            "drops and their submissions shift to late-night, that pattern as a "
            "whole is more consistent with stress-driven AI use than calculated "
            "academic dishonesty. The conversation that follows should reflect that."
        ),
    },
    {
        "heading": "What the tool cannot detect",
        "accent": PHOSPHOR_DIM,
        "body": (
            "  - Paraphrased AI output that has been edited to sound human\n"
            "  - AI use on assignments that involve factual lookup or summarization "
            "(where AI output and human output may be genuinely similar)\n"
            "  - Students who use AI as a brainstorming aid and then write in their "
            "own voice\n"
            "  - Students whose natural writing style overlaps with AI patterns "
            "(highly formal, well-organized, vocabulary-rich writers)\n\n"
            "The AIC is strongest at catching copy-paste laziness (smoking guns) "
            "and class-wide statistical outliers. It is weakest at distinguishing "
            "sophisticated AI use from authentic formal writing. Use it as one data "
            "point among many."
        ),
    },
]


# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class AICInfoDialog(QDialog):
    """Read-only explainer for how the Academic Integrity Check works."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("How the Academic Integrity Check Works")
        self.setMinimumSize(680, 560)
        self.resize(740, 700)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(0)
        root.setContentsMargins(0, 0, 0, 0)

        # ── Title bar ───────────────────────────────────────────────────────
        title_bar = QFrame()
        title_bar.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-bottom: 1px solid {BORDER_AMBER};
            }}
        """)
        tb_layout = QVBoxLayout(title_bar)
        tb_layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)
        tb_layout.setSpacing(SPACING_SM)

        title_lbl = QLabel("HOW THE ACADEMIC INTEGRITY CHECK WORKS")
        title_lbl.setStyleSheet(f"""
            color: {PHOSPHOR_HOT};
            font-size: 14px;
            font-weight: bold;
            letter-spacing: 2px;
        """)
        tb_layout.addWidget(title_lbl)

        subtitle_lbl = QLabel(
            "Patterns for conversation, not verdicts  —  "
            "Read this before reviewing any flags."
        )
        subtitle_lbl.setStyleSheet(f"color: {ROSE_ACCENT}; font-size: 12px;")
        tb_layout.addWidget(subtitle_lbl)

        root.addWidget(title_bar)

        # ── Scrollable content ──────────────────────────────────────────────
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: {BG_VOID}; border: none; }}
            QScrollBar:vertical {{
                background: {BG_INSET}; width: 8px; border-radius: 4px;
            }}
            QScrollBar::handle:vertical {{
                background: {BORDER_AMBER}; border-radius: 4px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet(f"background: {BG_VOID};")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        content_layout.setSpacing(SPACING_MD)

        for section in _SECTIONS:
            content_layout.addWidget(self._make_section(section))

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        root.addWidget(scroll, 1)

        # ── Footer / close button ───────────────────────────────────────────
        footer = QFrame()
        footer.setStyleSheet(f"""
            QFrame {{
                background: {BG_CARD};
                border-top: 1px solid {BORDER_DARK};
            }}
        """)
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)
        footer_layout.addStretch()

        close_btn = QPushButton("Close")
        make_secondary_button(close_btn)
        close_btn.setFixedWidth(100)
        close_btn.clicked.connect(self.accept)
        footer_layout.addWidget(close_btn)

        root.addWidget(footer)

    def _make_section(self, section: dict) -> QFrame:
        """Build one accordion-style card for a content section."""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: {CARD_GRADIENT};
                border: 1px solid {BORDER_DARK};
                border-radius: 6px;
            }}
        """)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        layout.setSpacing(SPACING_SM)

        # Heading
        heading = QLabel(section["heading"].upper())
        heading.setStyleSheet(f"""
            color: {section['accent']};
            font-size: 10px;
            font-weight: bold;
            letter-spacing: 1px;
        """)
        layout.addWidget(heading)

        # Separator
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color: {BORDER_DARK}; background: {BORDER_DARK}; max-height: 1px;")
        layout.addWidget(sep)

        # Body
        body = QLabel(section["body"])
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setStyleSheet(f"""
            color: {PHOSPHOR_MID};
            font-size: 12px;
            line-height: 1.6;
            padding: 4px 0;
        """)
        layout.addWidget(body)

        return card
