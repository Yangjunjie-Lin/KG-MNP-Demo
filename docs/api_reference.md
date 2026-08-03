# API Reference (v1)

All routes are under `/api/v1`.

## System

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Liveness |
| GET | /ready | Readiness (SQLite; Neo4j not required) |
| GET | /meta | Service metadata |

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

## Cases / Ontology / CQ / Rules / Examples / Views

See OpenAPI at `/docs` or `docs/api/openapi.json`.

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
