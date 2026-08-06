# Provenance Model

Every compiled business assertion receives a stable `owl:Axiom` record in the
modeling provenance graph. Source records, source fields, mapping rules and
modeling evidence are deduplicated by semantic content. Review decisions remain
separate records in the review audit graph. No new Stage 06 ontology classes
are declared; compiler metadata belongs in `compilation-manifest.json`.

The final ReviewDecisionLog is a `prov:Entity`, its stable review session is a
`prov:Activity`, and the stable reviewer is a `prov:Agent`. Only individual
human decisions are instances of `mnp:ReviewDecision`. Session start/end and
decision times are emitted as `xsd:dateTime`; reviewer identity, display name,
role, and affiliation are retained when present.
