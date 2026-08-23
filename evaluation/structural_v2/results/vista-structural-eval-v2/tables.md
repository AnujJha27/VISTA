# VISTA structural eval v1 tables

## Metrics

- exact_semantic_classification: 48/48 (100.0%)
- total_cases: 48
- false_certification: 0/36 (0.0%)
- positive_acceptance: 12/12 (100.0%)
- near_miss_certificate_withheld: 12/12 (100.0%)
- unsupported_certificate_withheld: 13/13 (100.0%)
- malformed_input_rejected: 12/12 (100.0%)
- tamper_detection: 324/324 (100.0%)
- reproducible_disposition: 48/48 (100.0%)
- stable_obligation_hash: 36/36 (100.0%)

## Domain x class

| domain | class | cases | correct | unsupported | malformed | false certs |
|---|---:|---:|---:|---:|---:|---:|
| operator | malformed | 4 | 4 | 0 | 4 | 0 |
| operator | near_miss | 4 | 4 | 1 | 0 | 0 |
| operator | positive | 4 | 4 | 0 | 0 | 0 |
| operator | unsupported | 4 | 4 | 4 | 0 | 0 |
| spatial | malformed | 4 | 4 | 0 | 4 | 0 |
| spatial | near_miss | 5 | 5 | 0 | 0 | 0 |
| spatial | positive | 4 | 4 | 0 | 0 | 0 |
| spatial | unsupported | 3 | 3 | 3 | 0 | 0 |
| xc | malformed | 4 | 4 | 0 | 4 | 0 |
| xc | near_miss | 3 | 3 | 0 | 0 | 0 |
| xc | positive | 4 | 4 | 0 | 0 | 0 |
| xc | unsupported | 5 | 5 | 5 | 0 | 0 |

## Tampering

| mutation | detected | rejected by |
|---|---:|---|
| evidence_node | 36/36 | translation validation |
| ir_field | 36/36 | translation validation |
| message_depth | 36/36 | translation validation |
| operator_form | 36/36 | translation validation |
| root_node | 36/36 | translation validation |
| rule_identifier | 36/36 | translation validation |
| rule_version | 36/36 | translation validation |
| source_hash | 36/36 | translation validation |
| xc_form | 36/36 | translation validation |
