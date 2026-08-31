from __future__ import annotations

import copy

import pytest

from kg_mnp.contracts.canonical import semantic_hash, stable_urn
from kg_mnp.contracts.registry import load_contract_registry
from kg_mnp.modeling.control_plane.artifacts import finalize_document
from kg_mnp.modeling.control_plane.candidates import (
    normalize_candidate_drafts,
    recalculate_candidate_identity,
)
from kg_mnp.modeling.control_plane.errors import ModelingProposalError
from kg_mnp.modeling.control_plane.limits import ModelingLimits
from kg_mnp.modeling.control_plane.providers.models import (
    candidate_body,
    candidate_draft,
)


def test_candidate_partitions_identity_evidence_and_dependencies(prompt04_case: dict) -> None:
    proposal = prompt04_case["proposal"]
    assert proposal["tbox_candidates"]
    assert proposal["mapping_candidates"]
    assert proposal["abox_candidates"]
    for candidate in [
        *proposal["tbox_candidates"],
        *proposal["mapping_candidates"],
        *proposal["abox_candidates"],
    ]:
        signature, candidate_id = recalculate_candidate_identity(candidate)
        assert (signature, candidate_id) == (
            candidate["semantic_signature"],
            candidate["candidate_id"],
        )
        assert candidate["review_required"] is True
        assert candidate["evidence_refs"] or candidate["domain_asset_refs"]


