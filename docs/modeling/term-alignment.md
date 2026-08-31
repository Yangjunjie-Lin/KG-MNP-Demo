# Deterministic Term Alignment

The built-in aligner emits `EXACT_IRI`, `EXACT_LABEL`, `NORMALIZED_LABEL`,
`DECLARED_ALIAS`, `DECLARED_SYNONYM`, `LEXICAL_SIMILARITY`, or `NO_MATCH`.
Scores are integer basis points used only for deterministic ordering; they are
not semantic correctness probabilities.

Every alignment remains `review_required=true`, including exact matches.
Equal-scoring alternatives share an ambiguity group and are not silently
selected. Lexical similarity is always review-required, provider provenance is
kept separate from deterministic lexical evidence, and no alignment mutates
the baseline. Mixed-script/homoglyph risk is surfaced for human inspection.
