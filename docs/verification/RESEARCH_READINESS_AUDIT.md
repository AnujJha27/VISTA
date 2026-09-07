# VISTA Research-Readiness Audit

A focused research-soundness hardening pass over the theorem-centric VISTA
pipeline, following the prior hardening passes (theorem-centric-gaps issues
1-16, A-I; the earlier research-readiness red-team pass). This document is
a developer artifact, not marketing copy. Where something is unsupported,
this says so explicitly. It supersedes all prior versions of this file.

## 1. Exact implemented claim

> VISTA checks whether artifact-grounded structural facts are sufficient to
> establish selected Lean requirements under explicit interface and
> external assumptions, and emits an artifact-bound certificate whose
> formal conclusions are checked by Lean.

Nothing more. In particular, this claim does **not** mean: that Lean
verifies the model itself; that Lean proves an external assumption true;
that runtime hash consistency is equivalent to a cryptographic digital
signature; that the tool has demonstrated generality across artifacts,
architectures, or scientific domains; that any trained floating-point
value has been verified; or that an unsupported mathematical bridge (e.g.
`Testv2/StructuralCapabilityMatrix.lean`, see section 16) has been
machine-checked.

## 2. Trusted computing base

- The Lean 4 kernel + the pinned `mathlib` revision (`v4.31.0`,
  `examples/dft/lean/lean-toolchain`/`lakefile.toml`) -- the only component
  that performs formal proof checking.
- `extractors.torch_export_worker.extract` -- the sole PT2 deserialization
  boundary, run inside a Bubblewrap sandbox in the fully-safe path.
  `trusted_local=True` bypasses this boundary entirely for an
  already-produced extraction result -- see section 11.
- `dftcert.structural.dft_capability_plugin.DFT_CAPABILITY_PLUGIN` -- the
  one domain adapter, looked up only via the generic registry
  (`dftcert.structural.plugin.get_adapter`, research-readiness audit issue
  7) -- the verification harness (`dftcert.verification.api`) never
  imports this concrete module by name, guarded by
  `tests/test_public_api.py::AdapterRegistryDependencyDirectionTests`.
  Its own source file's hash is bound into every session/certificate it
  produces.
- `dftcert.verification.*` (session, resolver, certificate, package, api,
  cli) -- the generic, domain-agnostic theorem-centric harness.
- The operating system / filesystem / Python interpreter each component
  runs under -- not independently attested (no reproducible-build or
  remote-attestation layer exists).

## 3. Extracted facts

Directly from `extractors.torch_export_worker.extract`, bound by
`artifact_sha256`: the exported FX graph's nodes/ops/args, and -- for
small integer/boolean tensors only -- their literal contents
(`structural_values`). This is a structural restriction, not merely a
policy one: `structural_values` is populated only for
`torch.bool`/`int8`/`int16`/`int32`/`int64` tensors under 4096 elements
(`extractors/torch_export_worker.py`); a trained floating-point
parameter's actual values are never captured by this extractor at all
(research-readiness audit issue 13 -- re-confirmed this pass by direct
code inspection; no float `structural_values` path exists anywhere
reachable from `dftcert.verification`). Shape/dtype/hash/`state_kind` are
recorded for every tensor regardless, exposing the architecture without
exposing what was learned.

## 4. Inferred facts

`DFTCapabilityPlugin.derive`'s classifications -- site count, self-adjoint
operator construction, XC form, message-passing depth -- computed by real
graph-shape/ATen-op-name pattern matching and independently re-derived and
compared on every use via `validate_translation`. Provenance-labeled
`artifact_grounded`.

