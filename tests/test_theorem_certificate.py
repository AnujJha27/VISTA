"""`dftcert.verification.certificate` against a real Lean toolchain (spec
sections 19/23/27.4, theorem-centric-gaps issues A/B/C): the generated
wrapper theorem must actually compile, external assumptions must survive
as real binders (never `axiom`), and the report must refuse to assemble
while anything is unresolved -- gated on the GENERATED certificate
declaration's own axiom closure, not the entrypoint's.
"""
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.core import verify_structural_certificate
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.certificate import (
    assemble_certificate_report, generate_certificate_source, parse_certificate_axiom_closure,
)
from dftcert.verification.lean_inspect import inspect_declarations
from dftcert.verification.package import VerificationPackageBuilder
from dftcert.verification.session import start_session

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _constraints, _inventory

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
PLAIN_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"
CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"
ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# `dftcert.structural.core` forbids the same four tokens in any generated
# certificate; the theorem-centric certificate must be just as clean.
_FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|unsafe)\b")


def _package(entrypoint, **overrides):
    kwargs = dict(
        lean_project=PROJECT, entrypoints=[entrypoint], adapter=DFT_CAPABILITY_PLUGIN,
        interface_contract=_constraints(),
    )
    kwargs.update(overrides)
    return VerificationPackageBuilder(**kwargs).as_dict()


def _start(package, out, symmetrized=True):
    return start_session(
        artifact_sha256="deadbeef", inventory=_inventory(adjacency=_CHAIN3, stages=0, symmetrized=symmetrized),
        extractor_version="t", package=package, adapter=DFT_CAPABILITY_PLUGIN,
        project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
    )


def _ready_session(entrypoint, tmp, **package_overrides):
    package = _package(entrypoint, **package_overrides)
    session = _start(package, Path(tmp) / "session.json")
    for premise in session.unresolved_premises:
        session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
    return session, package


def _generate(session, entrypoint, namespace):
    return generate_certificate_source(
        session=session.value, entrypoint=entrypoint, namespace=namespace, entry_modules=["Testv2.Requirements"],
        project_root=PROJECT, trusted_local=True, timeout_s=180,
    )


