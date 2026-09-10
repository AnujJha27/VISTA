"""The public, author-facing Python API; `dftcert.verification.cli` is a thin
argument-parsing shell over these same functions, so CLI and library use
share one trusted implementation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
# Importing `dftcert.structural` (not any one plugin) triggers built-in
# adapters to self-register; the harness never imports a concrete plugin.
from .. import structural as _structural_domains  # noqa: F401
from ..structural.plugin import StructuralPlugin, get_adapter
from .certificate import assemble_certificate_report, generate_certificate_source, parse_certificate_axiom_closure
from .lean_inspect import inspect_declarations
from .package import load_package, package_sha256
from .session import (
    VerificationSession, check_package_freshness,
    load_session as _load_session,
    start_session as _start_session_from_inventory,
)

DEFAULT_ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})


def _resolve_adapter(package: dict[str, Any]) -> StructuralPlugin:
    profile = package["adapter"]["profile"]
    adapter = get_adapter(profile)
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
        # Deferred: only this path needs `dftcert.sandbox`'s POSIX-only
        # `resource` module.
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


def _workspace_descriptor_path(session: str | Path) -> Path:
    session_path = Path(session)
    return session_path.with_name(session_path.stem + ".workspace.json")


def _write_workspace_descriptor(
    *, session: str | Path, package: str | Path, project: str | Path,
    artifact: str | Path | None, extraction_result: str | Path | None,
    bubblewrap: str, extractor_python: str, lean_command, timeout_s: int, trusted_local: bool,
) -> None:
    """On-disk record of `start_session`'s inputs, so `refresh_session` can
    re-invoke the same trusted backend after a package decision changes."""
    descriptor = {
        "package": str(Path(package).resolve()), "project": str(Path(project).resolve()),
        "artifact": str(Path(artifact).resolve()) if artifact is not None else None,
        "extraction_result": str(Path(extraction_result).resolve()) if extraction_result is not None else None,
        "bubblewrap": bubblewrap, "extractor_python": extractor_python,
        "lean_command": list(lean_command), "timeout_s": timeout_s, "trusted_local": trusted_local,
    }
    _workspace_descriptor_path(session).write_text(
        json.dumps(descriptor, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )


def start_session(
    *, artifact: str | Path | None = None, extraction_result: str | Path | None = None,
    package: str | Path, session: str | Path, project: str | Path,
    bubblewrap: str = "bwrap", extractor_python: str = "/usr/bin/python3",
    lean_command=("lake", "env", "lean", "-j", "1"), timeout_s: int = 600,
    trusted_local: bool = False,
) -> VerificationSession:
    """Derive/resume a verification session from a real `.pt2` artifact
    (via the bubblewrap sandbox) or a trusted-local extraction result JSON,
    plus a `package` file."""
    package_value = load_package(package)
    adapter = _resolve_adapter(package_value)
    result = _extraction_result(
        artifact=artifact, extraction_result=extraction_result,
        bubblewrap=bubblewrap, extractor_python=extractor_python, trusted_local=trusted_local,
    )
    session_result = _start_session_from_inventory(
        artifact_sha256=result["artifact_sha256"], inventory=result["inventory"],
        extractor_version=result["extractor_version"], package=package_value, adapter=adapter,
        project_root=project, output=session, lean_command=lean_command,
        timeout_s=timeout_s, trusted_local=trusted_local,
    )
    _write_workspace_descriptor(
        session=session, package=package, project=project, artifact=artifact,
        extraction_result=extraction_result, bubblewrap=bubblewrap, extractor_python=extractor_python,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    return session_result


def refresh_session(session: str | Path) -> VerificationSession:
    """Re-invoke `start_session` with its original inputs, read from the
    workspace descriptor `start_session` wrote -- lets a TUI apply a
    persisted package decision without reimplementing resolution."""
    descriptor_path = _workspace_descriptor_path(session)
    if not descriptor_path.is_file():
        raise ManifestError(
            f"no workspace descriptor at {descriptor_path} -- this session was not created via "
            f"dftcert.verification.api.start_session, so it cannot be automatically refreshed"
        )
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    return start_session(
        artifact=descriptor["artifact"], extraction_result=descriptor["extraction_result"],
        package=descriptor["package"], session=session, project=descriptor["project"],
        bubblewrap=descriptor["bubblewrap"], extractor_python=descriptor["extractor_python"],
        lean_command=descriptor["lean_command"], timeout_s=descriptor["timeout_s"],
        trusted_local=descriptor["trusted_local"],
    )


def resume_session(
    session: str | Path, *, package: str | Path | None = None, project: str | Path | None = None,
    artifact: str | Path | None = None, extraction_result: str | Path | None = None,
    bubblewrap: str = "bwrap", extractor_python: str = "/usr/bin/python3", trusted_local: bool = False,
) -> VerificationSession:
    """Validated resume: with no extra arguments this is a plain read-only
    load; pass `package`/`project` and/or `artifact`/`extraction_result` to
    check freshness against them. A stale result's `status` is set to
    `"stale"` in the returned in-memory object only -- disk is never
    touched, so no decision is silently overwritten."""
    resumed = _load_session(session)
    if package is None and project is None and artifact is None and extraction_result is None:
        return resumed
    stale_reasons: list[str] = []
    if package is not None:
        package_value = load_package(package)
        if package_sha256(package_value) != resumed.value["formal_package_binding"]["package_sha256"]:
            stale_reasons.append("package hash mismatch")
        if project is not None:
            try:
                check_package_freshness(package_value, project)
            except ManifestError as error:
                stale_reasons.append(str(error))
        try:
            live_identity = _resolve_adapter(package_value).semantic_identity
        except ManifestError as error:
            stale_reasons.append(str(error))
        else:
            if live_identity != resumed.value["adapter_binding"]:
                stale_reasons.append("adapter identity mismatch")
    if artifact is not None or extraction_result is not None:
        result = _extraction_result(
            artifact=artifact, extraction_result=extraction_result,
            bubblewrap=bubblewrap, extractor_python=extractor_python, trusted_local=trusted_local,
        )
        if result["artifact_sha256"] != resumed.value["artifact_binding"]["artifact_sha256"]:
            stale_reasons.append("artifact hash mismatch")
    if stale_reasons:
        resumed.value["status"] = "stale"
        resumed.value["stale_reasons"] = stale_reasons
    return resumed


def _require_assumptions_are_package_normalized(
    resumed: VerificationSession, package_value: dict[str, Any], targets: list[str],
) -> None:
    """Every assumption a certified target relies on must be represented
    exactly in the package's own `external_assumptions` -- a session-local
    `VerificationSession.accept_assumption` is exploratory only and can
    never certify by itself; certification only ever refuses, never
    silently copies the decision into the package.

    Matched by `(proposition_fingerprint, rationale)`, not `premise_id`:
    a companion Prop-sorted data binder's copied assumption carries the
    companion's own node id, which is never itself a package key even
    though it shares the premise's authored proposition/rationale."""
    package_assumptions = {
        (item["proposition_fingerprint"], item["rationale"])
        for item in package_value.get("external_assumptions", [])
    }
    for node_id, node in resumed.value["nodes"].items():
        if node["status"] != "specified_assumption" or node["entrypoint"] not in targets:
            continue
        session_assumption = node.get("external_assumption") or {}
        key = (session_assumption.get("proposition_fingerprint"), session_assumption.get("rationale"))
        if key not in package_assumptions:
            raise ManifestError(
                f"node {node_id!r} is a specified_assumption in the session but is not "
                f"represented (or does not exactly match) in the resolved package's "
                f"external_assumptions -- a session-local acceptance (`VerificationSession."
                f"accept_assumption`) is exploratory only and can never certify on its own; "
                f"author it into the package via `add_external_assumption(...)` and re-derive "
                f"the session before certifying (research-readiness audit issue 2)"
            )


