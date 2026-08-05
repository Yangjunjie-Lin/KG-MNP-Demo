from __future__ import annotations

import pytest

from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal

from ._helpers import generate, load_input


def test_every_example_has_an_empty_schema_delta() -> None:
    for name in (
        "partial-basic",
        "explicit-null",
        "declared-missing",
        "conflicting-values",
        "unmapped-fields",
        "low-confidence-source",
    ):
        assert generate(name)["schema_delta_candidates"] == []


def test_ontology_release_mode_is_rejected() -> None:
    dependencies = load_modeling_dependencies()
    with pytest.raises(ValueError, match="UNSUPPORTED_IN_STAGE_04"):
        generate_modeling_proposal(
            load_input("partial-basic"),
            dependencies["ontology_baseline"],
            dependencies["mapping_rules"],
            dependencies["terminology_profile"],
            dependencies["proposal_policy"],
            term_iris=set(dependencies["term_iris"]),
            run_mode="ONTOLOGY_RELEASE",
        )

