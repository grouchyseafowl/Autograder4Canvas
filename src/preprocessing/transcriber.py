"""
Audio transcription backend for student submissions.

Supports two backends, auto-detected:
  1. whisper.cpp CLI (preferred) — native binary, fastest, uses Metal/CUDA.
     User compiles or installs via Homebrew/package manager.
  2. faster-whisper (fallback)  — pure Python via CTranslate2, pip-installable.

Both run entirely on-device — no audio data leaves the machine.

Key feature: both backends support a TRANSLATE mode that transcribes
non-English audio directly to English in one step, which is far better
quality than transcribe → LLM translate for audio content.

Supports common audio/video formats students submit via Canvas:
  .mp3, .m4a, .wav, .ogg, .webm, .mp4, .mov, .flac, .aac
"""

import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import requests as http_requests

logger = logging.getLogger("autograder.preprocessing")


# --- Result types ---

@dataclass
class TranscriptionSegment:
    """A single segment from Whisper output."""
    start: float       # seconds
    end: float          # seconds
    text: str


@dataclass
class TranscriptionResult:
    """Result of transcribing an audio file."""
    filename: str
    transcript: str                     # Full joined text
    segments: List[TranscriptionSegment] = field(default_factory=list)
    detected_language: Optional[str] = None
    was_translated: bool = False        # True if Whisper translated to English
    duration_seconds: float = 0.0
    success: bool = True
    error: Optional[str] = None
    backend_used: Optional[str] = None  # "whisper-cpp" or "faster-whisper"


# --- Audio detection ---

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".wav", ".ogg", ".webm",
    ".mp4", ".mov", ".flac", ".aac", ".wma",
    ".opus", ".oga",
}

AUDIO_MIME_PREFIXES = ("audio/", "video/")


def is_audio_attachment(attachment: Dict) -> bool:
    """Check if a Canvas attachment is an audio/video file we can transcribe."""
    content_type = attachment.get("content-type", "")
    filename = attachment.get("filename", "")
    ext = Path(filename).suffix.lower()
    return (
        any(content_type.startswith(p) for p in AUDIO_MIME_PREFIXES)
        or ext in AUDIO_EXTENSIONS
    )


# --- whisper.cpp binary discovery ---

def _find_whisper_cpp_binary() -> Optional[str]:
    """
    Find the whisper-cli (or whisper-cpp) binary on the system.

    Search order:
      1. WHISPER_CPP_PATH environment variable
      2. PATH (whisper-cli, whisper-cpp, whisper)
      3. Common build locations:
         - ~/whisper.cpp/build/bin/whisper-cli  (source build)
         - Homebrew locations
    """
    # 1. Environment variable override
    env_path = os.environ.get("WHISPER_CPP_PATH")
    if env_path and os.path.isfile(env_path) and os.access(env_path, os.X_OK):
        return env_path

    # 2. Check PATH for common binary names
    for name in ("whisper-cli", "whisper-cpp", "whisper"):
        found = shutil.which(name)
        if found:
            return found

    # 3. Common build/install locations
    home = Path.home()
    candidates = [
        home / "whisper.cpp" / "build" / "bin" / "whisper-cli",
        home / "whisper.cpp" / "build" / "bin" / "main",
        home / "whisper.cpp" / "main",
    ]

    # Platform-specific locations
    system = platform.system()
    if system == "Darwin":
        candidates.extend([
            Path("/opt/homebrew/bin/whisper-cli"),
            Path("/usr/local/bin/whisper-cli"),
        ])
    elif system == "Linux":
        candidates.extend([
            Path("/usr/local/bin/whisper-cli"),
            home / ".local" / "bin" / "whisper-cli",
        ])
    elif system == "Windows":
        candidates.extend([
            home / "whisper.cpp" / "build" / "bin" / "Release" / "whisper-cli.exe",
            home / "whisper.cpp" / "build" / "bin" / "whisper-cli.exe",
        ])

    for path in candidates:
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path)

    return None


