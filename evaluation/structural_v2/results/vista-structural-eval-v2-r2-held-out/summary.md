# VISTA Structural V2 evaluation

## Integrity

- all bundle checks passed (manifest agreement, artifact hashes, policy/IR/certificate consistency)

## Domain x class

| domain | class | cases | exact-correct | unsupported-obs | malformed-obs | false certs |
|---|---:|---:|---:|---:|---:|---:|
| operator | malformed | 1 | 1 | 0 | 1 | 0 |
| operator | near_miss | 1 | 1 | 0 | 0 | 0 |
| operator | positive | 1 | 1 | 0 | 0 | 0 |
| operator | unsupported | 1 | 1 | 1 | 0 | 0 |
| spatial | malformed | 1 | 1 | 0 | 1 | 0 |
| spatial | near_miss | 1 | 1 | 0 | 0 | 0 |
| spatial | positive | 1 | 1 | 0 | 0 | 0 |
| spatial | unsupported | 1 | 1 | 1 | 0 | 0 |
| xc | malformed | 1 | 1 | 0 | 1 | 0 |
| xc | near_miss | 1 | 1 | 0 | 0 | 0 |
| xc | positive | 1 | 1 | 0 | 0 | 0 |
| xc | unsupported | 1 | 1 | 1 | 0 | 0 |

## Metrics

- cases: 12
- exact semantic classification: 12/12 (100.0%)
- false certification: 0/9 (0.0%)
- positive acceptance: 3/3 (100.0%)
- near miss certificate withheld: 3/3 (100.0%)
- unsupported certificate withheld: 3/3 (100.0%)
- malformed input rejected: 3/3 (100.0%)
- tamper detection: 81/81 (100.0%)
- reproducible disposition: 12/12 (100.0%)
- bundle integrity issues: 0
- note: exact_semantic_classification is the correctness headline; *_withheld metrics measure certificate refusal only
