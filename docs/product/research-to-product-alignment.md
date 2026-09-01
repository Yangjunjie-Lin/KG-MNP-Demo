# Research-to-Product Alignment

The revised product preserves the research questions while replacing unsafe or
overly domain-specific product interpretations.

| Research content | Product realization | Authority boundary |
|---|---|---|
| “本体论和 AI 智能体协同的知识工具链框架” | Project Control Plane, explicit semantic authority boundary, pluggable providers, and integration adapters | AI Agent is an advisory proposal/explanation component, never the formal semantic authority. |
| “多模态规则化” | Prompt 3 deterministic media detection, validated provider plans, constrained parsing/normalization, Evidence Record, evidence-bound KG-IR, and structural Quality Gates | Extracted content stays an observation with source coordinates and cannot become formal semantics without review. Metadata-only image/WAV support is not semantic understanding. |
| “AI 大模型与领域约束的本体构建” | Prompt 4 approved Scope/CQs, locked baseline reuse, offline rule/reuse/manual/recorded proposal providers, closed candidates, formal prevalidation, replayable human review, and deterministic compiler-ready package; Prompt 5 attests and compiles only that confirmed input into a formally validated, provenance-closed, unpublished package | Providers propose; domain constraints pre-validate; humans confirm; deterministic code alone compiles. Recorded bytes are not a live LLM, and OWL/SHACL/CQ results are not an accuracy claim. |
| “执行反馈与智能演进” | Feedback Issue, Change Proposal, Semantic Diff, Regression Validation, and Controlled Release | Feedback cannot mutate a released ontology or deploy a repair directly. |
| 原平台原型 | Unified Ontology Workbench plus Domain Packs | The workbench coordinates governed artifacts; domain content remains outside the core. |

## Decisions

- AI Agent is no longer treated as a formal semantic authority.
- Business execution is not the toolchain kernel.
- Forestry is the first planned Domain Pack pilot, not core code and not yet
  implemented.
- MNP is a migrated baseline Domain Pack, not the universal product model.
- OMS, ODS, and OSS are pluggable integration-layer adapters.
- “Automatic evolution” is replaced by controlled, versioned evolution with
  review, semantic diff, regression validation, release, and rollback.
- Prompt 3 implements deterministic Core planning rather than an Agent planner;
  it reports missing providers instead of fabricating OCR, ASR, vision, or video
  observations.
- Evidence binding and authoritative ingestion identifiers remain Core-owned;
  installed Python Plugins are explicit trust decisions and not Domain Pack
  content or an OS sandbox.
- Prompt 4 candidate and package identifiers remain Core-owned; scores are
  ordering evidence rather than semantic probabilities, and all candidates
  require explicit human decisions.
- Prompt 4 structural prevalidation and CQ coverage do not claim OWL
  consistency, SHACL execution, CQ execution, or semantic accuracy.
- Prompt 5 distinguishes compilation coverage, OWL consistency, SHACL
  conformance, executable CQ oracles, and provenance closure. None proves
  domain truth, business correctness, evidence truthfulness, or cross-industry
  performance.
- Prompt 5 emits only `VALIDATED_UNPUBLISHED`; it does not calculate SemVer,
  register, release, activate, deploy, repair, or execute business actions.

This alignment distinguishes the implemented Prompt 4 modeling/review control
plane and Prompt 5 deterministic compilation/package boundary from later
lifecycle and product capabilities. The implemented chain demonstrates
structural traceability, deterministic compilation, declared formal gates, and
reproducible packaging; it does not establish semantic accuracy without ground
truth. Live LLM planning, semantic diff, automatic SemVer classification,
Package Registry rewrite, publication/activation rewrite, a unified Workbench,
and Forestry implementation remain planned.
