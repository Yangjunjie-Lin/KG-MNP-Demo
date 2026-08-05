# Explicit and Inferred Fact Boundary

## Fact classes

| Class | Meaning |
|---|---|
| EXPLICIT | Asserted by formal compilation inputs |
| INFERRED | Produced by OWL, rule sets, or store reasoning |
| PROPOSED | Unconfirmed candidate |
| REJECTED | Explicitly rejected candidate |
| REVIEW_ONLY | Exists only in the review layer |

## Rules

1. Inferred facts must not be presented as source facts.
2. Inferred facts must not carry fabricated source-field evidence.
3. Future query results must distinguish explicit from inferred facts.
4. GraphDB integration must preserve the same boundary.
5. Provenance must point to explicit assertions, not fake inferred sources.
6. Inference results may record a rule or ruleset identity, but must not pretend
   to originate from the source JSON.

## Modeling implications

- Confirmed ABox decisions may become EXPLICIT after compilation.
- OWL-RL or store reasoning may add INFERRED triples.
- ModelingProposal content remains PROPOSED until review.
- `CONFIRMED + REVIEW_ONLY` stays outside the formal graph.
- Rejected candidates remain REJECTED and must not re-enter as EXPLICIT without
  a new review decision.
