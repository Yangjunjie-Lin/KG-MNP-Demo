# Public Contract Policy

Prompt 2 freezes one public Contract Kernel before plugins, ingestion, IR,
compilers, registries, or UI modules grow independent formats. The sole catalog
is packaged at `kg_mnp.contracts/catalog.json`; every public schema is immutable
at a released `$id`. A breaking change receives a new Semantic Version and a
new `$id`. Corrections that alter accepted or rejected payloads never replace
published bytes in place.

Public schemas use JSON Schema Draft 2020-12, closed core objects, stable HTTPS
identifiers, and package-local `$ref` targets. Registry construction has no
network retrieval callback. Secrets, absolute paths, usernames, machine names,
wall-clock fields in digest preimages, executable extensions, NaN and Infinity
are outside the public contracts.

Authority is explicit: descriptive and proposal artifacts are not confirmed
inputs. An Artifact Reference, manifest, Domain Pack, Workspace, or lock proves
content identity only. It cannot prove review or publication. Only a reviewed
Confirmed Modeling Package may enter the retained deterministic compiler.

## Stable CLI exit codes

The Prompt 2 public commands use one stable exit-code table. Validation and
security failures are never reported as success.

| Code | Name | Meaning |
|---:|---|---|
| 0 | `SUCCESS` | Command completed and every requested validation/check passed. |
| 2 | `USAGE_ERROR` | Command syntax or required arguments are invalid. |
| 3 | `CONTRACT_INVALID` | A document, schema, Catalog, or Domain Pack contract is invalid. |
| 4 | `PATH_OR_SECURITY_VIOLATION` | Unsafe path, document, filesystem object, or executable content was rejected. |
| 5 | `LOCK_MISMATCH` | A Catalog, Pack, or Project lock is absent, stale, tampered, or mismatched. |
| 6 | `DEPENDENCY_RESOLUTION_ERROR` | An exact local Pack version or dependency closure cannot be resolved. |
| 7 | `WORKSPACE_INVALID` | Workspace manifest/layout/authority state is invalid. |
| 8 | `INTERNAL_ERROR` | An unexpected implementation error reached the CLI boundary. |

`--json` returns the stable keys `command`, `status`, `code`, `subject`,
`errors`, `warnings`, and `result`; error arrays are deterministically ordered.
Ordinary failures print concise diagnostics without a Python traceback. A full
traceback is emitted only when the caller explicitly supplies `--debug`.

## Compatibility and scope

The retained `kg_mnp.modeling` contract functions are thin compatibility
layers over this Kernel and produce the same canonical bytes, hashes, schema
payloads, and accept/reject behavior. Other Stage/Phase schema registries stay
internal and are marked `INTERNAL_CONTRACT_MIGRATION_DEFERRED`; they are not a
second public Catalog.
