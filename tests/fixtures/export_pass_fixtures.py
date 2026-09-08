"""One-time fixture generation for the final paper-oriented engineering pass
(needs a Python environment with the pinned `torch` installed -- this repo's
tests never generate `.pt2` fixtures at run time). Produces:

    tests/fixtures/unconstrained_operator.pt2
        `examples/dft/models/structural_gnns.UnconstrainedOperatorGNN` --
        the negative artifact for tests/test_self_adjoint_demo.py (operator
        = bare `base_operator`, not symmetrized -- `guaranteedSelfAdjoint`
        cannot be discharged) and for its forged-session adversarial
        regression.

    tests/fixtures/certified_ring_seed_a.pt2
    tests/fixtures/certified_ring_seed_b.pt2
        Same architecture (`CertifiedRingGNN`) exported twice with
        different `torch.manual_seed` calls -- i.e. different trainable
        `base_operator` initializations -- for
        tests/test_pretraining_scope.py's regression: different
        `artifact_sha256`, same structural classification/formal
        candidates, same verification result.

Run once from the repo root:

    python tests/fixtures/export_pass_fixtures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import torch

_MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "examples" / "dft" / "models"
sys.path.insert(0, str(_MODELS_DIR))
from structural_gnns import CertifiedRingGNN, UnconstrainedOperatorGNN  # noqa: E402

FIXTURES = Path(__file__).resolve().parent
EXAMPLE = (torch.randn(6, 1),)


def _export(model: torch.nn.Module, destination: Path) -> None:
    program = torch.export.export(model.eval(), EXAMPLE)
    torch.export.save(program, destination)
    print(destination)


def main() -> int:
    torch.manual_seed(20260905)  # matches examples/dft/models/export_structural_gnns.py
    _export(UnconstrainedOperatorGNN(), FIXTURES / "unconstrained_operator.pt2")

    torch.manual_seed(1)
    _export(CertifiedRingGNN(), FIXTURES / "certified_ring_seed_a.pt2")

    torch.manual_seed(2)
    _export(CertifiedRingGNN(), FIXTURES / "certified_ring_seed_b.pt2")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
