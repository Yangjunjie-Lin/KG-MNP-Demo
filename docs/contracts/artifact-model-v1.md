# Artifact Model v1

ArtifactReference v1 binds a stable artifact URN, type, contract, schema,
safe relative path, media type, byte size, SHA-256, optional semantic hash,
dependencies and provenance references. Dependency and provenance arrays are
deduplicated and sorted. When a filesystem root is supplied, size, digest and
root confinement are verified.

ArtifactManifest v1 describes a closed immutable set and selected roots. Its
artifact dependency graph must have no duplicate, dangling, or cyclic edge.
`artifact_set_id` is derived from the canonical manifest without that field.
The manifest deliberately has no review-status or publication-authority field;
an artifact type that claims confirmed authority is rejected by semantic
validation. This contract is not the final Versioned Ontology Package.

