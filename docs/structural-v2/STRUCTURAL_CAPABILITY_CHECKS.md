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

## Provisional graph-hop locality correction (theorem-centric path)

**This section documents a further research-soundness correction. It does
not present a final physical definition of locality; the exact physical
notion of "long-range" for this domain is provisional pending domain-expert
confirmation.**

> VISTA currently uses graph-hop distance greater than a configurable range
> `R` as a provisional operational definition of long-range coupling. The
> graph is artifact-grounded; `R` is a specified domain parameter; the
> long-range relation is derived by VISTA.

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
into a structural check. A first correction addressed this by requiring an
explicitly, hand-supplied list of long-range site pairs -- itself later
retired: a hand-picked pair is a human interpretation with no connection to
the artifact's actual topology at all, and let the caller "declare" long-
range coupling into existence regardless of the real adjacency graph.

The theorem-centric requirement (`Testv2.Requirements.
ValidPretrainingArchitecture`/`...Conditional`) now uses a provisional,
purely operational notion instead: **shortest-path graph distance greater
than a configurable range `R`** (`LongRange_R(i, j) := shortestPathDistance_G(i,
j) > R`), derived by VISTA from the artifact's own adjacency graph -- never
a hand-supplied pair set. `non_local_capacity`/`canRepresentNonLocal`
(Lean) remain in this codebase only as deprecated, historical values --
kept so any already-generated certificate that references them stays
re-checkable, never used as the live theorem-centric capacity premise.

The corrected design:

- **`locality_range`** (interface_contract field, default `4`): the
  graph-hop radius `R` within which two sites are considered local. This
  is the **only** locality datum VISTA accepts, and it is **SPECIFIED
  INTERFACE**, never artifact-grounded -- the artifact establishes site
  count, adjacency, and operator construction, never which graph-hop
  radius counts as "local" for this domain. Syntax-validated at
  package-authoring time (`_locality_range`: must be a non-negative
  integer). VISTA never accepts a hand-supplied long-range pair list at
  any point in this pipeline.
- The long-range pair set itself is **inferred**, never specified: given
  the artifact-grounded adjacency graph and the specified `R`, VISTA (in
  Python, for the IR's own `long_range_capacity` field, and independently
  in Lean, for the live theorem-centric premise) computes shortest-path
  distance and derives which pairs exceed `R`. Provenance is therefore:
  adjacency/graph -> Extracted; `locality_range` (`R`) -> Specified
  interface; shortest-path distance -> Inferred; long-range pair set ->
  Inferred.
