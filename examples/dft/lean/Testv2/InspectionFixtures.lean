/-! Tiny fixtures for `dftcert.verification.lean_inspect` tests: one declaration
per binder-kind combination the inspector must report structurally, never by
parsing pretty-printed text. Deliberately not `VISTA`-annotated -- ordinary
Lean, imported by fully-qualified name only. -/
namespace Testv2.InspectionFixtures

/-- Two explicit `Nat` binders with the same type -- the case name/type-string matching would get wrong. -/
def sumOfTwoNats (siteCount depth : Nat) : Nat := siteCount + depth

/-- Explicit, implicit, instance-implicit, and a dependent binder together. -/
def dependentExample {n : Nat} [DecidableEq Nat] (site : Fin (n + 1)) (label : String) : Bool :=
  label.length == site.val

theorem sumOfTwoNats_comm (siteCount depth : Nat) :
    sumOfTwoNats siteCount depth = sumOfTwoNats depth siteCount := by
  unfold sumOfTwoNats; omega

/-- A proposition binder alongside data binders, the shape a real verification-entrypoint premise takes. -/
theorem propositionBinderExample (n : Nat) (hpos : n > 0) : n ≥ 1 := hpos

/-- Depends on helper lemma `sumOfTwoNats_comm` -- exercises dependency closure without treating the helper as a requirement. -/
theorem usesHelperLemma (a b : Nat) : sumOfTwoNats a b = sumOfTwoNats b a :=
  sumOfTwoNats_comm a b

/-- Implicit `{n}`, instance-implicit `[DecidableEq Nat]`, and an explicit dependent binder:
    the resolver must synthesize the instance via Lean's own typeclass resolution (never an
    artifact candidate) and resolve `n` transitively via `site`'s own candidate. -/
theorem implicitBinderExample {n : Nat} [DecidableEq Nat] (site : Fin n) : True :=
  trivial

/-- Two independent `Prop` binders and a premise depending on only the first: accepting `hP`
    must associate `P` only, never `Q` -- a `pretty_type == "Prop"` heuristic can't tell them apart. -/
theorem twoIndependentPropParameters (P Q : Prop) (hP : P) : P :=
  hP

/-- A premise depending on BOTH `Prop` parameters: accepting `h` must preserve its exact type
    `P ∧ Q` on the certificate, never collapse to `P` or `Q` alone. -/
theorem conjunctionAssumption (P Q : Prop) (h : P ∧ Q) : P ∧ Q :=
  h

/-- A predicate over a plain `Nat`, deliberately NOT a `Prop`-sorted parameter itself. -/
def SomePredicate (n : Nat) : Prop := n > 0

/-- `x`'s own type is `Nat`, not `Prop`: accepting `h` must never turn `x` into a free `Prop`
    parameter, so certification stays blocked on `x` regardless of `h`. -/
theorem natDependentPredicate (x : Nat) (h : SomePredicate x) : True :=
  trivial

/-- A predicate over an arbitrary type -- a genuinely unresolvable `Type`-sorted parameter must never be coerced. -/
def GenericProperty {α : Type} (x : α) : Prop := True

/-- Must fail closed unless Lean genuinely resolves `α` and `x` -- neither is `Prop`-sorted, so accepting `h` must never touch either. -/
theorem typeDependentPredicate {α : Type} (x : α) (h : GenericProperty x) : True :=
  trivial

/-- Explicit + implicit + instance-implicit + explicit binders in a genuine `theorem` (not a `def`),
    so certificate generation, not just binder resolution, is exercised end to end. -/
theorem mixedBinderCertificateExample {n : Nat} [DecidableEq Nat] (site : Fin n) (extra : Nat) :
    extra = extra :=
  rfl

end Testv2.InspectionFixtures
