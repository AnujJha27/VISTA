"""Persistent `VerificationSession` (spec section 14): runs the full
per-entrypoint resolution pipeline (`dftcert.verification.resolver`) once,
records every data/premise node with its status and provenance, and is
resumable as long as the artifact/package/adapter fingerprints it was built
from still match. A blocked run is a normal, valid, resumable session --
never `failed`.

The Python API (`start_session`/`resume_session`/`VerificationSession.
accept_assumption`) and the future TUI (`dftcert.verification.tui`) must
both go through this module's methods -- neither may reimplement
resolution semantics of its own (spec section 16).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..manifest import ManifestError
from .lean_inspect import inspect_declarations
from .model import new_session, validate_node, validate_session
from .package import package_sha256
from .resolver import resolve_entrypoint

# Node statuses that count as resolved for `ready_for_certificate`.
_RESOLVED_STATUSES = frozenset({"artifact_grounded", "specified_interface", "formally_discharged", "specified_assumption"})


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _node_id(entrypoint: str, index: int) -> str:
    return f"{entrypoint}#{index}"


def _adapter_binding(*, profile: str, adapter_version: str) -> dict[str, str]:
    return {"profile": profile, "adapter_version": adapter_version}


def _build_nodes_for_entrypoint(
    *, entrypoint: str, resolved: dict[str, Any], candidates: list[Any],
    binder_types: list[dict[str, Any]], external_assumptions: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    candidates_by_key = {candidate.key: candidate for candidate in candidates}
    nodes: dict[str, dict[str, Any]] = {}
    for entry in resolved["data_binders"]:
        node_id = _node_id(entrypoint, entry["index"])
        status = entry["status"]
        binder_type = binder_types[entry["index"]]
        base = {
            "kind": "data", "entrypoint": entrypoint, "binder_path": str(entry["index"]),
            "type_fingerprint": binder_type["type_fingerprint"], "dependency_node_ids": [],
            "binder_name": binder_type["name"],
        }
        if status == "resolved":
            key = entry["chosen_candidate_key"]
            candidate = candidates_by_key[key]
            nodes[node_id] = {
                **base, "pretty_type": candidate.display_label,
                "status": candidate.provenance, "evidence_refs": list(candidate.evidence_refs),
                "candidate_keys": [key], "chosen_candidate_key": key, "lean_expr": candidate.lean_expr,
            }
        elif status == "ambiguous_binding":
            nodes[node_id] = {
                **base, "pretty_type": binder_type["type_display"],
                "status": "ambiguous_binding", "evidence_refs": [],
                "candidate_keys": entry["matching_candidate_keys"],
            }
        else:
            nodes[node_id] = {
                **base, "pretty_type": binder_type["type_display"],
                "status": "unresolved", "evidence_refs": [],
            }
    for entry in resolved["premises"]:
        node_id = _node_id(entrypoint, entry["index"])
        assumption = external_assumptions.get(node_id)
        if entry["status"] == "formally_discharged":
            status = "formally_discharged"
        elif assumption is not None:
            status = "specified_assumption"
        else:
            status = "unresolved"
        node = {
            "kind": "premise", "entrypoint": entrypoint, "binder_path": str(entry["index"]),
            "type_fingerprint": entry["type_fingerprint"], "pretty_type": entry["type_display"],
            "status": status, "dependency_node_ids": [], "evidence_refs": [],
            "binder_name": binder_types[entry["index"]]["name"],
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
        # and none should try to. Accepting the proof premise as an explicit
        # assumption resolves that companion binder too: both stay free
        # binders on the generated certificate theorem (never a concrete
        # substitution, never an `axiom`) rather than blocking forever.
        for other_id, other in self.value["nodes"].items():
            if (
                other["kind"] == "data" and other["status"] == "unresolved"
                and other["entrypoint"] == node["entrypoint"] and other["pretty_type"] == "Prop"
            ):
                other["status"] = "specified_assumption"
                other["external_assumption"] = {**node["external_assumption"], "premise_id": other_id}
                other["dependency_node_ids"] = sorted({*other["dependency_node_ids"], premise_id})
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
    *, artifact_sha256: str, artifact_ir: dict[str, Any], ir_sha256: str, package: dict[str, Any],
    adapter, project_root: str | Path, imports: list[str] | None = None,
    output: str | Path, lean_command=("lake", "env", "lean", "-j", "1"),
    timeout_s: int = 600, trusted_local: bool = False,
) -> VerificationSession:
    """Derive/revalidate has already happened by the time `artifact_ir` is
    passed in (the generic structural harness's job); this only runs the
    theorem-centric resolution and writes the session. `adapter` is a
    `StructuralPlugin` instance -- its `lean_import` is used as the default
    module to import unless `imports` overrides it."""
    package_sha = package_sha256(package)
    adapter_binding = _adapter_binding(profile=package["adapter"]["profile"], adapter_version=package["adapter"]["adapter_version"])
    output_path = Path(output)
    if output_path.exists():
        existing = json.loads(output_path.read_text(encoding="utf-8"))
        unchanged = (
            existing.get("artifact_binding", {}).get("artifact_sha256") == artifact_sha256
            and existing.get("formal_package_binding", {}).get("package_sha256") == package_sha
            and existing.get("adapter_binding") == adapter_binding
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
        nodes = _build_nodes_for_entrypoint(
            entrypoint=entrypoint, resolved=resolved, candidates=candidates,
            binder_types=introspected["binders"], external_assumptions=external_assumptions,
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
