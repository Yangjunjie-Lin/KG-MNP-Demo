# Current Capability Matrix

This matrix records repository state at Prompt 3. “Implemented” means exercised
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
| Public Contract Catalog | One packaged Catalog and deterministic Catalog Lock bind 34 public Draft 2020-12 schemas; the frozen 1.0 catalog schema remains byte-identical and catalog schema 1.1 adds `ingestion`. |
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
| Field-to-Ontology Mapping | Planned for Prompt 4 proposal and human-review work. |
| LLM Proposal Provider | Planned and constrained to proposal authority. |
| Unified Review Experience | Planned; retained review behavior has not been rewritten. |
| New Compiler Kernel | Planned; the retained deterministic compiler remains in place. |
| Final Versioned Ontology Package | Planned; Artifact Manifest v1 is only a constrained file-set manifest. |
| Semantic Diff | Planned for controlled evolution; existing amendment diff is not represented as the final semantic diff. |
| Unified REST API | Planned after contracts stabilize. |
| Unified Workbench | Planned; current read-only Workbench is retained and has not been rewritten. |
| Forestry Domain Pack Implementation | Planned; the formal manifest declares zero capabilities and assets, with no fabricated forestry content. |
| Generic GraphDB Backend | Planned; the retained concrete GraphDB integration is not a generic backend abstraction. |

## OUT_OF_SCOPE

| Capability | Reason |
|---|---|
| Agent as semantic authority | Violates the authority boundary. |
| Direct AI writes to released OWL/RDF/SHACL/ABox | Violates review and deterministic compilation controls. |
| Autonomous production self-evolution | Feedback must become a reviewed Change Proposal and controlled release. |
| Core business execution platform | Execution belongs to integration adapters, not the ontology toolchain kernel. |
| Universal industry claims | Capabilities must be validated by concrete Domain Packs and evidence. |
