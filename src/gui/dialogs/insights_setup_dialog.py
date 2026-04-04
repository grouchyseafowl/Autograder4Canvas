"""
First-run setup assistant for the Insights Engine.

Detects which dependencies are installed, which need setup,
and walks the teacher through getting everything working —
no terminal required.

Triggered automatically when teacher first opens Generate Insights,
or manually from Settings.
"""

import logging
import subprocess
import sys
import shutil
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QScrollArea, QWidget, QSizePolicy,
)
from PySide6.QtCore import Qt, Signal, QThread

from gui.styles import (
    px,
    SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    TERM_GREEN, BURN_RED, STATUS_WARN, AMBER_BTN,
    BG_VOID, BG_CARD, BG_INSET,
    BORDER_DARK, BORDER_AMBER,
    make_section_label, make_h_rule, make_content_pane,
    make_run_button, make_secondary_button,
)

log = logging.getLogger("autograder.insights_setup")


# ---------------------------------------------------------------------------
# Dependency checks
# ---------------------------------------------------------------------------

def _is_apple_silicon() -> bool:
    """Detect if running on Apple Silicon (M1/M2/M3/M4)."""
    import platform
    return (
        platform.system() == "Darwin"
        and platform.machine() == "arm64"
    )


def _is_externally_managed() -> bool:
    """Detect Homebrew / system Python that blocks bare pip install."""
    v = sys.version_info
    lib_dir = f"lib/python{v.major}.{v.minor}"
    for prefix in (sys.prefix, sys.base_prefix):
        marker = Path(prefix) / lib_dir / "EXTERNALLY-MANAGED"
        if marker.exists():
            return True
    return False


def _check_mlx() -> bool:
    """Is mlx-lm installed and importable?"""
    try:
        import mlx_lm  # noqa: F401
        return True
    except ImportError:
        return False


def _check_ollama_installed() -> bool:
    """Is the Ollama binary on the system?"""
    return shutil.which("ollama") is not None


def _check_ollama_running() -> bool:
    """Is the Ollama server responding?"""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        return r.status_code == 200
    except Exception:
        return False


def _check_ollama_model(model: str = "llama3.1:8b") -> bool:
    """Is the specified model pulled in Ollama?"""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return any(
                m == model or m.startswith(model.split(":")[0])
                for m in models
            )
    except Exception:
        pass
    return False


def _check_spacy_model() -> bool:
    """Is the spaCy English model installed?"""
    try:
        import spacy
        spacy.load("en_core_web_sm")
        return True
    except Exception:
        return False


def _check_vader() -> bool:
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        SentimentIntensityAnalyzer()
        return True
    except Exception:
        return False


def _check_sentence_transformers() -> bool:
    try:
        import sentence_transformers  # noqa: F401
        return True
    except ImportError:
        return False


def _check_sklearn() -> bool:
    try:
        import sklearn  # noqa: F401
        return True
    except ImportError:
        return False


def _check_whisper() -> bool:
    """Check if a fully-working Whisper backend is available.

    Returns True only when transcription will actually work — i.e., either
    faster-whisper is importable, OR whisper.cpp has both a binary AND a model
    file. Checking the binary alone is a false positive (binary without model
    = not usable).
    """
    try:
        from faster_whisper import WhisperModel  # noqa: F401
        return True
    except ImportError:
        pass
    # Use the actual backend availability check (binary + model both required)
    try:
        from preprocessing.transcriber import WhisperCppBackend
        return WhisperCppBackend().is_available()
    except Exception:
        pass
    return False


def _check_whisper_binary_only() -> bool:
    """True if whisper.cpp binary is on PATH but model may be missing."""
    try:
        from preprocessing.transcriber import _find_whisper_cpp_binary
        return _find_whisper_cpp_binary() is not None
    except Exception:
        pass
    return shutil.which("whisper-cli") is not None


def _check_file_extraction() -> bool:
    """Check if DOCX, PDF, and RTF text extraction libraries are available."""
    try:
        from docx import Document  # noqa: F401
        from pdfminer.high_level import extract_text  # noqa: F401
        from striprtf.striprtf import rtf_to_text  # noqa: F401
        return True
    except ImportError:
        return False


