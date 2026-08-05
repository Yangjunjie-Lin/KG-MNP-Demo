# Stage 03 — Ontology Release Baseline

## Status

Stage 03 release **1.0.0** comprises the formal IRIs, module ownership,
SHACL profiles, reproducible OWL 2 DL reasoning, machine-readable attestation,
repository hygiene, and runtime legacy-term gates described below. Stage 03 is
PASS only when the complete `verify-stage-03` target succeeds; a stale or
self-declared report is not sufficient.

## Formal IRIs

| Kind | Value |
|---|---|
| Ontology version | `1.0.0` |
| Term namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#` |
| Shape namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/shapes#` |
| Instance base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/data/` |
| Schema base | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/` |
| Modeling Schema namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/modeling/` |
| Legacy Schema namespace | `https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/` |
| Root ontology | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp` |
| Root version IRI | `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/1.0.0/kg-mnp` |

Python package version remains `0.1.0` and is independent of the ontology
release version.

## Artifacts

- `docs/ontology/ontology-audit-report.md`
- `docs/ontology/term-inventory.csv`
- `docs/ontology/term-change-log.csv`
- `docs/ontology/iri-migration.csv`
- `docs/ontology/reasoner-attestation.json` (formal machine-readable proof)
- `docs/ontology/reasoner-report.md`
- `docs/ontology/decisions/ODR-001` … `ODR-006`
- `ontology/kg-mnp.ttl` + `catalog-v001.xml`
- `ontology/mnp-modeling-provenance.ttl`
- SHACL profiles under `shapes/` and `examples/eligibility-use-case/shapes/`
- Legacy eligibility JSON Schema under
  `examples/eligibility-use-case/schemas/mnp_case_input.schema.json`
- `config/reasoner-allowlist.yaml`
- `config/legacy-term-allowlist.yaml`
- `scripts/check_schema_identifiers.py`

Runtime evidence is deliberately separate from formal release proof. A normal
run writes ignored files under `runtime_reports/ontology/`, including
`reasoner-run.json`, `reasoner-input.nt`, `reasoned-ontology.owl`,
`unsatisfiable.txt`, `unexpected-equivalences.json`, and, only when ROBOT emits
an incoherence explanation, `unsatisfiable-debug.owl`. The debug ontology is
not treated as a line-oriented class list.
Normal execution never rewrites either tracked reasoner document.

## Legacy JSON Schema closure

The eligibility input schema was moved out of the repository-level `schemas/`
directory and into its owning example at
`examples/eligibility-use-case/schemas/mnp_case_input.schema.json`. There is no
compatibility copy or symbolic link at the old location. Its identifier is now
`https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/legacy/eligibility/mnp-case-input/1.0`,
under the stable `schemas.legacy` namespace.

This file remains the legacy eligibility input contract. It is not a
`CleanedPartialData` contract and is not an entry point for the future central
Modeling Pipeline. The root `schemas/` directory and its `schemas.modeling`
identifier namespace are reserved for Stage 04 Modeling Contracts; Stage 03
does not create any of those schemas.

`check_schema_identifiers.py` parses repository JSON Schemas, verifies their
Draft 2020-12 declarations, absolute HTTPS identifiers, uniqueness, and
category namespace membership. The check is fully offline: it never resolves
an identifier or downloads a remote schema.

## ROBOT and HermiT supply chain

ROBOT and HermiT are different components. ROBOT is the command-line tool that
loads the input and invokes the reasoner; HermiT is the OWL 2 DL reasoner bundled
as a ROBOT dependency. Their versions must therefore never share one ambiguous
"reasoner version" field.

| Field | Controlled value / source |
|---|---|
| ROBOT version | `1.9.7` |
| ROBOT download | `https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar` |
| ROBOT SHA-256 | `91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d` |
| HermiT version | `1.4.5.456`, read from the fixed JAR's embedded Maven `pom.properties` |
| Java | 17 or newer; the actual run records the Java version |
| RDFLib canonicalizer | exactly `7.6.0`; recorded in runtime and formal proof |

The fixed SHA-256 in source code is the trust anchor. `ensure_robot()` verifies
an existing cache before use. A missing JAR is downloaded only from the URL
above into a temporary file, verified against the fixed hash, and atomically
moved into the cache only after it matches. A local `.sha256` sidecar is not a
trust source. If HermiT dependency metadata cannot be read reliably, its version
must be reported as `UNKNOWN`, never as ROBOT `1.9.7`. This project permits
`UNKNOWN` only for that dependency-version field when the fixed ROBOT artifact,
actual HermiT execution, and all semantic results are verified. An unknown
consistency result or `NOT_RUN` status can never pass.

## Release and reasoner input hashes

The release and reasoner input are related but are not the same byte stream:

- `release_source_hash` fingerprints `ontology/kg-mnp.ttl`, every module marked
  `runtime: true` in `config/ontology_modules.yaml`, the module configuration
  itself, and `ontology/catalog-v001.xml`. The default profile explicitly
  excludes `mnp-alignments.ttl`; an optional-alignment profile requires its own
  independently named hash. Stable relative path labels and LF-normalized UTF-8
  content make this manifest hash independent of checkout location and line
  endings.
- `reasoner_input_semantic_hash` fingerprints the canonical RDF graph actually
  supplied to HermiT after runtime modules are merged and network imports are
  removed. Canonical blank-node labels and sorted canonical statements make it
  stable across repeat runs and operating systems.
- `reasoner_input_file_hash` fingerprints the exact merged file read by ROBOT.
  It provides byte-level run auditability and cannot substitute for the release
  source hash.

The canonical input algorithm is coupled to RDFLib, so `rdflib==7.6.0` is
exactly pinned in both dependency manifests and recorded in the attestation.
This prevents a later 7.x canonicalizer or serializer change from silently
drifting the Stage 03 input hash.

`verify-reasoner-run` recomputes the physical and semantic input hashes from the
runtime artifacts. `verify-reasoner-report` recomputes the current release
source hash and requires the formal attestation, the current successful run, and
the tracked Markdown rendering to agree.

## Reasoner outcomes

The run status distinguishes `PASS`, `FAIL_INCONSISTENT`,
`FAIL_UNSATISFIABLE_CLASSES`, `FAIL_UNEXPECTED_EQUIVALENCES`,
`FAIL_TOOL_ERROR`, and `NOT_RUN`. A non-zero tool exit is not silently
relabelled as ontology inconsistency, and a missing run or missing required
output cannot pass.

The unsatisfiable output parser ignores comments, headings, and `owl:Nothing`
itself, but any unsatisfiable named class fails the gate. Unexpected
`owl:equivalentClass` pairs are computed from the asserted-versus-reasoned graph
delta. Self-equivalence, asserted equivalence, `owl:Nothing` failure items, and
unordered pairs explicitly approved in `config/reasoner-allowlist.yaml` are
excluded; every other inferred pair fails Stage 03.

## Running and attesting

Run the complete gate with:

```bash
make verify-stage-03
```

For focused diagnosis, run the same ordered components explicitly:

```bash
make verify-stage-03-core
make verify-schema-identifiers
make verify-robot-checksum
make reasoner-check
make verify-reasoner-run
make verify-reasoner-report
make verify-no-runtime-legacy-terms
```

Normal execution updates only `runtime_reports/ontology/`. To intentionally
refresh a release proof after reviewing a successful run, use the explicit
promotion mode, then inspect the tracked diff:

```bash
make reasoner-check
make verify-reasoner-run
python scripts/run_reasoner.py --update-attestation
make verify-reasoner-report
git diff --check
git diff -- docs/ontology/reasoner-attestation.json docs/ontology/reasoner-report.md
```

`reasoner-attestation.json` is the single formal data source. The Markdown is a
deterministic rendering of that JSON and must not be edited independently. Its
execution command uses `python scripts/run_reasoner.py` (or symbolic placeholders
such as `<ROBOT_JAR>`), so the tracked proof contains no drive letter, username,
home directory, temporary directory, or local checkout path. Both formal files
record the distinct ROBOT and HermiT versions and the Java version used for the
attested release execution.

## Gates

`verify-stage-03` uses recursive Make invocations to enforce this strict order:

1. Stage 03 core, including Stage 01 and Stage 02 regression gates
2. Offline JSON Schema identifier and schema-governance gate
3. Fixed ROBOT checksum tests
4. Actual HermiT execution
5. Runtime run verification
6. Formal JSON/Markdown report verification
7. Runtime legacy-term scan

CI calls this one complete target, then fails if `git diff --exit-code` is
non-zero or `git status --short` is non-empty. Ignored reasoner runtime evidence
therefore remains available for diagnosis without contaminating the checkout.

The legacy scan covers current code, ontology, shapes, data, schemas, examples,
mappings, rules, queries, competency questions, tests, and scripts. The
`schemas/` scan root remains configured even when no root schema file exists,
so future Stage 04 assets cannot silently reintroduce old identifiers. Both the
old ontology `#` namespace and the HTTP/HTTPS `example.org` document or JSON
Schema `/` namespaces are rejected. Historical IRIs or deprecated names may
remain only where the machine-readable allowlist identifies a migration record,
declaration, decision/history document, or dedicated test fixture. No Neo4j
helper modules remain in the current runtime path.

## Out of scope (Stage 04+)

Stage 03 does not implement Proposal Pipeline schemas, Review/Confirm,
GraphDB, WebVOWL, a new HTTP API, or a frontend. Those remain NOT STARTED and
this closure repair must not create their live schemas or runtime integrations.
