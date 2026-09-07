from __future__ import annotations

import json

import pytest

from kg_mnp.workbench.binding import WorkbenchBinding
from kg_mnp.workbench.errors import WorkbenchError
from kg_mnp.workbench.manifest import (
    build_workbench_package,
    validate_workbench_package,
)

from ._helpers import write_phase01_artifact


@pytest.fixture
def historical_ui_bytes(tmp_path):
    """Inert legacy-format data, not a retained copy of the retired product UI."""
    directory=tmp_path/'historical-format-input'
    (directory/'assets').mkdir(parents=True)
    (directory/'index.html').write_text('<!doctype html><title>Synthetic format fixture</title>',encoding='utf-8')
    (directory/'assets/app.js').write_text('// inert format fixture',encoding='utf-8')
    (directory/'assets/styles.css').write_text('body{color:black}',encoding='utf-8')
    return directory


def test_frontend_build_is_byte_deterministic_and_bound_to_phase01(tmp_path,historical_ui_bytes) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    first = build_workbench_package(tmp_path / "first", binding,source_directory=historical_ui_bytes)
    second = build_workbench_package(tmp_path / "second", binding,source_directory=historical_ui_bytes)
    assert first == second
    assert first["frontend_build_hash"] == second["frontend_build_hash"]
    assert first["phase01_attestation_hash"] == binding.phase01_attestation_hash
    assert first["semantic_authority"] is False
    assert first["status"] == "WORKBENCH_PACKAGE_VALIDATED"


def test_package_validation_fails_on_bundle_or_manifest_tampering(tmp_path,historical_ui_bytes) -> None:
    binding = WorkbenchBinding.load(write_phase01_artifact(tmp_path / "phase01"))
    package = tmp_path / "package"
    build_workbench_package(package, binding,source_directory=historical_ui_bytes)
    (package / "assets" / "app.js").write_text("tampered", encoding="utf-8")
    with pytest.raises(WorkbenchError, match="PACKAGE_INVALID"):
        validate_workbench_package(package, binding)

    build_workbench_package(package, binding,source_directory=historical_ui_bytes)
    manifest_path = package / "workbench-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["query_registry_hash"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(WorkbenchError, match="PACKAGE_INVALID"):
        validate_workbench_package(package, binding)


def test_production_bundle_contains_no_direct_storage_connection_material() -> None:
    from pathlib import Path
    source=Path(__file__).resolve().parents[2]/'workbench/src'
    joined = b"\n".join(
        path.read_bytes().lower()
        for path in source.rglob("*")
        if path.suffix in {'.ts','.tsx'} and '.test.' not in path.name
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
