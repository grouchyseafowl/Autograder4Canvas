"""
Preprocessing pipeline for multilingual and audio submissions.

Detects non-English text and audio attachments in student submissions,
then translates/transcribes them so the insights pipeline receives
uniform English text.

Transcription backends (auto-detected):
  - whisper.cpp CLI (native, preferred if installed)
  - faster-whisper Python library (pip install, fallback)

Translation backends:
  - Local Ollama (default, 8B-friendly with chunking)
  - Cloud API (OpenAI-compatible, opt-in for institutional access)
"""

from .image_transcriber import ImageTranscriber, ImageTranscriptionResult, is_image_attachment
from .pipeline import PreprocessingPipeline, PreprocessedSubmission
from .transcriber import Transcriber, TranscriptionResult, is_audio_attachment
from .translator import Translator, TranslationResult
from .language_detector import detect_language, LanguageResult

__all__ = [
    "PreprocessingPipeline",
    "PreprocessedSubmission",
    "ImageTranscriber",
    "ImageTranscriptionResult",
    "is_image_attachment",
    "Transcriber",
    "TranscriptionResult",
    "is_audio_attachment",
    "Translator",
    "TranslationResult",
    "detect_language",
    "LanguageResult",
]
