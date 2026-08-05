# Legacy Eligibility Use Case

The mobile-number-portability eligibility implementation is retained as a
downstream example of the existing ontology assets. It is not the repository's
central modeling pipeline and is excluded from the default Stage 01 gate.

## Eligibility SHACL profile

Strict eligibility constraints live under:

- [`shapes/eligibility-instance-shapes.ttl`](shapes/eligibility-instance-shapes.ttl)

Loader profile key: `eligibility` (composes
`shapes/foundation-instance-shapes.ttl` plus this file). See
[`shapes/README.md`](../../shapes/README.md) for the full profile table
(`foundation`, `eligibility`, `ontology_schema`).

## Legacy eligibility JSON Schema

The legacy input contract now lives at:

- [`schemas/mnp_case_input.schema.json`](schemas/mnp_case_input.schema.json)

Its stable, versioned identifier is
`https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/eligibility/mnp-case-input/1.0`.
The schema remains a Draft 2020-12 contract for the eligibility example. It is
not the future central `CleanedPartialData` contract and must not be reused as
the Modeling Pipeline's input schema.

The repository-level `schemas/` path is reserved for Stage 04 Modeling
Contracts. No Stage 04 schema is created by this migration. The Schema
Identifier gate validates local schema files and namespace membership entirely
offline; it does not resolve `$id` or download a remote schema.

The other example assets currently remain in their original repository
locations to avoid breaking the established RDF, SHACL, OWL-RL, SPARQL, and
rule tests. This is the explicit Stage 01 exception to a physical directory
move:

- `inputs/`, `data/`, and `rules/eligibility_rules.yaml`
- `competency_questions/` and `queries/*.rq`
- `src/kg_mnp_demo/evaluator.py`, `rule_engine.py`, `trace.py`, and
  `trace_graph.py`
- `src/kg_mnp_demo/pipeline.py` and the supporting `application/` services
- `demo_outputs/` as versioned research snapshots

These paths may move in a later, separately reviewed migration. The retained
CLI is RDF-only; the old frontend, HTTP API, SQLite execution history, and
Neo4j backend have been removed.

To exercise the legacy eligibility example explicitly:

```bash
kg-mnp-eligibility evaluate --case CASE-03 --backend rdf
kg-mnp-eligibility trace --case CASE-03 --backend rdf
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python -m kg_mnp_demo.pipeline --input inputs/case03.json --output-dir runtime_outputs/case03
```

The installed console script is `kg-mnp-eligibility`. The name `kg-mnp` is
reserved for the future ontology modeling CLI and must not run eligibility
evaluation. `python -m kg_mnp_demo.cli` remains an internal compatibility entry
and is not the repository's central command.

Generated output belongs under `runtime_outputs/` and is not versioned.
