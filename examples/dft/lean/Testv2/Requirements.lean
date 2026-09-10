import Testv2.StructuralV2

/-! Theorem-centric DFT entrypoints: ordinary Lean theorems, no VISTA
annotations, no `axiom`/`sorry` -- a theorem's binder telescope IS the
requirement `dftcert.verification.lean_inspect` reads back.

`allPairsReachable` gets its own entrypoint (`ValidMessagePassingCoverage`),
not folded into `AcceptableArchitecture`: no operator-construction recipe
`DFTCapabilityPlugin` recognizes depends on message passing, so combining
them would force an inapplicable premise on every certifiable artifact.

PROVISIONAL LOCALITY: `siteCount`/`edges`/`op` are artifact-grounded, but
"long-range" is not decidable from this theory alone. VISTA uses graph-hop
distance beyond a `specified_interface` range (`locality : LocalityRange`)
as a provisional definition; the long-range pair set is always DERIVED by
`canRepresentLongRangeCoupling` from `edges` and `locality`, never supplied.
This cannot establish that graph-hop distance is the physically correct
notion of long-range for this domain -- pending domain-expert confirmation.
See `Testv2.StructuralV2.canRepresentLongRangeCoupling` and
`docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md`. -/

namespace Testv2.Requirements

open Testv2.StructuralV2

/-- Pre-training requirement: a self-adjoint operator with capacity for
    coupling on some pair the graph-hop relation DERIVES as long-range, fed
    by a discontinuity-compatible XC form. `locality` (the range `R`) is
    `specified_interface`; the long-range relation itself is inferred, not
    supplied -- see the module docstring. -/
def AcceptableArchitecture
    (siteCount : Nat) (edges : List (Nat × Nat)) (locality : LocalityRange)
    (op : OperatorForm) (xc : XCForm) : Prop :=
  guaranteedSelfAdjoint op = true ∧
  canRepresentLongRangeCoupling siteCount edges locality op = true ∧
  xcSupportsDiscontinuity xc = true

theorem ValidPretrainingArchitecture
    (siteCount : Nat) (edges : List (Nat × Nat)) (locality : LocalityRange)
    (op : OperatorForm) (xc : XCForm)
    (hSA : guaranteedSelfAdjoint op = true)
    (hLR : canRepresentLongRangeCoupling siteCount edges locality op = true)
    (hXC : xcSupportsDiscontinuity xc = true) :
    AcceptableArchitecture siteCount edges locality op xc :=
  ⟨hSA, hLR, hXC⟩

/-- Same requirement plus one premise not formalizable from any artifact
    fact: `TargetRequiresLongRangeCoupling` is a genuine `Prop` binder, not
    a global `axiom`, so it stays an explicit assumption on the generated
    certificate theorem, never silently discharged. -/
theorem ValidPretrainingArchitectureConditional
    (siteCount : Nat) (edges : List (Nat × Nat)) (locality : LocalityRange)
    (op : OperatorForm) (xc : XCForm)
    (TargetRequiresLongRangeCoupling : Prop)
    (hSA : guaranteedSelfAdjoint op = true)
    (hLR : canRepresentLongRangeCoupling siteCount edges locality op = true)
    (hXC : xcSupportsDiscontinuity xc = true)
    (hPhysical : TargetRequiresLongRangeCoupling) :
    AcceptableArchitecture siteCount edges locality op xc :=
  ⟨hSA, hLR, hXC⟩

/-- VISTA's minimal pre-training guarantee: self-adjointness of the
    recognized operator alone, no site-count/long-range/XC premises.
    `guaranteedSelfAdjoint` stands in for `B + Bᵀ` self-adjointness for any
    `B` (see `StructuralCapabilityMatrix.lean`). Kept independent of
    `AcceptableArchitecture` so this requirement can't force unrelated
    facts onto an artifact. -/
def SelfAdjointCompatible (op : OperatorForm) : Prop :=
  guaranteedSelfAdjoint op = true

theorem ValidSelfAdjointConstruction
    (op : OperatorForm) (hSA : guaranteedSelfAdjoint op = true) :
    SelfAdjointCompatible op :=
  hSA

/-- The message-passing receptive-field requirement, kept separate from
    `AcceptableArchitecture` -- see module docstring. -/
def MessagePassingCoverage (edges : List (Nat × Nat)) (depth siteCount : Nat) : Prop :=
  allPairsReachable edges depth siteCount = true

theorem ValidMessagePassingCoverage
    (edges : List (Nat × Nat)) (depth siteCount : Nat)
    (hCov : allPairsReachable edges depth siteCount = true) :
    MessagePassingCoverage edges depth siteCount :=
  hCov

end Testv2.Requirements
