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

- Draft ReviewDecisionLogs may remain incomplete, but draft integrity still
  enforces schema, proposal binding, reviewer consistency, policy-legal existing
  decisions, modified-candidate validity, decision IDs, and log hash
- `review finalize` runs full semantic validation before returning a final log
- Confirmed packages require final logs
- Package Validator independently re-derives the expected package and requires
  deterministic equality; self-hash alone is not trust
- All frozen dependencies (ontology baseline, mapping rules, terminology
  profile, proposal policy, review policy, generator version) must match the
  proposal snapshot; policy load failures fail closed
- `confirmed_schema_delta` remains empty for dataset modeling
- Reviewer identity remains declarative attribution, not authentication

## Still out of scope

OWL/SHACL/RDF compilers, GraphDB, WebVOWL, frontend review UI, HTTP API,
databases, LLM reviewers, and cryptographic reviewer authentication.
