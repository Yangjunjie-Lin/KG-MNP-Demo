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
