# Ontology modules (Stage 03 release 1.0.0)

Open **`ontology/kg-mnp.ttl`** in Protégé 5.6.x with **`catalog-v001.xml`** in the same folder (Protégé auto-loads the catalog for offline `owl:imports`).

| File | Runtime? | Role |
|------|----------|------|
| `kg-mnp.ttl` | entry | Root aggregate; imports runtime modules only |
| `mnp-core.ttl` | yes | Cross-module annotation / governance properties |
| `mnp-identity.ttl` | yes | Subscriber, phone assignment, identity |
| `mnp-account-billing.ttl` | yes | Accounts, bills, payments |
| `mnp-service-contract.ttl` | yes | Services, subscriptions, contracts, `billedThrough` |
| `mnp-process.ttl` | yes | MNP cases, process steps, auth codes |
| `mnp-compliance.ttl` | yes | Assessment, decision, rules, blocking reasons |
| `mnp-evidence-time.ttl` | yes | Business evidence and time |
| `mnp-modeling-provenance.ttl` | yes | Mapping / modeling provenance (not case evidence) |
| `mnp-code-list.ttl` | yes | Controlled code individuals |
| `mnp-alignments.ttl` | **optional** | External alignment annotations only |
| `catalog-v001.xml` | — | Offline IRI → local TTL map |

## Formal IRIs

- Term namespace: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#`
- Root ontology: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp`
- Version IRI: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/kg-mnp`
- Ontology release version: **1.0.0** (Python package version remains independent)

## Alignments optional

`mnp-alignments.ttl` is excluded from the root imports and from default `loader` runtime load. Use `include_alignments=True` only for documentation review. No `owl:equivalentClass` / `owl:equivalentProperty` to third-party ontologies.

## Loader

`config/ontology_modules.yaml` is the sole module catalog. `loader.py` reads it; do not hardcode a second list.

## Audit / reasoner

```bash
python scripts/audit_ontology.py
python scripts/check_catalog.py
python scripts/check_ontology_release.py
python scripts/run_reasoner.py   # ROBOT + HermiT (Java required)
```
