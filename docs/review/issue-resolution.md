# Issue Resolution

Every issue decision lands in either `rejected_items` or `deferred_items`.
Issues never enter confirmed ABox or schema-delta sections.

## REJECT

Requires non-empty rationale, reviewer, and `decided_at`.

If the original issue is `blocking=true`, REJECT also requires at least one of:

- non-empty decision `evidence_refs`
- a related candidate decision of `MODIFY_AND_CONFIRM` or `REJECT`

## DEFER

Retains the issue identity in the package and records audit detail in
`publication_manifest.deferred_issue_details`.

Any deferred blocking issue forces:

```text
package_status = BLOCKED
compile_allowed = false
```
