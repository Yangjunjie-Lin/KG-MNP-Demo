# Stage 05 Migration — Human Review and Confirmed Modeling Package

## What Stage 05 adds

- Frozen `review-policy-1.0.0.yaml`
- Review Action / Review Policy / Review Common contracts
- Deterministic review identifiers and hashes
- File-based `kg-mnp review *` workflow
- Deterministic `ConfirmedModelingPackage` builder
- Package readiness (`READY_FOR_COMPILATION` / `BLOCKED`)

## Contract versioning

Stage 04 contracts retained at `$id` version `1.0`:

- `review-decision-log/1.0`
- `confirmed-modeling-package/1.0`
- `common/1.0`

No MDR-001 schema bump was required. Cross-object rules that JSON Schema cannot
express are enforced by Stage 05 semantic validators.

New contracts:

- `review-common/1.0`
- `review-action/1.0`
- `review-policy/1.0`

## Compatibility notes

- Draft ReviewDecisionLogs may remain incomplete
- Final logs require exact-once coverage and self-validating IDs/hashes
- Confirmed packages require final logs
- `confirmed_schema_delta` remains empty for dataset modeling
- Reviewer identity remains declarative attribution, not authentication

## Still out of scope

OWL/SHACL/RDF compilers, GraphDB, WebVOWL, frontend review UI, HTTP API,
databases, LLM reviewers, and cryptographic reviewer authentication.
