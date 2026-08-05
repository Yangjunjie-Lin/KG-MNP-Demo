# Namespace Policy

Machine source: `config/namespaces.yaml`.

Stage 02 froze the formal IRI policy, and Stage 03 migrated the released
ontology and legacy eligibility JSON Schema to the project namespaces below.

## Frozen namespaces

| Kind | Value |
|---|---|
| Project base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/` |
| Ontology base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| Module IRI template | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/{module}` |
| Version IRI template | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/{version}/{module}` |
| Shape namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#` |
| Schema base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/` |
| Modeling Schema namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/` |
| Legacy Schema namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/` |
| Instance base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/data/` |
| Evidence base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/evidence/` |
| Mapping base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/mapping/` |
| Review base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/review/` |

Named graphs:

| Graph | IRI |
|---|---|
| ontology | `urn:kg-mnp:ontology` |
| shapes | `urn:kg-mnp:shapes` |
| instances | `urn:kg-mnp:instances` |
| evidence | `urn:kg-mnp:evidence` |
| mappings | `urn:kg-mnp:mappings` |
| review | `urn:kg-mnp:review` |

## IRI kinds

- Ontology IRI: ontology document identity
- Module IRI: individual ontology module identity
- Version IRI: versioned module identity
- Term IRI: class or property identity under the terms namespace
- Shape IRI: SHACL shape identity
- Schema IRI: versioned JSON Schema contract identity
- Instance IRI: ABox individual identity
- Evidence IRI: evidence resource identity
- Mapping IRI: mapping resource identity
- Review IRI: review resource identity
- Named graph IRI: stable graph partition identity

## JSON Schema namespace roles

- `schemas/modeling/` is reserved for the formal Modeling Contracts introduced
  in Stage 04. Stage 03 does not create those contracts.
- `schemas/legacy/` identifies contracts owned by retained legacy use cases.
  The eligibility input schema is one such contract and is not the future
  `CleanedPartialData` contract.
- A Schema IRI identifies a JSON Schema contract. It is not an ontology term
  namespace, instance namespace, or named graph namespace, and it conveys none
  of those kinds of semantic authority.
- File location and `$id` are governed separately. The legacy contract lives
  with its example under `examples/eligibility-use-case/schemas/`, while its
  stable `$id` remains below `schemas.legacy`.
- Schema identifier checks are offline. They parse repository files and policy
  only; they never resolve `$id` or download a remote Schema.

## Stability rules

- Changing a label does not change an IRI.
- Moving a file path does not change an IRI.
- WebVOWL node IDs do not determine IRIs.
- GraphDB internal IDs do not determine IRIs.
- Random UUIDs are not used for stable TBox terms.

## Stage boundary

Stage 03 closes the legacy Schema location, identifier, and scan coverage gaps.
The repository-level `schemas/` path is reserved for Stage 04 Modeling
Contracts, but no Modeling Contract schema or Proposal Pipeline is introduced
by this policy update.
