# Deterministic RDF

Canonical UTF-8 LF N-Triples and N-Quads are the authoritative serializations.
Lines are sorted by their escaped RDF terms and blank nodes are forbidden in
formal compiled graphs. Turtle and TriG are fixed-prefix human-readable views
generated from the same triples/quads; RDFLib's insertion order is never used as
an authority hash.
