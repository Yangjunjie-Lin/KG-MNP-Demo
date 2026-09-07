# KG-MNP Ontology Workbench / KG-MNP 本体工程工作台

Status: proposed information architecture, **not implemented UI**. Formal UI
acceptance is stopped because the 8A backend workflow gate does not pass.
The old three static applications have not been packaged together or declared
to be this product. No production frontend stack/build is claimed.

| Navigation group | Intended pages | Authoritative boundary |
| --- | --- | --- |
| Project selection | Select/create, identity, exact Pack/version | Workspace + ProjectManifest/ProjectLock |
| 资料与证据 | Sources/ingestion, quality/evidence | Source, IngestionPlan/Run, KG-IR, locators |
| 本体建模 | Scope/CQ, concepts/relations, mapping/constraints, proposals/review | Core modeling and human review |
| 验证与版本 | Compilation, packages/releases, diff/impact/regression, environments | Compiler + lifecycle registry |
| 浏览与集成 | Ontology/object explorer, integration status | Released package, OMS/ODS, optional adapters |
| 任务与设置 | Jobs, packs/plugins, identity/permissions | Persistent JobStore, authenticated Principal |

The planned shell has project switching, current Principal, Pack/version,
build context, global jobs and environment selection. First use selects a
project; it does not default to MNP or forestry. Domain labels come from data,
not pack-specific application branches. Chinese labels remain distinct from
IRIs, IDs and contract fields. Empty/error/forbidden/stale/partial/blocked states
must be distinct. No unknown metric may be rendered as zero.

The implementation boundary remains Workbench → existing API →
ApplicationService → existing core. No second backend or authorization store
is introduced. Session, query-cache, diagram/table/evidence interaction and
responsive/keyboard behavior have **not** been implemented or verified here.
