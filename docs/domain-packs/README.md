# Domain Packs

Domain Packs isolate domain terminology, ontology modules, evidence sources,
mappings, shapes, rules, competency questions, queries, and reviewed fixtures
from the deterministic semantic kernel.

Prompt 2 freezes `DomainPackManifest` and `DomainPackLock` v1. Each `pack.yaml`
is schema- and semantics-validated, each `pack.lock.json` deterministically
binds declared bytes and dependency closure, and the local Registry resolves
only exact local versions. Resolution never downloads content or executes a
Pack file.

Current statuses:

- `minimal`: `EXPERIMENTAL`, with six real, tiny, industry-neutral assets for
  cross-domain contract tests only;
- `mnp`: `MIGRATED_BASELINE`, containing migrated historical assets;
- `forestry`: `PLANNED`, with zero capabilities and assets, representing the
  forestry pilot intention only.

Domain Packs provide content and constraints. They cannot replace human review,
the deterministic compiler, package validation, registry controls, or release
governance.

The formal contract and lock preimage are documented in
[`domain-pack-contract-v1.md`](domain-pack-contract-v1.md) and
[`domain-pack-lock-v1.md`](domain-pack-lock-v1.md). A valid lock proves content
identity, not correctness, production readiness, human review, or release.
