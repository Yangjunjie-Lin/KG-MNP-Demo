# KG-MNP Ontology Toolchain

> Evidence-bound, review-governed and deterministic ontology engineering toolchain

**Current status:** Prompt 8 backend remediation in progress — `NO_GO_BACKEND_NOT_READY`.
The requested **KG-MNP Ontology Workbench / KG-MNP 本体工程工作台** is not yet
delivered. The operation catalogue is not a completed HTTP business workflow.
See [Prompt 8 report](docs/verification/prompt-08-final-report.md) and
[service recovery/run instructions](docs/workbench/backend-remediation.md).

KG-MNP is being repositioned as a pluggable, verifiable and traceable ontology
engineering toolchain. It converts heterogeneous source material into
evidence-bound modeling candidates, subjects those candidates to formal checks
and human review, and allows only a deterministic semantic compiler to produce
authoritative ontology artifacts.

Prompt 4 closes the evidence-to-review loop and produces a deterministic
`READY_FOR_COMPILATION` Confirmed Modeling Package. Prompt 5 now attests that
input and deterministically compiles it into a portable **Versioned Ontology
Package** whose only successful state is `VALIDATED_UNPUBLISHED`. Registration,
release, activation, rollback, and semantic-version classification remain
separate lifecycle work; the package is not a publication or deployment.

## What is implemented now

- Compiler Input Attestation against the current Project Lock, Contract Catalog,
  Domain Pack locks, review log, evidence closure, and confirmed partitions;
- a deterministic Semantic Compiler Snapshot and explicit Compilation Plan with
  finite resource limits and user-supplied ontology/package versions;
- generic TBox, ABox, safe SHACL Core, and declarative MappingPlan compilation;
- canonical N-Triples/N-Quads plus deterministic Turtle/TriG named-graph views;
- statement provenance, review audit, evidence lineage, and 100% provenance
  closure validation;
- pinned local ROBOT 1.9.7/HermiT OWL 2 DL profile and consistency gates,
  isolated final pySHACL validation, and explicit read-only CQ execution;
- a closed-set Ontology Package Manifest and Lock, independent verification,
  transactional build behavior, and deterministic portable `.kgop` export;
- `kg-mnp compile` and `kg-mnp package` CLI routes without publication,
  registration, activation, force, repair, or automatic-version options;
- `ModelingProposal`, `ReviewDecisionLog`, and `ConfirmedModelingPackage`
  contracts and validation;
- review-governed confirmation with deterministic identifiers and hashes;
- deterministic RDF/Turtle/TriG generation from confirmed packages;
- OWL consistency and SHACL validation;
- modeling provenance and review-audit artifacts;
- publication reconstruction and verification;
- activation and rollback governance;
- offline GraphDB packaging and a read-only application/workbench baseline;
- a packaged Public Contract Catalog with 115 Draft 2020-12 schemas and a
  fully offline Registry;
- Artifact Reference, Artifact Manifest, and Validation Report v1 contracts;
- formal DomainPackManifest/DomainPackLock v1 contracts, local discovery,
  exact-version dependency resolution, validation, and deterministic locks;
- ProjectManifest/ProjectLock and transactional Project Workspace v1; and
- Plugin SDK v1, metadata-only installed-distribution discovery, explicit
  external allowlisting, deterministic provider selection and snapshots;
- content-addressed SourceAsset/SourceBatch storage with bounded local file and
  directory registration;
- deterministic media detection and real TXT, Markdown, JSON, CSV/TSV, XLSX,
  DOCX, PDF, image-metadata and WAV-metadata parsers;
- core-authoritative SourceLocator, TransformationRecord, EvidenceRecord,
  structural QualityReport, IngestionPlan/Run and evidence-bound KG-IR;
- transactional ingestion artifacts integrated with ArtifactReference and
  ArtifactManifest; and
- `kg-mnp plugin`, `source`, `ingest`, and `ir` CLI routes in addition to the
  Prompt 2 routes;
- approved Ontology Scope and stale-safe human Scope Approval;
- Competency Question Sets and explicitly structural-only coverage;
- locked local Ontology Baseline Snapshots, terminology catalogs, and
  deterministic reviewed term alignments;
