# Ontology Competency Questions (Stage 03)

These competency questions (CQs) validate the **formal ontology release 1.0.0**
after IRI migration and semantic ODRs. They are distinct from the legacy
business eligibility CQ registry under `competency_questions/` (CQ-01…CQ-15 for
case decisions). Both suites may coexist; this document owns the ontology-audit
CQ set required by Stage 03.

| Field | Value |
|---|---|
| Ontology version | 1.0.0 |
| Term NS | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| Root IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp` |
| Version IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/kg-mnp` |
| Status | Outline — SPARQL files and automated tests to be attached during implementation |
| Related ODRs | ODR-001 … ODR-006 |

Prefix used in sketches:

```sparql
PREFIX mnp:   <https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#>
PREFIX rdfs:  <http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl:   <http://www.w3.org/2002/07/owl#>
PREFIX skos:  <http://www.w3.org/2004/02/skos/core#>
PREFIX dcterms: <http://purl.org/dc/terms/>
```

---

## CQ-01 — Class definition, module, and superclass

**Question (en):** Given a class, find its definition, defining module, and
superclass(es).  
**Question (zh):** 给定类，查找定义、模块和上位类。

**Intent:** Single-defining-module and annotation completeness for TBox classes.

**Inputs:** Class IRI (e.g. `mnp:ServiceSubscription`).

**Expected evidence:** `skos:definition`@en/@zh-CN, module metadata /
`isDefinedBy` or inventory join, `rdfs:subClassOf` named parents.

**Acceptance:** Returns bilingual definitions; exactly one defining module in
inventory; superclasses listed without duplicate defining axioms in other
modules.

**SPARQL status:** _Stub — query file TBD_ (`queries/ontology/cq01_class_module.rq` planned).

---

## CQ-02 — Object property domain, range, and inverse

**Question (en):** Given an object property, find domain, range, and inverse.  
**Question (zh):** 给定对象属性，查找 Domain、Range 和 inverse。

**Intent:** Domain/range audit against ODRs; inverse consistency
(`hasCaseEvidence` ↔ `evidenceForCase`).

**Inputs:** Object property IRI (e.g. `mnp:billedThrough`).

**Expected evidence:** `rdfs:domain`, `rdfs:range`, `owl:inverseOf`,
deprecation/replacement if any.

**Acceptance:** Matches ODR-001…004 decisions for priority properties.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-03 — Subscriber → Subscription → PhoneNumber

**Question (en):** Given a Subscriber, trace ServiceSubscription and PhoneNumber.  
**Question (zh):** 给定 Subscriber，追溯 Subscription 和 PhoneNumber。

**Intent:** ODR-001 chain via `holdsSubscription` and inverse of
`assignedToSubscription` (or equivalent path).

**Inputs:** Subscriber instance IRI.

**Path sketch:**

```text
Subscriber --holdsSubscription--> ServiceSubscription
PhoneNumber --assignedToSubscription--> ServiceSubscription
```

**Acceptance:** Does not require deprecated `ownsPhoneNumber` / `hasSubscription`.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-04 — PhoneNumber → Subscription → Billing Account

**Question (en):** Given a PhoneNumber, trace ServiceSubscription and billing account.  
**Question (zh):** 给定 PhoneNumber，追溯 Subscription 和 Billing Account。

**Intent:** ODR-001 `assignedToSubscription` + `billedThrough` with domain
`ServiceSubscription`.

**Inputs:** PhoneNumber instance IRI.

**Acceptance:** Account reached through subscription; no subscriber-domain
`billedThrough`.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-05 — Assessment produces unique Decision

**Question (en):** Given an Assessment, find its Decision (expect uniqueness in
published eligibility graphs).  
**Question (zh):** 给定 Assessment，查找唯一 Decision。

**Intent:** ODR-002 `producesDecision`; eligibility profile cardinality.

**Inputs:** EligibilityAssessment IRI.

**Acceptance:** One `EligibilityDecision` in complete eligibility fixtures;
foundation graphs may be incomplete without failing foundation profile.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-06 — BlockingDecision → BlockingReason

**Question (en):** Given a BlockingDecision, find BlockingReason individuals.  
**Question (zh):** 给定 BlockingDecision，查找 BlockingReason。

**Intent:** ODR-002 `hasBlockingReason` (not deprecated `producesBlockingReason`).