def _check_vision_model() -> bool:
    """Check if a vision model is available for handwriting transcription."""
    try:
        import requests
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", [])]
            return any(
                v in m.lower() for m in models
                for v in ("llava", "vision", "bakllava", "moondream")
            )
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# Background installer worker
# ---------------------------------------------------------------------------

# Where the app creates its own venv for managed package installs.
_APP_VENV = Path.home() / ".autograder4canvas" / "venv"


def _ensure_app_venv() -> Path:
    """Create the app-managed venv if it doesn't exist. Returns venv pip path."""
    venv_pip = _APP_VENV / "bin" / "pip"
    if not venv_pip.exists():
        import venv as _venv
        _APP_VENV.parent.mkdir(parents=True, exist_ok=True)
        _venv.create(str(_APP_VENV), with_pip=True, system_site_packages=True)
    return venv_pip


def app_venv_python() -> str:
    """Return the path to the app venv's Python, or sys.executable if no venv."""
    p = _APP_VENV / "bin" / "python3"
    return str(p) if p.exists() else sys.executable


class _InstallerWorker(QThread):
    """Runs pip install or other setup commands in background."""
    progress = Signal(str)
    finished = Signal(bool, str)  # success, message

    # install_mode: "global" uses sys.executable + --break-system-packages
    #               "venv" creates/uses ~/.autograder4canvas/venv/
    def __init__(self, task: str, install_mode: str = "global", parent=None):
        super().__init__(parent)
        self._task = task
        self._install_mode = install_mode

    def run(self):
        try:
            if self._task == "pip_deps":
                self._install_pip_deps()
            elif self._task == "spacy_model":
                self._install_spacy_model()
            elif self._task == "mlx_install":
                self._install_mlx()
            elif self._task == "ollama_pull":
                self._pull_ollama_model()
            elif self._task == "ollama_serve":
                self._start_ollama()
        except Exception as e:
            self.finished.emit(False, str(e))

    def _pip_install_cmd(self, *packages: str) -> list[str]:
        """Build pip install command using the chosen install mode."""
        if self._install_mode == "venv":
            venv_pip = _ensure_app_venv()
            return [str(venv_pip), "install", "--quiet"] + list(packages)
        else:
            cmd = [sys.executable, "-m", "pip", "install", "--quiet"]
            if _is_externally_managed():
                cmd.append("--break-system-packages")
            cmd.extend(packages)
            return cmd

    def _install_pip_deps(self):
        """Install missing pip packages."""
        packages = []
        if not _check_vader():
            packages.append("vaderSentiment")
        if not _check_sentence_transformers():
            packages.append("sentence-transformers")
        if not _check_sklearn():
            packages.append("scikit-learn")
        if not _check_file_extraction():
            packages.extend(["python-docx", "pdfminer.six", "striprtf", "odfpy"])
        # Install faster-whisper if no working whisper backend exists.
        # This includes the case where whisper.cpp binary is installed but the
        # GGML model file is missing — binary alone = not usable, so we need a
        # fallback. faster-whisper is the simpler install; whisper.cpp is faster
        # but requires a separate model download step.
        if not _check_whisper():
            packages.append("faster-whisper")
        try:
            import pydantic  # noqa: F401
        except ImportError:
            packages.append("pydantic")
        try:
            import textstat  # noqa: F401
        except ImportError:
            packages.append("textstat")
        try:
            import langdetect  # noqa: F401
        except ImportError:
            packages.append("langdetect")

        if not packages:
            self.finished.emit(True, "All Python packages already installed.")
            return

        self.progress.emit(f"Installing {', '.join(packages)}...")
        result = subprocess.run(
            self._pip_install_cmd(*packages),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            self.finished.emit(True, f"Installed: {', '.join(packages)}")
        else:
            self.finished.emit(False, f"pip install failed:\n{result.stderr[:500]}")

    def _install_mlx(self):
        """Install mlx-lm for Apple Silicon native inference."""
        self.progress.emit("Installing MLX (Apple Silicon AI framework)...")
        result = subprocess.run(
            self._pip_install_cmd("mlx-lm"),
            capture_output=True, text=True, timeout=300,
        )
        if result.returncode == 0:
            self.finished.emit(True, "MLX installed. Your Mac can now run AI models natively.")
        else:
            self.finished.emit(False, f"MLX install failed:\n{result.stderr[:500]}")

    def _install_spacy_model(self):
        self.progress.emit("Downloading spaCy English model (~15 MB)...")
        result = subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            self.finished.emit(True, "spaCy model installed.")
        else:
            self.finished.emit(False, f"spaCy download failed:\n{result.stderr[:500]}")

    def _pull_ollama_model(self):
        """Pull llama3.1:8b via Ollama REST API (not CLI — avoids terminal)."""
        try:
            import requests
            self.progress.emit("Downloading llama3.1:8b (~4.9 GB)...\nThis may take a while.")
            r = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": "llama3.1:8b", "stream": False},
                timeout=1800,  # 30 min timeout for large download
            )
            if r.status_code == 200:
                self.finished.emit(True, "Model llama3.1:8b downloaded successfully.")
            else:
                self.finished.emit(False, f"Ollama pull failed: {r.text[:300]}")
        except Exception as e:
            self.finished.emit(False, f"Could not pull model: {e}")

    def _start_ollama(self):
        """Try to start the Ollama server."""
        self.progress.emit("Starting Ollama server...")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait a moment for it to start
            import time
            for _ in range(10):
                time.sleep(1)
                if _check_ollama_running():
                    self.finished.emit(True, "Ollama server started.")
                    return
            self.finished.emit(False, "Ollama started but not responding yet. Try again in a moment.")
        except FileNotFoundError:
            self.finished.emit(False, "Ollama not found. Please install from ollama.com")


