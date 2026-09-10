"""Pre-training architectural-capability certification for the DFT/GNN
target: the project's only structural plugin, and it never reads an
extracted parameter's floating-point content anywhere in its derivation,
IR, or checks.

Checks: `all_pairs_reachable` (site coverage within the operator's own
message-passing ancestry, not applicable when the recipe doesn't depend on
message passing at all), `non_local_capacity` (recipe admits a nonzero
off-diagonal assignment, given >=2 sites), `self_adjoint` (output is zero,
identity, or a parameter plus its transpose), `xc_discontinuity_compatible`
(XC path contains a supported hinge). See
`docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md`.
"""
from __future__ import annotations

from typing import Any

from ..manifest import ManifestError
from ..verification.model import FormalBindingCandidate
from .plugin import StructuralPlugin, _refs, register_adapter

_ZERO_TARGETS = {
    "aten.zeros.default", "aten.zeros_like.default", "aten.zero.default",
}
_IDENTITY_TARGETS = {"aten.eye.default"}
_ADD_TARGETS = {"aten.add.tensor"}
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
_NON_LOCAL_CAPABLE_RECIPES = {"param"}
_TRAINABLE_PARAMETER_STATE_KIND_MARKERS = ("parameter",)


def _observed_ops(nodes: list[dict[str, Any]]) -> list[str]:
    return sorted({_target(node) for node in nodes if _target(node)})


def _derivation(
    *, claim: str, value: Any, root: str | None, evidence_nodes: list[str],
    rule: str, observed_nodes: list[dict[str, Any]], metadata: dict[str, Any] | None = None,
    rule_version: int = 1,
) -> dict[str, Any]:
    """Hash-bound explanation for one semantic lowering result."""
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


def _resolve_operator_layout(input_constraints: dict[str, Any]) -> dict[str, Any]:
    """The operator's declared domain/codomain axis grouping; defaults to
    plain n x n. Only the canonical contiguous grouping is supported -- a
    reordered or interleaved one is rejected, never guessed at."""
    raw = input_constraints.get("operator_layout")
    if raw is None:
        return {"output_axes": [0], "input_axes": [1]}
    if not isinstance(raw, dict):
        raise ManifestError("operator_layout must be an object")
    output_axes, input_axes = raw.get("output_axes"), raw.get("input_axes")
    if not isinstance(output_axes, list) or not output_axes or not isinstance(input_axes, list):
        raise ManifestError("operator_layout.output_axes/input_axes must be non-empty lists")
    rank = len(output_axes)
    if len(input_axes) != rank:
        raise ManifestError("operator_layout.output_axes and input_axes must have equal length")
    if output_axes != list(range(rank)) or input_axes != list(range(rank, 2 * rank)):
        raise ManifestError(
            "operator_layout only supports the canonical contiguous axis grouping "
            "(output_axes=[0..r-1], input_axes=[r..2r-1]); a reordered or "
            "interleaved grouping is not supported"
        )
    return {"output_axes": output_axes, "input_axes": input_axes}


def _adjoint_permutation(node: dict[str, Any]) -> list[Any] | None:
    """The literal permutation argument of a `permute` node, if present."""
    args = node.get("args")
    positional = args if isinstance(args, list) else []
    if len(positional) > 1 and isinstance(positional[1], list):
        return positional[1]
    kwargs = node.get("kwargs")
    dims = kwargs.get("dims") if isinstance(kwargs, dict) else None
    return dims if isinstance(dims, list) else None


def _is_adjoint_of(node: dict[str, Any], layout: dict[str, Any]) -> bool:
    """Whether `node` actually constructs the adjoint under `layout`, by
    checking its real permutation/axis arguments rather than trusting the
    op name alone (a no-op permutation must not pass just because the op
    is on the reviewed list)."""
    target = _target(node)
    if target == "aten.permute.default":
        return _adjoint_permutation(node) == layout["input_axes"] + layout["output_axes"]
    rank = len(layout["output_axes"])
    if rank != 1:
        return False  # only `permute` can express a swap of more than two axes
    if target == "aten.transpose.int":
        args = node.get("args")
        positional = args if isinstance(args, list) else []
        if len(positional) < 3:
            return False
        dim0, dim1 = positional[1], positional[2]
        return {dim0, dim1} == {0, 1} and dim0 != dim1
    return target in {"aten.t.default", "aten.numpy_t.default"}  # no axes to check; unambiguous for rank 2


