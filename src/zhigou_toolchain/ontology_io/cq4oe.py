"""Version-specific CQ4OE input adapter; no reference ontology/axiom access."""
from __future__ import annotations

from zhigou_toolchain.contracts.canonical import semantic_hash

from .contracts import ModelingInput

CQ4OE_COMMIT = "248e0c6cfa498c4630b17a83290628d9f8adc4b6"


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
        group_id=semantic_hash(sorted(allowed, key=lambda r: (r["id"], r["value"]))), mode="CQS_TBOX",
        competency_questions=[r["id"] + ": " + r["value"] for r in allowed],
        requirements=["Generate class/property terms from the CQs." if task == "cq2term" else "Generate an OWL TBox from the CQs.",
            "No instances supplied: ABox generation is NOT_APPLICABLE. Do not invent example individuals.",
            "CQCoverage concerns required TBox axioms, not SPARQL answer correctness.",
            *(["UPSTREAM_REPEATED_CQ_IDS: preserve all original occurrences; IDs alone cannot disambiguate questions."] if repeated_ids else [])])
