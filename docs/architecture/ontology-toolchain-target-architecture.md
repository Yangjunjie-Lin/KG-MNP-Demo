# Ontology Toolchain Target Architecture

This is the target product architecture. Shaded boundaries distinguish the
deterministic semantic authority, plugin extension points, and domain content.
Solid arrows carry governed artifacts; dashed arrows carry control or adapter
requests. Prompts 2 and 3 implement the Contract Kernel, local Domain Pack
Registry, Project Workspace control plane, local Plugin Registry, and the
evidence-bound ingestion slice. The remaining target boxes are not implied to
be implemented by their presence in this diagram.

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
    PROPOSAL[Modeling Proposal]
    PREVALIDATE[Formal Pre-validation]
    CONFIRMED[Confirmed Modeling Package]
  end

  subgraph AUTH[Semantic Authority Boundary]
    COMPILER[Deterministic Semantic Compiler]
    FORMAL[OWL / RDF / SHACL / Provenance]
    VALIDATE[Deterministic Validation]
    PACKAGE[Versioned Ontology Package]
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
  KGIR -->|artifact| PROPOSAL -->|artifact| PREVALIDATE
  PREVALIDATE -->|review packet| REVIEW
  REVIEW -->|decision artifact| CONFIRMED
  CONFIRMED -->|authoritative input| COMPILER --> FORMAL --> VALIDATE --> PACKAGE
  PACKAGE --> REGISTRY --> DIFF --> RELEASE --> ROLLBACK
  PACKAGE --> STORE
  EVIDENCE --> STORE
  PROPOSAL --> STORE

  PREG -. explicitly enables .-> PROVIDERS
  PROVIDERS -. extends .-> INGEST
  PROVIDERS -. proposes only .-> PROPOSAL
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
  class COMPILER,FORMAL,VALIDATE,PACKAGE authority;
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

## Prompt 2 and Prompt 3 implemented slice

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

The `proposal`, `review`, `confirmed`, `build`, `package`, and release-registry
authority boundaries remain unchanged. Prompt 3 does not implement an LLM
planner, OCR, vision, ASR, video understanding, a new review experience, an
ontology-modeling rewrite, final package assembly, semantic diff, REST,
Workbench replacement, Forestry content, or a generic GraphDB backend. For the
detailed implemented control and artifact flow, see
`plugin-driven-ingestion-architecture.md`.
