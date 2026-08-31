# Ontology Modeling Evaluation Protocol

## Experimental unit

An experiment fixes a Contract Catalog/Lock, Project and Domain Pack locks,
approved scope, CQ set, KG-IR/evidence closure, baseline snapshot, provider
snapshots and recorded model bytes, limits, review policy, and an expert gold
standard when accuracy metrics are reported. Repetitions use fresh absolute
workspace paths and preserve raw artifacts and decision logs.

## Metrics

Report scope requirement coverage; CQ structural coverage; baseline reuse and
new-concept proposal rates; candidate evidence and unsupported-candidate rates;
conflict and prevalidation pass/review/fail rates; review acceptance,
modification, rejection, deferral, and reviewer-correction rates; deterministic
reproduction rate; time to first proposal and confirmed package; and, only
against a versioned human gold standard, precision/recall/F1 for term
alignment, field mapping, TBox candidates, and ABox assertions.

Each metric must publish numerator, denominator, exclusions, confidence
interval method where applicable, provider snapshot, dataset/pack identity, and
reviewer protocol. Determinism compares canonical bytes and semantic IDs across
runs and paths; model-output reproducibility is reported separately from
recorded-byte reproducibility.

## Prohibited interpretations

Provider scores are not probabilities or accuracy. Review acceptance is not
semantic accuracy. Structural CQ coverage is not CQ execution success.
Precision/recall/F1 is not reported without an expert gold standard. Prompt 4
does not claim full OWL consistency, final SHACL validation, hallucination
reduction percentages, cross-industry improvement, or Forestry performance.
