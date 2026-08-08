# Stage 08 publication goldens

The four packages below bind the Stage 04–07 scenario authorities to one shared,
TBox-only WebVOWL projection. Their publication identifiers differ, while their
`visualization_semantic_hash` values must be identical because ABox/review changes
cannot change the ontology visualization.

These are formal deterministic packages. Browser screenshots, WebVOWL layout
coordinates, Docker state, upstream source checkouts, GraphDB data, and licenses
are runtime evidence and are never part of these goldens.

The offline reconstruction is anchored to the audited OWL2VOWL 0.3.7 raw-output
fixture under `fixtures/`; its SHA-256 is pinned in the WebVOWL runtime policy.
The live `--network none` converter must reproduce that fixture and its normalized
projection byte-for-byte before a publication attestation can be issued.

Regenerate and validate a package with:

```bash
kg-mnp publication build --scenario full-confirmation \
  --output-dir examples/publication/expected/full-confirmation --force
kg-mnp publication validate --scenario full-confirmation \
  --package-dir examples/publication/expected/full-confirmation
```
