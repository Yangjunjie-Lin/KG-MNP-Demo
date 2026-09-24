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


def paired_cluster_aggregate(baseline, experiment, *, aggregate, bootstrap_samples=2000, seed=1729):
    """Re-run the native aggregate on every paired cluster resample.

    Input maps group -> replicate -> list of native payloads. The callback is
    invoked once per replicate with the complete sampled payload list; repeat
    estimates are averaged afterwards, never treated as independent samples.
    Payload multiplicity is preserved; a native SET-micro callback must retain
    its own union semantics. This function never averages sample F1 for it.
    """
    if set(baseline) != set(experiment) or bootstrap_samples < 100:
        raise ValueError("INVALID_PAIRED_AGGREGATE_INPUT")
    keys = sorted(baseline)
    replicates = sorted(baseline[keys[0]]) if keys else []
    if not replicates or any(sorted(side[k]) != replicates for side in (baseline, experiment) for k in keys):
        raise ValueError("PAIRED_REPLICATES_DIFFER")

    def estimate(side, sampled):
        values = [aggregate([row for key in sampled for row in side[key][rep]]) for rep in replicates]
        if any(not math.isfinite(v) for v in values):
            raise ValueError("NONFINITE_NATIVE_AGGREGATE")
        return mean(values)

    baseline_score, experiment_score = estimate(baseline, keys), estimate(experiment, keys)
    delta = experiment_score - baseline_score
    estimates = {"baseline_score": baseline_score, "experiment_score": experiment_score,
        "difference_unit": "FRACTION_NOT_RELATIVE_PERCENT", "absolute_change_percentage_points": 100 * delta,
        "relative_change_percent": 100 * delta / baseline_score if baseline_score > 0 else None,
        "relative_change_status": "DEFINED" if baseline_score > 0 else "UNDEFINED_NONPOSITIVE_BASELINE"}
    if len(keys) < 2:
        return {**estimates, "status": "INSUFFICIENT_INDEPENDENT_UNITS", "difference": delta, "confidence_interval_95": None,
            "p_value": None, "independent_groups": len(keys), "replicate_count": len(replicates),
            "baseline_confidence_interval_95": None, "experiment_confidence_interval_95": None,
            "absolute_change_percentage_points_ci95": None, "relative_change_percent_ci95": None}
    rng = random.Random(seed)
    boot, baseline_boot, experiment_boot, relative_boot = [], [], [], []
    for _ in range(bootstrap_samples):
        sampled = rng.choices(keys, k=len(keys))
        left_value, right_value = estimate(baseline, sampled), estimate(experiment, sampled)
        boot.append(right_value - left_value)
        baseline_boot.append(left_value)
        experiment_boot.append(right_value)
        if left_value > 0:
            relative_boot.append(100 * (right_value - left_value) / left_value)
    # Exact paired cluster exchange for small n; MC otherwise. Repeat vectors
    # are swapped as a unit. Non-additive metrics are recomputed, not sign-flipped.
    exact = len(keys) <= 12
    patterns = range(2 ** len(keys)) if exact else [rng.getrandbits(len(keys)) for _ in range(bootstrap_samples)]
    extreme, count = 0, 0
    for mask in patterns:
        left = {k: (experiment if mask & (1 << i) else baseline)[k] for i, k in enumerate(keys)}
        right = {k: (baseline if mask & (1 << i) else experiment)[k] for i, k in enumerate(keys)}
        extreme += abs(estimate(right, keys) - estimate(left, keys)) >= abs(delta) - 1e-12
        count += 1
    def interval(values):
        ordered = sorted(values)
        return [ordered[int(.025 * len(ordered))], ordered[int(.975 * len(ordered))]]

    delta_ci = interval(boot)
    relative_defined = baseline_score > 0 and len(relative_boot) == bootstrap_samples
    return {**estimates, "status": "MEASURED", "difference": delta, "confidence_interval_95": delta_ci,
        "baseline_confidence_interval_95": interval(baseline_boot), "experiment_confidence_interval_95": interval(experiment_boot),
        "absolute_change_percentage_points_ci95": [100 * value for value in delta_ci],
        "relative_change_percent_ci95": interval(relative_boot) if relative_defined else None,
        "relative_change_ci_status": "DEFINED" if relative_defined else "UNDEFINED_BOOTSTRAP_NONPOSITIVE_BASELINE",
        "confidence_interval_method": "PAIRED_SOURCE_CLUSTER_PERCENTILE_BOOTSTRAP_ALL_REPLICATES",
        "bootstrap_samples": bootstrap_samples,
        "p_value": extreme / count if exact else (extreme + 1) / (count + 1), "independent_groups": len(keys),
        "replicate_count": len(replicates), "resampling_unit": "SOURCE_CLUSTER_ALL_REPLICATES", "native_aggregate_recomputed": True,
        "test": "EXACT_PAIRED_CLUSTER_EXCHANGE" if exact else "MONTE_CARLO_PAIRED_CLUSTER_EXCHANGE", "seed": seed}
