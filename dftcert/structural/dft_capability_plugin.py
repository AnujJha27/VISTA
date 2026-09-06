"""Pre-training architectural-capability certification for the DFT/GNN target.

`dft_plugin.DFTPlugin` certifies a real fact about a candidate's own
*extracted trained floats*: is the learned self-energy operator actually
diagonal, or does it actually have a nonzero off-diagonal entry. That fact
cannot exist before training -- there are no weights yet, and `derive()`
gets there by calling `_operator_matrix`/`_locality_from_recipe`, which read
a parameter's actual floating-point content.

This plugin asks the question that *can* be answered before training, from
`derive_structure()` alone -- topology, message-passing chains, and operator
construction *classification* -- and never calls anything that reads a
parameter's floating-point content:

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
  site count, reusing `DFTPlugin`'s own construction classification --
  never about the values currently stored in it.
- `self_adjoint`/`xc_discontinuity_compatible`: unchanged from `DFTPlugin`
  -- already recipe-only, no floats.

`DFTPlugin`'s real-weight `locality` observation never enters this plugin's
derivation, IR, or checks at all -- not merely non-gating. See
`STRUCTURAL_CAPABILITY_CHECKS.md`.
"""
from __future__ import annotations

from typing import Any

from ..manifest import ManifestError
from .dft_plugin import (
    DFTPlugin, _ancestors, _lean_edges, _lean_operator, _lean_xc,
    _message_chain, _revalidate_structure, _validate_structure_sections,
)

_NON_LOCAL_CAPABLE_RECIPES = {"sum_transpose", "param"}


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


class DFTCapabilityPlugin(DFTPlugin):
    name = "dft-capability"
    ir_schema_version = 4
    analyzer_version = "dft-structural-capability-analysis-1"
    policy_version = "dft-structural-capability-1"
    compiler_version = "dft-structural-capability-lean-1"

    def derive(
        self, *, inventory: dict[str, Any], nodes: list[dict[str, Any]],
        roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """`derive_structure()` only -- never `derive()`, which would also
        compute the real-weight `locality` observation from extracted
        floats. This plugin's derivation never reads a trainable value."""
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
        sections = super().translation_sections(derivation=derivation, roles=roles, input_constraints=input_constraints)
        sections["schema_version"] = self.ir_schema_version
        return sections

    def validate_ir_sections(self, value: dict[str, Any]) -> None:
        _validate_structure_sections(value)
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ManifestError("structural IR is missing capabilities")
        if capabilities.get("expected_locality") not in {"local", "non_local"}:
            raise ManifestError("capabilities.expected_locality must be 'local' or 'non_local'")
        if not isinstance(capabilities.get("all_pairs_reachable"), bool):
            raise ManifestError("capabilities.all_pairs_reachable must be boolean")
        if not isinstance(capabilities.get("all_pairs_reachable_applicable"), bool):
            raise ManifestError("capabilities.all_pairs_reachable_applicable must be boolean")
        if not isinstance(capabilities.get("non_local_capacity"), bool):
            raise ManifestError("capabilities.non_local_capacity must be boolean")
        count = value["topology"]["site_count"]
        depth = capabilities.get("operator_message_depth")
        unreachable = capabilities.get("unreachable_pairs")
        if capabilities["all_pairs_reachable_applicable"]:
            if not isinstance(depth, int) or isinstance(depth, bool) or depth < 0:
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
        elif depth is not None or unreachable is not None or not capabilities["all_pairs_reachable"]:
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
        # Deliberately not `super().lean_preamble_fields()`: that reads
        # `value["locality"]` (the real-weight observation), which does not
        # exist in this plugin's IR at all -- there is no float-derived
        # field anywhere in this preamble.
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
                f"{self.lean_import}.canRepresentNonLocal {namespace}.operatorForm) = "
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


DFT_CAPABILITY_PLUGIN = DFTCapabilityPlugin()
