"""Primary Structural V3 certification architecture (domain-agnostic harness
+ pluggable domains; see VISTA_GENERALIZATION.md). `dft_plugin.DFT_PLUGIN` is
the default plugin every harness function uses unless another is passed."""

from .core import (
    assemble_structural_certificate,
    assess_structural_ir,
    confirmed_description_ir,
    generate_structural_obligations,
    structural_ir_from_inventory,
    structural_failure_witnesses,
    structural_report,
    validate_translation,
    verify_structural_certificate,
)
from .dft_plugin import DFT_PLUGIN, DFTPlugin
from .plugin import StructuralPlugin

__all__ = [
    "assemble_structural_certificate",
    "assess_structural_ir",
    "confirmed_description_ir",
    "generate_structural_obligations",
    "structural_ir_from_inventory",
    "structural_failure_witnesses",
    "structural_report",
    "validate_translation",
    "verify_structural_certificate",
    "DFT_PLUGIN",
    "DFTPlugin",
    "StructuralPlugin",
]
