# Prompt 3 ingestion baseline audit

This audit was performed on `codex/plugin-ingestion-kgir-p03` at source commit
`d04e9b494a99932532ae9c359653878aa32261d7` before Prompt 3 implementation.
The source worktree was clean. The immutable historical tag resolves to
`e45da340267de8d4b7b3a54177822aa641e3a601`, and Prompt 1 and Prompt 2 are
ancestors. Detailed command output is intentionally kept below the ignored
`runtime_reports/refactor/prompt-03/` directory.

## Prompt 2 Contract Kernel

The repository has exactly one public catalog at
`src/kg_mnp/contracts/catalog.json`, one offline registry in
`kg_mnp.contracts`, and one catalog lock. Its 20 entries at the audit point
were:

1. `cleaned-partial-data`
2. `common`
3. `confirmed-modeling-package`
4. `mapping-rules`
5. `modeling-proposal`
6. `ontology-baseline-manifest`
7. `review-action`
8. `review-common`
9. `review-decision-log`
10. `review-policy`
11. `terminology-profile`
12. `artifact-manifest`
13. `artifact-reference`
14. `contract-catalog`
15. `domain-pack-lock`
16. `domain-pack-manifest`
17. `project-lock`
18. `project-manifest`
19. `toolchain-common`
20. `validation-report`

The catalog semantic digest was
`b6bf0748a8330f2841eb5d1ce1cf93f8d7bd21e37f763d4a283527e513080f45`;
the lock ID was
`urn:kg-mnp:contract-catalog-lock:acb509211fa9ab18afd6628201859d10dd78ffff2acb563aa435b44e64fa86bc`.
The frozen catalog schema permits only `toolchain` and `modeling` scopes, so
Prompt 3 must publish a compatible catalog-schema revision rather than alter
the 1.0 schema in place.

`ArtifactReference` and `ArtifactManifest` already supply safe relative
artifact paths, SHA-256 byte binding, closed dependencies/provenance and
deterministic manifests. They are core primitives for ingestion artifacts.
`ProjectManifest` and `ProjectLock` bind the project, catalog and Domain Pack
closure. The Workspace service builds an exact layout, treats `reports/` and
`tmp/` as non-authoritative, and prohibits Prompt 2 from placing authority in
`artifacts/confirmed/`. A catalog change intentionally makes old Project
Locks stale; re-locking is the migration, not accepting an old digest.

The three locked Domain Packs were present and verified with content digests:

- minimal: `9243d8a995a4a87b8d2048bf7cb0069203e3d7d528e57409e6d3f985ac11e014`
- mnp: `2554d6d4bbd98b4defd2a46243d6f4f01842320bcc929aff0a3a03ba7cc6ddd1`
- forestry: `58dbf2ab75189ecefdaf79e6c5e49ae7c796471e9be65aa48cbf0e21a21d66e9`

The MNP Prompt 1 golden covers 84 assets. The Prompt 2 protected snapshot
covers 1,052 files with tree digest
`e39390641d4518c8e56614637a06dfe29d7c8a1d8fb9275ef40376bc2e500fe1`.

## Existing surface and dependencies

The root `kg-mnp` router preserves modeling, contracts, Domain Pack,
Workspace, application, workbench, diagnostics, governance, amendment and
activation routes. It had no public `plugin`, `source`, `ingest` or `ir`
routes. Packaging included catalog, lock and modeling/toolchain schemas, but
no Plugin manifests or ingestion package data. Core dependencies included
RDFLib, pySHACL, OWL-RL, PyYAML, jsonschema, FastAPI and Uvicorn. There was no
document-ingestion optional extra.

There was no Plugin SDK, provider discovery, local Plugin registry, Source
Content Store, SourceAsset/SourceBatch, deterministic media detector,
Ingestion Plan/Run, ingestion Evidence Record, KG-IR, OCR provider,
transcription provider or multimodal semantic model. Existing occurrences of
"evidence" are modeling, diagnostics, publication, application or ontology
terms and are not an evidence-bound ingestion record implementation.

