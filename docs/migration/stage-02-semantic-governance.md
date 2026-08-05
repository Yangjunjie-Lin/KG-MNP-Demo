# Stage 02 Semantic Governance

## Base SHA

| Field | Value |
|---|---|
| Repository | `Yangjunjie-Lin/KG-MNP-Demo` |
| Branch | `main` |
| Base SHA | `deaf4a6c31ed97a7835abcfede48ead7ca41a663` |
| Latest commit | `deaf4a6 Refactor project structure and remove obsolete code` |
| Initial working tree | Clean relative to `main` at start of this task |
| Stage status | PASS (working tree; no commit created) |

## Stage 01 closure result

Stage 01 closure completed before Stage 02 work. Frontend, Docker fullstack
entry points, Neo4j formal backend, FastAPI/SQLite execution history, and the
old fixed-diagram path remain absent. The legacy eligibility CLI is registered
only as `kg-mnp-eligibility`.

## CLI rename

| Before | After |
|---|---|
| `kg-mnp = kg_mnp_demo.cli:main` | removed |
| — | `kg-mnp-eligibility = kg_mnp_demo.cli:main` |

`kg-mnp` is reserved for a future ontology modeling CLI and must not execute
eligibility evaluation. No placeholder central CLI was added.

## Semantic authority decision

Accepted ADR:
[`docs/adr/ADR-001-semantic-authority.md`](../adr/ADR-001-semantic-authority.md).

Authoritative chain:

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

Formal compilation inputs are limited to Frozen Ontology Baseline, Confirmed
Modeling Package, and Versioned Build Policy.

## TBox / ABox boundary

Frozen in
[`docs/architecture/tbox-abox-boundary.md`](../architecture/tbox-abox-boundary.md).

- TBox holds schema constructs.
- ABox holds instance facts and evidence bindings.
- Default Dataset Modeling must not modify TBox.
- Ontology Release requires Confirmed Schema Delta with
  `publication_scope = TBOX`.

## Status vocabulary

Machine config: `config/modeling-statuses.yaml`.

Separated vocabularies:

- `review_status`
- `review_decision`
- `issue_types`
- `publication_scope`

`CONFIRMED` does not imply TBOX or ABOX publication. `DEFER` is a decision, not
a review status.

## Evidence layers

Frozen in
[`docs/architecture/evidence-layers.md`](../architecture/evidence-layers.md).

- Modeling Evidence supports schema and mapping decisions.
- Business Fact Evidence supports concrete ABox assertions.
- Evidence does not equal confirmation.

## OWL / SHACL boundary

Frozen in
[`docs/architecture/owl-shacl-semantics.md`](../architecture/owl-shacl-semantics.md).

- OWL: open-world logical axioms and inference.
- SHACL: closed-world data quality validation.
- Domain/Range inference must not be treated as database type errors.

## Explicit / inferred boundary

Frozen in
[`docs/architecture/explicit-inferred-boundary.md`](../architecture/explicit-inferred-boundary.md).

Fact classes: EXPLICIT, INFERRED, PROPOSED, REJECTED, REVIEW_ONLY.

## Namespace policy

Machine config: `config/namespaces.yaml`.

Future GitHub Pages namespace:

- Project base: `https://yangjunjie-lin.github.io/KG-MNP-Demo/`
- Ontology base: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/`
- Terms: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#`
- Shapes: `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#`
- Instances: `https://yangjunjie-lin.github.io/KG-MNP-Demo/data/`
- Evidence: `https://yangjunjie-lin.github.io/KG-MNP-Demo/evidence/`
- Mappings: `https://yangjunjie-lin.github.io/KG-MNP-Demo/mapping/`
- Review: `https://yangjunjie-lin.github.io/KG-MNP-Demo/review/`
- Named graphs: `urn:kg-mnp:*`

Existing TTL migration deferred to Stage 03. Stage 02 does not claim formal IRI
migration is complete.

## Release policy

Machine config: `config/ontology-release-policy.yaml`.

- Semantic versioning
- Major / minor / patch classifications
- Deprecation requires marker, change log, and migration retention
- Schema Delta requires review, rationale, evidence, compatibility assessment,
  and explicit TBOX scope
- Generated artifacts must not be hand-edited as authority

## Protégé / GraphDB / WebVOWL policy

| Tool | Role | Forbidden |
|---|---|---|
| Protégé | Inspection, trial edits, reasoning | Direct formal publication |
| GraphDB | Storage, SPARQL, reasoning, exploration | Ontology editing authority |
| WebVOWL | TBox visualization | Instance facts or review decisions |

Protégé findings must return through Review Decision → authoritative inputs →
recompile → generated artifacts.

## Tests

- `tests/governance/test_namespace_policy.py`
- `tests/governance/test_modeling_statuses.py`
- `tests/governance/test_release_policy.py`
- `tests/governance/test_semantic_authority.py`
- `tests/governance/test_stage_boundaries.py`
- `tests/governance/test_stage_01_closure.py`

Gates:

```bash
make verify-stage-01
make verify-semantic-governance
make verify-stage-02
```

## Deferred Stage 03 work

- Formal replacement of `example.org`
- Formal ontology term audit
- Domain/Range corrections
- Bilingual label completion
- Module imports refactor
- Reasoner report
- Term change log

## Known risks

- Existing TTL modules still use `example.org`; documentation must not imply
  migration is finished.
- Legacy eligibility assets remain in original paths by Stage 01 exception.
- No Modeling Proposal, Review, Confirm, or Compiler implementation exists yet.
- Remote GitHub Actions results were not executed from this environment; local
  Stage 02 gates are the verification evidence for this working tree.
