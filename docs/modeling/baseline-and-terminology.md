# Baseline Snapshot and Terminology

`OntologyBaselineSnapshot` is a read-only, deterministic index over the
ontology and SHACL assets in the exact selected Domain Pack locks. Every
element retains its source asset ID and file SHA-256. Only the locked local
dependency closure is parsed; remote `owl:imports`, symlinks, path escape,
changed asset bytes, duplicate IRIs, and triple/import-depth limit violations
fail closed. The snapshot never modifies or copies a Domain Pack into the
workspace.

Indexes cover IRI, label, normalized label, language, property type,
domain/range, hierarchy, and source asset. Equivalent packs at different
absolute paths produce the same snapshot bytes.

`TerminologyCatalog` combines locked Domain Pack terminology, baseline labels
and definitions, approved scope terms, evidence-bound KG-IR field/header/record
labels, and explicit human terms. Each term preserves source type, source
reference, evidence, aliases, definitions, candidate IRIs, language, and
status. KG-IR content remains untrusted evidence. No internet dictionary,
remote ontology, unpinned embedding, or model-authored definition becomes an
authority.
