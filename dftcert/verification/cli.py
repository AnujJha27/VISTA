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
from .session import VerificationSession


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
    resume.add_argument(
        "--package", default=None,
        help="validate freshness against this package (spec/theorem-centric-gaps issue D); "
             "omit for a plain read-only load",
    )
    resume.add_argument("--project", default=None, help="validate Lean project/toolchain freshness")
    resume.add_argument("--artifact", default=None, help="validate artifact hash freshness (via BubblewrapExtractor)")
    resume.add_argument("--extraction-result", default=None, help="validate artifact hash freshness (trusted-local)")
    resume.add_argument("--bubblewrap", default="bwrap")
    resume.add_argument("--extractor-python", default="/usr/bin/python3")
    resume.add_argument("--trusted-local", action="store_true")

    certify = commands.add_parser("certify", help="generate + verify the final certificate theorem")
    # No --lean-import: the package's own hash-bound `lean_theory.
    # entry_modules` is the sole formal environment certification runs
    # under (spec/theorem-centric-gaps issue 1) -- there is no second,
    # caller-suppliable import set that could diverge from it.
    certify.add_argument("--session", required=True, help="overwritten with a freshly re-derived session before certifying")
    certify.add_argument("--package", required=True)
    certify.add_argument("--project", required=True)
    certify.add_argument(
        "--artifact",
        help="path to the .pt2 artifact; extracted via the bubblewrap sandbox and used to freshly "
             "re-derive the certification-relevant session state (never trusted from --session on disk)",
    )
    certify.add_argument(
        "--extraction-result",
        help="path to an already-produced trusted-local extraction result JSON "
             "(bypasses the sandbox; requires --trusted-local)",
    )
    certify.add_argument("--bubblewrap", default="bwrap")
    certify.add_argument("--extractor-python", default="/usr/bin/python3")
    certify.add_argument("--entrypoint", action="append", dest="entrypoints",
                          help="repeatable; omit to certify every selected target (spec section 11)")
    certify.add_argument(
        "--allow-subset-certificate", action="store_true",
        help="required to certify only some of --entrypoint when the package selected more "
             "(spec/theorem-centric-gaps issue G): the resulting bundle is marked "
             "certificate_scope=selected_subset, never claimed as a full package certificate",
    )
    certify.add_argument("--namespace", default=None)
    certify.add_argument("--output-dir", required=True, help="directory to write the certificate bundle into")
    certify.add_argument("--lean-command", default="lake env lean -j 1")
    certify.add_argument("--timeout-s", type=int, default=300)
    certify.add_argument("--trusted-local", action="store_true")

    verify_bundle = commands.add_parser(
        "verify-bundle",
        help="independently recompute a certified bundle's own hashes/fingerprints (never trust stored fields)",
    )
    verify_bundle.add_argument("--bundle-dir", required=True, help="the certify --output-dir to check")
    verify_bundle.add_argument("--package", default=None, help="also re-check package/adapter identity")
    verify_bundle.add_argument("--project", default=None, help="also re-check Lean project freshness")
    verify_bundle.add_argument("--artifact", default=None, help="also re-check the artifact hash (via BubblewrapExtractor)")
    verify_bundle.add_argument("--extraction-result", default=None, help="also re-check the artifact hash (trusted-local)")
    verify_bundle.add_argument("--bubblewrap", default="bwrap")
    verify_bundle.add_argument("--extractor-python", default="/usr/bin/python3")
    verify_bundle.add_argument("--trusted-local", action="store_true")
    verify_bundle.add_argument(
        "--full", action="store_true",
        help="research-readiness audit issue 9: strictly stronger than the default lightweight "
             "self-consistency check -- actually recompiles each certificate with the live Lean "
             "toolchain and reapplies the live axiom policy to the freshly-recomputed axiom "
             "closure. Requires --package and --project (nothing to recompile against without a "
             "live Lean project). Never a substitute for --package/--project on their own.",
    )
    verify_bundle.add_argument("--lean-command", default="lake env lean -j 1")
    verify_bundle.add_argument("--timeout-s", type=int, default=300)
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
            output = _summary(api.resume_session(
                options.session, package=options.package, project=options.project,
                artifact=options.artifact, extraction_result=options.extraction_result,
                bubblewrap=options.bubblewrap, extractor_python=options.extractor_python,
                trusted_local=options.trusted_local,
            ))
        elif options.command == "certify":
            manifest = api.certify_session(
                session=options.session, package=options.package, project=options.project,
                output_dir=options.output_dir,
                artifact=options.artifact, extraction_result=options.extraction_result,
                bubblewrap=options.bubblewrap, extractor_python=options.extractor_python,
                entrypoints=options.entrypoints, allow_subset_certificate=options.allow_subset_certificate,
                namespace=options.namespace,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
                trusted_local=options.trusted_local,
            )
            output = {
                "status": manifest["status"], "conditional": manifest["conditional"],
                "certificate_scope": manifest["certificate_scope"],
                "manifest": str((Path(options.output_dir) / "manifest.json").resolve()),
                "targets": manifest["targets"],
            }
        elif options.command == "interact":
            from .tui import run_interactive
            return run_interactive(options.session, package_path=options.package)
        elif options.command == "verify-bundle":
            output = api.verify_certificate_bundle(
                options.bundle_dir, package=options.package, project=options.project,
                artifact=options.artifact, extraction_result=options.extraction_result,
                bubblewrap=options.bubblewrap, extractor_python=options.extractor_python,
                trusted_local=options.trusted_local, full=options.full,
                lean_command=shlex.split(options.lean_command), timeout_s=options.timeout_s,
            )
            print(json.dumps(output, sort_keys=True, default=str))
            return 0 if output["consistent"] else 1
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