def _find_whisper_cpp_model(model_size: str = "base") -> Optional[str]:
    """
    Find a whisper.cpp GGML model file.

    Search order:
      1. WHISPER_CPP_MODEL environment variable
      2. ~/whisper.cpp/models/ directory
      3. XDG/platform cache directories
    """
    env_model = os.environ.get("WHISPER_CPP_MODEL")
    if env_model and os.path.isfile(env_model):
        return env_model

    home = Path.home()
    models_dir = home / "whisper.cpp" / "models"

    if models_dir.is_dir():
        # Prefer: exact match → turbo → standard
        # e.g., for "base": ggml-base.bin, for "large-v3-turbo": ggml-large-v3-turbo.bin
        candidates = [
            f"ggml-{model_size}.bin",
            f"for-tests-ggml-{model_size}.bin",
        ]

        # Also look for any available model if preferred size not found
        for name in candidates:
            path = models_dir / name
            if path.is_file():
                return str(path)

        # Fallback: find any .bin model, preferring larger ones
        preference_order = [
            "large-v3-turbo", "large-v3", "large", "medium", "small", "base", "tiny",
        ]
        for size in preference_order:
            for f in models_dir.glob(f"*{size}*.bin"):
                if "en" not in f.name:  # Prefer multilingual models
                    return str(f)
        for f in models_dir.glob(f"*.bin"):
            if "for-tests" not in f.name:
                return str(f)

    return None


# --- whisper.cpp backend ---

