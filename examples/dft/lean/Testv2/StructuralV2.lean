namespace Testv2.StructuralV2

inductive XCForm where
  | hinge
  | smooth
  | unsupported
deriving DecidableEq, Repr

inductive OperatorForm where
  | zero
  | identity
  | parameter (name : String)
  /-- A base term not positively confirmed to be a free/trainable
      parameter -- distinct from `.parameter` so `guaranteedSelfAdjoint`
      (holds for `base + base^T` regardless of `base`) and
      `canRepresentNonLocal` (needs an actual free parameter) can disagree:
      `opaque + adjoint opaque` is self-adjoint but has no off-diagonal
      freedom, same as `zero + adjoint zero`. -/
  | opaque (name : String)
  | adjoint (value : OperatorForm)
  | add (left right : OperatorForm)
  | unsupported
deriving DecidableEq, Repr

def xcSupportsDiscontinuity : XCForm → Bool
  | .hinge => true
  | .smooth => false
  | .unsupported => false

def guaranteedSelfAdjoint : OperatorForm → Bool
  | .zero => true
  | .identity => true
  | .add left (.adjoint right) => left == right
  | .add (.adjoint left) right => left == right
  | _ => false

def reachableWithin (edges : List (Nat × Nat)) : Nat → Nat → Nat → Bool
  | 0, source, target => source == target
  | depth + 1, source, target =>
      source == target || edges.any fun edge =>
        edge.1 == source && reachableWithin edges depth edge.2 target

/-- DEPRECATED: reachability for a hand-authored pair list only, superseded
    by `allPairsReachable`. Kept so frozen historical certificates stay
    re-checkable. -/
def allCovered (edges : List (Nat × Nat)) (depth : Nat)
    (requirements : List (Nat × Nat)) : Bool :=
  requirements.all fun coupling =>
    reachableWithin edges depth coupling.1 coupling.2

/-- Every ordered pair of distinct sites is reachable within the declared
    message-passing depth -- topology and depth alone, never extracted
    weights or a hand-picked pair. -/
def allPairsReachable (edges : List (Nat × Nat)) (depth : Nat) (siteCount : Nat) : Bool :=
  (List.range siteCount).all fun source =>
    (List.range siteCount).all fun target =>
      source == target || reachableWithin edges depth source target

/-- DEPRECATED. True if some parameter assignment gives a nonzero
    off-diagonal entry (any `.parameter`, given `siteCount >= 2`) -- flawed
    because `i ≠ j` alone doesn't establish the domain considers that pair
    long-range. Superseded by `canRepresentLongRangeCoupling`, which derives
    the relation from `edges` and a specified graph-hop `locality`. Kept so
    frozen historical certificates stay re-checkable. -/
def canRepresentNonLocal (siteCount : Nat) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => siteCount >= 2
  | .add (.parameter _) (.adjoint (.parameter _)) => siteCount >= 2
  | .add (.adjoint (.parameter _)) (.parameter _) => siteCount >= 2
  | _ => false

/-- A specified-interface domain parameter: the graph-hop radius within
    which two sites count as local (see `Testv2.Requirements` module
    docstring). Wrapped in its own `structure`, not a bare `Nat`, so the
    resolver's type-based candidate matching can never confuse this
    SPECIFIED-INTERFACE value with an artifact-grounded `Nat` like
    `siteCount`. -/
structure LocalityRange where
  range : Nat
deriving DecidableEq, Repr

