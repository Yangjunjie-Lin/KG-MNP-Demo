from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.modeling.control_plane.providers.recorded_model import (
    verify_model_invocation_record,
)
from kg_mnp.modeling.control_plane.service import ModelingWorkspaceService
from kg_mnp.root_cli import main


def test_model_provider_list_and_conformance(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["model", "provider", "list", "--json"]) == 0
    output = capsys.readouterr().out
    assert "baseline-reuse-provider" in output
    assert "PROPOSAL_ONLY" in output
    assert main(["model", "provider", "conformance", "rule-mapping-provider", "--json"]) == 0


def test_model_help_exposes_product_commands(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["model", "--help"])
    assert raised.value.code == 0
    output = capsys.readouterr().out
    for command in ("scope", "cq", "baseline", "terminology", "propose", "prevalidate", "trace"):
        assert command in output
    assert "auto-approve" not in output


def test_recorded_provider_request_export_and_response_import_are_offline(
    prompt04_case: dict,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "recorded-workspace"
    shutil.copytree(prompt04_case["workspace"], workspace)
    service = ModelingWorkspaceService(workspace)
    service.write_build(
        prompt04_case["scope"]["scope_id"],
        {
            "ontology-scope.json": prompt04_case["scope"],
            "scope-approval.json": prompt04_case["approval"],
            "competency-question-set.json": prompt04_case["question_set"],
            "baseline-snapshot.json": prompt04_case["baseline"],
            "terminology-catalog.json": prompt04_case["terminology"],
            "term-alignment-set.json": prompt04_case["alignments"],
            "field-mapping-candidate-set.json": prompt04_case["field_mappings"],
            "modeling-input-bundle.json": prompt04_case["input_bundle"],
        },
    )
    request_path = tmp_path / "provider-request.json"
    assert (
        main(
            [
                "model",
                "provider-request",
                "export",
                str(workspace),
                "--input-bundle",
                prompt04_case["input_bundle"]["modeling_input_bundle_id"],
                "--capability",
                "tbox-proposal",
                "--output",
                str(request_path),
                "--json",
            ]
        )
        == 0
    )
    capsys.readouterr()
    response_path = tmp_path / "recorded-response.json"
    response_path.write_text(json.dumps({"candidate_drafts": []}), encoding="utf-8")
    assert (
        main(
            [
                "model",
                "provider-response",
                "import",
                str(workspace),
                str(response_path),
                "--provider",
                "recorded-model-output-provider",
                "--json",
            ]
        )
        == 0
    )
    invocation = service.latest_artifact("KG_MNP_MODEL_INVOCATION_RECORD")
    verify_model_invocation_record(
        invocation,
        request_bytes=request_path.read_bytes(),
        response_bytes=response_path.read_bytes(),
    )
    assert invocation["determinism_class"] == "RECORDED_BYTES_ONLY"


def test_cq_coverage_accepts_confirmed_package_id(
    prompt04_case: dict,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    workspace = tmp_path / "package-coverage-workspace"
    shutil.copytree(prompt04_case["workspace"], workspace)
    service = ModelingWorkspaceService(workspace)
    service.write_build(
        prompt04_case["scope"]["scope_id"],
        {
            "ontology-scope.json": prompt04_case["scope"],
            "competency-question-set.json": prompt04_case["question_set"],
        },
    )
    service.write_proposal(
        prompt04_case["proposal"]["proposal_id"],
        {"ontology-modeling-proposal.json": prompt04_case["proposal"]},
    )
    service.write_confirmed(
        prompt04_case["package"]["package_id"], prompt04_case["package"]
    )

    assert (
        main(
            [
                "model",
                "cq",
                "coverage",
                str(workspace),
                prompt04_case["package"]["package_id"],
                "--json",
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["proposal_id"] == prompt04_case["proposal"]["proposal_id"]
    assert report["execution_claimed"] is False
