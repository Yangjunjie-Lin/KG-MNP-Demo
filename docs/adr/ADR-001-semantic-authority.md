# ADR-001: Semantic Authority for KG-MNP

## Title

Semantic authority chain for ontology and knowledge graph foundation work.

## Status

Accepted

## Date

2026-08-05

## Context

KG-MNP is transitioning from a legacy eligibility demo into an ontology and
knowledge graph foundation. Residual JSON records are incomplete. Modeling
cannot treat a single cleaned dataset, an LLM suggestion, Protégé edits,
GraphDB exports, or WebVOWL layouts as independent authorities. The project
needs one explicit chain that separates business inputs, controlled semantic
dependencies, review decisions, confirmed packages, and generated artifacts.

## Decision

Formal semantic authority follows this chain:

```text
CleanedPartialData
+ OntologyBaseline@version
+ MappingRules@version
+ TerminologyProfile@version
        ↓
ModelingProposal
        ↓
ReviewDecisionLog
        ↓
ConfirmedModelingPackage
        ↓
OntologyBaseline@version
+ Confirmed Schema Delta
+ Confirmed ABox Decisions
        ↓
Generated OWL / SHACL / RDF / Provenance / Review Artifacts
```

CleanedPartialData is the only business data input. It is not the only semantic
dependency. Ontology baselines, mapping rules, terminology profiles, review
logs, and release policy are controlled semantic dependencies. Modeling
Proposal artifacts are candidates only. Only a Confirmed Modeling Package may
drive later formal compilation.

## Authoritative inputs

| Component | Authority | Role |
|---|---|---|
| CleanedPartialData | No formal semantic authority | Sole business data input |
| OntologyBaseline@version | Yes | Published TBox baseline |
| MappingRules@version | Controlled dependency | Candidate mapping generation |
| TerminologyProfile@version | Controlled dependency | Term matching and synonym support |
| ReviewDecisionLog | Yes | Human decision record |
| ConfirmedModelingPackage | Yes | Reviewed change and fact decisions |
| ReleasePolicy@version | Controlled dependency | Version and publication rules |
| Git | Version authority | Stores authoritative inputs, policies, and release artifacts |

Future compilers may consume only:

```text
Frozen Ontology Baseline
+ Confirmed Modeling Package
+ Versioned Build Policy
```

A cleaned JSON record alone cannot determine a complete ontology.

## Generated artifacts

Generated OWL, SHACL, RDF, provenance, and review artifacts are publication
outputs. They must be regenerated from authoritative inputs and must not become
a second independent modeling authority.

## Prohibited authority paths

- Protégé OWL edits committed as formal releases without Confirmed Package
  write-back.
- GraphDB Workbench ontology edits exported over Git ontology modules.
- WebVOWL layout interpreted as ontology relation definitions.
- Unreviewed LLM output entering formal TBox or ABox.
- Treating ModelingProposal as ConfirmedModelingPackage.
- Treating OWL/SHACL files as hand-edited sources of truth when a confirmed
  package exists for the same release.

## Consequences

- Default Dataset Modeling must not modify TBox.
- TBox changes require an approved Schema Delta with explicit
  `publication_scope = TBOX`.
- Explicit, inferred, proposed, rejected, and review-only facts remain distinct.
- Absence of data is not negation.
- Graph connectivity must not invent relations.
- Field names alone must not mint formal TBox terms.

## Alternatives considered

1. **JSON-first authority** — Rejected because cleaned partial data is
   incomplete and cannot define schema.
2. **OWL-file authority via Protégé** — Rejected because it bypasses review
   and versioned inputs.
3. **GraphDB-as-editor** — Rejected because storage/query tooling must not
   override Git-reviewed semantics.
4. **LLM auto-confirm** — Rejected because automatic confirmation of terms,
   relations, or constraints is forbidden.

## Migration implications

Stage 02 freezes the authority model, status vocabulary, namespace policy, and
release policy. Existing `example.org` IRIs, Domain/Range corrections, modeling
schemas, proposal pipelines, GraphDB, and WebVOWL remain deferred to later
stages.

## Verification

- `docs/architecture/semantic-authority-chain.md` restates the chain.
- `config/modeling-statuses.yaml` separates review status, decision, issue
  type, and publication scope.
- `tests/governance/test_semantic_authority.py` checks key authority markers.
- `make verify-stage-02` includes Stage 01 regression and governance tests.
