# Project Workspace v1

Workspace v1 contains `project.yaml`, `project.lock.json`, `sources/`, the
eight artifact areas (`evidence`, `ir`, `proposals`, `reviews`, `confirmed`,
`builds`, `validation`, `packages`), `registry/`, `reports/`, and `tmp/`.
Reports and temporary files are non-authoritative and do not enter the lock.

Prompt 2 only establishes the filesystem boundary. It does not parse sources,
create evidence/IR/proposals, confirm content, compile, publish, or populate a
registry. `artifacts/confirmed` remains empty; files placed there without a
later reviewed workflow are rejected by Prompt 2 validation.

Initialization accepts only a missing or empty real directory. It builds a
complete sibling staging tree, validates the Pack/Catalog and both manifests,
then atomically renames the tree. Failure removes only the owned staging path.
Validation rejects symlinks, non-regular files, unknown top-level authority
entries and missing layout. Status is one of `UNINITIALIZED`, `VALID`,
`INVALID`, `STALE_PROJECT_LOCK`, `STALE_DOMAIN_PACK_LOCK`,
`MISSING_DOMAIN_PACK`, or `CONTRACT_CATALOG_MISMATCH`.

