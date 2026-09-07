"""`dftcert.verification`'s public API (spec/theorem-centric-gaps issue
14): `start_session`/`certify_session` take high-level paths (artifact/
extraction result, package, session, project) -- never a caller-supplied
artifact hash, IR, or adapter object -- and run the exact same trusted
implementation `vista verify`'s CLI does.
"""
import json
import shutil
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


class AdapterRegistryDependencyDirectionTests(unittest.TestCase):
    """research-readiness audit issue 7: the verification harness looks up
    a domain adapter only through the generic registry owned by the
    structural/plugin boundary -- it must never import a concrete domain
    plugin module (e.g. `dft_capability_plugin`) by name itself. A source-
    text check (not just a behavioral one) guards the dependency direction
    itself, so a future edit that reintroduces a direct import is caught
    even if it happens to still resolve adapters correctly at runtime."""

    def test_api_module_never_imports_a_concrete_domain_plugin(self):
        """Checks actual `import`/`from ... import` statements only (via
        `ast`, not a raw substring search) -- a comment or docstring
        explaining the registry's own rationale may still mention the
        concrete plugin's name by way of example without violating this."""
        import ast
        import inspect
        tree = ast.parse(inspect.getsource(api))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, "dft_capability_plugin")
                self.assertFalse((node.module or "").endswith(".dft_capability_plugin"))
                self.assertNotIn("DFT_CAPABILITY_PLUGIN", [alias.name for alias in node.names])
            elif isinstance(node, ast.Import):
                self.assertFalse(any("dft_capability_plugin" in alias.name for alias in node.names))

    def test_get_adapter_resolves_the_registered_profile(self):
        from dftcert.structural.plugin import get_adapter
        self.assertIs(get_adapter(DFT_CAPABILITY_PLUGIN.name), DFT_CAPABILITY_PLUGIN)

    def test_get_adapter_returns_none_for_an_unknown_profile(self):
        from dftcert.structural.plugin import get_adapter
        self.assertIsNone(get_adapter("no-such-domain-plugin"))

    def test_resolve_adapter_fails_closed_on_an_unknown_profile(self):
        with self.assertRaises(ManifestError):
            api._resolve_adapter({"adapter": {"profile": "no-such-domain-plugin"}})


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class TrustedLocalDoesNotAuthenticateTheInventoryTests(unittest.TestCase):
    """research-readiness audit issue 6: `trusted_local=True` bypasses the
    Bubblewrap sandbox entirely -- `validate_translation` proves the IR is
    consistent with the SUPPLIED inventory, never that the inventory is
    authentic-from-real-artifact-bytes. A fully hand-fabricated, internally
    self-consistent extraction result (this test's own `artifact_sha256`
    is the literal string "deadbeef", never a real file hash) certifies
    exactly as cleanly as a genuine one -- this is the documented trust
    reduction `trusted_local=True` is an explicit opt-in to (`docs/
    TRUST_CHAIN_AUDIT.md` section 2's trusted-local row), not a bug to be
    quietly fixed later. This test exists so that boundary stays honestly
    represented: if a future change makes this test fail by starting to
    reject a fabricated trusted-local inventory, update the trust-chain
    docs to reflect the new, stronger guarantee rather than treating this
    test as simply broken."""

    def test_a_fully_fabricated_trusted_local_inventory_still_certifies(self):
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)  # artifact_sha256="deadbeef" -- fabricated, not a real hash
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
                binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                output_dir=str(Path(tmp) / "certificate"), trusted_local=True, timeout_s=180,
            )
            # Certifies cleanly -- no real .pt2 bytes were ever read for this
            # session, by design (research-readiness audit issue 6).
            self.assertEqual(manifest["status"], "certified")
            self.assertEqual(manifest["artifact_binding"]["artifact_sha256"], "deadbeef")


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
                output_dir=str(Path(tmp) / "certificate"),
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


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class CertificateBundleSelfConsistencyTests(unittest.TestCase):
    """research-readiness audit section 3: a certificate bundle's own
    recorded hashes must be independently re-derivable from the actual
    files on disk, never merely trusted because they are already present
    inside the bundle being checked."""

    def _certified_bundle(self, tmp):
        extraction_path = Path(tmp) / "extraction.json"
        _write_extraction_result(extraction_path)
        package_path = Path(tmp) / "package.json"
        VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(),
            binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
        ).write(package_path)
        session_path = Path(tmp) / "session.json"
        start_session(
            extraction_result=str(extraction_path), package=str(package_path),
            session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
        )
        output_dir = Path(tmp) / "certificate"
        certify_session(
            session=str(session_path), package=str(package_path), project=str(PROJECT),
            output_dir=str(output_dir), trusted_local=True, timeout_s=180,
        )
        return package_path, output_dir

    def test_freshly_certified_bundle_is_self_consistent(self):
        with TemporaryDirectory() as tmp:
            package_path, output_dir = self._certified_bundle(tmp)
            result = api.verify_certificate_bundle(str(output_dir), package=str(package_path), project=str(PROJECT))
            self.assertTrue(result["consistent"], result["checks"])
            self.assertTrue(all(check["ok"] for check in result["checks"].values()))

    def test_tampered_certificate_source_bytes_are_detected(self):
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            source_path = output_dir / f"{ENTRYPOINT.replace('.', '_')}.lean"
            source_path.write_text(source_path.read_text(encoding="utf-8") + "\n-- tampered\n", encoding="utf-8")
            result = api.verify_certificate_bundle(str(output_dir))
            self.assertFalse(result["consistent"])
            self.assertFalse(result["checks"][f"{ENTRYPOINT}:certificate_source_hash"]["ok"])

    def test_tampered_report_field_is_detected(self):
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            report_path = output_dir / f"{ENTRYPOINT.replace('.', '_')}-report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["conditional"] = not report["conditional"]  # flip a field, keep the old report_sha256
            report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
            result = api.verify_certificate_bundle(str(output_dir))
            self.assertFalse(result["consistent"])
            self.assertFalse(result["checks"][f"{ENTRYPOINT}:report_self_hash"]["ok"])

    def test_tampered_manifest_field_is_detected(self):
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            manifest_path = output_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["conditional"] = not manifest["conditional"]  # flip a field, keep the old manifest_sha256
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            result = api.verify_certificate_bundle(str(output_dir))
            self.assertFalse(result["consistent"])
            self.assertFalse(result["checks"]["manifest_self_hash"]["ok"])

    def test_changed_package_after_certification_is_detected(self):
        with TemporaryDirectory() as tmp:
            package_path, output_dir = self._certified_bundle(tmp)
            other_package = VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
                interface_contract=_constraints(),
                # a different package body -- its sha256 cannot match the certified binding.
            ).write(package_path)
            result = api.verify_certificate_bundle(str(output_dir), package=str(package_path))
            self.assertFalse(result["consistent"])
            self.assertFalse(result["checks"]["package_hash_matches_binding"]["ok"])

    def test_manifest_records_bundle_relative_paths(self):
        """research-readiness audit issue 8: `manifest.json` must never bake
        in an absolute path tied to the machine/directory that produced the
        bundle -- only paths relative to the bundle root itself."""
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            manifest = json.loads((output_dir / "manifest.json").read_text(encoding="utf-8"))
            for item in manifest["per_target"]:
                self.assertFalse(Path(item["source"]).is_absolute(), item["source"])
                self.assertFalse(Path(item["report"]).is_absolute(), item["report"])

    def test_moved_bundle_directory_still_verifies(self):
        """A bundle produced under one path must remain independently
        verifiable after being moved/copied to a completely different
        directory (research-readiness audit issue 8) -- proves the
        relative-path recording above is not merely cosmetic."""
        with TemporaryDirectory() as tmp:
            package_path, output_dir = self._certified_bundle(tmp)
            moved_dir = Path(tmp) / "moved" / "elsewhere" / "certificate"
            moved_dir.parent.mkdir(parents=True)
            shutil.move(str(output_dir), str(moved_dir))
            result = api.verify_certificate_bundle(str(moved_dir), package=str(package_path), project=str(PROJECT))
            self.assertTrue(result["consistent"], result["checks"])

    def test_path_traversal_in_manifest_is_rejected(self):
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            manifest_path = output_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["per_target"][0]["source"] = "../../../../../../etc/passwd"
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            with self.assertRaises(ManifestError):
                api.verify_certificate_bundle(str(output_dir))

    def test_absolute_path_in_manifest_is_rejected(self):
        with TemporaryDirectory() as tmp:
            _, output_dir = self._certified_bundle(tmp)
            manifest_path = output_dir / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["per_target"][0]["report"] = str(Path(tmp) / "outside-the-bundle-report.json")
            manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
            with self.assertRaises(ManifestError):
                api.verify_certificate_bundle(str(output_dir))

    def test_full_reverification_requires_package_and_project(self):
        """research-readiness audit issue 9: `full=True` is meaningless
        without a live Lean project to actually recompile against -- must
        refuse rather than silently falling back to the lightweight check."""
        with TemporaryDirectory() as tmp:
            package_path, output_dir = self._certified_bundle(tmp)
            with self.assertRaises(ManifestError):
                api.verify_certificate_bundle(str(output_dir), full=True)
            with self.assertRaises(ManifestError):
                api.verify_certificate_bundle(str(output_dir), package=str(package_path), full=True)
            with self.assertRaises(ManifestError):
                api.verify_certificate_bundle(str(output_dir), project=str(PROJECT), full=True)

    def test_full_reverification_recompiles_and_passes_for_a_clean_bundle(self):
        """research-readiness audit issue 9: `full=True` actually invokes
        the live Lean toolchain again (recompiling each certificate,
        recomputing its generated declaration's own fresh axiom closure,
        reapplying the live package's axiom policy) -- strictly more than
        the lightweight, bytes-only self-consistency check, and distinctly
        labeled (`mode`, `:full_recompile`/`:full_axiom_policy_reapplied`
        checks) so the two are never confused with each other."""
        with TemporaryDirectory() as tmp:
            package_path, output_dir = self._certified_bundle(tmp)
            lightweight = api.verify_certificate_bundle(
                str(output_dir), package=str(package_path), project=str(PROJECT),
            )
            self.assertEqual(lightweight["mode"], "lightweight")
            self.assertTrue(lightweight["consistent"])
            self.assertNotIn(f"{ENTRYPOINT}:full_recompile", lightweight["checks"])

            full = api.verify_certificate_bundle(
                str(output_dir), package=str(package_path), project=str(PROJECT),
                trusted_local=True, timeout_s=180, full=True,
            )
            self.assertEqual(full["mode"], "full")
            self.assertTrue(full["consistent"], full["checks"])
            self.assertTrue(full["checks"][f"{ENTRYPOINT}:full_recompile"]["ok"])
            self.assertTrue(full["checks"][f"{ENTRYPOINT}:full_axiom_policy_reapplied"]["ok"])


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class PackageOwnedLeanEnvironmentTests(unittest.TestCase):
    """research-readiness audit issue 1: the package's own `lean_theory.
    entry_modules` is the sole source of the formal environment resolution
    AND certification run under -- there is no second, caller-suppliable
    `--lean-import`/`lean_import` runtime import set capable of diverging
    from it. `certify_session` no longer accepts a `lean_import` parameter
    at all (a `TypeError` on an old-style call proves this structurally,
    not just by convention)."""

    ALT_ENTRYPOINT = "Physics.ValidModel"  # namespace != module path (Testv2.AltModule); issue 13

    def test_certify_session_has_no_lean_import_parameter(self):
        """A caller cannot even attempt to certify against a different
        formal environment than the package's own -- the parameter simply
        does not exist to pass."""
        with self.assertRaises(TypeError):
            certify_session(
                session="x", package="x", project="x", output_dir="x",
                lean_import="Testv2.Requirements",
            )

    def test_multi_module_package_resolves_and_certifies_both_targets(self):
        """A package whose two selected entrypoints live in two different
        Lean modules (`Testv2.AltModule` and `Testv2.Requirements`) must
        resolve AND certify both -- using exactly `entry_modules`, never a
        single caller-supplied module string that could only ever import
        one of them."""
        with TemporaryDirectory() as tmp:
            extraction_path = Path(tmp) / "extraction.json"
            _write_extraction_result(extraction_path)
            package_path = Path(tmp) / "package.json"
            VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[ENTRYPOINT, self.ALT_ENTRYPOINT],
                adapter=DFT_CAPABILITY_PLUGIN, interface_contract=_constraints(),
                entry_modules=["Testv2.AltModule", "Testv2.Requirements"],
                binding_choices=[
                    {"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"},
                    {"entrypoint": self.ALT_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"},
                ],
            ).write(package_path)
            session_path = Path(tmp) / "session.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")

            output_dir = Path(tmp) / "certificate"
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                output_dir=str(output_dir), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertEqual(set(manifest["targets"]), {ENTRYPOINT, self.ALT_ENTRYPOINT})
            for entrypoint in (ENTRYPOINT, self.ALT_ENTRYPOINT):
                safe = entrypoint.replace(".", "_")
                self.assertTrue((output_dir / f"{safe}.lean").exists())

    def test_entry_modules_are_hash_bound_by_package_sha256(self):
        """Two packages differing only in `entry_modules` must have
        different `package_sha256` -- the module list is part of package
        identity, not a side channel a caller could silently change
        post-hoc without it being detected as a different package."""
        base = VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[self.ALT_ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(), entry_modules=["Testv2.AltModule"],
        ).sha256()
        different_modules = VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[self.ALT_ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(), entry_modules=["Testv2.AltModule", "Testv2.Requirements"],
        ).sha256()
        self.assertNotEqual(base, different_modules)


CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class SessionLocalAssumptionCannotCertifyTests(unittest.TestCase):
    """research-readiness audit issue 2: `VerificationSession.
    accept_assumption` is a session-local, exploratory decision -- it must
    never by itself make a target certifiable. Only an assumption
    normalized into the package's own `external_assumptions` (via
    `add_external_assumption`, then re-deriving the session) is a
    certifiable decision, exactly like a binding choice."""

    def _package_and_session(self, tmp):
        extraction_path = Path(tmp) / "extraction.json"
        _write_extraction_result(extraction_path)
        package_path = Path(tmp) / "package.json"
        VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[CONDITIONAL_ENTRYPOINT], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(),
            binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
        ).write(package_path)
        session_path = Path(tmp) / "session.json"
        session = start_session(
            extraction_result=str(extraction_path), package=str(package_path),
            session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
        )
        return package_path, session_path, session

    def test_session_local_assumption_alone_cannot_certify(self):
        with TemporaryDirectory() as tmp:
            package_path, session_path, session = self._package_and_session(tmp)
            premise = session.unresolved_premises[0]
            session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            self.assertEqual(session.status, "ready_for_certificate")  # session itself looks ready...

            # ...but certification must still refuse: the package this
            # session was built from has no matching external_assumption.
            with self.assertRaises(ManifestError):
                certify_session(
                    session=str(session_path), package=str(package_path), project=str(PROJECT),
                    output_dir=str(Path(tmp) / "certificate"), trusted_local=True, timeout_s=180,
                )

    def test_package_normalized_assumption_can_certify(self):
        """The exact same assumption, authored into the package instead,
        certifies cleanly -- proving the block above is about WHERE the
        decision lives, not a blanket ban on conditional certificates."""
        with TemporaryDirectory() as tmp:
            package_path, session_path, session = self._package_and_session(tmp)
            premise = session.unresolved_premises[0]
            add_external_assumption(
                package_path, premise_id=premise["id"],
                proposition_fingerprint=premise["type_fingerprint"],
                rationale="physical target requires non-locality",
            )
            extraction_path = Path(tmp) / "extraction.json"
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                output_dir=str(Path(tmp) / "certificate"), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(manifest["status"], "certified")
            self.assertTrue(manifest["conditional"])


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
            # research-readiness audit issue 2: the canonical, certifiable
            # route for an assumption is package-normalized, not session-
            # local `accept_assumption` -- author it into the package, then
            # re-derive the session from the (now-changed) package.
            for premise in session.unresolved_premises:
                add_external_assumption(
                    package_path, premise_id=premise["id"],
                    proposition_fingerprint=premise["type_fingerprint"],
                    rationale="physical target requires non-locality",
                )
            session = start_session(
                extraction_result=str(extraction_path), package=str(package_path),
                session=str(session_path), project=str(PROJECT), trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "ready_for_certificate")

            output_dir = Path(tmp) / "certificate"
            manifest = certify_session(
                session=str(session_path), package=str(package_path), project=str(PROJECT),
                output_dir=str(output_dir),
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
                    output_dir=str(Path(tmp) / "certificate"),
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
                output_dir=str(Path(tmp) / "certificate"),
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
                    output_dir=str(Path(tmp) / "certificate"),
                    trusted_local=True, timeout_s=180,
                )


if __name__ == "__main__":
    unittest.main()
