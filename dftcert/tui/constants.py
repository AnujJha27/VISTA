from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_POLICY = ROOT / "policies/dft-architecture-v1.json"
DEFAULT_HYPOTHESIS = (
    "A DFT architecture with an XC derivative discontinuity, nonlocal spatial "
    "coupling, and a self-adjoint learned self-energy operator."
)
EXAMPLES = {
    "pass": (
        "A DFT architecture with an XC derivative discontinuity at an "
        "electron-number boundary, nonlocal spatial coupling, and a "
        "self-adjoint learned self-energy operator."
    ),
    "missing": (
        "The proposed model is nonlocal and uses message passing to propagate "
        "density information across sites, but it does not specify "
        "self-adjointness or the XC derivative discontinuity."
    ),
    "violation": (
        "The architecture has an XC derivative discontinuity and nonlocal "
        "coupling, but the learned self-energy operator is explicitly "
        "non-self-adjoint."
    ),
    "gap": (
        "The hypothesis proposes a rotationally equivariant DFT architecture "
        "with self-adjoint Fourier-space kernels and a long-range nonlocal "
        "receptive field."
    ),
}
