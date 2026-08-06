# ModelingProposal

A ModelingProposal is a deterministic, non-publishable review artifact. It
records the exact input semantic hash and exact versions and hashes of the
ontology baseline, mapping rules, terminology profile, proposal policy, and
generator.

It may contain candidate entities, ABox candidate assertions, review-only
issues, and unmapped fields. Every candidate and issue has a content-derived
identifier. All generated review statuses are `PROPOSED`; high confidence,
an existing target term, or a confirmed mapping rule never changes that.

For Stage 04:

```json
"run_mode": "DATASET_MODELING"
"schema_delta_candidates": []
```

`ONTOLOGY_RELEASE` mode and TBox candidates are unsupported. The artifact is
JSON, not RDF, and is not written into `ontology/`. Stage 05 may review it into
a `ConfirmedModelingPackage`, but that package still cannot drive OWL, SHACL,
RDF, GraphDB, or WebVOWL publication until a later compiler stage.

Business fact evidence and modeling evidence remain separate fields. Proposal
values include only what is needed to state a candidate or review issue; the
complete source dataset is not copied into the artifact.

