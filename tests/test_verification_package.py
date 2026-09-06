import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.verification.package import VerificationPackageBuilder, load_package, package_sha256

LEAN_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"


def _builder(**overrides):
    kwargs = dict(
        lean_project=LEAN_PROJECT,
        entrypoints=["Testv2.Requirements.ValidPretrainingArchitecture"],
        adapter_profile="dft-capability",
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
            _builder(external_assumptions=[{"premise_id": "Not.A.Selected.Entrypoint#3", "rationale": "x"}])
        _builder(external_assumptions=[
            {"premise_id": "Testv2.Requirements.ValidPretrainingArchitecture#3", "rationale": "x"},
        ])

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


if __name__ == "__main__":
    unittest.main()
