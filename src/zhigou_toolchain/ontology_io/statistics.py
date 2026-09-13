"""Paired document/group statistics; repeated calls are not independent units."""
from __future__ import annotations

import math
import random
from statistics import mean


def paired_comparison(baseline, experiment, *, bootstrap_samples=2000, seed=1729):
    if bootstrap_samples < 100 or any(not math.isfinite(v) for groups in (baseline, experiment) for values in groups.values() for v in values):
        raise ValueError("INVALID_STATISTICAL_INPUT")
    if set(baseline) != set(experiment):
        raise ValueError("PAIRED_GROUPS_DIFFER")
    if any(not baseline[key] or len(baseline[key]) != len(experiment[key]) for key in baseline):
        raise ValueError("PAIRED_REPLICATES_DIFFER")
    # Each value is the set of replicate scores for one independent group.
    delta = [mean(experiment[key]) - mean(baseline[key]) for key in sorted(baseline)]
    if len(delta) < 2:
        return {"status": "INSUFFICIENT_INDEPENDENT_UNITS", "independent_groups": len(delta), "difference": mean(delta) if delta else None,
            "confidence_interval_95": None, "p_value": None, "resampling_unit": "DOCUMENT_OR_ONTOLOGY_GROUP"}
    rng = random.Random(seed)
    samples = sorted(mean(rng.choices(delta, k=len(delta))) for _ in range(bootstrap_samples))
    observed = abs(mean(delta))
    extreme = sum(abs(mean(d * rng.choice((-1, 1)) for d in delta)) >= observed for _ in range(bootstrap_samples))
    return {"status": "MEASURED", "difference": mean(delta), "confidence_interval_95": [samples[int(.025 * bootstrap_samples)], samples[int(.975 * bootstrap_samples)]],
        "p_value": (extreme + 1) / (bootstrap_samples + 1), "test": "PAIRED_SIGN_RANDOMIZATION_MONTE_CARLO",
        "independent_groups": len(delta), "resampling_unit": "DOCUMENT_OR_ONTOLOGY_GROUP", "bootstrap_samples": bootstrap_samples,
        "seed": seed, "difference_unit": "FRACTION_NOT_RELATIVE_PERCENT"}


def holm_adjust(p_values):
    """Holm step-down correction across the preregistered primary family."""
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in p_values.values()):
        raise ValueError("INVALID_P_VALUE")
    adjusted, previous = {}, 0.
    for index, (name, value) in enumerate(sorted(p_values.items(), key=lambda row: (row[1], row[0]))):
        previous = max(previous, min(1., value * (len(p_values) - index)))
        adjusted[name] = previous
    return adjusted
