# Domain Coupling Inventory

## Direct MNP authority assets

- ontology root, modules, import catalog, module configuration, baseline
  manifest, term inventory, and reasoner evidence;
- MNP case RDF and JSON fixtures, regulations, source systems, and case history;
- TM Forum field mappings and source review records;
- eligibility rule catalog, SHACL shapes, competency questions, and SPARQL
  queries;
- application query registry and terminology/mapping profiles.

These assets move to `domain_packs/mnp` in Prompt 1, except the historical term
inventory and reasoner documentation under `docs/ontology`, which remain
release evidence and are flagged for later package-bound relocation.

## Retained domain-coupled code

The eligibility CLI implementation, namespaces, loader, input adapter,
mappings, rule engine, evaluator, pipeline, RDF builder, trace graph, and
showcase code remain temporarily in the renamed package. They are retained only
to protect existing regression coverage and are classified
`DOMAIN_SPECIFIC_RELOCATION_PENDING`; the public eligibility console script is
removed.

## Retained capability packages requiring generalization

- `application`, `workbench`, and `diagnostics` still assume the historical MNP
  publication/query vocabulary;
- `governance`, `amendment`, and `activation` retain application-phase contracts;
- `graphdb`, `webvowl`, and `publication` retain concrete package identities and
  scenario assumptions;
- `modeling` and `compilation` are the semantic core but still consume MNP
  baseline dependencies and example goldens.

## Tests, scripts, examples, and web

Tests and scripts contain substantial domain terminology and numbered boundary
assertions. They are updated for package/path identity but not deleted or
weakened. Reviewed `examples/**/expected` artifacts remain authorized golden
fixtures. Web applications remain prototypes pending unified Workbench work.

## Future boundary work

Later prompts must replace direct MNP dependency loading with a formal Domain
Pack/Workspace contract; relocate eligibility code and remaining release
evidence; generalize adapter configuration; and reorganize tests, scripts, CI,
and UI by stable capability. No forestry or cross-industry implementation is
inferred from the Prompt 1 layout.
