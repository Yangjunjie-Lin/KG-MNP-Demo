# Prompt 1 Baseline Audit

## Identity and safety gate

| Item | Verified value |
|---|---|
| Repository | `Yangjunjie-Lin/KG-MNP-Demo` |
| Initial branch | `main` |
| Initial HEAD | `e45da340267de8d4b7b3a54177822aa641e3a601` |
| `origin/main` | `e45da340267de8d4b7b3a54177822aa641e3a601` |
| Refactor branch | `codex/ontology-toolchain-refactor-p01` |
| Baseline Tag | `kg-mnp-phase06-baseline-2026-08-30` (annotated) |
| Baseline Tag target | `e45da340267de8d4b7b3a54177822aa641e3a601` |
| Initial worktree | Clean |
| Python | 3.12.6 |
| pip | 26.1.2 |

The required fetch, status, branch, SHA, log, Tag, and remote checks were run
before any destructive operation. `origin/main` matched the expected SHA and no
user modifications were present.

## Existing package and entry points

Before refactor:

- distribution: `kg-mnp-demo` 0.1.0;
- Python package: historical namespace recorded in the migration matrix;
- root CLI: `kg-mnp` routed to `root_cli:main`;
- eligibility CLI: `kg-mnp-eligibility` routed to the domain-specific CLI.

## Repository inventory

Top-level tracked product areas included `.github`, `competency_questions`,
`config`, `data`, `demo_outputs`, `deploy`, `docs`, `examples`, `inputs`,
`mappings`, `ontology`, `queries`, `references`, `rules`, `schemas`, `scripts`,
`shapes`, `src`, `tests`, `third_party`, and `web`. Local ignored caches,
virtual environments, temporary evidence folders, build output, and runtime
reports were also present but were not tracked.

`src` contained the root eligibility/pipeline modules and capability packages
for modeling, compilation, GraphDB, WebVOWL, publication, application,
workbench, diagnostics, governance, amendment, and activation.

Test domains included root MNP tests plus activation, amendment, application,
application governance, cases, competency questions, compilation, diagnostics,
governance, GraphDB, modeling, ontology, ontology release, publication,
reasoner, review, schema governance, scripts, WebVOWL, and workbench.

Stage/Phase names occurred in 359 files. Explicitly named scripts included the
Stage 03 catalog/build utilities, Stage 05/06 example generators, and
Application Phase 01–06 artifact verifiers. These remain protected pending the
later capability-based test/CI cleanup.

## Domain coupling

The audit found 768 files containing MNP/eligibility/porting/account/billing or
related domain terms. The principal authority roots were `ontology`, `data`,
`inputs`, `mappings`, `rules`, `shapes`, `competency_questions`, and `queries`.
MNP coupling also exists in configuration, examples/goldens, scripts, tests,
web applications, IRIs, and retained eligibility internals. See the dedicated
[inventory](domain-coupling-inventory.md).

## Tracked generated artifacts

- `demo_outputs`: 11 tracked files, including generated JSON, inference,
  validation, trace, what-if, summary, and HTML output.
- `runtime_outputs`, `runtime_reports`, `runtime_logs`: zero tracked files.
- reviewed golden artifacts under `examples/**/expected` and test fixtures were
  retained.

## Dependencies

Runtime dependencies were `rdflib==7.6.0`, `pyshacl`, `owlrl`, `PyYAML`,
`jsonschema`, `fastapi==0.115.0`, and `uvicorn==0.30.6`. Development dependencies
were pytest 8.x, Ruff 0.16.2, and httpx 0.27.2; Playwright was an optional WebVOWL
extra.

## CI structure

The single workflow contained Python core and offline jobs plus separately
gated integration jobs for GraphDB, publication/WebVOWL, application,
workbench, diagnostics, governance, amendment, and activation. Commercial
GraphDB and browser-dependent work remained in explicit integration jobs. No
existing semantic gate was removed in Prompt 1.

## Baseline validation

| Command | Result | Counts / notes |
|---|---|---|
| `python -m pip install -e ".[dev]"` | PASS | Editable install completed; pip reported unrelated pre-existing `deepeval` environment conflicts. |
| `python -m ruff check .` | FAIL | 323 existing violations; 239 reported as safely fixable. No claim of a green lint baseline. |
| `python -m pytest -q` | PASS | 1057 collected; 1054 passed; 3 skipped; 0 failed; 0 xfailed; approximately 18m50s. |
| `make verify-repo-hygiene` | PASS | Existing hygiene script passed. |
| `make verify-stage-06` | PASS | Repository, ontology, reasoner, schema, modeling, review, compilation, security, CLI, and boundary sub-gates passed. |
| `make verify-application-phase-06-offline` | PASS | Application through activation offline sub-gates passed; existing platform/concurrency skips remained visible. |

No licensed GraphDB live integration, Docker-backed integration, or new browser
download was run as part of this baseline. Those commands are not reported as
passing. Detailed command output is local-only under
`runtime_reports/refactor/prompt-01/` and is ignored by Git.

## Post-refactor validation

The first complete post-refactor run intentionally exposed stale relocation
assumptions rather than hiding them: 1073 tests were collected, with 1028
passed, 29 failed, 13 setup errors, and 3 skipped in 1928.302 seconds. The
failures were limited to old competency-question paths, exact legacy-term scan
roots/lines, path-derived application goldens, retained authority fixture
identities, and historical freeze tests comparing the authorized namespace and
Domain Pack migration against pre-migration commits. Every group was repaired
and rerun; no test was removed, skipped, xfailed, or weakened.

Final results:

| Command | Result | Counts / notes |
|---|---|---|
| `python -m pip install -e ".[dev]"` | PASS | `kg-mnp-toolchain==0.2.0.dev0` installed editable in 47.5s. |
| `python -m ruff check .` | PASS | All repository checks passed; the 323 baseline violations were repaired. |
| `python -m pytest --collect-only -q` | PASS | 1073 tests collected. |
| `python -m pytest -q` | PASS | 1070 passed; 3 skipped; 0 failed; 0 errors; 0 xfailed; 1952.3s. |
| `make verify-repo-hygiene` | PASS | No tracked runtime output, secret-like file, cache, old source package, or duplicate top-level authority; 5.8s. |
| `make verify-toolchain-foundation` | PASS | 16/16 Prompt 1 tests plus import and both CLI bootstrap commands; 23.3s. |
| `make verify-stage-06` | PASS | Full retained ontology/modeling/review/compiler chain, including local ROBOT/HermiT reasoner verification; 1080.4s. |
| `make verify-application-phase-06-offline` | PASS | Full retained offline Application-to-Activation chain; 103 activation tests passed and 3 existing platform/concurrency tests skipped; 1188.4s. |
| namespace and roadmap greps | PASS | No active `kg_mnp_demo`, Stage 09, or Phase 07 match outside the three permitted migration-audit documents. |
| tracked runtime/secret/cache scan | PASS | Zero tracked runtime paths, secret/cache filenames, forbidden history directories, or duplicate top-level MNP authorities. |

The exact post-migration retained semantic tree is guarded across 978 intended
files by a cross-platform-normalized SHA-256 snapshot while separately proving
the historical closure commits and immutable baseline Tag remain ancestors.
This replaces stale byte comparisons to pre-rename paths without allowing
unreviewed semantic drift.

No live GraphDB/Docker integration, commercial-license integration, or fresh
browser download was run post-refactor. Those remain
`NOT_RUN_EXTERNAL_PREREQUISITE`, not PASS. Existing local caches and virtual
environment contents are ignored and are not repository artifacts.
