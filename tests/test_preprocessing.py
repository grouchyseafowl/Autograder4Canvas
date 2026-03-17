#!/usr/bin/env python3
"""
Test the preprocessing pipeline with realistic student submissions.

Three test cases:
  1. English audio (.m4a) — transcription only
  2. Spanish text (.txt)  — translation only
  3. Spanish audio (.m4a) — transcription AND translation

Run from repo root:
    python tests/test_preprocessing.py
"""

import sys
import json
from pathlib import Path

# Ensure src/ is importable
src = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src))

FIXTURES = Path(__file__).parent / "preprocessing_fixtures"


def _make_fake_submission(
    sub_id: int, user_id: int, assignment_id: int,
    body: str = "", attachments: list = None,
) -> dict:
    """Build a Canvas-like submission dict for testing."""
    return {
        "id": sub_id,
        "user_id": user_id,
        "assignment_id": assignment_id,
        "body": body,
        "attachments": attachments or [],
    }


def _make_local_attachment(filepath: Path) -> dict:
    """Fake a Canvas attachment dict that points to a local file.

    The preprocessor downloads from `url` — for local testing we
    serve via a quick file:// URL, but the transcriber needs a
    real download. We'll work around this below.
    """
    return {
        "filename": filepath.name,
        "url": filepath.as_uri(),
        "content-type": (
            "audio/mp4" if filepath.suffix == ".m4a"
            else "text/plain"
        ),
        "size": filepath.stat().st_size,
    }


