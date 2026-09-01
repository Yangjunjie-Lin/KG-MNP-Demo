# ABox Compilation

Individuals, class assertions, typed/language data assertions and object
assertions are compiled in dependency-safe order. Subjects, classes,
properties and objects must exist with the correct OWL type. RDF lexical forms
and language tags are validated without conversion or repair. Duplicate facts,
functional conflicts and Data/Object Property confusion fail the transaction.
