# Formal Pre-validation

Formal pre-validation runs 30 deterministic structural and authority checks:
contracts and IDs; Project/Catalog/Pack/Scope bindings; KG-IR and evidence
closure; IRI and namespace rules; baseline/type/label/domain/range/datatype
checks; dependency closure and cycles; partition separation; mapping and SHACL
structure; CQ structural coverage; provider/model invocation closure; conflict
classification; unsupported candidates; finite resources; and artifact
closure.

The result is `PASS`, `REVIEW_REQUIRED`, or `FAIL`, with stable issue ordering.
Any candidate requiring a human decision produces `REVIEW_REQUIRED`; security,
contract, stale-authority, or blocking closure failures produce `FAIL`.

This report is not an OWL consistency result, SHACL execution report, CQ query
result, semantic-accuracy score, or completed human review. Those final
compiler validations are Prompt 5 responsibilities, and the contract fixes all
three execution-claimed flags to false.
