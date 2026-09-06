#!/usr/bin/env python3
"""Build the verification package for this demo -- the one Python step in
the workflow the CLI itself doesn't cover (`VerificationPackageBuilder` is
a public class, not yet a CLI subcommand). Uses only the public
`dftcert.verification` API described in `dftcert/verification/__init__.py`'s
module docstring.

Run from the repository root:

    python examples/theorem_centric_demo/build_package.py
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
ENTRYPOINT = "Testv2.Requirements.ValidPretrainingArchitectureConditional"


def main() -> None:
    interface_contract = json.loads((HERE / "interface_contract.json").read_text(encoding="utf-8"))
    package_sha256 = VerificationPackageBuilder(
        lean_project=LEAN_PROJECT,
        entrypoints=[ENTRYPOINT],
        adapter=DFT_CAPABILITY_PLUGIN,
        interface_contract=interface_contract,
        # siteCount resolves unaided against this fixture's real adjacency
        # buffer; this binding_choice is included anyway to show the
        # authoring shape -- see the README's "resolve an ambiguity" note.
        binding_choices=[{"entrypoint": ENTRYPOINT, "binder_path": "0", "candidate_key": "site_count"}],
    ).write(HERE / "vista-package.json")
    print(f"wrote {HERE / 'vista-package.json'} (package_sha256={package_sha256})")


if __name__ == "__main__":
    main()
