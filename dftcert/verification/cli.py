"""`vista verify ...`: the generic theorem-centric command family (spec
section 22), alongside -- never replacing -- the existing `vista
structural` commands. `start` is the canonical trusted entrypoint: it
performs safe extraction itself (or accepts an already-produced trusted-
local extraction result) and derives the structural IR itself under the
package's own interface contract -- it never accepts a pre-built IR
(spec/theorem-centric-gaps issue 1).
"""
from __future__ import annotations

import argparse
import json
import shlex
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
from ..structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from ..structural.plugin import StructuralPlugin
from .certificate import assemble_certificate_report, generate_certificate_source
from .lean_inspect import inspect_declarations
from .package import load_package, package_sha256
from .session import (
    VerificationSession, check_package_freshness, resume_session, start_session,
)

# Ordinary Lean foundational axioms/standard classical principles (spec
# section 9) -- everything else blocks certification by default, unless
# the package's own hash-bound `axiom_policy.additional_allowed` names it
# explicitly (spec/theorem-centric-gaps issue 12: no command-line-only
# trust escalation -- extra allowed axioms are package provenance, not a
# runtime flag).
DEFAULT_ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# Adapters are looked up by the `profile` name a package/CLI caller
# selects -- before any artifact IR exists, unlike
# `dftcert.structural.cli._resolve_plugin`'s IR-schema-version lookup.
_ADAPTERS_BY_PROFILE: dict[str, StructuralPlugin] = {
    DFT_CAPABILITY_PLUGIN.name: DFT_CAPABILITY_PLUGIN,
}


def _resolve_adapter(package: dict[str, Any]) -> StructuralPlugin:
    profile = package["adapter"]["profile"]
    adapter = _ADAPTERS_BY_PROFILE.get(profile)
    if adapter is None:
        raise ManifestError(f"no known adapter for profile {profile!r}")
    return adapter


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


def _extraction_result(options: argparse.Namespace) -> dict[str, Any]:
    if bool(options.artifact) == bool(options.extraction_result):
        raise ManifestError("start needs exactly one of --artifact or --extraction-result")
    if options.artifact:
        # Deferred import: only this path needs `dftcert.sandbox`'s
        # POSIX-only `resource` module for bubblewrap sandboxing.
        from ..sandbox import BubblewrapExtractor
        return BubblewrapExtractor(
            bubblewrap=options.bubblewrap, python=options.extractor_python,
        ).extract(options.artifact)
    if not options.trusted_local:
        raise ManifestError(
            "--extraction-result bypasses the extraction sandbox; pass --trusted-local to accept it"
        )
    return _object(options.extraction_result)


def _run_start(options: argparse.Namespace) -> dict[str, Any]:
    package = load_package(options.package)
    adapter = _resolve_adapter(package)
    result = _extraction_result(options)
    session = start_session(
        artifact_sha256=result["artifact_sha256"], inventory=result["inventory"],
        extractor_version=result["extractor_version"], package=package, adapter=adapter,
        project_root=options.project, output=options.session,
        lean_command=shlex.split(options.lean_command),
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


def _certify_one(
    *, session: VerificationSession, package: dict[str, Any], entrypoint: str,
    project_root: str, lean_import: str, namespace: str, output_dir: Path,
    lean_command: list[str], timeout_s: int, trusted_local: bool,
) -> dict[str, Any]:
    source = generate_certificate_source(
        session=session.value, entrypoint=entrypoint, namespace=namespace, lean_import=lean_import,
    )
    full_source = f"import {lean_import}\n\n{source}"
    safe_name = entrypoint.replace(".", "_")
    source_path = output_dir / f"{safe_name}.lean"
    source_path.write_text(full_source, encoding="utf-8")
    introspected = inspect_declarations(
        project_root=project_root, imports=[lean_import], declarations=[entrypoint],
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )[entrypoint]
    from ..structural.core import verify_structural_certificate
    compiled = verify_structural_certificate(
        project_root=project_root, certificate_source=source_path,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if compiled["status"] != "verified":
        return {"entrypoint": entrypoint, "status": "verification_error", "diagnostics": compiled["diagnostics"]}
    allowed = DEFAULT_ALLOWED_AXIOMS | frozenset(package.get("axiom_policy", {}).get("additional_allowed", []))
    report = assemble_certificate_report(
        session=session.value, package=package, entrypoint=entrypoint,
        certificate_source=full_source, axiom_closure=introspected["axioms"], allowed_axioms=allowed,
    )
    report_path = output_dir / f"{safe_name}-report.json"
    _write(report_path, report)
    return {
        "entrypoint": entrypoint, "status": report["status"], "conditional": report["conditional"],
        "source": str(source_path.resolve()), "report": str(report_path.resolve()),
        "certificate_source_sha256": report["certificate_source_sha256"],
        "report_sha256": report["report_sha256"],
    }


def _run_certify(options: argparse.Namespace) -> dict[str, Any]:
    session = resume_session(options.session)
    package = load_package(options.package)
    # Issue 3: certify must not succeed against a package that does not
    # match what the session was actually built from, nor one that has
    # drifted from the live Lean project since.
    if package_sha256(package) != session.value["formal_package_binding"]["package_sha256"]:
        raise ManifestError(
            "certify package does not match the package this session was built from "
            "(formal_package_binding.package_sha256 mismatch)"
        )
    check_package_freshness(package, options.project)
    if session.status != "ready_for_certificate":
        raise ManifestError(
            f"session is {session.status!r}, not ready_for_certificate -- refusing to certify "
            f"while nodes remain unresolved: {[item['id'] for item in session.unresolved_premises]}"
        )
    targets = options.entrypoints or [target["entrypoint"] for target in session.value["targets"]]
    output_dir = Path(options.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    lean_command = shlex.split(options.lean_command)
    per_target = []
    for entrypoint in targets:
        namespace = options.namespace or f"VISTA.Generated_{session.value['ir_sha256'][:12]}_{entrypoint.replace('.', '_')}"
        per_target.append(_certify_one(
            session=session, package=package, entrypoint=entrypoint, project_root=options.project,
            lean_import=options.lean_import, namespace=namespace, output_dir=output_dir,
            lean_command=lean_command, timeout_s=options.timeout_s, trusted_local=options.trusted_local,
        ))
    # Spec section 11: certification succeeds for the package only when
    # EVERY selected target is closed (formally or conditionally) --
    # any unresolved/failed target blocks the aggregate bundle.
    all_certified = all(item["status"] == "certified" for item in per_target)
    manifest = {
        "status": "certified" if all_certified else "verification_error",
        "targets": [item["entrypoint"] for item in per_target],
        "conditional": any(item.get("conditional") for item in per_target),
        "artifact_binding": session.value["artifact_binding"],
        "adapter_binding": session.value["adapter_binding"],
        "formal_package_binding": session.value["formal_package_binding"],
        "ir_sha256": session.value["ir_sha256"],
        "per_target": per_target,
    }
    manifest["manifest_sha256"] = sha256_value(manifest)
    _write(output_dir / "manifest.json", manifest)
    return {
        "status": manifest["status"], "conditional": manifest["conditional"],
        "manifest": str((output_dir / "manifest.json").resolve()),
        "targets": manifest["targets"],
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