Issue 5 (fail-closed trainable-parameter classification): the
`unconstrained_parameter` capacity claim now requires POSITIVE evidence of
trainability -- an explicit `state_kind` containing `"parameter"`
(matching torch.export's own `InputKind.PARAMETER`). A missing/unknown
classification, an explicit buffer, or an explicit constant all fail
closed to `unsupported`, never fall back to a permissive default.
Self-adjointness (`guaranteedSelfAdjoint`, which holds for `B + Bᵀ`
regardless of whether `B` is trainable) is architecturally unaffected --
the `symmetrized` recipe never calls the parameter-classification check at
all. Regression tests: `tests/test_structural_adjoint_recognition.py`,
`tests/test_structural_capability.py`, `tests/test_formal_binding_candidates.py`.

Issue 3 (`canRepresentNonLocal`): the prior grammar incorrectly granted
non-local representational capacity to any `.add _ (.adjoint _)`
construction regardless of whether either operand actually contained a
free `.parameter` -- so `zero + adjoint zero` (genuinely incapable of a
nonzero off-diagonal entry, for any site count) was wrongly accepted.
Fixed to require a genuine `.parameter` on both sides of the pattern.
Non-local capacity and guaranteed self-adjointness are independent
properties of the same construction (an unequal-parameter construction can
have capacity without being guaranteed self-adjoint) -- deliberately never
conflated; see section 16 for the exact Lean-level statement and the 16
`#guard` regression cases pinned directly in `StructuralV2.lean`.

**Further correction, post-hardening-pass review, now the live
theorem-centric premise**: `canRepresentNonLocal`/`non_local_capacity`
above (fixed as described) are still kept only as a DEPRECATED HISTORICAL
ALIAS. Even the fixed grammar still treats "some off-diagonal entry exists"
as sufficient evidence of physical non-locality, which is itself an
unverified physical assumption -- an arbitrary off-diagonal entry does not
establish that the coupling it represents is between sites the domain
actually considers long-range. The live theorem-centric requirement now
uses `canRepresentLongRangeCoupling siteCount longRangePairs op`, which
requires an EXPLICITLY SPECIFIED (never inferred, never artifact-derived)
list of long-range site pairs (`longRangePairs`, `specified_interface`
provenance -- see section 5) and grants capacity only when the
construction contains a confirmed free parameter with the freedom to
couple at least one of those specified pairs. Self-adjointness is never
weakened by this correction. A grouped `[N, m, N, m]` operator layout
(multiple orbitals per site, no established site-axis correspondence) is
conservatively treated as unsupported/unresolved for long-range capacity
specifically, never `false` (a confident negative would overclaim; `None`/
unresolved is the honest answer). Regression:
`tests/test_long_range_coupling.py` (18 cases across the five categories:
long-range pairs, operator capacity, the symmetrized case, grouped
layouts, message-passing independence). **The exact physical definition of
"long-range" for this domain remains provisional, pending domain-expert
confirmation** -- see `docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md`'s
"Provisional long-range-coupling correction" section and
`Testv2.Requirements`'s own module docstring.

## 5. Specified interface assumptions

The package's `interface_contract`: `output_contracts` (which exported
output node is "the XC energy" etc.), `adjacency_convention`, and
`long_range_pairs` (e.g. `[[0, 3]]` -- which site pairs the domain
considers long-range, see section 4's further correction). The tool cannot
discover these from the graph alone -- a declared interpretation,
hash-bound into `package_sha256`, syntax-validated at authoring time
(non-negative integer pairs) with bounds validated later against the
artifact's own derived `site_count`.

Issue 10 (adjacency selection provenance): which state entry was selected
as "the adjacency" -- `declared` (matched the analyst's own
`adjacency_state_name` exactly) vs `heuristic_name_match` (a fallback the
tool applied because they didn't) -- was already hash-bound into
`ir_sha256` but not previously retrievable from the theorem-centric
certificate report itself. Now surfaced as `report["adjacency_selection"]
= {"selected_state_name": ..., "selection_provenance": ...}`
(`dftcert/verification/session.py`, `dftcert/verification/certificate.py`).
Regression: `tests/test_theorem_certificate.py::UnconditionalCertificateTests::
test_report_marks_unconditional_certificate_with_no_assumptions`.

## 6. Specified assumptions

A `Prop`-sorted premise a selected theorem requires that no artifact fact
or formal theory establishes (e.g. `TargetRequiresNonLocality`). Survives
as a real, unproven binder on the generated certificate theorem (never an
`axiom`); the report names the exact proposition/fingerprint/rationale;
revoking it puts the target back to unresolved (no one-way ratchet).

Issue 2 (no certifiable session-local assumptions): `VerificationSession.
accept_assumption` is session-local/exploratory only -- it can make a
session's own `status` read `ready_for_certificate`, but
`certify_session` now independently refuses (via
`_require_assumptions_are_package_normalized`) unless the exact same
assumption (matched by `(proposition_fingerprint, rationale)`) is also
present in the resolved package's own `external_assumptions`. Certifying
never silently copies a session-local decision into the package -- it only
ever refuses. The canonical, certifiable route is
`dftcert.verification.package.add_external_assumption` followed by
re-deriving the session.

**One real bug found and fixed this pass**: the matching check originally
keyed the package's `external_assumptions` by `premise_id`, but a
premise's companion Prop-sorted data binder
(`_apply_companion_conversions` in `dftcert/verification/session.py`)
carries a *copy* of the premise's `external_assumption` with `premise_id`
rewritten to the companion's own node id (for self-describing certificate
reports) -- so the companion's node id was never itself a key in the
package's `external_assumptions`, and a legitimately package-normalized
conditional certificate was incorrectly refused. Fixed by matching on the
`(proposition_fingerprint, rationale)` pair instead of `premise_id`.
Regression: `tests/test_public_api.py::SessionLocalAssumptionCannotCertifyTests`,
`::MultiTargetCertificationTests::test_two_entrypoint_package_produces_an_aggregate_bundle`.

## 7. Lean-resolved binders

An implicit/strict-implicit binder Lean's own typeclass synthesis or
transitive unification resolved, never artifact evidence, never a user
interpretation -- but not something that should block certification once
Lean itself has legitimately supplied it. Recorded as `lean_resolved`,
distinct from every other provenance class.

## 8. Formally checked claims

- That the selected entrypoint theorem, applied to the concrete
  artifact-derived/assumed values, actually kernel-type-checks.
- For premises the adapter claims are structurally satisfied: real
  `rfl`-discharged proofs the kernel reduces and confirms.
- The **generated certificate declaration's own** axiom closure
  (`Lean.collectAxioms`), never the entrypoint's alone.
- Lean project/theorem-source integrity as a whole (`project_fingerprint`
  hashes every `.lean` file under the project root).
- `Testv2/StructuralV2.lean`'s `canRepresentNonLocal`/`guaranteedSelfAdjoint`
  truth tables: 16 `#guard` assertions, checked on every `lake build` of
  that module -- see section 16.

## 9. Unverified claims

- That the extractor faithfully deserializes `.pt2` bytes (trusted
  extraction-boundary code, not independently re-verified by Lean).
- That the adapter's Python-side graph-shape classification is correct in
  general (verified by code inspection + tests for the recipes currently
  recognized, not proven for all possible future recipes).
- That an accepted external assumption is actually true of the real world.
- Anything about trained floating-point parameter values, training
  convergence, or numerical/experimental correctness -- see section 3.
- That the interface contract's role mapping/adjacency convention reflects
  the artifact's actual physical meaning (a specified interpretation, by
  design, never Lean-checked).
