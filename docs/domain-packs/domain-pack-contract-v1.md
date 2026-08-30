# Domain Pack Contract v1

DomainPackManifest v1 declares exact identity/version, lifecycle,
compatibility, license expression, capabilities, namespaces, assets,
entrypoints, exact dependencies and controlled extensions. Pack IDs are lower
kebab-case and must equal their directory. Asset paths are relative POSIX paths
and entrypoints reference asset IDs rather than duplicate paths.

Lifecycle meanings are `PLANNED`, `SCAFFOLD`, `EXPERIMENTAL`,
`MIGRATED_BASELINE`, `STABLE`, and `DEPRECATED`. PLANNED makes no implemented
capability claim. MIGRATED_BASELINE preserves known assets but is not a
cross-industry stability claim. Capability declarations and asset kinds close
in both directions.

Packs provide data, knowledge and constraints only. Python, shell scripts,
binaries, executable permissions, path/symlink escapes and undeclared semantic
files are rejected. RDF, SHACL RDF, templated/read-only SPARQL, JSON/YAML and
ontology IRI/import closure are checked locally; no Pack file is executed and
no remote ontology import is fetched.

