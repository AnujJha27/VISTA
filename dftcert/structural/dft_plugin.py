"""The DFT structural-certification plugin: VISTA's first `StructuralPlugin`.

Everything here is domain-specific to the DFT/GNN self-energy target
(topology/message-passing/XC form/operator construction/locality). The
harness in `dftcert.structural.core` knows none of this; it only calls the
`StructuralPlugin` interface. See `VISTA_GENERALIZATION.md`.

`derive()` is the single source of truth: it computes everything -- topology,
message-passing, XC form, operator construction and recipe, and the actual
locality observation -- once, from raw inventory/nodes. Every other method
below only reads back what `derive()` already computed, so there is no
second code path that could silently disagree with it.
"""
from __future__ import annotations

from typing import Any

from ..manifest import ManifestError
from .plugin import StructuralPlugin, _refs

_ZERO_TARGETS = {
    "aten.zeros.default", "aten.zeros_like.default", "aten.zero.default",
}
_IDENTITY_TARGETS = {"aten.eye.default"}
_ADD_TARGETS = {"aten.add.tensor"}
_ADJOINT_TARGETS = {
    "aten.transpose.int", "aten.permute.default", "aten.t.default",
    "aten.numpy_t.default",
}
_HINGE_TARGETS = {
    "aten.relu.default", "aten.leaky_relu.default", "aten.clamp_min.default",
    "aten.maximum.default", "aten.abs.default", "aten.hardtanh.default",
}
_SMOOTH_TARGETS = {
    "aten.sigmoid.default", "aten.softplus.default", "aten.tanh.default",
    "aten.silu.default", "aten.gelu.default",
}
_ADJACENCY_ALIAS_TARGETS = {
    "aten.to.dtype", "aten._to_copy.default", "prims.convert_element_type.default",
    "aten.alias.default", "aten.clone.default", "aten.contiguous.default",
    "aten.detach.default",
}
_MESSAGE_TARGETS = {
    "aten.matmul.default", "aten.mm.default", "aten.bmm.default", "aten.mv.default",
}

# The candidate's own extracted operator values are checked against this fixed,
# named/versioned rule -- never a silently-chosen tolerance. It is a property
# of this plugin (like the semantic-lowering rules below), not something a
# candidate or analyst can tune per run.
LOCALITY_RULE = {"name": "operator_offdiag_abs_threshold", "version": 1, "threshold": 1e-9}


def _observed_ops(nodes: list[dict[str, Any]]) -> list[str]:
    return sorted({_target(node) for node in nodes if _target(node)})


def _derivation(
    *, claim: str, value: Any, root: str | None, evidence_nodes: list[str],
    rule: str, observed_nodes: list[dict[str, Any]], metadata: dict[str, Any] | None = None,
    rule_version: int = 1,
) -> dict[str, Any]:
    """Compact, hash-bound explanation for one semantic lowering result."""
    result = {
        "claim": claim,
        "value": value,
        "root": root,
        "evidence_nodes": evidence_nodes,
        "rule": rule,
        "rule_version": rule_version,
        "observed_ops": _observed_ops(observed_nodes),
    }
    if metadata:
        result["metadata"] = metadata
    return result


def _ancestors(nodes: list[dict[str, Any]], root: str) -> list[dict[str, Any]]:
    by_name = {
        node.get("name"): node for node in nodes
        if isinstance(node, dict) and isinstance(node.get("name"), str)
    }
    seen: set[str] = set()
    pending = [root]
    ordered: list[dict[str, Any]] = []
    while pending:
        name = pending.pop()
        if name in seen or name not in by_name:
            continue
        seen.add(name)
        node = by_name[name]
        ordered.append(node)
        pending.extend(_refs(node.get("args")))
        pending.extend(_refs(node.get("kwargs")))
    return ordered


def _target(node: dict[str, Any]) -> str:
    return str(node.get("target", "")).lower()


def _has_target(nodes: list[dict[str, Any]], targets: set[str]) -> bool:
    return any(_target(node) in targets for node in nodes)


