"""Pre-training architectural-capability certification for the DFT/GNN target.

`dft_plugin.DFTPlugin` certifies a real fact about the candidate's own
*extracted trained floats*: is the learned self-energy operator actually
diagonal, or does it actually have a nonzero off-diagonal entry. That fact
cannot exist before training -- there are no weights yet.

This plugin asks the question that *can* be answered before training, from
the architecture alone (topology, message-passing depth, operator
construction recipe) -- never from any extracted floating-point value:

- `all_pairs_reachable`: every ordered pair of sites is reachable from every
  other within the declared message-passing depth. A fact about the graph
  and depth alone (`edges`/`depth`/`site_count`), computed the same way for
  every candidate.
- `non_local_capacity`: when non-locality is claimed, does the operator's
  construction recipe admit *some* parameter assignment with a nonzero
  off-diagonal entry? `zero`/`identity` never can; `symmetrized`
  (`B + B^T`) and `unconstrained_parameter` always can. A fact about the
  recipe, reusing `DFTPlugin`'s own construction classification -- never
  about the values currently stored in it.
- `self_adjoint`: unchanged from `DFTPlugin` -- it was already recipe-only,
  no floats.

`DFTPlugin`'s real-weight `locality` observation is still computed by
`derive()` (inherited unchanged) and carried in the IR/report for
information, but it does not gate `supported()` or this plugin's
disposition -- see `STRUCTURAL_CAPABILITY_CHECKS.md`.
"""
from __future__ import annotations

from typing import Any

from ..manifest import ManifestError
from .dft_plugin import DFTPlugin

_NON_LOCAL_CAPABLE_RECIPES = {"sum_transpose", "param"}


def _non_local_capacity(recipe: dict[str, Any]) -> bool:
    return recipe.get("kind") in _NON_LOCAL_CAPABLE_RECIPES


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
        derivation = super().derive(
            inventory=inventory, nodes=nodes, roles=roles, input_constraints=input_constraints,
        )
        unreachable = _unreachable_pairs(derivation["site_count"], derivation["edges"], derivation["depth"])
        derivation["capabilities"] = {
            "all_pairs_reachable": not unreachable,
            "unreachable_pairs": unreachable,
            "non_local_capacity": _non_local_capacity(derivation["operator_recipe"]),
        }
        return derivation

    def ir_sections(self, *, derivation: dict[str, Any], input_constraints: dict[str, Any]) -> dict[str, Any]:
        sections = super().ir_sections(derivation=derivation, input_constraints=input_constraints)
        sections["capabilities"] = derivation["capabilities"]
        return sections

    def translation_sections(
        self, *, derivation: dict[str, Any], roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        sections = super().translation_sections(derivation=derivation, roles=roles, input_constraints=input_constraints)
        sections["schema_version"] = self.ir_schema_version
        return sections

    def validate_ir_sections(self, value: dict[str, Any]) -> None:
        super().validate_ir_sections(value)
        capabilities = value.get("capabilities")
        if not isinstance(capabilities, dict):
            raise ManifestError("structural IR is missing capabilities")
        if not isinstance(capabilities.get("all_pairs_reachable"), bool):
            raise ManifestError("capabilities.all_pairs_reachable must be boolean")
        if not isinstance(capabilities.get("non_local_capacity"), bool):
            raise ManifestError("capabilities.non_local_capacity must be boolean")
        count = value["topology"]["site_count"]
        unreachable = capabilities.get("unreachable_pairs")
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

    def revalidate(
        self, *, inventory: dict[str, Any], value: dict[str, Any],
        input_constraints: dict[str, Any], derivation: dict[str, Any], roles: dict[str, str],
    ) -> None:
        super().revalidate(
            inventory=inventory, value=value, input_constraints=input_constraints,
            derivation=derivation, roles=roles,
        )
        if value["capabilities"] != derivation["capabilities"]:
            raise ManifestError("capabilities claim does not match its derivation")

    def checked_claim_names(self) -> list[str]:
        return [*super().checked_claim_names(), "capabilities"]

    def checks(self, value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        capabilities = value["capabilities"]
        expected = value["locality"]["expected"]
        return {
            "xc_discontinuity_compatible": {
                "satisfied": value["xc"]["form"] == "hinge",
                "form": value["xc"]["form"],
                "provenance_nodes": value["xc"].get("provenance_nodes", []),
            },
            "all_pairs_reachable": {
                "satisfied": capabilities["all_pairs_reachable"],
                "unreachable_pairs": capabilities["unreachable_pairs"],
                "depth": value["message_passing"]["depth"],
                "provenance_nodes": value["topology"].get("provenance_nodes", []),
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
                "unreachable_pairs": check["unreachable_pairs"], "depth": check["depth"],
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
                "Every ordered pair of sites is reachable from every other within the declared "
                "message-passing depth -- a fact about topology and depth alone, never about "
                "extracted weights."
            ),
            "non_local_capacity": (
                "When non-locality is claimed, the operator's construction recipe admits some "
                "parameter assignment with a nonzero off-diagonal entry -- a fact about the "
                "construction, never about the values currently stored in it."
            ),
            "self_adjoint": "The declared operator output is structurally zero, identity, or a parameter plus its transpose.",
        }

    def model_description_lines(self, value: dict[str, Any]) -> list[str]:
        capabilities = value["capabilities"]
        coverage = (
            "covered" if capabilities["all_pairs_reachable"]
            else f"gaps: {capabilities['unreachable_pairs']}"
        )
        return [
            f"- Topology: {value['topology']['site_count']} sites and {len(value['topology']['directed_edges'])} directed edges.",
            f"- All-pairs receptive field: {coverage} within depth {value['message_passing']['depth']}.",
            f"- Self-energy non-local capacity: {capabilities['non_local_capacity']} (claimed {value['locality']['expected']}).",
            f"- Self-energy construction: {value['operator']['construction']}; supporting graph nodes: {value['operator'].get('provenance_nodes', [])}.",
            f"- XC output construction: {value['xc']['form']}; supporting graph nodes: {value['xc'].get('provenance_nodes', [])}.",
            f"- (informational, non-gating) observed real-weight locality: {value['locality']}.",
        ]

    def lean_preamble_fields(self, value: dict[str, Any], namespace: str) -> str:
        base = super().lean_preamble_fields(value, namespace)
        return base + f"\ndef siteCount : Nat := {value['topology']['site_count']}"

    def lean_statements(
        self, value: dict[str, Any], namespace: str, checks: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        return {
            "xc_discontinuity_compatible": (
                f"theorem generated_xc_structure : {self.lean_import}.xcSupportsDiscontinuity "
                f"{namespace}.xcForm = {str(checks['xc_discontinuity_compatible']['satisfied']).lower()}"
            ),
            "all_pairs_reachable": (
                f"theorem generated_coverage_structure : {self.lean_import}.allPairsReachable "
                f"{namespace}.edges {namespace}.messageDepth {namespace}.siteCount = "
                f"{str(checks['all_pairs_reachable']['satisfied']).lower()}"
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


DFT_CAPABILITY_PLUGIN = DFTCapabilityPlugin()
