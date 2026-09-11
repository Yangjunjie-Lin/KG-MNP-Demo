"""Non-self-referential ontology package lock."""

from __future__ import annotations

import hashlib
from typing import Any

from zhigou_toolchain.contracts.canonical import semantic_hash
from zhigou_toolchain.contracts.document_io import deterministic_json_bytes

from ..artifacts import media_type_for_path, semantic_sha256
from ..contracts import finalize_artifact


def build_package_lock(manifest: dict[str, Any], payload_files: dict[str, bytes]) -> dict[str, Any]:
    manifest_bytes = deterministic_json_bytes(manifest)
    rows = []
    for path, data in sorted(payload_files.items()):
        if path in {"ontology-package.json", "ontology-package.lock.json"}:
            raise ValueError("manifest and lock are not payload_files")
        rows.append({"path": path, "media_type": media_type_for_path(path), "size_bytes": len(data), "byte_sha256": hashlib.sha256(data).hexdigest(), "semantic_sha256": semantic_sha256(path, data), "role": "PACKAGE_PAYLOAD"})
    core = {"manifest_kind": "KG_MNP_ONTOLOGY_PACKAGE_LOCK", "schema_version": "1.0.0", "package_id": manifest["package_id"], "package_name": manifest["package_name"], "package_version": manifest["package_version"], "manifest_file_sha256": hashlib.sha256(manifest_bytes).hexdigest(), "manifest_semantic_sha256": semantic_hash(manifest), "payload_files": rows, "canonicalization_profile": "KG-MNP RDF Canonical Profile v1"}
    return finalize_artifact(core, id_field="lock_id", urn_kind="ontology-package-lock", contract="ontology-package-lock")
