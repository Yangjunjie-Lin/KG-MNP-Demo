# ODR-005 — Modeling Provenance Module

| Field | Value |
|---|---|
| ODR ID | ODR-005 |
| Title | Introduce mnp-modeling-provenance; separate modeling from business evidence |
| Status | Accepted |
| Ontology version | 1.0.0 |
| Date | 2026-08-05 |
| Related modules | `mnp-modeling-provenance` (new), `mnp-core`, `mnp-evidence-time` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| New module IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/mnp-modeling-provenance` |
| New version IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/mnp-modeling-provenance` |

## Context

Stage 02 froze the semantic authority chain (CleanedPartialData → ModelingProposal
→ ReviewDecisionLog → ConfirmedModelingPackage → generated OWL/SHACL). Stage 03
must introduce stable **TBox** concepts for modeling provenance without
implementing Stage 04 JSON schemas, proposal pipelines, or review ABox
instances. `MappingRecord` currently lives in `mnp-core.ttl` and is easily
confused with business `EvidenceRecord`.

## Current model

- `MappingRecord` and several mapping datatype properties are defined in
  `mnp-core.ttl`.
- Business evidence uses `EvidenceRecord` under the eligibility / evidence-time
  story.
- No dedicated modeling-provenance module exists.
- No TBox distinction between modeling review decisions and eligibility
  decisions (`EligibilityDecision`).
- Stage 02 docs describe Modeling Evidence vs Business Fact Evidence in prose
  only (`docs/architecture/evidence-layers.md`).

## Problem

1. Core should not own mapping/provenance vocabulary that belongs to the
   modeling chain.
2. Treating mapping or modeling justification as `EvidenceRecord` would pollute
   eligibility evidence queries and SHACL.
3. Reusing `EligibilityDecision` (or informal “decision”) for schema review
   would conflate portability outcomes with ontology governance outcomes.
4. Stage 03 must not invent a large unused class zoo; only stable concepts
   needed by the frozen authority chain should be declared—as TBox only.

## Candidate alternatives

### A — Leave MappingRecord in core; document prose-only provenance

No new module; rely on architecture docs until Stage 04.

### B — New modeling-provenance module with TBox-only terms (selected)

Create `ontology/mnp-modeling-provenance.ttl` and move mapping/modeling terms
there. Distinguish modeling evidence from business evidence and review
decisions from eligibility decisions.

### C — Full PROV-O import as runtime dependency

Import W3C PROV-O into the root ontology and subclass everything from it.

### D — Define Stage 04 ABox individuals now

Mint sample ReviewDecision and MappingRule instances in `data/`.

## Selected model

**Alternative B.**

New runtime module: `mnp-modeling-provenance` (imported by root `kg-mnp`).

TBox-only classes (minimum set):

| Class | Role |
|---|---|
| `MappingRecord` | Documented mapping from an external field/API path to an MNP term |
| `ModelingAssertion` | Proposed or confirmed schema/ABox modeling assertion unit |
| `RelationAssertion` | Typed relation assertion within a modeling package |
| `ModelingEvidence` | Evidence supporting schema/mapping decisions (≠ `EvidenceRecord`) |
| `SourceRecord` | Reference to a cleaned partial source record |
| `SourceField` | Field/JSON Pointer within a source record |
| `MappingRule` | Versioned rule describing how source fields map to terms |
| `ReviewDecision` | Governance review outcome for a proposal item (≠ `EligibilityDecision`) |

Rules:

1. `MappingRecord` **moves out of** `mnp-core` (MOVE_MODULE).
2. `ModelingEvidence` is **disjoint in intent** from `EvidenceRecord`; do not
   declare them equivalent; prefer explicit disjointness if reasoner-safe.
3. `ReviewDecision` must not be a subclass of `EligibilityDecision` (or vice
   versa).
4. No Stage 04 JSON Schema, no proposal generator, no review ABox individuals
   in this stage.
5. Every new term gets bilingual labels/definitions and source status
   (e.g. `PROJECT_GOVERNANCE` / `LOCAL_EXTENSION`).

## Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| A — Prose only | Leaves MappingRecord misplaced; fails Stage 03 module audit. |
| C — Runtime PROV-O import | Remote/license/runtime risk; Stage 02 forbids treating PROV-O as substitute domain ontology. |
| D — Emit ABox now | Violates Stage 03 scope; Stage 04 territory. |

## OWL consequences

- Create `mnp-modeling-provenance.ttl` with ontology metadata, versionInfo
  `1.0.0`, and imports of `mnp-core` only as needed (no cycles).
- Move `MappingRecord` defining axioms and mapping datatype properties out of
  core.
- Declare the eight classes (and only properties clearly required to connect
  them at TBox level—avoid speculative property explosion).
- Root `kg-mnp` imports the new module; `config/ontology_modules.yaml` lists it
  as runtime.
- Alignments module may annotate mapping terms as local/governance without
  forcing alignments into default runtime if policy keeps alignments optional.

## SHACL consequences

- Ontology-schema shapes: new classes/properties must satisfy label/definition
  completeness.
- Foundation-instance shapes may later constrain `RelationAssertion` structure;
  Stage 03 may add minimal structural checks only if needed for published
  graphs—**no** requirement for complete review packages.
- Eligibility shapes must not target `ModelingEvidence` or `ReviewDecision`.

## Data migration impact

| Asset | Impact |
|---|---|
| `ontology/mnp-core.ttl` | Remove defining triples for `MappingRecord` (and related mapping DPs) |
| New TTL module | Hold defining triples |
| Existing eligibility `data/` | No ModelingEvidence/ReviewDecision instances expected |
| term-inventory / change-log | Record MOVE_MODULE and ADD decisions |
| Loader config | Include new module file |

## Compatibility impact

| Change | Compatibility class |
|---|---|
| New module + classes | Minor if additive alone; packaged in 1.0.0 major IRI release |
| Moving `MappingRecord` defining module | Compatible IRI if term NS unchanged; tooling that assumed core file ownership must update |
| No ABox yet | No instance breakage |

## Evidence / source

- Stage 03 brief §11 and §8.2
- `docs/adr/ADR-001-semantic-authority.md`
- `docs/architecture/semantic-authority-chain.md`
- `docs/architecture/evidence-layers.md`
- `docs/architecture/tbox-abox-boundary.md`
- Existing `MappingRecord` stub in `mnp-core.ttl`

## Tests

- Module metadata: modeling-provenance ontology IRI / version IRI present
- `MappingRecord` defining module = modeling-provenance (not core)
- Annotation completeness for the eight classes
- Disjointness / non-hierarchy checks: `ReviewDecision` ↛ `EligibilityDecision`
- Competency CQ-09 can resolve modeling source/module metadata for a term
- Stage boundary tests: no Stage 04 schema files introduced by this ODR
