"""OSKGC input whitelist and audited native metric methods, without generation.

Only the public category-level ontology is input. Per-entry triples and schemas
are private scoring targets. Native SS matches the FIRST reference schema with
the predicted relation, and penalizes extra schemas; these behaviours are kept.
"""
from __future__ import annotations

import ast
import hashlib
import math
from collections import defaultdict
from typing import (  # noqa: UP035 - pinned upstream method annotation globals
    Dict,
    List,
    Optional,
    Tuple,
)

from defusedxml import ElementTree as ET

from .contracts import EvaluationScope, ModelingInput

OSKGC_COMMIT = "b6a12ed38f131abb10ba22a785bba1d5d886aee0"
OSKGC_SCORER_SHA256 = "d2684f2fb64e4f47d8b297a2932ea2eafe8fe6c54116b1cbcd319f48de40854c"
OSKGC_HIERARCHY_SHA256 = "070cb4ad219f3083a949fe033fedf1473a9938654a5eb4ffdd065056df77674a"
METHODS = {"calculate_metrics", "calculate_ss_score", "get_distance_between_types", "get_distance_to_root", "process_record", "calculate_scores_from_ss"}


def adapt_oskgc(entry, category_schema, *, split: EvaluationScope = "LOCAL_HOLDOUT"):
    identifier, category = entry.attrib["id"], entry.attrib["category"]
    if category_schema["id"] != category:
        raise ValueError("CATEGORY_SCHEMA_ID_MISMATCH")
    text = entry.findtext("text")
    if not text:
        raise ValueError("OSKGC_TEXT_MISSING")
    # Do not access entry.find('triples') or entry.find('schemas') here.
    schema = {"id": category_schema["id"],
        "entity_types": [{k: row[k] for k in ("id", "label")} for row in category_schema["entity type"]],
        "relations": [{k: row[k] for k in ("id", "label", "domain", "range")} for row in category_schema["relation"]],
        "hierarchy": [{k: row[k] for k in ("id", "label", "domain", "range")} for row in category_schema["hierarchy"]]}
    return ModelingInput(sample_id=identifier, benchmark_id="oskgc", task_id="schema_guided_abox", dataset_version=OSKGC_COMMIT,
        split=split, evaluation_scope=split, group_id=hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest(),
        mode="SCHEMA_ABOX", text=text, allowed_schema=schema,
        requirements=["Extract source-supported triples and the schema/type predictions required by OSKGC.",
            "Use only this category-level ontology; no per-sample target schema is available.",
            "Research only; data licence header/body conflict; exclude data from commercial deliveries."])


def scoring_target(entry):
    """Scoring-side extraction; never call from an Agent or input adapter."""
    return {"triples": [[r.findtext("sub").replace("_", " ").lower(), r.findtext("rel").lower(), r.findtext("obj").replace("_", " ").lower()]
            for r in entry.findall("triples/triple")],
        "schemas": [[r.findtext(k) for k in ("sub", "rel", "obj")] for r in entry.findall("schemas/schema")]}


def hierarchy_from_bytes(raw):
    if hashlib.sha256(raw).hexdigest() != OSKGC_HIERARCHY_SHA256:
        raise ValueError("OSKGC_HIERARCHY_CHANGED")
    hierarchy, children, siblings = {}, {}, {}
    def visit(node, path):
        name = node.get("name")
        if not name:
            return
        hierarchy[name] = [*path, name]
        nodes = node.findall("entity_type")
        children[name] = len(nodes)
        for child in nodes:
            if child.get("name"):
                siblings[child.get("name")] = len(nodes) - 1
            visit(child, [*path, name])
    for child in ET.fromstring(raw).findall("entity_type"):
        visit(child, [])
    return hierarchy, children, siblings


