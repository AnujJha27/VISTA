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
uses it unless a different `plugin=` is passed explicitly. The CLI
(`dftcert/structural/cli.py`) still keeps a plugin registry (`PROFILES`,
selected via `--profile` on `analyze-pt2`/`analyze-extraction`; `generate`/
`report`/`assemble` resolve the plugin from the loaded IR's own
`ir_schema_version`, so the choice is certificate-bound rather than a flag
that could be pointed at the wrong plugin after the fact) with a single
entry registered today -- kept as a registry rather than hardcoded to one
plugin specifically so a future second plugin (a different verification
domain, or a second DFT variant) is "add an entry," not "redesign the CLI."

## Provisional long-range-coupling correction (theorem-centric path)

**This section documents a further research-soundness correction. It does
not present a final physical definition of locality; the exact physical
notion of "long-range" for this domain is provisional pending domain-expert
confirmation.**

`non_local_capacity` (below) treats "the operator's construction recipe
admits *some* nonzero off-diagonal entry" as the notion of non-locality.
That itself was already a correction from an earlier, unsound version that
granted capacity to any `symmetrized` construction regardless of parameter
confirmation (see the `symmetrized` bullet below). But even the corrected
`non_local_capacity` still has a deeper issue for the THEOREM-CENTRIC path
specifically: an arbitrary off-diagonal entry does not, by itself,
establish that the coupling it represents is between sites the domain
actually considers physically far apart ("long-range"). Treating `i ≠ j`
alone as sufficient was itself an unverified physical assumption smuggled
into a structural check.

The theorem-centric requirement (`Testv2.Requirements.
ValidPretrainingArchitecture`/`...Conditional`) has been corrected to use a
provisional, explicitly weaker and more honest notion instead:
**representational capacity to couple at least one EXPLICITLY SPECIFIED
long-range site pair**, never an inferred one. `non_local_capacity`/
`canRepresentNonLocal` (Lean) remain in this codebase only as deprecated,
historical values -- kept so any already-generated certificate that
references them stays re-checkable, never used as the live theorem-centric
capacity premise.

The corrected design:

- **`long_range_pairs`** (interface_contract field, e.g. `[[0, 3]]`): which
  site pairs the domain specification declares to be outside the
  local/short-range region. This is **SPECIFIED INTERFACE**, never
  artifact-grounded -- the artifact establishes site count and operator
  construction, never which physical distances count as "long-range."
  Syntax-validated at package-authoring time (`_long_range_pairs_syntax`:
  each entry must be a pair of non-negative integers); bounds against the
  artifact's own derived `site_count` are validated later, by
  `Testv2.StructuralV2.validLongRangePair` itself, once the artifact is
  known (a package may be authored before the artifact is). An
  out-of-range pair or a self-pair (`i = i`) is never counted as valid --
  fails closed, never raises.
- **`long_range_capacity`** (capability, theorem-centric-authoritative):
  `None` means unsupported/unresolved (a grouped `[N, m, N, m]` operator
  layout, where there is no established correspondence between a flattened
  tensor axis and the physical site index -- see "Grouped operator
  layouts" below); otherwise `True`/`False` depending on whether the
  construction contains a confirmed free parameter (never a fixed buffer,
  constant, or unknown classification) AND at least one of the specified
  `long_range_pairs` is valid for the derived `site_count`. Message-passing
  depth never enters this computation at all -- GNN receptive field and
  operator long-range capacity are unrelated statements, deliberately kept
  separate (`ValidMessagePassingCoverage` stays its own entrypoint).
- Self-adjointness is **never** weakened by any of this: `guaranteedSelfAdjoint`
  holds for `B + Bᵀ` regardless of whether `B` is a confirmed parameter or a
  grouped layout -- only the stronger long-range-capacity claim needs the
  extra evidence.

**Paper-safe claim after this correction:** given an explicit specification
of which site pairs count as long-range, VISTA checks whether the exported
architecture contains sufficient structural freedom to represent coupling
on at least one such pair, while independently checking structural
self-adjointness and other selected Lean requirements. It does **not**
claim to have proven the self-energy is physically non-local, and it does
**not** claim that the supplied long-range classification is itself
physically correct -- that interpretation is specified, not verified.

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
  `zero`/`identity` never can. `unconstrained_parameter` (a free matrix)
  can, and always requires a confirmed trainable parameter to even reach
  that classification. `symmetrized` (`B + B^T`) can too, but only when
  `B` is confirmed a free/trainable parameter -- a `B` the artifact gives
  no positive trainability evidence for (a fixed buffer, a constant, or
  simply missing classification metadata) is still self-adjoint by
  construction, but has no parameter to choose and therefore no capacity
  to realize an off-diagonal entry, exactly like `zero`/`identity`. A
  second site must also exist for an off-diagonal entry to live at -- a
  1x1 matrix has none, for any recipe. A fact about the recipe, the
  parameter-confirmation evidence, and site count, never about the values
  currently stored in it.
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

## A claim of trainable freedom must actually be positively confirmed

`_operator_construction`/`_is_plausible_parameter_node` check the
extractor's own `state_kind` classification (from `torch.export`'s
`graph_signature.input_specs`) and require an explicit, positive
`InputKind.PARAMETER` marker before treating a node as a free, trainable
matrix. This is a fail-closed allowlist, not a blacklist of known-bad
kinds: an explicit user-input, buffer, or constant classification is
rejected, and so is a MISSING or unrecognized classification (e.g. an
older extractor, or a hand-authored specification that never set
`state_kind` at all) -- there is no permissive default for "we don't
know."

