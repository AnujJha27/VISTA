/-! The selected entrypoint theorem is completely clean, but a value an
adapter/candidate might resolve a binder to depends on a custom axiom. VISTA
must reject certification because the *generated certificate's own* axiom
closure contains it -- checking only the entrypoint's closure would miss this. -/
namespace Testv2.AxiomAdversarial

axiom MyCustomAxiom : Nat

/-- Depends on `MyCustomAxiom` -- never referenced by `cleanEntrypoint`
    itself, only by a value a test resolves one of its binders to. -/
noncomputable def poisonedValue : Nat := MyCustomAxiom

/-- The selected entrypoint: clean on its own (only `propext`, if that,
    in its closure). -/
theorem cleanEntrypoint (n : Nat) (h : n = n) : n = n := h

end Testv2.AxiomAdversarial
