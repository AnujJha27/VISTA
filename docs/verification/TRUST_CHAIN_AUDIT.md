# VISTA Trust-Chain Audit

Red-team pass against the claim:

> VISTA checks whether artifact-grounded structural facts are sufficient to
> establish selected Lean requirements under explicit interface and external
> assumptions, and emits a certificate bound to the analyzed artifact,
> verification package, formal theory, adapter semantics, and proof result.

This document is a developer artifact, not marketing copy. Every row below is
backed by either an existing automated test, a newly-added regression test,
or an explicit statement that the property is a documented trust assumption
rather than a checked one.

## 1. One certificate traced backwards

Generated from the real, committed `tests/fixtures/certified_ring.pt2` (a
6-site ring, symmetrized self-energy operator, hinge XC), using only the
public `dftcert.verification` API (`start_session` → `certify_session`).

| Step | Implementing function | Hash/fingerprint binding it | Relationship |
|---|---|---|---|
| Certificate conclusion | generated `theorem certificate` in the `.lean` bundle | `certificate_source_sha256` | formally checked |
| Discharge of 3 structural premises | `rfl` against `guaranteedSelfAdjoint`/`canRepresentLongRangeCoupling`/`xcSupportsDiscontinuity` (`StructuralV2.lean`; `canRepresentLongRangeCoupling` supersedes `canRepresentNonLocal`, kept only as a deprecated historical alias -- research-soundness correction) | kernel-checked by `verify_structural_certificate` | formally checked (real Bool computation, not vacuous — see below) |
| Selected entrypoint | `Testv2.Requirements.ValidPretrainingArchitecture` | `project_fingerprint` (whole-project hash) | formally checked |
| `FormalBindingCandidate`s (site_count, edges, operator_form, locality_range, xc_form) | `DFTCapabilityPlugin.formal_binding_candidates` | `evidence_refs` → IR provenance nodes (`locality_range` carries none -- it is `specified_interface`, not artifact-grounded; the long-range pair set it and `edges` together determine is derived by Lean itself, never a candidate of its own) | inferred/specified, independently revalidated |
| Structural IR facts (`topology`, `operator`, `xc`) | `DFTCapabilityPlugin.derive` | `translation_sha256`, `inventory_sha256` | inferred from raw graph shape |
| Semantic derivation (`_operator_construction`, `_xc_form`) | real FX-graph structural pattern match (checks the `add` node's two operands, that one is literally the adjoint of the other via the same base node name) | — | inferred, not a label trusted at face value |
| Extracted graph/state evidence | `extractors.torch_export_worker.extract` | `inventory_sha256` | extracted |
| `model.pt2` bytes | `sha256_file` | `artifact_sha256` | extracted |

Concretely verified for this run: all 7 `used_facts` node names
(`add`, `b_adjacency`, `density`, `numpy_t`, `p_base_operator`, `relu`,
`sum_1`) exist verbatim in the raw extraction inventory — not fabricated.
`AcceptableArchitecture`'s three sub-properties are real, non-trivial
`Bool`-valued pattern matches (e.g. `guaranteedSelfAdjoint` only returns
`true` for `.zero`, `.identity`, or an `add`/`adjoint` pair with *equal*
operands) — the `rfl` proofs in the generated certificate are genuine
kernel-checked computations on the concrete artifact-derived values, not
rubber-stamped.

**One documented trust assumption found and left as-is (by design, not a
bug):** `_lean_operator`'s per-recipe string (e.g. `"symmetrized"` →
`.add (.parameter "base") (.adjoint (.parameter "base"))`) is a hand-authored
constant. Its correctness depends entirely on `_operator_construction`'s
Python-side classification being sound — which it is, by genuine graph-shape
inspection (checked above) — but there is no way for Lean itself to detect a
mismatch between a *hypothetical* new recipe string and its actual recognition
logic. This is inherent to any "compile a classification to a fixed Lean
term" design; the mitigation is that `formal_binding_candidates` is small,
adapter-internal, and covered by `tests/test_structural_capability.py`.

## 2. Tamper matrix

"Detected" means: a *before* run raises `ManifestError` and refuses to
proceed; "N/A" means the tamper mutates something the design does not (and
should not) treat as a hash-bound trust boundary in the first place.

