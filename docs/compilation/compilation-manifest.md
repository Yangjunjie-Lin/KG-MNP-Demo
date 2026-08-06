# Compilation Manifest

The manifest records the compiler policy/dependencies, stable graph IRIs,
asserted/provenance/review counts, SHACL and OWL statuses, and a closed artifact
manifest. Every artifact has an ID, relative path, role, media type, byte hash,
semantic hash, size, and RDF count where applicable. It contains no timestamps,
absolute paths, host data, usernames, or run durations.

The JSON Schema is closed at every object boundary. Artifact paths and IDs are
unique, paths are repository-independent relative paths without parent
segments, hashes are lowercase SHA-256 values, and triple and quad counts are
mutually exclusive. SHACL result counts are checked against the projected
results rather than trusted as declarations.

The manifest self-hash excludes only `compilation_id` and
`compilation_semantic_hash`; a validator always reconstructs the expected set
from the authority inputs, so a self-consistent forged manifest is insufficient.
