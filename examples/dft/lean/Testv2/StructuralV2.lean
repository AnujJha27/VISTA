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

/-- Does this operator construction admit *some* parameter assignment with a
    nonzero off-diagonal entry? `.zero`/`.identity` never can, for any
    assignment -- and neither does ANY `.add`/`.adjoint` combination built
    only from `.zero`/`.identity`/`.unsupported`: `zero + adjoint zero =
    zero`, `identity + adjoint identity = 2 • identity` (diagonal only),
    genuinely incapable of an off-diagonal entry regardless of `siteCount`.
    Only a construction that actually contains an unconstrained
    `.parameter` -- bare, or added to the adjoint of a (possibly
    different) `.parameter` -- has the representational freedom to
    realize one, PROVIDED there are at least two sites for an
    off-diagonal entry to exist at all (a 1x1 matrix has none, for any
    recipe, so `siteCount` is a real precondition of this claim, not a
    separate Python-only check layered on top of a Lean fact that doesn't
    mention it).

    Deliberately does NOT require the two `.parameter`s to match (that is
    `guaranteedSelfAdjoint`'s own, separate, stricter condition: `B_p +
    B_q^T` is only guaranteed self-adjoint for every assignment when
    `p = q`) -- non-local *capacity* and guaranteed self-adjointness are
    independent properties of the same construction, checked separately,
    never conflated: a mismatched-parameter construction can still
    genuinely realize an off-diagonal entry (independent `B_p`, `B_q` can
    certainly produce one) even though it is not guaranteed self-adjoint,
    and `AcceptableArchitecture` only accepts a construction where BOTH
    hold of the exact same term.

    A fact about the construction and site count alone -- never about any
    extracted floating-point value, since there are none before
    training. -/
def canRepresentNonLocal (siteCount : Nat) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => siteCount >= 2
  | .add (.parameter _) (.adjoint (.parameter _)) => siteCount >= 2
  | .add (.adjoint (.parameter _)) (.parameter _) => siteCount >= 2
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

end Testv2.StructuralV2
