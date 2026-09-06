"""`dftcert.verification.session` against a real Lean toolchain and the
real DFT adapter (spec section 14/16/27.5, theorem-centric-gaps issues
1-4): a blocked session is valid and resumable, resume is idempotent while
fingerprints match, a changed fingerprint goes stale rather than silently
reusing old decisions, and `accept_assumption` is the only way an
unresolved premise becomes certifiable.

`start_session` takes the raw graph `inventory` (never a pre-built IR) and
derives the structural IR itself under the package's own
`interface_contract` -- there is no parameter through which a caller could
hand it a tampered semantic fact while keeping the artifact hash.
"""
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.core import structural_ir_from_inventory
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.package import VerificationPackageBuilder
from dftcert.verification.session import resume_session, start_session

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _constraints, _inventory

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
PLAIN_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"
CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"


def _package(entrypoint, **overrides):
    kwargs = dict(
        lean_project=PROJECT, entrypoints=[entrypoint], adapter=DFT_CAPABILITY_PLUGIN,
        interface_contract=_constraints(),
    )
    kwargs.update(overrides)
    return VerificationPackageBuilder(**kwargs).as_dict()


def _inv(*, symmetrized=True):
    return _inventory(adjacency=_CHAIN3, stages=0, symmetrized=symmetrized)


