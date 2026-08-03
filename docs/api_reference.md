# API Reference (v1)

All routes are under `/api/v1`.

**OpenAPI (typed):** `docs/api/openapi.json` — regenerate with `python scripts/export_openapi.py`.

**API schema version:** response `schema_version` `1.0`, path `/api/v1`.

## System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness |
| GET | /ready | Readiness (SQLite; Neo4j not required) |
| GET | /meta | Service metadata (CORS / max body env hints) |

## Assessments

| Method | Path |
|--------|------|
| POST | /assessments |
| GET | /assessments |
| GET | /assessments/{execution_id} |
| GET | /assessments/{execution_id}/trace |
| GET | /assessments/{execution_id}/artifacts |
| POST | /assessments/{execution_id}/what-if |
| GET | /assessments/compare?left=&right= |

Request body for create: `{ "payload": <MNPCaseInput>, "persist": bool, "force_recompute": bool }`.

Idempotency: same `case_id` + `assessment_time` + `input_hash` with `persist=true` and `force_recompute=false` returns the existing execution without a new artifact directory. `force_recompute=true` replaces the row and removes the previous artifact directory after a successful save.

Body size: env `KG_MNP_MAX_REQUEST_BYTES` (default 1 MiB) → HTTP 413 / `REQUEST_TOO_LARGE`.

Unknown core response fields are rejected (`extra="forbid"`). Prefer OpenAPI for TypeScript clients.

## Cases / Ontology / CQ / Rules / Examples / Views

See OpenAPI at `/docs` or `docs/api/openapi.json`.

Rule update impact (SQLite history only):

```text
GET /api/v1/rule-updates/affected-assessments?rule_id=MNP-ELIG-005&old_version=1.0&new_version=1.1
```

Examples: `GET /examples` lists nine `runnable=true` JSON cases (`inputs/case01.json` … `case09.json`).

Dashboard stats: `example_cases` (repo), `executions` (SQLite rows), `latest_case_states` (per-case latest) — do not mix.

### curl examples

```bash
curl -s http://127.0.0.1:8000/api/v1/health

curl -s -X POST http://127.0.0.1:8000/api/v1/assessments \
  -H "Content-Type: application/json" \
  -d "{\"payload\": $(cat inputs/case03.json), \"persist\": true}"

curl -s http://127.0.0.1:8000/api/v1/ontology/summary

curl -s -X POST http://127.0.0.1:8000/api/v1/competency-questions/CQ-01/execute \
  -H "Content-Type: application/json" \
  -d "{\"case_id\":\"CASE-01\"}"
```
