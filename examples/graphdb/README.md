# Stage 07 GraphDB import package examples

`expected/` contains four deterministic `GraphDBImportPackage` golden outputs.
They are generated only from the frozen Stage 03 runtime TBox and independently
validated Stage 06 compilation packages. Runtime GraphDB data, logs, HTTP
responses, credentials, and import attestations are intentionally excluded.

Regenerate the closed package sets with:

```bash
python scripts/generate_graphdb_goldens.py
```
