# Prompt 2 Contract Audit

This audit was performed on `codex/ontology-toolchain-contracts-p02` before
any existing schema was changed. The source tree was the exact Prompt 1 commit
`a7114eef25f2f2a262cd69793a8d3e2b444836fc`. Detailed command output, every
schema `$ref`, and every pre-change SHA-256 are retained locally under the
Git-ignored `runtime_reports/refactor/prompt-02/` directory.

## Entry identity

- Remote Prompt 1 head: `a7114eef25f2f2a262cd69793a8d3e2b444836fc`.
- Historical tag target: `e45da340267de8d4b7b3a54177822aa641e3a601`.
- Initial worktree: clean.
- Initial protected tree: 978 files,
  `25bb5818de52132f71056d543f3b019aeb8bbbe9a04bf2b82ff522b89e7c4c24`.
- Existing schema inventory: 63 schemas below `schemas/`, plus the MNP
  eligibility fixture schema.

## Public modeling contracts to migrate

| Contract file | Stable `$id` | Pre-move SHA-256 | Classification |
|---|---|---|---|
| `cleaned_partial_data.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/cleaned-partial-data/1.0` | `7fafb0921bd0f6f28fc0f879e0eec4ec8a426c0b49c30991421e28ef1cf531b7` | PUBLIC_TO_MIGRATE |
| `common.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/common/1.0` | `7c50453e35e0a3b3868d9480e35c75cb126b04355c96b5ff887995ae41c61e7c` | PUBLIC_TO_MIGRATE |
| `confirmed_modeling_package.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/confirmed-modeling-package/1.0` | `e8dfd1ce630f6c7e93a7e49691de7fac100895d143dc500afe1903a3e0107146` | PUBLIC_TO_MIGRATE |
| `mapping_rules.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/mapping-rules/1.0` | `57b5de7e6f2f9a2eb4735ef6b386016934186f29843f9dd9e21647b08f387137` | PUBLIC_TO_MIGRATE |
| `modeling_proposal.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/modeling-proposal/1.0` | `e7139bfd7402d6ba362134c3fa5537b478c0a42805b971ed54e701b513cdcd3b` | PUBLIC_TO_MIGRATE |
| `ontology_baseline_manifest.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/ontology-baseline-manifest/1.0` | `54adc74ba2bfd638ef2d8de805ea3c2ae6da114129396b9bb385f576a5de2781` | PUBLIC_TO_MIGRATE |
| `review_action.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/review-action/1.0` | `b2c041c9f1a6cb33b67fdf34b317b780112ca677b2e3f5013f15355a4ab939d3` | PUBLIC_TO_MIGRATE |
| `review_common.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/review-common/1.0` | `69b3af6bd9c70f17524d311d29aa5abcc7d066a01f992ca45885fba3448a3b7c` | PUBLIC_TO_MIGRATE |
| `review_decision_log.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/review-decision-log/1.0` | `ef24e251d4bbb4cbc12b081f6f371ec0e294c240a76151bada870b7f66c21ada` | PUBLIC_TO_MIGRATE |
| `review_policy.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/review-policy/1.0` | `5b252e1f0b558ad2fc9592a975c6ce9003a8152077ce631101418f5a1828ae54` | PUBLIC_TO_MIGRATE |
| `terminology_profile.schema.json` | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/terminology-profile/1.0` | `49841b8bc0089a562a314edfcd8740b41742a1d4a5278825075ed3a444cd1b69` | PUBLIC_TO_MIGRATE |

All eleven declare Draft 2020-12 and use local cross-contract references. Their
content and `$id` values are frozen during the move.

## Retained and domain-specific contracts

| Location | Count | Classification | Prompt 2 disposition |
|---|---:|---|---|
| `schemas/activation` | 7 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/amendment` | 4 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/application` | 7 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/compilation` | 5 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/diagnostics` | 5 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/governance` | 7 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/graphdb` | 8 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/publication` | 2 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/webvowl` | 4 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `schemas/workbench` | 5 | INTERNAL_RETAINED | INTERNAL_CONTRACT_MIGRATION_DEFERRED |
| `domain_packs/mnp/fixtures/eligibility-use-case/schemas` | 1 | DOMAIN_SPECIFIC | Retained inside the MNP pack |

No generated or duplicate schema authority was found at entry. The new public
catalog therefore becomes the only catalog for the migrated Modeling contracts
and new Toolchain contracts; retained Stage/Phase registries remain internal
until their explicitly deferred migrations.

## Code and packaging findings

- `kg_mnp.modeling.contracts` owned a hard-coded 11-item `CONTRACT_SPECS` tuple.
- `kg_mnp.modeling.registry` read `repository_root()/schemas/modeling` and already
  provided offline resolution, meta-schema checks, local `$ref` resolution and
  cycle detection.
- `kg_mnp.modeling.canonical_json` provided the retained canonical JSON profile.
- `kg_mnp.paths` centralized repository, provisional pack and runtime paths, but
  did not define Project Workspace v1.
- `kg_mnp.loader` retained MNP-specific compatibility paths.
- Setuptools had no package-data declaration, so schemas were unavailable from
  a non-source wheel install.
- Root CLI routed unrecognized commands into the Modeling CLI; no Domain Pack
  or Project Workspace route existed.
- Prompt 1 freeze covered `src/kg_mnp`, `schemas`, `domain_packs/mnp`, tests and
  other retained semantic roots, but not the other two pack directories.

## Pack findings

`minimal`, `mnp`, and `forestry` each contained only a Prompt 1 provisional
manifest. MNP contained the sole migrated semantic asset tree. Its pre-change
content hashes are captured in the local raw audit and will also be committed
as the Prompt 1 MNP preservation golden. Minimal had no semantic assets;
Forestry had no semantic assets and made no implementation claim.

## Implemented audit disposition

- The 11 Modeling schemas moved at 100% Git similarity into packaged Contract
  resources; pre- and post-move SHA-256 and `$id` values match.
- The authoritative Catalog contains 20 entries: 11 retained Modeling and nine
  Toolchain schemas. Catalog digest is
  `b6bf0748a8330f2841eb5d1ce1cf93f8d7bd21e37f763d4a283527e513080f45`.
- Modeling metadata, registry, and canonical JSON modules are thin compatibility
  layers; no second public `CONTRACT_SPECS` authority remains.
- All three Pack manifests are formal v1 documents with deterministic locks.
  MNP declares and locks all 84 assets in the Prompt 1 preservation golden.
- Package-data and isolated Wheel tests prove Catalog/schema loading outside a
  source checkout without repository-root or current-directory arithmetic.
- Retained non-Modeling Stage/Phase schemas remain in place with disposition
  `INTERNAL_CONTRACT_MIGRATION_DEFERRED`.
