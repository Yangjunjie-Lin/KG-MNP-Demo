# Stage 03 — Ontology Release Baseline

## Status

Stage 03 core release **1.0.0** with formal IRIs, module ownership, SHACL
profiles, and OWL 2 DL reasoner report.

## Formal IRIs

| Kind | Value |
|---|---|
| Ontology version | `1.0.0` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| Shape namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#` |
| Instance base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/data/` |
| Root ontology | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp` |
| Root version IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/kg-mnp` |

Python package version remains `0.1.0` and is independent of the ontology
release version.

## Artifacts

- `docs/ontology/ontology-audit-report.md`
- `docs/ontology/term-inventory.csv`
- `docs/ontology/term-change-log.csv`
- `docs/ontology/iri-migration.csv`
- `docs/ontology/reasoner-report.md`
- `docs/ontology/decisions/ODR-001` … `ODR-006`
- `ontology/kg-mnp.ttl` + `catalog-v001.xml`
- `ontology/mnp-modeling-provenance.ttl`
- SHACL profiles under `shapes/` and `examples/eligibility-use-case/shapes/`

## Gates

```bash
make verify-stage-03-core
make reasoner-check
make verify-reasoner-report
make verify-stage-03
```

## Out of scope (Stage 04+)

Proposal pipeline schemas, GraphDB, WebVOWL, new HTTP API / frontend.
