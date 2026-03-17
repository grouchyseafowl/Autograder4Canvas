"""
Chunked translation backend for student submissions.

Translates non-English text to English using either:
  - A local Ollama model (default: llama3.1:8b)
  - A cloud API (OpenAI-compatible endpoint, if institutional access provided)

Designed for 8B local models: text is split into small chunks (~150 words)
so each translation call stays well within the model's quality window.
"""

import logging
import re
import time
import requests
from dataclasses import dataclass
from typing import List, Optional

from .language_detector import language_name

logger = logging.getLogger("autograder.preprocessing")


@dataclass
class TranslationResult:
    """Result of translating a submission."""
    original_text: str
    translated_text: str
    source_language: str        # ISO 639-1 code
    source_language_name: str   # Human-readable name
    chunks_translated: int      # How many chunks were processed
    success: bool
    error: Optional[str] = None


# --- Chunking ---

# Target chunk size in words. 150 is conservative for 8B models —
# keeps each prompt+response well under 1K tokens.
CHUNK_TARGET_WORDS = 150

# Max words before we absolutely split, even mid-sentence.
CHUNK_MAX_WORDS = 200


def _split_into_chunks(text: str) -> List[str]:
    """
    Split text into translation-friendly chunks.

    Strategy: split on paragraph boundaries first, then sentence boundaries,
    targeting ~150 words per chunk. This preserves natural breakpoints
    so the LLM gets coherent context for each translation.
    """
    # Split into paragraphs
    paragraphs = re.split(r'\n\s*\n', text.strip())
    paragraphs = [p.strip() for p in paragraphs if p.strip()]

    chunks = []
    current_chunk = []
    current_words = 0

    for para in paragraphs:
        para_words = len(para.split())

        # If this paragraph alone exceeds max, split it by sentences
        if para_words > CHUNK_MAX_WORDS:
            # Flush current chunk first
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_words = 0

            sentences = re.split(r'(?<=[.!?])\s+', para)
            sent_chunk = []
            sent_words = 0
            for sent in sentences:
                sw = len(sent.split())
                if sent_words + sw > CHUNK_MAX_WORDS and sent_chunk:
                    chunks.append(" ".join(sent_chunk))
                    sent_chunk = []
                    sent_words = 0
                sent_chunk.append(sent)
                sent_words += sw
            if sent_chunk:
                chunks.append(" ".join(sent_chunk))
            continue

        # Would adding this paragraph exceed target?
        if current_words + para_words > CHUNK_TARGET_WORDS and current_chunk:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = []
            current_words = 0

        current_chunk.append(para)
        current_words += para_words

    if current_chunk:
        chunks.append("\n\n".join(current_chunk))

    if not chunks:
        chunks = [text]

    # Final pass: hard-split any chunk that still exceeds max words
    # (handles text with no paragraph or sentence boundaries)
    final = []
    for chunk in chunks:
        words = chunk.split()
        if len(words) <= CHUNK_MAX_WORDS:
            final.append(chunk)
        else:
            for i in range(0, len(words), CHUNK_MAX_WORDS):
                final.append(" ".join(words[i:i + CHUNK_MAX_WORDS]))

    return final


# --- Translation backends ---

def _build_translation_prompt(text: str, source_lang: str) -> tuple:
    """Build system and user prompts for translation."""
    lang = language_name(source_lang)
    system_prompt = (
        f"You are a professional translator. Translate the following {lang} "
        f"text into clear, natural English. Preserve the meaning, tone, and "
        f"structure of the original. This is a student's academic submission — "
        f"keep the student's voice and level of formality. "
        f"Output ONLY the English translation, nothing else."
    )
    user_prompt = text
    return system_prompt, user_prompt


