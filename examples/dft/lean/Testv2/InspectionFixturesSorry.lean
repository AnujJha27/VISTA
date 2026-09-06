/-! A declaration that must be rejected by the axiom/`sorry` audit (spec
section 9/27.2). Kept out of `Testv2.lean`'s aggregator import list so the
project's normal build stays free of `sorry` warnings; the introspection
tests import it by module name directly, the same way a real verification
session would import any other project module on demand. -/
namespace Testv2.InspectionFixturesSorry

theorem viaSorry (n : Nat) : n = n := by sorry

end Testv2.InspectionFixturesSorry
