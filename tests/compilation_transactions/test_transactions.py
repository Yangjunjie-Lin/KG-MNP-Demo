from __future__ import annotations

import json
from pathlib import Path

import pytest

from kg_mnp.contracts.canonical import stable_urn
from kg_mnp.semantic_kernel.errors import PackageError
from kg_mnp.semantic_kernel.transaction import SemanticCompilationTransaction


def test_failed_transaction_removes_staging_and_leaves_no_partial_destinations(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    build_id = stable_urn("semantic-compilation-build", {"failed": 1})
    package_id = stable_urn("ontology-package", {"failed": 1})
    transaction = SemanticCompilationTransaction(workspace, build_id=build_id, package_id=package_id)
    with pytest.raises(RuntimeError, match="failure"), transaction as active:
        (active.directory("package") / "partial.txt").write_text("partial", encoding="utf-8")
        raise RuntimeError("failure")
    assert not transaction.staging.exists()
    assert not any(path.exists() for path in transaction.destinations.values())


def test_existing_valid_package_is_reused_and_tamper_is_rejected(prompt05_case: dict) -> None:
    compiler = prompt05_case["compiler"]
    first = prompt05_case["result"]
    second = compiler.build(prompt05_case["plan"]["plan_id"])
    assert first.package_id == second.package_id
    assert first.package_directory == second.package_directory
    payload = first.package_directory / "data" / "abox.nt"
    original = payload.read_bytes()
    payload.write_bytes(original + b"\n")
    try:
        with pytest.raises(PackageError):
            compiler.build(prompt05_case["plan"]["plan_id"])
    finally:
        payload.write_bytes(original)


def test_same_package_name_version_different_identity_conflicts(prompt05_case: dict) -> None:
    workspace = prompt05_case["workspace"]
    existing = json.loads((prompt05_case["result"].package_directory / "ontology-package.json").read_bytes())
    build_id = stable_urn("semantic-compilation-build", {"conflict": 1})
    package_id = stable_urn("ontology-package", {"conflict": 1})
    transaction = SemanticCompilationTransaction(workspace, build_id=build_id, package_id=package_id)
    with transaction as active:
        staged = dict(existing)
        staged["package_id"] = package_id
        (active.directory("package") / "ontology-package.json").write_text(json.dumps(staged), encoding="utf-8")
        with pytest.raises(PackageError, match="name/version"):
            active.commit()
