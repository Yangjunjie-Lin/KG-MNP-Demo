"""Full frozen dependency binding tests."""

from __future__ import annotations

import copy

import pytest

from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package

from ._helpers import dependencies, load_expected_log, load_input, load_proposal


def test_stale_terminology_profile_hash_fails_build():
    deps = dependencies()
    profile = copy.deepcopy(deps["terminology_profile"])
    # Keep profile_version unchanged while mutating semantic content.
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


def test_stale_proposal_policy_hash_fails_build():
    deps = dependencies()
    policy = copy.deepcopy(deps["proposal_policy"])
    # Keep policy_version unchanged while mutating a semantic field.
    mutated = False
    for key, value in list(policy.items()):
        if key in {"policy_version", "policy_id"}:
            continue
        if isinstance(value, str):
            policy[key] = value + "-stale"
            mutated = True
            break
        if isinstance(value, list):
            policy[key] = list(value) + ["stale-marker"]
            mutated = True
            break
        if isinstance(value, dict):
            policy[key] = {**value, "_stale": True}
            mutated = True
            break
        if isinstance(value, bool):
            policy[key] = not value
            mutated = True
            break
    assert mutated
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
