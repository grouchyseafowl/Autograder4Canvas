"""Shared AIC concern-level colour palette.

Both grading_results_panel.py and prior_runs_panel.py import from here
so the visual language for academic integrity concern levels is consistent.
"""

from gui.styles import PHOSPHOR_DIM, WARN_PINK, BURN_RED, ROSE_ACCENT

CONCERN_COLOR = {
    "none":     "#3A2808",
    "low":      "#5A7A90",        # muted blue-grey
    "moderate": "#6A9AB8",        # mid baby blue
    "elevated": "#78B4DC",        # baby blue
    "high":     "#90C8F0",        # bright baby blue
}

CONCERN_LABEL = {
    "none":     "No concern",
    "low":      "Low",
    "moderate": "Moderate",
    "elevated": "Elevated",
    "high":     "High concern",
}