def _operator_state_name(inventory: dict[str, Any], node_name: str) -> str | None:
    """Reverse-lookup: which extracted state entry does this graph node alias?"""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return None
    for name, entry in state.items():
        if isinstance(entry, dict) and node_name in entry.get("graph_inputs", []):
            return name
    return None


def _shape_matches_site_count(inventory: dict[str, Any], node_name: str, site_count: int) -> bool:
    """Whether `node_name`'s exported shape is literally `[site_count,
    site_count]` -- fails CLOSED on a missing/malformed shape, so a
    too-small parameter can never be credited with long-range capacity."""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return False
    state_name = _operator_state_name(inventory, node_name)
    entry = state.get(state_name) if state_name else None
    if not isinstance(entry, dict):
        return False
    shape = entry.get("shape")
    if not isinstance(shape, list) or len(shape) != 2:
        return False
    rows, cols = shape
    if isinstance(rows, bool) or isinstance(cols, bool) or not isinstance(rows, int) or not isinstance(cols, int):
        return False
    return rows == site_count and cols == site_count


def _is_plausible_parameter_node(inventory: dict[str, Any], node_name: str) -> bool:
    """Whether `node_name` resolves to a state entry the extractor
    POSITIVELY classified as a trainable parameter (`InputKind.PARAMETER`).
    Required for `unconstrained_parameter`, fails CLOSED on anything else
    (buffer, constant, unrecognized). Not needed for `symmetrized`: `B +
    B^dagger` is self-adjoint for any `B`, trainable or not."""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return False
    state_name = _operator_state_name(inventory, node_name)
    entry = state.get(state_name) if state_name else None
    if not isinstance(entry, dict):
        return False
    kind = str(entry.get("state_kind", "")).lower()
    return any(marker in kind for marker in _TRAINABLE_PARAMETER_STATE_KIND_MARKERS)


def _operator_construction(
    nodes: list[dict[str, Any]], root: str, layout: dict[str, Any], inventory: dict[str, Any],
    site_count: int,
) -> tuple[str, list[str], dict[str, Any]]:
    """Classify the operator's construction and return a `recipe` describing
    it, purely from graph shape -- never a float.

    `symmetrized` (`add(base, adjoint(base))`) is self-adjoint for any
    `base`, so classification needs no parameter check; `unconstrained_
    parameter` claims `base` is itself free and trainable, which does.
    The recipe separately records `parameter_confirmed` (needed for the
    `non_local_capacity` claim: a fixed base symmetrized with its own
    transpose still can't realize an off-diagonal entry) and
    `site_dimension_confirmed` (needed for long-range capacity: a 2x2
    parameter can't represent 6-site coupling)."""
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
                if _is_adjoint_of(transformed_node, layout):
                    transformed_base = _direct_ref(transformed_node.get("args"))
                    if transformed_base == base:
                        return "symmetrized", provenance, {
                            "kind": "sum_transpose", "base": base, "transposed_base": transformed_base,
                            "parameter_confirmed": _is_plausible_parameter_node(inventory, base),
                            "site_dimension_confirmed": _shape_matches_site_count(inventory, base, site_count),
                        }
                    if (
                        transformed_base in by_name
                        and by_name.get(base, {}).get("op") in {"placeholder", "get_attr"}
                        and by_name[transformed_base].get("op") in {"placeholder", "get_attr"}
                        and _is_plausible_parameter_node(inventory, base)
                        and _is_plausible_parameter_node(inventory, transformed_base)
                    ):
                        return "unconstrained_parameter", provenance, {
                            "kind": "sum_transpose", "base": base, "transposed_base": transformed_base,
                            "parameter_confirmed": True,  # both operands already checked above
                            "site_dimension_confirmed": (
                                _shape_matches_site_count(inventory, base, site_count)
                                and _shape_matches_site_count(inventory, transformed_base, site_count)
                            ),
                        }
    if root_node.get("op") in {"placeholder", "get_attr"} and _is_plausible_parameter_node(inventory, root):
        return "unconstrained_parameter", provenance, {
            "kind": "param", "node": root,
            "site_dimension_confirmed": _shape_matches_site_count(inventory, root, site_count),
        }
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
) -> tuple[int, list[list[int]], list[str], str, str]:
    requested = input_constraints.get("adjacency_state_name")
    state_name = _state_name(inventory, requested)
    # Recorded since it's an interpretation choice, not an artifact fact:
    # either the analyst's declared name, or a heuristic name-match fallback.
    selection_provenance = "declared" if requested is not None and state_name == requested else "heuristic_name_match"
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
    return (
        size, edges, [str(item) for item in provenance if isinstance(item, str)],
        state_name, selection_provenance,
    )


