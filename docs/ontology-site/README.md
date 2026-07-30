# Ontology site

Generated with pinned WIDOCO **v1.4.25** (`widoco-1.4.25-jar-with-dependencies_JDK-17.jar`).

```bash
bash scripts/generate_docs.sh
```

Expected artifacts after a successful run:
- `index.html` (copied from `index-en.html` if needed)
- `index-en.html`
- `provenance/` metadata pages
- `resources/` static assets / cross-refs
- serialized `ontology.ttl` / `.owl` / `.nt` / `.jsonld`

Core pytest does **not** require this folder to be populated; JAR downloads are gitignored under `third_party/widoco/`.
