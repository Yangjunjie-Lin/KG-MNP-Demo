"""Readable quality/effect reports over existing independently scored outputs.

No generation, scoring gold, imputation, success-only denominators or invented
measurements. Correct the entire preregistered primary comparison family once.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from .statistics import holm_adjust


def quality_tables(summaries, paired_reports):
    """paired_reports maps (task, baseline) to an existing compare() result."""
    tasks = sorted({row["task"] for row in summaries})
    planned = {}
    for task in tasks:
        core_rows = [row for row in summaries if row["task"] == task and row["system"] == "TwoAgentKernelV1"]
        primary = core_rows[0].get("primary_metrics", []) if len(core_rows) == 1 else []
        if not primary:
            # No metric name may be inferred from successful score subsets.
            primary = ["UNAVAILABLE_PREREGISTERED_PRIMARY_METRIC"]
        for baseline in ("DirectGeneralLLM", "DirectBudgetControl"):
            for metric in primary:
                planned[(task, baseline, metric)] = None
    effect_rows, scores = [], []
    qualified = {}
    for row in summaries:
        score_status = row["status"].get("status") if isinstance(row["status"], dict) else row["status"]
        qualified[(row["task"], row["system"])] = score_status == "MEASURED" and row["failed"] == 0
        for metric in row["metrics"]:
            measured = score_status == "MEASURED" and metric["status"] == "MEASURED" and row["failed"] == 0
            scores.append({"task": row["task"], "system": row["system"], "metric": metric["name"],
                "score": metric["value"] if measured else None, "status": "MEASURED" if measured else "UNSCORABLE",
                "sample_count": row["sample_count"], "run_count": row["runs"], "failed": row["failed"],
                "metric_source": metric["source"], "matching": metric["matching"]})
        if not row["metrics"]:
            for metric in row.get("primary_metrics", ["UNAVAILABLE_PREREGISTERED_PRIMARY_METRIC"]):
                scores.append({"task": row["task"], "system": row["system"], "metric": metric, "score": None,
                    "status": score_status, "sample_count": row["sample_count"], "run_count": row["runs"],
                    "failed": row["failed"], "metric_source": None, "matching": None})
    fields = ("baseline_score", "experiment_score", "baseline_confidence_interval_95", "experiment_confidence_interval_95",
        "difference", "confidence_interval_95", "absolute_change_percentage_points", "absolute_change_percentage_points_ci95",
        "relative_change_percent", "relative_change_percent_ci95", "relative_change_status", "relative_change_ci_status",
        "independent_groups", "replicate_count", "p_value", "confidence_interval_method")
    for key in planned:
        task, baseline, metric = key
        paired = paired_reports.get((task, baseline))
        value = ((paired or {}).get("comparison") or {}).get("metrics", {}).get(metric)
        complete = (paired is not None and paired.get("status") == "MEASURED" and value is not None and value.get("status") == "MEASURED"
            and qualified.get((task, baseline), False) and qualified.get((task, "TwoAgentKernelV1"), False))
        available = value if complete and value is not None else {}
        effect_rows.append({"task": task, "baseline": baseline, "experiment": "TwoAgentKernelV1", "metric": metric,
            "status": "MEASURED" if complete else "BLOCKED_OR_INSUFFICIENT_EVIDENCE",
            **{field: available.get(field) for field in fields},
            "primary": True, "holm_adjusted_p": None, "family_complete": False, "supported_positive_effect": None})
        if complete:
            planned[key] = available.get("p_value")
    family_complete = bool(planned) and all(value is not None for value in planned.values())
    corrected = holm_adjust({"|".join(key): value for key, value in planned.items()}) if family_complete else {}
    for row in effect_rows:
        key = "|".join((row["task"], row["baseline"], row["metric"]))
        row.update(holm_adjusted_p=corrected.get(key), family_complete=family_complete,
            correction="HOLM_ALL_PREREGISTERED_TASK_BASELINE_PRIMARY_COMPARISONS")
        if family_complete and row["confidence_interval_95"] is not None:
            row["supported_positive_effect"] = row["confidence_interval_95"][0] > 0 and row["holm_adjusted_p"] < .05
    return {"quality_scores": scores, "effects": effect_rows, "primary_family_complete": family_complete,
        "primary_family_size": len(planned), "official_ranking": False,
        "interpretation": "Frozen task-native local evaluation; no production/expert/official-ranking authority. Null is not zero or no improvement."}


def write_quality_tables(output, summaries, paired_reports):
    output = Path(output)
    tables = quality_tables(summaries, paired_reports)
    (output / "quality-and-effects.json").write_text(json.dumps(tables, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    for name, rows in (("quality-scores.csv", tables["quality_scores"]), ("effects.csv", tables["effects"])):
        with (output / name).open("w", encoding="utf-8-sig", newline="") as stream:
            if not rows:
                continue
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows({k: "null" if v is None else json.dumps(v) if isinstance(v, list) else v for k, v in row.items()} for row in rows)
    lines = ["# Local benchmark quality and paired effects", "",
        "These tables reflect frozen predictions only; they are not an official leaderboard or a production approval.", "",
        "| Task | System | Metric | Score | State |", "|---|---|---|---:|---|"]
    for row in tables["quality_scores"]:
        lines.append(f"| {row['task']} | {row['system']} | {row['metric']} | {row['score'] if row['score'] is not None else 'null'} | {row['status']} |")
    lines += ["", "| Task | Baseline | Metric | Change (percentage points) | 95% CI (percentage points) | Relative change (%) | Holm p |",
        "|---|---|---|---:|---|---:|---:|"]
    for row in tables["effects"]:
        values = [row[name] if row[name] is not None else "null" for name in ("absolute_change_percentage_points", "absolute_change_percentage_points_ci95", "relative_change_percent", "holm_adjusted_p")]
        lines.append(f"| {row['task']} | {row['baseline']} | {row['metric']} | " + " | ".join(map(str, values)) + " |")
    lines += ["", "The Holm primary family is complete: " + str(tables["primary_family_complete"]), "",
        "Negative changes and intervals crossing zero remain visible. A zero baseline makes relative improvement undefined.",
        "Repeated model calls are not independent source samples. Missing primary comparisons block family-wide significance claims."]
    (output / "QUALITY_REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tables
