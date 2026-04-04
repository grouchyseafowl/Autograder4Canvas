"""
Image analysis for student submissions via vision LLM.

Students submit images for several reasons:
  - Photos of handwritten notes
  - Artistic/creative projects (drawings, collages, photos)
  - Visual/diagram-based assignments

This module handles all three cases: it transcribes any visible text
AND describes the visual content so the teacher can understand what
was submitted even if the original image isn't open in front of them.

Intentionally slow — vision inference takes 30-60s per image on an 8B
model — but it's the only way to include visual work in the analysis
pipeline without losing those students entirely.

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
    """Result from analyzing one image submission."""
    filename: str
    transcript: str = ""          # Verbatim text visible in the image (if any)
    description: str = ""         # Visual description of the image content
    is_visual_art: bool = False   # True when no text found — primarily a visual submission
    success: bool = False
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Analysis prompt
# ---------------------------------------------------------------------------

_ANALYSIS_PROMPT = """\
A student submitted this image as part of a class assignment. Analyze it \
carefully and respond in the following format:

TEXT: [Any text visible in the image — handwriting, printed text, labels, \
captions. Transcribe word for word. Write NONE if no text is visible.]

VISUAL: [A concise, respectful description of what the image shows — what \
the student created or depicted. 1-3 sentences. This helps the teacher \
understand the submission without opening the file.]

Be accurate and neutral. This is for an educator reviewing student work."""


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

    def _check_ollama_vision(self, pull_if_missing: bool = False) -> bool:
        """Check if Ollama has a vision model available.

        If pull_if_missing is True and the configured model isn't present,
        attempts to pull it via `ollama pull` before returning.
        """
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
                # Auto-select first available vision model if configured one
                # isn't present
                if not any(
                    m == self._model or m.startswith(self._model.split(":")[0])
                    for m in models
                ):
                    self._model = vision_models[0]
                return True

            # Configured model present?
            if any(
                m == self._model or m.startswith(self._model.split(":")[0])
                for m in models
            ):
                return True

            # Nothing found — optionally pull
            if pull_if_missing:
                return self._ollama_pull(self._model)

            return False
        except Exception:
            return False

    def _ollama_pull(self, model: str) -> bool:
        """Attempt to pull an Ollama model. Returns True if successful."""
        import subprocess
        logger.info("Vision model '%s' not found — attempting ollama pull...", model)
        try:
            result = subprocess.run(
                ["ollama", "pull", model],
                capture_output=True, text=True, timeout=600,
            )
            if result.returncode == 0:
                logger.info("Pulled vision model: %s", model)
                return True
            logger.warning(
                "ollama pull %s failed (rc=%d): %s",
                model, result.returncode, result.stderr[:200],
            )
        except FileNotFoundError:
            logger.warning("ollama command not found — cannot auto-pull vision model")
        except Exception as e:
            logger.warning("ollama pull failed: %s", e)
        return False

    def ensure_available(self) -> bool:
        """Like is_available() but attempts to pull/download the model if missing.

        For MLX: mlx_vlm will auto-download from HuggingFace on first use,
        so this just checks the import is available.
        For Ollama: attempts ollama pull if the model isn't installed yet.
        """
        if self._backend == "ollama":
            return self._check_ollama_vision(pull_if_missing=True)
        elif self._backend == "mlx":
            return self._check_mlx_vision()
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

    def _parse_analysis_response(self, raw: str, filename: str) -> ImageTranscriptionResult:
        """Parse the TEXT: / VISUAL: response format into an ImageTranscriptionResult."""
        transcript = ""
        description = ""
        is_visual_art = False

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.upper().startswith("TEXT:"):
                val = stripped[5:].strip()
                if val.upper() != "NONE" and val:
                    transcript = val
            elif stripped.upper().startswith("VISUAL:"):
                description = stripped[7:].strip()

        # If model didn't follow format, use full response as description
        if not transcript and not description:
            description = raw.strip()

        is_visual_art = bool(description and not transcript)

        return ImageTranscriptionResult(
            filename=filename,
            transcript=transcript,
            description=description,
            is_visual_art=is_visual_art,
            success=True,
        )

    def _ollama_transcribe(
        self, image_path: str, filename: str
    ) -> ImageTranscriptionResult:
        """Use Ollama's vision model to analyze an image."""
        try:
            with open(image_path, "rb") as f:
                image_b64 = base64.b64encode(f.read()).decode("utf-8")

            r = http_requests.post(
                f"{self._ollama_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": [{
                        "role": "user",
                        "content": _ANALYSIS_PROMPT,
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
            raw = r.json().get("message", {}).get("content", "")
            return self._parse_analysis_response(raw, filename)

        except Exception as e:
            logger.warning("Image analysis failed for %s: %s", filename, e)
            return ImageTranscriptionResult(
                filename=filename, error=str(e)
            )

    def _mlx_transcribe(
        self, image_path: str, filename: str
    ) -> ImageTranscriptionResult:
        """Use MLX vision model to analyze an image."""
        try:
            from mlx_vlm import load, generate
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import load_config

            model_name = self._model or "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"

            if not hasattr(self, "_mlx_cache"):
                self._mlx_cache = {}

            if model_name not in self._mlx_cache:
                logger.info("Loading MLX vision model: %s (may download on first use)", model_name)
                model, processor = load(model_name)
                config = load_config(model_name)
                self._mlx_cache[model_name] = (model, processor, config)

            model, processor, config = self._mlx_cache[model_name]

            formatted = apply_chat_template(
                processor, config,
                _ANALYSIS_PROMPT,
                num_images=1,
            )
            result = generate(
                model, processor, formatted,
                image=[image_path],
                max_tokens=2048,
                verbose=False,
            )
            raw = result.text if hasattr(result, "text") else str(result)
            return self._parse_analysis_response(raw, filename)

        except Exception as e:
            logger.warning("MLX image analysis failed for %s: %s", filename, e)
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
