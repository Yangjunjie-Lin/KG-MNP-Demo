from __future__ import annotations

from copy import deepcopy

from kg_mnp_demo.modeling.canonical_json import canonical_json_bytes
from kg_mnp_demo.modeling.dependencies import load_modeling_dependencies
from kg_mnp_demo.modeling.proposal import generate_modeling_proposal

from ._helpers import generate, load_input


def test_same_inputs_generate_identical_bytes_and_identifiers() -> None:
    first = generate("partial-basic")
    second = generate("partial-basic")
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert first["proposal_id"] == second["proposal_id"]
    assert first["proposal_semantic_hash"] == second["proposal_semantic_hash"]
    assert [item["candidate_id"] for item in first["candidate_entities"]] == [
        item["candidate_id"] for item in second["candidate_entities"]
    ]
    assert [item["issue_id"] for item in first["issues"]] == [
        item["issue_id"] for item in second["issues"]
    ]


def test_dependency_change_changes_snapshot_and_proposal_hash() -> None:
    dependencies = load_modeling_dependencies()
    policy = deepcopy(dependencies["proposal_policy"])
    policy["policy_version"] = "1.0.1"
    changed = generate_modeling_proposal(
        load_input("partial-basic"),
        dependencies["ontology_baseline"],
        dependencies["mapping_rules"],
        dependencies["terminology_profile"],
        policy,
        term_iris=set(dependencies["term_iris"]),
    )
    original = generate("partial-basic")
    assert changed["dependency_snapshot"]["proposal_policy_hash"] != original[
        "dependency_snapshot"
    ]["proposal_policy_hash"]
    assert changed["proposal_semantic_hash"] != original["proposal_semantic_hash"]


def test_all_expected_proposals_are_byte_exact_golden_outputs() -> None:
    from ._helpers import ROOT

    for name in (
        "partial-basic",
        "explicit-null",
        "declared-missing",
        "conflicting-values",
        "unmapped-fields",
        "low-confidence-source",
    ):
        expected = (
            ROOT
            / "examples"
            / "modeling"
            / "expected-proposals"
            / f"{name}.proposal.json"
        ).read_bytes()
        assert canonical_json_bytes(generate(name)) + b"\n" == expected
