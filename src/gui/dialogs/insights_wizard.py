"""
Insights Engine Setup Wizard.

Multi-page dialog that walks teachers through configuring the AI
analysis backend.  Triggered on first use of Generate Insights,
or from Settings > Reconfigure.

Pages:
  0. School AI Access — does your school provide AI with a privacy agreement?
  1. Your Setup — hardware detection + recommended configuration
  2. Getting Ready — install models, test, done

The browser-handoff export is always available regardless of wizard
configuration — it's a feature of the insights panel, not a backend
choice.  This wizard configures the *automated* pipeline backend.
"""

import logging
import subprocess
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QLineEdit, QStackedWidget, QProgressBar,
    QScrollArea, QWidget, QApplication,
)
from PySide6.QtCore import Qt, Signal, QThread

from gui.styles import (
    px,
    SPACING_XS, SPACING_SM, SPACING_MD, SPACING_LG,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM, PHOSPHOR_GLOW,
    TERM_GREEN, BURN_RED, STATUS_WARN,
    BG_VOID, BG_INSET,
    BORDER_DARK, BORDER_AMBER, AMBER_BTN, ROSE_ACCENT,
    PANE_BG_GRADIENT,
    make_section_label, make_h_rule, make_content_pane,
)

log = logging.getLogger("autograder.insights_wizard")


# ---------------------------------------------------------------------------
# Model availability helpers
# ---------------------------------------------------------------------------

def _detect_available_models() -> dict:
    """Check which AI models are already installed."""
    from insights.llm_backend import (
        check_ollama, check_ollama_model, check_mlx,
    )
    info = {
        "ollama_running": False,
        "has_gemma_12b": False,
        "has_gemma_27b": False,
        "mlx_available": False,
    }
    if check_ollama():
        info["ollama_running"] = True
        info["has_gemma_12b"] = check_ollama_model("gemma3:12b")
        info["has_gemma_27b"] = check_ollama_model("gemma3:27b")
    info["mlx_available"] = check_mlx()
    return info


# ---------------------------------------------------------------------------
# Shared helpers — match conventions from setup_dialog / settings_panel
# ---------------------------------------------------------------------------

def _make_scanline_sep() -> QFrame:
    """Amber CRT scanline — matches setup_dialog.py pattern."""
    sep = QFrame()
    sep.setFixedHeight(2)
    sep.setStyleSheet("""
        QFrame {
            background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0.00 rgba(240,168,48, 0),
                stop:0.15 rgba(240,168,48, 0.25),
                stop:0.40 rgba(240,168,48, 0.70),
                stop:0.50 rgba(255,200,80, 1.00),
                stop:0.60 rgba(240,168,48, 0.70),
                stop:0.85 rgba(240,168,48, 0.25),
                stop:1.00 rgba(240,168,48, 0));
            border: none;
        }
    """)
    return sep


def _field_label(text: str) -> QLabel:
    """Uppercase muted field label — matches settings_panel pattern."""
    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px; font-weight: 500;"
        f" letter-spacing: 0.8px; background: transparent; border: none;"
        f" text-transform: uppercase;"
    )
    return lbl


