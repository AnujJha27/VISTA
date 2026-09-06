"""Theorem-centric certificate generation (spec sections 19/23): from a
`ready_for_certificate` session, generate one final wrapper theorem per
target that applies the selected entrypoint to its resolved data and
discharged premises in the exact binder order Lean itself reported --
never a hand-coded assumption about a signature's shape. Every explicit
external assumption survives as a real binder on the generated theorem;
none is ever emitted as an `axiom` (spec section 13).
"""
from __future__ import annotations

import hashlib
from typing import Any

from ..manifest import ManifestError, sha256_value


def _ordered_nodes(session: dict[str, Any], entrypoint: str) -> list[tuple[str, dict[str, Any]]]:
    entries = [
        (node_id, node) for node_id, node in session["nodes"].items()
        if node["entrypoint"] == entrypoint
    ]
    return sorted(entries, key=lambda item: int(item[1]["binder_path"]))


def _companion_free_binder_names(nodes: list[tuple[str, dict[str, Any]]]) -> dict[str, str]:
    """node_id (of a premise) -> the Lean identifier of the free `Prop`-sort
    data binder it was resolved alongside (spec section 13's
    `TargetRequiresNonLocality`/`hPhysical` pair) -- `accept_assumption`
    links these via `dependency_node_ids`."""
    result = {}
    for _, node in nodes:
        if node["kind"] == "data" and node["status"] == "specified_assumption":
            for dependent_id in node["dependency_node_ids"]:
                result[dependent_id] = node["binder_name"]
    return result


def generate_certificate_source(
    *, session: dict[str, Any], entrypoint: str, namespace: str, lean_import: str,
) -> str:
    """The generated wrapper theorem's full Lean source, ready to append
    after `import {lean_import}`. Raises if any node this target's root
    set depends on is not in a resolved/discharged/assumed state -- no
    certificate may be assembled while a required premise is unresolved
    (spec section 19)."""
    nodes = _ordered_nodes(session, entrypoint)
    if not nodes:
        raise ManifestError(f"no nodes recorded for entrypoint {entrypoint!r}")
    companions = _companion_free_binder_names(nodes)
    defs: list[str] = []
    free_binders: list[str] = []
    app_args: list[str] = []
    for node_id, node in nodes:
        name = node["binder_name"]
        status = node["status"]
        if node["kind"] == "data":
            if status in {"artifact_grounded", "specified_interface"}:
                def_name = f"artifact_{name}"
                defs.append(f"def {def_name} := {node['lean_expr']}")
                app_args.append(def_name)
            elif status == "specified_assumption":
                free_binders.append(f"({name} : Prop)")
                app_args.append(name)
            else:
                raise ManifestError(f"cannot generate certificate: node {node_id!r} is {status!r}, not resolved")
        else:
            if status == "formally_discharged":
                proof_name = f"proof_{name}"
                defs.append(f"theorem {proof_name} : {node['pretty_type']} := {node['proof_result_ref']}")
                app_args.append(proof_name)
            elif status == "specified_assumption":
                type_text = companions.get(node_id, node["pretty_type"])
                free_binders.append(f"({name} : {type_text})")
                app_args.append(name)
            else:
                raise ManifestError(f"cannot generate certificate: node {node_id!r} is {status!r}, not resolved")
    binder_clause = (" " + " ".join(free_binders)) if free_binders else ""
    target = next(target for target in session["targets"] if target["entrypoint"] == entrypoint)
    lines = [
        f"namespace {namespace}",
        "",
        *defs,
        "",
        f"theorem certificate{binder_clause} :",
        f"    {target['conclusion_display']} := by",
        f"  exact {entrypoint} " + " ".join(app_args),
        "",
        f"end {namespace}",
        "",
    ]
    return "\n".join(lines)


def assemble_certificate_report(
    *, session: dict[str, Any], package: dict[str, Any], entrypoint: str,
    certificate_source: str, axiom_closure: list[str], allowed_axioms: frozenset[str],
) -> dict[str, Any]:
    """The distinguishing report (spec section 19): every node's provenance
    class, the axiom closure, and whether the result is conditional on any
    external assumption. Does not itself invoke Lean -- pass in the
    already-verified `axiom_closure` (spec section 9) and the compiled
    `certificate_source`'s own status separately."""
    nodes = dict(_ordered_nodes(session, entrypoint))
    blocking_axioms = sorted(set(axiom_closure) - allowed_axioms)
    if "sorryAx" in axiom_closure:
        raise ManifestError("certificate blocked: entrypoint's axiom closure includes sorryAx")
    if blocking_axioms:
        raise ManifestError(f"certificate blocked: non-allowlisted axioms {blocking_axioms}")
    by_status: dict[str, list[str]] = {}
    for node_id, node in nodes.items():
        by_status.setdefault(node["status"], []).append(node_id)
    unresolved = [
        *by_status.get("unresolved", []), *by_status.get("ambiguous_binding", []),
    ]
    if unresolved:
        raise ManifestError(f"certificate blocked: unresolved/ambiguous nodes {unresolved}")
    assumptions = [
        node["external_assumption"] for node in nodes.values()
        if node["status"] == "specified_assumption" and node["kind"] == "premise"
    ]
    report = {
        "status": "certified",
        "entrypoint": entrypoint,
        "conditional": bool(assumptions),
        "external_assumptions": assumptions,
        "artifact_grounded_nodes": by_status.get("artifact_grounded", []),
        "specified_interface_nodes": by_status.get("specified_interface", []),
        "formally_discharged_nodes": by_status.get("formally_discharged", []),
        "specified_assumption_nodes": by_status.get("specified_assumption", []),
        "axiom_closure": sorted(axiom_closure),
        "artifact_binding": session["artifact_binding"],
        "adapter_binding": session["adapter_binding"],
        "formal_package_binding": session["formal_package_binding"],
        "ir_sha256": session["ir_sha256"],
        "certificate_source_sha256": hashlib.sha256(certificate_source.encode()).hexdigest(),
    }
    report["report_sha256"] = sha256_value(report)
    return report
