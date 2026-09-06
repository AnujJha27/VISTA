# VISTA Research-Readiness Audit

A red-team pass against the theorem-centric VISTA pipeline, following the
prior hardening passes (theorem-centric-gaps issues 1-16, A-I). This
document is a developer artifact, not marketing copy. Where something is
unsupported, this says so explicitly.

# Exact implemented claim

> VISTA checks whether artifact-grounded structural facts are sufficient to
> establish selected Lean requirements under explicit interface and
> external assumptions, and emits a certificate bound to the analyzed
> artifact, verification package, formal theory, adapter semantics, and
> proof result.

Nothing more. In particular: **not** "Lean verifies the model", **not**
that an accepted external assumption has been proven true, and **not** a
claim of generality across artifacts or architectures beyond the one
analyzed.

# Trusted computing base

- The Lean 4 kernel + the pinned `mathlib` revision (`v4.31.0`,
  `examples/dft/lean/lean-toolchain`/`lakefile.toml`) — the only component
  that performs formal proof checking.
- `extractors.torch_export_worker.extract` — the sole PT2 deserialization
  boundary (run inside a Bubblewrap sandbox in the fully-safe path, or
  trusted-local for testing/CI without a working sandbox).
- `dftcert.structural.dft_capability_plugin.DFT_CAPABILITY_PLUGIN` — the one
  domain adapter, whose own source file's hash is bound into every session/
  certificate it produces.
- `dftcert.verification.*` (session, resolver, certificate, package, api,
  cli) — the generic, domain-agnostic theorem-centric harness (confirmed
  clean of hardcoded DFT assumptions this pass — see below).
- The operating system / filesystem / Python interpreter each component
  runs under — not independently attested (no reproducible-build or
  remote-attestation layer exists).

# Artifact-to-certificate chain

```
model.pt2 bytes
  -> extractors.torch_export_worker.extract (safe extraction; artifact_sha256)
  -> structural_ir_from_inventory (semantic lowering under interface_contract)
  -> validate_translation (independent re-derivation + comparison; runs every time)
  -> DFTCapabilityPlugin.formal_binding_candidates (Lean-instantiable facts, evidence_refs)
  -> resolve_entrypoint (Lean Meta telescope inspection of the SELECTED theorem)
  -> per-binder resolution: artifact_grounded | specified_interface | lean_resolved
     | formally_discharged | specified_assumption | ambiguous_binding | unresolved
  -> generate_certificate_source (Lean-Meta-driven; builds the wrapper theorem)
  -> verify_structural_certificate (real Lean compile + kernel check)
  -> Lean.collectAxioms on the GENERATED certificate declaration itself (not the entrypoint)
  -> assemble_certificate_report (gates on that closure; records provenance per node)
  -> certify_session (aggregate manifest; certificate_scope explicit; hash-bound)
```

Traced concretely for one real certificate this pass (see
`docs/TRUST_CHAIN_AUDIT.md` section 1): every edge above was followed for
`tests/fixtures/certified_ring.pt2` and confirmed non-vacuous —
`used_facts` node names verified present in the raw extraction, and the
three discharged Boolean premises (`guaranteedSelfAdjoint`,
`canRepresentNonLocal`, `xcSupportsDiscontinuity`) confirmed to be real,
falsifiable pattern matches, not tautologies.

# Extracted facts

Directly from `extractors.torch_export_worker.extract`, bound by
`artifact_sha256`: the exported FX graph's nodes/ops/args, and — for small
integer/boolean tensors only (explicitly never a float parameter's trained
values) — their literal contents (`structural_values`). Shape/dtype/hash/
`state_kind` are recorded for every tensor regardless, exposing the
architecture without exposing what was learned.

# Inferred facts

`DFTCapabilityPlugin.derive`'s classifications — site count, self-adjoint
operator construction, XC form, message-passing depth — computed by real
graph-shape/ATen-op-name pattern matching (verified this pass: real ATen op
names, real adjoint-permutation checks, never a label trusted at face
value) and independently re-derived + compared on every use via
`validate_translation`. Provenance-labeled `artifact_grounded`.

