from __future__ import annotations

import copy
from pathlib import Path

import pytest

from kg_mnp_demo.modeling.canonical_json import semantic_hash
from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package
from kg_mnp_demo.modeling.identifiers import candidate_id
from kg_mnp_demo.modeling.review_identifiers import (
    confirmed_item_id,
    confirmed_package_id,
    decision_log_hash,
    package_semantic_hash,
    review_decision_id,
)
from kg_mnp_demo.modeling.review_log import finalize_review_decision_log
from kg_mnp_demo.modeling.review_policy import ReviewPolicyError
from kg_mnp_demo.modeling import review_policy as review_policy_module
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_confirmed_modeling_package_semantics,
    validate_review_decision_log_semantics,
)

from ._helpers import (
    dependencies,
    load_expected_log,
    load_expected_package,
    load_input,
    load_proposal,
)


def _validate_complete(package, *, scenario: str, input_name: str, **dep_overrides):
    deps = dependencies()
    deps.update(dep_overrides)
    validate_confirmed_modeling_package_semantics(
        package,
        load_proposal(input_name),
        load_expected_log(scenario),
        cleaned_partial_data=load_input(input_name),
        ontology_baseline=deps["ontology_baseline"],
        mapping_rules=deps["mapping_rules"],
        terminology_profile=deps["terminology_profile"],
        proposal_policy=deps["proposal_policy"],
        review_policy=deps["review_policy"],
        term_types=deps["term_types"],
        require_complete=True,
    )


def _rehash_package(package: dict) -> dict:
    package = copy.deepcopy(package)
    digest = package_semantic_hash(package)
    package["package_semantic_hash"] = digest
    package["package_id"] = confirmed_package_id(digest)
    return package


def _as_draft(log: dict) -> dict:
    draft = copy.deepcopy(log)
    session = dict(draft["review_session"])
    session.pop("completed_at", None)
    draft["review_session"] = session
    draft["log_hash"] = decision_log_hash(draft)
    return draft


def test_tampered_hashes_and_ids_fail_closed():
    proposal = load_proposal()
    log = copy.deepcopy(load_expected_log("full-confirmation"))
    deps = dependencies()
    log["log_hash"] = "a" * 64
    with pytest.raises(SemanticValidationError, match="log_hash"):
        validate_review_decision_log_semantics(
            log,
            proposal,
            review_policy=deps["review_policy"],
            require_final=True,
            term_types=deps["term_types"],
        )
    log = copy.deepcopy(load_expected_log("full-confirmation"))
    log["decisions"][0]["decision_id"] = "urn:kg-mnp:review-decision:" + "b" * 64
    with pytest.raises(SemanticValidationError, match="decision_id"):
        validate_review_decision_log_semantics(
            log,
            proposal,
            review_policy=deps["review_policy"],
            require_final=True,
            term_types=deps["term_types"],
        )
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    package["package_semantic_hash"] = "c" * 64
    with pytest.raises(SemanticValidationError, match="package_semantic_hash"):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_unknown_and_duplicate_targets_fail():
    proposal = load_proposal()
    deps = dependencies()
    log = copy.deepcopy(load_expected_log("full-confirmation"))
    log["decisions"][0]["candidate_id"] = "urn:kg-mnp:candidate:" + "f" * 64
    with pytest.raises(SemanticValidationError, match="unknown candidate_id"):
        validate_review_decision_log_semantics(
            log,
            proposal,
            review_policy=deps["review_policy"],
            require_final=True,
            term_types=deps["term_types"],
        )
    log = copy.deepcopy(load_expected_log("full-confirmation"))
    log["decisions"].append(copy.deepcopy(log["decisions"][0]))
    with pytest.raises(SemanticValidationError, match="multiple review decisions"):
        validate_review_decision_log_semantics(
            log,
            proposal,
            review_policy=deps["review_policy"],
            require_final=False,
            term_types=deps["term_types"],
        )


def test_blocking_deferred_cannot_be_ready():
    """Self-hash must be valid; failure must come from readiness reconstruction."""

    package = copy.deepcopy(load_expected_package("deferred-review"))
    package["publication_manifest"]["package_status"] = "READY_FOR_COMPILATION"
    package["publication_manifest"]["compile_allowed"] = True
    package["publication_manifest"]["unresolved_blocking_issue_ids"] = []
    package = _rehash_package(package)
    assert package["package_semantic_hash"] == package_semantic_hash(package)
    assert package["package_id"] == confirmed_package_id(package)
    with pytest.raises(
        SemanticValidationError,
        match="readiness derivation|deterministic reconstruction",
    ):
        _validate_complete(
            package,
            scenario="deferred-review",
            input_name="conflicting-values",
        )


