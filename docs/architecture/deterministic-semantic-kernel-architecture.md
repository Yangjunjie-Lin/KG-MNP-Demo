# Deterministic Semantic Kernel Architecture

```mermaid
flowchart LR
  subgraph W[Workspace Boundary]
    subgraph H[Human Confirmation Boundary]
      C[Confirmed Modeling Package]
    end
    subgraph D[Domain Pack Boundary]
      B[Locked local baseline]
    end
    subgraph A[Semantic Compiler Authority Boundary]
      I[Input Attestation] --> S[Compiler Snapshot] --> P[Compilation Plan]
      P --> K[TBox / ABox / SHACL / Mapping]
      B --> K
      K --> N[Named Graph Dataset] --> V[Statement Provenance / Audit / Lineage]
    end
    subgraph G[Validation Boundary]
      V --> R[RDF] --> O[OWL] --> SH[SHACL] --> Q[CQ] --> PC[Provenance Closure]
    end
    subgraph PK[Package Boundary]
      PC --> M[Manifest / Lock] --> U[VALIDATED_UNPUBLISHED]
    end
  end
  U --> RB[Prompt 6 Registry Boundary]
  I -->|FAIL| F[Failure report / rollback]
  P -->|FAIL| F
  R -->|FAIL| F
  O -->|FAIL| F
  SH -->|FAIL| F
  Q -->|FAIL| F
  PC -->|FAIL| F
```

There is deliberately no repair arrow from a validation failure to providers,
an LLM, candidates or Domain Packs. Staging is under `tmp/compilation`; only a
fully verified closed set is atomically committed. The kernel accepts explicit
Domain Pack roots and package resources and never uses `repository_root`.
