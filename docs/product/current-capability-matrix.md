# Current Capability Matrix

This matrix records repository state at Prompt 5. “Implemented” means exercised
by retained code and tests; it does not mean the capability is already generic,
packaged as a stable public API, or validated across industries.

## IMPLEMENTED_AND_RETAINED

| Capability | Evidence and boundary |
|---|---|
| ModelingProposal | Versioned schema, deterministic generation, validation, and tests exist. It remains a proposal, not authority. |
| ReviewDecisionLog | Review actions, policy, deterministic log, security validation, and tests exist. |
| ConfirmedModelingPackage | Confirmation, readiness, closure, hashing, and reconstruction tests exist. |
| Deterministic RDF generation | The retained compiler produces canonical N-Triples/N-Quads and deterministic Turtle/TriG. |
| OWL/SHACL validation | Local OWL consistency and SHACL profiles/reports are exercised by offline tests. |
| Provenance | Modeling provenance and review-audit graphs are compiled and coverage-tested. |
| Publication verification | Publication packages can be reconstructed, verified, and attested offline. |
| Activation/rollback governance | Registry, state transition, pointer, concurrency, rollback, resolver, and attestation logic exist. |
| Public Contract Catalog | One packaged Catalog and deterministic Catalog Lock bind 83 public Draft 2020-12 schemas; all 59 pre-Prompt-5 schema bytes remain unchanged and the compilation family is additive. |
| Offline Contract Registry | Package-local `$ref` resolution, schema self-validation, and payload validation run without network retrieval. |
| Artifact Reference/Manifest v1 | Public identity and constrained immutable-file-set contracts exist; they do not represent review or the final ontology package. |
| Formal DomainPackManifest v1 | Formal manifests govern `minimal`, `mnp`, and `forestry` with explicit honest lifecycle states. |
| DomainPackLock v1 | Deterministic raw/semantic manifest hashes, asset hashes, dependency closure, content digest, and lock identity are implemented. |
| Local Domain Pack Registry | Explicit local roots, exact versions, capability checks, dependency closure, and cycle/conflict rejection are implemented; remote download is not. |
| ProjectManifest v1 | Exact Pack selection, profiles, and closed offline/strict settings are implemented. |
| ProjectLock v1 | The Project manifest, Contract Catalog, and resolved Pack closure are deterministically bound without time or absolute paths. |
| Project Workspace v1 | Transactional init, exact layout, open/validate/status/inspect/lock, and path/symlink/authority checks are implemented. Empty future artifact directories do not imply their later capabilities. |
| Contract/Pack/Workspace CLI | `kg-mnp contracts`, `domain-pack`, and `workspace` provide stable JSON envelopes and documented exit codes. |
| Plugin SDK v1 and Local Plugin Registry | Frozen request/response models, Protocols, metadata-only discovery, explicit external allowlisting, deterministic selection, snapshots and conformance are implemented. Installed Python plugins are trusted code, not an OS sandbox. |
| Source Content Store | SourceAsset/SourceBatch records bind content-addressed blobs without absolute source paths or timestamps. |
| SourceLocator and EvidenceRecord | Fourteen locator types and core-authoritative deterministic evidence/transformation closure are implemented. Evidence is observation, not confirmed knowledge. |
| Deterministic Ingestion Planner | The core planner binds finite limits, selected provider snapshots and policies. It is not an Agent or LLM planner. |
| Structured document parsers | TXT, Markdown, JSON, CSV/TSV, XLSX, DOCX and PDF text parsing plus image/WAV metadata are implemented with bounded security checks. OCR, ASR and video understanding are absent. |
| KG-IR and structural quality gate | Every intermediate item is evidence-bound; ontology/business-object kinds are prohibited. PASS/REVIEW_REQUIRED/FAIL are structural policy outcomes, not semantic accuracy. |
| Ingestion CLI | `kg-mnp plugin`, `source`, `ingest` and `ir` expose stable JSON envelopes and trace KG-IR to source blobs, snapshots and transformations. |
| Ontology Scope and Approval | Immutable scope, namespace/IRI policy, human approval semantic hash, and stale protection gate every provider run; no auto-approval exists. |
| Competency Questions | Closed question sets and structural coverage reports exist; the report explicitly does not claim CQ execution. |
| Baseline and Terminology | Locked local baseline snapshots and indexes, multi-source terminology, exact/normalized/alias/lexical alignment, ambiguity handling, and cross-path determinism are implemented without remote import. |
| Modeling Provider API 1.1 | `modeling-provider` manifests, immutable requests, proposal-only responses, snapshots, conformance, metadata-only external discovery, default disablement, and explicit enablement are implemented while API 1.0 remains compatible. |
| Offline Modeling Providers | Manual, baseline-reuse, rule-mapping, and recorded-model-output providers are implemented with denied network access and Core-owned candidate IDs. Recorded output is not live LLM invocation. |
| Closed Ontology Candidates | TBox, Mapping, ABox, and SHACL candidate bodies, evidence/KG-IR/baseline/provider closure, normalization, multi-provider merge, and deterministic conflict detection are implemented. |
| Formal Prevalidation | Thirty named structural, authority, closure, namespace, conflict, and resource checks emit PASS/REVIEW_REQUIRED/FAIL without claiming OWL, SHACL, or CQ final validation. |
| Human Review Control Plane | Dependency-ordered queues, development and production policies, explicit decisions, immutable revisions, append-only hashes, replay, stale/cross-project protection, role/quorum gates, and fail-closed finalization are implemented. |
| Prompt 4 Confirmed Modeling Package | Deterministic separated reviewed candidates and complete closure are emitted only as `READY_FOR_COMPILATION`; RDF, publication, registry, GraphDB, scripts, secrets, paths, and current-time identity are prohibited. |
| Model and Review CLI | `kg-mnp model` and `kg-mnp review` expose the Prompt 4 workflow without accept-all, auto-review, live-LLM, bypass, or force-finalize routes. |
| Compiler Input Attestation | The current confirmed package and every declared Workspace authority are reconstructed against current Project, Catalog, Domain Pack, evidence, candidate, and review locks; stale, duplicate, cross-project, or tampered authority fails closed. |
| Semantic Compiler Policy and Snapshot | Compiler 0.5.0 binds finite resource limits, canonicalization/skolemization profiles, package rules, implementation resources, dependencies, and the pinned local reasoner bundle without timestamps or host paths. |
| Deterministic Compilation Plan | Explicit package and ontology versions, candidate dispatch, named-graph roles, validation profiles, expected artifacts, and all finite limits are bound into a deterministic plan before RDF is written. |
| Generic semantic compilation | The same Domain-Pack-neutral kernel compiles confirmed TBox, ABox, safe SHACL Core, and a non-executable declarative MappingPlan; unsupported confirmed types and action/partition mismatches fail closed. |
| Canonical named RDF dataset | Blank-node-free generated graphs use canonical NT/NQ as semantic digest authority and deterministic TTL/TriG as round-trip-equivalent readable views. Graph IRIs bind package identity, role, and graph digest. |
| Formal validation gates | Pinned local ROBOT/HermiT OWL profile/consistency, isolated pySHACL, explicit read-only CQ queries with oracles, RDF round-trip, and provenance closure must all pass before a package is committed. |
| Statement provenance and evidence lineage | New statements bind confirmed items, candidates, review decisions, compiler activity, KG-IR/evidence/source closure, or locked baseline assets without inventing evidence. |
| Versioned Ontology Package | A portable closed-set Manifest and Lock produce only `VALIDATED_UNPUBLISHED`; strict verification reconstructs source authorities, named graphs, semantic identity, reports, payload bytes, and prohibited-content rules. |
| Deterministic `.kgop` export | Fixed ZIP ordering, timestamps, permissions, compression, path rules, duplicate detection, bomb limits, and independent verification provide byte-reproducible offline exports. |
| Compile and Package CLI | `kg-mnp compile` and `kg-mnp package` expose attestation, planning, build, validation, reproduction, inspection, export, and archive verification without registration, publication, activation, repair, or automatic versioning. |

