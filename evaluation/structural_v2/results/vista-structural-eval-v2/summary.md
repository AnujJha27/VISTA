# VISTA Structural V2 evaluation

## Integrity

- all bundle checks passed (manifest agreement, artifact hashes, policy/IR/certificate consistency)

## Domain x class

| domain | class | cases | exact-correct | unsupported-obs | malformed-obs | false certs |
|---|---:|---:|---:|---:|---:|---:|
| operator | malformed | 4 | 4 | 0 | 4 | 0 |
| operator | near_miss | 4 | 3 | 2 | 0 | 0 |
| operator | positive | 4 | 4 | 0 | 0 | 0 |
| operator | unsupported | 4 | 4 | 4 | 0 | 0 |
| spatial | malformed | 4 | 4 | 0 | 4 | 0 |
| spatial | near_miss | 5 | 5 | 0 | 0 | 0 |
| spatial | positive | 4 | 4 | 0 | 0 | 0 |
| spatial | unsupported | 3 | 2 | 2 | 0 | 0 |
| xc | malformed | 4 | 4 | 0 | 4 | 0 |
| xc | near_miss | 3 | 3 | 0 | 0 | 0 |
| xc | positive | 4 | 4 | 0 | 0 | 0 |
| xc | unsupported | 5 | 4 | 4 | 0 | 0 |

## Metrics

- cases: 48
- exact semantic classification: 45/48 (93.8%)
- false certification: 0/36 (0.0%)
- positive acceptance: 12/12 (100.0%)
- near miss certificate withheld: 12/12 (100.0%)
- unsupported certificate withheld: 13/13 (100.0%)
- malformed input rejected: 12/12 (100.0%)
- tamper detection: 324/324 (100.0%)
- reproducible disposition: 48/48 (100.0%)
- bundle integrity issues: 0
- note: exact_semantic_classification is the correctness headline; *_withheld metrics measure certificate refusal only
