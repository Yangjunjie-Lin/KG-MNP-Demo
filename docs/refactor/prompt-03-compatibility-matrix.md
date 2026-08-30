# Prompt 3 compatibility matrix

| Surface | Baseline | Prompt 3 result | Verification |
|---|---|---|---|
| Original 20 public schemas | Frozen bytes and IDs | Byte-identical | Exact SHA-256 map and base-commit diff: PASS |
| Public Contract Catalog | 20 entries | One 34-entry additive catalog; no second registry | Two generator checks and lock verification: PASS |
| Contract Catalog schema 1.0 | Closed scope enum | 1.0 preserved; compatible 1.1 adds `ingestion` | Schema/migration tests: PASS |
| ArtifactReference/Manifest | v1 | Reused for four ingestion artifact sets and closure | Artifact/tamper tests: PASS |
| DomainPackManifest/Lock | v1 | All three lock bytes/digests unchanged | Generator, byte diff and 84/84 MNP gate: PASS |
| ProjectManifest/Lock | v1 | Semantics unchanged; old catalog binding becomes stale and re-locks | Workspace stale/re-lock tests: PASS |
| Workspace | Exact Prompt 2 layout | Uses existing open roots; `confirmed`/`packages` stay empty | Workspace/transaction tests: PASS |
| ModelingProposal | Retained | Unchanged | Retained modeling regression: PASS |
| ReviewDecisionLog | Retained | Unchanged | Retained review regression: PASS |
| ConfirmedModelingPackage | Retained authority | Never emitted by ingestion | Authority boundary tests: PASS |
| Compiler/publication/activation | Retained | No implementation rewrite | Retained lifecycle regressions and dedicated offline gates |
| Root CLI | Existing routes | Adds plugin/source/ingest/ir; legacy dispatch retained | Root and Prompt 3 CLI tests/smoke: PASS |
| Wheel package data | Catalog and schemas | 34 schemas, 13 manifests, entry points, SDK and core packaged | Isolated wheel probes: PASS |
| OCR/ASR/vision/video | Absent | Still absent; image/WAV metadata only, video unresolved | Format/quality/CLI smoke: PASS |
