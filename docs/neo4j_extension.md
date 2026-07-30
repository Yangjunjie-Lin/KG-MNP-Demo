# Neo4j + neosemantics (n10s) — practical graph backend

MVP offline RDF tests still do **not** require Neo4j. CLI defaults to **rdf**; Neo4j must be selected with `--backend neo4j`.

## Start Neo4j

1. Install and start **Docker Desktop**.
2. From `kg-mnp-demo`:

```bash
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
docker compose up -d
python -m pip install -e ".[neo4j]"
python -m kg_mnp_demo.cli neo4j-ping
```

- Browser UI: http://localhost:7474  
- Bolt: `bolt://localhost:7687`  
- Auth: `neo4j` / `kgmnp-demo-pass` (from compose / `.env.example`)

Plugins via `NEO4J_PLUGINS='["apoc","n10s"]'`.

## Workflow

```bash
python -m kg_mnp_demo.cli neo4j-up          # print setup instructions
python -m kg_mnp_demo.cli neo4j-load --case CASE-03 --reset
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend neo4j
python -m kg_mnp_demo.cli trace --case CASE-03 --backend neo4j
python -m kg_mnp_demo.cli run-all --backend neo4j
```

Offline (no Neo4j):

```bash
python -m kg_mnp_demo.cli evaluate --case CASE-03 --backend rdf
python scripts/showcase_demo.py
pytest   # core suite; neo4j tests skip if DB down
pytest -m neo4j
```

## What runs where

| Step | Engine |
|------|--------|
| SHACL / OWL-RL / eligibility rules | Python (deterministic) |
| Persist case + assessment + reasons | Neo4j (n10s RDF import + Cypher MERGE overlay) |
| Trace paths | Cypher in `queries/cypher/` |

## Cypher path shape

```cypher
(c:MNPCase)-[:hasEligibilityAssessment]->(a)
  -[:producesBlockingReason]->(r)
  -[:supportedByEvidence|triggeredByRule|citesClause|recommendsAction]->()
```

## Troubleshooting

| Symptom | Action |
|---------|--------|
| `neo4j-ping` fails | Ensure Docker is running; `docker compose ps`; wait for healthcheck |
| n10s import error | Overlay Cypher store still writes assessment; check `neo4j_load.rdf_import` in JSON |
| Auth failed | Match password in compose and `NEO4J_PASSWORD` |
| Port in use | Change host ports in `docker-compose.yml` |

Stop: `docker compose down` (add `-v` to wipe volumes).
