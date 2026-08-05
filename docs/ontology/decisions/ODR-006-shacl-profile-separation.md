# ODR-006 — SHACL Profile Separation

| Field | Value |
|---|---|
| ODR ID | ODR-006 |
| Title | Separate ontology-schema, foundation-instance, and eligibility-instance SHACL |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related assets | `shapes/`, `examples/eligibility-use-case/shapes/`, `src/kg_mnp_demo/validator.py` |
| Shape namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#` |

## Context

Pre-1.0.0 validation uses a single `shapes/mnp-shapes.ttl` that mixes TBox
quality concerns, generic instance hygiene, and strict legacy eligibility-use
case rules (exactly one number per case, assessment must use evidence, blocking
reasons must cite rules, etc.). Stage 03 reframes the repository as an ontology
foundation with a legacy eligibility example; SHACL profiles must follow that
boundary.

## Current model

Single file:

```text
shapes/mnp-shapes.ttl
```

Notable mixed targets include:

- `MNPCaseShape` — case id, exactly one number, applicant, ≥1 case evidence
- `EvidenceRecordShape` — source system, generatedAt, status enum
- `EligibilityAssessmentShape` — usesEvidence, rules, dependsOn, producesDecision, uses⊆case SPARQL
- `BlockingDecisionShape` / `BlockingReasonShape` — strict blocking provenance
- Additional process / contract / billing integrity shapes in the same graph

Validator loads shapes as one bundle without profiles.

## Problem

1. Foundation / partial-data graphs fail eligibility-grade constraints.
2. Ontology authors cannot validate label/definition completeness separately
   from ABox rules.
3. Legacy eligibility demos must keep strict constraints without imposing them
   on all KG-MNP consumers.
4. Duplicating the same shape file per profile would diverge and break
   Stage 03 “no copy-based profiles” rule.

## Candidate alternatives

### A — Keep one monolithic shapes file

Document severity tags only; no file split.

### B — Split into three profile graphs (selected)

```text
shapes/ontology-schema-shapes.ttl
shapes/foundation-instance-shapes.ttl
examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl
```

Validator selects profiles explicitly.

### C — Put all three files under `examples/eligibility-use-case/shapes/`

Treat every shape as example-scoped.

### D — Encode all instance rules as OWL cardinality

Eliminate most SHACL.

## Selected model

**Alternative B** (Stage 03 brief §19). Paths:

| Profile | File | Purpose |
|---|---|---|
| Ontology schema | `shapes/ontology-schema-shapes.ttl` | TBox quality (labels, definitions, version IRI, deprecated replacement, audited domain/range or explicit exemption) |
| Foundation instance | `shapes/foundation-instance-shapes.ttl` | Stable KG foundation constraints (IRI/datatype hygiene, explicit relation assertion structure, evidence reference typing, no review-only statuses in published graphs) |
| Eligibility instance | `examples/eligibility-use-case/shapes/eligibility-instance-shapes.ttl` | Legacy eligibility use-case strictness (case completeness, assessment evidence/rules, blocking provenance, uses⊆case) |

Validator API direction:

```text
validate_graph(graph, profile="foundation")
validate_graph(graph, profile="eligibility")
validate_ontology_schema(graph)
```

Rules:

- `foundation` must not auto-load eligibility shapes.
- `eligibility` explicitly loads legacy eligibility shapes (and may compose
  foundation if documented).
- Ontology schema validation is separate from ABox validation.
- Old nine-case tests select `eligibility`; new foundation tests select
  `foundation`.
- Do not implement profiles by copying the same triples into multiple files.

Historical `shapes/mnp-shapes.ttl` is migrated/split and must not remain the
authoritative mixed bundle after Stage 03.

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Monolith | Continues wrong default strictness for foundation graphs. |
| C — All under examples/ | Mis-scopes ontology-schema and foundation shapes as eligibility examples. |
| D — OWL-only | Violates OWL vs SHACL boundary; harms partial-data posture. |

## OWL consequences

- None directly; SHACL split must not silently convert closed-world eligibility
  rules into OWL axioms.
- Ontology release still carries OWL domain/range per ODRs; SHACL must not
  mechanically mirror every domain/range as a violation.

## SHACL consequences

### ontology-schema-shapes.ttl

Examples of checks:

- Formal class/property has `rdfs:label`@en and @zh-CN
- Formal class/property has `skos:definition`@en and @zh-CN
- Object properties have audited domain/range or documented exemption
- Datatype properties have range
- Deprecated terms have replacement or rationale
- Ontology resources expose `owl:versionIRI`

### foundation-instance-shapes.ttl

Examples of checks:

- Identifier datatypes
- Structural integrity for explicit modeling relation assertions (when present)
- Evidence reference typing without requiring full eligibility packages
- Published graphs exclude review-only statuses (per Stage 02 vocab)

Must **not** assume every partial record has complete eligibility evidence.

### eligibility-instance-shapes.ttl

Migrate strict legacy rules, including:

- Case exactly one phone number / applicant (as required by the demo)
- Assessment uses ≥1 evidence and cites rules
- Blocking decision has blocking reasons (via ODR-002 path)
- Blocking reasons cite evidence, rule, version, clause
- usesEvidence ⊆ hasCaseEvidence SPARQL constraint

Each named shape should carry bilingual labels, severity, and bilingual
messages; SPARQL prefixes use the formal term/shape namespaces.

## Data migration impact

| Asset | Impact |
|---|---|
| `shapes/mnp-shapes.ttl` | Split / retire as authority |
| New shape files | Receive migrated constraints |
| `examples/eligibility-use-case/` | Host eligibility shapes + README pointer |
| Validator / loader | Profile-aware paths from config |
| Tests | Explicit profile selection |
| CI gates | `verify-shacl-profiles` |

Instance TTL data files change only as required by other ODRs/IRI migration;
profile separation alone does not rewrite business facts.

## Compatibility impact

| Change | Compatibility class |
|---|---|
| Default validation no longer equals old monolith | Breaking for callers that assumed one shapes file |
| Eligibility profile preserves legacy strictness | Compatible for nine-case suite when profile selected |
| Foundation profile relaxation | Intentional compatibility with partial data |

## Evidence / source

- Stage 03 brief §19–§20
- Current `shapes/mnp-shapes.ttl`
- `docs/architecture/owl-shacl-semantics.md`
- `docs/architecture/tbox-abox-boundary.md`
- ODR-002, ODR-003, ODR-004 (constraints that move with eligibility profile)

## Tests

- `test_shape_profiles.py` — foundation does not load eligibility shapes
- `test_foundation_shacl.py` — partial graph without full eligibility evidence can pass
- `test_eligibility_shacl.py` — legacy strict violations still detected
- Nine-case regression uses eligibility profile
- Ontology schema shapes fail fixtures missing bilingual definitions
- No duplicate authoritative shape graphs for the same profile
