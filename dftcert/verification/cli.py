"""`vista verify ...`: the generic theorem-centric command family (spec
section 22), alongside -- never replacing -- the existing `vista
structural` commands. A thin argument-parsing shell over
`dftcert.verification.api` -- the CLI and the public Python API call the
same trusted implementation (spec/theorem-centric-gaps issue 14).
"""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path

from ..manifest import ManifestError
from . import api
from .lean_inspect import inspect_declarations
from .session import VerificationSession, resume_session


def _summary(session: VerificationSession) -> dict:
    return {
        "status": session.status,
        "session": str(session.path),
        "targets": [target["entrypoint"] for target in session.value["targets"]],
        "unresolved_premises": [item["id"] for item in session.unresolved_premises],
    }


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="vista verify", description="Theorem-centric VISTA verification workflow"
    )
    commands = root.add_subparsers(dest="command", required=True)

    start = commands.add_parser(
        "start", help="derive a verification session from a real artifact and a package"
    )
    start.add_argument("--artifact", help="path to the .pt2 artifact; extracted via the bubblewrap sandbox")
    start.add_argument(
        "--extraction-result",
        help="path to an already-produced trusted-local extraction result JSON "
             "(bypasses the sandbox; requires --trusted-local)",
    )
    start.add_argument("--bubblewrap", default="bwrap")
    start.add_argument("--extractor-python", default="/usr/bin/python3")
    start.add_argument("--package", required=True)
    start.add_argument("--session", required=True)
    start.add_argument("--project", required=True)
    start.add_argument("--lean-command", default="lake env lean -j 1")
    start.add_argument("--timeout-s", type=int, default=600)
    start.add_argument("--trusted-local", action="store_true")

    inspect = commands.add_parser("inspect", help="structured Lean declaration introspection")
    inspect.add_argument("--project", required=True)
    inspect.add_argument("--import", dest="imports", action="append", required=True)
    inspect.add_argument("--declaration", dest="declarations", action="append", required=True)
    inspect.add_argument("--lean-command", default="lake env lean -j 1")
    inspect.add_argument("--timeout-s", type=int, default=300)
    inspect.add_argument("--trusted-local", action="store_true")

    interact = commands.add_parser("interact", help="theorem-centered terminal UI over a session")
    interact.add_argument("--session", required=True)
    interact.add_argument(
        "--package", default=None,
        help="enables [b] choose binding for an ambiguous_binding node",
    )

    resume = commands.add_parser("resume", help="print a session's current status/unresolved premises")
    resume.add_argument("--session", required=True)

    certify = commands.add_parser("certify", help="generate + verify the final certificate theorem")
    certify.add_argument("--session", required=True)
    certify.add_argument("--package", required=True)
    certify.add_argument("--project", required=True)
    certify.add_argument("--entrypoint", action="append", dest="entrypoints",
                          help="repeatable; omit to certify every selected target (spec section 11)")
    certify.add_argument("--lean-import", required=True)
    certify.add_argument("--namespace", default=None)
    certify.add_argument("--output-dir", required=True, help="directory to write the certificate bundle into")
    certify.add_argument("--lean-command", default="lake env lean -j 1")
    certify.add_argument("--timeout-s", type=int, default=300)
    certify.add_argument("--trusted-local", action="store_true")
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        options = parser().parse_args(argv)
        if options.command == "start":
            session = api.start_session(
                artifact=options.artifact, extraction_result=options.extraction_result,
                package=options.package, session=options.session, project=options.project,
                bubblewrap=options.bubblewrap, extractor_python=options.extractor_python,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
                trusted_local=options.trusted_local,
            )
            output = _summary(session)
        elif options.command == "inspect":
            output = inspect_declarations(
                project_root=options.project, imports=options.imports, declarations=options.declarations,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
                trusted_local=options.trusted_local,
            )
        elif options.command == "resume":
            output = _summary(resume_session(options.session))
        elif options.command == "certify":
            manifest = api.certify_session(
                session=options.session, package=options.package, project=options.project,
                lean_import=options.lean_import, output_dir=options.output_dir,
                entrypoints=options.entrypoints, namespace=options.namespace,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
                trusted_local=options.trusted_local,
            )
            output = {
                "status": manifest["status"], "conditional": manifest["conditional"],
                "manifest": str((Path(options.output_dir) / "manifest.json").resolve()),
                "targets": manifest["targets"],
            }
        elif options.command == "interact":
            from .tui import run_interactive
            return run_interactive(options.session, package_path=options.package)
        else:
            raise ManifestError(f"unknown command {options.command!r}")
        print(json.dumps(output, sort_keys=True, default=str))
        # A blocked/in-progress session is a successful, valid, resumable
        # production (spec section 22) -- never an error exit on its own.
        return 0 if output.get("status") not in {"invalid", "verification_error"} else 1
    except (ManifestError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "invalid", "diagnostics": str(error)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
