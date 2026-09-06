"""Issue 15: one real end-to-end trust-chain test against a genuine,
committed `.pt2` artifact (`tests/fixtures/certified_ring.pt2`, exported
from `examples/dft/models/structural_gnns.CertifiedRingGNN` -- a 6-site
ring, symmetrized self-energy operator, hinge XC) -- not a synthetic
`artifact_sha256 = "deadbeef"` fixture like the rest of this suite.

`RealArtifactEndToEndTests` exercises the full pipeline through the real
extractor logic directly (`extractors.torch_export_worker.extract`,
`trusted_local=True`) -- real artifact hash -> package-bound semantic
lowering -> independent revalidation -> formal binding candidates -> Lean
theorem inspection -> binder resolution -> premise discharge ->
certificate generation -> Lean kernel check -> hash-bound certificate
bundle -- but does NOT exercise the Bubblewrap sandbox path (spec/
theorem-centric-gaps issue H: this validates real extraction *logic*,
never call it "safe extraction" on its own). Also includes a tampering
test: editing a semantic fact after extraction (keeping the artifact
hash) must not certify.

`BubblewrapSandboxEndToEndTests` is the actual "safe extraction" case:
`model.pt2 -> BubblewrapExtractor -> theorem pipeline -> certificate`,
skipped explicitly (never faked) when `bwrap` is unavailable or the
sandboxed interpreter can't import torch.
"""
import json
import shutil
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import VerificationPackageBuilder, certify_session, start_session
from extractors.torch_export_worker import extract

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

_SANDBOX_PYTHON = "/usr/bin/python3"


def _bubblewrap_skip_reason() -> str | None:
    if shutil.which("bwrap") is None:
        return "bwrap is not installed in this environment"
    probe = subprocess.run(
        [_SANDBOX_PYTHON, "-c", "import torch"], capture_output=True, timeout=30,
    )
    if probe.returncode != 0:
        return f"{_SANDBOX_PYTHON} (the sandboxed interpreter) cannot import torch"
    return None


_BUBBLEWRAP_SKIP_REASON = _bubblewrap_skip_reason()

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

            report = json.loads((output_dir / f"{ENTRYPOINT.replace('.', '_')}-report.json").read_text(encoding="utf-8"))
            self.assertTrue(report["used_facts"])
            self.assertTrue(all(
                axiom in {"propext", "Classical.choice", "Quot.sound"}
                for axiom in report["certificate_axiom_closure"]
            ))
            source = (output_dir / f"{ENTRYPOINT.replace('.', '_')}.lean").read_text(encoding="utf-8")
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


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
@unittest.skipIf(_BUBBLEWRAP_SKIP_REASON, _BUBBLEWRAP_SKIP_REASON)
class BubblewrapSandboxEndToEndTests(unittest.TestCase):
    """Issue H: the actual safe-extraction path -- `model.pt2 ->
    BubblewrapExtractor -> theorem pipeline -> certificate` -- as opposed
    to `RealArtifactEndToEndTests`, which calls the extractor logic
    directly and never exercises the sandbox at all."""

    def test_full_trust_chain_certifies_the_real_artifact_via_the_sandbox(self):
        # Deferred import: `dftcert.sandbox` unconditionally imports the
        # POSIX-only `resource` module -- only this (skipped-on-Windows)
        # test needs it, and a module-level import would break test
        # collection entirely under the Windows python.exe this project
        # otherwise runs its tests under.
        from dftcert.sandbox import BubblewrapExtractor
        result = BubblewrapExtractor(python=_SANDBOX_PYTHON).extract(ARTIFACT)
        with TemporaryDirectory() as tmp:
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=CONSTRAINTS,
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"

            session = start_session(
                artifact=str(ARTIFACT), package=str(package_path),
                session=str(session_path), project=str(PROJECT), timeout_s=180,
            )
            self.assertEqual(session.value["artifact_binding"]["artifact_sha256"], result["artifact_sha256"])
            self.assertEqual(session.status, "ready_for_certificate")

            output_dir = Path(tmp) / "certificate"
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                lean_import="Testv2.Requirements", output_dir=str(output_dir), timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertEqual(manifest["artifact_binding"]["artifact_sha256"], result["artifact_sha256"])
            source = (output_dir / f"{ENTRYPOINT.replace('.', '_')}.lean").read_text(encoding="utf-8")
            self.assertNotRegex(source, r"\b(sorry|admit|axiom|unsafe)\b")


if __name__ == "__main__":
    unittest.main()
