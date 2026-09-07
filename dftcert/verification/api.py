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

import hashlib
import json
from pathlib import Path
from typing import Any

from ..manifest import ManifestError, sha256_value
# research-readiness audit issue 7: the verification harness looks up a
# domain adapter only through the generic registry owned by the
# structural/plugin boundary (`dftcert.structural.plugin`) -- it never
# imports a concrete domain plugin module (e.g. `dft_capability_plugin`)
# by name itself. Importing the `dftcert.structural` package (not any one
# plugin inside it) is what causes built-in adapters to self-register;
# this is a bootstrap side effect of that package's own `__init__`, not a
# harness-side dependency on any one domain.
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


def _workspace_descriptor_path(session: str | Path) -> Path:
    session_path = Path(session)
    return session_path.with_name(session_path.stem + ".workspace.json")


def _write_workspace_descriptor(
    *, session: str | Path, package: str | Path, project: str | Path,
    artifact: str | Path | None, extraction_result: str | Path | None,
    bubblewrap: str, extractor_python: str, lean_command, timeout_s: int, trusted_local: bool,
) -> None:
    """A safe, explicit, on-disk record of the inputs `start_session` was
    called with (spec/theorem-centric-gaps issue F) -- lets a later
    `refresh_session` re-invoke the same trusted backend after a package
    decision changes, without the TUI ever caching those inputs itself as
    hidden in-process state."""
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
    """Re-invoke the same trusted `start_session` backend with the exact
    inputs it was originally called with (spec/theorem-centric-gaps issue
    F) -- for a TUI/interactive caller that just persisted a package
    decision (a binding choice or an external assumption) and wants the
    theorem tree refreshed in place, without duplicating any resolver
    logic of its own. Requires a workspace descriptor next to `session`
    (written automatically by `start_session`); raises `ManifestError` if
    none exists -- the caller should fall back to telling the user to
    re-run `vista verify start` manually."""
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
    """The validated resume (spec/theorem-centric-gaps issue D): with no
    extra arguments this is a plain read-only load (equivalent to
    `dftcert.verification.session.load_session`) -- pass `package`/
    `project` and/or `artifact`/`extraction_result` to actually check the
    loaded session is still fresh against them. A stale session's `status`
    is reported as `"stale"` in the returned (in-memory only) object --
    the file on disk is never touched, so no decision is ever silently
    overwritten."""
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
    """research-readiness audit issue 2: every assumption a certified
    target actually relies on must be represented exactly in the resolved
    verification package whose hash the certificate is bound to -- never
    merely present in the session (which `VerificationSession.
    accept_assumption` can set without ever touching the package, e.g. a
    quick session-local/exploratory decision). Certification never
    silently copies a session-local decision into the package here (that
    would mutate specification state as a side effect of certifying) --
    it only ever refuses. The canonical, certifiable route for an
    assumption is `dftcert.verification.package.add_external_assumption`
    followed by re-deriving the session, exactly like a binding choice.

    Matched by the `(proposition_fingerprint, rationale)` pair rather than
    by `premise_id`: a premise's own companion Prop-sorted data binder
    (`_apply_companion_conversions`) carries a *copy* of the premise's
    `external_assumption` with `premise_id` rewritten to the companion's
    own node id (for self-describing certificate reports) -- so the
    companion's node id is never itself a key in the package's
    `external_assumptions`, even though it legitimately shares the same
    authored proposition/rationale as the premise it derives from."""
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
    output_dir: str | Path, entrypoints: list[str] | None = None,
    allow_subset_certificate: bool = False,
    namespace: str | None = None, lean_command=("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 300, trusted_local: bool = False,
) -> dict[str, Any]:
    """Generate + Lean-check the final certificate theorem for every
    selected target and assemble the hash-bound certificate bundle (spec
    section 11): `manifest.json` plus one `.lean`/`-report.json` pair per
    target in `output_dir`. Refuses if the session isn't
    `ready_for_certificate`, if `package` doesn't match what the session
    was built from, or if the Lean project has drifted since the package
    was authored.

    Also refuses if any certified target relies on a `specified_assumption`
    node that is not represented exactly (same `proposition_fingerprint`
    and `rationale`) in the resolved package's own `external_assumptions`
    (research-readiness audit issue 2) -- a session-local-only
    `VerificationSession.accept_assumption` is exploratory and can never
    certify by itself; author the assumption into the package via
    `dftcert.verification.package.add_external_assumption` and re-derive
    the session first.

    There is no separate `lean_import`/runtime import override (spec/
    theorem-centric-gaps issue 1): every module imported while resolving
    the selected theorem, generating the certificate, compiling it, and
    inspecting its axiom closure is exactly `package["lean_theory"][
    "entry_modules"]` -- the same package whose hash this bundle is bound
    to. There is no second, caller-suppliable formal environment capable
    of diverging from the one the package hash already commits to.

    By default certifies every entrypoint the package selected. Passing
    `entrypoints` as a strict subset of those produces a debug/partial
    bundle, not a package certificate -- spec/theorem-centric-gaps issue G
    requires that be an explicit, deliberate choice (`allow_subset_
    certificate=True`), never silently implied by just passing
    `entrypoints`, and the resulting manifest records `certificate_scope`
    (`"full_package"` vs `"selected_subset"`) plus the full
    `package_entrypoints` list so a subset bundle can never be mistaken
    for a complete package certificate."""
    resumed = _load_session(session)
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
    package_entrypoints = sorted(target["entrypoint"] for target in resumed.value["targets"])
    targets = sorted(entrypoints) if entrypoints else package_entrypoints
    certificate_scope = "full_package" if targets == package_entrypoints else "selected_subset"
    if certificate_scope == "selected_subset" and not allow_subset_certificate:
        raise ManifestError(
            f"certify_session was given a subset of the package's selected entrypoints "
            f"({targets} of {package_entrypoints}) -- pass allow_subset_certificate=True to "
            f"explicitly certify a non-package-complete debug bundle (spec/theorem-centric-gaps issue G)"
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
    # Spec section 11: certification succeeds for the package only when
    # EVERY selected target is closed (formally or conditionally) -- any
    # unresolved/failed target blocks the aggregate bundle.
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
    # `certificate_source_sha256` (assembled below) hashes this exact
    # in-memory string's UTF-8 bytes -- `newline=""` is required so the
    # file written to disk is byte-for-byte identical to that, rather than
    # having Python's default text-mode newline translation rewrite every
    # `\n` to `\r\n` on Windows, which would make the recorded hash never
    # actually match the file it claims to describe (research-readiness
    # audit section 3: caught by `verify_certificate_bundle`).
    source_path.write_text(full_source, encoding="utf-8", newline="")
    # Recorded for audit only -- the selected entrypoint's own axiom
    # closure never gates certification (issue C).
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
        # research-readiness audit issue 8: `manifest.json` records paths
        # relative to the bundle root (`output_dir`), never absolute --
        # an absolute path bakes in the exact machine/directory the bundle
        # happened to be produced under, making the bundle non-portable
        # (e.g. copied to another machine, or even just a different
        # checkout path on the same machine). `posix_path` (forward
        # slashes) keeps the recorded path identical across platforms, not
        # merely relative -- `verify_certificate_bundle` resolves it back
        # against its own `bundle_dir` root.
        "source": source_path.relative_to(output_dir).as_posix(),
        "report": report_path.relative_to(output_dir).as_posix(),
        "certificate_source_sha256": report["certificate_source_sha256"],
        "report_sha256": report["report_sha256"],
    }


