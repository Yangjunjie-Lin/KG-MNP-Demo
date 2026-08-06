# Security Boundary

Compilation is fail-closed. Direct proposal compilation, blocked or tampered
packages, stale dependencies, schema deltas, unconfirmed references, duplicate
entity IRIs, TBox injection, blank nodes, null literals, SHACL violations, and
non-consistent reasoner results are rejected. Literal content is serialized by
RDF term writers, so quotes, newlines and Turtle-looking text cannot create extra
triples. Artifact hashes are rechecked against an independent authoritative
reconstruction; a manifest self-hash is not an authorization token.
