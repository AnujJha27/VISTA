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

from dftcert.verification.cli import main
from dftcert.verification.package import VerificationPackageBuilder

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _ir

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class VerifyCliEndToEndTests(unittest.TestCase):
    def test_start_resume_certify_round_trip(self):
        with TemporaryDirectory() as tmp:
            ir_path = Path(tmp) / "ir.json"
            ir_path.write_text(json.dumps(_ir(adjacency=_CHAIN3, stages=0, symmetrized=True)), encoding="utf-8")
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter_profile="dft-capability",
                interface_contract={},
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"

            start_rc = main([
                "start", "--ir", str(ir_path), "--package", str(package_path),
                "--session", str(session_path), "--project", str(PROJECT),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(start_rc, 0)
            self.assertEqual(json.loads(session_path.read_text())["status"], "ready_for_certificate")

            resume_rc = main(["resume", "--session", str(session_path)])
            self.assertEqual(resume_rc, 0)

            source_path = Path(tmp) / "Cert.lean"
            report_path = Path(tmp) / "report.json"
            certify_rc = main([
                "certify", "--session", str(session_path), "--package", str(package_path),
                "--project", str(PROJECT), "--entrypoint", ENTRYPOINT,
                "--lean-import", "Testv2.Requirements", "--source-output", str(source_path),
                "--report-output", str(report_path), "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(certify_rc, 0)
            report = json.loads(report_path.read_text())
            self.assertEqual(report["status"], "certified")
            self.assertFalse(report["conditional"])

    def test_certify_refuses_a_blocked_session(self):
        with TemporaryDirectory() as tmp:
            ir_path = Path(tmp) / "ir.json"
            ir_path.write_text(json.dumps(_ir(adjacency=_CHAIN3, stages=0, symmetrized=True)), encoding="utf-8")
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter_profile="dft-capability",
                interface_contract={},
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            main([
                "start", "--ir", str(ir_path), "--package", str(package_path),
                "--session", str(session_path), "--project", str(PROJECT),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(json.loads(session_path.read_text())["status"], "blocked_on_premise")
            rc = main([
                "certify", "--session", str(session_path), "--package", str(package_path),
                "--project", str(PROJECT), "--entrypoint", ENTRYPOINT,
                "--lean-import", "Testv2.Requirements",
                "--source-output", str(Path(tmp) / "Cert2.lean"),
                "--report-output", str(Path(tmp) / "report2.json"),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertNotEqual(rc, 0)


if __name__ == "__main__":
    unittest.main()
