# Prompt 3 claim-evidence matrix

This matrix is initialized from the baseline audit. Status changes require
working code, a public contract where applicable, a real test and a bounded
example. A schema or mock alone is insufficient evidence.

| Claim | Supporting code | Contract | Test | Example | Status | Limitation |
|---|---|---|---|---|---|---|
| One offline public contract registry | `kg_mnp.contracts` | Contract Catalog 1.1 | `tests/contracts` | contracts CLI | SUPPORTED | Remote resolution remains prohibited. |
| Locked Domain Pack closure | `kg_mnp.domain_packs` | DomainPackManifest/Lock v1 | `tests/domain_packs` | three packs | SUPPORTED | Does not execute Plugin code. |
| Deterministic Project Workspace | `kg_mnp.workspace` | ProjectManifest/Lock v1 | `tests/workspace` | workspace CLI | SUPPORTED | Catalog migration requires re-lock. |
| Plugin SDK v1 and metadata-only discovery | `kg_mnp.plugins` | PluginManifest/Snapshot v1 | `tests/plugins`, plugin security/CLI | independent fixture wheel and plugin smoke | SUPPORTED | Installed Python is explicitly trusted code, not an OS sandbox or signature. |
| Content-addressed Source Store | `ingestion.source_store` | SourceAsset/Batch v1 | `tests/sources`, source security/CLI | minimal project and CLI smoke | SUPPORTED | Prompt 3 accepts bounded local regular files only. |
| Deterministic parser planning | `ingestion.planner`, `plugins.selection` | IngestionPlan v1 | planner/executor and ambiguity tests | all-format CLI smoke | SUPPORTED | Core planner only; no LLM or Agent planner. |
| Evidence source/transformation/Plugin closure | `ingestion.evidence`, `transformations` | EvidenceRecord/TransformationRecord v1 | `tests/evidence`, tamper tests | TXT trace to blob | SUPPORTED | Evidence is an observation, not confirmed knowledge. |
| Evidence-bound KG-IR | `ingestion.kgir` | KGIRItem/Dataset v1 | `tests/kgir`, IR CLI | deterministic dataset and trace | SUPPORTED | Ontology and business-object kinds are prohibited. |
| Structural quality gates | `ingestion.quality` | QualityReport v1 | `tests/quality`, executor cases | PASS and REVIEW_REQUIRED formats | SUPPORTED | Structural metrics are not semantic accuracy without ground truth. |
| Multi-format parsing | built-in parsers | Plugin/Common and locator contracts | parser/document security and E2E tests | TXT/MD/JSON/CSV/TSV/XLSX/DOCX/PDF/PNG/WAV | PARTIALLY_SUPPORTED | PNG/WAV are metadata-only; PDF ordering and formula text require review. |
| LLM ingestion planning | None | None | Boundary tests | None | NOT_IMPLEMENTED | Deliberately deferred; deterministic Core planning is not an Agent. |
| OCR accuracy | None | None | None | None | OUT_OF_SCOPE | No OCR provider or ground truth. |
| Vision/ASR/video understanding | None | None | None | None | OUT_OF_SCOPE | Missing providers must be reported honestly. |
| Ontology modeling and field mapping | Existing legacy layers only | Modeling contracts | Existing regressions | Existing examples | OUT_OF_SCOPE | Prompt 3 must not emit modeling authority. |
