# Old/New Compiler Mapping

The old `kg_mnp.compilation` entry consumes the historical Stage 06 contract,
loads MNP-specific ontology/shapes, compiles primarily ABox, and proceeds into
the retained publication-era artifact model. The new `kg_mnp.semantic_kernel`
entry consumes only `OntologyConfirmedModelingPackage/1.0.0`, reconstructs its
authority closure, dispatches every confirmed TBox/Mapping/ABox/SHACL type,
and ends at `VALIDATED_UNPUBLISHED`.

Canonical NT/NQ and pinned ROBOT/HermiT execution have one generic primitive
with legacy wrappers. Prompt 5 adds structural baseline skolemization,
configurable readable RDF prefixes, named graph roles, statement provenance,
explicit CQ oracles, strict package locking and deterministic `.kgop` export.
The new compiler never calls Stage 06 `build_artifact_set`, publication,
activation, a provider, an LLM, GraphDB, or registry code.
