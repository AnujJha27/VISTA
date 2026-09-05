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

/-- Historical (legacy V2) checker: `requirements` was a finite list of
    `(source, target)` pairs, hand-authored in the candidate's own
    constraints, that had to be reachable from the candidate's adjacency
    (`edges`) within `depth` hops. Superseded by `localityMatches` below,
    which checks a fact about the candidate's *own actual extracted values*
    instead of coverage of externally-declared pairs. Kept only so frozen V2
    evaluation certificates (`evaluation/structural_v2/`) remain
    re-checkable; the live V3 pipeline no longer generates obligations
    against this. -/
def allCovered (edges : List (Nat × Nat)) (depth : Nat)
    (requirements : List (Nat × Nat)) : Bool :=
  requirements.all fun coupling =>
    reachableWithin edges depth coupling.1 coupling.2

/-- V3: `observedNonzeroOffDiagonal` is the list of (source, target) pairs
    where the candidate's *own* extracted learned-self-energy matrix
    actually has a real off-diagonal entry exceeding the disclosed threshold
    -- computed by the analyzer directly from the candidate's real values
    (`dftcert.structural.core._operator_matrix`/`_observed_locality`), never
    supplied by a candidate, an analyst, or any external reference. A claim
    of `expectedLocal` is verified by checking whether that observed list is
    empty (local) or not (non-local). -/
def localityMatches (expectedLocal : Bool) (observedNonzeroOffDiagonal : List (Nat × Nat)) : Bool :=
  expectedLocal == observedNonzeroOffDiagonal.isEmpty

/-- V4: every ordered pair of distinct sites is reachable from every other
    within the declared message-passing depth -- a fact about topology and
    depth alone (`edges`, `depth`, `siteCount`), never about extracted
    weights and never a hand-picked pair. -/
def allPairsReachable (edges : List (Nat × Nat)) (depth : Nat) (siteCount : Nat) : Bool :=
  (List.range siteCount).all fun source =>
    (List.range siteCount).all fun target =>
      source == target || reachableWithin edges depth source target

/-- V4: does this operator construction admit *some* parameter assignment
    with a nonzero off-diagonal entry? `.zero`/`.identity` never can, for any
    assignment; an unconstrained `.parameter` and a symmetrized
    `.add p (.adjoint p)` (or its mirror) always can. A fact about the
    construction alone -- never about the values currently stored in it (see
    `localityMatches` for that). -/
def canRepresentNonLocal : OperatorForm → Bool
  | .zero => false
  | .identity => false
  | .parameter _ => true
  | .add _ (.adjoint _) => true
  | .add (.adjoint _) _ => true
  | _ => false

end Testv2.StructuralV2
