# Prompt 5 Compatibility Matrix

| Surface | Result | Boundary |
|---|---|---|
| Original 59 schemas | Preserved | Historical Catalog hashes are asserted byte-for-byte. |
| Catalog/Registry | Additive migration | One Catalog at 1.2.0 and one offline Registry; 83 resources. |
| Plugin API 1.0/1.1 | Retained | Providers remain proposal-only and never enter compiler authority. |
| Ingestion, Evidence, KG-IR | Retained | Compiler resolves their immutable artifacts but does not reinterpret KG-IR. |
| Prompt 4 modeling/review | Retained | Current-Catalog rerun produces the sole compiler input. |
| Stage 06 compiler/CLI | Retained | Compatibility wrappers preserve old input/publication/activation behavior. |
| Domain Packs | Read-only | Explicit local registry, manifest/lock verification, copied package assets. |
| Publication/activation/rollback | Retained legacy only | Prompt 5 does not invoke or extend these operations. |
| GraphDB/application | No Prompt 5 writes | Outside the semantic kernel and package build transaction. |
| Wheel install | Supported | Schemas, policy, vocabulary, verifier, archive and CLI are package resources. |