- Whether `Testv2/StructuralCapabilityMatrix.lean` is machine-checked --
  it is not, currently; see section 16 for the exact blocker.
- That the Bubblewrap sandbox path is itself airtight against a
  maliciously crafted `.pt2` (the sandbox test exists but could not be run
  in this environment -- no torch-capable POSIX interpreter available; it
  skips explicitly rather than being faked).
- That the theorem-centric approach scales to entrypoints/theorems
  significantly more complex than the DFT examples exercised here.
- Any claim about a second scientific domain -- explicitly out of scope
  for this pass; only checked that the generic harness contains no
  hardcoded DFT assumptions (research-readiness audit issue 7).

## 10. Artifact / package / adapter / formal-theory bindings

`artifact_sha256`, `inventory_sha256`, `translation_sha256`, `ir_sha256`,
`package_sha256` (over the entire authored package: binding choices,
external assumptions with their proposition fingerprints and rationales,
selected entrypoints, `entry_modules`, interface contract, axiom policy --
all in one hash), adapter `implementation_sha256` (of the adapter's own
source file), `project_fingerprint` (every `.lean` file under the Lean
project root), `certificate_source_sha256`, `report_sha256`,
`manifest_sha256`.

Issue 1 (package must fully own the Lean environment): the prior
`--lean-import`/`lean_import` runtime override, capable of diverging from
the package's own hash-bound formal environment, has been removed
entirely from `certify_session`, `generate_certificate_source`, and the
CLI. Every module imported while resolving the selected theorem,
generating the certificate, compiling it, and inspecting its axiom closure
is exactly `package["lean_theory"]["entry_modules"]` (a list, enabling
genuine multi-module packages -- previously impossible with a single
string). Regression: `tests/test_public_api.py::PackageOwnedLeanEnvironmentTests`
(includes a real two-module package, `Testv2.AltModule` +
`Testv2.Requirements`, certifying both targets in one bundle, and a test
confirming `entry_modules` changes `package_sha256`).