def test_multi_provider_duplicate_merges_provenance(prompt04_case: dict) -> None:
    evidence_id = prompt04_case["input_bundle"]["evidence_record_ids"][0]
    item_id = prompt04_case["dataset"]["items"][0]["item_id"]
    draft = candidate_draft(
        draft_ref="one",
        draft_kind="SHACL",
        candidate_action="CONSTRAIN",
        body=candidate_body(
            candidate_type="MIN_COUNT",
            target_iri="urn:kg-mnp:project:prompt04-test-project:shape",
            integer_value=1,
        ),
        rationale="bounded structured SHACL candidate",
        kg_ir_item_refs=[item_id],
        evidence_refs=[evidence_id],
    )
    # Response identity is contract-checked, so reuse a real response envelope and
    # replace only its draft through the public builder in provider tests.
    real = copy.deepcopy(prompt04_case["responses"][0])
    real["candidate_drafts"] = [draft]
    core = {key: value for key, value in real.items() if key not in {"response_id", "response_digest"}}
    real["response_digest"] = semantic_hash(core)
    real["response_id"] = stable_urn(
        "modeling-provider-response", {"response_digest": real["response_digest"]}
    )
    result = normalize_candidate_drafts(
        [real, real],
        scope=prompt04_case["scope"],
        evidence_ids=set(prompt04_case["input_bundle"]["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in prompt04_case["dataset"]["items"]},
        baseline_element_ids={item["element_id"] for item in prompt04_case["baseline"]["elements"]},
    )
    assert len(result["candidates"]) == 1
    assert result["candidates"][0]["candidate_kind"] == "SHACL"


def test_candidate_count_limit_fails_closed(prompt04_case: dict) -> None:
    with pytest.raises(ModelingProposalError, match="candidate count limit"):
        normalize_candidate_drafts(
            prompt04_case["responses"],
            scope=prompt04_case["scope"],
            evidence_ids=set(prompt04_case["input_bundle"]["evidence_record_ids"]),
            kg_ir_item_ids={
                item["item_id"] for item in prompt04_case["dataset"]["items"]
            },
            baseline_element_ids={
                item["element_id"] for item in prompt04_case["baseline"]["elements"]
            },
            limits=ModelingLimits(max_total_candidates=1),
        )


def test_closed_candidate_contract_supports_all_required_types() -> None:
    schema = load_contract_registry().get_schema("ontology-candidate-set")
    candidate_types = set(
        schema["properties"]["candidates"]["items"]["properties"]["body"]["properties"][
            "candidate_type"
        ]["enum"]
    )
    assert candidate_types == {
        "CLASS",
        "OBJECT_PROPERTY",
        "DATA_PROPERTY",
        "SUBCLASS_AXIOM",
        "DOMAIN_AXIOM",
        "RANGE_AXIOM",
        "DISJOINT_CLASSES_AXIOM",
        "RECORD_TO_CLASS",
        "FIELD_TO_DATA_PROPERTY",
        "REFERENCE_TO_OBJECT_PROPERTY",
        "VALUE_MAPPING",
        "IRI_TEMPLATE",
        "NULL_HANDLING_POLICY",
        "INDIVIDUAL",
        "CLASS_ASSERTION",
        "DATA_PROPERTY_ASSERTION",
        "OBJECT_PROPERTY_ASSERTION",
        "NODE_SHAPE",
        "PROPERTY_SHAPE",
        "MIN_COUNT",
        "MAX_COUNT",
        "DATATYPE",
        "CLASS_CONSTRAINT",
        "NODE_KIND",
        "IN_VALUES",
    }


def test_out_of_scope_type_mismatch_and_homoglyph_require_review(
    prompt04_case: dict,
) -> None:
    evidence_id = prompt04_case["input_bundle"]["evidence_record_ids"][0]
    item_id = prompt04_case["dataset"]["items"][0]["item_id"]
    drafts = [
        candidate_draft(
            draft_ref="out-of-scope",
            draft_kind="SHACL",
            candidate_action="CONSTRAIN",
            body=candidate_body(
                candidate_type="MIN_COUNT",
                target_iri="urn:kg-mnp:project:prompt04-test-project:shape",
                integer_value=1,
            ),
            rationale="out-of-scope audit candidate",
            kg_ir_item_refs=[item_id],
            evidence_refs=[evidence_id],
        ),
        candidate_draft(
            draft_ref="wrong-partition",
            draft_kind="ABOX",
            candidate_action="ASSERT",
            body=candidate_body(
                candidate_type="CLASS",
                target_iri="urn:kg-mnp:project:prompt04-test-project:wrong",
            ),
            rationale="wrong closed partition",
            kg_ir_item_refs=[item_id],
            evidence_refs=[evidence_id],
        ),
        candidate_draft(
            draft_ref="homoglyph",
            draft_kind="TBOX",
            candidate_action="CREATE_NEW",
            body=candidate_body(
                candidate_type="CLASS",
                target_iri="urn:kg-mnp:project:prompt04-test-project:homoglyph",
                label="Entitу",
            ),
            rationale="mixed-script label requires review",
            kg_ir_item_refs=[item_id],
            evidence_refs=[evidence_id],
        ),
    ]
    response = copy.deepcopy(prompt04_case["responses"][0])
    response["candidate_drafts"] = drafts
    core = {
        key: value
        for key, value in response.items()
        if key not in {"response_id", "response_digest"}
    }
    response["response_digest"] = semantic_hash(core)
    response["response_id"] = stable_urn(
        "modeling-provider-response",
        {"response_digest": response["response_digest"]},
    )
    scoped = copy.deepcopy(prompt04_case["scope"])
    scoped["target_artifacts"].remove("SHACL")
    scoped = finalize_document(
        scoped,
        id_field="scope_id",
        urn_kind="ontology-scope",
    )
    result = normalize_candidate_drafts(
        [response],
        scope=scoped,
        evidence_ids=set(prompt04_case["input_bundle"]["evidence_record_ids"]),
        kg_ir_item_ids={item["item_id"] for item in prompt04_case["dataset"]["items"]},
        baseline_element_ids={
            item["element_id"] for item in prompt04_case["baseline"]["elements"]
        },
    )
    issues = {
        item["code"]
        for candidate in result["candidates"]
        for item in candidate["issues"]
    }
    assert {
        "OUT_OF_SCOPE_CANDIDATE",
        "ELEMENT_TYPE_CONFLICT",
        "UNICODE_HOMOGLYPH_RISK",
    } <= issues
