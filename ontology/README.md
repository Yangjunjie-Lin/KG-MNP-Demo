# Ontology files

| File | Role | Runtime? | Module |
|------|------|----------|--------|
| `mnp-core.ttl` | Domain classes, properties, OWL cardinality | Yes | CORE |
| `mnp-compliance.ttl` | Reassessment / clause helpers | Yes | COMPLIANCE |
| `mnp-identity.ttl` | Natural person, documents, verification | Yes | IDENTITY |
| `mnp-account-billing.ttl` | Billing account, bills, outstanding balance | Yes | ACCOUNT_BILLING |
| `mnp-service-contract.ttl` | Plans, commitment, termination | Yes | SERVICE_CONTRACT |
| `mnp-process.ttl` | Process steps, authorization code | Yes | PROCESS |
| `mnp-evidence-time.ttl` | Evidence validity & time annotations | Yes | EVIDENCE_TIME |
| `mnp-code-list.ttl` | Controlled status codes | Yes | CODE_LIST |
| `mnp-alignments.ttl` | dcterms/rdfs/skos alignment annotations | No (optional) | ALIGNMENTS |

All runtime modules are loaded explicitly by `loader.ontology_paths()` (offline; no remote `owl:imports` resolution).

Module catalog authority: `config/ontology_modules.yaml`.

Open `mnp-core.ttl` plus any module file in Protégé 5.6.x.
Do **not** treat alignments as imports required for reasoning.
