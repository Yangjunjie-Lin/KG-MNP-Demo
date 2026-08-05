from __future__ import annotations

from copy import deepcopy

from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal

from ._helpers import generate, load_input


def test_partial_basic_generates_abox_candidates_only() -> None:
    proposal = generate("partial-basic")
    assert proposal["run_mode"] == "DATASET_MODELING"
    assert len(proposal["candidate_entities"]) == 3
    assert len(proposal["candidate_assertions"]) == 2
    assert proposal["schema_delta_candidates"] == []
    for candidate in [
        *proposal["candidate_entities"],
        *proposal["candidate_assertions"],
    ]:
        assert candidate["review_status"] == "PROPOSED"
        assert candidate["publication_scope"] == "ABOX"
        assert candidate["business_fact_evidence_refs"] == ["source-basic"]
        assert candidate["modeling_evidence_refs"]


def test_proposal_snapshots_every_dependency() -> None:
    snapshot = generate("partial-basic")["dependency_snapshot"]
    assert snapshot["ontology_version"] == "1.0.0"
    assert snapshot["mapping_set_version"] == "1.0.0"
    assert snapshot["terminology_profile_version"] == "1.0.0"
    assert snapshot["proposal_policy_version"] == "1.0.0"
    for key in (
        "ontology_release_source_hash",
        "mapping_rules_hash",
        "terminology_profile_hash",
        "proposal_policy_hash",
    ):
        assert len(snapshot[key]) == 64


def test_generator_does_not_mutate_any_semantic_input() -> None:
    dependencies = load_modeling_dependencies()
    cleaned = load_input("partial-basic")
    values = [
        cleaned,
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        dependencies["proposal_policy"],
    ]
    before = deepcopy(values)
    generate_modeling_proposal(
        *values,
        term_iris=set(dependencies["term_iris"]),
    )
    assert values == before
