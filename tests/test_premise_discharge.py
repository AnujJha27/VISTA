"""`dftcert.verification.resolver` (spec section 12) against a real Lean
toolchain: Route 1 deterministic discharge, and "failure to discharge is
not proof of falsity" (section 2.5) -- an honestly-false premise and a
premise blocked by an unresolved data binder must both come back
`unresolved`, never a fabricated witness either way.
"""
import unittest
from pathlib import Path

from dftcert.verification.model import FormalBindingCandidate
from dftcert.verification.resolver import resolve_entrypoint

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"

_SITE_COUNT_3 = FormalBindingCandidate(
    key="site_count", lean_expr="3", provenance="artifact_grounded",
    evidence_refs=("a",), display_label="siteCount = 3",
)
_IDENTITY = FormalBindingCandidate(
    key="operator_form", lean_expr="Testv2.StructuralV2.OperatorForm.identity",
    provenance="artifact_grounded", evidence_refs=("a",), display_label="operator = identity",
)
_SYMMETRIZED = FormalBindingCandidate(
    key="operator_form",
    lean_expr='Testv2.StructuralV2.OperatorForm.add (.parameter "base") (.adjoint (.parameter "base"))',
    provenance="artifact_grounded", evidence_refs=("a",), display_label="operator = symmetrized",
)
_HINGE = FormalBindingCandidate(
    key="xc_form", lean_expr="Testv2.StructuralV2.XCForm.hinge",
    provenance="artifact_grounded", evidence_refs=("a",), display_label="xc = hinge",
)
# research-soundness correction: `ValidPretrainingArchitecture`/
# `...Conditional` now have a `longRangePairs : Testv2.StructuralV2.
# LongRangePairs` binder (`hLR` depends on it); a valid pair for
# `siteCount = 3` is needed for `hLR` to discharge at all.
_LONG_RANGE_PAIRS = FormalBindingCandidate(
    key="long_range_pairs", lean_expr="⟨[(0, 2)]⟩",
    provenance="specified_interface", evidence_refs=(), display_label="longRangePairs = [[0, 2]]",
)


def _resolve(entrypoint, candidates):
    return resolve_entrypoint(
        project_root=PROJECT, imports=["Testv2.Requirements"], entrypoint=entrypoint,
        candidates=candidates, trusted_local=True, timeout_s=180,
    )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class PremiseDischargeTests(unittest.TestCase):
    def test_all_premises_discharge_for_a_long_range_capable_symmetrized_operator(self):
        result = _resolve(
            "Testv2.Requirements.ValidPretrainingArchitecture",
            [_SITE_COUNT_3, _LONG_RANGE_PAIRS, _SYMMETRIZED, _HINGE],
        )
        statuses = {p["index"]: p["status"] for p in result["premises"]}
        self.assertTrue(all(status == "formally_discharged" for status in statuses.values()), statuses)

    def test_an_honestly_false_premise_is_unresolved_not_a_fabricated_disproof(self):
        """`identity` genuinely cannot represent long-range coupling
        (`canRepresentLongRangeCoupling _ _ .identity = false`) -- Route 1
        must report this premise `unresolved`, never claim it proved the
        negation."""
        result = _resolve(
            "Testv2.Requirements.ValidPretrainingArchitecture",
            [_SITE_COUNT_3, _LONG_RANGE_PAIRS, _IDENTITY, _HINGE],
        )
        by_index = {p["index"]: p for p in result["premises"]}
        long_range_premise = next(
            p for p in by_index.values() if "canRepresentLongRangeCoupling" in p["type_display"]
        )
        self.assertEqual(long_range_premise["status"], "unresolved")

    def test_premise_depending_on_an_unresolved_data_binder_is_unresolved(self):
        """No candidate for `xc` -> `hXC`'s instantiated type still carries a
        metavariable -> discharge must not be attempted/claimed."""
        result = _resolve(
            "Testv2.Requirements.ValidPretrainingArchitecture",
            [_SITE_COUNT_3, _LONG_RANGE_PAIRS, _SYMMETRIZED],
        )
        by_index = {p["index"]: p for p in result["premises"]}
        xc_premise = next(p for p in by_index.values() if "xcSupportsDiscontinuity" in p.get("type_display", ""))
        self.assertEqual(xc_premise["status"], "unresolved")

    def test_conditional_entrypoints_external_assumption_premise_is_unresolved(self):
        result = _resolve(
            "Testv2.Requirements.ValidPretrainingArchitectureConditional",
            [_SITE_COUNT_3, _LONG_RANGE_PAIRS, _SYMMETRIZED, _HINGE],
        )
        statuses = [p["status"] for p in result["premises"]]
        self.assertEqual(statuses.count("formally_discharged"), 3)
        self.assertEqual(statuses.count("unresolved"), 1)


if __name__ == "__main__":
    unittest.main()
