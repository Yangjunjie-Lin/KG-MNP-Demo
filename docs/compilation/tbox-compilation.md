# TBox Compilation

The TBox compiler dispatches Class, Object/Data Property, Subclass, Domain,
Range and pairwise Disjoint candidates. Reuse/alignment must resolve in the
locked baseline and emits no duplicate declaration. New declarations must be
inside the approved namespace and cannot collide with a baseline IRI. RDFLib
terms produce a stable overlay ontology header, delta and effective closure;
generated graphs contain no blank nodes.
