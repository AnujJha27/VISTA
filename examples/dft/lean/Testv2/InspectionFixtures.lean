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

/-- Implicit `{n}`, instance-implicit `[DecidableEq Nat]`, and an explicit
    dependent binder together (theorem-centric-gaps issue 6): the resolver
    must synthesize the instance via Lean's own typeclass resolution
    (never offering it an artifact candidate), and must resolve `n`
    transitively via the unification triggered by elaborating `site`'s own
    candidate -- never by directly offering `n` an artifact candidate
    itself (an implicit non-instance binder is a type-level parameter, not
    an artifact-data slot). -/
theorem implicitBinderExample {n : Nat} [DecidableEq Nat] (site : Fin n) : True :=
  trivial

/-- Two independent `Prop`-sorted data binders and one premise depending on
    only the first (theorem-centric-gaps issue 8): accepting `hP` as an
    explicit assumption must resolve/associate `P` only, never `Q` -- a
    same-entrypoint/`pretty_type == "Prop"` heuristic would get this wrong
    (it can't distinguish `P` from `Q`). -/
theorem twoIndependentPropParameters (P Q : Prop) (hP : P) : P :=
  hP

/-- CASE 2 (theorem-centric-gaps issue B): a premise depending on BOTH of
    two `Prop` parameters. Accepting `h` must preserve its EXACT type
    `P ∧ Q` on the generated certificate -- never collapse it to `P` or
    `Q` alone, and never drop either companion binder. -/
theorem conjunctionAssumption (P Q : Prop) (h : P ∧ Q) : P ∧ Q :=
  h

/-- A predicate over a plain `Nat` -- deliberately NOT a `Prop`-sorted
    parameter itself. -/
def SomePredicate (n : Nat) : Prop := n > 0

/-- CASE 3 (theorem-centric-gaps issue B): `x`'s own type is `Nat`, not
    `Prop`. If `x` is never separately resolved, accepting `h` must NOT
    turn `x` into a free `Prop` parameter -- certification must stay
    blocked on `x` regardless of what happens to `h`. -/
theorem natDependentPredicate (x : Nat) (h : SomePredicate x) : True :=
  trivial

/-- A predicate over an arbitrary type -- exercises that a genuinely
    unresolvable `Type`-sorted parameter is never coerced into anything. -/
def GenericProperty {α : Type} (x : α) : Prop := True

/-- CASE 4 (theorem-centric-gaps issue B): must fail closed unless Lean
    can genuinely resolve `α` and `x` -- neither is `Prop`-sorted, so
    accepting `h` must never touch either. -/
theorem typeDependentPredicate {α : Type} (x : α) (h : GenericProperty x) : True :=
  trivial

/-- theorem-centric-gaps issue A acceptance test #5: explicit + implicit +
    instance-implicit + a second explicit binder together, in a genuine
    `theorem` (not just a `def`), so certificate generation (not just
    binder resolution) can be exercised end to end. -/
theorem mixedBinderCertificateExample {n : Nat} [DecidableEq Nat] (site : Fin n) (extra : Nat) :
    extra = extra :=
  rfl

end Testv2.InspectionFixtures
