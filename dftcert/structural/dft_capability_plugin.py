"""Pre-training architectural-capability certification for the DFT/GNN target.

This is the project's ONLY structural plugin: it certifies architectural
*capability* before a single weight is trained, and never reads an
extracted parameter's floating-point content anywhere in its derivation,
IR, or checks. There used to be a second, post-training plugin that read
real trained weights to check numeric locality (`operator_locality_verified`)
-- it has been removed entirely: this project's claim is a pre-training
check, and keeping a post-training plugin alongside it made that claim
ambiguous. See `STRUCTURAL_CAPABILITY_CHECKS.md`.

Checks:

- `all_pairs_reachable`: every ordered pair of sites is reachable from every
  other within the message-passing depth found *strictly within the
  operator's own ancestry* -- not a separately declared `message_state`
  output that the operator need not depend on at all. When the operator's
  construction recipe does not depend on message-passing (e.g. a bare or
  symmetrized parameter -- the only recipes this plugin currently
  recognizes), the check is `not applicable`: a message-passing-derived
  receptive-field claim is meaningless for an operator that message passing
  never touches, and is never silently satisfied by an unrelated branch.
- `non_local_capacity`: when non-locality is claimed and there are at least
  two sites, does the operator's construction recipe admit *some*
  parameter assignment with a nonzero off-diagonal entry? `zero`/`identity`
  never can; `symmetrized` (`B + B^T`) and `unconstrained_parameter` can,
  provided a second site actually exists for an off-diagonal entry to live
  at (a 1x1 matrix has none, for any recipe). A fact about the recipe and
  site count, never about the values currently stored in it.
- `self_adjoint`: the declared operator output is structurally zero,
  identity, or a parameter plus its transpose -- recipe-only, no floats.
- `xc_discontinuity_compatible`: the declared XC output path contains a
  supported hinge construction.
"""
from __future__ import annotations

from typing import Any

from ..manifest import ManifestError
from ..verification.model import FormalBindingCandidate
from .plugin import StructuralPlugin, _refs

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
_NON_LOCAL_CAPABLE_RECIPES = {"sum_transpose", "param"}
_NON_PARAMETER_STATE_KIND_MARKERS = ("user_input",)


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


def _resolve_operator_layout(input_constraints: dict[str, Any]) -> dict[str, Any]:
    """The operator's declared domain/codomain axis grouping. Default is the
    plain n x n matrix (`output_axes=[0]`, `input_axes=[1]`), covering every
    artifact certified before this field existed. A grouped layout -- e.g.
    site and orbital/spin axes folded together into a shape like
    `[N, m, N, m]`, still mathematically a linear operator on the flattened
    Nm-dimensional space once the axis groups are known -- is opt-in via
    `input_constraints.operator_layout`. Only the canonical contiguous
    grouping (`output_axes=[0..r-1]`, `input_axes=[r..2r-1]`) is supported;
    a reordered or interleaved grouping is `unsupported`, never guessed at.
    This only matters for correctly recognizing the adjoint construction
    (`_is_adjoint_of`) -- there is no float-reading anywhere in this plugin
    that would need to know which axis is a "site" versus an "orbital"."""
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
    """Whether `node` actually constructs the adjoint under `layout` -- by
    inspecting its real permutation/axis arguments, never by op name alone.
    A `permute`/`transpose.int` call with a no-op or wrong permutation (e.g.
    `transpose.int(x, 0, 0)`, or `permute(x, [0, 1])` -- neither actually
    swaps anything) must not be accepted just because its op name is on the
    reviewed list; only `.t()`/`numpy_T` have no axis arguments to check and
    are unambiguous for a two-axis tensor."""
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
    return target in {"aten.t.default", "aten.numpy_t.default"}


def _operator_state_name(inventory: dict[str, Any], node_name: str) -> str | None:
    """Reverse-lookup: which extracted state entry does this graph node alias?"""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return None
    for name, entry in state.items():
        if isinstance(entry, dict) and node_name in entry.get("graph_inputs", []):
            return name
    return None


def _is_plausible_parameter_node(inventory: dict[str, Any], node_name: str) -> bool:
    """Whether `node_name` does NOT resolve to a state entry the extractor
    classified as a plain runtime input -- so a "built from an unconstrained
    parameter" claim (implying trainable freedom, used for `non_local_capacity`)
    can never secretly be built from a raw activation input that was never a
    trainable weight at all. Fails permissive (True) when no classification
    is available at all (`state_kind` absent or unrecognized, since a
    hand-authored specification or an older extractor version may not carry
    it); fails closed only on an explicit user-input classification -- a
    real signal, not a guess."""
    state = inventory.get("state", {})
    if not isinstance(state, dict):
        return True
    state_name = _operator_state_name(inventory, node_name)
    entry = state.get(state_name) if state_name else None
    if not isinstance(entry, dict):
        return True
    kind = str(entry.get("state_kind", "")).lower()
    return not any(marker in kind for marker in _NON_PARAMETER_STATE_KIND_MARKERS)


