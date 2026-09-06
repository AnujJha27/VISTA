# Pre-training architectural capability checks

`dftcert/structural/dft_capability_plugin.py` (`DFTCapabilityPlugin`) is
this project's only structural plugin. It certifies architectural
*capability* before a single weight is trained, and never reads an
extracted parameter's floating-point content anywhere in its derivation,
IR, or checks -- that is the whole claim this project makes. An earlier
version of this codebase also had a second, post-training plugin that read
real trained weights to check numeric locality; it has been removed
entirely, so that claim can't be ambiguous.

It is the harness's default: every function in `dftcert/structural/core.py`
uses it unless a different `plugin=` is passed explicitly, and the CLI
(`dftcert/structural/cli.py`) has no plugin-selection flag at all, since
there is nothing to select between.

## What it checks

- **`all_pairs_reachable`**: every ordered pair of sites is reachable from
  every other within the message-passing depth found *strictly within the
  operator's own ancestry* -- not a separately declared `message_state`
  output that the operator need not depend on at all. `zero`/`identity`/
  `symmetrized`/`unconstrained_parameter` (the only recipes this plugin
  recognizes) are all built purely from parameters and adjoints -- none of
  them consume the adjacency, so this check is honestly `not applicable`
  for every operator recognized today, rather than being silently
  "satisfied" by an unrelated message-passing branch elsewhere in the
  graph. It becomes a real, checkable claim only once a future recipe kind
  is recognized whose root actually depends on adjacency-fed message
  passing.
- **`non_local_capacity`**: when `expected_locality == "non_local"` and
  there are at least two sites, does the operator's construction *recipe*
  admit some parameter assignment with a nonzero off-diagonal entry?
  `zero`/`identity` never can; `symmetrized` (`B + B^T`) and
  `unconstrained_parameter` (a free matrix) can, provided a second site
  exists for an off-diagonal entry to live at -- a 1x1 matrix has none,
  for any recipe. A fact about the recipe and site count, never about the
  values currently stored in it.
- **`self_adjoint`**: the declared operator output is structurally zero,
  identity, or a parameter plus its transpose -- recipe-only, no floats.
- **`xc_discontinuity_compatible`**: the declared XC output path contains a
  supported hinge construction.

`supported()` does not require any extracted floats -- a `.pt2` with only
small bool/int adjacency buffers and no captured numeric weights is fully
certifiable by these checks.

## `derive()` never reads a float, structurally, not just by convention

`derive_structure()` computes topology, message-passing chains, XC form,
and operator-construction *classification* -- all from graph shape alone.
`derive()` calls `derive_structure()` and adds only the `capabilities`
dict computed from that same structural derivation (message-passing
reachability, non-local capacity) -- nothing in that path ever opens a
parameter's actual stored values. `ir_sections()`/`validate_ir_sections()`/
`revalidate()` never reference anything resembling a real-weight
observation. There is no `locality`-shaped field anywhere in this plugin's
IR to accidentally leak a float through.

## Operator layout: beyond a literal n x n matrix

The self-energy is not necessarily stored as a plain `[N, N]` tensor. With
`m` orbitals (or spins) per site, a natural export shape is `[N, m, N, m]`
(site and orbital axes each split into a domain group and a codomain
group). Flattening `(site, orbital)` into one combined index still gives an
ordinary linear operator on the `N*m`-dimensional space -- so this plugin
does not hard-code "operator = rank-2 tensor."
`input_constraints.operator_layout` (optional; defaults to
`{"output_axes": [0], "input_axes": [1]}`, i.e. the plain matrix) declares
which axes form the codomain group and which form the domain group. Only
the canonical contiguous grouping (`output_axes=[0..r-1]`,
`input_axes=[r..2r-1]`) is supported; a reordered or interleaved grouping
is rejected outright, not guessed at.

This only matters for correctly recognizing the adjoint construction (and
therefore `self_adjoint`/`non_local_capacity`) for a grouped operator --
there is no float-reading anywhere in this plugin that would need to know
which axis is a "site" versus an "orbital", so the layout carries no
`site_axis`/locality-projection concept at all. For a plain matrix, any
reviewed transpose op is the (unique, if it actually swaps the two axes)
adjoint; `.t()`/`numpy_T` (no axis arguments, unambiguous for a two-axis
tensor) are accepted only there. `transpose.int(x, dim0, dim1)` and
`permute.default(x, dims)` are checked against their REAL arguments at
every rank -- a no-op call (`transpose.int(x, 0, 0)`, or
`permute(x, [0, 1])`) is not a transpose at all and is never accepted just
because its op name is on the reviewed list. For a grouped layout, only
`permute` can express the required swap of the whole domain group with the
whole codomain group, and its literal permutation argument must equal that
exact swap -- `numpy_T`/`.t()`/`transpose.int` are rejected outright once
there is more than one axis per side, because none of them can realize a
multi-axis block swap in one node.

Deliberately out of scope for now (a batch/frequency axis like `Σ(ω)` is
not itself an operator axis, and treating every extra tensor dimension as
part of the Hilbert-space operator would be wrong): axes outside the
declared `output_axes`/`input_axes` groups, complex/conjugate scalars
(this repo only ever extracts real floats), and non-contiguous or
reordered axis groupings.

## An `unconstrained_parameter` must actually be a parameter

