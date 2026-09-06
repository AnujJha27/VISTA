"""VISTA theorem-centric verification: package/session data model, Lean
introspection, binding resolution, and certificate assembly. See
`VISTA_THEOREM_CENTRIC_CODEX_SPEC.md`.

The generic structural harness (`dftcert.structural`) stays domain-agnostic
and pre-training-only; this package adds a theorem-centric path alongside
it without replacing it (`dftcert.structural.cli`'s existing `structural`
commands keep working unchanged).
"""
from __future__ import annotations