def _lean_edges(edges: list[list[int]]) -> str:
    return "[" + ", ".join(f"({left}, {right})" for left, right in edges) + "]"


def _lean_xc(form: str) -> str:
    return {"hinge": ".hinge", "smooth": ".smooth", "unsupported": ".unsupported"}[form]


def _is_grouped_layout(layout: dict[str, Any]) -> bool:
    """A grouped `[N, m, N, m]` layout has more than one axis per side; for
    it, long-range capacity is unsupported since a flattened off-diagonal
    entry has no established correspondence to a site pair."""
    return len(layout.get("output_axes", [0])) != 1


def _long_range_eligible(recipe: dict[str, Any], layout: dict[str, Any]) -> bool:
    """Whether this recipe's base counts as a free parameter for LONG-RANGE
    CAPACITY: needs `parameter_confirmed`, a plain non-grouped layout, and
    `site_dimension_confirmed` (shape must actually match site count).
    Self-adjointness never gates on this -- `guaranteedSelfAdjoint` holds
    for `.opaque` exactly as for `.parameter`."""
    kind = recipe.get("kind")
    confirmed = bool(recipe.get("parameter_confirmed")) if kind == "sum_transpose" else kind == "param"
    return (
        confirmed
        and not _is_grouped_layout(layout)
        and bool(recipe.get("site_dimension_confirmed"))
    )


def _lean_operator(construction: str, recipe: dict[str, Any] | None = None, layout: dict[str, Any] | None = None) -> str:
    """Lowers a confirmed, plain-layout parameter as `.parameter "base"`
    (grantable long-range capacity); an unconfirmed one as `.opaque "base"`
    (still self-adjoint, never granted long-range capacity)."""
    eligible = _long_range_eligible(recipe or {}, layout or {})
    if construction == "symmetrized" and not eligible:
        return '.add (.opaque "base") (.adjoint (.opaque "base"))'
    if construction == "unconstrained_parameter" and not eligible:
        return '.opaque "unconstrained"'
    return {
        "zero": ".zero",
        "identity": ".identity",
        "symmetrized": '.add (.parameter "base") (.adjoint (.parameter "base"))',
        "unconstrained_parameter": '.parameter "unconstrained"',
        "unsupported": ".unsupported",
    }[construction]


def _locality_range(input_constraints: dict[str, Any]) -> int:
    """The DFT interface contract's `locality_range` field `R` (default 4):
    `LongRange_R(i, j) := shortestPathDistance_G(i, j) > R`, always computed
    from artifact-grounded topology, never a hand-supplied pair list."""
    value = input_constraints.get("locality_range", 4)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManifestError("interface_contract.locality_range must be a non-negative integer")
    return value


def _lean_locality_range(locality_range: int) -> str:
    """`⟨R⟩` form of `LocalityRange`, a wrapper struct (not a `Nat` alias) so
    the type-based resolver never confuses it with `siteCount : Nat`."""
    return f"⟨{locality_range}⟩"


def _long_range_capacity(
    recipe: dict[str, Any], site_count: int, layout: dict[str, Any],
    edges: list[list[int]], locality_range: int,
) -> bool | None:
    """`None` means unsupported/unresolved (grouped layout), never a
    confident `False`. Otherwise: eligible parameter present, and at least
    one site pair more than `locality_range` hops apart."""
    if _is_grouped_layout(layout):
        return None
    if not _long_range_eligible(recipe, layout):
        return False
    return bool(_unreachable_pairs(site_count, edges, locality_range))


def _non_local_capacity(recipe: dict[str, Any], site_count: int) -> bool:
    if site_count < 2:
        return False
    kind = recipe.get("kind")
    if kind == "sum_transpose":
        # Only has non-local capacity if `base` is a confirmed free parameter.
        return bool(recipe.get("parameter_confirmed"))
    return kind in _NON_LOCAL_CAPABLE_RECIPES


