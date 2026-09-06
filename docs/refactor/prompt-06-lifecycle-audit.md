# Prompt 6 lifecycle audit

The 0.6.0 lifecycle surface is additive to the Prompt 5 package and lock
contracts.  Registry history is append-only, snapshots and indexes are
rebuildable projections, and release/environment pointers are independently
controlled states.  The audit commands are offline and fail closed on digest,
path, event-chain, contract, or human-review violations.