`_operator_construction` checks the extractor's own `state_kind`
classification (from `torch.export`'s `graph_signature.input_specs`) and
rejects an explicit user-input classification, so `non_local_capacity`
(which claims a free, trainable matrix) can never be satisfied by a node
that's actually a plain runtime activation input. Permissive when no
classification is available at all (older extractor, hand-authored
specification), since that metadata is optional -- fails closed only on an
explicit signal, never a guess. This never applies to the `symmetrized`
recipe's own add/adjoint pair: `B + B^dagger` is self-adjoint for ANY `B`,
trained or not, so `self_adjoint` never needed this check.

## Adjacency selection is either declared or a labeled heuristic

`input_constraints.adjacency_state_name` is optional; when omitted, the
adjacency buffer is found by a name-match heuristic (any state entry whose
name contains `"adjacency"`). `semantic_derivations.topology.metadata.
selection_provenance` records `"declared"` or `"heuristic_name_match"`, so
a reader can tell which happened without re-deriving it.

## Lean

`examples/dft/lean/Testv2/StructuralV2.lean`:

- `allPairsReachable edges depth siteCount` -- `∀ x y, x = y ∨
  reachableWithin edges depth x y`.
- `canRepresentNonLocal siteCount : OperatorForm → Bool` -- `true` for
  `.parameter _` and `.add _ (.adjoint _)` / `.add (.adjoint _) _` only
  when `siteCount >= 2` (a 1x1 matrix has no off-diagonal entry for any
  recipe -- this is a real precondition of the claim, not a Python-only
  check layered on top of a Lean fact that doesn't mention it), `false`
  otherwise.
- `guaranteedSelfAdjoint`/`xcSupportsDiscontinuity`: unchanged, recipe-only.

`examples/dft/lean/Testv2/StructuralCapabilityMatrix.lean` (imports
Mathlib) states the actual real-matrix facts that `canRepresentNonLocal`/
`guaranteedSelfAdjoint` stand in for as computable `Bool` functions over the
finite `OperatorForm` grammar the analyzer emits. It is deliberately **not**
imported by `Testv2.lean` (the library's aggregator/default build target) --
doing so would make Mathlib a hard dependency of every other file in this
library, which the project's pinned toolchain cannot currently build (see
below). It is standalone, invoked directly (`lake env lean
Testv2/StructuralCapabilityMatrix.lean`), and nothing in the certificate
pipeline (`lean_import = "Testv2.StructuralV2"`) references it:

- `symmetrized_is_symm`: for every real matrix `B`, `B + Bᵀ` is symmetric
  (restates Mathlib's own `Matrix.isSymm_add_transpose_self` under this
  project's name).
- `symmetrized_can_be_nonlocal`: for `n ≥ 2`, some real matrix `B` makes
  `B + Bᵀ` non-local, witnessed by `Matrix.single 0 1 1`.

Both cite exact, source-verified Mathlib lemma/def names
(`Matrix.isSymm_add_transpose_self`, `Matrix.single`,
`Matrix.transpose_apply`), and neither uses `sorry`. `Testv2/StructuralV2.lean`
(no Mathlib dependency) is confirmed to build under `lake env lean` in this
environment.

**`Testv2/StructuralCapabilityMatrix.lean` could NOT be machine-verified in
this environment, and this is a real, pre-existing repo problem, not a
transient one**: `lake exe cache get` reports this project's
`lean-toolchain` (`v4.31.0`) does not match the vendored Mathlib checkout's
own (`v4.33.0-rc1`), so no prebuilt cache applies; building Mathlib from
source against the pinned `v4.31.0` toolchain then fails outright --
`Mathlib/Init.lean` itself does not elaborate under that Lean version
(`Invalid field notation ... cannot resolve field 'find?'`,
`failed to synthesize instance for 'for_in%' notation`). The vendored
Mathlib commit in `lake-manifest.json` is simply too new for this
project's pinned Lean toolchain. This is a repo-wide inconsistency (every
other file here is Mathlib-free specifically because of it) and fixing it
-- re-pinning the toolchain or the Mathlib `rev`, then re-vendoring -- is a
separate, riskier maintenance task well beyond this plugin. Until that
happens, treat `symmetrized_is_symm`/`symmetrized_can_be_nonlocal` as
**hand-checked against the real Mathlib API, not machine-verified anywhere
in this repo**.

## Known limitations

- `confirmed_description_ir` (the human-attested, no-artifact path) is not
  routed through the plugin interface at all -- it always builds a
  `capabilities`-shaped IR by hand, so a future second plugin would need
  its own lowering here rather than reusing this one automatically.
- No frozen evaluation corpus exists for this plugin yet -- the CLI and
  Python API are wired up, but there is no pinned corpus of
  positive/near-miss/unsupported/malformed cases the way the (now removed)
  post-training plugin's `evaluation/structural_v3/` had.
- No structural-fingerprint hash (a hash of everything except mutable
  trainable numeric values) exists yet. `source.parameter_structure_sha256`
  already hashes only shape/dtype/sha256/state_kind/aliases per parameter,
  which is close but still changes when a parameter's *content* hash changes
  post-training; a true training-invariant fingerprint would be a `core.py`
  change, out of scope here.
- `adjacency_convention` and `operator_layout` still silently default
  (`target_source` and the plain n x n matrix respectively) rather than
  being required. A stricter mode could reject a missing declaration
  outright instead of defaulting -- deliberately not done here, since it
  would break every existing certificate that relied on the default.
- The original `constraints.json`/specification file's own hash is not
  separately bound anywhere; only its normalized, resolved meaning (via
  `translation`/the IR) is hashed.
