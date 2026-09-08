-- MACHINE-VERIFIED: this file is imported by `Testv2.lean` and builds
-- cleanly under `lake build` (Lean v4.31.0 / Mathlib v4.31.0). Two prior
-- blockers, both now fixed, are kept here for history: (1) a stale local
-- `lake-manifest.json` had drifted out of sync with `lakefile.toml`'s
-- already-correct `rev = "v4.31.0"` pin, misdiagnosed as a toolchain/Mathlib
-- version mismatch -- `lake update` against the unchanged v4.31.0 toolchain
-- fixed it; (2) the doc comment immediately above `namespace
-- Testv2.StructuralCapabilityMatrix` used `/-- -/` (declaration-doc syntax,
-- only valid before a `def`/`theorem`/etc.), which the parser rejected --
-- changed to `/-! -/` (module/section-doc syntax), which `namespace`
-- accepts. See docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md.
import Mathlib.Data.Matrix.Basis
import Mathlib.LinearAlgebra.Matrix.Symmetric
import Mathlib.Data.Real.Basic

/-! The generic real-matrix facts behind `canRepresentNonLocal`/
    `guaranteedSelfAdjoint` (`Testv2.StructuralV2`) for the `symmetrized`
    (`B + Bᵀ`) operator recipe: for *every* real matrix `B`, `B + Bᵀ` is
    symmetric, and for `n ≥ 2` *some* real matrix `B` makes `B + Bᵀ` actually
    non-local (a genuine nonzero off-diagonal entry). `canRepresentNonLocal`/
    `guaranteedSelfAdjoint` only need to answer this for the finite
    `OperatorForm` grammar the analyzer emits (as computable `Bool`
    functions); these two theorems are the underlying statement over actual
    matrices that grammar is standing in for. -/
namespace Testv2.StructuralCapabilityMatrix

open Matrix

/-- `B + Bᵀ` is symmetric for every real matrix `B` -- the guarantee behind
    the `symmetrized` recipe's `guaranteedSelfAdjoint = true`. Already in
    Mathlib as `Matrix.isSymm_add_transpose_self`; restated here under this
    project's own name so the certificate's provenance points at a
    statement this repo owns, not just an upstream lemma name that could be
    renamed independently of any change here. -/
theorem symmetrized_is_symm {n : ℕ} (B : Matrix (Fin n) (Fin n) ℝ) :
    (B + Bᵀ).IsSymm :=
  Matrix.isSymm_add_transpose_self B

/-- For `n ≥ 2`, some real matrix `B` makes `B + Bᵀ` non-local: the guarantee
    behind the `symmetrized` recipe's `canRepresentNonLocal = true`. Witness:
    `B = Matrix.single 0 1 1` (all zero except a `1` at `(0, 1)`), so
    `(B + Bᵀ) 0 1 = 1 ≠ 0`. -/
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