# Specified interface assumptions

The package's `interface_contract`: `output_contracts` (which exported
output node is "the XC energy" etc.) and `adjacency_convention`. The tool
cannot discover these from the graph alone — they are a declared
interpretation, hash-bound into `package_sha256`, and a wrong-but-valid
mapping is a documented interpretation choice (never silently upgraded to
`artifact_grounded`). One transparency gap found and documented (not fixed
this pass, no soundness impact): whether the adjacency state buffer was
matched by the analyst's exact declared name or a weaker heuristic
name-match fallback is computed and hash-bound into the IR but not
surfaced in the theorem-centric certificate report itself.

# Explicit theorem assumptions

A `Prop`-sorted premise a selected theorem requires that no artifact fact or
formal theory establishes (e.g. `TargetRequiresNonLocality`). Verified this
pass, end to end: it survives as a real, unproven binder on the generated
certificate theorem (never an `axiom`); the report names the exact
proposition/fingerprint/rationale; changing the proposition invalidates the
old decision; **revoking it puts the target back to unresolved** (new
regression test added — no one-way ratchet); there is no "assume all" path;
arbitrary unresolved data cannot be smuggled in as a `Prop` assumption
(`is_prop_sort` gating). A real regression was found and fixed this pass:
the companion-binder auto-conversion (a `Prop`-sorted data binder a premise
depends on) only fired through the old session-local `accept_assumption`,
not through the new package-driven rebuild path — extracted into a shared
helper both paths now call.

# What Lean checks

- That the selected entrypoint theorem, applied to the concrete
  artifact-derived/assumed values, actually kernel-type-checks.
- For premises the adapter claims are structurally satisfied: real
  `rfl`/tactic-discharged proofs the kernel reduces and confirms — not
  merely believed by the Python side.
- The **generated certificate declaration's own** axiom closure
  (`Lean.collectAxioms`, an inherently transitive operation) — verified
  this pass via an adversarial fixture that a custom axiom buried in a data
  binder's *value* (never referenced by the entrypoint theorem itself) is
  still caught, proving the closure is not inferred from the entrypoint
  alone.
- Lean project/theorem-source integrity as a whole (`project_fingerprint`
  hashes every `.lean` file under the project root) — any edit to the
  selected entrypoint's own file *or* a helper file it depends on (e.g.
  `StructuralV2.lean`) is caught before certification, though not
  file-granular.

# What Lean does not check

- That the extractor faithfully deserializes `.pt2` bytes (trusted
  extraction-boundary code, not independently re-verified by Lean).
- That the adapter's Python-side graph-shape classification is correct in
  general (verified by code inspection + tests this pass for the recipes
  currently recognized, not proven for all possible future recipes).
- That an accepted external assumption is actually true of the real world.
- Anything about trained floating-point parameter values, training
  convergence, or numerical/experimental correctness — structurally,
  VISTA's extractor never captures a trained value as evidence in the
  first place.
- That the interface contract's role mapping/adjacency convention reflects
  the artifact's actual physical meaning (a specified interpretation, by
  design, never Lean-checked).

# Hash/fingerprint bindings