Issue 8 (portable, path-safe certificate bundles): `manifest.json`'s
per-target `source`/`report` paths are now recorded relative to the
bundle root (POSIX-separated), never absolute -- a bundle produced under
one machine/path can be copied or moved elsewhere and still verify.
`verify_certificate_bundle` resolves them via `_resolve_bundle_relative_path`,
which fails closed (`ManifestError`) on an absolute path or one that
resolves (after following symlinks) outside the bundle root -- rejecting
`..` traversal and symlink escapes alike. Regression:
`tests/test_public_api.py::CertificateBundleSelfConsistencyTests::
test_manifest_records_bundle_relative_paths`,
`::test_moved_bundle_directory_still_verifies`,
`::test_path_traversal_in_manifest_is_rejected`,
`::test_absolute_path_in_manifest_is_rejected`.

## 11. Normal vs. trusted-local extraction trust

Two genuinely different trust levels, previously blurred by an inaccurate
tamper-matrix claim (research-readiness audit issue 6):

- **Real extraction** (artifact bytes -> Bubblewrap sandbox -> inventory,
  never trusted-local): if the resulting inventory file is subsequently
  edited by hand, `validate_translation` independently re-derives every
  semantic claim from the raw graph nodes/args still present in the
  inventory and compares -- an edit that changes a semantic claim without
  also editing the underlying raw graph shape consistently is caught.
- **`trusted_local=True` / `--extraction-result`** (bypasses the sandbox
  entirely; no real `.pt2` bytes are ever read for that session): `
  validate_translation` only proves the derived IR is *consistent with the
  supplied inventory* -- it has no artifact bytes to re-derive that
  inventory from in the first place. A fully hand-fabricated, internally
  self-consistent inventory describing a fictional architecture passes
  exactly as cleanly as a genuine one. **This is corrected from a prior
  overclaim** that an edited trusted-local inventory is "necessarily
  detected" -- it is not, by design; `trusted_local=True` is an explicit,
  named opt-in to this exact trust reduction (documented for testing/CI
  without a working sandbox).

This is no longer merely asserted -- it is pinned by a regression test:
`tests/test_public_api.py::TrustedLocalDoesNotAuthenticateTheInventoryTests::
test_a_fully_fabricated_trusted_local_inventory_still_certifies` certifies
a session whose `artifact_sha256` is the literal string `"deadbeef"`,
proving the boundary stays honest rather than silently narrowing or
widening over time. See `docs/verification/TRUST_CHAIN_AUDIT.md` section 2 for the
corrected tamper-matrix row.

## 12. Conditional certificate semantics

A certificate whose `conditional` field is `true` depends on at least one
`specified_assumption` node (section 6) -- it is never claimed proven,
only that the stated conclusion follows *given* the assumption, which
survives as a real free binder on the generated theorem. `certify_session`
aggregates per-target results into one manifest; certification succeeds
for the whole package only when every selected target is closed (formally
or conditionally) -- any unresolved/failed target blocks the aggregate
bundle. Passing a strict subset of the package's selected entrypoints
produces an explicitly `selected_subset`-scoped bundle
(`allow_subset_certificate=True` required), never silently mistaken for a
complete package certificate.

## 13. Axiom policy

`DEFAULT_ALLOWED_AXIOMS = {propext, Classical.choice, Quot.sound}` plus
whatever a package's own `axiom_policy.additional_allowed` names --
hash-bound into `package_sha256`, never a runtime flag. Gated on the
**generated certificate declaration's own** axiom closure
(`certificate_axiom_closure`), never the entrypoint's alone -- a resolved
data binder's own Lean expression could depend on an axiom the entrypoint
theorem itself never mentions. `sorryAx` in the closure unconditionally
blocks certification, policy or no policy.

## 14. Bundle self-consistency vs. full re-verification

Two explicitly distinct, differently-named modes of
`verify_certificate_bundle` (research-readiness audit issue 9):

- **Lightweight (default, `full=False`)**: re-hashes bytes already on
  disk -- the manifest's own self-hash, each report's self-hash, each
  certificate source file's byte-hash against its recorded
  `certificate_source_sha256`, the certified target set against the
  package's full entrypoint set -- plus, when given live inputs, the
  live package hash, live adapter identity, live Lean-project freshness,
  and a fresh artifact hash. Never invokes Lean.
