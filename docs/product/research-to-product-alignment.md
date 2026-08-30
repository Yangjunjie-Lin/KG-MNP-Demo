# Research-to-Product Alignment

The revised product preserves the research questions while replacing unsafe or
overly domain-specific product interpretations.

| Research content | Product realization | Authority boundary |
|---|---|---|
| “本体论和 AI 智能体协同的知识工具链框架” | Project Control Plane, explicit semantic authority boundary, pluggable providers, and integration adapters | AI Agent is an advisory proposal/explanation component, never the formal semantic authority. |
| “多模态规则化” | Prompt 3 deterministic media detection, validated provider plans, constrained parsing/normalization, Evidence Record, evidence-bound KG-IR, and structural Quality Gates | Extracted content stays an observation with source coordinates and cannot become formal semantics without review. Metadata-only image/WAV support is not semantic understanding. |
| “AI 大模型与领域约束的本体构建” | Proposal Provider, Formal Pre-validation, Human Review, and Deterministic Compiler | The LLM proposes; domain constraints pre-validate; humans confirm; deterministic code compiles. |
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

This alignment distinguishes the implemented Prompt 3 ingestion kernel from
planned semantic capabilities. Prompt 3 demonstrates structural traceability,
closure, deterministic selection, and reproducibility; it does not establish
semantic accuracy without ground truth. LLM planning, ontology modeling and
mapping, semantic diff, a unified Workbench, and forestry implementation remain
planned.
