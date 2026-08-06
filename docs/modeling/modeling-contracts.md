# Modeling Contracts

The closed modeling registry under `schemas/modeling/` now contains eleven
JSON Schema Draft 2020-12 contracts. Their stable HTTPS identifiers belong to
the `schemas.modeling` namespace in `config/namespaces.yaml`, while every `$ref`
is resolved offline. The identifiers are contract identities; they are not
ontology term IRIs and are never dereferenced over the network.

| Contract | Role | Formal semantic authority |
|---|---|---:|
| Common definitions | Reusable value objects | No |
| CleanedPartialData | Sole business-data input | No |
| ModelingProposal | Review candidates and issues | No |
| ReviewDecisionLog | Human decisions | Yes |
| ConfirmedModelingPackage | Reviewed publication input | Yes |
| OntologyBaselineManifest | Frozen Stage 03 dependency | Controlled authority |
| MappingRules | Safe candidate-generation rules | Controlled dependency |
| TerminologyProfile | Labels, aliases, normalized forms | Controlled dependency |
| Review Common | Shared review value objects | No |
| Review Action | Explicit human review input | No; input only |
| Review Policy | Frozen Stage 05 review policy | Controlled dependency |

`ModelingProposal` is deliberately not a `ConfirmedModelingPackage`. Stage 05
adds the file-based review workflow and deterministic package builder while
keeping Stage 04 contract `$id` values at version `1.0`.

The documents under `tests/fixtures/modeling/` and `examples/review/` exist to
exercise validators and golden outputs. They are not production audit evidence.

The local registry validates every schema with `Draft202012Validator`, checks
unique IDs, resolves all references from preloaded local resources, and fails
closed for missing, duplicate, unknown, or cyclic resources.
