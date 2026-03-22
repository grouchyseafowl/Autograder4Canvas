"""
Pre-analysis gate: detect obviously non-analyzable text.

Catches keyboard mash, Lorem Ipsum, and repetition spam BEFORE expensive
LLM analysis runs.  This is a compute-efficiency gate — it prevents the
system from burning 2+ minutes of LLM time on text that contains no
analyzable content.

Conservative by design — only flags truly obvious cases.

Will NOT flag:
  - Poor grammar or non-standard English
  - Stream-of-consciousness writing
  - Slang-heavy or vernacular text
  - Text in other languages (should be translated first)
  - Short but genuine submissions (handled by word-count minimum)
  - Translated submissions (translation itself validates real language)

Equity note:
  The was_translated flag bypasses this gate entirely.  Translation
  validates that the text is real human language in SOME language,
  so the English-centric heuristics here don't apply.
"""

import re
from collections import Counter
from dataclasses import dataclass
from typing import Optional


@dataclass
class GibberishResult:
    """Result of the pre-analysis gibberish gate."""

    is_gibberish: bool
    reason: str  # "keyboard_mash", "lorem_ipsum", "repetition_spam", ""
    confidence: float  # 0.0–1.0
    detail: str = ""  # human-readable explanation for teacher

    @property
    def should_skip_llm(self) -> bool:
        """Whether this submission should skip LLM analysis."""
        return self.is_gibberish and self.confidence >= 0.7


# -----------------------------------------------------------------------
# Detection patterns
# -----------------------------------------------------------------------

_LOREM_IPSUM = re.compile(
    r"lorem\s+ipsum|dolor\s+sit\s+amet|consectetur\s+adipiscing",
    re.IGNORECASE,
)

# Keyboard rows for mash detection
_KEYBOARD_ROWS = ("qwertyuiop", "asdfghjkl", "zxcvbnm")


def _has_vowel(word: str) -> bool:
    """Check if a word contains at least one vowel (broad set for loanwords)."""
    return bool(re.search(r"[aeiouyáéíóúàèìòùäëïöü]", word.lower()))


def _is_keyboard_sequence(word: str) -> bool:
    """Check if a word looks like consecutive keys on a keyboard row."""
    word = word.lower()
    if len(word) < 4:
        return False
    for row in _KEYBOARD_ROWS:
        streak = 0
        for ch in word:
            if ch in row:
                streak += 1
                if streak >= 4:
                    return True
            else:
                streak = 0
    return False


# -----------------------------------------------------------------------
# Main gate function
# -----------------------------------------------------------------------

def check_gibberish(
    text: str,
    *,
    was_translated: bool = False,
) -> GibberishResult:
    """Pre-analysis gate: detect obviously non-analyzable text.

    Parameters
    ----------
    text : str
        The submission text (post-HTML-stripping, post-translation).
    was_translated : bool
        If True, skip all checks — translation validates real language.

    Returns
    -------
    GibberishResult
        Whether the text is gibberish and should skip LLM analysis.
    """
    # Translation validates the text is real language — skip entirely
    if was_translated:
        return GibberishResult(False, "", 0.0)

    words = text.split()

    # Too short to analyze — handled by word minimum gate elsewhere
    if len(words) < 15:
        return GibberishResult(False, "below_word_minimum", 0.0)

    # ----- 1. Lorem Ipsum -----
    if _LOREM_IPSUM.search(text):
        return GibberishResult(
            True,
            "lorem_ipsum",
            0.95,
            "Submission contains Lorem Ipsum placeholder text",
        )

    # ----- 2. Keyboard mash -----
    # Strip punctuation from words for analysis
    clean_words = [
        w.strip(".,!?;:'\"()-[]{}") for w in words
        if len(w.strip(".,!?;:'\"()-[]{}")) >= 3
    ]

    if clean_words:
        keyboard_count = sum(1 for w in clean_words if _is_keyboard_sequence(w))
        no_vowel_count = sum(1 for w in clean_words if not _has_vowel(w))

        keyboard_ratio = keyboard_count / len(clean_words)
        no_vowel_ratio = no_vowel_count / len(clean_words)

        if keyboard_ratio > 0.4:
            return GibberishResult(
                True,
                "keyboard_mash",
                0.9,
                f"{keyboard_count}/{len(clean_words)} words appear to be "
                f"keyboard sequences",
            )

        if no_vowel_ratio > 0.5 and len(clean_words) > 10:
            return GibberishResult(
                True,
                "keyboard_mash",
                0.85,
                f"{no_vowel_count}/{len(clean_words)} words contain no vowels",
            )

    # ----- 3. Excessive single-word repetition -----
    word_freq = Counter(
        w.lower().strip(".,!?;:'\"()-") for w in words
    )
    if word_freq:
        most_common_word, most_common_count = word_freq.most_common(1)[0]
        # One word > 40% of the text AND text is non-trivial length
        if most_common_count / len(words) > 0.4 and len(words) > 20:
            return GibberishResult(
                True,
                "repetition_spam",
                0.9,
                f"'{most_common_word}' repeated {most_common_count}/{len(words)} "
                f"times",
            )

    # ----- 4. Very low unique word ratio -----
    # Normal English text: ~50-65% unique words in a 200-word essay.
    # Repetitive but real text: ~30-40%.
    # Threshold 12% catches only true spam (24 unique words in 200).
    unique_ratio = len(word_freq) / len(words) if words else 1.0
    if unique_ratio < 0.12 and len(words) > 30:
        return GibberishResult(
            True,
            "repetition_spam",
            0.85,
            f"Only {len(word_freq)} unique words in {len(words)}-word "
            f"submission ({unique_ratio:.0%} unique)",
        )

    # Passed all checks
    return GibberishResult(False, "", 0.0)
