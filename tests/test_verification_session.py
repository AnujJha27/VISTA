"""`dftcert.verification.session` against a real Lean toolchain and the
real DFT adapter (spec section 14/16/27.5): a blocked session is valid and
resumable, resume is idempotent while fingerprints match, a changed
fingerprint goes stale rather than silently reusing old decisions, and
`accept_assumption` is the only way an unresolved premise becomes
certifiable.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.package import VerificationPackageBuilder
from dftcert.verification.session import resume_session, start_session

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _ir

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
PLAIN_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"
CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"


def _package(entrypoint, **overrides):
    kwargs = dict(
        lean_project=PROJECT, entrypoints=[entrypoint], adapter_profile="dft-capability",
        interface_contract={},
    )
    kwargs.update(overrides)
    return VerificationPackageBuilder(**kwargs).as_dict()


def _value():
    return _ir(adjacency=_CHAIN3, stages=0, symmetrized=True)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class SessionBlockedAndResumeTests(unittest.TestCase):
    def test_blocked_session_is_valid_and_resumable_not_failed(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            session = start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=_package(PLAIN_ENTRYPOINT), adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "blocked_on_premise")
            self.assertTrue(out.exists())
            reloaded = resume_session(out)
            self.assertEqual(reloaded.status, "blocked_on_premise")
            self.assertEqual(reloaded.value["nodes"], session.value["nodes"])

    def test_unchanged_inputs_resume_with_decisions_intact(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            package = _package(
                CONDITIONAL_ENTRYPOINT,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            session = start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            for premise in session.unresolved_premises:
                session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            self.assertEqual(session.status, "ready_for_certificate")
            again = start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            self.assertEqual(again.status, "ready_for_certificate")
            self.assertEqual(again.value["decisions"], session.value["decisions"])

    def test_changed_package_hash_goes_stale_and_preserves_old_session(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=_package(PLAIN_ENTRYPOINT), adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            original = json.loads(out.read_text(encoding="utf-8"))
            changed_package = _package(PLAIN_ENTRYPOINT, interface_contract={"note": "different"})
            start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=changed_package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            new_value = json.loads(out.read_text(encoding="utf-8"))
            self.assertNotEqual(new_value["formal_package_binding"], original["formal_package_binding"])
            stale_files = list(Path(tmp).glob("session.stale-*.json"))
            self.assertEqual(len(stale_files), 1)
            self.assertEqual(json.loads(stale_files[0].read_text(encoding="utf-8")), original)

    def test_changed_artifact_hash_goes_stale(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=_package(PLAIN_ENTRYPOINT), adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            start_session(
                artifact_sha256="a2-different", artifact_ir=_value(), ir_sha256="ir1",
                package=_package(PLAIN_ENTRYPOINT), adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            self.assertEqual(len(list(Path(tmp).glob("session.stale-*.json"))), 1)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class AssumptionMechanicsTests(unittest.TestCase):
    def test_accept_assumption_requires_a_premise_node(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            session = start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=_package(PLAIN_ENTRYPOINT), adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            data_node_id = next(
                nid for nid, node in session.value["nodes"].items() if node["kind"] == "data"
            )
            with self.assertRaises(ManifestError):
                session.accept_assumption(premise_id=data_node_id, rationale="nope")

    def test_accept_assumption_is_saved_immediately(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            package = _package(
                CONDITIONAL_ENTRYPOINT,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            session = start_session(
                artifact_sha256="a1", artifact_ir=_value(), ir_sha256="ir1",
                package=package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            premise = session.unresolved_premises[0]
            session.accept_assumption(premise_id=premise["id"], rationale="domain expert says so")
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["nodes"][premise["id"]]["status"], "specified_assumption")


if __name__ == "__main__":
    unittest.main()
