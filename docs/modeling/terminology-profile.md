# Terminology Profile

`config/modeling/terminology-profile-1.0.0.yaml` is a versioned label and alias
profile over terms already present in the Stage 03 inventory. It does not
define ontology terms, domains, ranges, subclass axioms, or equivalence axioms.

Term IRIs are checked exactly and case-sensitively against the frozen term
inventory. Preferred labels, aliases, and normalized forms support review and
matching only. If one normalized alias points to more than one term, the full
set must be declared in an ambiguity group. The generator may report those
matches but must not silently choose one.

The profile intentionally covers only terms used by the Stage 04 rule set and
examples rather than copying the entire ontology inventory.

