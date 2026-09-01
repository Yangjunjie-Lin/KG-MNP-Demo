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
