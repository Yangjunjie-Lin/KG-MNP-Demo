from __future__ import annotations

from copy import deepcopy

import pytest

from kg_mnp_demo.activation.contracts import (
    ACTIVATION_EVENT_TYPES,
    ACTIVATION_EXECUTION_STATUSES,
    ACTIVATION_KINDS,
    ACTIVATION_PROPOSAL_STATUSES,
    ACTIVATION_REGISTRY_STATUS,
    ACTIVATION_REVIEW_DECISIONS,
    ACTIVE_POINTER_STATUS,
    APPLICATION_PHASE06_STATUS,
    DRAFT_2020_12,
    SCHEMAS,
    ActivationContractError,
    activation_contract_hash,
    load_activation_schema,
    strict_json_bytes,
    validate_activation_contract,
)
from kg_mnp_demo.activation.errors import ActivationError, ActivationErrorCode

HASH = "a" * 64
OTHER_HASH = "b" * 64
COMMIT = "c" * 40


def _proposal() -> dict:
    return {
        "contract_version": "1.0",
        "activation_proposal_id": "urn:kg-mnp:activation-proposal:" + HASH,
        "activation_kind": "ACTIVATE_NEW_VERIFIED_PUBLICATION",
        "target_publication_id": "urn:kg-mnp:e2e-publication:" + HASH,
        "target_publication_semantic_hash": HASH,
        "target_repository_id": "kg-mnp-" + HASH[:20],
        "target_repository_semantic_hash": OTHER_HASH,
        "target_publication_attestation_sha256": HASH,
        "target_lineage_source_type": "PHASE05_VERIFIED_PUBLICATION",
        "target_lineage_source_attestation_sha256": OTHER_HASH,
        "target_authority_binding_hash": HASH,
        "base_pointer_hash": OTHER_HASH,
        "base_generation": 0,
        "rationale": "Explicit deployment selection request.",
        "created_by_label": "operator-supplied label",
        "explicit_human_intent": True,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": False,
        "production_authority": True,
        "status": "DRAFT",
    }


def _review() -> dict:
    return {
        "contract_version": "1.0",
        "activation_review_decision_id": (
            "urn:kg-mnp:activation-review-decision:" + HASH
        ),
        "activation_proposal_id": "urn:kg-mnp:activation-proposal:" + HASH,
        "decision": "APPROVE_FOR_ACTIVATION",
        "resulting_status": "APPROVED_FOR_ACTIVATION",
        "reviewed_by_label": "operator-supplied reviewer label",
        "review_note": "Explicitly approved for deployment activation.",
        "explicit_human_action": True,
        "operator_identity_claim": "OPERATOR_SUPPLIED_LABEL_ONLY",
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": False,
        "production_authority": True,
    }


def _event() -> dict:
    return {
        "contract_version": "1.0",
        "event_id": "urn:kg-mnp:activation-event:" + HASH,
        "event_hash": HASH,
        "sequence": 1,
        "previous_event_hash": "GENESIS",
        "event_type": "RegistryBootstrapped",
        "payload": {"bootstrap_status": "BOOTSTRAP_CURRENT_REFERENCE"},
        "payload_hash": OTHER_HASH,
        "test_only": False,
        "production_authority": True,
        "observed_at": None,
    }


def _pointer() -> dict:
    return {
        "contract_version": "1.0",
        "pointer_id": "urn:kg-mnp:current-publication-pointer:" + HASH,
        "generation": 0,
        "active_publication_id": "urn:kg-mnp:e2e-publication:" + HASH,
        "active_publication_semantic_hash": HASH,
        "active_repository_id": "kg-mnp-" + HASH[:20],
        "active_repository_semantic_hash": OTHER_HASH,
        "active_publication_attestation_sha256": HASH,
        "lineage_source_type": "BOOTSTRAP_CURRENT_REFERENCE",
        "lineage_source_attestation_sha256": OTHER_HASH,
        "previous_pointer_hash": "GENESIS",
        "pointer_hash": HASH,
        "semantic_authority": False,
        "deployment_selection_metadata": True,
        "status": "ACTIVE_VERIFIED_PUBLICATION",
    }


def _registry() -> dict:
    return {
        "contract_version": "1.0",
        "registry_id": "urn:kg-mnp:activation-registry:" + HASH,
        "authority_binding_hash": HASH,
        "bootstrap_pointer": _pointer(),
        "events": [_event()],
        "registry_revision": 1,
        "head_event_hash": HASH,
        "current_pointer_hash": HASH,
        "registry_hash": OTHER_HASH,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": False,
        "production_authority": True,
        "status": "ACTIVATION_REGISTRY_ACTIVE",
    }


