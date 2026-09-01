# Ontology Toolchain Target Architecture

This is the target product architecture. Shaded boundaries distinguish the
deterministic semantic authority, plugin extension points, and domain content.
Solid arrows carry governed artifacts; dashed arrows carry control or adapter
requests. Prompts 2–5 implement the Contract Kernel, local Domain Pack Registry,
Project Workspace, local Plugin Registry, evidence-bound ingestion, and the
evidence-grounded modeling/review control plane through a deterministic
compiler-ready package, then the deterministic semantic kernel and portable
`VALIDATED_UNPUBLISHED` package boundary. The remaining lifecycle and interface
boxes are not implied to be implemented by their presence in this diagram.

```mermaid
flowchart TB
  subgraph UI[User Interfaces]
    WB[Workbench]
    CLI[CLI]
    REST[REST API]
    SDK[Python SDK]
  end

  subgraph CP[Project Control Plane]
    PROJECT[Project Workspace v1]
    CONTRACTS[Contract Catalog / Offline Registry]
    LOCKS[Project and Pack Locks]
    POLICY[Policy and Quality Gates]
    REVIEW[Human Review]
  end

  subgraph DATA[Data and Evidence Pipeline]
    SOURCE[Source Assets]
    INGEST[Deterministic Ingestion Plan and Providers]
    EVIDENCE[Evidence Records]
    KGIR[Evidence-bound KG-IR]
  end

  subgraph MODEL[Ontology Modeling Pipeline]
    SCOPE[Approved Scope and CQs]
    BASE[Baseline and Terminology]
    PROVIDER[Proposal-only Modeling Providers]
    PROPOSAL[Modeling Proposal]
    PREVALIDATE[Formal Pre-validation]
    CONFIRMED[Confirmed Modeling Package]
  end

  subgraph AUTH[Semantic Authority Boundary]
    ATTEST[Compiler Input Attestation]
    SNAPSHOT[Pinned Compiler Snapshot]
    PLAN[Deterministic Compilation Plan]
    COMPILER[TBox / ABox / SHACL / Mapping Compiler]
    FORMAL[Canonical Named Graph Dataset and Provenance]
  end

  subgraph VALIDATION[Formal Validation Boundary]
    RDFV[RDF Syntax and Round-trip]
    OWLV[OWL Profile and HermiT Consistency]
    SHV[Final SHACL]
    CQV[Explicit CQ Oracles]
    PROVV[Provenance Closure]
  end

  subgraph PKG[Package Boundary]
    PACKAGE[Manifest and Lock]
    UNPUBLISHED[VALIDATED_UNPUBLISHED .kgop]
  end

  subgraph LIFE[Registry and Lifecycle]
    REGISTRY[Package Registry]
    DIFF[Semantic Diff]
    RELEASE[Controlled Release]
    ROLLBACK[Rollback]
  end

  subgraph PLUG[Plugin Extension Boundary]
    PREG[Local Plugin Registry - Ingestion Implemented]
    PROVIDERS[Ingestion Implemented / Other Providers Planned]
  end

  subgraph DOMAIN[Domain Content Boundary]
    DREG[Domain Pack Registry]
    MNP[MNP Domain Pack]
    FORESTRY[Forestry Domain Pack - Planned]
    FUTURE[Future Domain Packs]
  end

  STORE[(Artifact Store)]

  subgraph ADAPTERS[Integration Adapters]
    GAD[GraphDB Adapter]
    VAD[WebVOWL Adapter]
    OMS[OMS Adapter]
    OQ[Object Query Adapter]
    AW[Action Workflow Adapter]
  end

  GRAPHDB[(GraphDB)]
  WEBVOWL[WebVOWL]
  EXTERNAL[OMS / ODS / OSS]

  WB -. control .-> PROJECT
  CLI -. control .-> PROJECT
  REST -. control .-> PROJECT
  SDK -. control .-> PROJECT
  CONTRACTS -. validates .-> PROJECT
  PROJECT -. binds .-> LOCKS
  LOCKS -. pins .-> DREG
  PROJECT -. orchestrates .-> INGEST
  PROJECT -. applies .-> POLICY
  POLICY -. gates .-> PREVALIDATE
  REVIEW -. confirms .-> CONFIRMED

  SOURCE -->|artifact| INGEST -->|artifact| EVIDENCE -->|artifact| KGIR
  KGIR -->|untrusted evidence| PROVIDER
  SCOPE -. controls .-> PROVIDER
  BASE -->|locked reuse context| PROVIDER
  PROVIDER -->|candidate drafts| PROPOSAL -->|artifact| PREVALIDATE
  PREVALIDATE -->|review packet| REVIEW
  REVIEW -->|decision artifact| CONFIRMED
  CONFIRMED -->|only new semantic input| ATTEST --> SNAPSHOT --> PLAN --> COMPILER
  BASE -->|locked local closure| COMPILER
  COMPILER --> FORMAL --> RDFV --> OWLV --> SHV --> CQV --> PROVV
  PROVV --> PACKAGE --> UNPUBLISHED
  UNPUBLISHED -. future Prompt 6 input .-> REGISTRY --> DIFF --> RELEASE --> ROLLBACK
  UNPUBLISHED --> STORE
  ATTEST -->|FAIL| FAILURE[Transactional failure report]
  PLAN -->|FAIL| FAILURE
  RDFV -->|FAIL| FAILURE
  OWLV -->|FAIL| FAILURE
  SHV -->|FAIL| FAILURE
  CQV -->|FAIL| FAILURE
  PROVV -->|FAIL| FAILURE
  EVIDENCE --> STORE
  PROPOSAL --> STORE

  PREG -. explicitly enables .-> PROVIDERS
  PROVIDERS -. extends .-> INGEST
  PROVIDERS -. proposes only .-> PROVIDER
  DREG -. selects .-> MNP
  DREG -. selects .-> FORESTRY
  DREG -. selects .-> FUTURE
  MNP -->|domain artifacts| INGEST
  MNP -->|constraints| PREVALIDATE
  FORESTRY -->|future domain artifacts| INGEST
  FUTURE -->|future domain artifacts| INGEST

  RELEASE -. adapter control .-> GAD
  RELEASE -. adapter control .-> VAD
  RELEASE -. adapter control .-> OMS
  RELEASE -. adapter control .-> OQ
  RELEASE -. adapter control .-> AW
  GAD -->|package projection| GRAPHDB
  VAD -->|TBox projection| WEBVOWL
  OMS -. integration .-> EXTERNAL
  OQ -. read/query .-> EXTERNAL
  AW -. action request .-> EXTERNAL

  classDef authority fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px;
  classDef plugin fill:#e3f2fd,stroke:#0d47a1,stroke-dasharray:5 5;
  classDef domain fill:#fff3e0,stroke:#e65100,stroke-dasharray:5 5;
  class ATTEST,SNAPSHOT,PLAN,COMPILER,FORMAL,RDFV,OWLV,SHV,CQV,PROVV,PACKAGE,UNPUBLISHED authority;
  class PREG,PROVIDERS plugin;
  class DREG,MNP,FORESTRY,FUTURE domain;
```

