"""VISTA theorem-centric verification: package/session data model, Lean
introspection, binding resolution, and certificate assembly, alongside
(not replacing) the domain-agnostic `dftcert.structural` harness.

    from dftcert.verification import (
        VerificationPackageBuilder, start_session, resume_session, certify_session,
    )
    from dftcert.verification.package import add_external_assumption

    package = VerificationPackageBuilder(
        lean_project="examples/dft/lean", entrypoints=[...],
        adapter=DFT_CAPABILITY_PLUGIN, interface_contract={...},
    )
    package.write("vista-package.json")

    session = start_session(
        artifact="model.pt2", package="vista-package.json",
        session="session.json", project="examples/dft/lean", trusted_local=True,
    )

    # External assumptions are authored into the PACKAGE, not the session:
    # `VerificationSession.accept_assumption` is session-local/exploratory
    # and can never by itself make a target certifiable.
    for premise in session.unresolved_premises:
        add_external_assumption(
            "vista-package.json", premise_id=premise["id"],
            proposition_fingerprint=premise["type_fingerprint"], rationale="...",
        )
    session = start_session(
        artifact="model.pt2", package="vista-package.json",
        session="session.json", project="examples/dft/lean", trusted_local=True,
    )

    certify_session(
        session="session.json", package="vista-package.json", project="examples/dft/lean",
        output_dir="build/vista/certificate", artifact="model.pt2", trusted_local=True,
    )

The claim VISTA establishes: artifact-grounded structural facts are
sufficient to establish selected Lean requirements under explicit interface
and external assumptions -- never that Lean verifies the model itself, and
an accepted assumption stays a free binder on the certificate, never proven.

Trust boundary, by node/fact provenance:

    EXTRACTED            artifact hash, graph/state facts from safe
                          extraction -- or, under trusted_local=True with a
                          pre-produced extraction result, only as
                          trustworthy as that JSON file itself.
    INFERRED / DERIVED   adapter semantic classifications recomputed from
                          extracted evidence.
    SPECIFIED INTERFACE  output roles/layout supplied by the package's
                          `interface_contract`.
    SPECIFIED ASSUMPTION  a premise explicitly accepted by a domain expert,
                          staying a real certificate binder, never an axiom.
    FORMALLY CHECKED      Lean elaboration/kernel checking.
    UNVERIFIED            any claim outside those explicit theorem
                          premises -- no claim made about it at all.
"""
from __future__ import annotations

from .package import VerificationPackageBuilder

__all__ = [
    "VerificationPackageBuilder", "start_session", "resume_session", "certify_session",
    "verify_certificate_bundle",
]

# Lazy (PEP 562): eagerly importing `api` here would deadlock against
# `dftcert.structural.dft_capability_plugin`'s import of this package.
def __getattr__(name: str):
    if name in {"start_session", "resume_session", "certify_session", "verify_certificate_bundle"}:
        from . import api
        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
