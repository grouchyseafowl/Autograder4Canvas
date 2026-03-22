"""Shared AIC engagement-level colour palette.

Both grading_results_panel.py and prior_runs_panel.py import from here
so the visual language for engagement depth / conversation opportunity is consistent.

Reframed from concern levels to engagement framing (2026-03-22):
  "suspicious score" → "engagement depth"
  "concern level" → "conversation opportunity"
  "human presence" → "personal connection"
"""

from gui.styles import PHOSPHOR_DIM, WARN_PINK, BURN_RED, ROSE_ACCENT

# Internal key → colour mapping (keys unchanged for data compat)
CONCERN_COLOR = {
    "none":     "#3A2808",
    "low":      "#5A7A90",        # muted blue-grey
    "moderate": "#6A9AB8",        # mid baby blue
    "elevated": "#78B4DC",        # baby blue
    "high":     "#90C8F0",        # bright baby blue
}

# Internal key → user-facing label (engagement frame)
CONCERN_LABEL = {
    "none":     "Strong engagement",
    "low":      "Adequate engagement",
    "moderate": "Conversation suggested",
    "elevated": "Conversation recommended",
    "high":     "Conversation needed",
}
