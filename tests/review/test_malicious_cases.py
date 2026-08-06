from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package
from kg_mnp_demo.modeling.semantic_validation import (
    SemanticValidationError,
    validate_confirmed_modeling_package_semantics,
    validate_review_decision_log_semantics,
)

from ._helpers import dependencies, load_expected_log, load_expected_package, load_input, load_proposal


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
        validate_confirmed_modeling_package_semantics(
            package,
            proposal,
            load_expected_log("full-confirmation"),
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
            require_complete=True,
        )


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
    package = copy.deepcopy(load_expected_package("deferred-review"))
    package["publication_manifest"]["package_status"] = "READY_FOR_COMPILATION"
    package["publication_manifest"]["compile_allowed"] = True
    deps = dependencies()
    with pytest.raises(SemanticValidationError):
        validate_confirmed_modeling_package_semantics(
            package,
            load_proposal("conflicting-values"),
            load_expected_log("deferred-review"),
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
            require_complete=True,
        )


def test_package_count_mismatch_fails():
    package = copy.deepcopy(load_expected_package("full-confirmation"))
    package["publication_manifest"]["confirmed_abox_count"] = 0
    deps = dependencies()
    with pytest.raises(SemanticValidationError, match="confirmed_abox_count"):
        validate_confirmed_modeling_package_semantics(
            package,
            load_proposal(),
            load_expected_log("full-confirmation"),
            review_policy=deps["review_policy"],
            term_types=deps["term_types"],
            require_complete=True,
        )
