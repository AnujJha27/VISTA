#!/usr/bin/env python3
"""Build the verification package for VISTA's own minimal, headline
example: structural self-adjointness alone (`Testv2.Requirements.
ValidSelfAdjointConstruction`), no site-count/long-range/XC/message-passing
premises. See README.md ("Minimal self-adjointness example") for what this
demonstrates and why it's deliberately smaller than
`examples/theorem_centric_demo` (the fuller DFT case study).

Run from the repository root:

    python examples/self_adjoint_demo/build_package.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT_ROOT = HERE.parents[1]
sys.path.insert(0, str(PROJECT_ROOT))  # run directly without a `pip install -e .` step

from dftcert.structural.dft_capability_plugin import DFT_CAPABILITY_PLUGIN  # noqa: E402
from dftcert.verification import VerificationPackageBuilder  # noqa: E402

LEAN_PROJECT = PROJECT_ROOT / "examples" / "dft" / "lean"
ENTRYPOINT = "Testv2.Requirements.ValidSelfAdjointConstruction"


def main() -> None:
    interface_contract = json.loads((HERE / "interface_contract.json").read_text(encoding="utf-8"))
    # No binding_choices needed: `op : OperatorForm` is this entrypoint's
    # only data binder, and exactly one candidate
    # (`formal_binding_candidates`'s `operator_form`) has that Lean type --
    # the resolver matches it unaided.
    package_sha256 = VerificationPackageBuilder(
        lean_project=LEAN_PROJECT, entrypoints=[ENTRYPOINT],
        adapter=DFT_CAPABILITY_PLUGIN, interface_contract=interface_contract,
    ).write(HERE / "vista-package.json")
    print(f"wrote {HERE / 'vista-package.json'} (package_sha256={package_sha256})")


if __name__ == "__main__":
    main()
