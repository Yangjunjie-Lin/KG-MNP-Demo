# Modification Policy

`MODIFY_AND_CONFIRM` is the most constrained Stage 05 path.

## Limits

- Only candidate targets are allowed
- Candidate kind cannot change
- Publication scope must remain `ABOX`
- Original `source_paths`, business evidence, modeling evidence, and mapping rule
  IDs must be preserved
- Target terms must exist in the frozen ontology term inventory with the correct
  OWL term type
- No TBox / schema-delta creation is allowed
- Instance IRIs must remain absolute project instance IRIs or stable URNs

## Confirmed representation

Stage 05 does not mutate a proposal candidate in place and reuse its old
`candidate_id`. Packages store a confirmation envelope with:

- `source_candidate_id`
- `effective_candidate_id`
- `confirmation_mode` (`ORIGINAL` or `MODIFIED`)
- `semantic_content`
- `semantic_hash`
- `confirmed_item_id`

Review evidence remains on the decision, not disguised as original business
evidence.
