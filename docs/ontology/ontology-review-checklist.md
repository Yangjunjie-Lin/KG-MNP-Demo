# Ontology Review Checklist

Stage 03 formal OWL/SHACL semantic audit checklist for KG-MNP ontology release
**1.0.0**. Use this list while producing `ontology-audit-report.md`, ODRs, and
gate evidence. Mark each item `PASS` / `FAIL` / `DEFERRED` with notes.

Ontology version under review: `1.0.0`  
Root ontology IRI: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp`  
Root version IRI: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/kg-mnp`  
Term namespace: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#`  
Shape namespace: `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#`

---

## 1. Governance inputs consumed

- [ ] `config/namespaces.yaml` read and applied
- [ ] `config/modeling-statuses.yaml` respected (no conflating review vs publication)
- [ ] `config/ontology-release-policy.yaml` applied to change classification
- [ ] ADR-001 semantic authority chain unchanged
- [ ] TBox/ABox, OWL/SHACL, evidence-layer, and explicit/inferred docs respected
- [ ] Stage 01 and Stage 02 gates still PASS before ontology edits land

## 2. Module structure and imports

- [ ] Root `ontology/kg-mnp.ttl` exists and only aggregates metadata + imports
- [ ] Runtime modules listed in `config/ontology_modules.yaml` (no hardcoded second list in loader)
- [ ] `mnp-modeling-provenance.ttl` present (ODR-005)
- [ ] `mnp-alignments.ttl` optional; not forced into default runtime without audit
- [ ] `catalog-v001.xml` maps versionless and version IRIs to local files
- [ ] No cyclic imports; no domain module imports the root
- [ ] Each formal module has bilingual title/description, license, `owl:versionIRI`, `owl:versionInfo "1.0.0"`

## 3. IRI migration

- [ ] Formal term IRIs use GitHub Pages term namespace
- [ ] `docs/ontology/iri-migration.csv` complete for migrated resources
- [ ] No uncontrolled global string replace of third-party or historical URLs
- [ ] Formal runtime assets free of `http://example.org/kg-mnp`
- [ ] Allowlisted historical exceptions documented (migration docs, snapshots, fixtures)
- [ ] Data, queries, mappings, rules, Python namespaces, schemas, and tests migrated together

## 4. Term ownership and inventory

- [ ] `term-inventory.csv` covers classes, object/datatype/annotation properties, code-list individuals, named shapes, ontology resources
- [ ] Every term has exactly one defining module
- [ ] `audit_decision` ∈ {ACCEPT, MODIFY, MOVE_MODULE, DEPRECATE, REMOVE_DUPLICATE}
- [ ] Priority terms audited (Subscriber, PhoneNumber, TelecomAccount, TelecomService, ServiceSubscription, ServiceContract, MNPCase, EligibilityAssessment, EligibilityDecision, BlockingReason, EvidenceRecord, AssessmentDependency, MappingRecord, and listed properties)
- [ ] Inventory generation is deterministic (byte-identical on re-run)

## 5. Core semantic ODRs

- [ ] ODR-001 number–subscription–account accepted and implemented
- [ ] ODR-002 assessment–decision–blocking accepted and implemented
- [ ] ODR-003 evidence availability vs use accepted and implemented
- [ ] ODR-004 AssessmentDependency deprecation accepted and implemented
- [ ] ODR-005 modeling-provenance module accepted and implemented (TBox only)
- [ ] ODR-006 SHACL profile separation accepted and implemented
- [ ] Deprecated terms have `owl:deprecated`, change log, replacement/rationale, retention note

## 6. OWL modeling quality

- [ ] Domain/Range treated as inference axioms, not database type errors
- [ ] No accidental multi-domain intersection unless intended
- [ ] Cardinality used only for true ontological necessities; partial-data rules in SHACL
- [ ] Decision subclass disjointness reviewed and retained where valid
- [ ] No unjustified `owl:equivalentClass` / `owl:equivalentProperty` in alignments
- [ ] No remote import of license-incompatible ontologies into runtime
- [ ] Class vs individual boundaries correct for code lists

## 7. Bilingual annotations and provenance

- [ ] Every formal class and property has `rdfs:label`@en and @zh-CN
- [ ] Every formal class and property has `skos:definition`@en and @zh-CN
- [ ] Labels are not machine identifiers; definitions are not label copies
- [ ] Local extensions carry source status (e.g. LOCAL_EXTENSION, INDUSTRY_ALIGNED, STANDARD_REUSED, PROJECT_GOVERNANCE)
- [ ] ModelingEvidence ≠ EvidenceRecord; ReviewDecision ≠ EligibilityDecision

## 8. SHACL profiles

- [ ] `shapes/ontology-schema-shapes.ttl` exists
- [ ] `shapes/foundation-instance-shapes.ttl` exists
- [ ] `examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl` exists
- [ ] Foundation does not require full eligibility evidence packages
- [ ] Eligibility retains strict legacy demo constraints
- [ ] Validator exposes explicit profiles; eligibility tests select eligibility
- [ ] Named shapes have bilingual labels/messages and severity
- [ ] SPARQL constraints use formal namespaces

## 9. Logic and reasoner

- [ ] RDFLib parse of all formal modules succeeds
- [ ] OWL-RL smoke inference passes
- [ ] Full OWL 2 DL reasoner executed (HermiT/ROBOT or documented equivalent)
- [ ] `docs/ontology/reasoner-report.md` records version, command, hash, consistency, unsatisfiables
- [ ] No forged PASS if reasoner not run (use CONDITIONAL)

## 10. Legacy eligibility protection

- [ ] Nine case graphs migrate without silent semantic drift
- [ ] `kg-mnp-eligibility` CLI remains the eligibility entry
- [ ] Result changes only where ODRs require them, and are documented per case
- [ ] Historical `demo_outputs/` not used as runtime authority

## 11. Competency questions and tests

- [ ] `docs/ontology/competency-questions.md` CQ-01…CQ-12 present
- [ ] Core CQ SPARQL + tests in place
- [ ] `tests/ontology_release/` covers modules, catalog, inventory, annotations, deprecations, profiles, determinism
- [ ] Stage gates: `verify-ontology-audit`, `verify-ontology-release`, `verify-shacl-profiles`, `verify-legacy-eligibility`, `verify-stage-03-core`, `reasoner-check`, `verify-stage-03`

## 12. Stage boundary (must remain false)

- [ ] No Stage 04 cleaned/proposal/review/confirmed JSON Schemas implemented as live pipeline
- [ ] No Modeling Proposal / Confirm / RDF compiler productization
- [ ] No GraphDB repository integration
- [ ] No WebVOWL / OWL2VOWL productization
- [ ] No new frontend / HTTP API for modeling
- [ ] No commit/push performed as part of audit-only documentation drops unless explicitly requested

---

## Sign-off stub

| Role | Name | Date | Result |
|---|---|---|---|
| Ontology auditor | _TBD_ | _TBD_ | _TBD_ |
| Stage 03 owner | _TBD_ | _TBD_ | PASS / CONDITIONAL / FAIL |

Related decisions: [ODR-001](decisions/ODR-001-number-subscription-account-model.md) …
[ODR-006](decisions/ODR-006-shacl-profile-separation.md).  
Migration report outline: [stage-03-ontology-release.md](../migration/stage-03-ontology-release.md).
