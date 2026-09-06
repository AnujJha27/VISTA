"""`dftcert.verification.certificate` against a real Lean toolchain (spec
sections 19/23/27.4): the generated wrapper theorem must actually compile,
external assumptions must survive as real binders (never `axiom`), and the
report must refuse to assemble while anything is unresolved.
"""
import re
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN
from dftcert.verification.certificate import assemble_certificate_report, generate_certificate_source
from dftcert.verification.lean_inspect import inspect_declarations
from dftcert.verification.package import VerificationPackageBuilder
from dftcert.verification.session import start_session

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON
from tests.test_structural_capability import _CHAIN3, _ir

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
PLAIN_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitecture"
CONDITIONAL_ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"
ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})

# `dftcert.structural.core` forbids the same four tokens in any generated
# certificate; the theorem-centric certificate must be just as clean.
_FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|unsafe)\b")


def _ready_session(entrypoint, tmp, **package_overrides):
    kwargs = dict(
        lean_project=PROJECT, entrypoints=[entrypoint], adapter_profile="dft-capability",
        interface_contract={},
    )
    kwargs.update(package_overrides)
    package = VerificationPackageBuilder(**kwargs).as_dict()
    out = Path(tmp) / "session.json"
    session = start_session(
        artifact_sha256="deadbeef", artifact_ir=_ir(adjacency=_CHAIN3, stages=0, symmetrized=True),
        ir_sha256="cafebabe", package=package, adapter=DFT_CAPABILITY_PLUGIN,
        project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
    )
    for premise in session.unresolved_premises:
        session.accept_assumption(premise_id=premise["id"], rationale="physical target requires non-locality")
    return session, package


def _compiles(source: str, imports: str = "import Testv2.Requirements\n\n") -> subprocess.CompletedProcess:
    with TemporaryDirectory() as tmp:
        path = Path(tmp) / "Cert.lean"
        path.write_text(imports + source, encoding="utf-8")
        return subprocess.run(["lake", "env", "lean", "-j", "1", str(path)], cwd=PROJECT, capture_output=True, text=True)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class UnconditionalCertificateTests(unittest.TestCase):
    def test_fully_resolved_entrypoint_generates_a_compiling_certificate(self):
        with TemporaryDirectory() as tmp:
            session, _ = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            self.assertEqual(session.status, "ready_for_certificate")
            source = generate_certificate_source(
                session=session.value, entrypoint=PLAIN_ENTRYPOINT,
                namespace="VISTA.TestUnconditional", lean_import="Testv2.Requirements",
            )
            self.assertNotRegex(source, _FORBIDDEN)
            result = _compiles(source)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_report_marks_unconditional_certificate_with_no_assumptions(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = generate_certificate_source(
                session=session.value, entrypoint=PLAIN_ENTRYPOINT,
                namespace="VISTA.TestUnconditional2", lean_import="Testv2.Requirements",
            )
            axioms = inspect_declarations(
                project_root=PROJECT, imports=["Testv2.Requirements"], declarations=[PLAIN_ENTRYPOINT],
                trusted_local=True, timeout_s=120,
            )[PLAIN_ENTRYPOINT]["axioms"]
            report = assemble_certificate_report(
                session=session.value, package=package, entrypoint=PLAIN_ENTRYPOINT,
                certificate_source=source, axiom_closure=axioms, allowed_axioms=ALLOWED_AXIOMS,
            )
            self.assertFalse(report["conditional"])
            self.assertEqual(report["external_assumptions"], [])
            self.assertEqual(report["status"], "certified")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ConditionalCertificateTests(unittest.TestCase):
    def test_assumption_survives_as_a_binder_never_as_an_axiom(self):
        with TemporaryDirectory() as tmp:
            session, _ = _ready_session(
                CONDITIONAL_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            self.assertEqual(session.status, "ready_for_certificate")
            source = generate_certificate_source(
                session=session.value, entrypoint=CONDITIONAL_ENTRYPOINT,
                namespace="VISTA.TestConditional", lean_import="Testv2.Requirements",
            )
            self.assertNotRegex(source, _FORBIDDEN)
            self.assertIn("(TargetRequiresNonLocality : Prop)", source)
            self.assertIn("(hPhysical : TargetRequiresNonLocality)", source)
            result = _compiles(source)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_report_marks_certificate_conditional_on_the_named_assumption(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                CONDITIONAL_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": CONDITIONAL_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = generate_certificate_source(
                session=session.value, entrypoint=CONDITIONAL_ENTRYPOINT,
                namespace="VISTA.TestConditional2", lean_import="Testv2.Requirements",
            )
            axioms = inspect_declarations(
                project_root=PROJECT, imports=["Testv2.Requirements"], declarations=[CONDITIONAL_ENTRYPOINT],
                trusted_local=True, timeout_s=120,
            )[CONDITIONAL_ENTRYPOINT]["axioms"]
            report = assemble_certificate_report(
                session=session.value, package=package, entrypoint=CONDITIONAL_ENTRYPOINT,
                certificate_source=source, axiom_closure=axioms, allowed_axioms=ALLOWED_AXIOMS,
            )
            self.assertTrue(report["conditional"])
            self.assertEqual(len(report["external_assumptions"]), 1)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class BlockedCertificateTests(unittest.TestCase):
    def test_unresolved_node_refuses_certificate_generation(self):
        with TemporaryDirectory() as tmp:
            package = VerificationPackageBuilder(
                lean_project=PROJECT, entrypoints=[PLAIN_ENTRYPOINT], adapter_profile="dft-capability",
                interface_contract={},
            ).as_dict()
            out = Path(tmp) / "session.json"
            session = start_session(
                artifact_sha256="deadbeef", artifact_ir=_ir(adjacency=_CHAIN3, stages=0, symmetrized=True),
                ir_sha256="cafebabe", package=package, adapter=DFT_CAPABILITY_PLUGIN,
                project_root=PROJECT, output=out, trusted_local=True, timeout_s=180,
            )
            self.assertEqual(session.status, "blocked_on_premise")
            with self.assertRaises(ManifestError):
                generate_certificate_source(
                    session=session.value, entrypoint=PLAIN_ENTRYPOINT,
                    namespace="VISTA.TestBlocked", lean_import="Testv2.Requirements",
                )

    def test_sorryax_in_axiom_closure_blocks_the_report(self):
        with TemporaryDirectory() as tmp:
            session, package = _ready_session(
                PLAIN_ENTRYPOINT, tmp,
                binding_choices=[{"entrypoint": PLAIN_ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
            )
            source = generate_certificate_source(
                session=session.value, entrypoint=PLAIN_ENTRYPOINT,
                namespace="VISTA.TestSorry", lean_import="Testv2.Requirements",
            )
            with self.assertRaises(ManifestError):
                assemble_certificate_report(
                    session=session.value, package=package, entrypoint=PLAIN_ENTRYPOINT,
                    certificate_source=source, axiom_closure=["propext", "sorryAx"],
                    allowed_axioms=ALLOWED_AXIOMS,
                )


if __name__ == "__main__":
    unittest.main()
