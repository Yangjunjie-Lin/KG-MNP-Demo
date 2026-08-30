# Repository Migration Matrix

## Directory decisions

| Current area | Decision | Prompt 1 destination / rationale |
|---|---|---|
| `ontology/` | `MOVE_TO_MNP_DOMAIN_PACK` | All modules and catalog define the MNP ontology; move to `domain_packs/mnp/ontology/`. |
| `data/` | `MOVE_TO_MNP_DOMAIN_PACK` | MNP case, regulation, and reference-system fixtures move to `domain_packs/mnp/fixtures/data/`. |
| `inputs/` | `MOVE_TO_MNP_DOMAIN_PACK` | MNP case JSON inputs move to `domain_packs/mnp/fixtures/inputs/`. |
| `mappings/` | `MOVE_TO_MNP_DOMAIN_PACK` | TMF-to-MNP mapping moves to `domain_packs/mnp/mappings/`. |
| `rules/` | `MOVE_TO_MNP_DOMAIN_PACK` | Eligibility rules move to `domain_packs/mnp/rules/`. |
| `shapes/` | `MOVE_TO_MNP_DOMAIN_PACK` | Shapes constrain the MNP vocabulary and move to `domain_packs/mnp/shapes/`. |
| `competency_questions/` | `MOVE_TO_MNP_DOMAIN_PACK` | All questions test MNP business semantics; move to the MNP pack. |
| `queries/` | `MOVE_TO_MNP_DOMAIN_PACK` | Root and application queries use MNP terms and move to the MNP pack. |
| `config/` | `SPLIT_GENERIC_AND_DOMAIN` | MNP ontology module, baseline, mapping, terminology, and query registry configuration moves with the pack; compiler/review/proposal/security and adapter policy remains core for now. |
| `references/` | `SPLIT_GENERIC_AND_DOMAIN` | MNP/TMF evidence and reviews move to `domain_packs/mnp/terminology/`; the generic open-source matrix remains. |
| `examples/` | `SPLIT_GENERIC_AND_DOMAIN` | The eligibility-use-case moves into MNP fixtures. Reviewed compiler/review/GraphDB/publication golden artifacts remain in `examples` until artifact contracts stabilize. |
| `demo_outputs/` | `DELETE_GENERATED` | Tracked run output is removed; Git history and the baseline Tag preserve it. |
| `schemas/` | `DEFER_TO_LATER_PROMPT` | Formal artifact/workspace/pack contract work belongs to later prompts. The legacy eligibility schema remains explicitly marked for relocation. |
| `src/` | `SPLIT_GENERIC_AND_DOMAIN` | Namespace is reset now; semantic kernel is retained. Eligibility internals are `DOMAIN_SPECIFIC_RELOCATION_PENDING`. |
| `tests/` | `SPLIT_GENERIC_AND_DOMAIN` | Regression/golden tests are retained; Prompt 1 adds foundation boundaries. Full domain/capability test reorganization is later work. |
| `scripts/` | `DEFER_TO_LATER_PROMPT` | Imports and paths are updated now; numbered and domain-coupled script cleanup is deferred. |
| `web/` | `DEFER_TO_LATER_PROMPT` | Existing web prototypes remain protected and require later unified Workbench work. |
| `deploy/` | `KEEP_AS_GENERIC_CORE` | Integration deployment configuration remains adapter infrastructure; references are updated. |

## Authoritative path moves

| Old path | New path |
|---|---|
| `ontology/*` | `domain_packs/mnp/ontology/*` |
| `data/*` | `domain_packs/mnp/fixtures/data/*` |
| `inputs/*` | `domain_packs/mnp/fixtures/inputs/*` |
| `mappings/*` | `domain_packs/mnp/mappings/*` |
| `rules/*` | `domain_packs/mnp/rules/*` |
| `shapes/*` | `domain_packs/mnp/shapes/*` |
| `competency_questions/*` | `domain_packs/mnp/competency_questions/*` |
| `queries/*` | `domain_packs/mnp/queries/*` |
| `config/ontology_modules.yaml` | `domain_packs/mnp/ontology/modules.yaml` |
| `config/modeling/ontology-baseline-1.0.0.json` | `domain_packs/mnp/ontology/ontology-baseline-1.0.0.json` |
| `config/modeling/mapping-rules-1.0.0.yaml` | `domain_packs/mnp/mappings/modeling-rules-1.0.0.yaml` |
| `config/modeling/terminology-profile-1.0.0.yaml` | `domain_packs/mnp/terminology/terminology-profile-1.0.0.yaml` |
| `config/application/query-registry-1.0.0.yaml` | `domain_packs/mnp/queries/query-registry-1.0.0.yaml` |
| `references/source_manifest.yaml` | `domain_packs/mnp/terminology/source_manifest.yaml` |
| `references/cto_review.md` | `domain_packs/mnp/terminology/cto_review.md` |
| `references/tmf_field_review.md` | `domain_packs/mnp/terminology/tmf_field_review.md` |
| `examples/eligibility-use-case/*` | `domain_packs/mnp/fixtures/eligibility-use-case/*` |

No old authority copy or top-level symlink is retained.

## Deferred coupling

- eligibility engine, input adapter, pipeline, evaluator, and root MNP helpers:
  `DOMAIN_SPECIFIC_RELOCATION_PENDING`;
- historical MNP IRIs and release identities: retained to preserve validated
  semantics and hashes;
- compiler/review/publication examples: reviewed golden artifacts, not runtime
  output, pending the final artifact contract;
- GraphDB, WebVOWL, application, diagnostics, governance, amendment, activation,
  and workbench modules: implemented but require adapter/capability refactor;
- Stage/Phase scripts, tests, CLI names, and CI jobs: retained temporarily to
  protect the semantic kernel, with complete cleanup deferred.