def _direct_ref(value: Any) -> str | None:
    refs = _refs(value)
    return refs[0] if len(refs) == 1 else None


def _operator_construction(
    nodes: list[dict[str, Any]], root: str,
) -> tuple[str, list[str], dict[str, Any]]:
    """Classify the operator's construction and return a `recipe` describing
    exactly how to compute its concrete matrix from raw extracted parameter
    values (see `_operator_matrix`) -- the single source of truth shared by
    the classification and the actual-value computation, so they can never
    silently disagree.
    """
    by_name = {node["name"]: node for node in nodes if isinstance(node.get("name"), str)}
    provenance = [node["name"] for node in _ancestors(nodes, root)]
    root_node = by_name.get(root, {})
    if _has_target([root_node], _ZERO_TARGETS):
        return "zero", provenance, {"kind": "zero"}
    if _has_target([root_node], _IDENTITY_TARGETS):
        return "identity", provenance, {"kind": "identity"}
    if _has_target([root_node], _ADD_TARGETS):
        arguments = _refs(root_node.get("args"))
        if len(arguments) >= 2:
            left, right = arguments[:2]
            for base, transformed in ((left, right), (right, left)):
                transformed_node = by_name.get(transformed, {})
                if _has_target([transformed_node], _ADJOINT_TARGETS):
                    transformed_base = _direct_ref(transformed_node.get("args"))
                    if transformed_base == base:
                        return "symmetrized", provenance, {
                            "kind": "sum_transpose", "base": base, "transposed_base": transformed_base,
                        }
                    if (
                        transformed_base in by_name
                        and by_name.get(base, {}).get("op") in {"placeholder", "get_attr"}
                        and by_name[transformed_base].get("op") in {"placeholder", "get_attr"}
                    ):
                        return "unconstrained_parameter", provenance, {
                            "kind": "sum_transpose", "base": base, "transposed_base": transformed_base,
                        }
    if root_node.get("op") in {"placeholder", "get_attr"}:
        return "unconstrained_parameter", provenance, {"kind": "param", "node": root}
    return "unsupported", provenance, {"kind": "unsupported"}


def _xc_form(nodes: list[dict[str, Any]], root: str) -> tuple[str, list[str]]:
    ancestors = _ancestors(nodes, root)
    provenance = [node["name"] for node in ancestors]
    hinge = _has_target(ancestors, _HINGE_TARGETS)
    smooth = _has_target(ancestors, _SMOOTH_TARGETS)
    if hinge and smooth:
        return "unsupported", provenance
    if hinge:
        return "hinge", provenance
    if smooth:
        return "smooth", provenance
    return "unsupported", provenance


def _adjacency_aliases(nodes: list[dict[str, Any]], adjacency_inputs: list[str]) -> list[str]:
    aliases = set(adjacency_inputs)
    while True:
        additions = {
            node["name"] for node in nodes
            if isinstance(node.get("name"), str)
            and _has_target([node], _ADJACENCY_ALIAS_TARGETS)
            and len(_refs(node.get("args"))) == 1
            and _refs(node.get("args"))[0] in aliases
        }
        if additions <= aliases:
            return [node["name"] for node in nodes if node.get("name") in aliases]
        aliases.update(additions)


def _message_chain(
    nodes: list[dict[str, Any]], root: str, adjacency_inputs: list[str],
) -> tuple[list[str], bool]:
    """Follow only consecutive adjacency-fed matmuls from the declared output."""
    by_name = {node["name"]: node for node in nodes if isinstance(node.get("name"), str)}
    adjacency_aliases = set(_adjacency_aliases(nodes, adjacency_inputs))
    current, stages = root, []
    while True:
        node = by_name.get(current, {})
        refs = _refs(node.get("args"))
        if not _has_target([node], _MESSAGE_TARGETS):
            return stages, node.get("op") == "placeholder"
        adjacency = [ref for ref in refs if ref in adjacency_aliases]
        state = [ref for ref in refs if ref not in adjacency_aliases]
        if len(adjacency) != 1 or len(state) != 1:
            return stages, False
        stages.append(current)
        current = state[0]