| Mutation | Detected before certification? | Detected during certification? | Changes certificate identity? | Old certificate still incorrectly applicable? | Evidence |
|---|---|---|---|---|---|
| `model.pt2` bytes | Yes (`start_session`/`resume_session` artifact hash check) | — | Yes (`artifact_sha256`) | No | `test_changed_artifact_hash_goes_stale`, `test_tampered_artifact_bytes_change_the_hash`, `test_resume_rejects_changed_artifact` |
| Extraction inventory (edited post-extraction, same artifact hash) -- **real-extraction path only** (`extract` ran against actual `.pt2` bytes inside the Bubblewrap sandbox, then the resulting inventory file was subsequently edited by hand before being handed to `structural_ir_from_inventory`) | Yes (`validate_translation` independently re-derives every semantic claim from the *raw graph nodes/args* still present in the inventory and compares -- an edit that changes a semantic claim without also editing the underlying raw graph shape consistently is caught) | — | Yes (`inventory_sha256`) | No | `test_tampered_semantic_fact_after_extraction_cannot_certify`, `test_edited_semantic_fact_is_rejected_even_with_the_correct_artifact_hash` |
| Extraction inventory supplied directly via `--extraction-result`/`extraction_result=` with `--trusted-local`/`trusted_local=True` (bypasses the Bubblewrap sandbox entirely -- no real `.pt2` bytes are ever read for this session) | **Not detected, by design -- corrected from a prior overclaim.** `validate_translation` only proves the derived IR is *consistent with the supplied inventory*; it has no artifact bytes to re-derive that inventory from in the first place, so a fully hand-fabricated inventory describing a fictional architecture (internally self-consistent raw-graph nodes/args, matching semantic claims) passes exactly as cleanly as a genuine one. `trusted_local=True` is an explicit, named opt-in to this exact trust reduction (documented for testing/CI without a working sandbox, per `dftcert/verification/__init__.py`'s trusted-computing-base note) -- it is never claimed, and must never be claimed, that an edited trusted-local inventory is "necessarily detected". The real-artifact path (artifact bytes -> Bubblewrap `extract` -> inventory, never trusted-local) is unaffected by this row and remains covered by the row above. | Yes (`inventory_sha256`, same as any other inventory) | No -- the certificate is bound to whatever `artifact_sha256`/`inventory_sha256` the trusted-local input hashed to, honestly recording that no independent artifact-bytes re-derivation ever occurred | code inspection: `dftcert/verification/api.py::_extraction_result` (`trusted_local` gate), `dftcert/verification/__init__.py` trusted-computing-base docstring |
| Interface contract | Yes (different `interface_contract` → different derived IR → different `ir_sha256`; never silently merged) | — | Yes | No | `test_interface_contract_mismatch_is_not_silently_combined` |
| Output role mapping (`output_contracts`) | N/A — this is a *specified interface* value, not derived; a wrong-but-valid mapping is a documented interpretation choice, reflected as `specified_interface` provenance, never silently upgraded to `artifact_grounded` | — | Yes (part of `interface_contract`, hashed into `package_sha256`) | No (a re-derivation under a different contract always produces a different `ir_sha256`) | design: `StructuralPlugin.role_roots`; `dftcert/verification/__init__.py`'s documented provenance classes |
| Locality range (`interface_contract.locality_range`) | N/A — same as the output role mapping: `specified_interface`, not derived; a domain expert changing `R` is a legitimate interpretation change, always reflected as a different `ir_sha256`/`package_sha256`, never silently upgraded to `artifact_grounded` and never claimed to be physically correct in the first place (research-soundness correction). The long-range pair set itself is never a tamperable input at all -- it is always inferred by VISTA from the artifact-grounded `edges` and this one integer, so there is no pair list to tamper with. | — | Yes (hashed into `package_sha256`) | No | code inspection: `dft_capability_plugin.py::_locality_range`; `docs/structural-v2/STRUCTURAL_CAPABILITY_CHECKS.md`'s "Provisional graph-hop locality correction" |
| Operator layout (`operator.layout`) | Partially: a non-canonical (reordered) `output_axes`/`input_axes` shape is rejected outright (`ManifestError`); a canonical-but-semantically-wrong layout fails closed (the real adjoint-permutation check in `_is_adjoint_of` just won't match, so the operator falls through to `unsupported` rather than false-positive `symmetrized`) | — | Yes | No | code inspection: `dft_capability_plugin.py` lines ~143-155, ~179 |
| Structural IR (edited post-derivation) | Yes (`validate_translation` re-derives from raw inventory and compares) | — | Yes | No | `test_edited_semantic_fact_is_rejected_even_with_the_correct_artifact_hash` |
| Binding choice | Yes (changes `package_sha256`; a session built from a different package goes `stale`, never silently reused) | — | Yes | No | `test_changed_package_hash_goes_stale_and_preserves_old_session`, `test_resume_rejects_changed_package` |
| Accepted external assumption | Yes (a wrong `proposition_fingerprint` is never applied; changes `package_sha256`) | — | Yes | No | `test_stale_package_declared_assumption_with_wrong_fingerprint_is_not_applied`, `test_add_external_assumption_persists_into_package_and_applies_on_restart` |
| Proposition fingerprint | Yes (exact-match required against the premise Lean *just now* derived) | — | Yes | No | same as above (issue 7) |
| Selected Lean entrypoint | Yes (changes `package_sha256`/`lean_theory.entrypoints`) | — | Yes | No | `test_changed_package_hash_goes_stale_and_preserves_old_session` (same mechanism) |
| Lean theorem source (entrypoint's own file) | Yes (`project_fingerprint` hashes every `.lean` file under the project root) | — | Yes | No | `test_stale_project_fingerprint_is_rejected` |
| Helper Lean theorem (e.g. `StructuralV2.lean`) | Yes (same whole-project fingerprint — not file-granular, but sufficient: *any* `.lean` edit under the project is caught) | — | Yes | No | same mechanism as above |
| `lean-toolchain` | Yes | — | Yes | No | `test_stale_toolchain_is_rejected` |
| Adapter semantic implementation (live code changes after package authored) | Yes (`semantic_identity` hashes the adapter's own source file; checked both at `start_session` and via `resume_session`/`verify_certificate_bundle`) | — | Yes | No | `test_modified_adapter_identity_in_package_is_rejected`, `test_resume_rejects_changed_adapter_identity` |
| Axiom policy | Yes (an extra allowed axiom must come from the package's own hash-bound `axiom_policy`, never a runtime flag) | Yes (gated at `assemble_certificate_report` on the *generated certificate's* axiom closure) | Yes | No | `test_custom_axiom_blocks_unless_named_in_package_axiom_policy` |
| Generated certificate source (edited on disk after `certify_session`) | — | N/A at generation time (nothing to detect yet) | — | **Found and fixed**: the file was written with OS text-mode newline translation (`\r\n` on Windows), so `certificate_source_sha256` never actually matched the file's own bytes even with *no* tampering at all. Fixed by writing with `newline=""`. A genuine post-hoc edit is now caught by `verify_certificate_bundle`'s `<entrypoint>:certificate_source_hash` check. | Would have incorrectly appeared applicable before the fix (hash mismatch was unconditional, not tamper-specific) | `test_tampered_certificate_source_bytes_are_detected`, `test_freshly_certified_bundle_is_self_consistent` |
| Certificate report (edited on disk) | — | N/A | — | Detected by `verify_certificate_bundle`'s `<entrypoint>:report_self_hash` check (re-hashes the parsed report minus its own `report_sha256` field) | `test_tampered_report_field_is_detected` |
| Aggregate certificate manifest (edited on disk) | — | N/A | — | Detected by `verify_certificate_bundle`'s `manifest_self_hash` check | `test_tampered_manifest_field_is_detected` |

**Important scope note:** every "detected before certification" row above is
runtime validation inside this codebase (Python re-derivation + Lean
recompilation), not cryptographic protection in the sense of a signature or a
tamper-evident log. Nothing here claims to detect an attacker with write
access to the bundle *files* and enough sophistication to also fabricate a
consistent set of hashes across every field simultaneously — the self-hashes
only prove *internal* consistency (the bundle agrees with itself), which is
exactly what `verify_certificate_bundle` checks and no more. Cross-checking
against a *live* package/project/artifact (also supported by
`verify_certificate_bundle`) is what catches drift against the outside
world; it still trusts whatever `project`/`package`/`artifact` paths the
caller points it at.

## 3. New tooling added by this pass

`dftcert.verification.api.verify_certificate_bundle` (also `vista verify
verify-bundle` on the CLI) independently recomputes, for an existing
certified bundle directory:

- the manifest's own self-hash;
- each per-target report's own self-hash, and the manifest's reference to it;
- each generated certificate `.lean` file's actual byte hash;
- the certified target set against the package's full entrypoint set;
- optionally (when given live `package`/`project`/`artifact` inputs): the
  live package hash, adapter identity, Lean-project freshness, and artifact
  hash, each against the bundle's recorded binding.

It never trusts a field merely because it is already present inside the
object being checked — see `tests/test_public_api.py::
CertificateBundleSelfConsistencyTests` for both the happy path and four
independent tamper cases (source bytes, report field, manifest field,
changed package).

## 4. Documented workflow, run for real (research-readiness audit section 8)

Ran the exact workflow `dftcert/verification/__init__.py`'s module docstring
describes — build a package, `python vista verify start` from the real
`.pt2` fixture, resume, accept an assumption in the conditional example,
re-run start to apply it, `python vista verify certify`, inspect the
bundle, `python vista verify verify-bundle` — using the actual installed
entrypoint script (`vista`, at the repo root) on this project's primary dev
toolchain (Windows `python.exe`), not by calling internal functions.

**Two real bugs found and fixed, both the same class of problem:** the
`vista`/`vista` console entrypoint (`dftcert.local_cli`) imported
POSIX-only modules at module level that only specific *legacy* commands
actually need — `curses` (only used by one assumption-confirmation TUI
fallback) and `fcntl` (via `dftcert.legacy.pipeline`, only used by the
legacy local-pipeline commands). Neither is needed by `verify` at all, but
because Python must execute every top-level import when a module loads,
`python vista verify start ...` crashed immediately with `ModuleNotFoundError`
on Windows before parsing a single argument — the documented workflow could
not be run at all on this project's own primary toolchain. Fixed by deferring
both imports to exactly the legacy code paths that use them (the same
pattern already used for `dftcert.sandbox` elsewhere in this codebase).
Regression guard: `tests/test_local_cli_import.py`.

**One completeness gap, documented rather than fixed this pass:** there is
no CLI subcommand for `add_binding_choice`/`add_external_assumption` outside
the interactive `vista verify interact` TUI (which needs a real terminal).
A non-interactive/scripted caller must drop into the public Python API
(`dftcert.verification.package.add_external_assumption`) directly, which
does work and is documented, but is not CLI-exposed. Left as-is per this
pass's own scope ("do not add broad new functionality unless required to
fix a demonstrated problem") since the workflow is not actually broken —
just less convenient to script than the interactive path.

## 6. Persisted-session trust gap -- found and fixed (final engineering pass)

**The gap.** Before this fix, `certify_session` (`dftcert/verification/
api.py`) built the final certificate from `nodes` (`lean_expr`, resolved
binder/premise status) read out of whatever was already on disk at
`session`, via a raw, non-revalidating `load_session` -- never re-deriving
them from a live artifact. `nodes` is not covered by any hash `certify_
session` checked (`artifact_sha256`, `formal_package_binding.package_sha256`):
an attacker (or an accidental hand-edit) could take a genuine session built
from a real artifact whose recognized operator construction is `unconstrained`
(a bare parameter -- `guaranteedSelfAdjoint = false`, premise stays
`unresolved`), edit its persisted `session.json` to claim the operator was
the `symmetrized` (self-adjoint) form and that the self-adjointness premise
was `formally_discharged`, and `certify_session` would generate and Lean-check
a certificate for that forged, well-typed term -- Lean correctly verifies the
*application*, but the relationship "this term came from this artifact" was
never established. The tamper matrix in section 2 above has no row for this
exact case (every existing row's "Detected before certification?" answer is
about tampering the *pre-persistence* derivation path, e.g. an inventory
edited between extraction and `structural_ir_from_inventory`, or the package/
project/toolchain -- never a `session.json` edited *after* `start_session`
wrote it and *before* `certify_session` read it back).

**The fix.** `certify_session` now requires `artifact` or `extraction_result`
(exactly one, same semantics as `start_session`) and always freshly re-derives
the certification-relevant session -- via the same trusted `start_session`
backend, now with a new `force_fresh=True` flag that skips its existing
"reuse the file at `output` unchanged" shortcut (that shortcut only compares
`artifact_sha256`/`package_sha256`/`adapter_binding`/`ir_sha256`, none of
which cover `nodes` either -- so without `force_fresh` it has the same latent
gap; see the note in `dftcert/verification/session.py::start_session`'s
docstring). The freshly-derived session unconditionally overwrites `session`
on disk. `session`'s role is therefore now purely a trusted-OUTPUT
convenience (inspection/comparison after the fact) -- nothing `certify_
session` reads back from that path ever influences what gets certified.
This is the design principle the spec states directly: persisted sessions
are workspace/cache/UI state, not trusted certificate-issuance evidence; all
certification-relevant authored decisions already belong in the package
(`binding_choices`, `external_assumptions`, `interface_contract`, selected
entrypoints), which `start_session` re-reads and re-applies fresh every time
regardless.

**Regression test:** `tests/test_self_adjoint_demo.py::
ForgedSessionCannotCertifyTests::
test_forged_session_with_real_artifact_hash_does_not_certify` -- starts a
genuine session from the real, committed negative artifact
(`tests/fixtures/unconstrained_operator.pt2`, `examples/dft/models/
structural_gnns.UnconstrainedOperatorGNN`, operator = bare `base_operator`),
confirms it is `blocked_on_premise`, hand-edits the persisted `session.json`
to claim the symmetrized operator (exact string a genuine artifact would
produce) and a `formally_discharged` self-adjointness premise while leaving
`artifact_binding`/`formal_package_binding` untouched, confirms via a raw
`load_session` that the forgery really is schema-valid and really does claim
`ready_for_certificate` (not a strawman), then asserts `certify_session`
given the real artifact raises `ManifestError` -- and that it overwrites the
forged file on disk with the honest, freshly-derived (`blocked_on_premise`)
session rather than merely ignoring the forgery in memory.

**Known residual, explicitly not fixed by this pass:** `start_session`'s own
`output`-reuse shortcut (used by the ordinary interactive/workspace flow, not
by `certify_session` after this fix) still only compares the four bindings
above, not `nodes`. A caller who edits a persisted `session.json`'s `nodes`
by hand and then calls plain `start_session` again against the same
`output` path, with `force_fresh` left `False` (its default), would get that
edited `nodes` content back unchanged -- but this can no longer, by itself,
produce a certificate: `certify_session` never trusts it. Left as a
documented latent characteristic of the interactive-resume shortcut, not a
certificate-issuance vulnerability, and out of this pass's scope (it is a
performance-motivated cache-reuse check for the workspace/display path only).

## 7. Pre-training-scope fix: per-tensor content hash removed from the raw inventory (final engineering pass)

**The gap.** `extractors/torch_export_worker.py::state_inventory` computed
and stored `"sha256": hashlib.sha256(raw).hexdigest()` (a content hash of
the tensor's actual raw bytes) for *every* tensor in `program.state_dict`,
including trainable float `PARAMETER`s -- a content-derived commitment to a
parameter's actual initialized/trained values, even though nothing in this
codebase ever read that field (confirmed by inspection: no other file
references `entry["sha256"]`/`state[...]["sha256"]`). `dftcert/structural/
core.py::structural_ir_from_inventory` already deliberately excluded this
field when building `parameter_structure` (the actual verification
evidence) -- so it never became a formal binding candidate or theorem
premise -- but it was still present in the raw inventory JSON persisted
alongside every session/extraction-result, an unused violation of this
project's own pre-training-scope rule ("do not compute/store a raw-value
content hash in the structural extraction inventory... unless some existing
non-semantic artifact-integrity mechanism demonstrably requires it" -- none
does).

**The fix.** Removed the per-tensor `sha256` field entirely. `state_
inventory` now records only `shape`/`dtype`/`graph_inputs`/`state_kind`/
`aliases` (plus bounded literal `structural_values` for small bool/int
structural buffers, unchanged) for every tensor. The whole-file
`artifact_sha256` (`sha256_file`, unchanged) remains the sole
artifact-identity commitment.

**Regression test:** `tests/test_pretraining_scope.py` -- two artifacts
exported from the same architecture (`CertifiedRingGNN`) with different
`torch.manual_seed` calls have different `artifact_sha256`, but (after this
fix) a byte-identical raw `inventory` and structural IR/formal binding
candidates, and certify the same result. Before this fix, `inventory`
differed too (each trainable parameter's `sha256` sub-field differed),
though it never affected `parameter_structure_sha256`/candidates/the
verification result -- this fix removes that harmless-but-unused
divergence, not a soundness gap on its own.

## 5. Selection vs. minimal construction (research-readiness audit issue 11)

A scope distinction worth stating plainly, not a bug and not a redesign in
progress:

- **Theorem-driven binder/obligation SELECTION -- implemented.** The full
  structural IR (`dftcert.structural.core.structural_ir_from_inventory`) is
  derived first, unconditionally, from the raw artifact inventory alone --
  with no awareness of which Lean entrypoint(s) a package even selected.
  `dftcert.verification.resolver.resolve_entrypoint` then walks the
  *selected* theorem's own binder telescope in Lean and asks, per binder,
  whether one of those already-derived facts happens to fill it.
- **Theorem-driven MINIMAL IR CONSTRUCTION -- not implemented, not planned.**
  An architecture where the selected theorem's requirements would instead
  drive *which* structural facts get derived from the artifact in the first
  place (deriving only what that theorem's binders actually need, skipping
  everything else) does not exist anywhere in this codebase. VISTA always
  computes the full, fixed set of structural facts a plugin's `derive`
  method knows how to compute, regardless of theorem selection; selection
  only ever chooses among facts that already exist.

This does not affect soundness -- a resolved binder is still checked
candidate-by-candidate against real evidence either way -- and no lazy/
on-demand IR construction work is in progress or implied by this document.
See `dftcert/verification/resolver.py`'s own module docstring for the same
distinction stated at the code level.
