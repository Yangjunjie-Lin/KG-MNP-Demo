# Prompt 2 Compatibility Matrix

| Surface | Entry implementation | Prompt 2 authority | Compatibility decision |
|---|---|---|---|
| Modeling contract metadata | `kg_mnp.modeling.contracts` | `kg_mnp.contracts.catalog` | Modeling module becomes a filtered thin wrapper; no second catalog. |
| Modeling registry | Source-tree `schemas/modeling` | Packaged offline registry | Existing function signatures and custom test-directory loading remain available. |
| Canonical JSON | `kg_mnp.modeling.canonical_json` | `kg_mnp.contracts.canonical` | Exact algorithm/profile retained through re-export. |
| Modeling Schema `$id` | Eleven stable 1.0 identifiers | Same identifiers | Bytes and accept/reject behavior remain unchanged. |
| Activation schemas | Internal Stage/Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Amendment schemas | Internal Stage/Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Application schemas | Internal Stage/Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Compilation schemas | Internal Stage registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Diagnostics schemas | Internal Stage/Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Governance schemas | Internal Stage/Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| GraphDB schemas | Internal Stage registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Publication schemas | Internal Stage registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| WebVOWL schemas | Internal Stage registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| Workbench schemas | Internal Phase registry | Unchanged | INTERNAL_CONTRACT_MIGRATION_DEFERRED. |
| MNP case-input schema | MNP eligibility fixture | Domain Pack asset | DOMAIN_SPECIFIC; retained and locked in place. |
| Root CLI | Legacy Modeling default plus application routes | Adds Contracts, Domain Pack and Workspace routes | Legacy argv is forwarded unchanged. |
| MNP loader paths | Repository-local compatibility layer | Local Domain Pack Registry for new APIs | Retained loader remains functional; no generic kernel dependency on repository root. |
| Project workspace | Provisional `KG_MNP_WORKSPACE` helper | Project Workspace v1 | New authority is explicit and fail-closed; old helper remains for legacy code. |

Prompt 2 does not reinterpret a Modeling Proposal, Review Decision Log, or
Confirmed Modeling Package. In particular, a Domain Pack, Artifact Reference,
Artifact Manifest, Project Workspace or lock is never evidence of human review
and never upgrades proposal content to confirmed authority.

## Verified result

The full retained suite, Stage 06 gate, and Application Phase 06 offline gate
pass with the compatibility layers. ModelingProposal, ReviewDecisionLog,
ConfirmedModelingPackage, compiler, publication, activation/rollback, and
legacy CLI routes retain their behavior. The only intentional root routing
change is that `contracts`, `domain-pack`, and `workspace` are now public
first-token authorities; every other legacy argument vector is forwarded
unchanged to its previous implementation.
