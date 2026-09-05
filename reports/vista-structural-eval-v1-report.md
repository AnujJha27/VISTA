# VISTA Structural V2 — Evaluation Report (`vista-structural-eval-v1` → `vista-structural-eval-v2`)

Date: 2026-08-23

## Outcome summary

| metric | v1 (36 cases) | v2 (48 cases) |
|---|---|---|
| **exact semantic classification** | **31/36 (86.1%)** | **45/48 (93.8%)** |
| **false certification** | **1/27 (3.7%)** | **0/36 (0.0%)** |
| positive acceptance | 9/9 (100.0%) | 12/12 (100.0%) |
| near-miss-certificate-withheld | 9/9 (100.0%) | 12/12 (100.0%) |
| unsupported-certificate-withheld | 9/10 (90.0%) | 13/13 (100.0%) |
| malformed-input-rejected | 7/9 (77.8%) | 12/12 (100.0%) |
| tamper detection | 216/243 (88.9%) | 324/324 (100%) |
| reproducible disposition | 36/36 | 48/48 |
| stable obligation hash | 29/29 | 36/36 |

`*_certificate_withheld` metrics measure certificate refusal, not semantic accuracy. Exact
semantic classification is the correctness headline.

Metric denominators: *false certification* = verified certificates among all primary-run cases whose
independently expected outcome is not `supported-and-compatible` (27 in v1: 36 minus 9 positives —
this includes the near-miss case `operator-nearmiss-indirect-transpose`, whose expectation is
`unsupported`). *unsupported-withheld* = non-certified among expected-`unsupported` cases
(10 in v1 for the same reason).

## A. Evaluation setup

**Corpus.** 36 controlled Torch-exportable cases (`evaluation/structural_v2/corpus_manifest.json`):
12 spatial / 12 operator / 12 XC; per domain: 3 positive, 3 near-miss, 3 unsupported, 3 malformed.
Split: 24 development / 12 held-out evaluation. Expected labels are authored independently in the
manifest; `corpus_models.py` only constructs artifacts and never sees labels.

**Frozen condition `vista-structural-eval-v1`:**
- git revision: `397679a39c605750a567734832fe3ae22ac25f3f` (recorded in `experiment.json`, pinned at `069d492`)
- semantic rules (all rule_version 1): topology.adjacency_state, message.adjacency_fed_matmul,
  xc.hinge_activation, xc.smooth_activation, xc.unrecognized_composition, operator.zero_root,
  operator.identity_root, operator.add_adjoint_pair, operator.unconstrained_root,
  operator.unrecognized_composition
- Structural IR schema: v2 · extractor: torch-export-inventory-v2 · policy: dft-structural-v2
- compiler: dft-structural-lean-v2 · Lean toolchain: leanprover/lean4:v4.31.0
- Python 3.12.5 (Windows), PyTorch 2.6.0+cu124, Windows-11-10.0.26200 via WSL interop
- export path: real production `torch.export.export` + `torch.export.save` (.pt2); extraction via
  `extractors/torch_export_worker.py`; all semantics via `dftcert.structural` — no duplicated logic.

**Harness repairs made during audit** (harness only; no semantic rules changed):
1. Certificate project root corrected to `examples/dft/lean` (home of `Testv2.StructuralV2`).
2. Case output directory created before certificate write.
3. Operator tamper mutation made non-vacuous.
4. UTF-8 enforced for certificate/evidence writes (Windows cp1252 corrupted the Lean `×`).
5. Lenient decoding of Lean diagnostics (build chatter is non-UTF-8 on Windows).
6. Invalid-adjacency injection implemented for `operator-malformed-invalid-adjacency`.

## B. Results

The correctness headline is exact semantic classification: **v1 = 31/36 (86.1%)** and
**v2 = 45/48 (93.8%)**. The v2 mismatches are `spatial-unsupported-nonlinear`,
`operator-nearmiss-b-plus-cT`, and `x2-unsupported-gelu`. The handoff note listed v1 as
30/36; recomputation from the preserved `cases.csv` against manifest expectations gives
31/36, so this report uses the measured value.

