"""`DFTCapabilityPlugin.formal_binding_candidates` -- the terms the DFT
adapter exposes to the theorem-centric resolver (spec section 10). Reuses
`test_structural_capability`'s inventory builder: a ring adjacency with a
symmetrized (`add p_base p_base^T`) operator and a `relu`-based (hinge) XC
root, no extracted floats anywhere.
"""
import unittest

from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.model import FormalBindingCandidate
from tests.test_structural_capability import _CHAIN3, _ir


class FormalBindingCandidateTests(unittest.TestCase):
    def test_candidates_cover_site_count_operator_and_xc(self):
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True)
        candidates = DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value)
        self.assertTrue(all(isinstance(item, FormalBindingCandidate) for item in candidates))
        by_key = {item.key: item for item in candidates}
        self.assertEqual(by_key["site_count"].lean_expr, "3")
        self.assertEqual(
            by_key["operator_form"].lean_expr,
            'Testv2.StructuralV2.OperatorForm.add (.parameter "base") (.adjoint (.parameter "base"))',
        )
        self.assertEqual(by_key["xc_form"].lean_expr, "Testv2.StructuralV2.XCForm.hinge")

    def test_every_candidate_is_artifact_grounded_or_specified_interface_with_evidence(self):
        # research-soundness correction: `locality_range` is deliberately
        # NOT artifact_grounded -- it is SPECIFIED INTERFACE data (the
        # graph-hop radius `R`), and carries no artifact evidence_refs at
        # all, unlike every other candidate here. Which pairs are
        # long-range is never itself a candidate -- it is derived by Lean
        # from `edges` and `R`, both of which ARE artifact/specified
        # candidates already covered by this loop.
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True)
        for candidate in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value):
            if candidate.key == "locality_range":
                self.assertEqual(candidate.provenance, "specified_interface")
                continue
            self.assertEqual(candidate.provenance, "artifact_grounded")
            self.assertTrue(candidate.evidence_refs, f"{candidate.key} has no evidence_refs")

    def test_bare_parameter_operator_is_not_symmetrized(self):
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=False)
        by_key = {item.key: item for item in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value)}
        self.assertEqual(by_key["operator_form"].lean_expr, 'Testv2.StructuralV2.OperatorForm.parameter "unconstrained"')

    def test_not_applicable_message_depth_emits_no_fake_zero_candidate(self):
        """Issue 10: neither recipe this pipeline can build through the
        public path ever depends on message passing, so
        `operator_message_depth` is honestly `None` (not applicable) --
        never silently coerced into the artifact fact `depth = 0`, which
        would let an unrelated theorem `Nat` binder receive a fabricated
        value for a property that was never established."""
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True)
        self.assertIsNone(value["capabilities"]["operator_message_depth"])
        keys = {item.key for item in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value)}
        self.assertNotIn("operator_message_depth", keys)

    def test_derivation_works_without_expected_locality(self):
        """Issue 5: theorem-centric artifact-fact derivation is
        policy-neutral -- `expected_locality` is a requirement a selected
        Lean theorem's premises express, not something needed merely to
        describe the artifact's topology/operator/XC facts."""
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True, expected_locality=None)
        self.assertIsNone(value["capabilities"]["expected_locality"])
        candidates = DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value)
        by_key = {item.key: item for item in candidates}
        self.assertEqual(by_key["site_count"].lean_expr, "3")
        self.assertEqual(by_key["xc_form"].lean_expr, "Testv2.StructuralV2.XCForm.hinge")

    def test_legacy_checks_still_require_expected_locality(self):
        """The fixed legacy policy judgment (`vista structural`'s own
        `checks()`) is unaffected -- it still can't judge non-local
        capacity without a concrete requirement, so no behavior change for
        existing legacy callers."""
        from dftcert.manifest import ManifestError
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True, expected_locality=None)
        with self.assertRaises(ManifestError):
            DFT_CAPABILITY_PLUGIN.checks(value)


if __name__ == "__main__":
    unittest.main()
