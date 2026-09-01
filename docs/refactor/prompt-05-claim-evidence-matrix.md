# Prompt 5 Claim–Evidence Matrix

## SUPPORTED

The implementation and tests support: Confirmed Package as sole semantic
input; deterministic TBox/ABox/SHACL compilation; inert MappingPlan; canonical
named-graph RDF; local pinned OWL profile/HermiT gates; final SHACL; explicit
read-only CQ execution with an oracle; statement provenance, review audit and
evidence lineage; strict manifest/lock verification; deterministic `.kgop`;
and absence of automatic publication, activation, repair, version bump,
registry writes and GraphDB writes.

## PARTIALLY_SUPPORTED

- OWL consistency is a result only for the pinned engine, declared profile and
  exact local closure actually executed. It is not a proof for every possible
  OWL semantic regime.
- CQ status is conclusive only for registered queries with explicit assertions.
  `EXECUTED_NO_ORACLE` remains `UNVERIFIED`.
- Structural baseline skolemization is KG-MNP RDF Canonical Profile v1, not a
  claim of URDNA2015 conformance.

## NOT_IMPLEMENTED

Semantic diff, automatic SemVer classification, Package Registry rewrite,
release publication, version activation, rollback rewrite, and live GraphDB
deployment are not implemented by Prompt 5.

## OUT_OF_SCOPE

LLM repair, automatic ontology evolution, business Action execution, and a
Forestry implementation are outside this phase.
