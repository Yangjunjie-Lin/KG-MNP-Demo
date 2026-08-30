# Current Capability Matrix

This matrix records repository state at Prompt 1. “Implemented” means exercised
by retained code and tests; it does not mean the capability is already generic,
packaged as a stable public API, or validated across industries.

## IMPLEMENTED_AND_RETAINED

| Capability | Evidence and boundary |
|---|---|
| ModelingProposal | Versioned schema, deterministic generation, validation, and tests exist. It remains a proposal, not authority. |
| ReviewDecisionLog | Review actions, policy, deterministic log, security validation, and tests exist. |
| ConfirmedModelingPackage | Confirmation, readiness, closure, hashing, and reconstruction tests exist. |
| Deterministic RDF generation | The retained compiler produces canonical N-Triples/N-Quads and deterministic Turtle/TriG. |
| OWL/SHACL validation | Local OWL consistency and SHACL profiles/reports are exercised by offline tests. |
| Provenance | Modeling provenance and review-audit graphs are compiled and coverage-tested. |
| Publication verification | Publication packages can be reconstructed, verified, and attested offline. |
| Activation/rollback governance | Registry, state transition, pointer, concurrency, rollback, resolver, and attestation logic exist. |

## IMPLEMENTED_BUT_REQUIRES_REFACTOR

| Capability | Required refactor |
|---|---|
| GraphDB integration | Decouple MNP packages, commercial runtime assumptions, and a concrete backend from the core. |
| Workbench | Consolidate the read-only prototype into a toolchain workbench after public contracts stabilize. |
| Diagnostics | Generalize authority loading and domain constraints. |
| Governance | Reframe operational governance around toolchain projects and controlled release. |
| Amendment | Replace application-specific amendment semantics with Change Proposals and semantic diff. |
| Activation | Align activation artifacts with the future package registry and workspace contracts. |
| Stage/Phase CLI | Retire numbered routing without rewriting the complete CLI in Prompt 1. |
| MNP-specific path assumptions | Use centralized repository/domain/runtime resolution and later move remaining coupling behind Domain Pack contracts. |
| Eligibility internals | Retained temporarily for regression only; public eligibility console entry is removed and relocation remains pending. |

## PLANNED

| Capability | Status |
|---|---|
| Project Workspace | Planned; no final contract in Prompt 1. |
| Formal Domain Pack contract | Planned for Prompt 2; current manifests are provisional. |
| Plugin SDK and provider registry | Planned; no placeholder API is claimed. |
| Multimodal ingestion | Planned research/product work; not implemented. |
| Evidence-bound KG-IR | Planned; current evidence models are inputs to later design. |
| LLM proposal provider | Planned and constrained to proposal authority. |
| Unified Workbench and REST API | Planned after contracts stabilize. |
| Semantic Diff | Planned for controlled evolution; existing amendment diff is not represented as the final semantic diff. |
| Forestry Domain Pack | Planned scaffold only; no forestry ontology, data, or validation exists. |

## OUT_OF_SCOPE

| Capability | Reason |
|---|---|
| Agent as semantic authority | Violates the authority boundary. |
| Direct AI writes to released OWL/RDF/SHACL/ABox | Violates review and deterministic compilation controls. |
| Autonomous production self-evolution | Feedback must become a reviewed Change Proposal and controlled release. |
| Core business execution platform | Execution belongs to integration adapters, not the ontology toolchain kernel. |
| Universal industry claims | Capabilities must be validated by concrete Domain Packs and evidence. |
