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

    def test_every_candidate_is_artifact_grounded_with_evidence(self):
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=True)
        for candidate in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value):
            self.assertEqual(candidate.provenance, "artifact_grounded")
            self.assertTrue(candidate.evidence_refs, f"{candidate.key} has no evidence_refs")

    def test_bare_parameter_operator_is_not_symmetrized(self):
        value = _ir(adjacency=_CHAIN3, stages=0, symmetrized=False)
        by_key = {item.key: item for item in DFT_CAPABILITY_PLUGIN.formal_binding_candidates(value)}
        self.assertEqual(by_key["operator_form"].lean_expr, 'Testv2.StructuralV2.OperatorForm.parameter "unconstrained"')


if __name__ == "__main__":
    unittest.main()