def _resolve_bundle_relative_path(bundle_root: Path, relative: str) -> Path:
    """Safely resolve a `manifest.json`-recorded path (research-readiness
    audit issue 8: always bundle-root-relative, never absolute) against
    `bundle_root`. Fails closed (`ManifestError`) rather than reading
    anything for: an absolute path (would ignore `bundle_root` entirely --
    checked explicitly before ever joining, since joining a `Path` with an
    absolute right-hand side silently discards the left side); a `..`
    (or symlink) that resolves outside `bundle_root` once both sides are
    fully resolved. A tampered/malicious manifest can therefore never make
    this function read a file outside the bundle directory."""
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
    bundle (`certify_session`'s `output_dir`) claims about itself
    (research-readiness audit section 3) -- never trusting a field merely
    because it is already stored inside the object being checked. Always
    checks (no live inputs required): the manifest's own self-hash; each
    per-target report's own self-hash; the manifest's `report_sha256`
    reference against the actual report file; each generated certificate
    `.lean` source file's actual bytes-hash against its report's recorded
    `certificate_source_sha256`; the certified target set against the
    package's full selected-entrypoint set recorded in the manifest.
    Optionally also checks (when the corresponding live input is given):
    the package's current hash, the live adapter identity, the live
    Lean-project fingerprint, and the artifact hash from a fresh
    extraction -- each against the manifest's own recorded binding.

    The manifest's per-target `source`/`report` paths are bundle-root-
    relative (research-readiness audit issue 8), so a bundle directory can
    be moved or copied elsewhere and still verify; they are resolved here
    via `_resolve_bundle_relative_path`, which refuses (rather than
    silently reading) an absolute path or one that resolves outside
    `bundle_dir` (`..` traversal or a symlink escape).

    `full=True` (research-readiness audit issue 9) is a strictly stronger,
    explicitly separate mode from the lightweight self-consistency check
    above: instead of only re-hashing bytes already on disk, it actually
    invokes the live Lean toolchain again -- recompiling each certificate
    `.lean` source file from scratch, recomputing the freshly-compiled
    GENERATED certificate declaration's own axiom closure (never the
    entrypoint's -- same distinction `certify_session` itself draws), and
    reapplying the live package's `axiom_policy` to that fresh closure --
    catching a drifted/reinstalled Lean toolchain or mathlib revision that
    now silently accepts (or rejects) something the original certification
    run did not. Requires both `package` and `project` (there is nothing to
    recompile against without a live Lean project). Still explicitly does
    NOT re-derive a fresh session from the artifact/inventory end to end
    (that would mean re-running the entire resolution pipeline, not just
    re-checking the bundle) -- documented as a known remaining gap, never
    silently implied by `full=True`. Neither mode is, or claims to be,
    cryptographic tamper-evidence (no signature, no tamper-evident log) --
    both only prove internal/live consistency, stated explicitly here and
    in `docs/verification/TRUST_CHAIN_AUDIT.md`.

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
        # research-readiness audit issue 9: package is already loaded above
        # (full=True requires it) -- reused here rather than reloaded.
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
        # Step 10 (re-deriving a fresh session from the artifact/inventory
        # end to end, not merely recompiling the already-generated
        # certificate sources) is a known, documented gap -- deliberately
        # not attempted here, and never silently implied by `full=True`.
        checks["full_reverification_scope_note"] = {
            "ok": True,
            "note": (
                "full=True recompiles each certificate and reapplies the live axiom "
                "policy; it does NOT re-derive a fresh session from the artifact/"
                "inventory end to end (that would re-run the entire resolution "
                "pipeline, not just re-check this bundle) -- documented remaining gap, "
                "research-readiness audit issue 9"
            ),
        }

    consistent = all(check.get("ok", False) for check in checks.values())
    return {"consistent": consistent, "mode": "full" if full else "lightweight", "checks": checks}
