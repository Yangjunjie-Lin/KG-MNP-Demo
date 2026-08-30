# MNP Domain Pack

Status: **MIGRATED_BASELINE**

This pack contains the historical mobile-number-portability baseline migrated
from generic repository roots. Migrated asset types include:

- ontology modules and the import catalog;
- MNP case and reference RDF fixtures;
- JSON case inputs and the legacy eligibility example contract;
- TM Forum mappings and evidence references;
- terminology and domain review sources;
- SHACL shapes and eligibility rules;
- competency questions and application/domain queries.

The formal `pack.yaml` enumerates the frozen Prompt 1 assets and
`pack.lock.json` binds their exact content deterministically. The migration
preserves historical IRIs and normalized semantic content; a dedicated golden
inventory rejects changes to the 84 Prompt 1 assets.

`MIGRATED_BASELINE` does not mean `STABLE`, cross-industry, production-ready,
or independently revalidated. The Manifest and Lock do not elevate retained
eligibility behavior into the toolchain product core.
