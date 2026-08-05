# ODR-002 — Assessment, Decision, and Blocking Model

| Field | Value |
|---|---|
| ODR ID | ODR-002 |
| Title | Assessment → Decision → BlockingReason model |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related modules | `mnp-compliance`, `mnp-evidence-time` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |

## Context

Eligibility evaluation produces a decision object and, when blocked, one or more
blocking reasons with rule/evidence provenance. The pre-1.0.0 model allowed an
`EligibilityAssessment` to produce both a decision and blocking reasons
directly, which duplicates outcome semantics and complicates Conditional /
Manual Review outcomes.

## Current model

```text
EligibilityAssessment
    producesDecision        → EligibilityDecision
    producesBlockingReason  → BlockingReason

BlockingReason
    supportedByEvidence     → EvidenceRecord
    triggeredByRule         → EligibilityRule
    triggeredByRuleVersion  → RuleVersion
    citesClause             → RegulatoryClause
    recommendsAction        → RemediationAction
```

SHACL `BlockingDecisionShape` currently requires that the assessment which
produced a `BlockingDecision` also `producesBlockingReason` at least once.
Decision subclasses (`EligibleDecision`, `BlockingDecision`,
`ConditionalDecision`, `ManualReviewDecision`) are treated as mutually
exclusive outcome types.

## Problem

1. Blocking reasons are outcomes of a **decision**, not parallel products of
   the assessment activity.
2. Dual assertion (`producesDecision` + `producesBlockingReason`) risks
   inconsistency: a decision typed as eligible while the assessment still
   emits blocking reasons, or the reverse.
3. Conditional and manual-review decisions need a single decision node that can
   carry zero or more blocking / review reasons without a second assessment
   edge vocabulary.
4. Trace and SPARQL paths must choose between assessment→reason and
   decision→reason; keeping both without distinction violates Stage 03
   “no dual equivalent modeling” guidance.

## Candidate alternatives

### A — Keep assessment-produced blocking reasons

Retain `producesBlockingReason` from `EligibilityAssessment`. Document that
reasons are assessment artifacts and decisions are summary labels.

### B — Decision-owned blocking reasons (selected)

```text
EligibilityAssessment
    producesDecision → EligibilityDecision

EligibilityDecision
    hasBlockingReason → BlockingReason
```

Deprecate `producesBlockingReason`.

### C — Reify OutcomeBundle

Introduce an intermediate `AssessmentOutcome` node holding both decision type
and reason set.

### D — Attach reasons only to `BlockingDecision`

Make `hasBlockingReason` domain = `BlockingDecision` only (not the parent
`EligibilityDecision`).

## Selected model

**Alternative B**, with domain of `hasBlockingReason` = `EligibilityDecision`
(so Conditional / Manual Review decisions may also carry reasons when needed).

| Term | Decision |
|---|---|
| `producesDecision` | **ACCEPT** — Assessment → Decision (typically functional in published graphs) |
| `hasBlockingReason` | **ADD** — Decision → BlockingReason |
| `producesBlockingReason` | **DEPRECATE** — replacement path `producesDecision` / `hasBlockingReason` |
| Decision subclasses | **ACCEPT** disjointness among Eligible / Blocking / Conditional / ManualReview |

Canonical pattern:

```text
EligibilityAssessment --producesDecision--> EligibilityDecision
EligibilityDecision   --hasBlockingReason--> BlockingReason   (0..n; required for BlockingDecision in eligibility SHACL)
```

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Keep assessment→reason | Continues dual outcome modeling; SHACL and evaluator stay coupled to a deprecated pattern. |
| C — OutcomeBundle | Extra reification without required independent metadata in 1.0.0; deferred unless Stage 04 needs it. |
| D — Domain = BlockingDecision only | Over-constrains Conditional/ManualReview cases that still need cited reasons. |

## OWL consequences

- Add `hasBlockingReason` with domain `EligibilityDecision` and range
  `BlockingReason`.
- Deprecate `producesBlockingReason` with replacement documentation.
- Retain `producesDecision` domain/range; keep cardinality of “exactly one
  decision per assessment” as a published-graph / SHACL concern unless audit
  proves it is an ontological necessity (lean SHACL for partial data).
- Keep decision-class disjointness; do not weaken it merely because ABox data
  may temporarily lack typing.

## SHACL consequences

- Move blocking-reason presence checks from assessment `producesBlockingReason`
  to decision `hasBlockingReason`.
- Eligibility profile: `BlockingDecision` must have ≥1 `hasBlockingReason`.
- Eligibility profile: each `BlockingReason` still requires evidence, rule,
  rule version, and clause links as today.
- Foundation profile must not require complete blocking provenance for every
  partial graph.
- Update SPARQL constraints inside shapes to the formal term namespace.

## Data migration impact

| Asset | Impact |
|---|---|
| Case TTL / evaluator output | Re-link reasons from assessment to decision via `hasBlockingReason` |
| Trace / RDF builder | Stop emitting `producesBlockingReason` |
| CQ-02 / CQ-03 business queries and Stage 03 CQ-06 | Traverse Decision→BlockingReason |
| SHACL eligibility shapes | Rewrite BlockingDecision SPARQL constraint |
| Tests | Update expected triples and violation messages |

## Compatibility impact

| Change | Compatibility class |
|---|---|
| Deprecate `producesBlockingReason` | Major for writers/readers of that edge |
| Add `hasBlockingReason` | Additive property (packaged in 1.0.0 major) |
| SHACL message and path changes | Breaking for clients that key on old violation text |

Legacy CLI `kg-mnp-eligibility` remains the eligibility entry point; result
semantics should stay stable where only the reason attachment path changes.

## Evidence / source

- Stage 03 brief §14
- Existing `shapes/mnp-shapes.ttl` `BlockingDecisionShape` / `BlockingReasonShape`
- Case data patterns (`data/CASE-*.ttl`) using assessment→reason today
- `docs/architecture/owl-shacl-semantics.md`

## Tests

- ODR domain/range tests for `producesDecision` and `hasBlockingReason`
- Deprecated `producesBlockingReason` metadata present
- Eligibility SHACL: blocking decision without reasons fails; with
  `hasBlockingReason` passes
- Foundation SHACL does not require blocking reasons
- CQ-05 (unique decision) and CQ-06 (blocking reasons via decision)
- Nine-case eligibility regression after graph rewrite
