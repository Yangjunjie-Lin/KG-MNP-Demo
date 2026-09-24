"""Closed vocabulary is task-authorized baseline plus actual S2 proposals."""
from __future__ import annotations

from copy import deepcopy

from zhigou_toolchain.contracts.canonical import semantic_hash


def close_vocabulary(proposal, supplied_cards):
    """Do not infer labels from S3 predictions or any scoring/reference data."""
    result = deepcopy(proposal)
    added = {"classes": [], "entities": [], "relations": []}
    fields = {"CLASS": "classes", "ENTITY": "entities", "OBJECT_PROPERTY": "relations"}
    for card in supplied_cards:
        if card["element_kind"] not in fields:
            raise ValueError("UNSUPPORTED_TASK_VOCABULARY_KIND")
        field, label = fields[card["element_kind"]], card["label"]
        if label not in result[field]:
            result[field].append(label)
            added[field].append(label)
    return result, {"basis": "TASK_SUPPLIED_LABELS_PLUS_ACTUAL_S2_PROPOSAL", "added_from_input": added,
        "proposal_sha256": semantic_hash(proposal), "effective_sha256": semantic_hash(result),
        "facts_or_scoring_answers_used": False, "approval": "NOT_GRANTED"}
