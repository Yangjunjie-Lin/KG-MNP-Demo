# IngestionPlan and IngestionRun v1

The Prompt 3 planner is `DETERMINISTIC_CORE`, not an Agent. It validates the
current ProjectLock/Catalog, SourceBatch and blobs; selects media detector,
parser, normalizer and structural evaluator providers; snapshots them; and
binds all finite limits and policies into `plan_id`. Missing providers,
signature/extension conflicts and selection ambiguity produce `UNRESOLVED`.

Execution replays detection, verifies every snapshot, parses and normalizes,
binds evidence in Core, closes KG-IR and computes the structural gate. Formal
files are staged below `tmp/ingestion/<run-hash>` and committed to build,
evidence, IR and validation artifact directories while holding an atomic
Workspace lock. Failures remove staging and leave no partial formal run.

Existing run IDs are reusable only after all documents, ArtifactManifests and
referenced hashes revalidate. Tamper and partial-directory states fail closed.
`artifacts/confirmed`, `artifacts/packages` and publication registries remain
outside ingestion authority.
