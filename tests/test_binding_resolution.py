"""`dftcert.verification.resolver.resolve_entrypoint`'s data-binder
resolution against a real Lean toolchain (spec section 27.3): never pick
among multiple typechecking candidates, never accept a wrong-typed one.
"""
import unittest
from pathlib import Path

from dftcert.manifest import ManifestError
from dftcert.verification.model import FormalBindingCandidate
from dftcert.verification.resolver import resolve_entrypoint

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"

_SITE_COUNT = FormalBindingCandidate(
    key="site_count", lean_expr="3", provenance="artifact_grounded",
    evidence_refs=("n1",), display_label="siteCount = 3",
)
_DEPTH = FormalBindingCandidate(
    key="operator_message_depth", lean_expr="2", provenance="artifact_grounded",
    evidence_refs=("n2",), display_label="operatorMessageDepth = 2",
)
_OPERATOR = FormalBindingCandidate(
    key="operator_form", lean_expr="Testv2.StructuralV2.OperatorForm.identity",
    provenance="artifact_grounded", evidence_refs=("n3",), display_label="operator = identity",
)
_XC = FormalBindingCandidate(
    key="xc_form", lean_expr="Testv2.StructuralV2.XCForm.hinge",
    provenance="artifact_grounded", evidence_refs=("n4",), display_label="xc = hinge",
)


