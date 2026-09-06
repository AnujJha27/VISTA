/-! Fixture for theorem-centric-gaps issue 13: a Lean declaration's
namespace need not match the module path Lean actually imports it from.
`Physics.ValidModel` lives here, in `Testv2/AltModule.lean` -- a package
selecting it must say so via an explicit `entry_modules` override
(`Testv2.AltModule`), never by splitting the declaration name on its last
dot (`Physics`, which does not exist as an importable module). -/
namespace Physics

theorem ValidModel (n : Nat) (hpos : n > 0) : n ≥ 1 := hpos

end Physics
