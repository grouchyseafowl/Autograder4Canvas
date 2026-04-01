"""
gibberish_gate.py — unit tests.

Tests the pre-analysis gate that decides whether to run LLM analysis.
This gate is equity-critical: false positives silently exclude a student
from all analysis.  The equity exemptions (AAVE, multilingual, translated,
non-standard English) are the most important things to lock down.

Design principles validated here:
  - was_translated ALWAYS bypasses all checks — translation validates real language
  - Below the 15-word minimum: gate stays open (handled elsewhere)
  - Keyboard mash, Lorem Ipsum, repetition spam: gate closes
  - AAVE, vernacular, slang, stream-of-consciousness: gate STAYS OPEN
  - Poor grammar or non-standard English: gate STAYS OPEN

All tests use synthetic text — no real student data.

Run with: python3 -m pytest tests/test_gibberish_gate.py -v
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

from insights.gibberish_gate import (
    GibberishResult,
    _has_vowel,
    _is_keyboard_sequence,
    check_gibberish,
)


# ---------------------------------------------------------------------------
# Synthetic corpora — no real student data
# ---------------------------------------------------------------------------

# Genuine English with non-standard grammar — must NOT be flagged
AAVE_TEXT = """\
Deadass this reading was hitting different. Crenshaw be explaining how the law
ain't built for Black women — like my aunt done told me this same thing growing
up but now I got the academic language for it. Y'all know how the system works,
finna act like race and gender separate but they wasn't never separate for us.
Lowkey this changed how I think about discrimination cases."""

STREAM_OF_CONSCIOUSNESS = """\
so I was reading this and I kept thinking wait no that's not right let me
back up okay so Crenshaw is saying the law treats race and gender like they
separate but they not separate they never was separate that's the whole point
I had to read that paragraph like three times before I got it and even now
I'm not totally sure I understand but I think what she's saying is the
framework itself is broken not just the people using it"""

SLANG_TEXT = """\
ngl this reading slapped. didn't expect to be this pressed about a law review
article but here we are lol. crenshaw literally just explained everything that
happens in my neighborhood and now i can't unsee it. the general motors case
tho... that's wild. they literally told these women their race problem wasn't
a race problem and their gender problem wasn't a gender problem. make it make
sense honestly"""

POOR_GRAMMAR = """\
This reading are very important for understand how discrimination work different
for different people. The author she explain that Black womens facing problem
that no one see because the courts only looking at one thing at time. I think
this article it very helpful for understand why my community having trouble
even when they do everything right. The law not always fair for everyone."""

GENUINE_REFLECTION = """\
Crenshaw's framework on intersectionality changed how I think about legal systems.
She argues that when courts analyze discrimination through single-axis frameworks,
they structurally erase the specific harms faced by people with compound identities.
The General Motors case is a powerful example — Black women's claims were dismissed
because they didn't fit either the race-discrimination or gender-discrimination
mold. This has real implications for how we think about legal advocacy."""

# True gibberish — should be flagged
KEYBOARD_MASH = " ".join([
    "asdfgh qwerty zxcvbn asdfghjkl qwertyuiop",
    "zxcvbnm asdfgh qwerty asdfghjk lkjhgfdsa",
    "mnbvcxz poiuytrewq asdfghjkl qwertyuiop",
    "zxcvbnm mnbvcxz qwerty asdfgh",
])

LOREM_IPSUM = """\
Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor
incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis
nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat.
Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore."""

REPETITION_SPAM = " ".join(["test"] * 30 + ["word"] * 5)

LOW_UNIQUE_SPAM = " ".join(["the"] * 20 + ["and"] * 15 + ["to"] * 15)


# ---------------------------------------------------------------------------
# GibberishResult — should_skip_llm property
# ---------------------------------------------------------------------------

class TestGibberishResultProperty:
    def test_should_skip_when_gibberish_and_high_confidence(self):
        result = GibberishResult(is_gibberish=True, reason="lorem_ipsum", confidence=0.95)
        assert result.should_skip_llm is True

    def test_should_skip_at_exact_threshold(self):
        result = GibberishResult(is_gibberish=True, reason="keyboard_mash", confidence=0.7)
        assert result.should_skip_llm is True

    def test_should_not_skip_when_not_gibberish(self):
        result = GibberishResult(is_gibberish=False, reason="", confidence=0.0)
        assert result.should_skip_llm is False

    def test_should_not_skip_when_low_confidence(self):
        # gibberish=True but confidence < 0.7 → don't skip
        result = GibberishResult(is_gibberish=True, reason="uncertain", confidence=0.5)
        assert result.should_skip_llm is False


# ---------------------------------------------------------------------------
# _has_vowel helper
# ---------------------------------------------------------------------------

class TestHasVowel:
    def test_plain_vowel(self):
        assert _has_vowel("hello") is True

    def test_no_vowel(self):
        assert _has_vowel("qwrtp") is False

    def test_accented_vowel(self):
        assert _has_vowel("café") is True

    def test_single_vowel(self):
        assert _has_vowel("a") is True

    def test_y_counts_as_vowel(self):
        # y is included in the broad set for loanwords
        assert _has_vowel("myth") is True


# ---------------------------------------------------------------------------
# _is_keyboard_sequence helper
# ---------------------------------------------------------------------------

class TestIsKeyboardSequence:
    def test_qwerty_sequence(self):
        assert _is_keyboard_sequence("qwerty") is True

    def test_asdf_sequence(self):
        assert _is_keyboard_sequence("asdfgh") is True

    def test_real_word_not_keyboard(self):
        assert _is_keyboard_sequence("hello") is False

    def test_too_short_not_flagged(self):
        # < 4 chars
        assert _is_keyboard_sequence("qwe") is False

    def test_mixed_rows_not_keyboard(self):
        # Letters jump between rows — 'hello' has h(middle), e(top), l(middle), l, o(top)
        assert _is_keyboard_sequence("hello") is False

    def test_zxcv_sequence(self):
        assert _is_keyboard_sequence("zxcvbn") is True


# ---------------------------------------------------------------------------
# Equity tests — gate must STAY OPEN for these
# These are the most important tests: false positives harm real students.
# ---------------------------------------------------------------------------

class TestEquityExemptions:
    """The gate must never flag genuine student writing.

    This includes non-standard dialects, vernacular, stream-of-consciousness,
    poor grammar, and slang. These are linguistic assets (#COMMUNITY_CULTURAL_WEALTH),
    not gibberish.
    """

    def test_aave_text_not_flagged(self):
        result = check_gibberish(AAVE_TEXT)
        assert result.is_gibberish is False, (
            "AAVE text must not be flagged — these are linguistic features, not errors"
        )

    def test_stream_of_consciousness_not_flagged(self):
        result = check_gibberish(STREAM_OF_CONSCIOUSNESS)
        assert result.is_gibberish is False, (
            "Stream-of-consciousness writing is genuine student voice"
        )

    def test_slang_heavy_text_not_flagged(self):
        result = check_gibberish(SLANG_TEXT)
        assert result.is_gibberish is False, (
            "Slang reflects authentic register — not a sign of fake/empty submission"
        )

    def test_poor_grammar_not_flagged(self):
        result = check_gibberish(POOR_GRAMMAR)
        assert result.is_gibberish is False, (
            "Non-standard grammar may reflect ESL, translanguaging, or dialect — "
            "not gibberish"
        )

    def test_translated_text_always_bypassed(self):
        """was_translated=True must bypass ALL checks, even for LOREM IPSUM."""
        # Even Lorem ipsum passes if it was "translated" — the flag means
        # a real translation pipeline validated it as real language
        result = check_gibberish(LOREM_IPSUM, was_translated=True)
        assert result.is_gibberish is False
        assert result.confidence == 0.0

    def test_translated_flag_bypasses_keyboard_mash(self):
        result = check_gibberish(KEYBOARD_MASH, was_translated=True)
        assert result.is_gibberish is False

    def test_genuine_reflection_not_flagged(self):
        result = check_gibberish(GENUINE_REFLECTION)
        assert result.is_gibberish is False


# ---------------------------------------------------------------------------
# Word minimum — gate stays open for short genuine text
# ---------------------------------------------------------------------------

class TestWordMinimum:
    def test_below_15_words_not_flagged(self):
        # Short text handled by word-count minimum elsewhere
        result = check_gibberish("This is a short submission.")
        assert result.is_gibberish is False

    def test_14_word_lorem_ipsum_not_flagged(self):
        # Even Lorem ipsum below 15 words → below_word_minimum, not flagged
        result = check_gibberish("Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor")
        # This is 12 words — below minimum
        assert result.is_gibberish is False

    def test_word_minimum_reason_set(self):
        result = check_gibberish("Three words here.")
        assert result.reason == "below_word_minimum"

    def test_14_word_text_reason_set(self):
        result = check_gibberish("word " * 14)
        assert result.reason == "below_word_minimum"
        assert result.is_gibberish is False


# ---------------------------------------------------------------------------
# Gibberish detection — gate closes for actual garbage
# ---------------------------------------------------------------------------

class TestGibberishDetection:
    def test_lorem_ipsum_flagged(self):
        result = check_gibberish(LOREM_IPSUM)
        assert result.is_gibberish is True
        assert result.reason == "lorem_ipsum"

    def test_lorem_ipsum_confidence_high(self):
        result = check_gibberish(LOREM_IPSUM)
        assert result.confidence >= 0.9

    def test_lorem_ipsum_detail_populated(self):
        result = check_gibberish(LOREM_IPSUM)
        assert len(result.detail) > 0

    def test_keyboard_mash_flagged(self):
        result = check_gibberish(KEYBOARD_MASH)
        assert result.is_gibberish is True
        assert result.reason == "keyboard_mash"

    def test_keyboard_mash_should_skip_llm(self):
        result = check_gibberish(KEYBOARD_MASH)
        assert result.should_skip_llm is True

    def test_repetition_spam_flagged(self):
        result = check_gibberish(REPETITION_SPAM)
        assert result.is_gibberish is True
        assert result.reason == "repetition_spam"

    def test_repetition_spam_detail_mentions_word(self):
        result = check_gibberish(REPETITION_SPAM)
        assert "test" in result.detail or "repeated" in result.detail

    def test_low_unique_ratio_flagged(self):
        result = check_gibberish(LOW_UNIQUE_SPAM)
        assert result.is_gibberish is True
        assert result.reason == "repetition_spam"

    def test_result_is_gibberish_result_type(self):
        result = check_gibberish(LOREM_IPSUM)
        assert isinstance(result, GibberishResult)

    def test_empty_text_below_minimum(self):
        result = check_gibberish("")
        assert result.is_gibberish is False

    def test_dolor_sit_amet_variant_also_flagged(self):
        text = ("dolor sit amet consectetur adipiscing elit " * 6).strip()
        result = check_gibberish(text)
        assert result.is_gibberish is True


# ---------------------------------------------------------------------------
# _is_keyboard_sequence — adjacency fix regression tests
# ---------------------------------------------------------------------------

class TestKeyboardSequenceAdjacency:
    """
    #LANGUAGE_JUSTICE: The keyboard mash detector must NOT flag common
    English words whose letters happen to sit on the same row. Without
    the adjacency check, words like 'people', 'power', 'equity' trigger
    false positives — silently excluding students from analysis.
    """

    def test_people_not_keyboard(self):
        assert _is_keyboard_sequence("people") is False

    def test_power_not_keyboard(self):
        assert _is_keyboard_sequence("power") is False

    def test_pretty_not_keyboard(self):
        assert _is_keyboard_sequence("pretty") is False

    def test_equity_not_keyboard(self):
        assert _is_keyboard_sequence("equity") is False

    def test_write_not_keyboard(self):
        assert _is_keyboard_sequence("write") is False

    def test_require_not_keyboard(self):
        assert _is_keyboard_sequence("require") is False

    def test_territory_not_keyboard(self):
        assert _is_keyboard_sequence("territory") is False

    def test_deadass_not_keyboard(self):
        """AAVE truth marker must not be flagged as keyboard mash."""
        assert _is_keyboard_sequence("deadass") is False

    def test_qwerty_still_caught(self):
        assert _is_keyboard_sequence("qwerty") is True

    def test_asdfgh_still_caught(self):
        assert _is_keyboard_sequence("asdfgh") is True

    def test_reversed_sequence_caught(self):
        """Reversed keyboard mash: lkjhgf."""
        assert _is_keyboard_sequence("lkjhgf") is True

    def test_four_char_sequence_not_caught(self):
        """4-char sequences now fall below the 5-streak threshold — acceptable trade-off."""
        assert _is_keyboard_sequence("asdf") is False
