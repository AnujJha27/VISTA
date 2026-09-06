"""Regression tests for the validated `resume_session` (spec/theorem-
centric-gaps issue D): a bare resume is a plain read-only load, but passing
`package`/`project`/`artifact`/`extraction_result` must independently catch
each freshness dimension drifting -- package content, Lean project/theory,
adapter implementation, artifact binding -- marking the returned in-memory
session `stale` without ever rewriting the file on disk.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import api
from dftcert.verification.package import VerificationPackageBuilder

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _constraints, _inventory

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"


def _write_extraction_result(path: Path, *, artifact_sha256: str = "deadbeef") -> None:
    path.write_text(json.dumps({
        "inventory": _inventory(adjacency=_CHAIN3, stages=0, symmetrized=True),
        "artifact_sha256": artifact_sha256, "extractor_version": "t",
    }), encoding="utf-8")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ResumeFreshnessTests(unittest.TestCase):
    def _fresh_session(self, tmp):
        extraction_path = Path(tmp) / "extraction.json"
        _write_extraction_result(extraction_path)
        package_path = Path(tmp) / "package.json"
        VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(),
            binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
        ).write(package_path)
        session_path = Path(tmp) / "session.json"
        api.start_session(
            extraction_result=str(extraction_path), package=str(package_path),
            session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
        )
        return extraction_path, package_path, session_path

    def test_bare_resume_is_a_plain_load_never_stale(self):
        with TemporaryDirectory() as tmp:
            _, _, session_path = self._fresh_session(tmp)
            resumed = api.resume_session(str(session_path))
            self.assertEqual(resumed.status, "ready_for_certificate")
            self.assertNotIn("stale_reasons", resumed.value)

    def test_resume_accepts_a_genuinely_unchanged_package_and_project(self):
        with TemporaryDirectory() as tmp:
            _, package_path, session_path = self._fresh_session(tmp)
            resumed = api.resume_session(str(session_path), package=str(package_path), project=str(PROJECT))
            self.assertEqual(resumed.status, "ready_for_certificate")
            self.assertNotIn("stale_reasons", resumed.value)

    def test_resume_rejects_changed_package(self):
        with TemporaryDirectory() as tmp:
            _, _, session_path = self._fresh_session(tmp)
            other_package_path = Path(tmp) / "other-package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
                # deliberately no binding_choices -- a different package body,
                # so its sha256 cannot match the one this session was built from.
            ).write(other_package_path)
            resumed = api.resume_session(str(session_path), package=str(other_package_path))
            self.assertEqual(resumed.status, "stale")
            self.assertTrue(any("package hash" in reason for reason in resumed.value["stale_reasons"]))
            # the on-disk session file itself must be untouched -- a stale
            # verdict is never silently persisted over a prior decision.
            self.assertEqual(json.loads(session_path.read_text())["status"], "ready_for_certificate")

    def test_resume_rejects_changed_lean_project(self):
        with TemporaryDirectory() as tmp:
            _, package_path, session_path = self._fresh_session(tmp)
            drifted_project = Path(tmp) / "drifted_project"
            drifted_project.mkdir()
            (drifted_project / "lean-toolchain").write_text(
                "leanprover/lean4:v0.0.0-drifted\n", encoding="utf-8",
            )
            resumed = api.resume_session(
                str(session_path), package=str(package_path), project=str(drifted_project),
            )
            self.assertEqual(resumed.status, "stale")
            self.assertTrue(any(
                "project" in reason.lower() or "toolchain" in reason.lower()
                for reason in resumed.value["stale_reasons"]
            ))
            self.assertEqual(json.loads(session_path.read_text())["status"], "ready_for_certificate")

    def test_resume_rejects_changed_adapter_identity(self):
        with TemporaryDirectory() as tmp:
            _, package_path, session_path = self._fresh_session(tmp)
            value = json.loads(session_path.read_text())
            # Simulate the adapter's executing implementation having
            # changed since this session was built -- the session's
            # recorded binding no longer matches DFT_CAPABILITY_PLUGIN's
            # live `semantic_identity`.
            value["adapter_binding"] = {
                **value["adapter_binding"], "implementation_sha256": "0" * 64,
            }
            session_path.write_text(json.dumps(value), encoding="utf-8")
            resumed = api.resume_session(str(session_path), package=str(package_path))
            self.assertEqual(resumed.status, "stale")
            self.assertTrue(any("adapter identity" in reason for reason in resumed.value["stale_reasons"]))

    def test_resume_rejects_changed_artifact(self):
        with TemporaryDirectory() as tmp:
            _, _, session_path = self._fresh_session(tmp)
            drifted_extraction = Path(tmp) / "drifted-extraction.json"
            _write_extraction_result(drifted_extraction, artifact_sha256="cafebabe")
            resumed = api.resume_session(
                str(session_path), extraction_result=str(drifted_extraction), trusted_local=True,
            )
            self.assertEqual(resumed.status, "stale")
            self.assertTrue(any("artifact hash" in reason for reason in resumed.value["stale_reasons"]))
            self.assertEqual(json.loads(session_path.read_text())["status"], "ready_for_certificate")


if __name__ == "__main__":
    unittest.main()