**Inputs:** BlockingDecision IRI (or assessment that produces it).

**Acceptance:** Reasons attached to the decision; rule/evidence provenance
remain queryable from `BlockingReason`.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-07 — Distinguish hasCaseEvidence vs usesEvidence

**Question (en):** Distinguish case-available evidence from assessment-used evidence.  
**Question (zh):** 区分 hasCaseEvidence 与 usesEvidence。

**Intent:** ODR-003; inverse `evidenceForCase` may be used for navigation.

**Inputs:** MNPCase IRI and related EligibilityAssessment IRI.

**Acceptance:** Fixture with unused case evidence returns it under
`hasCaseEvidence` but not under that assessment’s `usesEvidence`.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-08 — Rule → RegulatoryClause

**Question (en):** Given a Rule, trace RegulatoryClause.  
**Question (zh):** 给定 Rule，追溯 RegulatoryClause。

**Intent:** Compliance linkage via `operationalizesClause` (and related cites
from blocking reasons where applicable).

**Inputs:** EligibilityRule IRI.

**Acceptance:** Clause and optional document path resolvable under formal IRIs.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-09 — Term modeling source and module

**Question (en):** Given a term, find modeling source metadata and defining module.  
**Question (zh):** 给定术语，查找建模来源和模块。

**Intent:** ODR-005 modeling-provenance TBox + inventory/module annotations;
not Stage 04 proposal ABox.

**Inputs:** Term IRI (class or property).

**Acceptance:** Defining module and source/source_status available from
ontology annotations and/or term inventory join; MappingRecord terms resolve
to modeling-provenance module.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-10 — Deprecated term and replacement

**Question (en):** Find deprecated terms and their replacements.  
**Question (zh):** 查找 deprecated term 与 replacement。

**Intent:** Release-policy deprecation markers for ODR-001/002/004 terms.

**Expected deprecated set (non-exhaustive):** `hasSubscription`,
`ownsPhoneNumber`, `relatedAccount`, `producesBlockingReason`,
`AssessmentDependency`, `dependsOn`, `dependsOnEvidence`,
`dependsOnRuleVersion`.

**Acceptance:** Each has `owl:deprecated true` and replacement or rationale
annotation; listed in `term-change-log.csv`.

**SPARQL status:** _Stub — query file TBD_.

---

## CQ-11 — Legacy eligibility case traceability

**Question (en):** Verify legacy eligibility case traceability still works under
formal IRIs and updated ODRs.  
**Question (zh):** 验证 legacy 资格案例追溯。

**Intent:** Protect nine-case demo: decision, reasons, evidence, rules remain
queryable via eligibility profile semantics.

**Inputs:** Case id (e.g. `CASE-03`).

**Acceptance:** `kg-mnp-eligibility evaluate/trace` and SPARQL traces succeed;
documented intentional deltas only where ODRs force graph shape changes.

**SPARQL status:** _Stub — may wrap existing eligibility CQ queries after IRI migration_.

---

## CQ-12 — Bilingual semantic completeness

**Question (en):** Check that all formal terms have English and Chinese labels
and definitions.  
**Question (zh):** 检查所有正式术语的中英文语义完整性。

**Intent:** Stage 03 annotation gate; feeds ontology-schema SHACL and inventory.

**Inputs:** None (whole TBox) or module filter.

**Acceptance:** Zero missing `rdfs:label`@en/@zh-CN and `skos:definition`@en/@zh-CN
for formal classes and properties in runtime modules; report lists gaps if any.

**SPARQL status:** _Stub — query file TBD_; also enforced by schema shapes /
`test_term_annotations.py`.

---

## Implementation backlog

| Item | Status |
|---|---|
| SPARQL query files under `queries/ontology/` or `competency_questions/ontology/` | Not created yet |
| `tests/ontology_release/test_competency_queries.py` | Not created yet |
| Fixtures illustrating ODR-001/003 distinctions | Not created yet |
| Cross-links from `ontology/README.md` | Pending Stage 03 README update |

## Out of scope for this CQ set

- Stage 04 missing/conflict instance queries over ModelingProposal data
- GraphDB-specific endpoints
- WebVOWL visualization checks
- Replacing the legacy business eligibility CQ-01…CQ-15 registry
