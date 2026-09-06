# Prompt 6 — Ontology Registry and Controlled Release Lifecycle

The lifecycle layer is an offline, content-addressed control plane. A package is
first `VALIDATED_UNPUBLISHED`, an imported registry record is
`IMPORTED_VERIFIED`, a reviewed immutable release is `RELEASED`, and an
environment pointer is `CONTROL_PLANE_SELECTED` (or
`NO_RELEASE_SELECTED`). These states are separate documents and are never
silently inferred from one another.

Registry events are append-only JSON records linked by sequence, previous hash,
semantic hash, and a CAS head. Snapshots and indexes are deterministic
projections that can be rebuilt from the event log. Package and lock bytes are
copied into content-addressed storage and are never modified in place.

Semantic diffs compare effective TBox, ABox, SHACL, mappings, competency
questions, dependencies, annotations, provenance, and metadata. Unknown
constructs remain review-blocking. Release publication requires explicit human
review; activation and rollback require an environment policy and a CAS pointer
transition.
