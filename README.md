# VISTA

**V**erification of **I**nteratomic **S**urrogates via **T**heorem-based
**A**ssurance

> Artifact-grounded structural verification of exported ML models with Lean

VISTA is a research prototype for checking whether structural facts derived
from an exported machine-learning artifact are sufficient to instantiate
selected formal requirements expressed as Lean theorems under explicit
interface and external assumptions. A trusted extraction and semantic-adapter
layer connects artifact evidence to formal terms; Lean checks the resulting
theorem application. Lean does not parse or verify the exported model
artifact itself.

## Overview

You have an exported model (`model.pt2`) and want to check a specific,
narrow structural property against it -- not "is this model good," but "does
this theorem's premises hold given how this artifact is actually built."
VISTA reads the model's real exported computation graph, derives specific
structural facts from it under a domain adapter's explicit interpretation,
uses those facts (plus any facts the user explicitly specifies or assumes)
to instantiate a Lean theorem, and lets the Lean kernel decide whether the
resulting application checks. The output is a certificate: a hash-bound JSON
bundle that says exactly which facts were extracted, which were specified,
which were assumed, and which Lean formally checked.

```text
model.pt2
    -> sandboxed extraction
    -> structural evidence
    -> semantic adapter
    -> theorem premises
    -> Lean
    -> certificate
```

## Research question

Does an exported ML artifact's recognizable structural construction suffice
to instantiate a selected Lean theorem's premises, under an explicit,
auditable interface interpretation and a fully visible set of unresolved
external assumptions -- with the final theorem application checked by the
Lean kernel, not asserted by any Python code, LLM, or human review?

## Verification pipeline

1. **Sandboxed extraction.** `model.pt2` is loaded inside a Bubblewrap
   sandbox (`dftcert/sandbox.py`, `extractors/torch_export_worker.py`) and
   its real `torch.export` computation graph is read: node operations,
   arguments, tensor shapes/dtypes, `torch.export` state classification
   (parameter vs. buffer), and graph-input/alias structure. The whole
   file's SHA-256 (`artifact_sha256`) is computed from the exact bytes and
   binds everything downstream to this one artifact.
2. **Structural evidence.** `dftcert/structural/core.py` derives an
   architecture-level structural IR from the raw inventory: topology,
   operator construction, exchange-correlation form, message-passing
   structure (for the DFT case study adapter) -- independently re-derived
   and cross-checked against the raw graph nodes it claims to summarize
   (`validate_translation`), never merely asserted.
3. **Semantic adapter.** A domain adapter (`dftcert/structural/plugin.py`'s
   `StructuralPlugin` interface; the one adapter in this repo is
   `dft_capability_plugin.py`) turns structural IR facts into candidate Lean
   terms (`FormalBindingCandidate`s) -- e.g. an `OperatorForm` value for the
   artifact's recognized operator construction.
4. **Theorem premises.** `dftcert/verification/resolver.py` inspects a
   selected Lean theorem's real elaborated binder telescope
   (`dftcert/verification/lean_inspect.py`) and matches candidates to
   binders by Lean type. A binder with no matching candidate, or with a
   `Prop`-sorted premise nothing can establish, stays unresolved -- it can
   be filled by an explicit, package-authored external assumption, but never
   silently.
5. **Lean.** `dftcert/verification/certificate.py` generates an ordinary
   Lean source file applying the selected theorem to the resolved terms and
   invokes the real Lean toolchain to elaborate and kernel-check it. No
   `sorry`, no custom `axiom`; the generated certificate's own axiom closure
   is inspected and gated against an explicit, package-declared allow-list.
6. **Certificate.** The result is a JSON bundle (`manifest.json` plus one
   `.lean`/`-report.json` pair per certified target) hash-bound to the exact
   artifact, the verification package, and the Lean project/toolchain
   fingerprint -- independently re-derivable and re-checkable
   (`vista verify verify-bundle`) without trusting any field merely because
   it is already present in the bundle.