| metric | value |
|---|---|
| total cases | 36 (×3 repeats = 108 runs) |
| **false certification** | **1/27 (3.7%)** |
| positive acceptance | 9/9 (100%) |
| near-miss-certificate-withheld | 9/9 (100%) |
| unsupported-certificate-withheld | 9/10 (90%) |
| malformed-input-rejected | 7/9 (77.8%) |
| tamper detection | 216/243 (88.9%) |
| reproducible disposition | 36/36 (100%) |
| stable obligation hash | 29/29 (100%) |

**Definition.** *False certification* = a corpus case whose independently specified expected outcome
is anything other than `supported-and-compatible`, yet whose observed pipeline outcome was a Lean-
`verified` structural certificate. Count: **1** (`xc-unsupported-mixed`).

Full tables: `evaluation/structural_v2/results/latest/{cases.csv,cases.json,summary.json,summary.md,tables.md,tables.tex,metrics.json}`.

## C. Failure analysis (all unexpected results)

1. **xc-unsupported-mixed → certified (FALSE CERTIFICATION). Cause: semantic-rule bug.**
   `_xc_form` scans all ancestors of the XC root; `sigmoid(relu(·))` finds a hinge ancestor and is
   classified `hinge`. Mixed compositions must not inherit a nested hinge form.
   *Preservation:* V1 result retained unmodified. *Proposed fix (separate):* classify by root-level
   activation or reject mixed hinge/smooth ancestry as `unsupported`. Applying it creates
   `vista-structural-eval-v2`.
2. **spatial-unsupported-nonlinear → supported-but-incompatible. Cause: semantic-rule limitation.**
   The message rule silently stops at the first non-matmul node instead of reporting that nonlinear
   separation makes composition unrecognized (`unsupported`).
3. **operator-nearmiss-b-plus-cT → unsupported. Cause: semantic-rule limitation.**
   `base + otherᵀ` falls through to `unrecognized_composition`; the vocabulary has no
   "add with mismatched adjoint source" → `unconstrained_parameter` mapping.
4. **operator-malformed-wrong-role, xc-malformed-wrong-role → unsupported. Cause: incorrect corpus
   expectation.** A contract role pointing at the wrong-but-valid index satisfies current input-
   contract validation (roles unique, set complete); rejection as `malformed` is unenforceable
   without new validation semantics.
5. No exporter, extractor, translation-validation, compiler, Lean, or infrastructure failures in the
   final run.

## D. Tampering & reproducibility

Tampering (post-extraction mutation of meaning-bearing evidence; each run once per non-malformed case):

| mutation | detected | rejected by |
|---|---:|---|
| message_depth, xc_form, operator_form, evidence_node, root_node, rule_identifier, rule_version, ir_field | 27/27 each | translation validation |
| source.artifact_sha256 | **0/27** | **not detected — documented gap**: `validate_translation` re-derives claims from inventory but never rebinds the IR's artifact hash to the actual artifact bytes |

Reproducibility: every clean case ran 3× under the frozen condition. Semantic status, IR value,
generated obligation hash, Lean disposition, and certificate disposition were identical across
repeats for 36/36 cases (obligation-hash stability checked over the 29 cases reaching obligation
generation).

## E. Claim boundary

These experiments establish: for this 36-case frozen corpus, the chain artifact → extraction →
semantic lowering → Structural IR → translation validation → policy → Lean certificate behaves
per its independently specified labels, with 100% positive acceptance, zero false certifications
among near-miss/unsupported-by-vocabulary cases except one documented bug, deterministic outputs,
and strong tamper sensitivity — except artifact-hash rebinding.

Lean checks propositions generated from the analyzer's own IR, and translation validation reuses
the same derivation logic, so this chain proves internal consistency; semantic correctness evidence
comes from agreement with independently authored corpus labels only.

