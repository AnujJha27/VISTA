"""`vista verify ...`: the generic theorem-centric command family (spec
section 22), alongside -- never replacing -- the existing `vista
structural` commands. Consumes an already-produced, validated structural
IR (`vista structural analyze-pt2`/`analyze-extraction`); artifact
extraction itself stays that command's job.
"""
from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
from ..structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from ..structural.plugin import StructuralPlugin
from .certificate import assemble_certificate_report, generate_certificate_source
from .lean_inspect import inspect_declarations
from .package import load_package
from .session import VerificationSession, resume_session, start_session

# Ordinary Lean foundational axioms/standard classical principles (spec
# section 9) -- everything else blocks certification by default.
DEFAULT_ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# Mirrors `dftcert.structural.cli.PROFILES`/`_resolve_plugin` (an IR's own
# `ir_schema_version` picks its plugin back up), but imports the plugin
# directly rather than through `dftcert.structural.cli` -- that module
# pulls in `dftcert.sandbox` (POSIX-only `resource`) for artifact
# extraction, which this command family never needs.
_PLUGINS_BY_SCHEMA_VERSION: dict[int, StructuralPlugin] = {
    DFT_CAPABILITY_PLUGIN.ir_schema_version: DFT_CAPABILITY_PLUGIN,
}


def _resolve_plugin(ir: dict[str, Any]) -> StructuralPlugin:
    version = ir.get("ir_schema_version")
    plugin = _PLUGINS_BY_SCHEMA_VERSION.get(version)
    if plugin is None:
        raise ManifestError(f"no known plugin for ir_schema_version {version!r}")
    return plugin


def _object(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: str | Path, value: Any) -> None:
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        prog="vista verify", description="Theorem-centric VISTA verification workflow"
    )
    commands = root.add_subparsers(dest="command", required=True)

    start = commands.add_parser("start", help="derive/resolve a verification session from an IR and package")
    start.add_argument("--ir", required=True)
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

    resume = commands.add_parser("resume", help="print a session's current status/unresolved premises")
    resume.add_argument("--session", required=True)

    certify = commands.add_parser("certify", help="generate + verify the final certificate theorem")
    certify.add_argument("--session", required=True)
    certify.add_argument("--package", required=True)
    certify.add_argument("--project", required=True)
    certify.add_argument("--entrypoint", required=True)
    certify.add_argument("--lean-import", required=True)
    certify.add_argument("--namespace", default=None)
    certify.add_argument("--source-output", required=True)
    certify.add_argument("--report-output", required=True)
    certify.add_argument("--lean-command", default="lake env lean -j 1")
    certify.add_argument("--timeout-s", type=int, default=300)
    certify.add_argument("--trusted-local", action="store_true")
    certify.add_argument("--allowed-axiom", dest="allowed_axioms", action="append", default=[])
    return root


def _run_start(options: argparse.Namespace) -> dict[str, Any]:
    ir = _object(options.ir)
    package = load_package(options.package)
    adapter = _resolve_plugin(ir)
    artifact_sha256 = ir["source"].get("artifact_sha256") or ir["source"].get("description_sha256")
    session = start_session(
        artifact_sha256=artifact_sha256, artifact_ir=ir, ir_sha256=sha256_value(ir),
        package=package, adapter=adapter, project_root=options.project,
        output=options.session, lean_command=shlex.split(options.lean_command),
        timeout_s=options.timeout_s, trusted_local=options.trusted_local,
    )
    return _summary(session)


def _summary(session: VerificationSession) -> dict[str, Any]:
    return {
        "status": session.status,
        "session": str(session.path),
        "targets": [target["entrypoint"] for target in session.value["targets"]],
        "unresolved_premises": [item["id"] for item in session.unresolved_premises],
    }


def _run_certify(options: argparse.Namespace) -> dict[str, Any]:
    session = resume_session(options.session)
    if session.status != "ready_for_certificate":
        raise ManifestError(
            f"session is {session.status!r}, not ready_for_certificate -- refusing to certify "
            f"while nodes remain unresolved: {[item['id'] for item in session.unresolved_premises]}"
        )
    package = load_package(options.package)
    namespace = options.namespace or f"VISTA.Generated_{session.value['ir_sha256'][:12]}"
    source = generate_certificate_source(
        session=session.value, entrypoint=options.entrypoint,
        namespace=namespace, lean_import=options.lean_import,
    )
    full_source = f"import {options.lean_import}\n\n{source}"
    Path(options.source_output).write_text(full_source, encoding="utf-8")
    introspected = inspect_declarations(
        project_root=options.project, imports=[options.lean_import], declarations=[options.entrypoint],
        lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
        trusted_local=options.trusted_local,
    )[options.entrypoint]
    from ..structural.core import verify_structural_certificate
    compiled = verify_structural_certificate(
        project_root=options.project, certificate_source=options.source_output,
        lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
        trusted_local=options.trusted_local,
    )
    if compiled["status"] != "verified":
        return {"status": "verification_error", "diagnostics": compiled["diagnostics"]}
    allowed = DEFAULT_ALLOWED_AXIOMS | frozenset(options.allowed_axioms)
    report = assemble_certificate_report(
        session=session.value, package=package, entrypoint=options.entrypoint,
        certificate_source=full_source, axiom_closure=introspected["axioms"], allowed_axioms=allowed,
    )
    _write(options.report_output, report)
    return {
        "status": report["status"], "conditional": report["conditional"],
        "source": str(Path(options.source_output).resolve()),
        "report": str(Path(options.report_output).resolve()),
    }


def main(argv: list[str] | None = None) -> int:
    try:
        options = parser().parse_args(argv)
        if options.command == "start":
            output = _run_start(options)
        elif options.command == "inspect":
            output = inspect_declarations(
                project_root=options.project, imports=options.imports, declarations=options.declarations,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
                trusted_local=options.trusted_local,
            )
        elif options.command == "resume":
            output = _summary(resume_session(options.session))
        elif options.command == "certify":
            output = _run_certify(options)
        elif options.command == "interact":
            from .tui import run_interactive
            return run_interactive(options.session)
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