def _receipt() -> dict:
    return {
        "contract_version": "1.0",
        "execution_id": "urn:kg-mnp:activation-execution:" + HASH,
        "proposal_id": "urn:kg-mnp:activation-proposal:" + HASH,
        "review_decision_id": "urn:kg-mnp:activation-review-decision:" + HASH,
        "old_pointer_hash": HASH,
        "new_pointer_hash": OTHER_HASH,
        "old_generation": 0,
        "new_generation": 1,
        "target_publication_id": "urn:kg-mnp:e2e-publication:" + HASH,
        "target_publication_semantic_hash": HASH,
        "target_repository_id": "kg-mnp-" + HASH[:20],
        "target_repository_semantic_hash": OTHER_HASH,
        "target_publication_attestation_sha256": HASH,
        "verification_evidence_hashes": {
            "publication_tree_sha256": HASH,
            "publication_attestation_sha256": OTHER_HASH,
            "expected_repository_semantic_hash": HASH,
            "live_repository_semantic_hash": HASH,
        },
        "event_id": "urn:kg-mnp:activation-event:" + OTHER_HASH,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "test_only": False,
        "production_authority": True,
        "status": "ACTIVATION_APPLIED",
    }


ATTESTATION_IDENTITIES = {
    "stage08_identity",
    "phase01_identity",
    "phase02_identity",
    "phase03_identity",
    "phase04_identity",
    "phase05_identity",
    "production_base_publication_id",
    "production_base_repository_id",
}
ATTESTATION_HASHES = {
    "production_base_publication_hash",
    "production_base_repository_hash",
    "production_pointer_initial_hash",
    "production_pointer_final_hash",
    "controlled_fixture_hash",
    "controlled_p0_publication_hash",
    "controlled_p1_publication_hash",
    "controlled_p0_repository_hash",
    "controlled_p1_repository_hash",
    "p0_repository_before_hash",
    "p0_repository_after_activation_hash",
    "p0_repository_after_rollback_hash",
    "p1_repository_before_hash",
    "p1_repository_after_activation_hash",
    "p1_repository_after_rollback_hash",
    "p0_publication_tree_before_hash",
    "p0_publication_tree_after_hash",
    "p1_publication_tree_before_hash",
    "p1_publication_tree_after_hash",
}


def _attestation() -> dict:
    schema = load_activation_schema("application-phase06-attestation")
    value: dict[str, object] = {
        "contract_version": "1.0",
        "commit_sha": COMMIT,
        "production_pointer_unchanged": True,
        "semantic_authority": False,
        "deployment_governance_only": True,
        "status": "APPLICATION_PUBLICATION_ACTIVATION_VERIFIED",
    }
    value.update({field: f"identity:{field}" for field in ATTESTATION_IDENTITIES})
    value.update({field: HASH for field in ATTESTATION_HASHES})
    for field in set(schema["properties"]) - set(value):
        value[field] = 0
    value.update(
        {
            "controlled_activation_cycles": 1,
            "controlled_rollback_cycles": 1,
            "controlled_initial_generation": 0,
            "controlled_post_activation_generation": 1,
            "controlled_final_generation": 2,
            "determinism_runs": 2,
            "determinism_passed": 2,
        }
    )
    assert set(value) == set(schema["properties"])
    return value


SAMPLES = {
    "activation-proposal": _proposal,
    "activation-review-decision": _review,
    "activation-event": _event,
    "current-publication-pointer": _pointer,
    "activation-registry": _registry,
    "activation-execution-receipt": _receipt,
    "application-phase06-attestation": _attestation,
}


def test_seven_contracts_are_exact_closed_draft_2020_12_https() -> None:
    assert set(SCHEMAS) == set(SAMPLES)
    assert len(SCHEMAS) == 7
    for name in SCHEMAS:
        schema = load_activation_schema(name)
        assert schema["$schema"] == DRAFT_2020_12
        assert schema["$id"].startswith(
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/schemas/activation/"
        )
        assert schema["additionalProperties"] is False
        assert set(schema["required"]) == set(schema["properties"])
        validate_activation_contract(name, SAMPLES[name]())
    assert len(activation_contract_hash()) == 64


