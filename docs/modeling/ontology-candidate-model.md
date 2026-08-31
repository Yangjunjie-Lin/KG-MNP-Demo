# Closed Ontology Candidate Model

Candidates are partitioned into TBox, Mapping, ABox, and SHACL. TBox supports
class/property declarations and subclass/domain/range/disjoint axioms. Mapping
supports record-to-class, field/reference mappings, value maps, IRI templates,
and null policy. ABox supports individuals and class/data/object assertions.
SHACL supports node/property shapes and closed cardinality, datatype, class,
node-kind, and enumerated-value constraints.

Bodies are structured JSON, never RDF/Turtle, free SHACL, Python, Shell,
Jinja, or SPARQL UPDATE. Every candidate records KG-IR, EvidenceRecord, Domain
asset, CQ, baseline, provider snapshot, model invocation, and dependency
references plus rationale and support status. Core identity uses only the
closed semantic body, kind, scope, and action; provider IDs are rejected.

Same semantic signatures merge evidence, provider provenance, and rationales.
Conflicts cover IRI/type/label/domain/range/datatype/subclass/cardinality,
mapping/literal/provider/evidence, out-of-scope, and namespace cases.
Unsupported or out-of-scope candidates remain auditable but are blocking and
cannot enter a confirmed package. Provider agreement never equals approval.
