# Ontology Toolchain Target Architecture

This is the target product architecture. Shaded boundaries distinguish the
deterministic semantic authority, plugin extension points, and domain content.
Solid arrows carry governed artifacts; dashed arrows carry control or adapter
requests. Prompt 1 establishes boundaries and migration foundations only.

```mermaid
flowchart TB
  subgraph UI[User Interfaces]
    WB[Workbench]
    CLI[CLI]
    REST[REST API]
    SDK[Python SDK]
  end

  subgraph CP[Project Control Plane]
    PROJECT[Project / Configuration]
    POLICY[Policy and Quality Gates]
    REVIEW[Human Review]
  end

  subgraph DATA[Data and Evidence Pipeline]
    SOURCE[Source Assets]
    INGEST[Ingestion Providers]
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
    PREG[Plugin Registry]
    PROVIDERS[Ingestion / Proposal / Store / Visualization Providers]
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

  PREG -. loads .-> PROVIDERS
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