def _state_entry(inventory: dict[str, Any], requested: str | None) -> dict[str, Any] | None:
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return None
    if requested and isinstance(state.get(requested), dict):
        return state[requested]
    for name, value in state.items():
        if "adjacency" in name.lower() and isinstance(value, dict):
            return value
    return None


def _state_name(inventory: dict[str, Any], requested: str | None) -> str | None:
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return None
    if requested and isinstance(state.get(requested), dict):
        return requested
    return next(
        (name for name, value in state.items()
         if isinstance(name, str) and "adjacency" in name.lower() and isinstance(value, dict)),
        None,
    )


def _topology(
    inventory: dict[str, Any], input_constraints: dict[str, Any],
) -> tuple[int, list[list[int]], list[str], str]:
    state_name = _state_name(inventory, input_constraints.get("adjacency_state_name"))
    entry = _state_entry(inventory, state_name)
    if not entry:
        raise ManifestError("artifact has no extractable structural adjacency buffer")
    values = entry.get("structural_values")
    if (
        not isinstance(values, list) or not values
        or any(not isinstance(row, list) for row in values)
        or any(not isinstance(cell, (bool, int)) for row in values for cell in row)
    ):
        raise ManifestError("adjacency buffer must be a small exported boolean/integer matrix")
    size = len(values)
    if any(len(row) != size for row in values):
        raise ManifestError("adjacency buffer must be square")
    convention = input_constraints.get("adjacency_convention", "target_source")
    if convention not in {"target_source", "source_target"}:
        raise ManifestError("adjacency_convention must be target_source or source_target")
    edges = []
    for row, values_row in enumerate(values):
        for column, connected in enumerate(values_row):
            if bool(connected):
                edges.append(
                    [column, row] if convention == "target_source" else [row, column]
                )
    provenance = entry.get("graph_inputs", [])
    return size, edges, [str(item) for item in provenance if isinstance(item, str)], state_name


def _operator_state_name(inventory: dict[str, Any], node_name: str) -> str | None:
    """Reverse-lookup: which extracted state entry does this graph node alias?"""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return None
    for name, entry in state.items():
        if isinstance(entry, dict) and node_name in entry.get("graph_inputs", []):
            return name
    return None


def _param_matrix(
    inventory: dict[str, Any], node_name: str, site_count: int,
) -> list[list[float]] | None:
    """The concrete site_count x site_count matrix of a raw extracted parameter,
    or None if its real values were not safely capturable (too large, wrong
    shape, or not a small numeric/boolean/integer tensor)."""
    state = inventory.get("state", {})
    state_name = _operator_state_name(inventory, node_name)
    entry = state.get(state_name) if isinstance(state, dict) and state_name else None
    if not isinstance(entry, dict):
        return None
    values = entry.get("structural_values")
    if (
        not isinstance(values, list) or len(values) != site_count
        or any(not isinstance(row, list) or len(row) != site_count for row in values)
        or any(not isinstance(cell, (bool, int, float)) for row in values for cell in row)
    ):
        return None
    return [[float(cell) for cell in row] for row in values]


def _operator_matrix(
    recipe: dict[str, Any], inventory: dict[str, Any], site_count: int,
) -> list[list[float]] | None:
    """Compute the operator's concrete matrix from its construction `recipe`
    (see `_operator_construction`) and safely-extracted raw parameter values.
    Returns None when the actual values cannot be determined without
    executing arbitrary graph code (e.g. an unrecognized construction, or a
    parameter too large/not numeric to have been captured) -- callers must
    treat that as "locality undetermined", never guess.
    """
    kind = recipe.get("kind")
    if kind == "zero":
        return [[0.0] * site_count for _ in range(site_count)]
    if kind == "identity":
        return [[1.0 if row == col else 0.0 for col in range(site_count)] for row in range(site_count)]
    if kind == "param":
        return _param_matrix(inventory, recipe["node"], site_count)
    if kind == "sum_transpose":
        base = _param_matrix(inventory, recipe["base"], site_count)
        other = _param_matrix(inventory, recipe["transposed_base"], site_count)
        if base is None or other is None:
            return None
        return [
            [base[row][col] + other[col][row] for col in range(site_count)]
            for row in range(site_count)
        ]
    return None


