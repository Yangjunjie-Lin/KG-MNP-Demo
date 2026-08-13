from __future__ import annotations

from copy import deepcopy

from kg_mnp_demo.governance.authority_binding import GovernanceAuthority
from kg_mnp_demo.governance.proposal import empty_payload
from scripts.governance_controlled_fixture import (
    ControlledDiagnosticFixture,
    controlled_governance_authority_for_test_harness,
    controlled_governance_workspace_for_test_harness,
)


def authority() -> GovernanceAuthority:
    """Return authority only through the explicitly TEST-ONLY fixture adapter."""

    return controlled_governance_authority_for_test_harness(
        ControlledDiagnosticFixture.create()
    )


def workspace(authority_value: GovernanceAuthority | None = None, current_authority=None):
    value = authority_value or authority()
    return controlled_governance_workspace_for_test_harness(value, current_authority)


def issue(authority_value: GovernanceAuthority | None = None):
    value = authority_value or authority()
    return next(iter(value.issues.values()))


def value_payload(lexical: str = "candidate"):
    value = empty_payload()
    value["rdf_term"] = {
        "term_type": "LITERAL",
        "iri": None,
        "lexical_form": lexical,
        "datatype_iri": "http://www.w3.org/2001/XMLSchema#string",
        "language": None,
    }
    return value


def proposal_arguments(authority_value: GovernanceAuthority | None = None):
    row = issue(authority_value)
    return {
        "target_diagnostic_id": row["diagnostic_id"],
        "target_diagnostic_basis_hash": row["diagnostic_basis_hash"],
        "proposal_type": "PROPOSE_VALUE_CANDIDATE",
        "proposed_payload": value_payload(),
        "rationale": "Operator-entered rationale; proposed value is not a fact.",
        "created_by_label": "operator-supplied label",
        "proposal_revision": 1,
    }


def stale(authority_value: GovernanceAuthority) -> GovernanceAuthority:
    return GovernanceAuthority(
        authority_type="CONTROLLED_TEST_HARNESS",
        publication_id=authority_value.publication_id,
        publication_semantic_hash=authority_value.publication_semantic_hash,
        repository_semantic_hash=authority_value.repository_semantic_hash,
        upstream_phase03_attestation_sha256=(
            authority_value.upstream_phase03_attestation_sha256
        ),
        upstream_phase03_diagnostic_package_hash="e" * 64,
        issues=deepcopy(dict(authority_value.issues)),
    )
