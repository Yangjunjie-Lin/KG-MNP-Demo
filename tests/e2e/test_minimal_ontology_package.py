from __future__ import annotations

import json
import shutil
from pathlib import Path

from kg_mnp.semantic_kernel.compiler import SemanticCompiler
from kg_mnp.semantic_kernel.packaging.archive import archive_bytes
from kg_mnp.semantic_kernel.packaging.verifier import verify_package

ROOT = Path(__file__).resolve().parents[2]


def test_minimal_current_catalog_full_package_gate(prompt05_case: dict) -> None:
    result = prompt05_case["result"]
    package = result.package_directory
    manifest = json.loads((package / "ontology-package.json").read_bytes())
    reports = {
        path.name: json.loads(path.read_bytes())
        for path in (package / "validation").glob("*.json")
    }
    assert prompt05_case["attestation"]["status"] == "VALID"
    assert verify_package(package)["status"] == "VALID"
    assert manifest["package_status"] == "VALIDATED_UNPUBLISHED"
    assert reports["owl-profile-report.json"]["status"] == "PASSED"
    assert reports["owl-consistency-report.json"]["status"] == "CONSISTENT"
    assert reports["shacl-validation-report.json"]["status"] == "CONFORMS"
    assert reports["competency-question-test-report.json"]["required_passed"] is True
    assert reports["provenance-closure-report.json"]["coverage_basis_points"] == 10000
    assert archive_bytes(package) == archive_bytes(package)


def test_minimal_package_reproduces_from_a_different_absolute_workspace(prompt05_case: dict, tmp_path: Path) -> None:
    copied_workspace = tmp_path / "different-absolute-root" / "workspace"
    shutil.copytree(prompt05_case["workspace"], copied_workspace)
    compiler = SemanticCompiler(
        copied_workspace,
        domain_packs_root=ROOT / "domain_packs",
        reasoner_jar=prompt05_case["jar"],
    )
    reproduction = compiler.reproduce(prompt05_case["plan"]["plan_id"])
    copied_package = copied_workspace / "artifacts" / "packages" / prompt05_case["result"].package_directory.name
    assert reproduction["status"] == "PASSED"
    assert reproduction["package_id"] == prompt05_case["result"].package_id
    assert (copied_package / "ontology-package.lock.json").read_bytes() == (
        prompt05_case["result"].package_directory / "ontology-package.lock.json"
    ).read_bytes()
    assert archive_bytes(copied_package) == archive_bytes(prompt05_case["result"].package_directory)
