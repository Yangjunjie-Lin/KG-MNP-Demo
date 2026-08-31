from __future__ import annotations

import pytest
from jsonschema import ValidationError

from kg_mnp.contracts.registry import validate_contract
from kg_mnp.modeling.control_plane.competency import (
    build_question_set,
    structural_coverage,
)
from kg_mnp.modeling.control_plane.errors import ModelingControlError


def test_coverage_is_structural_and_never_claims_execution(prompt04_case: dict) -> None:
    report = structural_coverage(prompt04_case["question_set"], prompt04_case["proposal"])
    assert report["execution_claimed"] is False
    assert all(item["structural_only"] for item in report["coverage"])
    assert {item["status"] for item in report["coverage"]} <= {"COVERED", "PARTIAL", "GAP"}


def test_duplicate_question_id_and_invalid_answer_shape_fail(prompt04_case: dict) -> None:
    question = {
        "question_id": "urn:kg-mnp:competency-question:" + "1" * 64,
        "question_text": "Question?",
        "purpose": "Purpose",
    }
    with pytest.raises(ModelingControlError, match="duplicate"):
        build_question_set(
            project_lock_id=prompt04_case["project_lock"]["lock_id"],
            scope_id=prompt04_case["scope"]["scope_id"],
            questions=[question, question],
        )
    invalid = dict(prompt04_case["question_set"])
    invalid["questions"] = [dict(invalid["questions"][0], expected_answer_shape="SPARQL")]
    with pytest.raises(ValidationError):
        validate_contract("competency-question-set", invalid)