`artifact_sha256`, `inventory_sha256`, `translation_sha256`, `ir_sha256`,
`package_sha256` (over the *entire* authored package: binding choices,
external assumptions with their proposition fingerprints and rationales,
selected entrypoints, interface contract, axiom policy — all in one hash),
adapter `implementation_sha256` (of the adapter's own source file),
`project_fingerprint` (every `.lean` file under the Lean project root),
`certificate_source_sha256`, `report_sha256`, `manifest_sha256`. All
verified independently re-derivable (not merely stored) via the new
`verify_certificate_bundle` / `vista verify verify-bundle`, added this pass
— see `docs/TRUST_CHAIN_AUDIT.md` section 3.

**One real bug found and fixed this pass**: `certificate_source_sha256` was
computed from an in-memory string but the `.lean` file was written with
Python's default text-mode newline translation, so on Windows the file's
actual on-disk bytes (`\r\n`) never matched the hash that claimed to
describe them — a self-consistency failure present even with *zero*
tampering. Fixed by writing the file with `newline=""`.

# Tamper matrix

See `docs/TRUST_CHAIN_AUDIT.md` section 2 for the full table (17 mutation
targets). Summary: every mutation that changes a hash-bound input is caught
before certification proceeds (fail-closed, never a silent stale reuse);
mutations to already-certified bundle *files* (source, report, manifest)
are caught by the new `verify_certificate_bundle`, not by the certify path
itself (which has nothing left to check once the bundle exists). No claim
of cryptographic tamper-evidence — this is runtime validation, stated
explicitly in the trust-chain document.

# Known limitations

- Adjacency state-buffer binding provenance (declared name vs. heuristic
  name-match) is hash-bound but not surfaced in the theorem-centric
  report.
- The separate, older "vista structural" legacy harness
  (`dftcert.structural.core`) has minor DFT-specific naming baked into
  otherwise-generic functions (a hardcoded Lean namespace prefix, a
  hardcoded `"project": "testv2"` field) — pre-existing, out of scope for
  this pass, does not affect the theorem-centric layer.
- No CLI subcommand exists for authoring a binding choice or external
  assumption outside the interactive `vista verify interact` TUI; a
  non-interactive/scripted caller must use the public Python API directly
  (`dftcert.verification.package.add_external_assumption`), which works and
  is documented, but is less convenient to script.
- The new CI coverage (`make verification-test`, wired into
  `.github/workflows/ci.yml`) has been syntax-validated locally (`make -n`)
  and exercises the exact test suite verified extensively in this session,
  but **the actual GitHub Actions run has not been observed to complete** —
  whether `lake exe cache get` succeeds from GitHub's runners, and the real
  wall-clock time, are unverified. This is stated as a known limitation
  rather than a claimed-working CI pipeline.
- `_lean_operator`'s per-recipe Lean-string mapping is a hand-authored
  constant; its soundness depends entirely on the Python-side graph-shape
  classification being correct (verified for the recipes currently
  recognized), with no independent Lean-side check that a hypothetical new
  recipe's classification and its compiled-to Lean term actually agree.

# Remaining unverified claims

- That the theorem-centric approach scales to entrypoints/theorems
  significantly more complex than the DFT examples exercised here.
- That the Bubblewrap sandbox path is itself airtight against a
  maliciously crafted `.pt2` (the sandbox test exists but could not be run
  in this environment — no torch-capable POSIX interpreter available; it
  skips explicitly rather than being faked).
- Any claim about a second scientific domain — explicitly out of scope for
  this pass (audit_instructions.md section 11); only checked that generic
  code contains no hardcoded DFT assumptions (confirmed for
  `dftcert.verification.*`).

# Commands used for final verification

```
# Full theorem-centric + structural suite (Windows python.exe)
python -m pytest -q tests/ --ignore=tests/test_dftcert.py --ignore=tests/test_orchestrator.py
# => 142 passed, 1 skipped (Bubblewrap sandbox: no torch-capable sandboxed interpreter)

# Legacy vista structural suite (WSL python3)
python3 -m pytest -q tests/test_dftcert.py tests/test_orchestrator.py
# => 74 passed, 2 subtests passed

# Real certificate generation + backward trace (ad hoc script against the
# real committed tests/fixtures/certified_ring.pt2, deleted after use)
# => certified, certificate_axiom_closure=["propext"]

# Full documented user workflow, via the real `vista` CLI entrypoint
python vista verify start --extraction-result ... --package ... --session ... --project examples/dft/lean --trusted-local --timeout-s 180
python vista verify resume --session ...
python vista verify start ...   # re-applies an accepted assumption
python vista verify certify --session ... --package ... --project examples/dft/lean --lean-import Testv2.Requirements --output-dir ... --trusted-local --timeout-s 180
python vista verify verify-bundle --bundle-dir ... --package ... --project examples/dft/lean
# => certified, conditional=true, consistent=true

make -n verification-test   # Makefile syntax dry-run only, not a real CI run
```
