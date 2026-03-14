"""
Design system for Canvas Autograder GUI.

Aesthetic direction: Retro-Futurist Amber Terminal
- Warm near-black backgrounds (phosphor CRT void)
- Amber phosphor text hierarchy
- Dusty rose for active states / primary actions
- Terminal green for success, burn red for errors
- Monospace throughout
"""

# ---------------------------------------------------------------------------
# Spacing scale
# ---------------------------------------------------------------------------
SPACING_XS = 4
SPACING_SM = 8
SPACING_MD = 16
SPACING_LG = 24

# ---------------------------------------------------------------------------
# Font sizes
# ---------------------------------------------------------------------------
FONT_SMALL  = 11
FONT_NORMAL = 13
FONT_LARGE  = 15
FONT_MONO   = 13

# ---------------------------------------------------------------------------
# Window geometry
# ---------------------------------------------------------------------------
WIN_MIN_W      = 900
WIN_MIN_H      = 650
WIN_DEFAULT_W  = 1280
WIN_DEFAULT_H  = 860

LEFT_PANEL_MIN  = 260
LEFT_PANEL_PREF = 300

# ---------------------------------------------------------------------------
# Amber terminal colour palette
# ---------------------------------------------------------------------------

# Backgrounds — warm near-void
BG_VOID       = "#0A0800"   # outer void (window bg)
BG_PANEL      = "#130E04"   # sidebar / panel surface
BG_CARD       = "#1C1508"   # card / content surface
BG_INSET      = "#0E0A02"   # recessed areas (inputs, data)

# Phosphor text hierarchy
PHOSPHOR_HOT  = "#F0A830"   # bright — primary text, highlights
PHOSPHOR_MID  = "#A06A10"   # mid — secondary text
PHOSPHOR_DIM  = "#5A3C08"   # dim — placeholders, muted labels
PHOSPHOR_GLOW = "#2E1C06"   # barely-there — subtle bg tint

# Accents
AMBER_BTN     = "#C87C10"   # amber — secondary action buttons
ROSE_ACCENT   = "#CC5282"   # rose — primary run/go action
ROSE_DIM      = "#7A3458"   # rose hover / border
WARN_PINK     = "#C4708A"   # soft rose — warning toast text

# Status
TERM_GREEN    = "#72B85A"   # connected / ok
BURN_RED      = "#C04020"   # error

# Borders
BORDER_DARK   = "#3A2808"   # subtle warm border
BORDER_AMBER  = "#6A4A12"   # glowing amber border

# ---------------------------------------------------------------------------
# Backwards-compatible aliases (existing code imports these by name)
# ---------------------------------------------------------------------------
SIDEBAR_BG       = BG_PANEL
SIDEBAR_TEXT     = PHOSPHOR_MID
SIDEBAR_BORDER   = BORDER_DARK
SIDEBAR_SEL_BG   = "#2C1C08"
SIDEBAR_SEL_TEXT = PHOSPHOR_HOT
SIDEBAR_HOVER    = "#1A1205"

CONTENT_BG       = BG_VOID
SURFACE_BG       = BG_CARD
BORDER_COLOR     = BORDER_DARK
BORDER_FOCUS     = PHOSPHOR_HOT

TEXT_PRIMARY     = PHOSPHOR_HOT
TEXT_SECONDARY   = PHOSPHOR_MID
TEXT_PLACEHOLDER = PHOSPHOR_DIM

ACCENT_BLUE      = AMBER_BTN       # secondary button accent
ACCENT_AMBER     = ROSE_ACCENT     # primary run button
ACCENT_AMBER_HOV = "#A83E68"
ACCENT_AMBER_TXT = PHOSPHOR_HOT

STATUS_OK        = TERM_GREEN
STATUS_ERR       = BURN_RED
STATUS_WARN      = "#D87020"

GROUP_HEADER_BG  = "#1A1208"
GROUP_HEADER_FG  = PHOSPHOR_MID

# ---------------------------------------------------------------------------
# Shared gradient backgrounds  (import these instead of redefining per-file)
#
# IMPORTANT — QWidget vs QFrame:
#   QWidget ignores stylesheet `background:` unless WA_StyledBackground is set.
#   QFrame paints stylesheet backgrounds automatically.
#   Any panel that needs a gradient background MUST inherit QFrame, not QWidget.
# ---------------------------------------------------------------------------
CARD_GRADIENT  = ("qradialgradient(cx:0.52,cy:0.44,radius:0.90,fx:0.48,fy:0.40,"
                  "stop:0.00 #2C2212,stop:0.60 #171208,stop:1.00 #100C03)")