def _compile(source: str):
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "Cert.lean"
        path.write_text(source, encoding="utf-8")
        return verify_structural_certificate(
            project_root=PROJECT, certificate_source=path, trusted_local=True, timeout_s=180,
        )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class UnconditionalCertificateTests(unittest.TestCase):
    def test_fully_resolved_entrypoint_generates_a_compiling_certificate(self):
        with TemporaryDirectory() as tmp:
            session, _ = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            self.assertEqual(session.status, "ready_for_certificate")
            source = _generate(session, PLAIN_ENTRYPOINT, "VISTA.TestUnconditional")
            self.assertNotRegex(source, _FORBIDDEN)
            compiled = _compile(source)
            self.assertEqual(compiled["status"], "verified", compiled["diagnostics"])

    def test_report_marks_unconditional_certificate_with_no_assumptions(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = _generate(session, PLAIN_ENTRYPOINT, "VISTA.TestUnconditional2")
            compiled = _compile(source)
            self.assertEqual(compiled["status"], "verified", compiled["diagnostics"])
            entrypoint_axioms = inspect_declarations(
                project_root=PROJECT, imports=["Testv2.Requirements"], declarations=[PLAIN_ENTRYPOINT],
                trusted_local=True, timeout_s=120,
            )[PLAIN_ENTRYPOINT]["axioms"]
            certificate_axioms = parse_certificate_axiom_closure(compiled["diagnostics"])
            report = assemble_certificate_report(
                session=session.value, package=package, entrypoint=PLAIN_ENTRYPOINT,
                certificate_source=source, entrypoint_axiom_closure=entrypoint_axioms,
                certificate_axiom_closure=certificate_axioms, allowed_axioms=ALLOWED_AXIOMS,
            )
            self.assertFalse(report["conditional"])
            self.assertEqual(report["external_assumptions"], [])
            self.assertEqual(report["status"], "certified")
            self.assertTrue(report["used_facts"], "used_facts should list the IR evidence nodes actually relied on")
            # research-readiness audit issue 10: adjacency selection
            # provenance is surfaced directly on the report -- `_constraints()`
            # declares `adjacency_state_name: "adjacency"`, which matches the
            # fixture's own state entry name exactly, so selection is
            # `declared`, not a `heuristic_name_match` fallback.
            self.assertEqual(report["adjacency_selection"], {
                "selected_state_name": "adjacency", "selection_provenance": "declared",
            })


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ConditionalCertificateTests(unittest.TestCase):
    def test_assumption_survives_as_a_binder_never_as_an_axiom(self):
        with TemporaryDirectory() as tmp:
            session, _ = _ready_session(
                CONDITIONAL_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            self.assertEqual(session.status, "ready_for_certificate")
            source = _generate(session, CONDITIONAL_ENTRYPOINT, "VISTA.TestConditional")
            self.assertNotRegex(source, _FORBIDDEN)
            self.assertIn("TargetRequiresLongRangeCoupling : Prop", source)
            # `hPhysical`'s premise type (`TargetRequiresLongRangeCoupling`)
            # is non-dependent (nothing downstream mentions its value), so
            # Lean's printer renders that binder in the TYPE as a plain
            # arrow ("TargetRequiresLongRangeCoupling → ...") rather than a
            # named "(hPhysical : ...)" -- still a genuine binder, not an
            # axiom: `hPhysical` itself appears as a real lambda-bound
            # parameter on the VALUE side.
            self.assertIn("TargetRequiresLongRangeCoupling →", source)
            self.assertIn("fun TargetRequiresLongRangeCoupling hPhysical =>", source)
            compiled = _compile(source)
            self.assertEqual(compiled["status"], "verified", compiled["diagnostics"])

    def test_report_marks_certificate_conditional_on_the_named_assumption(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                CONDITIONAL_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = _generate(session, CONDITIONAL_ENTRYPOINT, "VISTA.TestConditional2")
            compiled = _compile(source)
            self.assertEqual(compiled["status"], "verified", compiled["diagnostics"])
            entrypoint_axioms = inspect_declarations(
                project_root=PROJECT, imports=["Testv2.Requirements"], declarations=[CONDITIONAL_ENTRYPOINT],
                trusted_local=True, timeout_s=120,
            )[CONDITIONAL_ENTRYPOINT]["axioms"]
            certificate_axioms = parse_certificate_axiom_closure(compiled["diagnostics"])
            report = assemble_certificate_report(
                session=session.value, package=package, entrypoint=CONDITIONAL_ENTRYPOINT,
                certificate_source=source, entrypoint_axiom_closure=entrypoint_axioms,
                certificate_axiom_closure=certificate_axioms, allowed_axioms=ALLOWED_AXIOMS,
            )
            self.assertTrue(report["conditional"])
            self.assertEqual(len(report["external_assumptions"]), 1)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class BlockedCertificateTests(unittest.TestCase):
    def test_unresolved_node_refuses_certificate_generation(self):
        with TemporaryDirectory() as tmp:
            package = _package(PLAIN_ENTRYPOINT)
            session = _start(package, Path(tmp) / "session.json", symmetrized=False)
            self.assertEqual(session.status, "blocked_on_premise")
            with self.assertRaises(ManifestError):
                _generate(session, PLAIN_ENTRYPOINT, "VISTA.TestBlocked")

    def test_sorryax_in_axiom_closure_blocks_the_report(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = _generate(session, PLAIN_ENTRYPOINT, "VISTA.TestSorry")
            with self.assertRaises(ManifestError):
                assemble_certificate_report(
                    session=session.value, package=package, entrypoint=PLAIN_ENTRYPOINT,
                    certificate_source=source, entrypoint_axiom_closure=["propext"],
                    certificate_axiom_closure=["propext", "sorryAx"], allowed_axioms=ALLOWED_AXIOMS,
                )

    def test_custom_axiom_blocks_unless_named_in_package_axiom_policy(self):
        """Issue 12: no command-line-only trust escalation -- an extra
        allowed axiom must come from the package's own hash-bound
        axiom_policy, never a runtime flag."""
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = _generate(session, PLAIN_ENTRYPOINT, "VISTA.TestCustomAxiom")
            self.assertEqual(package["axiom_policy"], {"additional_allowed": []})
            with self.assertRaises(ManifestError):
                assemble_certificate_report(
                    session=session.value, package=package, entrypoint=PLAIN_ENTRYPOINT,
                    certificate_source=source, entrypoint_axiom_closure=["propext"],
                    certificate_axiom_closure=["propext", "MyCustomAxiom"], allowed_axioms=ALLOWED_AXIOMS,
                )
            package_with_policy = _package(
                PLAIN_ENTRYPOINT,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
                axiom_policy={"additional_allowed": ["MyCustomAxiom"]},
            )
            allowed_with_package_policy = ALLOWED_AXIOMS | frozenset(
                package_with_policy["axiom_policy"]["additional_allowed"]
            )
            report = assemble_certificate_report(
                session=session.value, package=package_with_policy, entrypoint=PLAIN_ENTRYPOINT,
                certificate_source=source, entrypoint_axiom_closure=["propext"],
                certificate_axiom_closure=["propext", "MyCustomAxiom"],
                allowed_axioms=allowed_with_package_policy,
            )
            self.assertEqual(report["status"], "certified")


if __name__ == "__main__":
    unittest.main()
