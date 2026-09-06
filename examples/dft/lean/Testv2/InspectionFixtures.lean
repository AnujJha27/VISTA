/-! Tiny fixtures for `dftcert.verification.lean_inspect` tests (spec section
27.2): one declaration per binder-kind combination the inspector must report
structurally, never by parsing pretty-printed text. Deliberately not
`VISTA`-annotated -- ordinary Lean, imported by fully-qualified name only. -/
namespace Testv2.InspectionFixtures

/-- Two explicit `Nat` binders with the same type -- exactly the case
    Python-side name/type-string matching would get wrong (spec section 11). -/
def sumOfTwoNats (siteCount depth : Nat) : Nat := siteCount + depth

/-- Explicit, implicit, instance-implicit, and a dependent binder together. -/
def dependentExample {n : Nat} [DecidableEq Nat] (site : Fin (n + 1)) (label : String) : Bool :=
  label.length == site.val

theorem sumOfTwoNats_comm (siteCount depth : Nat) :
    sumOfTwoNats siteCount depth = sumOfTwoNats depth siteCount := by
  unfold sumOfTwoNats; omega

/-- A proposition binder alongside data binders -- the shape a real
    verification-entrypoint theorem premise takes. -/
theorem propositionBinderExample (n : Nat) (hpos : n > 0) : n ≥ 1 := hpos

/-- Depends on a helper lemma (`sumOfTwoNats_comm`) -- exercises dependency
    closure without treating the helper itself as a requirement. -/
theorem usesHelperLemma (a b : Nat) : sumOfTwoNats a b = sumOfTwoNats b a :=
  sumOfTwoNats_comm a b

end Testv2.InspectionFixtures
