# Backend Quickstart

## Install

```bash
python -m pip install -e ".[dev,api]"
```

## CLI (no API deps required)

```bash
python -m kg_mnp_demo.pipeline --input inputs/case03.json --output-dir runtime_outputs/case03
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python scripts/showcase_demo.py --case CASE-03
```

## API

```bash
kg-mnp-api
# or
uvicorn kg_mnp_demo.api.app:app --reload
```

- Health: http://127.0.0.1:8000/api/v1/health
- Docs: http://127.0.0.1:8000/docs
- OpenAPI: http://127.0.0.1:8000/openapi.json (also exported to `docs/api/openapi.json`)

### Environment

| Variable | Default | Purpose |
|----------|---------|---------|
| `KG_MNP_MAX_REQUEST_BYTES` | `1048576` | Request body size limit |
| `KG_MNP_CORS_ORIGINS` | (local defaults) | Allowed browser origins |

### Idempotency

`POST /assessments` with `persist=true` and `force_recompute=false` reuses an existing row for the same `case_id` + `assessment_time` + `input_hash` and does not create orphan artifact directories.

### Examples

All nine cases are runnable via `GET/POST /api/v1/examples/...` using JSON under `inputs/`.

### Dashboard

`GET /api/v1/views/dashboard` returns split counters (`example_cases`, `executions`, `latest_case_states`) and live SHACL `shape_count` from `shapes/mnp-shapes.ttl`.

## Seed demo data

```bash
python scripts/seed_demo_data.py
```

Does **not** run on import. Writes to `runtime_data/kg_mnp.sqlite3` (includes CASE-06 historical rule-version rows for rule-update queries).

## Docker

```bash
docker compose -f docker-compose.api.yml up --build
```

Neo4j is optional (`--profile neo4j`) and not part of health checks. Persist SQLite via the compose volume so history survives restarts.

## Architecture invariants

- Eligibility is decided only by the deterministic rule engine
- OWL is the semantic authority; SHACL validates input and assessment graphs
- SPARQL traces real RDF edges only
- SQLite stores execution metadata/artifacts index, not ontology
- `real_world_execution_allowed=false`