def _unreachable_pairs(
    site_count: int, edges: list[list[int]], depth: int,
) -> list[dict[str, int]]:
    """Ordered (source, target) pairs not reachable within `depth` hops."""
    adjacency: dict[int, set[int]] = {site: set() for site in range(site_count)}
    for source, target in edges:
        adjacency[source].add(target)
    unreachable = []
    for start in range(site_count):
        seen = {start}
        frontier = {start}
        for _ in range(depth):
            frontier = {nxt for node in frontier for nxt in adjacency[node]} - seen
            if not frontier:
                break
            seen |= frontier
        unreachable.extend(
            {"source": start, "target": target}
            for target in range(site_count)
            if target != start and target not in seen
        )
    unreachable.sort(key=lambda item: (item["source"], item["target"]))
    return unreachable


def _operator_message_stages(
    nodes: list[dict[str, Any]], operator_root: str, adjacency_aliases: list[str],
) -> list[str] | None:
    """Adjacency-fed message-passing stages within the operator's OWN
    ancestry. `None` means the operator doesn't depend on message-passing
    at all, so a receptive-field claim about it doesn't apply."""
    ancestor_names = {
        node["name"] for node in _ancestors(nodes, operator_root)
        if isinstance(node.get("name"), str)
    }
    if not ancestor_names & set(adjacency_aliases):
        return None
    stages, recognized = _message_chain(nodes, operator_root, adjacency_aliases)
    return stages if recognized else None


def _reachability(
    *, nodes: list[dict[str, Any]], operator_root: str, adjacency_aliases: list[str],
    site_count: int, edges: list[list[int]],
) -> dict[str, Any]:
    stages = _operator_message_stages(nodes, operator_root, adjacency_aliases)
    if stages is None:
        return {"applicable": False, "satisfied": True, "depth": None, "unreachable_pairs": None}
    depth = len(stages)
    unreachable = _unreachable_pairs(site_count, edges, depth)
    return {"applicable": True, "satisfied": not unreachable, "depth": depth, "unreachable_pairs": unreachable}


def _validate_structure_sections(value: dict[str, Any]) -> None:
    """Shape checks for `topology`/`message_passing`/`xc`/`operator` (never
    `capabilities`); factored out so a future plugin sharing this IR shape
    can reuse it."""
    topology = value.get("topology")
    message = value.get("message_passing")
    xc = value.get("xc")
    operator = value.get("operator")
    if not all(isinstance(item, dict) for item in (topology, message, xc, operator)):
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
    layout = operator.get("layout")
    if not isinstance(layout, dict):
        raise ManifestError("operator.layout is missing")
    output_axes, input_axes = layout.get("output_axes"), layout.get("input_axes")
    if not isinstance(output_axes, list) or not output_axes or output_axes != list(range(len(output_axes))):
        raise ManifestError("operator.layout.output_axes is invalid")
    rank = len(output_axes)
    if input_axes != list(range(rank, 2 * rank)):
        raise ManifestError("operator.layout.input_axes is invalid")


def _revalidate_structure(
    *, value: dict[str, Any], input_constraints: dict[str, Any],
    derivation: dict[str, Any], roles: dict[str, str],
) -> None:
    """Independently rechecks `topology`/`message_passing`/`xc`/`operator`/
    `semantic_derivations` against a freshly recomputed `derivation` (never
    `capabilities`)."""
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
    if translation.get("operator") != {
        "root": roles["learned_self_energy"], "construction": derivation["operator"],
        "layout": derivation["operator_layout"],
    }:
        raise ManifestError("translation operator derivation is invalid")
    if value["operator"] != {
        "construction": derivation["operator"], "provenance_nodes": derivation["operator_nodes"],
        "layout": derivation["operator_layout"], "recipe": derivation["operator_recipe"],
    }:
        raise ManifestError("IR operator claim does not match its derivation")


