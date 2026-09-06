"""Persistent `VerificationSession` (spec section 14): derives artifact-
grounded structural facts itself (never trusts a foreign IR blob -- see
`start_session`), runs the full per-entrypoint resolution pipeline
(`dftcert.verification.resolver`) once, records every data/premise node
with its status and provenance, and is resumable as long as the artifact/
package/adapter/Lean-project fingerprints it was built from still match. A
blocked run is a normal, valid, resumable session -- never `failed`.

The Python API (`start_session`/`resume_session`/`VerificationSession.
accept_assumption`) and the TUI (`dftcert.verification.tui`) must both go
through this module's methods -- neither may reimplement resolution
semantics of its own (spec section 16).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..certificate import project_fingerprint
from ..manifest import ManifestError, sha256_value
from ..structural.core import structural_ir_from_inventory
from .lean_inspect import inspect_declarations
from .model import new_session, validate_node, validate_session
from .package import package_sha256
from .resolver import resolve_entrypoint

# Node statuses that count as resolved for `ready_for_certificate`.
# `lean_resolved` is Lean's own typeclass synthesis or transitive
# unification (an implicit/instance-implicit binder) -- not artifact
# evidence, not a user interpretation, but also not something that should
# block certification once Lean itself has legitimately supplied it.
_RESOLVED_STATUSES = frozenset({
    "artifact_grounded", "specified_interface", "formally_discharged",
    "specified_assumption", "lean_resolved",
})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node_id(entrypoint: str, index: int) -> str:
    return f"{entrypoint}#{index}"


def check_package_freshness(package: dict[str, Any], project_root: str | Path) -> None:
    """Issue 3: the package's recorded Lean project fingerprint/toolchain
    are checked against the LIVE project on disk, not merely stored. A
    package authored before the theory changed is stale evidence even if
    its own JSON is internally self-consistent."""
    root = Path(project_root)
    toolchain_path = root / "lean-toolchain"
    if not toolchain_path.is_file():
        raise ManifestError(f"{root} is not a Lean project (no lean-toolchain file)")
    current_fingerprint = project_fingerprint(root)
    if current_fingerprint != package["lean_theory"]["project_fingerprint"]:
        raise ManifestError(
            "Lean project has changed since this package was authored "
            "(project_fingerprint mismatch) -- re-author the package against the current theory"
        )
    current_toolchain = toolchain_path.read_text(encoding="utf-8").strip()
    if current_toolchain != package["lean_theory"]["toolchain"]:
        raise ManifestError(
            "Lean toolchain has changed since this package was authored -- re-author the package"
        )


def check_adapter_identity(package: dict[str, Any], adapter) -> dict[str, str]:
    """Issue 4: the adapter's identity is computed from the *executing*
    implementation (`StructuralPlugin.semantic_identity`), never trusted
    from package-authored text, and checked against what the package
    recorded at authoring time. Returns the live identity for binding."""
    live = adapter.semantic_identity
    recorded = package["adapter"]
    if live != recorded:
        raise ManifestError(
            f"package was authored against a different adapter implementation: "
            f"package records {recorded!r}, executing adapter is {live!r}"
        )
    return live


def _build_nodes_for_entrypoint(
    *, entrypoint: str, resolved: dict[str, Any], candidates: list[Any],
    binder_names: list[str], external_assumptions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    candidates_by_key = {candidate.key: candidate for candidate in candidates}
    nodes: dict[str, dict[str, Any]] = {}

    def dep_ids(entry: dict[str, Any]) -> list[str]:
        return [_node_id(entrypoint, i) for i in entry.get("dependency_indices", [])]

    for entry in resolved["data_binders"]:
        node_id = _node_id(entrypoint, entry["index"])
        status = entry["status"]
        base = {
            "kind": "data", "entrypoint": entrypoint, "binder_path": str(entry["index"]),
            "binder_info": entry["binder_info"], "type_fingerprint": entry["type_fingerprint"],
            "dependency_node_ids": dep_ids(entry), "binder_name": binder_names[entry["index"]],
        }
        if status == "forced_choice_unknown_key":
            raise ManifestError(
                f"package binding_choices for {node_id!r} references a candidate key "
                f"the executing adapter does not currently offer"
            )
        if status == "resolved" and entry.get("resolution") == "instance_synthesized":
            nodes[node_id] = {
                **base, "pretty_type": entry["type_display"], "status": "lean_resolved",
                "evidence_refs": [], "resolution": "instance_synthesized",
            }
        elif status == "resolved" and "chosen_candidate_key" in entry:
            key = entry["chosen_candidate_key"]
            candidate = candidates_by_key[key]
            nodes[node_id] = {
                **base, "pretty_type": candidate.display_label,
                "status": candidate.provenance, "evidence_refs": list(candidate.evidence_refs),
                "candidate_keys": [key], "chosen_candidate_key": key, "lean_expr": candidate.lean_expr,
            }
        elif status == "resolved":
            # An implicit/strict-implicit binder resolved transitively via
            # unification with a later explicit binder's candidate --
            # Lean's own elaborator supplied the value, not the adapter.
            nodes[node_id] = {
                **base, "pretty_type": entry["type_display"], "status": "lean_resolved",
                "evidence_refs": [], "resolution": "transitive_unification",
            }
        elif status == "ambiguous_binding":
            nodes[node_id] = {
                **base, "pretty_type": entry["type_display"],
                "status": "ambiguous_binding", "evidence_refs": [],
                "candidate_keys": entry["matching_candidate_keys"],
            }
        else:
            nodes[node_id] = {
                **base, "pretty_type": entry["type_display"],
                "status": "unresolved", "evidence_refs": [],
            }
    for entry in resolved["premises"]:
        node_id = _node_id(entrypoint, entry["index"])
        assumption = external_assumptions.get(node_id)
        # Issue 7: a package-declared assumption is only ever applied if
        # its recorded proposition fingerprint matches the fingerprint
        # Lean *just now* derived for this exact premise, and only to a
        # premise that is genuinely unresolved -- never silently
        # downgrading an already formally_discharged proof, and never
        # applied to a different proposition than the one the rationale
        # was actually written against.
        assumption_applies = (
            assumption is not None
            and entry["status"] != "formally_discharged"
            and assumption["proposition_fingerprint"] == entry["type_fingerprint"]
        )
        if entry["status"] == "formally_discharged":
            status = "formally_discharged"
        elif assumption_applies:
            status = "specified_assumption"
        else:
            status = "unresolved"
        node = {
            "kind": "premise", "entrypoint": entrypoint, "binder_path": str(entry["index"]),
            "binder_info": entry["binder_info"], "type_fingerprint": entry["type_fingerprint"],
            "pretty_type": entry["type_display"], "status": status,
            "dependency_node_ids": dep_ids(entry), "evidence_refs": [],
            "binder_name": binder_names[entry["index"]],
        }
        if status == "formally_discharged":
            node["proof_result_ref"] = entry.get("proof_tactic")
        if status == "specified_assumption":
            node["external_assumption"] = assumption
        nodes[node_id] = node
    for node_id, node in nodes.items():
        validate_node(node_id, node)
    return nodes


def _session_status(nodes: dict[str, dict[str, Any]]) -> str:
    return "ready_for_certificate" if all(node["status"] in _RESOLVED_STATUSES for node in nodes.values()) else "blocked_on_premise"


class VerificationSession:
    """Thin wrapper over the session dict (spec section 14) plus the path
    it persists to. `.value` is always the canonical, schema-validated
    representation -- callers should not mutate it directly; go through
    `accept_assumption`/`save`."""

    def __init__(self, value: dict[str, Any], *, path: str | Path | None = None):
        validate_session(value)
        self.value = value
        self.path = Path(path) if path is not None else None

    @property
    def status(self) -> str:
        return self.value["status"]

    @property
    def unresolved_premises(self) -> list[dict[str, Any]]:
        return [
            {"id": node_id, **node} for node_id, node in self.value["nodes"].items()
            if node["kind"] == "premise" and node["status"] in {"unresolved", "ambiguous_binding"}
        ]

    def accept_assumption(self, *, premise_id: str, rationale: str) -> None:
        node = self.value["nodes"].get(premise_id)
        if node is None:
            raise ManifestError(f"no such premise node {premise_id!r}")
        if node["kind"] != "premise":
            raise ManifestError(f"{premise_id!r} is not a proposition premise")
        if node["status"] not in {"unresolved"}:
            raise ManifestError(
                f"premise {premise_id!r} is {node['status']!r}, not eligible for an explicit assumption"
            )
        node["status"] = "specified_assumption"
        node["external_assumption"] = {
            "premise_id": premise_id, "proposition_fingerprint": node["type_fingerprint"],
            "pretty_proposition": node["pretty_type"], "entrypoints": [node["entrypoint"]], "rationale": rationale,
        }
        # A premise like `hPhysical : TargetRequiresNonLocality` (spec
        # section 13) is preceded by its own bare `Prop`-sorted DATA binder
        # -- no adapter candidate can ever ground an arbitrary proposition,
        # and none should try to. Accepting the proof premise as an
        # explicit assumption resolves that companion binder too, using
        # this premise's OWN Lean-derived dependency_node_ids (never a
        # `pretty_type == "Prop"` guess, which can't distinguish this
        # premise's actual parameter from an unrelated same-typed one --
        # spec issue 8): both stay free binders on the generated
        # certificate theorem (never a concrete substitution, never an
        # `axiom`) rather than blocking forever.
        for dep_id in node["dependency_node_ids"]:
            dep = self.value["nodes"].get(dep_id)
            if dep is not None and dep["kind"] == "data" and dep["status"] == "unresolved":
                dep["status"] = "specified_assumption"
                dep["external_assumption"] = {**node["external_assumption"], "premise_id": dep_id}
        self.value["decisions"].append({
            "kind": "accept_assumption", "premise_id": premise_id, "rationale": rationale, "at": _now(),
        })
        self._recompute_status()
        self.save()

    def _recompute_status(self) -> None:
        if self.value["status"] not in {"stale", "certified", "invalid_input", "verification_error"}:
            self.value["status"] = _session_status(self.value["nodes"])
        self.value["updated_at"] = _now()

    def save(self, path: str | Path | None = None) -> None:
        target = Path(path) if path is not None else self.path
        if target is None:
            raise ManifestError("session has no output path to save to")
        validate_session(self.value)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        self.path = target


def start_session(
    *, artifact_sha256: str, inventory: dict[str, Any], extractor_version: str,
    package: dict[str, Any], adapter, project_root: str | Path, imports: list[str] | None = None,
    output: str | Path, lean_command=("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 600, trusted_local: bool = False,
) -> VerificationSession:
    """The canonical trusted entrypoint (spec/theorem-centric-gaps issue 1):
    takes the raw, safely-extracted graph `inventory` (never a pre-built
    IR) and derives the structural IR itself, via
    `dftcert.structural.core.structural_ir_from_inventory` under the
    package's OWN `interface_contract` (issue 2) -- which independently
    re-derives and compares every semantic claim against the inventory as
    part of that same call. There is no way to hand this function an
    edited semantic fact while keeping the artifact hash: the IR is never
    accepted as input, only ever built by this trusted code path.

    Also verifies the package is fresh against the live Lean project
    (issue 3) and that the executing adapter matches the package's
    recorded identity (issue 4) before doing any resolution work.
    `adapter` is a `StructuralPlugin` instance -- its `lean_import` is the
    default module to import unless `imports` overrides it."""
    check_package_freshness(package, project_root)
    adapter_binding = check_adapter_identity(package, adapter)
    artifact_ir = structural_ir_from_inventory(
        inventory=inventory, artifact_sha256=artifact_sha256, extractor_version=extractor_version,
        input_constraints=package["interface_contract"], plugin=adapter,
    )
    ir_sha256 = sha256_value(artifact_ir)
    package_sha = package_sha256(package)
    output_path = Path(output)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        unchanged = (
            existing.get("artifact_binding", {}).get("artifact_sha256") == artifact_sha256
            and existing.get("formal_package_binding", {}).get("package_sha256") == package_sha
            and existing.get("adapter_binding") == adapter_binding
            and existing.get("ir_sha256") == ir_sha256
        )
        if unchanged:
            return VerificationSession(existing, path=output_path)
        stale_path = output_path.with_name(output_path.stem + f".stale-{int(datetime.now(timezone.utc).timestamp())}" + output_path.suffix)
        output_path.rename(stale_path)
    external_assumptions = {item["premise_id"]: item for item in package.get("external_assumptions", [])}
    modules = imports if imports is not None else package["lean_theory"]["entry_modules"]
    candidates = adapter.formal_binding_candidates(artifact_ir)
    entrypoints = package["lean_theory"]["entrypoints"]
    all_nodes: dict[str, dict[str, Any]] = {}
    targets = []
    for entrypoint in entrypoints:
        forced_choices = {
            int(choice["binder_path"]): choice["candidate_key"]
            for choice in package.get("binding_choices", []) if choice["entrypoint"] == entrypoint
        }
        resolved = resolve_entrypoint(
            project_root=project_root, imports=modules, entrypoint=entrypoint,
            candidates=candidates, forced_choices=forced_choices,
            lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
        )
        introspected = inspect_declarations(
            project_root=project_root, imports=modules, declarations=[entrypoint],
            lean_command=lean_command, timeout_s=timeout_s, trusted_local=trusted_local,
        )[entrypoint]
        if not introspected.get("exists"):
            raise ManifestError(
                f"entrypoint {entrypoint!r} was not found after importing {modules} -- "
                f"check lean_theory.entry_modules and the declaration name"
            )
        binder_names = [binder["name"] for binder in introspected["binders"]]
        nodes = _build_nodes_for_entrypoint(
            entrypoint=entrypoint, resolved=resolved, candidates=candidates,
            binder_names=binder_names, external_assumptions=external_assumptions,
        )
        all_nodes.update(nodes)
        targets.append({
            "entrypoint": entrypoint, "root_node_ids": sorted(nodes),
            "conclusion_display": resolved["conclusion"]["type_display"],
        })
    session = new_session(
        session_id=f"vista-{ir_sha256[:12]}-{package_sha[:12]}",
        artifact_binding={"artifact_sha256": artifact_sha256},
        adapter_binding=adapter_binding,
        formal_package_binding={"package_sha256": package_sha},
        ir_sha256=ir_sha256, created_at=_now(),
    )
    session["nodes"] = all_nodes
    session["targets"] = targets
    session["status"] = _session_status(all_nodes)
    result = VerificationSession(session, path=output_path)
    result.save()
    return result


def resume_session(path: str | Path) -> VerificationSession:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return VerificationSession(value, path=Path(path))
