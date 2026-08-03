# Frontend Integration Contract

## Base URL

```text
http://127.0.0.1:8000/api/v1
```

## Schema version

- Assessment response `schema_version`: `1.0`
- API path version: `/api/v1`
- OpenAPI: `docs/api/openapi.json`

## Start backend

```bash
python -m pip install -e ".[api]"
kg-mnp-api
```

## Idempotency

Same `case_id` + `assessment_time` + `input_hash` with `persist=true` and `force_recompute=false` returns the original execution **without** creating a new artifact directory.

`force_recompute=true` replaces the idempotent DB row and, after the new record is saved successfully, deletes the previous artifact directory. Failed saves keep the old record and old artifacts; the new directory is cleaned up.

## Request size limit

Env: `KG_MNP_MAX_REQUEST_BYTES` (default 1048576). Oversize → HTTP 413 / `REQUEST_TOO_LARGE`.

## Dashboard stats

| Field | Meaning |
|-------|---------|
| `example_cases` | Fixed repo cases CASE-01..09 |
| `executions` | All SQLite assessment rows |
| `latest_case_states` | Per-case latest decision |

## CASE-06

| Assessment | Time | Version | Decision |
|------------|------|---------|----------|
| Historical | 2026-05-15 | MNP-ELIG-005 v1.0 | ELIGIBLE |
| Current | 2026-07-01 | MNP-ELIG-005 v1.1 | BLOCKED |

## Runnable examples

All nine cases are `runnable=true` with JSON under `inputs/case0N.json`.

## Rule update query

```text
GET /api/v1/rule-updates/affected-assessments?rule_id=MNP-ELIG-005&old_version=1.0&new_version=1.1
```

Queries SQLite history only (no hard-coded CASE-06 load).

## API contract

- Unknown response fields are rejected by core Pydantic models (`extra="forbid"` where frozen).
- Frontend clients should generate types from `docs/api/openapi.json`.
- Frozen JSON Schemas under `schemas/api/` mirror the same contracts.

## Frontend must NOT

- Submit arbitrary SPARQL / TTL
- Re-implement eligibility
- Invent graph edges
- Compute What-if diffs locally
- Treat demo clauses as formal law
