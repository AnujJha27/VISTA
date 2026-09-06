"""`dftcert.verification.bindings.resolve_data_binders` against a real Lean
toolchain (spec section 27.3): never pick among multiple typechecking
candidates, never accept a wrong-typed one.
"""
import unittest
from pathlib import Path

from dftcert.manifest import ManifestError
from dftcert.verification.bindings import resolve_data_binders
from dftcert.verification.model import FormalBindingCandidate

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
    return resolve_data_binders(
        project_root=PROJECT, imports=["Testv2.Requirements"], entrypoint=ENTRYPOINT,
        candidates=candidates, trusted_local=True, timeout_s=180, **kwargs,
    )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class BindingResolutionTests(unittest.TestCase):
    def test_exactly_one_typechecking_candidate_resolves_automatically(self):
        result = _resolve([_OPERATOR, _XC])
        by_index = {entry["index"]: entry for entry in result}
        self.assertEqual(by_index[1]["status"], "resolved")
        self.assertEqual(by_index[1]["chosen_candidate_key"], "operator_form")
        self.assertEqual(by_index[2]["status"], "resolved")
        self.assertEqual(by_index[2]["chosen_candidate_key"], "xc_form")

    def test_zero_candidates_is_unresolved(self):
        result = _resolve([_XC])
        by_index = {entry["index"]: entry for entry in result}
        self.assertEqual(by_index[0]["status"], "unresolved")
        self.assertEqual(by_index[0]["matching_candidate_keys"], [])

    def test_two_same_typed_candidates_are_ambiguous_never_first_picked(self):
        result = _resolve([_SITE_COUNT, _DEPTH, _OPERATOR, _XC])
        siteCountEntry = next(entry for entry in result if entry["index"] == 0)
        self.assertEqual(siteCountEntry["status"], "ambiguous_binding")
        self.assertEqual(set(siteCountEntry["matching_candidate_keys"]), {"site_count", "operator_message_depth"})
        self.assertNotIn("chosen_candidate_key", siteCountEntry)

    def test_explicit_user_choice_resolves_the_ambiguity(self):
        result = _resolve([_SITE_COUNT, _DEPTH, _OPERATOR, _XC], forced_choices={0: "site_count"})
        siteCountEntry = next(entry for entry in result if entry["index"] == 0)
        self.assertEqual(siteCountEntry["status"], "resolved")
        self.assertEqual(siteCountEntry["chosen_candidate_key"], "site_count")

    def test_wrong_typed_candidate_is_rejected_by_lean_not_python(self):
        """`operator_form`'s Lean expression (an `OperatorForm`) must never
        match `siteCount`'s `Nat` binder -- Lean's own elaborator rejects
        it; nothing in `resolve_data_binders` special-cases these types."""
        result = _resolve([_OPERATOR])
        siteCountEntry = next(entry for entry in result if entry["index"] == 0)
        self.assertEqual(siteCountEntry["status"], "unresolved")

    def test_prop_binders_are_reported_as_premises_not_data(self):
        result = _resolve([_OPERATOR, _XC])
        premise_indices = {entry["index"] for entry in result if entry["kind"] == "premise"}
        self.assertEqual(premise_indices, {3, 4, 5})

    def test_distinct_candidate_keys_required(self):
        with self.assertRaises(ManifestError):
            _resolve([_XC, FormalBindingCandidate(
                key="xc_form", lean_expr="Testv2.StructuralV2.XCForm.smooth",
                provenance="artifact_grounded", evidence_refs=(), display_label="dup",
            )])


if __name__ == "__main__":
    unittest.main()
