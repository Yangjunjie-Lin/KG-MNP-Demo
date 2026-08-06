from __future__ import annotations

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.confirmation import build_confirmed_modeling_package

from ._helpers import dependencies, load_expected_log, load_expected_package, load_input, load_proposal


def test_package_builder_is_byte_deterministic():
    deps = dependencies()
    first = build_confirmed_modeling_package(
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
    second = build_confirmed_modeling_package(
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
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert canonical_json_bytes(first) == canonical_json_bytes(
        load_expected_package("full-confirmation")
    )
