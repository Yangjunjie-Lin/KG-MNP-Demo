# Domain Packs

This directory contains data-only domain-owned assets governed by formal
`DomainPackManifest` and deterministic `DomainPackLock` v1 contracts. Local
validation rejects path escape, unsafe manifests, undeclared semantic files,
and executable content. No Pack content is executed or fetched remotely.

- `minimal`: `EXPERIMENTAL`, six industry-neutral contract-test assets;
- `mnp`: `MIGRATED_BASELINE`, formally enumerated and locked historical assets;
- `forestry`: `PLANNED`, zero-content intent for a future forestry pilot.

See `docs/domain-packs/README.md` for authority and lifecycle boundaries. A
Manifest or Lock establishes identity and closure; it does not establish
confirmation, publication, production readiness, or universal validity.
