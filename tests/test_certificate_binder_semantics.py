"""Generic (non-DFT) binder/certificate-generation semantics against a real
Lean toolchain (theorem-centric-gaps issues A/B/C): certificate generation
must handle explicit/implicit/instance-implicit/`lean_resolved` binders
correctly, external assumptions must preserve their EXACT Lean type rather
than being reconstructed from a heuristic, and the generated certificate's
OWN axiom closure (not the entrypoint's) must gate certification.

Builds sessions directly from `resolve_entrypoint` + `lean_inspect` (no DFT
adapter needed -- these fixtures are plain Lean, unrelated to any domain)
to exercise the real `session`/`certificate` code paths without a full
artifact pipeline.
"""
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from dftcert.manifest import ManifestError
from dftcert.verification.certificate import (
    assemble_certificate_report, generate_certificate_source, parse_certificate_axiom_closure,
)
from dftcert.verification.lean_inspect import inspect_declarations
from dftcert.verification.model import FormalBindingCandidate, new_session
from dftcert.verification.resolver import resolve_entrypoint
from dftcert.verification.session import VerificationSession, _build_nodes_for_entrypoint, _session_status

from tests.test_lean_introspection import _HAS_LEAN, _SKIP_REASON

PROJECT = Path(__file__).resolve().parent.parent / "examples" / "dft" / "lean"
ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})


def _session_for(
    entrypoint: str, module: str, candidates: list[FormalBindingCandidate] = (),
    forced_choices: dict[int, str] | None = None,
) -> VerificationSession:
    resolved = resolve_entrypoint(
        project_root=PROJECT, imports=[module], entrypoint=entrypoint,
        candidates=list(candidates), forced_choices=forced_choices, trusted_local=True, timeout_s=120,
    )
    introspected = inspect_declarations(
        project_root=PROJECT, imports=[module], declarations=[entrypoint],
        trusted_local=True, timeout_s=120,
    )[entrypoint]
    binder_names = [binder["name"] for binder in introspected["binders"]]
    nodes = _build_nodes_for_entrypoint(
        entrypoint=entrypoint, resolved=resolved, candidates=list(candidates),
        binder_names=binder_names, external_assumptions={},
    )
    value = new_session(
        session_id="test", artifact_binding={"artifact_sha256": "n/a"},
        adapter_binding={"profile": "n/a", "semantic_version": "n/a", "implementation_sha256": "n/a"},
        formal_package_binding={"package_sha256": "n/a"}, ir_sha256="n/a", created_at="1970-01-01T00:00:00+00:00",
    )
    value["nodes"] = nodes
    value["targets"] = [{
        "entrypoint": entrypoint, "root_node_ids": sorted(nodes),
        "conclusion_display": resolved["conclusion"]["type_display"],
    }]
    value["status"] = _session_status(nodes)
    tmp = TemporaryDirectory()
    session = VerificationSession(value, path=Path(tmp.name) / "session.json")
    session._tmp = tmp  # keep the directory alive for the session's lifetime
    return session


