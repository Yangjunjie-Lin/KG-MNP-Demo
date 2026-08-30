from __future__ import annotations

import os
from pathlib import Path

import pytest

from kg_mnp.domain_packs.validation import validate_domain_pack
from tests.domain_packs.conftest import read_manifest, write_manifest


def test_undeclared_semantic_and_executable_files_fail_closed(minimal_copy: Path) -> None:
    (minimal_copy / "shadow.ttl").write_text("@prefix x: <urn:x:> .", encoding="utf-8")
    (minimal_copy / "payload.py").write_text("raise RuntimeError('must never run')", encoding="utf-8")
    result = validate_domain_pack(minimal_copy, verify_lock=False)
    codes = {item["code"] for item in result.report["checks"]}
    assert "PACK_FILESYSTEM_VIOLATION" in codes
    assert "payload.py" in " ".join(item["message"] for item in result.report["checks"])


@pytest.mark.skipif(os.name == "nt", reason="POSIX execute permission bits are not exposed on Windows")
def test_executable_permission_is_rejected(minimal_copy: Path) -> None:
    path = minimal_copy / "ontology" / "minimal.ttl"
    path.chmod(0o755)
    assert validate_domain_pack(minimal_copy, verify_lock=False).report["status"] == "INVALID"


def test_symlink_escape_is_rejected_or_explicitly_skipped(minimal_copy: Path, tmp_path: Path) -> None:
    outside = tmp_path / "outside.ttl"
    outside.write_text("@prefix x: <urn:x:> .", encoding="utf-8")
    target = minimal_copy / "shadow.ttl"
    try:
        target.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"platform cannot create test symlink: {exc}")
    result = validate_domain_pack(minimal_copy, verify_lock=False)
    assert "symlink escapes" in " ".join(item["message"] for item in result.report["checks"])


@pytest.mark.parametrize(
    "asset_id,content",
    [
        ("minimal-ontology", "not turtle"),
        ("minimal-shapes", "not turtle"),
        ("minimal-query-list-entities", "DELETE WHERE { ?s ?p ?o }"),
    ],
)
def test_invalid_rdf_shacl_and_sparql_are_rejected(minimal_copy: Path, asset_id: str, content: str) -> None:
    manifest = read_manifest(minimal_copy)
    asset = next(item for item in manifest["assets"] if item["asset_id"] == asset_id)
    (minimal_copy / asset["path"]).write_text(content, encoding="utf-8")
    result = validate_domain_pack(minimal_copy, verify_lock=False)
    assert "ASSET_PARSE_FAILED" in {item["code"] for item in result.report["checks"]}


def test_ontology_iri_mismatch_is_rejected(minimal_copy: Path) -> None:
    manifest = read_manifest(minimal_copy)
    ontology = next(item for item in manifest["assets"] if item["asset_id"] == "minimal-ontology")
    ontology["ontology_iri"] = "https://example.invalid/not-declared"
    write_manifest(minimal_copy, manifest)
    codes = {item["code"] for item in validate_domain_pack(minimal_copy, verify_lock=False).report["checks"]}
    assert "ONTOLOGY_IRI_MISMATCH" in codes

