from __future__ import annotations

import pytest

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.confirmation import PackageBuildError, build_confirmed_modeling_package

from ._helpers import dependencies, load_expected_log, load_expected_package, load_input, load_proposal


def test_builder_matches_golden_full_confirmation():
    deps = dependencies()
    package = build_confirmed_modeling_package(
        load_input(),
        load_proposal(),
        load_expected_log("full-confirmation"),
        deps["ontology_baseline"],
        deps["mapping_rules"],
        deps["terminology_profile"],
        deps["proposal_policy"],
        deps["review_policy"],
        term_types=deps["term_types"],
    )
    expected = load_expected_package("full-confirmation")
    assert canonical_json_bytes(package) == canonical_json_bytes(expected)
    assert package["confirmed_schema_delta"] == []
    assert package["publication_manifest"]["package_status"] == "READY_FOR_COMPILATION"


def test_builder_rejects_blocked_by_default():
    deps = dependencies()
    with pytest.raises(PackageBuildError, match="BLOCKED"):
        build_confirmed_modeling_package(
            load_input("conflicting-values"),
            load_proposal("conflicting-values"),
            load_expected_log("deferred-review"),
            deps["ontology_baseline"],
            deps["mapping_rules"],
            deps["terminology_profile"],
            deps["proposal_policy"],
            deps["review_policy"],
            term_types=deps["term_types"],
        )
