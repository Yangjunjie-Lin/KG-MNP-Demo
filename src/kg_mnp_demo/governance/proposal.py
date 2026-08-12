"""ResolutionProposal construction and semantic policy."""

from __future__ import annotations

import re
from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from kg_mnp_demo.modeling.canonical_json import stable_urn

from .authority_binding import GovernanceAuthority
from .contracts import validate_governance_contract
from .errors import GovernanceError, GovernanceErrorCode

PROPOSAL_TYPES = frozenset(
    {
        "PROPOSE_VALUE_CANDIDATE",
        "PROPOSE_EVIDENCE_ATTACHMENT",
        "PROPOSE_SOURCE_ATTACHMENT",
        "REQUEST_REVIEW_REOPEN",
        "PROPOSE_CONSTRAINT_REVIEW",
        "NO_CHANGE_RECOMMENDED",
    }
)
FORBIDDEN_MARKERS = re.compile(
    r"(?is)\b(?:INSERT\s+DATA|DELETE\s+DATA|SPARQL\s+UPDATE|GRAPHDB\s+UPDATE|JSON\s+PATCH|RAW\s+RDF\s+PATCH|SHELL\s+COMMAND)\b|(?:https?://[^\s]+/(?:repositories|rest)/)|(?:https?://(?:127\.0\.0\.1|localhost):7200\b)",
)
PAYLOAD_FIELDS = {
    "rdf_term",
    "evidence_refs",
    "source_refs",
    "candidate_refs",
    "constraint_refs",
    "review_reopen_reason",
}


def empty_payload() -> dict[str, Any]:
    return {
        "rdf_term": None,
        "evidence_refs": [],
        "source_refs": [],
        "candidate_refs": [],
        "constraint_refs": [],
        "review_reopen_reason": None,
    }


def _text_values(value: Any):
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _text_values(child)
    elif isinstance(value, str):
        yield value


def _validate_rdf_term(value: Mapping[str, Any]) -> None:
    if set(value) != {"term_type", "iri", "lexical_form", "datatype_iri", "language"}:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "RDF term field set mismatch"
        )
    kind = value.get("term_type")
    if kind == "IRI":
        iri = value.get("iri")
        if (
            not isinstance(iri, str)
            or not iri.startswith(("http://", "https://", "urn:"))
            or any(
                value.get(field) is not None
                for field in ("lexical_form", "datatype_iri", "language")
            )
        ):
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "invalid IRI term"
            )
    elif kind == "LITERAL":
        if (
            not isinstance(value.get("lexical_form"), str)
            or value.get("iri") is not None
        ):
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST, "invalid literal term"
            )
        if value.get("datatype_iri") is not None and value.get("language") is not None:
            raise GovernanceError(
                GovernanceErrorCode.INVALID_REQUEST,
                "literal cannot have datatype and language",
            )
    else:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "unknown RDF term type"
        )


def normalize_payload(proposal_type: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload) != PAYLOAD_FIELDS:
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "proposed payload field set mismatch"
        )
    result = deepcopy(dict(payload))
    for field in ("evidence_refs", "source_refs", "candidate_refs", "constraint_refs"):
        values = result[field]
        if not isinstance(values, list) or any(
            not isinstance(item, str) for item in values
        ):
            raise GovernanceError(GovernanceErrorCode.INVALID_REQUEST)
        result[field] = sorted(set(values))
    if result["rdf_term"] is not None:
        if not isinstance(result["rdf_term"], Mapping):
            raise GovernanceError(GovernanceErrorCode.INVALID_REQUEST)
        _validate_rdf_term(result["rdf_term"])
    required = {
        "PROPOSE_VALUE_CANDIDATE": result["rdf_term"] is not None,
        "PROPOSE_EVIDENCE_ATTACHMENT": bool(result["evidence_refs"]),
        "PROPOSE_SOURCE_ATTACHMENT": bool(result["source_refs"]),
        "REQUEST_REVIEW_REOPEN": bool(result["review_reopen_reason"]),
        "PROPOSE_CONSTRAINT_REVIEW": bool(result["constraint_refs"]),
        "NO_CHANGE_RECOMMENDED": result == empty_payload(),
    }
    if not required.get(proposal_type, False):
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "proposal payload does not match type"
        )
    if any(FORBIDDEN_MARKERS.search(text) for text in _text_values(result)):
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST,
            "patch or mutation content is forbidden",
        )
    return result


def create_resolution_proposal(
    *,
    authority: GovernanceAuthority,
    workspace_id: str,
    sequence: int,
    previous_event_hash: str,
    target_diagnostic_id: str,
    target_diagnostic_basis_hash: str,
    proposal_type: str,
    proposed_payload: Mapping[str, Any],
    rationale: str,
    created_by_label: str,
    proposal_revision: int = 1,
) -> dict[str, Any]:
    if proposal_type not in PROPOSAL_TYPES:
        raise GovernanceError(GovernanceErrorCode.INVALID_PROPOSAL_TYPE)
    authority.require_issue(target_diagnostic_id, target_diagnostic_basis_hash)
    if not isinstance(rationale, str) or not rationale.strip():
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "human rationale is required"
        )
    if not isinstance(created_by_label, str) or not created_by_label.strip():
        raise GovernanceError(
            GovernanceErrorCode.INVALID_REQUEST, "operator-supplied label is required"
        )
    payload = normalize_payload(proposal_type, proposed_payload)
    semantic = {
        "workspace_id": workspace_id,
        "sequence": sequence,
        "previous_event_hash": previous_event_hash,
        "target_diagnostic_id": target_diagnostic_id,
        "target_diagnostic_basis_hash": target_diagnostic_basis_hash,
        "proposal_type": proposal_type,
        "proposed_payload": payload,
        "rationale": rationale,
        "created_by_label": created_by_label,
        "proposal_revision": proposal_revision,
    }
    proposal = {
        "contract_version": "1.0",
        "proposal_id": stable_urn("resolution-proposal", semantic),
        "target_diagnostic_id": target_diagnostic_id,
        "target_diagnostic_basis_hash": target_diagnostic_basis_hash,
        **authority.binding,
        "proposal_type": proposal_type,
        "proposed_payload": payload,
        "rationale": rationale,
        "created_by_label": created_by_label,
        "proposal_revision": proposal_revision,
        "status": "DRAFT",
    }
    validate_governance_contract("resolution-proposal", proposal)
    return proposal
