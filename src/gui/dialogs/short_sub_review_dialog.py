"""
ShortSubReviewDialog — Teacher review queue for Short Submission Review results.

Shows each pending SSR-CREDIT submission with the LLM's assessment.
Teacher can accept (post CREDIT to Canvas) or reject (leave incomplete).
"""

from __future__ import annotations

from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QWidget, QTextEdit,
)

from gui.styles import (
    px,
    PHOSPHOR_HOT, PHOSPHOR_MID, PHOSPHOR_DIM,
    TERM_GREEN, BURN_RED, STATUS_WARN,
    BG_VOID, BG_CARD, BG_INSET,
    BORDER_DARK, BORDER_AMBER, ROSE_ACCENT,
    GripSplitter,
    make_section_label, make_h_rule,
)


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

_ST_PENDING  = "pending"
_ST_ACCEPTED = "accepted"
_ST_REJECTED = "rejected"
_ST_SKIPPED  = "skipped"

_ST_COLOR = {
    _ST_PENDING:  PHOSPHOR_DIM,
    _ST_ACCEPTED: TERM_GREEN,
    _ST_REJECTED: BURN_RED,
    _ST_SKIPPED:  PHOSPHOR_DIM,
}

_VERDICT_COLOR = {
    "CREDIT":        TERM_GREEN,
    "TEACHER_REVIEW": STATUS_WARN,
}


# ---------------------------------------------------------------------------
# _StudentRow — sidebar row
# ---------------------------------------------------------------------------

class _StudentRow(QWidget):
    """Single row in the student list sidebar."""

    def __init__(self, key: str, review_item: dict, parent=None):
        super().__init__(parent)
        self.key = key
        self.review_item = review_item
        self._status = _ST_PENDING

        lo = QHBoxLayout(self)
        lo.setContentsMargins(8, 4, 8, 4)
        lo.setSpacing(8)

        self._pip = QLabel("●")
        self._pip.setFixedWidth(12)
        self._pip.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(8)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._pip)

        name = review_item.get("student_name") or f"User {review_item.get('user_id', '?')}"
        aname = review_item.get("assignment_name", "")
        conf = review_item.get("review", {}).get("confidence", 0.0)

        self._name_lbl = QLabel(name)
        self._name_lbl.setStyleSheet(
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._name_lbl, 1)

        self._conf_lbl = QLabel(f"{int(conf * 100)}%")
        self._conf_lbl.setFixedWidth(36)
        self._conf_lbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._conf_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px;"
            f" background: transparent; border: none;"
        )
        lo.addWidget(self._conf_lbl)

        self.setToolTip(aname)
        self.setMinimumHeight(34)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_status(self, status: str) -> None:
        self._status = status
        color = _ST_COLOR.get(status, PHOSPHOR_DIM)
        self._pip.setStyleSheet(
            f"color: {color}; font-size: {px(8)}px;"
            f" background: transparent; border: none;"
        )

    def set_selected(self, selected: bool) -> None:
        bg = f"background: rgba(240,168,48,0.10);" if selected else "background: transparent;"
        color = PHOSPHOR_HOT if selected else PHOSPHOR_MID
        self._name_lbl.setStyleSheet(
            f"color: {color}; font-size: {px(11)}px; {bg} border: none;"
        )
        self.setStyleSheet(bg)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            p = self.parent()
            while p and not isinstance(p, ShortSubReviewDialog):
                p = p.parent()
            if p:
                p._select_key(self.key)


# ---------------------------------------------------------------------------
# ShortSubReviewDialog
# ---------------------------------------------------------------------------

