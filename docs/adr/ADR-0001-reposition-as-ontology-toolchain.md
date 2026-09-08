# ADR-0001: Reposition KG-MNP as an Ontology Toolchain

> 长期权威与契约原则继续采用；下列历史输入格式、旧 CLI/平台共存及未来阶段实施条款已被当前契约和入口迁移部分替代。本文保留当时的决策背景，不代表当前功能状态。参见[迁移结论](../migration/history-and-current-boundaries.md)与[当前架构](../architecture/toolchain.md)。

- **Status:** Accepted
- **Date:** 2026-08-30
- **Baseline:** `kg-mnp-phase06-baseline-2026-08-30`

## Context

The repository proved a substantial semantic path around an MNP scenario:
evidence-aware proposals, review, confirmed packages, deterministic compilation,
validation, publication, diagnostics, governance, amendment, activation, and
rollback. Its product identity and directory layout nevertheless remained tied
to MNP eligibility, hard-coded repository paths, and an indefinitely expanding
numbered delivery model. Research goals now require a reusable ontology
engineering toolchain with explicit authority and extension boundaries.

## Decision

KG-MNP becomes **KG-MNP Ontology Toolchain**. Its core deliverable is a
Versioned Ontology Package generated only by a deterministic semantic compiler
from a human-confirmed modeling package. AI and Agents may propose and explain;
Domain Packs contain industry semantics; plugins and OMS/ODS/OSS integrations
remain outside the semantic authority boundary.

The Python distribution becomes `kg-mnp-toolchain`, the namespace becomes
`kg_mnp`, and `kg-mnp` is the sole public console entry. MNP authority assets
move from generic roots into `domain_packs/mnp`. Minimal and forestry packs are
truthfully labeled scaffolds.

## Alternatives considered

1. **Continue the current MNP product.** Rejected because it conflates a domain
   validation scenario with the reusable product boundary.
2. **Continue numbered Stage/Phase expansion.** Rejected because numbering
   expresses chronology rather than stable product capabilities and encourages
   parallel authority paths and duplicated closure gates.
3. **Allow Agent-authored production semantics.** Rejected because an opaque,
   probabilistic component cannot guarantee evidence closure, review approval,
   deterministic output, validation, or rollback safety.
4. **Keep domain assets in core for convenience.** Rejected because path-level
   coupling prevents honest cross-domain validation and makes MNP accidental
   global authority.
5. **Copy the old tree into an archive directory.** Rejected because Git history
   and the immutable baseline Tag provide the authoritative, auditable archive.

## Why the old Stage/Phase model is retired

The retained gates protected incremental work effectively, but further numbered
expansion would turn implementation history into permanent product architecture.
Existing gates remain temporarily to protect the semantic kernel; later prompts
will reorganize them by capability without inventing a new number.

## Why Agent is not semantic authority

Agents and LLMs are non-deterministic, provider-dependent, and may omit or
invent facts. Their output is therefore a Modeling Proposal that must retain
evidence and pass formal pre-validation and human review. The deterministic
compiler is the sole producer of authoritative OWL/RDF/SHACL/ABox artifacts.

## Why domain assets leave the core

Telecom vocabulary, eligibility rules, cases, mappings, queries, and shapes are
useful validation assets but not universal compiler logic. Moving them into an
MNP Domain Pack makes the boundary inspectable and creates an honest route for
forestry and future domains without contaminating the semantic kernel.

## Consequences

Positive consequences include a stable product identity, an explicit authority
model, clearer provenance and release responsibilities, and testable domain
separation. Costs include widespread import/path updates, temporary adapters for
historical modules, golden artifact regeneration where path metadata changes,
and a multi-prompt migration before public contracts stabilize.

## Migration plan

1. Freeze the verified historical baseline and establish product documentation.
2. Rename the package and distribution; centralize repository/domain/runtime
   path resolution.
3. Move MNP assets into a provisional Domain Pack and remove generated outputs.
4. Add foundation tests and CI while retaining older semantic gates.
5. In later prompts, freeze artifact/workspace/pack/plugin contracts and
   reorganize ingestion, review, compilation, registry, adapters, API, and UI.

## Risks

- Historical tests and golden artifacts still encode MNP and numbered names.
- Domain-coupled configuration may remain outside the pack until later prompts.
- A path-only move can change manifests even when RDF semantics are identical.
- Downstream users of the old namespace or eligibility console entry must
  migrate; no compatibility package is provided.
- The target architecture may be overclaimed unless planned capabilities stay
  visibly marked as planned.

## Reversibility

The decision is reversible through Git history and the annotated baseline Tag
`kg-mnp-phase06-baseline-2026-08-30`, which points to commit
`e45da340267de8d4b7b3a54177822aa641e3a601`. The Tag is the immutable historical
state; no archive or legacy directory is created.
