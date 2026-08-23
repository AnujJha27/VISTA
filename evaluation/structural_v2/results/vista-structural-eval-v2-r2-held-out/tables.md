# VISTA structural eval v1 tables

## Metrics

- exact_semantic_classification: 12/12 (100.0%)
- total_cases: 12
- false_certification: 0/9 (0.0%)
- positive_acceptance: 3/3 (100.0%)
- near_miss_certificate_withheld: 3/3 (100.0%)
- unsupported_certificate_withheld: 3/3 (100.0%)
- malformed_input_rejected: 3/3 (100.0%)
- tamper_detection: 81/81 (100.0%)
- reproducible_disposition: 12/12 (100.0%)
- stable_obligation_hash: 9/9 (100.0%)

## Domain x class

| domain | class | cases | correct | unsupported | malformed | false certs |
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

## Tampering

| mutation | detected | rejected by |
|---|---:|---|
| evidence_node | 9/9 | translation validation |
| ir_field | 9/9 | translation validation |
| message_depth | 9/9 | translation validation |
| operator_form | 9/9 | translation validation |
| root_node | 9/9 | translation validation |
| rule_identifier | 9/9 | translation validation |
| rule_version | 9/9 | translation validation |
| source_hash | 9/9 | translation validation |
| xc_form | 9/9 | translation validation |
