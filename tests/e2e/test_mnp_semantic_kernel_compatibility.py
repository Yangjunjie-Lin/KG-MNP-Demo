from __future__ import annotations

import json
from pathlib import Path

from mnp_prompt05_support import build_mnp_prompt05

from kg_mnp.semantic_kernel.packaging.verifier import verify_package


def test_mnp_current_catalog_review_confirmation_and_semantic_kernel(tmp_path: Path) -> None:
    case = build_mnp_prompt05(tmp_path)
    assert case["attestation"]["status"] == "VALID"
    assert case["confirmed"]["package_status"] == "READY_FOR_COMPILATION"
    assert len(case["confirmed"]["confirmed_tbox"]) == 1
    assert not case["confirmed"]["confirmed_abox"]
    assert case["plan"]["candidate_dispatch"][0]["candidate_action"] == "REUSE_EXISTING"
    verified = verify_package(case["result"].package_directory)
    manifest = json.loads((case["result"].package_directory / "ontology-package.json").read_bytes())
    cq_report = json.loads((case["result"].package_directory / "validation/competency-question-test-report.json").read_bytes())
    assert verified["status"] == "VALID"
    assert manifest["package_status"] == "VALIDATED_UNPUBLISHED"
    assert cq_report["required_passed"] is True
    assert case["lock_path"].read_bytes() == case["lock_before"]
    assert case["registry_after"] == case["registry_before"]
    assert not (case["opened"].root / "graphdb").exists()
