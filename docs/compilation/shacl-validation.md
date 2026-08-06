# SHACL Validation

Stage 06 uses the frozen `foundation-instance` profile from
`shapes/foundation-instance-shapes.ttl`. Profiles are copied with LF-normalized
source bytes and hashes into the compilation directory. pySHACL runs offline
with RDFS inference, `advanced=false`, `js=false`, and no automatic repair.

Raw result blank-node identities are discarded. Every report RDF term is
projected explicitly as an IRI, a Literal with lexical form/datatype/language,
or a structural node with a content-derived stable IRI. The N-Triples report is
rebuilt from that projection, so a Literal is never coerced into an IRI and a
runtime blank-node label is never published. Results have stable semantic IDs
and deterministic JSON and N-Triples serializations. Violations block
compilation; warnings and infos are recorded.