## Trust model

Every fact VISTA uses falls into exactly one of these classes -- this is the
actual distinction the tool makes, not marketing:

| Class | Meaning |
| --- | --- |
| Extracted | Direct evidence from the exported artifact |
| Inferred | Deterministic adapter conclusions derived from extracted evidence |
| Specified interface | Semantic interpretation supplied by the user/domain |
| Specified assumption | Explicit unresolved theorem premise accepted conditionally |
| Formally checked | Lean elaboration/kernel-checked result |
| Unverified | Claim outside the trusted verification chain |

VISTA is a **pre-training structural verifier**. It never uses a trainable
parameter's values as verification premises -- verification depends on
architecture-level information such as graph structure, operation
structure, tensor shape/dtype, `torch.export` state classification
(parameter vs. buffer), and explicitly identified structural state (e.g. a
small boolean adjacency/mask buffer, where the exact values are themselves
part of the architecture). The exact artifact SHA-256 still binds the
certificate to the specific exported file -- that hash identifies which
bytes were checked, but is never itself treated as evidence about what a
parameter's trained/initialized values are. Concretely: two artifacts
exported from the same architecture with different random initializations
produce different `artifact_sha256` values but the same structural
classification, the same formal binding candidates, and the same
verification result (`tests/test_pretraining_scope.py`).

