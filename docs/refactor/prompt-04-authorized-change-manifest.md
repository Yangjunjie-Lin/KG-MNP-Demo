# Prompt 4 Authorized Change Manifest

## Frozen baseline

- Protected file count: 1161.
- Protected tree digest: `1e57eb06d004c7f2f3e42ddabd51ac2c3957dfc0fba77000aa0e95530f3d77eb`.
- Prompt 1: `a7114eef25f2f2a262cd69793a8d3e2b444836fc`.
- Prompt 2: `d04e9b494a99932532ae9c359653878aa32261d7`.
- Prompt 3: `52fb0bc064ed7a715ddc3269d23e89a1a78c917c`.
- Historical baseline: `e45da340267de8d4b7b3a54177822aa641e3a601`.

The 34 Prompt 3 schema resources, Plugin API 1.0 schemas, 13 Prompt 3 plugin manifests and entry points, and all three Domain Pack lock files are byte-frozen. Their protected roots are not narrowed.

## Authorized additions and compatible edits

- New Prompt 4 modeling schemas under `src/kg_mnp/contracts/schemas/modeling/`.
- Compatible Plugin API 1.1 schema resources and proposal-only modeling provider manifests.
- One regenerated authoritative Contract Catalog and Catalog Lock.
- New `src/kg_mnp/modeling/control_plane/` implementation and `model`/`review` root CLI routes.
- Tests for scope, competency questions, baseline, terminology, alignment, providers, candidates, prevalidation, review, confirmation, security, determinism, CLI, E2E, and packaging.
- Prompt 4 architecture, modeling, research, product, ADR, audit, compatibility, and claim-evidence documentation.
- Makefile and CI capability gates named for modeling, not a historical stage/phase.
- Package version change from 0.3.0 to 0.4.0 and package-resource/entry-point additions.
- Freeze snapshot regeneration only after preservation and regression gates pass.

## Audited Prompt 4 snapshot

- New protected file count: 1253.
- New protected tree digest: `b2f6e753171932aec8afe96ada74b3c9c4de77947f2b0e48031d5bb55403f5e1`.
- Protected roots remain exactly: `src/kg_mnp`, `schemas`, `config`, `domain_packs`, `deploy`, `scripts`, `tests`, `web`, and `examples`.
- Added contracts: 22 closed modeling contracts plus compatible Plugin API 1.1 common, manifest, and snapshot contracts; the single Catalog now contains 59 entries.
- Added providers: manual candidate, baseline reuse, rule mapping, and recorded model output, all with `PROPOSAL_ONLY` authority.
- Added control plane and review: scope/approval, competency questions, baseline/terminology/alignment, input bundle, candidates/conflicts, prevalidation, append-only human review/replay, confirmation, transactions, CLI, and ModelingRun state.
- Added tests and Golden controls: Prompt 3 schema/manifest/Pack Lock byte preservation, Prompt 4 contracts and control-plane families, security, determinism, CLI, Minimal/MNP E2E, external provider wheel, packaging, and CI matrix coverage.
- Added documentation: modeling architecture, ADR, evaluation protocol, audit, compatibility, claim-evidence, product alignment, and this authorization record.
- Catalog migration: Prompt 3's 34 contract resources remain byte-identical while the Catalog and Catalog Lock are deterministically regenerated for 59 entries.
- Packaging compatibility: the legacy `kg_mnp.modeling` public exports are lazily resolved so the Prompt 4 `model` and `review` control-plane routes load from an installed Wheel without a repository development root; the legacy functions and fallback CLI remain available unchanged when invoked.
- Defense-in-depth: Baseline Snapshot loading now reuses the existing Domain Pack manifest and lock verifier, so a jointly altered asset/lock pair, forged lock identity, or remote/unlocked `owl:imports` fails closed; regressions also cover inert KG-IR prompt injection, candidate count limits, and stale review authority bindings.
- Authorization evidence before update: all eight Prompt 4 component Make targets passed; Prompt 3 regression selection passed with two skips; Stage 06 passed; and all Application Phase 01–06 tests except the six self-referential historical snapshot callers passed with three skips.

## Explicitly unauthorized

No Domain Pack semantic edits, Forestry implementation, live model call, remote ontology import, authoritative RDF/OWL/SHACL generation, GraphDB write, package registry mutation, publication/activation operation, accept-all/auto-approval, history rewrite, tag replacement, or reduction of existing freeze coverage is authorized.

This snapshot was populated only after the required non-snapshot gates passed. Changing a digest is not evidence that an unauthorized semantic change is acceptable; the Prompt 1, Prompt 2, Prompt 3, and historical baseline ancestry checks remain fail closed.
