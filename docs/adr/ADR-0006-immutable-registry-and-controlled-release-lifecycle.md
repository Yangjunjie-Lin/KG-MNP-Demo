# ADR-0006: immutable registry and controlled release lifecycle

We adopt an append-only local registry with deterministic replay and explicit
human release/activation gates.  This preserves Prompt 5 bytes and authority,
keeps semantic compilation at its existing policy version, and defers network
sync, garbage collection, automatic versioning, and automatic release.
