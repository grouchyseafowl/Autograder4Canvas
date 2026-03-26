"""
Language detection for student submissions.

Uses the lightweight `langdetect` library (Google's language-detection port)
to identify non-English text. No LLM required — runs in milliseconds.
"""

import logging
import re
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger("autograder.preprocessing")

try:
    from langdetect import detect, detect_langs, LangDetectException
    from langdetect import DetectorFactory
    # Make detection deterministic
    DetectorFactory.seed = 0
    _LANGDETECT_AVAILABLE = True
except ImportError:
    _LANGDETECT_AVAILABLE = False
    logger.warning("langdetect not installed — language detection disabled")


@dataclass
class LanguageResult:
    """Result of language detection on a text."""
    language_code: str          # ISO 639-1 code ("en", "es", "zh-cn", etc.)
    confidence: float           # 0.0–1.0
    needs_translation: bool     # True if not English and confidence is high enough
    original_text: str          # The text that was analyzed
    # Three-way multilingual classification:
    #   "monolingual_english" — no non-English detected
    #   "concept_inclusion"   — isolated non-English terms/phrases (don't translate)
    #   "code_switching"      — bilingual fluency, switching between languages (don't translate — asset)
    #   "primary_other_language" — written primarily in another language (translate, preserve original)
    multilingual_type: str = "monolingual_english"
    # Non-English languages detected (for metadata pass-through)
    detected_languages: Optional[list] = None


# Minimum text length (in words) to attempt detection.
# Very short texts produce unreliable results.
MIN_WORDS_FOR_DETECTION = 8

# Confidence threshold: below this, we assume English (benefit of the doubt).
CONFIDENCE_THRESHOLD = 0.70


def _clean_for_detection(text: str) -> str:
    """Strip HTML, URLs, and Canvas markup that confuse detection."""
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _classify_multilingual_type(
    cleaned_text: str,
    top_lang: str,
    confidence: float,
    needs_translation: bool,
) -> tuple:
    """Classify the three-way multilingual type via per-sentence detection.

    Returns (multilingual_type, detected_languages_list).

    The distinction matters for downstream handling:
      - code_switching: preserve as-is, it's a linguistic asset
      - concept_inclusion: preserve as-is, the foreign term IS the point
      - primary_other_language: translate for analysis, preserve original for teacher
      - monolingual_english: no special handling needed
    """
    if needs_translation:
        return "primary_other_language", [top_lang]

    if top_lang == "en" and confidence >= CONFIDENCE_THRESHOLD:
        # English is dominant — check per-sentence for mixed content
        try:
            sentences = re.split(r'(?<=[.!?])\s+', cleaned_text)
            sentences = [s.strip() for s in sentences if len(s.split()) >= 4]

            non_english_count = 0
            detected_langs = set()
            for sent in sentences:
                try:
                    sent_langs = detect_langs(sent)
                    sent_top = sent_langs[0]
                    if str(sent_top.lang) != "en" and sent_top.prob >= 0.6:
                        non_english_count += 1
                        detected_langs.add(str(sent_top.lang))
                except (LangDetectException, Exception):
                    pass

            lang_list = sorted(detected_langs) if detected_langs else None

            if non_english_count >= 2:
                # Multiple non-English sentences = code-switching
                return "code_switching", lang_list
            elif non_english_count == 1 or detected_langs:
                # Isolated non-English = concept inclusion
                return "concept_inclusion", lang_list
            else:
                return "monolingual_english", None

        except Exception as e:
            logger.debug(f"Per-sentence detection failed: {e}")
            return "monolingual_english", None

    return "monolingual_english", None


def detect_language(text: str) -> LanguageResult:
    """
    Detect the language of a student submission.

    Returns a LanguageResult. If detection fails or text is too short,
    defaults to English (benefit of the doubt — never penalize students
    for detection errors).

    Args:
        text: Raw submission text (may contain HTML).

    Returns:
        LanguageResult with language code, confidence, and translation flag.
    """
    cleaned = _clean_for_detection(text)

    # Too short to detect reliably
    if len(cleaned.split()) < MIN_WORDS_FOR_DETECTION:
        return LanguageResult(
            language_code="en",
            confidence=0.0,
            needs_translation=False,
            original_text=text,
        )

    if not _LANGDETECT_AVAILABLE:
        return LanguageResult(
            language_code="en",
            confidence=0.0,
            needs_translation=False,
            original_text=text,
        )

    try:
        langs = detect_langs(cleaned)
        top = langs[0]
        lang_code = str(top.lang)
        confidence = top.prob

        needs_translation = (
            lang_code != "en"
            and confidence >= CONFIDENCE_THRESHOLD
        )

        # Classify the three-way multilingual type
        multilingual_type, detected_langs = _classify_multilingual_type(
            cleaned, lang_code, confidence, needs_translation,
        )

        return LanguageResult(
            language_code=lang_code,
            confidence=confidence,
            needs_translation=needs_translation,
            original_text=text,
            multilingual_type=multilingual_type,
            detected_languages=detected_langs,
        )

    except LangDetectException:
        # Detection failed — default to English
        return LanguageResult(
            language_code="en",
            confidence=0.0,
            needs_translation=False,
            original_text=text,
        )
    except Exception as e:
        logger.warning(f"Language detection error: {e}")
        return LanguageResult(
            language_code="en",
            confidence=0.0,
            needs_translation=False,
            original_text=text,
        )


# Human-readable language names for common codes (used in comments/reports)
LANGUAGE_NAMES = {
    "af": "Afrikaans", "ar": "Arabic", "bg": "Bulgarian", "bn": "Bengali",
    "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
    "de": "German", "el": "Greek", "en": "English", "es": "Spanish",
    "et": "Estonian", "fa": "Persian", "fi": "Finnish", "fr": "French",
    "gu": "Gujarati", "he": "Hebrew", "hi": "Hindi", "hr": "Croatian",
    "hu": "Hungarian", "id": "Indonesian", "it": "Italian", "ja": "Japanese",
    "kn": "Kannada", "ko": "Korean", "lt": "Lithuanian", "lv": "Latvian",
    "mk": "Macedonian", "ml": "Malayalam", "mr": "Marathi", "ne": "Nepali",
    "nl": "Dutch", "no": "Norwegian", "pa": "Punjabi", "pl": "Polish",
    "pt": "Portuguese", "ro": "Romanian", "ru": "Russian", "sk": "Slovak",
    "sl": "Slovenian", "so": "Somali", "sq": "Albanian", "sv": "Swedish",
    "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "th": "Thai",
    "tl": "Tagalog", "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu",
    "vi": "Vietnamese", "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
}


def language_name(code: str) -> str:
    """Return human-readable name for an ISO 639-1 code."""
    return LANGUAGE_NAMES.get(code, code.upper())
