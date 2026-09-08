# ADR-0002: Public Contract, Domain Pack, and Workspace Kernel

> 长期权威与契约原则继续采用；下列历史输入格式、旧 CLI/平台共存及未来阶段实施条款已被当前契约和入口迁移部分替代。本文保留当时的决策背景，不代表当前功能状态。参见[迁移结论](../migration/history-and-current-boundaries.md)与[当前架构](../architecture/toolchain.md)。

## Context

The retained implementation had strong local Modeling validation but a
source-tree registry, provisional Pack metadata, MNP path coupling and no final
Project Workspace contract. Later prompts would otherwise invent incompatible
formats and authority shortcuts.

## Decision

Freeze one packaged public Contract Kernel, DomainPackManifest/Lock v1, and
ProjectManifest/Lock/Workspace v1. Keep internal Stage/Phase schemas in place
until separately migrated. Make every new resolver local-only and fail-closed.

## Why a single Contract Kernel

One catalog provides unique names, identifiers, resources, versions and
digests. Modeling APIs filter and delegate to it; they do not own another list.
This prevents behavior and digest drift between product modules.

## Why Domain Packs are data-only

Packs cross a supply-chain trust boundary. Executable code could bypass review,
network and compiler controls. Packs therefore contain only declared knowledge,
constraints, queries, fixtures and documentation, and no executable payload.

## Why Workspace locks exact Pack versions

Projects must be reproducible and reviewable. Exact version, content digest,
capability and dependency closure eliminate ambient “latest” resolution and
make Pack tampering visible.

## Why Locks omit wall-clock time

Time and machine state are not semantic inputs. Omitting them makes equal
content byte-stable across repeated runs and absolute directories.

## Why remote resolution is forbidden by default

Network retrieval makes validation non-reproducible and introduces mutable
third-party input. Schemas, Packs and ontology import declarations must close
locally; remote download/registry policy is future, explicit work.

## Why Agent/LLM cannot become semantic authority

Models may propose or explain. They cannot attest human review, confirm an
artifact, compile formal semantics, mutate releases, or turn feedback into
published ontology changes.

## Alternatives Considered

Per-module schemas were rejected because they fragment compatibility. Remote
registries were deferred because they add signing, transport and cache policy.
Executable Pack hooks were rejected because they violate the trust boundary.
Path-based project configuration was rejected because it is non-portable and
can bypass declared assets.

## Consequences

Public schema evolution now requires versioned catalog work. Packs must fully
declare semantic content. Projects fail when locks or the Catalog change. The
benefit is deterministic, installable, auditable behavior shared by Prompts
3–9.

## Migration

The eleven Modeling schemas move byte-for-byte into package resources. Their
Python modules become compatibility wrappers. Minimal gains small real test
assets, MNP gains a formal manifest/lock without semantic edits, and Forestry
remains PLANNED. Retained internal schemas are marked deferred.

## Risks

Raw hashes require normalized repository text bytes. Large MNP manifests are
verbose. Exact dependencies intentionally avoid a general SemVer solver.
Status classification must remain stable as later authoritative workflows are
added.

## Reversibility

The new modules and resources can be reverted as a branch without rewriting
Prompt 1 or the historical tag. Once consumers publish v1 documents, changes
must proceed by versioned migration rather than in-place mutation.
