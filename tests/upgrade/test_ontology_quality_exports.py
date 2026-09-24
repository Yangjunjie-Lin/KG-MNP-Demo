"""Synthetic statistics/report verification, not measured model performance."""
import csv
import json
from copy import deepcopy
from statistics import mean

import pytest

from zhigou_toolchain.ontology_io.quality_exports import (
    quality_tables,
    write_quality_tables,
)
from zhigou_toolchain.ontology_io.statistics import paired_cluster_aggregate


def test_absolute_relative_effects_and_score_intervals_share_paired_clusters():
    left = {f"g{i}": {0: [.2], 1: [.4]} for i in range(4)}
    right = {f"g{i}": {0: [.3], 1: [.5]} for i in range(4)}
    result = paired_cluster_aggregate(left, right, aggregate=mean, bootstrap_samples=100)
    assert result["baseline_score"] == pytest.approx(.3)
    assert result["experiment_score"] == pytest.approx(.4)
    assert result["difference"] == pytest.approx(.1)
    assert result["absolute_change_percentage_points"] == pytest.approx(10)
    assert result["relative_change_percent"] == pytest.approx(100 / 3)
    assert result["confidence_interval_95"] == pytest.approx([.1, .1])
    assert result["baseline_confidence_interval_95"] == pytest.approx([.3, .3])
    assert result["experiment_confidence_interval_95"] == pytest.approx([.4, .4])
    assert result["relative_change_percent_ci95"] == pytest.approx([100 / 3, 100 / 3])
    assert result["independent_groups"] == 4 and result["replicate_count"] == 2


def test_zero_baseline_relative_effect_is_undefined_not_infinity():
    left = {"a": {0: [0]}, "b": {0: [0]}}
    right = {"a": {0: [.5]}, "b": {0: [.5]}}
    result = paired_cluster_aggregate(left, right, aggregate=mean, bootstrap_samples=100)
    assert result["difference"] == .5 and result["relative_change_percent"] is None
    assert result["relative_change_percent_ci95"] is None
    assert result["relative_change_status"] == "UNDEFINED_NONPOSITIVE_BASELINE"
    json.dumps(result, allow_nan=False)


def test_zero_baseline_resample_does_not_get_dropped_to_narrow_relative_ci():
    left = {"a": {0: [0]}, "b": {0: [.5]}}
    right = {"a": {0: [.1]}, "b": {0: [.6]}}
    result = paired_cluster_aggregate(left, right, aggregate=mean, bootstrap_samples=100)
    assert result["relative_change_percent"] is not None
    assert result["relative_change_percent_ci95"] is None
    assert result["relative_change_ci_status"] == "UNDEFINED_BOOTSTRAP_NONPOSITIVE_BASELINE"


def test_unequal_cluster_sizes_keep_sample_weights_and_negative_effects():
    left = {"a": {0: [.2]}, "b": {0: [.6, .6, .6]}}
    right = {"a": {0: [.1]}, "b": {0: [.5, .5, .5]}}
    result = paired_cluster_aggregate(left, right, aggregate=mean, bootstrap_samples=100)
    assert result["baseline_score"] == .5 and result["experiment_score"] == .4
    assert result["absolute_change_percentage_points"] == pytest.approx(-10)
    assert result["confidence_interval_95"] == pytest.approx([-.1, -.1])


def test_single_source_does_not_gain_ci_by_repeating_model():
    result = paired_cluster_aggregate({"a": {0: [.2], 1: [.4]}}, {"a": {0: [.3], 1: [.5]}}, aggregate=mean, bootstrap_samples=100)
    assert result["baseline_score"] == pytest.approx(.3)
    assert result["confidence_interval_95"] is None and result["relative_change_percent_ci95"] is None
    assert result["independent_groups"] == 1 and result["replicate_count"] == 2


def fixture():
    summaries, pairs = [], {}
    for task in ("flagship", "reuse"):
        for system in ("DirectGeneralLLM", "DirectBudgetControl", "TwoAgentKernelV1"):
            summaries.append({"task": task, "system": system, "sample_count": 3, "runs": 9, "completed": 9, "failed": 0,
                "status": {"status": "MEASURED"}, "primary_metrics": ["score"], "metrics": [{"name": "score", "source": "SYNTHETIC_FIXTURE",
                    "matching": "exact", "status": "MEASURED", "value": .5}]})
        for baseline in ("DirectGeneralLLM", "DirectBudgetControl"):
            pairs[(task, baseline)] = {"status": "MEASURED", "comparison": {"metrics": {"score": {
                "status": "MEASURED", "p_value": .02, "confidence_interval_95": [.01, .2], "difference": .1,
                "baseline_score": .4, "experiment_score": .5, "absolute_change_percentage_points": 10,
                "absolute_change_percentage_points_ci95": [1, 20], "relative_change_percent": 25,
                "relative_change_percent_ci95": [2, 45], "independent_groups": 3, "replicate_count": 3}}}}
    return summaries, pairs


def test_holm_applies_across_tasks_and_both_baselines_not_just_each_pair():
    summaries, pairs = fixture()
    result = quality_tables(summaries, pairs)
    assert result["primary_family_complete"] and result["primary_family_size"] == 4
    assert all(row["holm_adjusted_p"] == .08 for row in result["effects"])
    assert all(row["supported_positive_effect"] is False for row in result["effects"])


@pytest.mark.parametrize("missing", ["pair", "failed_summary", "unscorable_pair"])
def test_missing_primary_preserves_null_and_whole_correction_family(missing):
    summaries, pairs = fixture()
    if missing == "pair":
        pairs.pop(("reuse", "DirectGeneralLLM"))
    elif missing == "failed_summary":
        summaries[3]["failed"] = 1
    else:
        pairs[("reuse", "DirectGeneralLLM")]["status"] = "UNSCORABLE"
    result = quality_tables(summaries, pairs)
    assert not result["primary_family_complete"] and result["primary_family_size"] == 4
    assert all(row["holm_adjusted_p"] is None and row["supported_positive_effect"] is None for row in result["effects"])
    blocked = next(row for row in result["effects"] if row["task"] == "reuse" and row["baseline"] == "DirectGeneralLLM")
    assert blocked["difference"] is None


def test_blocked_task_remains_visible_without_fabricated_metric(tmp_path):
    summaries, pairs = fixture()
    summaries += [{"task": "cq2onto", "system": system, "sample_count": 6, "runs": 18, "completed": 0, "failed": 18,
        "status": {"status": "BLOCKED_NATIVE_SCORER"}, "primary_metrics": ["Axiom"], "metrics": []}
        for system in ("DirectGeneralLLM", "DirectBudgetControl", "TwoAgentKernelV1")]
    before = deepcopy(summaries)
    result = write_quality_tables(tmp_path, summaries, pairs)
    assert summaries == before and result["primary_family_size"] == 6 and not result["primary_family_complete"]
    assert len(result["quality_scores"]) == 9
    rows = list(csv.DictReader((tmp_path / "quality-scores.csv").open(encoding="utf-8-sig")))
    assert all(row["score"] == "null" for row in rows if row["task"] == "cq2onto")
    assert (tmp_path / "QUALITY_REPORT.md").is_file()
    assert json.loads((tmp_path / "quality-and-effects.json").read_text())["official_ranking"] is False
