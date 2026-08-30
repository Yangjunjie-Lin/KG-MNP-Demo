# KG-MNP Ontology Toolchain Product Charter

## Product definition

**Product name:** KG-MNP Ontology Toolchain

**Positioning:** A pluggable, verifiable and traceable domain ontology
engineering toolchain that binds modeling decisions to source evidence, human
review, deterministic compilation, validation, and controlled release.

**Primary users:** ontology engineers, semantic architects, domain experts,
data-governance reviewers, research engineers, and platform teams that publish
or consume governed semantic assets.

**User problem:** ontology programs must turn heterogeneous, incomplete, and
sometimes conflicting sources into formal artifacts without allowing an
opaque model or integration system to bypass evidence, review, validation, or
release governance.

## Core deliverable

The core deliverable is a **Versioned Ontology Package**. Its eventual public
contract is expected to describe, as applicable:

- TBox and ABox;
- SHACL Shapes;
- Mapping Rules;
- Terminology;
- Evidence and Source References;
- Review Decisions;
- Validation Reports;
- Competency Question Results;
- a Dependency Manifest;
- a Semantic Hash;
- a Release Attestation; and
- a Semantic Diff.

Prompt 2 establishes Artifact Reference/Manifest v1 and Project Workspace v1
as shared identity, containment, and locking contracts. Prompt 3 adds the
Plugin SDK, content-addressed sources, Evidence Records, structural quality
gates, and evidence-bound KG-IR. Artifact Manifest v1 remains distinct from the
final Versioned Ontology Package contract; neither ingestion nor KG-IR implies
review, confirmation, release, or publication authority.

## Product principles

### Semantic Authority Boundary

LLMs and Agents are advisory proposal providers. They may generate a Modeling
Proposal, explain a validation issue, or recommend a repair, but they cannot
write authoritative OWL, RDF, SHACL, or production ABox artifacts. OMS, ODS,
OSS, GraphDB, WebVOWL, object-query, and action-workflow systems are integration
adapters rather than semantic compilation authorities.

### Proposal versus confirmed artifact

A Proposal is an evidence-linked, reviewable candidate that may be incomplete,
ambiguous, or rejected. A Confirmed Artifact is derived only from explicit
human review decisions and a closed, validated Confirmed Modeling Package.
Unreviewed candidates never cross this boundary.

### Domain Pack principle

Domain vocabulary, mappings, shapes, rules, evidence profiles, competency
questions, and fixtures belong in Domain Packs. MNP, forestry, and future
industries extend the toolchain without becoming hard-coded core authorities.
Prompt 2 formalizes DomainPackManifest/DomainPackLock v1, local exact-version
resolution, and data-only validation. A Pack supplies content and constraints;
its manifest or lock does not make that content confirmed semantic authority.

### Plugin principle

Replaceable ingestion, extraction, proposal, storage, visualization, and
integration providers use explicit contracts and capability declarations.
Prompt 3 implements Plugin SDK v1 for local source, detection, parsing,
normalization, and structural-quality providers. Discovery reads metadata
without importing external implementations; external installed code is disabled
until explicitly allowed. A Python Plugin is trusted installed code, not an OS
sandbox, and cannot own authoritative Evidence or KG-IR identifiers. Plugins
cannot bypass confirmation, deterministic compilation, validation, or release
controls.

### Traceability principle

Every accepted modeling decision must remain traceable through source
references, evidence, candidate identity, review decisions, compiled facts,
validation results, and release lineage.

### Deterministic build principle

Equivalent confirmed inputs and pinned dependencies must produce byte- or
semantically stable formal artifacts and hashes. Only the deterministic
semantic kernel may compile an authoritative package.

### Controlled evolution principle

Execution feedback becomes a Feedback Issue and then, if authorized, a Change
Proposal. It is evaluated with semantic diff and regression validation before a
new controlled release. Published artifacts are never self-mutated.

## Current non-goals

- an MNP eligibility decision product;
- a forestry business-management platform;
- an Agent that executes business actions or edits production ontologies;
- autonomous ontology deployment after execution failure;
- claims of universal multimodal or cross-industry support;
- a new numbered Stage or Application Phase;
- treating Artifact Manifest v1 as the final Versioned Ontology Package;
- treating ingestion observations or KG-IR as reviewed ontology or business
  objects;
- an LLM planner or fabricated OCR, vision, ASR, or video understanding;
- treating Workspace directory creation as implementation of review,
  compilation, publication, or package-registry behavior; and
- a general-purpose Python security sandbox.

## 2026–2027 research and product scope

The current foundation includes stable public artifact/workspace contracts,
formal local Domain Packs, Plugin SDK v1, deterministic local ingestion,
Evidence Records, structural quality gates, and evidence-bound KG-IR. The
planned scope is to support constrained LLM proposal providers; consolidate
review, compilation, validation, registry, diff, release, and rollback
experiences; and validate the architecture with an honest forestry pilot Domain
Pack. Delivery remains incremental, and planned capabilities must not be
represented as implemented.