- **`long_range_capacity`** (capability, theorem-centric-authoritative):
  `None` means unsupported/unresolved (a grouped `[N, m, N, m]` operator
  layout, where there is no established correspondence between a flattened
  tensor axis and the physical site index -- see "Grouped operator
  layouts" below); otherwise `True`/`False` depending on whether the
  construction contains a confirmed free parameter (never a fixed buffer,
  constant, or unknown classification) AND the derived graph-hop-distance
  relation places at least one pair of distinct sites more than
  `locality_range` hops apart. Disconnected pairs are handled explicitly
  and consistently: they are always long-range, at any `R`, since they are
  unreachable at any depth. Message-passing depth never enters this
  computation at all -- GNN receptive field and operator long-range
  capacity are unrelated statements, deliberately kept separate
  (`ValidMessagePassingCoverage` stays its own entrypoint).
- Self-adjointness is **never** weakened by any of this: `guaranteedSelfAdjoint`
  holds for `B + Bᵀ` regardless of whether `B` is a confirmed parameter or a
  grouped layout -- only the stronger long-range-capacity claim needs the
  extra evidence.

**Paper-safe claim after this correction:** given a specified graph-hop
range `R`, VISTA derives which site pairs its own artifact-grounded
adjacency graph places more than `R` hops apart, and checks whether the
exported architecture contains sufficient structural freedom to represent
coupling on at least one such pair, while independently checking structural
self-adjointness and other selected Lean requirements. It does **not**
claim to have proven the self-energy is physically non-local, and it does
**not** claim that graph-hop distance beyond `R` is itself the physically
correct notion of "long-range" for this domain -- that operational
definition is specified (via `R`), not verified.

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
- **`long_range_capacity`**: when `expected_locality == "non_local"`, does
  the operator's construction *recipe* admit some parameter assignment
  with nonzero coupling on at least one site pair the artifact-grounded
  adjacency graph places more than the specified `locality_range` (`R`)
  hops apart? This is the SAME graph-hop definition the theorem-centric
  path uses (`long_range_capacity` above) -- this legacy fixed-policy check
  no longer uses the retired "some off-diagonal entry exists" criterion
  (`non_local_capacity`, kept in the IR only as a deprecated historical
  value; see "Provisional graph-hop locality correction" above).
  `zero`/`identity` never have this freedom, for any assignment.
  `unconstrained_parameter` and `symmetrized` can, but only when the
  parameter is confirmed trainable (a fixed buffer, constant, or missing
  classification is still self-adjoint by construction, when symmetrized,
  but has no parameter to choose) AND the derived graph-hop relation
  actually classifies some pair as long-range. A fact about the recipe,
  the parameter-confirmation evidence, and the topology, never about the
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
observation. The only locality-shaped field anywhere in this plugin's IR
is `locality_range` -- a single specified integer, never a float, never a
hand-supplied pair list.

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

## Adjacency selection is always declared, never guessed

`input_constraints.adjacency_state_name` is REQUIRED -- which state entry
is "the adjacency" is a specified-interface interpretation, exactly like
`output_contracts`, and is never inferred from a name-match heuristic. An
artifact could otherwise contain, say, both `fake_adjacency_debug` and
`physical_neighbour_matrix`; a heuristic ("any state entry whose name
contains `adjacency`") could silently select the wrong one while remaining
fully deterministic and while the selected tensor's own values were still
genuinely extracted -- the proposition "these values encode the graph
locality is defined on" would still be an unverified interpretation, not an
artifact fact. `semantic_derivations.topology.metadata.selection_provenance`
is always `"declared"`.

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
- `LocalityRange` -- a genuine wrapper `structure` around a bare `Nat`
  (`range`), not a type alias: the theorem-centric resolver matches a
  candidate to a binder purely by Lean TYPE, and a plain `Nat` would risk
  silent cross-matching with the unrelated `siteCount : Nat` binder.
- `isLongRangePair edges locality pair : Bool` -- `pair.1 != pair.2 &&
  !reachableWithin edges locality.range pair.1 pair.2`: two distinct sites
  whose shortest-path distance in `edges` exceeds `locality.range`: derived
  from the graph and `R` alone, never a hand-supplied pair. A self-pair
  (`i = i`) is never a witness. A disconnected pair (unreachable at any
  depth) is long-range at any `R`, handled by the same predicate, no
  special case.
- `hasLongRangePair siteCount edges locality : Bool` -- whether some pair
  of distinct sites in `[0, siteCount)` is long-range under `locality`.
- `canRepresentLongRangeCoupling siteCount edges locality : OperatorForm →
  Bool` -- the live, theorem-centric-authoritative capacity premise.
  `true` for a bare `.parameter _`, or the same `add`/`adjoint` `.parameter`
  shapes as `canRepresentNonLocal`, but only when `hasLongRangePair
  siteCount edges locality` -- never merely `siteCount >= 2`. `false`
  otherwise, including for `.opaque`.
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
finite `OperatorForm` grammar the analyzer emits. It **is** imported by
`Testv2.lean` (the library's aggregator/default build target) and is
machine-checked by a plain `lake build`, under the same pinned Lean v4.31.0 /
Mathlib v4.31.0 toolchain as the rest of this library -- Mathlib was already
a dependency of other files in this library (e.g. `StructuralV2.lean`), so
importing it here adds no new toolchain requirement. Nothing in the
certificate pipeline (`lean_import = "Testv2.StructuralV2"`) references it;
it exists to justify, over actual Mathlib matrices, the two `OperatorForm`
recipe guarantees the certificate pipeline's `Bool` functions assert:

- `symmetrized_is_symm`: for every real matrix `B`, `B + Bᵀ` is symmetric
  (restates Mathlib's own `Matrix.isSymm_add_transpose_self` under this
  project's name).
- `symmetrized_can_be_nonlocal`: for `n ≥ 2`, some real matrix `B` makes
  `B + Bᵀ` non-local, witnessed by `Matrix.single 0 1 1`.

Both cite exact, source-verified Mathlib lemma/def names
(`Matrix.isSymm_add_transpose_self`, `Matrix.single`, `Matrix.single_apply`,
`Matrix.transpose_apply`), and neither uses `sorry`. `Testv2/StructuralV2.lean`
and `Testv2/StructuralCapabilityMatrix.lean` both build cleanly under
`lake build` in this environment.

**`Testv2/StructuralCapabilityMatrix.lean` is machine-verified in this
repo.** Two earlier blockers, both now resolved:

- A stale LOCAL `lake-manifest.json` had drifted out of sync with
  `lakefile.toml`'s already-correct `rev = "v4.31.0"` pin (never
  regenerated after that pin was set), which was previously misdiagnosed as
  a `lean-toolchain`/Mathlib version incompatibility. `lake update`, run
  against the unchanged `v4.31.0` toolchain (never an upgrade), regenerates
  a correct manifest. `lake-manifest.json` itself is gitignored, so a fresh
  checkout (including CI) resolves correctly from `lakefile.toml`'s pin and
  was never actually affected by this local staleness.
- Adding `import Mathlib.Data.Real.Basic` (needed to resolve an `ℝ`
  instance-resolution gap this file's other two imports leave open)
  exposed a parser error, `unexpected token 'namespace'; expected 'lemma'`,
  at the `namespace Testv2.StructuralCapabilityMatrix` line. Root cause:
  the doc comment directly above that line used `/-- -/` (declaration-doc
  syntax, valid only immediately before a `def`/`theorem`/etc.) where
  `namespace` requires `/-! -/` (module/section-doc syntax). Fixing the
  comment kind and adding the import resolved both issues; no changes were
  needed to `symmetrized_is_symm` or `symmetrized_can_be_nonlocal`
  themselves, since `Matrix.single_apply` (used in the latter's proof)
  already exists in the vendored Mathlib rev and was never the problem.

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
