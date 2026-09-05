# Pre-training architectural capability checks

`dftcert/structural/dft_plugin.py` (`DFTPlugin`) certifies a real fact about
a candidate's own *extracted trained floats*: is the learned self-energy
operator actually diagonal, or does it actually have a nonzero off-diagonal
entry (see `STRUCTURAL_V3.md`). That fact cannot exist before training --
there are no weights yet.

`dftcert/structural/dft_capability_plugin.py` (`DFTCapabilityPlugin`) checks
what *can* be established before training, from the architecture alone,
without reading a single floating-point value. Select it by passing
`plugin=DFT_CAPABILITY_PLUGIN` to the functions in `dftcert/structural/core.py`
instead of the default `DFT_PLUGIN`.

## What it checks

- **`all_pairs_reachable`**: every ordered pair of sites is reachable from
  every other within the declared message-passing depth -- a fact about
  `edges`/`depth`/`site_count` alone (graph diameter vs. depth). No pair is
  hand-picked; every pair is checked.
- **`non_local_capacity`**: when `expected_locality == "non_local"`, does the
  operator's construction *recipe* admit some parameter assignment with a
  nonzero off-diagonal entry? `zero`/`identity` never can; `symmetrized`
  (`B + B^T`) and `unconstrained_parameter` (a free matrix) always can. This
  reuses `DFTPlugin`'s existing construction classification -- a fact about
  the recipe, never about the values currently stored in it. When
  `expected_locality == "local"`, this check does not apply and is trivially
  satisfied.
- **`self_adjoint`**: unchanged from `DFTPlugin` -- it was already
  recipe-only (`construction in {zero, identity, symmetrized}`).
- **`xc_discontinuity_compatible`**: unchanged from `DFTPlugin`.

`supported()` does not require any extracted floats -- a `.pt2` with only
small bool/int adjacency buffers and no captured numeric weights is fully
certifiable by these checks.

`derive()` still computes `DFTPlugin`'s real-weight `locality` observation
(when floats are extractable) and it still appears in the IR/report, but it
is not one of this plugin's `checks()` and does not gate `supported()` or
its disposition -- it is an informational, non-authoritative observation
only. Running `DFTPlugin` on the same artifact after training gives the
authoritative post-training fact.

## Lean

`examples/dft/lean/Testv2/StructuralV2.lean` gains two defs, reusing the
existing `reachableWithin`/`OperatorForm` machinery:

- `allPairsReachable edges depth siteCount` -- `∀ x y, x = y ∨
  reachableWithin edges depth x y`.
- `canRepresentNonLocal : OperatorForm → Bool` -- `true` for `.parameter _`
  and `.add _ (.adjoint _)` / `.add (.adjoint _) _`, `false` for
  `.zero`/`.identity`/anything else.

`guaranteedSelfAdjoint` and `xcSupportsDiscontinuity` are reused as-is.

## Known limitations

- `confirmed_description_ir` (the human-attested, no-artifact path) is not
  routed through the plugin interface at all -- passing
  `plugin=DFT_CAPABILITY_PLUGIN` to it will fail IR validation because it
  never fills in `capabilities`. Fixing this is a `confirmed_description_ir`
  change that would apply to every plugin, not specific to this one.
- No structural-fingerprint hash (a hash of everything except mutable
  trainable numeric values) exists yet. `source.parameter_structure_sha256`
  already hashes only shape/dtype/sha256/state_kind/aliases per parameter,
  which is close but still changes when a parameter's *content* hash changes
  post-training; a true training-invariant fingerprint would be a `core.py`
  change applying to every plugin, out of scope here.
- No general theorem over arbitrary real matrices ("for any B, B + B^T is
  self-adjoint"; "for n >= 2, some B makes B + B^T non-local") was added.
  `canRepresentNonLocal`/`guaranteedSelfAdjoint` already give the same
  answer as computable `Bool` functions over the finite `OperatorForm`
  grammar the analyzer actually emits, which is what generated obligations
  need; a fully general Mathlib-style proof over `Matrix ℝ` would be a much
  larger undertaking with no effect on any certificate.