class WhisperCppBackend:
    """Transcription via whisper.cpp CLI subprocess."""

    def __init__(
        self,
        binary_path: Optional[str] = None,
        model_path: Optional[str] = None,
        model_size: str = "base",
        threads: int = 4,
    ):
        self._binary = binary_path or _find_whisper_cpp_binary()
        self._model = model_path or _find_whisper_cpp_model(model_size)
        self.threads = threads

    def is_available(self) -> bool:
        return self._binary is not None and self._model is not None

    def get_info(self) -> str:
        """Return human-readable info about the backend."""
        if not self.is_available():
            return "whisper.cpp: not available"
        model_name = Path(self._model).stem if self._model else "unknown"
        return f"whisper.cpp: {self._binary} (model: {model_name})"

    def transcribe(
        self,
        file_path: str,
        translate: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe (or translate) an audio file via whisper-cli.

        Args:
            file_path: Path to audio file.
            translate: If True, use --translate to output English directly.
        """
        filename = Path(file_path).name

        if not self.is_available():
            return TranscriptionResult(
                filename=filename, transcript="", success=False,
                error="whisper.cpp binary or model not found",
            )

        # whisper-cli outputs JSON with segments
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_base = os.path.join(tmp_dir, "output")

            # Convert non-WAV audio to 16kHz mono WAV for reliable whisper.cpp input
            input_path = file_path
            ext = Path(file_path).suffix.lower()
            if ext != ".wav":
                wav_path = os.path.join(tmp_dir, "input.wav")
                try:
                    # macOS: afconvert. Linux/Windows: ffmpeg.
                    if shutil.which("afconvert"):
                        subprocess.run(
                            ["afconvert", file_path, wav_path,
                             "-d", "LEI16", "-f", "WAVE", "-r", "16000"],
                            capture_output=True, timeout=30,
                        )
                    elif shutil.which("ffmpeg"):
                        subprocess.run(
                            ["ffmpeg", "-i", file_path, "-ar", "16000",
                             "-ac", "1", "-y", wav_path],
                            capture_output=True, timeout=30,
                        )
                    if os.path.exists(wav_path):
                        input_path = wav_path
                    else:
                        log.warning("Audio conversion failed — trying original format")
                except Exception as e:
                    log.warning("Audio conversion error: %s — trying original format", e)

            cmd = [
                self._binary,
                "-m", self._model,
                "-t", str(self.threads),
                "-l", "auto",       # auto-detect language
                "-oj",              # output JSON
                "-of", output_base, # output file prefix
                input_path,
            ]
            if translate:
                cmd.insert(-1, "--translate")

            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10 min max for long recordings
                )

                if result.returncode != 0:
                    stderr = result.stderr.strip()[:200]
                    return TranscriptionResult(
                        filename=filename, transcript="", success=False,
                        error=f"whisper-cli exited {result.returncode}: {stderr}",
                        backend_used="whisper-cpp",
                    )

                # Parse JSON output
                json_path = output_base + ".json"
                if not os.path.isfile(json_path):
                    # Fall back to text output
                    txt_path = output_base + ".txt"
                    if os.path.isfile(txt_path):
                        transcript = Path(txt_path).read_text().strip()
                        return TranscriptionResult(
                            filename=filename, transcript=transcript,
                            was_translated=translate, success=True,
                            backend_used="whisper-cpp",
                        )
                    return TranscriptionResult(
                        filename=filename, transcript="", success=False,
                        error="No output file produced",
                        backend_used="whisper-cpp",
                    )

                with open(json_path) as f:
                    data = json.load(f)

                segments = []
                texts = []
                for seg in data.get("transcription", []):
                    text = seg.get("text", "").strip()
                    if text:
                        t_start = seg.get("timestamps", {}).get("from", "00:00:00,000")
                        t_end = seg.get("timestamps", {}).get("to", "00:00:00,000")
                        segments.append(TranscriptionSegment(
                            start=_parse_timestamp(t_start),
                            end=_parse_timestamp(t_end),
                            text=text,
                        ))
                        texts.append(text)

                transcript = " ".join(texts)
                detected_lang = data.get("result", {}).get("language", None)

                # Estimate duration from last segment
                duration = segments[-1].end if segments else 0.0

                return TranscriptionResult(
                    filename=filename,
                    transcript=transcript,
                    segments=segments,
                    detected_language=detected_lang,
                    was_translated=translate,
                    duration_seconds=duration,
                    success=True,
                    backend_used="whisper-cpp",
                )

            except subprocess.TimeoutExpired:
                return TranscriptionResult(
                    filename=filename, transcript="", success=False,
                    error="Transcription timed out (>10 min)",
                    backend_used="whisper-cpp",
                )
            except Exception as e:
                return TranscriptionResult(
                    filename=filename, transcript="", success=False,
                    error=str(e), backend_used="whisper-cpp",
                )


def _parse_timestamp(ts: str) -> float:
    """Parse whisper.cpp timestamp like '00:01:23,456' to seconds."""
    try:
        ts = ts.replace(",", ".")
        parts = ts.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        return 0.0
    except (ValueError, IndexError):
        return 0.0


# --- faster-whisper backend (fallback) ---

try:
    from faster_whisper import WhisperModel
    _FASTER_WHISPER_AVAILABLE = True
except ImportError:
    _FASTER_WHISPER_AVAILABLE = False


class FasterWhisperBackend:
    """Transcription via faster-whisper Python library (CTranslate2)."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
    ):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def is_available(self) -> bool:
        return _FASTER_WHISPER_AVAILABLE

    def get_info(self) -> str:
        if not self.is_available():
            return "faster-whisper: not installed"
        return f"faster-whisper: model={self.model_size}, device={self.device}"

    def _get_model(self):
        if self._model is not None:
            return self._model
        if not _FASTER_WHISPER_AVAILABLE:
            return None
        try:
            logger.info(f"Loading faster-whisper model '{self.model_size}'...")
            self._model = WhisperModel(
                model_size_or_path=self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
            return self._model
        except Exception as e:
            logger.error(f"Failed to load faster-whisper model: {e}")
            return None

    def transcribe(
        self,
        file_path: str,
        translate: bool = False,
    ) -> TranscriptionResult:
        filename = Path(file_path).name
        model = self._get_model()
        if model is None:
            return TranscriptionResult(
                filename=filename, transcript="", success=False,
                error="faster-whisper model not available",
            )

        try:
            task = "translate" if translate else "transcribe"
            segments_iter, info = model.transcribe(
                file_path,
                beam_size=5,
                task=task,
                vad_filter=True,
                vad_parameters={"min_silence_duration_ms": 500},
            )

            segments = []
            texts = []
            for seg in segments_iter:
                segments.append(TranscriptionSegment(
                    start=seg.start, end=seg.end,
                    text=seg.text.strip(),
                ))
                texts.append(seg.text.strip())

            return TranscriptionResult(
                filename=filename,
                transcript=" ".join(texts),
                segments=segments,
                detected_language=info.language,
                was_translated=translate,
                duration_seconds=info.duration,
                success=True,
                backend_used="faster-whisper",
            )

        except Exception as e:
            logger.error(f"faster-whisper transcription failed: {e}")
            return TranscriptionResult(
                filename=filename, transcript="", success=False,
                error=str(e), backend_used="faster-whisper",
            )


# --- Unified Transcriber ---

class Transcriber:
    """
    Transcribes audio files using the best available backend.

    Priority: whisper.cpp (native, faster) → faster-whisper (pip, portable).

    Both backends support a translate mode that converts non-English
    audio directly to English — better quality than transcribe + LLM
    translate, and eliminates an LLM call.
    """

    def __init__(
        self,
        backend: str = "auto",
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        whisper_cpp_binary: Optional[str] = None,
        whisper_cpp_model: Optional[str] = None,
        whisper_cpp_threads: int = 4,
    ):
        """
        Args:
            backend: "auto", "whisper-cpp", or "faster-whisper".
            model_size: Model size for faster-whisper ("tiny"…"large-v3").
            device: Device for faster-whisper ("cpu", "cuda", "auto").
            compute_type: Compute type for faster-whisper.
            whisper_cpp_binary: Override path to whisper-cli binary.
            whisper_cpp_model: Override path to whisper.cpp GGML model.
            whisper_cpp_threads: Thread count for whisper.cpp.
        """
        self._backend_pref = backend
        self._cpp = WhisperCppBackend(
            binary_path=whisper_cpp_binary,
            model_path=whisper_cpp_model,
            model_size=model_size,
            threads=whisper_cpp_threads,
        )
        self._fw = FasterWhisperBackend(
            model_size=model_size,
            device=device,
            compute_type=compute_type,
        )
        self._active_backend = None

    def _resolve_backend(self):
        """Pick the best available backend."""
        if self._active_backend is not None:
            return self._active_backend

        if self._backend_pref == "whisper-cpp":
            self._active_backend = self._cpp if self._cpp.is_available() else None
        elif self._backend_pref == "faster-whisper":
            self._active_backend = self._fw if self._fw.is_available() else None
        else:
            # Auto: prefer whisper.cpp (native perf), fall back to faster-whisper
            if self._cpp.is_available():
                self._active_backend = self._cpp
            elif self._fw.is_available():
                self._active_backend = self._fw

        if self._active_backend:
            logger.info(f"Transcription backend: {self._active_backend.get_info()}")
        else:
            logger.warning("No transcription backend available")

        return self._active_backend

    def is_available(self) -> bool:
        return self._resolve_backend() is not None

    def get_info(self) -> str:
        backend = self._resolve_backend()
        return backend.get_info() if backend else "No backend available"

    def transcribe_file(
        self,
        file_path: str,
        translate: bool = False,
    ) -> TranscriptionResult:
        """
        Transcribe a local audio file.

        Args:
            file_path: Path to audio file.
            translate: If True, output English translation directly
                       (skips the need for LLM translation of audio).
        """
        backend = self._resolve_backend()
        if backend is None:
            return TranscriptionResult(
                filename=Path(file_path).name,
                transcript="", success=False,
                error="No transcription backend available",
            )
        return backend.transcribe(file_path, translate=translate)

    def transcribe_from_url(
        self,
        url: str,
        filename: str,
        headers: Optional[Dict[str, str]] = None,
        translate: bool = False,
    ) -> TranscriptionResult:
        """
        Download an audio file from a Canvas attachment URL and transcribe it.

        Args:
            url: Download URL.
            filename: Original filename (for logging/results).
            headers: HTTP headers (e.g. Canvas auth).
            translate: If True, translate non-English audio to English.
        """
        ext = Path(filename).suffix.lower() or ".wav"
        tmp_path = None
        try:
            logger.info(f"  Downloading audio: {filename}...")
            r = http_requests.get(url, headers=headers, timeout=120, stream=True)
            r.raise_for_status()

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                for chunk in r.iter_content(chunk_size=8192):
                    tmp.write(chunk)
                tmp_path = tmp.name

            logger.info(f"  Transcribing: {filename}...")
            result = self.transcribe_file(tmp_path, translate=translate)
            result.filename = filename
            return result

        except Exception as e:
            logger.error(f"Download/transcription failed for {filename}: {e}")
            return TranscriptionResult(
                filename=filename, transcript="", success=False,
                error=str(e),
            )
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