## IMPLEMENTED_BUT_REQUIRES_REFACTOR

| Capability | Required refactor |
|---|---|
| GraphDB integration | Decouple MNP packages, commercial runtime assumptions, and a concrete backend from the core. |
| Workbench | Consolidate the read-only prototype into a toolchain workbench after public contracts stabilize. |
| Diagnostics | Generalize authority loading and domain constraints. |
| Governance | Reframe operational governance around toolchain projects and controlled release. |
| Amendment | Replace application-specific amendment semantics with Change Proposals and semantic diff. |
| Activation | Align activation artifacts with the future package registry and workspace contracts. |
| Stage/Phase CLI | Retire numbered routing without rewriting the complete CLI in Prompt 1. |
| MNP-specific path assumptions | Use centralized repository/domain/runtime resolution and later move remaining coupling behind Domain Pack contracts. |
| Eligibility internals | Retained temporarily for regression only; public eligibility console entry is removed and relocation remains pending. |

## PLANNED

| Capability | Status |
|---|---|
| LLM Ingestion Planner | Planned; Prompt 3 implements only the deterministic core planner. |
| OCR/Vision/ASR/Video providers | Planned optional providers; metadata parsers do not claim semantic understanding. |
| Live LLM Proposal Provider | Not implemented; only offline recorded model bytes can be imported and remain proposals. |
| Unified Review Experience | Planned; the Prompt 4 review CLI/control plane is implemented, but no unified Workbench experience is claimed. |
| Semantic Diff | Planned for controlled evolution; existing amendment diff is not represented as the final semantic diff. |
| Automatic SemVer Classification | Planned; Prompt 5 requires the operator to supply ontology and package versions explicitly. |
| Package Registry Rewrite | Planned; Prompt 5 verifies packages but never registers them. |
| Release Publication | Planned; `VALIDATED_UNPUBLISHED` is not a release state. |
| Version Activation and Rollback Rewrite | Planned against the future package registry; retained historical lifecycle code is not Prompt 5 authority. |
| Unified REST API | Planned after contracts stabilize. |
| Unified Workbench | Planned; current read-only Workbench is retained and has not been rewritten. |
| Forestry Domain Pack Implementation | Planned; the formal manifest declares zero capabilities and assets, with no fabricated forestry content. |
| Generic GraphDB Backend | Planned; the retained concrete GraphDB integration is not a generic backend abstraction. |
| OMS/ODS/OSS adapters and Business Actions | Planned outside the semantic compiler authority; Prompt 5 performs no business execution. |
| Feedback Object and Controlled Evolution | Planned; compiler failures never trigger automatic ontology repair or model calls. |
| Full Stage/Phase Cleanup | Planned separately so retained historical gates and public compatibility remain testable. |

## OUT_OF_SCOPE

| Capability | Reason |
|---|---|
| Agent as semantic authority | Violates the authority boundary. |
| Direct AI writes to released OWL/RDF/SHACL/ABox | Violates review and deterministic compilation controls. |
| Autonomous production self-evolution | Feedback must become a reviewed Change Proposal and controlled release. |
| Core business execution platform | Execution belongs to integration adapters, not the ontology toolchain kernel. |
| Universal industry claims | Capabilities must be validated by concrete Domain Packs and evidence. |
