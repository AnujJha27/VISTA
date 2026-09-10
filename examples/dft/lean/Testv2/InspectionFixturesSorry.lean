/-! A declaration that must be rejected by the axiom/`sorry` audit. Kept out of
`Testv2.lean`'s aggregator import list so the project's normal build stays free
of `sorry` warnings; introspection tests import it by module name directly. -/
namespace Testv2.InspectionFixturesSorry

theorem viaSorry (n : Nat) : n = n := by sorry

end Testv2.InspectionFixturesSorry
