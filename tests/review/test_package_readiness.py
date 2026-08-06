from __future__ import annotations

import pytest

from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package

from ._helpers import dependencies, load_expected_log, load_expected_package, load_input, load_proposal


@pytest.mark.parametrize(
    ("name", "input_name", "status", "compile_allowed"),
    [
        ("full-confirmation", "partial-basic", "READY_FOR_COMPILATION", True),
        ("modified-confirmation", "partial-basic", "READY_FOR_COMPILATION", True),
        ("rejection", "partial-basic", "READY_FOR_COMPILATION", True),
        ("deferred-review", "conflicting-values", "BLOCKED", False),
        ("issue-resolution", "conflicting-values", "READY_FOR_COMPILATION", True),
    ],
)
def test_readiness_scenarios(name, input_name, status, compile_allowed):
    package = load_expected_package(name)
    manifest = package["publication_manifest"]
    assert manifest["package_status"] == status
    assert manifest["compile_allowed"] is compile_allowed
    assert package["confirmed_schema_delta"] == []
    if status == "READY_FOR_COMPILATION":
        deps = dependencies()
        rebuilt = build_confirmed_modeling_package(
            load_input(input_name),
            load_proposal(input_name),
            load_expected_log(name),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            deps["terminology_profile"],
            deps["proposal_policy"],
            deps["review_policy"],
            term_types=deps["term_types"],
        )
        assert rebuilt["publication_manifest"]["package_status"] == "READY_FOR_COMPILATION"
    else:
        deps = dependencies()
        with pytest.raises(PackageBuildError):
            build_confirmed_modeling_package(
                load_input(input_name),
                load_proposal(input_name),
                load_expected_log(name),
                deps["ontology_baseline"],
                deps["mapping_rules"],
                deps["terminology_profile"],
                deps["proposal_policy"],
                deps["review_policy"],
                term_types=deps["term_types"],
            )
        blocked = build_confirmed_modeling_package(
            load_input(input_name),
            load_proposal(input_name),
            load_expected_log(name),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            deps["terminology_profile"],
            deps["proposal_policy"],
            deps["review_policy"],
            allow_blocked=True,
            term_types=deps["term_types"],
        )
        assert blocked["publication_manifest"]["package_status"] == "BLOCKED"
        assert blocked["publication_manifest"]["compile_allowed"] is False