## Boundary rules

- **Control flow** coordinates providers, policies, reviews, registries, and
  adapters; it does not create formal semantics by itself.
- **Artifact flow** moves immutable or versioned evidence, proposals, decisions,
  compilation inputs, outputs, reports, and packages.
- **Semantic authority** begins only at a reviewed Confirmed Modeling Package.
  The deterministic kernel owns formal generation and validation.
- **Plugin extension** may ingest, extract, propose, store, visualize, or
  integrate, but cannot bypass authority gates.
- **Domain content** is supplied by Domain Packs. No domain pack becomes the
  core compiler or a universal ontology.

## Prompt 2–5 implemented slice

The Contract Catalog and all public schemas are package resources accessed via
`importlib.resources`; they do not depend on the repository root or current
working directory. Registry resolution is package-local and offline. Formal
Domain Pack manifests are data-only, validated against executable content and
path escape, and locked to exact bytes and dependency closure. Project
Workspace v1 transactionally creates the filesystem boundary and binds its
Project Manifest to the Contract Catalog and exact Pack locks.

Prompt 3 activates only the `sources`, `artifacts/evidence`, `artifacts/ir`, and
`artifacts/validation` ingestion paths. The Source Store is content-addressed;
the deterministic planner binds provider snapshots; Core binds every accepted
observation to a SourceLocator, EvidenceRecord, and TransformationRecord before
building KG-IR. Structural quality can pass, require review, or fail. Image and
WAV support is metadata-only, while unsupported video, non-WAV audio, scanned
documents, and unavailable semantic providers remain unresolved or require
review without invented text.

Prompt 4 activates descendants under the existing modeling build, proposal,
review, and confirmed artifact roots. Approved Scope/CQs and a locked baseline
control Plugin API 1.1 proposal providers; Core normalizes closed candidates and
prevalidates them; humans decide through a replayable append-only log; and only
a non-RDF `READY_FOR_COMPILATION` package crosses the review boundary. The
package and release-registry authorities remain untouched.

Prompt 5 attests only the current confirmed package and its closed Workspace
authorities, snapshots the compiler and pinned local ROBOT/HermiT bundle, and
binds explicit versions and finite limits into a deterministic plan. The same
Domain-Pack-neutral kernel compiles TBox, ABox, safe SHACL Core, MappingPlan,
named graphs, provenance, audit, and evidence lineage. RDF, OWL, SHACL,
executable CQ oracles, provenance closure, package integrity, and reproduction
are fail-closed gates. Package commit is transactional and produces only
`VALIDATED_UNPUBLISHED`; no failure edge returns to providers, candidates, an
LLM, or a Domain Pack for automatic repair.

No live LLM, OCR/vision/ASR/video understanding, semantic diff, automatic SemVer
classification, Package Registry rewrite, controlled publication, activation
rewrite, REST, Workbench replacement, Forestry content, or generic GraphDB
backend is claimed. See `plugin-driven-ingestion-architecture.md` for Prompt 3,
`evidence-grounded-modeling-architecture.md` for Prompt 4, and
`deterministic-semantic-kernel-architecture.md` for Prompt 5.