def _certify(session: VerificationSession, entrypoint: str, module: str, namespace: str):
    source = generate_certificate_source(
        session=session.value, entrypoint=entrypoint, namespace=namespace, entry_modules=[module],
        project_root=PROJECT, trusted_local=True, timeout_s=120,
    )
    import subprocess
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "Cert.lean"
        path.write_text(source, encoding="utf-8")
        result = subprocess.run(["lake", "env", "lean", "-j", "1", str(path)], cwd=PROJECT, capture_output=True, text=True)
    return source, result


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ExplicitOnlyCertificateTests(unittest.TestCase):
    """Issue A acceptance test #1: explicit binder only."""

    def test_explicit_binders_certificate_compiles(self):
        candidates = [
            FormalBindingCandidate(key="n", lean_expr="5", provenance="artifact_grounded",
                                    evidence_refs=("a",), display_label="n=5"),
        ]
        session = _session_for(
            "Testv2.InspectionFixtures.propositionBinderExample", "Testv2.InspectionFixtures", candidates,
        )
        self.assertEqual(session.status, "ready_for_certificate")
        source, result = _certify(session, "Testv2.InspectionFixtures.propositionBinderExample",
                                   "Testv2.InspectionFixtures", "VISTA.TestExplicitOnly")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ImplicitInstanceCertificateTests(unittest.TestCase):
    """Issue A acceptance tests #2/#3/#5: implicit binder resolved
    transitively, instance-implicit synthesized, and a mixed
    explicit+implicit+instance-implicit theorem, all producing a
    compiling certificate (never emitted as ordinary positional args)."""

    def test_implicit_and_instance_implicit_binder_certificate_compiles(self):
        site = FormalBindingCandidate(key="site", lean_expr="(2 : Fin 3)", provenance="artifact_grounded",
                                       evidence_refs=("a",), display_label="site")
        session = _session_for(
            "Testv2.InspectionFixtures.implicitBinderExample", "Testv2.InspectionFixtures", [site],
        )
        self.assertEqual(session.status, "ready_for_certificate")
        by_index = {int(n["binder_path"]): n for n in session.value["nodes"].values()}
        self.assertEqual(by_index[0]["status"], "lean_resolved")  # n, transitive
        self.assertEqual(by_index[1]["status"], "lean_resolved")  # DecidableEq Nat, instance
        source, result = _certify(session, "Testv2.InspectionFixtures.implicitBinderExample",
                                   "Testv2.InspectionFixtures", "VISTA.TestImplicitInstance")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_mixed_explicit_implicit_instance_certificate_compiles(self):
        candidates = [
            FormalBindingCandidate(key="site", lean_expr="(2 : Fin 3)", provenance="artifact_grounded",
                                    evidence_refs=("a",), display_label="site"),
            FormalBindingCandidate(key="extra", lean_expr="7", provenance="artifact_grounded",
                                    evidence_refs=("a",), display_label="extra"),
        ]
        # `site : Fin n` and `extra : Nat` are each independently
        # candidate-worthy (a `Fin`-typed literal coerces to `Nat` too, and
        # a bare numeral can elaborate against `Fin ?n` before `n` is
        # pinned down) -- genuinely ambiguous_binding, resolved the same
        # way real ambiguity always is: an explicit forced choice, not a
        # test-fixture bug.
        session = _session_for(
            "Testv2.InspectionFixtures.mixedBinderCertificateExample", "Testv2.InspectionFixtures", candidates,
            forced_choices={2: "site", 3: "extra"},
        )
        self.assertEqual(session.status, "ready_for_certificate")
        source, result = _certify(session, "Testv2.InspectionFixtures.mixedBinderCertificateExample",
                                   "Testv2.InspectionFixtures", "VISTA.TestMixed")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unresolved_implicit_binder_blocks_certification(self):
        """Issue A acceptance test #7: no candidate for `site` at all ->
        `n` never gets unified -> both stay unresolved -> certificate
        generation must refuse, never guess."""
        session = _session_for(
            "Testv2.InspectionFixtures.implicitBinderExample", "Testv2.InspectionFixtures", [],
        )
        self.assertEqual(session.status, "blocked_on_premise")
        with self.assertRaises(ManifestError):
            generate_certificate_source(
                session=session.value, entrypoint="Testv2.InspectionFixtures.implicitBinderExample",
                namespace="VISTA.TestBlocked", entry_modules=["Testv2.InspectionFixtures"],
                project_root=PROJECT, trusted_local=True, timeout_s=120,
            )


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class ExternalAssumptionTypingTests(unittest.TestCase):
    """Issue B: external assumption typing must preserve the exact Lean
    binder type, never a heuristic reconstruction."""

    def test_case1_single_prop_parameter_preserved_exactly(self):
        session = _session_for(
            "Testv2.InspectionFixtures.twoIndependentPropParameters", "Testv2.InspectionFixtures", [],
        )
        premise_id = next(nid for nid, n in session.value["nodes"].items() if n["kind"] == "premise")
        session.accept_assumption(premise_id=premise_id, rationale="test")
        by_index = {int(n["binder_path"]): n for n in session.value["nodes"].values()}
        self.assertEqual(by_index[0]["status"], "specified_assumption")  # P
        self.assertEqual(by_index[1]["status"], "unresolved")  # Q, never touched
        # Q being unresolved means the SESSION overall stays blocked -- this
        # test only checks P/hP typing, not full certification (see case2).
        self.assertEqual(session.status, "blocked_on_premise")

    def test_case2_conjunction_preserves_exact_type_p_and_q(self):
        session = _session_for(
            "Testv2.InspectionFixtures.conjunctionAssumption", "Testv2.InspectionFixtures", [],
        )
        premise_id = next(nid for nid, n in session.value["nodes"].items() if n["kind"] == "premise")
        # Before any assumption is accepted, P/Q are still bare unassigned
        # metavariables, so the premise's OWN stored pretty_type honestly
        # shows placeholders here -- the exact "P ∧ Q" text is what the
        # generated CERTIFICATE must show (checked below), since that's
        # where named free binders actually get threaded through Lean.
        session.accept_assumption(premise_id=premise_id, rationale="test")
        self.assertEqual(session.status, "ready_for_certificate")
        by_index = {int(n["binder_path"]): n for n in session.value["nodes"].values()}
        self.assertEqual(by_index[0]["status"], "specified_assumption")  # P
        self.assertEqual(by_index[1]["status"], "specified_assumption")  # Q -- neither overwrites the other
        source, result = _certify(session, "Testv2.InspectionFixtures.conjunctionAssumption",
                                   "Testv2.InspectionFixtures", "VISTA.TestConjunction")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Lean's printer groups same-typed adjacent binders as "(P Q : Prop)"
        # rather than repeating "Prop" per binder -- both names must still
        # appear as genuine bound parameters of that exact type.
        self.assertIn("P Q : Prop", source)
        self.assertIn("P ∧ Q", source)  # h's own type preserved verbatim, never "P" or "Q" alone

    def test_case3_nat_dependency_never_becomes_prop(self):
        session = _session_for(
            "Testv2.InspectionFixtures.natDependentPredicate", "Testv2.InspectionFixtures", [],
        )
        premise_id = next(nid for nid, n in session.value["nodes"].items() if n["kind"] == "premise")
        session.accept_assumption(premise_id=premise_id, rationale="test")
        by_index = {int(n["binder_path"]): n for n in session.value["nodes"].values()}
        self.assertEqual(by_index[0]["pretty_type"], "Nat")
        self.assertFalse(by_index[0]["is_prop_sort"])
        self.assertEqual(by_index[0]["status"], "unresolved")  # x -- never coerced to specified_assumption
        self.assertEqual(session.status, "blocked_on_premise")  # x still blocks certification
        with self.assertRaises(ManifestError):
            generate_certificate_source(
                session=session.value, entrypoint="Testv2.InspectionFixtures.natDependentPredicate",
                namespace="VISTA.TestCase3", entry_modules=["Testv2.InspectionFixtures"],
                project_root=PROJECT, trusted_local=True, timeout_s=120,
            )

    def test_case4_type_sorted_parameter_never_becomes_prop(self):
        session = _session_for(
            "Testv2.InspectionFixtures.typeDependentPredicate", "Testv2.InspectionFixtures", [],
        )
        premise_id = next(nid for nid, n in session.value["nodes"].items() if n["kind"] == "premise")
        session.accept_assumption(premise_id=premise_id, rationale="test")
        by_index = {int(n["binder_path"]): n for n in session.value["nodes"].values()}
        self.assertEqual(by_index[0]["pretty_type"], "Type")  # alpha
        self.assertFalse(by_index[0]["is_prop_sort"])
        self.assertEqual(by_index[0]["status"], "unresolved")
        self.assertEqual(by_index[1]["status"], "unresolved")  # x : alpha
        self.assertEqual(session.status, "blocked_on_premise")


