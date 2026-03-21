"""
Left sidebar panel: collapsible semester tree.
Visual language matches the setup dialog — panel gradient, amber accents,
monospace type hierarchy.
"""
import re
import json
from pathlib import Path

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget, QTreeWidgetItem,
    QStyledItemDelegate, QStyleOptionViewItem, QStyle,
    QInputDialog, QMenu, QMessageBox,
)
from gui.dialogs.message_dialog import show_info, show_warning, show_critical
from PySide6.QtCore import Signal, Qt, QSize, QRect
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QRadialGradient, QPainterPath

from gui.styles import (
    px,
    SPACING_SM,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    SIDEBAR_SEL_BG, SIDEBAR_SEL_TEXT, SIDEBAR_HOVER,
    ROSE_ACCENT, BORDER_DARK, BORDER_AMBER,
    PANEL_GRADIENT, BG_INSET, PANE_BG_GRADIENT,
    make_section_label,
)
from gui.widgets.status_pip import draw_pip

# ---------------------------------------------------------------------------
# Item data roles
# ---------------------------------------------------------------------------
_ROLE_ID       = Qt.ItemDataRole.UserRole
_ROLE_TYPE     = Qt.ItemDataRole.UserRole + 1   # "term" | "course" | "placeholder"
_ROLE_NAME     = Qt.ItemDataRole.UserRole + 2   # original Canvas name (for signals)
_ROLE_CODE     = Qt.ItemDataRole.UserRole + 3   # cleaned code, e.g. "ETHN-1-02"
_ROLE_TITLE    = Qt.ItemDataRole.UserRole + 4   # extracted title
_ROLE_BADGE    = Qt.ItemDataRole.UserRole + 5   # ungraded count (int)
_ROLE_FORMAT   = Qt.ItemDataRole.UserRole + 6   # effective modality: "online"|"blended"|""
_ROLE_NICKNAME = Qt.ItemDataRole.UserRole + 7   # user-set nickname (str or "")
_ROLE_PUBLISHED = Qt.ItemDataRole.UserRole + 8  # bool: True = available/published

_COURSE_ROW_H = px(46)  # px — tall enough for two text lines
_PILL_SLOT_W  = px(26)  # fixed width for modality pill slot (matches bulk run)
_PILL_GAP     = px(6)   # gap between pill and code text

# ---------------------------------------------------------------------------
# Modality tag definitions  (label, pill-border-color)
# ---------------------------------------------------------------------------
_FORMAT_TAGS = {
    "on_campus": ("IP",  "#7DAB72"),   # muted green  — in-person/physical
    "online":    ("OL",  "#5BA8C9"),   # steel blue   — fully remote
    "blended":   ("HY",  "#C97AB8"),   # rose/mauve   — hybrid
    "hybrid":    ("HY",  "#C97AB8"),   # alias for blended
}

# Menu options shown in the Set Modality submenu (in display order)
_MODALITY_MENU = [
    ("on_campus", "IP — In Person"),
    ("online",    "OL — Online"),
    ("blended",   "HY — Hybrid"),
]

# ---------------------------------------------------------------------------
# Local metadata store  (~/.canvas_autograder_course_meta.json)
# ---------------------------------------------------------------------------
_META_PATH = Path.home() / ".canvas_autograder_course_meta.json"


