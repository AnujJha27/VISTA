"""`dftcert.verification`'s public API (spec/theorem-centric-gaps issue
14): `start_session`/`certify_session` take high-level paths (artifact/
extraction result, package, session, project) -- never a caller-supplied
artifact hash, IR, or adapter object -- and run the exact same trusted
implementation `vista verify`'s CLI does.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import VerificationPackageBuilder, certify_session, resume_session, start_session
from dftcert.verification.cli import main as cli_main

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _constraints, _inventory

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"


def _write_extraction_result(path: Path) -> None:
    path.write_text(json.dumps({
        "inventory": _inventory(adjacency=_CHAIN3, stages=0, symmetrized=True),
        "artifact_sha256": "deadbeef", "extractor_version": "t",
    }), encoding="utf-8")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class PublicApiTests(unittest.TestCase):
    def test_start_certify_round_trip_via_public_api_only(self):
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

            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT),
                trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")

            resumed = resume_session(str(session_path))
            self.assertEqual(resumed.status, "ready_for_certificate")

            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                lean_import="Testv2.Requirements", output_dir=str(Path(tmp) / "certificate"),
                trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")

    def test_public_api_and_cli_produce_the_same_session_status(self):
        """CLI and Python API must call the same underlying trusted
        implementation -- not two independent copies that could drift."""
        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            extraction_path = Path(tmp_a) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp_a) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
            ).write(package_path)

            api_session_path = Path(tmp_a) / "session.json"
            start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(api_session_path), project=str(PROJECT),
                trusted_local=True, timeout_s=180,
            )

            cli_session_path = Path(tmp_b) / "session.json"
            rc = cli_main([
                "start", "--extraction-result", str(extraction_path), "--package", str(package_path),
                "--session", str(cli_session_path), "--project", str(PROJECT),
                "--trusted-local", "--timeout-s", "180",
            ])
            self.assertEqual(rc, 0)

            api_value = json.loads(api_session_path.read_text())
            cli_value = json.loads(cli_session_path.read_text())
            self.assertEqual(api_value["nodes"], cli_value["nodes"])
            self.assertEqual(api_value["status"], cli_value["status"])


if __name__ == "__main__":
    unittest.main()
