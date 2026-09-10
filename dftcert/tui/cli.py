"""Argument parsing and the `main` entrypoint for the terminal UI."""
from __future__ import annotations

import argparse
from typing import Any

from ..legacy.hypothesis import policy_coverage
from ..legacy.policy import Policy
from .app import TuiApp
from .constants import DEFAULT_HYPOTHESIS, DEFAULT_POLICY
from .inspectors import build_proof_review, build_run_inspector, build_search_inspector
from .rendering import build_artifact_report, build_hypothesis_report, render_plain


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Terminal UI for VISTA")
    parser.add_argument("--policy", default=str(DEFAULT_POLICY))
    parser.add_argument("--model-id", default="terminal-hypothesis")
    parser.add_argument("--hypothesis", default=DEFAULT_HYPOTHESIS)
    parser.add_argument("--manifest")
    parser.add_argument("--proof-results")
    parser.add_argument("--certificate-report")
    parser.add_argument("--search-result")
    parser.add_argument("--run-dir")
    parser.add_argument("--review-run-dir")
    parser.add_argument("--coverage", action="store_true")
    parser.add_argument(
        "--once", action="store_true",
        help="print a non-interactive terminal report and exit",
    )
    parser.add_argument("--width", type=int, default=100)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    options = arguments(argv)
    policy = Policy.load(options.policy)
    data: dict[str, Any]
    if options.coverage:
        data = policy_coverage(policy)
        if options.once:
            print(render_plain(data, coverage=True, width=options.width))
            return 0
        mode = "coverage"
    elif options.search_result:
        data = build_search_inspector(options.search_result)
        if options.once:
            print(render_plain(data, width=options.width))
            return 0
        mode = "inspector"
    elif options.run_dir:
        data = build_run_inspector(options.run_dir)
        if options.once:
            print(render_plain(data, width=options.width))
            return 0
        mode = "inspector"
    elif options.review_run_dir:
        data = build_proof_review(options.review_run_dir)
        if options.once:
            print(render_plain(data, width=options.width))
            return 0
        mode = "proof_review"
    elif options.manifest:
        data = build_artifact_report(
            policy=policy,
            manifest_path=options.manifest,
            proof_results_path=options.proof_results,
            certificate_report_path=options.certificate_report,
        )
        if options.once:
            print(render_plain(data, width=options.width))
            return 0
        mode = "artifact"
    else:
        data = build_hypothesis_report(
            policy=policy, model_id=options.model_id,
            hypothesis=options.hypothesis,
        )
        if options.once:
            print(render_plain(data, width=options.width))
            return 0
        mode = "report"
    TuiApp(
        policy=policy, model_id=options.model_id,
        hypothesis=options.hypothesis,
        mode=mode,
        data=data,
        refresh_path=(options.review_run_dir or options.run_dir) if not options.once else None,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
