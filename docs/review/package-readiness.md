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
