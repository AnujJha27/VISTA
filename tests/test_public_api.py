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

from dftcert.manifest import ManifestError
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification import VerificationPackageBuilder, certify_session, resume_session, start_session
from dftcert.verification import api
from dftcert.verification.cli import main as cli_main
from dftcert.verification.package import add_external_assumption
from dftcert.verification.session import start_session as _low_level_start_session

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


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class WorkspaceRefreshTests(unittest.TestCase):
    """Issue F: `api.start_session` writes a workspace descriptor next to
    the session so a later `api.refresh_session` can re-invoke the exact
    same trusted backend after a package decision changes -- without the
    caller (the TUI, in practice) ever re-deriving inputs or duplicating
    resolver logic itself."""

    def test_start_session_writes_a_workspace_descriptor(self):
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            descriptor_path = Path(tmp) / "session.workspace.json"
            self.assertTrue(descriptor_path.exists())
            descriptor = json.loads(descriptor_path.read_text())
            self.assertEqual(descriptor["package"], str(package_path.resolve()))
            self.assertEqual(descriptor["trusted_local"], True)

    def test_refresh_session_re_runs_with_a_persisted_package_decision(self):
        """CONDITIONAL_ENTRYPOINT's own siteCount binder resolves unaided
        in this codebase (no `binding_choices` needed) -- its hPhysical
        premise is the genuinely blocking node, needing an explicit
        assumption. Exercises `api.refresh_session` (issue F) re-invoking
        the trusted backend after `add_external_assumption` (issue E)
        persists a package decision -- the same integration the TUI relies
        on, without duplicating resolver logic here."""
        conditional_entrypoint = "Testv2.Requirements.ValidPretrainingArchitectureConditional"
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[conditional_entrypoint], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "blocked_on_premise")
            premise = session.unresolved_premises[0]

            add_external_assumption(
                package_path, premise_id=premise["id"],
                proposition_fingerprint=premise["type_fingerprint"], rationale="physical target requires non-locality",
            )
            refreshed = api.refresh_session(str(session_path))
            self.assertEqual(refreshed.status, "ready_for_certificate")
            self.assertEqual(refreshed.value["nodes"][premise["id"]]["status"], "specified_assumption")

    def test_refresh_session_without_a_descriptor_raises(self):
        """A session built via the low-level `dftcert.verification.session.
        start_session` (bypassing `api.start_session`) has no workspace
        descriptor -- refresh must fail closed, never guess inputs."""
        with TemporaryDirectory() as tmp:
            package = VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).as_dict()
            session_path = Path(tmp) / "session.json"
            _low_level_start_session(
                artifact_sha256="deadbeef", inventory=_inventory(adjacency=_CHAIN3, stages=0, symmetrized=True),
                extractor_version="t", package=package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=session_path, trusted_local=True, timeout_s=180,
            )
            with self.assertRaises(ManifestError):
                api.refresh_session(str(session_path))


CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class MultiTargetCertificationTests(unittest.TestCase):
    """Issue 11: a package selecting multiple entrypoints produces one
    aggregate certificate bundle; any unresolved target blocks it."""

    def _package(self, tmp, **overrides):
        extraction_path = Path(tmp) / "extraction.json"
        _write_extraction_result(extraction_path)
        package_path = Path(tmp) / "package.json"
        kwargs = dict(
            lean_project=PROJECT, entrypoints=[ENTRYPOINT, CONDITIONAL_ENTRYPOINT],
            adapter=DFT_CAPABILITY_PLUGIN, interface_contract=_constraints(),
            binding_choices=[
                {"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"},
                {"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"},
            ],
        )
        kwargs.update(overrides)
        VerificationPackageBuilder(**kwargs).write(package_path)
        return extraction_path, package_path

    def test_two_entrypoint_package_produces_an_aggregate_bundle(self):
        with TemporaryDirectory() as tmp:
            extraction_path, package_path = self._package(tmp)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            for premise in session.unresolved_premises:
                session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            self.assertEqual(session.status, "ready_for_certificate")

            output_dir = Path(tmp) / "certificate"
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                lean_import="Testv2.Requirements", output_dir=str(output_dir),
                trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertEqual(manifest["certificate_scope"], "full_package")
            self.assertEqual(set(manifest["package_entrypoints"]), {ENTRYPOINT, CONDITIONAL_ENTRYPOINT})
            self.assertEqual(set(manifest["targets"]), {ENTRYPOINT, CONDITIONAL_ENTRYPOINT})
            self.assertTrue(manifest["conditional"])  # the conditional entrypoint needed an assumption
            for entrypoint in (ENTRYPOINT, CONDITIONAL_ENTRYPOINT):
                safe = entrypoint.replace(".", "_")
                self.assertTrue((output_dir / f"{safe}.lean").exists())
                self.assertTrue((output_dir / f"{safe}-report.json").exists())

    def test_subset_certification_is_refused_without_explicit_opt_in(self):
        """Issue G: passing only some of the package's selected entrypoints
        must never silently produce a bundle that could be mistaken for a
        complete package certificate."""
        with TemporaryDirectory() as tmp:
            extraction_path, package_path = self._package(tmp)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            for premise in session.unresolved_premises:
                session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            with self.assertRaises(Exception):
                certify_session(
                    session=str(session_path), package=str(package_path), project=str(PROJECT),
                    lean_import="Testv2.Requirements", output_dir=str(Path(tmp) / "certificate"),
                    entrypoints=[ENTRYPOINT], trusted_local=True, timeout_s=180,
                )

    def test_subset_certification_with_explicit_opt_in_is_marked_non_complete(self):
        with TemporaryDirectory() as tmp:
            extraction_path, package_path = self._package(tmp)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            for premise in session.unresolved_premises:
                session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                lean_import="Testv2.Requirements", output_dir=str(Path(tmp) / "certificate"),
                entrypoints=[ENTRYPOINT], allow_subset_certificate=True, trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["certificate_scope"], "selected_subset")
            self.assertEqual(manifest["targets"], [ENTRYPOINT])
            self.assertEqual(set(manifest["package_entrypoints"]), {ENTRYPOINT, CONDITIONAL_ENTRYPOINT})

    def test_one_unresolved_target_blocks_the_aggregate_certificate(self):
        with TemporaryDirectory() as tmp:
            extraction_path, package_path = self._package(
                tmp, binding_choices=[
                    {"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"},
                    # deliberately no binding_choice for CONDITIONAL_ENTRYPOINT's siteCount:
                    # it stays ambiguous_binding.
                ],
            )
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "blocked_on_premise")
            with self.assertRaises(Exception):
                certify_session(
                    session=str(session_path), package=str(package_path), project=str(PROJECT),
                    lean_import="Testv2.Requirements", output_dir=str(Path(tmp) / "certificate"),
                    trusted_local=True, timeout_s=180,
                )


if __name__ == "__main__":
    unittest.main()
