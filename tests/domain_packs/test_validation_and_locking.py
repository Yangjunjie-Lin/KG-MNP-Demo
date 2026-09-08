from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.domain_packs.locking import (
    DomainPackLockError,
    generate_pack_lock,
    verify_pack_lock,
)
from kg_mnp.domain_packs.validation import (
    load_domain_pack_manifest,
    validate_domain_pack,
)

from .conftest import ROOT, read_manifest, write_manifest


@pytest.mark.parametrize(
    "pack,lifecycle,version",
    [("minimal", "EXPERIMENTAL", "0.1.0"), ("mnp", "MIGRATED_BASELINE", "1.0.0"), ("forestry", "EXPERIMENTAL", "0.2.0")],
)
def test_repository_packs_are_formal_valid_and_locked(pack: str, lifecycle: str, version: str) -> None:
    result = validate_domain_pack(ROOT / "domain_packs" / pack)
    assert result.valid, result.report
    assert result.manifest is not None
    assert result.manifest.document["lifecycle"] == lifecycle
    assert result.manifest.pack_version == version
    assert verify_pack_lock(result.manifest).document["manifest_kind"] == "KG_MNP_DOMAIN_PACK_LOCK"


def test_forestry_has_no_fabricated_semantic_claims() -> None:
    manifest = load_domain_pack_manifest(ROOT / "domain_packs" / "forestry").document
    assert manifest["lifecycle"] == "EXPERIMENTAL"
    assert manifest["pack_version"] == "0.2.0"
    assert "合成数据" in manifest["display_name"]
    declaration = json.loads((ROOT / "domain_packs/forestry/fixtures/source-declaration.json").read_bytes())
    assert declaration["synthetic"] is True
    assert declaration["tree_records"] == declaration["inspection_records"] == 6
    assert declaration["sites"] == 2
    for claim in ("private_coordinates", "field_trial", "expert_signature", "diagnosis_or_risk_prediction"):
        assert declaration[claim] is False


def test_lock_generation_and_check_are_byte_deterministic(minimal_copy: Path) -> None:
    manifest = load_domain_pack_manifest(minimal_copy)
    first = generate_pack_lock(manifest).path.read_bytes()
    second = generate_pack_lock(manifest).path.read_bytes()
    assert first == second
    assert generate_pack_lock(manifest, check=True).path.read_bytes() == first
    assert b"generated_at" not in first
    assert str(minimal_copy).encode() not in first


def test_same_pack_copied_to_another_absolute_path_has_the_same_lock(tmp_path: Path) -> None:
    first = tmp_path / "one" / "minimal"
    second = tmp_path / "two" / "minimal"
    shutil.copytree(ROOT / "domain_packs" / "minimal", first)
    shutil.copytree(ROOT / "domain_packs" / "minimal", second)
    left = generate_pack_lock(load_domain_pack_manifest(first)).path.read_bytes()
    right = generate_pack_lock(load_domain_pack_manifest(second)).path.read_bytes()
    assert left == right


def test_changed_asset_and_manifest_make_lock_stale(minimal_copy: Path) -> None:
    manifest = load_domain_pack_manifest(minimal_copy)
    (minimal_copy / "ontology" / "minimal.ttl").write_text("invalid changed content", encoding="utf-8")
    with pytest.raises((DomainPackLockError, Exception)):
        verify_pack_lock(manifest)
    result = validate_domain_pack(minimal_copy)
    assert result.report["status"] == "INVALID"
    assert {item["code"] for item in result.report["checks"]} >= {"ASSET_PARSE_FAILED", "DOMAIN_PACK_LOCK_MISMATCH"}


def test_mnp_prompt01_semantic_content_is_preserved() -> None:
    golden = json.loads((ROOT / "tests" / "golden" / "domain-packs" / "mnp-prompt01-content.json").read_text(encoding="utf-8"))
    for item in golden["assets"]:
        content = (ROOT / item["path"]).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(content).hexdigest() == item["sha256"], item["path"]


def test_invalid_manifest_enums_and_identifiers_fail_structural_validation(minimal_copy: Path) -> None:
    for field, value in (("lifecycle", "PRODUCTION"), ("pack_id", "../minimal"), ("pack_version", "1.2")):
        manifest = read_manifest(minimal_copy)
        manifest[field] = value
        write_manifest(minimal_copy, manifest)
        result = validate_domain_pack(minimal_copy, verify_lock=False)
        assert not result.valid
        assert result.report["checks"][0]["code"] == "MANIFEST_SCHEMA_INVALID"


@pytest.mark.parametrize("mode", ["asset-id", "asset-path"])
def test_duplicate_asset_identity_and_path_are_rejected(minimal_copy: Path, mode: str) -> None:
    manifest = read_manifest(minimal_copy)
    key = "asset_id" if mode == "asset-id" else "path"
    manifest["assets"][1][key] = manifest["assets"][0][key]
    manifest["assets"] = sorted(manifest["assets"], key=lambda item: item["asset_id"])
    write_manifest(minimal_copy, manifest)
    codes = {item["code"] for item in validate_domain_pack(minimal_copy, verify_lock=False).report["checks"]}
    assert ("DUPLICATE_ASSET_ID" if mode == "asset-id" else "DUPLICATE_ASSET_PATH") in codes


def test_missing_asset_dangling_entrypoint_and_capability_mismatch_are_rejected(minimal_copy: Path) -> None:
    manifest = read_manifest(minimal_copy)
    (minimal_copy / manifest["assets"][0]["path"]).unlink()
    manifest["entrypoints"]["broken"] = "missing-asset"
    manifest["capabilities"].append("mappings")
    manifest["capabilities"].sort()
    write_manifest(minimal_copy, manifest)
    codes = {item["code"] for item in validate_domain_pack(minimal_copy, verify_lock=False).report["checks"]}
    assert {"ASSET_SECURITY_VIOLATION", "DANGLING_ENTRYPOINT", "CAPABILITY_WITHOUT_ASSET"} <= codes


@pytest.mark.parametrize("path", ["../escape.ttl", "/absolute.ttl", "C:/drive.ttl", r"\\server\\share.ttl"])
def test_manifest_asset_path_attacks_are_rejected(minimal_copy: Path, path: str) -> None:
    manifest = read_manifest(minimal_copy)
    manifest["assets"][0]["path"] = path
    write_manifest(minimal_copy, manifest)
    assert validate_domain_pack(minimal_copy, verify_lock=False).report["status"] == "INVALID"
