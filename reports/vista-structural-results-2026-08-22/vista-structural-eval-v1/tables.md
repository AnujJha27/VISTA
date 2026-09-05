# VISTA structural eval v1 tables

## Metrics

- total_cases: 36
- false_certification: 1/27 (3.7%)
- positive_acceptance: 9/9 (100.0%)
- near_miss_rejection: 9/9 (100.0%)
- unsupported_withheld: 9/10 (90.0%)
- malformed_rejection: 7/9 (77.8%)
- tamper_detection: 216/243 (88.9%)
- reproducible_disposition: 36/36 (100.0%)
- stable_obligation_hash: 29/29 (100.0%)

## Domain x class

| domain | class | cases | correct | unsupported | malformed | false certs |
|---|---:|---:|---:|---:|---:|---:|
| operator | malformed | 3 | 2 | 1 | 2 | 0 |
| operator | near_miss | 3 | 2 | 2 | 0 | 0 |
| operator | positive | 3 | 3 | 0 | 0 | 0 |
| operator | unsupported | 3 | 3 | 3 | 0 | 0 |
| spatial | malformed | 3 | 3 | 0 | 3 | 0 |
| spatial | near_miss | 3 | 3 | 0 | 0 | 0 |
| spatial | positive | 3 | 3 | 0 | 0 | 0 |
| spatial | unsupported | 3 | 2 | 2 | 0 | 0 |
| xc | malformed | 3 | 2 | 1 | 2 | 0 |
| xc | near_miss | 3 | 3 | 0 | 0 | 0 |
| xc | positive | 3 | 3 | 0 | 0 | 0 |
| xc | unsupported | 3 | 2 | 2 | 0 | 1 |

## Tampering

| mutation | detected | rejected by |
|---|---:|---|
| evidence_node | 27/27 | translation validation |
| ir_field | 27/27 | translation validation |
| message_depth | 27/27 | translation validation |
| operator_form | 27/27 | translation validation |
| root_node | 27/27 | translation validation |
| rule_identifier | 27/27 | translation validation |
| rule_version | 27/27 | translation validation |
| source_hash | 0/27 | not detected (documented gap) |
| xc_form | 27/27 | translation validation |