/-- `(i, j)` is LONG-RANGE under `LongRange_R(i, j) := shortestPathDistance(i, j) > R`:
    distinct sites whose shortest-path distance exceeds `locality.range`.
    `!reachableWithin edges locality.range i j` covers both "distance > R"
    and "disconnected" uniformly (disconnected means no path exists at any
    range, so it's always long-range) via the same reachability predicate
    already used for message-passing coverage. Self-pairs are excluded
    explicitly and are never a witness. -/
def isLongRangePair (edges : List (Nat × Nat)) (locality : LocalityRange) (pair : Nat × Nat) : Bool :=
  pair.1 != pair.2 && !reachableWithin edges locality.range pair.1 pair.2

/-- Whether some pair of distinct sites in `[0, siteCount)` is long-range
    under `locality` -- DERIVED from `edges` and `locality`, never a
    hand-supplied pair set. -/
def hasLongRangePair (siteCount : Nat) (edges : List (Nat × Nat)) (locality : LocalityRange) : Bool :=
  (List.range siteCount).any fun i =>
    (List.range siteCount).any fun j => isLongRangePair edges locality (i, j)

/-- True if some parameter assignment realizes nonzero coupling on a
    `hasLongRangePair` pair AND the construction has an unconstrained
    `.parameter` (never `.opaque`) to realize it; `.zero`/`.identity` never
    qualify. Does not require the two `.parameter`s in an `add`/`adjoint`
    pair to match -- that's `guaranteedSelfAdjoint`'s own, independently
    checked condition. -/
def canRepresentLongRangeCoupling
    (siteCount : Nat) (edges : List (Nat × Nat)) (locality : LocalityRange) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => hasLongRangePair siteCount edges locality
  | .add (.parameter _) (.adjoint (.parameter _)) => hasLongRangePair siteCount edges locality
  | .add (.adjoint (.parameter _)) (.parameter _) => hasLongRangePair siteCount edges locality
  | _ => false

-- Truth-table regression checks, run automatically on every `lake build`.
#guard canRepresentNonLocal 5 .zero == false
#guard canRepresentNonLocal 5 .identity == false
#guard canRepresentNonLocal 2 (.parameter "p") == true
#guard canRepresentNonLocal 1 (.parameter "p") == false
#guard canRepresentNonLocal 0 (.parameter "p") == false
-- same parameter on both sides: genuine non-local capacity (and, checked
-- separately below, guaranteed self-adjoint too).
#guard canRepresentNonLocal 2 (.add (.parameter "p") (.adjoint (.parameter "p"))) == true
#guard canRepresentNonLocal 2 (.add (.adjoint (.parameter "p")) (.parameter "p")) == true
-- mismatched parameters: still non-local capacity even though NOT self-adjoint -- independent checks.
#guard canRepresentNonLocal 2 (.add (.parameter "p") (.adjoint (.parameter "q"))) == true
#guard guaranteedSelfAdjoint (.add (.parameter "p") (.adjoint (.parameter "q"))) == false
-- no `.parameter` anywhere means no representational freedom, regardless of siteCount.
#guard canRepresentNonLocal 5 (.add .zero (.adjoint .zero)) == false
#guard canRepresentNonLocal 5 (.add .identity (.adjoint .identity)) == false
#guard canRepresentNonLocal 5 (.add .unsupported (.adjoint .unsupported)) == false
#guard canRepresentNonLocal 5 .unsupported == false
-- guaranteedSelfAdjoint pinned here too so a future edit can't conflate the two.
#guard guaranteedSelfAdjoint .zero == true
#guard guaranteedSelfAdjoint .identity == true
#guard guaranteedSelfAdjoint (.add (.parameter "p") (.adjoint (.parameter "p"))) == true

-- `.opaque + adjoint .opaque` is still self-adjoint but has no free parameter, so no non-local capacity.
#guard guaranteedSelfAdjoint (.add (.opaque "base") (.adjoint (.opaque "base"))) == true
#guard canRepresentNonLocal 5 (.add (.opaque "base") (.adjoint (.opaque "base"))) == false
#guard canRepresentNonLocal 5 (.opaque "base") == false

-- Graph-hop long-range semantics: the relation is DERIVED from `edges` and `R`, never hand-supplied.
def chainEdges : List (Nat × Nat) := [(0, 1), (1, 0), (1, 2), (2, 1), (2, 3), (3, 2)]
def disconnectedEdges : List (Nat × Nat) := [(0, 1), (1, 0), (2, 3), (3, 2)]

-- self-pairs are never long-range witnesses, for any edges/range.
#guard isLongRangePair chainEdges ⟨0⟩ (2, 2) == false
#guard isLongRangePair chainEdges ⟨100⟩ (2, 2) == false
-- distance(0, 3) = 3 hops: long-range once R < 3, local once R >= 3, same `chainEdges`.
#guard isLongRangePair chainEdges ⟨2⟩ (0, 3) == true
#guard isLongRangePair chainEdges ⟨3⟩ (0, 3) == false
#guard hasLongRangePair 4 chainEdges ⟨2⟩ == true
#guard hasLongRangePair 4 chainEdges ⟨4⟩ == false
-- disconnected sites are long-range at ANY range, no special-casing.
#guard isLongRangePair disconnectedEdges ⟨100⟩ (0, 2) == true
#guard hasLongRangePair 4 disconnectedEdges ⟨100⟩ == true
-- zero/identity: no representational freedom, regardless of the derived relation.
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩ .zero == false
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩ .identity == false
-- capacity tracks whether the DERIVED relation has a long-range pair, never `siteCount >= 2` alone.
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩ (.parameter "p") == true
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨4⟩ (.parameter "p") == false
#guard canRepresentLongRangeCoupling 1 chainEdges ⟨0⟩ (.parameter "p") == false
-- symmetrized: still requires a derived long-range pair; self-adjointness is checked separately.
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩
  (.add (.parameter "p") (.adjoint (.parameter "p"))) == true
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨4⟩
  (.add (.parameter "p") (.adjoint (.parameter "p"))) == false
-- `.opaque` base: self-adjoint when symmetrized, but never granted long-range capacity.
#guard guaranteedSelfAdjoint (.add (.opaque "base") (.adjoint (.opaque "base"))) == true
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩
  (.add (.opaque "base") (.adjoint (.opaque "base"))) == false
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩ (.opaque "base") == false
#guard canRepresentLongRangeCoupling 4 chainEdges ⟨2⟩ .unsupported == false

end Testv2.StructuralV2
