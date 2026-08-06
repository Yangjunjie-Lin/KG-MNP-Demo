# Candidate RDF Mapping

The Stage 06 mapping table is closed:

| Candidate kind | RDF result |
|---|---|
| `ENTITY` | one `rdf:type` assertion for `proposed_iri` and `class_iri` |
| `CLASS_ASSERTION` | one `rdf:type` assertion for the confirmed subject |
| `OBJECT_PROPERTY_ASSERTION` | one resource triple using confirmed subject/object entities |
| `DATA_PROPERTY_ASSERTION` | one typed or language-tagged literal triple |
| `MAPPING_ASSERTION` | rejected until a typed object contract exists |

No labels, identifiers, domain/range axioms, or inferred triples are added
implicitly. Null literals, unknown kinds, ontology terms used as instances, and
unconfirmed references fail closed.