def main():
    print("=" * 60)
    print("PREPROCESSING PIPELINE TEST")
    print("=" * 60)

    # ------------------------------------------------------------------
    # Test 1: Spanish text (translation only)
    # ------------------------------------------------------------------
    print("\n── Test 1: Spanish Text Submission (translation) ──\n")
    spanish_text = (FIXTURES / "spanish_essay.txt").read_text()

    sub_spanish_text = _make_fake_submission(
        sub_id=1001, user_id=101, assignment_id=5001,
        body=spanish_text,
    )

    from preprocessing.language_detector import detect_language, language_name
    lang = detect_language(spanish_text)
    print(f"  Language detected: {language_name(lang.language_code)}"
          f" (confidence: {lang.confidence:.0%})")
    print(f"  Needs translation: {lang.needs_translation}")

    if lang.needs_translation:
        from preprocessing.translator import Translator
        translator = Translator(backend="ollama", model="llama3.1:8b")
        if translator.is_available():
            print("  Translating (chunked, via Ollama)...")
            result = translator.translate(spanish_text, lang.language_code)
            print(f"  Success: {result.success}")
            print(f"  Chunks translated: {result.chunks_translated}")
            print(f"  First 200 chars of translation:")
            print(f"    {result.translated_text[:200]}...")
        else:
            print("  ⚠ Ollama not available — skipping translation test")
            print("    Start Ollama with: ollama serve")

    # ------------------------------------------------------------------
    # Test 2: English audio (transcription only)
    # ------------------------------------------------------------------
    print("\n── Test 2: English Audio Submission (transcription) ──\n")
    english_audio = FIXTURES / "english_reflection.m4a"

    if english_audio.exists():
        from preprocessing.transcriber import Transcriber
        transcriber = Transcriber(model_size="medium")
        if transcriber.is_available():
            print(f"  Transcribing {english_audio.name}...")
            result = transcriber.transcribe_file(str(english_audio))
            print(f"  Success: {result.success}")
            print(f"  Duration: {result.duration_seconds:.1f}s")
            print(f"  Detected language: {result.detected_language}")
            print(f"  Transcript ({len(result.transcript.split())} words):")
            print(f"    {result.transcript[:300]}...")
        else:
            print("  ⚠ Whisper not available — skipping transcription test")
            print("    Install with: pip install faster-whisper")
            print("    Or build whisper.cpp from source")
    else:
        print(f"  ⚠ Audio file not found: {english_audio}")
        print("    Generate with: say -v 'Ava (Enhanced)' -o english_reflection.m4a --data-format=alac 'test text'")

    # ------------------------------------------------------------------
    # Test 3: Spanish audio (transcription + translation)
    # ------------------------------------------------------------------
    print("\n── Test 3: Spanish Audio Submission (transcription + translation) ──\n")
    spanish_audio = FIXTURES / "spanish_reflection.m4a"

    if spanish_audio.exists():
        from preprocessing.transcriber import Transcriber
        transcriber = Transcriber(model_size="medium")
        if transcriber.is_available():
            print(f"  Transcribing {spanish_audio.name}...")
            result = transcriber.transcribe_file(str(spanish_audio))
            print(f"  Success: {result.success}")
            print(f"  Duration: {result.duration_seconds:.1f}s")
            print(f"  Detected language: {result.detected_language}")
            print(f"  Transcript ({len(result.transcript.split())} words):")
            print(f"    {result.transcript[:300]}...")

            if result.success and result.transcript:
                # Now detect language and translate
                lang = detect_language(result.transcript)
                print(f"\n  Language of transcript: {language_name(lang.language_code)}"
                      f" (confidence: {lang.confidence:.0%})")

                if lang.needs_translation:
                    from preprocessing.translator import Translator
                    translator = Translator(backend="ollama", model="llama3.1:8b")
                    if translator.is_available():
                        print("  Translating transcript to English...")
                        tr = translator.translate(result.transcript, lang.language_code)
                        print(f"  Translation success: {tr.success}")
                        print(f"  English translation:")
                        print(f"    {tr.translated_text[:300]}...")
                    else:
                        print("  ⚠ Ollama not available for translation")
                else:
                    print("  Transcript already in English (or detected as English)")
        else:
            print("  ⚠ Whisper not available")
    else:
        print(f"  ⚠ Audio file not found: {spanish_audio}")

    # ------------------------------------------------------------------
    # Test 4: Full pipeline integration
    # ------------------------------------------------------------------
    print("\n── Test 4: Full Pipeline (all three submissions together) ──\n")

    from preprocessing import PreprocessingPipeline

    pipeline = PreprocessingPipeline(
        translation_enabled=True,
        transcription_enabled=True,
        whisper_model="medium",
        translation_backend="ollama",
        translation_model="llama3.1:8b",
    )

    # For the full pipeline test, we simulate what the insights engine does:
    # The pipeline expects Canvas submission dicts. For audio attachments,
    # it normally downloads from a URL. For local testing, we'll process
    # the text submission through the pipeline and handle audio separately.

    submissions = [
        # Spanish text submission
        _make_fake_submission(
            sub_id=1001, user_id=101, assignment_id=5001,
            body=spanish_text,
        ),
        # English text submission (as a control)
        _make_fake_submission(
            sub_id=1002, user_id=102, assignment_id=5001,
            body=(
                "Omi and Winant's concept of racial formation helped me "
                "understand how race is constructed through politics and "
                "culture. I connected this to my own experience growing up "
                "in a redlined neighborhood."
            ),
        ),
    ]

    def _progress(current, total, msg):
        print(f"  [{current+1}/{total}] {msg}")

    results = pipeline.process_submissions(submissions, progress_callback=_progress)

    print(f"\n  Processed {len(results)} submissions:")
    for r in results:
        print(f"    Student {r.user_id}: {r.processing_summary}")
        if r.was_translated:
            print(f"      Translated from: {r.original_language_name}")
            print(f"      English text: {r.text[:150]}...")
        elif r.text:
            print(f"      Text: {r.text[:150]}...")
        if r.needs_teacher_comment:
            print(f"      Teacher comment: {r.teacher_comment[:150]}...")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"  Spanish text file:  {FIXTURES / 'spanish_essay.txt'}")
    print(f"  English audio:      {FIXTURES / 'english_reflection.m4a'}")
    print(f"  Spanish audio:      {FIXTURES / 'spanish_reflection.m4a'}")
    print()
    print("  To use these with the GUI, you'd need to:")
    print("  1. Upload them as Canvas assignment submissions")
    print("  2. Or create a demo mode that feeds local files to the pipeline")
    print()


if __name__ == "__main__":
    main()
