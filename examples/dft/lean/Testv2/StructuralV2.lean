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
    assignment; an unconstrained `.parameter` and a symmetrized
    `.add p (.adjoint p)` (or its mirror) can, PROVIDED there are at least
    two sites for an off-diagonal entry to exist at all -- a 1x1 matrix has
    none, for any recipe, so `siteCount` is a real precondition of this
    claim, not a separate Python-only check layered on top of a Lean fact
    that doesn't mention it. A fact about the construction and site count
    alone -- never about any extracted floating-point value, since there
    are none before training. -/
def canRepresentNonLocal (siteCount : Nat) : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => siteCount >= 2
  | .add _ (.adjoint _) => siteCount >= 2
  | .add (.adjoint _) _ => siteCount >= 2
  | _ => false

end Testv2.StructuralV2
