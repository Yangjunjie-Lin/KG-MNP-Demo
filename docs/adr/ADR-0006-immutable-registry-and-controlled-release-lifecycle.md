# ADR-0006: immutable registry and controlled release lifecycle

> 长期权威与契约原则继续采用；下列历史输入格式、旧 CLI/平台共存及未来阶段实施条款已被当前契约和入口迁移部分替代。本文保留当时的决策背景，不代表当前功能状态。参见[迁移结论](../migration/history-and-current-boundaries.md)与[当前架构](../architecture/toolchain.md)。

We adopt an append-only local registry with deterministic replay and explicit
human release/activation gates.  This preserves Prompt 5 bytes and authority,
keeps semantic compilation at its existing policy version, and defers network
sync, garbage collection, automatic versioning, and automatic release.