PANEL_GRADIENT = ("qradialgradient(cx:0.50,cy:0.46,radius:0.88,fx:0.53,fy:0.42,"
                  "stop:0.00 #201A08,stop:0.60 #121006,stop:1.00 #090702)")

MONO_FONT = '"Menlo", "Consolas", "Courier New", monospace'

# ---------------------------------------------------------------------------
# Application-wide QSS
# ---------------------------------------------------------------------------
_BTN_BG      = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #201A0A,stop:1 #181205)"
_BTN_HOV_BG  = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #2A220E,stop:1 #1E1808)"
_BTN_PRE_BG  = "qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #181205,stop:1 #131003)"

APP_QSS = f"""

/* ── Global ──────────────────────────────────────────────────────────────── */
QWidget {{
    font-family: "Menlo", "Consolas", "Courier New", monospace;
    font-size: 13px;
    color: {TEXT_PRIMARY};
    background: {CONTENT_BG};
}}

QMainWindow, QDialog {{
    background: {CONTENT_BG};
}}

/* ── Menu bar ─────────────────────────────────────────────────────────────── */
QMenuBar {{
    background: {SIDEBAR_BG};
    color: {SIDEBAR_TEXT};
    padding: 2px 0;
    border-bottom: 1px solid {SIDEBAR_BORDER};
}}
QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 4px;
    margin: 2px 2px;
}}
QMenuBar::item:selected {{
    background: {SIDEBAR_SEL_BG};
    color: {SIDEBAR_SEL_TEXT};
}}
QMenu {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 6px;
    padding: 4px 0;
}}
QMenu::item {{
    padding: 6px 20px 6px 12px;
    color: {PHOSPHOR_MID};
}}
QMenu::item:selected {{
    background: {SIDEBAR_SEL_BG};
    color: {PHOSPHOR_HOT};
    border-radius: 3px;
}}
QMenu::separator {{
    height: 1px;
    background: {BORDER_DARK};
    margin: 4px 8px;
}}

/* ── Tool bar ─────────────────────────────────────────────────────────────── */
QToolBar {{
    background: {SIDEBAR_BG};
    border: none;
    border-bottom: 1px solid {SIDEBAR_BORDER};
    padding: 4px 8px;
    spacing: 4px;
}}
QToolBar QToolButton {{
    color: {SIDEBAR_TEXT};
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 5px 10px;
    font-size: 12px;
}}
QToolBar QToolButton:hover {{
    background: {SIDEBAR_HOVER};
    border-color: {SIDEBAR_BORDER};
    color: {PHOSPHOR_HOT};
}}
QToolBar QToolButton:pressed {{
    background: {SIDEBAR_SEL_BG};
}}
QToolBar::separator {{
    width: 1px;
    background: {SIDEBAR_BORDER};
    margin: 4px 6px;
}}

/* ── Tab widget ───────────────────────────────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    border-top: 1px solid {BORDER_DARK};
    background: {CONTENT_BG};
}}
QTabBar {{
    background: {SIDEBAR_BG};
}}
QTabBar::tab {{
    background: {SIDEBAR_BG};
    color: {PHOSPHOR_DIM};
    padding: 8px 20px;
    border-bottom: 2px solid transparent;
    font-size: 13px;
}}
QTabBar::tab:selected {{
    color: {PHOSPHOR_HOT};
    border-bottom: 2px solid {ROSE_ACCENT};
    font-weight: bold;
}}
QTabBar::tab:hover:!selected {{
    background: {SIDEBAR_HOVER};
    color: {PHOSPHOR_MID};
}}

/* ── Status bar ───────────────────────────────────────────────────────────── */
QStatusBar {{
    background: {SIDEBAR_BG};
    color: {SIDEBAR_TEXT};
    border-top: 1px solid {SIDEBAR_BORDER};
    font-size: 12px;
}}
QStatusBar QLabel {{
    padding: 3px 6px;
    color: {SIDEBAR_TEXT};
}}

/* ── Group boxes ──────────────────────────────────────────────────────────── */
QGroupBox {{
    font-weight: 600;
    font-size: 11px;
    color: {PHOSPHOR_DIM};
    border: 1px solid {BORDER_DARK};
    border-radius: 6px;
    padding-top: 18px;
    margin-top: 8px;
    background: {BG_CARD};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {PHOSPHOR_DIM};
    text-transform: uppercase;
    letter-spacing: 1px;
    font-size: 11px;
}}

/* ── Buttons ──────────────────────────────────────────────────────────────── */
QPushButton {{
    background: {_BTN_BG};
    color: {PHOSPHOR_MID};
    border: 1px solid rgba(90, 60, 8, 0.55);
    border-radius: 4px;
    padding: 6px 14px;
    font-size: 13px;
    min-height: 22px;
}}
QPushButton:hover {{
    background: {_BTN_HOV_BG};
    border-color: {BORDER_AMBER};
    color: {PHOSPHOR_HOT};
}}
QPushButton:pressed {{
    background: {_BTN_PRE_BG};
    padding-top: 7px; padding-bottom: 5px;
    padding-left: 15px; padding-right: 13px;
    border-color: rgba(90, 60, 8, 0.35);
}}
QPushButton:disabled {{
    color: {PHOSPHOR_GLOW};
    border-color: rgba(58, 40, 8, 0.3);
    background: {_BTN_BG};
}}

/* Run / primary accent (rose) */
QPushButton#runButton, QPushButton[accent="true"] {{
    background: {_BTN_BG};
    color: {ROSE_ACCENT};
    border: 1px solid rgba(204, 82, 130, 0.50);
    font-weight: 600;
    padding: 7px 18px;
}}
QPushButton#runButton:hover, QPushButton[accent="true"]:hover {{
    background: {_BTN_HOV_BG};
    border-color: rgba(204, 82, 130, 0.90);
    color: {ROSE_ACCENT};
}}
QPushButton#runButton:pressed, QPushButton[accent="true"]:pressed {{
    background: {_BTN_PRE_BG};
    padding-top: 8px; padding-bottom: 6px;
    padding-left: 19px; padding-right: 17px;
    border-color: rgba(204, 82, 130, 0.35);
}}
QPushButton#runButton:disabled, QPushButton[accent="true"]:disabled {{
    color: rgba(122, 52, 88, 0.45);
    border-color: rgba(122, 52, 88, 0.25);
}}

/* Secondary amber buttons */
QPushButton[secondary="true"] {{
    background: {_BTN_BG};
    color: {AMBER_BTN};
    border: 1px solid rgba(200, 124, 16, 0.50);
    font-weight: 500;
}}
QPushButton[secondary="true"]:hover {{
    background: {_BTN_HOV_BG};
    border-color: rgba(200, 124, 16, 0.90);
    color: {PHOSPHOR_HOT};
}}
QPushButton[secondary="true"]:disabled {{
    color: rgba(200, 124, 16, 0.30);
    border-color: rgba(200, 124, 16, 0.20);
}}

/* ── Line edits ───────────────────────────────────────────────────────────── */
QLineEdit {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    padding: 5px 8px;
    color: {PHOSPHOR_HOT};
    selection-background-color: {PHOSPHOR_GLOW};
    selection-color: {PHOSPHOR_HOT};
}}
QLineEdit:focus {{
    border-color: {PHOSPHOR_HOT};
    outline: none;
}}
QLineEdit:disabled {{
    background: {BG_VOID};
    color: {PHOSPHOR_DIM};
}}

/* ── Combo box ────────────────────────────────────────────────────────────── */
QComboBox {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    padding: 5px 8px;
    color: {PHOSPHOR_HOT};
    min-height: 22px;
}}
QComboBox:focus {{
    border-color: {PHOSPHOR_HOT};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}
QComboBox QAbstractItemView {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    color: {PHOSPHOR_MID};
    selection-background-color: {SIDEBAR_SEL_BG};
    selection-color: {PHOSPHOR_HOT};
}}

/* ── Spin box ─────────────────────────────────────────────────────────────── */
QSpinBox, QDoubleSpinBox, QTimeEdit {{
    background: {BG_INSET};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    padding: 4px 8px;
    color: {PHOSPHOR_HOT};
}}
QSpinBox:focus, QDoubleSpinBox:focus, QTimeEdit:focus {{
    border-color: {PHOSPHOR_HOT};
}}

/* ── Checkboxes / radio buttons ───────────────────────────────────────────── */
QCheckBox, QRadioButton {{
    color: {PHOSPHOR_MID};
    spacing: 6px;
}}
QCheckBox:disabled, QRadioButton:disabled {{
    color: {PHOSPHOR_DIM};
}}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 14px;
    height: 14px;
    border: 1px solid {BORDER_AMBER};
    border-radius: 3px;
    background: {BG_INSET};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {AMBER_BTN};
    border-color: {PHOSPHOR_HOT};
}}

/* ── List widget (course list) ────────────────────────────────────────────── */
QListWidget {{
    background: {SIDEBAR_BG};
    border: none;
    border-right: 1px solid {SIDEBAR_BORDER};
    color: {SIDEBAR_TEXT};
    outline: none;
    font-size: 13px;
}}
QListWidget::item {{
    padding: 7px 10px;
    border-radius: 0;
    border-left: 3px solid transparent;
}}
QListWidget::item:selected {{
    background: {SIDEBAR_SEL_BG};
    color: {SIDEBAR_SEL_TEXT};
    border-left: 3px solid {ROSE_ACCENT};
}}
QListWidget::item:hover:!selected {{
    background: {SIDEBAR_HOVER};
    color: {PHOSPHOR_HOT};
}}

/* ── Tree widget (assignments) ────────────────────────────────────────────── */
QTreeWidget {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    alternate-background-color: {GROUP_HEADER_BG};
    color: {PHOSPHOR_MID};
    outline: none;
}}
QTreeWidget::item {{
    padding: 4px 4px;
    color: {PHOSPHOR_MID};
}}
QTreeWidget::item:selected {{
    background: {SIDEBAR_SEL_BG};
    color: {PHOSPHOR_HOT};
}}
QTreeWidget::item:hover:!selected {{
    background: {GROUP_HEADER_BG};
}}
QHeaderView::section {{
    background: {GROUP_HEADER_BG};
    color: {PHOSPHOR_DIM};
    border: none;
    border-right: 1px solid {BORDER_DARK};
    border-bottom: 1px solid {BORDER_DARK};
    padding: 5px 8px;
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
QHeaderView::section:first {{
    border-left: none;
}}

/* ── Scroll areas ─────────────────────────────────────────────────────────── */
QScrollArea {{
    border: none;
    background: {CONTENT_BG};
}}
QScrollArea > QWidget > QWidget {{
    background: {CONTENT_BG};
}}
QScrollBar:vertical {{
    background: {BG_PANEL};
    width: 8px;
    margin: 0;
    border-radius: 4px;
}}
QScrollBar::handle:vertical {{
    background: {BORDER_AMBER};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{
    background: {PHOSPHOR_MID};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background: {BG_PANEL};
    height: 8px;
    border-radius: 4px;
}}
QScrollBar::handle:horizontal {{
    background: {BORDER_AMBER};
    border-radius: 4px;
    min-width: 30px;
}}

/* ── Splitter handle ──────────────────────────────────────────────────────── */
QSplitter::handle {{
    background: {SIDEBAR_BORDER};
}}
QSplitter::handle:hover {{
    background: {AMBER_BTN};
}}

/* ── Text edit (log output) ───────────────────────────────────────────────── */
QTextEdit, QTextBrowser {{
    background: {BG_CARD};
    border: 1px solid {BORDER_DARK};
    border-radius: 4px;
    color: {PHOSPHOR_MID};
    selection-background-color: {PHOSPHOR_GLOW};
    selection-color: {PHOSPHOR_HOT};
}}
QTextEdit[monospace="true"] {{
    background: {BG_INSET};
    color: {PHOSPHOR_MID};
    font-family: "JetBrains Mono", "Cascadia Code", "Menlo", "Consolas", monospace;
    font-size: 12px;
    border-color: {BORDER_DARK};
    border-radius: 4px;
    padding: 4px;
}}

/* ── Dialog ───────────────────────────────────────────────────────────────── */
QDialog {{
    background: {CONTENT_BG};
}}

/* ── Message boxes ────────────────────────────────────────────────────────── */
QMessageBox {{
    background: {BG_CARD};
}}

/* ── Labels ───────────────────────────────────────────────────────────────── */
QLabel[heading="true"] {{
    font-size: 15px;
    font-weight: 700;
    color: {PHOSPHOR_HOT};
}}
QLabel[muted="true"] {{
    color: {PHOSPHOR_DIM};
    font-size: 12px;
}}
QLabel[status_ok="true"] {{
    color: {STATUS_OK};
    font-weight: 600;
}}
QLabel[status_err="true"] {{
    color: {STATUS_ERR};
    font-weight: 600;
}}

/* ── Form layout label column ─────────────────────────────────────────────── */
QFormLayout QLabel {{
    color: {PHOSPHOR_DIM};
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 1px;
    padding-right: 4px;
    text-transform: uppercase;
}}

"""

# ---------------------------------------------------------------------------
# Convenience: apply visual property shorthand
# ---------------------------------------------------------------------------

def make_run_button(btn) -> None:
    """Style a QPushButton as the primary Run action (rose accent)."""
    btn.setProperty("accent", "true")
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def make_secondary_button(btn) -> None:
    """Style a QPushButton as an amber secondary action."""
    btn.setProperty("secondary", "true")
    btn.style().unpolish(btn)
    btn.style().polish(btn)


def make_monospace_textedit(te) -> None:
    """Style a QTextEdit as dark monospace terminal output."""
    te.setProperty("monospace", "true")
    te.style().unpolish(te)
    te.style().polish(te)
