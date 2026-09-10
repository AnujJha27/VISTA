-- MACHINE-VERIFIED: imported by `Testv2.lean`, builds under `lake build`. See
-- docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md.
import Mathlib.Data.Matrix.Basis
import Mathlib.LinearAlgebra.Matrix.Symmetric
import Mathlib.Data.Real.Basic

/-! The generic real-matrix facts behind `canRepresentNonLocal`/
    `guaranteedSelfAdjoint` (`Testv2.StructuralV2`) for the `symmetrized`
    (`B + Bᵀ`) recipe: `B + Bᵀ` is symmetric for every real `B`, and for
    `n ≥ 2` some real `B` makes it non-local. The finite `OperatorForm`
    grammar's `Bool` functions are computable stand-ins for these
    statements over actual matrices. -/
namespace Testv2.StructuralCapabilityMatrix

open Matrix

/-- `B + Bᵀ` is symmetric for every real `B` -- backs `symmetrized`'s
    `guaranteedSelfAdjoint = true`. Restated under this repo's own name
    (Mathlib: `Matrix.isSymm_add_transpose_self`) so certificate provenance
    doesn't depend on an upstream lemma name we don't control. -/
theorem symmetrized_is_symm {n : ℕ} (B : Matrix (Fin n) (Fin n) ℝ) :
    (B + Bᵀ).IsSymm :=
  Matrix.isSymm_add_transpose_self B

/-- For `n ≥ 2`, some real `B` makes `B + Bᵀ` non-local -- backs
    `symmetrized`'s `canRepresentNonLocal = true`. Witness: `B` with a
    single `1` at `(0, 1)`, so `(B + Bᵀ) 0 1 = 1 ≠ 0`. -/
theorem symmetrized_can_be_nonlocal {n : ℕ} (h : 2 ≤ n) :
    ∃ B : Matrix (Fin n) (Fin n) ℝ, ∃ i j : Fin n, i ≠ j ∧ (B + Bᵀ) i j ≠ 0 := by
  have h0 : 0 < n := by omega
  have h1 : 1 < n := by omega
  refine ⟨Matrix.single (⟨0, h0⟩ : Fin n) (⟨1, h1⟩ : Fin n) (1 : ℝ), ⟨0, h0⟩, ⟨1, h1⟩, ?_, ?_⟩
  · simp [Fin.ext_iff]
  · have hij : ¬((⟨0, h0⟩ : Fin n) = ⟨1, h1⟩ ∧ (⟨1, h1⟩ : Fin n) = ⟨0, h0⟩) := by
      simp [Fin.ext_iff]
    simp [Matrix.add_apply, Matrix.transpose_apply, Matrix.single_apply, hij]

end Testv2.StructuralCapabilityMatrix