def _body_text(text: str) -> QLabel:
    """Wrapping body text."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet(
        f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
        f" background: transparent; border: none;"
    )
    return lbl


# Button factory — inline QSS like setup_dialog for reliable rendering
_BTN_BG  = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #201A0A,stop:1 #181205)"
_BTN_HOV = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2A220E,stop:1 #1E1808)"
_BTN_PRE = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #181205,stop:1 #131003)"


def _wiz_btn(text: str, accent_hex: str) -> QPushButton:
    """Button with explicit inline QSS — matches setup_dialog pattern."""
    r = int(accent_hex[1:3], 16)
    g = int(accent_hex[3:5], 16)
    b = int(accent_hex[5:7], 16)
    bdr = f"rgba({r},{g},{b}, 0.50)"
    bdr_hot = f"rgba({r},{g},{b}, 0.90)"
    btn = QPushButton(text)
    btn.setStyleSheet(f"""
        QPushButton {{
            background: {_BTN_BG};
            color: {accent_hex};
            border: 1px solid {bdr};
            border-radius: 4px;
            padding: 6px 16px;
            font-weight: 600;
            font-size: {px(13)}px;
        }}
        QPushButton:hover {{
            background: {_BTN_HOV};
            border: 1px solid {bdr_hot};
        }}
        QPushButton:pressed {{
            background: {_BTN_PRE};
            padding-top: 7px; padding-bottom: 5px;
        }}
        QPushButton:disabled {{
            color: rgba({r},{g},{b}, 0.30);
            border-color: rgba({r},{g},{b}, 0.20);
        }}
    """)
    btn.setFixedHeight(px(32))
    return btn


_INPUT_QSS = (
    f"QLineEdit {{"
    f" background: {BG_INSET};"
    f" border: 1px solid {BORDER_DARK};"
    f" border-radius: 4px;"
    f" padding: 4px 8px;"
    f" color: {PHOSPHOR_HOT};"
    f" font-size: {px(13)}px;"
    f" min-height: {px(26)}px;"
    f" selection-background-color: {PHOSPHOR_GLOW};"
    f"}}"
    f"QLineEdit:focus {{"
    f" border-color: {PHOSPHOR_HOT};"
    f"}}"
    f"QLineEdit::placeholder {{"
    f" color: {PHOSPHOR_DIM};"
    f"}}"
)

# Scrollbar styling to match amber theme (from settings_panel pattern)
_SCROLL_QSS = (
    f"QScrollBar:vertical {{"
    f" background: {BG_VOID}; width: 8px; border: none;"
    f"}}"
    f"QScrollBar::handle:vertical {{"
    f" background: {BORDER_AMBER}; border-radius: 4px; min-height: 20px;"
    f"}}"
    f"QScrollBar::handle:vertical:hover {{ background: {PHOSPHOR_MID}; }}"
    f"QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{"
    f" height: 0; }}"
    f"QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{"
    f" background: none; }}"
)


# ---------------------------------------------------------------------------
# Selectable option card
# ---------------------------------------------------------------------------

# Gradient backgrounds for option cards — glow emanates from left edge.
# Base colors must be clearly distinct from BG_INSET (#0E0A02) so cards
# are visually identifiable. BG_PANEL (#130E04) for rest, BG_CARD (#1C1508) for hover.
_OPT_REST_BG = (
    "qradialgradient(cx:-0.1,cy:0.5,radius:1.3,"
    "stop:0.00 rgba(160,100,12,60),stop:0.35 #130E04,stop:1.00 #0E0A03)"
)
_OPT_HOVER_BG = (
    "qradialgradient(cx:-0.1,cy:0.5,radius:1.1,"
    "stop:0.00 rgba(220,140,24,100),stop:0.35 #1C1508,stop:1.00 #130E04)"
)
_OPT_ACTIVE_BG = (
    "qradialgradient(cx:-0.05,cy:0.5,radius:0.85,"
    "stop:0.00 rgba(240,168,48,120),stop:0.30 #2A1E08,stop:0.70 #1C1508,"
    "stop:1.00 #130E04)"
)


class _OptionCard(QFrame):
    """Clickable card with radio dot, gradient fill, and hover effects."""
    clicked = Signal()

    def __init__(self, title: str, description: str, idx: int, parent=None):
        super().__init__(parent)
        self._selected = False
        name = f"wizOpt{idx}"
        self.setObjectName(name)
        self._obj_name = name
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lo = QHBoxLayout(self)
        lo.setContentsMargins(
            SPACING_SM + 2, SPACING_SM + 2, SPACING_SM + 2, SPACING_SM + 2,
        )
        lo.setSpacing(SPACING_SM)

        # Radio dot
        self._dot = QLabel("\u25cb")
        self._dot.setFixedWidth(px(18))
        self._dot.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
        )
        lo.addWidget(self._dot, 0, Qt.AlignmentFlag.AlignTop)

        text_lo = QVBoxLayout()
        text_lo.setSpacing(2)
        self._title_lbl = QLabel(title)
        self._title_lbl.setWordWrap(True)
        text_lo.addWidget(self._title_lbl)

        self._desc_lbl = QLabel(description)
        self._desc_lbl.setWordWrap(True)
        text_lo.addWidget(self._desc_lbl)
        lo.addLayout(text_lo, 1)

        self._apply_style()

    @property
    def selected(self) -> bool:
        return self._selected

    def set_selected(self, sel: bool):
        self._selected = sel
        self._apply_style()

    def _apply_style(self):
        n = self._obj_name
        _lbl_bg = "background: transparent; border: none;"
        if self._selected:
            self.setStyleSheet(
                f"QFrame#{n} {{"
                f" background: {_OPT_ACTIVE_BG};"
                f" border: 1px solid {PHOSPHOR_MID};"
                f" border-left: 3px solid {PHOSPHOR_HOT};"
                f" border-radius: 6px;"
                f"}}"
            )
            self._dot.setText("\u25cf")
            self._dot.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px; {_lbl_bg}"
            )
            self._title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" font-weight: 600; {_lbl_bg}"
            )
            self._desc_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(10)}px; {_lbl_bg}"
            )
        else:
            self.setStyleSheet(
                f"QFrame#{n} {{"
                f" background: {_OPT_REST_BG};"
                f" border: 1px solid {BORDER_DARK};"
                f" border-radius: 6px;"
                f"}}"
                f"QFrame#{n}:hover {{"
                f" background: {_OPT_HOVER_BG};"
                f" border-color: {BORDER_AMBER};"
                f"}}"
            )
            self._dot.setText("\u25cb")
            self._dot.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(14)}px; {_lbl_bg}"
            )
            self._title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" font-weight: 600; {_lbl_bg}"
            )
            self._desc_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; {_lbl_bg}"
            )

    def enterEvent(self, event):
        if not self._selected:
            self._title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" font-weight: 600; background: transparent; border: none;"
            )
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self._selected:
            self._title_lbl.setStyleSheet(
                f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                f" font-weight: 600; background: transparent; border: none;"
            )
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.clicked.emit()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# Copyable IT blurb
# ---------------------------------------------------------------------------

_IT_BLURB = (
    "Hi, I\u2019m setting up an educational analytics tool and have two "
    "quick questions: (1) Does our school have a Data Processing Agreement "
    "with any AI providers that would cover analyzing student writing? "
    "(2) If so, is there an institutional API key and server URL I could "
    "use to connect? Thank you!"
)


_blurb_counter = 0


class _CopyableBlurb(QFrame):
    """Styled text block with a copy button."""

    def __init__(self, label: str, text: str, parent=None):
        super().__init__(parent)
        global _blurb_counter
        _blurb_counter += 1
        name = f"copyBlurb{_blurb_counter}"
        self.setObjectName(name)
        self.setStyleSheet(
            f"QFrame#{name} {{"
            f" background: {BG_INSET};"
            f" border: 1px solid {BORDER_DARK};"
            f" border-radius: 6px;"
            f"}}"
        )
        lo = QVBoxLayout(self)
        lo.setContentsMargins(SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM)
        lo.setSpacing(SPACING_XS)

        hdr_row = QHBoxLayout()
        hdr_row.setSpacing(SPACING_XS)
        hdr = QLabel(label.upper())
        hdr.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px; font-weight: bold;"
            f" letter-spacing: 1.5px; background: transparent; border: none;"
        )
        hdr_row.addWidget(hdr, 1)

        copy_btn = QPushButton("\u29c9")  # ⧉ overlapping squares glyph
        copy_btn.setToolTip("Copy to clipboard")
        copy_btn.setFixedSize(px(22), px(22))
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                color: {PHOSPHOR_DIM};
                font-size: {px(14)}px;
                padding: 0;
            }}
            QPushButton:hover {{ color: {PHOSPHOR_HOT}; }}
            QPushButton:pressed {{ color: {PHOSPHOR_MID}; }}
        """)
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        hdr_row.addWidget(copy_btn)
        lo.addLayout(hdr_row)

        body = QLabel(f"\u201c{text}\u201d")
        body.setWordWrap(True)
        body.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none; font-style: italic;"
        )
        lo.addWidget(body)


# ---------------------------------------------------------------------------
# Background worker for install + test
# ---------------------------------------------------------------------------

class _SetupWorker(QThread):
    """Runs setup tasks sequentially in a background thread."""
    progress = Signal(str)     # step_name
    step_done = Signal(str, bool)  # step_name, success
    all_done = Signal(bool)    # overall success

    def __init__(self, tasks: list, parent=None):
        super().__init__(parent)
        self._tasks = tasks

    def run(self):
        all_ok = True
        for task in self._tasks:
            name = task["name"]
            self.progress.emit(name)
            try:
                ok = task["fn"]()
                self.step_done.emit(name, ok)
                if not ok:
                    all_ok = False
            except Exception as e:
                log.warning("Setup task '%s' failed: %s", name, e)
                self.step_done.emit(name, False)
                all_ok = False
        self.all_done.emit(all_ok)


def _task_install_pip_deps() -> bool:
    """Install missing Python analysis packages."""
    from gui.dialogs.insights_setup_dialog import (
        _check_vader, _check_sklearn, _check_sentence_transformers,
        _check_file_extraction, _is_externally_managed,
    )
    import sys

    packages = []
    if not _check_vader():
        packages.append("vaderSentiment")
    if not _check_sklearn():
        packages.append("scikit-learn")
    if not _check_sentence_transformers():
        packages.append("sentence-transformers")
    if not _check_file_extraction():
        packages.extend(["python-docx", "pdfminer.six"])
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
        return True

    cmd = [sys.executable, "-m", "pip", "install", "--quiet"]
    if _is_externally_managed():
        cmd.append("--break-system-packages")
    cmd.extend(packages)
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    return result.returncode == 0


