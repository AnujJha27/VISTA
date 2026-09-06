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
every artifact this project can currently certify. -/

namespace Testv2.Requirements

open Testv2.StructuralV2

/-- The pre-training structural requirement: a self-adjoint operator with
    the representational capacity for a non-local self-energy, fed by an
    XC construction compatible with the discontinuity DFT's exact
    exchange-correlation functional must exhibit. -/
def AcceptableArchitecture (siteCount : Nat) (op : OperatorForm) (xc : XCForm) : Prop :=
  guaranteedSelfAdjoint op = true ∧
  canRepresentNonLocal siteCount op = true ∧
  xcSupportsDiscontinuity xc = true

theorem ValidPretrainingArchitecture
    (siteCount : Nat) (op : OperatorForm) (xc : XCForm)
    (hSA : guaranteedSelfAdjoint op = true)
    (hNL : canRepresentNonLocal siteCount op = true)
    (hXC : xcSupportsDiscontinuity xc = true) :
    AcceptableArchitecture siteCount op xc :=
  ⟨hSA, hNL, hXC⟩

/-- Same structural requirement, plus one premise that is deliberately not
    formalizable from any artifact fact or this theory: `TargetRequiresNonLocality`
    is a genuine `Prop`-sorted binder (never a global `axiom`), so the resolver
    can only ever discharge it as an explicit external assumption -- it
    stays a binder on the generated certificate theorem, never gets
    silently proved or axiomatized (spec section 13). -/
theorem ValidPretrainingArchitectureConditional
    (siteCount : Nat) (op : OperatorForm) (xc : XCForm)
    (TargetRequiresNonLocality : Prop)
    (hSA : guaranteedSelfAdjoint op = true)
    (hNL : canRepresentNonLocal siteCount op = true)
    (hXC : xcSupportsDiscontinuity xc = true)
    (hPhysical : TargetRequiresNonLocality) :
    AcceptableArchitecture siteCount op xc :=
  ⟨hSA, hNL, hXC⟩

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
