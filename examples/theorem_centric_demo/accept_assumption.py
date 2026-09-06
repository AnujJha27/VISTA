#!/usr/bin/env python3
"""Accept the one explicit assumption this demo's conditional entrypoint
needs -- `TargetRequiresNonLocality`, a genuine `Prop`-sorted binder that no
artifact fact or formal theory could ever establish on its own (see the
README). Writes the decision into the package file itself (spec/theorem-
centric-gaps issue E), the same normalized state a binding choice gets.

Run from the repository root, after `vista verify start` reports
`blocked_on_premise`:

    python examples/theorem_centric_demo/accept_assumption.py
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dftcert.verification import resume_session  # noqa: E402
from dftcert.verification.package import add_external_assumption  # noqa: E402


def main() -> None:
    session = resume_session(str(HERE / "session.json"))
    premise = session.unresolved_premises[0]
    print(f"accepting {premise['id']} : {premise['pretty_type']}")
    add_external_assumption(
        HERE / "vista-package.json", premise_id=premise["id"],
        proposition_fingerprint=premise["type_fingerprint"],
        rationale="the target architecture is understood to require non-local self-energy support",
    )
    print("recorded in vista-package.json -- re-run `vista verify start` to apply it")


if __name__ == "__main__":
    main()
