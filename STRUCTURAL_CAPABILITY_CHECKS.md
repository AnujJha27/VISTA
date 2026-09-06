# Pre-training architectural capability checks

`dftcert/structural/dft_plugin.py` (`DFTPlugin`) certifies a real fact about
a candidate's own *extracted trained floats*: is the learned self-energy
operator actually diagonal, or does it actually have a nonzero off-diagonal
entry (see `STRUCTURAL_V3.md`). That fact cannot exist before training --
there are no weights yet.

`dftcert/structural/dft_capability_plugin.py` (`DFTCapabilityPlugin`) checks
what *can* be established before training, from the architecture alone.
Reachable end-to-end from the CLI too: `analyze-pt2`/`analyze-extraction`
take `--profile dft-capability` (default `dft`); `generate`/`report`/
`assemble` resolve the plugin from the loaded IR's own `ir_schema_version`
(`3` -> `DFT_PLUGIN`, `4` -> `DFT_CAPABILITY_PLUGIN`) rather than a separate
flag, so the choice is certificate-bound (covered by `ir_sha256`) and
cannot be pointed at the wrong plugin after the fact. From Python, pass
`plugin=DFT_CAPABILITY_PLUGIN` to the functions in
`dftcert/structural/core.py` instead of the default `DFT_PLUGIN`.

## `derive()` is split so the capability path truly never reads a float

`DFTPlugin.derive()` used to compute topology/message-passing/XC/operator
classification *and* the real-weight locality observation in one method.
It is now `derive_structure()` (topology, message-passing chains, XC form,
operator-construction recipe -- no float ever read) plus `derive()`
(`derive_structure()` + `_locality_from_recipe`, the only place that reads
an extracted parameter's floating-point content).
`DFTCapabilityPlugin.derive()` calls `derive_structure()` only -- never
`derive()` -- so its derivation, IR, and checks never contain a `locality`
field or anything computed from one. This is enforced structurally, not
just by convention: `ir_sections()`/`validate_ir_sections()`/`revalidate()`
for this plugin never reference `value["locality"]` at all (previously an
earlier draft still inherited `locality` from `derive()` and only left it
out of the *gating* checks -- that made the "no floating-point value" claim
true only of the check outcome, not of the pipeline that produced it; fixed
here by never computing it in the first place).

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
  for any recipe. This reuses `DFTPlugin`'s existing construction
  classification -- a fact about the recipe and site count, never about
  the values currently stored in it.
- **`self_adjoint`**: unchanged from `DFTPlugin` -- already recipe-only.
- **`xc_discontinuity_compatible`**: unchanged from `DFTPlugin`.

`supported()` does not require any extracted floats -- a `.pt2` with only
small bool/int adjacency buffers and no captured numeric weights is fully
certifiable by these checks.

`non_local_capacity`'s "off-diagonal entry" is layout-agnostic by
construction: it only asks whether the recipe kind and site count admit
*some* assignment with a cross-site coupling, never inspecting a concrete
shape. So `input_constraints.operator_layout` (see `STRUCTURAL_V3.md` for
the full design -- a self-energy with orbital/spin axes, e.g. shape
`[N, m, N, m]`, rather than a plain `[N, N]` matrix) needs no special
handling here; `derive_structure()` resolves and echoes it in
`operator.layout` for every plugin built on this module, and the adjoint
recognition it gates (rejecting `numpy_T`/`.t()` for a grouped layout,
requiring an exact permutation match) is shared, symbolic, structural code
-- never a reason this plugin would need to touch a float.

## Lean

`examples/dft/lean/Testv2/StructuralV2.lean` gains two defs, reusing the
existing `reachableWithin`/`OperatorForm` machinery:

- `allPairsReachable edges depth siteCount` -- `∀ x y, x = y ∨
  reachableWithin edges depth x y`.
- `canRepresentNonLocal : OperatorForm → Bool` -- `true` for `.parameter _`
  and `.add _ (.adjoint _)` / `.add (.adjoint _) _`, `false` for
  `.zero`/`.identity`/anything else.

`examples/dft/lean/Testv2/StructuralCapabilityMatrix.lean` (new, imports
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
project's pinned Lean toolchain. This is a repo-wide inconsistency
predating this change (every other file here is Mathlib-free specifically
because of it) and fixing it -- re-pinning the toolchain or the Mathlib
`rev`, then re-vendoring -- is a separate, riskier maintenance task well
beyond this plugin. Until that happens, treat
`symmetrized_is_symm`/`symmetrized_can_be_nonlocal` as **hand-checked
against the real Mathlib API, not machine-verified anywhere in this repo**.

## Known limitations

- `confirmed_description_ir` (the human-attested, no-artifact path) is not
  routed through the plugin interface at all -- passing
  `plugin=DFT_CAPABILITY_PLUGIN` to it will fail IR validation because it
  never fills in `capabilities`. Fixing this is a `confirmed_description_ir`
  change that would apply to every plugin, not specific to this one.
- No frozen evaluation corpus exists for this plugin yet
  (`evaluation/structural_v3/` has no capability-plugin counterpart) --
  the CLI and Python API are wired up, but there is no corpus of
  positive/near-miss/unsupported/malformed cases pinned the way
  `evaluation/structural_v3/corpus_manifest.json` pins `DFTPlugin`'s.
- No structural-fingerprint hash (a hash of everything except mutable
  trainable numeric values) exists yet. `source.parameter_structure_sha256`
  already hashes only shape/dtype/sha256/state_kind/aliases per parameter,
  which is close but still changes when a parameter's *content* hash changes
  post-training; a true training-invariant fingerprint would be a `core.py`
  change applying to every plugin, out of scope here.
