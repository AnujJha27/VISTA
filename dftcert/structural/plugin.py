"""The domain-plugin interface. See VISTA_GENERALIZATION.md.

VISTA's harness (`dftcert.structural.core`) -- extraction plumbing, hashing,
translation-validation re-derivation, certificate assembly/binding, Lean
invocation -- is domain-agnostic. Everything that knows what a "claim" means
for one verification target lives behind this interface, implemented once
per domain. `dftcert.structural.dft_plugin.DFT_PLUGIN` is the first (and,
today, only) implementation; it is also the harness's default, so every
existing caller keeps working unchanged.

Each plugin owns its own default Lean import (`lean_import`): the module its
generated obligations are checked against. The harness never hardcodes a
Lean module name -- a different domain brings its own proof base.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from ..manifest import ManifestError


def _refs(value: Any) -> list[str]:
    """Node-name references inside an exported-graph `args`/`kwargs` tree.
    Generic to the torch-export JSON shape, not to any one domain."""
    if isinstance(value, dict):
        if set(value) == {"node"} and isinstance(value["node"], str):
            return [value["node"]]
        return [item for child in value.values() for item in _refs(child)]
    if isinstance(value, list):
        return [item for child in value for item in _refs(child)]
    return []


def _output_roots(nodes: list[dict[str, Any]]) -> list[str]:
    outputs = [node for node in nodes if node.get("op") == "output"]
    if len(outputs) != 1:
        raise ManifestError("structural inventory requires exactly one output node")
    return _refs(outputs[0].get("args"))


class StructuralPlugin(ABC):
    name: str
    lean_import: str
    ir_schema_version: int
    analyzer_version: str
    policy_version: str
    compiler_version: str

    @abstractmethod
    def role_requirements(self) -> set[str]:
        """Required `output_contracts` roles, e.g. {"xc_energy", ...}."""

    def role_roots(
        self, nodes: list[dict[str, Any]], input_constraints: dict[str, Any],
    ) -> dict[str, str]:
        """Generic `output_contracts` resolution shared by every plugin:
        maps this plugin's required role names to the exported graph's
        output node names. Not abstract -- override only if a domain needs
        different role-resolution semantics."""
        roots = _output_roots(nodes)
        contracts = input_constraints.get("output_contracts")
        if not isinstance(contracts, list):
            raise ManifestError("output_contracts must identify structural output roles")
        result: dict[str, str] = {}
        for contract in contracts:
            if not isinstance(contract, dict):
                raise ManifestError("output contracts must be objects")
            index, role = contract.get("index"), contract.get("role")
            if not isinstance(index, int) or not isinstance(role, str) or index < 0 or index >= len(roots):
                raise ManifestError("output contract index or role is invalid")
            if role in result:
                raise ManifestError(f"duplicate output contract role {role!r}")
            result[role] = roots[index]
        if len(set(result.values())) != len(result):
            raise ManifestError("output contract roles must resolve to distinct outputs")
        required = self.role_requirements()
        if set(result) != required:
            raise ManifestError(f"output_contracts must map exactly {sorted(required)}")
        return result

    @abstractmethod
    def derive(
        self, *, inventory: dict[str, Any], nodes: list[dict[str, Any]],
        roles: dict[str, str], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """Lower raw graph/tensor facts into a domain-specific `derivation`
        dict -- the single source of truth every method below reuses. Stored
        verbatim in `translation.semantic_derivations`."""

    @abstractmethod
    def ir_sections(
        self, *, derivation: dict[str, Any], input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """Top-level IR sections beyond `ir_schema_version`/`source`/
        `translation` (for DFT: `topology`, `message_passing`, `xc`,
        `operator`, `locality`)."""

    @abstractmethod
    def translation_sections(
        self, *, derivation: dict[str, Any], roles: dict[str, str],
        input_constraints: dict[str, Any],
    ) -> dict[str, Any]:
        """The domain-specific parts of the `translation` sub-object."""

    @abstractmethod
    def validate_ir_sections(self, value: dict[str, Any]) -> None:
        """Raise `ManifestError` if this plugin's IR sections are malformed."""

    @abstractmethod
    def revalidate(
        self, *, inventory: dict[str, Any], value: dict[str, Any],
        input_constraints: dict[str, Any], derivation: dict[str, Any],
        roles: dict[str, str],
    ) -> None:
        """Independently recompute this plugin's claims from raw inventory
        and raise `ManifestError` on any disagreement with `value`."""

    @abstractmethod
    def checked_claim_names(self) -> list[str]:
        """Claim names this plugin's `revalidate` covers, appended to
        `translation_validation.checked_claims`."""

    @abstractmethod
    def checks(self, value: dict[str, Any]) -> dict[str, dict[str, Any]]:
        """name -> {"satisfied": bool, ...evidence, "provenance_nodes": [...]}."""

    @abstractmethod
    def supported(self, value: dict[str, Any]) -> bool:
        """Whether every check is even evaluable (gates `formalization_required`)."""

    @abstractmethod
    def failure_witness(self, name: str, check: dict[str, Any]) -> dict[str, Any]:
        """One structured witness for an unsatisfied check."""

    @abstractmethod
    def what_was_checked(self) -> dict[str, str]:
        """check name -> human-readable description, for `structural_report`."""

    @abstractmethod
    def model_description_lines(self, value: dict[str, Any]) -> list[str]:
        """Extra lines for `structural_model_description`."""

    def trust_boundary_lines(self) -> list[str]:
        """`structural_report`'s `trust_boundary` list. Generic default for
        any plugin that adds nothing beyond the harness's own guarantees;
        override to disclose what THIS plugin's checks do and do not
        establish (e.g. whether a real-weight observation exists at all)."""
        return [
            "The PT2 artifact is deserialized only by the extractor boundary; its SHA-256 binds this report to that file.",
            "Lean can verify the generated structural theorems, but it does not parse the PT2 binary itself.",
            "This report does not assess training convergence or general physical correctness.",
        ]

    @abstractmethod
    def lean_preamble_fields(self, value: dict[str, Any], namespace: str) -> str:
        """Domain-specific `def ... := ...` lines for the Lean preamble,
        referencing this plugin's own `lean_import` module."""

    @abstractmethod
    def lean_statements(
        self, value: dict[str, Any], namespace: str, checks: dict[str, dict[str, Any]],
    ) -> dict[str, str]:
        """check name -> Lean theorem statement string. Omit a name if its
        check cannot be stated (e.g. undetermined) rather than faking one."""
