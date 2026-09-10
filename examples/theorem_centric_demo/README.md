# Theorem-Centric Demo

A minimal, reproducible walk-through of the theorem-centric VISTA workflow,
using the real, already-committed `tests/fixtures/certified_ring.pt2`
fixture (a 6-site ring, symmetrized self-energy operator, hinge XC) --
no new model is introduced for this demo.

It certifies `Testv2.Requirements.ValidPretrainingArchitectureConditional`,
the *conditional* entrypoint, specifically because walking through it
exercises every provenance class at once: artifact-derived facts, a
specified interface interpretation, one explicit assumption, and Lean-checked
conclusions.

## What each kind of evidence means here

Reading the final certificate report (`certificate/*-report.json`), every
node falls into exactly one of these buckets -- this is the actual
distinction the tool makes, not a marketing claim:

- **Artifact-derived facts** (`artifact_grounded_nodes`, nodes `#0`, `#1`,
  `#3`, `#4` in the real report): `siteCount = 6`, the ring adjacency
  (`edges`), the self-adjoint operator construction, and the XC form are
  read directly from the real `.pt2`'s exported computation graph and
  adjacency buffer -- deterministically re-derived and checked for
  consistency against the raw extraction (the same adapter implementation
  re-run, not a second independent checker), never merely asserted.
- **Supplied interface interpretation** (`specified_interface_nodes`, node
  `#2` in the real report): which of the graph's output nodes correspond to
  "the XC energy", "the learned self-energy", and "the message state" is a
  human-supplied mapping (the adjacency convention too) -- the tool cannot
  discover this from the graph alone. As of the graph-hop locality
  correction (research-soundness pass), this demo has one concrete
  specified-interface locality datum: `localityRange` --
  `interface_contract.json`'s `locality_range: 2` declares the graph-hop
  radius `R` within which two sites are considered local. Everything about
  *which* pairs actually count as long-range is then DERIVED by VISTA
  itself from the artifact-grounded `edges` and this one integer -- sites 0
  and 3 (the two furthest apart on this 6-site ring, 3 hops) come out
  long-range because `3 > R`, never because anyone hand-picked that pair.
  `R` is a specified interpretation, exactly like the output-role mapping,
  and the report labels it that way rather than implying Lean discovered or
  verified it.
- **Explicit assumption** (`external_assumptions`/`specified_assumption_nodes`,
  nodes `#5`/`#9` in the real report): `TargetRequiresLongRangeCoupling` -- a
  real `Prop`-sorted premise this entrypoint requires that no artifact fact
  or formal theory establishes. Accepting it (`accept_assumption.py`)
  records the *exact* proposition, its fingerprint, and a rationale into the
  package; it survives on the generated certificate theorem as a real,
  unproven binder -- never discharged, never an `axiom`. Critically, the
  generated certificate's *conclusion* (`ConditionallyAcceptableArchitecture`)
  literally conjoins `TargetRequiresLongRangeCoupling` with the derived
  structural facts, so accepting this assumption is what makes the stronger,
  conjoined claim available at all -- it is never a decorative premise a
  reader could drop without changing what gets proven (an earlier version of
  this entrypoint had exactly that flaw: its conclusion was plain
  `AcceptableArchitecture`, which `ValidPretrainingArchitecture` already
  proves with strictly fewer premises, making the assumption provably
  unused).
