"""The public, author-facing Python API (spec/theorem-centric-gaps issue
14): `dftcert.verification.cli` is a thin argument-parsing shell over
these same functions -- there is exactly one trusted implementation of
"derive a session from a real artifact" and "certify a package's selected
targets", never a second one duplicated between CLI and library use.

Low-level building blocks (`dftcert.verification.session.start_session`,
which takes an already-extracted `inventory` directly; `resolve_entrypoint`;
`generate_certificate_source`; ...) remain available for advanced/internal
use, but a normal caller only ever needs the three functions here.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
from ..structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from ..structural.plugin import StructuralPlugin
from .certificate import assemble_certificate_report, generate_certificate_source, parse_certificate_axiom_closure
from .lean_inspect import inspect_declarations
from .package import load_package, package_sha256
from .session import (
    VerificationSession, check_package_freshness,
    resume_session as _resume_session,
    start_session as _start_session_from_inventory,
)

DEFAULT_ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

_ADAPTERS_BY_PROFILE: dict[str, StructuralPlugin] = {
    DFT_CAPABILITY_PLUGIN.name: DFT_CAPABILITY_PLUGIN,
}


def _resolve_adapter(package: dict[str, Any]) -> StructuralPlugin:
    profile = package["adapter"]["profile"]
    adapter = _ADAPTERS_BY_PROFILE.get(profile)
    if adapter is None:
        raise ManifestError(f"no known adapter for profile {profile!r}")
    return adapter


def _extraction_result(
    *, artifact: str | Path | None, extraction_result: str | Path | None,
    bubblewrap: str, extractor_python: str, trusted_local: bool,
) -> dict[str, Any]:
    if bool(artifact) == bool(extraction_result):
        raise ManifestError("pass exactly one of artifact or extraction_result")
    if artifact:
        # Deferred import: only this path needs `dftcert.sandbox`'s
        # POSIX-only `resource` module for bubblewrap sandboxing.
        from ..sandbox import BubblewrapExtractor
        return BubblewrapExtractor(bubblewrap=bubblewrap, python=extractor_python).extract(artifact)
    if not trusted_local:
        raise ManifestError(
            "extraction_result bypasses the extraction sandbox; pass trusted_local=True to accept it"
        )
    value = json.loads(Path(extraction_result).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ManifestError(f"{extraction_result} must contain a JSON object")
    return value


def start_session(
    *, artifact: str | Path | None = None, extraction_result: str | Path | None = None,
    package: str | Path, session: str | Path, project: str | Path,
    bubblewrap: str = "bwrap", extractor_python: str = "/usr/bin/python3",
    lean_command=("lake", "env", "lean", "-j", "1"), timeout_s: int = 600,
    trusted_local: bool = False,
) -> VerificationSession:
    """Derive/resume a verification session from a real `.pt2` artifact
    (safely extracted via the bubblewrap sandbox) or an already-produced
    trusted-local extraction result JSON, and a `package` file -- the
    ergonomics spec/theorem-centric-gaps issue 14 asks for: callers never
    construct an artifact hash, IR, or adapter object by hand."""
    package_value = load_package(package)
    adapter = _resolve_adapter(package_value)
    result = _extraction_result(
        artifact=artifact, extraction_result=extraction_result,
        bubblewrap=bubblewrap, extractor_python=extractor_python, trusted_local=trusted_local,
    )
    return _start_session_from_inventory(
        artifact_sha256=result["artifact_sha256"], inventory=result["inventory"],
        extractor_version=result["extractor_version"], package=package_value, adapter=adapter,
        project_root=project, output=session, lean_command=lean_command,
        timeout_s=timeout_s, trusted_local=trusted_local,
    )


def resume_session(session: str | Path) -> VerificationSession:
    return _resume_session(session)


def certify_session(
    *, session: str | Path, package: str | Path, project: str | Path,
    lean_import: str, output_dir: str | Path, entrypoints: list[str] | None = None,
    namespace: str | None = None, lean_command=("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, Any]:
    """Generate + Lean-check the final certificate theorem for every
    selected target (or just `entrypoints`, if given) and assemble the
    hash-bound certificate bundle (spec section 11): `manifest.json` plus
    one `.lean`/`-report.json` pair per target in `output_dir`. Refuses if
    the session isn't `ready_for_certificate`, if `package` doesn't match
    what the session was built from, or if the Lean project has drifted
    since the package was authored."""
    resumed = _resume_session(session)
    package_value = load_package(package)
    if package_sha256(package_value) != resumed.value["formal_package_binding"]["package_sha256"]:
        raise ManifestError(
            "certify package does not match the package this session was built from "
            "(formal_package_binding.package_sha256 mismatch)"
        )
    check_package_freshness(package_value, project)
    if resumed.status != "ready_for_certificate":
        raise ManifestError(
            f"session is {resumed.status!r}, not ready_for_certificate -- refusing to certify "
            f"while nodes remain unresolved: {[item['id'] for item in resumed.unresolved_premises]}"
        )
    targets = entrypoints or [target["entrypoint"] for target in resumed.value["targets"]]
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    per_target = [
        _certify_one(
            session=resumed, package=package_value, entrypoint=entrypoint, project_root=project,
            lean_import=lean_import,
            namespace=namespace or f"VISTA.Generated_{resumed.value['ir_sha256'][:12]}_{entrypoint.replace('.', '_')}",
            output_dir=out_dir, lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
        )
        for entrypoint in targets
    ]
    # Spec section 11: certification succeeds for the package only when
    # EVERY selected target is closed (formally or conditionally) -- any
    # unresolved/failed target blocks the aggregate bundle.
    all_certified = all(item["status"] == "certified" for item in per_target)
    manifest = {
        "status": "certified" if all_certified else "verification_error",
        "targets": [item["entrypoint"] for item in per_target],
        "conditional": any(item.get("conditional") for item in per_target),
        "artifact_binding": resumed.value["artifact_binding"],
        "adapter_binding": resumed.value["adapter_binding"],
        "formal_package_binding": resumed.value["formal_package_binding"],
        "ir_sha256": resumed.value["ir_sha256"],
        "per_target": per_target,
    }
    manifest["manifest_sha256"] = sha256_value(manifest)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _certify_one(
    *, session: VerificationSession, package: dict[str, Any], entrypoint: str,
    project_root: str | Path, lean_import: str, namespace: str, output_dir: Path,
    lean_command, timeout_s: int, trusted_local: bool,
) -> dict[str, Any]:
    full_source = generate_certificate_source(
        session=session.value, entrypoint=entrypoint, namespace=namespace, lean_import=lean_import,
        project_root=project_root, lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    safe_name = entrypoint.replace(".", "_")
    source_path = output_dir / f"{safe_name}.lean"
    source_path.write_text(full_source, encoding="utf-8")
    # Recorded for audit only -- the selected entrypoint's own axiom
    # closure never gates certification (issue C).
    entrypoint_introspected = inspect_declarations(
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
    # Issue C: gate on the GENERATED certificate declaration's own axiom
    # closure (embedded in `full_source` itself and collected in this same
    # compilation), never the entrypoint's.
    certificate_axiom_closure = parse_certificate_axiom_closure(compiled["diagnostics"])
    allowed = DEFAULT_ALLOWED_AXIOMS | frozenset(package.get("axiom_policy", {}).get("additional_allowed", []))
    report = assemble_certificate_report(
        session=session.value, package=package, entrypoint=entrypoint,
        certificate_source=full_source, entrypoint_axiom_closure=entrypoint_introspected["axioms"],
        certificate_axiom_closure=certificate_axiom_closure, allowed_axioms=allowed,
    )
    report_path = output_dir / f"{safe_name}-report.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "entrypoint": entrypoint, "status": report["status"], "conditional": report["conditional"],
        "source": str(source_path.resolve()), "report": str(report_path.resolve()),
        "certificate_source_sha256": report["certificate_source_sha256"],
        "report_sha256": report["report_sha256"],
    }
