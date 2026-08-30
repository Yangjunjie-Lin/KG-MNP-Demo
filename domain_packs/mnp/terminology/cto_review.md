# CTO review notes

**Repository:** https://github.com/Point-Topic/cto-ontology  
**License:** GPL-3.0  
**Reviewed on:** 2026-07-30  
**Files reviewed (remote, not copied):**
- `README.md`
- `resource/cto_core.ttl`
- `resource/cto_extended.ttl`

## Concepts inspected

| CTO term | Relevance to MNP | Decision |
|----------|------------------|----------|
| `foaf:Person` / `foaf:Organization` | Party layer vs Subscriber | PARTIAL / related — not equivalent |
| `cto:Service`, `cto:CellularService` | Service catalog vs TelecomService | `skos:closeMatch` to Service only |
| `cto:MeasurementRecord` | Observation with magnitude | PARTIAL note only — different purpose from EvidenceRecord |
| `cto:WholesaleAccessPlatform` / `dcat:DataService` | Information channels | PARTIAL vs InformationSystem |
| `cto:validFrom` / `cto:validTo` | Temporal validity inspiration | LOCAL properties kept (`evidenceValidUntil`, rule effective windows) |
| PhoneNumber / MNPCase / Eligibility* | Not present | LOCAL_ONLY |

## Differences

- CTO focuses on broadband market/network topology and organization relationships.
- KG-MNP focuses on portability eligibility, evidence provenance, rule versions, regulatory clauses, and remediation actions.
- Because CTO is GPL-3.0, this project **does not copy** OWL class axioms into the repo.

## Alignment policy used

- `dcterms:source`, `rdfs:seeAlso`, optional `skos:closeMatch`
- **No** `owl:equivalentClass` for unverified CTO terms
- Runtime loaders do not require `mnp-alignments.ttl`
