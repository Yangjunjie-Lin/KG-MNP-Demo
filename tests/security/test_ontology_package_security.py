from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from kg_mnp.semantic_kernel.errors import PackageError
from kg_mnp.semantic_kernel.packaging.locking import build_package_lock
from kg_mnp.semantic_kernel.packaging.verifier import verify_package


def test_package_manifest_and_lock_tamper_both_fail(prompt05_case: dict, tmp_path: Path) -> None:
    for name in ("ontology-package.json", "ontology-package.lock.json"):
        target = tmp_path / name.replace(".json", "")
        shutil.copytree(prompt05_case["result"].package_directory, target)
        authority = target / name
        document = json.loads(authority.read_bytes())
        if name == "ontology-package.json":
            document["package_status"] = "PUBLISHED"
        else:
            document["content_digest"] = "0" * 64
        authority.write_text(json.dumps(document), encoding="utf-8")
        with pytest.raises(PackageError):
            verify_package(target)


def test_rehashed_identity_payload_digest_tamper_fails_semantic_reconstruction(
    prompt05_case: dict,
    tmp_path: Path,
) -> None:
    target = tmp_path / "identity-payload"
    shutil.copytree(prompt05_case["result"].package_directory, target)
    manifest_path = target / "ontology-package.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["semantic_summary"]["identity_payload_digest"] = "0" * 64

    from kg_mnp.contracts.canonical import semantic_hash
    from kg_mnp.contracts.document_io import deterministic_json_bytes

    preimage = dict(manifest)
    preimage.pop("package_id")
    preimage.pop("content_digest")
    manifest["content_digest"] = semantic_hash(preimage)
    manifest_path.write_bytes(deterministic_json_bytes(manifest))

    payloads = {
        path.relative_to(target).as_posix(): path.read_bytes()
        for path in target.rglob("*")
        if path.is_file()
        and path.name not in {"ontology-package.json", "ontology-package.lock.json"}
    }
    lock = build_package_lock(manifest, payloads)
    (target / "ontology-package.lock.json").write_bytes(deterministic_json_bytes(lock))
    with pytest.raises(PackageError, match="identity"):
        verify_package(target)