- **Full (`full=True`)**: strictly stronger, requires both `package` and
  `project` (there is nothing to recompile against without a live Lean
  project). Actually invokes the live Lean toolchain again: recompiles
  each certificate `.lean` source file from scratch, recomputes the
  freshly-compiled generated certificate's own axiom closure, and
  reapplies the live package's axiom policy to that fresh closure --
  catching a drifted/reinstalled toolchain or mathlib revision that now
  silently accepts (or rejects) something the original run did not.
  Explicitly documented as **not** re-deriving a fresh session from the
  artifact/inventory end to end (that would re-run the entire resolution
  pipeline, not just re-check the existing bundle) -- a known, stated
  remaining gap (`checks["full_reverification_scope_note"]`), never
  silently implied by `full=True`.

Neither mode is, or claims to be, cryptographic tamper-evidence (no
signature, no tamper-evident log) -- both only prove internal/live
consistency. Wired into the CLI as `vista verify verify-bundle --full`.
Regression: `tests/test_public_api.py::CertificateBundleSelfConsistencyTests::
test_full_reverification_requires_package_and_project`,
`::test_full_reverification_recompiles_and_passes_for_a_clean_bundle`.

## 15. Known limitations

- **The physical definition of "long-range" is provisional.** VISTA checks
  capacity for coupling on an explicitly SPECIFIED pair set
  (`long_range_pairs`); it has no notion of Euclidean distance, lattice
  distance, graph-hop distance, or any other physical metric, and does not
  claim the specified pairs are the physically correct notion of long-range
  for this domain. This is a deliberate, minimal design choice (never infer
  physical range from `i ≠ j`, a flattened tensor index, or message-passing
  hop count) so the pair specification can be replaced later without
  rewriting the theorem-centric harness -- pending domain-expert
  confirmation of the actual physical definition.
- **Grouped operator layouts have no long-range-capacity support yet.** A
  `[N, m, N, m]` layout (multiple orbitals per site) is conservatively
  unsupported/unresolved (`None`) for `long_range_capacity`, never a
  confident `true`/`false` -- there is no established correspondence
  between a flattened tensor axis and the physical site index for this
  case. Only the plain `[N, N]` one-degree-of-freedom-per-site case is
  currently supported.
- `_lean_operator`'s per-recipe Lean-string mapping is a hand-authored
  constant; its soundness depends entirely on the Python-side graph-shape
  classification being correct (verified for the recipes currently
  recognized), with no independent Lean-side check that a hypothetical
  new recipe's classification and its compiled-to Lean term actually
  agree.
- Theorem-driven binder SELECTION is implemented; theorem-driven MINIMAL
  IR CONSTRUCTION is not, and is not planned (research-readiness audit
  issue 11) -- the full structural IR is always derived unconditionally
  from the raw inventory, with no awareness of which theorem was
  selected; selection only chooses among facts that already exist. See
  `docs/verification/TRUST_CHAIN_AUDIT.md` section 5 and
  `dftcert/verification/resolver.py`'s own module docstring.
- `Testv2/StructuralCapabilityMatrix.lean` is not currently machine-checked
  -- see section 16 for the exact, corrected blocker (a parser error, not
  a genuine v4.31.0/mathlib incompatibility as previously and incorrectly
  claimed).
- No CLI subcommand exists for authoring a binding choice or external
  assumption outside the interactive `vista verify interact` TUI; a
  non-interactive/scripted caller must use the public Python API directly
  (`dftcert.verification.package.add_external_assumption`), which works
  and is documented, but is less convenient to script.
- The separate, older "vista structural" legacy harness
  (`dftcert.structural.core`, `dftcert.legacy.*`) has minor DFT-specific
  naming baked into otherwise-generic functions and its own float-aware
  `locality` plugin (`DFTPlugin`) -- confirmed this pass, by grep, to be
  unreachable from `dftcert.verification` (the theorem-centric path never
  imports it) -- pre-existing, out of scope, does not affect the
  theorem-centric layer's pre-training-only claim.
- The hosted GitHub Actions CI run has been exercised locally (the exact
  `make verification-test` steps, including a from-scratch `lake exe
  cache get`/`lake build` with no manifest present, run and observed to
  succeed this pass -- see section 17) but **the actual hosted GitHub
  Actions run itself has not been observed to complete** in this
  environment. Stated as a known limitation, never claimed as a passing
  hosted CI run.

## 16. Exact toolchain / dependency pins

- **Lean toolchain**: `leanprover/lean4:v4.31.0`
  (`examples/dft/lean/lean-toolchain`) -- unchanged throughout this
  entire pass. Never upgraded, never switched to a `-rc`/`nightly`/
  `latest` build.
- **Mathlib**: `lakefile.toml` declares `rev = "v4.31.0"` exactly (not a
  floating branch). Resolves to commit `fabf563a7c95a166b8d7b6efca11c8b4dc9d911f`.
