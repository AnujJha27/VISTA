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

- **Artifact-derived facts** (`artifact_grounded_nodes` in the report):
  `siteCount = 6`, the self-adjoint operator construction, and the XC form
  are read directly from the real `.pt2`'s exported computation graph and
  adjacency buffer -- independently re-derived and checked against the raw
  extraction, never merely asserted.
- **Supplied interface interpretation** (`interface_contract.json`): which
  of the graph's output nodes correspond to "the XC energy", "the learned
  self-energy", and "the message state" is a human-supplied mapping (the
  adjacency convention too) -- the tool cannot discover this from the graph
  alone. Nothing in this demo currently lands in `specified_interface_nodes`
  because none of this entrypoint's *binders* are filled directly from an
  interface value, but the mapping is still what makes the artifact-derived
  facts above interpretable at all.
- **Explicit assumption** (`external_assumptions`/`specified_assumption_nodes`):
  `TargetRequiresNonLocality` -- a real `Prop`-sorted premise this entrypoint
  requires that no artifact fact or formal theory establishes. Accepting it
  (`accept_assumption.py`) records the *exact* proposition, its fingerprint,
  and a rationale into the package; it survives on the generated certificate
  theorem as a real, unproven binder (see the `.lean` file: `fun
  TargetRequiresNonLocality hPhysical => ...`) -- never discharged, never an
  `axiom`.
- **Lean-checked conclusions** (`formally_discharged_nodes`,
  `certificate_axiom_closure`): given the artifact-derived siteCount/operator/
  XC values, Lean's kernel checks `guaranteedSelfAdjoint`, `canRepresentNonLocal`,
  and `xcSupportsDiscontinuity` actually reduce to `true` by computation. The
  generated certificate's own axiom closure (not just the entrypoint's --
  see `dftcert/verification/certificate.py`) is `["propext"]`: no `sorry`,
  no custom axioms.

**Not claimed:** that this generalizes to any other artifact or architecture,
that Lean has verified anything about real floating-point training behavior,
or that the accepted assumption has been proven true -- it remains exactly
what its rationale says, forever conditional on it.

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

Expected output (a fresh session, blocked on the one explicit premise):

```json
{"session": "examples/theorem_centric_demo/session.json", "status": "blocked_on_premise", "targets": ["Testv2.Requirements.ValidPretrainingArchitectureConditional"], "unresolved_premises": ["Testv2.Requirements.ValidPretrainingArchitectureConditional#7"]}
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
