/-! A declaration's namespace need not match its module path: `Physics.ValidModel`
lives in `Testv2/AltModule.lean`, so a package must select it via an explicit
`entry_modules` override (`Testv2.AltModule`), never by splitting the
declaration name on its last dot. -/
namespace Physics

theorem ValidModel (n : Nat) (hpos : n > 0) : n ≥ 1 := hpos

end Physics
