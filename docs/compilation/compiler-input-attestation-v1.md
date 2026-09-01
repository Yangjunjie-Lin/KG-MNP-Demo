# Compiler Input Attestation v1

The attestor validates the Prompt 4 package schema/identity/status, recalculates
candidate identities and partitions, verifies Catalog/Project/Pack binding,
resolves the full authority manifest from the workspace, validates known
contracts, and compares proposal/review semantic hashes. Different bytes for
one artifact ID are `DUPLICATE_ARTIFACT_ID`; stale locks/catalogs fail closed.
Only `VALID` can enter planning. Historical artifacts are never rebound.
