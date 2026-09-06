# Activation and rollback

Activation and rollback use explicit human review, expected generation/hash,
atomic writes, registry events, and execution receipts.  A stale pointer is a
concurrency conflict rather than an implicit overwrite.
