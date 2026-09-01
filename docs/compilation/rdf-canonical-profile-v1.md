# KG-MNP RDF Canonical Profile v1

Canonical NT and NQ are UTF-8/LF, BOM-free, de-duplicated, lexically sorted,
one statement per line, with one final LF when non-empty. NQ sorting keys are
graph, subject, predicate and object. Turtle/TriG use deterministic prefixes
and sorted statements but are readable projections, not the sole semantic
digest basis.

Generated authority graphs forbid blank nodes. Locked baseline blank nodes are
canonicalized by RDF structure and replaced with stable skolem IRIs while the
original baseline bytes remain in the package. Prefix collisions fail. This
profile does not claim URDNA2015.

N-Quads cannot serialize an empty named graph. Empty authoritative graph roles
therefore remain explicit zero-count rows in the RDF Dataset Manifest and
contribute their empty-graph semantic digest, while producing no N-Quads line.
Strict verification requires every non-empty manifest graph to be present,
rejects undeclared serialized graphs, and reconstructs zero-count roles as empty
graphs before validating graph digests and the normalized package identity.