def test_package_count_mismatch_fails():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    package["publication_manifest"]["confirmed_abox_count"] = 0
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_rehashed_readiness_forgery():
    test_blocking_deferred_cannot_be_ready()


def test_rehashed_semantic_content_forgery():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    item = package["confirmed_abox_decisions"][0]
    content = copy.deepcopy(item["confirmed_candidate"]["semantic_content"])
    content["rationale"] = str(content.get("rationale", "")) + " forged"
    item["confirmed_candidate"]["semantic_content"] = content
    item["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    item["confirmed_candidate"]["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=item["confirmed_candidate"]["source_candidate_id"],
        effective_candidate_id=item["confirmed_candidate"]["effective_candidate_id"],
        confirmation_mode=item["confirmed_candidate"]["confirmation_mode"],
        semantic_content=content,
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_wrong_confirmed_item_id_after_rehash():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    item = package["confirmed_abox_decisions"][0]
    item["confirmed_candidate"]["confirmed_item_id"] = (
        "urn:kg-mnp:confirmed-item:" + "a" * 64
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_wrong_confirmed_semantic_hash_after_rehash():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    item = package["confirmed_abox_decisions"][0]
    item["confirmed_candidate"]["semantic_hash"] = "b" * 64
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_broken_closure_after_rehash():
    package = copy.deepcopy(load_expected_package("rejection"))
    rejected = next(
        item["candidate_id"] for item in package["rejected_items"] if "candidate_id" in item
    )
    assertion = next(
        item
        for item in package["confirmed_abox_decisions"]
        if item["confirmed_candidate"]["semantic_content"].get("candidate_kind")
        == "OBJECT_PROPERTY_ASSERTION"
    )
    content = copy.deepcopy(assertion["confirmed_candidate"]["semantic_content"])
    content["object"] = rejected
    assertion["confirmed_candidate"]["semantic_content"] = content
    assertion["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    assertion["confirmed_candidate"]["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=assertion["confirmed_candidate"]["source_candidate_id"],
        effective_candidate_id=assertion["confirmed_candidate"]["effective_candidate_id"],
        confirmation_mode=assertion["confirmed_candidate"]["confirmation_mode"],
        semantic_content=content,
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError, match="deterministic reconstruction"):
        _validate_complete(package, scenario="rejection", input_name="partial-basic")


def test_functional_conflict_after_rehash():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    original = next(
        item
        for item in package["confirmed_abox_decisions"]
        if item["confirmed_candidate"]["semantic_content"].get("candidate_kind")
        == "DATA_PROPERTY_ASSERTION"
    )
    forged = copy.deepcopy(original)
    content = copy.deepcopy(forged["confirmed_candidate"]["semantic_content"])
    content["object"] = {
        **content["object"],
        "value": str(content["object"].get("value", "")) + "-conflict",
    }
    content["rationale"] = str(content.get("rationale", "")) + " conflict duplicate"
    forged_candidate_id = "urn:kg-mnp:candidate:" + "c" * 64
    forged_decision_id = "urn:kg-mnp:review-decision:" + "d" * 64
    forged["candidate_id"] = forged_candidate_id
    forged["decision_id"] = forged_decision_id
    forged["confirmed_candidate"]["semantic_content"] = content
    forged["confirmed_candidate"]["semantic_hash"] = semantic_hash(content)
    forged["confirmed_candidate"]["source_candidate_id"] = forged_candidate_id
    forged["confirmed_candidate"]["effective_candidate_id"] = forged_candidate_id
    forged["confirmed_candidate"]["confirmed_item_id"] = confirmed_item_id(
        source_candidate_id=forged_candidate_id,
        effective_candidate_id=forged_candidate_id,
        confirmation_mode="ORIGINAL",
        semantic_content=content,
    )
    package["confirmed_abox_decisions"].append(forged)
    package["publication_manifest"]["confirmed_abox_count"] = len(
        package["confirmed_abox_decisions"]
    )
    package = _rehash_package(package)
    with pytest.raises(SemanticValidationError):
        _validate_complete(package, scenario="full-confirmation", input_name="partial-basic")


def test_finalize_illegal_decision():
    proposal = load_proposal("conflicting-values")
    deps = dependencies()
    draft = _as_draft(load_expected_log("deferred-review"))
    for decision in draft["decisions"]:
        if "issue_id" not in decision:
            continue
        decision["decision"] = "CONFIRM"
        decision["decision_id"] = review_decision_id(
            proposal_id=str(proposal["proposal_id"]),
            target_id=str(decision["issue_id"]),
            decision="CONFIRM",
            rationale=str(decision["rationale"]),
            reviewer_id=str(decision["reviewer_id"]),
            decided_at=str(decision["decided_at"]),
            evidence_refs=list(decision.get("evidence_refs") or []),
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


def test_finalize_illegal_modified_candidate():
    proposal = load_proposal()
    deps = dependencies()
    draft = _as_draft(load_expected_log("modified-confirmation"))
    for decision in draft["decisions"]:
        if decision.get("decision") != "MODIFY_AND_CONFIRM":
            continue
        modified = copy.deepcopy(decision["modified_candidate"])
        modified["source_paths"] = ["/forged/missing-original"]
        modified["rationale"] = str(modified.get("rationale", "")) + " illegal"
        modified["candidate_id"] = candidate_id(modified)
        decision["modified_candidate"] = modified
        decision["decision_id"] = review_decision_id(
            proposal_id=str(proposal["proposal_id"]),
            target_id=str(decision["candidate_id"]),
            decision="MODIFY_AND_CONFIRM",
            rationale=str(decision["rationale"]),
            reviewer_id=str(decision["reviewer_id"]),
            decided_at=str(decision["decided_at"]),
            evidence_refs=list(decision.get("evidence_refs") or []),
            modified_candidate=modified,
        )
        break
    draft["log_hash"] = decision_log_hash(draft)
    with pytest.raises(SemanticValidationError, match="source_paths|preserve|schema"):
        finalize_review_decision_log(
            proposal,
            draft,
            completed_at="2026-08-06T02:00:00Z",
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
        )


def test_stale_dependency_build_and_validate():
    deps = dependencies()
    profile = copy.deepcopy(deps["terminology_profile"])
    profile["entries"] = list(profile.get("entries", [])) + [
        {"term_iri": "urn:kg-mnp:stale-term", "preferred_label": "stale"}
    ]
    with pytest.raises(PackageBuildError, match="terminology_profile_hash mismatch"):
        build_confirmed_modeling_package(
            load_input(),
            load_proposal(),
            load_expected_log("full-confirmation"),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            profile,
            deps["proposal_policy"],
            deps["review_policy"],
            term_types=deps["term_types"],
        )
    policy = copy.deepcopy(deps["proposal_policy"])
    for key, value in list(policy.items()):
        if key in {"policy_version", "policy_id", "generator_version"}:
            continue
        if isinstance(value, str):
            policy[key] = value + "-stale"
            break
        if isinstance(value, bool):
            policy[key] = not value
            break
    with pytest.raises(PackageBuildError, match="proposal_policy_hash mismatch"):
        build_confirmed_modeling_package(
            load_input(),
            load_proposal(),
            load_expected_log("full-confirmation"),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            deps["terminology_profile"],
            policy,
            deps["review_policy"],
            term_types=deps["term_types"],
        )
    package = load_expected_package("full-confirmation")
    stale_review = copy.deepcopy(deps["review_policy"])
    stale_review["policy_id"] = stale_review["policy_id"] + "-stale"
    with pytest.raises(SemanticValidationError):
        _validate_complete(
            package,
            scenario="full-confirmation",
            input_name="partial-basic",
            review_policy=stale_review,
        )


def test_policy_failure_fail_closed(tmp_path: Path, monkeypatch):
    missing = tmp_path / "missing-review-policy.yaml"
    monkeypatch.setattr(review_policy_module, "REVIEW_POLICY_PATH", missing)
    review_policy_module.load_default_review_policy.cache_clear()
    with pytest.raises((ReviewPolicyError, SemanticValidationError)):
        validate_review_decision_log_semantics(
            load_expected_log("full-confirmation"),
            load_proposal(),
            review_policy=None,
            require_final=True,
        )
    review_policy_module.load_default_review_policy.cache_clear()
