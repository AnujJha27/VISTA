"""`vista verify start/resume/certify` (spec section 22) end to end against
a real Lean toolchain. Exercises `dftcert.verification.cli.main` directly
(the same entrypoint `dftcert.local_cli`'s `verify` subcommand forwards to)
rather than spawning a subprocess, to keep this in the same fast/skip path
as the rest of the Lean-integration suite.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.cli import main
from dftcert.verification.package import VerificationPackageBuilder

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _constraints, _inventory

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"


def _write_extraction_result(path: Path, *, symmetrized: bool = True) -> None:
    path.write_text(json.dumps({
        "inventory": _inventory(adjacency=_CHAIN3, stages=0, symmetrized=symmetrized),
        "artifact_sha256": "deadbeef", "extractor_version": "t",
    }), encoding="utf-8")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class VerifyCliEndToEndTests(unittest.TestCase):
    def test_start_resume_certify_round_trip(self):
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"

            start_rc = main([
                "start", "--extraction-result", str(extraction_path), "--package", str(package_path),
                "--session", str(session_path), "--project", str(PROJECT),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(start_rc, 0)
            self.assertEqual(json.loads(session_path.read_text())["status"], "ready_for_certificate")

            resume_rc = main(["resume", "--session", str(session_path)])
            self.assertEqual(resume_rc, 0)

            output_dir = Path(tmp) / "certificate"
            certify_rc = main([
                "certify", "--session", str(session_path), "--package", str(package_path),
                "--project", str(PROJECT), "--entrypoint", ENTRYPOINT,
                "--output-dir", str(output_dir),
                "--extraction-result", str(extraction_path),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(certify_rc, 0)
            manifest = json.loads((output_dir / "manifest.json").read_text())
            self.assertEqual(manifest["status"], "certified")
            self.assertFalse(manifest["conditional"])
            self.assertEqual(manifest["targets"], [ENTRYPOINT])
            self.assertTrue((output_dir / f"{ENTRYPOINT.replace('.', '_')}.lean").exists())
            self.assertTrue((output_dir / f"{ENTRYPOINT.replace('.', '_')}-report.json").exists())

    def test_certify_refuses_a_blocked_session(self):
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path, symmetrized=False)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            main([
                "start", "--extraction-result", str(extraction_path), "--package", str(package_path),
                "--session", str(session_path), "--project", str(PROJECT),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(json.loads(session_path.read_text())["status"], "blocked_on_premise")
            rc = main([
                "certify", "--session", str(session_path), "--package", str(package_path),
                "--project", str(PROJECT), "--entrypoint", ENTRYPOINT,
                "--output-dir", str(Path(tmp) / "certificate"),
                "--extraction-result", str(extraction_path),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertNotEqual(rc, 0)

    def test_extraction_result_requires_trusted_local(self):
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
            ).write(package_path)
            rc = main([
                "start", "--extraction-result", str(extraction_path), "--package", str(package_path),
                "--session", str(Path(tmp) / "session.json"), "--project", str(PROJECT),
                "--timeout-s", "180",
            ])
            self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
