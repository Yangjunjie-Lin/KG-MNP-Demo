# Domain Pack Lock v1

DomainPackLock v1 binds raw and semantic manifest hashes, sorted asset records,
exact dependencies, canonicalization profile, content digest and lock ID. Each
asset record contains only asset ID, relative path, media type, byte size and
raw SHA-256. The lock has no time or absolute path.

The content-digest preimage consists of `manifest_kind`, `schema_version`,
`pack_id`, `pack_version`, both manifest hashes, sorted `assets`, sorted
`dependencies`, and `canonicalization_profile`. The lock ID is the stable
`domain-pack-lock` URN derived from that digest. Any declared file change or
dependency change makes verification fail.

Dependency resolution is exact-version and local-only. Every dependency names
its content digest and required capabilities. The resolver detects missing
packs, version conflicts, digest mismatch and cycles, and returns deterministic
closure order. `lock --check`, `validate`, `inspect`, and `verify-lock` are
read-only.

