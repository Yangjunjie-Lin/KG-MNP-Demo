# Review Workflow

Stage 05 uses an explicit file workflow. There is no frontend, database, or
automatic reviewer.

## Commands

```bash
kg-mnp review init
kg-mnp review status
kg-mnp review record
kg-mnp review validate
kg-mnp review finalize
kg-mnp confirm build
kg-mnp package validate
kg-mnp package inspect
```

## Behavior

| Command | Writes decisions? | Notes |
|---|---|---|
| `review init` | No | Creates draft log with `decisions: []` |
| `review status` | No | Coverage and finalize readiness only |
| `review record` | Yes, exactly one explicit action | Rejects unknown/duplicate/completed targets |
| `review validate` | No | Draft or final semantic validation |
| `review finalize` | Finalizes only | Requires exact-once coverage |
| `confirm build` | No | Builds package from final log |

## Output locations

Default writable outputs:

- `runtime_outputs/review/`
- `runtime_outputs/confirmed-packages/`

Both are gitignored. Commands refuse to overwrite existing files unless
`--force` is provided.

## Correction policy

A completed ReviewDecisionLog cannot be appended or silently rewritten. Create a
new review session and a new decision log instead.
