# Prompt 2 Authorized Change Manifest

This manifest authorizes only the Contract Kernel, formal Domain Packs,
Project Workspace v1, associated CLI/tests/docs/package resources, and the
minimum compatibility edits needed to keep Prompt 1 behavior intact.

## Before state

- Prompt 1 head: `a7114eef25f2f2a262cd69793a8d3e2b444836fc`.
- Protected roots: `src/kg_mnp`, `schemas`, `config`, `domain_packs/mnp`,
  `deploy`, `scripts`, `tests`, `web`, and `examples`.
- Protected file count: 978.
- Protected tree digest:
  `25bb5818de52132f71056d543f3b019aeb8bbbe9a04bf2b82ff522b89e7c4c24`.
- Total tracked file count: 1063.

## Authorized changes

- Add `kg_mnp.contracts`, `kg_mnp.domain_packs`, and `kg_mnp.workspace`.
- Move the 11 public Modeling schemas into package resources without changing
  bytes or identifiers.
- Add nine Toolchain Draft 2020-12 schemas and one authoritative catalog/lock.
- Replace three provisional pack manifests, add deterministic pack locks, and
  add the minimal contract-test semantic assets.
- Add tests, golden locks, documentation, ADR, Makefile gates and a CI job.
- Extend root CLI routing while preserving every legacy route.
- Update package data and schema-identifier scanning for installed resources.
- Expand Prompt 1 snapshot protection to all Domain Packs only after Prompt 2
  tests, locks and MNP content preservation pass.

## Explicitly unauthorized

No MNP semantic asset may change. No Forestry ontology or data may be invented.
No Plugin SDK, ingestion, LLM provider, compiler rewrite, final ontology
package, semantic diff, REST API, Workbench rewrite, backend abstraction, or
Stage/Phase cleanup is authorized.

## After state

- Protected roots: `src/kg_mnp`, `schemas`, `config`, `domain_packs`, `deploy`,
  `scripts`, `tests`, `web`, and `examples`.
- Protected file count: 1052.
- Protected tree digest:
  `e39390641d4518c8e56614637a06dfe29d7c8a1d8fb9275ef40376bc2e500fe1`.
- Total repository file count after applying the authorized working set: 1146
  (83 net additions over the 1063-file Prompt 1 tree).
- Prompt 1 head ancestry: PASS.
- Historical baseline ancestry and immutable tag target: PASS.
- MNP preservation golden: PASS, 84 Prompt 1 assets; all 84 are now declared
  in the formal Manifest and bound by the Pack Lock.

## Added inventory

- `src/kg_mnp/contracts/`: Contract Kernel, Catalog/Lock, nine Toolchain
  schemas, and packaged Modeling resources.
- `src/kg_mnp/domain_packs/`: local Registry, resolution, validation, locking,
  data-only security, models, and CLI.
- `src/kg_mnp/workspace/`: Workspace v1 layout, service, status, validation,
  security, locking, models, and CLI.
- `domain_packs/*/pack.lock.json` and the six real minimal test assets.
- `scripts/generate_contract_catalog.py`,
  `scripts/generate_prompt02_pack_manifests.py`,
  `scripts/generate_mnp_prompt01_content_golden.py`, and
  `scripts/normalize_domain_pack_text.py`.
- Prompt 2 contract/domain/workspace/security/CLI/packaging tests and the MNP
  preservation golden.
- Prompt 2 Contract, Domain Pack, Workspace, architecture, ADR, audit, and
  compatibility documentation.

## Modified inventory

- Packaging/resource declarations, schema identifier scan, root CLI routes,
  Modeling compatibility wrappers, `.gitattributes`, Makefile, CI, current
  product/architecture documents, Domain Pack READMEs/manifests, and narrowly
  affected legacy routing/freeze tests.
- MNP semantic asset bytes and identifiers were not changed. LF comparison is
  normalized by the preservation gate and `.gitattributes`; the only MNP
  authority changes are `pack.yaml` and the new generated `pack.lock.json`.

## Moves and deletions

- Eleven `schemas/modeling/*.schema.json` files moved with 100% Git similarity
  into `src/kg_mnp/contracts/schemas/modeling/`; every SHA-256 and `$id` is
  unchanged.
- No other file was deleted. The former Modeling paths disappear only as the
  source side of those audited moves; no second authoritative copy remains.

The update was authorized only after Contract/Pack/Workspace gates, 84-asset
MNP preservation, retained regression without freeze (1134 passed, 6 skipped),
and all 14 freeze tests passed. Final commit and push evidence is recorded in
the Prompt 2 Final Report so this manifest does not require a self-referential
commit hash.
