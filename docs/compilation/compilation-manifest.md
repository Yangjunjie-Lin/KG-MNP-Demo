# Compilation Manifest

The manifest records the compiler policy/dependencies, stable graph IRIs,
asserted/provenance/review counts, SHACL and OWL statuses, and a closed artifact
manifest. Every artifact has an ID, relative path, role, media type, byte hash,
semantic hash, size, and RDF count where applicable. It contains no timestamps,
absolute paths, host data, usernames, or run durations.

The manifest self-hash excludes only `compilation_id` and
`compilation_semantic_hash`; a validator always reconstructs the expected set
from the authority inputs, so a self-consistent forged manifest is insufficient.