def _observed_locality(
    matrix: list[list[float]], site_count: int, rule: dict[str, Any],
) -> dict[str, Any]:
    """The actual (source, target) pairs -- convention: row = target, column =
    source, matching (Sigma e_source)(target) -- whose value exceeds the
    fixed disclosed threshold, and whether the matrix is therefore local
    (diagonal-only) or non-local, as a real fact about the extracted values.
    """
    threshold = rule["threshold"]
    off_diagonal = [
        {"source": column, "target": row}
        for row in range(site_count)
        for column in range(site_count)
        if row != column and abs(matrix[row][column]) > threshold
    ]
    off_diagonal.sort(key=lambda item: (item["source"], item["target"]))
    return {"local": not off_diagonal, "off_diagonal_nonzero": off_diagonal}


def _locality_from_recipe(
    recipe: dict[str, Any], inventory: dict[str, Any], site_count: int, expected: str,
) -> dict[str, Any]:
    matrix = _operator_matrix(recipe, inventory, site_count)
    if matrix is None:
        return {
            "expected": expected, "available": False,
            "observed_local": None, "off_diagonal_nonzero": None, "rule": LOCALITY_RULE,
        }
    observed = _observed_locality(matrix, site_count, LOCALITY_RULE)
    return {
        "expected": expected, "available": True,
        "observed_local": observed["local"],
        "off_diagonal_nonzero": observed["off_diagonal_nonzero"],
        "rule": LOCALITY_RULE,
    }


def _lean_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _lean_edges(edges: list[list[int]]) -> str:
    return "[" + ", ".join(f"({left}, {right})" for left, right in edges) + "]"


def _lean_pairs(pairs: list[dict[str, int]]) -> str:
    return "[" + ", ".join(
        f"({item['source']}, {item['target']})" for item in pairs
    ) + "]"


def _lean_xc(form: str) -> str:
    return {"hinge": ".hinge", "smooth": ".smooth", "unsupported": ".unsupported"}[form]


def _lean_operator(construction: str) -> str:
    return {
        "zero": ".zero",
        "identity": ".identity",
        "symmetrized": '.add (.parameter "base") (.adjoint (.parameter "base"))',
        "unconstrained_parameter": '.parameter "unconstrained"',
        "unsupported": ".unsupported",
    }[construction]