def _operator_construction(
    nodes: list[dict[str, Any]], root: str, layout: dict[str, Any], inventory: dict[str, Any],
) -> tuple[str, list[str], dict[str, Any]]:
    """Classify the operator's construction and return a `recipe` describing
    it, purely from graph shape -- never a float.

    Self-adjointness (the `symmetrized` recipe, `add(base, adjoint(base))`)
    holds for *any* `base` -- B + B^dagger is self-adjoint regardless of
    whether B is a trained weight, so that branch never needs a parameter
    check. `unconstrained_parameter` is different: it claims `base` is a
    free, trainable matrix, which does need `_is_plausible_parameter_node`.
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
                if _is_adjoint_of(transformed_node, layout):
                    transformed_base = _direct_ref(transformed_node.get("args"))
                    if transformed_base == base:
                        return "symmetrized", provenance, {
                            "kind": "sum_transpose", "base": base, "transposed_base": transformed_base,
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
                        }
    if root_node.get("op") in {"placeholder", "get_attr"} and _is_plausible_parameter_node(inventory, root):
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
) -> tuple[int, list[list[int]], list[str], str, str]:
    requested = input_constraints.get("adjacency_state_name")
    state_name = _state_name(inventory, requested)
    # Which state entry became "the adjacency" is either exactly what the
    # analyst declared, or a heuristic name-match fallback (any state entry
    # whose name contains "adjacency") when they didn't -- a real
    # interpretation choice, not an artifact fact, so it is recorded rather
    # than left indistinguishable from a declared name.
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


def _lean_operator(construction: str) -> str:
    return {
        "zero": ".zero",
        "identity": ".identity",
        "symmetrized": '.add (.parameter "base") (.adjoint (.parameter "base"))',
        "unconstrained_parameter": '.parameter "unconstrained"',
        "unsupported": ".unsupported",
    }[construction]


def _non_local_capacity(recipe: dict[str, Any], site_count: int) -> bool:
    return site_count >= 2 and recipe.get("kind") in _NON_LOCAL_CAPABLE_RECIPES


def _unreachable_pairs(
    site_count: int, edges: list[list[int]], depth: int,
) -> list[dict[str, int]]:
    """Ordered (source, target) pairs not reachable from `source` within
    `depth` directed hops of `edges` -- empty iff the architecture places no
    receptive-field obstruction on any pair of sites."""
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
    """Adjacency-fed message-passing stages found strictly within the
    operator's OWN ancestry (never a separately declared `message_state`
    root). `None` means the operator does not depend on message-passing at
    all -- e.g. a bare or symmetrized parameter, the only recipes this
    plugin currently recognizes -- so a message-passing-derived
    receptive-field claim about it does not apply."""
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
    """Shape checks for `topology`/`message_passing`/`xc`/`operator` --
    never `capabilities`, which is each plugin's own concern. Factored out
    (not just inlined into one class) so a future second plugin sharing this
    same DFT-shaped topology/xc/operator IR (a different check set over the
    same architecture facts) can reuse it instead of re-deriving it."""
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
    `semantic_derivations` against a freshly recomputed `derivation` --
    never `capabilities`. Factored out for the same reason as
    `_validate_structure_sections` above."""
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
        "layout": derivation["operator_layout"],
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
        classification alone -- topology (a declared bool/int adjacency
        buffer, never a trainable float), message-passing depth, XC form,
        operator-construction recipe. Never reads a single extracted
        parameter's floating-point content."""
        # `expected_locality` is a *requirement* (what the caller wants),
        # not an artifact fact -- optional here so a theorem-centric caller
        # can derive pure structural facts without supplying one; the fixed
        # legacy policy check (`checks()`, the only place that judges it)
        # still requires a concrete value, so `vista structural` callers
        # see no behavior change.
        expected_locality = input_constraints.get("expected_locality")
        if expected_locality not in {"local", "non_local", None}:
            raise ManifestError("input_constraints.expected_locality must be 'local' or 'non_local'")
        layout = _resolve_operator_layout(input_constraints)
        count, edges, graph_inputs, state_name, adjacency_selection_provenance = _topology(inventory, input_constraints)
        aliases = _adjacency_aliases(nodes, graph_inputs)
        stages, message_recognized = _message_chain(nodes, roles["message_state"], graph_inputs)
        xc_form, xc_nodes = _xc_form(nodes, roles["xc_energy"])
        operator, operator_nodes, operator_recipe = _operator_construction(nodes, roles["learned_self_energy"], layout, inventory)
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
            },
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

    def checked_claim_names(self) -> list[str]:
        return ["topology", "message_passing", "xc", "operator", "semantic_derivations", "capabilities"]

    def checks(self, value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        capabilities = value["capabilities"]
        expected = capabilities["expected_locality"]
        # The legacy fixed-policy judgment (unlike theorem-centric
        # `formal_binding_candidates`, which needs no locality requirement
        # at all) genuinely cannot judge `non_local_capacity` without one.
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
        construction, XC form. Topology (edges/depth) is exposed too since a
        selected theorem may genuinely need `allPairsReachable`, but the
        current recognized self-energy recipes never depend on message
        passing (see `all_pairs_reachable`'s `applicable` flag above)."""
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
                lean_expr=_lean_operator(operator["construction"]).replace(".", f"{self.lean_import}.OperatorForm.", 1),
                provenance="artifact_grounded",
                evidence_refs=tuple(operator.get("provenance_nodes", [])),
                display_label=f"operator = {operator['construction']}",
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
        # `operator_message_depth = None` means "not applicable" (the
        # operator's construction recipe doesn't depend on message passing
        # at all -- see `_reachability`), not the artifact fact "depth =
        # 0". Emitting a fabricated zero candidate here would let an
        # unrelated theorem `Nat` binder silently receive a made-up value
        # for a property that was never established at all.
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