- **Lean-checked conclusions** (`formally_discharged_nodes`, nodes `#6`,
  `#7`, `#8`; `certificate_axiom_closure`): given the artifact-derived
  siteCount/edges/operator/XC values AND the specified `localityRange`,
  Lean's kernel derives the long-range relation from `edges` and
  `localityRange` itself and checks `guaranteedSelfAdjoint`,
  `canRepresentLongRangeCoupling`, and `xcSupportsDiscontinuity` actually
  reduce to `true` by computation. Lean proves the theorem holds for THESE
  bound values; it does not, and cannot, establish that graph-hop distance
  beyond `R = 2` is the physically correct notion of "long-range" for this
  domain -- that interpretation is supplied, not verified (see "Provisional
  locality definition" below). The generated certificate's own axiom
  closure (not just the entrypoint's -- see
  `dftcert/verification/certificate.py`) is `["propext"]`: no `sorry`, no
  custom axioms.

**Not claimed:** that this generalizes to any other artifact or architecture,
that Lean has verified anything about real floating-point training behavior,
that graph-hop distance beyond the specified `locality_range` is the
physically correct notion of locality for this domain, or that the accepted
assumption has been proven true -- it remains exactly what its rationale
says, forever conditional on it.

## Provisional locality definition

VISTA currently uses graph-hop distance greater than a configurable range
`R` as a provisional operational definition of long-range coupling. The
graph is artifact-grounded; `R` is a specified domain parameter; the
long-range relation is derived by VISTA.

This demo's `canRepresentLongRangeCoupling` premise replaces an earlier,
unsound notion (`canRepresentNonLocal`, kept in `Testv2/StructuralV2.lean`
only as a deprecated historical alias) that treated *any* off-diagonal
matrix entry as sufficient evidence of physical non-locality. That is not
true in general: an arbitrary off-diagonal entry does not by itself
establish that the coupling it represents is between sites the domain
actually considers far apart. A later, intermediate correction required an
explicit, hand-supplied list of site pairs -- itself later retired in favor
of the current mechanism, since a hand-picked pair is no more
artifact-grounded than an arbitrary off-diagonal entry was. The current,
still-provisional notion instead derives the long-range pair set itself
(`shortestPathDistance(i, j) > R`) from the artifact's own adjacency graph
and a single specified integer `R` (`interface_contract.json`'s
`locality_range`), and checks only whether the architecture has the
representational freedom (a confirmed trainable parameter, not a fixed
buffer or unknown classification) to couple at least one pair that
relation classifies as long-range. The exact physical definition of
"long-range" for this domain (Euclidean distance, lattice distance,
graph-hop distance, or something else) is not decided by this tool and may
be refined by a domain expert without rewriting the theorem-centric harness
-- only the operational definition of `LongRange_R`, and how `R` is
validated, would need to change.

## Running it

From the repository root, with a real Lean toolchain available for
`examples/dft/lean` (see the repo's own test setup for how the environment
gets one) and the `vista` script at the repo root:

```
python examples/theorem_centric_demo/build_package.py
python examples/theorem_centric_demo/extract_artifact.py
python vista verify start \
  --extraction-result examples/theorem_centric_demo/extraction-result.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --session examples/theorem_centric_demo/session.json \
  --project examples/dft/lean --trusted-local --timeout-s 180
```

Expected output (a fresh session, blocked on the one explicit premise --
everything else, including the `localityRange` specified-interface binder
and the `hLR` long-range-coupling premise (its long-range relation derived
from `edges` and `localityRange`), resolves automatically):

```json
{"session": "examples/theorem_centric_demo/session.json", "status": "blocked_on_premise", "targets": ["Testv2.Requirements.ValidPretrainingArchitectureConditional"], "unresolved_premises": ["Testv2.Requirements.ValidPretrainingArchitectureConditional#9"]}
```

Accept the one explicit assumption this entrypoint needs, then re-run start
to apply it (a package decision is only ever applied by re-deriving the
session against Lean -- see `dftcert/verification/session.py`):

```
python examples/theorem_centric_demo/accept_assumption.py
python vista verify start \
  --extraction-result examples/theorem_centric_demo/extraction-result.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --session examples/theorem_centric_demo/session.json \
  --project examples/dft/lean --trusted-local --timeout-s 180
```

Expected output now:

```json
{"session": "examples/theorem_centric_demo/session.json", "status": "ready_for_certificate", "targets": ["Testv2.Requirements.ValidPretrainingArchitectureConditional"], "unresolved_premises": []}
```

Certify, then independently re-verify the resulting bundle's own hashes
(never trust a field merely because it's already stored inside the bundle):

```
python vista verify certify \
  --session examples/theorem_centric_demo/session.json \
  --package examples/theorem_centric_demo/vista-package.json \
  --project examples/dft/lean \
  --output-dir examples/theorem_centric_demo/certificate \
  --extraction-result examples/theorem_centric_demo/extraction-result.json \
  --trusted-local --timeout-s 180

python vista verify verify-bundle \
  --bundle-dir examples/theorem_centric_demo/certificate \
  --package examples/theorem_centric_demo/vista-package.json \
  --project examples/dft/lean
```

Expected: `"status": "certified"`, `"conditional": true` from `certify`, and
`"consistent": true` from `verify-bundle`. Inspect
`examples/theorem_centric_demo/certificate/*-report.json` for the exact
provenance breakdown described above, and the `.lean` file to see the
assumption surviving as a real binder.

None of `session.json`, `extraction-result.json`, `vista-package.json`, or
`certificate/` are committed here -- they're fully reproducible from the
three scripts above and the real `.pt2` fixture, and would otherwise go
stale against the actual Lean project.
