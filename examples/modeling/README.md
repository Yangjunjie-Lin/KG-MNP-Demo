# Stage 04 Modeling Examples

These six fixtures are synthetic and contain no real personal information:

- `partial-basic` exercises candidate entities and assertions.
- `explicit-null` preserves a JSON null and produces an issue.
- `declared-missing` records explicit missing information without inventing a value.
- `conflicting-values` preserves all source alternatives without a winner.
- `unmapped-fields` records an unsupported field without minting a TBox term.
- `low-confidence-source` retains proposed candidates and adds confidence issues.

`expected-proposals/` contains deterministic golden results generated from the
versioned Stage 04 dependencies. Re-run with the central CLI only when an
authoritative input or dependency intentionally changes:

```bash
kg-mnp propose --input examples/modeling/inputs/partial-basic.json \
  --output runtime_outputs/modeling/partial-basic.proposal.json
```

The expected JSON files are review fixtures, not formal semantic authority.

