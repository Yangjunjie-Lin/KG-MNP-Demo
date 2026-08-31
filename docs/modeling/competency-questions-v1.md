# Competency Questions v1

A `CompetencyQuestionSet` precedes candidate generation and is bound to the
approved scope and Project Lock. Each question records text, purpose, priority,
expected answer shape (`BOOLEAN`, `ENTITY_LIST`, `SCALAR`, `TABLE`, or
`GRAPH_PATTERN`), required concepts/relations/constraints, evidence and Domain
Pack references, validation intent, and status.

Prompt 4 produces only a structural `CompetencyQuestionCoverageReport`. It asks
whether candidates exist for the requested structures and whether an evidence
and review path is present. `structural_only=true` and
`execution_claimed=false` are invariant. No SPARQL query, reasoner test, or
final CQ pass is executed or claimed; those belong to Prompt 5.

Duplicate question IDs, missing purpose, unsupported answer shapes, and broken
contract/evidence references fail closed. A coverage gap remains reviewable and
cannot be hidden by provider scores.