They do **not** establish: numerical accuracy of any model, trained-model quality, general physical
correctness of DFT claims, completeness of Torch-to-IR semantic rules, robustness beyond the
mutation set, or security of the `trusted_local` compilation path.

## F. Condition v2 (`vista-structural-eval-v2`, frozen at `c69e574`)

**Repairs applied (assurance defects only; V1 bundle preserved untouched):**
1. Mixed hinge+smooth XC ancestry now lowers to `unsupported` (`xc.*` rules → version 2). Fixes the
   v1 false certification in both compositions `sigmoid(relu)` and `relu(sigmoid)`.
2. `validate_translation` binds the IR's `source.artifact_sha256` to the extractor-reported artifact
   hash → source-hash tampering is now rejected by translation validation (100% tamper detection).
3. Input contracts additionally require distinct roles to resolve to distinct output roots, making
   the two wrong-role cases enforceable as `malformed`.

**Full v2 result:** exact semantic classification is **45/48 (93.8%)**. The three mismatches are
`spatial-unsupported-nonlinear`, `operator-nearmiss-b-plus-cT`, and `x2-unsupported-gelu`.

**Fresh held-out cohort:** 12 new cases (4 spatial / 4 operator / 4 XC), authored adversarially
around the repaired XC rule *before* any v2 run. 11/12 correct. The one mismatch,
`x2-unsupported-gelu`, is an **incorrect corpus expectation**: `aten.gelu.default` is deliberately
in the smooth-activation vocabulary, so `smooth → supported-but-incompatible` is spec-correct.
The label was authored without consulting the target vocabulary and is retained unmodified.

**Carried-over limitations (unchanged by design):** `spatial-unsupported-nonlinear` reports
`supported-but-incompatible` instead of `unsupported`; `operator-nearmiss-b-plus-cT` reports
`unsupported` instead of `unconstrained_parameter`/incompatible. Both are vocabulary-scope issues,
documented as candidates for a future condition; neither produced an unsound certificate.

**Reproduction:** same commands with `--results evaluation/structural_v2/results/vista-structural-eval-v2`.
Bundles: `results/vista-structural-eval-v1`, `results/vista-structural-eval-v2`.

## G. Hardened score verification

The v2 score exits 0 with zero integrity issues. Running the same verifier against the preserved
v1 bundle is expected to flag its missing v2 condition fingerprint/manifest agreement; the output
was recorded verbatim below (exit status 1):

```json
{
  "cases": 36,
  "exact_semantic_classification": "31/36 (86.1%)",
  "false_certification": "1/27 (3.7%)",
  "positive_acceptance": "9/9 (100.0%)",
  "near_miss_certificate_withheld": "9/9 (100.0%)",
  "unsupported_certificate_withheld": "9/10 (90.0%)",
  "malformed_input_rejected": "7/9 (77.8%)",
  "tamper_detection": "216/243 (88.9%)",
  "reproducible_disposition": "36/36 (100.0%)",
  "bundle_integrity_issues": 13,
  "note": "exact_semantic_classification is the correctness headline; *_withheld metrics measure certificate refusal only"
}
```

## Reproduction commands

```bash
# tests (Linux side)
python3 -m unittest -v tests.test_orchestrator        # 28 tests
python3 -m unittest -v tests.test_dftcert             # 63+ tests
python3 -m unittest -v tests.test_structural_v2_evaluation
make build/tests && ./build/tests                     # C++ assertions
make lean                                             # Lean build

# full evaluation v1 (preserved bundle; do not overwrite)
# full evaluation v2:
cd "/mnt/d/fun stuff/proof_vibe"
rm -rf evaluation/structural_v2/results/vista-structural-eval-v2
python.exe evaluation/structural_v2/run.py --generate --repeats 3 \
  --results evaluation/structural_v2/results/vista-structural-eval-v2
python.exe evaluation/structural_v2/report.py \
  evaluation/structural_v2/results/vista-structural-eval-v2
```
