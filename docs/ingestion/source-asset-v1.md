# SourceAsset and SourceBatch v1

The Workspace Source Store copies local regular files into
`sources/blobs/sha256/<prefix>/<sha256>`. Source records and batches are stored
under `sources/records` and `sources/batches`. Symlinks, FIFO/socket/device
inputs, unbounded recursion and unsafe display paths are rejected.

`source_id` hashes the byte SHA-256, detected media type and Source Identity
Profile v1. Original name, display path, absolute origin, mtime and registration
time are excluded. Equal bytes and detected media type therefore have the same
ID across absolute directories. Existing blobs are rehashed before reuse.

SourceBatch sorts and de-duplicates source IDs, binds the current ProjectLock,
and verifies every SourceAsset and blob. Its ID includes no label-derived path,
time or machine data. A Catalog migration intentionally requires re-locking the
Workspace before a new IngestionPlan can be created.
