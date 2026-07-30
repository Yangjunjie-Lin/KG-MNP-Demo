# Ontology files

| File | Role | Runtime? |
|------|------|----------|
| `mnp-core.ttl` | Domain classes, properties, OWL cardinality | Yes |
| `mnp-compliance.ttl` | Reassessment / clause helpers | Yes |
| `mnp-alignments.ttl` | dcterms/rdfs/skos alignment annotations | No (optional) |

Open `mnp-core.ttl` (and optionally `mnp-compliance.ttl`) in Protégé 5.6.x.
Do **not** treat alignments as imports required for reasoning.
