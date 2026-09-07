"""VISTA theorem-centric verification: package/session data model, Lean
introspection, binding resolution, and certificate assembly. See
`VISTA_THEOREM_CENTRIC_CODEX_SPEC.md`.

The generic structural harness (`dftcert.structural`) stays domain-agnostic
and pre-training-only; this package adds a theorem-centric path alongside
it without replacing it (`dftcert.structural.cli`'s existing `structural`
commands keep working unchanged).

Public author-facing API (spec/theorem-centric-gaps issue 14) -- `vista
verify`'s CLI calls these same functions, never a second implementation:

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

    # An explicit external assumption is authored into the PACKAGE, not the
    # session (research-readiness audit issue 2: `VerificationSession.
    # accept_assumption` is a session-local/exploratory decision only --
    # it can never by itself make a target certifiable). Re-deriving the
    # session from the now-changed package is what actually applies it,
    # exactly like a binding choice.
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
        output_dir="build/vista/certificate", trusted_local=True,
    )

The defensible claim this package establishes: VISTA checks whether
artifact-grounded structural facts are sufficient to establish selected
Lean requirements under explicit interface and external assumptions --
never that Lean verifies the model itself, and never that an accepted
external assumption has thereby been proven true (it remains a free
binder on the generated certificate theorem, exactly as recorded).

Trust boundary, by node/fact provenance:

    EXTRACTED           exact artifact hash, graph/state facts directly
                        from safe extraction (`dftcert.sandbox`/
                        `extractors.torch_export_worker`) -- unless the
                        caller passed `trusted_local=True` with an
                        already-produced extraction result (no Bubblewrap
                        sandbox, no real artifact bytes read for this
                        session at all), in which case these facts are
                        only as trustworthy as that JSON file the caller
                        supplied; VISTA re-derives the IR *from* it but has
                        no way to independently confirm the file itself
                        came from genuine artifact bytes (see
                        `docs/verification/TRUST_CHAIN_AUDIT.md` section 2's
                        trusted-local row).
    INFERRED / DERIVED  adapter semantic classifications (`artifact_
                        grounded` nodes) recomputed from extracted
                        evidence, independently revalidated against it.
    SPECIFIED INTERFACE output roles/layout/semantic interpretation
                        supplied by the package's `interface_contract`.
    SPECIFIED ASSUMPTION a theorem premise explicitly accepted by a user/
                        domain expert (`specified_assumption` nodes) --
                        stays a real binder on the certificate, never an
                        `axiom`.
    FORMALLY CHECKED    Lean elaboration/kernel checking: theorem
                        introspection, premise discharge
                        (`formally_discharged`), the generated certificate
                        theorem itself.
    UNVERIFIED          any physical/modeling claim outside those explicit
                        theorem premises -- this package makes no claim
                        about it at all.
"""
from __future__ import annotations

from .package import VerificationPackageBuilder

__all__ = [
    "VerificationPackageBuilder", "start_session", "resume_session", "certify_session",
    "verify_certificate_bundle",
]

# `dftcert.verification.api` imports `dftcert.structural.dft_capability_plugin`,
# which itself imports `dftcert.verification.model` -- importing `api` eagerly
# here would deadlock whichever side is mid-import first. Lazy attribute
# access (PEP 562) defers it until an attribute is actually used, by which
# point both packages have finished initializing.
def __getattr__(name: str):
    if name in {"start_session", "resume_session", "certify_session", "verify_certificate_bundle"}:
        from . import api
        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
