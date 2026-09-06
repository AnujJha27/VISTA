# VISTA generalization: domain-agnostic verification harness

**Status: implemented, first pass.** `dftcert/structural/plugin.py` defines
`StructuralPlugin` (a Python ABC); `dftcert/structural/dft_capability_plugin.py` is
`DFTCapabilityPlugin`, VISTA's only plugin (everything that used to be hardcoded in
`core.py`), exposed as the module-level singleton `DFT_CAPABILITY_PLUGIN`;
`dftcert/structural/core.py` is now the domain-agnostic harness -- every
public function takes `plugin: StructuralPlugin = DFT_CAPABILITY_PLUGIN`, so every
existing caller (CLI, tests, eval corpora) keeps working unchanged while a
different plugin is now a real, pluggable option.

Resolved (from the open questions below): the interface is a **Python ABC**
(not a declarative schema), and the Lean import target is a **per-plugin
default** (`plugin.lean_import`, e.g. `"Testv2.StructuralV2"` for DFT) --
not a per-run override. A plugin brings its own Lean proof base; the harness
never hardcodes one.

## The idea

Today VISTA is hardcoded to one domain: DFT self-energy operators over a
GNN-shaped candidate (`topology`/`message_passing`/`xc`/`operator`/
`locality`, all DFT-flavored names, all defined in
`dftcert/structural/core.py`, all checked against one fixed Lean module,
`Testv2.StructuralV2`).

The goal is to stop being DFT-specific. VISTA should become a general
**verification harness**: given (1) a candidate artifact, (2) a claim about
that artifact, and (3) a **Lean proof base that the user supplies**, VISTA
extracts the artifact's real values, generates the Lean obligations that
follow from the claim, and checks them against the user's own Lean library
-- not a library VISTA ships and hardcodes. DFT/self-energy locality becomes
*one instance* of this, not the whole system.

Concretely, from the user: *"people plug in the base for their verification
as Lean proofs and we use them"* -- the Lean side (the definitions and
theorems the generated obligations are checked against) is supplied by
whoever is using VISTA for their domain, not shipped as
`Testv2.StructuralV2` forever.

## What's domain-specific today vs. what's actually generic

Looking at the current pipeline with this split in mind:

**Already generic (the harness):**
- Artifact extraction is already generic at the graph level: nodes, ops,
  targets, args, small-tensor raw values, hashes. Nothing in
  `extractors/torch_export_worker.py` is DFT-specific.
- Hash binding, translation validation (independent recompute-and-compare),
  certificate assembly (`sourceSha256`/`irSha256` binding,
  `generated_*_binding := rfl` theorems), and `verify_structural_certificate`
  (`lake env lean` invocation, timeout/process-group handling) don't know or
  care what the claim being checked *means*.
- The overall shape -- extract -> derive claims -> generate Lean obligations
  -> verify -> bind into a certificate -- is domain-agnostic already.

**Currently hardcoded (the DFT plugin, living inside the "generic" module):**
- The specific roles (`xc_energy`, `learned_self_energy`, `message_state`)
  and the requirement that there be exactly three of them.
- The specific semantic-lowering rules (`_xc_form`, `_operator_construction`,
  `_topology`, `_message_chain`) -- these are pattern-matches over
  DFT/GNN-shaped Torch ops (`aten.relu`, `aten.eye`, adjacency matmul chains).
- The specific checks (`xc_discontinuity_compatible`, `self_adjoint`,
  `operator_locality_verified`) and their pass/fail semantics.
- The specific Lean target: every generated obligation names
  `Testv2.StructuralV2.<something>` -- a module VISTA ships, not one the
  verifier-author wrote.

## Implemented shape

`dftcert/structural/` now has three modules:

1. **`core.py`** (the harness, domain-agnostic): artifact extraction
   plumbing, hashing, translation-validation re-derivation, certificate
   assembly/binding, `verify_structural_certificate` (`lake env lean`
   invocation). Every public function (`structural_ir_from_inventory`,
   `validate_structural_ir`, `validate_translation`, `assess_structural_ir`,
   `structural_failure_witnesses`, `structural_report`,
   `structural_model_description`, `generate_structural_obligations`,
   `assemble_structural_certificate`) takes `plugin: StructuralPlugin =
   DFT_CAPABILITY_PLUGIN` as a keyword-only argument.
