```
JSON business input (optional)
        │
        ▼
   JSON Schema + normalize
        │
        ▼
   RDF instance builder (hasCaseEvidence)
        │
Case RDF + Regulations + Systems
        │
        ▼
   Input Graph SHACL (pySHACL)
        │
        ▼
   OWL-RL (owlrl) ── subclass/property expansion
        │
        ▼
   Python rule engine ── amounts, dates, validity (assessment_time param)
        │
        ▼
   Materialize EligibilityAssessment / Decision / Reasons
        │
        ▼
   Assessment Graph SHACL
        │
        ├──────────────────────────────┐
        ▼                              ▼
   SPARQL dependency subgraph   Neo4j (n10s + Cypher overlay)
   offline --backend rdf        practical --backend neo4j
```

## Evidence relations

| Predicate | Role |
|-----------|------|
| `hasCaseEvidence` | Case → available evidence pool |
| `usesEvidence` | Assessment → evidence actually used in that evaluation |

Evidence selection is relation-based. IRI naming prefixes such as `Ev-03-` are display labels only.

## Trace structure

Audit output is a **dependency subgraph** rooted at the case assessment, not a fabricated linear chain. Edges must exist as RDF triples (`producesBlockingReason`, `supportedByEvidence`, `triggeredByRule`, …).

## Responsibility split

| Layer | Responsibility |
|-------|----------------|
| OWL | Concepts, relations, stable cardinality/disjointness |
| SHACL | Instance completeness (input + assessment graphs) |
| OWL-RL | Deterministic type/relation expansion |
| YAML + Python | Eligibility checks needing numeric/date logic |
| JSON adapter | Schema validate + normalize; no eligibility logic |
| RDF builder | Deterministic IRI/instance generation; no decisions |
| SPARQL / trace_graph | Offline audit subgraph |
| Neo4j + Cypher | Persistent graph store and path traces (optional) |

Alignments (`mnp-alignments.ttl`) are documentation-grade and optional at runtime.
Start Neo4j with `docker compose up -d` — see `docs/neo4j_extension.md`.