The full stage-by-stage trust classification for one real certificate, the
tamper matrix (what's detected and how), and every known trust-chain issue
found and fixed are in
[`docs/verification/TRUST_CHAIN_AUDIT.md`](docs/verification/TRUST_CHAIN_AUDIT.md) --
read that document, not this README, for the complete audit.

## Minimal self-adjointness example

The primary example demonstrates VISTA itself, not a full scientific
formalization. The property: an operator built as `A = B + Bᵀ` for any real
matrix `B` is self-adjoint (`Aᵀ = (B + Bᵀ)ᵀ = Bᵀ + B = B + Bᵀ = A`) -- a
clean, pre-training, architecture-only guarantee that depends on how the
operator is *constructed*, never on `B`'s trained/initialized values.

`examples/dft/lean/Testv2/StructuralV2.lean` defines a finite, computable
grammar for recognized operator constructions and the guarantee itself:

```lean
inductive OperatorForm where
  | zero | identity | parameter (name : String) | opaque (name : String)
  | adjoint (value : OperatorForm) | add (left right : OperatorForm) | unsupported

def guaranteedSelfAdjoint : OperatorForm → Bool
  | .zero => true
  | .identity => true
  | .add left (.adjoint right) => left == right
  | .add (.adjoint left) right => left == right
  | _ => false
```

and `examples/dft/lean/Testv2/Requirements.lean` states the minimal
theorem-centric entrypoint against it, with no site-count/long-range/XC/
message-passing premises at all:

```lean
def SelfAdjointCompatible (op : OperatorForm) : Prop :=
  guaranteedSelfAdjoint op = true

theorem ValidSelfAdjointConstruction
    (op : OperatorForm) (hSA : guaranteedSelfAdjoint op = true) :
    SelfAdjointCompatible op :=
  hSA
```

Two real, committed `.pt2` artifacts (`examples/dft/models/
structural_gnns.py`), same architecture family, different operator recipe:

- **Positive** -- `CertifiedRingGNN`: `learned_self_energy = base_operator +
  base_operator.T`. The adapter recognizes this as the `symmetrized`
  construction; `op` resolves to `.add (.parameter "base") (.adjoint
  (.parameter "base"))`; `guaranteedSelfAdjoint` reduces to `true` by
  computation; the certificate is emitted.
- **Negative** -- `UnconstrainedOperatorGNN`: `learned_self_energy =
  base_operator` (no symmetrization). The adapter recognizes a bare
  parameter; `guaranteedSelfAdjoint` reduces to `false`; the `hSA` premise
  cannot be discharged; no certificate is emitted. **VISTA does not
  establish "this model is mathematically non-self-adjoint"** -- `base_
  operator`'s actual values are never inspected at all (pre-training scope).
  It establishes only that the selected self-adjointness requirement cannot
  be derived from the artifact's *recognized structural construction*.

No adapter change was needed to isolate this from the fuller DFT
formalization: `formal_binding_candidates` already derives an `OperatorForm`
candidate unconditionally, independent of which theorem is selected, and the
theorem-centric resolver only ever asks for the binders the *selected*
theorem actually has.

See `tests/test_self_adjoint_demo.py` for both outcomes end to end, and its
`ForgedSessionCannotCertifyTests` for the adversarial regression described in
the trust-chain audit.

## What a certificate means

A certificate says: for this exact artifact's SHA-256, under this exact
verification package's interface interpretation and declared external
assumptions, and against this exact Lean project/toolchain fingerprint, Lean
kernel-checked that the selected theorem applies to the derived/specified/
assumed terms recorded in the report -- with no `sorry` and no axiom outside
an explicit, package-declared allow-list.

## What a certificate does NOT establish

- That Lean verified or parsed the model artifact's binary file itself --
  Lean only ever sees the generated theorem-application source.
- That any external assumption on the certificate is true -- it remains a
  free, visible binder on the generated theorem, forever, never discharged
  or axiomatized by the act of certifying.
- That a specified interface interpretation (which output means what, the
  graph-hop locality range `R`, etc.) is itself artifact-derived -- it is a
  human/domain interpretation, recorded and hash-bound, not verified. Which
  site pairs count as long-range is never itself specified -- it is derived
  by VISTA from the artifact-grounded adjacency graph and `R`.
- Anything about trained numerical behavior or post-training performance --
  VISTA is pre-training and structural only.
- That the Python extractor or semantic adapter is itself formally verified
  -- both are ordinary, tested (not proof-checked) Python.
- That VISTA supports arbitrary ML architectures or arbitrary domains -- one
  domain adapter (a DFT case study) exists today.

## Reproducing the example

Requires a real Lean toolchain for `examples/dft/lean` (pinned exactly --
see "Trusted computing base") and, for the `--artifact` path below, a
working Bubblewrap sandbox with a Python interpreter that has the pinned
`torch` installed (`requirements-repro.txt`).

```bash
python examples/self_adjoint_demo/build_package.py

python vista verify start \
  --artifact tests/fixtures/certified_ring.pt2 \
  --package examples/self_adjoint_demo/vista-package.json \
  --session examples/self_adjoint_demo/session.json \
  --project examples/dft/lean --timeout-s 180 --trusted-local

python vista verify certify \
  --session examples/self_adjoint_demo/session.json \
  --package examples/self_adjoint_demo/vista-package.json \
  --project examples/dft/lean \
  --output-dir examples/self_adjoint_demo/certificate \
  --artifact tests/fixtures/certified_ring.pt2 --timeout-s 180 --trusted-local
```

`--artifact` still sends the `.pt2` through the Bubblewrap sandbox for
extraction. `--trusted-local` is required here for a separate reason: it is
also what permits the Lean compiler itself to be invoked locally (Lean
resolution/introspection), which is not sandboxed.

Expect `"status": "certified"`. Point `--artifact` at
`tests/fixtures/unconstrained_operator.pt2` (build it first with
`python tests/fixtures/export_pass_fixtures.py`, which needs torch) instead
to see the negative case: `start` reports `"status": "blocked_on_premise"`,
and `certify` refuses.

A weaker, `--trusted-local` mode exists for CI/development: pass
`--extraction-result <path> --trusted-local` instead of `--artifact` to
supply an already-produced extraction result JSON directly, bypassing the
Bubblewrap sandbox entirely. This is explicitly a weaker trust mode -- it
authenticates the derived facts *against the supplied inventory*, never
that the inventory itself came from genuine artifact bytes (see the
trust-chain audit's trusted-local row). `--artifact` always performs real
PT2 extraction through the sandbox; `--extraction-result ... --trusted-local`
accepts supplied extraction evidence directly.

## Trusted computing base

- The Lean toolchain: `leanprover/lean4:v4.31.0` with Mathlib pinned to the
  same tag (`examples/dft/lean/lakefile.toml`) -- the actual kernel that
  checks every certificate.
- The Bubblewrap sandboxed extractor (`dftcert/sandbox.py`,
  `extractors/torch_export_worker.py`) and its `torch.export` reading logic
  -- ordinary Python, tested but not formally verified.
- The semantic adapter (`dftcert/structural/dft_capability_plugin.py`) that
  turns structural evidence into candidate Lean terms -- also ordinary,
  tested Python; ordinary code review, not formal verification, is what
  backs its correctness.
- The verification harness (`dftcert/verification/`) that resolves theorem
  binders, generates certificate sources, and assembles/hash-binds bundles.
- `--trusted-local` extraction results and any accepted external assumption
  are explicit, named trust reductions, never silently implied.

## Repository layout

- `dftcert/structural/` -- the domain-agnostic structural harness plus the
  one DFT domain adapter.
- `dftcert/verification/` -- the theorem-centric verification harness:
  packages, sessions, resolver, Lean introspection, certificate assembly.
- `extractors/` -- the sandboxed `.pt2` extraction worker.
- `examples/dft/lean/` -- the Lean project (`Testv2.StructuralV2`,
  `Testv2.Requirements`, and the broader DFT case-study modules: `HK.lean`,
  `KS.lean`, `Janak.lean`, `XC.lean`, `Spatial.lean`).
- `examples/self_adjoint_demo/` -- this README's minimal example.
- `examples/theorem_centric_demo/` -- the fuller DFT case study (site
  count, long-range coupling, XC discontinuity, one explicit external
  assumption) -- a broader scientific formalization exercise, not required
  reading to understand VISTA itself.
- `examples/dft/models/structural_gnns.py` -- the small exportable model
  family (`CertifiedRingGNN`, `UnconstrainedOperatorGNN`, and other
  positive/negative variants) used throughout.
- `tests/` -- theorem-centric verification tests, the real-artifact and
  Bubblewrap-sandbox end-to-end tests, the self-adjoint demo, and the
  pre-training-scope/adversarial regressions.
- `docs/verification/TRUST_CHAIN_AUDIT.md` -- the complete trust-chain
  audit.

## Current limitations

- One domain adapter exists (the DFT case study); VISTA does not currently
  support arbitrary architectures or domains without writing a new adapter.
- Theorem-driven *selection* (which already-derived facts fill a selected
  theorem's binders) is implemented; theorem-driven *minimal IR
  construction* (deriving only what a theorem needs) is not -- the adapter
  always computes its full, fixed set of structural facts.
- The Python extractor and semantic adapter are not formally verified; their
  correctness is established by code review and tests, not by Lean.
- `--trusted-local` mode authenticates derived facts against a supplied
  inventory, never that the inventory came from genuine artifact bytes.
- The broader DFT formalization (`examples/dft/lean/Testv2/HK.lean`,
  `KS.lean`, `Janak.lean`, `XC.lean`, `Spatial.lean`, and related modules)
  is a case study, not a completed physical theory; treat any module
  described as experimental/incomplete in `docs/structural-v2/` as exactly
  that, and consult that directory before relying on any one of them.
- The fuller DFT case study uses graph-hop distance greater than a
  configurable range `R` (`locality_range`) as a provisional operational
  definition of long-range coupling: the adjacency graph is
  artifact-grounded, `R` is a specified domain parameter, and the
  long-range relation itself is derived by VISTA -- never a claim about
  physically correct locality for this domain.

## Citation

See [`CITATION.cff`](CITATION.cff).