class _CourseMetaStore:
    """Persists user-set nicknames and modality overrides, keyed by course id."""

    def __init__(self):
        self._data: dict = {}
        self._load()

    def _load(self) -> None:
        if _META_PATH.exists():
            try:
                self._data = json.loads(_META_PATH.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self) -> None:
        _META_PATH.parent.mkdir(parents=True, exist_ok=True)
        _META_PATH.write_text(
            json.dumps(self._data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def get_nickname(self, course_id: int) -> str:
        return self._data.get(str(course_id), {}).get("nickname", "")

    def set_nickname(self, course_id: int, nickname: str) -> None:
        self._data.setdefault(str(course_id), {})["nickname"] = nickname
        self._save()

    def clear_nickname(self, course_id: int) -> None:
        entry = self._data.get(str(course_id), {})
        entry.pop("nickname", None)
        self._save()

    def get_format(self, course_id: int) -> str:
        return self._data.get(str(course_id), {}).get("format", "")

    def set_format(self, course_id: int, fmt: str) -> None:
        self._data.setdefault(str(course_id), {})["format"] = fmt
        self._save()

    def clear_format(self, course_id: int) -> None:
        entry = self._data.get(str(course_id), {})
        entry.pop("format", None)
        self._save()


_meta = _CourseMetaStore()   # module-level singleton

# ---------------------------------------------------------------------------
# Course name/title parser
# ---------------------------------------------------------------------------

# Term prefixes in compact form:  "2026SP", "2025FA", "2024SU", "2024WI"
_RE_COMPACT_TERM = re.compile(r'^\d{4}[A-Z]{2,3}\b\s*', re.IGNORECASE)
# Term names in long form:  "Spring 2026 ", "Fall 2025 "
_RE_NAMED_TERM = re.compile(
    r'^(Spring|Fall|Summer|Winter|Spr|Win|Sum)\s+\d{4}\b\s*', re.IGNORECASE
)
# Trailing compact term:  " 2026SP"
_RE_TRAIL_COMPACT = re.compile(r'\s+\d{4}[A-Z]{2,3}$', re.IGNORECASE)
# Trailing named term:  " Spring 2026"
_RE_TRAIL_NAMED = re.compile(
    r'\s+(Spring|Fall|Summer|Winter|Spr|Win|Sum)\s+\d{4}$', re.IGNORECASE
)


def _parse_course(name: str, code: str) -> tuple:
    """
    Returns (display_code, display_title) extracted from Canvas course data.

    Handles:
      - Term-prefix codes:     "2026SP ETHN-1-02"        → code "ETHN-1-02"
      - Cross-listed codes:    "ETHN-27.2026SP, HIST-27…" → code "ETHN-27"
      - Trailing term suffix:  "ETHN-27AN-LS01.2026SP"   → code "ETHN-27AN-LS01"
      - Name = "CODE: Title"   → title "Title"
      - Name = "CODE Title"    → title "Title"
      - Name = "Season YYYY Title" → title "Title"
      - Trailing term in name: "Title 2026SP"            → stripped
    """
    # ── clean the code ──────────────────────────────────────────────────────
    c = (code or '').strip()
    c = _RE_COMPACT_TERM.sub('', c).strip()          # strip "2026SP "
    if ',' in c:
        c = c.split(',')[0].strip()                  # cross-listed: keep first
    c = re.sub(r'\.\d{4}[A-Z]{2,3}$', '', c, flags=re.IGNORECASE).strip()  # ".2026SP"

    # ── extract title from name ─────────────────────────────────────────────
    t = name.strip()

    # Strategy 1: split on first ": "
    # Handles both simple ("ETHN-1-02: Intro…") and cross-listed
    # ("ETHN-27.2026SP, HIST-27.2026SP: Native American Hist/Lit") cleanly.
    if ': ' in t:
        t = t.split(': ', 1)[1].strip()
    else:
        # Strategy 2: strip term prefixes then leading code prefix
        t = _RE_COMPACT_TERM.sub('', t).strip()
        t = _RE_NAMED_TERM.sub('', t).strip()
        for candidate in (c, code or ''):
            candidate = candidate.strip()
            if candidate and t.upper().startswith(candidate.upper()):
                t = t[len(candidate):].lstrip(':').lstrip('-').strip()
                break

    # Remove trailing term tokens (applies to both paths)
    t = _RE_TRAIL_COMPACT.sub('', t).strip()
    t = _RE_TRAIL_NAMED.sub('', t).strip()

    # Fallback: if nothing useful extracted, show original name
    if not t or t.upper() == c.upper():
        t = name.strip()

    return (c or code or '?', t)


# ---------------------------------------------------------------------------
# Two-line delegate
# ---------------------------------------------------------------------------

class _CourseDelegate(QStyledItemDelegate):
    """Renders course items with: code + [modality tag] on line 1, title on line 2."""

    def paint(self, painter: QPainter,
              option: QStyleOptionViewItem, index) -> None:
        if index.data(_ROLE_TYPE) != "course":
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)

        painter.save()

        is_sel   = bool(opt.state & QStyle.StateFlag.State_Selected)
        is_hover = bool(opt.state & QStyle.StateFlag.State_MouseOver)

        # ── background — edge-to-edge void band + radial glow + pip ────────
        if is_sel or is_hover:
            # Span the full viewport width so the glow band goes edge-to-edge
            # instead of creating a floating black box against the tree gradient.
            from PySide6.QtCore import QRect as _QRect
            vp_w = painter.device().width()
            full_rect = _QRect(0, opt.rect.y(), vp_w, opt.rect.height())
            painter.setClipping(False)
            painter.fillRect(full_rect, QColor("#0A0800"))

            # Left-biased radial glow: origin anchored near the left edge
            # so the light radiates from behind the pip indicator.
            glow_cx = vp_w * 0.18
            glow_cy = opt.rect.y() + opt.rect.height() * 0.50
            glow_r  = vp_w * 0.90

            if is_sel:
                center_col = QColor(204, 82, 130, 72)    # rose primary
                mid_col    = QColor(204, 82, 130, 20)
                bloom_col  = QColor(204, 82, 130, 38)
            else:
                center_col = QColor(240, 168, 48, 50)    # amber hover
                mid_col    = QColor(240, 168, 48, 15)
                bloom_col  = QColor(240, 168, 48, 24)

            clip = QPainterPath()
            clip.addRect(full_rect)

            # Primary glow pass
            grad = QRadialGradient(glow_cx, glow_cy, glow_r)
            grad.setColorAt(0.0, center_col)
            grad.setColorAt(0.6, mid_col)
            grad.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.save()
            painter.setClipPath(clip)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grad)
            painter.drawRect(full_rect)

            # Bloom pass
            bloom = QRadialGradient(glow_cx, glow_cy, glow_r * 0.50)
            bloom.setColorAt(0.0, bloom_col)
            bloom.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setBrush(bloom)
            painter.drawRect(full_rect)
            painter.restore()

            painter.setClipping(True)

            # Pip indicator — anchored near the left edge of the full band
            pip_cx = float(opt.rect.x() // 2 + 4)   # midpoint of branch area
            pip_cy = float(opt.rect.y() + opt.rect.height() / 2)
            painter.save()
            if is_sel:
                draw_pip(painter, pip_cx, pip_cy, 10,
                         r=204, g=82, b=130, bloom_alpha=60, core_alpha=200)
            else:
                draw_pip(painter, pip_cx, pip_cy, 8,
                         r=240, g=168, b=48, bloom_alpha=28, core_alpha=130)
            painter.restore()

        # ── bottom separator ─────────────────────────────────────────────────
        p = QPen(QColor(BORDER_DARK), 1)
        painter.setPen(p)
        painter.drawLine(opt.rect.x(), opt.rect.bottom(),
                         opt.rect.right(), opt.rect.bottom())

        # ── data ─────────────────────────────────────────────────────────────
        code     = index.data(_ROLE_CODE)     or ""
        title    = index.data(_ROLE_NICKNAME) or index.data(_ROLE_TITLE) or ""
        badge    = index.data(_ROLE_BADGE)    or 0
        fmt      = index.data(_ROLE_FORMAT)   or ""
        tag_info = _FORMAT_TAGS.get(fmt.lower())   # (label, color) or None

        if badge:
            code = f"{code}  [{badge}]"

        # ── colors ───────────────────────────────────────────────────────────
        if is_sel:
            code_col  = QColor(SIDEBAR_SEL_TEXT)
            title_col = QColor(SIDEBAR_SEL_TEXT)
        elif badge:
            code_col  = QColor(PHOSPHOR_HOT)
            title_col = QColor(PHOSPHOR_DIM)
        else:
            code_col  = QColor(PHOSPHOR_MID)
            title_col = QColor(PHOSPHOR_DIM)

        # ── layout ───────────────────────────────────────────────────────────
        code_font  = _mono(11, bold=is_sel or bool(badge))
        title_font = _mono(9)

        code_h, title_h, gap = px(16), px(13), px(3)
        block_h = code_h + gap + title_h
        y0 = opt.rect.y() + (opt.rect.height() - block_h) // 2

        # Pill occupies a fixed-width slot at the left, code text follows
        pill_x = opt.rect.x() + 2
        x  = pill_x + _PILL_SLOT_W + _PILL_GAP
        w  = opt.rect.x() + opt.rect.width() - x - 8

        # ── draw modality pill (left-aligned, before code) ───────────────────
        if tag_info:
            tag_label, tag_hex = tag_info
            tag_font = _mono(8)
            tag_color = QColor(tag_hex)
            pill_w  = _PILL_SLOT_W
            pill_h  = px(14)
            pill_y  = y0 + (code_h - pill_h) // 2

            painter.setFont(tag_font)
            pen2 = QPen(tag_color, 1)
            pen2.setCosmetic(True)
            painter.setPen(pen2)
            painter.drawRoundedRect(pill_x, pill_y, pill_w, pill_h, 3, 3)

            painter.setPen(tag_color)
            painter.drawText(
                QRect(pill_x, pill_y, pill_w, pill_h),
                Qt.AlignmentFlag.AlignCenter,
                tag_label,
            )

        # ── draw code ─────────────────────────────────────────────────────────
        painter.setFont(code_font)
        painter.setPen(code_col)
        fm = painter.fontMetrics()
        painter.drawText(
            QRect(x, y0, w, code_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm.elidedText(code, Qt.TextElideMode.ElideRight, w),
        )

        # ── draw title ────────────────────────────────────────────────────────
        painter.setFont(title_font)
        painter.setPen(title_col)
        fm2 = painter.fontMetrics()
        painter.drawText(
            QRect(x, y0 + code_h + gap, w, title_h),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            fm2.elidedText(title, Qt.TextElideMode.ElideRight, w),
        )

        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index) -> QSize:
        if index.data(_ROLE_TYPE) == "course":
            return QSize(option.rect.width() or 200, _COURSE_ROW_H)
        return super().sizeHint(option, index)


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

# Side-origin gradient: light bleeds in from the left edge (CRT backlight effect)
_SIDE_GRADIENT = ("qradialgradient(cx:0.08,cy:0.45,radius:1.20,fx:0.03,fy:0.40,"
                  "stop:0.00 #201A08,stop:0.55 #130E04,stop:1.00 #090702)")

_TREE_QSS = f"""
    QTreeWidget {{
        background: {BG_INSET};
        color: {PHOSPHOR_MID};
        border: none;
        border-bottom-left-radius: 6px;
        border-bottom-right-radius: 6px;
        outline: none;
    }}
    QTreeWidget::item {{
        border-bottom: 1px solid {BORDER_DARK};
        border-left: 3px solid transparent;
        padding-left: 1px;
    }}
    QTreeWidget::item:selected {{
        background: transparent;
        color: {SIDEBAR_SEL_TEXT};
        border-left: 3px solid transparent;
    }}
    QTreeWidget::item:hover:!selected {{
        background: transparent;
        color: {PHOSPHOR_HOT};
        border-left: 3px solid transparent;
    }}
    QTreeWidget::branch {{
        background: transparent;
    }}
    QTreeWidget::branch:selected {{
        background: transparent;
    }}
    QTreeWidget::branch:hover:!selected {{
        background: transparent;
    }}
"""

_PANEL_QSS = f"""
    QFrame#coursePanel {{
        background: {PANE_BG_GRADIENT};
        border: 1px solid {BORDER_DARK};
        border-top-color: {BORDER_AMBER};
        border-radius: 8px;
    }}
    QFrame#coursePanel QLabel {{
        background: transparent;
        border: none;
    }}
"""


def _mono(size: int = 12, bold: bool = False) -> QFont:
    f = QFont("Menlo")
    f.setStyleHint(QFont.StyleHint.Monospace)
    f.setPixelSize(px(size))
    f.setBold(bold)
    return f


# ---------------------------------------------------------------------------
# Panel widget
# ---------------------------------------------------------------------------

class CoursePanel(QFrame):
    course_selected = Signal(int, str)  # (course_id, course_name)
    term_selected   = Signal(int)       # (term_id,)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("coursePanel")
        self.setStyleSheet(_PANEL_QSS)
        self._course_items: dict = {}   # course_id -> QTreeWidgetItem
        self._editor = None             # CanvasEditor, set via set_editor()
        self._active_workers: list = [] # prevent premature GC
        self._setup_ui()

    # ── UI construction ────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(SPACING_SM)

        header = make_section_label("Courses")
        layout.addWidget(header)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0.00 rgba(240,168,48,0),
                    stop:0.20 rgba(240,168,48,0.35),
                    stop:0.50 rgba(240,168,48,0.70),
                    stop:0.80 rgba(240,168,48,0.35),
                    stop:1.00 rgba(240,168,48,0));
                border: none;
            }}
        """)
        layout.addWidget(sep)

        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setRootIsDecorated(False)
        self._tree.setIndentation(14)
        self._tree.setAnimated(True)
        self._tree.setMouseTracking(True)
        self._tree.setStyleSheet(_TREE_QSS)
        self._tree.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )

        self._delegate = _CourseDelegate()
        self._tree.setItemDelegate(self._delegate)

        self._tree.itemExpanded.connect(self._on_item_expanded)
        self._tree.itemCollapsed.connect(self._on_item_collapsed)
        self._tree.itemClicked.connect(self._on_item_clicked)
        self._tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._tree)

    # ── Public API ─────────────────────────────────────────────────────────

    def populate_terms(self, terms: list) -> None:
        """Receive term list (fires right before courses arrive in the same queue batch)."""
        self._tree.blockSignals(True)
        self._tree.clear()

        for term_id, term_name, is_current in terms:
            term_item = QTreeWidgetItem()
            arrow = "v" if is_current else ">"
            label = f"{arrow}  {term_name.upper()}" + ("  ●" if is_current else "")
            term_item.setText(0, label)
            term_item.setForeground(0, QColor(PHOSPHOR_HOT if is_current else PHOSPHOR_DIM))
            term_item.setFont(0, _mono(11, bold=is_current))
            term_item.setData(0, _ROLE_ID,   term_id)
            term_item.setData(0, _ROLE_TYPE, "term")
            term_item.setFlags(term_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            term_item.setBackground(0, QColor(SIDEBAR_SEL_BG if is_current else "#0E0A02"))
            self._tree.addTopLevelItem(term_item)
            if is_current:
                self._tree.expandItem(term_item)

        self._tree.blockSignals(False)

    def add_courses_for_term(self, term_id: int, courses: list) -> None:
        """Called for every term as courses arrive. Empty terms are removed."""
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            item = root.child(i)
            if item.data(0, _ROLE_ID) != term_id:
                continue

            if not courses:
                root.removeChild(item)
                return

            item.takeChildren()
            for c in courses:
                cid   = c.get("id")
                name  = c.get("name", f"Course {cid or '?'}")
                code  = c.get("course_code", "")
                disp_code, disp_title = _parse_course(name, code)

                # Effective modality: user override takes precedence over Canvas
                canvas_fmt = (c.get("course_format") or "").lower()
                user_fmt   = _meta.get_format(cid) if cid else ""
                eff_fmt    = user_fmt or canvas_fmt

                nickname  = _meta.get_nickname(cid) if cid else ""
                published = c.get("workflow_state", "available") == "available"

                child = QTreeWidgetItem([""])   # text drawn by delegate
                child.setData(0, _ROLE_ID,        cid)
                child.setData(0, _ROLE_TYPE,      "course")
                child.setData(0, _ROLE_NAME,      name)
                child.setData(0, _ROLE_CODE,      disp_code)
                child.setData(0, _ROLE_TITLE,     disp_title)
                child.setData(0, _ROLE_BADGE,     0)
                child.setData(0, _ROLE_FORMAT,    eff_fmt)
                child.setData(0, _ROLE_NICKNAME,  nickname)
                child.setData(0, _ROLE_PUBLISHED, published)
                child.setSizeHint(0, QSize(200, _COURSE_ROW_H))
                item.addChild(child)
                if cid is not None:
                    self._course_items[cid] = child

            if item.isExpanded():
                self.term_selected.emit(term_id)
                return

    def populate(self, terms: list, courses_by_term: dict) -> None:
        """
        Atomic one-shot population — call this instead of set_terms + add_courses_for_term
        to avoid the flash of empty term rows while courses are still loading.

        terms           = [(term_id, term_name, is_current), ...]
        courses_by_term = {term_id: [course_dict, ...]}
        """
        self._tree.blockSignals(True)
        self._tree.clear()
        self._course_items.clear()

        for term_id, term_name, is_current in terms:
            courses = courses_by_term.get(term_id, [])
            if not courses:
                continue   # skip empty terms entirely — no flash, no removal

            term_item = QTreeWidgetItem()
            arrow = "v" if is_current else ">"
            label = f"{arrow}  {term_name.upper()}" + ("  ●" if is_current else "")
            term_item.setText(0, label)
            term_item.setForeground(0, QColor(PHOSPHOR_HOT if is_current else PHOSPHOR_DIM))
            term_item.setFont(0, _mono(11, bold=is_current))
            term_item.setData(0, _ROLE_ID,   term_id)
            term_item.setData(0, _ROLE_TYPE, "term")
            term_item.setFlags(term_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            term_item.setBackground(0, QColor(SIDEBAR_SEL_BG if is_current else "#0E0A02"))
            self._tree.addTopLevelItem(term_item)

            for c in courses:
                cid   = c.get("id")
                name  = c.get("name", f"Course {cid or '?'}")
                code  = c.get("course_code", "")
                disp_code, disp_title = _parse_course(name, code)

                canvas_fmt = (c.get("course_format") or "").lower()
                user_fmt   = _meta.get_format(cid) if cid else ""
                eff_fmt    = user_fmt or canvas_fmt
                nickname   = _meta.get_nickname(cid) if cid else ""
                published  = c.get("workflow_state", "available") == "available"

                child = QTreeWidgetItem([""])
                child.setData(0, _ROLE_ID,        cid)
                child.setData(0, _ROLE_TYPE,      "course")
                child.setData(0, _ROLE_NAME,      name)
                child.setData(0, _ROLE_CODE,      disp_code)
                child.setData(0, _ROLE_TITLE,     disp_title)
                child.setData(0, _ROLE_BADGE,     0)
                child.setData(0, _ROLE_FORMAT,    eff_fmt)
                child.setData(0, _ROLE_NICKNAME,  nickname)
                child.setData(0, _ROLE_PUBLISHED, published)
                child.setSizeHint(0, QSize(200, _COURSE_ROW_H))
                term_item.addChild(child)
                if cid is not None:
                    self._course_items[cid] = child

            if is_current:
                self._tree.expandItem(term_item)

        self._tree.blockSignals(False)

    def set_editor(self, editor) -> None:
        """Receive the CanvasEditor instance from the main window."""
        self._editor = editor

    def clear(self) -> None:
        self._course_items.clear()
        self._tree.clear()

    def set_course_ungraded(self, course_id: int, ungraded_count: int) -> None:
        child = self._course_items.get(course_id)
        if child is None:
            return
        child.setData(0, _ROLE_BADGE, ungraded_count)
        self._tree.update(self._tree.indexFromItem(child))

    # ── Internal helpers ───────────────────────────────────────────────────

    def _make_placeholder(self) -> QTreeWidgetItem:
        ph = QTreeWidgetItem(["  …"])
        ph.setData(0, _ROLE_TYPE, "placeholder")
        ph.setForeground(0, QColor(PHOSPHOR_DIM))
        ph.setFont(0, _mono(12))
        ph.setFlags(ph.flags() & ~Qt.ItemFlag.ItemIsSelectable)
        return ph

    # ── Context menu ───────────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self._tree.itemAt(pos)
        if item is None or item.data(0, _ROLE_TYPE) != "course":
            return

        cid      = item.data(0, _ROLE_ID)
        nickname = item.data(0, _ROLE_NICKNAME) or ""
        fmt      = item.data(0, _ROLE_FORMAT)   or ""

        from gui.styles import menu_qss
        menu = QMenu(self._tree)
        menu.setStyleSheet(menu_qss())

        # ── Nickname ──────────────────────────────────────────────────────
        nick_act = menu.addAction("Set Nickname…")
        nick_act.triggered.connect(lambda: self._edit_nickname(item, cid))

        if nickname:
            clear_nick = menu.addAction("Clear Nickname")
            clear_nick.triggered.connect(lambda: self._clear_nickname(item, cid))

        # ── Push to Canvas — always shown so users know the feature exists ─
        menu.addSeparator()
        push_act = menu.addAction("Push Name to Canvas…")
        push_act.setEnabled(bool(nickname and self._editor))
        if not nickname:
            push_act.setToolTip("Set a nickname first to enable this action.")
        elif not self._editor:
            push_act.setToolTip("Connect to Canvas in Settings to enable this action.")
        else:
            push_act.triggered.connect(
                lambda: self._offer_push_to_canvas(item, cid, nickname)
            )

        menu.addSeparator()

        # ── Modality ─────────────────────────────────────────────────────
        fmt_menu = menu.addMenu("Set Modality")
        for key, label in _MODALITY_MENU:
            act = fmt_menu.addAction(label)
            act.setEnabled(fmt != key)
            act.triggered.connect(
                lambda checked, k=key: self._set_format(item, cid, k)
            )
        fmt_menu.addSeparator()
        clear_fmt = fmt_menu.addAction("Clear (not set)")
        clear_fmt.setEnabled(bool(fmt))
        clear_fmt.triggered.connect(lambda: self._clear_format(item, cid))

        # ── Publish / Unpublish course ────────────────────────────────
        menu.addSeparator()
        is_published = item.data(0, _ROLE_PUBLISHED)
        if is_published is None:
            is_published = True

        if is_published:
            unpub_act = menu.addAction("Unpublish Course…")
            unpub_act.setEnabled(bool(self._editor))
            if not self._editor:
                unpub_act.setToolTip("Connect to Canvas in Settings to enable this action.")
            else:
                unpub_act.triggered.connect(
                    lambda: self._toggle_course_publish(item, cid, False)
                )
        else:
            pub_act = menu.addAction("Publish Course")
            pub_act.setEnabled(bool(self._editor))
            if not self._editor:
                pub_act.setToolTip("Connect to Canvas in Settings to enable this action.")
            else:
                pub_act.triggered.connect(
                    lambda: self._toggle_course_publish(item, cid, True)
                )

        menu.exec(self._tree.viewport().mapToGlobal(pos))

    def _edit_nickname(self, item: QTreeWidgetItem, cid: int) -> None:
        # Pre-populate: existing nickname first, then fall back to extracted title
        current = (
            item.data(0, _ROLE_NICKNAME)
            or item.data(0, _ROLE_TITLE)
            or ""
        )
        text, ok = QInputDialog.getText(
            self, "Set Nickname",
            "Custom name for this course (shown below the code):",
            text=current,
        )
        if not ok:
            return

        nick = text.strip()
        if nick:
            _meta.set_nickname(cid, nick)
        else:
            _meta.clear_nickname(cid)
        item.setData(0, _ROLE_NICKNAME, nick)
        self._tree.update(self._tree.indexFromItem(item))

    def _clear_nickname(self, item: QTreeWidgetItem, cid: int) -> None:
        _meta.clear_nickname(cid)
        item.setData(0, _ROLE_NICKNAME, "")
        self._tree.update(self._tree.indexFromItem(item))

    def _set_format(self, item: QTreeWidgetItem, cid: int, fmt: str) -> None:
        _meta.set_format(cid, fmt)
        item.setData(0, _ROLE_FORMAT, fmt)
        self._tree.update(self._tree.indexFromItem(item))

    def _clear_format(self, item: QTreeWidgetItem, cid: int) -> None:
        _meta.clear_format(cid)
        item.setData(0, _ROLE_FORMAT, "")
        self._tree.update(self._tree.indexFromItem(item))

    def _offer_push_to_canvas(
        self, item: QTreeWidgetItem, cid: int, nickname: str
    ) -> None:
        """Custom confirmation dialog — polished comparison of old vs new name."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton
        from PySide6.QtCore import QSize

        original = item.data(0, _ROLE_NAME) or ""

        dlg = QDialog(self)
        dlg.setWindowTitle("Push Name to Canvas")
        dlg.setFixedWidth(480)
        dlg.setStyleSheet(f"""
            QDialog {{
                background: #120900;
                border: 1px solid {BORDER_AMBER};
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; border: none; }}
            QPushButton {{
                background: #1E1200;
                color: {PHOSPHOR_MID};
                border: 1px solid #4A3000;
                border-radius: 4px;
                padding: 6px 20px;
                font-family: Menlo;
                font-size: {px(11)}px;
            }}
            QPushButton:hover {{ background: #2A1A00; color: {PHOSPHOR_HOT}; border-color: {BORDER_AMBER}; }}
            QPushButton#confirm {{ color: {PHOSPHOR_HOT}; border-color: {BORDER_AMBER}; }}
            QPushButton#confirm:hover {{ background: #3A2200; }}
        """)

        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(0)

        def _row(label_text, value_text, value_color=PHOSPHOR_MID):
            from PySide6.QtWidgets import QLabel
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label_text)
            lbl.setFont(_mono(9))
            lbl.setStyleSheet(f"color: {PHOSPHOR_DIM}; min-width: 90px;")
            lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            val = QLabel(value_text)
            val.setFont(_mono(10))
            val.setStyleSheet(f"color: {value_color};")
            val.setWordWrap(True)
            row.addWidget(lbl)
            row.addWidget(val, 1)
            return row

        from PySide6.QtWidgets import QLabel, QFrame
        heading = QLabel("Update course name in Canvas?")
        heading.setFont(_mono(12, bold=True))
        heading.setStyleSheet(f"color: {PHOSPHOR_HOT}; padding-bottom: 12px;")
        layout.addWidget(heading)

        layout.addLayout(_row("Current:", original, PHOSPHOR_DIM))
        layout.addSpacing(4)
        layout.addLayout(_row("New name:", nickname, PHOSPHOR_HOT))
        layout.addSpacing(14)

        notice = QLabel(
            "Students, TAs, and co-instructors will see the new name in Canvas."
        )
        notice.setFont(_mono(9))
        notice.setStyleSheet(f"color: {PHOSPHOR_DIM}; padding-bottom: 14px;")
        notice.setWordWrap(True)
        layout.addWidget(notice)

        sep = QFrame()
        sep.setFixedHeight(1)
        sep.setStyleSheet(f"background: #2A1A00; border: none;")
        layout.addWidget(sep)
        layout.addSpacing(12)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Keep Local Only")
        cancel_btn.clicked.connect(dlg.reject)
        confirm_btn = QPushButton("Push to Canvas")
        confirm_btn.setObjectName("confirm")
        confirm_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addSpacing(8)
        btn_row.addWidget(confirm_btn)
        layout.addLayout(btn_row)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._push_name_to_canvas(item, cid, nickname)

    def _push_name_to_canvas(
        self, item: QTreeWidgetItem, cid: int, nickname: str
    ) -> None:
        """Fire the Canvas rename worker (no dialog — caller handles confirmation)."""
        from gui.workers import EditAssignmentWorker
        w = EditAssignmentWorker(
            api=None,
            editor=self._editor,
            fn=lambda: self._editor.rename_course(cid, nickname),
        )
        w.result_ready.connect(
            lambda result, _item=item, _nick=nickname:
                self._on_push_result(result, _item, _nick)
        )
        w.finished.connect(
            lambda: self._active_workers.remove(w)
            if w in self._active_workers else None
        )
        self._active_workers.append(w)
        w.start()

    def _on_push_result(
        self, result, item: QTreeWidgetItem, nickname: str
    ) -> None:
        if result.ok:
            # Update stored name so subsequent pushes show the right "current" value
            item.setData(0, _ROLE_NAME, nickname)
            show_info(
                self,
                "Name Updated",
                f"Canvas course name updated to:\n{nickname}",
            )
        else:
            show_warning(
                self,
                "Could Not Update Canvas",
                result.message or "The name could not be changed on Canvas.",
            )

    # ── Course publish / unpublish ─────────────────────────────────────────

    def _toggle_course_publish(
        self, item: QTreeWidgetItem, cid: int, publish: bool
    ) -> None:
        """Publish or unpublish a course on Canvas, running preflight first."""
        if not self._editor:
            return
        if not publish:
            # Preflight: check for enrolled students before unpublishing
            from gui.workers import EditAssignmentWorker
            w = EditAssignmentWorker(
                api=None,
                editor=self._editor,
                fn=lambda: self._editor.preflight_unpublish_course(cid),
            )
            w.result_ready.connect(
                lambda result, _item=item, _cid=cid, _pub=publish:
                    self._handle_course_publish_preflight(result, _item, _cid, _pub)
            )
            w.finished.connect(
                lambda: self._active_workers.remove(w)
                if w in self._active_workers else None
            )
            self._active_workers.append(w)
            w.start()
        else:
            self._execute_course_publish(item, cid, True)

    def _handle_course_publish_preflight(
        self, result, item: QTreeWidgetItem, cid: int, publish: bool
    ) -> None:
        if hasattr(result, "safe"):
            if result.safe:
                self._execute_course_publish(item, cid, publish)
                return
            if not result.can_proceed:
                msgs = "\n\n".join(w.message for w in result.blocking_warnings)
                show_critical(self, "Cannot Unpublish", msgs)
                return
            if result.advisory_warnings:
                msgs = "\n\n".join(w.message for w in result.advisory_warnings)
                reply = show_warning(
                    self, "Unpublish Course?",
                    msgs + "\n\nUnpublish course anyway?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    self._execute_course_publish(item, cid, publish)
                return
            self._execute_course_publish(item, cid, publish)
        else:
            if hasattr(result, "ok") and not result.ok:
                show_warning(self, "Preflight Error", result.message)
                return
            self._execute_course_publish(item, cid, publish)

    def _execute_course_publish(
        self, item: QTreeWidgetItem, cid: int, publish: bool
    ) -> None:
        from gui.workers import EditAssignmentWorker
        w = EditAssignmentWorker(
            api=None,
            editor=self._editor,
            fn=lambda: self._editor.set_course_published(cid, publish),
        )
        w.result_ready.connect(
            lambda result, _item=item, _pub=publish:
                self._on_course_publish_result(result, _item, _pub)
        )
        w.finished.connect(
            lambda: self._active_workers.remove(w)
            if w in self._active_workers else None
        )
        self._active_workers.append(w)
        w.start()

    def _on_course_publish_result(
        self, result, item: QTreeWidgetItem, publish: bool
    ) -> None:
        if result.ok:
            item.setData(0, _ROLE_PUBLISHED, publish)
            action = "published" if publish else "unpublished"
            show_info(
                self,
                "Course Updated",
                f"Course successfully {action} on Canvas.",
            )
        else:
            action = "publish" if publish else "unpublish"
            show_warning(
                self,
                "Could Not Update Canvas",
                f"Could not {action} course:\n\n{result.message}",
            )

    # ── Signal handlers ────────────────────────────────────────────────────

    def _on_item_expanded(self, item: QTreeWidgetItem) -> None:
        if item.data(0, _ROLE_TYPE) == "term":
            self._update_term_arrow(item, expanded=True)
            self.term_selected.emit(item.data(0, _ROLE_ID))

    def _on_item_collapsed(self, item: QTreeWidgetItem) -> None:
        if item.data(0, _ROLE_TYPE) == "term":
            self._update_term_arrow(item, expanded=False)

    def _update_term_arrow(self, item: QTreeWidgetItem, expanded: bool) -> None:
        """Swap the leading arrow character: v expanded, > collapsed."""
        text = item.text(0)
        old_arrow = "v" if not expanded else ">"
        new_arrow = "v" if expanded else ">"
        if text.startswith(f"{old_arrow}  "):
            item.setText(0, f"{new_arrow}  {text[3:]}")

    def get_all_courses_by_term(self) -> list:
        """Return [(term_id, term_name, is_current, [course_dicts]), ...] from tree data."""
        result = []
        root = self._tree.invisibleRootItem()
        for i in range(root.childCount()):
            term_item = root.child(i)
            if term_item.data(0, _ROLE_TYPE) != "term":
                continue
            term_id = term_item.data(0, _ROLE_ID)
            raw_label = term_item.text(0)
            is_current = "●" in raw_label
            # Strip arrow prefix ("v  " or ">  ") and "  ●" suffix to get clean term name
            clean_name = raw_label
            for pfx in ("v  ", ">  "):
                clean_name = clean_name.replace(pfx, "", 1)
            clean_name = clean_name.replace("  ●", "").strip()
            courses = []
            for j in range(term_item.childCount()):
                child = term_item.child(j)
                if child.data(0, _ROLE_TYPE) != "course":
                    continue
                courses.append({
                    "id":       child.data(0, _ROLE_ID),
                    "name":     child.data(0, _ROLE_NAME),
                    "code":     child.data(0, _ROLE_CODE),
                    "title":    child.data(0, _ROLE_TITLE),
                    "format":   child.data(0, _ROLE_FORMAT),
                    "nickname": child.data(0, _ROLE_NICKNAME),
                    "term_id":  term_id,
                })
            if courses:
                result.append((term_id, clean_name, is_current, courses))
        return result

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        item_type = item.data(0, _ROLE_TYPE)

        if item_type == "term":
            if item.isExpanded():
                self._tree.collapseItem(item)
            else:
                self._tree.expandItem(item)
            return

        if item_type != "course":
            return

        parent = item.parent()
        if parent:
            self.term_selected.emit(parent.data(0, _ROLE_ID))

        title = item.data(0, _ROLE_NICKNAME) or item.data(0, _ROLE_TITLE) or ""
        code  = item.data(0, _ROLE_CODE) or ""
        display_name = f"{title} ({code})" if title and code else title or code or ""
        self.course_selected.emit(item.data(0, _ROLE_ID), display_name)
