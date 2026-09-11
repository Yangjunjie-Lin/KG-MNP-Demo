from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from jsonschema import ValidationError
from kg_mnp.contracts import get_contract_schema, validate_contract
from kg_mnp.contracts.canonical import file_sha256, stable_urn
from kg_mnp.contracts.catalog import ContractCatalog
from kg_mnp.contracts.registry import build_contract_registry
from kg_mnp.contracts.validation import (
    artifact_manifest_checks,
    structural_validation_report,
)
from kg_mnp.modeling.registry import get_contract_schema as legacy_get_schema
from kg_mnp.modeling.registry import validate_contract as legacy_validate


def _artifact_manifest(root: Path) -> dict[str, object]:
    content = root / "a.json"
    content.write_text("{}", encoding="utf-8")
    artifact_id = stable_urn("artifact", {"name": "a"})
    payload: dict[str, object] = {
        "manifest_kind": "KG_MNP_ARTIFACT_MANIFEST",
        "schema_version": "1.0.0",
        "artifact_set_id": "",
        "artifacts": [
            {
                "manifest_kind": "KG_MNP_ARTIFACT_REFERENCE",
                "schema_version": "1.0.0",
                "artifact_id": artifact_id,
                "artifact_type": "review-input",
                "contract_name": "cleaned-partial-data",
                "contract_version": "1.0.0",
                "schema_id": get_contract_schema("cleaned-partial-data")["$id"],
                "path": "a.json",
                "media_type": "application/json",
                "size_bytes": content.stat().st_size,
                "sha256": file_sha256(content),
                "dependencies": [],
                "provenance_refs": [],
            }
        ],
        "root_artifacts": [artifact_id],
        "dependencies": [],
        "contract_catalog_digest": ContractCatalog.load().digest,
        "extensions": {},
    }
    payload["artifact_set_id"] = stable_urn(
        "artifact-set", {key: value for key, value in payload.items() if key != "artifact_set_id"}
    )
    return payload


def test_artifact_reference_and_manifest_validate_and_bind_real_files(tmp_path: Path) -> None:
    payload = _artifact_manifest(tmp_path)
    validate_contract("artifact-manifest", payload)
    assert artifact_manifest_checks(payload, artifact_root=tmp_path) == ()


def test_artifact_manifest_rejects_dangling_cycle_tamper_and_authority_claim(tmp_path: Path) -> None:
    payload = _artifact_manifest(tmp_path)
    artifact = payload["artifacts"][0]
    artifact["dependencies"] = [artifact["artifact_id"]]
    artifact["artifact_type"] = "confirmed-ontology"
    artifact["sha256"] = "0" * 64
    codes = {item.code for item in artifact_manifest_checks(payload, artifact_root=tmp_path)}
    assert {"ARTIFACT_DEPENDENCY_CYCLE", "ARTIFACT_FILE_MISMATCH", "UNSUPPORTED_AUTHORITY_CLAIM"} <= codes


def test_validation_report_is_stable_for_the_same_invalid_payload() -> None:
    first = structural_validation_report("project-manifest", {}, subject="project.yaml")
    second = structural_validation_report("project-manifest", {}, subject="project.yaml")
    assert first == second
    assert first["status"] == "INVALID"
    assert "generated_at" not in first


def test_modeling_compatibility_api_returns_identical_schema_and_behavior() -> None:
    payload = {
        "contract_version": "1.0",
        "document_id": "document-1",
        "dataset_id": "dataset-1",
        "data": {},
        "sources": [],
    }
    assert legacy_get_schema("cleaned_partial_data") == get_contract_schema("cleaned-partial-data")
    validate_contract("cleaned-partial-data", payload)
    legacy_validate("cleaned-partial-data", payload)
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        validate_contract("cleaned-partial-data", payload)
    with pytest.raises(ValidationError):
        legacy_validate("cleaned-partial-data", payload)


def test_custom_registry_fails_for_missing_ref_cycle_and_invalid_schema(tmp_path: Path) -> None:
    specs = ContractCatalog.load().filtered(scope="modeling")
    source = Path(__file__).resolve().parents[2] / "src" / "zhigou_toolchain" / "contracts" / "schemas" / "modeling"
    for mode, expected in (("missing", "unresolvable"), ("cycle", "cyclic"), ("invalid", "invalid Draft")):
        target = tmp_path / mode
        shutil.copytree(source, target)
        common_path = target / "common.schema.json"
        common = json.loads(common_path.read_text(encoding="utf-8"))
        if mode == "missing":
            common["$defs"]["Injected"] = {"$ref": "https://invalid.local/missing"}
        elif mode == "cycle":
            common["$defs"]["Injected"] = {"$ref": specs[0].schema_id}
            other_path = target / specs[0].filename
            other = json.loads(other_path.read_text(encoding="utf-8"))
            other.setdefault("$defs", {})["Injected"] = {"$ref": common["$id"]}
            other_path.write_text(json.dumps(other), encoding="utf-8")
        else:
            common["type"] = "not-a-json-schema-type"
        common_path.write_text(json.dumps(common), encoding="utf-8")
        with pytest.raises(Exception, match=expected):
            build_contract_registry(schema_directory=target, specs=specs, verify_catalog=False)