class Translator:
    """
    Translates text using a local Ollama model or cloud API.

    Follows the same lazy-init and graceful-degradation patterns
    as OllamaReplyChecker.
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "llama3.1:8b",
        base_url: str = "http://localhost:11434",
        api_key: Optional[str] = None,
        cloud_base_url: Optional[str] = None,
        cloud_model: Optional[str] = None,
    ):
        """
        Args:
            backend: "ollama" or "cloud" (OpenAI-compatible API).
            model: Ollama model name.
            base_url: Ollama server URL.
            api_key: API key for cloud backend.
            cloud_base_url: Base URL for cloud API (e.g. OpenAI, institutional).
            cloud_model: Model name for cloud API.
        """
        self.backend = backend
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.cloud_base_url = (cloud_base_url or "").rstrip("/")
        self.cloud_model = cloud_model
        self._ollama_available = None

    def _check_ollama(self) -> bool:
        """Check if Ollama is reachable (cached)."""
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            r = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                self._ollama_available = any(
                    m == self.model or m.startswith(self.model.split(":")[0])
                    for m in models
                )
                if not self._ollama_available:
                    logger.warning(
                        f"Ollama running but model '{self.model}' not found. "
                        f"Available: {models}"
                    )
            else:
                self._ollama_available = False
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def _translate_chunk_ollama(self, text: str, source_lang: str) -> Optional[str]:
        """Translate a single chunk via Ollama."""
        system_prompt, user_prompt = _build_translation_prompt(text, source_lang)
        try:
            r = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 1024,
                    },
                },
                timeout=180,
            )
            r.raise_for_status()
            return r.json().get("message", {}).get("content", "").strip()
        except Exception as e:
            logger.warning(f"Ollama translation chunk failed: {e}")
            return None

    def _translate_chunk_cloud(self, text: str, source_lang: str) -> Optional[str]:
        """Translate a single chunk via cloud API (OpenAI-compatible)."""
        if not self.api_key or not self.cloud_base_url:
            logger.warning("Cloud translation not configured")
            return None
        system_prompt, user_prompt = _build_translation_prompt(text, source_lang)
        try:
            r = requests.post(
                f"{self.cloud_base_url}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.cloud_model or "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.1,
                    "max_tokens": 512,
                },
                timeout=60,
            )
            r.raise_for_status()
            return (
                r.json()["choices"][0]["message"]["content"].strip()
            )
        except Exception as e:
            logger.warning(f"Cloud translation chunk failed: {e}")
            return None

    def _translate_chunk(self, text: str, source_lang: str) -> Optional[str]:
        """Route to the active backend."""
        if self.backend == "cloud":
            return self._translate_chunk_cloud(text, source_lang)
        else:
            return self._translate_chunk_ollama(text, source_lang)

    def is_available(self) -> bool:
        """Check whether the configured backend is reachable."""
        if self.backend == "cloud":
            return bool(self.api_key and self.cloud_base_url)
        return self._check_ollama()

    def translate(self, text: str, source_language: str) -> TranslationResult:
        """
        Translate a full submission from source_language to English.

        Splits the text into chunks, translates each independently,
        then reassembles. If any chunk fails, the original text for
        that chunk is kept (partial translation is better than none).

        Args:
            text: Full submission text.
            source_language: ISO 639-1 code of detected language.

        Returns:
            TranslationResult with translated text and metadata.
        """
        if not self.is_available():
            return TranslationResult(
                original_text=text,
                translated_text=text,
                source_language=source_language,
                source_language_name=language_name(source_language),
                chunks_translated=0,
                success=False,
                error=f"Translation backend '{self.backend}' not available",
            )

        chunks = _split_into_chunks(text)
        translated_chunks = []
        success_count = 0

        for i, chunk in enumerate(chunks):
            logger.info(
                f"  Translating chunk {i+1}/{len(chunks)} "
                f"({len(chunk.split())} words)..."
            )
            result = self._translate_chunk(chunk, source_language)
            if result:
                translated_chunks.append(result)
                success_count += 1
            else:
                # Keep original chunk on failure
                translated_chunks.append(chunk)
                logger.warning(
                    f"  Chunk {i+1} failed — keeping original text"
                )

            # Small delay between chunks to avoid overwhelming local model
            if i < len(chunks) - 1:
                time.sleep(0.5)

        translated_text = "\n\n".join(translated_chunks)

        return TranslationResult(
            original_text=text,
            translated_text=translated_text,
            source_language=source_language,
            source_language_name=language_name(source_language),
            chunks_translated=success_count,
            success=success_count > 0,
            error=None if success_count > 0 else "All chunks failed",
        )
