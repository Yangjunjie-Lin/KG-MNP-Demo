# Product Surface

Use `kg-mnp lifecycle` for registry initialization/import, feedback and change
proposals, semantic diff/version checks, consumer and impact analysis,
regression plans, release candidates and human review, and environment
activation/rollback. Commands emit a stable JSON envelope with a lifecycle exit
code and never expose a traceback unless `--debug` is supplied.

No command fetches a package, rewrites an ontology, bumps a version, approves a
release, mutates a published release, writes to GraphDB/OMS/ODS/OSS, or
activates an environment without an explicit human control-plane action.