def test_closed_enums_statuses_and_control_plane_flags() -> None:
    proposal = load_activation_schema("activation-proposal")["properties"]
    assert tuple(proposal["activation_kind"]["enum"]) == ACTIVATION_KINDS
    assert tuple(proposal["status"]["enum"]) == ACTIVATION_PROPOSAL_STATUSES
    assert proposal["explicit_human_intent"] == {"const": True}
    assert proposal["semantic_authority"] == {"const": False}
    assert proposal["deployment_governance_only"] == {"const": True}

    review = load_activation_schema("activation-review-decision")["properties"]
    assert tuple(review["decision"]["enum"]) == ACTIVATION_REVIEW_DECISIONS
    assert review["explicit_human_action"] == {"const": True}
    assert review["operator_identity_claim"] == {
        "const": "OPERATOR_SUPPLIED_LABEL_ONLY"
    }

    event = load_activation_schema("activation-event")["properties"]
    assert tuple(event["event_type"]["enum"]) == ACTIVATION_EVENT_TYPES
    assert "event_hash" in event
    assert event["observed_at"]["type"] == ["string", "null"]

    pointer = load_activation_schema("current-publication-pointer")["properties"]
    assert pointer["status"] == {"const": ACTIVE_POINTER_STATUS}
    assert pointer["semantic_authority"] == {"const": False}
    assert pointer["deployment_selection_metadata"] == {"const": True}

    registry = load_activation_schema("activation-registry")["properties"]
    assert registry["status"] == {"const": ACTIVATION_REGISTRY_STATUS}
    assert registry["semantic_authority"] == {"const": False}
    assert registry["deployment_governance_only"] == {"const": True}

    receipt = load_activation_schema("activation-execution-receipt")["properties"]
    assert tuple(receipt["status"]["enum"]) == ACTIVATION_EXECUTION_STATUSES
    evidence = receipt["verification_evidence_hashes"]
    assert evidence["additionalProperties"] is False
    assert set(evidence["required"]) == set(evidence["properties"])

    attestation = load_activation_schema("application-phase06-attestation")[
        "properties"
    ]
    assert attestation["status"] == {"const": APPLICATION_PHASE06_STATUS}
    assert attestation["semantic_authority"] == {"const": False}
    assert attestation["deployment_governance_only"] == {"const": True}


@pytest.mark.parametrize("name", sorted(SAMPLES))
def test_every_contract_rejects_unexpected_fields(name: str) -> None:
    value = deepcopy(SAMPLES[name]())
    value["confirmed_fact"] = True
    with pytest.raises(ActivationContractError, match="confirmed_fact"):
        validate_activation_contract(name, value)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a": 1, "A": 2}',
        b'{"outer": {"key": 1, "KEY": 2}}',
        b'{"a": NaN}',
        b'{"a": Infinity}',
        b'{"a": -Infinity}',
    ],
)
def test_strict_json_rejects_casefolded_duplicates_and_non_finite_numbers(
    raw: bytes,
) -> None:
    with pytest.raises(ActivationContractError):
        strict_json_bytes(raw)


def test_forbidden_statuses_flags_and_plain_hash_event_ids_fail_closed() -> None:
    proposal = _proposal()
    proposal["activation_kind"] = "PATCH_ACTIVE_PUBLICATION"
    with pytest.raises(ActivationContractError):
        validate_activation_contract("activation-proposal", proposal)

    review = _review()
    review["explicit_human_action"] = False
    with pytest.raises(ActivationContractError):
        validate_activation_contract("activation-review-decision", review)

    event = _event()
    event["event_id"] = HASH
    with pytest.raises(ActivationContractError):
        validate_activation_contract("activation-event", event)

    pointer = _pointer()
    pointer["status"] = "UNVERIFIED"
    with pytest.raises(ActivationContractError):
        validate_activation_contract("current-publication-pointer", pointer)

    receipt = _receipt()
    receipt["status"] = "SEMANTIC_CHANGE_APPLIED"
    with pytest.raises(ActivationContractError):
        validate_activation_contract("activation-execution-receipt", receipt)


def test_activation_errors_have_stable_fail_closed_codes() -> None:
    error = ActivationError(
        ActivationErrorCode.TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET
    )
    assert error.to_dict() == {
        "code": "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET",
        "detail": "TEST_FIXTURE_NOT_ALLOWED_AS_PRODUCTION_ACTIVATION_TARGET",
        "status": "FAILED",
    }
    assert (
        ActivationError("AUTHORITY_MISMATCH").code
        is ActivationErrorCode.AUTHORITY_MISMATCH
    )
