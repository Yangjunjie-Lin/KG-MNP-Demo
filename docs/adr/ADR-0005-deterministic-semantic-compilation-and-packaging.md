# ADR-0005: Deterministic Semantic Compilation and Packaging

> 长期权威与契约原则继续采用；下列历史输入格式、旧 CLI/平台共存及未来阶段实施条款已被当前契约和入口迁移部分替代。本文保留当时的决策背景，不代表当前功能状态。参见[迁移结论](../migration/history-and-current-boundaries.md)与[当前架构](../architecture/toolchain.md)。

## Status

Accepted for Prompt 5.

## Decision

The reviewed Prompt 4 Confirmed Package is the only new semantic input. The
compiler verifies but does not reinterpret KG-IR, and provider plugins cannot
enter its authority. The historical Stage 06 compiler remains a compatibility
surface, not the new entry point. A domain-neutral overlay module preserves the
locked baseline; explicit user versions avoid an unreviewed SemVer decision.

Canonical NT/NQ are the semantic digest basis. Turtle/TriG are deterministic
readable views. Generated blank nodes are prohibited and baseline structures
are stably skolemized. OWL profile/consistency, final SHACL, explicit CQ oracles
and provenance closure are mandatory and have no automatic repair loop.
Natural-language CQs never become generated SPARQL in this phase.

The output is a portable, locked `VALIDATED_UNPUBLISHED` package. Registry,
semantic diff, publication, activation and rollback remain Prompt 6. `.kgop`
is outside the lock to avoid self-reference while retaining deterministic
export and independent verification.

## Alternatives

Directly extending Stage 06 was rejected because its contract, MNP paths and
publication coupling violate the new boundary. Runtime blank-node labels,
automatic version inference, remote imports, provider compiler plugins and
validation-triggered LLM repair were rejected as non-reproducible authority.

## Consequences, risks and reversibility

Builds require complete current-Catalog authority closure and a trusted local
reasoner for strict packages. Large ontology performance, engine boundaries,
query/oracle quality and baseline skolemization remain risks. The package is
portable but not published. The migration is reversible by retaining all old
contracts and CLI behavior; the additive kernel and Catalog 1.2 entries can be
removed without rewriting historical artifacts, though new packages would no
longer validate.
