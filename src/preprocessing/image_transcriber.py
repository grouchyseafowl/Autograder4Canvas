"""
Handwritten notes transcription via vision LLM.

Students sometimes submit photos of handwritten notes. This module
detects image attachments and uses a small vision model (via Ollama
or MLX) to transcribe handwritten text.

This is intentionally slow — vision inference on an 8B model takes
30-60 seconds per image — but it's the only way to include handwritten
work in the analysis pipeline without losing those students' voices.

Runs entirely on-device. No student images leave the machine.
"""

import base64
import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import requests as http_requests

logger = logging.getLogger("autograder.preprocessing")

# Image extensions and MIME types that might contain handwritten notes
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".tiff", ".bmp", ".webp"}
IMAGE_MIME_PREFIXES = ("image/",)


def is_image_attachment(attachment: Dict) -> bool:
    """Check if a Canvas attachment is an image we should try to transcribe."""
    content_type = attachment.get("content-type", "")
    filename = attachment.get("filename", "")
    ext = Path(filename).suffix.lower()
    return (
        any(content_type.startswith(p) for p in IMAGE_MIME_PREFIXES)
        or ext in IMAGE_EXTENSIONS
    )


@dataclass
class ImageTranscriptionResult:
    """Result from transcribing one image."""
    filename: str
    transcript: str = ""
    success: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Transcription prompt
# ---------------------------------------------------------------------------

_TRANSCRIPTION_PROMPT = """\
This is a photo of a student's handwritten work. Transcribe ALL the \
handwritten text you can see, preserving the student's original words \
as closely as possible. Include crossed-out text in [brackets].

If this is not handwritten text (e.g., a printed page, diagram, or \
unrelated photo), respond with: [NOT HANDWRITTEN TEXT]

Respond with ONLY the transcribed text, nothing else."""


class ImageTranscriber:
    """Transcribe handwritten notes from images using a vision LLM.

    Supports Ollama (with a vision model like llava or llama3.2-vision)
    and MLX (with mlx-vlm).
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "llama3.2-vision:11b",
        ollama_base_url: str = "http://localhost:11434",
    ):
        self._backend = backend
        self._model = model
        self._ollama_url = ollama_base_url

    def is_available(self) -> bool:
        """Check if a vision model is available."""
        if self._backend == "ollama":
            return self._check_ollama_vision()
        elif self._backend == "mlx":
            return self._check_mlx_vision()
        return False

    def _check_ollama_vision(self) -> bool:
        """Check if Ollama has a vision model available."""
        try:
            r = http_requests.get(
                f"{self._ollama_url}/api/tags", timeout=5
            )
            if r.status_code != 200:
                return False
            models = [m["name"] for m in r.json().get("models", [])]
            # Check for common vision models
            vision_models = [
                m for m in models
                if any(v in m.lower() for v in (
                    "llava", "vision", "bakllava", "moondream",
                ))
            ]
            if vision_models:
                # Auto-select first available vision model if user didn't
                # configure one explicitly
                if not any(
                    m == self._model or m.startswith(self._model.split(":")[0])
                    for m in models
                ):
                    self._model = vision_models[0]
                return True
            # Also check if the configured model exists
            return any(
                m == self._model or m.startswith(self._model.split(":")[0])
                for m in models
            )
        except Exception:
            return False

    def _check_mlx_vision(self) -> bool:
        """Check if MLX vision is available."""
        try:
            from mlx_vlm import load  # noqa: F401
            return True
        except ImportError:
            return False

    def transcribe_image(
        self, image_path: str
    ) -> ImageTranscriptionResult:
        """Transcribe handwritten text from an image file."""
        filename = Path(image_path).name

        if self._backend == "ollama":
            return self._ollama_transcribe(image_path, filename)
        elif self._backend == "mlx":
            return self._mlx_transcribe(image_path, filename)
        return ImageTranscriptionResult(
            filename=filename, error="No vision backend configured"
        )

    def _ollama_transcribe(
        self, image_path: str, filename: str
    ) -> ImageTranscriptionResult:
        """Use Ollama's vision model to transcribe an image."""
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            r = http_requests.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{
                        "role": "user",
                        "content": _TRANSCRIPTION_PROMPT,
                        "images": [image_b64],
                    }],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 2048,
                    },
                },
                timeout=120,  # Vision inference is slow
            )
            r.raise_for_status()
            text = r.json().get("message", {}).get("content", "")

            # Check if the model said it's not handwritten
            if "[NOT HANDWRITTEN TEXT]" in text:
                return ImageTranscriptionResult(
                    filename=filename,
                    transcript="",
                    success=True,  # successfully determined it's not handwriting
                )

            return ImageTranscriptionResult(
                filename=filename,
                transcript=text.strip(),
                success=True,
            )

        except Exception as e:
            logger.warning("Image transcription failed for %s: %s", filename, e)
            return ImageTranscriptionResult(
                filename=filename, error=str(e)
            )

    def _mlx_transcribe(
        self, image_path: str, filename: str
    ) -> ImageTranscriptionResult:
        """Use MLX vision model to transcribe an image."""
        try:
            from mlx_vlm import load, generate
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import load_config

            model_name = self._model or "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"

            if not hasattr(self, "_mlx_cache"):
                self._mlx_cache = {}

            if model_name not in self._mlx_cache:
                model, processor = load(model_name)
                config = load_config(model_name)
                self._mlx_cache[model_name] = (model, processor, config)

            model, processor, config = self._mlx_cache[model_name]

            formatted = apply_chat_template(
                processor, config,
                _TRANSCRIPTION_PROMPT,
                num_images=1,
            )
            result = generate(
                model, processor, formatted,
                image=[image_path],
                max_tokens=2048,
                verbose=False,
            )
            text = result.text if hasattr(result, "text") else str(result)

            if "[NOT HANDWRITTEN TEXT]" in text:
                return ImageTranscriptionResult(
                    filename=filename, transcript="", success=True,
                )

            return ImageTranscriptionResult(
                filename=filename, transcript=text.strip(), success=True,
            )

        except Exception as e:
            logger.warning("MLX image transcription failed for %s: %s", filename, e)
            return ImageTranscriptionResult(
                filename=filename, error=str(e),
            )

    def transcribe_from_url(
        self,
        url: str,
        filename: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> ImageTranscriptionResult:
        """Download an image from URL and transcribe it."""
        tmp_path = None
        try:
            ext = Path(filename).suffix.lower() or ".jpg"
            r = http_requests.get(
                url, headers=headers or {}, timeout=60, stream=True,
            )
            r.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name

            return self.transcribe_image(tmp_path)

        except Exception as e:
            logger.warning("Image download failed for %s: %s", filename, e)
            return ImageTranscriptionResult(
                filename=filename, error=str(e),
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
