from __future__ import annotations

import pytest

from kg_mnp_demo.amendment.candidate_binding import bind_amendment_to_proposal
from kg_mnp_demo.amendment.errors import AmendmentError, AmendmentErrorCode
from kg_mnp_demo.amendment.republication import (
    assert_abox_only_invariants,
    new_repository_identity,
)


def test_candidate_binding_rejects_input_hash_mismatch() -> None:
    request = {
        "amendment_type": "PROPOSE_VALUE_CANDIDATE",
        "structured_proposed_payload": {
            "rdf_term": None,
            "evidence_refs": [],
            "source_refs": [],
            "candidate_refs": [],
            "constraint_refs": [],
            "review_reopen_reason": None,
        },
    }
    with pytest.raises(AmendmentError) as error:
        bind_amendment_to_proposal(
            amendment_request=request,
            proposal={"input_snapshot": {"input_semantic_hash": "a" * 64}},
            revised_cleaned_data_hash="b" * 64,
            declared_changed_json_pointers=["/data/x"],
        )
    assert error.value.code == AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH


def test_candidate_binding_requires_exact_literal_language_and_datatype() -> None:
    request = {
        "amendment_type": "PROPOSE_VALUE_CANDIDATE",
        "structured_proposed_payload": {
            "rdf_term": {
                "term_type": "LITERAL",
                "iri": None,
                "lexical_form": "ACTIVE",
                "datatype_iri": None,
                "language": "en",
            },
            "evidence_refs": [],
            "source_refs": [],
            "candidate_refs": [],
            "constraint_refs": [],
            "review_reopen_reason": None,
        },
    }
    proposal = {
        "input_snapshot": {"input_semantic_hash": "a" * 64},
        "candidate_entities": [],
        "candidate_assertions": [
            {
                "candidate_id": "urn:candidate:status",
                "candidate_kind": "DATA_PROPERTY_ASSERTION",
                "subject_ref": "urn:candidate:subject",
                "predicate_iri": "urn:predicate:status",
                "object": {
                    "value": "ACTIVE",
                    "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
                },
                "source_paths": ["/subscription/status"],
                "business_fact_evidence_refs": [],
                "publication_scope": "ABOX",
            }
        ],
        "schema_delta_candidates": [],
    }
    with pytest.raises(AmendmentError) as error:
        bind_amendment_to_proposal(
            amendment_request=request,
            proposal=proposal,
            revised_cleaned_data_hash="a" * 64,
            declared_changed_json_pointers=["/data/subscription/status"],
        )
    assert error.value.code == AmendmentErrorCode.REENTRY_SEMANTIC_MISMATCH


def test_abox_only_invariants_are_explicit() -> None:
    assert_abox_only_invariants(
        old_tbox_hash="a" * 64,
        new_tbox_hash="a" * 64,
        old_shacl_hash="b" * 64,
        new_shacl_hash="b" * 64,
        old_abox_hash="c" * 64,
        new_abox_hash="d" * 64,
        old_publication_hash="e" * 64,
        new_publication_hash="f" * 64,
        old_webvowl_hash="g" * 64,
        new_webvowl_hash="g" * 64,
    )
    with pytest.raises(AmendmentError):
        assert_abox_only_invariants(
            old_tbox_hash="a" * 64,
            new_tbox_hash="z" * 64,
            old_shacl_hash="b" * 64,
            new_shacl_hash="b" * 64,
            old_abox_hash="c" * 64,
            new_abox_hash="d" * 64,
            old_publication_hash="e" * 64,
            new_publication_hash="f" * 64,
            old_webvowl_hash="g" * 64,
            new_webvowl_hash="g" * 64,
        )


def test_new_repository_identity_is_publication_derived() -> None:
    value = "a" * 64
    assert new_repository_identity(value).endswith(value)
