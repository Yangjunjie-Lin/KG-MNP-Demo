# Project Lock v1

ProjectLock v1 binds raw and semantic `project.yaml` hashes, the public catalog
semantic digest, exact resolved Pack locks/capabilities/dependency depths, and
Workspace layout version. Resolved Packs are sorted by ID and version.

Its digest preimage is the complete lock core without `content_digest` or
`lock_id`. The stable `project-lock` URN is derived from the content digest.
Manifest, Catalog, Pack content, Pack lock or closure changes make the Project
Lock stale. Regeneration is atomic; `kg-mnp workspace lock --check` never writes.