class DFTCapabilityPlugin(StructuralPlugin):
    name = "dft-capability"
    lean_import = "Testv2.StructuralV2"
    ir_schema_version = 1
    analyzer_version = "dft-structural-capability-analysis-1"
    policy_version = "dft-structural-capability-1"
    compiler_version = "dft-structural-capability-lean-1"

    def role_requirements(self) -> set[str]:
        return {"xc_energy", "learned_self_energy", "message_state"}

    def derive_structure(
        self, *, inventory: dict[str, Any], nodes: list[dict[str, Any]],
        roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """Everything computable from graph shape and construction
        classification alone: topology, message-passing depth, XC form,
        operator-construction recipe. Never reads a parameter's float
        content."""
        # A requirement, not an artifact fact -- optional here so a
        # theorem-centric caller can skip it; checks() still requires it.
        expected_locality = input_constraints.get("expected_locality")
        if expected_locality not in {"local", "non_local", None}:
            raise ManifestError("input_constraints.expected_locality must be 'local' or 'non_local'")
        layout = _resolve_operator_layout(input_constraints)
        locality_range = _locality_range(input_constraints)
        count, edges, graph_inputs, state_name, adjacency_selection_provenance = _topology(inventory, input_constraints)
        aliases = _adjacency_aliases(nodes, graph_inputs)
        stages, message_recognized = _message_chain(nodes, roles["message_state"], graph_inputs)
        xc_form, xc_nodes = _xc_form(nodes, roles["xc_energy"])
        operator, operator_nodes, operator_recipe = _operator_construction(
            nodes, roles["learned_self_energy"], layout, inventory, count,
        )
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
                          "adjacency_convention": input_constraints.get("adjacency_convention", "target_source"),
                          "selection_provenance": adjacency_selection_provenance},
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
        adjacency_aliases_list = _adjacency_aliases(nodes, graph_inputs)
        return {
            "semantic_derivations": semantic_derivations,
            "site_count": count, "edges": edges, "graph_inputs": graph_inputs,
            "adjacency_state": state_name, "adjacency_aliases": adjacency_aliases_list,
            "depth": len(stages), "stage_nodes": stages, "message_recognized": message_recognized,
            "xc_form": xc_form, "xc_nodes": xc_nodes,
            "operator": operator, "operator_nodes": operator_nodes, "operator_recipe": operator_recipe,
            "operator_layout": layout,
            "expected_locality": expected_locality,
            "locality_range": locality_range,
        }

    def derive(
        self, *, inventory: dict[str, Any], nodes: list[dict[str, Any]],
        roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        derivation = self.derive_structure(
            inventory=inventory, nodes=nodes, roles=roles, input_constraints=input_constraints,
        )
        reachability = _reachability(
            nodes=nodes, operator_root=roles["learned_self_energy"],
            adjacency_aliases=derivation["adjacency_aliases"],
            site_count=derivation["site_count"], edges=derivation["edges"],
        )
        derivation["capabilities"] = {
            "expected_locality": derivation["expected_locality"],
            "all_pairs_reachable": reachability["satisfied"],
            "all_pairs_reachable_applicable": reachability["applicable"],
            "unreachable_pairs": reachability["unreachable_pairs"],
            "operator_message_depth": reachability["depth"],
            "non_local_capacity": _non_local_capacity(derivation["operator_recipe"], derivation["site_count"]),
            # Theorem-centric-authoritative replacement for the above (which
            # is kept as deprecated/historical). `None` means unresolved,
            # never a confident `False`.
            "long_range_capacity": _long_range_capacity(
                derivation["operator_recipe"], derivation["site_count"],
                derivation["operator_layout"], derivation["edges"], derivation["locality_range"],
            ),
        }
        return derivation

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
            "operator": {
                "construction": derivation["operator"], "provenance_nodes": derivation["operator_nodes"],
                "layout": derivation["operator_layout"],
                # Exposed here so callers of this shallow dict (e.g.
                # formal_binding_candidates) need not reach into
                # translation.semantic_derivations for _lean_operator's input.
                "recipe": derivation["operator_recipe"],
            },
            # The only specified-interface locality input (a graph-hop
            # radius); long-range pairs are always derived, never supplied.
            "locality_range": derivation["locality_range"],
            "capabilities": derivation["capabilities"],
        }

    def translation_sections(
        self, *, derivation: dict[str, Any], roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "schema_version": self.ir_schema_version,
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
            "operator": {
                "root": roles["learned_self_energy"], "construction": derivation["operator"],
                "layout": derivation["operator_layout"],
            },
            "semantic_derivations": derivation["semantic_derivations"],
        }

    def validate_ir_sections(self, value: dict[str, Any]) -> None:
        _validate_structure_sections(value)
        count = value["topology"]["site_count"]
        locality_range = value.get("locality_range")
        if isinstance(locality_range, bool) or not isinstance(locality_range, int) or locality_range < 0:
            raise ManifestError("locality_range must be a non-negative integer")
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ManifestError("structural IR is missing capabilities")
        if capabilities.get("expected_locality") not in {"local", "non_local", None}:
            raise ManifestError("capabilities.expected_locality must be 'local' or 'non_local'")
        if not isinstance(capabilities.get("all_pairs_reachable"), bool):
            raise ManifestError("capabilities.all_pairs_reachable must be boolean")
        if not isinstance(capabilities.get("all_pairs_reachable_applicable"), bool):
            raise ManifestError("capabilities.all_pairs_reachable_applicable must be boolean")
        if not isinstance(capabilities.get("non_local_capacity"), bool):
            raise ManifestError("capabilities.non_local_capacity must be boolean")
        long_range_capacity = capabilities.get("long_range_capacity")
        if long_range_capacity is not None and not isinstance(long_range_capacity, bool):
            raise ManifestError("capabilities.long_range_capacity must be boolean or null (unsupported)")
        capability_depth = capabilities.get("operator_message_depth")
        unreachable = capabilities.get("unreachable_pairs")
        if capabilities["all_pairs_reachable_applicable"]:
            if not isinstance(capability_depth, int) or isinstance(capability_depth, bool) or capability_depth < 0:
                raise ManifestError("capabilities.operator_message_depth must be non-negative when applicable")
            if not isinstance(unreachable, list) or any(
                not isinstance(item, dict)
                or not isinstance(item.get("source"), int) or not isinstance(item.get("target"), int)
                or item["source"] < 0 or item["source"] >= count
                or item["target"] < 0 or item["target"] >= count
                for item in unreachable
            ):
                raise ManifestError("capabilities.unreachable_pairs is invalid")
            if bool(unreachable) == capabilities["all_pairs_reachable"]:
                raise ManifestError("capabilities.all_pairs_reachable contradicts unreachable_pairs")
        elif capability_depth is not None or unreachable is not None or not capabilities["all_pairs_reachable"]:
            raise ManifestError("a not-applicable coverage claim must carry no depth/witness and be vacuously true")

    def revalidate(
        self, *, inventory: dict[str, Any], value: dict[str, Any],
        input_constraints: dict[str, Any], derivation: dict[str, Any], roles: dict[str, str],
    ) -> None:
        _revalidate_structure(value=value, input_constraints=input_constraints, derivation=derivation, roles=roles)
        if value["capabilities"] != derivation["capabilities"]:
            raise ManifestError("capabilities claim does not match its derivation")
        if value.get("locality_range") != derivation["locality_range"]:
            raise ManifestError("locality_range claim does not match the interface contract")

    def checked_claim_names(self) -> list[str]:
        return ["topology", "message_passing", "xc", "operator", "semantic_derivations", "capabilities", "locality_range"]

    def checks(self, value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        capabilities = value["capabilities"]
        expected = capabilities["expected_locality"]
        # Unlike formal_binding_candidates, this fixed-policy judgment can't
        # evaluate non_local_capacity without a concrete requirement.
        if expected not in {"local", "non_local"}:
            raise ManifestError(
                "capabilities.expected_locality must be 'local' or 'non_local' to evaluate structural checks"
            )
        return {
            "xc_discontinuity_compatible": {
                "satisfied": value["xc"]["form"] == "hinge",
                "form": value["xc"]["form"],
                "provenance_nodes": value["xc"].get("provenance_nodes", []),
            },
            "all_pairs_reachable": {
                "satisfied": capabilities["all_pairs_reachable"],
                "applicable": capabilities["all_pairs_reachable_applicable"],
                "unreachable_pairs": capabilities["unreachable_pairs"],
                "operator_message_depth": capabilities["operator_message_depth"],
                "provenance_nodes": value["operator"].get("provenance_nodes", []),
            },
            "non_local_capacity": {
                "satisfied": expected == "local" or capabilities["non_local_capacity"],
                "expected": expected,
                "capacity": capabilities["non_local_capacity"],
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
        )

    def failure_witness(self, name: str, check: dict[str, Any]) -> dict[str, Any]:
        if name == "xc_discontinuity_compatible":
            return {
                "fact": name, "kind": "construction_form", "observed": check["form"],
                "required": "hinge", "provenance_nodes": check["provenance_nodes"],
            }
        if name == "all_pairs_reachable":
            return {
                "fact": name, "kind": "coverage_gap",
                "applicable": check["applicable"], "unreachable_pairs": check["unreachable_pairs"],
                "operator_message_depth": check["operator_message_depth"],
                "provenance_nodes": check["provenance_nodes"],
            }
        if name == "non_local_capacity":
            return {
                "fact": name, "kind": "insufficient_operator_capacity",
                "expected": check["expected"], "capacity": check["capacity"],
                "provenance_nodes": check["provenance_nodes"],
            }
        return {
            "fact": name, "kind": "operator_construction", "observed": check["construction"],
            "required": ["zero", "identity", "symmetrized"], "provenance_nodes": check["provenance_nodes"],
        }

    def what_was_checked(self) -> dict[str, str]:
        return {
            "xc_discontinuity_compatible": "The declared XC output path contains a supported hinge construction.",
            "all_pairs_reachable": (
                "Every ordered pair of sites is reachable from every other within the message-passing "
                "depth found strictly within the self-energy operator's OWN ancestry -- not a separately "
                "declared message-passing output the operator need not depend on. Not applicable when "
                "the operator's construction recipe does not depend on message-passing at all (the only "
                "recipes this plugin currently recognizes -- bare and symmetrized parameters -- never do)."
            ),
            "non_local_capacity": (
                "When non-locality is claimed and there are at least two sites, the operator's "
                "construction recipe admits some parameter assignment with a nonzero off-diagonal entry "
                "-- a fact about the construction and site count, never about the values currently "
                "stored in it."
            ),
            "self_adjoint": "The declared operator output is structurally zero, identity, or a parameter plus its transpose.",
        }

    def model_description_lines(self, value: dict[str, Any]) -> list[str]:
        capabilities = value["capabilities"]
        coverage = (
            "not applicable (operator does not depend on message-passing)"
            if not capabilities["all_pairs_reachable_applicable"]
            else "covered" if capabilities["all_pairs_reachable"]
            else f"gaps: {capabilities['unreachable_pairs']}"
        )
        return [
            f"- Topology: {value['topology']['site_count']} sites and {len(value['topology']['directed_edges'])} directed edges.",
            f"- All-pairs receptive field (within the operator's own ancestry): {coverage}"
            + ("" if capabilities["operator_message_depth"] is None else f" within depth {capabilities['operator_message_depth']}")
            + ".",
            f"- Self-energy non-local capacity: {capabilities['non_local_capacity']} (claimed {capabilities['expected_locality']}).",
            f"- Self-energy construction: {value['operator']['construction']}; supporting graph nodes: {value['operator'].get('provenance_nodes', [])}.",
            f"- XC output construction: {value['xc']['form']}; supporting graph nodes: {value['xc'].get('provenance_nodes', [])}.",
            "- No extracted floating-point weight value was read to compute any of the above.",
        ]

    def trust_boundary_lines(self) -> list[str]:
        return [
            "The PT2 artifact is deserialized only by the extractor boundary; its SHA-256 binds this report to that file.",
            "The translation validator independently rechecks the IR claims against the exported graph inventory. No extracted parameter's floating-point content is read anywhere in this plugin's derivation, IR, or checks -- there is no real-weight observation in this report at all, and nothing here is 'not applicable' because a value happened to look uninteresting.",
            "Lean can verify the generated structural theorems, but it does not parse the PT2 binary itself.",
            "`all_pairs_reachable` is only applicable when the self-energy operator's own construction recipe actually depends on message-passing; none of the recipes recognized today (zero/identity/symmetrized/unconstrained parameter) do, so it is `not applicable` (vacuously satisfied, not gating) for every artifact this plugin can currently certify.",
            "This report certifies architectural capability only -- never training convergence, numerical accuracy, or that a trained instance actually realizes the capability certified here.",
        ]

    def lean_preamble_fields(self, value: dict[str, Any], namespace: str) -> str:
        capabilities = value["capabilities"]
        depth = capabilities["operator_message_depth"] if capabilities["operator_message_depth"] is not None else 0
        return (
            f"def edges : List (Nat × Nat) := {_lean_edges(value['topology']['directed_edges'])}\n"
            f"def siteCount : Nat := {value['topology']['site_count']}\n"
            f"def operatorMessageDepth : Nat := {depth}\n"
            f"def expectedLocal : Bool := {str(capabilities['expected_locality'] == 'local').lower()}\n"
            f"def xcForm : {self.lean_import}.XCForm := {_lean_xc(value['xc']['form'])}\n"
            f"def operatorForm : {self.lean_import}.OperatorForm := "
            f"{_lean_operator(value['operator']['construction'], value['operator'].get('recipe'))}"
        )

    def lean_statements(
        self, value: dict[str, Any], namespace: str, checks: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        statements = {
            "xc_discontinuity_compatible": (
                f"theorem generated_xc_structure : {self.lean_import}.xcSupportsDiscontinuity "
                f"{namespace}.xcForm = {str(checks['xc_discontinuity_compatible']['satisfied']).lower()}"
            ),
            "non_local_capacity": (
                f"theorem generated_capacity_structure : ({namespace}.expectedLocal || "
                f"{self.lean_import}.canRepresentNonLocal {namespace}.siteCount {namespace}.operatorForm) = "
                f"{str(checks['non_local_capacity']['satisfied']).lower()}"
            ),
            "self_adjoint": (
                f"theorem generated_operator_structure : {self.lean_import}.guaranteedSelfAdjoint "
                f"{namespace}.operatorForm = {str(checks['self_adjoint']['satisfied']).lower()}"
            ),
        }
        if checks["all_pairs_reachable"]["applicable"]:
            statements["all_pairs_reachable"] = (
                f"theorem generated_coverage_structure : {self.lean_import}.allPairsReachable "
                f"{namespace}.edges {namespace}.operatorMessageDepth {namespace}.siteCount = "
                f"{str(checks['all_pairs_reachable']['satisfied']).lower()}"
            )
        return statements

    def formal_binding_candidates(self, value: dict[str, Any]) -> list[FormalBindingCandidate]:
        """Terms needed to instantiate the DFT theorem entrypoints in
        `examples/dft/lean/Testv2/Requirements.lean`: site count, operator
        construction, XC form, and topology in case a theorem needs
        `allPairsReachable`."""
        topology, operator, xc = value["topology"], value["operator"], value["xc"]
        capabilities = value["capabilities"]
        candidates = [
            FormalBindingCandidate(
                key="site_count",
                lean_expr=str(topology["site_count"]),
                provenance="artifact_grounded",
                evidence_refs=tuple(topology.get("provenance_nodes", [])),
                display_label=f"siteCount = {topology['site_count']}",
            ),
            FormalBindingCandidate(
                key="operator_form",
                lean_expr=_lean_operator(
                    operator["construction"], operator.get("recipe"), operator.get("layout"),
                ).replace(".", f"{self.lean_import}.OperatorForm.", 1),
                provenance="artifact_grounded",
                evidence_refs=tuple(operator.get("provenance_nodes", [])),
                display_label=f"operator = {operator['construction']}",
            ),
            FormalBindingCandidate(
                key="locality_range",
                lean_expr=_lean_locality_range(value.get("locality_range", 4)),
                # The only specified-interface locality datum (a graph-hop
                # radius `R`); Lean derives the long-range relation from it.
                provenance="specified_interface",
                evidence_refs=(),
                display_label=f"localityRange = {value.get('locality_range', 4)}",
            ),
            FormalBindingCandidate(
                key="xc_form",
                lean_expr=_lean_xc(xc["form"]).replace(".", f"{self.lean_import}.XCForm.", 1),
                provenance="artifact_grounded",
                evidence_refs=tuple(xc.get("provenance_nodes", [])),
                display_label=f"xc = {xc['form']}",
            ),
            FormalBindingCandidate(
                key="edges",
                lean_expr=_lean_edges(topology["directed_edges"]),
                provenance="artifact_grounded",
                evidence_refs=tuple(topology.get("provenance_nodes", [])),
                display_label=f"edges = {topology['directed_edges']}",
            ),
        ]
        # `None` means not applicable, not "depth = 0"; a fabricated zero
        # here could silently fill an unrelated theorem's Nat binder.
        if capabilities["operator_message_depth"] is not None:
            candidates.append(FormalBindingCandidate(
                key="operator_message_depth",
                lean_expr=str(capabilities["operator_message_depth"]),
                provenance="artifact_grounded",
                evidence_refs=tuple(operator.get("provenance_nodes", [])),
                display_label=f"operatorMessageDepth = {capabilities['operator_message_depth']}",
            ))
        return candidates


DFT_CAPABILITY_PLUGIN = DFTCapabilityPlugin()
# Self-registers so the verification harness can look this adapter up by
# profile name without importing this module directly.
register_adapter(DFT_CAPABILITY_PLUGIN)