2. **`plugin.py`**: the `StructuralPlugin` ABC. `role_roots` (output-contract
   resolution) is a concrete, generic method on the base class -- any plugin
   gets it for free from `role_requirements()`. Everything else is abstract:
   `derive`, `ir_sections`, `translation_sections`, `validate_ir_sections`,
   `revalidate`, `checked_claim_names`, `checks`, `supported`,
   `failure_witness`, `what_was_checked`, `model_description_lines`,
   `lean_preamble_fields`, `lean_statements`. `derive()` is the single
   source of truth: it computes semantic derivations *and* the actual
   observation (for DFT: the locality fact) once; every other method reads
   back what `derive()` already computed rather than recomputing anything,
   so two code paths can never silently disagree.
3. **`dft_capability_plugin.py`**: `DFTCapabilityPlugin`, moving essentially
   all of the old `core.py` DFT-specific logic (topology/message-passing/XC
   form/operator-construction/pre-training capability) behind that
   interface, plus `DFT_CAPABILITY_PLUGIN = DFTCapabilityPlugin()`, the
   module-level default instance. Its `lean_import = "Testv2.StructuralV2"`.

The harness produces byte-for-byte the same IR/certificate shape DFT always
produced (`ir_sections`/`translation_sections` are merged straight into the
top-level IR/translation dicts) -- this was a pure reorganization for DFT,
not a behavior change, confirmed by the full existing test suite and a real
end-to-end Lean re-verification passing unchanged after the split.

## Why this is a real generalization, not a relabeling

The distinction that matters: today, if you wanted to verify a *different*
kind of claim (say, a robotics control policy's Lyapunov stability, or a
crypto protocol's non-interference property) you'd have to fork
`dftcert/structural/core.py` and hand-edit DFT-specific functions. Under this
design, you'd write a plugin implementing the same small interface DFT now
implements, point it at your own Lean library, and reuse extraction, hashing,
translation validation, and certificate assembly unchanged.

## Non-goals (explicitly out of scope for this note and for any first pass)

- This is not a request to build a general theorem-proving orchestrator (the
  existing `orchestrator/` package already exists for LLM-driven proof
  search across arbitrary Lean goals; this note is about VISTA's
  *artifact-verification* harness specifically, not proof search).
- This does not imply rewriting the DFT plugin's actual semantics
  (topology/xc/operator/locality) -- only relocating them behind an
  interface.
- No commitment yet to exact interface method names/shapes above; the
  sketch is meant to be concrete enough to implement against, not final.

## Resolved

1. ~~Python ABC vs. declarative schema?~~ **Python ABC** (`StructuralPlugin`).
   No declarative manifest layer was added -- YAGNI until a second plugin
   actually needs one.
4. ~~Where does the Lean-import configuration live?~~ **Per-plugin default**
   only (`plugin.lean_import`), not a per-run override -- nothing has asked
   for per-run override yet.

## Still open

2. `structural_report`'s `what_was_checked` strings, and
   `structural_model_description`'s "Adjacency evidence" line, are still
   DFT-flavored prose hardcoded in the harness (`core.py`), not sourced from
   the plugin -- true generic report language across domains is unsolved.
3. Backward compatibility check for V1/V2 frozen evaluation results
   (`evaluation/structural_v2/`): not yet done as a formal audit. The
   post-training V3 plugin and its `evaluation/structural_v3/` corpus
   were removed entirely (this project's claim is pre-training only, and
   keeping a post-training plugin alongside it made that ambiguous). What
   *is* confirmed: the full existing unit test suite and a fresh real Lean
   re-verification pass unchanged post-split, and the one remaining
   plugin's IR/certificate output shape is unchanged (a pure reorganization).
   No second plugin exists yet to prove the interface actually generalizes
   in practice -- treat it as a sound first pass, not a proven-general one.

This document will be updated (not silently replaced) as the design evolves
further, e.g. when a second plugin is actually written.

## Superseding direction: theorem-centric verification

This note's `StructuralPlugin` still defines what it means for the DFT
plugin's own *fixed* `checks()` to be satisfied. A deeper architectural
change, specified in `VISTA_THEOREM_CENTRIC_CODEX_SPEC.md` and implemented
under `dftcert/verification/`, inverts that: the selected Lean *theorem*
now defines the mathematical requirement, and the artifact adapter (this
same `StructuralPlugin`, plus its new `formal_binding_candidates()`) only
supplies Lean-instantiable facts. `StructuralPlugin.checks()`/`lean_
statements()` and the `vista structural` CLI commands are unchanged and
still work -- the theorem-centric path (`vista verify ...`) is additive,
not a replacement, until a direct test proves equivalence and deletion is
explicitly approved (per that spec's section 20.2).
