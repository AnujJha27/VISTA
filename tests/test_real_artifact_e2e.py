"""Issue 15: one real end-to-end trust-chain test against a genuine,
committed `.pt2` artifact (`tests/fixtures/certified_ring.pt2`, exported
from `examples/dft/models/structural_gnns.CertifiedRingGNN` -- a 6-site
ring, symmetrized self-energy operator, hinge XC) -- not a synthetic
`artifact_sha256 = "deadbeef"` fixture like the rest of this suite.

Exercises the full pipeline: real safe extraction -> real artifact hash ->
package-bound semantic lowering -> independent revalidation -> formal
binding candidates -> Lean theorem inspection -> binder resolution ->
premise discharge -> certificate generation -> Lean kernel check ->
hash-bound certificate bundle. Also includes a tampering test: editing a
semantic fact after extraction (keeping the artifact hash) must not
certify.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import VerificationPackageBuilder, certify_session, start_session
from extractors.torch_export_worker import extract

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ARTIFACT = Path(__file__).resolve().parent / "fixtures" / "certified_ring.pt2"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"
CONSTRAINTS = {
    "adjacency_convention": "target_source",
    "output_contracts": [
        {"index": 0, "role": "xc_energy"},
        {"index": 1, "role": "learned_self_energy"},
        {"index": 2, "role": "message_state"},
    ],
}


def _extract():
    return extract(ARTIFACT)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class RealArtifactEndToEndTests(unittest.TestCase):
    def test_full_trust_chain_certifies_the_real_artifact(self):
        result = _extract()
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            extraction_path.write_text(json.dumps(result), encoding="utf-8")
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=CONSTRAINTS,
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"

            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            # The real artifact hash, not a placeholder.
            self.assertEqual(session.value["artifact_binding"]["artifact_sha256"], result["artifact_sha256"])
            self.assertEqual(len(result["artifact_sha256"]), 64)
            self.assertEqual(session.status, "ready_for_certificate")

            output_dir = Path(tmp) / "certificate"
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                lean_import="Testv2.Requirements", output_dir=str(output_dir),
                trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertFalse(manifest["conditional"])
            self.assertEqual(manifest["artifact_binding"]["artifact_sha256"], result["artifact_sha256"])
            self.assertTrue(manifest["formal_package_binding"]["package_sha256"])
            self.assertEqual(manifest["adapter_binding"], DFT_CAPABILITY_PLUGIN.semantic_identity)

            report = json.loads((output_dir / f"{ENTRYPOINT.replace('.', '_')}-report.json").read_text())
            self.assertTrue(report["used_facts"])
            self.assertTrue(all(axiom in {"propext", "Classical.choice", "Quot.sound"} for axiom in report["axiom_closure"]))
            source = (output_dir / f"{ENTRYPOINT.replace('.', '_')}.lean").read_text()
            self.assertNotRegex(source, r"\b(sorry|admit|axiom|unsafe)\b")

    def test_tampered_semantic_fact_after_extraction_cannot_certify(self):
        """Edit a semantic fact (xc form) in an otherwise-genuine IR built
        from the real artifact, keeping the artifact hash untouched --
        must be rejected by the harness's own independent revalidation."""
        result = _extract()
        genuine = structural_ir_from_inventory(
            inventory=result["inventory"], artifact_sha256=result["artifact_sha256"],
            extractor_version=result["extractor_version"], input_constraints=CONSTRAINTS,
            plugin=DFT_CAPABILITY_PLUGIN,
        )
        tampered = json.loads(json.dumps(genuine))
        tampered["xc"]["form"] = "smooth"  # real fact is "hinge"
        self.assertNotEqual(tampered, genuine)
        with self.assertRaises(ManifestError):
            from dftcert.structural.core import validate_translation
            validate_translation(
                inventory=result["inventory"], value=tampered, input_constraints=CONSTRAINTS,
                artifact_sha256=result["artifact_sha256"], plugin=DFT_CAPABILITY_PLUGIN,
            )

    def test_tampered_artifact_bytes_change_the_hash(self):
        """A single flipped byte in the real .pt2 file changes the hash
        start_session binds -- confirming the hash is a real function of
        the artifact's own bytes, not a label."""
        original = ARTIFACT.read_bytes()
        mutated = bytearray(original)
        mutated[-1] ^= 0xFF
        with TemporaryDirectory() as tmp:
            mutated_path = Path(tmp) / "mutated.pt2"
            mutated_path.write_bytes(bytes(mutated))
            from dftcert.manifest import sha256_file
            self.assertNotEqual(sha256_file(mutated_path), sha256_file(ARTIFACT))


if __name__ == "__main__":
    unittest.main()
