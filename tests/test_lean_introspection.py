"""`dftcert.verification.lean_inspect` against a real Lean toolchain (spec
section 27.2) -- structured introspection, never `#print`-text parsing.
Fixtures live in `examples/dft/lean/Testv2/InspectionFixtures*.lean`.

Requires a working `lake env lean` for the `examples/dft/lean` project
(the same one the rest of this repository's Lean-integration tooling
needs); skipped if that toolchain cannot even report its version, so this
suite doesn't fail the whole run on a machine with no Lean installed.
"""
import shutil
import subprocess
import unittest
from pathlib import Path

from dftcert.verification.lean_inspect import LeanIntrospectionError, inspect_declarations

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"


def _lean_available() -> bool:
    if shutil.which("lake") is None:
        return False
    try:
        subprocess.run(["lake", "env", "lean", "--version"], cwd=PROJECT,
                        capture_output=True, timeout=60)
        return True
    except OSError:
        return False


_SKIP_REASON = "no working `lake env lean` toolchain for examples/dft/lean"
_HAS_LEAN = _lean_available()


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class FixtureIntrospectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results = inspect_declarations(
            project_root=PROJECT,
            imports=["Testv2.InspectionFixtures"],
            declarations=[
                "Testv2.InspectionFixtures.sumOfTwoNats",
                "Testv2.InspectionFixtures.dependentExample",
                "Testv2.InspectionFixtures.propositionBinderExample",
                "Testv2.InspectionFixtures.usesHelperLemma",
                "Testv2.InspectionFixtures.NoSuchThing",
            ],
            trusted_local=True, timeout_s=180,
        )

    def test_missing_declaration_reports_exists_false_not_an_error(self):
        entry = self.results["Testv2.InspectionFixtures.NoSuchThing"]
        self.assertEqual(entry, {"declaration": "Testv2.InspectionFixtures.NoSuchThing", "exists": False})

    def test_two_explicit_binders_of_the_same_type_are_distinguished_by_position_not_type_string(self):
        binders = self.results["Testv2.InspectionFixtures.sumOfTwoNats"]["binders"]
        self.assertEqual([b["name"] for b in binders], ["siteCount", "depth"])
        self.assertEqual({b["binder_info"] for b in binders}, {"explicit"})
        # Same type -> same fingerprint; a resolver must not use this alone to tell them apart.
        self.assertEqual(binders[0]["type_fingerprint"], binders[1]["type_fingerprint"])

    def test_implicit_instance_implicit_and_dependent_binders_are_reported(self):
        binders = {b["name"]: b for b in self.results["Testv2.InspectionFixtures.dependentExample"]["binders"]}
        by_info = {b["binder_info"] for b in binders.values()}
        self.assertEqual(by_info, {"implicit", "instanceImplicit", "explicit"})
        dependent = next(b for b in binders.values() if b["type_display"].startswith("Fin"))
        self.assertIn("n", dependent["type_fingerprint_source"])

    def test_proposition_binder_is_flagged_is_prop_data_binder_is_not(self):
        binders = self.results["Testv2.InspectionFixtures.propositionBinderExample"]["binders"]
        by_name = {b["name"]: b for b in binders}
        self.assertFalse(by_name["n"]["is_prop"])
        self.assertTrue(by_name["hpos"]["is_prop"])

    def test_type_fingerprint_is_a_canonical_machine_representation_not_pretty_print(self):
        binders = self.results["Testv2.InspectionFixtures.dependentExample"]["binders"]
        dependent = next(b for b in binders if b["name"] == "site")
        self.assertEqual(dependent["type_display"], "Fin (n + 1)")
        self.assertNotEqual(dependent["type_display"], dependent["type_fingerprint_source"])
        self.assertIn("HAdd.hAdd", dependent["type_fingerprint_source"])

    def test_theorem_using_a_helper_lemma_reports_it_in_dependencies_not_as_a_premise(self):
        entry = self.results["Testv2.InspectionFixtures.usesHelperLemma"]
        self.assertEqual(entry["kind"], "theorem")
        self.assertEqual([b["name"] for b in entry["binders"]], ["a", "b"])
        self.assertIn("Testv2.InspectionFixtures.sumOfTwoNats_comm", entry["dependencies"])

    def test_dependency_closure_excludes_out_of_project_library_internals(self):
        entry = self.results["Testv2.InspectionFixtures.usesHelperLemma"]
        self.assertTrue(all(name.startswith("Testv2.") for name in entry["dependencies"]))


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class SorryAxiomAuditTests(unittest.TestCase):
    def test_sorry_shows_up_as_sorryax_in_the_axiom_closure(self):
        results = inspect_declarations(
            project_root=PROJECT, imports=["Testv2.InspectionFixturesSorry"],
            declarations=["Testv2.InspectionFixturesSorry.viaSorry"],
            trusted_local=True, timeout_s=180,
        )
        self.assertIn("sorryAx", results["Testv2.InspectionFixturesSorry.viaSorry"]["axioms"])


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class DftRequirementsIntrospectionTests(unittest.TestCase):
    """The real DFT theorem entrypoints (spec section 20.3) -- confirms the
    inspector reads an ordinary, non-VISTA-annotated theorem's binder
    telescope exactly as elaborated, external-assumption binder included."""

    @classmethod
    def setUpClass(cls):
        cls.results = inspect_declarations(
            project_root=PROJECT, imports=["Testv2.Requirements"],
            declarations=[
                "Testv2.Requirements.ValidPretrainingArchitecture",
                "Testv2.Requirements.ValidPretrainingArchitectureConditional",
                "Testv2.Requirements.ValidMessagePassingCoverage",
            ],
            trusted_local=True, timeout_s=180,
        )

    def test_fully_resolvable_entrypoint_binders(self):
        entry = self.results["Testv2.Requirements.ValidPretrainingArchitecture"]
        names = [b["name"] for b in entry["binders"]]
        self.assertEqual(names, ["siteCount", "longRangePairs", "op", "xc", "hSA", "hLR", "hXC"])
        is_prop = {b["name"]: b["is_prop"] for b in entry["binders"]}
        self.assertEqual(
            {name: is_prop[name] for name in ("siteCount", "longRangePairs", "op", "xc")},
            {"siteCount": False, "longRangePairs": False, "op": False, "xc": False},
        )
        self.assertTrue(all(is_prop[name] for name in ("hSA", "hLR", "hXC")))

    def test_external_assumption_prop_binder_is_a_data_binder_not_a_premise(self):
        entry = self.results["Testv2.Requirements.ValidPretrainingArchitectureConditional"]
        by_name = {b["name"]: b for b in entry["binders"]}
        # `TargetRequiresLongRangeCoupling : Prop` -- a Sort-valued data
        # binder (its own type, `Prop`, is not itself a Prop) -- distinct
        # from `hPhysical`, the actual proof premise selecting it (spec
        # section 5/13).
        self.assertFalse(by_name["TargetRequiresLongRangeCoupling"]["is_prop"])
        self.assertTrue(by_name["hPhysical"]["is_prop"])
        self.assertEqual(by_name["hPhysical"]["type_display"], "TargetRequiresLongRangeCoupling")

    def test_message_passing_coverage_is_a_separate_entrypoint(self):
        entry = self.results["Testv2.Requirements.ValidMessagePassingCoverage"]
        self.assertEqual([b["name"] for b in entry["binders"]], ["edges", "depth", "siteCount", "hCov"])


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class IntrospectionFailureModeTests(unittest.TestCase):
    def test_requires_trusted_local(self):
        from dftcert.manifest import ManifestError
        with self.assertRaises(ManifestError):
            inspect_declarations(
                project_root=PROJECT, imports=["Testv2.StructuralV2"],
                declarations=["Testv2.StructuralV2.guaranteedSelfAdjoint"],
            )

    def test_timeout_raises_introspection_error_not_a_crash(self):
        # A real, tiny timeout -- not mocked -- but small enough (Lean must
        # still start its process, load Mathlib-derived imports, and
        # elaborate) that it always fires regardless of how fast or
        # cache-warm the host is; `timeout_s=5` used to assume a slow
        # environment and went flaky once CI got fast enough to finish
        # inside 5s.
        with self.assertRaises(LeanIntrospectionError):
            inspect_declarations(
                project_root=PROJECT, imports=["Testv2.StructuralV2"],
                declarations=["Testv2.StructuralV2.guaranteedSelfAdjoint"],
                lean_command=("lake", "env", "lean", "-j", "1"),
                trusted_local=True, timeout_s=0.01,
            )


if __name__ == "__main__":
    unittest.main()
