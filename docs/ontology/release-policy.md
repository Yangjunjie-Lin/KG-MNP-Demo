# Ontology Release Policy

Machine source: `config/ontology-release-policy.yaml`.

Stage 02 freezes release and compatibility rules. No ontology terms are changed
in this stage.

## Versioning

The project uses semantic versioning for ontology releases.

## Major changes

Examples:

- Formal IRI change
- Term removal
- Semantic redefinition
- Incompatible Domain or Range change
- Incompatible cardinality change
- Reidentification of class or instance identity

## Minor changes

Examples:

- Additive class
- Additive property
- Additive optional shape
- Additive mapping
- Additive external alignment
- Additive module that does not break existing data

## Patch changes

Examples:

- Spelling correction
- Label correction
- Definition clarification without logical change
- Source metadata update
- Documentation fix

## Deprecation

Required:

- `owl:deprecated true`
- Term change log
- Replacement term when available
- Migration note
- Retention for at least one migration cycle

Immediate removal of a published term is forbidden.

## Approval

Schema Delta publication requires:

- Human review
- Explicit TBOX publication scope
- Rationale
- Evidence
- Compatibility assessment

## Generated artifacts

- Direct manual edits of generated artifacts are forbidden.
- Artifacts must be regenerated from authoritative inputs.
