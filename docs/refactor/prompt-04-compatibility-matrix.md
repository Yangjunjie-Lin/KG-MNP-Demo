# Prompt 4 Compatibility Matrix

| Surface | Prompt 4 policy | Verification |
|---|---|---|
| Contract Kernel | RETAIN_API_COMPATIBLE; add entries to the only Catalog | Catalog and full regression gates |
| Existing 34 schemas | RETAIN_BYTE_IDENTICAL | Git object/byte digest comparison to Prompt 3 |
| Plugin API 1.0 | RETAIN_BYTE_IDENTICAL | 1.0 manifest/snapshot tests and 13-plugin discovery |
| Plugin API 1.1 | Add `modeling-provider` with `PROPOSAL_ONLY` authority | 1.1 contract and conformance tests |
| Prompt 3 ingestion | RETAIN_API_COMPATIBLE | Prompt 3 offline and selected/full pytest |
| Source/Evidence/KG-IR | Reuse as the only data/evidence input chain | closure and trace tests |
| Domain Packs | Read-only; lock bytes and content digests preserved | pack gates and MNP 84/84 golden |
| Workspace v1 | Retain top-level layout; add descendants below existing artifact roots | workspace and transaction tests |
| Legacy ModelingProposal | Retained and routed by legacy CLI; public exports are lazy only to avoid repository-root discovery during Prompt 4 Wheel imports | Stage 06 and isolated Wheel tests |
| Legacy ReviewDecisionLog | Retained; new review family is separate | Stage 06 tests |
| Legacy ConfirmedModelingPackage | Retained; no implicit conversion to Prompt 4 package | Stage 06 tests |
| Legacy compiler | Unchanged; Prompt 4 adapter deferred | Stage 06 tests and architecture boundary test |
| Publication | Unchanged and not called | boundary/security tests |
| Activation/Rollback | Unchanged and not called | Application Phase 06 offline tests |
| Legacy CLI | Retained; new explicit `model` and `review` routes added; both help routes load outside a source checkout | legacy, new CLI, and isolated Wheel tests |

The new Confirmed Modeling Package is a deterministic, reviewed compiler input marked only `READY_FOR_COMPILATION`; it is not a published ontology and is not accepted by the old compiler without the Prompt 5 adapter.