# ---------------------------------------------------------------------------
# Setup dialog
# ---------------------------------------------------------------------------

class InsightsSetupDialog(QDialog):
    """First-run assistant that checks and installs Insights dependencies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insights Engine Setup")
        self.setMinimumSize(600, 500)
        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")
        self._worker: Optional[_InstallerWorker] = None
        self._build_ui()
        self._run_checks()

    def _build_ui(self):
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        lo.setSpacing(SPACING_MD)

        title = QLabel("INSIGHTS ENGINE SETUP")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        lo.addWidget(title)

        sub = QLabel(
            "These tools power the AI-assisted features: Generate Insights, "
            "multilingual translation, and audio transcription. They are NOT "
            "required for basic autograding — complete/incomplete grading, "
            "discussion forum checks, and academic integrity analysis all "
            "work without any of this.\n\n"
            "Everything below runs locally on your computer. No student data "
            "leaves your machine."
        )
        sub.setWordWrap(True)
        sub.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(sub)
        lo.addWidget(make_h_rule())

        # Scrollable checklist
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        container = QWidget()
        container.setStyleSheet(f"background: {BG_VOID};")
        self._check_lo = QVBoxLayout(container)
        self._check_lo.setContentsMargins(0, 0, 0, 0)
        self._check_lo.setSpacing(SPACING_SM)
        scroll.setWidget(container)
        lo.addWidget(scroll, 1)

        # Progress area
        self._progress_label = QLabel("")
        self._progress_label.setWordWrap(True)
        self._progress_label.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setStyleSheet(
            f"QProgressBar {{ background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; height: 8px; }}"
            f"QProgressBar::chunk {{ background: {AMBER_BTN}; border-radius: 3px; }}"
        )
        lo.addWidget(self._progress_bar)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._install_btn = QPushButton("Install Missing Components")
        make_run_button(self._install_btn)
        self._install_btn.clicked.connect(self._install_missing)
        btn_row.addWidget(self._install_btn)

        self._recheck_btn = QPushButton("Re-check")
        make_secondary_button(self._recheck_btn)
        self._recheck_btn.clicked.connect(self._run_checks)
        btn_row.addWidget(self._recheck_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        lo.addLayout(btn_row)

    def _run_checks(self):
        """Run all dependency checks and populate the checklist."""
        # Clear existing
        while self._check_lo.count():
            item = self._check_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        self._checks = {}

        # Core Python packages
        self._add_check("Python analysis packages",
                        "VADER sentiment, scikit-learn, sentence-transformers, etc.",
                        _check_vader() and _check_sklearn(),
                        auto_installable=True)

        self._add_check("spaCy English model",
                        "Named entity recognition (people, places, concepts).",
                        _check_spacy_model(),
                        auto_installable=True)

        # AI model backend — recommend MLX on Apple Silicon, Ollama elsewhere
        apple_silicon = _is_apple_silicon()
        mlx_ok = _check_mlx()
        ollama_installed = _check_ollama_installed()
        ollama_running = _check_ollama_running() if ollama_installed else False
        ollama_model = _check_ollama_model() if ollama_running else False

        if apple_silicon:
            self._check_lo.addWidget(make_h_rule())
            self._check_lo.addWidget(make_section_label(
                "AI Model — Apple Silicon Detected"
            ))
            self._check_lo.addWidget(QLabel(
                "Your Mac has an Apple Silicon chip! MLX runs AI models "
                "natively on your hardware — faster and more memory-efficient "
                "than Ollama. We recommend MLX, but Ollama works too."
            ))

            self._add_check("MLX (recommended for your Mac)",
                            "Apple's native AI framework. Runs models directly "
                            "on your chip — no separate server needed. "
                            "We can install it automatically.",
                            mlx_ok,
                            auto_installable=True)

            self._check_lo.addWidget(make_section_label(
                "Alternative: Ollama"
            ))
            self._check_lo.addWidget(QLabel(
                "Ollama also works on Apple Silicon. Use it if you prefer, "
                "or if you already have it installed with models downloaded."
            ))
        else:
            self._check_lo.addWidget(make_h_rule())
            self._check_lo.addWidget(make_section_label("AI Model"))

        self._add_check("Ollama installed",
                        "Ollama is a free app that runs AI models locally on "
                        "your computer — like having a private AI that never "
                        "sends data anywhere. Install it like any other app."
                        + (" (Optional if using MLX above.)" if apple_silicon and mlx_ok else ""),
                        ollama_installed,
                        auto_installable=False,
                        help_url="https://ollama.com/download")

        self._add_check("Ollama running",
                        "Ollama runs quietly in the background, like Dropbox "
                        "or Spotify. It starts automatically after install, or "
                        "you can open it from Applications.",
                        ollama_running,
                        auto_installable=ollama_installed)

        self._add_check("AI model downloaded",
                        "The actual AI model (llama3.1:8b, ~4.9 GB). Think of "
                        "Ollama as the player and this as the album — you need "
                        "both. We can download it for you automatically.",
                        ollama_model,
                        auto_installable=ollama_running)

        # Optional
        self._check_lo.addWidget(make_h_rule())
        self._check_lo.addWidget(make_section_label("Optional (not required for basic use)"))

        self._add_check("File text extraction (DOCX, PDF)",
                        "Extracts text from uploaded documents so students who "
                        "submit Word or PDF files are included in the analysis. "
                        "Without this, file uploads appear as blank submissions.",
                        _check_file_extraction(),
                        auto_installable=True)

        whisper_ok = _check_whisper()
        whisper_binary = _check_whisper_binary_only() if not whisper_ok else False
        if whisper_binary and not whisper_ok:
            # Binary found but model missing — give specific guidance
            whisper_desc = (
                "whisper.cpp binary found but no GGML model file located. "
                "Download a model with: cd ~/whisper.cpp && "
                "bash models/download-ggml-model.sh base  "
                "— or we can install faster-whisper (Python fallback) automatically."
            )
        else:
            whisper_desc = (
                "For transcribing audio/video student submissions. "
                "Only needed if students submit voice memos or videos. "
                "Runs locally — no audio leaves your machine. "
                "We can install faster-whisper automatically."
            )
        self._add_check("Audio transcription (Whisper)",
                        whisper_desc,
                        whisper_ok,
                        auto_installable=True,
                        optional=True)

        self._add_check("Handwriting transcription (Vision AI)",
                        "For reading handwritten notes submitted as photos. "
                        "Requires a vision model in Ollama (e.g. llava or "
                        "llama3.2-vision). This is SLOW (30-60 sec per image) "
                        "and the transcription WILL contain errors — you'll be "
                        "asked to verify each transcription before it enters "
                        "the analysis.",
                        _check_vision_model(),
                        auto_installable=False,
                        optional=True)

        self._check_lo.addStretch()

        # Update install button
        missing_auto = sum(
            1 for c in self._checks.values()
            if not c["ok"] and c["auto"] and not c.get("optional")
        )
        if missing_auto > 0:
            self._install_btn.setEnabled(True)
            self._install_btn.setText(
                f"Install {missing_auto} Missing Component{'s' if missing_auto != 1 else ''}"
            )
        else:
            all_ok = all(c["ok"] for c in self._checks.values() if not c.get("optional"))
            if all_ok:
                self._install_btn.setText("Everything is ready!")
                self._install_btn.setEnabled(False)
            else:
                self._install_btn.setText("Some items need manual setup (see below)")
                self._install_btn.setEnabled(False)

    def _add_check(self, name: str, description: str, ok: bool,
                   auto_installable: bool = False, help_url: str = "",
                   optional: bool = False):
        """Add a dependency check row to the list."""
        pane = make_content_pane(f"check_{name.replace(' ', '_')[:20]}")
        plo = QHBoxLayout(pane)
        plo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        plo.setSpacing(SPACING_SM)

        # Status icon
        if ok:
            icon = QLabel("✓")
            icon.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(18)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
        else:
            icon = QLabel("○" if optional else "✗")
            color = PHOSPHOR_DIM if optional else BURN_RED
            icon.setStyleSheet(
                f"color: {color}; font-size: {px(18)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
        icon.setFixedWidth(24)
        plo.addWidget(icon)

        # Text
        text_lo = QVBoxLayout()
        text_lo.setSpacing(0)
        name_lbl = QLabel(name)
        name_color = PHOSPHOR_HOT if ok else (PHOSPHOR_DIM if optional else PHOSPHOR_MID)
        name_lbl.setStyleSheet(
            f"color: {name_color}; font-size: {px(13)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        text_lo.addWidget(name_lbl)

        desc_lbl = QLabel(description)
        desc_lbl.setWordWrap(True)
        desc_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        text_lo.addWidget(desc_lbl)

        if not ok and help_url:
            link_lbl = QLabel(f'<a href="{help_url}" style="color: {AMBER_BTN};">'
                              f'Download →</a>')
            link_lbl.setOpenExternalLinks(True)
            link_lbl.setStyleSheet("background: transparent; border: none;")
            text_lo.addWidget(link_lbl)

        plo.addLayout(text_lo, 1)

        self._check_lo.addWidget(pane)
        self._checks[name] = {"ok": ok, "auto": auto_installable, "optional": optional}

    def _install_missing(self):
        """Install auto-installable missing components sequentially."""
        self._install_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._install_queue = []

        if not self._checks.get("Python analysis packages", {}).get("ok"):
            self._install_queue.append("pip_deps")
        if not self._checks.get("spaCy English model", {}).get("ok"):
            self._install_queue.append("spacy_model")
        if not self._checks.get("MLX (recommended for your Mac)", {}).get("ok") and _is_apple_silicon():
            self._install_queue.append("mlx_install")
        if (self._checks.get("Ollama installed", {}).get("ok")
                and not self._checks.get("Ollama running", {}).get("ok")):
            self._install_queue.append("ollama_serve")
        if (self._checks.get("Ollama running", {}).get("ok")
                and not self._checks.get("AI model downloaded", {}).get("ok")):
            self._install_queue.append("ollama_pull")
        # If Ollama was just started, model pull may also be needed
        if ("ollama_serve" in self._install_queue
                and not self._checks.get("AI model downloaded", {}).get("ok")):
            self._install_queue.append("ollama_pull")

        self._run_next_install()

    def _run_next_install(self):
        if not self._install_queue:
            self._progress_bar.setVisible(False)
            self._progress_label.setText("Done! Re-checking...")
            self._run_checks()
            return

        task = self._install_queue.pop(0)
        self._worker = _InstallerWorker(task)
        self._worker.progress.connect(self._on_install_progress)
        self._worker.finished.connect(self._on_install_finished)
        self._worker.start()

    def _on_install_progress(self, msg: str):
        self._progress_label.setText(msg)

    def _on_install_finished(self, success: bool, msg: str):
        if success:
            self._progress_label.setText(f"✓ {msg}")
        else:
            self._progress_label.setText(f"✗ {msg}")
            log.warning("Install step failed: %s", msg)
        # Continue with next item regardless
        self._run_next_install()
