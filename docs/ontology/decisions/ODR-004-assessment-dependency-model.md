# ODR-004 — Assessment Dependency Model

| Field | Value |
|---|---|
| ODR ID | ODR-004 |
| Title | Deprecate AssessmentDependency indirection |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related modules | `mnp-compliance`, `mnp-evidence-time` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |

## Context

The pre-1.0.0 core module defines both direct assessment links
(`usesEvidence`, `usesRuleVersion`) and an indirection class
`AssessmentDependency` reached via `dependsOn`, with further properties
`dependsOnEvidence` and `dependsOnRuleVersion`. Eligibility SHACL currently
requires at least one `dependsOn` link. Stage 03 must decide whether the
indirection carries independent metadata or is redundant.

## Current model

```text
EligibilityAssessment
    usesEvidence     → EvidenceRecord
    usesRuleVersion  → RuleVersion
    dependsOn        → AssessmentDependency

AssessmentDependency
    dependsOnEvidence    → EvidenceRecord
    dependsOnRuleVersion → RuleVersion
```

In practice, case graphs and the evaluator largely mirror the same evidence and
rule version facts through both paths. `AssessmentDependency` has no dedicated
datatype properties for dependency type, validity window, provenance, or
status beyond those links.

## Problem

1. Two equivalent ways to state “this assessment used evidence E / rule version
   R” without a declared semantic difference.
2. SHACL `minCount 1` on `dependsOn` forces reified nodes even when direct
   properties already satisfy the competency need.
3. Maintaining both paths increases migration and inverse-consistency cost.
4. Stage 03 forbids retaining two equivalent relation sets without distinction.

## Candidate alternatives

### A — Keep AssessmentDependency as first-class

Retain the class and require it; optionally deprecate direct `uses*` properties.

### B — Enrich AssessmentDependency with metadata

Keep the class only if new properties are added (dependency type, version,
validity, provenance, status, evaluation time).

### C — Deprecate indirection; keep direct uses* (selected)

Deprecate `AssessmentDependency`, `dependsOn`, `dependsOnEvidence`, and
`dependsOnRuleVersion`. Keep `usesEvidence` and `usesRuleVersion`.

### D — Property-chain sugar only

Declare `dependsOnEvidence` as a property chain of `dependsOn` ∘ … while still
asserting dependency nodes.

## Selected model

**Alternative C.**

| Term | Decision |
|---|---|
| `usesEvidence` | **ACCEPT** (see ODR-003) |
| `usesRuleVersion` | **ACCEPT** |
| `AssessmentDependency` | **DEPRECATE** |
| `dependsOn` | **DEPRECATE** |
| `dependsOnEvidence` | **DEPRECATE** |
| `dependsOnRuleVersion` | **DEPRECATE** |

Rationale: the class does not currently carry independent metadata. Direct
properties already answer CQ needs for “which evidence / rule version did this
assessment use?” If Stage 04+ needs typed dependency provenance, a new
confirmed Schema Delta may reintroduce a richer dependency class—not revive
the empty wrapper silently.

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Keep as mandatory | Continues dual modeling; SHACL noise for no gain. |
| B — Enrich now | Speculative attributes not required for 1.0.0 release; violates “don’t invent unused TBox”. |
| D — Chain sugar | Still forces reified nodes; complexity without new facts. |

## OWL consequences

- Mark the four deprecated terms with `owl:deprecated true`, change notes, and
  replacement pointers to `usesEvidence` / `usesRuleVersion`.
- Remove OWL cardinality/restrictions that require `dependsOn` on assessments
  (if present in core restrictions).
- Do not delete deprecated IRIs in 1.0.0; retain for one migration cycle.
- Align `affectsAssessment` / rule-update traces with direct assessment links.

## SHACL consequences

- Remove eligibility `minCount` on `dependsOn`.
- Eligibility profile should require `usesEvidence` and rule linkage
  (`evaluatedByRule` / `usesRuleVersion`) as appropriate to the use case.
- Foundation profile must not require assessment dependency nodes.

## Data migration impact

| Asset | Impact |
|---|---|
| Case TTL | Drop `AssessmentDependency` individuals and `dependsOn*` triples; ensure `usesEvidence` / `usesRuleVersion` remain |
| Evaluator / RDF builder | Stop creating dependency blank nodes / IRIs |
| SHACL | Remove dependsOn constraint |
| Queries | Prefer direct uses* paths |
| Alignments | Update `AssessmentDependency` alignment status to deprecated/local historical |

## Compatibility impact

| Change | Compatibility class |
|---|---|
| Deprecation of dependency vocabulary | Major for any consumer that only read `dependsOn` |
| Retention of `uses*` | Compatible with existing direct edges |
| SHACL no longer requires dependency nodes | Relaxation for eligibility graphs that already have uses* |

## Evidence / source

- Stage 03 brief §16
- Property and class declarations in `ontology/mnp-core.ttl`
- `mnp:EligibilityAssessmentShape` dependsOn constraint in `shapes/mnp-shapes.ttl`
- Alignment annotation `mnp:AssessmentDependency mnp:alignmentStatus "LOCAL_ONLY"`

## Tests

- Deprecated-term suite covers all four dependency terms
- Eligibility fixtures pass without `AssessmentDependency` nodes
- Eligibility fixtures fail when `usesEvidence` is missing (profile-specific)
- CQ-05 / rule-version queries use `usesRuleVersion` only
- No test reintroduces dual assertion as a requirement
