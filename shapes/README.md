# SHACL shape profiles

Stage 03 separates SHACL into three profiles (ODR-006). Named shapes use the
formal shape namespace `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#`
and term prefix `mnp:` → `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#`.

| Profile | Loader key | File | Purpose |
|---------|------------|------|---------|
| Ontology schema | `ontology_schema` | [`ontology-schema-shapes.ttl`](ontology-schema-shapes.ttl) | TBox quality: bilingual `rdfs:label` / `skos:definition` on formal classes and properties; `owl:versionIRI` on ontology resources |
| Foundation instance | `foundation` | [`foundation-instance-shapes.ttl`](foundation-instance-shapes.ttl) | Stable ABox hygiene for partial graphs (identifier/datatype checks; soft typing when values are present; mapping-record modeling fields). Does **not** require case evidence or assessment `usesEvidence` |
| Eligibility instance | `eligibility` | [`../examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl`](../examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl) | Legacy eligibility use-case strictness (case completeness, assessment evidence/rules/decision, blocking provenance via `hasBlockingReason`) |

## Usage

```text
validate_graph(graph, profile="foundation")
validate_graph(graph, profile="eligibility")   # loads foundation + eligibility
validate_ontology_schema(graph)                # ontology_schema profile
```

`eligibility` composes foundation shapes plus the eligibility file. Foundation
never auto-loads eligibility shapes.

## Retired monolith

`shapes/mnp-shapes.ttl` has been removed. Its constraints were split into the
three profiles above. Do not reintroduce a mixed authority shapes file.
