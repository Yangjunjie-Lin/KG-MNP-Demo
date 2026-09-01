# SHACL Final Validation

Final validation runs effective ABox against effective shapes with effective
TBox as ontology graph. pySHACL is offline with RDFS inference, imports and
JavaScript disabled, advanced features disabled, and Meta-SHACL enabled.
Deterministic result IDs and order are rebuilt from semantic result content.
Any Violation, engine error or timeout fails; warnings and infos remain
reported according to policy.
