# ODR-001 — Number, Subscription, and Account Model

| Field | Value |
|---|---|
| ODR ID | ODR-001 |
| Title | Number–Subscription–Account relational model |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related modules | `mnp-identity`, `mnp-service-contract`, `mnp-account-billing`, `mnp-core` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |

## Context

Stage 03 formalizes the commercial relationship between a subscriber, a
service subscription, a phone number, and a billing account. The pre-1.0.0
model mixed ownership-like shortcuts (`ownsPhoneNumber`), a vague subscription
link (`hasSubscription`), a subscriber-domain billing edge (`billedThrough`),
and a redundant account shortcut (`relatedAccount`). These shortcuts conflict
with TMF-style product/subscription/account patterns and produce incorrect OWL
domain inference when billing is asserted on a person rather than a
subscription.

## Current model

Pre-1.0.0 declarations in `ontology/mnp-core.ttl` (temporary
`http://example.org/kg-mnp#` namespace):

```text
Subscriber  --ownsPhoneNumber-->  PhoneNumber
Subscriber  --hasSubscription-->  ServiceSubscription
Subscriber  --billedThrough-->    TelecomAccount
Subscriber  --relatedAccount-->   TelecomAccount

ServiceSubscription --subscribesToService--> TelecomService
ServiceSubscription --governedByContract-->  ServiceContract
```

Observations from case data and queries:

- Most eligibility paths need the subscription as the commercial hub.
- Billing facts are about the subscription/service relationship, not the
  natural-person subscriber as domain subject.
- `relatedAccount` duplicates the billing path without adding distinct
  semantics.
- `ownsPhoneNumber` implies property ownership rather than service assignment.

## Problem

1. `billedThrough` with `rdfs:domain Subscriber` causes OWL reasoners to type
   any subject of billing as a `Subscriber`, even when the intended subject is
   a `ServiceSubscription`.
2. `ownsPhoneNumber` encodes an ownership reading that is legally and
   commercially ambiguous for MNP.
3. `hasSubscription` is underspecified relative to the clearer
   `holdsSubscription` reading (subscriber holds a commercial subscription).
4. `relatedAccount` is redundant with `billedThrough` once billing is anchored
   on the subscription.
5. There is no first-class link from `PhoneNumber` to
   `ServiceSubscription`, so number–subscription–account traces rely on
   informal conventions.

## Candidate alternatives

### A — Keep subscriber-centric shortcuts

Retain `ownsPhoneNumber`, `hasSubscription`, subscriber-domain `billedThrough`,
and `relatedAccount`. Add documentation notes only.

### B — Subscription-centric chain (selected)

```text
Subscriber
    holdsSubscription → ServiceSubscription

PhoneNumber
    assignedToSubscription → ServiceSubscription

ServiceSubscription
    subscribesToService → TelecomService
    billedThrough → TelecomAccount
    governedByContract → ServiceContract
```

Deprecate `hasSubscription`, `ownsPhoneNumber`, and `relatedAccount`.

### C — Introduce `hasAssignedPhoneNumber` on Subscriber

Replace `ownsPhoneNumber` with a direct subscriber→number assignment property
while keeping billing on the subscriber.

### D — Make `relatedAccount` a named inverse shortcut

Keep `relatedAccount` as an explicitly inverse or property-chain materialization
of `holdsSubscription` ∘ `billedThrough`.

## Selected model

**Alternative B.**

| Term | Decision |
|---|---|
| `holdsSubscription` | **ADD** — domain `Subscriber`, range `ServiceSubscription` |
| `hasSubscription` | **DEPRECATE** — replacement `holdsSubscription` |
| `assignedToSubscription` | **ADD** — domain `PhoneNumber`, range `ServiceSubscription` |
| `billedThrough` | **MODIFY** — domain `ServiceSubscription`, range `TelecomAccount` |
| `ownsPhoneNumber` | **DEPRECATE** — express via `holdsSubscription` + `assignedToSubscription` (inverse direction from number) |
| `relatedAccount` | **DEPRECATE** — redundant with `billedThrough` on the subscription |
| `subscribesToService` | **ACCEPT** (unchanged semantics) |
| `governedByContract` | **ACCEPT** (unchanged semantics) |

Canonical chain:

```text
Subscriber --holdsSubscription--> ServiceSubscription
PhoneNumber --assignedToSubscription--> ServiceSubscription
ServiceSubscription --billedThrough--> TelecomAccount
ServiceSubscription --subscribesToService--> TelecomService
ServiceSubscription --governedByContract--> ServiceContract
```

