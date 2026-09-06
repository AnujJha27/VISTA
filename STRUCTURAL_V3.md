# Structural V3: locality claims verified against the candidate's own values

V3 replaces Structural V2's `required_couplings` (a list of `(source,
target)` pairs, hand-authored in the same file as the candidate's own
constraints) entirely. It does not touch XC semantics or the self-adjoint
check. V1/V2 remain reproducible unchanged; see `evaluation/structural_v2/`
(frozen, untouched).

> **Note:** the domain-agnostic split described in `VISTA_GENERALIZATION.md`
> has since been implemented: `dftcert/structural/core.py` is now a generic
> harness, and everything below (topology/xc/operator/locality) lives in
> `dftcert/structural/dft_plugin.py` as `DFTPlugin`, the harness's default
> plugin. The semantics described below are unchanged -- this document still
> accurately describes what the DFT plugin checks and why; it's just
> reached through a `plugin` argument now (defaulting to `DFT_PLUGIN`, so
> nothing calling it changed).

## Why `required_couplings` had to go, not just move

An earlier V3 draft moved the coupling pairs into a separate
"reference-operator" file, independently hash-bound and validated. That
was a real, tested, working design -- but it was still, mechanically, a
human typing `{"source": 0, "target": 3}` somewhere. Generic non-locality
(`NonLocal(Sigma)`) never identifies *which* pair is required either -- that
was the original design's own stated constraint, and it is exactly why a
pair had to come from *somewhere*, supplied by *someone*. No matter how much
tamper-evidence and provenance is wrapped around that file, the number itself
is still asserted, not derived from anything.

**V3 asks a different, answerable question instead: is the candidate's own
learned self-energy operator actually local (diagonal) or actually non-local
(has a genuine off-diagonal entry)?** That is a real fact about the
candidate's own extracted trained values -- computable, not asserted, by
anyone.

## Old data flow (rejected)

```
candidate .pt2 -> candidate structural facts (adjacency, depth)
                                                          |
required_couplings / reference-operator file             |
(a human, somewhere, typing (source, target) pairs) ------+---> obligations -> Lean
```

## New data flow (V3)

```
candidate .pt2 --------> extractor also captures small (<=4096-element)
                          FLOAT parameter values, not just bool/int shape
                          evidence (extractors/torch_export_worker.py)
                                     |
                                     v
                     dftcert.structural.core._operator_matrix
                     computes the operator's REAL concrete matrix from
                     those values, using the *same* recipe the analyzer
                     already uses to classify zero/identity/symmetrized/
                     unconstrained_parameter -- one source of truth
                                     |
                                     v
                     _observed_locality: real off-diagonal-nonzero pairs,
                     against a fixed named/versioned threshold
                                     |
                                     v
              +----------------------+----------------------+
              |                                              |
  analyst's expected_locality claim               observed_local (real fact)
  ("local" or "non_local", an input                                |
  constraint -- never a pair)                                      |
              +----------------------+----------------------+
                                     |
                                     v
                    operator_locality_verified check
                    (claim vs. real fact -- reported, not gamed)
                                     |
                                     v
                                   Lean
                                     |
                                     v
                          hash-bound certificate