@unittest.skipUnless(_HAS_LEAN, _SKIP_REASON)
class GeneratedCertificateAxiomAuditTests(unittest.TestCase):
    """Issue C: only the GENERATED certificate's own axiom closure gates
    certification -- an adapter-provided value that depends on a custom
    axiom must be caught even though the entrypoint theorem is clean."""

    def test_adapter_injected_axiom_blocks_certification(self):
        poisoned = FormalBindingCandidate(
            key="n", lean_expr="Testv2.AxiomAdversarial.poisonedValue", provenance="artifact_grounded",
            evidence_refs=("a",), display_label="n",
        )
        session = _session_for(
            "Testv2.AxiomAdversarial.cleanEntrypoint", "Testv2.AxiomAdversarial", [poisoned],
        )
        self.assertEqual(session.status, "ready_for_certificate")
        source, result = _certify(session, "Testv2.AxiomAdversarial.cleanEntrypoint",
                                   "Testv2.AxiomAdversarial", "VISTA.TestAxiomAdversarial")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)  # compiles fine
        certificate_axioms = parse_certificate_axiom_closure(result.stdout + result.stderr)
        self.assertIn("Testv2.AxiomAdversarial.MyCustomAxiom", certificate_axioms)
        entrypoint_axioms = inspect_declarations(
            project_root=PROJECT, imports=["Testv2.AxiomAdversarial"],
            declarations=["Testv2.AxiomAdversarial.cleanEntrypoint"], trusted_local=True, timeout_s=120,
        )["Testv2.AxiomAdversarial.cleanEntrypoint"]["axioms"]
        self.assertNotIn("Testv2.AxiomAdversarial.MyCustomAxiom", entrypoint_axioms)  # entrypoint itself is clean
        with self.assertRaises(ManifestError):
            assemble_certificate_report(
                session=session.value, package={"axiom_policy": {"additional_allowed": []}},
                entrypoint="Testv2.AxiomAdversarial.cleanEntrypoint", certificate_source=source,
                entrypoint_axiom_closure=entrypoint_axioms, certificate_axiom_closure=certificate_axioms,
                allowed_axioms=ALLOWED_AXIOMS,
            )

    def test_explicitly_allowing_the_custom_axiom_permits_certification(self):
        poisoned = FormalBindingCandidate(
            key="n", lean_expr="Testv2.AxiomAdversarial.poisonedValue", provenance="artifact_grounded",
            evidence_refs=("a",), display_label="n",
        )
        session = _session_for(
            "Testv2.AxiomAdversarial.cleanEntrypoint", "Testv2.AxiomAdversarial", [poisoned],
        )
        source, result = _certify(session, "Testv2.AxiomAdversarial.cleanEntrypoint",
                                   "Testv2.AxiomAdversarial", "VISTA.TestAxiomAllowed")
        certificate_axioms = parse_certificate_axiom_closure(result.stdout + result.stderr)
        report = assemble_certificate_report(
            session=session.value, package={"axiom_policy": {"additional_allowed": ["Testv2.AxiomAdversarial.MyCustomAxiom"]}},
            entrypoint="Testv2.AxiomAdversarial.cleanEntrypoint", certificate_source=source,
            entrypoint_axiom_closure=[], certificate_axiom_closure=certificate_axioms,
            allowed_axioms=ALLOWED_AXIOMS | {"Testv2.AxiomAdversarial.MyCustomAxiom"},
        )
        self.assertEqual(report["status"], "certified")


if __name__ == "__main__":
    unittest.main()