def _resolve(candidates, **kwargs):
    return resolve_entrypoint(
        project_root=PROJECT, imports=["Testv2.Requirements"], entrypoint=ENTRYPOINT,
        candidates=candidates, trusted_local=True, timeout_s=180, **kwargs,
    )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class BindingResolutionTests(unittest.TestCase):
    def test_exactly_one_typechecking_candidate_resolves_automatically(self):
        # `ValidPretrainingArchitecture`'s real signature is (siteCount,
        # edges, locality, op, xc, hSA, hLR, hXC) -- the graph-hop
        # long-range correction replaced the old `longRangePairs` binder
        # with `edges`/`locality` (Testv2/StructuralV2.lean's
        # `canRepresentLongRangeCoupling`), so `op`/`xc` are indices 3/4.
        result = _resolve([_OPERATOR, _XC])
        by_index = {entry["index"]: entry for entry in result["data_binders"]}
        self.assertEqual(by_index[3]["status"], "resolved")
        self.assertEqual(by_index[3]["chosen_candidate_key"], "operator_form")
        self.assertEqual(by_index[4]["status"], "resolved")
        self.assertEqual(by_index[4]["chosen_candidate_key"], "xc_form")

    def test_zero_candidates_is_unresolved(self):
        result = _resolve([_XC])
        by_index = {entry["index"]: entry for entry in result["data_binders"]}
        self.assertEqual(by_index[0]["status"], "unresolved")

    def test_two_same_typed_candidates_are_ambiguous_never_first_picked(self):
        result = _resolve([_SITE_COUNT, _DEPTH, _OPERATOR, _XC])
        site_count_entry = next(entry for entry in result["data_binders"] if entry["index"] == 0)
        self.assertEqual(site_count_entry["status"], "ambiguous_binding")
        self.assertEqual(set(site_count_entry["matching_candidate_keys"]), {"site_count", "operator_message_depth"})
        self.assertNotIn("chosen_candidate_key", site_count_entry)

    def test_explicit_user_choice_resolves_the_ambiguity(self):
        result = _resolve([_SITE_COUNT, _DEPTH, _OPERATOR, _XC], forced_choices={0: "site_count"})
        site_count_entry = next(entry for entry in result["data_binders"] if entry["index"] == 0)
        self.assertEqual(site_count_entry["status"], "resolved")
        self.assertEqual(site_count_entry["chosen_candidate_key"], "site_count")

    def test_wrong_typed_candidate_is_rejected_by_lean_not_python(self):
        """`operator_form`'s Lean expression (an `OperatorForm`) must never
        match `siteCount`'s `Nat` binder -- Lean's own elaborator rejects
        it; nothing in `resolve_entrypoint` special-cases these types."""
        result = _resolve([_OPERATOR])
        site_count_entry = next(entry for entry in result["data_binders"] if entry["index"] == 0)
        self.assertEqual(site_count_entry["status"], "unresolved")

    def test_prop_binders_are_reported_as_premises_not_data(self):
        # hSA/hLR/hXC -- indices 5/6/7, after siteCount/edges/locality/op/xc
        # (see comment above).
        result = _resolve([_OPERATOR, _XC])
        premise_indices = {entry["index"] for entry in result["premises"]}
        self.assertEqual(premise_indices, {5, 6, 7})

    def test_all_data_binders_are_explicit_and_carry_no_dependencies(self):
        """The real DFT entrypoints have no implicit/instance binders --
        every data binder should be reported `explicit` with an empty
        dependency list (spec issues 6/8)."""
        result = _resolve([_OPERATOR, _XC])
        for entry in result["data_binders"]:
            self.assertEqual(entry["binder_info"], "explicit")
            self.assertEqual(entry["dependency_indices"], [])

    def test_distinct_candidate_keys_required(self):
        with self.assertRaises(ManifestError):
            _resolve([_XC, FormalBindingCandidate(
                key="xc_form", lean_expr="Testv2.StructuralV2.XCForm.smooth",
                provenance="artifact_grounded", evidence_refs=(), display_label="dup",
            )])


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ImplicitAndInstanceBinderTests(unittest.TestCase):
    """Issue 6: implicit/instance-implicit binders are not treated as
    artifact-data slots the way explicit binders are."""

    def _resolve_fixture(self, candidates):
        return resolve_entrypoint(
            project_root=PROJECT, imports=["Testv2.InspectionFixtures"],
            entrypoint="Testv2.InspectionFixtures.implicitBinderExample",
            candidates=candidates, trusted_local=True, timeout_s=120,
        )

    def test_instance_implicit_binder_is_synthesized_not_offered_a_candidate(self):
        result = self._resolve_fixture([])
        by_index = {e["index"]: e for e in result["data_binders"]}
        self.assertEqual(by_index[1]["binder_info"], "instanceImplicit")
        self.assertEqual(by_index[1]["status"], "resolved")
        self.assertEqual(by_index[1]["resolution"], "instance_synthesized")
        self.assertNotIn("chosen_candidate_key", by_index[1])

    def test_implicit_binder_resolves_transitively_never_via_direct_candidate(self):
        site = FormalBindingCandidate(
            key="site", lean_expr="(2 : Fin 3)", provenance="artifact_grounded",
            evidence_refs=("a",), display_label="site = 2 : Fin 3",
        )
        result = self._resolve_fixture([site])
        by_index = {e["index"]: e for e in result["data_binders"]}
        self.assertEqual(by_index[0]["binder_info"], "implicit")
        self.assertEqual(by_index[0]["status"], "resolved")
        self.assertNotIn("chosen_candidate_key", by_index[0])
        self.assertEqual(by_index[2]["dependency_indices"], [0])

    def test_implicit_binder_with_no_dependent_candidate_stays_unresolved(self):
        """No candidate for `site` at all -> nothing ever unifies `n`;
        both must come back genuinely unresolved, never guessed."""
        result = self._resolve_fixture([])
        by_index = {e["index"]: e for e in result["data_binders"]}
        self.assertEqual(by_index[0]["status"], "unresolved")
        self.assertEqual(by_index[2]["status"], "unresolved")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class DependencyEdgeTests(unittest.TestCase):
    """Issue 8: a premise's recorded dependency must come from Lean's own
    expression structure, never a `pretty_type == "Prop"` guess -- `(P Q :
    Prop) (hP : P)` is exactly the case that guess gets wrong."""

    def test_premise_depends_on_its_own_prop_parameter_only(self):
        result = resolve_entrypoint(
            project_root=PROJECT, imports=["Testv2.InspectionFixtures"],
            entrypoint="Testv2.InspectionFixtures.twoIndependentPropParameters",
            candidates=[], trusted_local=True, timeout_s=120,
        )
        premise = result["premises"][0]
        self.assertEqual(premise["dependency_indices"], [0])  # P, never Q (index 1)


if __name__ == "__main__":
    unittest.main()
