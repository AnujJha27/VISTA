"""Terminal UI for VISTA: hypothesis reports, policy coverage, and
agentic-run/proof-review inspectors, interactive (curses) or `--once`
plain-text. Split by concern: `rendering` (data -> lines, no curses),
`curses_widgets` (raw curses primitives), `inspectors` (path -> data),
`app` (`TuiApp` + the assumption-review screen), `cli` (argparse + `main`).
This module re-exports the same public names the single-file `tui.py` used
to, so `from dftcert.tui import ...` call sites are unaffected."""
from __future__ import annotations

from .app import TuiApp
from .assumption_review import confirm_assumptions_tui
from .cli import arguments, main
from .constants import DEFAULT_HYPOTHESIS, DEFAULT_POLICY, EXAMPLES
from .curses_widgets import attr, draw_box, init_colors
from .inspectors import build_proof_review, build_run_inspector, build_search_inspector
from .rendering import (
    assessment_lines,
    build_artifact_report,
    build_hypothesis_report,
    coverage_lines,
    event_summary,
    event_summary_lines,
    human_turn_summary,
    label,
    load_json_list,
    load_json_object,
    load_json_value,
    load_jsonl_objects,
    proof_review_entries,
    proof_review_lines,
    render_plain,
    report_lines,
    run_inspector_lines,
    search_outcome,
    search_result_lines,
    status_color,
    wrap_lines,
)

__all__ = [
    "TuiApp", "confirm_assumptions_tui",
    "arguments", "main",
    "DEFAULT_HYPOTHESIS", "DEFAULT_POLICY", "EXAMPLES",
    "attr", "draw_box", "init_colors",
    "build_proof_review", "build_run_inspector", "build_search_inspector",
    "assessment_lines", "build_artifact_report", "build_hypothesis_report",
    "coverage_lines", "event_summary", "event_summary_lines", "human_turn_summary",
    "label", "load_json_list", "load_json_object", "load_json_value", "load_jsonl_objects",
    "proof_review_entries", "proof_review_lines", "render_plain", "report_lines",
    "run_inspector_lines", "search_outcome", "search_result_lines", "status_color", "wrap_lines",
]