## Legacy overlap classification

| Existing capability | Classification | Prompt 3 treatment |
|---|---|---|
| `kg_mnp.contracts` catalog, registry, canonical JSON and document I/O | REUSE_AS_CORE_PRIMITIVE | Reuse without a second catalog or registry. |
| ArtifactReference and ArtifactManifest | REUSE_AS_CORE_PRIMITIVE | Bind ingestion outputs and closure. |
| Project Workspace and Project Lock | WRAP_FOR_COMPATIBILITY | Add sub-layouts without changing v1 semantics. |
| `input_adapter` and `rdf_builder` | SUPERSEDED_LATER | Retain unchanged; they remain modeling/application inputs, not Prompt 3 parsers. |
| modeling `cleaned_partial_data` | DOMAIN_SPECIFIC | Never emit it from Prompt 3. |
| application trace/evidence | DOMAIN_SPECIFIC | Retain as the read-only business/application plane. |
| diagnostics evidence | DOMAIN_SPECIFIC | Retain; not SourceLocator evidence. |
| publication/compiler provenance | RETAIN_UNCHANGED | Preserve byte and API compatibility. |
| loader-like GraphDB/publication import code | OUT_OF_SCOPE | It consumes confirmed artifacts and is not source ingestion. |
| OCR, ASR, vision and video understanding | OUT_OF_SCOPE | Report missing provider/review required; never fabricate content. |

No legacy implementation was moved or deleted during the audit.

## Modification-before baseline

The prescribed editable install, Ruff, toolchain foundation, catalog, Domain
Pack, Workspace, Prompt 2 offline, Prompt 2 targeted pytest, Stage 06 and
Application Phase 06 offline commands all completed successfully. Existing
platform skips and upstream deprecation warnings are recorded in the runtime
reports and are not represented as executed passes.

## Prompt 3 audited outcome

The implementation remains additive to the baseline classified above. The one
catalog now contains 34 entries and validates against the compatible catalog
schema 1.1. Its semantic digest is
`984c2031a36e6332c0c0a5724dc0dabbeb1f6f07f8389c3bda02e6744dccb5ed`;
the lock ID is
`urn:kg-mnp:contract-catalog-lock:2f6a21f2533bf466437139cc0749dcfc43b6994ff0c8272d9918c7c45eb185be`.
All original 20 schema byte hashes remain exact.

The audited additions are Plugin SDK v1 and 13 deterministic built-ins,
metadata-only external discovery with explicit enablement, the content-addressed
Source Store, deterministic media/planning/execution, Core-owned Evidence and
KG-IR binding, structural quality gates, transaction/lock handling, Artifact
Manifest integration, and public `plugin`, `source`, `ingest`, and `ir` routes.
The independent fixture wheel proves external discovery without import,
default disablement, explicit enablement, and typed conformance.

End-to-end CLI evidence covers TXT, Markdown, JSON, CSV, TSV, XLSX, DOCX, PDF,
PNG metadata, WAV metadata, and an unsupported MP4 stub. The MP4 plan is
`UNRESOLVED` with `MISSING_TRANSCRIPTION_OR_VIDEO_PROVIDER` and zero fabricated
items. XLSX formulas, PDF text ordering, image metadata, and WAV metadata require
review; this is not OCR, vision, ASR, or video understanding.

The original three Pack Lock files remain byte-identical, their content digests
remain exact, and MNP remains 84/84. The authorized protected snapshot expands
from 1,052 files / `e39390641d4518c8e56614637a06dfe29d7c8a1d8fb9275ef40376bc2e500fe1`
to 1,161 files / `1e57eb06d004c7f2f3e42ddabd51ac2c3957dfc0fba77000aa0e95530f3d77eb`
without shrinking any protected root.
