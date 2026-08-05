# OWL and SHACL Semantics

## OWL

OWL is used for open-world semantics:

- Class and property definitions
- Logical axioms
- Type inference
- Subclass inference
- Equivalence and disjointness
- Semantic reasoning

OWL Domain and Range are inference axioms, not database column type checks.

Example:

```text
ownsPhoneNumber domain Subscriber
```

Given:

```text
X ownsPhoneNumber Y
```

a reasoner may infer:

```text
X rdf:type Subscriber
```

That inference is not a traditional field-type validation error.

## SHACL

SHACL is used for closed-world data quality checks:

- Required fields
- Cardinality limits for validation
- Datatypes
- Value ranges
- Controlled values
- Pre-publication data checks

## Must not confuse

Forbidden interpretations:

- Mechanically copy every OWL Domain/Range into a SHACL violation
- Call a SHACL violation an OWL logical inconsistency
- Treat OWL cardinality as a database non-null constraint
- Interpret missing triples as negated facts

## Future constraint metadata

Later stages may model constraints with fields such as:

- `semantic_layer`
- `constraint_type`
- `target_scope`
- `severity`
- `closed_world`

Stage 02 freezes the semantic boundary only. It does not implement a complete
constraint schema.
