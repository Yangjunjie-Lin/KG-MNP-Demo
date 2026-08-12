from __future__ import annotations

import pytest

from kg_mnp_demo.governance.contracts import SCHEMAS, load_governance_schema
from kg_mnp_demo.governance.errors import GovernanceError, GovernanceErrorCode
from kg_mnp_demo.governance.proposal import create_resolution_proposal, empty_payload
from kg_mnp_demo.governance.workspace import GovernanceWorkspace

from ._helpers import authority, proposal_arguments, value_payload


def test_six_contracts_are_closed_draft_2020_12_https() -> None:
    assert len(SCHEMAS) == 6
    for name in SCHEMAS:
        schema = load_governance_schema(name)
        assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert schema["$id"].startswith("https://yangjunjie-lin.github.io/")
        assert schema["additionalProperties"] is False


@pytest.mark.parametrize(
    "proposal_type",
    [
        "RAW_RDF_PATCH",
        "RAW_SPARQL",
        "GRAPHDB_UPDATE",
        "ARBITRARY_PATCH",
        "JSON_PATCH",
        "SHELL_COMMAND",
        "PYTHON_CODE",
        "FILE_PATH",
    ],
)
def test_proposal_type_is_a_closed_allowlist(proposal_type: str) -> None:
    auth = authority()
    arguments = proposal_arguments(auth)
    arguments["proposal_type"] = proposal_type
    with pytest.raises(GovernanceError) as caught:
        create_resolution_proposal(
            authority=auth,
            workspace_id="urn:kg-mnp:governance-workspace:" + "0" * 64,
            sequence=1,
            previous_event_hash="GENESIS",
            **arguments,
        )
    assert caught.value.code == GovernanceErrorCode.INVALID_PROPOSAL_TYPE


def test_rdf_term_fidelity_and_patch_content_policy() -> None:
    auth = authority()
    bad = proposal_arguments(auth)
    bad["proposed_payload"] = value_payload("INSERT DATA { <x> <y> <z> }")
    with pytest.raises(GovernanceError, match="mutation content"):
        GovernanceWorkspace.initialize(auth).create_proposal(
            expected_workspace_revision=0, **bad
        )
    missing_term = proposal_arguments(auth)
    missing_term["proposed_payload"] = empty_payload()
    with pytest.raises(GovernanceError, match="does not match type"):
        GovernanceWorkspace.initialize(auth).create_proposal(
            expected_workspace_revision=0, **missing_term
        )


def test_only_a_current_verified_issue_can_be_targeted() -> None:
    auth = authority()
    arguments = proposal_arguments(auth)
    arguments["target_diagnostic_id"] = "urn:kg-mnp:diagnostic:" + "1" * 64
    with pytest.raises(GovernanceError) as caught:
        GovernanceWorkspace.initialize(auth).create_proposal(
            expected_workspace_revision=0, **arguments
        )
    assert caught.value.code == GovernanceErrorCode.UNKNOWN_DIAGNOSTIC
    arguments = proposal_arguments(auth)
    arguments["target_diagnostic_basis_hash"] = "2" * 64
    with pytest.raises(GovernanceError) as caught:
        GovernanceWorkspace.initialize(auth).create_proposal(
            expected_workspace_revision=0, **arguments
        )
    assert caught.value.code == GovernanceErrorCode.STALE_DIAGNOSTIC_BINDING


def test_operator_label_is_not_an_authenticated_identity() -> None:
    schema = load_governance_schema("resolution-proposal")
    assert "created_by_label" in schema["properties"]
    forbidden = {"authenticated_user", "verified_reviewer", "legal_identity"}
    assert not forbidden & set(schema["properties"])
