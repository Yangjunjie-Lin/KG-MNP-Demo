# Review Identifiers

All Stage 05 identifiers are deterministic SHA-256 URNs. They never use uuid4,
random values, process IDs, absolute local paths, or implicit system time.

## Session ID

```text
urn:kg-mnp:review-session:<sha256>
```

Semantic inputs:

- proposal ID / hash
- reviewer ID
- started_at
- review policy ID / version
- optional session label

## Decision ID

```text
urn:kg-mnp:review-decision:<sha256>
```

Semantic inputs include target, decision, rationale, reviewer, decided_at,
evidence refs, and modified candidate content when present.

## Decision Log ID

```text
urn:kg-mnp:review-decision-log:<sha256>
```

Represents the review session binding. Adding decisions does not change it.

## Log Hash

SHA-256 over the full log excluding only `log_hash`.

## Package ID / Hash

`package_semantic_hash` excludes `package_id` and `package_semantic_hash`.

```text
urn:kg-mnp:confirmed-modeling-package:<package_semantic_hash>
```
