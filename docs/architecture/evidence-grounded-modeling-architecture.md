# Evidence-Grounded Modeling Architecture

Prompt 4 turns approved requirements and untrusted evidence into a reviewed,
deterministic compiler input. Solid arrows carry artifacts; dashed arrows are
control decisions. The boundaries are authority boundaries, not process names.

```mermaid
flowchart LR
  subgraph DATA[Data / Evidence Boundary]
    KGIR[KG-IR Dataset]
    DP[Locked Domain Pack]
    BASE[Ontology Baseline]
    TERM[Terminology Catalog]
  end
  subgraph CONTROL[Project Control]
    SCOPE[Approved Scope]
    CQ[Competency Questions]
  end
  subgraph PROVIDER[Provider Proposal Boundary]
    MP[Modeling Providers]
    NORM[Candidate Normalizer]
    CONFLICT[Conflict Detector]
  end
  subgraph HUMAN[Human Authority Boundary]
    PRE[Formal Prevalidator]
    QUEUE[Human Review Queue]
    LOG[Decision Log]
    CONF[Confirmed Modeling Package]
  end
  subgraph COMPILER[Prompt 5 Compiler Authority Boundary]
    C5[Deterministic Semantic Compiler]
  end

  DP --> BASE --> TERM
  KGIR --> TERM
  SCOPE -. controls .-> MP
  CQ -. requirements .-> MP
  KGIR --> MP
  BASE --> MP
  TERM --> MP
  MP -->|candidate drafts only| NORM --> CONFLICT --> PRE
  PRE -->|PASS or REVIEW_REQUIRED| QUEUE
  PRE -. FAIL / repair required .-> MP
  QUEUE -. explicit human actions .-> LOG --> CONF
  CONF -->|READY_FOR_COMPILATION| C5
```

KG-IR is evidence, never an ontology. Providers cannot write workspaces or own
final IDs. Formal prevalidation cannot claim reasoning or CQ execution. Human
review is the only confirmation authority in this phase. The Confirmed
Modeling Package crosses into Prompt 5 but contains no authoritative semantic
syntax and triggers no compiler, publication, GraphDB, OMS, ODS, or OSS action.
