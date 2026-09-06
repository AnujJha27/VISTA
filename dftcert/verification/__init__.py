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

    package = VerificationPackageBuilder(
        lean_project="examples/dft/lean", entrypoints=[...],
        adapter=DFT_CAPABILITY_PLUGIN, interface_contract={...},
    )
    package.write("vista-package.json")

    session = start_session(
        artifact="model.pt2", package="vista-package.json",
        session="session.json", project="examples/dft/lean", trusted_local=True,
    )
    for premise in session.unresolved_premises:
        session.accept_assumption(premise_id=premise["id"], rationale="...")

    certify_session(
        session="session.json", package="vista-package.json", project="examples/dft/lean",
        lean_import="Testv2.Requirements", output_dir="build/vista/certificate", trusted_local=True,
    )
"""
from __future__ import annotations

from .package import VerificationPackageBuilder

__all__ = ["VerificationPackageBuilder", "start_session", "resume_session", "certify_session"]

# `dftcert.verification.api` imports `dftcert.structural.dft_capability_plugin`,
# which itself imports `dftcert.verification.model` -- importing `api` eagerly
# here would deadlock whichever side is mid-import first. Lazy attribute
# access (PEP 562) defers it until an attribute is actually used, by which
# point both packages have finished initializing.
def __getattr__(name: str):
    if name in {"start_session", "resume_session", "certify_session"}:
        from . import api
        return getattr(api, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