def _start(*, package, output, artifact_sha256="a1", symmetrized=True):
    return start_session(
        artifact_sha256=artifact_sha256, inventory=_inv(symmetrized=symmetrized), extractor_version="t",
        package=package, adapter=DFT_CAPABILITY_PLUGIN,
        project_root=PROJECT, output=output, trusted_local=True, timeout_s=180,
    )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class SessionBlockedAndResumeTests(unittest.TestCase):
    def test_blocked_session_is_valid_and_resumable_not_failed(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            # An unconstrained-parameter operator has non-local capacity
            # but is not self-adjoint -- hSA genuinely cannot discharge, so
            # this stays honestly blocked (unlike the symmetrized fixture,
            # which -- since issue 10's fix removed the spurious
            # operator_message_depth candidate -- now resolves unaided).
            session = _start(package=_package(PLAIN_ENTRYPOINT), output=out, symmetrized=False)
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
            session = _start(package=package, output=out)
            for premise in session.unresolved_premises:
                session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
            self.assertEqual(session.status, "ready_for_certificate")
            again = _start(package=package, output=out)
            self.assertEqual(again.status, "ready_for_certificate")
            self.assertEqual(again.value["decisions"], session.value["decisions"])

    def test_changed_package_hash_goes_stale_and_preserves_old_session(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            _start(package=_package(PLAIN_ENTRYPOINT), output=out)
            original = json.loads(out.read_text(encoding="utf-8"))
            changed_package = _package(PLAIN_ENTRYPOINT, interface_contract={**_constraints(), "note": "different"})
            _start(package=changed_package, output=out)
            new_value = json.loads(out.read_text(encoding="utf-8"))
            self.assertNotEqual(new_value["formal_package_binding"], original["formal_package_binding"])
            stale_files = list(Path(tmp).glob("session.stale-*.json"))
            self.assertEqual(len(stale_files), 1)
            self.assertEqual(json.loads(stale_files[0].read_text(encoding="utf-8")), original)

    def test_changed_artifact_hash_goes_stale(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            _start(package=_package(PLAIN_ENTRYPOINT), output=out, artifact_sha256="a1")
            _start(package=_package(PLAIN_ENTRYPOINT), output=out, artifact_sha256="a2-different")
            self.assertEqual(len(list(Path(tmp).glob("session.stale-*.json"))), 1)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class TrustedInputChainTests(unittest.TestCase):
    """Issues 1/2: start_session derives the IR itself from the raw
    inventory under the package's own interface_contract -- there is no
    way to smuggle a tampered semantic fact through while keeping the
    artifact hash, because there is no "give me a finished IR" parameter
    at all."""

    def test_edited_semantic_fact_is_rejected_even_with_the_correct_artifact_hash(self):
        """The old attack this closes: build a correct IR, edit one
        semantic field (xc form), keep the artifact_sha256 and every hash
        field untouched. `start_session` has no "give me a finished IR"
        parameter at all -- it only ever calls
        `structural_ir_from_inventory`, which re-derives every semantic
        claim from the raw inventory and compares (`plugin.revalidate`).
        This directly exercises that same revalidation a tampered IR would
        hit, via the public `dftcert.structural.core.validate_translation`
        entrypoint it uses internally."""
        from dftcert.structural.core import validate_translation

        genuine = structural_ir_from_inventory(
            inventory=_inv(), artifact_sha256="a1", extractor_version="t",
            input_constraints=_constraints(), plugin=DFT_CAPABILITY_PLUGIN,
        )
        tampered = json.loads(json.dumps(genuine))
        tampered["xc"]["form"] = "smooth"  # was "hinge"; artifact_sha256 untouched
        self.assertNotEqual(tampered, genuine)  # sanity: the tamper actually changed something
        with self.assertRaises(ManifestError):
            validate_translation(
                inventory=_inv(), value=tampered, input_constraints=_constraints(),
                artifact_sha256="a1", plugin=DFT_CAPABILITY_PLUGIN,
            )
        # The untampered IR revalidates cleanly against the same inventory.
        validate_translation(
            inventory=_inv(), value=genuine, input_constraints=_constraints(),
            artifact_sha256="a1", plugin=DFT_CAPABILITY_PLUGIN,
        )

    def test_interface_contract_mismatch_is_not_silently_combined(self):
        """Deriving under contract A then asking a package with contract B
        to reuse it is impossible by construction: start_session always
        derives fresh from (inventory, package.interface_contract).
        Different contracts -> different IR -> different session/package
        binding, never silently merged."""
        with TemporaryDirectory() as tmp_a, TemporaryDirectory() as tmp_b:
            contract_a = _constraints(expected_locality="non_local")
            contract_b = _constraints(expected_locality="local")
            out_a = Path(tmp_a) / "session.json"
            out_b = Path(tmp_b) / "session.json"
            session_a = _start(package=_package(PLAIN_ENTRYPOINT, interface_contract=contract_a), output=out_a)
            session_b = _start(package=_package(PLAIN_ENTRYPOINT, interface_contract=contract_b), output=out_b)
            self.assertNotEqual(session_a.value["ir_sha256"], session_b.value["ir_sha256"])

    def test_derivation_does_not_require_expected_locality(self):
        """Issue 5, exercised through the real trusted entrypoint: a
        theorem-centric package's interface_contract need not specify a
        locality policy at all."""
        with TemporaryDirectory() as tmp:
            contract = {k: v for k, v in _constraints().items() if k != "expected_locality"}
            out = Path(tmp) / "session.json"
            session = _start(package=_package(PLAIN_ENTRYPOINT, interface_contract=contract), output=out)
            self.assertIn(session.status, {"blocked_on_premise", "ready_for_certificate"})


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class FreshnessTests(unittest.TestCase):
    """Issue 3: package freshness is actively checked against the live
    Lean project, not merely stored."""

    def test_stale_project_fingerprint_is_rejected(self):
        package = _package(PLAIN_ENTRYPOINT)
        package["lean_theory"]["project_fingerprint"] = "0" * 64
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                _start(package=package, output=Path(tmp) / "session.json")

    def test_stale_toolchain_is_rejected(self):
        package = _package(PLAIN_ENTRYPOINT)
        package["lean_theory"]["toolchain"] = "leanprover/lean4:v0.0.0"
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                _start(package=package, output=Path(tmp) / "session.json")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class AdapterIdentityTests(unittest.TestCase):
    """Issue 4: the adapter's identity is computed from the executing
    implementation, checked against the package's recorded identity."""

    def test_modified_adapter_identity_in_package_is_rejected(self):
        package = _package(PLAIN_ENTRYPOINT)
        package["adapter"] = {**package["adapter"], "implementation_sha256": "0" * 64}
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                _start(package=package, output=Path(tmp) / "session.json")

    def test_matching_adapter_identity_is_accepted(self):
        with TemporaryDirectory() as tmp:
            session = _start(package=_package(PLAIN_ENTRYPOINT), output=Path(tmp) / "session.json")
            self.assertEqual(session.value["adapter_binding"], DFT_CAPABILITY_PLUGIN.semantic_identity)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class AssumptionMechanicsTests(unittest.TestCase):
    def test_accept_assumption_requires_a_premise_node(self):
        with TemporaryDirectory() as tmp:
            out = Path(tmp) / "session.json"
            session = _start(package=_package(PLAIN_ENTRYPOINT), output=out)
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
            session = _start(package=package, output=out)
            premise = session.unresolved_premises[0]
            session.accept_assumption(premise_id=premise["id"], rationale="domain expert says so")
            on_disk = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(on_disk["nodes"][premise["id"]]["status"], "specified_assumption")

    def test_stale_package_declared_assumption_with_wrong_fingerprint_is_not_applied(self):
        """Issue 7: a package-declared external assumption whose recorded
        proposition_fingerprint does not match the premise Lean just
        derived must not be silently applied."""
        with TemporaryDirectory() as tmp:
            package = _package(
                CONDITIONAL_ENTRYPOINT,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
                external_assumptions=[{
                    "premise_id": f"{CONDITIONAL_ENTRYPOINT}#7",
                    "proposition_fingerprint": "0" * 64,  # wrong on purpose
                    "rationale": "stale claim from a previous theorem version",
                }],
            )
            session = _start(package=package, output=Path(tmp) / "session.json")
            node = session.value["nodes"][f"{CONDITIONAL_ENTRYPOINT}#7"]
            self.assertEqual(node["status"], "unresolved")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class NamespaceModulePathMismatchTests(unittest.TestCase):
    """Issue 13: `Physics.ValidModel` lives in `Testv2/AltModule.lean` --
    an entrypoint whose namespace does not match its module path at all.
    A package must say so via an explicit entry_modules override; the
    session-building pipeline must import that module (not one guessed
    from the declaration's own namespace) and actually find/resolve it."""

    def test_entrypoint_is_found_via_explicit_entry_modules_override(self):
        entrypoint = "Physics.ValidModel"
        package = VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=[entrypoint], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(), entry_modules=["Testv2.AltModule"],
        ).as_dict()
        with TemporaryDirectory() as tmp:
            session = _start(package=package, output=Path(tmp) / "session.json")
            target = next(t for t in session.value["targets"] if t["entrypoint"] == entrypoint)
            # The DFT adapter's `site_count` candidate (a plain Nat) happens
            # to typecheck against this fixture's own unrelated Nat binder
            # too -- expected (nothing here is DFT-specific), just confirms
            # the entrypoint was actually found/resolved via the override.
            self.assertEqual(target["conclusion_display"], "3 ≥ 1")

    def test_guessed_module_from_namespace_does_not_exist(self):
        """The auto-derive fallback (splitting on the last dot) would guess
        module `Physics` here, which does not exist as an importable
        module at all -- confirms the override is load-bearing, not
        incidentally unnecessary."""
        package = VerificationPackageBuilder(
            lean_project=PROJECT, entrypoints=["Physics.ValidModel"], adapter=DFT_CAPABILITY_PLUGIN,
            interface_contract=_constraints(),
        ).as_dict()
        self.assertEqual(package["lean_theory"]["entry_modules"], ["Physics"])
        with TemporaryDirectory() as tmp:
            with self.assertRaises(Exception):
                _start(package=package, output=Path(tmp) / "session.json")


if __name__ == "__main__":
    unittest.main()