def _task_install_spacy() -> bool:
    from gui.dialogs.insights_setup_dialog import _check_spacy_model
    if _check_spacy_model():
        return True
    import sys
    result = subprocess.run(
        [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
        capture_output=True, text=True, timeout=120,
    )
    return result.returncode == 0


def _task_ensure_ollama() -> bool:
    from insights.llm_backend import check_ollama, reset_ollama_cache
    reset_ollama_cache()
    return check_ollama()


def _make_task_pull_model(model: str):
    """Factory: callable that pulls an Ollama model."""
    def _pull() -> bool:
        from insights.llm_backend import check_ollama_model
        if check_ollama_model(model):
            return True  # already have it
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/pull",
                json={"name": model, "stream": False},
                timeout=1800,
            )
            return r.status_code == 200
        except Exception:
            return False
    return _pull


def _make_task_test_inference(model: str):
    """Factory: callable that tests inference on the given model."""
    def _test() -> bool:
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": "Say hello in one word."}
                    ],
                    "stream": False,
                    "options": {"num_predict": 20},
                },
                timeout=120,
            )
            if r.status_code == 200:
                return len(r.json().get("message", {}).get("content", "")) > 0
        except Exception:
            pass
        return False
    return _test


def _task_test_cloud(url: str, key: str, model: str) -> bool:
    """Test a cloud API connection."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=key, base_url=url)
        r = client.chat.completions.create(
            model=model,
            max_tokens=20,
            messages=[{"role": "user", "content": "Say hello in one word."}],
        )
        return bool(r.choices[0].message.content)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# The Wizard
# ---------------------------------------------------------------------------

class InsightsWizard(QDialog):
    """Multi-page setup wizard for the Insights Engine AI backend.

    Pages:
      0 — School AI Access (institutional DPA question)
      1 — Your Setup (hardware detection + config)
      2 — Getting Ready (install + test)
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Insights Engine Setup")
        self.setMinimumSize(720, 540)
        self.setModal(True)
        self.setObjectName("insightsWizard")
        # Use QPalette for dialog background — inline QSS on QDialog cascades
        # into children and overrides QPushButton gradient fills.
        from PySide6.QtGui import QPalette, QColor
        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Window, QColor(BG_VOID))
        self.setPalette(pal)

        self._choice = ""  # "institutional", "local", "unsure"
        from insights.llm_backend import detect_hardware
        self._hw = detect_hardware()
        self._models: dict = {}
        self._recommended_model = ""
        self._worker: Optional[_SetupWorker] = None

        self._build_ui()
        self._load_existing_settings()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """Cancel worker if still running."""
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().closeEvent(event)

    def reject(self):
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
        super().reject()

    # ------------------------------------------------------------------
    # Pre-populate from existing settings (for re-launch from Settings)
    # ------------------------------------------------------------------

    def _load_existing_settings(self):
        """If settings already exist, pre-populate fields."""
        from settings import load_settings
        s = load_settings()

        url = s.get("insights_cloud_url", "")
        key = s.get("insights_cloud_key", "")
        privacy = s.get("insights_cloud_privacy", "")

        if privacy == "institutional_dpa" and url:
            self._inst_url_edit.setText(url)
            self._inst_key_edit.setText(key)
            self._inst_model_edit.setText(s.get("insights_cloud_model", ""))
            self._on_card_clicked(self._card_inst)
        elif privacy == "anonymized_only" and key:
            self._on_card_clicked(self._card_local)
            self._enhance_toggle.setChecked(True)
            self._enhance_key_edit.setText(key)
            self._enhance_model_edit.setText(s.get("insights_cloud_model", ""))

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Title bar
        title_bar = QFrame()
        title_bar.setObjectName("wizTitleBar")
        title_bar.setStyleSheet(
            f"QFrame#wizTitleBar {{ background: {BG_VOID}; border: none; }}"
        )
        tb_lo = QHBoxLayout(title_bar)
        tb_lo.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_SM)

        title = QLabel("INSIGHTS ENGINE SETUP")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(16)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        tb_lo.addWidget(title)
        tb_lo.addStretch()

        self._page_indicator = QLabel("1 / 3")
        self._page_indicator.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        tb_lo.addWidget(self._page_indicator)
        root.addWidget(title_bar)
        root.addWidget(make_h_rule())

        # Pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_page_access())
        self._stack.addWidget(self._build_page_config())
        self._stack.addWidget(self._build_page_install())
        root.addWidget(self._stack, 1)

        # Footer
        root.addWidget(_make_scanline_sep())

        footer = QFrame()
        footer.setObjectName("wizFooter")
        footer.setStyleSheet(
            f"QFrame#wizFooter {{ background: {BG_VOID}; border: none; }}"
        )
        f_lo = QHBoxLayout(footer)
        f_lo.setContentsMargins(SPACING_LG, SPACING_SM, SPACING_LG, SPACING_SM)

        self._back_btn = _wiz_btn("\u2190  Back", AMBER_BTN)
        self._back_btn.clicked.connect(self._on_back)
        self._back_btn.setVisible(False)
        f_lo.addWidget(self._back_btn)

        f_lo.addStretch()

        self._skip_btn = _wiz_btn("Skip for Now", AMBER_BTN)
        self._skip_btn.clicked.connect(self.reject)
        f_lo.addWidget(self._skip_btn)

        f_lo.addSpacing(SPACING_SM)

        self._next_btn = _wiz_btn("Next  \u2192", ROSE_ACCENT)
        self._next_btn.clicked.connect(self._on_next)
        self._next_btn.setEnabled(False)
        f_lo.addWidget(self._next_btn)

        root.addWidget(footer)

    # ------------------------------------------------------------------
    # Page 0: School AI Access
    # ------------------------------------------------------------------

    def _build_page_access(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizPage0")
        page.setStyleSheet(f"QWidget#wizPage0 {{ background: {BG_VOID}; }}")

        outer = QVBoxLayout(page)
        outer.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        outer.setSpacing(SPACING_SM)

        outer.addWidget(make_section_label(
            "Does your school provide AI access?"
        ))
        outer.addWidget(make_h_rule())
        outer.addSpacing(SPACING_XS)

        # ── Two-column: dark inset selector (left) + content pane (right) ──
        cols = QHBoxLayout()
        cols.setSpacing(SPACING_MD)

        # ── LEFT: selector in a recessed terminal surface ──
        selector = QFrame()
        selector.setObjectName("wizSelector")
        selector.setStyleSheet(
            f"QFrame#wizSelector {{"
            f" background: {BG_INSET};"
            f" border: 1px solid {BORDER_DARK};"
            f" border-radius: 8px;"
            f"}}"
        )
        sel_lo = QVBoxLayout(selector)
        sel_lo.setContentsMargins(
            SPACING_SM + 2, SPACING_MD, SPACING_SM + 2, SPACING_MD,
        )
        sel_lo.setSpacing(SPACING_SM)

        self._card_inst = _OptionCard(
            "School AI service",
            "Your school has a data agreement with an AI provider",
            idx=0,
        )
        self._card_unsure = _OptionCard(
            "I\u2019m not sure",
            "Set up local now, get IT info for later",
            idx=1,
        )
        self._card_local = _OptionCard(
            "Keep data on my computer",
            "Runs locally \u2014 requires 16 GB RAM",
            idx=2,
        )

        for card in (self._card_inst, self._card_unsure, self._card_local):
            sel_lo.addWidget(card)
            card.clicked.connect(lambda c=card: self._on_card_clicked(c))

        # ── System status panel — hardware + existing config ──
        status_pane = QFrame()
        status_pane.setObjectName("wizStatus")
        status_pane.setStyleSheet(
            f"QFrame#wizStatus {{"
            f" background: qradialgradient(cx:0.5,cy:0.3,radius:1.0,"
            f"   stop:0.00 rgba(10,8,0,255),"
            f"   stop:0.60 rgba(8,6,0,255),"
            f"   stop:1.00 rgba(6,5,0,255));"
            f" border: 1px solid {BORDER_DARK};"
            f" border-top-color: {BORDER_AMBER};"
            f" border-radius: 6px;"
            f"}}"
        )
        st_lo = QVBoxLayout(status_pane)
        st_lo.setContentsMargins(
            SPACING_SM, SPACING_SM, SPACING_SM, SPACING_SM,
        )
        st_lo.setSpacing(SPACING_XS)

        st_hdr = QLabel("SYSTEM STATUS")
        st_hdr.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
            f" font-weight: bold; letter-spacing: 1.5px;"
            f" background: transparent; border: none;"
        )
        st_lo.addWidget(st_hdr)

        # Build status lines
        hw = self._hw
        lines = []
        if hw.get("apple_silicon"):
            lines.append(("CHIP", "Apple Silicon", PHOSPHOR_DIM))
        lines.append(("RAM", f"{hw.get('ram_gb', 0):.0f} GB", PHOSPHOR_DIM))

        # Single "LOCAL AI" line — combines hardware check + server status
        from insights.llm_backend import check_ollama
        try:
            ollama_ok = check_ollama()
        except Exception:
            ollama_ok = False

        if not hw.get("can_run_12b"):
            lines.append(("LOCAL AI", "\u2717 Needs 16 GB RAM", BURN_RED))
        elif ollama_ok:
            if hw.get("can_run_27b"):
                lines.append(("LOCAL AI", "\u2713 Ready (full)", TERM_GREEN))
            else:
                lines.append(("LOCAL AI", "\u2713 Ready", TERM_GREEN))
        else:
            lines.append(("LOCAL AI", "\u2014 Needs setup", PHOSPHOR_MID))

        # Check existing cloud config
        from settings import load_settings
        _s = load_settings()
        _cloud_url = _s.get("insights_cloud_url", "")
        _cloud_priv = _s.get("insights_cloud_privacy", "")
        if _cloud_url and _cloud_priv == "institutional_dpa":
            lines.append(("CLOUD API", "\u2713 Configured", TERM_GREEN))
        elif _cloud_url:
            lines.append(("CLOUD API", "\u2713 Enhancement", TERM_GREEN))
        else:
            lines.append(("CLOUD API", "\u2014 None", PHOSPHOR_DIM))

        for key, val, color in lines:
            row = QHBoxLayout()
            row.setSpacing(SPACING_XS)
            k_lbl = QLabel(key)
            k_lbl.setStyleSheet(
                f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
                f" background: transparent; border: none;"
            )
            k_lbl.setFixedWidth(px(58))
            row.addWidget(k_lbl)

            v_lbl = QLabel(val)
            v_lbl.setStyleSheet(
                f"color: {color}; font-size: {px(9)}px;"
                f" background: transparent; border: none;"
            )
            row.addWidget(v_lbl, 1)
            st_lo.addLayout(row)

        sel_lo.addWidget(status_pane, 1)

        selector.setFixedWidth(px(230))
        cols.addWidget(selector)

        # ── RIGHT: detail in a content pane (amber-topped surface) ──
        detail_pane = make_content_pane("wizDetailPane")
        dp_lo = QVBoxLayout(detail_pane)
        dp_lo.setContentsMargins(SPACING_MD, SPACING_MD, SPACING_MD, SPACING_MD)
        dp_lo.setSpacing(0)

        self._detail_stack = QStackedWidget()
        self._detail_stack.setObjectName("wizDetailStack")
        self._detail_stack.setStyleSheet(
            "QStackedWidget#wizDetailStack { background: transparent; }"
        )

        # Detail 0: empty prompt
        empty = QWidget()
        empty.setObjectName("wizEmpty")
        empty.setStyleSheet("QWidget#wizEmpty { background: transparent; }")
        e_lo = QVBoxLayout(empty)
        e_lo.setContentsMargins(0, 0, 0, 0)
        hint = QLabel("Select an option on the left\nto see details here.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        e_lo.addStretch()
        e_lo.addWidget(hint)
        e_lo.addStretch()
        self._detail_stack.addWidget(empty)  # 0

        # Detail 1: institutional — API fields
        inst_s = QScrollArea()
        inst_s.setWidgetResizable(True)
        inst_s.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + _SCROLL_QSS
        )
        inst_w = QWidget()
        inst_w.setObjectName("wizInstW")
        inst_w.setStyleSheet("QWidget#wizInstW { background: transparent; }")
        inst_s.setWidget(inst_w)
        id_lo = QVBoxLayout(inst_w)
        id_lo.setContentsMargins(0, 0, 0, 0)
        id_lo.setSpacing(SPACING_SM)

        id_lo.addWidget(make_section_label("School AI connection"))
        id_lo.addWidget(make_h_rule())
        id_lo.addWidget(_body_text(
            "Enter connection details from IT. If you don\u2019t "
            "have them yet, click Next \u2014 we\u2019ll set up local "
            "analysis and you can add this later."
        ))
        id_lo.addWidget(_field_label("API Server URL"))
        self._inst_url_edit = QLineEdit()
        self._inst_url_edit.setPlaceholderText(
            "e.g. https://your-school.openai.azure.com/v1"
        )
        self._inst_url_edit.setStyleSheet(_INPUT_QSS)
        id_lo.addWidget(self._inst_url_edit)

        id_lo.addWidget(_field_label("API Key"))
        self._inst_key_edit = QLineEdit()
        self._inst_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._inst_key_edit.setPlaceholderText("Paste API key from IT")
        self._inst_key_edit.setStyleSheet(_INPUT_QSS)
        id_lo.addWidget(self._inst_key_edit)

        id_lo.addWidget(_field_label("Model Name"))
        self._inst_model_edit = QLineEdit()
        self._inst_model_edit.setPlaceholderText(
            "e.g. gpt-4o, claude-sonnet-4-20250514"
        )
        self._inst_model_edit.setStyleSheet(_INPUT_QSS)
        id_lo.addWidget(self._inst_model_edit)

        id_lo.addStretch()
        self._detail_stack.addWidget(inst_s)  # 1

        # Detail 2: unsure — guidance
        unsure_s = QScrollArea()
        unsure_s.setWidgetResizable(True)
        unsure_s.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + _SCROLL_QSS
        )
        unsure_w = QWidget()
        unsure_w.setObjectName("wizUnsureW")
        unsure_w.setStyleSheet("QWidget#wizUnsureW { background: transparent; }")
        unsure_s.setWidget(unsure_w)
        ud_lo = QVBoxLayout(unsure_w)
        ud_lo.setContentsMargins(0, 0, 0, 0)
        ud_lo.setSpacing(SPACING_SM)

        ud_lo.addWidget(make_section_label("Ask your IT department"))
        ud_lo.addWidget(make_h_rule())
        ud_lo.addWidget(_body_text(
            "Your IT department will know in one email. Here\u2019s "
            "something you can send them:"
        ))
        ud_lo.addSpacing(SPACING_XS)
        ud_lo.addWidget(_CopyableBlurb(
            "Something you can send to IT", _IT_BLURB,
        ))
        ud_lo.addSpacing(SPACING_XS)
        ud_lo.addWidget(_body_text(
            "We\u2019ll set up local analysis for now. You can add "
            "institutional access anytime in Settings."
        ))
        ud_lo.addStretch()
        self._detail_stack.addWidget(unsure_s)  # 2

        # Detail 3: local — privacy confirmation
        local_s = QScrollArea()
        local_s.setWidgetResizable(True)
        local_s.setStyleSheet(
            "QScrollArea { border: none; background: transparent; }"
            + _SCROLL_QSS
        )
        local_w = QWidget()
        local_w.setObjectName("wizLocalW")
        local_w.setStyleSheet("QWidget#wizLocalW { background: transparent; }")
        local_s.setWidget(local_w)
        lw_lo = QVBoxLayout(local_w)
        lw_lo.setContentsMargins(0, 0, 0, 0)
        lw_lo.setSpacing(SPACING_SM)

        lw_lo.addWidget(make_section_label("Local analysis"))
        lw_lo.addWidget(make_h_rule())
        lw_lo.addWidget(_body_text(
            "All analysis will run on your computer using a "
            "local AI model. Student submissions never leave "
            "your machine."
        ))
        lw_lo.addSpacing(SPACING_SM)
        lw_lo.addWidget(_body_text(
            "On the next page we\u2019ll check your hardware "
            "and recommend the best model for your computer."
        ))
        lw_lo.addStretch()
        self._detail_stack.addWidget(local_s)  # 3

        dp_lo.addWidget(self._detail_stack)
        cols.addWidget(detail_pane, 1)
        outer.addLayout(cols, 1)

        return page

    # ------------------------------------------------------------------
    # Page 1: Your Setup (hardware + config)
    # ------------------------------------------------------------------

    def _build_page_config(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizPage1")
        page.setStyleSheet(f"QWidget#wizPage1 {{ background: {BG_VOID}; }}")

        lo = QVBoxLayout(page)
        lo.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label("Your Computer"))
        lo.addWidget(make_h_rule())

        # Hardware info pane
        hw_pane = make_content_pane("wizHwPane")
        hw_lo = QHBoxLayout(hw_pane)
        hw_lo.setContentsMargins(SPACING_MD, SPACING_XS + 2, SPACING_MD, SPACING_XS + 2)
        hw_lo.setSpacing(SPACING_SM)

        self._hw_icon = QLabel("\u2713")
        self._hw_icon.setFixedWidth(px(24))
        self._hw_icon.setStyleSheet(
            f"color: {TERM_GREEN}; font-size: {px(18)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        hw_lo.addWidget(self._hw_icon)

        hw_text_lo = QVBoxLayout()
        hw_text_lo.setSpacing(0)
        self._hw_title = QLabel(self._hw["description"])
        self._hw_title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        hw_text_lo.addWidget(self._hw_title)

        self._hw_desc = QLabel("Checking capabilities\u2026")
        self._hw_desc.setWordWrap(True)
        self._hw_desc.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        hw_text_lo.addWidget(self._hw_desc)
        hw_lo.addLayout(hw_text_lo, 1)

        lo.addWidget(hw_pane)

        # Recommendation
        lo.addWidget(make_section_label("What We\u2019ll Set Up"))
        lo.addWidget(make_h_rule())

        self._rec_label = QLabel("")
        self._rec_label.setWordWrap(True)
        self._rec_label.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._rec_label)

        # --- Enhancement section — two-column layout (shown only for 12B) ---
        self._enhance_section = QFrame()
        self._enhance_section.setVisible(False)
        self._enhance_section.setStyleSheet("background: transparent;")
        enh_lo = QVBoxLayout(self._enhance_section)
        enh_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        enh_lo.setSpacing(SPACING_XS)

        enh_lo.addWidget(make_section_label("Optional: Cloud Enhancement"))
        enh_lo.addWidget(make_h_rule())

        # Two-column: LEFT = explanation, RIGHT = privacy + controls
        enh_cols = QHBoxLayout()
        enh_cols.setSpacing(SPACING_MD)

        # LEFT — what it is and what it adds
        enh_left = QWidget()
        enh_left.setStyleSheet("background: transparent;")
        el_lo = QVBoxLayout(enh_left)
        el_lo.setContentsMargins(0, 0, 0, 0)
        el_lo.setSpacing(SPACING_XS)
        el_lo.addWidget(_body_text(
            "Local analysis covers the essentials. Cloud enhancement "
            "adds richer interpretation on top of that."
        ))
        el_lo.addSpacing(SPACING_XS)
        el_lo.addWidget(_body_text(
            "What it adds:\n"
            "  \u2022  Deeper read of what class patterns mean\n"
            "  \u2022  More specific next-session suggestions\n"
            "  \u2022  Stronger recognition of multilingual\n"
            "       and diverse writing as strengths"
        ))
        el_lo.addStretch()

        # RIGHT — privacy notice + toggle + fields
        enh_right = QWidget()
        enh_right.setStyleSheet("background: transparent;")
        er_lo = QVBoxLayout(enh_right)
        er_lo.setContentsMargins(0, 0, 0, 0)
        er_lo.setSpacing(SPACING_XS)

        ferpa_pane = make_content_pane("wizFerpaPane")
        fp_lo = QHBoxLayout(ferpa_pane)
        fp_lo.setContentsMargins(SPACING_XS, SPACING_XS, SPACING_XS, SPACING_XS)
        fp_lo.setSpacing(SPACING_XS)
        ferpa_icon = QLabel("\u26a0")
        ferpa_icon.setFixedWidth(px(16))
        ferpa_icon.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        fp_lo.addWidget(ferpa_icon)
        ferpa_text = QLabel(
            "Privacy-safe: only anonymized class-level patterns are "
            "sent \u2014 nothing identifying leaves your computer."
        )
        ferpa_text.setWordWrap(True)
        ferpa_text.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        fp_lo.addWidget(ferpa_text, 1)
        er_lo.addWidget(ferpa_pane)

        er_lo.addSpacing(SPACING_XS)

        from gui.widgets.switch_toggle import SwitchToggle
        self._enhance_toggle = SwitchToggle(
            "Enable cloud enhancement", wrap_width=200,
        )
        self._enhance_toggle.toggled.connect(self._on_enhance_toggled)
        er_lo.addWidget(self._enhance_toggle)

        self._enhance_fields = QFrame()
        self._enhance_fields.setVisible(False)
        self._enhance_fields.setStyleSheet("background: transparent;")
        ef_lo = QVBoxLayout(self._enhance_fields)
        ef_lo.setContentsMargins(0, SPACING_XS, 0, 0)
        ef_lo.setSpacing(SPACING_XS)

        ef_lo.addWidget(_body_text(
            "Create a free account at openrouter.ai, generate an "
            "API key, and paste it below."
        ))
        ef_lo.addWidget(_field_label("OpenRouter API Key"))
        self._enhance_key_edit = QLineEdit()
        self._enhance_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._enhance_key_edit.setPlaceholderText("Paste OpenRouter API key")
        self._enhance_key_edit.setStyleSheet(_INPUT_QSS)
        ef_lo.addWidget(self._enhance_key_edit)

        ef_lo.addWidget(_field_label("Model (optional)"))
        self._enhance_model_edit = QLineEdit()
        self._enhance_model_edit.setPlaceholderText(
            "google/gemma-2-27b-it  (default, ~$0.01/run)"
        )
        self._enhance_model_edit.setStyleSheet(_INPUT_QSS)
        ef_lo.addWidget(self._enhance_model_edit)

        er_lo.addWidget(self._enhance_fields)
        er_lo.addStretch()

        enh_cols.addWidget(enh_left, 1)
        enh_cols.addWidget(enh_right, 1)
        enh_lo.addLayout(enh_cols)
        lo.addWidget(self._enhance_section)

        # --- No-local-capability message ---
        self._no_local_msg = QFrame()
        self._no_local_msg.setVisible(False)
        self._no_local_msg.setStyleSheet("background: transparent;")
        nl_lo = QVBoxLayout(self._no_local_msg)
        nl_lo.setContentsMargins(0, 0, 0, 0)
        nl_lo.addWidget(_body_text(
            "This computer doesn\u2019t have enough memory to run a local "
            "AI model. To use automated analysis, you\u2019ll need to "
            "connect a school-provided AI service.\n\n"
            "In the meantime, the Export to Chatbot button in the Insights "
            "panel lets you copy student submissions into any AI tool you "
            "already have access to \u2014 no setup required."
        ))
        lo.addWidget(self._no_local_msg)

        lo.addStretch()
        return page

    # ------------------------------------------------------------------
    # Page 2: Getting Ready (install + test)
    # ------------------------------------------------------------------

    def _build_page_install(self) -> QWidget:
        page = QWidget()
        page.setObjectName("wizPage2")
        page.setStyleSheet(f"QWidget#wizPage2 {{ background: {BG_VOID}; }}")

        lo = QVBoxLayout(page)
        lo.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_LG)
        lo.setSpacing(SPACING_SM)

        lo.addWidget(make_section_label("Getting Ready"))
        lo.addWidget(make_h_rule())

        self._setup_summary = QLabel("")
        self._setup_summary.setWordWrap(True)
        self._setup_summary.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._setup_summary)
        lo.addSpacing(SPACING_SM)

        # Checklist container
        self._checklist_lo = QVBoxLayout()
        self._checklist_lo.setSpacing(SPACING_XS)
        lo.addLayout(self._checklist_lo)

        lo.addSpacing(SPACING_SM)

        # Progress bar
        self._install_progress = QProgressBar()
        self._install_progress.setRange(0, 0)  # indeterminate
        self._install_progress.setVisible(False)
        self._install_progress.setFixedHeight(px(8))
        self._install_progress.setStyleSheet(
            f"QProgressBar {{ background: {BG_INSET};"
            f" border: 1px solid {BORDER_DARK};"
            f" border-radius: 4px; }}"
            f"QProgressBar::chunk {{ background: {AMBER_BTN};"
            f" border-radius: 3px; }}"
        )
        lo.addWidget(self._install_progress)

        self._install_status = QLabel("")
        self._install_status.setWordWrap(True)
        self._install_status.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._install_status)

        lo.addStretch()

        # "You're all set" banner
        self._done_banner = QFrame()
        self._done_banner.setVisible(False)
        self._done_banner.setObjectName("doneBanner")
        self._done_banner.setStyleSheet(
            f"QFrame#doneBanner {{"
            f" background: {PANE_BG_GRADIENT};"
            f" border: 1px solid {TERM_GREEN};"
            f" border-radius: 8px;"
            f"}}"
        )
        db_lo = QHBoxLayout(self._done_banner)
        db_lo.setContentsMargins(SPACING_MD, SPACING_SM, SPACING_MD, SPACING_SM)

        done_icon = QLabel("\u2713")
        done_icon.setStyleSheet(
            f"color: {TERM_GREEN}; font-size: {px(20)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        done_icon.setFixedWidth(px(28))
        db_lo.addWidget(done_icon)

        self._done_text = QLabel(
            "You\u2019re all set! The analysis engine is ready."
        )
        self._done_text.setStyleSheet(
            f"color: {TERM_GREEN}; font-size: {px(13)}px; font-weight: 600;"
            f" background: transparent; border: none;"
        )
        db_lo.addWidget(self._done_text, 1)
        lo.addWidget(self._done_banner)

        return page

    # ------------------------------------------------------------------
    # Card selection logic (page 0)
    # ------------------------------------------------------------------

    def _on_card_clicked(self, card: _OptionCard):
        cards = (self._card_inst, self._card_unsure, self._card_local)
        for c in cards:
            c.set_selected(c is card)

        if card is self._card_inst:
            self._choice = "institutional"
            self._detail_stack.setCurrentIndex(1)
        elif card is self._card_unsure:
            self._choice = "unsure"
            self._detail_stack.setCurrentIndex(2)
        else:
            self._choice = "local"
            self._detail_stack.setCurrentIndex(3)

        self._next_btn.setEnabled(True)

    # ------------------------------------------------------------------
    # Enhancement toggle
    # ------------------------------------------------------------------

    def _on_enhance_toggled(self, checked: bool):
        self._enhance_fields.setVisible(checked)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _on_next(self):
        current = self._stack.currentIndex()

        if current == 0:
            if (self._choice == "institutional"
                    and self._inst_url_edit.text().strip()
                    and self._inst_key_edit.text().strip()):
                # Has institutional details — skip hardware, go to install
                self._populate_install_page()
                self._stack.setCurrentIndex(2)
            else:
                self._populate_config_page()
                self._stack.setCurrentIndex(1)

        elif current == 1:
            self._populate_install_page()
            self._stack.setCurrentIndex(2)

        elif current == 2:
            self._save_settings()
            self.accept()

        self._update_nav()

    def _on_back(self):
        current = self._stack.currentIndex()

        # Cancel running worker if going back from install page
        if current == 2 and self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)
            self._worker = None
            self._install_progress.setVisible(False)

        if current == 2:
            # If we skipped page 1, go back to page 0
            if (self._choice == "institutional"
                    and self._inst_url_edit.text().strip()
                    and self._inst_key_edit.text().strip()):
                self._stack.setCurrentIndex(0)
            else:
                self._stack.setCurrentIndex(1)
        elif current > 0:
            self._stack.setCurrentIndex(current - 1)

        self._update_nav()

    def _update_nav(self):
        idx = self._stack.currentIndex()
        self._back_btn.setVisible(idx > 0)
        self._page_indicator.setText(f"{idx + 1} / 3")

        if idx == 2:
            self._next_btn.setText("Done")
            self._next_btn.setEnabled(self._done_banner.isVisible())
        elif idx == 1:
            self._next_btn.setText("Set Up  \u2192")
            self._next_btn.setEnabled(True)
        else:
            self._next_btn.setText("Next  \u2192")
            self._next_btn.setEnabled(self._choice != "")

    # ------------------------------------------------------------------
    # Populate config page (page 1)
    # ------------------------------------------------------------------

    def _populate_config_page(self):
        """Fill page 1 based on choice + hardware."""
        self._models = _detect_available_models()
        hw = self._hw
        has_27b = self._models.get("has_gemma_27b", False)
        has_12b = self._models.get("has_gemma_12b", False)

        # Hardware summary
        if hw["can_run_27b"]:
            self._hw_icon.setText("\u2713")
            self._hw_icon.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(18)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            self._hw_desc.setText(
                "This computer can run the full analysis model. "
                "No cloud services needed."
            )
        elif hw["can_run_12b"]:
            self._hw_icon.setText("\u2713")
            self._hw_icon.setStyleSheet(
                f"color: {TERM_GREEN}; font-size: {px(18)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            self._hw_desc.setText(
                "This computer can run the core analysis model. "
                "Optional cloud enhancement available."
            )
        else:
            self._hw_icon.setText("\u2717")
            self._hw_icon.setStyleSheet(
                f"color: {BURN_RED}; font-size: {px(18)}px; font-weight: bold;"
                f" background: transparent; border: none;"
            )
            self._hw_desc.setText(
                "Not enough memory for local AI. You\u2019ll need "
                "institutional AI access or the Export to Chatbot feature."
            )

        # Recommendation
        self._enhance_section.setVisible(False)
        self._no_local_msg.setVisible(False)

        if hw["can_run_27b"]:
            model = "gemma3:27b"
            status = "already installed" if has_27b else "will be downloaded (~17 GB)"
            self._rec_label.setText(
                f"Full analysis model \u2014 {status}.\n\n"
                "This is the best local option for your computer. It "
                "produces rich, detailed analysis \u2014 comparable to "
                "cloud-based tools \u2014 with all student data staying "
                "on your machine."
            )
            self._recommended_model = model

        elif hw["can_run_12b"]:
            model = "gemma3:12b"
            status = "already installed" if has_12b else "will be downloaded (~8 GB)"
            self._rec_label.setText(
                f"Core analysis model \u2014 {status}.\n\n"
                "Handles the full analysis pipeline locally. All student "
                "data stays on your computer."
            )
            self._recommended_model = model
            self._enhance_section.setVisible(True)

        else:
            self._rec_label.setText("")
            self._no_local_msg.setVisible(True)
            self._recommended_model = ""

    # ------------------------------------------------------------------
    # Populate install page (page 2)
    # ------------------------------------------------------------------

    def _populate_install_page(self):
        """Build the task list and start installation."""
        # Cancel any running worker
        if self._worker and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(2000)

        # Set summary text
        if (self._choice == "institutional"
                and self._inst_url_edit.text().strip()
                and self._inst_key_edit.text().strip()):
            self._setup_summary.setText(
                "Connecting to your school\u2019s AI service. "
                "We\u2019ll verify the connection and install a few tools."
            )
        elif self._recommended_model:
            parts = ["Setting up local analysis on your computer."]
            if (self._enhance_section.isVisible()
                    and self._enhance_toggle.isChecked()
                    and self._enhance_key_edit.text().strip()):
                parts.append(
                    "Cloud enhancement is enabled \u2014 only anonymized "
                    "class patterns will be sent."
                )
            else:
                parts.append("All student data stays on your computer.")
            self._setup_summary.setText(" ".join(parts))
        else:
            self._setup_summary.setText(
                "Installing analysis tools. You can connect an AI "
                "service later in Settings."
            )

        # Clear previous checklist
        while self._checklist_lo.count():
            item = self._checklist_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        tasks = []
        self._step_widgets: dict = {}

        # Always: pip deps + spacy
        tasks.append({
            "name": "Analysis tools",
            "fn": _task_install_pip_deps,
        })
        tasks.append({
            "name": "Language detection",
            "fn": _task_install_spacy,
        })

        if (self._choice == "institutional"
                and self._inst_url_edit.text().strip()
                and self._inst_key_edit.text().strip()):
            # Institutional API — test the connection
            url = self._inst_url_edit.text().strip()
            key = self._inst_key_edit.text().strip()
            model = self._inst_model_edit.text().strip() or "gpt-4o"
            tasks.append({
                "name": "School connection",
                "fn": lambda u=url, k=key, m=model: _task_test_cloud(u, k, m),
            })

        elif self._recommended_model:
            # Local model
            model = self._recommended_model
            tasks.append({
                "name": "AI model server",
                "fn": _task_ensure_ollama,
            })
            tasks.append({
                "name": "AI model download",
                "fn": _make_task_pull_model(model),
            })
            tasks.append({
                "name": "Testing AI model",
                "fn": _make_task_test_inference(model),
            })

            # Enhancement
            if (self._enhance_section.isVisible()
                    and self._enhance_toggle.isChecked()
                    and self._enhance_key_edit.text().strip()):
                enh_key = self._enhance_key_edit.text().strip()
                enh_model = (
                    self._enhance_model_edit.text().strip()
                    or "google/gemma-2-27b-it"
                )
                tasks.append({
                    "name": "Cloud enhancement",
                    "fn": lambda k=enh_key, m=enh_model: _task_test_cloud(
                        "https://openrouter.ai/api/v1", k, m,
                    ),
                })

        # Build checklist UI
        for task in tasks:
            row = self._make_check_row(task["name"])
            self._checklist_lo.addWidget(row)
            self._step_widgets[task["name"]] = row

        # Start
        self._install_progress.setVisible(True)
        self._done_banner.setVisible(False)
        self._next_btn.setEnabled(False)
        self._next_btn.setText("Done")

        self._worker = _SetupWorker(tasks, self)
        self._worker.progress.connect(self._on_step_progress)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _make_check_row(self, name: str) -> QFrame:
        """Create a checklist row: icon + label + status."""
        row = QFrame()
        row_name = f"chk_{id(row)}"
        row.setObjectName(row_name)
        row.setStyleSheet(
            f"QFrame#{row_name} {{ background: transparent; border: none; }}"
        )

        lo = QHBoxLayout(row)
        lo.setContentsMargins(SPACING_SM, SPACING_XS, SPACING_SM, SPACING_XS)
        lo.setSpacing(SPACING_SM)

        icon = QLabel("\u25cb")
        icon.setFixedWidth(px(20))
        icon.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(14)}px;"
            f" background: transparent; border: none;"
        )
        icon.setObjectName("icon")
        lo.addWidget(icon)

        lbl = QLabel(name)
        lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(12)}px;"
            f" background: transparent; border: none;"
        )
        lbl.setObjectName("label")
        lo.addWidget(lbl, 1)

        status_lbl = QLabel("")
        status_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        status_lbl.setObjectName("status")
        lo.addWidget(status_lbl)

        return row

    # ------------------------------------------------------------------
    # Install progress callbacks
    # ------------------------------------------------------------------

    def _on_step_progress(self, name: str):
        row = self._step_widgets.get(name)
        if not row:
            return
        icon = row.findChild(QLabel, "icon")
        label = row.findChild(QLabel, "label")
        status_lbl = row.findChild(QLabel, "status")
        if icon:
            icon.setText("\u25c9")
            icon.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(14)}px;"
                f" background: transparent; border: none;"
            )
        if label:
            label.setStyleSheet(
                f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
        if status_lbl:
            status_lbl.setText("running\u2026")
        self._install_status.setText(f"Setting up: {name}\u2026")

    def _on_step_done(self, name: str, ok: bool):
        row = self._step_widgets.get(name)
        if not row:
            return
        icon = row.findChild(QLabel, "icon")
        label = row.findChild(QLabel, "label")
        status_lbl = row.findChild(QLabel, "status")

        if ok:
            if icon:
                icon.setText("\u2713")
                icon.setStyleSheet(
                    f"color: {TERM_GREEN}; font-size: {px(14)}px;"
                    f" font-weight: bold;"
                    f" background: transparent; border: none;"
                )
            if label:
                label.setStyleSheet(
                    f"color: {PHOSPHOR_HOT}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
            if status_lbl:
                status_lbl.setText("")
        else:
            if icon:
                icon.setText("\u2717")
                icon.setStyleSheet(
                    f"color: {BURN_RED}; font-size: {px(14)}px;"
                    f" font-weight: bold;"
                    f" background: transparent; border: none;"
                )
            if label:
                label.setStyleSheet(
                    f"color: {PHOSPHOR_MID}; font-size: {px(12)}px;"
                    f" background: transparent; border: none;"
                )
            if status_lbl:
                status_lbl.setText("failed")
                status_lbl.setStyleSheet(
                    f"color: {BURN_RED}; font-size: {px(11)}px;"
                    f" background: transparent; border: none;"
                )

    def _on_all_done(self, success: bool):
        self._install_progress.setVisible(False)
        self._worker = None

        if success:
            self._done_banner.setVisible(True)
            self._install_status.setText("")
        else:
            self._install_status.setText(
                "Some steps didn\u2019t complete. You can close this "
                "and try again from Settings \u2192 Reconfigure."
            )
            self._install_status.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(12)}px;"
                f" background: transparent; border: none;"
            )
            self._done_banner.setVisible(True)
            self._done_text.setText(
                "Setup partially complete \u2014 some steps will need "
                "to be retried."
            )
            self._done_text.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(13)}px;"
                f" font-weight: 600;"
                f" background: transparent; border: none;"
            )

        self._next_btn.setEnabled(True)
        self._update_nav()

    # ------------------------------------------------------------------
    # Save settings
    # ------------------------------------------------------------------

    def _save_settings(self):
        """Persist the wizard's configuration."""
        from settings import load_settings, save_settings

        s = load_settings()
        s["insights_setup_complete"] = True

        if (self._choice == "institutional"
                and self._inst_url_edit.text().strip()
                and self._inst_key_edit.text().strip()):
            # Institutional API — runs the whole pipeline through cloud
            s["insights_cloud_url"] = self._inst_url_edit.text().strip()
            s["insights_cloud_key"] = self._inst_key_edit.text().strip()
            s["insights_cloud_model"] = (
                self._inst_model_edit.text().strip() or "gpt-4o"
            )
            s["insights_cloud_api_format"] = "openai"
            s["insights_cloud_privacy"] = "institutional_dpa"
            s["insights_model_tier"] = "deep_thinking"

        elif self._recommended_model:
            # Local model
            s["insights_llm_backend"] = "ollama"
            s["insights_translation_model"] = self._recommended_model

            if "27b" in self._recommended_model:
                s["insights_model_tier"] = "medium"
            else:
                s["insights_model_tier"] = "auto"

            # Enhancement
            if (self._enhance_section.isVisible()
                    and self._enhance_toggle.isChecked()
                    and self._enhance_key_edit.text().strip()):
                s["insights_cloud_url"] = "https://openrouter.ai/api/v1"
                s["insights_cloud_key"] = (
                    self._enhance_key_edit.text().strip()
                )
                s["insights_cloud_model"] = (
                    self._enhance_model_edit.text().strip()
                    or "google/gemma-2-27b-it"
                )
                s["insights_cloud_api_format"] = "openai"
                s["insights_cloud_privacy"] = "anonymized_only"
            else:
                s["insights_cloud_url"] = ""
                s["insights_cloud_key"] = ""
                s["insights_cloud_privacy"] = ""
        else:
            # No local capability, no institutional — minimal config
            s["insights_model_tier"] = "auto"

        save_settings(s)
