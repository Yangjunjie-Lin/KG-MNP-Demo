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
| `review record` | Yes, exactly one explicit action | Validates draft integrity before append; rejects unknown/duplicate/completed targets |
| `review validate` | No | Draft or final semantic validation |
| `review finalize` | Finalizes only | Requires exact-once coverage **and** runs full semantic validation (policy matrix, modified candidates, term types, IDs, hashes) before returning the final log |
| `confirm build` | No | Builds package from final log |
| `package validate` | No | Independently re-derives the expected package from authoritative inputs and requires deterministic equality |

## Finalization fail-closed rules

`review finalize` itself rejects illegal decisions even when Decision IDs and the
log hash were recomputed correctly. Examples:

- Issue target + `CONFIRM` / `MODIFY_AND_CONFIRM`
- Any `DEPRECATE`
- Illegal `MODIFY_AND_CONFIRM` payloads (missing source fields, kind drift, TBOX scope, bad term types)
- Unknown / duplicate / missing targets, wrong reviewer, illegal IDs or hashes

Policy load failures fail closed. There is no degrade-to-weaker-checks path.

## Package verification

`package validate` does **not** trust package self-reported readiness, closure, or
confirmed envelopes. It re-derives the unique package from:

- CleanedPartialData
- ModelingProposal
- Final ReviewDecisionLog
- Ontology Baseline, Mapping Rules, Terminology Profile, Proposal Policy, Review Policy

Self-hash proves only that a file is internally consistent. Deterministic
reconstruction proves the file is the unique output of those authorities.
Recomputing `package_semantic_hash` / `package_id` cannot authorize a tampered
package.

## Output locations

Default writable outputs:

- `runtime_outputs/review/`
- `runtime_outputs/confirmed-packages/`

Both are gitignored. Commands refuse to overwrite existing files unless
`--force` is provided.

## Correction policy

A completed ReviewDecisionLog cannot be appended or silently rewritten. Create a
new review session and a new decision log instead.
