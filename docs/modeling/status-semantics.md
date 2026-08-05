# Modeling Status Semantics

Status values are separated into four vocabularies. Do not reuse one mixed
`status` field for review state, decision action, issue type, and publication
scope.

Machine source: `config/modeling-statuses.yaml`.

## review_status

Current review state of an object:

| Value | Meaning |
|---|---|
| PROPOSED | No formal decision yet |
| CONFIRMED | Passed an effective review |
| REJECTED | Explicitly refused |
| DEPRECATED | Previously confirmed, now retired |

`DEFER` is not a review status. `MISSING_INFORMATION` is not a review status.
`TBOX` is not a review status.

## review_decision

Reviewer actions:

| Value | Meaning |
|---|---|
| CONFIRM | Accept as proposed |
| REJECT | Refuse |
| MODIFY_AND_CONFIRM | Accept after explicit modification |
| DEFER | Postpone; decision type only |
| DEPRECATE | Retire a previously confirmed item |

`DEFER` records a decision to wait. It must not be treated as a publication
state.

## issue_types

An item may carry multiple issue types:

- MISSING_INFORMATION
- CONFLICT
- AMBIGUOUS
- UNSUPPORTED
- INCONSISTENT_SOURCE
- LOW_CONFIDENCE

Example:

```yaml
review_status: PROPOSED
issue_types:
  - AMBIGUOUS
  - LOW_CONFIDENCE
publication_scope: REVIEW_ONLY
```

`CONFIRMED` is not an issue type.

## publication_scope

Where a confirmed item may be published later:

- TBOX
- ABOX
- EVIDENCE
- MAPPING
- REVIEW_ONLY
- NONE

Important:

```text
CONFIRMED ≠ automatic TBOX publication
CONFIRMED ≠ automatic ABOX publication
```

`CONFIRMED + REVIEW_ONLY` remains outside the formal graph until a later
decision changes publication scope.