class DFTPlugin(StructuralPlugin):
    name = "dft"
    lean_import = "Testv2.StructuralV2"
    ir_schema_version = 3
    analyzer_version = "dft-structural-analysis-v6"
    policy_version = "dft-structural-v3"
    compiler_version = "dft-structural-lean-v3"

    def role_requirements(self) -> set[str]:
        return {"xc_energy", "learned_self_energy", "message_state"}

    def derive(
        self, *, inventory: dict[str, Any], nodes: list[dict[str, Any]],
        roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """Computes -- once -- everything every other method needs: semantic
        derivations (for translation/provenance) AND the actual locality
        observation (real extracted values, not re-derived elsewhere)."""
        count, edges, graph_inputs, state_name = _topology(inventory, input_constraints)
        aliases = _adjacency_aliases(nodes, graph_inputs)
        stages, message_recognized = _message_chain(nodes, roles["message_state"], graph_inputs)
        xc_form, xc_nodes = _xc_form(nodes, roles["xc_energy"])
        operator, operator_nodes, operator_recipe = _operator_construction(nodes, roles["learned_self_energy"])
        by_name = {node.get("name"): node for node in nodes if isinstance(node.get("name"), str)}
        stage_graph = [by_name[name] for name in stages]
        xc_graph = _ancestors(nodes, roles["xc_energy"])
        operator_graph = _ancestors(nodes, roles["learned_self_energy"])
        topology_graph = [by_name[name] for name in aliases if name in by_name]
        semantic_derivations = {
            "topology": _derivation(
                claim="topology.adjacency", value={"site_count": count, "directed_edges": edges},
                root=state_name, evidence_nodes=aliases, rule="topology.adjacency_state",
                observed_nodes=topology_graph,
                metadata={"state_name": state_name, "graph_inputs": graph_inputs,
                          "adjacency_convention": input_constraints.get("adjacency_convention", "target_source")},
            ),
            "message_passing": _derivation(
                claim="message_passing.depth", value=len(stages), root=roles["message_state"],
                evidence_nodes=stages, rule="message.adjacency_fed_matmul",
                observed_nodes=stage_graph, rule_version=2,
                metadata={"stages": stages, "recognized": message_recognized},
            ),
            "xc": _derivation(
                claim="xc.form", value=xc_form, root=roles["xc_energy"],
                evidence_nodes=xc_nodes,
                rule={"hinge": "xc.hinge_activation", "smooth": "xc.smooth_activation"}.get(xc_form, "xc.unrecognized_composition"),
                rule_version=2,
                observed_nodes=xc_graph,
                metadata=(
                    {"reason": "mixed hinge and smooth activation composition"}
                    if (xc_form == "unsupported" and _has_target(xc_graph, _HINGE_TARGETS) and _has_target(xc_graph, _SMOOTH_TARGETS))
                    else {"reason": "no supported hinge or smooth activation"} if xc_form == "unsupported" else None
                ),
            ),
            "operator": _derivation(
                claim="operator.construction", value=operator, root=roles["learned_self_energy"],
                evidence_nodes=operator_nodes,
                rule={
                    "zero": "operator.zero_root", "identity": "operator.identity_root",
                    "symmetrized": "operator.add_adjoint_pair",
                    "unconstrained_parameter": "operator.unconstrained_root",
                }.get(operator, "operator.unrecognized_composition"),
                rule_version=2 if operator == "unconstrained_parameter" else 1,
                observed_nodes=operator_graph,
                metadata={
                    "recipe": operator_recipe,
                    **({"reason": "unrecognized operator composition"} if operator == "unsupported" else {}),
                },
            ),
        }
        expected_locality = input_constraints.get("expected_locality")
        if expected_locality not in {"local", "non_local"}:
            raise ManifestError("input_constraints.expected_locality must be 'local' or 'non_local'")
        locality = _locality_from_recipe(operator_recipe, inventory, count, expected_locality)
        adjacency_aliases_list = _adjacency_aliases(nodes, graph_inputs)
        return {
            "semantic_derivations": semantic_derivations,
            "site_count": count, "edges": edges, "graph_inputs": graph_inputs,
            "adjacency_state": state_name, "adjacency_aliases": adjacency_aliases_list,
            "depth": len(stages), "stage_nodes": stages, "message_recognized": message_recognized,
            "xc_form": xc_form, "xc_nodes": xc_nodes,
            "operator": operator, "operator_nodes": operator_nodes, "operator_recipe": operator_recipe,
            "locality": locality,
        }

    def ir_sections(self, *, derivation: dict[str, Any], input_constraints: dict[str, Any]) -> dict[str, Any]:
        return {
            "topology": {
                "site_count": derivation["site_count"],
                "directed_edges": derivation["edges"],
                "provenance_nodes": derivation["graph_inputs"],
            },
            "message_passing": {
                "depth": derivation["depth"], "recognized": derivation["message_recognized"],
                "provenance_nodes": derivation["stage_nodes"],
            },
            "xc": {"form": derivation["xc_form"], "provenance_nodes": derivation["xc_nodes"]},
            "operator": {"construction": derivation["operator"], "provenance_nodes": derivation["operator_nodes"]},
            "locality": derivation["locality"],
        }

    def translation_sections(
        self, *, derivation: dict[str, Any], roles: dict[str, str],
        input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": 3,
            "roles": roles,
            "topology": {
                "state_name": derivation["adjacency_state"],
                "graph_inputs": derivation["graph_inputs"],
                "adjacency_aliases": derivation["adjacency_aliases"],
                "adjacency_convention": input_constraints.get("adjacency_convention", "target_source"),
            },
            "message_passing": {
                "root": roles["message_state"], "stages": derivation["stage_nodes"],
                "recognized": derivation["message_recognized"],
            },
            "xc": {"root": roles["xc_energy"], "form": derivation["xc_form"]},
            "operator": {"root": roles["learned_self_energy"], "construction": derivation["operator"]},
            "semantic_derivations": derivation["semantic_derivations"],
        }

    def validate_ir_sections(self, value: dict[str, Any]) -> None:
        topology = value.get("topology")
        message = value.get("message_passing")
        xc = value.get("xc")
        operator = value.get("operator")
        locality = value.get("locality")
        if not all(isinstance(item, dict) for item in (topology, message, xc, operator, locality)):
            raise ManifestError("structural IR sections are missing")
        count = topology.get("site_count")
        edges = topology.get("directed_edges")
        if not isinstance(count, int) or isinstance(count, bool) or count <= 0:
            raise ManifestError("site_count must be positive")
        if not isinstance(edges, list) or any(
            not isinstance(edge, list) or len(edge) != 2
            or any(not isinstance(node, int) or node < 0 or node >= count for node in edge)
            for edge in edges
        ):
            raise ManifestError("directed_edges are invalid")
        depth = message.get("depth")
        if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
            raise ManifestError("message-passing depth must be non-negative")
        if "recognized" in message and not isinstance(message["recognized"], bool):
            raise ManifestError("message-passing recognition must be boolean")
        if xc.get("form") not in {"hinge", "smooth", "unsupported"}:
            raise ManifestError("unsupported XC form value")
        if operator.get("construction") not in {
            "zero", "identity", "symmetrized", "unconstrained_parameter", "unsupported"
        }:
            raise ManifestError("unsupported operator construction value")
        if locality.get("expected") not in {"local", "non_local"}:
            raise ManifestError("locality.expected must be 'local' or 'non_local'")
        if not isinstance(locality.get("available"), bool):
            raise ManifestError("locality.available must be boolean")
        if locality["available"]:
            if not isinstance(locality.get("observed_local"), bool):
                raise ManifestError("locality.observed_local must be boolean when available")
            off_diagonal = locality.get("off_diagonal_nonzero")
            if not isinstance(off_diagonal, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("source"), int) or not isinstance(item.get("target"), int)
                or item["source"] < 0 or item["source"] >= count
                or item["target"] < 0 or item["target"] >= count
                for item in off_diagonal
            ):
                raise ManifestError("locality.off_diagonal_nonzero is invalid")
            rule = locality.get("rule")
            if not isinstance(rule, dict):
                raise ManifestError("locality.rule is missing")
            # A human-attested (confirmed_description) claim has no real computed
            # off-diagonal witness to cross-check -- only torch_export's
            # independently-derived observation is held to this invariant.
            if rule.get("name") != "human_attested" and bool(off_diagonal) == locality["observed_local"]:
                raise ManifestError("locality.observed_local contradicts off_diagonal_nonzero")
        elif locality.get("observed_local") is not None or locality.get("off_diagonal_nonzero") is not None:
            raise ManifestError("unavailable locality must not carry an observation")

    def revalidate(
        self, *, inventory: dict[str, Any], value: dict[str, Any],
        input_constraints: dict[str, Any], derivation: dict[str, Any],
        roles: dict[str, str],
    ) -> None:
        translation = value["translation"]
        if translation.get("semantic_derivations") != derivation["semantic_derivations"]:
            raise ManifestError("translation semantic derivations do not match the raw exported graph")
        topology = translation.get("topology")
        if topology != {
            "state_name": derivation["adjacency_state"],
            "graph_inputs": derivation["graph_inputs"],
            "adjacency_aliases": derivation["adjacency_aliases"],
            "adjacency_convention": input_constraints.get("adjacency_convention", "target_source"),
        } or value["topology"]["site_count"] != derivation["site_count"] or value["topology"]["directed_edges"] != derivation["edges"]:
            raise ManifestError("translation topology claim does not match its adjacency evidence")
        if translation.get("message_passing") != {
            "root": roles["message_state"], "stages": derivation["stage_nodes"], "recognized": derivation["message_recognized"],
        }:
            raise ManifestError("translation message-passing derivation is invalid")
        if value["message_passing"] != {
            "depth": derivation["depth"], "recognized": derivation["message_recognized"], "provenance_nodes": derivation["stage_nodes"],
        }:
            raise ManifestError("IR message-passing claim does not match its derivation")
        if translation.get("xc") != {"root": roles["xc_energy"], "form": derivation["xc_form"]}:
            raise ManifestError("translation XC derivation is invalid")
        if value["xc"] != {"form": derivation["xc_form"], "provenance_nodes": derivation["xc_nodes"]}:
            raise ManifestError("IR XC claim does not match its derivation")
        if translation.get("operator") != {"root": roles["learned_self_energy"], "construction": derivation["operator"]}:
            raise ManifestError("translation operator derivation is invalid")
        if value["operator"] != {"construction": derivation["operator"], "provenance_nodes": derivation["operator_nodes"]}:
            raise ManifestError("IR operator claim does not match its derivation")
        if value["locality"] != derivation["locality"]:
            raise ManifestError("locality claim/observation does not match the raw exported operator values")

    def checked_claim_names(self) -> list[str]:
        return ["topology", "message_passing", "xc", "operator", "semantic_derivations", "locality"]

    def checks(self, value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        locality = value["locality"]
        locality_ok = locality["available"] and (
            locality["observed_local"] if locality["expected"] == "local" else not locality["observed_local"]
        )
        return {
            "xc_discontinuity_compatible": {
                "satisfied": value["xc"]["form"] == "hinge",
                "form": value["xc"]["form"],
                "provenance_nodes": value["xc"].get("provenance_nodes", []),
            },
            "operator_locality_verified": {
                "satisfied": locality_ok,
                "expected": locality["expected"],
                "available": locality["available"],
                "observed_local": locality["observed_local"],
                "off_diagonal_nonzero": locality["off_diagonal_nonzero"],
                "rule": locality["rule"],
                "provenance_nodes": value["operator"].get("provenance_nodes", []),
            },
            "self_adjoint": {
                "satisfied": value["operator"]["construction"] in {"zero", "identity", "symmetrized"},
                "construction": value["operator"]["construction"],
                "provenance_nodes": value["operator"].get("provenance_nodes", []),
            },
        }

    def supported(self, value: dict[str, Any]) -> bool:
        return (
            value["message_passing"].get("recognized", True)
            and value["xc"]["form"] != "unsupported"
            and value["operator"]["construction"] != "unsupported"
            and value["locality"]["available"]
        )

    def failure_witness(self, name: str, check: dict[str, Any]) -> dict[str, Any]:
        if name == "xc_discontinuity_compatible":
            return {
                "fact": name, "kind": "construction_form", "observed": check["form"],
                "required": "hinge", "provenance_nodes": check["provenance_nodes"],
            }
        if name == "operator_locality_verified":
            return {
                "fact": name,
                "kind": "locality_undetermined" if not check["available"] else "locality_mismatch",
                "expected": check["expected"], "observed_local": check["observed_local"],
                "off_diagonal_nonzero": check["off_diagonal_nonzero"], "rule": check["rule"],
                "provenance_nodes": check["provenance_nodes"],
            }
        return {
            "fact": name, "kind": "operator_construction", "observed": check["construction"],
            "required": ["zero", "identity", "symmetrized"], "provenance_nodes": check["provenance_nodes"],
        }

    def what_was_checked(self) -> dict[str, str]:
        return {
            "xc_discontinuity_compatible": "The declared XC output path contains a supported hinge construction.",
            "operator_locality_verified": "The candidate's own extracted learned-self-energy values are actually diagonal (local) or actually have a genuine off-diagonal entry (non-local), matching the declared expectation -- computed from the candidate's real extracted values, not asserted by anyone.",
            "self_adjoint": "The declared operator output is structurally zero, identity, or a parameter plus its transpose.",
        }

    def model_description_lines(self, value: dict[str, Any]) -> list[str]:
        topology = value["topology"]
        locality = value["locality"]
        observed_text = (
            "undetermined (construction not recognized or too large to extract)"
            if not locality["available"]
            else "local (no off-diagonal entry exceeds the threshold)" if locality["observed_local"]
            else f"non-local (off-diagonal entries: {locality['off_diagonal_nonzero']})"
        )
        return [
            f"- Topology: {topology['site_count']} sites and {len(topology['directed_edges'])} directed edges.",
            f"- Self-energy locality: claimed {locality['expected']}; observed {observed_text} "
            f"(rule {locality['rule']['name']}@{locality['rule']['version']}, threshold {locality['rule'].get('threshold')}).",
            f"- Message passing: {value['message_passing']['depth']} consecutive adjacency-fed stage(s): {value['message_passing'].get('provenance_nodes', [])}.",
            f"- XC output construction: {value['xc']['form']}; supporting graph nodes: {value['xc'].get('provenance_nodes', [])}.",
            f"- Self-energy construction: {value['operator']['construction']}; supporting graph nodes: {value['operator'].get('provenance_nodes', [])}.",
        ]

    def lean_preamble_fields(self, value: dict[str, Any], namespace: str) -> str:
        locality = value["locality"]
        return (
            f"def edges : List (Nat × Nat) := {_lean_edges(value['topology']['directed_edges'])}\n"
            f"def messageDepth : Nat := {value['message_passing']['depth']}\n"
            f"-- observedNonzeroOffDiagonal is computed by the analyzer directly from the\n"
            f"-- candidate's own extracted parameter values (rule {locality['rule'].get('name')}\n"
            f"-- @{locality['rule'].get('version')}, threshold {locality['rule'].get('threshold')}).\n"
            f"-- Nobody supplies these pairs; they are read off the candidate's real weights.\n"
            f"def observedNonzeroOffDiagonal : List (Nat × Nat) := {_lean_pairs(locality['off_diagonal_nonzero'] or [])}\n"
            f"def expectedLocal : Bool := {str(locality['expected'] == 'local').lower()}\n"
            f"def xcForm : {self.lean_import}.XCForm := {_lean_xc(value['xc']['form'])}\n"
            f"def operatorForm : {self.lean_import}.OperatorForm := {_lean_operator(value['operator']['construction'])}"
        )

    def lean_statements(
        self, value: dict[str, Any], namespace: str, checks: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        statements = {
            "xc_discontinuity_compatible": (
                f"theorem generated_xc_structure : {self.lean_import}.xcSupportsDiscontinuity "
                f"{namespace}.xcForm = {str(checks['xc_discontinuity_compatible']['satisfied']).lower()}"
            ),
            "self_adjoint": (
                f"theorem generated_operator_structure : {self.lean_import}.guaranteedSelfAdjoint "
                f"{namespace}.operatorForm = {str(checks['self_adjoint']['satisfied']).lower()}"
            ),
        }
        if value["locality"]["available"]:
            statements["operator_locality_verified"] = (
                f"theorem generated_locality_structure : {self.lean_import}.localityMatches "
                f"{namespace}.expectedLocal {namespace}.observedNonzeroOffDiagonal = "
                f"{str(checks['operator_locality_verified']['satisfied']).lower()}"
            )
        return statements


DFT_PLUGIN = DFTPlugin()
