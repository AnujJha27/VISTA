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
  /-- A base term the artifact classifier could not positively confirm is a
      free/trainable parameter (e.g. a fixed buffer, a constant, or simply
      missing classification metadata) -- distinct from `.parameter` so
      that `guaranteedSelfAdjoint` (which holds for `base + base^T`
      regardless of what `base` is) and `canRepresentNonLocal` (which
      requires an actual free parameter to have any representational
      freedom at all) can disagree about the same term, as they must:
      `zero + adjoint zero` is self-adjoint but has no off-diagonal
      freedom, and neither does `opaque + adjoint opaque` for the exact
      same reason -- there is no parameter to choose. -/
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

/-- Historical: `requirements` was a finite list of `(source, target)` pairs,
    hand-authored in the candidate's own constraints, that had to be
    reachable from the candidate's adjacency (`edges`) within `depth` hops.
    Superseded entirely by `allPairsReachable` below, which requires
    coverage of every pair rather than an externally hand-picked list. Kept
    only so frozen historical evaluation certificates remain re-checkable;
    the live pipeline no longer generates obligations against this. -/
def allCovered (edges : List (Nat × Nat)) (depth : Nat)
    (requirements : List (Nat × Nat)) : Bool :=
  requirements.all fun coupling =>
    reachableWithin edges depth coupling.1 coupling.2

/-- Every ordered pair of distinct sites is reachable from every other
    within the declared message-passing depth -- a fact about topology and
    depth alone (`edges`, `depth`, `siteCount`), never about extracted
    weights and never a hand-picked pair. -/
def allPairsReachable (edges : List (Nat × Nat)) (depth : Nat) (siteCount : Nat) : Bool :=
  (List.range siteCount).all fun source =>
    (List.range siteCount).all fun target =>
      source == target || reachableWithin edges depth source target

/-- DEPRECATED / HISTORICAL ALIAS. Originally: does this operator
    construction admit *some* parameter assignment with a nonzero
    off-diagonal entry? `.zero`/`.identity` never can, for any assignment;
    only a construction that actually contains an unconstrained
    `.parameter` -- bare, or added to the adjoint of a (possibly different)
    `.parameter` -- has the representational freedom to realize one,
    provided `siteCount >= 2`.

    Kept only so frozen historical certificates that already reference it
    remain re-checkable; the live theorem-centric requirement
    (`Testv2.Requirements`) no longer uses this as its authoritative
    capacity premise. Treating "some pair `i ≠ j` has a nonzero
    off-diagonal entry" as sufficient for physical non-locality was itself
    the bug: an arbitrary off-diagonal entry does not establish that the
    coupling it represents is between sites the domain actually considers
    long-range. Superseded by `canRepresentLongRangeCoupling` below, which
    requires an explicitly specified long-range site pair (`longRangePairs`,
    a `specified_interface` fact) rather than inferring physical range from
    `i ≠ j` alone. -/
def canRepresentNonLocal (siteCount : Nat) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => siteCount >= 2
  | .add (.parameter _) (.adjoint (.parameter _)) => siteCount >= 2
  | .add (.adjoint (.parameter _)) (.parameter _) => siteCount >= 2
  | _ => false

/-- A site-pair reference is only meaningful for a declared `siteCount`
    when both indices are actually sites (`< siteCount`) and it names two
    distinct sites -- a self-pair (`i = i`) is never a coupling between two
    sites at all, let alone a long-range one. Malformed pairs (out of
    bounds, or a self-pair) fail closed: they simply don't count, rather
    than raising or being silently dropped upstream. -/
def validLongRangePair (siteCount : Nat) (pair : Nat × Nat) : Bool :=
  pair.1 < siteCount && pair.2 < siteCount && pair.1 != pair.2

