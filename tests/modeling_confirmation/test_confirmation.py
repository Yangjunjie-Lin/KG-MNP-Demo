from __future__ import annotations

import copy
import json

import pytest
from jsonschema import ValidationError

from kg_mnp.contracts.document_io import deterministic_json_bytes
from kg_mnp.modeling.control_plane.confirmation import (
    build_confirmed_package,
    verify_confirmed_package,
)
from kg_mnp.modeling.control_plane.errors import (
    ConfirmedPackageError,
    ModelingControlError,
)
from kg_mnp.modeling.control_plane.review.actions import build_review_action
from kg_mnp.modeling.control_plane.review.finalization import finalize_review


def test_confirmed_package_is_closed_partitioned_and_compiler_ready(prompt04_case: dict) -> None:
    package = prompt04_case["package"]
    verify_confirmed_package(package)
    assert package["package_status"] == "READY_FOR_COMPILATION"
    assert all(item["publication_scope"] == "TBOX" for item in package["confirmed_tbox"])
    assert all(item["publication_scope"] == "MAPPING" for item in package["confirmed_mapping"])
    assert all(item["publication_scope"] == "ABOX" for item in package["confirmed_abox"])
    assert package["evidence_closure"]["coverage_basis_points"] == 10000
    assert package["dependency_closure"]["coverage_basis_points"] == 10000
    serialized = json.dumps(package, sort_keys=True).casefold()
    assert "publication_manifest" not in serialized
    assert "graphdb_url" not in serialized


def test_package_tamper_and_prohibited_payload_fail(prompt04_case: dict) -> None:
    changed = copy.deepcopy(prompt04_case["package"])
    changed["review_semantic_hash"] = "f" * 64
    with pytest.raises((ConfirmedPackageError, ModelingControlError, ValidationError)):
        verify_confirmed_package(changed)
    prohibited = copy.deepcopy(prompt04_case["package"])
    prohibited["confirmed_tbox"][0]["rationale"] = "```turtle malicious"
    with pytest.raises(ModelingControlError, match="executable, RDF"):
        verify_confirmed_package(prohibited)


def test_package_id_has_no_operational_time_dependency(prompt04_case: dict) -> None:
    package = prompt04_case["package"]
    assert not any(key.endswith("_at") for key in package)
    assert package["package_id"].endswith(package["package_id"].rsplit(":", 1)[-1])


def test_operational_timestamps_do_not_change_confirmed_package_bytes(
    prompt04_case: dict,
) -> None:
    actions = []
    for original in prompt04_case["actions"]:
        actions.append(
            build_review_action(
                queue=prompt04_case["queue"],
                proposal=prompt04_case["proposal"],
                policy=prompt04_case["policy"],
                existing_actions=actions,
                decision=original["decision"],
                reviewer_id=original["reviewer_id"],
                reviewer_role=original["reviewer_role"],
                rationale=original["rationale"],
                candidate_id=original["candidate_id"],
                decided_at="2035-06-07T08:09:10Z",
                session_id="different-operational-session",
                display_name="Different Display Name",
            )
        )
    finalization = finalize_review(
        queue=prompt04_case["queue"],
        proposal=prompt04_case["proposal"],
        prevalidation=prompt04_case["prevalidation"],
        policy=prompt04_case["policy"],
        actions=actions,
        coverage_report=prompt04_case["coverage"],
        scope=prompt04_case["scope"],
        scope_approval=prompt04_case["approval"],
        current_project_lock_id=prompt04_case["project_lock"]["lock_id"],
    )
    rebuilt = build_confirmed_package(
        project_lock=prompt04_case["project_lock"],
        input_bundle=prompt04_case["input_bundle"],
        scope=prompt04_case["scope"],
        scope_approval=prompt04_case["approval"],
        question_set=prompt04_case["question_set"],
        coverage_report=prompt04_case["coverage"],
        baseline=prompt04_case["baseline"],
        terminology=prompt04_case["terminology"],
        alignments=prompt04_case["alignments"],
        field_mappings=prompt04_case["field_mappings"],
        proposal=prompt04_case["proposal"],
        prevalidation=prompt04_case["prevalidation"],
        review_policy=prompt04_case["policy"],
        finalization=finalization,
        actions=actions,
        review_queue=prompt04_case["queue"],
    )
    assert deterministic_json_bytes(rebuilt) == deterministic_json_bytes(
        prompt04_case["package"]
    )
