# ADR-0003: Plugin-driven evidence-bound ingestion

> 长期权威与契约原则继续采用；下列历史输入格式、旧 CLI/平台共存及未来阶段实施条款已被当前契约和入口迁移部分替代。本文保留当时的决策背景，不代表当前功能状态。参见[迁移结论](../migration/history-and-current-boundaries.md)与[当前架构](../architecture/toolchain.md)。

- Status: Accepted
- Scope: Prompt 3

## Context

Prompt 2 established one offline Contract Catalog, deterministic Workspace and
data-only Domain Packs. Prompt 3 needs heterogeneous parsing without coupling
ontology modeling authority to file libraries or third-party providers.

## Decision

Introduce Plugin SDK v1 before ontology-modeling refactoring. Plugins are
installed Python distributions discovered from metadata without automatic
import. External code is disabled until explicitly allowlisted. The built-in
planner is deterministic and offline. PluginSnapshot binds declared code for
reproduction, while Source/Evidence/KG-IR/artifact IDs and writes remain Core
authority.

Plugins are installed code, never Domain Pack content: Packs remain portable,
reviewable data and cannot become a code-loading channel. Discovery does not
auto-import because listing untrusted installed metadata must not execute it.
This is still not an OS sandbox once an operator enables a Python provider.

Evidence Binder stays Core so providers cannot forge authoritative provenance.
KG-IR is evidence-constrained intermediate structure, not ontology or a
business object. Modeling scope, terms, relations, field mappings and human
review are deferred to Prompt 4. OCR, vision, ASR and video understanding are
not faked; missing capability becomes review/unresolved. Remote source access
and network providers are disabled to keep this gate offline and reproducible.

PluginSnapshot is a digest binding for manifest, implementation and
configuration. It is not a code signature or trust proof.

## Alternatives considered

- Put executable providers in Domain Packs: rejected because it collapses the
  data/code trust boundary.
- Import all entry points during discovery: rejected because `plugin list`
  would execute external code.
- Let plugins emit evidence or KG-IR files: rejected because provider and
  provenance authority would be inseparable.
- Use an LLM planner now: rejected because provider selection and replay gates
  first require deterministic contracts and security limits.
- Claim metadata parsers as OCR/ASR: rejected as technically false.

## Consequences and risks

The core is replaceable and reproducible, and optional libraries can be absent
without breaking base imports. Costs include more contracts, snapshot churn on
legitimate code changes, PDF extraction-order risk, platform-specific symlink
tests, and no defense against malicious explicitly enabled Python at the OS
level. Large-scale performance remains unvalidated.

## Migration and reversibility

Catalog schema 1.1 additively introduces `ingestion`; frozen catalog schema 1.0
and the original 20 schemas remain available byte-for-byte. Old ProjectLocks
become stale and must be regenerated; Domain Pack locks do not change.
Ingestion modules and new catalog entries can be removed in a later compatible
release without rewriting retained modeling/compiler behavior, provided stored
Prompt 3 artifacts are migrated or retained with their schemas.
