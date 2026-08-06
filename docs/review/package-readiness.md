# Package Readiness

`publication_manifest.package_status` is only:

- `READY_FOR_COMPILATION`
- `BLOCKED`

## READY_FOR_COMPILATION

Requires all of:

- complete review coverage
- no deferred blocking issues
- complete confirmed reference closure
- empty `confirmed_schema_delta`
- valid confirmed semantics
- matching dependency hashes
- `compile_allowed = true`

## BLOCKED

Occurs when blocking deferred issues remain or confirmed assertions depend on
unconfirmed entities. `compile_allowed` must be `false`.

## Builder default

```bash
kg-mnp confirm build ...                 # rejects BLOCKED packages
kg-mnp confirm build ... --allow-blocked # audit-only BLOCKED package
```

A BLOCKED package is an audit artifact. Stage 06 must not compile it.

## Validator recomputes readiness

`package validate` does not trust `publication_manifest` fields as declared.
It re-derives `package_status`, `compile_allowed`,
`unresolved_blocking_issue_ids`, `unconfirmed_dependency_candidate_ids`, and
related counts from Proposal + Final ReviewDecisionLog + confirmed content, then
requires the package to equal that derivation. Rehashing a forged
`READY_FOR_COMPILATION` status therefore fails closed.
