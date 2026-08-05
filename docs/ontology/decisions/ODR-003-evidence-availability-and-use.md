# ODR-003 — Evidence Availability and Use

| Field | Value |
|---|---|
| ODR ID | ODR-003 |
| Title | Separate case evidence availability from assessment evidence use |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related modules | `mnp-process`, `mnp-compliance`, `mnp-evidence-time` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |

## Context

MNP cases accumulate business-fact evidence over time. An eligibility
assessment uses a snapshot of that evidence (and may omit available items or,
in incomplete graphs, reference items not yet linked). Stage 02 already
separates modeling evidence from business-fact evidence; Stage 03 must keep
**availability on the case** distinct from **use by an assessment**.

## Current model

```text
MNPCase
    hasCaseEvidence → EvidenceRecord

EvidenceRecord
    evidenceForCase → MNPCase          (owl:inverseOf hasCaseEvidence)

EligibilityAssessment
    usesEvidence → EvidenceRecord
    aboutCase    → MNPCase
```

Comments in `mnp-core.ttl` already state that `usesEvidence` is distinct from
`hasCaseEvidence`. Eligibility SHACL includes a SPARQL constraint requiring
every `usesEvidence` target to also appear under the case’s
`hasCaseEvidence`.

## Problem

1. Merging the two properties would erase the difference between “on file for
   the case” and “actually used in this assessment run”.
2. Dropping `evidenceForCase` would remove a convenient inverse for SPARQL and
   Protégé navigation; keeping it without audit risks wrong domain/range or
   unwanted type inference.
3. Treating the eligibility SPARQL constraint as a universal foundation rule
   would reject legitimate partial graphs where assessment drafts exist before
   case evidence linkage is complete.

## Candidate alternatives

### A — Merge into a single `involvesEvidence`

One property for both case and assessment, distinguished only by subject type.

### B — Keep separate properties + keep inverse (selected)

Retain `hasCaseEvidence`, `usesEvidence`, and `evidenceForCase` as inverse of
`hasCaseEvidence`, with audited domain/range.

### C — Keep separate properties; drop inverse

Delete `evidenceForCase` and rely on property paths / SPARQL inverses only.

### D — Make `usesEvidence` a subproperty of `hasCaseEvidence`

Force every used evidence item to entail case availability via OWL.

## Selected model

**Alternative B.**

| Term | Decision |
|---|---|
| `hasCaseEvidence` | **ACCEPT** — case-available / attached evidence |
| `usesEvidence` | **ACCEPT** — assessment-used evidence snapshot |
| `evidenceForCase` | **ACCEPT** — inverse of `hasCaseEvidence` |
| Merge / subproperty entailment | **REJECT** |

Semantics:

```text
hasCaseEvidence:
  Evidence currently available or attached to the MNP case.

usesEvidence:
  Evidence snapshot actually used by a specific EligibilityAssessment.

evidenceForCase:
  Inverse navigation EvidenceRecord → MNPCase; no extra semantics.
```

Governance note: these properties apply to **business-fact** `EvidenceRecord`
instances, not to modeling-provenance evidence (`ModelingEvidence` per
ODR-005).

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Merge | Collapses availability vs use; breaks reassessment and audit trails. |
| C — Drop inverse | Loses useful navigation; inverse is cheap and correctly typed. |
| D — Subproperty | Incorrect: an assessment must not OWL-entail case attachment when data is partial or when historical snapshots diverge. |

## OWL consequences

- Keep both object properties with explicit bilingual definitions emphasizing
  the distinction.
- Keep `owl:inverseOf` between `hasCaseEvidence` and `evidenceForCase`.
- Domain/range:
  - `hasCaseEvidence`: domain `MNPCase`, range `EvidenceRecord`
  - `usesEvidence`: domain `EligibilityAssessment`, range `EvidenceRecord`
  - `evidenceForCase`: domain `EvidenceRecord`, range `MNPCase`
- Do not declare `usesEvidence rdfs:subPropertyOf hasCaseEvidence`.
- Move defining axioms to the appropriate evidence/process/compliance modules
  under single-defining-module rules.

## SHACL consequences

- Eligibility profile may retain the SPARQL check that used evidence ⊆ case
  evidence for complete evaluation graphs.
- Foundation profile must **not** require `hasCaseEvidence` minCount or the
  uses⊆case SPARQL rule for every graph.
- Ontology-schema shapes do not encode this instance rule.

## Data migration impact

| Asset | Impact |
|---|---|
| Existing case TTL | Keep both edges; update namespace only |
| Evaluator | Continue emitting both; do not collapse |
| Queries / CQ-07 | Explicitly demonstrate the distinction |
| SHACL | Split constraint into eligibility profile |

No structural triple rewrite beyond IRI migration and profile relocation.

## Compatibility impact

| Change | Compatibility class |
|---|---|
| Keep both properties | Compatible semantically with pre-1.0.0 intent |
| Formal IRI migration | Major (release 1.0.0) |
| Moving SPARQL constraint to eligibility profile | Behavior change only for callers using foundation profile |

## Evidence / source

- Stage 03 brief §15
- Inline comments on `hasCaseEvidence` / `usesEvidence` in `mnp-core.ttl`
- `docs/architecture/evidence-layers.md` (business-fact vs modeling evidence)
- Existing eligibility SPARQL constraint in `shapes/mnp-shapes.ttl`

## Tests

- Annotation / definition tests state the availability vs use distinction
- CQ-07 SPARQL returns different bindings for case-available vs assessment-used
  evidence on a fixture that includes unused case evidence
- Foundation profile accepts a graph missing the uses⊆case condition
- Eligibility profile still fails when used evidence is not on the case
- No OWL entailment test expects `usesEvidence` to imply `hasCaseEvidence`
