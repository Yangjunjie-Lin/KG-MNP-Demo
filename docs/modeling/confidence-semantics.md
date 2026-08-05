# Confidence Semantics

Confidence records the declared support for a candidate; it is not truth,
review confirmation, or publication permission. Candidate confidence contains
a level, an optional score, its basis, and deterministic rule/source
components.

The policy fixes `HIGH`, `MEDIUM`, `LOW`, and `UNKNOWN` score ranges. If both a
rule and field source declare a numeric score, the conservative minimum is
used and the basis is `RULE_AND_SOURCE`. With one component the basis states
which component supplied it; with no score the level is `UNKNOWN`.

Low or unknown confidence produces a `LOW_CONFIDENCE` review issue. A high
confidence candidate remains `PROPOSED`. There is no random, hidden, or LLM
score.

