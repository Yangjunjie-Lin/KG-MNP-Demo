"""Small deterministic fixtures shared by Prompt 5 unit tests."""

from __future__ import annotations

from typing import Any

from kg_mnp.contracts.canonical import stable_urn


def candidate(
    candidate_type: str,
    *,
    candidate_kind: str,
    candidate_action: str,
    ordinal: int = 0,
    **body_overrides: Any,
) -> dict[str, Any]:
    """Return the smallest compiler-facing form of a confirmed candidate."""

    body = {
        "candidate_type": candidate_type,
        "subject_iri": None,
        "predicate_iri": None,
        "object_iri": None,
        "label": None,
        "source_field": None,
        "target_iri": None,
        "literal": None,
        "values": [],
        "integer_value": None,
        "conversion_policy": "NONE",
        "null_policy": "NONE",
    }
    body.update(body_overrides)
    identifier = stable_urn(
        "ontology-candidate",
        {"candidate_type": candidate_type, "ordinal": ordinal, "body": body},
    )
    return {
        "candidate_id": identifier,
        "candidate_kind": candidate_kind,
        "candidate_action": candidate_action,
        "body": body,
        "kg_ir_item_refs": [stable_urn("kgir-item", {"ordinal": ordinal})],
        "evidence_refs": [stable_urn("evidence-record", {"ordinal": ordinal})],
        "provider_snapshot_refs": [],
        "model_invocation_refs": [],
        "competency_question_refs": [stable_urn("competency-question", {"ordinal": ordinal})],
        "domain_asset_refs": [],
        "baseline_element_refs": [],
        "dependency_candidate_refs": [],
    }