- Plugin API 1.1 and four offline, proposal-only modeling providers: manual,
  baseline reuse, rule mapping, and recorded model output;
- Core-owned TBox, Mapping, ABox, and SHACL candidate normalization, identity,
  evidence closure, multi-provider merge, and conflict detection;
- 30-check formal structural prevalidation with finite Modeling Run limits;
- dependency-ordered human review queues, role/quorum policy, append-only action
  chains, candidate revision, replay, and separate semantic/operational hashes;
- a deterministic, non-RDF Confirmed Modeling Package with the sole status
  `READY_FOR_COMPILATION`; and
- explicit `kg-mnp model` and `kg-mnp review` CLI routes while the legacy
  modeling route remains compatible.
- Prompt 6 lifecycle repair gates for real package regression, release review,
  publication, attestation, audited activation, and explicitly selected
  historical rollback;
- a single Prompt 7 Operation Catalog and Application Service shared by the
  local CLI, Local SDK, HTTP SDK, and REST API;
- local server-managed bearer credentials, project/object authorization,
  durable SQLite jobs with idempotency and fencing, and append-only service
  audit records;
- local RDF/OMS/ODS readers, WebVOWL JSON export, GraphDB protocol planning,
  SSRF/target policy checks, and a workflow outbox that does not claim remote
  execution success.

These capabilities are retained from the historical implementation. Some are
still coupled to MNP paths or the former staged command structure and therefore
remain refactor targets.

## What is not implemented yet

The repository does not provide a live LLM provider, LLM planner, OCR, vision
classification, ASR, video understanding, automatic SemVer classification, a
unified Workbench, or an externally live GraphDB/WebVOWL deployment. Recorded
model output is an offline import, not a model call. The Prompt 7 API is a
governed service boundary; catalogue items without a core implementation are
explicitly blocked.
Image and WAV support is metadata-only; scanned PDFs and unsupported audio/video
require review or a missing provider. The Forestry Domain Pack remains a
planning scaffold only.
No Agent or LLM is an ontology authority.

## Semantic authority

1. LLMs and Agents may create proposals, explanations, or recommended fixes.
2. They may not write authoritative OWL, RDF, SHACL, or production ABox data.
3. Unreviewed candidates cannot enter a Confirmed Modeling Package.
4. Only the deterministic semantic compiler may generate formal semantic
   artifacts from a confirmed package.
5. Feedback creates a Change Proposal; it cannot mutate a released ontology.
6. Domain content enters through Domain Packs. OMS, ODS, OSS, GraphDB, WebVOWL,
   object-query, and action-workflow systems are integration adapters, not
   compilation authorities.

## Architecture

```text
Source Assets -> Evidence-bound KG-IR -> Approved Scope + CQ + Locked Baseline
    -> Proposal-only Providers -> Modeling Proposal
    -> Formal Structural Pre-validation -> Explicit Human Review
    -> Confirmed Modeling Package -> Deterministic Semantic Compiler
    -> OWL / RDF / SHACL / Provenance -> OWL / SHACL / CQ / Closure Validation
    -> VALIDATED_UNPUBLISHED Versioned Ontology Package
    -> Future Registry / Controlled Release / Activation / Rollback
```

See the [target architecture](docs/architecture/ontology-toolchain-target-architecture.md)
for the control, artifact, authority, plugin, and domain boundaries. See the
[Prompt 7 service architecture](docs/architecture/prompt-07-unified-services.md),
[operation coverage](docs/architecture/operation-coverage.md), and
[ADR-0007](docs/adr/ADR-0007.md) for the application boundary.

## Repository structure

```text
src/kg_mnp/             Python package, Contract Kernel, Workspace, and retained semantic kernel
domain_packs/           formal data-only DomainPackManifest v1 layout
  minimal/              experimental industry-neutral contract-test assets
  mnp/                  locked migrated historical MNP assets
  forestry/             planned scaffold; no forestry ontology or data
schemas/                retained internal Stage/Phase schemas; public Modeling schemas are packaged
config/                 generic policies and integration configuration
examples/               reviewed deterministic golden artifacts
tests/                  retained regression suite plus Prompt 1 foundation gates
docs/                   product, architecture, ADR, and migration evidence
scripts/                retained verification and historical migration utilities
```

