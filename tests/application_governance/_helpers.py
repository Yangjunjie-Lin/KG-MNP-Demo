from __future__ import annotations

from copy import deepcopy

from kg_mnp_demo.governance.authority_binding import GovernanceAuthority
from kg_mnp_demo.governance.proposal import empty_payload


def authority() -> GovernanceAuthority:
    publication_hash = "a" * 64
    basis_hash = "f" * 64
    diagnostic_id = f"urn:kg-mnp:diagnostic:{basis_hash}"
    issue = {
        "diagnostic_id": diagnostic_id,
        "diagnostic_basis_hash": basis_hash,
        "classification": "REQUIRED_VALUE_MISSING",
        "scope": "CURRENT_DIAGNOSTIC",
        "explanation": "untrusted <img src=x onerror=window.__xss=1>",
    }
    return GovernanceAuthority(
        publication_id=f"urn:kg-mnp:e2e-publication:{publication_hash}",
        publication_semantic_hash=publication_hash,
        repository_semantic_hash="b" * 64,
        phase03_attestation_hash="c" * 64,
        diagnostic_package_hash="d" * 64,
        issues={diagnostic_id: issue},
    )


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
        **{
            **authority_value.binding,
            "diagnostic_package_hash": "e" * 64,
            "issues": deepcopy(authority_value.issues),
        }
    )