class ShortSubReviewDialog(QDialog):
    """Modal dialog for reviewing SSR-CREDIT pending submissions.

    reviews: dict produced by RunWorker._ssr_accumulated_reviews
        key: "{aid}:{user_id}"
        value: {student_name, submission_text, assignment_id, assignment_name,
                course_id, course_name, user_id, review: {verdict, ...}}
    api: Canvas API object (used to post grades on accept)
    """

    def __init__(self, reviews: dict, api=None, parent=None):
        super().__init__(parent)
        self._reviews = reviews
        self._api = api
        self._keys: List[str] = list(reviews.keys())
        self._statuses: Dict[str, str] = {k: _ST_PENDING for k in self._keys}
        self._current_key: Optional[str] = self._keys[0] if self._keys else None
        self._row_widgets: Dict[str, _StudentRow] = {}

        self.setWindowTitle("Review Short Submissions")
        self.setModal(True)
        self.resize(1000, 640)
        self.setMinimumSize(760, 480)

        self.setStyleSheet(f"QDialog {{ background: {BG_VOID}; }}")

        self._build_ui()
        if self._current_key:
            self._select_key(self._current_key, update_sidebar=False)
            self._update_sidebar_selection()

    # ── UI construction ───────────────────────────────────────────────

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Header ────────────────────────────────────────────────────
        hdr = QWidget()
        hdr.setStyleSheet(f"background: {BG_CARD}; border-bottom: 1px solid {BORDER_AMBER};")
        hdr_lo = QHBoxLayout(hdr)
        hdr_lo.setContentsMargins(20, 12, 20, 12)
        hdr_lo.setSpacing(16)

        title = QLabel("SHORT SUBMISSION REVIEW")
        title.setStyleSheet(
            f"color: {PHOSPHOR_HOT}; font-size: {px(13)}px; font-weight: bold;"
            f" letter-spacing: 2px; background: transparent; border: none;"
        )
        hdr_lo.addWidget(title)
        hdr_lo.addStretch()

        self._counter_lbl = QLabel("")
        self._counter_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        hdr_lo.addWidget(self._counter_lbl)

        self._post_all_btn = QPushButton("Post All ≥70%")
        self._post_all_btn.setStyleSheet(
            f"QPushButton {{ color: {TERM_GREEN}; border: 1px solid {TERM_GREEN};"
            f" border-radius: 4px; padding: 4px 12px; background: transparent; }}"
            f" QPushButton:hover {{ background: rgba(48,200,80,0.12); }}"
        )
        self._post_all_btn.clicked.connect(self._on_post_all_high_confidence)
        hdr_lo.addWidget(self._post_all_btn)

        root.addWidget(hdr)

        # ── Body: sidebar + content ───────────────────────────────────
        body = QWidget()
        body.setStyleSheet(f"background: {BG_VOID};")
        body_lo = QHBoxLayout(body)
        body_lo.setContentsMargins(0, 0, 0, 0)
        body_lo.setSpacing(0)
        root.addWidget(body, 1)

        # Left sidebar
        sidebar = QFrame()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet(
            f"QFrame {{ background: {BG_INSET}; border-right: 1px solid {BORDER_DARK};"
            f" border-top: none; border-left: none; border-bottom: none; }}"
        )
        sb_lo = QVBoxLayout(sidebar)
        sb_lo.setContentsMargins(0, 0, 0, 0)
        sb_lo.setSpacing(0)

        sb_lbl = QLabel("STUDENTS")
        sb_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; font-weight: bold;"
            f" letter-spacing: 1.5px; padding: 8px 12px 4px 12px;"
            f" background: transparent; border: none;"
        )
        sb_lo.addWidget(sb_lbl)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        self._sidebar_lo = QVBoxLayout(container)
        self._sidebar_lo.setContentsMargins(0, 0, 0, 0)
        self._sidebar_lo.setSpacing(0)
        self._sidebar_lo.addStretch()
        scroll.setWidget(container)
        sb_lo.addWidget(scroll, 1)
        body_lo.addWidget(sidebar)

        # Populate sidebar rows
        for key in self._keys:
            row = _StudentRow(key, self._reviews[key], parent=container)
            self._row_widgets[key] = row
            self._sidebar_lo.insertWidget(self._sidebar_lo.count() - 1, row)

        # Right content area: split horizontally (submission | assessment)
        content = QWidget()
        content.setStyleSheet(f"background: {BG_VOID};")
        content_lo = QVBoxLayout(content)
        content_lo.setContentsMargins(0, 0, 0, 0)
        content_lo.setSpacing(0)
        body_lo.addWidget(content, 1)

        splitter = GripSplitter.create(Qt.Orientation.Horizontal)

        # Left pane: submission text
        left_pane = QFrame()
        left_pane.setStyleSheet("background: transparent; border: none;")
        left_lo = QVBoxLayout(left_pane)
        left_lo.setContentsMargins(16, 12, 8, 8)
        left_lo.setSpacing(6)
        left_lo.addWidget(make_section_label("Submission Text"))

        self._meta_lbl = QLabel("")
        self._meta_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(10)}px;"
            f" background: transparent; border: none;"
        )
        left_lo.addWidget(self._meta_lbl)

        self._text_view = QTextEdit()
        self._text_view.setReadOnly(True)
        font = QFont("Menlo")
        font.setPixelSize(px(11))
        font.setStyleHint(QFont.StyleHint.Monospace)
        self._text_view.setFont(font)
        self._text_view.setStyleSheet(
            f"background: {BG_INSET}; border: 1px solid {BORDER_DARK};"
            f" border-radius: 6px; color: {PHOSPHOR_MID};"
            f" padding: 8px; line-height: 1.5;"
        )
        left_lo.addWidget(self._text_view, 1)
        splitter.addWidget(left_pane)

        # Right pane: assessment
        right_pane = QFrame()
        right_pane.setStyleSheet("background: transparent; border: none;")
        right_lo = QVBoxLayout(right_pane)
        right_lo.setContentsMargins(8, 12, 16, 8)
        right_lo.setSpacing(6)
        right_lo.addWidget(make_section_label("LLM Assessment"))

        self._assessment_scroll = QScrollArea()
        self._assessment_scroll.setWidgetResizable(True)
        self._assessment_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._assessment_scroll.setStyleSheet("background: transparent; border: none;")
        self._assessment_widget = QWidget()
        self._assessment_widget.setStyleSheet("background: transparent;")
        self._assessment_lo = QVBoxLayout(self._assessment_widget)
        self._assessment_lo.setContentsMargins(0, 0, 0, 0)
        self._assessment_lo.setSpacing(8)
        self._assessment_lo.addStretch()
        self._assessment_scroll.setWidget(self._assessment_widget)
        right_lo.addWidget(self._assessment_scroll, 1)
        splitter.addWidget(right_pane)

        splitter.setSizes([420, 340])
        content_lo.addWidget(splitter, 1)

        # ── Footer: action buttons ─────────────────────────────────────
        footer = QWidget()
        footer.setStyleSheet(
            f"background: {BG_CARD}; border-top: 1px solid {BORDER_DARK};"
        )
        foot_lo = QHBoxLayout(footer)
        foot_lo.setContentsMargins(20, 10, 20, 10)
        foot_lo.setSpacing(10)

        self._prev_btn = QPushButton("← Prev")
        self._prev_btn.clicked.connect(self._on_prev)
        foot_lo.addWidget(self._prev_btn)

        self._next_btn = QPushButton("Next →")
        self._next_btn.clicked.connect(self._on_next)
        foot_lo.addWidget(self._next_btn)

        foot_lo.addStretch()

        self._skip_btn = QPushButton("Skip")
        self._skip_btn.clicked.connect(self._on_skip)
        foot_lo.addWidget(self._skip_btn)

        self._reject_btn = QPushButton("Reject — Leave Incomplete")
        self._reject_btn.setStyleSheet(
            f"QPushButton {{ color: {BURN_RED}; border: 1px solid {BURN_RED};"
            f" border-radius: 4px; padding: 4px 12px; background: transparent; }}"
            f" QPushButton:hover {{ background: rgba(200,60,60,0.12); }}"
        )
        self._reject_btn.clicked.connect(self._on_reject)
        foot_lo.addWidget(self._reject_btn)

        self._accept_btn = QPushButton("Accept — Post CREDIT")
        self._accept_btn.setStyleSheet(
            f"QPushButton {{ color: {TERM_GREEN}; border: 1px solid {TERM_GREEN};"
            f" border-radius: 4px; padding: 4px 12px; background: transparent; font-weight: bold; }}"
            f" QPushButton:hover {{ background: rgba(48,200,80,0.15); }}"
        )
        self._accept_btn.clicked.connect(self._on_accept)
        foot_lo.addWidget(self._accept_btn)

        self._close_btn = QPushButton("Done")
        self._close_btn.clicked.connect(self.accept)
        foot_lo.addWidget(self._close_btn)

        content_lo.addWidget(footer)

        self._update_counter()

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _esc(text: str) -> str:
        """Escape HTML special chars."""
        return (text.replace("&", "&amp;")
                    .replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace('"', "&quot;"))

    def _render_thread_html(
        self, reviewed_text: str, ctx: dict, wc: int
    ) -> str:
        """Build an HTML thread view for the QTextEdit.

        Parent post and siblings are dimmed; the reviewed reply is
        full-brightness with a ROSE_ACCENT left-border stripe.
        """
        dim = PHOSPHOR_DIM
        mid = PHOSPHOR_MID
        rose = ROSE_ACCENT

        parts = [
            f'<html><body style="background:{BG_INSET}; '
            f'font-family:Menlo,Courier New,monospace; font-size:11px;">'
        ]

        # Parent / original post
        parent = ctx.get("parent_post", "")
        if parent:
            parts.append(
                f'<p style="color:{dim}; font-size:10px; '
                f'font-weight:bold; margin:0 0 2px 0;">ORIGINAL POST</p>'
                f'<p style="color:{dim}; margin:0 0 12px 0;">'
                f'{self._esc(parent[:400])}</p>'
            )

        # Sibling replies — dim all, highlight the reviewed one
        reviewed_idx = ctx.get("reviewed_reply_index", -1)
        for i, reply in enumerate(ctx.get("sibling_replies", [])):
            is_reviewed = (i == reviewed_idx)
            if is_reviewed:
                # Rose left-stripe using a 1-row table (Qt HTML reliable)
                parts.append(
                    f'<table width="100%" cellspacing="0" cellpadding="0"'
                    f' style="margin-bottom:8px;">'
                    f'<tr>'
                    f'<td width="3" bgcolor="{rose}">&nbsp;</td>'
                    f'<td style="padding-left:8px;">'
                    f'<span style="color:{rose}; font-size:9px; '
                    f'font-weight:bold;">▶ THIS REPLY ({wc} words)</span><br>'
                    f'<span style="color:{mid};">'
                    f'{self._esc(reviewed_text)}</span>'
                    f'</td></tr></table>'
                )
            else:
                parts.append(
                    f'<p style="color:{dim}; margin:0 0 8px 4px;">'
                    f'Reply {i + 1}: {self._esc(reply[:200])}</p>'
                )

        parts.append("</body></html>")
        return "".join(parts)

    def _persist_override(self, item: dict, grade: str, reason: str) -> None:
        """Persist teacher decision to RunStore (non-critical, silently fails)."""
        try:
            from automation.run_store import RunStore
            store = RunStore()
            store.set_teacher_override(
                student_id=str(item.get("user_id", "")),
                assignment_id=str(item.get("assignment_id", "")),
                grade=grade,
                reason=reason,
            )
            store.close()
        except Exception:
            pass

    # ── Navigation ────────────────────────────────────────────────────

    def _select_key(self, key: str, update_sidebar: bool = True) -> None:
        if key not in self._reviews:
            return
        self._current_key = key
        item = self._reviews[key]
        review = item.get("review", {})

        # Update submission pane
        text = item.get("submission_text", "")
        wc = len(text.split()) if text else 0
        name = item.get("student_name") or f"User {item.get('user_id', '?')}"
        aname = item.get("assignment_name", "")
        cname = item.get("course_name", "")

        thread_ctx = review.get("thread_context")
        if thread_ctx:
            self._text_view.setHtml(
                self._render_thread_html(text, thread_ctx, wc)
            )
        else:
            self._text_view.setPlainText(text)

        self._meta_lbl.setText(
            f"{name}  ·  {aname}  ·  {cname}  ·  {wc} words"
        )

        # Rebuild assessment pane
        self._rebuild_assessment(review)

        if update_sidebar:
            self._update_sidebar_selection()
        self._update_counter()
        self._update_nav_buttons()

    def _update_sidebar_selection(self) -> None:
        for k, row in self._row_widgets.items():
            row.set_selected(k == self._current_key)

    def _on_prev(self) -> None:
        if not self._current_key:
            return
        idx = self._keys.index(self._current_key)
        if idx > 0:
            self._select_key(self._keys[idx - 1])

    def _on_next(self) -> None:
        if not self._current_key:
            return
        idx = self._keys.index(self._current_key)
        if idx < len(self._keys) - 1:
            self._select_key(self._keys[idx + 1])

    def _update_nav_buttons(self) -> None:
        if not self._current_key:
            return
        idx = self._keys.index(self._current_key)
        self._prev_btn.setEnabled(idx > 0)
        self._next_btn.setEnabled(idx < len(self._keys) - 1)

    def _update_counter(self) -> None:
        pending = sum(1 for s in self._statuses.values() if s == _ST_PENDING)
        total = len(self._keys)
        self._counter_lbl.setText(f"{pending} pending / {total} total")

    # ── Assessment pane ───────────────────────────────────────────────

    def _rebuild_assessment(self, review: dict) -> None:
        # Clear existing widgets
        while self._assessment_lo.count() > 1:  # keep trailing stretch
            item = self._assessment_lo.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        verdict = review.get("verdict", "")
        conf = review.get("confidence", 0.0)
        category = review.get("brevity_category", "")
        rationale = review.get("rationale", "")
        evidence = review.get("engagement_evidence") or []
        teacher_note = review.get("teacher_note")
        bias_warning = review.get("bias_warning")

        _label_qss = (
            f"color: {PHOSPHOR_DIM}; font-size: {px(9)}px; font-weight: bold;"
            f" letter-spacing: 1px; background: transparent; border: none;"
        )
        _value_qss = (
            f"color: {PHOSPHOR_MID}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )

        # Verdict row
        row = QHBoxLayout()
        v_color = _VERDICT_COLOR.get(verdict, PHOSPHOR_DIM)
        verdict_lbl = QLabel(verdict or "—")
        verdict_lbl.setStyleSheet(
            f"color: {v_color}; font-size: {px(16)}px; font-weight: bold;"
            f" background: transparent; border: none;"
        )
        row.addWidget(verdict_lbl)
        row.addStretch()
        conf_lbl = QLabel(f"{int(conf * 100)}% confidence")
        conf_lbl.setStyleSheet(
            f"color: {PHOSPHOR_DIM}; font-size: {px(11)}px;"
            f" background: transparent; border: none;"
        )
        row.addWidget(conf_lbl)
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container.setLayout(row)
        self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, container)

        if category:
            cat_lbl = QLabel(f"Category: {category.replace('_', ' ')}")
            cat_lbl.setStyleSheet(_value_qss)
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, cat_lbl)

        self._assessment_lo.insertWidget(
            self._assessment_lo.count() - 1, make_h_rule()
        )

        # Rationale
        if rationale:
            r_head = QLabel("RATIONALE")
            r_head.setStyleSheet(_label_qss)
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, r_head)
            r_body = QLabel(rationale)
            r_body.setWordWrap(True)
            r_body.setStyleSheet(_value_qss)
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, r_body)

        # Engagement evidence
        if evidence:
            e_head = QLabel("ENGAGEMENT EVIDENCE")
            e_head.setStyleSheet(_label_qss)
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, e_head)
            for e in evidence:
                e_item = QLabel(f"• {e}")
                e_item.setWordWrap(True)
                e_item.setStyleSheet(_value_qss)
                self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, e_item)

        # Teacher note
        if teacher_note:
            self._assessment_lo.insertWidget(
                self._assessment_lo.count() - 1, make_h_rule()
            )
            tn_head = QLabel("TEACHER NOTE")
            tn_head.setStyleSheet(_label_qss)
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, tn_head)
            tn_body = QLabel(teacher_note)
            tn_body.setWordWrap(True)
            tn_body.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(11)}px;"
                f" background: transparent; border: none;"
            )
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, tn_body)

        # Bias warning
        if bias_warning:
            bw_lbl = QLabel(bias_warning)
            bw_lbl.setWordWrap(True)
            bw_lbl.setStyleSheet(
                f"color: {STATUS_WARN}; font-size: {px(10)}px; font-style: italic;"
                f" background: rgba(255,176,0,0.06); border: 1px solid rgba(255,176,0,0.25);"
                f" border-radius: 4px; padding: 6px;"
            )
            self._assessment_lo.insertWidget(self._assessment_lo.count() - 1, bw_lbl)

    # ── Actions ───────────────────────────────────────────────────────

    def _on_skip(self) -> None:
        if not self._current_key:
            return
        self._statuses[self._current_key] = _ST_SKIPPED
        self._row_widgets[self._current_key].set_status(_ST_SKIPPED)
        self._update_counter()
        self._advance()

    def _on_reject(self) -> None:
        if not self._current_key:
            return
        item = self._reviews[self._current_key]
        self._persist_override(
            item, "incomplete",
            "Short Sub Review: Teacher reviewed and kept incomplete"
        )
        self._statuses[self._current_key] = _ST_REJECTED
        self._row_widgets[self._current_key].set_status(_ST_REJECTED)
        self._update_counter()
        self._advance()

    def _on_accept(self) -> None:
        if not self._current_key:
            return
        item = self._reviews[self._current_key]
        # Persist decision before Canvas post so it's never lost
        self._persist_override(
            item, "complete",
            "Short Sub Review: Teacher accepted CREDIT verdict"
        )
        success = self._post_credit_to_canvas(item)
        status = _ST_ACCEPTED if success else _ST_PENDING
        self._statuses[self._current_key] = status
        self._row_widgets[self._current_key].set_status(status)
        self._update_counter()
        if success:
            self._advance()

    def _on_post_all_high_confidence(self) -> None:
        """Post all pending reviews with confidence >= 0.70 to Canvas."""
        posted = 0
        for key, item in self._reviews.items():
            if self._statuses[key] != _ST_PENDING:
                continue
            conf = item.get("review", {}).get("confidence", 0.0)
            if conf >= 0.70:
                self._persist_override(
                    item, "complete",
                    "Short Sub Review: Teacher accepted via Post All ≥70%"
                )
                success = self._post_credit_to_canvas(item)
                if success:
                    self._statuses[key] = _ST_ACCEPTED
                    self._row_widgets[key].set_status(_ST_ACCEPTED)
                    posted += 1

        self._update_counter()
        self._post_all_btn.setText(f"Post All ≥70% (done: {posted})")
        self._post_all_btn.setEnabled(False)

    def _advance(self) -> None:
        """Move to the next pending item, or stay if none remain."""
        if not self._current_key:
            return
        idx = self._keys.index(self._current_key)
        # Try next pending after current
        for i in range(idx + 1, len(self._keys)):
            if self._statuses[self._keys[i]] == _ST_PENDING:
                self._select_key(self._keys[i])
                return
        # Try next pending before current
        for i in range(0, idx):
            if self._statuses[self._keys[i]] == _ST_PENDING:
                self._select_key(self._keys[i])
                return

    def _post_credit_to_canvas(self, item: dict) -> bool:
        """Submit 'complete' grade to Canvas. Returns True on success.

        No student-facing comment is added — the teacher-facing audit trail
        lives in RunStore (teacher_override + override_reason).
        """
        if not self._api:
            return False
        try:
            import requests as _req
            aid = item.get("assignment_id")
            cid = item.get("course_id")
            uid = item.get("user_id")
            base = self._api.base_url.rstrip("/")
            url = (f"{base}/api/v1/courses/{cid}/assignments/{aid}"
                   f"/submissions/{uid}")
            r = _req.put(
                url,
                headers=self._api.headers,
                json={"submission": {"posted_grade": "complete"}},
                timeout=30,
            )
            r.raise_for_status()
            return True
        except Exception:
            return False

    # ── Keyboard shortcuts ────────────────────────────────────────────

    def keyPressEvent(self, event) -> None:
        key = event.key()
        if key == Qt.Key.Key_Left:
            self._on_prev()
        elif key == Qt.Key.Key_Right:
            self._on_next()
        elif key == Qt.Key.Key_Return or key == Qt.Key.Key_Enter:
            self._on_accept()
        elif key == Qt.Key.Key_Delete or key == Qt.Key.Key_Backspace:
            self._on_reject()
        elif key == Qt.Key.Key_Escape:
            self.accept()
        else:
            super().keyPressEvent(event)
