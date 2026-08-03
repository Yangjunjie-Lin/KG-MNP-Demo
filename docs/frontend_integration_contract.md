# Frontend Integration Contract

## Base URL

```text
http://127.0.0.1:8000/api/v1
```

## Start backend

```bash
python -m pip install -e ".[api]"
kg-mnp-api
```

## OpenAPI / JSON Schema

- Live: `/openapi.json`
- Exported: `docs/api/openapi.json` via `python scripts/export_openapi.py`
- Frozen response schemas: `schemas/api/`

## Core flows

1. `POST /assessments` with case JSON → assessment response
2. `GET /assessments/{execution_id}` → reopen history
3. `GET /views/assessments/{execution_id}` → page-ready view model
4. `GET /ontology/modules` + `GET /views/ontology` → ontology UI
5. `POST /competency-questions/{cq_id}/execute` → controlled CQ only
6. `POST /views/what-if` → backend computes diffs

## Enums

- `decision`: `ELIGIBLE` | `BLOCKED` | `CONDITIONAL` | `MANUAL_REVIEW`
- `publication.status`: `PUBLISHABLE` | `NOT_PUBLISHABLE`
- `authCodeStatus`: `VALID` | `EXPIRED` | `MISSING` | `USED` | `REVOKED`
- process step codes: `ELIGIBILITY_CHECK` | `AUTHORIZATION_CODE_REQUEST` | `PORT_IN_SUBMISSION` | ...

## Error shape

```json
{
  "error": {
    "code": "INPUT_SCHEMA_ERROR",
    "message": "...",
    "details": [],
    "retryable": false
  }
}
```

## Frontend must NOT

- Submit arbitrary SPARQL
- Upload arbitrary TTL
- Re-implement eligibility rules
- Invent graph edges
- Treat demo regulatory clauses as formal law
- Rely on Neo4j
- Call an LLM to decide eligibility or explain diffs

## Fields computed only by backend

- `decision`, `blocking_reasons`, `rule_results`
- `process.can_advance` and process blocking reasons
- What-if diffs (`decision_change`, `reason_changes`)
- Trace subgraph edges
- Ontology key paths (`exists_in_rdf`)
