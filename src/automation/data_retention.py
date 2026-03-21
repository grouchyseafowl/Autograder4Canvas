"""
Auto-retention backend — runs at app startup to purge aged internal data.

Reads data_retention_* keys from settings.json and deletes records older than
the configured threshold from RunStore (grading, AIC, notes) and InsightsStore
(runs, codings, themes, feedback drafts).

Called from MainWindow.__init__ on a background thread so it never blocks the UI.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone


def run_auto_retention() -> dict | None:
    """Check settings and delete aged records if retention is enabled.

    Returns a summary dict on success, or None if retention is disabled /
    nothing to do.  Exceptions are caught and printed — this must never
    crash the app at startup.
    """
    try:
        from settings import load_settings

        s = load_settings()
        if not s.get("data_retention_enabled", False):
            return None

        years = int(s.get("data_retention_years", 0))
        days  = int(s.get("data_retention_days", 90))
        total_days = years * 365 + days

        if total_days <= 0:
            return None

        incl_grading  = bool(s.get("data_retention_grading", True))
        incl_aic      = bool(s.get("data_retention_aic", True))
        incl_notes    = bool(s.get("data_retention_notes", False))
        incl_insights = bool(s.get("data_retention_insights", True))

        # Teacher notes have their own separate timer
        notes_years = int(s.get("data_retention_notes_years", 2))
        notes_days_val = int(s.get("data_retention_notes_days", 0))
        notes_total_days = notes_years * 365 + notes_days_val

        if not any([incl_grading, incl_aic, incl_notes, incl_insights]):
            return None

        summary: dict = {}

        # ── RunStore (grading + AIC) — shared timer ───────────────────────
        if incl_grading or incl_aic:
            try:
                from automation.run_store import RunStore
                store = RunStore()
                deleted = store.delete_for_cleanup(
                    total_days,
                    include_aic=incl_aic,
                    include_grading=incl_grading,
                    include_notes=False,
                    include_profiles=False,
                )
                store.close()
                summary.update(deleted)
            except Exception:
                traceback.print_exc()

        # ── Teacher notes — separate timer ────────────────────────────────
        if incl_notes and notes_total_days > 0:
            try:
                from automation.run_store import RunStore
                store = RunStore()
                deleted = store.delete_for_cleanup(
                    notes_total_days,
                    include_aic=False,
                    include_grading=False,
                    include_notes=True,
                    include_profiles=False,
                )
                store.close()
                summary["notes"] = deleted.get("notes", 0)
            except Exception:
                traceback.print_exc()

        # ── InsightsStore (runs + codings + themes + feedback) ────────────
        if incl_insights:
            try:
                from insights.insights_store import InsightsStore
                istore = InsightsStore()
                ins_count = istore.delete_for_cleanup(total_days)
                istore.close()
                summary["insights"] = ins_count
            except Exception:
                traceback.print_exc()

        total = sum(summary.values())
        if total > 0:
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            print(f"[data-retention] {ts}  Purged {total} aged records "
                  f"(threshold {total_days}d): {summary}")
        return summary

    except Exception:
        traceback.print_exc()
        return None
