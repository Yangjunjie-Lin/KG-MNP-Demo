# Namespace Policy

Machine source: `config/namespaces.yaml`.

Stage 02 freezes the future formal IRI policy. Existing Turtle modules that
still use `example.org` are not migrated in this stage.

## Frozen namespaces

| Kind | Value |
|---|---|
| Project base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/` |
| Ontology base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| Module IRI template | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/{module}` |
| Version IRI template | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/{version}/{module}` |
| Shape namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#` |
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
- Instance IRI: ABox individual identity
- Evidence IRI: evidence resource identity
- Mapping IRI: mapping resource identity
- Review IRI: review resource identity
- Named graph IRI: stable graph partition identity

## Stability rules

- Changing a label does not change an IRI.
- Moving a file path does not change an IRI.
- WebVOWL node IDs do not determine IRIs.
- GraphDB internal IDs do not determine IRIs.
- Random UUIDs are not used for stable TBox terms.

## Stage boundary

Bulk replacement of `example.org` inside `ontology/`, `shapes/`, `mappings/`,
and `data/` is deferred to Stage 03. Stage 02 only establishes the future
namespace configuration and validates that configuration.
