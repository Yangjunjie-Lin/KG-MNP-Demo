# Prompt 5 Authorized Change Manifest

Authorized additions are the 24 Prompt 5 schemas, Catalog 1.2 entries, the
domain-neutral `kg_mnp.semantic_kernel` package, its policy/vocabulary
resources, compile/package CLI routes, Prompt 5 tests, documentation, Make/CI
gates, and the 0.5.0 package version. Authorized modifications are limited to
the single Catalog/Lock, package-data configuration, generic primitive wrappers
used by Stage 06, root CLI dispatch, capability documentation, generators,
tests that assert the migrated Catalog count, and the historical freeze after
all gates pass.

The 59 pre-Prompt-5 public schemas and every Domain Pack semantic asset and
Pack Lock are immutable. Runtime workspaces, packages, `.kgop` files, reasoner
caches, test logs, secrets, registry data, and GraphDB data are excluded from
version control. No file is moved or deleted. Prompt 4 artifacts are retained
as history and never rebound.

The freeze was updated only after the Prompt 5 functional, preservation,
packaging, Ruff, Prompt 4, Stage 06, Application Phase 06 non-snapshot, and
full non-snapshot test gates passed. The prior protected identity was 1,253
files with SHA-256
`b2f6e753171932aec8afe96ada74b3c9c4de77947f2b0e48031d5bb55403f5e1`;
the authorized Prompt 5 identity is 1,356 files with SHA-256
`ecce5e1a77eb73547fb3372d3117d7770be01680ac152aeea981894f3497bb4e`.
Protected roots were not reduced, and Prompt 4 commit
`eccc5092831503974c8aa54f158e6674445b1cb4` is now an explicit ancestry gate.
