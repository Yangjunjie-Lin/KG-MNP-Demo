# Research-to-Product Alignment

The revised product preserves the research questions while replacing unsafe or
overly domain-specific product interpretations.

| Research content | Product realization | Authority boundary |
|---|---|---|
| “本体论和 AI 智能体协同的知识工具链框架” | Project Control Plane, explicit semantic authority boundary, pluggable providers, and integration adapters | AI Agent is an advisory proposal/explanation component, never the formal semantic authority. |
| “多模态规则化” | Ingestion Pipeline, Evidence Record, evidence-bound KG-IR, and Quality Gates | Extracted content stays a candidate with source coordinates and cannot become formal semantics without review. |
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

This alignment establishes product direction. It does not claim Prompt 1 has
implemented the planned ingestion, KG-IR, LLM provider, semantic diff, unified
Workbench, or forestry assets.
