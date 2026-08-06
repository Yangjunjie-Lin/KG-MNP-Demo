# Decision Semantics

## Candidate decisions

Allowed:

- `CONFIRM`
- `MODIFY_AND_CONFIRM`
- `REJECT`
- `DEFER`

## Issue decisions

Allowed:

- `REJECT` — issue is not modeling-relevant, or is resolved by explicit evidence /
  related candidate decisions
- `DEFER` — issue remains unresolved and is retained for audit / readiness

Forbidden for issues:

- `CONFIRM`
- `MODIFY_AND_CONFIRM`
- `DEPRECATE`

## DEPRECATE

In Stage 05 `DATASET_MODELING`, `DEPRECATE` is forbidden. Stage 04 proposals do
not propose TBox term retirement; that belongs to a future ontology-release
review.

## Coverage

Every proposal `candidate_id` and every proposal `issue_id` must have exactly one
decision before finalization. `DEFER` counts as an explicit decision.
