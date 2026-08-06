"""Fail-closed review finalization security tests."""

from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.identifiers import candidate_id
from kg_mnp_demo.modeling.review_identifiers import decision_log_hash, review_decision_id
from kg_mnp_demo.modeling.review_log import finalize_review_decision_log
from kg_mnp_demo.modeling.semantic_validation import SemanticValidationError

from ._helpers import dependencies, load_expected_log, load_proposal


def _as_draft(log: dict) -> dict:
    draft = copy.deepcopy(log)
    session = dict(draft["review_session"])
    session.pop("completed_at", None)
    draft["review_session"] = session
    draft["log_hash"] = decision_log_hash(draft)
    return draft


def _rebind_decision(proposal: dict, decision: dict, *, new_decision: str, modified=None) -> dict:
    updated = copy.deepcopy(decision)
    updated["decision"] = new_decision
    if modified is None:
        updated.pop("modified_candidate", None)
    else:
        updated["modified_candidate"] = modified
    target = updated.get("candidate_id") or updated.get("issue_id")
    updated["decision_id"] = review_decision_id(
        proposal_id=str(proposal["proposal_id"]),
        target_id=str(target),
        decision=new_decision,
        rationale=str(updated["rationale"]),
        reviewer_id=str(updated["reviewer_id"]),
        decided_at=str(updated["decided_at"]),
        evidence_refs=list(updated.get("evidence_refs") or []),
        modified_candidate=updated.get("modified_candidate"),
    )
    return updated


def test_finalize_rejects_issue_confirm_with_valid_decision_id():
    proposal = load_proposal("conflicting-values")
    deps = dependencies()
    draft = _as_draft(load_expected_log("deferred-review"))
    for index, decision in enumerate(draft["decisions"]):
        if "issue_id" in decision:
            draft["decisions"][index] = _rebind_decision(
                proposal, decision, new_decision="CONFIRM"
            )
            break
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(
        SemanticValidationError,
        match="decision CONFIRM is not allowed for issue targets",
    ):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_finalize_rejects_candidate_deprecate_with_valid_decision_id():
    proposal = load_proposal()
    deps = dependencies()
    draft = _as_draft(load_expected_log("full-confirmation"))
    draft["decisions"][0] = _rebind_decision(
        proposal, draft["decisions"][0], new_decision="DEPRECATE"
    )
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(SemanticValidationError, match="DEPRECATE|not allowed for candidate"):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_finalize_rejects_illegal_modified_candidate_missing_source_paths():
    proposal = load_proposal()
    deps = dependencies()
    draft = _as_draft(load_expected_log("modified-confirmation"))
    target = None
    for index, decision in enumerate(draft["decisions"]):
        if decision.get("decision") == "MODIFY_AND_CONFIRM":
            target = index
            modified = copy.deepcopy(decision["modified_candidate"])
            # Schema-valid but drops original source provenance.
            modified["source_paths"] = ["/unrelated/forged/path"]
            modified["candidate_id"] = candidate_id(modified)
            draft["decisions"][index] = _rebind_decision(
                proposal,
                decision,
                new_decision="MODIFY_AND_CONFIRM",
                modified=modified,
            )
            break
    assert target is not None
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(SemanticValidationError, match="source_paths|preserve"):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_finalize_rejects_modified_candidate_kind_drift():
    proposal = load_proposal()
    deps = dependencies()
    draft = _as_draft(load_expected_log("modified-confirmation"))
    for index, decision in enumerate(draft["decisions"]):
        if decision.get("decision") != "MODIFY_AND_CONFIRM":
            continue
        modified = copy.deepcopy(decision["modified_candidate"])
        # Force an illegal kind change while keeping ABOX entity fields.
        modified["candidate_kind"] = "DATA_PROPERTY_ASSERTION"
        modified["predicate_iri"] = (
            "https://yangjunjie-lin.github.io/KG-MNP-Demo/ontology/terms#hasStatus"
        )
        modified["object"] = {"value": "ACTIVE", "datatype": "xsd:string"}
        modified["subject_ref"] = decision["candidate_id"]
        modified.pop("class_iri", None)
        modified.pop("proposed_iri", None)
        modified["candidate_id"] = candidate_id(modified)
        draft["decisions"][index] = _rebind_decision(
            proposal,
            decision,
            new_decision="MODIFY_AND_CONFIRM",
            modified=modified,
        )
        break
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(SemanticValidationError, match="candidate_kind|kind"):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_finalize_rejects_modified_candidate_tbox_scope():
    proposal = load_proposal()
    deps = dependencies()
    draft = _as_draft(load_expected_log("modified-confirmation"))
    for index, decision in enumerate(draft["decisions"]):
        if decision.get("decision") != "MODIFY_AND_CONFIRM":
            continue
        modified = copy.deepcopy(decision["modified_candidate"])
        modified["publication_scope"] = "TBOX"
        modified["candidate_id"] = candidate_id(modified)
        draft["decisions"][index] = _rebind_decision(
            proposal,
            decision,
            new_decision="MODIFY_AND_CONFIRM",
            modified=modified,
        )
        break
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(
        SemanticValidationError,
        match="ABOX|publication_scope|schema validation",
    ):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )
