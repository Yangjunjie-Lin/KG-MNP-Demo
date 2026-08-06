# Provenance Model

Every compiled business assertion receives a stable `owl:Axiom` record in the
modeling provenance graph. Source records, source fields, mapping rules and
modeling evidence are deduplicated by semantic content. Review decisions remain
separate records in the review audit graph. No new Stage 06 ontology classes
are declared; compiler metadata belongs in `compilation-manifest.json`.
