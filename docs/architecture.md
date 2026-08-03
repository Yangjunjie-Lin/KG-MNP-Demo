```
JSON business input (optional)
        │
        ▼
   AssessmentService (application layer)
        │
        ├─ JSON Schema + normalize
        ├─ RDF instance builder
        ├─ Input Graph SHACL
        ├─ OWL-RL
        ├─ Python rule engine
        ├─ Assessment materialization
        ├─ Assessment SHACL
        ├─ Process / auth-code checks
        └─ SPARQL dependency subgraph
        │
        ▼
   Stable AssessmentResponse (+ optional SQLite / artifacts)
        │
        ├─ CLI / pipeline / showcase
        └─ FastAPI /api/v1 (+ presentation views)
```

Ontology runtime modules are loaded explicitly from `loader.ontology_paths()` (offline).
Module catalog authority: `config/ontology_modules.yaml`.
SQLite stores execution metadata only; RDF remains semantic authority.
Neo4j remains optional and is not required for API health.

## Evidence relations

| Predicate | Role |
|-----------|------|
| `hasCaseEvidence` | Case → available evidence pool |
| `usesEvidence` | Assessment → evidence actually used in that evaluation |

Evidence selection is relation-based. IRI naming prefixes such as `Ev-03-` are display labels only.

## Trace structure

Audit output is a **dependency subgraph** rooted at the case assessment.
Edge selection is defined solely by `queries/assessment_subgraph.rq`.
Python (`trace_graph.py`) converts SPARQL rows into stable `nodes`/`edges` and verifies every edge exists in the RDF graph. Display layers must not invent predicates.

## Rule version selection

Applicable rule versions are chosen by `assessment_time` against closed
`effective_from`/`effective_to` windows. Overlaps or gaps raise
`RuleConfigurationError` (see `scripts/check_rule_versions.py`).

## Responsibility split

| Layer | Responsibility |
|-------|----------------|
| OWL | Concepts, relations, stable cardinality/disjointness |
| SHACL | Instance completeness (input + assessment graphs) |
| OWL-RL | Deterministic type/relation expansion |
| YAML + Python | Eligibility checks needing numeric/date logic |
| Process service | Authorization code / transition permission (separate from eligibility) |
| JSON adapter | Schema validate + normalize; no eligibility logic |
| RDF builder | Deterministic IRI/instance generation; no decisions |
| Application service | Single assessment entry for CLI/API |
| SPARQL / trace_graph | Offline audit subgraph |
| SQLite | Execution metadata + artifact index |
| Neo4j + Cypher | Persistent graph store and path traces (optional) |

Alignments (`mnp-alignments.ttl`) are documentation-grade and optional at runtime.
Start Neo4j with `docker compose up -d` — see `docs/neo4j_extension.md`.
