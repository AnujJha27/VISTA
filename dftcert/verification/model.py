"""Pure data model for the theorem-centric verification package and session:
plain dicts validated by explicit functions, following `dftcert.manifest`'s
convention. `FormalBindingCandidate` is the one frozen dataclass, since it
crosses the `StructuralPlugin` interface boundary."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..manifest import ManifestError

PACKAGE_SCHEMA_VERSION = 1
SESSION_SCHEMA_VERSION = 1

# A node's status doubles as its epistemic-provenance class -- there is no
# separate field for that, since it would always just agree with this one.
NODE_STATUSES = frozenset({
    "artifact_grounded",
    "specified_interface",
    "formally_discharged",
    "specified_assumption",
    "ambiguous_binding",
    "unresolved",
    # Lean's own typeclass synthesis or transitive unification resolved an
    # instance-implicit/implicit binder -- not artifact evidence, not a
    # user interpretation.
    "lean_resolved",
})

NODE_KINDS = frozenset({"data", "premise"})

SESSION_STATUSES = frozenset({
    "in_progress",
    "blocked_on_premise",
    "ready_for_certificate",
    "certified",
    "invalid_input",
    "verification_error",
    "stale",
})

BINDER_INFOS = frozenset({"explicit", "implicit", "strictImplicit", "instanceImplicit"})


@dataclass(frozen=True)
class FormalBindingCandidate:
    """A Lean-expressible term the adapter offers to instantiate a data
    binder. `provenance` is `artifact_grounded` or `specified_interface`."""

    key: str
    lean_expr: str
    provenance: str
    evidence_refs: tuple[str, ...]
    display_label: str

    def __post_init__(self) -> None:
        if self.provenance not in {"artifact_grounded", "specified_interface"}:
            raise ManifestError(f"binding candidate {self.key!r} has an invalid provenance")

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "lean_expr": self.lean_expr,
            "provenance": self.provenance,
            "evidence_refs": list(self.evidence_refs),
            "display_label": self.display_label,
        }


def validate_package(value: dict[str, Any]) -> None:
    """Structural validation of a canonical `ResolvedVerificationPackage`."""
    if not isinstance(value, dict):
        raise ManifestError("verification package must be an object")
    if value.get("schema_version") != PACKAGE_SCHEMA_VERSION:
        raise ManifestError(f"verification package must use schema version {PACKAGE_SCHEMA_VERSION}")
    adapter = value.get("adapter")
    if not isinstance(adapter, dict) or set(adapter) != {"profile", "semantic_version", "implementation_sha256"} \
            or not all(isinstance(adapter[key], str) and adapter[key] for key in adapter):
        raise ManifestError(
            "verification package adapter binding must be exactly "
            "{profile, semantic_version, implementation_sha256}, sourced from the adapter itself"
        )
    theory = value.get("lean_theory")
    if not isinstance(theory, dict):
        raise ManifestError("verification package lean_theory is invalid")
    for key in ("project_fingerprint", "toolchain"):
        if not isinstance(theory.get(key), str) or not theory[key]:
            raise ManifestError(f"verification package lean_theory.{key} is invalid")
    for key in ("entry_modules", "entrypoints"):
        items = theory.get(key)
        if not isinstance(items, list) or not items or any(not isinstance(item, str) for item in items):
            raise ManifestError(f"verification package lean_theory.{key} must be a non-empty string array")
    if not isinstance(value.get("interface_contract"), dict):
        raise ManifestError("verification package interface_contract must be an object")
    axiom_policy = value.get("axiom_policy")
    if not isinstance(axiom_policy, dict) or not isinstance(axiom_policy.get("additional_allowed"), list) \
            or any(not isinstance(item, str) or not item for item in axiom_policy["additional_allowed"]):
        raise ManifestError("verification package axiom_policy.additional_allowed must be a string array")
    bindings = value.get("binding_choices")
    if not isinstance(bindings, list):
        raise ManifestError("verification package binding_choices must be an array")
    for choice in bindings:
        if not isinstance(choice, dict) or not all(
            isinstance(choice.get(key), str) for key in ("entrypoint", "binder_path", "candidate_key")
        ):
            raise ManifestError("each binding choice needs entrypoint/binder_path/candidate_key strings")
        if choice["entrypoint"] not in theory["entrypoints"]:
            raise ManifestError(f"binding choice references unselected entrypoint {choice['entrypoint']!r}")
    assumptions = value.get("external_assumptions")
    if not isinstance(assumptions, list):
        raise ManifestError("verification package external_assumptions must be an array")
    for assumption in assumptions:
        if not isinstance(assumption, dict) or not all(
            isinstance(assumption.get(key), str) and assumption[key]
            for key in ("premise_id", "proposition_fingerprint", "rationale")
        ):
            raise ManifestError(
                "each external assumption needs string premise_id/proposition_fingerprint/rationale "
                "-- a bare premise_id is not enough to identify which exact proposition was accepted "
                "(spec/theorem-centric-gaps issue 7)"
            )
        if not any(
            assumption["premise_id"] == entrypoint or assumption["premise_id"].startswith(entrypoint + "#")
            for entrypoint in theory["entrypoints"]
        ):
            raise ManifestError(
                f"external assumption {assumption['premise_id']!r} does not reference a selected entrypoint"
            )
    if value.get("selection_source") not in {"python", "tui", "lean_attribute"}:
        raise ManifestError("verification package selection_source is invalid")


def validate_session(value: dict[str, Any]) -> None:
    if not isinstance(value, dict):
        raise ManifestError("verification session must be an object")
    if value.get("schema_version") != SESSION_SCHEMA_VERSION:
        raise ManifestError(f"verification session must use schema version {SESSION_SCHEMA_VERSION}")
    if not isinstance(value.get("session_id"), str) or not value["session_id"]:
        raise ManifestError("verification session needs a session_id")
    if value.get("status") not in SESSION_STATUSES:
        raise ManifestError("verification session status is invalid")
    for key in ("artifact_binding", "adapter_binding", "formal_package_binding", "nodes"):
        if not isinstance(value.get(key), dict):
            raise ManifestError(f"verification session {key} must be an object")
    for key in ("targets", "decisions"):
        if not isinstance(value.get(key), list):
            raise ManifestError(f"verification session {key} must be an array")
    for node_id, node in value["nodes"].items():
        validate_node(node_id, node)


def validate_node(node_id: str, node: dict[str, Any]) -> None:
    if not isinstance(node, dict):
        raise ManifestError(f"node {node_id!r} must be an object")
    if node.get("kind") not in NODE_KINDS:
        raise ManifestError(f"node {node_id!r} has an invalid kind")
    if node.get("status") not in NODE_STATUSES:
        raise ManifestError(f"node {node_id!r} has an invalid status")
    for key in ("entrypoint", "binder_path", "type_fingerprint", "pretty_type"):
        if not isinstance(node.get(key), str) or not node[key]:
            raise ManifestError(f"node {node_id!r} is missing {key}")
    if not isinstance(node.get("dependency_node_ids"), list):
        raise ManifestError(f"node {node_id!r} dependency_node_ids must be an array")
    if not isinstance(node.get("evidence_refs"), list):
        raise ManifestError(f"node {node_id!r} evidence_refs must be an array")
    if node["status"] == "ambiguous_binding" and not isinstance(node.get("candidate_keys"), list):
        raise ManifestError(f"ambiguous node {node_id!r} must list its candidate_keys")
    if node["status"] == "specified_assumption" and not isinstance(node.get("external_assumption"), dict):
        raise ManifestError(f"assumed node {node_id!r} must carry external_assumption metadata")


def new_session(
    *, session_id: str, artifact_binding: dict[str, Any], adapter_binding: dict[str, Any],
    formal_package_binding: dict[str, Any], ir_sha256: str, created_at: str,
) -> dict[str, Any]:
    return {
        "schema_version": SESSION_SCHEMA_VERSION,
        "session_id": session_id,
        "status": "in_progress",
        "artifact_binding": artifact_binding,
        "adapter_binding": adapter_binding,
        "formal_package_binding": formal_package_binding,
        "ir_sha256": ir_sha256,
        "targets": [],
        "nodes": {},
        "decisions": [],
        "created_at": created_at,
        "updated_at": created_at,
    }
