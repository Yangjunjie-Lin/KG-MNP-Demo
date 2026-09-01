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

The core deliverable is a **Versioned Ontology Package**. Prompt 5 implements
the first experimental package contract and its `VALIDATED_UNPUBLISHED` state.
It describes:

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
- deterministic package and semantic digests.

Release Attestation and Semantic Diff remain future lifecycle artifacts and are
deliberately absent from the Prompt 5 package authority.

Prompt 2 establishes Artifact Reference/Manifest v1 and Project Workspace v1
as shared identity, containment, and locking contracts. Prompt 3 adds the
Plugin SDK, content-addressed sources, Evidence Records, structural quality
gates, and evidence-bound KG-IR. Prompt 4 adds approved modeling scope,
competency questions, read-only baseline/terminology alignment, proposal-only
providers, closed candidates, formal prevalidation, explicit review replay, and
a deterministic Confirmed Modeling Package. Prompt 5 adds input attestation,
the pinned deterministic semantic kernel, TBox/ABox/SHACL/Mapping compilation,
OWL/SHACL/CQ/provenance gates, and a closed portable Ontology Package
Manifest/Lock with deterministic `.kgop` export. Artifact Manifest v1 remains
distinct from the Versioned Ontology Package contract; neither ingestion,
KG-IR, proposal, the compiler-ready package, nor `VALIDATED_UNPUBLISHED`
implies release, registration, activation, or publication.

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
controls. Prompt 4 Plugin API 1.1 adds only proposal-authority modeling
providers; Core still owns candidate IDs and every candidate remains subject to
human review.

### Traceability principle

Every accepted modeling decision must remain traceable through source
references, evidence, candidate identity, review decisions, compiled facts,
validation results, and release lineage.

### Deterministic build principle

Equivalent confirmed inputs and pinned dependencies must produce byte- or
semantically stable formal artifacts and hashes. Only the deterministic
semantic kernel may compile an authoritative package. The operator supplies
ontology and package versions explicitly; the compiler never repairs candidates
or infers a SemVer change. Canonical NT/NQ are digest authorities, while
deterministic Turtle/TriG are readable round-trip views.

### Formal validation and package boundary

A successful Prompt 5 package requires a valid input attestation, pinned
compiler snapshot and plan, RDF syntax/round-trip equivalence, the requested OWL
profile, HermiT consistency, final SHACL conformance, all REQUIRED CQ oracles,
and complete provenance closure. Failure leaves no valid package. The compiler
does not write GraphDB or a Package Registry and cannot publish or activate a
version.

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
- treating Artifact Manifest v1 as the Versioned Ontology Package Manifest;
- treating a `VALIDATED_UNPUBLISHED` package as registered, released, active,
  deployed, or semantically version-classified;
- treating ingestion observations or KG-IR as reviewed ontology or business
  objects;
- an LLM planner or fabricated OCR, vision, ASR, or video understanding;
- treating Workspace directory creation as implementation of review,
  compilation, publication, or package-registry behavior; and
- a general-purpose Python security sandbox.

## 2026–2027 research and product scope

The current foundation includes stable public artifact/workspace contracts,
formal local Domain Packs, Plugin APIs 1.0/1.1, deterministic local ingestion,
Evidence Records, evidence-bound KG-IR, approved modeling requirements,
baseline reuse, offline proposal providers, formal prevalidation, replayable
human review, a deterministic compiler-ready package, and the Prompt 5 semantic
compiler, formal validation gates, package lock, and deterministic offline
archive. Live LLM invocation, semantic diff, automatic SemVer classification,
the Package Registry rewrite, controlled publication, lifecycle rewrite,
unified interfaces, and an honest Forestry pilot remain planned. Delivery is
incremental, and planned capabilities must not be represented as implemented.
