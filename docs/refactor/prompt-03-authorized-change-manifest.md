# Prompt 3 authorized change manifest

## Authority

- Source commit: `d04e9b494a99932532ae9c359653878aa32261d7`
- Target branch: `codex/plugin-ingestion-kgir-p03`
- Prompt 2 protected file count: 1,052
- Prompt 2 protected tree digest: `e39390641d4518c8e56614637a06dfe29d7c8a1d8fb9275ef40376bc2e500fe1`
- Repository tracked file count at entry: 1,146

## Authorized additions and modifications

Prompt 3 authorizes additive ingestion contracts, the Plugin SDK, built-in
Plugin metadata and implementations, Source Store and ingestion modules,
public CLI routes, tests, reviewed examples, documentation, package metadata,
Makefile gates and a `toolchain-ingestion` CI job. It authorizes deterministic
regeneration of the single catalog and catalog lock, migration of controlled
Project Lock goldens made stale by the new catalog, and an audited expansion
of the protected snapshot.

The following remain protected and are not authorized to change in content:
the original 20 schema files, three Domain Pack locks and semantic assets, MNP
84-asset golden content, modeling/review/compiler/publication/activation
contracts, and historical ancestry assertions.

## Final inventory

- Final repository file count: 1,272 (1,146 baseline + 126 additions).
- Final protected file count: 1,161.
- Final protected tree digest:
  `1e57eb06d004c7f2f3e42ddabd51ac2c3957dfc0fba77000aa0e95530f3d77eb`.
- Protected roots: unchanged `src/kg_mnp`, `schemas`, `config`, `domain_packs`,
  `deploy`, `scripts`, `tests`, `web`, and `examples`.
- Catalog: 34 entries, semantic digest
  `984c2031a36e6332c0c0a5724dc0dabbeb1f6f07f8389c3bda02e6744dccb5ed`,
  lock ID
  `urn:kg-mnp:contract-catalog-lock:2f6a21f2533bf466437139cc0749dcfc43b6994ff0c8272d9918c7c45eb185be`.

### Added files by authority area

| Area | Count | Contents |
|---|---:|---|
| Public contracts | 14 | Compatible Contract Catalog schema 1.1 plus 13 Prompt 3 contracts under the single toolchain schema directory. |
| Plugin SDK | 39 | API/models, manifest/discovery/registry/selection/snapshot/security/conformance/CLI, 13 built-ins and 13 manifests. |
| Ingestion core | 21 | Source Store, media detection, planning, parsers, normalization, evidence/KG-IR/quality, transaction, Artifact integration, validation and CLI. |
| Tests and fixture package | 28 | Prompt 3 contract/plugin/source/parser/evidence/KG-IR/quality/security/CLI tests and an independent external wheel fixture. |
| Documentation | 17 | ADR, architecture, public Plugin/ingestion guides, evaluation protocol, and four audit matrices. |
| Reviewed examples | 5 | README plus TXT, Markdown, JSON, and CSV inputs; generated binaries remain ignored. |
| Reproducibility scripts | 2 | Deterministic optional fixture generator and complete CLI smoke runner. |

### Modified existing files

| File(s) | Authorized reason and compatibility effect |
|---|---|
| `.github/workflows/ci.yml`, `Makefile` | Add the capability-named `toolchain-ingestion` job and Prompt 3 offline/component gates; retain every earlier gate. |
| `README.md`, `docs/product/*`, target architecture | Report the implemented Prompt 3 slice and keep deferred capabilities honest. |
| `THIRD_PARTY_NOTICES.md`, `pyproject.toml`, `src/kg_mnp/__init__.py` | Add bounded document extras, entry points, package data/notices and release version 0.3.0. |
| `src/kg_mnp/contracts/catalog*.json`, `contracts/catalog.py` | Deterministically migrate the one Catalog/Lock to schema 1.1 and 34 entries. |
| `src/kg_mnp/root_cli.py` | Add four public Prompt 3 routes while preserving legacy dispatch. |
| Contract/CLI/product tests | Migrate exact catalog count/version/package assertions from Prompt 2 to Prompt 3 and add package-content checks. |
| `tests/refactor/_historical_freeze.py` | Authorized additive protected snapshot update after all prerequisite preservation/component gates. |

No files were moved or deleted. No Project Lock golden required a committed
rewrite; runtime workspaces correctly report an old catalog binding as stale and
deterministically re-lock. The original 20 schemas, all three Pack Locks, MNP
semantic assets, modeling/review/compiler/publication/activation contracts, and
historical ancestry constants remain byte-identical. Runtime outputs and logs
remain ignored and are not authorized committed artifacts.
