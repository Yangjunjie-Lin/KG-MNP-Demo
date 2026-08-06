# Stage 05 Review Examples

These fixtures are explicit human Review Actions and golden outputs for tests.
They are not live audit evidence from a production review board.

## Layout

```text
reviewers/
actions/
  full-confirmation/
  modified-confirmation/
  rejection/
  deferred-review/
  issue-resolution/
expected-logs/
expected-packages/
```

## Scenarios

| Scenario | Expected package status |
|---|---|
| full-confirmation | READY_FOR_COMPILATION |
| modified-confirmation | READY_FOR_COMPILATION |
| rejection | READY_FOR_COMPILATION |
| deferred-review | BLOCKED |
| issue-resolution | READY_FOR_COMPILATION |

## Regenerate

```bash
python scripts/generate_stage05_examples.py
```
