# VISTA Structural V2 evaluation

| domain | class | cases | correct | unsupported | malformed |
|---|---:|---:|---:|---:|---:|
| operator | malformed | 3 | 2 | 1 | 2 |
| operator | near_miss | 3 | 2 | 2 | 0 |
| operator | positive | 3 | 3 | 0 | 0 |
| operator | unsupported | 3 | 3 | 3 | 0 |
| spatial | malformed | 3 | 3 | 0 | 3 |
| spatial | near_miss | 3 | 3 | 0 | 0 |
| spatial | positive | 3 | 3 | 0 | 0 |
| spatial | unsupported | 3 | 2 | 2 | 0 |
| xc | malformed | 3 | 2 | 1 | 2 |
| xc | near_miss | 3 | 3 | 0 | 0 |
| xc | positive | 3 | 3 | 0 | 0 |
| xc | unsupported | 3 | 2 | 2 | 0 |

- cases: 36
- false certification: 1/27 (3.7%)
- positive acceptance: 9/9 (100.0%)
- near miss rejection: 9/9 (100.0%)
- unsupported withheld: 9/10 (90.0%)
- malformed rejection: 7/9 (77.8%)
- tamper detection: 216/243 (88.9%)
- deterministic obligation: 36/36 (100.0%)
- reproducible disposition: 36/36 (100.0%)
