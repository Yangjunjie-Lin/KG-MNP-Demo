# Stage 01 Repository Baseline

## Baseline

| Field | Recorded value |
|---|---|
| Repository | `Yangjunjie-Lin/KG-MNP-Demo` |
| Default branch | `main` (`origin/HEAD -> origin/main`) |
| Baseline SHA | `110867d6a5b50371cb4fe8e650b87bfbef8d4588` |
| Baseline log | `110867d Implement KG-MNP demo updates` |
| Initial status | ` M runtime_logs/fullstack.out.log` |

The initial log modification predated this migration and was recorded before
cleanup. Because `runtime_logs/` is an explicitly generated artifact scheduled
for removal in Stage 01, both tracked log files were deleted after the
workspace-specific processes were stopped; no reset or commit was used.

## Pre-migration file map

| Path | Role at baseline | Stage 01 treatment |
|---|---|---|
| `README.md` | Eligibility/fullstack demo entry | Rewritten as ontology-foundation entry |
| `pyproject.toml` | Python core plus API and Neo4j extras | API/Neo4j dependencies and scripts removed |
| `Makefile` | Python, frontend, Docker, Neo4j, E2E gates | Reduced to five Python-only targets |
| `.github/workflows/ci.yml` | Python, frontend, Docker, fullstack E2E | Reduced to Python ontology-core checks |
| `.dockerignore` | Docker build-context exclusions | Removed with the Docker entry points |
| `docker-compose.yml` | Neo4j/n10s backend | Removed |
| `docker-compose.fullstack.yml` | API, frontend, fullstack runtime | Removed |
| `frontend/` | React/Vite application, mocks, E2E, Nginx | Removed (223 tracked files) |
| `config/` | Ontology catalog plus fixed diagram configs | Catalog retained; diagram configs removed |
| `schemas/` | Case, API, and fixed diagram schemas | Case schema retained; API/diagram schemas removed |
| `ontology/` | OWL/Turtle modules | Retained unchanged semantically |
| `shapes/` | SHACL shapes | Retained |
| `mappings/` | TM Forum mapping | Retained |
| `queries/` | SPARQL and Neo4j Cypher | SPARQL retained; Cypher removed |
| `references/` | Source and license audit | Retained; stale Neo4j entries removed |
| `data/` | Nine RDF cases and reference facts | Retained |
| `src/kg_mnp_demo/` | RDF core, eligibility, API, storage, Neo4j | Core/example retained; API/storage/Neo4j removed |
| `tests/` | Core plus API/storage/frontend integration | Core ontology/RDF/example tests retained |
| `scripts/` | Core checks plus fullstack/API scripts | Core checks retained; obsolete scripts removed |
| `runtime_logs/` | Tracked local server logs | Removed from version control and ignored |
| `runtime_data/` | Local SQLite/artifacts | Untracked runtime data removed and ignored |
| `runtime_outputs/` | Generated local outputs | Untracked outputs removed and ignored |
| `demo_outputs/` | Versioned research snapshots | Retained intentionally |
| `docs/ontology-site/` | Generated WIDOCO output | Removed and ignored; regenerate on demand |

## Legacy system entry points

- Central task: deterministic MNP eligibility decision and traceability demo.
- Frontend: `frontend/src/main.tsx` and `frontend/src/app/App.tsx`.
- API: `kg-mnp-api` -> `kg_mnp_demo.api.app:main` and `/api/v1` routers.
- Eligibility: `src/kg_mnp_demo/pipeline.py`, `kg-mnp`, evaluator and rule engine.
- Execution history: `src/kg_mnp_demo/storage/`, SQLite, artifact repositories,
  and `scripts/seed_demo_data.py`.
- Neo4j: root `docker-compose.yml`, `neo4j_*.py`, Cypher queries, CLI commands,
  optional dependency, and integration tests.
- Fixed diagram: `canonical_business_diagram_v2` config/schema/checker, the
  five-layer business-role projection, fixed geometry tests, and screenshots.

The frontend and fixed-diagram files were confirmed in Git history at
`110867d` and earlier commits before deletion.

## CI and Docker dependencies removed

The old workflows installed Node 20, ran `npm ci`, generated OpenAPI types,
executed frontend unit/build jobs, installed Playwright Chromium, ran browser
E2E, and built/started the fullstack Compose file. These jobs and the API,
frontend, fullstack, and Neo4j Docker definitions were removed.

The root `.dockerignore` was removed because no Docker build context remains.
`.gitattributes` now pins shell scripts to LF so the optional documentation
generator remains parseable on Windows checkouts.

The current CI installs Python, checks repository hygiene and references, and
runs the scoped ontology-core Python suite. The full retained eligibility
regression suite remains available through `make test`, but is not part of the
Stage 01 gate. Neither path requires Node, Docker, GraphDB, WebVOWL, or an
external database.

## Assets intentionally retained

- All OWL modules in `ontology/` and their catalog.
- `shapes/mnp-shapes.ttl` and pySHACL tests.
- RDFLib loaders, OWL-RL inference, RDF builder, and their tests.
- `mappings/tmf_to_mnp.yaml`, SPARQL queries, competency questions, and source
  audit material.
- Nine case datasets, JSON inputs, eligibility rules, and versioned demo
  snapshots as the downstream legacy eligibility use case.

The retained eligibility paths are documented in
`examples/eligibility-use-case/README.md`; they are no longer described as the
repository's main modeling pipeline.

## Stage boundary

Stage 01 does not define semantic authority, replace ontology IRIs, implement
modeling proposal schemas, add a new modeling pipeline, or integrate GraphDB
or WebVOWL. Those changes require later stages and separate acceptance.