This positive-evidence requirement gates `unconstrained_parameter`
unconditionally (that classification literally cannot be reached without
it) and, separately, gates the `symmetrized` recipe's `non_local_capacity`
claim specifically. It never gates `symmetrized`'s own CLASSIFICATION or
its `self_adjoint` claim: `B + B^dagger` is self-adjoint for ANY `B`,
trained or not, so recognizing the construction and its self-adjointness
never needed this check and never will. Only the stronger claim, that the
construction additionally has non-local representational capacity, needs
a confirmed parameter to choose -- see `non_local_capacity` above.

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
- `canRepresentNonLocal siteCount : OperatorForm → Bool` -- **DEPRECATED /
  HISTORICAL ALIAS**, kept only so an already-generated certificate that
  references it stays re-checkable; no longer the theorem-centric-
  authoritative capacity premise (see "Provisional long-range-coupling
  correction" above). `true` for a bare `.parameter _`, or
  `.add (.parameter _) (.adjoint (.parameter _))` / `.add (.adjoint
  (.parameter _)) (.parameter _)`, only when `siteCount >= 2`; `false`
  otherwise, including for the exact same `add`/`adjoint` shape built from
  `.opaque` instead of `.parameter`.
- `validLongRangePair siteCount pair : Bool` -- both indices `< siteCount`
  and distinct; fails closed (false) on an out-of-bounds index or a
  self-pair, never raises.
- `LongRangePairs` -- a genuine wrapper `structure` around `List (Nat ×
  Nat)`, not a bare type alias: the theorem-centric resolver matches a
  candidate to a binder purely by Lean TYPE, and a plain alias would still
  be definitionally equal to `List (Nat × Nat)`, risking silent
  cross-matching with `ValidMessagePassingCoverage`'s own, unrelated
  `edges : List (Nat × Nat)` binder.
- `canRepresentLongRangeCoupling siteCount longRangePairs : OperatorForm →
  Bool` -- the live, theorem-centric-authoritative capacity premise.
  `true` for a bare `.parameter _`, or the same `add`/`adjoint` `.parameter`
  shapes as `canRepresentNonLocal`, but only when `longRangePairs` contains
  at least one pair valid for `siteCount` (`hasValidLongRangePair`) --
  never merely `siteCount >= 2`. `false` otherwise, including for `.opaque`.
- `OperatorForm` also has an `.opaque (name : String)` constructor,
  distinct from `.parameter`: a base term that is self-adjoint when
  symmetrized with its own adjoint (`guaranteedSelfAdjoint` holds for it
  exactly as it does for `.parameter`, since that only ever compares the
  two sides for equality) but never contributes long-range representational
  capacity, since `canRepresentLongRangeCoupling` only grants capacity to
  an actual `.parameter`.
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

**`Testv2/StructuralCapabilityMatrix.lean` still could NOT be
machine-verified in this environment, but the previous diagnosis of why
was wrong and has been corrected (research-readiness hardening pass).**
The earlier claim here was that this project's `lean-toolchain` (`v4.31.0`)
was older than the vendored Mathlib checkout required (`v4.33.0-rc1`), and
that neither a prebuilt cache nor a from-source build could succeed as a
result. That was traced to a stale LOCAL `lake-manifest.json` that had
drifted out of sync with `lakefile.toml`'s already-correct `rev =
"v4.31.0"` pin (never regenerated after that pin was set) -- not a real
incompatibility. `lake update`, run against the unchanged `v4.31.0`
toolchain (never an upgrade), regenerates a correct manifest, and the rest
of this Lean project (including files that import Mathlib, like this one's
neighbors would if they needed to) builds and passes `lake exe cache get`
cleanly under it. `lake-manifest.json` itself is gitignored, so every
fresh checkout (including CI) already resolves correctly from
`lakefile.toml`'s pin and was never actually affected by this local
staleness.

The actual remaining blocker for this specific file is different: adding
`import Mathlib.Data.Real.Basic` (needed to resolve an `ℝ` instance-
resolution gap this file's own two imports leave open) triggers a parser
error, `unexpected token 'namespace'; expected 'lemma'`, at the
`namespace Testv2.StructuralCapabilityMatrix` line above. Not yet
root-caused. Until it is fixed, treat `symmetrized_is_symm`/
`symmetrized_can_be_nonlocal` as **hand-checked against the real Mathlib
API, not machine-verified anywhere in this repo**.

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