- **Cli** (mathlib's own transitive dependency): resolves to
  `92564e5770e4d09f2d86dfbf8ada1e9c715b384c` under the same `v4.31.0` pin.
- `examples/dft/lean/lake-manifest.json` and `.lake/` are both gitignored
  -- every environment (a fresh dev checkout, or CI) resolves dependencies
  fresh from `lakefile.toml`'s exact pin every time; there is no
  persisted, potentially-stale manifest that could silently diverge from
  the declared pin. Confirmed this pass by deleting the local manifest
  entirely and re-running `lake exe cache get && lake build` from
  scratch: it recreated a manifest pinning exactly the same
  `v4.31.0`-resolved revisions above, and the build succeeded (8567
  jobs). **Corrected finding**: the STALE claim in a prior version of this
  document, that `Testv2/StructuralCapabilityMatrix.lean` "requires
  Mathlib v4.33.0-rc1" and is therefore incompatible with the pinned
  Lean, was traced to a local development machine's own out-of-date
  manifest file (from before `lakefile.toml` was edited to pin
  `v4.31.0`, never regenerated) -- not a real incompatibility. Running
  `lake update` (a normal, no-upgrade dependency *resolution* step, never
  a Lean/toolchain change) against the unchanged `lean-toolchain` and
  `lakefile.toml` fixed the local manifest.
- `Testv2/StructuralCapabilityMatrix.lean` itself still does not build --
  the ACTUAL blocker (after fixing the stale-manifest issue above) is a
  parser error, `unexpected token 'namespace'; expected 'lemma'` at its
  own `namespace Testv2.StructuralCapabilityMatrix` line, reproduced only
  when `import Mathlib.Data.Real.Basic` is added to resolve an unrelated
  `ℝ` instance-resolution gap. Not yet root-caused; kept out of the
  formally-checked claim and out of the default `Testv2` import graph
  (`Testv2.lean`) exactly as before. `STRUCTURAL_CAPABILITY_CHECKS.md`'s
  own stale "v4.33.0-rc1"/"not machine-verified anywhere" wording has the
  same root-cause correction pending in a future pass; not yet edited
  this pass (documented here as the accurate current state instead).

## 17. Commands actually run

```
# Toolchain/dependency inspection (before touching anything)
cat examples/dft/lean/lean-toolchain
cat examples/dft/lean/lakefile.toml

# Issue 4/14: stale-manifest fix and CI-equivalent fresh-resolve confirmation
lake update                       # regenerated the local dev manifest against the unchanged v4.31.0 pin
lake exe cache get                # 8542 files, all already cached (Azure)
lake build                        # Build completed successfully (8567 jobs)
# then, to confirm the CI-equivalent path specifically:
rm lake-manifest.json             # simulate a fresh checkout (manifest is gitignored, never committed)
lake exe cache get && lake build  # succeeded from scratch; manifest recreated with the same v4.31.0-resolved revs

# Issue 3: isolated module build for the canRepresentNonLocal fix + 16 #guard cases
lake build Testv2.StructuralV2    # Built successfully

# Full project rebuild (confirms Issues 1, 2, 3, 5, 7, 8, 9, 10 didn't break the Lean side)
lake build Testv2                 # Build completed successfully (8567 jobs)

# Python suites (Windows python.exe, per this project's primary dev toolchain)
python -m pytest -q tests/test_public_api.py -v
  # 27 passed (25 pre-existing/Issue-1/2/7/8/9-added tests, plus this
  # pass's 2 new adversarial-matrix classes: AdapterRegistryDependency
  # DirectionTests, TrustedLocalDoesNotAuthenticateTheInventoryTests)
python -m pytest -q tests/test_theorem_certificate.py tests/test_verification_session.py tests/test_verify_cli.py -v
  # 28 passed (confirms Issue 5's fail-closed change and Issue 10's
  # adjacency_selection field cause no regression in the broader
  # theorem-centric suite)
python -m pytest -q tests/test_structural_adjoint_recognition.py tests/test_structural_capability.py tests/test_structural_operator_layout.py tests/test_formal_binding_candidates.py -v
  # 32 passed (Issue 5's directly-affected pure-Python structural tests)

# CI configuration (present, syntax-checked locally; hosted run not observed)
cat .github/workflows/ci.yml
make -n verification-test         # Makefile syntax dry-run only
```

Do not quote any test count from a prior pass as a result of this one --
every count above was freshly observed during this pass.
