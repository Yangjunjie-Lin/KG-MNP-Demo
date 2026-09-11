"""Quality routing and field/text profiles over the existing verified KG-IR."""
from __future__ import annotations

from collections import Counter
from importlib.metadata import version

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.modeling.control_plane.mappings import table_identity


def check_input(dataset: dict, quality: dict) -> dict:
    evidence = {e["evidence_id"] for e in dataset["evidence_records"]}
    usable, quarantined = [], []
    for item in dataset["items"]:
        missing = sorted(set(item.get("evidence_refs", [])) - evidence)
        reasons = (["MISSING_EVIDENCE"] if not item.get("evidence_refs") else [])
        if missing:
            reasons.append("UNKNOWN_EVIDENCE_REFERENCE")
        reasons.extend(item.get("quality_flags", []))
        row = {"item_id": item["item_id"], "item_kind": item["item_kind"],
               "original_item": item, "reasons": reasons, "missing_evidence_refs": missing}
        (quarantined if reasons else usable).append(row)
    return {"dataset_id": dataset["dataset_id"], "quality_policy": "EVIDENCE_REQUIRED_V1",
            "usable": usable, "quarantined": quarantined, "pending": [], "upstream_quality": quality,
            "limits": "Evidence closure was reverified by verified_run. Business rules are not inferred from quality scores."}


def profile_data(dataset: dict, checked: dict) -> tuple[dict, dict[str, str]]:
    # Optional analysis dependency: core startup/import never loads pandas.
    import pandas as pd

    usable = {i["item_id"] for i in checked["usable"]}
    fields: dict[str, list] = {}
    texts = []
    evidence = {e["evidence_id"]: e for e in dataset["evidence_records"]}
    headers = {}
    for item in dataset["items"]:
        if item["item_kind"] == "table-cell" and item["payload"]["row"] == 1:
            headers[(table_identity(item, evidence), item["payload"]["column"])] = item["payload"]["value"]["normalized_lexical_value"]
    for item in dataset["items"]:
        if item["item_id"] not in usable:
            continue
        if item["item_kind"] == "table-cell":
            if item["payload"]["row"] == 1:
                continue
            identity = table_identity(item, evidence)
            field = str(identity) + ":" + str(headers.get((identity, item["payload"]["column"]), item["payload"]["column"]))
            fields.setdefault(field, []).append(item["payload"]["value"]["normalized_lexical_value"])
        elif item["item_kind"] == "scalar-field":
            fields.setdefault(item["payload"]["field_name"], []).append(item["payload"]["value"]["normalized_lexical_value"])
        elif item["item_kind"] == "text-block":
            text = item["payload"]["text"]
            texts.append({"item_id": item["item_id"], "text": text, "code_point_length": len(text),
                          "evidence_refs": item["evidence_refs"], "text_hash": semantic_hash(text)})
    profiles = []
    for field, values in sorted(fields.items()):
        series = pd.Series(values, dtype="object")
        profiles.append({"field": field, "sample_count": len(values), "isna_count": int(series.isna().sum()),
                         "empty_string_count": sum(v == "" for v in values),
                         "nunique": int(series.nunique()), "types": dict(Counter(type(v).__name__ for v in values)),
                         "examples": series.dropna().drop_duplicates().head(5).tolist()})
    return {"dataset_id": dataset["dataset_id"], "fields": profiles, "texts": texts,
            "sample_size": len(usable), "position_unit": "UNICODE_CODE_POINT_HALF_OPEN",
            "rule_inference": "NONE: 样本统计不产生必填或唯一业务规则。"}, {"pandas": version("pandas")}
