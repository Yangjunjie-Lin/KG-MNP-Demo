from __future__ import annotations

import json

import pytest

from kg_mnp_demo.workbench.binding import WorkbenchBinding
from kg_mnp_demo.workbench.errors import WorkbenchError
from kg_mnp_demo.workbench.manifest import (
    build_workbench_package,
    validate_workbench_package,
)

from ._helpers import write_phase01_artifact


def test_frontend_build_is_byte_deterministic_and_bound_to_phase01(tmp_path) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    first = build_workbench_package(tmp_path / "first", binding)
    second = build_workbench_package(tmp_path / "second", binding)
    assert first == second
    assert first["frontend_build_hash"] == second["frontend_build_hash"]
    assert first["phase01_attestation_hash"] == binding.phase01_attestation_hash
    assert first["semantic_authority"] is False
    assert first["status"] == "WORKBENCH_PACKAGE_VALIDATED"


def test_package_validation_fails_on_bundle_or_manifest_tampering(tmp_path) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    package = tmp_path / "package"
    build_workbench_package(package, binding)
    (package / "assets" / "app.js").write_text("tampered", encoding="utf-8")
    with pytest.raises(WorkbenchError, match="PACKAGE_INVALID"):
        validate_workbench_package(package, binding)

    build_workbench_package(package, binding)
    manifest_path = package / "workbench-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["query_registry_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkbenchError, match="PACKAGE_INVALID"):
        validate_workbench_package(package, binding)


def test_production_bundle_contains_no_direct_storage_connection_material(tmp_path) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    package = tmp_path / "package"
    build_workbench_package(package, binding)
    joined = b"\n".join(
        path.read_bytes().lower()
        for path in package.rglob("*")
        if path.is_file() and path.name != "workbench-manifest.json"
    )
    for marker in (
        b"/repositories/",
        b"sparql endpoint",
        b"graph store protocol",
        b"graphdb username",
        b"graphdb password",
        b"graphdb license",
        b"0.0.0.0",
    ):
        assert marker not in joined
