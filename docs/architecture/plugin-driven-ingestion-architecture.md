# Plugin-driven evidence-bound ingestion architecture

```mermaid
flowchart LR
  subgraph DP[Domain Pack boundary — data only]
    DPA[Pack assets and locked capability metadata]
  end
  subgraph WS[Project Workspace boundary]
    subgraph PB[Plugin boundary — installed trusted Python]
      SA[Source Adapter]
      MD[Media Detector]
      PP[Parser Plugin]
      NP[Normalizer Plugin]
      QE[Quality Evaluator]
    end
    subgraph CA[Core authority boundary]
      SS[Source Content Store]
      IP[Deterministic Ingestion Planner]
      EB[Core Evidence Binder]
      KB[KG-IR Builder]
      AS[Artifact Store]
    end
    RR[Review Required]
  end

  SA -->|artifact bytes| SS
  SS -->|control: registered SourceAsset| MD
  MD -->|control: detected media/capability| IP
  IP -->|control: validated plan and snapshot| PP
  PP -->|ParsedUnit| NP
  NP -->|NormalizedUnit| EB
  EB -->|Evidence + transformation artifacts| QE
  QE -->|PASS| KB
  QE -->|quality issue| RR
  KB -->|KG-IR artifacts| AS
  EB -->|Evidence artifacts| AS
  IP -->|Plan/Run artifacts| AS
  DPA -. capability/data context only; no code execution .-> IP
  RR -. operator/provider decision .-> IP
```

Solid arrows show control or artifact flow as labeled. Core alone assigns
Source/Evidence/KG-IR/artifact identities and commits formal files. Plugin code
cannot obtain a Workspace writer. Domain Packs do not carry executable plugin
code. Review does not turn KG-IR into ontology authority; it determines whether
later processing or a future provider is required.

The operation lock is process-external and stored under `tmp/locks`; its PID
and nonce are operational metadata excluded from semantic hashes. Staging is
non-authoritative until the four formal artifact directories commit.
