# Review Authority

Stage 05 freezes the human-review authority boundary for dataset modeling.

## Authority chain

```text
CleanedPartialData
        ↓
ModelingProposal
        ↓
Human Review Actions
        ↓
ReviewDecisionLog
        ↓
ConfirmedModelingPackage
        ↓
Stage 06 Compiler (not implemented here)
```

## What is and is not authority

| Artifact | Authority |
|---|---|
| ModelingProposal | Not formal semantic authority |
| Human Review Action | Explicit human input; not publishable alone |
| ReviewDecisionLog | Formal human decision record over one proposal |
| ConfirmedModelingPackage | Sole Stage 06 compiler input package |
| OWL / SHACL / RDF | Future deterministic compilation products only |

## Reviewer identity

`reviewer_id` is a self-declared attribution identifier such as
`urn:kg-mnp:reviewer:professor-001`.

It is not:

- a login account
- a cryptographic signature
- a PKI-backed identity proof

## Forbidden automatic authority

Stage 05 forbids:

- default decisions
- default `CONFIRM`
- confirm-all / bulk confirmation
- confidence-based auto confirmation
- mapping-rule-status auto confirmation
- issue-count auto confirmation
- LLM reviewers
- compiling a proposal without a final ReviewDecisionLog