def native_evaluator(raw):
    if hashlib.sha256(raw).hexdigest() != OSKGC_SCORER_SHA256:
        raise ValueError("OSKGC_SCORER_CHANGED")
    original = next(n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == "BaseEvaluator")
    methods = [n for n in original.body if isinstance(n, ast.FunctionDef) and n.name in METHODS]
    if {n.name for n in methods} != METHODS:
        raise ValueError("OSKGC_METRIC_INTERFACE_CHANGED")
    # Original method nodes unchanged; constructor, imports, response parsing,
    # disk output and directory discovery are not executed by the adapter.
    selected = ast.ClassDef(name="BaseEvaluator", bases=[], keywords=[], body=list(methods), decorator_list=[])
    tree = ast.fix_missing_locations(ast.Module(body=[selected], type_ignores=[]))
    namespace = {"math": math, "defaultdict": defaultdict, "Dict": Dict, "List": List, "Tuple": Tuple, "Optional": Optional}  # noqa: UP006
    exec(compile(tree, "locked_oskgc_native_metrics", "exec"), namespace)  # noqa: S102
    return namespace["BaseEvaluator"]()


def score_native(raw_scorer, predictions, targets, hierarchy):
    """Score already-frozen structured projections, with full sample accounting.

    Aggregation mirrors upstream Joint/PipelineEvaluator: micro uses globally
    unioned triple SETS; macro is the mean of per-file rounded macro F1 (not a
    document-weighted mean). This is not an invented ontology composite score.
    """
    if not predictions or set(predictions) != set(targets):
        raise ValueError("OSKGC_PREDICTION_TARGET_INVENTORY_DIFFER")
    evaluator = native_evaluator(raw_scorer)
    evaluator.parse_xml_file = lambda identifier: (targets[identifier]["triples"], targets[identifier]["schemas"])
    all_predictions, all_targets, files, rows, ss_records = [], [], defaultdict(list), [], []
    for identifier in sorted(predictions):
        projection, target = predictions[identifier], targets[identifier]
        # Same normalization as native response parsers; unlike gold XML,
        # predicted underscores are NOT replaced. Empty predictions score 0.
        triples = [tuple(v.strip().lower() for v in row) for row in projection["triples"]]
        if any(len(row) != 3 for row in triples):
            raise ValueError("OSKGC_UNSCORABLE_TRIPLE_ARITY")
        actual = [tuple(row) for row in target["triples"]]
        precision, recall, f1 = evaluator.calculate_metrics(triples, actual)
        ss = evaluator.process_record({"id": identifier, "schemas": projection["schemas"]}, *hierarchy)
        if ss is None:
            raise ValueError("OSKGC_UNSCORABLE_SCHEMA_TARGET")
        ss_records.append({"id": identifier, "SS": ss["SS"]})
        prefix = "_".join(identifier.split("_")[:2])
        files[prefix].append(f1)
        rows.append({"sample_id": identifier, "Precision": precision, "Recall": recall, "F1": f1, "SS": ss["SS"]})
        all_predictions.extend(triples)
        all_targets.extend(actual)
    precision, recall, micro = evaluator.calculate_metrics(all_predictions, all_targets)
    per_file = {key: round(sum(values) / len(values), 3) for key, values in files.items()}
    _group_ss, overall_ss = evaluator.calculate_scores_from_ss(ss_records)
    return {"metrics": {"Precision": precision, "Recall": recall, "micro_F1": micro,
            "macro_F1": round(sum(per_file.values()) / len(per_file), 3), "SS": overall_ss}, "samples": rows,
        "status": "MEASURED", "sample_count": len(rows), "failure_count": 0, "scorer_commit": OSKGC_COMMIT,
        "scorer_sha256": OSKGC_SCORER_SHA256, "aggregation": "PINNED_GLOBAL_TRIPLE_SET_MICRO_AND_FILE_MACRO",
        "limitations": ["Only native numeric results are returned; no reference triples or per-sample gold schemas are exported",
            "Full inference/semantic-artifact integration is separate from this native scorer adapter"]}