/-- A wrapper around `List (Nat × Nat)`, not a bare type alias: the
    theorem-centric resolver matches a candidate binding to a binder purely
    by LEAN TYPE (`dftcert.verification.resolver`), and `ValidMessagePassingCoverage`'s
    own `edges : List (Nat × Nat)` binder is a completely different,
    artifact-derived fact (the GNN's adjacency, not a domain-specified
    long-range pair set). A plain type alias (`def ... := List (Nat × Nat)`)
    would still be definitionally equal to `List (Nat × Nat)` and could
    therefore still be silently matched against `edges` (or vice versa); a
    genuine `structure` cannot. -/
structure LongRangePairs where
  pairs : List (Nat × Nat)
deriving DecidableEq, Repr

/-- Whether `longRangePairs` (SUPPLIED by the verification specification's
    interface contract -- `specified_interface` provenance, never derived
    from the artifact) contains at least one pair that is actually valid
    for `siteCount`. -/
def hasValidLongRangePair (siteCount : Nat) (longRangePairs : LongRangePairs) : Bool :=
  longRangePairs.pairs.any (validLongRangePair siteCount)

/-- Does this operator construction admit *some* parameter assignment with
    nonzero coupling on at least one of the explicitly specified
    `longRangePairs`? This is the PROVISIONAL working notion of "long-range
    representational capacity" (research-soundness correction -- see
    `Testv2.Requirements` module docstring): capacity is no longer granted
    merely because `siteCount >= 2` makes *some* off-diagonal entry exist
    at all -- it requires that at least one of the site pairs the domain
    specification has explicitly classified as long-range is even
    representable by this `siteCount` (`hasValidLongRangePair`), AND that
    the construction actually contains an unconstrained `.parameter` (never
    an `.opaque` base the artifact could not positively confirm is
    trainable -- see `OperatorForm.opaque`) with the freedom to realize
    that coupling.

    `.zero`/`.identity` never have this freedom, for any assignment or any
    pair. Deliberately does NOT require the two `.parameter`s in an
    `add`/`adjoint` pair to match -- that is `guaranteedSelfAdjoint`'s own,
    separate, stricter condition -- long-range capacity and guaranteed
    self-adjointness are independent properties of the same construction,
    checked separately, never conflated.

    This does not itself decide which physical site pairs count as
    "long-range" -- that is an unverified physical interpretation the
    domain specification supplies (`longRangePairs`), not something this
    function or the artifact establishes. -/
def canRepresentLongRangeCoupling
    (siteCount : Nat) (longRangePairs : LongRangePairs) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => hasValidLongRangePair siteCount longRangePairs
  | .add (.parameter _) (.adjoint (.parameter _)) => hasValidLongRangePair siteCount longRangePairs
  | .add (.adjoint (.parameter _)) (.parameter _) => hasValidLongRangePair siteCount longRangePairs
  | _ => false

-- research-readiness audit issue 3: exact truth-table regression checks,
-- one per case reasoned through in the fix -- run automatically on every
-- `lake build` of this module, no session/certificate machinery needed.
#guard canRepresentNonLocal 5 .zero == false
#guard canRepresentNonLocal 5 .identity == false
#guard canRepresentNonLocal 2 (.parameter "p") == true
#guard canRepresentNonLocal 1 (.parameter "p") == false
#guard canRepresentNonLocal 0 (.parameter "p") == false
-- same parameter on both sides: genuine non-local capacity (and, checked
-- separately below, guaranteed self-adjoint too).
#guard canRepresentNonLocal 2 (.add (.parameter "p") (.adjoint (.parameter "p"))) == true
#guard canRepresentNonLocal 2 (.add (.adjoint (.parameter "p")) (.parameter "p")) == true
-- mismatched parameters: still genuine non-local capacity (independent
-- B_p, B_q can realize a nonzero off-diagonal entry) even though NOT
-- guaranteed self-adjoint -- the two properties are checked independently.
#guard canRepresentNonLocal 2 (.add (.parameter "p") (.adjoint (.parameter "q"))) == true
#guard guaranteedSelfAdjoint (.add (.parameter "p") (.adjoint (.parameter "q"))) == false
-- the bug this fix closes: no `.parameter` anywhere means no
-- representational freedom at all, regardless of siteCount.
#guard canRepresentNonLocal 5 (.add .zero (.adjoint .zero)) == false
#guard canRepresentNonLocal 5 (.add .identity (.adjoint .identity)) == false
#guard canRepresentNonLocal 5 (.add .unsupported (.adjoint .unsupported)) == false
#guard canRepresentNonLocal 5 .unsupported == false
-- guaranteedSelfAdjoint is unchanged by this fix -- pinned here too so a
-- future edit to either function can't silently conflate them again.
#guard guaranteedSelfAdjoint .zero == true
#guard guaranteedSelfAdjoint .identity == true
#guard guaranteedSelfAdjoint (.add (.parameter "p") (.adjoint (.parameter "p"))) == true

