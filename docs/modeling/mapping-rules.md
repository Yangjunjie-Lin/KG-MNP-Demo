# Versioned Mapping Rules

The executable rule set is `config/modeling/mapping-rules-1.0.0.yaml`. Only
rules with uppercase `CONFIRMED` status execute. A rule uses an exact RFC 6901
pointer, a declared JSON value type, one allowed candidate kind, a full target
term IRI, and one transform from the finite registry.

Entity references used by assertion rules are wired through explicit entity
rule IDs. No Python expression, `eval`, dynamic template, unrestricted
JSONPath, user script, or natural-language transformation is executable.
Unknown transforms and target terms fail closed.

`mappings/tmf_to_mnp.yaml` remains a standards-alignment reference and
modeling-evidence source. Its OpenAPI component paths, lowercase historical
status, explanatory transformation prose, and legacy selection flag are not
runtime instructions. In particular:

```text
TM Forum OpenAPI / JSON Schema alignment
!=
OWL logical equivalence
```

The generator never interprets `related`, `broader`, or `narrower` as an OWL
equivalence axiom.