def certify_session(
    *, session: str | Path, package: str | Path, project: str | Path,
    output_dir: str | Path, artifact: str | Path | None = None,
    extraction_result: str | Path | None = None,
    bubblewrap: str = "bwrap", extractor_python: str = "/usr/bin/python3",
    entrypoints: list[str] | None = None,
    allow_subset_certificate: bool = False,
    namespace: str | None = None, lean_command=("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, Any]:
    """Generate + Lean-check the final certificate theorem for every
    selected target and assemble the hash-bound certificate bundle
    (`manifest.json` plus one `.lean`/`-report.json` pair per target) in
    `output_dir`.

    `artifact`/`extraction_result` (exactly one) is REQUIRED: the
    certification-relevant session is always freshly re-derived from it via
    `start_session(force_fresh=True)`, never read trustingly from the
    `session` file on disk, which is only overwritten with that fresh
    result for later inspection. This closes a real gap -- hand-editing a
    persisted session's `nodes` while keeping the original artifact/package
    hashes intact would otherwise certify a term that no longer reflects
    the real artifact.

    Refuses if `package` doesn't match the fresh session, if the Lean
    project has drifted since authoring, if any node of a certified target
    is `unresolved`/`ambiguous_binding` in the fresh derivation (scoped to
    `entrypoints`, so an unrelated unresolved entrypoint elsewhere never
    blocks certification -- the point of `allow_subset_certificate`), or if
    a certified target relies on a `specified_assumption` not represented
    exactly in the package's own `external_assumptions` (a session-local
    `accept_assumption` cannot satisfy this, since the fresh derivation
    never reads the old session file).

    There is no separate runtime import override: every module used to
    resolve, generate, compile, and inspect the axiom closure is exactly
    `package["lean_theory"]["entry_modules"]`, the same package this
    bundle's hash is bound to.

    By default certifies every package-selected entrypoint. A strict subset
    requires `allow_subset_certificate=True`; the manifest then records
    `certificate_scope="selected_subset"` (vs `"full_package"`) plus the
    full `package_entrypoints` list, so a subset bundle can never be
    mistaken for a complete one."""
    package_value = load_package(package)
    adapter = _resolve_adapter(package_value)
    extraction = _extraction_result(
        artifact=artifact, extraction_result=extraction_result,
        bubblewrap=bubblewrap, extractor_python=extractor_python, trusted_local=trusted_local,
    )
    resumed = _start_session_from_inventory(
        artifact_sha256=extraction["artifact_sha256"], inventory=extraction["inventory"],
        extractor_version=extraction["extractor_version"], package=package_value, adapter=adapter,
        project_root=project, output=session, lean_command=lean_command,
        timeout_s=timeout_s, trusted_local=trusted_local, force_fresh=True,
    )
    package_entrypoints = sorted(target["entrypoint"] for target in resumed.value["targets"])
    targets = sorted(entrypoints) if entrypoints else package_entrypoints
    certificate_scope = "full_package" if targets == package_entrypoints else "selected_subset"
    if certificate_scope == "selected_subset" and not allow_subset_certificate:
        raise ManifestError(
            f"certify_session was given a subset of the package's selected entrypoints "
            f"({targets} of {package_entrypoints}) -- pass allow_subset_certificate=True to "
            f"explicitly certify a non-package-complete debug bundle"
        )
    # Scoped to `targets`, not the whole session, so an unrelated unresolved
    # entrypoint never blocks certifying one that's genuinely resolved.
    unresolved_in_scope = [
        f"{node_id}" for node_id, node in resumed.value["nodes"].items()
        if node["entrypoint"] in targets and node["status"] in {"unresolved", "ambiguous_binding"}
    ]
    if unresolved_in_scope:
        raise ManifestError(
            f"refusing to certify while nodes remain unresolved for the selected targets "
            f"{targets}: {sorted(unresolved_in_scope)}"
        )
    _require_assumptions_are_package_normalized(resumed, package_value, targets)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    entry_modules = package_value["lean_theory"]["entry_modules"]
    per_target = [
        _certify_one(
            session=resumed, package=package_value, entrypoint=entrypoint, project_root=project,
            entry_modules=entry_modules,
            namespace=namespace or f"VISTA.Generated_{resumed.value['ir_sha256'][:12]}_{entrypoint.replace('.', '_')}",
            output_dir=out_dir, lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
        )
        for entrypoint in targets
    ]
    # Every selected target must be closed for the bundle to succeed.
    all_certified = all(item["status"] == "certified" for item in per_target)
    manifest = {
        "status": "certified" if all_certified else "verification_error",
        "certificate_scope": certificate_scope,
        "package_entrypoints": package_entrypoints,
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
    project_root: str | Path, entry_modules: list[str], namespace: str, output_dir: Path,
    lean_command, timeout_s: int, trusted_local: bool,
) -> dict[str, Any]:
    full_source = generate_certificate_source(
        session=session.value, entrypoint=entrypoint, namespace=namespace, entry_modules=entry_modules,
        project_root=project_root, lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    safe_name = entrypoint.replace(".", "_")
    source_path = output_dir / f"{safe_name}.lean"
    # newline="" keeps the on-disk bytes identical to what's hashed below;
    # default text-mode translation would rewrite \n to \r\n on Windows.
    source_path.write_text(full_source, encoding="utf-8", newline="")
    # Audit only -- the entrypoint's own axiom closure never gates certification.
    entrypoint_introspected = inspect_declarations(
        project_root=project_root, imports=entry_modules, declarations=[entrypoint],
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )[entrypoint]
    from ..structural.core import verify_structural_certificate
    compiled = verify_structural_certificate(
        project_root=project_root, certificate_source=source_path,
        lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
    )
    if compiled["status"] != "verified":
        return {"entrypoint": entrypoint, "status": "verification_error", "diagnostics": compiled["diagnostics"]}
    # Gate on the generated certificate declaration's own axiom closure, never the entrypoint's.
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
        # Bundle-root-relative (not absolute) so the bundle stays portable;
        # .as_posix() keeps it identical across platforms.
        "source": source_path.relative_to(output_dir).as_posix(),
        "report": report_path.relative_to(output_dir).as_posix(),
        "certificate_source_sha256": report["certificate_source_sha256"],
        "report_sha256": report["report_sha256"],
    }


def _resolve_bundle_relative_path(bundle_root: Path, relative: str) -> Path:
    """Resolve a manifest-recorded path against `bundle_root`, refusing
    (never reading) an absolute path or one that escapes `bundle_root` via
    `..`/symlink -- so a tampered manifest can't read outside the bundle."""
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ManifestError(
            f"certificate bundle path {relative!r} must be relative to the bundle root, not absolute"
        )
    root_resolved = bundle_root.resolve()
    resolved = (bundle_root / candidate).resolve()
    if not resolved.is_relative_to(root_resolved):
        raise ManifestError(
            f"certificate bundle path {relative!r} escapes the bundle root {bundle_root!r}"
        )
    return resolved


def verify_certificate_bundle(
    bundle_dir: str | Path, *, artifact: str | Path | None = None,
    extraction_result: str | Path | None = None, package: str | Path | None = None,
    project: str | Path | None = None, bubblewrap: str = "bwrap",
    extractor_python: str = "/usr/bin/python3", trusted_local: bool = False,
    full: bool = False, lean_command=("lake", "env", "lean", "-j", "1"), timeout_s: int = 300,
) -> dict[str, Any]:
    """Independently re-derive and check every hash/fingerprint a certified
    bundle claims about itself, never trusting a field merely because it's
    already stored in the object being checked. Always checks (no live
    inputs required): manifest and per-target report self-hashes, the
    manifest's report reference, each certificate source's bytes-hash, and
    the certified target set against the manifest's recorded package
    entrypoints. Optionally checks (when given) the live package hash,
    adapter identity, Lean-project fingerprint, and a fresh artifact hash
    against the manifest's recorded bindings.

    Per-target paths are resolved via `_resolve_bundle_relative_path`, so
    the bundle can be moved/copied and still verify.

    `full=True` additionally recompiles each certificate with the live Lean
    toolchain and reapplies the live axiom policy to the freshly recomputed
    closure -- catching a drifted toolchain/mathlib revision. Requires
    `package` and `project`. It does NOT re-derive a fresh session from the
    artifact/inventory end to end (a documented remaining gap). Neither
    mode is cryptographic tamper-evidence -- both only prove internal/live
    consistency.

    Returns `{"consistent": bool, "mode": "full" | "lightweight",
    "checks": {name: {"ok": bool, ...}}}`."""
    if full and (package is None or project is None):
        raise ManifestError(
            "verify_certificate_bundle(full=True) requires both package and project -- "
            "recompiling each certificate needs a live Lean project to compile it against"
        )
    bundle = Path(bundle_dir)
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    checks: dict[str, Any] = {}

    stored_manifest_hash = manifest.get("manifest_sha256")
    recomputed_manifest = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    recomputed_manifest_hash = sha256_value(recomputed_manifest)
    checks["manifest_self_hash"] = {
        "ok": recomputed_manifest_hash == stored_manifest_hash,
        "recorded": stored_manifest_hash, "recomputed": recomputed_manifest_hash,
    }

    package_entrypoints = set(manifest.get("package_entrypoints", []))
    certified_targets = set(manifest.get("targets", []))
    checks["certified_targets_are_a_subset_of_package_entrypoints"] = {
        "ok": certified_targets <= package_entrypoints if package_entrypoints else True,
        "package_entrypoints": sorted(package_entrypoints), "certified_targets": sorted(certified_targets),
    }
    if manifest.get("certificate_scope") == "full_package":
        checks["full_package_scope_actually_covers_every_entrypoint"] = {
            "ok": certified_targets == package_entrypoints,
        }

    for item in manifest.get("per_target", []):
        entrypoint = item["entrypoint"]
        source_path = _resolve_bundle_relative_path(bundle, item["source"])
        report_path = _resolve_bundle_relative_path(bundle, item["report"])
        source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
        checks[f"{entrypoint}:certificate_source_hash"] = {
            "ok": source_hash == item.get("certificate_source_sha256"),
            "recorded": item.get("certificate_source_sha256"), "recomputed": source_hash,
        }
        report_value = json.loads(report_path.read_text(encoding="utf-8"))
        stored_report_hash = report_value.get("report_sha256")
        recomputed_report = {k: v for k, v in report_value.items() if k != "report_sha256"}
        recomputed_report_hash = sha256_value(recomputed_report)
        checks[f"{entrypoint}:report_self_hash"] = {
            "ok": recomputed_report_hash == stored_report_hash,
            "recorded": stored_report_hash, "recomputed": recomputed_report_hash,
        }
        checks[f"{entrypoint}:manifest_report_reference"] = {
            "ok": item.get("report_sha256") == stored_report_hash,
        }

    if package is not None:
        package_value = load_package(package)
        live_package_hash = package_sha256(package_value)
        checks["package_hash_matches_binding"] = {
            "ok": live_package_hash == manifest["formal_package_binding"]["package_sha256"],
            "recorded": manifest["formal_package_binding"]["package_sha256"], "recomputed": live_package_hash,
        }
        try:
            live_identity = _resolve_adapter(package_value).semantic_identity
            checks["adapter_identity_matches_binding"] = {
                "ok": live_identity == manifest["adapter_binding"],
                "recorded": manifest["adapter_binding"], "recomputed": live_identity,
            }
        except ManifestError as error:
            checks["adapter_identity_matches_binding"] = {"ok": False, "error": str(error)}
        if project is not None:
            try:
                check_package_freshness(package_value, project)
                checks["lean_project_fresh_against_package"] = {"ok": True}
            except ManifestError as error:
                checks["lean_project_fresh_against_package"] = {"ok": False, "error": str(error)}

    if artifact is not None or extraction_result is not None:
        result = _extraction_result(
            artifact=artifact, extraction_result=extraction_result,
            bubblewrap=bubblewrap, extractor_python=extractor_python, trusted_local=trusted_local,
        )
        checks["artifact_hash_matches_binding"] = {
            "ok": result["artifact_sha256"] == manifest["artifact_binding"]["artifact_sha256"],
            "recorded": manifest["artifact_binding"]["artifact_sha256"], "recomputed": result["artifact_sha256"],
        }

    if full:
        # package is already loaded above (full=True requires it).
        from ..structural.core import verify_structural_certificate
        allowed = DEFAULT_ALLOWED_AXIOMS | frozenset(package_value.get("axiom_policy", {}).get("additional_allowed", []))
        for item in manifest.get("per_target", []):
            entrypoint = item["entrypoint"]
            source_path = _resolve_bundle_relative_path(bundle, item["source"])
            compiled = verify_structural_certificate(
                project_root=project, certificate_source=source_path,
                lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
            )
            checks[f"{entrypoint}:full_recompile"] = {
                "ok": compiled["status"] == "verified",
                **({"diagnostics": compiled["diagnostics"]} if compiled["status"] != "verified" else {}),
            }
            if compiled["status"] != "verified":
                continue
            fresh_closure = parse_certificate_axiom_closure(compiled["diagnostics"])
            blocking = sorted(set(fresh_closure) - allowed)
            checks[f"{entrypoint}:full_axiom_policy_reapplied"] = {
                "ok": "sorryAx" not in fresh_closure and not blocking,
                "recomputed_axiom_closure": sorted(fresh_closure), "allowed_axioms": sorted(allowed),
                "blocking_axioms": blocking,
            }
        checks["full_reverification_scope_note"] = {
            "ok": True,
            "note": (
                "full=True recompiles each certificate and reapplies the live axiom "
                "policy; it does NOT re-derive a fresh session from the artifact/"
                "inventory end to end -- documented remaining gap"
            ),
        }

    consistent = all(check.get("ok", False) for check in checks.values())
    return {"consistent": consistent, "mode": "full" if full else "lightweight", "checks": checks}
