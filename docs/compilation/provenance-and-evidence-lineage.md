# Provenance and Evidence Lineage

The domain-neutral vocabulary uses PROV-O and RDF reification. Each compiled
statement has a stable ID and binds graph role/IRI, confirmed candidate,
review log/hash, provider snapshots, KG-IR/evidence references, compilation
activity and compiler snapshot. Review audit records declared reviewer IDs and
roles without treating them as cryptographic identity. Evidence lineage links
only authorities that exist; it never fabricates evidence. The package gate
requires 10,000 basis-point reference closure, which does not assert evidence
truth.
