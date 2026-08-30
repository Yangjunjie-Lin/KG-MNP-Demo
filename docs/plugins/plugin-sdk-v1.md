# Plugin SDK v1

Plugin SDK v1 is the replaceable execution boundary beneath KG-MNP ingestion.
It uses the `kg_mnp.plugins` entry-point group, frozen dataclass requests and
responses, and runtime-checkable `Protocol` interfaces for source adapters,
media detectors, parsers, normalizers and quality evaluators.

Plugins receive bytes, media types and finite `ResourceLimits`. They do not
receive a Workspace service or Artifact writer. A parser returns `ParsedUnit`;
a normalizer returns `NormalizedUnit`; Core validates those values before it
creates TransformationRecord, EvidenceRecord, KG-IR identifiers or files.
Evidence binding is deliberately not a plugin kind.

Discovery reads installed distribution metadata and exactly one packaged
`kg_mnp_plugin_manifest.json` without calling `EntryPoint.load()`. Built-ins are
explicitly enabled. External installed distributions are listed as `DISABLED`
until their plugin ID is placed on an API/CLI allowlist. Missing optional
dependencies produce `MISSING_DEPENDENCY`; no command installs dependencies or
searches a Workspace/Domain Pack for Python.

Selection filters by explicit preference, kind, capability, media type, API
version, status, determinism and side-effect policy. It then sorts by priority
and plugin ID. An equal highest priority is
`AMBIGUOUS_PROVIDER_SELECTION`, never a random tie-break.

Conformance checks the manifest/snapshot, request and response types, response
authority boundary, finite output, exception conversion and repeated output.
It is a compatibility and reproducibility suite, not a malicious-code sandbox.

```bash
kg-mnp plugin list --json
kg-mnp plugin validate plain-text-parser
kg-mnp plugin snapshot plain-text-parser
kg-mnp plugin conformance plain-text-parser
```