## Local installation

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
python -c "import kg_mnp; print(kg_mnp.__name__)"
python -m kg_mnp --help
kg-mnp --help
```

The only public console script is `kg-mnp`. The former eligibility-specific
console entry is no longer part of the product surface. Retained eligibility
code is an internal MNP compatibility layer, not the toolchain's central task,
and is pending relocation or removal in a later Prompt.

## Verification

The Prompt 5 gates are offline and require no GraphDB service or browser:

```bash
python -m ruff check .
make verify-repo-hygiene
make verify-toolchain-foundation
make verify-contract-catalog
make verify-domain-packs
make verify-project-workspace
make verify-prompt-02-offline
make verify-plugin-sdk
make verify-source-store
make verify-ingestion-contracts
make verify-ingestion-parsers
make verify-evidence-kgir
make verify-ingestion-security
make verify-prompt-03-offline
make verify-modeling-scope
make verify-modeling-baseline
make verify-modeling-providers
make verify-modeling-candidates
make verify-modeling-prevalidation
make verify-modeling-review
make verify-modeling-confirmation
make verify-modeling-security
make verify-prompt-04-offline
make verify-semantic-kernel-contracts
make verify-compiler-input
make verify-tbox-compilation
make verify-abox-compilation
make verify-shacl-compilation
make verify-mapping-compilation
make verify-rdf-dataset
make verify-provenance-closure
make verify-owl-validation
make verify-shacl-final-validation
make verify-cq-execution
make verify-ontology-package
make verify-semantic-kernel-security
make verify-prompt-05-offline
make verify-stage-06
make verify-application-phase-06-offline
python -m pytest -q
```

Licensed or live integration targets remain separate and must not be reported
as passing unless their prerequisites are actually available.

## Domain Pack status

| Pack | Status | Meaning |
|---|---|---|
| `minimal` | `EXPERIMENTAL` | Real, minimal, industry-neutral assets for contract and boundary tests; not a production ontology. |
| `mnp` | `MIGRATED_BASELINE` | Historical MNP assets enumerated by a formal manifest and deterministic lock; not cross-industry or `STABLE`. |
| `forestry` | `PLANNED` | Placeholder for the forestry pilot requirement; contains no fabricated ontology, data, or validation result. |

## Documentation

- [Product Charter](docs/product/product-charter.md)
- [Current Capability Matrix](docs/product/current-capability-matrix.md)
- [Research-to-Product Alignment](docs/product/research-to-product-alignment.md)
- [Target Architecture](docs/architecture/ontology-toolchain-target-architecture.md)
- [Prompt 4 Modeling Architecture](docs/architecture/evidence-grounded-modeling-architecture.md)
- [Modeling Provider API](docs/modeling/modeling-provider-api.md)
- [Human Review Workflow](docs/modeling/human-review-workflow.md)
- [Contract and Workspace Kernel](docs/architecture/contract-and-workspace-kernel.md)
- [Public Contract Policy](docs/contracts/public-contract-policy.md)
- [Domain Pack Contract v1](docs/domain-packs/domain-pack-contract-v1.md)
- [Project Workspace v1](docs/workspaces/project-workspace-v1.md)
- [ADR-0001](docs/adr/ADR-0001-reposition-as-ontology-toolchain.md)
- [ADR-0002](docs/adr/ADR-0002-public-contract-domain-pack-and-workspace.md)
- [Prompt 1 Baseline Audit](docs/refactor/prompt-01-baseline-audit.md)
- [Repository Migration Matrix](docs/refactor/repository-migration-matrix.md)
- [Domain Packs](docs/domain-packs/README.md)

## Migration note

The former Stage 01–08 and Application Phase 01–06 route is preserved at the
immutable tag `kg-mnp-phase06-baseline-2026-08-30`. Git history and that tag are
the authoritative historical archive; no duplicate legacy source tree is kept.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
