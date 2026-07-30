```
Case RDF + Regulations + Systems
        │
        ▼
   SHACL (pySHACL) ── integrity of instances
        │
        ▼
   OWL-RL (owlrl) ── subclass/property expansion
        │
        ▼
   Python rule engine ── amounts, dates, validity, missing evidence
        │
        ├──────────────────────────────┐
        ▼                              ▼
   Assessment RDF (SPARQL)      Neo4j (n10s + Cypher overlay)
   offline --backend rdf        practical --backend neo4j (default)
```

## Responsibility split

| Layer | Responsibility |
|-------|----------------|
| OWL | Concepts, relations, stable cardinality/disjointness |
| SHACL | Instance completeness with readable messages |
| OWL-RL | Deterministic type/relation expansion |
| YAML + Python | Eligibility checks needing numeric/date logic |
| SPARQL | Offline audit trails |
| Neo4j + Cypher | Persistent graph store and path traces |

Alignments (`mnp-alignments.ttl`) are documentation-grade and optional at runtime.
Start Neo4j with `docker compose up -d` — see `docs/neo4j_extension.md`.
