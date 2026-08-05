# Deterministic Proposal Generation

`generate_modeling_proposal()` is a pure semantic operation once its five
documents and verified term inventory are supplied. It does not access the
network, clocks, randomness, the user home directory, GraphDB, or an LLM; it
does not mutate inputs or write ontology files.

The generator validates input and dependencies, resolves exact selectors,
preserves explicit null/missing/conflict states, executes confirmed rules and
finite transforms, builds candidates, records unmapped fields and issues,
sorts every semantic collection, assigns content hashes and stable IDs, and
validates the final Proposal.

The finite transform registry is:

```text
IDENTITY
STRING_TRIM
STRING_NORMALIZE
BOOLEAN_STRICT
INTEGER_STRICT
DECIMAL_STRICT
DATETIME_TO_UTC
CODE_NORMALIZE
IRI_FROM_STABLE_ID
```

A transform error produces an `UNSUPPORTED` issue and no transformed
assertion. It never substitutes false, zero, an empty string, or the current
time. Unknown target terms are rejected before generation.