```

## What actually changed

- `extractors/torch_export_worker.py` (`torch-export-inventory-v3`): also
  captures literal values for small float state tensors (previously only
  bool/int), tagged `structural_value_kind: "numeric"` so the analyzer never
  confuses a real weight with exact structural evidence.
- `dftcert/structural/core.py`: `_operator_construction` now returns a
  `recipe` (`zero` / `identity` / `param` / `sum_transpose`) alongside its
  existing classification -- the single source of truth `_operator_matrix`
  uses to compute the concrete matrix from raw extracted values.
  `_observed_locality` finds the real off-diagonal-nonzero pairs against a
  fixed, named, versioned rule (`operator_offdiag_abs_threshold`, threshold
  `1e-9` -- a property of the analyzer, not configurable per run, so nobody
  can tune it to make a model pass). `IR.locality = {expected, available,
  observed_local, off_diagonal_nonzero, rule}` replaces `IR.requirements`.
  `validate_translation` independently recomputes the whole thing from raw
  inventory and rejects any disagreement -- hand-editing the observation, or
  changing the claim without re-deriving, both fail closed.
- `dftcert/structural/reference.py` and the whole reference-operator/Q_ref
  mechanism: deleted. There is no external reference file anymore.
- `examples/dft/lean/Testv2/StructuralV2.lean`: adds `localityMatches
  (expectedLocal : Bool) (observedNonzeroOffDiagonal : List (Nat × Nat)) :
  Bool := expectedLocal == observedNonzeroOffDiagonal.isEmpty`. The old
  `allCovered`/`reachableWithin` stay, unused by the live pipeline, only so
  frozen V2 certificates remain re-checkable.
- CLI: `--reference-operator` is gone. `input_constraints.expected_locality`
  (`"local"` or `"non_local"`) is now a required field; `required_couplings`
  is gone from the normal path entirely.

## Verification semantics

`operator_locality_verified` is satisfied when `expected_locality` matches
`observed_local`, and `observed_local` could actually be determined (the
construction was recognized and its parameters were small enough to
capture). When the construction is unrecognized or the parameter is too
large, locality is `available: false` -- VISTA reports "undetermined," never
guesses, and the overall disposition becomes `formalization_required`
regardless of the claim.

A `true` result means only: *"the candidate's own extracted operator values
are actually diagonal (or actually have a real off-diagonal entry), matching
the declared expectation."* It does **not** establish training convergence,
numerical accuracy of the coupling *magnitudes*, or general physical
correctness -- only the coarse local/non-local fact, computed from real data.

## Certificate binding

The generated Lean preamble carries `observedNonzeroOffDiagonal` (the real
pairs, computed -- never supplied) and `expectedLocal`. The certificate binds
`sourceSha256`/`irSha256` exactly as before; there is no separate
reference-hash binding anymore since there is no separate reference file.

## Evaluation corpus

`evaluation/structural_v3/corpus_manifest.json` (13 frozen cases) and
`fresh_held_out_manifest.json` (6 held-out cases) cover: positive matches for
`zero`/`identity`/`symmetrized` constructions across both `chain` and `ring`
topologies; real, caught mismatches (a genuinely local operator claimed
non-local and vice versa); an independent-dimension near-miss (locality
passes, self-adjoint or XC fails, on their own); several distinct
unsupported-construction recognition boundaries (`nested`, `indirect`,
`transformed`, `diagonal`); and general malformed-input diversity (invalid
`expected_locality`, missing/duplicate output roles, invalid adjacency).

## Operator layout: beyond a literal n x n matrix

The self-energy is not necessarily stored as a plain `[N, N]` tensor. With
`m` orbitals (or spins) per site, a natural export shape is `[N, m, N, m]`
(site and orbital axes each split into a domain group and a codomain
group). Flattening `(site, orbital)` into one combined index still gives an
ordinary linear operator on the `N*m`-dimensional space -- so VISTA does not
hard-code "operator = rank-2 tensor." `input_constraints.operator_layout`
(optional; defaults to `{"output_axes": [0], "input_axes": [1],
"site_axis": 0}`, i.e. today's plain matrix) declares which axes form the
codomain group, which form the domain group, and which position within
each group is the site axis (the rest are orbital/spin/etc. axes, where
mixing on the SAME site never counts as a coupling across sites). Only the
canonical contiguous grouping (`output_axes=[0..r-1]`,
`input_axes=[r..2r-1]`) is supported; a reordered or interleaved grouping
is rejected outright, not guessed at.

This also changes what counts as the adjoint. For a plain matrix, any
reviewed transpose op is the (unique) adjoint. For a grouped layout, only
`aten.permute.default` can express the required swap of the whole domain
group with the whole codomain group, and its literal permutation argument
must equal that exact swap; `numpy_T`/`.t()`/`transpose.int` are rejected
for a grouped layout because none of them can realize a multi-axis block
swap in one node. `_observed_locality` also changes: instead of raw
row/column indices, it compares the SITE coordinate of each flattened row
and column (via `layout.site_axis`), so `off_diagonal_nonzero` reports real
site-to-site couplings, not merely off-diagonal entries in the flattened
matrix -- on-site orbital/spin mixing is still local. For the default
layout this reduces exactly to the original diagonal/off-diagonal check
(row IS the site, column IS the site), so every certificate issued before
this field existed is unaffected.

Deliberately out of scope for now (a batch/frequency axis like `Σ(ω)` is
not itself an operator axis, and treating every extra tensor dimension as
part of the Hilbert-space operator would be wrong): axes outside the
declared `output_axes`/`input_axes` groups, complex/conjugate scalars
(this repo only ever extracts real floats), and non-contiguous or
reordered axis groupings. Extending to any of these is a `_resolve_operator_layout`/
`_read_operator_tensor` change, not a rewrite of the recognition or
locality logic around it.

## Known limitations

- Locality is only checked for recognized, small (<=4096-element)
  constructions. A construction VISTA doesn't recognize (e.g. `torch.diag`,
  a scaled adjoint, a nested sum) is correctly left undetermined even when
  it happens to be genuinely local or non-local -- this is deliberate
  fail-closed behavior, not a gap to "fix" by guessing.
- The threshold (`1e-9`) is fixed and disclosed, not derived from the
  model's own numerical scale; a model whose intended-nonzero couplings are
  all smaller than that (or intended-zero couplings all larger, due to
  optimizer noise) would be misjudged. This is the same fixed-tolerance
  trade-off any exact-vs-numeric boundary makes; it is recorded in every
  certificate's `locality.rule`, never applied silently.
