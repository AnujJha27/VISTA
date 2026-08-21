# VISTA Structural V2 evaluation

| domain | class | cases | correct | unsupported | malformed |
|---|---:|---:|---:|---:|---:|
| operator | malformed | 4 | 4 | 0 | 4 |
| operator | near_miss | 4 | 3 | 2 | 0 |
| operator | positive | 4 | 4 | 0 | 0 |
| operator | unsupported | 4 | 4 | 4 | 0 |
| spatial | malformed | 4 | 4 | 0 | 4 |
| spatial | near_miss | 5 | 5 | 0 | 0 |
| spatial | positive | 4 | 4 | 0 | 0 |
| spatial | unsupported | 3 | 2 | 2 | 0 |
| xc | malformed | 4 | 4 | 0 | 4 |
| xc | near_miss | 3 | 3 | 0 | 0 |
| xc | positive | 4 | 4 | 0 | 0 |
| xc | unsupported | 5 | 4 | 4 | 0 |

- cases: 48
- false certification: 0/36 (0.0%)
- positive acceptance: 12/12 (100.0%)
- near miss rejection: 12/12 (100.0%)
- unsupported withheld: 13/13 (100.0%)
- malformed rejection: 12/12 (100.0%)
- tamper detection: 324/324 (100.0%)
- deterministic obligation: 48/48 (100.0%)
- reproducible disposition: 48/48 (100.0%)
