from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.errors import PackageError
from kg_mnp.semantic_kernel.packaging.verifier import verify_package


def test_valid_package_manifest_lock_reports_and_final_graph_bindings(prompt05_case: dict) -> None:
    package = prompt05_case["result"].package_directory
    result = verify_package(package)
    manifest = json.loads((package / "ontology-package.json").read_bytes())
    lock = json.loads((package / "ontology-package.lock.json").read_bytes())
    assert result["status"] == "VALID"
    assert manifest["package_status"] == "VALIDATED_UNPUBLISHED"
    assert lock["package_id"] == manifest["package_id"] == prompt05_case["result"].package_id
    assert "ontology-package.lock.json" not in {item["path"] for item in lock["payload_files"]}
    assert len(manifest["validation_reports"]) == 8
    assert all(item["graph_iri"].startswith("urn:kg-mnp:ontology-package-graph:") for item in manifest["graphs"])


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra"])
def test_package_tamper_missing_and_undeclared_files_fail_closed(prompt05_case: dict, tmp_path: Path, mutation: str) -> None:
    target = tmp_path / mutation
    shutil.copytree(prompt05_case["result"].package_directory, target)
    payload = target / "data" / "abox.nt"
    if mutation == "changed":
        payload.write_bytes(payload.read_bytes() + b"\n")
    elif mutation == "missing":
        payload.unlink()
    else:
        (target / "undeclared.txt").write_text("undeclared", encoding="utf-8")
    with pytest.raises(PackageError):
        verify_package(target)

