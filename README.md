# KG-MNP Ontology Toolchain

> Evidence-bound, review-governed and deterministic ontology engineering toolchain

**Current status:** Toolchain Contract Kernel — Prompt 2

KG-MNP is being repositioned as a pluggable, verifiable and traceable ontology
engineering toolchain. It converts heterogeneous source material into
evidence-bound modeling candidates, subjects those candidates to formal checks
and human review, and allows only a deterministic semantic compiler to produce
authoritative ontology artifacts.

The core product deliverable remains a future **Versioned Ontology Package**.
Prompt 2 freezes the shared contracts beneath that future package: one public
Contract Catalog and offline Registry, formal Domain Pack manifests and locks,
and a deterministic Project Workspace v1. It does not redefine the retained
compiler or claim the final package contract.

## What is implemented now

- `ModelingProposal`, `ReviewDecisionLog`, and `ConfirmedModelingPackage`
  contracts and validation;
- review-governed confirmation with deterministic identifiers and hashes;
- deterministic RDF/Turtle/TriG generation from confirmed packages;
- OWL consistency and SHACL validation;
- modeling provenance and review-audit artifacts;
- publication reconstruction and verification;
- activation and rollback governance;
- offline GraphDB packaging and a read-only application/workbench baseline;
- a packaged Public Contract Catalog with 20 Draft 2020-12 schemas and a
  fully offline Registry;
- Artifact Reference, Artifact Manifest, and Validation Report v1 contracts;
- formal DomainPackManifest/DomainPackLock v1 contracts, local discovery,
  exact-version dependency resolution, validation, and deterministic locks;
- ProjectManifest/ProjectLock and transactional Project Workspace v1; and
- `kg-mnp contracts`, `kg-mnp domain-pack`, and `kg-mnp workspace` CLI routes.

These capabilities are retained from the historical implementation. Some are
still coupled to MNP paths or the former staged command structure and therefore
remain refactor targets.

## What is not implemented yet

The repository does not yet provide a Plugin SDK, multimodal ingestion, the
final Evidence Record or KG-IR contract, an LLM proposal provider, a compiler
rewrite, the final Versioned Ontology Package, semantic diff, a unified REST
API, a unified Workbench, or a generic GraphDB backend. The Forestry Domain
Pack remains a planning scaffold only. No Agent or LLM is an ontology authority.

## Semantic authority

1. LLMs and Agents may create proposals, explanations, or recommended fixes.
2. They may not write authoritative OWL, RDF, SHACL, or production ABox data.
3. Unreviewed candidates cannot enter a Confirmed Modeling Package.
4. Only the deterministic semantic compiler may generate formal semantic
   artifacts from a confirmed package.
5. Feedback creates a Change Proposal; it cannot mutate a released ontology.
6. Domain content enters through Domain Packs. OMS, ODS, OSS, GraphDB, WebVOWL,
   object-query, and action-workflow systems are integration adapters, not
   compilation authorities.

## Architecture

```text
Source Assets -> Evidence-bound IR -> Modeling Proposal
    -> Formal Pre-validation -> Human Review
    -> Confirmed Modeling Package -> Deterministic Semantic Compiler
    -> OWL / RDF / SHACL / Provenance -> Validation
    -> Versioned Ontology Package -> Registry / Controlled Release / Rollback
```

See the [target architecture](docs/architecture/ontology-toolchain-target-architecture.md)
for the control, artifact, authority, plugin, and domain boundaries.

## Repository structure

```text
src/kg_mnp/             Python package, Contract Kernel, Workspace, and retained semantic kernel
domain_packs/           formal data-only DomainPackManifest v1 layout
  minimal/              experimental industry-neutral contract-test assets
  mnp/                  locked migrated historical MNP assets
  forestry/             planned scaffold; no forestry ontology or data
schemas/                retained internal Stage/Phase schemas; public Modeling schemas are packaged
config/                 generic policies and integration configuration
examples/               reviewed deterministic golden artifacts
tests/                  retained regression suite plus Prompt 1 foundation gates
docs/                   product, architecture, ADR, and migration evidence
scripts/                retained verification and historical migration utilities
```

## Local installation

Python 3.11 or newer is required.

```bash
python -m pip install -e ".[dev]"
python -c "import kg_mnp; print(kg_mnp.__name__)"
python -m kg_mnp --help
kg-mnp --help
```

The only public console script is `kg-mnp`. The former eligibility-specific
console entry is no longer part of the product surface. Retained eligibility
code is an internal MNP compatibility layer, not the toolchain's central task,
and is pending relocation or removal in a later Prompt.

## Verification

The Prompt 2 gates are offline and require no GraphDB service or browser:

```bash
python -m ruff check .
make verify-repo-hygiene
make verify-toolchain-foundation
make verify-contract-catalog
make verify-domain-packs
make verify-project-workspace
make verify-prompt-02-offline
make verify-stage-06
make verify-application-phase-06-offline
python -m pytest -q
```

Licensed or live integration targets remain separate and must not be reported
as passing unless their prerequisites are actually available.

## Domain Pack status

| Pack | Status | Meaning |
|---|---|---|
| `minimal` | `EXPERIMENTAL` | Real, minimal, industry-neutral assets for contract and boundary tests; not a production ontology. |
| `mnp` | `MIGRATED_BASELINE` | Historical MNP assets enumerated by a formal manifest and deterministic lock; not cross-industry or `STABLE`. |
| `forestry` | `PLANNED` | Placeholder for the forestry pilot requirement; contains no fabricated ontology, data, or validation result. |

## Documentation

- [Product Charter](docs/product/product-charter.md)
- [Current Capability Matrix](docs/product/current-capability-matrix.md)
- [Research-to-Product Alignment](docs/product/research-to-product-alignment.md)
- [Target Architecture](docs/architecture/ontology-toolchain-target-architecture.md)
- [Contract and Workspace Kernel](docs/architecture/contract-and-workspace-kernel.md)
- [Public Contract Policy](docs/contracts/public-contract-policy.md)
- [Domain Pack Contract v1](docs/domain-packs/domain-pack-contract-v1.md)
- [Project Workspace v1](docs/workspaces/project-workspace-v1.md)
- [ADR-0001](docs/adr/ADR-0001-reposition-as-ontology-toolchain.md)
- [ADR-0002](docs/adr/ADR-0002-public-contract-domain-pack-and-workspace.md)
- [Prompt 1 Baseline Audit](docs/refactor/prompt-01-baseline-audit.md)
- [Repository Migration Matrix](docs/refactor/repository-migration-matrix.md)
- [Domain Packs](docs/domain-packs/README.md)

## Migration note

The former Stage 01–08 and Application Phase 01–06 route is preserved at the
immutable tag `kg-mnp-phase06-baseline-2026-08-30`. Git history and that tag are
the authoritative historical archive; no duplicate legacy source tree is kept.

## License

Licensed under the Apache License 2.0. See [LICENSE](LICENSE) and
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
