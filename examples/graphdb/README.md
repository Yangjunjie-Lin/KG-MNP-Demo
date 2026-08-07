# Stage 07 GraphDB import package examples

`expected/` contains four deterministic `GraphDBImportPackage` golden outputs.
They are generated only from the frozen Stage 03 runtime TBox and independently
validated Stage 06 compilation packages. Runtime GraphDB data, logs, HTTP
responses, credentials, and import attestations are intentionally excluded.

Regenerate the closed package sets with:

```bash
python scripts/generate_graphdb_goldens.py
```

The physical default graph is verified separately from SPARQL's configured
default dataset. The runtime client sends
`GET /repositories/<repository-id>/rdf-graphs/service?default` with
`Accept: application/n-triples`, parses only that response, rejects blank nodes
or malformed RDF, and records the HTTP status, statement count, and semantic
hash in the live attestation. A named-graph-only repository may still expose
named-graph data to a plain SPARQL pattern; that visibility is not used as the
physical storage assertion. The licensed GraphDB 11.4.2 run observed HTTP 200
with `application/n-triples` and zero parsed statements for the empty physical
default graph, while the ordinary no-`GRAPH` SPARQL pattern returned named-graph
data. These independently observed results are frozen in the live attestation.

Stage 07 semantic dataset hashing follows RDF 1.1 string-literal equivalence:
an explicit `xsd:string` and the corresponding plain string literal hash as the
same RDF term. This is required because GraphDB 11.4.2 serializes an imported
explicit `xsd:string` as its equivalent plain form. Stage 06 canonical bytes are
unchanged by this GraphDB-specific semantic normalization.

Rejected/deferred review decisions are projected through the same Stage 06
Candidate-to-RDF functions into the audit-only
`forbidden-business-assertions.{nt,json}` artifacts. The artifacts are closed
by the import manifest and the verifier executes an exact RDF-term `VALUES`
check against the business graph. `MAPPING_ASSERTION` and unresolved issues are
represented explicitly as `NOT_APPLICABLE` with a controlled reason.
