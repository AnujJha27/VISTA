import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.package import VerificationPackageBuilder, load_package, package_sha256

LEAN_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"


def _builder(**overrides):
    kwargs = dict(
        lean_project=LEAN_PROJECT,
        entrypoints=["Testv2.Requirements.ValidPretrainingArchitecture"],
        adapter=DFT_CAPABILITY_PLUGIN,
        interface_contract={"output_contracts": [{"index": 0, "role": "xc_energy"}]},
    )
    kwargs.update(overrides)
    return VerificationPackageBuilder(**kwargs)


class PackageBuilderTests(unittest.TestCase):
    def test_deterministic_canonical_json(self):
        first = _builder().as_dict()
        second = _builder().as_dict()
        self.assertEqual(first, second)
        self.assertEqual(_builder().sha256(), _builder().sha256())

    def test_absolute_project_path_not_in_output_or_hash(self):
        package = _builder().as_dict()
        self.assertNotIn(str(LEAN_PROJECT), json.dumps(package))

    def test_entrypoint_order_is_canonicalized(self):
        forward = _builder(entrypoints=["Testv2.Requirements.A", "Testv2.Requirements.B"])
        backward = _builder(entrypoints=["Testv2.Requirements.B", "Testv2.Requirements.A"])
        self.assertEqual(forward.as_dict()["lean_theory"]["entrypoints"],
                         backward.as_dict()["lean_theory"]["entrypoints"])
        self.assertEqual(forward.sha256(), backward.sha256())

    def test_external_assumption_must_reference_a_selected_entrypoint(self):
        with self.assertRaises(ManifestError):
            _builder(external_assumptions=[{
                "premise_id": "Not.A.Selected.Entrypoint#3", "rationale": "x", "proposition_fingerprint": "f",
            }])
        _builder(external_assumptions=[{
            "premise_id": "Testv2.Requirements.ValidPretrainingArchitecture#3",
            "rationale": "x", "proposition_fingerprint": "f",
        }])

    def test_external_assumption_requires_a_proposition_fingerprint(self):
        """Issue 7: a bare premise_id is not enough to identify which exact
        proposition was accepted -- proposition_fingerprint and rationale
        are mandatory package fields, checked again at session time."""
        with self.assertRaises(ManifestError):
            _builder(external_assumptions=[{
                "premise_id": "Testv2.Requirements.ValidPretrainingArchitecture#3", "rationale": "x",
            }])
        with self.assertRaises(ManifestError):
            _builder(external_assumptions=[{
                "premise_id": "Testv2.Requirements.ValidPretrainingArchitecture#3",
                "proposition_fingerprint": "f",
            }])

    def test_tampering_changes_hash(self):
        baseline = _builder().sha256()
        changed_entrypoint = _builder(entrypoints=["Testv2.Requirements.SomethingElse"]).sha256()
        changed_contract = _builder(interface_contract={"output_contracts": []}).sha256()
        self.assertNotEqual(baseline, changed_entrypoint)
        self.assertNotEqual(baseline, changed_contract)

    def test_write_then_load_round_trips_and_validates(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "vista-package.json"
            expected_sha = _builder().write(path)
            loaded = load_package(path)
            self.assertEqual(package_sha256(loaded), expected_sha)

    def test_rejects_empty_entrypoints(self):
        with self.assertRaises(ManifestError):
            _builder(entrypoints=[])

    def test_rejects_non_lean_project(self):
        with TemporaryDirectory() as tmp:
            with self.assertRaises(ManifestError):
                _builder(lean_project=tmp)

    def test_adapter_identity_is_sourced_from_the_adapter_not_authored_text(self):
        """Issue 4: the package's adapter binding is exactly
        DFT_CAPABILITY_PLUGIN.semantic_identity -- there is no builder
        parameter through which a caller can author arbitrary adapter
        identity text."""
        package = _builder().as_dict()
        self.assertEqual(package["adapter"], DFT_CAPABILITY_PLUGIN.semantic_identity)
        self.assertEqual(set(package["adapter"]), {"profile", "semantic_version", "implementation_sha256"})

    def test_explicit_entry_modules_override_the_namespace_guess(self):
        """Issue 13: a declaration's namespace need not match its module
        path -- entry_modules, when given, is used verbatim."""
        package = _builder(entry_modules=["SomeOther.ModulePath"]).as_dict()
        self.assertEqual(package["lean_theory"]["entry_modules"], ["SomeOther.ModulePath"])

    def test_axiom_policy_defaults_to_no_additional_axioms_and_is_hash_bound(self):
        default_package = _builder().as_dict()
        self.assertEqual(default_package["axiom_policy"], {"additional_allowed": []})
        with_policy = _builder(axiom_policy={"additional_allowed": ["MyExtraAxiom"]})
        self.assertEqual(with_policy.as_dict()["axiom_policy"], {"additional_allowed": ["MyExtraAxiom"]})
        self.assertNotEqual(with_policy.sha256(), _builder().sha256())


if __name__ == "__main__":
    unittest.main()
