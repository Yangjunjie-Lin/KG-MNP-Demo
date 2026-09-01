# OWL Validation

OWL 2 DL profile validation and consistency are separate mandatory gates.
ROBOT 1.9.7/HermiT 1.4.5.456 executes with an argument array, `shell=False`, a
fixed JAR SHA-256, local canonical input, bounded output and timeout, and no
download/import. Missing prerequisites report `NOT_RUN_EXTERNAL_PREREQUISITE`
or `REASONER_UNAVAILABLE`; neither can create a valid strict package. OWL-RL
structural analysis is never described as full DL consistency.

The locked MNP closure historically uses seven standard DCTERMS/SKOS predicates
as annotations without explicit OWL declarations. Prompt 5 adds a deterministic,
semantically inert validation bridge that declares only actually used standard
predicates as `owl:AnnotationProperty` and records which locked asset required
each declaration. It does not modify Domain Pack bytes, invent domain axioms,
or weaken ROBOT's OWL 2 DL profile gate.
