import Testv2.StructuralV2

/-! First theorem-centric verification entrypoints for the DFT domain
(`VISTA_THEOREM_CENTRIC_CODEX_SPEC.md` section 20.3). Ordinary Lean
theorems, no VISTA-specific annotations, no `axiom`/`sorry`: a theorem's
elaborated binder telescope IS the requirement the theorem-centric resolver
reads back via `dftcert.verification.lean_inspect`.

`allPairsReachable` is deliberately its own entrypoint
(`ValidMessagePassingCoverage`), not folded into `AcceptableArchitecture`:
none of the operator-construction recipes `DFTCapabilityPlugin` currently
recognizes (bare or symmetrized parameters) depend on message passing at
all, so a combined requirement would force an inapplicable premise onto
every artifact this project can currently certify. Keeping them separate
also means message-passing depth alone can never change the operator
capacity result below -- they are unrelated statements about unrelated
things (GNN receptive field vs. the operator the architecture represents)
unless a future theorem explicitly links them.

PROVISIONAL LOCALITY NOTE (research-soundness correction): `siteCount` and
`op` are artifact-grounded facts, but which pairs of sites the underlying
physics actually considers "long-range" is not something this theory or
the artifact can determine on its own -- it is a `specified_interface` fact
the verification package supplies as `longRangePairs`. `AcceptableArchitecture`
below checks structural self-adjointness and whether the operator can
represent coupling on at least one of those SUPPLIED pairs; it does not,
and cannot, establish that the supplied pairs are the physically correct
notion of long-range coupling for this domain. That physical definition
remains provisional pending domain-expert confirmation -- see
`Testv2.StructuralV2.canRepresentLongRangeCoupling`'s own docstring and
`docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md`. -/

namespace Testv2.Requirements

open Testv2.StructuralV2

/-- The pre-training structural requirement: a self-adjoint operator with
    the representational capacity for coupling on at least one explicitly
    specified long-range site pair, fed by an XC construction compatible
    with the discontinuity DFT's exact exchange-correlation functional
    must exhibit. `longRangePairs` is a `specified_interface` fact, never
    artifact-grounded -- see the module docstring's provisional locality
    note. -/
def AcceptableArchitecture
    (siteCount : Nat) (longRangePairs : LongRangePairs)
    (op : OperatorForm) (xc : XCForm) : Prop :=
  guaranteedSelfAdjoint op = true ∧
  canRepresentLongRangeCoupling siteCount longRangePairs op = true ∧
  xcSupportsDiscontinuity xc = true

theorem ValidPretrainingArchitecture
    (siteCount : Nat) (longRangePairs : LongRangePairs) (op : OperatorForm) (xc : XCForm)
    (hSA : guaranteedSelfAdjoint op = true)
    (hLR : canRepresentLongRangeCoupling siteCount longRangePairs op = true)
    (hXC : xcSupportsDiscontinuity xc = true) :
    AcceptableArchitecture siteCount longRangePairs op xc :=
  ⟨hSA, hLR, hXC⟩

/-- Same structural requirement, plus one premise that is deliberately not
    formalizable from any artifact fact or this theory: `TargetRequiresLongRangeCoupling`
    is a genuine `Prop`-sorted binder (never a global `axiom`), so the resolver
    can only ever discharge it as an explicit external assumption -- it
    stays a binder on the generated certificate theorem, never gets
    silently proved or axiomatized (spec section 13). -/
theorem ValidPretrainingArchitectureConditional
    (siteCount : Nat) (longRangePairs : LongRangePairs) (op : OperatorForm) (xc : XCForm)
    (TargetRequiresLongRangeCoupling : Prop)
    (hSA : guaranteedSelfAdjoint op = true)
    (hLR : canRepresentLongRangeCoupling siteCount longRangePairs op = true)
    (hXC : xcSupportsDiscontinuity xc = true)
    (hPhysical : TargetRequiresLongRangeCoupling) :
    AcceptableArchitecture siteCount longRangePairs op xc :=
  ⟨hSA, hLR, hXC⟩

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
