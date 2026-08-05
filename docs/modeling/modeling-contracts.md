# Stage 04 Modeling Contracts

Stage 04 defines eight JSON Schema Draft 2020-12 contracts below
`schemas/modeling/`. Their stable HTTPS identifiers belong to the
`schemas.modeling` namespace in `config/namespaces.yaml`, while every `$ref`
is resolved from a closed local registry. The identifiers are contract
identities; they are not ontology term IRIs and are never dereferenced over
the network.

| Contract | Role | Formal semantic authority |
|---|---|---:|
| Common definitions | Reusable value objects | No |
| CleanedPartialData | Sole business-data input | No |
| ModelingProposal | Review candidates and issues | No |
| ReviewDecisionLog | Human decisions | Yes; contract only in Stage 04 |
| ConfirmedModelingPackage | Reviewed publication input | Yes; contract only in Stage 04 |
| OntologyBaselineManifest | Frozen Stage 03 dependency | Controlled authority |
| MappingRules | Safe candidate-generation rules | Controlled dependency |
| TerminologyProfile | Labels, aliases, normalized forms | Controlled dependency |

`ModelingProposal` is deliberately not a `ConfirmedModelingPackage`. Stage 04
implements schema and semantic validation for the two later contracts, but no
review workflow, confirmation workflow, or confirmed-package builder.

The documents under `tests/fixtures/modeling/` exist only to exercise those
cross-reference validators. They are synthetic test data, are not review
records, and carry no formal semantic authority.

The local registry validates every schema with `Draft202012Validator`, checks
unique IDs, resolves all references from preloaded local resources, and fails
closed for missing, duplicate, unknown, or cyclic resources.
