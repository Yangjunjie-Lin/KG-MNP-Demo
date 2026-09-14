"""Version-specific CQ4OE input adapter; no reference ontology/axiom access."""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import re
from pathlib import Path

from zhigou_toolchain.contracts.canonical import semantic_hash

from .contracts import ModelingInput

CQ4OE_COMMIT = "248e0c6cfa498c4630b17a83290628d9f8adc4b6"
TERM_SCORER_SHA256 = "1f675c2320a7d8c302d9d9d3bacf4231c488d41b82d47756960d79ffbc03f7a4"
HARD_FUNCTIONS = {"split_camel_case", "normalize_key", "normalize_text", "build_records", "make_gold_entry", "make_pred_entry",
    "match_one_to_one_greedy", "compute_lexical_sim_from_normalized", "get_threshold", "pre_process", "cal_metrics"}


def adapt_cq4oe(rows, *, sample_id, task):
    if task not in {"cq2term", "cq2onto"}:
        raise ValueError("UNKNOWN_CQ4OE_TASK")
    if not rows or any(not isinstance(r.get("id"), str) or not isinstance(r.get("value"), str) or not r["value"].strip() for r in rows):
        raise ValueError("CQ4OE_INVALID_INPUT")
    repeated_ids = len({row["id"] for row in rows}) != len(rows)
    # Keep public CQ IDs, never annotation/gold fields. The ontology is the
    # independent statistical unit, not each question or generated axiom.
    allowed = [{"id": row["id"], "value": row["value"]} for row in rows]
    return ModelingInput(sample_id=sample_id, benchmark_id="cq4oe_0_0_1", task_id=task,
        dataset_version=CQ4OE_COMMIT, split="PUBLIC_CQ_INPUTS", evaluation_scope="ADAPTED_ANALYSIS",
        group_id=semantic_hash({"benchmark": "cq4oe", "ontology": sample_id.split("_")[0]}), mode="CQS_TBOX",
        competency_questions=[r["id"] + ": " + r["value"] for r in allowed],
        cq_occurrences=[{"id": f"{sample_id}--{index:04d}", "original_id": r["id"], "value": r["value"]}
            for index, r in enumerate(allowed)],
        requirements=["Generate class/property terms from the CQs." if task == "cq2term" else "Generate an OWL TBox from the CQs.",
            "No instances supplied: ABox generation is NOT_APPLICABLE. Do not invent example individuals.",
            "CQCoverage concerns required TBox axioms, not SPARQL answer correctness.",
            *(["UPSTREAM_REPEATED_CQ_IDS: preserve all original occurrences; IDs alone cannot disambiguate questions."] if repeated_ids else [])])


def native_term_hard(directory, predicted, expected):
    """Native per-method term metric ONLY, not the full top-3 alignment pipeline.

    Original reviewed functions are unmodified; model/NLTK/import branches are
    not loaded or callable through this hard_match-only wrapper.
    """
    import json
    directory = Path(directory)
    lock = json.loads((directory / "asset-lock.json").read_bytes())
    path = "CQ2Term/scripts/concept_label_matching.py"
    raw = (directory / path).read_bytes()
    if lock["commit"] != CQ4OE_COMMIT or hashlib.sha256(raw).hexdigest() != TERM_SCORER_SHA256:
        raise ValueError("CQ4OE_SCORER_CHANGED")
    if next(r["sha256"] for r in lock["files"] if r["path"] == path) != TERM_SCORER_SHA256:
        raise ValueError("CQ4OE_SCORER_LOCK_CHANGED")
    selected = [n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef) and n.name in HARD_FUNCTIONS]
    if {n.name for n in selected} != HARD_FUNCTIONS:
        raise ValueError("CQ4OE_NATIVE_INTERFACE_CHANGED")
    namespace = {"re": re, "HARD_THRESHOLD": 1.0, "SEMANTIC_THRESHOLD": .6, "LEXICAL_THRESHOLD": .8}
    exec(compile(ast.Module(body=list(selected), type_ignores=[]), "locked_cq4oe_hard", "exec"), namespace)  # noqa: S102
    with contextlib.redirect_stdout(io.StringIO()):
        coverage, precision, recall, f1, _, _ = namespace["cal_metrics"](predicted, expected, "hard_match")
    return {"coverage": coverage, "precision": precision, "recall": recall, "f1": f1}
