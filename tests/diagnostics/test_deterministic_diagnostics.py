from __future__ import annotations

import copy
import random

import pytest

from kg_mnp_demo.diagnostics import (
    reconstruct_diagnostics,
    validate_diagnostic_package_against_authorities,
)

from ._helpers import snapshot


def requirement(**overrides):
    value = {
        "focus_node": "urn:entity:1",
        "path": "urn:property:required",
        "requirement_type": "SHACL_MIN_COUNT",
        "authority_iri": "urn:shape:constraint",
        "shape_iri": "urn:shape",
        "constraint_iri": "urn:constraint",
        "module": "test",
        "publication_id": "urn:kg-mnp:e2e-publication:" + "a" * 64,
        "min_count": 1,
        "max_count": 1,
    }
    value.update(overrides)
    return value


def test_rejection_does_not_satisfy_required_value() -> None:
    authority = snapshot(
        requirements=[requirement()],
        facts=[],
        candidates=[
            {
                "focus_node": "urn:entity:1",
                "path": "urn:property:required",
                "value": "rejected",
                "outcome": "REJECT",
                "candidate_ref": "urn:candidate:1",
                "review_decision_ref": "urn:review:1",
            }
        ],
    )
    package = reconstruct_diagnostics(authority)
    classifications = [issue["classification"] for issue in package["issues"]]
    assert "REQUIRED_VALUE_MISSING" in classifications
    assert "REJECTED_CANDIDATE_HISTORY" in classifications


def test_two_values_without_formal_exclusivity_do_not_invent_conflict() -> None:
    authority = snapshot(
        requirements=[requirement(max_count=None)],
        facts=[
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "a"},
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "b"},
        ],
    )
    assert not any(
        issue["classification"] == "CONFIRMED_VALUE_CONFLICT"
        for issue in reconstruct_diagnostics(authority)["issues"]
    )


def test_max_count_formal_conflict_preserves_authority() -> None:
    authority = snapshot(
        requirements=[requirement(path="urn:p")],
        facts=[
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "a"},
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "b"},
        ],
    )
    issues = reconstruct_diagnostics(authority)["issues"]
    conflict = next(issue for issue in issues if issue["classification"] == "CONFIRMED_VALUE_CONFLICT")
    assert conflict["authority_basis"][0]["constraint_iri"] == "urn:constraint"


def test_disjoint_classes_require_a_frozen_rule() -> None:
    classes = ["urn:class:a", "urn:class:b"]
    authority = snapshot(
        facts=[
            {"subject": "urn:entity:1", "predicate": "urn:type", "object": value}
            for value in classes
        ],
        conflict_rules=[
            {
                "focus_node": "urn:entity:1",
                "path": "urn:type",
                "rule_type": "OWL_DISJOINT_CLASSES",
                "authority_iri": "urn:axiom:disjoint",
                "module": "ontology",
                "publication_id": "urn:kg-mnp:e2e-publication:" + "a" * 64,
                "incompatible_values": classes,
            }
        ],
    )
    conflict = next(
        issue
        for issue in reconstruct_diagnostics(authority)["issues"]
        if issue["classification"] == "CONFIRMED_VALUE_CONFLICT"
    )
    assert conflict["authority_basis"][0]["requirement_type"] == "OWL_DISJOINT_CLASSES"


def test_evidence_and_source_gaps_need_explicit_requirements() -> None:
    fact = {
        "subject": "urn:entity:1",
        "predicate": "urn:p",
        "object": "value",
        "assertion_ref": "urn:assertion:1",
    }
    without_contract = reconstruct_diagnostics(snapshot(facts=[fact]))
    assert not any("REQUIRED_MISSING" in issue["classification"] for issue in without_contract["issues"])
    with_contract = reconstruct_diagnostics(
        snapshot(
            facts=[fact],
            requirements=[
                requirement(
                    path="urn:p",
                    evidence_required=True,
                    source_required=True,
                )
            ],
        )
    )
    classifications = {issue["classification"] for issue in with_contract["issues"]}
    assert {"EVIDENCE_REQUIRED_MISSING", "SOURCE_REQUIRED_MISSING"} <= classifications


def test_formal_constraint_severity_is_preserved_from_rdf_projection() -> None:
    authority = snapshot(
        constraint_results=[
            {
                "result_id": "urn:result:1",
                "focus_node": {"term_type": "IRI", "value": "urn:entity:1"},
                "result_path": {"term_type": "IRI", "value": "urn:p"},
                "value": None,
                "source_shape": {"term_type": "IRI", "value": "urn:shape:1"},
                "source_constraint_component": {
                    "term_type": "IRI",
                    "value": "http://www.w3.org/ns/shacl#MinCountConstraintComponent",
                },
                "severity": {
                    "term_type": "IRI",
                    "value": "http://www.w3.org/ns/shacl#Warning",
                },
                "message": "untrusted <script> text",
            }
        ]
    )
    issue = reconstruct_diagnostics(authority)["issues"][0]
    assert issue["classification"] == "FORMAL_CONSTRAINT_WARNING"
    assert issue["severity"] == "WARNING"
    assert issue["constraint_result"]["severity"] == "Warning"


def test_input_permutation_and_independent_reconstruction_are_stable() -> None:
    authority = snapshot(
        requirements=[requirement(path="urn:p"), requirement(path="urn:q", min_count=1)],
        facts=[
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "b"},
            {"subject": "urn:entity:1", "predicate": "urn:p", "object": "a"},
        ],
        candidates=[
            {"focus_node": "urn:entity:1", "path": "urn:q", "value": "x", "outcome": "DEFERRED"}
        ],
    )
    first = reconstruct_diagnostics(authority)
    shuffled = copy.deepcopy(authority)
    random.Random(7).shuffle(shuffled["facts"])
    random.Random(8).shuffle(shuffled["requirements"])
    second = reconstruct_diagnostics(shuffled)
    assert first.canonical_bytes() == second.canonical_bytes()
    assert validate_diagnostic_package_against_authorities(first, shuffled)["valid"]


def test_self_consistent_rehash_does_not_pass_authority_reconstruction() -> None:
    authority = snapshot(requirements=[requirement()], facts=[])
    package = reconstruct_diagnostics(authority).to_dict()
    package["issues"][0]["explanation"] = "forged"
    with pytest.raises(ValueError):
        validate_diagnostic_package_against_authorities(package, authority)


def test_sufficient_evidence_identity_is_bound_even_without_a_gap() -> None:
    evidence_requirement = requirement(
        path="urn:p",
        evidence_required=True,
        source_required=True,
    )
    fact = {
        "subject": "urn:entity:1",
        "predicate": "urn:p",
        "object": "value",
        "evidence_refs": ["urn:evidence:one"],
        "source_refs": ["urn:source:one"],
    }
    original = snapshot(requirements=[evidence_requirement], facts=[fact])
    package = reconstruct_diagnostics(original)
    assert package["issues"] == []
    attacked = copy.deepcopy(original)
    attacked["facts"][0]["evidence_refs"] = ["urn:evidence:other"]
    with pytest.raises(ValueError, match="authorities"):
        validate_diagnostic_package_against_authorities(package, attacked)
