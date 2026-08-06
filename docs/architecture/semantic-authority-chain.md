# Semantic Authority Chain

## Central chain

```text
CleanedPartialData
+ OntologyBaseline@version
+ MappingRules@version
+ TerminologyProfile@version
        ↓
ModelingProposal
        ↓
Human Review Actions
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

Stage 05 implements the human-review and confirmed-package segment. A
`ModelingProposal` is never compiled directly. High-confidence candidates are
never auto-confirmed. `ConfirmedModelingPackage` is still not OWL, SHACL, RDF,
or a knowledge graph.

## Input classes

### Business data input

`CleanedPartialData` is the only business data input. It supplies observed
fields and values for a dataset modeling run. It does not independently define
formal ontology terms.

### Controlled semantic dependencies

| Dependency | Role |
|---|---|
| OntologyBaseline@version | Frozen published TBox used by modeling and compilation |
| MappingRules@version | Versioned field-to-term mapping rules |
| TerminologyProfile@version | Labels, synonyms, and matching profiles |
| ReviewDecisionLog | Human decisions over proposals |
| ReleasePolicy@version | Compatibility and publication rules |

### Formal compilation inputs

Future compilers may accept only:

```text
Frozen Ontology Baseline
+ Confirmed Modeling Package
+ Versioned Build Policy
```

### JSON Schema contract identities

JSON Schema contracts use the project `schemas` namespace family defined in
`config/namespaces.yaml`:

- `schemas/modeling/` is reserved for the Stage 04 central Modeling Contracts.
- `schemas/legacy/` is restricted to retained legacy use-case contracts, such
  as the eligibility input contract.

These Schema identifiers are contract identities, not ontology term IRIs,
instance IRIs, or named graph IRIs. The legacy eligibility schema therefore
does not become `CleanedPartialData` and is not an authority or input adapter
for the future Modeling Pipeline. Stage 03 validates these identities offline
without resolving `$id` or downloading remote schemas.

## Authority levels

| Component | Formal semantic authority | Responsibility |
|---|---:|---|
| CleanedPartialData | No | Business data input |
| MappingRules | Controlled dependency | Generate candidate mappings |
| TerminologyProfile | Controlled dependency | Term matching and synonym support |
| ModelingProposal | No | Automatic or semi-automatic candidates |
| ReviewDecisionLog | Yes | Human decision record |
| ConfirmedModelingPackage | Yes | Reviewed change and fact decisions |
| OntologyBaseline | Yes | Published TBox baseline |
| OWL/SHACL artifacts | No; release products | Machine semantics and validation products |
| Protégé | No | Inspection, experimentation, and reasoning |
| GraphDB | No | RDF storage, query, and reasoning |
| WebVOWL | No | TBox visualization |
| Git | Version authority | Authoritative inputs, policies, and releases |

## Tool responsibilities

| Component | Allowed role | Forbidden role |
|---|---|---|
| Confirmed Modeling Package | Reviewed semantic decisions | Bypass review |
| OWL / SHACL | Formal machine products | Second hand-edited authority |
| Protégé | Trial edits, checks, reasoning | Direct formal publication |
| RDFLib / pySHACL | Offline build and validation | Inventing semantics |
| GraphDB | Storage, SPARQL, reasoning, instance exploration | Ontology editing authority |
| WebVOWL | TBox visualization | Instance facts or review decisions |
| Git | Version authority | Secrets, runtime data, local databases |

## Protégé write-back path

```text
Issue found in Protégé
→ Modeling / Review Decision
→ Update authoritative inputs
→ Recompile
→ Refresh generated artifacts
```

## Prohibited second authorities

```text
Protégé edit OWL → skip Confirmed Package → commit formal release
GraphDB Workbench edit → export over Git ontology
WebVOWL layout → treat as ontology definition
LLM output → unreviewed → formal TBox or ABox
```

## Frozen principles

1. Residual JSON is the only business data input, not the only semantic dependency.
2. ModelingProposal is never formal semantics.
3. Only ConfirmedModelingPackage may drive later formal compilation.
4. Default Dataset Modeling must not modify TBox.
5. TBox changes require approved Schema Delta.
6. OWL, SHACL, RDF, GraphDB, and WebVOWL are not independent modeling authorities.
7. LLM systems must not auto-confirm ontology terms, relations, or constraints.
8. Absence is not negation; missing information is not rejection.
9. Relations must not be invented for graph connectivity.
10. A single field name must not mint a formal TBox term.
11. Explicit, inferred, proposed, and review-only facts remain separated.
