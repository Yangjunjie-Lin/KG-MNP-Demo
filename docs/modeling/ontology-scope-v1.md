# Ontology Scope v1

`OntologyScope` is the immutable control document that says what a Prompt 4
modeling run may describe. It binds one Project Lock, the selected Domain Pack
locks, KG-IR datasets, modeling intent, target partitions, namespace policy,
language policy, IRI minting policy, acceptance gates, and prohibited
operations. Target object families are requirements, not confirmed classes or
instances.

New IRIs are limited to `https` and `urn`, to the approved namespace list, and
to deterministic human-readable slugs or content hashes. RDF, RDFS, OWL, XSD,
and SHACL namespaces are recorded as read-only. `file`, `javascript`, `data`,
and `ftp` IRIs and filesystem paths are rejected.

Before any provider runs, a human produces an `OntologyScopeApproval` with a
stable reviewer ID, role, decision, and rationale. Its semantic hash excludes
timestamps and display names. Any scope byte or semantic change makes that
approval stale. `REJECT` and `REQUEST_CHANGES` cannot authorize a proposal;
there is no auto-approval route.

The CLI surface is `kg-mnp model scope init|validate|inspect|approve|status`.
Approval proves a recorded human decision, not the real-world identity of the
reviewer; organizational identity controls remain external.
