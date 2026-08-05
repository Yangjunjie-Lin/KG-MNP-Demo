# OWL 2 DL Reasoner Attestation

- Status: `PASS`
- Ontology release version: `1.0.0`
- Root ontology IRI: `https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/kg-mnp`
- Release source hash (SHA-256): `fa6a74a5fb1e2862e04805de58c2ef67e43920a7be785b2fc370a93df1786bfc`
- Release source includes optional alignments: `false`
- Reasoner input semantic hash (SHA-256): `3c5cbf49843c1f7a440c4271b69c28add6ca93bb9364b81959bceb742c638873`
- Reasoner input file hash (SHA-256): `3c5cbf49843c1f7a440c4271b69c28add6ca93bb9364b81959bceb742c638873`
- Reasoner allowlist hash (SHA-256): `9522c8506b1e3cfd52e806b13ed8f5778f0be39a6ac987c647e2b1839db2a36a`
- RDFLib version (canonicalization): `7.6.0`
- ROBOT version: `1.9.7`
- ROBOT JAR SHA-256: `91890c2e83d0f092dd08731376f154b36610544cfbe8685337a1bf7244ccaa2d`
- ROBOT download URL: `https://github.com/ontodev/robot/releases/download/v1.9.7/robot.jar`
- Reasoner name: `HermiT`
- HermiT version: `1.4.5.456`
- Java version: `23.0.2`
- Consistency: `CONSISTENT`
- Unsatisfiable named-class check: `PASS`
- Unexpected equivalent-class check: `PASS`
- Execution command: `python scripts/run_reasoner.py`

The underlying portable ROBOT command template is:

```text
java -jar <ROBOT_JAR> reason --input <REASONER_INPUT> --reasoner hermit --equivalent-classes-allowed all --axiom-generators "SubClass EquivalentClass" --dump-unsatisfiable <UNSAT_DEBUG_ONTOLOGY> --output <REASONED_ONTOLOGY>
```

## Unsatisfiable named classes

- (none)

## Unexpected inferred equivalent classes

- (none)

## Allowlisted inferred equivalent classes

- (none)

## Warnings

- (none)

This Markdown file is generated deterministically from
`docs/ontology/reasoner-attestation.json`; do not edit it independently.
Runtime-only evidence is written under `runtime_reports/ontology/`.