Optional navigation (query-only, not asserted OWL property chains in 1.0.0):

```text
Subscriber → Subscription → PhoneNumber
PhoneNumber → Subscription → TelecomAccount
```

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Keep shortcuts | Preserves incorrect billing domain and ownership ambiguity; fails Stage 03 domain/range audit. |
| C — `hasAssignedPhoneNumber` | Still bypasses the subscription hub; duplicates the selected number→subscription edge in reverse without fixing billing. |
| D — Keep `relatedAccount` as chain | Adds a second asserted path that must stay synchronized; Stage 03 prefers explicit deprecation over dual modeling. |

## OWL consequences

- Add `holdsSubscription` and `assignedToSubscription` as object properties with
  audited domain/range and bilingual annotations.
- Mark `hasSubscription`, `ownsPhoneNumber`, and `relatedAccount` with
  `owl:deprecated true`, `skos:changeNote`, and replacement pointers.
- Change `billedThrough` domain from `Subscriber` to `ServiceSubscription`
  (major semantic change under release policy).
- Do **not** assert multi-domain unions that would intersect incorrectly.
- Do **not** encode partial-data “must have account” requirements as OWL
  cardinality; residual incompleteness remains an ABox/SHACL concern.
- Prefer defining these terms in identity / service-contract / account-billing
  modules rather than leaving them all in `mnp-core`.

## SHACL consequences

- Foundation shapes may check IRI/datatype hygiene only; they must not require
  a complete commercial chain for every partial record.
- Eligibility shapes may require case→number and assessment completeness, but
  must follow the new chain when validating billing or subscription links.
- Remove or rewrite any shape that assumes `Subscriber billedThrough Account`
  or `Subscriber ownsPhoneNumber`.
- Add optional shapes (eligibility or dedicated commercial profile later) for
  `assignedToSubscription` and `holdsSubscription` when those facts are in
  scope.

## Data migration impact

| Asset | Impact |
|---|---|
| `data/case*.ttl` | Rewrite `hasSubscription` → `holdsSubscription`; move `billedThrough` subjects to subscriptions; replace `ownsPhoneNumber` with number→subscription assignment; drop `relatedAccount` assertions |
| SPARQL / CQ queries | Update subscription and billing path patterns |
| `mappings/tmf_to_mnp.yaml` | Remap TMF relatedParty/product/account fields to the new chain |
| Evaluator / RDF builder | Emit new properties; stop materializing deprecated edges |
| Tests / fixtures | Expect new IRIs and graph shapes |

Migration retention: deprecated terms remain in the TBox for at least one
migration cycle with markers, per `docs/ontology/release-policy.md`.

## Compatibility impact

| Change | Compatibility class |
|---|---|
| Formal IRI migration + domain change of `billedThrough` | **Major** (1.0.0 first stable release) |
| Rename `hasSubscription` → `holdsSubscription` | Major term change (deprecate + replace) |
| Deprecate `ownsPhoneNumber`, `relatedAccount` | Major for consumers still writing those edges |
| Additive `assignedToSubscription` | Minor if considered alone; packaged inside 1.0.0 major release |

Consumers of pre-1.0.0 `example.org` graphs are not binary-compatible.
Historical snapshots under `demo_outputs/` and migration docs may retain old
IRIs under the Stage 03 allowlist.

## Evidence / source

- Stage 03 brief §13 (number–subscription–account audit baseline)
- TM Forum Customer / Product Inventory / Customer Bill patterns referenced in
  `ontology/mnp-alignments.ttl` and `mappings/tmf_to_mnp.yaml`
- `docs/architecture/owl-shacl-semantics.md` (domain/range as inference, not
  DB type checks)
- `docs/ontology/release-policy.md` (deprecation and major-change rules)
- Pre-1.0.0 definitions in `ontology/mnp-core.ttl`

## Tests

- Domain/range of `holdsSubscription`, `assignedToSubscription`, and
  `billedThrough` match this ODR (`tests/ontology_release/test_domain_range_decisions.py`)
- Deprecated terms carry `owl:deprecated` and replacement metadata
- No formal runtime asset asserts `ownsPhoneNumber` / `relatedAccount` /
  `hasSubscription` after migration (allowlisted history excepted)
- Competency queries CQ-03 and CQ-04 traverse the selected chain
- Legacy nine-case eligibility regression still passes under the eligibility
  SHACL profile after data rewrite
