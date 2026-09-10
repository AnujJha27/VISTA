"""VISTA's own minimal, headline demonstration (spec: "one minimal, rigorous
example that demonstrates the pipeline") -- deliberately smaller than
`tests/test_real_artifact_e2e.py`'s full DFT `AcceptableArchitecture`
requirement: the *only* formal requirement selected here is structural
self-adjointness (`Testv2.Requirements.ValidSelfAdjointConstruction`), with
no site-count/long-range/XC/message-passing premises at all. Same real
extractor logic, same `DFTCapabilityPlugin` adapter, same
`model.pt2 -> BubblewrapExtractor-shaped extraction -> structural IR ->
formal binding candidates -> theorem binder resolution -> Lean -> certificate`
pipeline as the fuller DFT example -- just a smaller selected theorem, to
show the theorem selection is genuinely independent of how much structural
data the adapter happens to derive (module docstring of `Testv2.Requirements`
and `dftcert.structural.dft_capability_plugin.DFTCapabilityPlugin.
formal_binding_candidates`, both unconditionally derive/expose an
`operator_form` candidate regardless of which entrypoint is selected -- no
adapter change was needed to support an operator-only target).

Positive artifact: `examples/dft/models/structural_gnns.CertifiedRingGNN`
(`learned_self_energy = base_operator + base_operator.T`) -- the recognized
"symmetrized" recipe, `guaranteedSelfAdjoint = true`, certifies.

Negative artifact: `examples/dft/models/structural_gnns.
UnconstrainedOperatorGNN` (`learned_self_energy = base_operator`, no
symmetrization) -- the recognized "unconstrained"/bare-parameter recipe,
`guaranteedSelfAdjoint = false`, does NOT certify. Precisely: VISTA does NOT
establish "this model is mathematically non-self-adjoint" (`base_operator`'s
actual trained values are never inspected -- pre-training scope, no
floating-point values are read at all here); it establishes only that the
selected self-adjointness requirement cannot be derived from the artifact's
*recognized structural construction* (a bare parameter, not a `symmetrized`
add/adjoint pair).

`ForgedSessionCannotCertifyTests` is the required adversarial regression for
the persisted-session trust-chain fix (`docs/verification/
TRUST_CHAIN_AUDIT.md`, "persisted-session trust gap"): starting a genuine
session from the negative (unconstrained-operator) artifact, then hand-
editing the persisted `session.json` to falsely claim the operator was the
symmetrized form and that self-adjointness was formally discharged -- while
keeping the real artifact hash and package binding untouched -- must NOT
certify, because `certify_session` now always freshly re-derives the
certification-relevant session state from the live artifact before
certifying, never trusting whatever is already on disk at `session`.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import VerificationPackageBuilder, certify_session, start_session
from extractors.torch_export_worker import extract

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
POSITIVE_ARTIFACT = FIXTURES / "certified_ring.pt2"
NEGATIVE_ARTIFACT = FIXTURES / "unconstrained_operator.pt2"
ENTRYPOINT = "Testv2.Requirements.ValidSelfAdjointConstruction"

# The minimal self-adjointness demo's interface contains no LOCALITY
# information at all -- `ValidSelfAdjointConstruction`'s two binders (`op`,
# `hSA`) never consume site-count/edges/locality_range/XC, and
# `locality_range` has a default (see `_locality_range`), so there is
# nothing to specify there. `adjacency_state_name` is still required
# (topology is always derived regardless of which entrypoint a package
# selects -- theorem-driven SELECTION is implemented, theorem-driven
# MINIMAL IR CONSTRUCTION is not, see `dftcert/verification/resolver.py`),
# and is never a name-match heuristic: which state entry is "the adjacency"
# is a specified interpretation, not something to guess at.
CONSTRAINTS = {
    "adjacency_state_name": "adjacency",
    "adjacency_convention": "target_source",
    "output_contracts": [
        {"index": 0, "role": "xc_energy"},
        {"index": 1, "role": "learned_self_energy"},
        {"index": 2, "role": "message_state"},
    ],
}


def _build_package(package_path: Path) -> None:
    VerificationPackageBuilder(
        lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
        interface_contract=CONSTRAINTS,
    ).write(package_path)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class SelfAdjointDemoTests(unittest.TestCase):
    def test_positive_symmetrized_operator_certifies(self):
        result = extract(POSITIVE_ARTIFACT)
        with TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            _build_package(package_path)
            extraction_path = Path(tmp) / "extraction.json"
            extraction_path.write_text(json.dumps(result), encoding="utf-8")
            session_path = Path(tmp) / "session.json"

            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")
            op_node = session.value["nodes"][f"{ENTRYPOINT}#0"]
            self.assertEqual(op_node["status"], "artifact_grounded")
            self.assertIn("add", op_node["lean_expr"])

            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                output_dir=str(Path(tmp) / "certificate"),
                extraction_result=str(extraction_path), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertFalse(manifest["conditional"])

    def test_negative_unconstrained_operator_does_not_certify(self):
        result = extract(NEGATIVE_ARTIFACT)
        with TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            _build_package(package_path)
            extraction_path = Path(tmp) / "extraction.json"
            extraction_path.write_text(json.dumps(result), encoding="utf-8")
            session_path = Path(tmp) / "session.json"

            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            # Blocked, not invalid: a real, resumable session that simply
            # cannot discharge hSA against this artifact's recognized
            # construction -- never "proved non-self-adjoint".
            self.assertEqual(session.status, "blocked_on_premise")
            hSA_node = session.value["nodes"][f"{ENTRYPOINT}#1"]
            self.assertEqual(hSA_node["status"], "unresolved")
            op_node = session.value["nodes"][f"{ENTRYPOINT}#0"]
            self.assertEqual(op_node["status"], "artifact_grounded")
            self.assertNotIn("add", op_node["lean_expr"])  # bare parameter, not add/adjoint

            with self.assertRaises(ManifestError):
                certify_session(
                    session=str(session_path), package=str(package_path), project=str(PROJECT),
                    output_dir=str(Path(tmp) / "certificate"),
                    extraction_result=str(extraction_path), trusted_local=True, timeout_s=180,
                )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ForgedSessionCannotCertifyTests(unittest.TestCase):
    """The required adversarial regression (spec Task 2): a persisted
    session, hand-edited to falsely claim a discharged self-adjointness
    premise against a symmetrized operator it was never actually derived
    from, while the real artifact hash/package binding are left untouched,
    must not certify."""

    def test_forged_session_with_real_artifact_hash_does_not_certify(self):
        result = extract(NEGATIVE_ARTIFACT)
        with TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            _build_package(package_path)
            extraction_path = Path(tmp) / "extraction.json"
            extraction_path.write_text(json.dumps(result), encoding="utf-8")
            session_path = Path(tmp) / "session.json"

            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "blocked_on_premise")
            genuine_artifact_sha256 = session.value["artifact_binding"]["artifact_sha256"]
            genuine_package_sha256 = session.value["formal_package_binding"]["package_sha256"]

            # Forge the persisted session.json: claim the operator was the
            # symmetrized (self-adjoint) form and that hSA was formally
            # discharged, WITHOUT touching artifact_binding/
            # formal_package_binding/ir_sha256 -- exactly the attack the
            # fix in dftcert/verification/api.py::certify_session closes.
            forged = json.loads(session_path.read_text(encoding="utf-8"))
            # Exactly the string a genuine "symmetrized, eligible" artifact
            # would produce (`dft_capability_plugin._lean_operator`) -- a
            # real, well-typed `OperatorForm` term, not a strawman.
            symmetrized_lean_expr = (
                'Testv2.StructuralV2.OperatorForm.add (.parameter "base") '
                '(.adjoint (.parameter "base"))'
            )
            forged["nodes"][f"{ENTRYPOINT}#0"]["lean_expr"] = symmetrized_lean_expr
            forged["nodes"][f"{ENTRYPOINT}#0"]["chosen_candidate_key"] = "operator_form"
            forged["nodes"][f"{ENTRYPOINT}#1"]["status"] = "formally_discharged"
            forged["nodes"][f"{ENTRYPOINT}#1"]["proof_result_ref"] = "rfl"
            forged["status"] = "ready_for_certificate"
            self.assertEqual(forged["artifact_binding"]["artifact_sha256"], genuine_artifact_sha256)
            self.assertEqual(forged["formal_package_binding"]["package_sha256"], genuine_package_sha256)
            session_path.write_text(json.dumps(forged, indent=2, sort_keys=True) + "\n", encoding="utf-8")

            # A raw, non-revalidating load of the forged file -- confirming
            # the forgery really is schema-valid and really does claim
            # ready_for_certificate, i.e. this is not a strawman the
            # existing schema validation would already reject on its own.
            from dftcert.verification.session import load_session
            reloaded = load_session(str(session_path))
            self.assertEqual(reloaded.status, "ready_for_certificate")
            self.assertIn("add", reloaded.value["nodes"][f"{ENTRYPOINT}#0"]["lean_expr"])

            # The canonical certificate-issuing path must not be fooled:
            # given the REAL artifact, it freshly re-derives the session
            # (overwriting the forged file) and refuses to certify.
            with self.assertRaises(ManifestError):
                certify_session(
                    session=str(session_path), package=str(package_path), project=str(PROJECT),
                    output_dir=str(Path(tmp) / "certificate"),
                    extraction_result=str(extraction_path), trusted_local=True, timeout_s=180,
                )

            # The forged content did not merely get ignored in memory -- it
            # was overwritten on disk with the honest, freshly-derived
            # session (spec: "persisted session may still be used for
            # user-facing interaction, display, or comparison", but only
            # ever as trusted OUTPUT of this path, never trusted input).
            after = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(after["status"], "blocked_on_premise")
            self.assertEqual(after["nodes"][f"{ENTRYPOINT}#1"]["status"], "unresolved")
            self.assertNotIn("add", after["nodes"][f"{ENTRYPOINT}#0"]["lean_expr"])


if __name__ == "__main__":
    unittest.main()