-- research-readiness audit (post-hardening-pass review): `base + base^T`
-- built from an `.opaque` (not positively confirmed trainable) base is
-- still guaranteed self-adjoint -- that classification never depended on
-- trainability -- but has NO non-local representational capacity, exactly
-- like `zero + adjoint zero`, since there is no free parameter to choose.
#guard guaranteedSelfAdjoint (.add (.opaque "base") (.adjoint (.opaque "base"))) == true
#guard canRepresentNonLocal 5 (.add (.opaque "base") (.adjoint (.opaque "base"))) == false
#guard canRepresentNonLocal 5 (.opaque "base") == false

-- Provisional long-range-coupling semantics regression checks (research-
-- soundness correction: retires "any off-diagonal entry" as sufficient for
-- physical non-locality; requires an explicitly specified long-range pair).
#guard validLongRangePair 4 (0, 3) == true
#guard validLongRangePair 4 (3, 0) == true
#guard validLongRangePair 4 (2, 2) == false
#guard validLongRangePair 4 (0, 4) == false
#guard validLongRangePair 4 (4, 0) == false
#guard hasValidLongRangePair 4 ⟨[]⟩ == false
#guard hasValidLongRangePair 4 ⟨[(2, 2)]⟩ == false
#guard hasValidLongRangePair 4 ⟨[(2, 2), (0, 3)]⟩ == true
-- zero/identity: no representational freedom at all, regardless of pairs.
#guard canRepresentLongRangeCoupling 5 ⟨[(0, 4)]⟩ .zero == false
#guard canRepresentLongRangeCoupling 5 ⟨[(0, 4)]⟩ .identity == false
-- a bare free parameter: capacity tracks whether a VALID long-range pair
-- was even supplied, never `siteCount >= 2` alone.
#guard canRepresentLongRangeCoupling 4 ⟨[(0, 3)]⟩ (.parameter "p") == true
#guard canRepresentLongRangeCoupling 4 ⟨[]⟩ (.parameter "p") == false
#guard canRepresentLongRangeCoupling 4 ⟨[(2, 2)]⟩ (.parameter "p") == false
#guard canRepresentLongRangeCoupling 1 ⟨[(0, 0)]⟩ (.parameter "p") == false
-- symmetrized (same parameter on both sides): capacity requires a valid
-- pair too; self-adjointness (checked separately) is unaffected.
#guard canRepresentLongRangeCoupling 4 ⟨[(0, 3)]⟩
  (.add (.parameter "p") (.adjoint (.parameter "p"))) == true
#guard canRepresentLongRangeCoupling 4 ⟨[]⟩
  (.add (.parameter "p") (.adjoint (.parameter "p"))) == false
-- an `.opaque` base (not positively confirmed trainable): still
-- self-adjoint when symmetrized, but never granted long-range capacity,
-- regardless of how many valid pairs are supplied.
#guard guaranteedSelfAdjoint (.add (.opaque "base") (.adjoint (.opaque "base"))) == true
#guard canRepresentLongRangeCoupling 4 ⟨[(0, 3)]⟩
  (.add (.opaque "base") (.adjoint (.opaque "base"))) == false
#guard canRepresentLongRangeCoupling 4 ⟨[(0, 3)]⟩ (.opaque "base") == false
#guard canRepresentLongRangeCoupling 4 ⟨[(0, 3)]⟩ .unsupported == false

end Testv2.StructuralV2
